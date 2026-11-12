"""
Microgrid Runtime Assurance Dashboard
=====================================

Reads the CSV files written by integration/scenarios.py and shows them in an
interactive Streamlit dashboard.

Launch from the repository root:
    python -m streamlit run dashboard.py

This file only READS data. It does not modify the simulator, the shield,
shared/config.py or any CSV file. No database is needed.

Important context (also shown inside the dashboard):
  * The controller is a RANDOM TEST CONTROLLER, not an RL agent.
  * The simulator assumes unlimited grid backup, so unmet load is always 0.
  * The five scenarios are synthetic stress tests derived from one dataset.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Microgrid Runtime Assurance",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --------------------------------------------------------------------------
# Paths and read-only configuration
# --------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = REPO_ROOT / "integration" / "results"
METRICS_FILE = RESULTS_DIR / "scenario_metrics.csv"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# shared/config.py is only imported (read-only) so the safe SoC band and
# power limit shown on charts always match the simulator.
try:
    from shared.config import BATTERY_KWH, DT_HOURS, MAX_POWER_KW, SOC_MAX, SOC_MIN

    CONFIG_SOURCE = "shared/config.py"
except Exception:  # pragma: no cover - fallback only
    BATTERY_KWH, DT_HOURS, MAX_POWER_KW, SOC_MAX, SOC_MIN = 100.0, 1.0, 50.0, 0.90, 0.20
    CONFIG_SOURCE = "built-in defaults (shared/config.py could not be imported)"

# --------------------------------------------------------------------------
# Scenarios
# --------------------------------------------------------------------------
SCENARIOS: dict[str, dict[str, str]] = {
    "normal": {
        "label": "Normal Operation",
        "desc": "Original dataset, no modifications.",
    },
    "cloudy": {
        "label": "Cloudy Days",
        "desc": "Solar output scaled to about 30\u201355% of the original, repeating on a 48-hour cycle.",
    },
    "demand_spike": {
        "label": "Demand Spike",
        "desc": "Load +60% between 17:00 and 20:00, once every seven days.",
    },
    "evening_peak": {
        "label": "Evening Peak",
        "desc": "Between 17:00 and 22:00 every day: load +35% and tariff +50%.",
    },
    "combined_stress": {
        "label": "Combined Stress",
        "desc": "Solar scaled to about 30\u201350%, plus evening load +50% and tariff +60%.",
    },
}
SCENARIO_KEYS = list(SCENARIOS.keys())

RESULT_COLUMNS = [
    "step", "solar_kw", "load_kw", "price_inr_kwh", "soc_before", "proposed_kw",
    "executed_kw", "shield_intervened", "shield_latency_ms", "safe_action",
    "backup_kw", "curtailed_kw", "unmet_load_kw", "step_cost_inr", "soc_after",
]
BOOL_COLUMNS = ["shield_intervened", "safe_action"]
NUMERIC_COLUMNS = [c for c in RESULT_COLUMNS if c not in BOOL_COLUMNS]

METRIC_COLUMNS = [
    "scenario", "shield_enabled", "simulation_steps", "total_cost_inr",
    "safety_violations", "interventions", "intervention_rate_percent",
    "violation_rate_percent", "unmet_load_kwh", "curtailed_energy_kwh",
    "mean_shield_latency_ms", "p95_shield_latency_ms", "max_shield_latency_ms",
]

# --------------------------------------------------------------------------
# Design tokens (from the Basedash style reference)
# --------------------------------------------------------------------------
VOID = "#000000"
CARBON = "#050607"
WHITE = "#ffffff"
BONE = "#e8eaee"
ASH = "#b3b3b3"
STEEL = "#808080"
GRAPHITE = "#333333"
VIOLET = "#9984d8"   # unshielded runs
MINT = "#3fcb7f"     # shielded runs
FONT_STACK = "Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Cormorant+Garamond:wght@400;500&display=swap');

html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background:
        radial-gradient(circle at top, rgba(153,132,216,0.18), transparent 32%),
        linear-gradient(180deg, #050607 0%, #0b0d0f 100%);
    color: #ffffff;
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
}
.stApp { letter-spacing: -0.03em; }
[data-testid="stHeader"] { background: transparent !important; height: 0; }
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] { display: none !important; }
.block-container {
    box-sizing: border-box;
    width: 100%;
    max-width: 1180px;
    margin: 0 auto;
    padding: 1.25rem 2rem 6rem;
}

.bd-nav,
.bd-hero,
.bd-sec,
.stTabs { width: 100%; }

p, li, label, span, div { font-family: inherit; }
a { color: #ffffff; }
hr { border-color: #333333; }

/* ---- Top bar ---- */
.bd-nav {
    display:flex;
    align-items:center;
    justify-content:space-between;
    height:52px;
    padding: 4px 0 12px 0;
    border-bottom: 1px solid rgba(255,255,255,0.08);
}
.bd-brand {
    display:flex;
    align-items:center;
    gap:10px;
    font-weight:600;
    font-size:15px;
    letter-spacing:0.08em;
    text-transform:uppercase;
    color:#f2f3f5;
}
.bd-logo {
    width:20px;
    height:20px;
    border:1px solid rgba(255,255,255,0.9);
    border-radius:6px;
    position:relative;
    background: linear-gradient(180deg, rgba(153,132,216,0.22), rgba(153,132,216,0.06));
}
.bd-logo::after {
    content:"";
    position:absolute;
    left:4px;
    right:4px;
    bottom:4px;
    height:6px;
    background: linear-gradient(180deg, #9984d8, #bdaef3);
    border-radius:2px;
}
.bd-status {
    display:flex;
    align-items:center;
    gap:8px;
    font-size:12px;
    font-weight:500;
    color:#b3b3b3;
    letter-spacing:0.04em;
    text-transform:uppercase;
}
.bd-dot {
    width:8px;
    height:8px;
    border-radius:50%;
    background:#3fcb7f;
    box-shadow:0 0 10px rgba(63,203,127,0.65);
    display:inline-block;
}

/* ---- Hero ---- */
.bd-hero {
    text-align:center;
    padding: 42px 0 8px 0;
    position:relative;
}
.bd-hero::before {
    content:"";
    position:absolute;
    left:50%;
    top:-16px;
    width:820px;
    height:300px;
    transform:translateX(-50%);
    background: radial-gradient(ellipse at center, rgba(163,102,255,0.24) 0%, rgba(123,78,245,0.12) 35%, rgba(82,49,184,0.04) 65%, transparent 100%);
    pointer-events:none;
    z-index:0;
}
.bd-hero > * { position:relative; z-index:1; }
.bd-pill {
    display:inline-flex;
    align-items:center;
    gap:8px;
    border:1px solid rgba(255,255,255,0.12);
    background: rgba(255,255,255,0.02);
    border-radius:999px;
    padding:6px 12px;
    font-size:12px;
    font-weight:500;
    color:#f0f1f3;
    letter-spacing:0.04em;
    text-transform:uppercase;
}
.bd-pill .bd-dot { width:6px; height:6px; background:#9984d8; box-shadow:none; }
.bd-h1, .bd-sec h2 {
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-weight: 500;
    font-size: clamp(2.6rem, 4vw, 4.2rem);
    line-height: 0.96;
    letter-spacing: -0.04em;
    color:#ffffff;
    margin: 0;
    padding: 0;
    font-feature-settings: "ss01" on, "ss02" on;
}
.bd-h1 { max-width: 860px; margin: 20px auto 0; }
.bd-subhead {
    font-size: 17px;
    line-height: 1.6;
    color: #b3b3b3;
    max-width: 680px;
    margin: 18px auto 0 auto;
}

/* ---- Section header ---- */
.bd-sec { text-align:center; padding: 38px 0 8px 0; }
.bd-sec p { font-size:16px; color:#b3b3b3; max-width:700px; margin: 16px auto 0 auto; line-height:1.5; }

/* ---- Controls ---- */
.bd-ctl-label {
    text-align:center;
    font-size:11px;
    font-weight:600;
    color:#b3b3b3;
    text-transform:uppercase;
    letter-spacing:0.12em;
    margin: 28px 0 8px 0;
}
[data-testid="stButtonGroup"] { justify-content:center; }
.bd-scn-desc { text-align:center; color:#b3b3b3; font-size:14px; margin: 14px 0 0 0; }

/* ---- Tabs ---- */
.stTabs [data-baseweb="tab-list"] {
    justify-content:center;
    gap:6px;
    border-bottom:1px solid rgba(255,255,255,0.08);
    margin-top: 28px;
}
.stTabs [data-baseweb="tab"] {
    color:#b3b3b3;
    font-size:14px;
    font-weight:500;
    padding: 10px 18px;
    background:transparent;
    border-radius:10px 10px 0 0;
}
.stTabs [aria-selected="true"] { color:#ffffff; }
.stTabs [data-baseweb="tab-highlight"] { background:#ffffff; height:2px; }
.stTabs [data-baseweb="tab-border"] { display:none; }

/* ---- Cards ---- */
.bd-card {
    background: linear-gradient(180deg, rgba(10,11,13,0.96), rgba(6,7,8,0.96));
    border:1px solid rgba(255,255,255,0.06);
    border-radius:18px;
    padding:18px 20px;
    height:100%;
    min-height:140px;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.02), 0 12px 28px rgba(0,0,0,0.26);
}
.bd-card-head { display:flex; justify-content:space-between; align-items:center; gap:8px; }
.bd-card-title { font-size:13px; color:#b3b3b3; font-weight:500; letter-spacing:0.02em; }
.bd-card-value { font-size:34px; line-height:1.1; font-weight:600; color:#fff; margin-top:10px; letter-spacing:-0.04em; word-break:break-word; }
.bd-card-value.sm { font-size:26px; }
.bd-card-foot { margin-top:6px; font-size:12px; color:#b3b3b3; display:flex; flex-wrap:wrap; gap:6px; align-items:baseline; }
.bd-delta { font-weight:600; font-size:13px; }
.bd-delta.good { color:#3fcb7f; }
.bd-delta.neutral { color:#ffffff; }
.bd-gap { height:18px; }

[class*="st-key-card-"] { background: rgba(5,6,7,0.96); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:18px 20px 12px 20px; }
.bd-ctitle { font-size:15px; font-weight:600; color:#fff; margin:0; }
.bd-ccap { font-size:13px; color:#808080; margin: 2px 0 6px 0; line-height:1.45; }
.bd-note { font-size:13px; color:#b3b3b3; line-height:1.6; }
.bd-note b { color:#fff; font-weight:500; }

/* ---- Table ---- */
.bd-table-wrap { background:#050607; border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:8px 8px 4px 8px; overflow-x:auto; }
table.bd-table { width:100%; border-collapse:collapse; font-size:14px; }
.bd-table th { text-align:right; color:#b3b3b3; font-weight:500; padding:12px 14px; border-bottom:1px solid rgba(255,255,255,0.09); white-space:nowrap; }
.bd-table th:first-child, .bd-table td:first-child { text-align:left; }
.bd-table td { text-align:right; padding:10px 14px; color:#e8eaee; border-bottom:1px solid rgba(255,255,255,0.04); font-variant-numeric: tabular-nums; white-space:nowrap; }
.bd-table td:first-child { color:#b3b3b3; }
.bd-table tr.grp td { color:#808080; font-size:12px; text-transform:uppercase; letter-spacing:0.08em; padding-top:18px; border-bottom:1px solid rgba(255,255,255,0.09); }
.bd-table th.sel, .bd-table td.sel { background: rgba(153,132,216,0.07); }
.bd-table td.good { color:#3fcb7f; }

/* ---- Error panel ---- */
.bd-error { background:#050607; border:1px solid rgba(255,255,255,0.08); border-radius:16px; padding:24px; margin-top:32px; }
.bd-error h3 { margin:0 0 8px 0; font-weight:500; font-size:20px; color:#fff; }
.bd-error p, .bd-error li { color:#b3b3b3; font-size:14px; line-height:1.6; }

/* ---- Misc Streamlit tweaks ---- */
[data-testid="stExpander"] { background:#050607; border:1px solid rgba(255,255,255,0.06); border-radius:16px; }
[data-testid="stExpander"] summary { color:#b3b3b3; }
</style>
"""


