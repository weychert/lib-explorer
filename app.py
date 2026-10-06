"""
LIB Explorer — interactive demo of LabFam Individual Biographies (LIB).

Shows, for one fictional person, what household-panel data look like
BEFORE harmonisation (point-in-time interview snapshots) and AFTER LIB
(continuous, dated spells and events).

All records are SYNTHETIC. No SOEP, SHP, BHPS/UKHLS, PSID or HILDA microdata
are used. Run with:  streamlit run app.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

DATA_FILE = Path(__file__).parent / "data" / "lib_synthetic_demo.xlsx"

LINKS = {
    "LIB website": "https://labfam.uw.edu.pl/labfam-individual-biographies-lib/",
    "Data Note (DOI)": "https://doi.org/10.21203/rs.3.rs-8376548/v1",
    "Code on GitHub": "https://github.com/weychert/LabFam-Individual-Biographies",
}

# How to obtain the real source data (LIB shares code, not data).
ACCESS = pd.DataFrame(
    [
        ("SOEP", "Germany", "DIW Berlin, RDC SOEP", "Data distribution contract signed by your institution", "Weeks"),
        ("SHP", "Switzerland", "FORS via SWISSUbase", "SWITCH edu-ID login + online usage contract", "Same day"),
        ("BHPS/UKHLS", "United Kingdom", "UK Data Service", "End User Licence (SN 6614) or Special Licence (SN 6931)", "Same day / weeks"),
        ("PSID", "United States", "ISR, University of Michigan", "Registration for public data; restricted data by contract", "Same day"),
        ("HILDA", "Australia", "DSS via Australian Data Archive", "Request + Confidentiality Deed Poll", "Weeks"),
    ],
    columns=["Panel", "Country", "Provider", "Access", "Typical waiting time"],
)

# Colours (colour-blind friendly, Okabe-Ito based)
EMP_COLORS = {
    "working": "#0072B2",
    "unemployed": "#D55E00",
    "not in labour force": "#E69F00",
    "retired": "#999999",
    "other": "#CC79A7",
    "unknown": "#DDDDDD",
}
PART_COLORS = {
    "no union": "#C9D6DF",
    "cohabitation": "#56B4E9",
    "marriage": "#009E73",
    "gap": "#EEEEEE",
}
CHILD_COLOR = "#7B3294"

ROW_EMP, ROW_PART, ROW_KIDS = "Employment", "Partnership", "Children"
ROWS = [ROW_KIDS, ROW_PART, ROW_EMP]  # bottom→top order in plotly categorical y


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------
def _ym_to_ts(s: str, end: bool = False) -> pd.Timestamp:
    """'YYYY-MM' -> Timestamp at start of month (or end of month if end=True)."""
    ts = pd.Timestamp(f"{s}-01")
    return ts + pd.offsets.MonthEnd(0) if end else ts


@st.cache_data
def load_data(path: Path) -> dict[str, pd.DataFrame]:
    wide = pd.read_excel(path, sheet_name="Wide_LIB", header=2)
    spells = pd.read_excel(path, sheet_name="Spells_long", header=2)
    obs = pd.read_excel(path, sheet_name="Panel_observations", header=2)
    curated = pd.read_excel(path, sheet_name="Curated_cases", header=2)

    spells["start_ts"] = spells["start"].astype(str).map(_ym_to_ts)
    spells["end_ts"] = spells["end"].astype(str).map(lambda s: _ym_to_ts(s, end=True))
    obs["ts"] = pd.to_datetime(
        dict(year=obs["interview_year"], month=obs["interview_month"], day=15)
    )
    return {"wide": wide, "spells": spells, "obs": obs, "curated": curated}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def age_at(ts: pd.Timestamp, born_y: int, born_m: int) -> int:
    return int((ts.year * 12 + ts.month - (born_y * 12 + born_m)) // 12)


def fmt_ym(ts: pd.Timestamp, precision: str = "month") -> str:
    return f"{ts.year}" if precision == "year" else ts.strftime("%b %Y")


def missed_by_snapshots(sp: pd.DataFrame, ob: pd.DataFrame) -> pd.Series:
    """True for spells inside the observation window that no interview falls into."""
    first = ob["ts"].min()
    out = []
    for _, r in sp.iterrows():
        if r["domain"] == "fertility" or r["start_ts"] < first:
            out.append(False)
            continue
        hit = ((ob["ts"] >= r["start_ts"]) & (ob["ts"] <= r["end_ts"])).any()
        out.append(not hit)
    return pd.Series(out, index=sp.index)


def child_born_between_waves(sp: pd.DataFrame, ob: pd.DataFrame) -> int:
    first = ob["ts"].min()
    kids = sp[sp["domain"] == "fertility"]
    return int((kids["start_ts"] >= first).sum())


# --------------------------------------------------------------------------
# Figure
# --------------------------------------------------------------------------
def build_figure(person: pd.Series, sp: pd.DataFrame, ob: pd.DataFrame,
                 show_age: bool) -> go.Figure:
    born_y, born_m = int(person["BORN_Y"]), int(person["BORN_M"])
    first_int, last_int = ob["ts"].min(), ob["ts"].max()
    x_min = min(sp["start_ts"].min(), first_int) - pd.DateOffset(months=12)
    x_max = max(sp["end_ts"].max(), last_int) + pd.DateOffset(months=12)

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.14,
        subplot_titles=(
            "<b>Before LIB</b> — what the panel records at each interview",
            "<b>After LIB</b> — harmonised, continuous life-course spells",
        ),
    )
    legend_seen: set[str] = set()

    def legend_once(name: str) -> bool:
        if name in legend_seen:
            return False
        legend_seen.add(name)
        return True

    # ---------------- BEFORE: snapshots ----------------
    for _, o in ob.iterrows():
        age = age_at(o["ts"], born_y, born_m)
        hover = (f"Interview {o['ts']:%b %Y} (age {age})<br>"
                 f"Employment: {o['employment_status_at_interview']}<br>"
                 f"Partnership: {o['partnership_status_at_interview']}<br>"
                 f"Children: {int(o['children_count_at_interview'])}")
        emp = o["employment_status_at_interview"]
        part = o["partnership_status_at_interview"]
        fig.add_trace(go.Scatter(
            x=[o["ts"]], y=[ROW_EMP], mode="markers",
            marker=dict(size=13, color=EMP_COLORS.get(emp, "#BBBBBB"),
                        line=dict(color="white", width=1.5)),
            name=emp, legendgroup=f"emp-{emp}", showlegend=False,
            hovertemplate=hover + "<extra></extra>"), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=[o["ts"]], y=[ROW_PART], mode="markers",
            marker=dict(size=13, color=PART_COLORS.get(part, "#BBBBBB"),
                        line=dict(color="#555555", width=1)),
            name=part, legendgroup=f"part-{part}", showlegend=False,
            hovertemplate=hover + "<extra></extra>"), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=[o["ts"]], y=[ROW_KIDS], mode="text",
            text=[str(int(o["children_count_at_interview"]))],
            textfont=dict(size=13, color=CHILD_COLOR),
            showlegend=False, hovertemplate=hover + "<extra></extra>"), row=1, col=1)

    # ---------------- AFTER: spells ----------------
    # shade period reconstructed from retrospective data (before first interview)
    if sp["start_ts"].min() < first_int:
        fig.add_shape(type="rect", xref="x2", yref="y2 domain",
                      x0=sp["start_ts"].min().strftime("%Y-%m-%d"), x1=first_int.strftime("%Y-%m-%d"),
                      y0=0, y1=1, fillcolor="#F2E8CF", opacity=0.6, line_width=0, layer="below")
        fig.add_annotation(x=first_int.strftime("%Y-%m-%d"), y=0.0, xref="x2", yref="y2 domain",
                           xanchor="right", yanchor="bottom", showarrow=False,
                           text="before panel entry: from retrospective data ",
                           font=dict(size=11, color="#7A6A3A"))
    # interview dates in the AFTER panel, for reference
    for t in ob["ts"]:
        fig.add_shape(type="line", xref="x2", yref="y2 domain", x0=t.strftime("%Y-%m-%d"),
                      x1=t.strftime("%Y-%m-%d"), y0=0, y1=1, layer="above",
                      line=dict(color="#888888", width=1, dash="dot"))

    for _, r in sp[sp["domain"] != "fertility"].iterrows():
        dom_row = ROW_EMP if r["domain"] == "employment" else ROW_PART
        palette = EMP_COLORS if r["domain"] == "employment" else PART_COLORS
        label = r["state_label"]
        color = palette.get(label, "#BBBBBB")
        dur_ms = (r["end_ts"] - r["start_ts"]).total_seconds() * 1000
        months = round(dur_ms / (1000 * 60 * 60 * 24 * 30.44))
        prec = r.get("date_precision", "month")
        missed = bool(r["missed"])
        partner = f"<br>Partner: {r['partner_id']}" if pd.notna(r.get("partner_id")) else ""
        hover = (f"<b>{label}</b><br>{fmt_ym(r['start_ts'], prec)} – {fmt_ym(r['end_ts'], prec)}"
                 f" ({months} months)<br>Age {age_at(r['start_ts'], born_y, born_m)}–"
                 f"{age_at(r['end_ts'], born_y, born_m)}<br>Date precision: {prec}{partner}"
                 + ("<br><b>⚠ Not visible in any interview snapshot</b>" if missed else ""))
        fig.add_trace(go.Bar(
            x=[dur_ms], base=[r["start_ts"]], y=[dom_row], orientation="h",
            marker=dict(color=color,
                        pattern=dict(shape="/" if prec == "year" else "", fgcolor="white", size=6),
                        line=dict(color="#111111" if missed else "white", width=3 if missed else 1)),
            name=label, legendgroup=f"{r['domain'][:4]}-{label}",
            showlegend=legend_once(f"{r['domain'][:4]}-{label}"),
            legendgrouptitle_text=None,
            hovertemplate=hover + "<extra></extra>", width=0.6), row=2, col=1)

    kids = sp[sp["domain"] == "fertility"]
    for _, k in kids.iterrows():
        prec = k.get("date_precision", "month")
        sex = k.get("child_sex") if pd.notna(k.get("child_sex")) else "unknown sex"
        hover = (f"<b>{k['state_label']}</b> ({sex})<br>Born {fmt_ym(k['start_ts'], prec)}"
                 f"<br>Parent's age {age_at(k['start_ts'], born_y, born_m)}<br>Date precision: {prec}")
        if prec == "year":  # year-only birth: draw a band over the whole year
            y0 = pd.Timestamp(year=k["start_ts"].year, month=1, day=1)
            fig.add_trace(go.Bar(
                x=[pd.Timedelta(days=365).total_seconds() * 1000], base=[y0], y=[ROW_KIDS],
                orientation="h", width=0.35,
                marker=dict(color=CHILD_COLOR, opacity=0.25, line=dict(width=0)),
                showlegend=legend_once("kid-year"), name="birth (year only)",
                hovertemplate=hover + "<extra></extra>"), row=2, col=1)
        else:
            fig.add_trace(go.Scatter(
                x=[k["start_ts"]], y=[ROW_KIDS], mode="markers+text",
                marker=dict(symbol="star", size=17, color=CHILD_COLOR),
                text=[k["state_label"].replace("child ", "#")], textposition="top center",
                textfont=dict(size=10, color=CHILD_COLOR),
                showlegend=legend_once("kid-month"), name="birth",
                hovertemplate=hover + "<extra></extra>"), row=2, col=1)

    # Legend entries for snapshot-only categories (e.g. "unknown")
    for lab in ob["employment_status_at_interview"].unique():
        if f"empl-{lab}" not in legend_seen and lab in EMP_COLORS:
            legend_seen.add(f"empl-{lab}")
            fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
                                     marker=dict(size=11, color=EMP_COLORS[lab]),
                                     name=lab, showlegend=True), row=1, col=1)

    for row in (1, 2):
        fig.update_yaxes(categoryorder="array", categoryarray=ROWS, row=row, col=1,
                         showgrid=False, tickfont=dict(size=13))
    fig.update_xaxes(type="date", range=[x_min, x_max], showgrid=True, gridcolor="#F0F0F0")

    if show_age:  # age ticks every 5 years on the bottom axis
        start = pd.Timestamp(year=born_y, month=born_m, day=1)
        ticks = [start + pd.DateOffset(years=a) for a in range(0, 101, 5)
                 if x_min <= start + pd.DateOffset(years=a) <= x_max]
        fig.update_xaxes(row=2, col=1, tickvals=ticks,
                         ticktext=[f"{t.year}<br>age {t.year - born_y}" for t in ticks])

    fig.update_layout(
        barmode="overlay", height=620, margin=dict(l=10, r=10, t=60, b=10),
        plot_bgcolor="white", hoverlabel=dict(bgcolor="white"),
        legend=dict(orientation="h", yanchor="top", y=-0.08, x=0, font=dict(size=12)),
    )
    return fig


# --------------------------------------------------------------------------
# Output preview
# --------------------------------------------------------------------------
def wide_blocks(person: pd.Series) -> dict[str, pd.DataFrame]:
    """Split one LIB wide row into readable per-domain tables (non-empty spells only)."""
    def block(prefix_cols: list[str], n: int, key: str, sep: str) -> pd.DataFrame:
        rows = []
        for i in range(1, n + 1):
            if pd.isna(person.get(key.format(i=i))):
                continue
            rows.append({c: person.get(c.format(i=i)) for c in prefix_cols})
        df = pd.DataFrame(rows, columns=prefix_cols)
        df.columns = [c.replace("{i}", "$") for c in prefix_cols]
        return df

    fert = block(["KID_{i}", "KID_Y{i}", "KID_M{i}", "KID_S{i}"], 10, "KID_Y{i}", "")
    part = block(["PARTNERSHIP_STATUS_{i}", "PARTNER_ID_{i}", "START_Y_{i}", "START_M_{i}",
                  "END_Y_{i}", "END_M_{i}", "END_SINGLE_{i}", "END_UNION_{i}",
                  "DIVORCE_{i}", "DIVORCE_Y_{i}", "DIVORCE_M_{i}"], 10, "PARTNERSHIP_STATUS_{i}", "_")
    emp = block(["EMPLOYMENT_STATUS_{i}", "ENTRY_Y{i}", "ENTRY_M{i}", "EXIT_Y{i}", "EXIT_M{i}"],
                10, "EMPLOYMENT_STATUS_{i}", "")
    for df in (fert, part, emp):
        df.index = range(1, len(df) + 1)
        df.index.name = "$"
    return {"Fertility": fert, "Partnership": part, "Employment": emp}


def _cell(v) -> str:
    """Display value as in the LIB output: integers without decimals, missing as NA."""
    if pd.isna(v):
        return "NA"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def lib_columns(wide: pd.DataFrame) -> list[str]:
    return [c for c in wide.columns if not c.startswith("DEMO_")]


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="LIB Explorer", page_icon="📈", layout="wide")
    data = load_data(DATA_FILE)
    wide, spells, obs, curated = data["wide"], data["spells"], data["obs"], data["curated"]

    # ---------- sidebar ----------
    with st.sidebar:
        st.markdown("### LIB Explorer")
        only_curated = st.toggle("Show curated demo cases only", value=True)
        pool = wide[wide["DEMO_CURATED"] == 1] if only_curated else wide
        order = ["SOEP", "SHP", "BHPS_UKHLS", "PSID", "HILDA"]
        panels = [p for p in order if p in set(pool["DEMO_PANEL"])] + sorted(set(pool["DEMO_PANEL"]) - set(order))
        panel = st.selectbox("Panel", panels, format_func=lambda p: p.replace("_", "/"))
        people = pool[pool["DEMO_PANEL"] == panel]
        pid = st.radio(
            "Fictional person", people["pid"].tolist(),
            format_func=lambda p: f"{p} · {people.loc[people.pid == p, 'DEMO_CASE_LABEL'].iloc[0]}",
        )
        show_age = st.toggle("Show age on time axis", value=True)
        st.divider()
        st.markdown("**Learn more**")
        for name, url in LINKS.items():
            st.markdown(f"- [{name}]({url})")
        st.caption("All biographies on this page are fictional and synthetic. "
                   "They do not reproduce any real respondent nor the "
                   "distributions of the source surveys.")

    person = wide[wide["pid"] == pid].iloc[0]
    sp = spells[spells["pid"] == pid].copy()
    ob = obs[obs["pid"] == pid].sort_values("ts")
    sp["missed"] = missed_by_snapshots(sp, ob)

    # ---------- header ----------
    st.title("LabFam Individual Biographies — from panel waves to life courses")
    st.markdown(
        "Household panels interview people roughly once a year. Jobs, partnerships and "
        "births do not wait for the interview. **LIB** combines panel waves, between-wave "
        "calendars and retrospective modules to rebuild **continuous monthly histories** "
        "of fertility, partnership and employment — harmonised across five panels."
    )

    sex = {1: "man", 2: "woman"}.get(int(person["SEX"]), "person")
    why = curated.loc[curated["pid"] == pid, "why_in_demo"]
    st.subheader(f"{person['DEMO_CASE_LABEL']}")
    st.markdown(
        f"Fictional {sex} born {int(person['BORN_Y'])}, "
        f"{person['DEMO_PANEL'].replace('_', '/')} ({person['DEMO_COUNTRY']}), "
        f"interviewed {int(person['FIRSTOBS_Y'])}–{int(person['LASTOBS_Y'])}."
        + (f"  \n_{why.iloc[0]}_" if len(why) else "")
    )

    n_pre = int((sp["start_ts"] < ob["ts"].min()).sum())
    n_missed = int(sp["missed"].sum())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Interview snapshots", len(ob))
    c2.metric("LIB spells & events", len(sp))
    c3.metric("Recovered from before panel entry", n_pre)
    c4.metric("Spells invisible in snapshots", n_missed)

    tab_tl, tab_out, tab_access = st.tabs(
        ["Before / After timeline", "Synthetic LIB output", "Get the real data"])

    with tab_tl:
        st.plotly_chart(build_figure(person, sp, ob, show_age), width="stretch")
        st.caption(
            "Top: one dot per interview — the status reported on that day, number = children. "
            "Bottom: LIB spells. Shaded area = history before the first interview. "
            "Hatched bars = dates known to the year only. Thick black outline = spell that "
            "starts and ends between two interviews. Dotted lines = interview dates. "
            "Leave with an employment contract (e.g. maternity leave) counts as working."
        )

    with tab_out:
        st.markdown(
            "LIB delivers **one row per person** in wide format, one block per domain, "
            "spells numbered chronologically (`$ = 1, 2, …`). Below is this person's "
            "synthetic row, split by domain."
        )
        for name, df in wide_blocks(person).items():
            st.markdown(f"**{name}**")
            if df.empty:
                st.caption("No spells/events.")
            else:
                st.dataframe(df.map(_cell), width="stretch")
        with st.expander("Coding used in the output"):
            st.markdown(
                "- `PARTNERSHIP_STATUS`: 0 no union · 1 cohabitation · 2 marriage · 3 gap\n"
                "- `END_SINGLE`: 0 ongoing · 1 cohabitation · 2 marriage\n"
                "- `END_UNION`: 0 ongoing · 1 marriage · 2 separation · 3 partner's death\n"
                "- `EMPLOYMENT_STATUS`: 1 working · 2 unemployed · 3 not in labour force · 4 retired · 5 other\n"
                "- `KID_M`: −1 = month unknown (year-only birth date); `KID_S`: 1 male · 2 female"
            )
        cols = lib_columns(wide)
        st.download_button(
            "Download synthetic sample (CSV, all fictional persons)",
            wide[cols].to_csv(index=False).encode("utf-8"),
            file_name="lib_synthetic_sample.csv", mime="text/csv",
        )

    with tab_access:
        st.markdown(
            "**LIB shares code, not data.** The harmonised biographies cannot be "
            "redistributed because the source surveys are licensed. To build them:\n\n"
            "1. Apply for access to the panel(s) you need (table below).\n"
            f"2. Download the open-source R code from [GitHub]({LINKS['Code on GitHub']}).\n"
            "3. Put the original files in the country folders, choose countries and domains "
            "in `01_data_selector.R`, and run the pipeline.\n"
        )
        st.dataframe(ACCESS, hide_index=True, width="stretch")
        st.caption(f"Details: [{LINKS['LIB website']}]({LINKS['LIB website']}) · "
                   f"Data Note: [{LINKS['Data Note (DOI)']}]({LINKS['Data Note (DOI)']})")


if __name__ == "__main__":
    main()
