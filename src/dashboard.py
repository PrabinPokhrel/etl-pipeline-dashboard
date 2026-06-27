"""
dashboard.py
Streamlit dashboard reading live data from Supabase PostgreSQL.
Shows pipeline health, daily revenue trends, and category performance.
"""

import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# ── Supabase client ───────────────────────────────────────────
@st.cache_resource
def get_client():
    # Try Streamlit secrets first (cloud), fall back to env vars (local)
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except Exception:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)

sb = get_client()

# ── Data loaders ──────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_daily_sales():
    res = sb.table("daily_sales") \
            .select("*") \
            .order("sale_date") \
            .execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df["sale_date"] = pd.to_datetime(df["sale_date"])
    return df

@st.cache_data(ttl=300)
def load_product_metrics():
    res = sb.table("product_metrics") \
            .select("*") \
            .order("metric_date") \
            .execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df["metric_date"] = pd.to_datetime(df["metric_date"])
    return df

@st.cache_data(ttl=300)
def load_pipeline_runs():
    res = sb.table("pipeline_runs") \
            .select("*") \
            .order("run_timestamp", desc=True) \
            .limit(100) \
            .execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df["run_timestamp"] = pd.to_datetime(df["run_timestamp"])
        df["run_date"]      = pd.to_datetime(df["run_date"])
    return df

# ── Load data ─────────────────────────────────────────────────
daily    = load_daily_sales()
products = load_product_metrics()
runs     = load_pipeline_runs()

# ── Sidebar ───────────────────────────────────────────────────
st.sidebar.title("ETL Pipeline Dashboard")
st.sidebar.markdown("**Live data from Supabase PostgreSQL**")
st.sidebar.markdown("---")

if not daily.empty:
    min_date = daily["sale_date"].min().date()
    max_date = daily["sale_date"].max().date()

    st.sidebar.markdown("**Filter by date**")
    start_date = st.sidebar.date_input(
        "Start date",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
    )
    end_date = st.sidebar.date_input(
        "End date",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
    )

    if start_date <= end_date:
        daily    = daily[
            (daily["sale_date"].dt.date >= start_date) &
            (daily["sale_date"].dt.date <= end_date)
        ]
        products = products[
            (products["metric_date"].dt.date >= start_date) &
            (products["metric_date"].dt.date <= end_date)
        ]
    else:
        st.sidebar.error("Start date must be before end date")

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Pipeline:** GitHub Actions daily schedule\n\n"
    "**Storage:** Supabase PostgreSQL\n\n"
    "**Stack:** Python, pandas, Supabase, Streamlit, Plotly"
)

# ── Header ────────────────────────────────────────────────────
st.title("Sales ETL Pipeline Dashboard")
st.markdown(
    "Automated daily ETL pipeline - Extract from source, "
    "Transform to aggregates, Load to Supabase PostgreSQL. "
    "Dashboard refreshes every 5 minutes."
)

# ── KPI cards ─────────────────────────────────────────────────
if not daily.empty:
    col1, col2, col3, col4, col5 = st.columns(5)

    total_rev  = daily["total_revenue"].sum()
    total_ord  = daily["total_orders"].sum()
    avg_daily  = daily["total_revenue"].mean()
    peak_rev   = daily["total_revenue"].max()
    n_days     = len(daily)

    col1.metric("Total Revenue",    f"£{total_rev:,.0f}")
    col2.metric("Total Orders",     f"{total_ord:,}")
    col3.metric("Avg Daily Revenue",f"£{avg_daily:,.0f}")
    col4.metric("Peak Day Revenue", f"£{peak_rev:,.0f}")
    col5.metric("Days Loaded",      f"{n_days}")

st.markdown("---")

# ── Revenue trend ─────────────────────────────────────────────
st.subheader("Daily Revenue Trend")

