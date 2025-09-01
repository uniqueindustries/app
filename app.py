import streamlit as st
import pandas as pd
import re, unicodedata

# ------------------------- PAGE / THEME -------------------------
st.set_page_config(page_title="Rhóms Profitability Dashboard", page_icon="🧮", layout="centered")

# Minimal CSS (pills, rows, color states)
st.markdown("""
<style>
.block-container{padding-top:1.6rem;padding-bottom:2rem;max-width:980px;}
h1{font-size:2.0rem!important;margin:.25rem 0 .6rem}
.caption{color:#64748b}

/* grid rows */
.row-4{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:10px 0 12px}
.row-3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:10px 0 12px}
.row-2{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin:10px 0 12px}

.pill{
  border-radius:14px;background:#fff;border:1px solid #e5e7eb;
  padding:14px 16px;box-shadow:0 1px 2px rgba(0,0,0,.03);
}
.pill .label{font-size:.78rem;color:#6b7280;letter-spacing:.2px;margin-bottom:.15rem}
.pill .value{font-weight:800;font-size:1.65rem;line-height:1.15}
.pill .sub{color:#94a3b8;font-size:.8rem;margin-top:.25rem}

/* states */
.pill.positive{border:1px solid #86efac;background:#f0fdf4}
.pill.positive .value{color:#15803d}
.pill.negative{border:1px solid #fca5a5;background:#fef2f2}
.pill.negative .value{color:#dc2626}

/* fx chip */
.fxchip{
  display:inline-flex;gap:6px;align-items:center;font-size:.78rem;color:#475569;
  background:#f1f5f9;border:1px solid #e2e8f0;padding:4px 8px;border-radius:999px;
}
.hr{height:1px;background:#f1f5f9;margin:10px 0 6px}
.center{display:flex;justify-content:center;gap:12px}
.inputbox{min-width:320px}
</style>
""", unsafe_allow_html=True)

# ------------------------- CONFIG / MAPPINGS -------------------------
MAIN_COST_TABLE = {
    "United States": {1: 8.00, 2: 10.50, 3: 13.00, 4: 15.50, 5: 18.00, 6: 20.50},
    "United Kingdom": {1: 5.50, 2: 8.00, 3: 10.00, 4: 12.00, 5: 14.00, 6: 16.00},
    "Canada": {1: 6.50, 2: 9.00, 3: 11.50, 4: 14.50, 5: 17.00, 6: 21.00},
}
EXTRA_COSTS = {
    "irritation proof razor": {"United States": 5.50, "United Kingdom": 4.50, "Canada": 5.50},
    "razor close trimmer": {"United Kingdom": 10.50},
    "shaving foam": {"United States": 6.00, "United Kingdom": 5.00, "Canada": 6.00},
}
ZERO_COGS_KEYS = ["express shipping","dermatologist guide","shipping protection"]
COUNTRY_MAP = {
    "GB":"United Kingdom","UK":"United Kingdom","United Kingdom":"United Kingdom",
    "CA":"Canada","CAN":"Canada","Canada":"Canada",
    "US":"United States","USA":"United States","United States":"United States",
}
COUNTRY_COLS = ["Shipping Country","Shipping Country Code","Shipping Address Country Code","Shipping Address Country"]
RECURRING_TAG = "Subscription Recurring Order"  # non-front-end marker

# ------------------------- HELPERS -------------------------
def norm(s):
    s = str(s)
    s = unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode("ascii").lower()
    s = re.sub(r"[\W_]+"," ", s)
    return " ".join(s.split())

def is_main(n): return "smoothing solution" in n or "smoothing serum" in n
def zero_cogs(n): return any(k in n for k in ZERO_COGS_KEYS)
def extra_key(n):
    for key in EXTRA_COSTS:
        if key in n: return key
    return None

def split_frontend(df: pd.DataFrame):
    """Return (front_end_df, recurring_df) based on Tags/Tag."""
    tag_col = "Tags" if "Tags" in df.columns else ("Tag" if "Tag" in df.columns else None)
    if tag_col is None:
        return df.copy(), df.iloc[0:0].copy()
    is_rec = df[tag_col].astype(str).str.contains(RECURRING_TAG, case=False, na=False)
    return df.loc[~is_rec].copy(), df.loc[is_rec].copy()

