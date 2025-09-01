import streamlit as st
import pandas as pd
import re, unicodedata

# ------------------------- PAGE / THEME -------------------------
st.set_page_config(page_title="Rhóms COGS Calculator", page_icon="🧮", layout="centered")

# Minimal CSS “cards”
st.markdown("""
<style>
.block-container{padding-top:2rem;padding-bottom:2.5rem;}
h1{font-size:2.1rem!important;margin-bottom:.4rem}
.caption{color:#6b7280}

.pill{
  border-radius:14px; background:#fff; border:1px solid #e5e7eb;
  padding:14px 16px; box-shadow:0 1px 2px rgba(0,0,0,.03);
}
.pill .label{font-size:.78rem; color:#6b7280; letter-spacing:.2px; margin-bottom:.15rem}
.pill .value{font-weight:800; font-size:1.6rem; line-height:1.15}
.small{color:#94a3b8; font-size:.8rem; margin-top:.35rem}

/* NEGATIVE state */
.pill.negative { border: 1px solid #fca5a5; background: #fef2f2; }
.pill.negative .value { color: #dc2626; }

/* POSITIVE state */
.pill.positive { border: 1px solid #86efac; background: #f0fdf4; }
.pill.positive .value { color: #15803d; }

.row{display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin:10px 0 16px}
.fxchip{
  display:inline-flex; gap:6px; align-items:center; font-size:.78rem; color:#475569;
  background:#f1f5f9; border:1px solid #e2e8f0; padding:4px 8px; border-radius:999px;
}
.hr{height:1px; background:#f1f5f9; margin:10px 0 6px}
</style>
""", unsafe_allow_html=True)



st.title("Rhóms COGS Calculator")
st.caption("Upload a Shopify orders CSV for any date. I’ll output **Total COGS (USD)**, **Revenue (GBP & USD)**, and **Shopify Fees (USD)**.")

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

def calc_cogs(df: pd.DataFrame, debug=False):
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
    revenue_col_candidates = ["Total", "Total Sales", "Total (GBP)", "Total Price"]
    revenue_col = next((c for c in revenue_col_candidates if c in df.columns), None)
    if revenue_col:
        revenue_gbp = pd.to_numeric(df[revenue_col], errors="coerce").fillna(0).sum()
    elif "Lineitem price" in df.columns:
        revenue_gbp = (pd.to_numeric(df["Lineitem price"], errors="coerce").fillna(0) *
                       pd.to_numeric(df.get("qty", 0), errors="coerce").fillna(0)).sum()
    else:
        revenue_gbp = 0.0

    revenue_usd = revenue_gbp * gbp_to_usd
    # Shopify fee formula (on USD revenue)
    fees_usd = ((revenue_usd * 0.028 + 0.3) * 1.1) + ((revenue_usd * 0.02) * 1.1)
    return round(revenue_gbp,2), round(revenue_usd,2), round(fees_usd,2)

# ------------------------- FRONT-END SPLIT -------------------------
RECURRING_TAG = "Subscription Recurring Order"  # provided by you

def split_frontend(df: pd.DataFrame, recurring_tag: str = RECURRING_TAG):
    """
    Returns (df_frontend, df_recurring) based on Tags/Tag column.
    If no tag column exists, treat everything as front-end (non-recurring).
    """
    tag_col = "Tags" if "Tags" in df.columns else ("Tag" if "Tag" in df.columns else None)
    if tag_col is None:
        return df.copy(), df.iloc[0:0].copy()  # no tags -> everything treated as front-end

    tags = df[tag_col].astype(str)
    is_recurring = tags.str.contains(recurring_tag, case=False, na=False)
    return df.loc[~is_recurring].copy(), df.loc[is_recurring].copy()


# ------------------------- SIDEBAR CONTROLS -------------------------
with st.sidebar:
    st.subheader("Settings")
    fx = st.number_input("GBP → USD rate", value=1.30, step=0.01, format="%.2f",
                         help="Revenue in your CSV is GBP; COGS table is USD. Default 1.30.")
    show_debug = st.toggle("Show per-order breakdown", value=False)
    st.caption("Change the FX rate if needed. Debug shows per-order COGS.")

    # NEW — Ad spend (USD)
    ad_spend_usd = st.number_input("Ad spend (USD)", value=0.00, min_value=0.00, step=10.00, format="%.2f",
                                   help="Total paid media spend for the uploaded period.")
  