# --------------------------------------------------------------------------
# Formatting helpers
# --------------------------------------------------------------------------
def group_indian(n: int) -> str:
    """Format an integer with Indian digit grouping, e.g. 1947652 -> 19,47,652."""
    s = str(abs(int(n)))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts + [tail])


def inr(value: float, signed: bool = False) -> str:
    n = int(round(value))
    sign = "\u2212" if n < 0 else ("+" if signed and n > 0 else "")
    return f"{sign}\u20b9{group_indian(n)}"


def count(value: float) -> str:
    return group_indian(int(round(value)))


def kwh(value: float) -> str:
    return f"{group_indian(int(round(value)))} kWh"


def pct(value: float, digits: int = 2, signed: bool = False) -> str:
    sign = "+" if signed and value > 0 else ("\u2212" if value < 0 else "")
    return f"{sign}{abs(value):.{digits}f}%"


def latency(value: float) -> str:
    if value == 0:
        return "0 ms"
    return f"{value:.5f} ms" if value < 0.01 else f"{value:.3f} ms"


def esc(text: object) -> str:
    return html.escape(str(text))


# --------------------------------------------------------------------------
# Data loading and validation
# --------------------------------------------------------------------------
class DataError(Exception):
    """Raised when a results file is missing, unreadable or inconsistent."""


