
import streamlit as st
import pandas as pd
import numpy as np
import io
import re
from dataclasses import dataclass

st.set_page_config(page_title="Gleamont Profitability Dashboard", layout="wide")

st.title("Gleamont Profitability Dashboard")
st.caption("Upload Shopify orders CSV + enter your ad spend to compute profit. Retains the dark style and clipboard TSV export.")

# -----------------------------
# Config: COGS tiers (1/3/5) by country
# -----------------------------
COGS = {
    "United Kingdom": {1: 6.7, 3: 9.9, 5: 12.9},
    "United States":  {1: 6.2, 3: 9.2, 5: 11.8},
    "Canada":         {1: 6.8, 3:10.6, 5: 14.1},
    "Australia":      {1: 6.7, 3:10.1, 5: 13.3},
    "New Zealand":    {1: 7.7, 3:11.2, 5: 14.5},
}

# Map shipping country code to our region name
COUNTRY_CODE_TO_REGION = {
    "GB": "United Kingdom",
    "UK": "United Kingdom",
    "US": "United States",
    "CA": "Canada",
    "AU": "Australia",
    "NZ": "New Zealand",
    # NL/EU handled specially below
}

EU_CODES = {"NL", "EU"}

# Columns that often carry country
COUNTRY_COLS = ["Shipping Country", "Billing Country"]

# Items that we explicitly skip from costing
ZERO_COGS_PHRASES = [
    "shipping protection",
    "route package protection",
    "gift card",
]

BASE_PRODUCT_TOKEN = "gleamont clinical strength internal deodorant"  # normalized token

def normalize_name(s: str) -> str:
    s = s or ""
    s = s.lower()
    # strip [free gift] or similar prefixes
    s = re.sub(r"\[.*?\]", "", s)
    # replace fancy dashes/emdash
    s = s.replace("—", " ").replace("-", " ")
    # normalize misspelling 'deodrant' -> 'deodorant'
    s = s.replace("deodrant", "deodorant")
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def is_base_product(line_name: str) -> bool:
    n = normalize_name(line_name)
    return BASE_PRODUCT_TOKEN in n

def is_zero_cogs(line_name: str) -> bool:
    n = normalize_name(line_name)
    return any(phrase in n for phrase in ZERO_COGS_PHRASES)

@dataclass
class CountryModel:
    S: float  # shipment overhead per order
    U: float  # per-unit cost

_country_model_cache = {}

def fit_country_model(region: str) -> CountryModel:
    # Fit S + U*n using exact points at n=1,3,5
    if region in _country_model_cache:
        return _country_model_cache[region]
    pts = COGS[region]
    xs = np.array([1.0, 3.0, 5.0])
    ys = np.array([pts[1], pts[3], pts[5]], dtype=float)
    A = np.vstack([np.ones_like(xs), xs]).T
    # least squares
    S, U = np.linalg.lstsq(A, ys, rcond=None)[0]
    model = CountryModel(S=float(S), U=float(U))
    _country_model_cache[region] = model
    return model

def compute_cost_for_units(region: str, n_units: int) -> float:
    if n_units <= 0:
        return 0.0
    model = fit_country_model(region)
    return model.S + model.U * n_units

def detect_region_from_row(row: pd.Series) -> (str, bool):
    # Return (region, eu_adjust)
    code = None
    for col in COUNTRY_COLS:
        if col in row and pd.notna(row[col]) and str(row[col]).strip():
            code = str(row[col]).strip().upper()
            break
    if code in EU_CODES:
        return ("United Kingdom", True)  # Use UK base + $1
    if code in COUNTRY_CODE_TO_REGION:
        return (COUNTRY_CODE_TO_REGION[code], False)
    return (None, False)

st.sidebar.header("Inputs")
ad_spend = st.sidebar.number_input("Ad spend (store currency)", min_value=0.0, value=0.0, step=100.0)
processor_fee_pct = st.sidebar.number_input("Payment processor fee % (of revenue)", min_value=0.0, value=0.0, step=0.1)
fixed_fee_per_order = st.sidebar.number_input("Fixed fee per order (store currency)", min_value=0.0, value=0.0, step=0.1)

uploaded = st.file_uploader("Upload Shopify orders CSV", type=["csv"])

