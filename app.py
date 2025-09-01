import streamlit as st
import pandas as pd
import re, unicodedata

# ------------------------- PAGE / META -------------------------
st.set_page_config(
    page_title="Rhóms Profitability Dashboard",
    page_icon="🧮",
    layout="centered",
)

# ------------------------- GLOBAL STYLES -------------------------
# Dark mode + lime accent + condensed headline stack (Futura-Condensed first, with solid fallbacks)
st.markdown("""
<style>
:root{
  --bg:#0b0f15;
  --panel:#121826;
  --panel-2:#0f1520;
  --text:#e5e7eb;
  --muted:#9aa4b2;
  --border:#1f2937;
  --lime:#A4DB32;
  --lime-weak:#c9f27a33;
  --red:#ef4444;
  --red-soft:#7f1d1d;
  --green:#22c55e;
  --green-soft:#052e16;
}

/* base */
html, body, .block-container{background:var(--bg); color:var(--text);}
.block-container{padding-top:1.6rem; padding-bottom:2rem; max-width:1100px;}
/* headline: Futura Condensed (if installed) -> similar condensed fallbacks */
h1, h2, h3, .hero, .value {
  font-family: "Futura-Condensed", "Futura Condensed", "Impact", "Oswald", "Barlow Condensed", "Arial Narrow", system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, "Helvetica Neue", Arial, "Noto Sans", sans-serif;
}
h1{font-size:2.4rem!important; letter-spacing:.3px; margin:.1rem 0 .8rem}
.caption{color:var(--muted)}

/* grid rows */
.row-4{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:14px 0 10px}
.row-3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:14px 0 10px}
.row-2{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin:14px 0 10px}

/* pills (cards) */
.pill{
  border-radius:14px; background:var(--panel); border:1px solid var(--border);
  padding:16px 18px; box-shadow:0 8px 24px rgba(0,0,0,.25), inset 0 1px 0 rgba(255,255,255,.02);
}
.pill .label{
  font-size:.82rem; color:var(--muted); letter-spacing:.2px; margin-bottom:.25rem; font-weight:600;
}
.pill .value{
  font-weight:900; font-size:2.2rem; line-height:1.05; color:var(--text);
  text-shadow: 0 0 12px rgba(164,219,50,.08);
}
.pill .sub{color:#aab4c2; font-size:.86rem; margin-top:.35rem}

.fxchip{
  display:inline-flex; gap:8px; align-items:center; font-size:.82rem; color:var(--text);
  background:linear-gradient(180deg, #151c28, #0e1420);
  border:1px solid var(--border); padding:6px 10px; border-radius:999px;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,.02);
}
.fxchip .dot{width:8px; height:8px; background:var(--lime); border-radius:999px; box-shadow:0 0 10px var(--lime);}

.hr{height:1px; background:var(--border); margin:12px 0 6px; opacity:.6}

/* STATES: profit */
.pill.positive{ border:1px solid var(--lime); box-shadow:0 0 0 1px var(--lime-weak), 0 8px 24px rgba(0,0,0,.25); }
.pill.positive .value{ color:var(--lime); text-shadow:0 0 16px rgba(164,219,50,.35); }
.pill.negative{ border:1px solid var(--red); background:linear-gradient(180deg, #1b1111, var(--panel)); }
.pill.negative .value{ color:#ff7a7a; text-shadow:0 0 10px rgba(239,68,68,.35); }

/* input panels */
.center{display:flex;justify-content:center;gap:16px;flex-wrap:wrap}
.inputbox{
  min-width:340px; background:var(--panel-2); border:1px dashed var(--border); text-align:center;
}
.inputbox .value{font-size:1.6rem}

/* Streamlit widgets tweaks */
.stSlider > div > div > div > div{ background:var(--lime) !important; }
.stButton>button, .stDownloadButton>button{
  background:var(--panel); color:var(--text); border:1px solid var(--border);
}
.stButton>button:hover, .stDownloadButton>button:hover{
  border-color:var(--lime); color:var(--lime);
}
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
RECURRING_TAG = "Subscription Recurring Order"  # tag to exclude from front-end

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
    tag_col = "Tags" if "Tags" in df.columns else ("Tag" if "Tag" in df.columns else None)
    if tag_col is None:
        return df.copy(), df.iloc[0:0].copy()
    is_rec = df[tag_col].astype(str).str.contains(RECURRING_TAG, case=False, na=False)
    return df.loc[~is_rec].copy(), df.loc[is_rec].copy()

def calc_cogs(df: pd.DataFrame, debug=False):
    if df.empty:
        return 0.0, []
    for c in COUNTRY_COLS:
        if c in df.columns: country_col = c; break
    else: raise ValueError("No shipping country column found in CSV.")

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
    revenue_col = next((c for c in ["Total", "Total Sales", "Total (GBP)", "Total Price"] if c in df.columns), None)
    if revenue_col:
        revenue_gbp = pd.to_numeric(df[revenue_col], errors="coerce").fillna(0).sum()
    elif "Lineitem price" in df.columns:
        qty = pd.to_numeric(df.get("Lineitem quantity", 0), errors="coerce").fillna(0).astype(float)
        price = pd.to_numeric(df["Lineitem price"], errors="coerce").fillna(0).astype(float)
        revenue_gbp = float((price * qty).sum())
    else:
        revenue_gbp = 0.0

    revenue_usd = revenue_gbp * gbp_to_usd
    fees_usd = ((revenue_usd * 0.028 + 0.3) * 1.1) + ((revenue_usd * 0.02) * 1.1)
    net_after_fees_usd = revenue_usd - fees_usd
    return round(revenue_gbp,2), round(revenue_usd,2), round(fees_usd,2), round(net_after_fees_usd,2)

def pill(number, label, sub=None, state="neutral"):
    cls = "pill" + (" positive" if state=="pos" else " negative" if state=="neg" else "")
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    return f'<div class="{cls}"><div class="label">{label}</div><div class="value">{number}</div>{sub_html}</div>'

# ------------------------- UI -------------------------
st.title("Rhóms Profitability Dashboard")
st.caption("Drop your Shopify CSV + Ad Spend. See blended & front-end profitability in one glance.")

# Centered hero inputs
colA, colB = st.columns([1,1])
with colA:
    file = st.file_uploader("Shopify CSV", type=["csv"], label_visibility="visible")
with colB:
    ad_spend_usd = st.number_input("Ad Spend (USD)", value=0.00, min_value=0.00, step=10.00, format="%.2f", label_visibility="visible")

# Details / settings expander (kept dark & minimal)
with st.expander("Details & Settings"):
    fx = st.number_input("GBP → USD rate", value=1.30, step=0.01, format="%.2f")
    show_debug = st.toggle("Show per-order breakdown", value=False)
    st.markdown(f'<span class="fxchip"><span class="dot"></span> FX £→$ = {fx:.2f}</span>', unsafe_allow_html=True)

if 'fx' not in locals(): fx = 1.30
if 'show_debug' not in locals(): show_debug = False

# ------------------------- MAIN CALC -------------------------
if file:
    df = pd.read_csv(file)

    # Split front-end vs recurring
    df_front, df_rec = split_frontend(df)

    # ---- BLENDED ----
    total_cogs_usd, logs = calc_cogs(df, debug=show_debug)
    revenue_gbp, revenue_usd, fees_usd, net_after_fees = calc_revenue_and_fees(df, fx)
    gross_profit = revenue_usd - fees_usd - total_cogs_usd
    overall_profit = gross_profit - ad_spend_usd
    blended_roas = (revenue_usd / ad_spend_usd) if ad_spend_usd > 0 else None

    # ---- FRONT-END (non-recurring) ----
    fe_cogs_usd, _ = calc_cogs(df_front, debug=False)
    fe_rev_gbp, fe_rev_usd, fe_fees_usd, fe_net_after_fees = calc_revenue_and_fees(df_front, fx)
    fe_gross_profit = fe_rev_usd - fe_fees_usd - fe_cogs_usd
    fe_overall_profit = fe_gross_profit - ad_spend_usd
    nc_roas = (fe_rev_usd / ad_spend_usd) if ad_spend_usd > 0 else None

    # Header FX chip
    st.markdown(f'<span class="fxchip"><span class="dot"></span> FX £→$ = {fx:.2f}</span>', unsafe_allow_html=True)
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    # -------- Row 1: BLENDED (4 pills) --------
    state_overall = "pos" if overall_profit > 0 else ("neg" if overall_profit < 0 else "neutral")
    r1 = [
        pill(f"${net_after_fees:,.2f}", "Net Revenue (USD)", sub=f"£{revenue_gbp:,.2f} – after fees"),
        pill(f"${total_cogs_usd:,.2f}", "COGS (USD)"),
        pill(f"${ad_spend_usd:,.2f}", "Ad Spend (USD)"),
        pill(f"${overall_profit:,.2f}" if overall_profit>=0 else f"-${abs(overall_profit):,.2f}",
             "Overall Profit/Loss (USD)", state=state_overall),
    ]
    st.markdown('<div class="row-4">' + "".join(r1) + '</div>', unsafe_allow_html=True)

    # -------- Row 2: FRONT-END (3 pills) --------
    state_fe = "pos" if fe_overall_profit > 0 else ("neg" if fe_overall_profit < 0 else "neutral")
    r2 = [
        pill(f"${fe_net_after_fees:,.2f}", "Net Revenue (USD) — NC", sub=f"£{fe_rev_gbp:,.2f} – after fees"),
        pill(f"${fe_cogs_usd:,.2f}", "COGS (USD) — NC"),
        pill(f"${fe_overall_profit:,.2f}" if fe_overall_profit>=0 else f"-${abs(fe_overall_profit):,.2f}",
             "Profit/Loss (USD) — NC", state=state_fe),
    ]
    st.markdown('<div class="row-3">' + "".join(r2) + '</div>', unsafe_allow_html=True)

    # -------- Row 3: ROAS (2 big pills) --------
    roas_blend_text = f"{blended_roas:,.2f}×" if blended_roas is not None else "–"
    roas_nc_text = f"{nc_roas:,.2f}×" if nc_roas is not None else "–"
    r3 = [
        pill(roas_blend_text, "Blended ROAS", sub="Revenue ÷ Ad Spend", state="pos" if blended_roas and blended_roas>=1 else "neg" if blended_roas else "neutral"),
        pill(roas_nc_text, "NC ROAS", sub="Front-end Revenue ÷ Ad Spend", state="pos" if nc_roas and nc_roas>=1 else "neg" if nc_roas else "neutral"),
    ]
    st.markdown('<div class="row-2">' + "".join(r3) + '</div>', unsafe_allow_html=True)

    # -------- Details Expander (optional) --------
    with st.expander("More details (open if needed)"):
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
        if show_debug and not df.empty:
            st.write("---")
            st.subheader("Per-order COGS breakdown (debug)")
            _, logs_all = calc_cogs(df, debug=True)
            for l in logs_all: st.write(l)

else:
    # onboarding state
    st.markdown('<div class="center">', unsafe_allow_html=True)
    st.markdown('<div class="pill inputbox"><div class="label">Step 1</div><div class="value">Upload Shopify CSV</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="pill inputbox"><div class="label">Step 2</div><div class="value">Enter Ad Spend (USD)</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.caption("Once both are set, your blended and front-end profitability will appear instantly.")