if not daily.empty:
    daily_sorted = daily.sort_values("sale_date")
    daily_sorted["rolling_7d"] = daily_sorted["total_revenue"] \
                                    .rolling(7, min_periods=1).mean()

    fig_rev = go.Figure()
    fig_rev.add_trace(go.Bar(
        x    = daily_sorted["sale_date"],
        y    = daily_sorted["total_revenue"],
        name = "Daily Revenue",
        marker_color = "#2563eb",
        opacity      = 0.6,
    ))
    fig_rev.add_trace(go.Scatter(
        x    = daily_sorted["sale_date"],
        y    = daily_sorted["rolling_7d"],
        name = "7-Day Rolling Avg",
        line = dict(color="#f59e0b", width=2.5),
    ))
    fig_rev.update_layout(
        height       = 380,
        legend       = dict(orientation="h", y=1.1),
        yaxis_title  = "Revenue (£)",
        xaxis_title  = "Date",
        hovermode    = "x unified",
        plot_bgcolor = "rgba(0,0,0,0)",
        paper_bgcolor= "rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_rev, use_container_width=True)

# ── Category performance ──────────────────────────────────────
st.subheader("Category Performance")

col_left, col_right = st.columns(2)

if not products.empty:
    # Revenue by category over time
    cat_pivot = products.pivot_table(
        index   = "metric_date",
        columns = "category",
        values  = "total_revenue",
        aggfunc = "sum"
    ).reset_index()

    fig_cat = px.area(
        cat_pivot,
        x       = "metric_date",
        y       = [c for c in cat_pivot.columns if c != "metric_date"],
        title   = "Revenue by Category Over Time",
        labels  = {"value": "Revenue (£)", "metric_date": "Date",
                   "variable": "Category"},
        color_discrete_sequence = ["#2563eb", "#16a34a", "#dc2626"],
    )
    fig_cat.update_layout(
        height       = 320,
        plot_bgcolor = "rgba(0,0,0,0)",
        paper_bgcolor= "rgba(0,0,0,0)",
        legend       = dict(orientation="h", y=1.1),
    )
    col_left.plotly_chart(fig_cat, use_container_width=True)

    # Category totals donut
    cat_totals = products.groupby("category")["total_revenue"] \
                         .sum().reset_index()
    fig_donut = px.pie(
        cat_totals,
        values = "total_revenue",
        names  = "category",
        hole   = 0.45,
        title  = "Revenue Share by Category",
        color_discrete_sequence = ["#2563eb", "#16a34a", "#dc2626"],
    )
    fig_donut.update_layout(
        height       = 320,
        plot_bgcolor = "rgba(0,0,0,0)",
        paper_bgcolor= "rgba(0,0,0,0)",
    )
    col_right.plotly_chart(fig_donut, use_container_width=True)

# ── Orders and avg order value ────────────────────────────────
st.subheader("Order Volume and Average Order Value")

col_a, col_b = st.columns(2)

if not daily.empty:
    fig_orders = px.bar(
        daily.sort_values("sale_date"),
        x     = "sale_date",
        y     = "total_orders",
        title = "Daily Order Volume",
        color_discrete_sequence = ["#16a34a"],
    )
    fig_orders.update_layout(
        height       = 280,
        plot_bgcolor = "rgba(0,0,0,0)",
        paper_bgcolor= "rgba(0,0,0,0)",
        yaxis_title  = "Orders",
        xaxis_title  = "Date",
    )
    col_a.plotly_chart(fig_orders, use_container_width=True)

    fig_aov = px.line(
        daily.sort_values("sale_date"),
        x     = "sale_date",
        y     = "avg_order_value",
        title = "Average Order Value (£)",
        color_discrete_sequence = ["#7c3aed"],
    )
    fig_aov.update_layout(
        height       = 280,
        plot_bgcolor = "rgba(0,0,0,0)",
        paper_bgcolor= "rgba(0,0,0,0)",
        yaxis_title  = "AOV (£)",
        xaxis_title  = "Date",
    )
    col_b.plotly_chart(fig_aov, use_container_width=True)

# ── Pipeline health ───────────────────────────────────────────
st.markdown("---")
st.subheader("Pipeline Health")

if not runs.empty:
    col_h1, col_h2, col_h3, col_h4 = st.columns(4)

    success_count = (runs["status"] == "SUCCESS").sum()
    failed_count  = (runs["status"] == "FAILED").sum()
    success_rate  = success_count / len(runs) * 100
    avg_duration  = runs["duration_secs"].mean()

    col_h1.metric("Total Runs",    len(runs))
    col_h2.metric("Successful",    success_count)
    col_h3.metric("Success Rate",  f"{success_rate:.1f}%")
    col_h4.metric("Avg Duration",  f"{avg_duration:.1f}s")

    # Recent runs table
    st.markdown("**Recent Pipeline Runs**")
    display_runs = runs[["run_date", "status", "rows_extracted",
                          "rows_loaded", "duration_secs",
                          "run_timestamp"]].head(20).copy()
    display_runs.columns = ["Date", "Status", "Rows Extracted",
                             "Rows Loaded", "Duration (s)", "Timestamp"]
    display_runs["Status"] = display_runs["Status"].apply(
        lambda x: "SUCCESS" if x == "SUCCESS" else "FAILED"
    )
    st.dataframe(display_runs, use_container_width=True, hide_index=True)

# ── Footer ────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "Built by **Prabin Pokhrel** | "
    "MSc Microdata Analysis, Dalarna University | "
    "[GitHub](https://github.com/PrabinPokhrel)"
)