def run_path(key: str, kind: str) -> Path:
    return RESULTS_DIR / f"{key}_{kind}.csv"


def required_files() -> list[Path]:
    files = [METRICS_FILE]
    for key in SCENARIO_KEYS:
        files.append(run_path(key, "baseline"))
        files.append(run_path(key, "shielded"))
    return files


def missing_files() -> list[Path]:
    return [p for p in required_files() if not p.exists()]


def _to_bool(series: pd.Series, column: str, name: str) -> pd.Series:
    if series.dtype == bool:
        return series
    mapped = (
        series.astype(str).str.strip().str.lower()
        .map({"true": True, "false": False, "1": True, "0": False})
    )
    if mapped.isna().any():
        raise DataError(f"{name}: column '{column}' contains values other than True/False.")
    return mapped.astype(bool)


@st.cache_data(show_spinner=False)
def load_run(path_str: str, mtime: float) -> pd.DataFrame:
    """Read and validate one per-step results CSV. `mtime` refreshes the cache."""
    path = Path(path_str)
    name = path.name
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        raise DataError(f"{name}: could not be read ({exc}).") from exc

    missing = [c for c in RESULT_COLUMNS if c not in df.columns]
    if missing:
        raise DataError(f"{name}: missing columns {missing}.")
    if df.empty:
        raise DataError(f"{name}: the file has no rows.")

    for col in NUMERIC_COLUMNS:
        values = pd.to_numeric(df[col], errors="coerce")
        if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
            raise DataError(f"{name}: column '{col}' has missing, non-numeric or infinite values.")
        df[col] = values.astype(float)

    for col in BOOL_COLUMNS:
        df[col] = _to_bool(df[col], col, name)

    for col in ("soc_before", "soc_after"):
        if (df[col] < -1e-6).any() or (df[col] > 1 + 1e-6).any():
            raise DataError(f"{name}: column '{col}' has values outside 0 to 1.")

    for col in ("solar_kw", "load_kw", "price_inr_kwh", "backup_kw", "curtailed_kw"):
        if (df[col] < -1e-9).any():
            raise DataError(f"{name}: column '{col}' has negative values.")

    if not df["step"].is_monotonic_increasing or df["step"].duplicated().any():
        raise DataError(f"{name}: 'step' is not strictly increasing.")

    # Helper columns. Hour of day is inferred from row order (hourly rows).
    idx = np.arange(len(df))
    df["t_day"] = idx / 24.0 + 1.0
    df["day_idx"] = idx // 24
    df["hour"] = idx % 24
    return df.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_metrics(path_str: str, mtime: float) -> pd.DataFrame:
    path = Path(path_str)
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        raise DataError(f"{path.name}: could not be read ({exc}).") from exc

    missing = [c for c in METRIC_COLUMNS if c not in df.columns]
    if missing:
        raise DataError(f"{path.name}: missing columns {missing}.")

    df["shield_enabled"] = _to_bool(df["shield_enabled"], "shield_enabled", path.name)
    for col in METRIC_COLUMNS:
        if col in ("scenario", "shield_enabled"):
            continue
        values = pd.to_numeric(df[col], errors="coerce")
        if values.isna().any():
            raise DataError(f"{path.name}: column '{col}' has missing or non-numeric values.")
        df[col] = values.astype(float)

    for key in SCENARIO_KEYS:
        rows = df[df["scenario"] == key]
        if len(rows) != 2 or set(rows["shield_enabled"]) != {True, False}:
            raise DataError(
                f"{path.name}: scenario '{key}' needs exactly one shielded and one unshielded row."
            )
    return df


def get_run(key: str, kind: str) -> pd.DataFrame:
    p = run_path(key, kind)
    return load_run(str(p), p.stat().st_mtime)


def get_metrics() -> pd.DataFrame:
    return load_metrics(str(METRICS_FILE), METRICS_FILE.stat().st_mtime)


def metric_row(metrics: pd.DataFrame, key: str, shielded: bool) -> pd.Series:
    rows = metrics[(metrics["scenario"] == key) & (metrics["shield_enabled"] == shielded)]
    return rows.iloc[0]


def summarize(df: pd.DataFrame) -> dict[str, float]:
    """Totals recomputed directly from the per-step file."""
    dt = DT_HOURS
    return {
        "steps": len(df),
        "cost": float(df["step_cost_inr"].sum()),
        "violations": int((~df["safe_action"]).sum()),
        "interventions": int(df["shield_intervened"].sum()),
        "backup_kwh": float(df["backup_kw"].sum() * dt),
        "curtailed_kwh": float(df["curtailed_kw"].sum() * dt),
        "solar_kwh": float(df["solar_kw"].sum() * dt),
        "load_kwh": float(df["load_kw"].sum() * dt),
        "charge_kwh": float((-df["executed_kw"].clip(upper=0)).sum() * dt),
        "discharge_kwh": float(df["executed_kw"].clip(lower=0).sum() * dt),
    }


# --------------------------------------------------------------------------
# UI building blocks
# --------------------------------------------------------------------------
def metric_card(
    title: str,
    value: str,
    sub: str = "",
    delta: str = "",
    tone: str = "neutral",
    small: bool = False,
    dot: bool = False,
) -> str:
    dot_html = '<span class="bd-dot"></span>' if dot else ""
    delta_html = f'<span class="bd-delta {tone}">{delta}</span>' if delta else ""
    sub_html = f"<span>{sub}</span>" if sub else ""
    cls = "bd-card-value sm" if small else "bd-card-value"
    return (
        '<div class="bd-card">'
        f'<div class="bd-card-head"><span class="bd-card-title">{title}</span>{dot_html}</div>'
        f'<div class="{cls}">{value}</div>'
        f'<div class="bd-card-foot">{delta_html}{sub_html}</div>'
        "</div>"
    )


def card_row(cards: list[str]) -> None:
    cols = st.columns(len(cards), gap="medium")
    for col, html_card in zip(cols, cards):
        with col:
            st.markdown(html_card, unsafe_allow_html=True)


def scenario_insights(metrics: pd.DataFrame) -> dict[str, dict[str, object]]:
    """Summarize the strongest, safest and fastest scenario across the benchmark set."""
    rows = []
    for key in SCENARIO_KEYS:
        mu, ms = metric_row(metrics, key, False), metric_row(metrics, key, True)
        rows.append({
            "key": key,
            "label": SCENARIOS[key]["label"],
            "cost_saving_inr": float(mu["total_cost_inr"] - ms["total_cost_inr"]),
            "violations_avoided": int(mu["safety_violations"] - ms["safety_violations"]),
            "mean_latency_ms": float(ms["mean_shield_latency_ms"]),
        })

    return {
        "best_cost": max(rows, key=lambda r: r["cost_saving_inr"]),
        "best_safety": max(rows, key=lambda r: r["violations_avoided"]),
        "fastest": min(rows, key=lambda r: r["mean_latency_ms"]),
    }