def calc_cogs(df: pd.DataFrame, debug=False):
    if df.empty: 
        return 0.0, []
    # find country col
    for c in COUNTRY_COLS:
        if c in df.columns: country_col = c; break
    else: raise ValueError("No shipping country column found in CSV.")
    # prep
    df = df.copy()
    df["qty"] = pd.to_numeric(df["Lineitem quantity"], errors="coerce").fillna(0).astype(int)
    df["Country"] = df[country_col].map(COUNTRY_MAP).fillna(df[country_col])

    total=0.0; logs=[]
    for oid, grp in df.groupby("Name"):
        country = str(grp["Country"].iloc[0]).strip()
        main_qty=0; extras_cost=0.0
        for _,r in grp.iterrows():
            n=norm(r["Lineitem name"]); q=int(r["qty"])
            if q==0 or zero_cogs(n): continue
            if is_main(n): main_qty += q; continue
            ek = extra_key(n)
            if ek:
                extras_cost += EXTRA_COSTS[ek].get(country,0) * q
            else:
                logs.append(f"{oid}: Unmapped {r['Lineitem name']}")
        main_cost = MAIN_COST_TABLE.get(country,{}).get(main_qty,0) if main_qty else 0
        total += main_cost + extras_cost
        if debug:
            logs.append(f"{oid} · {country} · main {main_qty}u = ${main_cost:.2f} · extras ${extras_cost:.2f}")
    return round(total,2), logs

def calc_revenue_and_fees(df: pd.DataFrame, gbp_to_usd: float):
    if df.empty:
        return 0.0, 0.0, 0.0, 0.0
    # Revenue (GBP) column detection
    revenue_col = next((c for c in ["Total", "Total Sales", "Total (GBP)", "Total Price"] if c in df.columns), None)
    if revenue_col:
        revenue_gbp = pd.to_numeric(df[revenue_col], errors="coerce").fillna(0).sum()
    elif "Lineitem price" in df.columns:
        # fallback: line price * qty
        qty = pd.to_numeric(df.get("Lineitem quantity", 0), errors="coerce").fillna(0).astype(float)
        price = pd.to_numeric(df["Lineitem price"], errors="coerce").fillna(0).astype(float)
        revenue_gbp = float((price * qty).sum())
    else:
        revenue_gbp = 0.0

    revenue_usd = revenue_gbp * gbp_to_usd
    fees_usd = ((revenue_usd * 0.028 + 0.3) * 1.1) + ((revenue_usd * 0.02) * 1.1)  # your formula
    net_after_fees_usd = revenue_usd - fees_usd
    return round(revenue_gbp,2), round(revenue_usd,2), round(fees_usd,2), round(net_after_fees_usd,2)

def pill(number, label, sub=None, state="neutral"):
    cls = "pill" + (" positive" if state=="pos" else " negative" if state=="neg" else "")
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    return f'<div class="{cls}"><div class="label">{label}</div><div class="value">{number}</div>{sub_html}</div>'

# ------------------------- HEADER + INPUTS -------------------------
st.title("Rhóms Profitability Dashboard")
st.caption("Upload a Shopify orders CSV and enter Ad Spend. Results show blended and front-end profitability at a glance.")

# Centered inputs (CSV + Ad Spend)
c1, c2 = st.columns([1,1])
with c1: 
    file = st.file_uploader("Shopify CSV", type=["csv"], label_visibility="visible")
with c2:
    ad_spend_usd = st.number_input("Ad Spend (USD)", value=0.00, min_value=0.00, step=10.00, format="%.2f", label_visibility="visible")

# Optional controls in expander
with st.expander("More details & settings"):
    fx = st.number_input("GBP → USD rate", value=1.30, step=0.01, format="%.2f")
    show_debug = st.toggle("Show per-order breakdown", value=False)
    st.markdown('<div class="fxchip">Using FX £→$ = {:.2f}</div>'.format(fx), unsafe_allow_html=True)

# Default FX if user never opens expander
if 'fx' not in locals():
    fx = 1.30
if 'show_debug' not in locals():
    show_debug = False

