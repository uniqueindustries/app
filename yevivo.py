import streamlit as st
import pandas as pd
import re, unicodedata

# ------------------------- PAGE / META -------------------------
st.set_page_config(
    page_title="Yevivo Profitability Dashboard",
    page_icon="🧮",
    layout="centered",
)

# ------------------------- GLOBAL STYLES -------------------------
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
}

/* Base layout / typography */
html, body, .block-container{background:var(--bg); color:var(--text);}
.block-container{padding-top:1.6rem; padding-bottom:2rem; max-width:1100px;}
h1{font-size:2.4rem!important; letter-spacing:.3px; margin:.1rem 0 .8rem}
.caption{color:var(--muted)}

/* Grid rows for KPI pills */
.row-4{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:14px 0 10px}
.row-3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:14px 0 10px}
.row-2{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin:14px 0 10px}

/* KPI pills */
.pill{
  border-radius:14px; background:var(--panel); border:1px solid var(--border);
  padding:16px 18px; box-shadow:0 8px 24px rgba(0,0,0,.25), inset 0 1px 0 rgba(255,255,255,.02);
}
.pill .label{font-size:.82rem; color:var(--muted); letter-spacing:.2px; margin-bottom:.25rem; font-weight:600;}
.pill .value{font-weight:900; font-size:2.2rem; line-height:1.05; color:var(--text);}
.pill .sub{color:#aab4c2; font-size:.86rem; margin-top:.35rem}
.pill.positive{ border:1px solid var(--lime); box-shadow:0 0 0 1px var(--lime-weak), 0 8px 24px rgba(0,0,0,.25); }
.pill.positive .value{ color:var(--lime); }
.pill.negative{ border:1px solid var(--red); background:linear-gradient(180deg, #1b1111, var(--panel)); }
.pill.negative .value{ color:#ff7a7a; }

/* FX / info chips */
.fxchip{
  display:inline-flex; gap:8px; align-items:center; font-size:.82rem; color:var(--text);
  background:linear-gradient(180deg, #151c28, #0e1420);
  border:1px solid var(--border); padding:6px 10px; border-radius:999px;
}
.fxchip .dot{width:8px; height:8px; background:var(--lime); border-radius:999px; box-shadow:0 0 10px var(--lime);}
.hr{height:1px; background:var(--border); margin:12px 0 6px; opacity:.6}

/* ===== HERO INPUTS (lime, huge, glowing) ===== */
.hero-pil{
  border-radius:18px; background:var(--panel); border:1px solid var(--border);
  box-shadow:0 10px 28px rgba(0,0,0,.35), 0 0 0 1px rgba(255,255,255,.03), 0 0 20px rgba(164,219,50,.10);
  padding:18px; transition:box-shadow .2s, border-color .2s;
}
.hero-pil:hover{
  border-color: var(--lime);
  box-shadow:0 12px 32px rgba(0,0,0,.45), 0 0 0 1px rgba(164,219,50,.25), 0 0 28px rgba(164,219,50,.20);
}
.hero-label{font-size:1rem; font-weight:800; color:var(--muted); margin:0 0 6px 2px;}
.hero-pil .big{ font-size:1.1rem; }

/* File uploader */
.hero-pil [data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"]{
  background:linear-gradient(180deg,#151c28,#0e1420);
  border:1px dashed var(--lime); border-radius:14px;
  padding:18px; box-shadow: inset 0 0 0 1px rgba(164,219,50,.12), 0 0 16px rgba(164,219,50,.10);
}
.hero-pil [data-testid="stFileUploader"] button{
  border:1px solid var(--lime); color:var(--text); background:transparent;
}
.hero-pil [data-testid="stFileUploader"] button:hover{ background: rgba(164,219,50,.08); }

/* Number input */
.hero-pil [data-testid="stNumberInput"] > div > div{
  background:linear-gradient(180deg,#151c28,#0e1420);
  border:1px solid var(--lime); border-radius:14px;
  box-shadow: inset 0 0 0 1px rgba(164,219,50,.12), 0 0 16px rgba(164,219,50,.10);
}
.hero-pil [data-testid="stNumberInput"] input{
  color:var(--text); font-size:1.6rem; font-weight:900; padding:16px 14px;
}
.hero-pil [data-testid="stNumberInput"] svg{ color:var(--text); }
.hero-pil .stFileUploader, .hero-pil .stNumberInput{ margin-top:6px; }

/* chip row */
.chips{display:flex; gap:10px; align-items:center; flex-wrap:wrap}

/* date chip */
.datechip{
  display:inline-flex; gap:8px; align-items:center; font-size:.82rem; color:var(--text);
  background:linear-gradient(180deg, #151c28, #0e1420);
  border:1px solid var(--border); padding:6px 10px; border-radius:999px;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,.02);
}
.datechip .cal{width:10px; height:10px; background:var(--lime); border-radius:2px;
  box-shadow:0 0 10px rgba(164,219,50,.6); display:inline-block; position:relative}
.datechip .cal:before{
  content:""; position:absolute; left:-2px; top:-2px; width:14px; height:3px;
  background:var(--lime); border-radius:3px; opacity:.9;
}

[data-baseweb="slider"] div[role="slider"]{ background: var(--lime) !important; }
[data-baseweb="slider"] div[data-testid="stSliderThumbValue"]{ color: var(--text) !important; }
</style>
""", unsafe_allow_html=True)

# ------------------------- CONFIG / MAPPINGS -------------------------
# YEVIVO MAIN PRODUCT COGS (USD) – from your screenshots:
# Australia: 1pc=8, 2pc=10.3, 3pc=12.9, 4pc=15.3
# UK:        1pc=6.2, 2pc=8.8, 3pc=11.3, 4pc=13.8
# 5+ units are extrapolated using the step between tiers 3 and 4.

MAIN_COST_TABLE = {
    "Australia": {
        1: 8.0,
        2: 10.3,
        3: 12.9,
        4: 15.3,
    },
    "United Kingdom": {
        1: 6.2,
        2: 8.8,
        3: 11.3,
        4: 13.8,
    },
}

# No extras yet for Yevivo – leave empty for now.
EXTRA_COSTS = {
    # "some extra product name": {"Australia": X, "United Kingdom": Y}
}

ZERO_COGS_KEYS = ["express shipping", "dermatologist guide", "shipping protection"]

COUNTRY_MAP = {
    "GB": "United Kingdom",
    "UK": "United Kingdom",
    "United Kingdom": "United Kingdom",
    "AU": "Australia",
    "AUS": "Australia",
    "Australia": "Australia",
}

COUNTRY_COLS = [
    "Shipping Country",
    "Shipping Country Code",
    "Shipping Address Country Code",
    "Shipping Address Country",
]

RECURRING_TAG = "Subscription Recurring Order"  # tag to exclude from NC view


# ------------------------- HELPERS -------------------------
def main_cost_with_extrapolation(country: str, main_qty: int):
    """
    Returns (cost, warning). If main_qty is above the highest tier, extrapolate
    using the last step. Example: cost[n] = cost[max] + (n-max)*step.
    """
    if not main_qty:
        return 0.0, None

    tiers = MAIN_COST_TABLE.get(country, {})
    if not tiers:
        return 0.0, f"Unknown country '{country}' for main tiers."

    if main_qty in tiers:
        return float(tiers[main_qty]), None

    max_tier = max(tiers.keys())
    if main_qty > max_tier:
        if (max_tier - 1) in tiers:
            step = tiers[max_tier] - tiers[max_tier - 1]
        else:
            step = 0
        est = tiers[max_tier] + step * (main_qty - max_tier)
        return float(round(est, 2)), f"Extrapolated main COGS for {main_qty} units"
    return 0.0, f"Missing main tier for {main_qty} units."


def norm(s: str) -> str:
    s = str(s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[\W_]+", " ", s)
    return " ".join(s.split())

def is_main(n: str) -> bool:
    """
    Treat any Yevivo bottle line as the main product.

    This is intentionally loose so it works for:
    - single bottles
    - 2/3/4 packs
    - any bundle where the name still contains 'Yevivo'
    """
    return "yevivo" in n




def zero_cogs(n: str) -> bool:
    return any(k in n for k in ZERO_COGS_KEYS)


def extra_key(n: str):
    for key in EXTRA_COSTS:
        if key in n:
            return key
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

    # find usable country column
    country_col = None
    for c in COUNTRY_COLS:
        if c in df.columns:
            country_col = c
            break
    if country_col is None:
        raise ValueError("No shipping country column found in CSV.")

    df = df.copy()
    df["qty"] = pd.to_numeric(df.get("Lineitem quantity", 0), errors="coerce").fillna(0).astype(int)
    df["Country"] = df[country_col].map(COUNTRY_MAP).fillna(df[country_col])

    logs = []
    total = 0.0

    for oid, grp in df.groupby("Name"):
        country = str(grp["Country"].iloc[0]).strip()
        main_qty = 0
        extras_cost = 0.0

        # Use only the rows that actually have a shipping country
        # (Shopify export is creating a duplicate row with Shipping Country = NaN)
        if country_col and grp[country_col].notna().any():
            items = grp[grp[country_col].notna()].copy()
        else:
            items = grp.copy()

        for _, r in items.iterrows():
            n = norm(r.get("Lineitem name", ""))
            q = int(r.get("qty", 0))
            if q == 0 or zero_cogs(n):
                continue

            if is_main(n):
                main_qty += q
                continue

            ek = extra_key(n)
            if ek:
                extras_cost += EXTRA_COSTS[ek].get(country, 0) * q
            else:
                logs.append(f"{oid}: Unmapped {r.get('Lineitem name', '')}")

        main_cost, warn = main_cost_with_extrapolation(country, main_qty)
        if debug and warn:
            logs.append(f"{oid}: {warn}")

        total += main_cost + extras_cost
        if debug:
            logs.append(
                f"{oid} · {country} · main {main_qty}u = ${main_cost:.2f} · extras ${extras_cost:.2f}"
            )

    return round(total, 2), logs


def calc_revenue_and_fees(df: pd.DataFrame):
    """
    Yevivo store currency is already USD.
    This returns (revenue_usd, fees_usd, net_after_fees_usd).
    """
    if df.empty:
        return 0.0, 0.0, 0.0

    revenue_col = next(
        (c for c in ["Total", "Total Sales", "Total (USD)", "Total Price"] if c in df.columns),
        None,
    )

    if revenue_col:
        revenue_usd = pd.to_numeric(df[revenue_col], errors="coerce").fillna(0).sum()
    elif "Lineitem price" in df.columns:
        qty = pd.to_numeric(df.get("Lineitem quantity", 0), errors="coerce").fillna(0).astype(float)
        price = pd.to_numeric(df["Lineitem price"], errors="coerce").fillna(0).astype(float)
        revenue_usd = float((price * qty).sum())
    else:
        revenue_usd = 0.0

    # Same blended fee assumption as Rhóms:
    # (Stripe/Shopify 2.8% + 30c) + (extra 2% fee), both grossed up 10% for FX/other.
    fees_usd = ((revenue_usd * 0.028 + 0.3) * 1.1) + ((revenue_usd * 0.02) * 1.1)
    net_after_fees_usd = revenue_usd - fees_usd
    return round(revenue_usd, 2), round(fees_usd, 2), round(net_after_fees_usd, 2)


def pill(number, label, sub=None, state="neutral"):
    cls = "pill" + (" positive" if state == "pos" else " negative" if state == "neg" else "")
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    return f'<div class="{cls}"><div class="label">{label}</div><div class="value">{number}</div>{sub_html}</div>'


DATE_COL_CANDIDATES = [
    "Created at",
    "Created At",
    "Processed at",
    "Order Date",
    "Order Created At",
]


def extract_date_series(df: pd.DataFrame) -> pd.Series:
    for col in DATE_COL_CANDIDATES:
        if col in df.columns:
            s = pd.to_datetime(df[col], errors="coerce", infer_datetime_format=True, utc=False)
            if s.notna().any():
                return s

    for col in df.columns:
        if any(k in col.lower() for k in ["date", "created", "processed"]):
            s = pd.to_datetime(df[col], errors="coerce", infer_datetime_format=True, utc=False)
            if s.notna().any():
                return s
    return pd.Series(dtype="datetime64[ns]")


def pretty_range(dmin: pd.Timestamp, dmax: pd.Timestamp) -> str:
    if pd.isna(dmin) or pd.isna(dmax):
        return "No dates found"
    dmin = pd.to_datetime(dmin)
    dmax = pd.to_datetime(dmax)
    if dmin.date() == dmax.date():
        return dmin.strftime("%b %d, %Y")
    if dmin.year == dmax.year:
        if dmin.month == dmax.month:
            return f"{dmin.strftime('%b %d')} → {dmax.strftime('%d, %Y')}"
        return f"{dmin.strftime('%b %d')} → {dmax.strftime('%b %d, %Y')}"
    return f"{dmin.strftime('%b %d, %Y')} → {dmax.strftime('%b %d, %Y')}"


# ------------------------- UI -------------------------
st.title("Yevivo Profitability Dashboard")
st.caption("Drop your Shopify CSV + Ad Spend. See blended & front-end profitability in one glance (USD).")

# Hero inputs
col_left, col_right = st.columns([1.8, 1])

with col_left:
    st.markdown('<div class="hero-label">Shopify CSV</div>', unsafe_allow_html=True)
    file = st.file_uploader(" ", type=["csv"], label_visibility="collapsed")

with col_right:
    st.markdown('<div class="hero-label">Ad Spend (USD)</div>', unsafe_allow_html=True)
    ad_spend_usd = st.number_input(
        " ",
        value=0.00,
        min_value=0.00,
        step=10.00,
        format="%.2f",
        label_visibility="collapsed",
    )

with st.expander("Details & Settings"):
    st.markdown(
        '<span class="fxchip"><span class="dot"></span> Store currency detected as USD. '
        "All figures below are in USD.</span>",
        unsafe_allow_html=True,
    )
    show_debug = st.toggle("Show per-order breakdown logs", value=False)

if "show_debug" not in locals():
    show_debug = False

# ------------------------- MAIN CALC -------------------------
if file:
    df = pd.read_csv(file)

    # Date range chip
    ds = extract_date_series(df)
    dmin, dmax = (ds.min(), ds.max()) if not ds.empty else (pd.NaT, pd.NaT)
    date_chip_text = pretty_range(dmin, dmax)

    # Split front-end vs recurring
    df_front, df_rec = split_frontend(df)

    # ---- BLENDED ----
    total_cogs_usd, logs = calc_cogs(df, debug=show_debug)
    revenue_usd, fees_usd, net_after_fees = calc_revenue_and_fees(df)
    gross_profit = revenue_usd - fees_usd - total_cogs_usd
    overall_profit = gross_profit - ad_spend_usd
    blended_roas = (revenue_usd / ad_spend_usd) if ad_spend_usd > 0 else None

    # ---- FRONT-END (non-recurring) ----
    fe_cogs_usd, _ = calc_cogs(df_front, debug=False)
    fe_revenue_usd, fe_fees_usd, fe_net_after_fees = calc_revenue_and_fees(df_front)
    fe_gross_profit = fe_revenue_usd - fe_fees_usd - fe_cogs_usd
    fe_overall_profit = fe_gross_profit - ad_spend_usd
    nc_roas = (fe_revenue_usd / ad_spend_usd) if ad_spend_usd > 0 else None

    # Header chips
    st.markdown(
        f'''
        <div class="chips">
          <span class="fxchip"><span class="dot"></span> Currency: USD store</span>
          <span class="datechip"><span class="cal"></span> {date_chip_text}</span>
        </div>
        ''',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

    # -------- Row 1: BLENDED --------
    state_overall = "pos" if overall_profit > 0 else ("neg" if overall_profit < 0 else "neutral")
    r1 = [
        pill(f"${net_after_fees:,.2f}", "Net Revenue (USD)", sub=f"${revenue_usd:,.2f} – after fees"),
        pill(f"${total_cogs_usd:,.2f}", "COGS (USD)"),
        pill(f"${ad_spend_usd:,.2f}", "Ad Spend (USD)"),
        pill(
            f"${overall_profit:,.2f}" if overall_profit >= 0 else f"-${abs(overall_profit):,.2f}",
            "Overall Profit/Loss (USD)",
            state=state_overall,
        ),
    ]
    st.markdown('<div class="row-4">' + "".join(r1) + "</div>", unsafe_allow_html=True)

    # -------- Row 2: FRONT-END --------
    state_fe = "pos" if fe_overall_profit > 0 else ("neg" if fe_overall_profit < 0 else "neutral")
    r2 = [
        pill(
            f"${fe_net_after_fees:,.2f}",
            "Net Revenue (USD) — NC",
            sub=f"${fe_revenue_usd:,.2f} – after fees",
        ),
        pill(f"${fe_cogs_usd:,.2f}", "COGS (USD) — NC"),
        pill(
            f"${fe_overall_profit:,.2f}" if fe_overall_profit >= 0 else f"-${abs(fe_overall_profit):,.2f}",
            "Profit/Loss (USD) — NC",
            state=state_fe,
        ),
    ]
    st.markdown('<div class="row-3">' + "".join(r2) + "</div>", unsafe_allow_html=True)

    # -------- Row 3: ROAS --------
    roas_blend_text = f"{blended_roas:,.2f}×" if blended_roas is not None else "–"
    roas_nc_text = f"{nc_roas:,.2f}×" if nc_roas is not None else "–"
    r3 = [
        pill(
            roas_blend_text,
            "Blended ROAS",
            sub="Revenue ÷ Ad Spend",
            state="pos" if blended_roas and blended_roas >= 1 else "neg" if blended_roas else "neutral",
        ),
        pill(
            roas_nc_text,
            "NC ROAS",
            sub="Front-end Revenue ÷ Ad Spend",
            state="pos" if nc_roas and nc_roas >= 1 else "neg" if nc_roas else "neutral",
        ),
    ]
    st.markdown('<div class="row-2">' + "".join(r3) + "</div>", unsafe_allow_html=True)

    # -------- Quick export row for Sheets --------
    export_row = {
        "Date (or range)": date_chip_text,
        "Total Revenue (USD)": round(net_after_fees, 2),
        "Ad Spend (USD)": round(ad_spend_usd, 2),
        "Total COGs (USD)": round(total_cogs_usd, 2),
        "Total Profit (USD)": round(overall_profit, 2),
        "NC Profit (USD)": round(fe_overall_profit, 2),
    }

    headers = [
        "Date (or range)",
        "Total Revenue (USD)",
        "Ad Spend (USD)",
        "Total COGs (USD)",
        "Total Profit (USD)",
        "NC Profit (USD)",
    ]
    values = [
        export_row["Date (or range)"],
        f'{export_row["Total Revenue (USD)"]:.2f}',
        f'{export_row["Ad Spend (USD)"]:.2f}',
        f'{export_row["Total COGs (USD)"]:.2f}',
        f'{export_row["Total Profit (USD)"]:.2f}',
        f'{export_row["NC Profit (USD)"]:.2f}',
    ]
    tsv_line = "\t".join(values)

    st.markdown("#### Quick paste to your P&L Sheet")
    st.caption("Click copy, then ⌘V / Ctrl+V into your Google Sheet (TSV format).")

    preview_df = pd.DataFrame(
        [
            {
                "Date (or range)": export_row["Date (or range)"],
                "Total Revenue (USD)": f'${export_row["Total Revenue (USD)"]:.2f}',
                "Ad Spend (USD)": f'${export_row["Ad Spend (USD)"]:.2f}',
                "Total COGs (USD)": f'${export_row["Total COGs (USD)"]:.2f}',
                "Total Profit (USD)": f'${export_row["Total Profit (USD)"]:.2f}',
                "NC Profit (USD)": f'${export_row["NC Profit (USD)"]:.2f}',
            }
        ]
    )[
        [
            "Date (or range)",
            "Total Revenue (USD)",
            "Ad Spend (USD)",
            "Total COGs (USD)",
            "Total Profit (USD)",
            "NC Profit (USD)",
        ]
    ]

    st.dataframe(preview_df, use_container_width=True, hide_index=True)

    import json as _json
    from streamlit.components.v1 import html as _st_html
    from io import StringIO as _StringIO

    _payload = _json.dumps(tsv_line)
    _st_html(
        f"""
      <button id="copyBtn" style="
        padding:10px 14px;border:1px solid #A4DB32;border-radius:10px;
        background:transparent;color:#e5e7eb;cursor:pointer;font-weight:700">
        📋 Copy row for Sheets
      </button>
      <script>
        const data = {_payload};
        const btn = document.getElementById('copyBtn');
        btn.addEventListener('click', async () => {{
          try {{
            await navigator.clipboard.writeText(data);
            const old = btn.innerText;
            btn.innerText = 'Copied!';
            setTimeout(()=>btn.innerText = old, 1200);
          }} catch (e) {{
            alert('Copy failed: ' + e);
          }}
        }});
      </script>
    """,
        height=70,
    )

    buf = _StringIO()
    buf.write("\t".join(headers) + "\n" + tsv_line)
    st.download_button(
        "⬇️ Download TSV",
        data=buf.getvalue().encode("utf-8"),
        file_name="yevivo_summary.tsv",
        mime="text/tab-separated-values",
    )

    # ========================= COGS BREAKDOWN / RECONCILIATION =========================
    def _per_order_cogs_breakdown(df_all: pd.DataFrame, date_series: pd.Series):
        rows = []

        # find usable country col
        country_col = None
        for c in COUNTRY_COLS:
            if c in df_all.columns:
                country_col = c
                break

        for oid, grp in df_all.groupby("Name"):
            # date
            dt = ""
            if not date_series.empty:
                try:
                    dtv = pd.to_datetime(date_series.loc[grp.index].dropna().iloc[0])
                    dt = dtv.strftime("%Y-%m-%d")
                except Exception:
                    dt = ""

            raw_country = str(grp[country_col].iloc[0]).strip() if country_col else ""
            norm_country = COUNTRY_MAP.get(raw_country, raw_country)
            country_known = norm_country in MAIN_COST_TABLE

            # ignore ghost rows — keep only records with a shipping country
            if country_col and grp[country_col].notna().any():
                items = grp[grp[country_col].notna()].copy()
            else:
                items = grp.copy()

            main_qty = 0
            extras_cost = 0.0
            unmapped = []

            for _, r in items.iterrows():
                q = int(pd.to_numeric(r.get("Lineitem quantity", 0), errors="coerce") or 0)
                n = norm(r.get("Lineitem name", ""))

                if q == 0 or zero_cogs(n):
                    continue

                if is_main(n):
                    main_qty += q
                    continue

                ek = extra_key(n)
                if ek:
                    price_map = EXTRA_COSTS.get(ek, {})
                    if norm_country in price_map:
                        extras_cost += price_map[norm_country] * q
                    else:
                        unmapped.append(str(r.get("Lineitem name", "")))
                else:
                    unmapped.append(str(r.get("Lineitem name", "")))

            main_cost, warn = main_cost_with_extrapolation(norm_country, main_qty)
            total_cogs = round((main_cost or 0.0) + (extras_cost or 0.0), 2)

            if not country_known:
                status = "Unknown country"
                computed = (main_cost > 0) or (extras_cost > 0)
            elif warn:
                status = warn
                computed = (main_cost > 0) or (extras_cost > 0)
            elif (main_cost > 0) or (extras_cost > 0):
                status = "OK"
                computed = True
            else:
                status = "Only zero-COGS/unmapped"
                computed = False

            rows.append(
                {
                    "Order ID": oid,
                    "Date": dt,
                    "Raw Country": raw_country,
                    "Country": norm_country,
                    "Main Units": int(main_qty),
                    "Main Cost (USD)": round(main_cost or 0.0, 2),
                    "Extras Cost (USD)": round(extras_cost or 0.0, 2),
                    "Total COGS (USD)": total_cogs,
                    "Computed?": computed,
                    "Status": status,
                    "Unmapped Lines": ", ".join(unmapped) if unmapped else "",
                    "Warnings": warn or "",
                }
            )

        return pd.DataFrame(rows)

    breakdown_df = _per_order_cogs_breakdown(df, ds)
    total_orders = int(breakdown_df.shape[0])
    computed_orders = int(breakdown_df["Computed?"].sum())
    left_out_orders = breakdown_df.loc[~breakdown_df["Computed?"], "Order ID"].tolist()

    st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
    st.markdown("### Reconciliation")

    r_recon = [
        pill(f"{total_orders}", "Total Orders (in CSV)"),
        pill(f"{computed_orders}", "Orders with Priced COGS", sub=f"{computed_orders}/{total_orders}"),
    ]
    st.markdown('<div class="row-2">' + "".join(r_recon) + "</div>", unsafe_allow_html=True)

    if left_out_orders:
        with st.expander("⚠️ Orders without priced COGS (click to review)"):
            st.dataframe(
                breakdown_df.loc[~breakdown_df["Computed?"], [
                    "Order ID",
                    "Date",
                    "Raw Country",
                    "Country",
                    "Main Units",
                    "Main Cost (USD)",
                    "Extras Cost (USD)",
                    "Total COGS (USD)",
                    "Status",
                    "Unmapped Lines",
                ]].sort_values(["Country", "Date", "Order ID"]),
                use_container_width=True,
                hide_index=True,
            )

    country_counts = (
        breakdown_df.groupby("Country", dropna=False)["Order ID"]
        .nunique()
        .sort_values(ascending=False)
        .reset_index()
        .rename(columns={"Order ID": "Orders"})
    )
    st.markdown("#### Orders per Country")
    st.dataframe(country_counts, use_container_width=True, hide_index=True)

    warning_rows = breakdown_df[breakdown_df["Warnings"] != ""]
    if not warning_rows.empty:
        with st.expander("⚠️ Orders with warnings (extrapolated or unusual)"):
            st.dataframe(
                warning_rows[
                    [
                        "Order ID",
                        "Date",
                        "Country",
                        "Main Units",
                        "Main Cost (USD)",
                        "Extras Cost (USD)",
                        "Total COGS (USD)",
                        "Status",
                        "Warnings",
                    ]
                ].sort_values(["Country", "Date", "Order ID"]),
                use_container_width=True,
                hide_index=True,
            )

    # Extra details
    with st.expander("More details (open if needed)"):
        st.write(f"**Revenue (USD):** ${revenue_usd:,.2f}")
        st.write(f"**Shopify & Payment Fees (USD):** ${fees_usd:,.2f}")
        st.write(f"**Net after Fees (USD):** ${net_after_fees:,.2f}")
        st.write(f"**Gross Profit (USD):** ${gross_profit:,.2f}")
        st.write("---")
        st.write(f"**Front-end Revenue (USD):** ${fe_revenue_usd:,.2f}")
        st.write(f"**Front-end Fees (USD):** ${fe_fees_usd:,.2f}")
        st.write(f"**Front-end Net after Fees (USD):** ${fe_net_after_fees:,.2f}")
        st.write(f"**Front-end Gross Profit (USD):** ${fe_gross_profit:,.2f}")

        if show_debug and not df.empty:
            st.write("---")
            st.subheader("Per-order COGS breakdown logs")
            _, logs_all = calc_cogs(df, debug=True)
            for l in logs_all:
                st.write(l)

else:
    # onboarding state
    st.markdown('<div class="pill"><div class="label">Step 1</div><div class="value">Upload Shopify CSV</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="pill"><div class="label">Step 2</div><div class="value">Enter Ad Spend (USD)</div></div>', unsafe_allow_html=True)
    st.caption("Once both are set, your blended and front-end profitability will appear instantly.")