if uploaded is not None:
    df = pd.read_csv(uploaded)
    # Build per-order aggregates
    # Determine units of base product per order (including FREE GIFT variant) and revenue
    df["__is_base"] = df["Lineitem name"].astype(str).map(is_base_product)
    df["__is_zero"] = df["Lineitem name"].astype(str).map(is_zero_cogs)

    # Revenue per order (take 'Total' once per order)
    order_rev = df.groupby("Name")["Total"].first()

    # Units for base product (sum ALL base and gift variants)
    units = df[df["__is_base"]].groupby("Name")["Lineitem quantity"].sum().rename("units")
    units = units.reindex(order_rev.index).fillna(0).astype(int)

    # Country/Region per order
    region_info = []
    for name, sub in df.groupby("Name"):
        row0 = sub.iloc[0]
        region, eu_adj = detect_region_from_row(row0)
        region_info.append((name, region, eu_adj))
    region_df = pd.DataFrame(region_info, columns=["Name", "region", "eu_adjust"]).set_index("Name")
    region_df = region_df.reindex(order_rev.index)

    # Tags per order
    tags = df.groupby("Name")["Tags"].first().fillna("")
    is_recurring = tags.str.contains("Subscription Recurring Order", case=False, na=False)
    is_first = tags.str.contains("Subscription First Order", case=False, na=False)

    # Compute COGS per order
    costs = []
    warnings = []
    for name in order_rev.index:
        reg = region_df.at[name, "region"]
        eu_adj = bool(region_df.at[name, "eu_adjust"])
        u = int(units.at[name]) if name in units.index else 0
        cost = 0.0
        warn = ""
        if u > 0 and reg in COGS:
            cost = compute_cost_for_units(reg, u)
        elif u > 0 and reg is None:
            warn = "Unmapped country"
        elif u == 0:
            cost = 0.0
        if eu_adj and u > 0:
            cost += 1.0
            warn = (warn + " | " if warn else "") + "EU/NL +$1 applied"
        costs.append(cost)
        warnings.append(warn)

    result = pd.DataFrame({
        "Order": order_rev.index,
        "Region": region_df["region"].values,
        "Units (incl. gifts)": units.values,
        "Revenue": order_rev.values,
        "COGS": costs,
        "Warning": warnings,
        "Tags": tags.reindex(order_rev.index).values,
        "Is Recurring": is_recurring.reindex(order_rev.index).values,
        "Is First Order": is_first.reindex(order_rev.index).values,
    }).set_index("Order")

    # Fees
    result["Proc Fees"] = (processor_fee_pct/100.0) * result["Revenue"] + fixed_fee_per_order

    # Split NC vs Recurring (use First Order to represent NC)
    nc_mask = result["Is First Order"]
    rec_mask = result["Is Recurring"]

    # Summaries
    rev_total = float(result["Revenue"].sum())
    cogs_total = float(result["COGS"].sum())
    fees_total = float(result["Proc Fees"].sum())

    rev_nc = float(result.loc[nc_mask, "Revenue"].sum())
    cogs_nc = float(result.loc[nc_mask, "COGS"].sum())
    fees_nc = float(result.loc[nc_mask, "Proc Fees"].sum())

    # Blended metrics (all orders)
    blended_profit = rev_total - cogs_total - fees_total - ad_spend
    blended_margin = blended_profit / rev_total if rev_total else 0.0
    blended_roas = rev_total / ad_spend if ad_spend else np.nan

    # Front-end NC metrics (ad spend applied here)
    nc_profit = rev_nc - cogs_nc - fees_nc - ad_spend
    nc_margin = nc_profit / rev_nc if rev_nc else 0.0
    nc_roas = rev_nc / ad_spend if ad_spend else np.nan

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Orders", len(result))
    col2.metric("Revenue (Total)", f"{rev_total:,.2f}")
    col3.metric("Blended Profit", f"{blended_profit:,.2f}")
    col4.metric("Blended ROAS", f"{blended_roas:,.2f}" if not np.isnan(blended_roas) else "—")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("NC Orders", int(nc_mask.sum()))
    col2.metric("NC Revenue", f"{rev_nc:,.2f}")
    col3.metric("NC Profit", f"{nc_profit:,.2f}")
    col4.metric("NC ROAS", f"{nc_roas:,.2f}" if not np.isnan(nc_roas) else "—")

    st.subheader("Per-order reconciliation")
    st.dataframe(result[["Region","Units (incl. gifts)","Revenue","COGS","Proc Fees","Warning","Tags"]])

    # Prepare TSV for clipboard / export
    st.subheader("Copy row for P&L")
    pnl = {
        "Revenue_Total": round(rev_total, 2),
        "Ad_Spend": round(ad_spend, 2),
        "COGS_Total": round(cogs_total, 2),
        "Fees_Total": round(fees_total, 2),
        "Blended_Profit": round(blended_profit, 2),
        "Blended_ROAS": round(blended_roas, 3) if not np.isnan(blended_roas) else "",
        "NC_Revenue": round(rev_nc, 2),
        "NC_COGS": round(cogs_nc, 2),
        "NC_Fees": round(fees_nc, 2),
        "NC_Profit": round(nc_profit, 2),
        "NC_ROAS": round(nc_roas, 3) if not np.isnan(nc_roas) else "",
        "Orders": int(len(result)),
        "NC_Orders": int(nc_mask.sum()),
    }
    tsv = "\t".join(map(str, pnl.values()))
    st.code("\t".join(pnl.keys()) + "\n" + tsv, language="text")

    st.download_button("Download P&L TSV", data=tsv, mime="text/tab-separated-values", file_name="gleamont_pnl.tsv")

else:
    st.info("Upload a Shopify orders CSV to begin.")