# ------------------------- MAIN UI -------------------------
file = st.file_uploader("Upload Shopify CSV", type=["csv"])

if file:
    df = pd.read_csv(file)

    # Split: front-end (exclude recurring) vs recurring
    df_front, df_rec = split_frontend(df)

    # Totals (orders count) for context
    total_orders = df["Name"].nunique()
    front_orders = df_front["Name"].nunique()

    
    total_cogs_usd, logs = calc_cogs(df, debug=show_debug)
    revenue_gbp, revenue_usd, fees_usd = calc_revenue_and_fees(df, fx)
    net_after_fees = max(revenue_usd - fees_usd, 0)  # just a display nicety
    gross_profit = max(revenue_usd - fees_usd - total_cogs_usd, 0)

    overall_profit = gross_profit - ad_spend_usd
    roas = (revenue_usd / ad_spend_usd) if ad_spend_usd > 0 else None

    # ---- FRONT-END (non-recurring) ----
    fe_cogs_usd, _ = calc_cogs(df_front, debug=False)
    fe_rev_gbp, fe_rev_usd, fe_fees_usd = calc_revenue_and_fees(df_front, fx)
    fe_net_after_fees = fe_rev_usd - fe_fees_usd
    fe_gross_profit = fe_rev_usd - fe_fees_usd - fe_cogs_usd

    # Ad spend is for acquisition, so attribute ALL ad spend to front-end by default
    fe_overall_profit = fe_gross_profit - ad_spend_usd
    fe_roas = (fe_rev_usd / ad_spend_usd) if ad_spend_usd > 0 else None


    # --- KPI pills layout ---
    st.markdown(f'<span class="fxchip">FX £→$ = {fx:.2f}</span>', unsafe_allow_html=True)
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    
    # Row 1: Revenue, Fees, COGS
    st.markdown('<div class="row">', unsafe_allow_html=True)
    st.markdown(f'''
    <div class="pill">
      <div class="label">Revenue (USD)</div>
      <div class="value">${revenue_usd:,.2f}</div>
      <div class="small">£{revenue_gbp:,.2f}</div>
    </div>''', unsafe_allow_html=True)
    st.markdown(f'''
    <div class="pill">
      <div class="label">Shopify Fees (USD)</div>
      <div class="value">${fees_usd:,.2f}</div>
    </div>''', unsafe_allow_html=True)
    st.markdown(f'''
    <div class="pill">
      <div class="label">Total COGS (USD)</div>
      <div class="value">${total_cogs_usd:,.2f}</div>
    </div>''', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Row 2: Net after Fees, Gross Profit, Ad Spend
    st.markdown('<div class="row">', unsafe_allow_html=True)
    st.markdown(f'''
    <div class="pill"><div class="label">Net after Fees (USD)</div>
    <div class="value">${(revenue_usd - fees_usd):,.2f}</div>
    <div class="small">Revenue USD – Fees</div></div>''', unsafe_allow_html=True)
    st.markdown(f'''
    <div class="pill"><div class="label">Gross Profit (USD)</div>
    <div class="value">${gross_profit:,.2f}</div>
    <div class="small">Revenue USD – Fees – COGS</div></div>''', unsafe_allow_html=True)
    st.markdown(f'''
    <div class="pill"><div class="label">Ad Spend (USD)</div>
    <div class="value">${ad_spend_usd:,.2f}</div></div>''', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Row 3: Overall Profit (red if negative), ROAS
    if overall_profit > 0:
        profit_class = "pill positive"
        profit_value = f"${overall_profit:,.2f}"
    elif overall_profit < 0:
        profit_class = "pill negative"
        profit_value = f"-${abs(overall_profit):,.2f}"
    else:
        profit_class = "pill"
        profit_value = "$0.00"


    # ---------- FRONT-END (Non-Recurring) ----------
    st.markdown("### Front-end Profitability (Non-Recurring)")
    st.caption(f"Excludes orders where Tags contain **“{RECURRING_TAG}”** · "
               f"{front_orders}/{total_orders} orders in this upload")

    # Row FE-1: Revenue, Fees, COGS
    st.markdown('<div class="row">', unsafe_allow_html=True)
    st.markdown(f'''
    <div class="pill">
      <div class="label">Revenue (USD)</div>
      <div class="value">${fe_rev_usd:,.2f}</div>
      <div class="small">£{fe_rev_gbp:,.2f}</div>
    </div>''', unsafe_allow_html=True)
    st.markdown(f'''
    <div class="pill">
      <div class="label">Shopify Fees (USD)</div>
      <div class="value">${fe_fees_usd:,.2f}</div>
    </div>''', unsafe_allow_html=True)
    st.markdown(f'''
    <div class="pill">
      <div class="label">Total COGS (USD)</div>
      <div class="value">${fe_cogs_usd:,.2f}</div>
    </div>''', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Row FE-2: Net after Fees, Gross Profit, Ad Spend (same input)
    st.markdown('<div class="row">', unsafe_allow_html=True)
    st.markdown(f'''
    <div class="pill"><div class="label">Net after Fees (USD)</div>
    <div class="value">${fe_net_after_fees:,.2f}</div>
    <div class="small">Revenue USD – Fees</div></div>''', unsafe_allow_html=True)
    st.markdown(f'''
    <div class="pill"><div class="label">Gross Profit (USD)</div>
    <div class="value">${fe_gross_profit:,.2f}</div>
    <div class="small">Revenue USD – Fees – COGS</div></div>''', unsafe_allow_html=True)
    st.markdown(f'''
    <div class="pill"><div class="label">Ad Spend (USD)</div>
    <div class="value">${ad_spend_usd:,.2f}</div>
    <div class="small">Assumed fully allocated to front-end</div></div>''', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Row FE-3: Overall Profit (colored), ROAS
    fe_profit_class = "pill positive" if fe_overall_profit > 0 else ("pill negative" if fe_overall_profit < 0 else "pill")
    fe_profit_value = (
        f"${fe_overall_profit:,.2f}" if fe_overall_profit >= 0 else f"-${abs(fe_overall_profit):,.2f}"
    )

    st.markdown('<div class="row">', unsafe_allow_html=True)
    st.markdown(f'''
    <div class="{fe_profit_class}">
      <div class="label">Overall Profit (USD)</div>
      <div class="value">{fe_profit_value}</div>
      <div class="small">Front-end Gross Profit – Ad Spend</div>
    </div>''', unsafe_allow_html=True)

    if fe_roas is not None:
        st.markdown(f'''
        <div class="pill"><div class="label">ROAS (Front-end)</div>
        <div class="value">{fe_roas:,.2f}×</div>
        <div class="small">Front-end Revenue ÷ Ad Spend</div></div>''', unsafe_allow_html=True)
    else:
        st.markdown('''
        <div class="pill"><div class="label">ROAS (Front-end)</div>
        <div class="value">–</div>
        <div class="small">Set Ad Spend to see ROAS</div></div>''', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


    
    st.markdown('<div class="row">', unsafe_allow_html=True)
    st.markdown(f'''
    <div class="{profit_class}">
      <div class="label">Overall Profit (USD)</div>
      <div class="value">{profit_value}</div>
      <div class="small">Gross Profit – Ad Spend</div>
    </div>''', unsafe_allow_html=True)
    
    if roas is not None:
        st.markdown(f'''
        <div class="pill"><div class="label">ROAS</div>
        <div class="value">{roas:,.2f}×</div>
        <div class="small">Revenue ÷ Ad Spend</div></div>''', unsafe_allow_html=True)
    else:
        st.markdown('''
        <div class="pill"><div class="label">ROAS</div>
        <div class="value">–</div>
        <div class="small">Set Ad Spend to see ROAS</div></div>''', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Debug log
    if show_debug and logs:
        st.markdown("#### Breakdown")
        for l in logs:
            st.write(l)



else:
    st.info("Drag a Shopify CSV above to calculate COGS, revenue, and fees.")

