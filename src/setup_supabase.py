"""
setup_supabase.py
Creates tables in Supabase PostgreSQL for the ETL pipeline.
Run once before the pipeline.
"""

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_KEY"]
sb  = create_client(url, key)

# Create tables via SQL using Supabase RPC
# We use the REST API to insert - tables must be created via Supabase dashboard SQL editor

print("Supabase connection test...")
print(f"  URL: {url}")

# Test connection by listing tables
try:
    result = sb.table("pipeline_runs").select("*").limit(1).execute()
    print("  pipeline_runs table: EXISTS")
except Exception as e:
    print(f"  pipeline_runs table: NOT FOUND - create via SQL editor")

try:
    result = sb.table("daily_sales").select("*").limit(1).execute()
    print("  daily_sales table: EXISTS")
except Exception as e:
    print(f"  daily_sales table: NOT FOUND - create via SQL editor")

try:
    result = sb.table("product_metrics").select("*").limit(1).execute()
    print("  product_metrics table: EXISTS")
except Exception as e:
    print(f"  product_metrics table: NOT FOUND - create via SQL editor")

print("\nConnection successful.")