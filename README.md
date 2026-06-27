# ETL Pipeline Dashboard

**Automated daily sales ETL pipeline with Supabase PostgreSQL backend and live Streamlit dashboard**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Live-red)](https://streamlit.io/)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-green)](https://supabase.com/)
[![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Daily%20Schedule-blue)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status: Complete](https://img.shields.io/badge/Status-Complete-brightgreen)]()

> **Portfolio project for data analyst applications in Stockholm. Demonstrates a production-style automated ETL pipeline: synthetic sales data extracted daily, transformed to aggregates, loaded to Supabase PostgreSQL, and visualised in a live Streamlit dashboard. GitHub Actions runs the pipeline automatically at 06:00 UTC every day.**

---

## Live Dashboard

The dashboard reads live data from Supabase PostgreSQL and refreshes every 5 minutes.

**Features:**
- 5 KPI cards: total revenue, total orders, avg daily revenue, peak day revenue, days loaded
- Daily revenue trend with 7-day rolling average overlay
- Category performance: area chart over time + revenue share donut
- Daily order volume and average order value
- Pipeline health monitor: success rate, run log, duration tracking
- Interactive date range filter (start and end date pickers)

---

## Pipeline Architecture

```
Source (synthetic sales generator)
           |
           v
    EXTRACT
    - Simulates daily transaction pull from source system
    - Generates Poisson-distributed order counts with weekday
      and seasonal multipliers
    - Produces raw transaction records with category, quantity,
      price, discount, revenue
           |
           v
    TRANSFORM
    - Aggregates raw transactions to daily_sales (1 row per day)
    - Aggregates to product_metrics (1 row per category per day)
    - Computes: total revenue, order count, units sold,
      avg order value, top category
           |
           v
    LOAD (Supabase PostgreSQL)
    - Upserts daily_sales on sale_date conflict
    - Upserts product_metrics on (metric_date, category) conflict
    - Idempotent: safe to re-run for same date
           |
           v
    LOG
    - Records run metadata to pipeline_runs table
    - Tracks: status, rows extracted, rows loaded, duration
           |
           v
    GitHub Actions (daily 06:00 UTC)
    - Checks out repo, installs dependencies
    - Runs src/pipeline.py with Supabase secrets
    - Logs success/failure to Supabase
           |
           v
    Streamlit Dashboard
    - Reads from all three Supabase tables
    - Caches data for 5 minutes (ttl=300)
    - Interactive date filtering
    - Pipeline health monitoring
```

---

## Database Schema

Three tables in Supabase PostgreSQL:

**pipeline_runs** - ETL run log
| Column | Type | Description |
|---|---|---|
| id | BIGSERIAL | Primary key |
| run_date | DATE | Date processed |
| run_timestamp | TIMESTAMPTZ | When pipeline ran |
| status | TEXT | SUCCESS or FAILED |
| rows_extracted | INTEGER | Raw transactions extracted |
| rows_loaded | INTEGER | Rows upserted to Supabase |
| duration_secs | REAL | Pipeline runtime |
| error_message | TEXT | Error detail if failed |

**daily_sales** - Daily aggregates (unique per date)
| Column | Type | Description |
|---|---|---|
| sale_date | DATE UNIQUE | Trading date |
| total_revenue | REAL | Sum of all revenue |
| total_orders | INTEGER | Number of transactions |
| total_units | INTEGER | Units sold |
| avg_order_value | REAL | Mean transaction value |
| top_category | TEXT | Highest revenue category |

**product_metrics** - Category aggregates (unique per date + category)
| Column | Type | Description |
|---|---|---|
| metric_date | DATE | Trading date |
| category | TEXT | Product category |
| total_revenue | REAL | Category revenue |
| total_units | INTEGER | Category units |
| avg_price | REAL | Mean unit price |

---

## Key Results (1-Year Backfill)

| Metric | Value |
|---|---|
| Days loaded | 365 |
| Total pipeline runs | 365 |
| Success rate | 100% |
| Avg pipeline duration | 0.2s |
| Technology revenue share | 58.6% |
| Furniture revenue share | 29.9% |
| Office Supplies share | 11.5% |
| Weekend revenue drop | ~60% vs weekday |
| Q4 seasonal uplift | ~30% above baseline |

---

## Pipeline Features

**Idempotency** - the pipeline uses upsert with conflict resolution on unique keys, so re-running for the same date safely overwrites without duplicating data.

**Weekday and seasonal modelling** - order counts follow a Poisson distribution with a weekday multiplier (weekends at 40% of weekday volume) and a seasonal multiplier (Q4 at 130% of baseline, spring at 110%).

**Run logging** - every pipeline execution records its status, row counts, and duration to the `pipeline_runs` table, enabling the dashboard to show pipeline health history.

**Backfill support** - the `backfill_days` parameter allows historical data loading without code changes.

---

## Project Structure

```
etl-pipeline-dashboard/
├── .github/
│   └── workflows/
│       └── main.yml              # GitHub Actions daily schedule
├── src/
│   ├── pipeline.py               # ETL pipeline (extract, transform, load, log)
│   ├── dashboard.py              # Streamlit dashboard
│   └── setup_supabase.py        # Connection test utility
├── requirements.txt
├── .gitignore                    # Excludes .env and venv
└── README.md
```

---

## How to Run Locally

```bash
git clone https://github.com/PrabinPokhrel/etl-pipeline-dashboard.git
cd etl-pipeline-dashboard

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env` in the project root:

```
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_service_role_key
```

Run the pipeline:

```bash
# Run for today only
python src/pipeline.py

# Backfill last 365 days
python -c "from src.pipeline import run_pipeline; run_pipeline(backfill_days=364)"
```

Run the dashboard:

```bash
streamlit run src/dashboard.py
```

---

## GitHub Actions Setup

The workflow in `.github/workflows/main.yml` runs daily at 06:00 UTC. To enable:

1. Go to **Settings > Secrets and variables > Actions**
2. Add `SUPABASE_URL` and `SUPABASE_KEY` as repository secrets
3. The workflow triggers automatically or can be run manually via **Actions > Run workflow**

---

## Streamlit Cloud Deployment

1. Connect repo at share.streamlit.io
2. Set main file to `src/dashboard.py`
3. Add secrets in TOML format under Advanced settings:

```toml
SUPABASE_URL = "your_supabase_project_url"
SUPABASE_KEY = "your_supabase_service_role_key"
```

---

## Tech Stack

- **Python:** pandas, numpy, python-dotenv, supabase-py
- **Database:** Supabase PostgreSQL (free tier)
- **Dashboard:** Streamlit, Plotly
- **Automation:** GitHub Actions (cron schedule)
- **Deployment:** Streamlit Cloud

---

## Author

**Prabin Pokhrel**
MSc Microdata Analysis (Business Intelligence, EQF Level 7), Dalarna University, Sweden
BSc Statistics, Tribhuvan University, Nepal

[GitHub: PrabinPokhrel](https://github.com/PrabinPokhrel) | [LinkedIn](https://linkedin.com/in/prabinpokhrel) | prabinpokhrel261@gmail.com