# ------------------------- MAIN -------------------------
if file:
    df = pd.read_csv(file)

    # Split front-end vs recurring
    df_front, df_rec = split_frontend(df)
    total_orders = df["Name"].nunique() if "Name" in df.columns else len(df.drop_duplicates())

    # ---- BLENDED (all orders) ----
    total_cogs_usd, logs = calc_cogs(df, debug=show_debug)
    revenue_gbp, revenue_usd, fees_usd, net_after_fees = calc_revenue_and_fees(df, fx)
    gross_profit = revenue_usd - fees_usd - total_cogs_usd
    overall_profit = gross_profit - ad_spend_usd
    blended_roas = (revenue_usd / ad_spend_usd) if ad_spend_usd > 0 else None

    # ---- FRONT-END (non-recurring) ----
    fe_cogs_usd, _ = calc_cogs(df_front, debug=False)
    fe_rev_gbp, fe_rev_usd, fe_fees_usd, fe_net_after_fees = calc_revenue_and_fees(df_front, fx)
    fe_gross_profit = fe_rev_usd - fe_fees_usd - fe_cogs_usd
    fe_overall_profit = fe_gross_profit - ad_spend_usd  # all ad spend attributed to acquisition
    nc_roas = (fe_rev_usd / ad_spend_usd) if ad_spend_usd > 0 else None

    # Header chip (FX)
    st.markdown(f'<div class="fxchip">FX £→$ = {fx:.2f}</div>', unsafe_allow_html=True)
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    # ---------------- Row 1: BLENDED (4 pills) ----------------
    state_overall = "pos" if overall_profit > 0 else ("neg" if overall_profit < 0 else "neutral")
    r1 = [
        pill(f"${net_after_fees:,.2f}", "Net Revenue (USD)", sub=f"£{revenue_gbp:,.2f} – fees"),
        pill(f"${total_cogs_usd:,.2f}", "COGS (USD)"),
        pill(f"${ad_spend_usd:,.2f}", "Ad Spend (USD)"),
        pill(f"${overall_profit:,.2f}" if overall_profit>=0 else f"-${abs(overall_profit):,.2f}",
             "Overall Profit/Loss (USD)", state=state_overall),
    ]
    st.markdown('<div class="row-4">' + "".join(r1) + '</div>', unsafe_allow_html=True)

    # ---------------- Row 2: FRONT-END (3 pills) ----------------
    state_fe = "pos" if fe_overall_profit > 0 else ("neg" if fe_overall_profit < 0 else "neutral")
    r2 = [
        pill(f"${fe_net_after_fees:,.2f}", "Net Revenue (USD) — NC", sub=f"£{fe_rev_gbp:,.2f} – fees"),
        pill(f"${fe_cogs_usd:,.2f}", "COGS (USD) — NC"),
        pill(f"${fe_overall_profit:,.2f}" if fe_overall_profit>=0 else f"-${abs(fe_overall_profit):,.2f}",
             "Profit/Loss (USD) — NC", state=state_fe),
    ]
    st.markdown('<div class="row-3">' + "".join(r2) + '</div>', unsafe_allow_html=True)

    # ---------------- Row 3: ROAS (2 big pills) ----------------
    roas_blend_text = f"{blended_roas:,.2f}×" if blended_roas is not None else "–"
    roas_nc_text = f"{nc_roas:,.2f}×" if nc_roas is not None else "–"
    r3 = [
        pill(roas_blend_text, "Blended ROAS", sub="Revenue ÷ Ad Spend"),
        pill(roas_nc_text, "NC ROAS", sub="Front-end Revenue ÷ Ad Spend"),
    ]
    st.markdown('<div class="row-2">' + "".join(r3) + '</div>', unsafe_allow_html=True)

    # ---------------- Details Expander ----------------
    with st.expander("More details (open if you need them)"):
        st.write(f"**Orders uploaded:** {total_orders}")
        st.write(f"**Revenue (GBP):** £{revenue_gbp:,.2f}")
        st.write(f"**Revenue (USD):** ${revenue_usd:,.2f}")
        st.write(f"**Shopify Fees (USD):** ${fees_usd:,.2f}")
        st.write(f"**Net after Fees (USD):** ${net_after_fees:,.2f}")
        st.write(f"**Gross Profit (USD):** ${gross_profit:,.2f}")
        st.write("---")
        st.write(f"**Front-end Revenue (GBP):** £{fe_rev_gbp:,.2f}")
        st.write(f"**Front-end Revenue (USD):** ${fe_rev_usd:,.2f}")
        st.write(f"**Front-end Fees (USD):** ${fe_fees_usd:,.2f}")
        st.write(f"**Front-end Net after Fees (USD):** ${fe_net_after_fees:,.2f}")
        st.write(f"**Front-end Gross Profit (USD):** ${fe_gross_profit:,.2f}")
        if show_debug:
            st.write("---")
            st.subheader("Per-order COGS breakdown (debug)")
            _, logs_all = calc_cogs(df, debug=True)
            for l in logs_all: st.write(l)

else:
    # guide when nothing uploaded
    st.markdown('<div class="center">', unsafe_allow_html=True)
    st.markdown('<div class="pill inputbox"><div class="label">Step 1</div><div class="value">Upload Shopify CSV</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="pill inputbox"><div class="label">Step 2</div><div class="value">Enter Ad Spend (USD)</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.caption("Once both are set, your blended and front-end profitability will appear instantly, without scrolling.")