def gap() -> None:
    st.markdown('<div class="bd-gap"></div>', unsafe_allow_html=True)


def section_header(title: str, subtitle: str = "") -> None:
    sub = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(f'<div class="bd-sec"><h2>{esc(title)}</h2>{sub}</div>', unsafe_allow_html=True)
    gap()


_card_counter = [0]


def chart_card(title: str, fig: go.Figure, caption: str = "") -> None:
    """Draw a titled chart inside a recessed card."""
    _card_counter[0] += 1
    n = _card_counter[0]
    try:
        box = st.container(key=f"card-{n}")
    except TypeError:  # very old Streamlit without container keys
        box = st.container(border=True)
    with box:
        st.markdown(f'<p class="bd-ctitle">{title}</p>', unsafe_allow_html=True)
        if caption:
            st.markdown(f'<p class="bd-ccap">{caption}</p>', unsafe_allow_html=True)
        config = {"displayModeBar": False}
        try:
            st.plotly_chart(fig, width="stretch", config=config, key=f"chart-{n}")
        except TypeError:
            st.plotly_chart(fig, use_container_width=True, config=config, key=f"chart-{n}")
    gap()


def note_card(title: str, body_html: str) -> None:
    _card_counter[0] += 1
    try:
        box = st.container(key=f"card-{_card_counter[0]}")
    except TypeError:
        box = st.container(border=True)
    with box:
        st.markdown(f'<p class="bd-ctitle">{title}</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="bd-note">{body_html}</div>', unsafe_allow_html=True)
    gap()


def error_panel(title: str, lines: list[str], command: str | None = None) -> None:
    items = "".join(f"<li>{line}</li>" for line in lines)
    st.markdown(
        f'<div class="bd-error"><h3>{esc(title)}</h3><ul>{items}</ul></div>',
        unsafe_allow_html=True,
    )
    if command:
        st.code(command, language="bash")


def segmented(options: list, key: str, default, format_func=str):
    """Pill-style single choice. Falls back to a radio on older Streamlit."""
    last_key = f"_last_{key}"
    _, control_col, _ = st.columns([1, 3, 1], gap="small")
    with control_col:
        if hasattr(st, "segmented_control"):
            value = st.segmented_control(
                key, options, default=default, key=key,
                format_func=format_func, label_visibility="collapsed",
            )
        else:
            value = st.radio(
                key, options, index=options.index(default), key=key,
                horizontal=True, format_func=format_func, label_visibility="collapsed",
            )
    if value is None:  # user clicked the selected pill again
        value = st.session_state.get(last_key, default)
    st.session_state[last_key] = value
    return value


# --------------------------------------------------------------------------
# Plot helpers
# --------------------------------------------------------------------------
def style_fig(
    fig: go.Figure,
    height: int = 340,
    ytitle: str | None = None,
    xtitle: str | None = None,
    legend: bool = True,
    hovermode: str = "x unified",
) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=4, r=8, t=8, b=4),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_STACK, size=12, color=ASH),
        hovermode=hovermode,
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor="#0b0c0e", bordercolor=GRAPHITE,
                        font=dict(family=FONT_STACK, color=WHITE, size=12)),
        bargap=0.25,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=GRAPHITE, tickcolor=GRAPHITE,
                     automargin=True)
    fig.update_yaxes(gridcolor="#15171a", zeroline=False, linecolor=GRAPHITE, automargin=True)
    if xtitle:
        fig.update_xaxes(title_text=xtitle)
    if ytitle:
        fig.update_yaxes(title_text=ytitle)
    return fig


def line_trace(df: pd.DataFrame, y: pd.Series | np.ndarray, name: str, color: str,
               width: float = 1.3, dash: str | None = None) -> go.Scattergl:
    return go.Scattergl(
        x=df["t_day"], y=y, name=name, mode="lines",
        line=dict(color=color, width=width, dash=dash),
    )


