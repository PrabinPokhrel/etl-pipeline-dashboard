"""
pipeline.py
ETL pipeline: Extract synthetic sales data, Transform, Load to Supabase.
Designed to run daily via GitHub Actions.

Pipeline steps:
  1. EXTRACT  - Generate daily sales data (simulates API/database source)
  2. TRANSFORM - Aggregate to daily and category-level metrics
  3. LOAD     - Upsert to Supabase PostgreSQL
  4. LOG      - Record pipeline run metadata
"""

import os
import time
import random
import numpy as np
import pandas as pd
from datetime import date, timedelta
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# ── Supabase client ───────────────────────────────────────────
url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_KEY"]
sb  = create_client(url, key)

# ── Constants ─────────────────────────────────────────────────
CATEGORIES   = ["Technology", "Furniture", "Office Supplies"]
PRODUCTS_PER = {"Technology": 50, "Furniture": 30, "Office Supplies": 40}
BASE_REVENUE  = {"Technology": 800, "Furniture": 400, "Office Supplies": 150}

random.seed(int(date.today().strftime("%Y%m%d")))
np.random.seed(int(date.today().strftime("%Y%m%d")))


# ── EXTRACT ───────────────────────────────────────────────────
def extract(target_date: date) -> pd.DataFrame:
    """
    Simulates extracting raw transaction records for a given date.
    In production this would query a source database or API.
    """
    print(f"  [EXTRACT] Generating transactions for {target_date}...")

    # Weekday multiplier - lower on weekends
    weekday = target_date.weekday()
    day_factor = 1.0 if weekday < 5 else 0.4

    # Seasonal factor - higher in Q4
    month = target_date.month
    seasonal = 1.0 + 0.3 * (month >= 10) + 0.1 * (month in [3, 4, 5])

    records = []
    for category in CATEGORIES:
        n_orders = int(np.random.poisson(
            lam=20 * day_factor * seasonal
        ))
        base = BASE_REVENUE[category]

        for _ in range(n_orders):
            qty      = random.randint(1, 8)
            price    = round(random.uniform(base * 0.5, base * 2.0), 2)
            discount = random.choice([0, 0, 0, 0.1, 0.15, 0.2])
            revenue  = round(qty * price * (1 - discount), 2)

            records.append({
                "date":     target_date.isoformat(),
                "category": category,
                "quantity": qty,
                "price":    price,
                "discount": discount,
                "revenue":  revenue,
            })

    df = pd.DataFrame(records)
    print(f"    Extracted {len(df)} raw transactions")
    return df


# ── TRANSFORM ─────────────────────────────────────────────────
def transform(df: pd.DataFrame, target_date: date):
    """
    Transforms raw transactions into two aggregated outputs:
      1. daily_summary  - one row per day
      2. category_summary - one row per category per day
    """
    print(f"  [TRANSFORM] Aggregating {len(df)} transactions...")

    # Daily summary
    daily = {
        "sale_date":       target_date.isoformat(),
        "total_revenue":   round(df["revenue"].sum(), 2),
        "total_orders":    len(df),
        "total_units":     int(df["quantity"].sum()),
        "avg_order_value": round(df["revenue"].mean(), 2),
        "top_category":    df.groupby("category")["revenue"]
                             .sum().idxmax(),
    }

    # Category summary
    cat_agg = df.groupby("category").agg(
        total_revenue = ("revenue",  "sum"),
        total_units   = ("quantity", "sum"),
        avg_price     = ("price",    "mean"),
    ).reset_index()
    cat_agg["metric_date"] = target_date.isoformat()
    cat_agg["total_revenue"] = cat_agg["total_revenue"].round(2)
    cat_agg["avg_price"]     = cat_agg["avg_price"].round(2)

    print(f"    Daily revenue  : £{daily['total_revenue']:,.2f}")
    print(f"    Total orders   : {daily['total_orders']}")
    print(f"    Top category   : {daily['top_category']}")

    return daily, cat_agg


# ── LOAD ──────────────────────────────────────────────────────
def load(daily: dict, cat_agg: pd.DataFrame, target_date: date):
    """
    Upserts transformed data to Supabase PostgreSQL.
    Uses upsert to handle re-runs gracefully.
    """
    print(f"  [LOAD] Upserting to Supabase...")

    # Upsert daily_sales
    sb.table("daily_sales").upsert(
        daily,
        on_conflict="sale_date"
    ).execute()
    print(f"    daily_sales    : 1 row upserted")

    # Upsert product_metrics
    cat_records = cat_agg.to_dict(orient="records")
    sb.table("product_metrics").upsert(
        cat_records,
        on_conflict="metric_date,category"
    ).execute()
    print(f"    product_metrics: {len(cat_records)} rows upserted")


# ── LOG ───────────────────────────────────────────────────────
def log_run(target_date: date, status: str, rows_extracted: int,
            rows_loaded: int, duration: float, error: str = None):
    """Records pipeline run metadata to pipeline_runs table."""
    sb.table("pipeline_runs").insert({
        "run_date":       target_date.isoformat(),
        "status":         status,
        "rows_extracted": rows_extracted,
        "rows_loaded":    rows_loaded,
        "duration_secs":  round(duration, 2),
        "error_message":  error,
    }).execute()


# ── MAIN PIPELINE ─────────────────────────────────────────────
def run_pipeline(target_date: date = None, backfill_days: int = 0):
    """
    Runs the full ETL pipeline for one or more dates.
    backfill_days > 0 runs pipeline for the past N days.
    """
    if target_date is None:
        target_date = date.today()

    dates = [target_date - timedelta(days=i)
             for i in range(backfill_days, -1, -1)]

    print("=" * 55)
    print("ETL PIPELINE - SALES DATA")
    print("=" * 55)
    print(f"Target dates  : {dates[0]} to {dates[-1]}")
    print(f"Dates to process: {len(dates)}")

    total_extracted = 0
    total_loaded    = 0

    for d in dates:
        print(f"\nProcessing {d}...")
        t0 = time.time()
        try:
            raw_df           = extract(d)
            daily, cat_agg   = transform(raw_df, d)
            load(daily, cat_agg, d)

            rows_ext   = len(raw_df)
            rows_load  = 1 + len(cat_agg)
            duration   = time.time() - t0

            log_run(d, "SUCCESS", rows_ext, rows_load, duration)
            total_extracted += rows_ext
            total_loaded    += rows_load
            print(f"  Done in {duration:.2f}s")

        except Exception as e:
            duration = time.time() - t0
            log_run(d, "FAILED", 0, 0, duration, str(e))
            print(f"  ERROR: {e}")

    print(f"\n{'='*55}")
    print(f"PIPELINE COMPLETE")
    print(f"  Dates processed : {len(dates)}")
    print(f"  Rows extracted  : {total_extracted:,}")
    print(f"  Rows loaded     : {total_loaded:,}")
    print(f"{'='*55}")


if __name__ == "__main__":
    # Run pipeline for today + backfill last 89 days (90 days total)
    run_pipeline(backfill_days=89)