def soc_figure(base: pd.DataFrame, shld: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_hrect(y0=SOC_MIN * 100, y1=SOC_MAX * 100, fillcolor="rgba(63,203,127,0.06)",
                  line_width=0, layer="below")
    for level in (SOC_MIN * 100, SOC_MAX * 100):
        fig.add_hline(y=level, line=dict(color=STEEL, width=1, dash="dot"))
    fig.add_trace(line_trace(base, base["soc_after"] * 100, "Unshielded", VIOLET))
    fig.add_trace(line_trace(shld, shld["soc_after"] * 100, "Shielded", MINT))
    style_fig(fig, height=360, ytitle="State of charge (%)", xtitle="Day")
    fig.update_yaxes(range=[-2, 102])
    return fig


def proposed_executed_figure(shld: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for level in (-MAX_POWER_KW, MAX_POWER_KW):
        fig.add_hline(y=level, line=dict(color=STEEL, width=1, dash="dot"))
    fig.add_trace(line_trace(shld, shld["proposed_kw"], "Proposed by controller", STEEL, 1.1))
    fig.add_trace(line_trace(shld, shld["executed_kw"], "Executed after shield", MINT, 1.4))
    style_fig(fig, height=340, ytitle="Battery power (kW, + discharge)", xtitle="Day")
    return fig


def charge_discharge_figure(shld: pd.DataFrame) -> go.Figure:
    p = shld["executed_kw"].to_numpy()
    fig = go.Figure()
    fig.add_trace(go.Bar(x=shld["t_day"], y=np.where(p >= 0, p, np.nan), name="Discharging",
                         marker=dict(color=MINT, line_width=0)))
    fig.add_trace(go.Bar(x=shld["t_day"], y=np.where(p < 0, p, np.nan), name="Charging",
                         marker=dict(color=VIOLET, line_width=0)))
    style_fig(fig, height=300, ytitle="Executed power (kW)", xtitle="Day")
    fig.update_layout(barmode="relative", bargap=0)
    return fig


def grouped_bar(categories: list[str], series: list[tuple[str, list[float], str]],
                ytitle: str, height: int = 300, tickformat: str | None = None) -> go.Figure:
    fig = go.Figure()
    for name, values, color in series:
        fig.add_trace(go.Bar(x=categories, y=values, name=name,
                             marker=dict(color=color, line_width=0)))
    style_fig(fig, height=height, ytitle=ytitle)
    fig.update_layout(barmode="group", bargap=0.35, bargroupgap=0.08)
    if tickformat:
        fig.update_yaxes(tickformat=tickformat)
    return fig


# --------------------------------------------------------------------------
# Time window
# --------------------------------------------------------------------------
WINDOWS = {"7 days": 7, "30 days": 30, "Full year": None}


def choose_window(n_rows: int) -> tuple[int, int, str]:
    """Return (start_row, end_row, label) for the time-series charts."""
    n_days = max(1, n_rows // 24)
    options = [w for w, d in WINDOWS.items() if d is None or d < n_days]
    if "Full year" not in options:
        options.append("Full year")
    default = "30 days" if "30 days" in options else options[0]

    st.markdown('<div class="bd-ctl-label">Time window for time-series charts</div>',
                unsafe_allow_html=True)
    window = segmented(options, "window", default)
    if window not in options:
        window = default

    days = WINDOWS[window]
    if days is None:
        return 0, n_rows, "full simulated period"

    max_start = max(1, n_days - days + 1)
    left, mid, right = st.columns([1, 2, 1])
    with mid:
        start_day = st.slider("Starting day", 1, max_start, 1, key=f"start_{window}")
    start = (start_day - 1) * 24
    end = min(n_rows, start + days * 24)
    return start, end, f"days {start_day}\u2013{start_day + days - 1}"


# --------------------------------------------------------------------------
# Tabs
# --------------------------------------------------------------------------
def tab_overview(key: str, metrics: pd.DataFrame, base: pd.DataFrame, shld: pd.DataFrame) -> None:
    info = SCENARIOS[key]
    mu, ms = metric_row(metrics, key, False), metric_row(metrics, key, True)
    diff = ms["total_cost_inr"] - mu["total_cost_inr"]
    diff_pct = diff / mu["total_cost_inr"] * 100 if mu["total_cost_inr"] else 0.0
    insights = scenario_insights(metrics)

    section_header("Overview", f"{esc(info['label'])}. {esc(info['desc'])}")

    card_row([
        metric_card("Selected scenario", esc(info["label"]), "Random test controller", small=True, dot=True),
        metric_card("Benchmark leader", esc(insights["best_cost"]["label"]), "Largest cost reduction", small=True),
        metric_card("Best cost savings", inr(insights["best_cost"]["cost_saving_inr"]),
                    "Shielded vs unshielded", small=True),
        metric_card("Fastest shield response", latency(insights["fastest"]["mean_latency_ms"]),
                    f"{esc(insights['fastest']['label'])} scenario", small=True),
    ])
    gap()

    card_row([
        metric_card("Simulation steps", count(ms["simulation_steps"]), f"{DT_HOURS:g} hour per step"),
        metric_card("Operating cost (shielded)", inr(ms["total_cost_inr"]),
                    f"Unshielded: {inr(mu['total_cost_inr'])}"),
        metric_card("Cost difference", inr(diff, signed=True),
                    "Shielded minus unshielded",
                    delta=pct(diff_pct, 1, signed=True),
                    tone="good" if diff < 0 else "neutral"),
        metric_card("Safety violations (shielded)", count(ms["safety_violations"]),
                    f"Unshielded: {count(mu['safety_violations'])} ({mu['violation_rate_percent']:.2f}% of steps)"),
    ])
    gap()
    card_row([
        metric_card("Shield interventions", count(ms["interventions"]),
                    f"{ms['intervention_rate_percent']:.2f}% of steps"),
        metric_card("Mean shield latency", latency(ms["mean_shield_latency_ms"]),
                    "Time per shield call, shielded run", small=True),
        metric_card("P95 shield latency", latency(ms["p95_shield_latency_ms"]),
                    f"Single worst call: {latency(ms['max_shield_latency_ms'])}", small=True),
        metric_card("Most violations avoided", count(insights["best_safety"]["violations_avoided"]),
                    f"{esc(insights['best_safety']['label'])} scenario", small=True),
    ])
    gap()

    fig = go.Figure()
    fig.add_trace(line_trace(base, base["step_cost_inr"].cumsum() / 1e5, "Unshielded", VIOLET, 1.6))
    fig.add_trace(line_trace(shld, shld["step_cost_inr"].cumsum() / 1e5, "Shielded", MINT, 1.6))
    style_fig(fig, height=340, ytitle="Cumulative cost (\u20b9 lakh)", xtitle="Day")
    chart_card(
        "Cumulative operating cost",
        fig,
        "Grid backup energy multiplied by the tariff, summed over the full simulated period. "
        "The two runs also differ in their battery trajectories, so the gap is not a per-step saving.",
    )


def tab_battery(key: str, base: pd.DataFrame, shld: pd.DataFrame, s: int, e: int, wlabel: str) -> None:
    section_header(
        "Battery analytics",
        f"State of charge and battery power for {esc(SCENARIOS[key]['label'])}. "
        f"Time-series charts show {esc(wlabel)}.",
    )
    b, h = base.iloc[s:e], shld.iloc[s:e]

    chart_card(
        "Battery state of charge, shielded vs unshielded",
        soc_figure(b, h),
        f"Shaded band is the safe range ({SOC_MIN * 100:.0f}\u2013{SOC_MAX * 100:.0f}%). "
        "State of charge is the value after each step.",
    )
    chart_card(
        "Proposed vs executed battery power (shielded run)",
        proposed_executed_figure(h),
        f"Dotted lines mark the \u00b1{MAX_POWER_KW:.0f} kW power limit. "
        "Where the two lines differ, the shield changed the controller's proposal.",
    )
    chart_card(
        "Charging and discharging behaviour (shielded run)",
        charge_discharge_figure(h),
        "Positive bars are discharging, negative bars are charging.",
    )

    left, right = st.columns(2, gap="medium")
    sb, ss = summarize(base), summarize(shld)
    with left:
        fig = grouped_bar(
            ["Charged", "Discharged"],
            [("Unshielded", [sb["charge_kwh"], sb["discharge_kwh"]], VIOLET),
             ("Shielded", [ss["charge_kwh"], ss["discharge_kwh"]], MINT)],
            "Commanded energy (kWh)", tickformat=",.0f",
        )
        chart_card(
            "Commanded battery energy, full period",
            fig,
            "Executed power multiplied by time step. The unshielded run can command power the "
            "battery cannot physically absorb at its SoC limits.",
        )
    with right:
        fig = go.Figure()
        for df, name, color in ((base, "Unshielded", VIOLET), (shld, "Shielded", MINT)):
            prof = df.groupby("hour")["executed_kw"].mean()
            fig.add_trace(go.Scatter(x=prof.index, y=prof.values, name=name, mode="lines+markers",
                                     line=dict(color=color, width=1.6), marker=dict(size=5)))
        style_fig(fig, height=300, ytitle="Mean executed power (kW)", xtitle="Hour of day")
        fig.update_xaxes(dtick=3)
        chart_card(
            "Mean executed power by hour of day",
            fig,
            "Hour of day is inferred from row order (one row per hour).",
        )


def tab_energy(key: str, base: pd.DataFrame, shld: pd.DataFrame, s: int, e: int, wlabel: str) -> None:
    section_header(
        "Energy flow analytics",
        f"Solar, load, grid backup and curtailment for {esc(SCENARIOS[key]['label'])}. "
        f"Time-series charts show {esc(wlabel)}.",
    )
    sb, ss = summarize(base), summarize(shld)
    card_row([
        metric_card("Solar generation", kwh(sb["solar_kwh"]), "Scenario input, full period"),
        metric_card("Load demand", kwh(sb["load_kwh"]), "Scenario input, full period"),
        metric_card("Grid backup energy", kwh(ss["backup_kwh"]), f"Shielded. Unshielded: {kwh(sb['backup_kwh'])}",
                    small=True),
        metric_card("Curtailed energy", kwh(ss["curtailed_kwh"]), f"Shielded. Unshielded: {kwh(sb['curtailed_kwh'])}",
                    small=True),
    ])
    gap()

    b, h = base.iloc[s:e], shld.iloc[s:e]

    fig = go.Figure()
    fig.add_trace(line_trace(h, h["solar_kw"], "Solar generation", BONE, 1.4))
    fig.add_trace(line_trace(h, h["load_kw"], "Load demand", STEEL, 1.4))
    style_fig(fig, height=320, ytitle="Power (kW)", xtitle="Day")
    chart_card("Solar generation and load demand", fig,
               "These inputs are identical for the shielded and unshielded runs.")

    fig = go.Figure()
    fig.add_trace(line_trace(b, b["backup_kw"], "Unshielded", VIOLET, 1.2))
    fig.add_trace(line_trace(h, h["backup_kw"], "Shielded", MINT, 1.2))
    style_fig(fig, height=320, ytitle="Grid backup power (kW)", xtitle="Day")
    chart_card("Grid backup power", fig,
               "Whatever load is not covered by solar and the battery is supplied by the grid "
               "(the model assumes unlimited grid backup, so unmet load is always zero).")

    daily_b = b.groupby("day_idx")["curtailed_kw"].sum() * DT_HOURS
    daily_h = h.groupby("day_idx")["curtailed_kw"].sum() * DT_HOURS
    x = (daily_h.index + 1).tolist()
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x, y=daily_b.values, name="Unshielded", marker=dict(color=VIOLET, line_width=0)))
    fig.add_trace(go.Bar(x=x, y=daily_h.values, name="Shielded", marker=dict(color=MINT, line_width=0)))
    style_fig(fig, height=320, ytitle="Curtailed energy per day (kWh)", xtitle="Day")
    fig.update_layout(barmode="group", bargap=0.2, bargroupgap=0.05)
    chart_card(
        "Curtailed energy per day", fig,
        "In this simulator, curtailed energy is any surplus supply after meeting load: "
        "solar plus battery discharge minus load. It can include discharged battery energy, "
        "so it is not a pure measure of wasted solar.",
    )


def tab_shield(key: str, metrics: pd.DataFrame, base: pd.DataFrame, shld: pd.DataFrame,
               s: int, e: int, wlabel: str) -> None:
    mu, ms = metric_row(metrics, key, False), metric_row(metrics, key, True)
    section_header(
        "Safety shield analytics",
        f"What the shield did in the {esc(SCENARIOS[key]['label'])} run.",
    )
    avoided = int(mu["safety_violations"] - ms["safety_violations"])
    card_row([
        metric_card("Total interventions", count(ms["interventions"]), "Steps where executed \u2260 proposed"),
        metric_card("Intervention rate", pct(ms["intervention_rate_percent"]),
                    f"of {count(ms['simulation_steps'])} steps"),
        metric_card("Violations: unshielded minus shielded", count(avoided),
                    f"{count(mu['safety_violations'])} unshielded vs {count(ms['safety_violations'])} shielded",
                    small=True, tone="good"),
        metric_card("Max shield latency", latency(ms["max_shield_latency_ms"]),
                    "Single worst call", small=True),
    ])
    gap()

    h = shld.iloc[s:e]
    daily = h.groupby("day_idx")["shield_intervened"].sum()
    fig = go.Figure(go.Bar(x=(daily.index + 1).tolist(), y=daily.values, name="Interventions",
                           marker=dict(color=MINT, line_width=0)))
    style_fig(fig, height=300, ytitle="Interventions per day", xtitle="Day", legend=False)
    fig.update_layout(bargap=0.15)
    chart_card("Timeline of shield interventions", fig,
               f"Number of hourly steps per day where the shield changed the proposal ({esc(wlabel)}).")

    left, right = st.columns(2, gap="medium")
    with left:
        lat = shld["shield_latency_ms"].to_numpy()
        cap = float(np.percentile(lat, 99.5))
        above = int((lat > cap).sum())
        fig = go.Figure(go.Histogram(x=lat[lat <= cap], nbinsx=40,
                                     marker=dict(color=MINT, line_width=0), name="Shield calls"))
        mean_v, p95_v = float(np.mean(lat)), float(np.percentile(lat, 95))
        fig.add_vline(x=mean_v, line=dict(color=WHITE, width=1, dash="dot"),
                      annotation_text="mean", annotation_font=dict(color=ASH, size=11))
        fig.add_vline(x=p95_v, line=dict(color=VIOLET, width=1, dash="dot"),
                      annotation_text="P95", annotation_font=dict(color=ASH, size=11),
                      annotation_position="top left")
        style_fig(fig, height=300, ytitle="Number of calls (log scale)", xtitle="Latency (ms)",
                  legend=False, hovermode="closest")
        fig.update_yaxes(type="log")
        fig.update_xaxes(tickformat=".4f")
        chart_card(
            "Shield latency distribution", fig,
            f"Time taken by each shield call. The axis is cut at the 99.5th percentile; "
            f"{count(above)} slower calls are not drawn. Values are quantised by the system timer.",
        )
    with right:
        iv = shld[shld["shield_intervened"]]
        if len(iv):
            mag = (iv["proposed_kw"] - iv["executed_kw"]).abs()
            fig = go.Figure(go.Histogram(x=mag, nbinsx=40, marker=dict(color=VIOLET, line_width=0),
                                         name="Interventions"))
            style_fig(fig, height=300, ytitle="Number of interventions", xtitle="Correction size (kW)",
                      legend=False, hovermode="closest")
            chart_card("Size of the shield's corrections", fig,
                       "Absolute difference between proposed and executed battery power, "
                       "for intervened steps only.")
        else:
            note_card("Size of the shield's corrections", "No interventions in this run.")

    iv = shld[shld["shield_intervened"]]
    n_iv = max(len(iv), 1)
    dis = int((iv["proposed_kw"] > 0).sum())
    chg = int((iv["proposed_kw"] < 0).sum())
    card_row([
        metric_card("Discharge proposals changed", count(dis), f"{dis / n_iv * 100:.1f}% of interventions"),
        metric_card("Charge proposals changed", count(chg), f"{chg / n_iv * 100:.1f}% of interventions"),
    ])
    gap()
    note_card(
        "What these numbers do and do not show",
        "<b>Checked:</b> after each step the simulator tests whether the executed action satisfies "
        "<b>rule_soc</b> and <b>rule_power_limit</b> from shield/rules.py. A violation is a step that fails "
        "that test. <b>Violations avoided</b> compares two separate runs; their battery trajectories differ, "
        "so it is not a step-by-step counterfactual.<br>"
        "<b>Not shown:</b> any guarantee beyond those implemented rules, or performance of a learned "
        "controller. The controller here is a random test controller, and the result is one seeded experiment.",
    )


def tab_comparison(selected: str, metrics: pd.DataFrame) -> None:
    section_header(
        "Scenario comparison",
        "All five scenarios side by side. This tab does not depend on the scenario selector, "
        "which only highlights one column.",
    )

    rows = []
    for key in SCENARIO_KEYS:
        mu, ms = metric_row(metrics, key, False), metric_row(metrics, key, True)
        bu = summarize(get_run(key, "baseline"))["backup_kwh"]
        bs = summarize(get_run(key, "shielded"))["backup_kwh"]
        rows.append({
            "key": key, "label": SCENARIOS[key]["label"],
            "cost_u": mu["total_cost_inr"], "cost_s": ms["total_cost_inr"],
            "viol_u": mu["safety_violations"], "viol_s": ms["safety_violations"],
            "int_n": ms["interventions"], "int_rate": ms["intervention_rate_percent"],
            "curt_u": mu["curtailed_energy_kwh"], "curt_s": ms["curtailed_energy_kwh"],
            "back_u": bu, "back_s": bs,
            "lat_mean": ms["mean_shield_latency_ms"], "lat_p95": ms["p95_shield_latency_ms"],
            "lat_max": ms["max_shield_latency_ms"],
        })
    comp = pd.DataFrame(rows)

    # ---- Table ----
    sel_idx = SCENARIO_KEYS.index(selected)

    def cells(values: list[str], good: list[bool] | None = None) -> str:
        out = []
        for i, v in enumerate(values):
            cls = ["sel"] if i == sel_idx else []
            if good and good[i]:
                cls.append("good")
            out.append(f'<td class="{" ".join(cls)}">{esc(v)}</td>')
        return "".join(out)

    def row(label: str, values: list[str], good: list[bool] | None = None) -> str:
        return f"<tr><td>{esc(label)}</td>{cells(values, good)}</tr>"

    def group(label: str) -> str:
        return f'<tr class="grp"><td colspan="{len(rows) + 1}">{esc(label)}</td></tr>'

    cost_diff = comp["cost_s"] - comp["cost_u"]
    cost_diff_pct = cost_diff / comp["cost_u"] * 100
    head = "".join(
        f'<th class="{"sel" if i == sel_idx else ""}">{esc(r["label"])}</th>' for i, r in enumerate(rows)
    )
    body = "".join([
        group("Operating cost"),
        row("Unshielded", [inr(v) for v in comp["cost_u"]]),
        row("Shielded", [inr(v) for v in comp["cost_s"]]),
        row("Difference (shielded \u2212 unshielded)",
            [f"{inr(d, signed=True)} ({pct(p, 1, signed=True)})" for d, p in zip(cost_diff, cost_diff_pct)],
            [d < 0 for d in cost_diff]),
        group("Safety"),
        row("Violations, unshielded", [count(v) for v in comp["viol_u"]]),
        row("Violations, shielded", [count(v) for v in comp["viol_s"]]),
        row("Interventions (shielded)", [count(v) for v in comp["int_n"]]),
        row("Intervention rate (shielded)", [pct(v) for v in comp["int_rate"]]),
        group("Energy"),
        row("Curtailed, unshielded", [kwh(v) for v in comp["curt_u"]]),
        row("Curtailed, shielded", [kwh(v) for v in comp["curt_s"]]),
        row("Grid backup, unshielded", [kwh(v) for v in comp["back_u"]]),
        row("Grid backup, shielded", [kwh(v) for v in comp["back_s"]]),
        group("Shield latency (shielded run)"),
        row("Mean", [latency(v) for v in comp["lat_mean"]]),
        row("P95", [latency(v) for v in comp["lat_p95"]]),
        row("Maximum (single worst call)", [latency(v) for v in comp["lat_max"]]),
    ])
    st.markdown(
        f'<div class="bd-table-wrap"><table class="bd-table"><thead><tr><th></th>{head}</tr></thead>'
        f"<tbody>{body}</tbody></table></div>",
        unsafe_allow_html=True,
    )
    gap()

    labels = comp["label"].tolist()
    two = lambda u, s_: [("Unshielded", list(u), VIOLET), ("Shielded", list(s_), MINT)]

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        chart_card("Operating cost", grouped_bar(labels, two(comp["cost_u"] / 1e5, comp["cost_s"] / 1e5),
                                                 "\u20b9 lakh", tickformat=",.1f"))
    with c2:
        chart_card("Safety violations", grouped_bar(labels, two(comp["viol_u"], comp["viol_s"]),
                                                    "Violating steps", tickformat=",.0f"))
    c3, c4 = st.columns(2, gap="medium")
    with c3:
        chart_card("Intervention rate (shielded)",
                   grouped_bar(labels, [("Shielded", list(comp["int_rate"]), MINT)],
                               "% of steps", tickformat=".1f"))
    with c4:
        chart_card("Curtailed energy", grouped_bar(labels, two(comp["curt_u"], comp["curt_s"]),
                                                   "kWh", tickformat=",.0f"))
    c5, c6 = st.columns(2, gap="medium")
    with c5:
        chart_card("Grid backup energy", grouped_bar(labels, two(comp["back_u"], comp["back_s"]),
                                                     "kWh", tickformat=",.0f"))
    with c6:
        chart_card("Shield latency (shielded run)",
                   grouped_bar(labels, [("Mean", list(comp["lat_mean"]), MINT),
                                        ("P95", list(comp["lat_p95"]), VIOLET)],
                               "ms per shield call", tickformat=".4f"))

    same = (comp["viol_u"].nunique() == 1 and comp["viol_s"].nunique() == 1
            and comp["int_n"].nunique() == 1)
    if same:
        note_card(
            "Why violations and interventions are identical across scenarios",
            "The random test controller ignores the state and depends only on the seed, and the "
            "battery's state of charge depends only on the executed battery power. Solar, load and "
            "tariff therefore change cost, curtailment and grid backup, but not the violation or "
            "intervention counts. This is a property of this experiment, not a finding about the shield.",
        )


# --------------------------------------------------------------------------
# Data checks and notes
# --------------------------------------------------------------------------
def consistency_checks(key: str, metrics: pd.DataFrame, base: pd.DataFrame, shld: pd.DataFrame) -> list[tuple[str, bool]]:
    checks = []
    for shielded, df in ((False, base), (True, shld)):
        tag = "shielded" if shielded else "unshielded"
        m, s = metric_row(metrics, key, shielded), summarize(df)
        checks.append((f"{tag}: steps match scenario_metrics.csv", int(m["simulation_steps"]) == s["steps"]))
        checks.append((f"{tag}: violations match", int(m["safety_violations"]) == s["violations"]))
        checks.append((f"{tag}: interventions match", int(m["interventions"]) == s["interventions"]))
        checks.append((f"{tag}: cost matches",
                       abs(m["total_cost_inr"] - s["cost"]) <= 1e-6 * max(1.0, abs(s["cost"]))))
        checks.append((f"{tag}: curtailed energy matches",
                       abs(m["curtailed_energy_kwh"] - s["curtailed_kwh"]) <= 1e-6 * max(1.0, s["curtailed_kwh"])))
    checks.append(("both runs have the same number of steps", len(base) == len(shld)))
    checks.append(("unmet load is zero in both runs",
                   bool((base["unmet_load_kw"] == 0).all() and (shld["unmet_load_kw"] == 0).all())))
    return checks


def footer(key: str, metrics: pd.DataFrame, base: pd.DataFrame, shld: pd.DataFrame) -> None:
    gap()
    with st.expander("About these results and data checks"):
        st.markdown(
            '<div class="bd-note">'
            "<b>Controller.</b> A random test controller proposes battery power between \u221280 and +80 kW. "
            "It is not an RL agent, and these figures are not RL performance.<br>"
            "<b>Grid backup.</b> The simulator assumes unlimited grid backup, so unmet load is always zero. "
            "The battery does not independently cover demand spikes; the grid supplies any remaining deficit.<br>"
            "<b>Scenarios.</b> Synthetic stress tests derived from one dataset, not independent real-world "
            "weather or demand data. Each result is a single run with a fixed seed.<br>"
            f"<b>Battery.</b> {BATTERY_KWH:g} kWh, safe SoC {SOC_MIN * 100:.0f}\u2013{SOC_MAX * 100:.0f}%, "
            f"power limit {MAX_POWER_KW:g} kW (read from {esc(CONFIG_SOURCE)}). Positive power is discharging.<br>"
            "<b>Time axis.</b> Rows are hourly, so day and hour of day are inferred from row order."
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(f'<div class="bd-ctitle" style="margin-top:16px">Data checks for {esc(SCENARIOS[key]["label"])}</div>',
                    unsafe_allow_html=True)
        results = consistency_checks(key, metrics, base, shld)
        for label, ok in results:
            st.markdown(f"{'\u2713' if ok else '\u2717'}  {label}")
        if not all(ok for _, ok in results):
            st.warning("Some checks failed. The per-step files and scenario_metrics.csv may come from "
                       "different runs. Re-run `python integration/scenarios.py`.")
        st.caption(f"Source folder: {RESULTS_DIR}")


# --------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------
def render_top() -> None:
    st.markdown(
        '<div class="bd-nav">'
        '<div class="bd-brand"><span class="bd-logo"></span>Microgrid Assurance</div>'
        '<div class="bd-status"><span class="bd-dot"></span>Results loaded from CSV</div>'
        "</div>"
        '<div class="bd-hero">'
        '<span class="bd-pill"><span class="bd-dot"></span>Random test controller \u00b7 not an RL agent</span>'
        '<h1 class="bd-h1">Runtime assurance for microgrid energy dispatch</h1>'
        f'<p class="bd-subhead">Shielded versus unshielded simulation of a {BATTERY_KWH:g} kWh battery '
        "microgrid across five synthetic stress scenarios.</p>"
        "</div>",
        unsafe_allow_html=True,
    )


def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    render_top()

    # 1. Are the files there?
    missing = missing_files()
    if missing:
        names = [f"<code>{esc(p.relative_to(REPO_ROOT))}</code>" for p in missing[:12]]
        if len(missing) > 12:
            names.append(f"and {len(missing) - 12} more")
        error_panel(
            "Scenario results not found",
            ["The dashboard reads the files written by integration/scenarios.py, and these are missing:"]
            + names
            + ["Run the generator from the repository root, then refresh this page:"],
            "python integration/scenarios.py",
        )
        st.stop()

    # 2. Are they valid?
    try:
        metrics = get_metrics()
    except DataError as exc:
        error_panel("Scenario metrics file is invalid", [esc(exc), "Re-run the generator to rebuild it."],
                    "python integration/scenarios.py")
        st.stop()

    # 3. Scenario selector.
    st.markdown('<div class="bd-ctl-label">Scenario</div>', unsafe_allow_html=True)
    key = segmented(SCENARIO_KEYS, "scenario", "normal", lambda k: SCENARIOS[k]["label"])
    if key not in SCENARIOS:
        key = "normal"
    st.markdown(f'<div class="bd-scn-desc">{esc(SCENARIOS[key]["desc"])}</div>', unsafe_allow_html=True)

    try:
        base, shld = get_run(key, "baseline"), get_run(key, "shielded")
        if len(base) != len(shld):
            raise DataError(
                f"{key}: baseline has {len(base)} rows but shielded has {len(shld)}. "
                "They must come from the same scenario run."
            )
    except DataError as exc:
        error_panel("A results file is invalid", [esc(exc), "Re-run the generator to rebuild it."],
                    "python integration/scenarios.py")
        st.stop()

    s, e, wlabel = choose_window(len(shld))

    tabs = st.tabs(["Overview", "Battery", "Energy flow", "Safety shield", "Scenario comparison"])
    with tabs[0]:
        tab_overview(key, metrics, base, shld)
    with tabs[1]:
        tab_battery(key, base, shld, s, e, wlabel)
    with tabs[2]:
        tab_energy(key, base, shld, s, e, wlabel)
    with tabs[3]:
        tab_shield(key, metrics, base, shld, s, e, wlabel)
    with tabs[4]:
        try:
            tab_comparison(key, metrics)
        except DataError as exc:
            error_panel("Could not build the comparison", [esc(exc)], "python integration/scenarios.py")

    footer(key, metrics, base, shld)


main()