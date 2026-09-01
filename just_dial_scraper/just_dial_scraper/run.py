import os
import sys
import argparse
from datetime import datetime

# Adjust path to find justdial package
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "justdial"))
from justdial.db import init_databases, get_table_name, get_connection, get_pdp_table_name
from justdial.scraper import run_scraper
from justdial.PDP import crawl_pdp

def test_db_connection():
    import psycopg2
    print("Testing connection to PostgreSQL...")
    try:
        conn = get_connection()
        print("[SUCCESS] PostgreSQL connection succeeded.")
        
        cursor = conn.cursor()
        cursor.execute("SELECT current_database();")
        db = cursor.fetchone()[0]
        print(f"Connected to Database: {db}")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[FAILED] PostgreSQL connection failed: {e}")

def export_db_to_excel(date_str=None):
    try:
        import pandas as pd
        import openpyxl
    except ImportError:
        print("Required dependencies 'pandas' and 'openpyxl' are missing.")
        print("Please install them using: pip install pandas openpyxl")
        return

    import psycopg2
    
    table_name = get_table_name(date_str)
    print(f"Attempting to export table '{table_name}' to Excel...")

    df = None
    
    try:
        pg_conn = get_connection()
        query = f'SELECT * FROM "{table_name}"'
        df = pd.read_sql(query, pg_conn)
        print(f"Successfully loaded {len(df)} rows from PostgreSQL table '{table_name}'.")
        pg_conn.close()
    except Exception as e:
        print(f"PostgreSQL export failed: {e}")
        df = None

    if df is not None and len(df) > 0:
        output_filename = f"{table_name}.xlsx"
        try:
            df.to_excel(output_filename, index=False)
            print(f"[OK] Excel export completed! File saved to: {os.path.abspath(output_filename)}")
        except Exception as e:
            print(f"Error writing Excel file: {e}")
    else:
        print("No data found to export.")

def export_pdp_to_excel(date_str=None):
    try:
        import pandas as pd
        import openpyxl
    except ImportError:
        print("Required dependencies 'pandas' and 'openpyxl' are missing.")
        print("Please install them using: pip install pandas openpyxl")
        return

    import psycopg2
    
    table_name = get_pdp_table_name(date_str)
    print(f"Attempting to export PDP table '{table_name}' to Excel...")

    df = None
    
    try:
        pg_conn = get_connection()
        query = f'SELECT * FROM "{table_name}"'
        df = pd.read_sql(query, pg_conn)
        print(f"Successfully loaded {len(df)} rows from PostgreSQL table '{table_name}'.")
        pg_conn.close()
    except Exception as e:
        print(f"PostgreSQL export failed: {e}")
        df = None

    if df is not None and len(df) > 0:
        # Clean and format emails with a semicolon and space
        if "bussiness_email" in df.columns:
            def clean_and_format_emails(val):
                if pd.isna(val):
                    return ""
                normalized = str(val).replace(';', ',').replace('|', ',')
                emails = []
                for e in normalized.split(','):
                    e_clean = e.strip()
                    if e_clean and e_clean not in emails:
                        emails.append(e_clean)
                return "; ".join(emails)
            df["bussiness_email"] = df["bussiness_email"].apply(clean_and_format_emails)

        output_filename = f"{table_name}.xlsx"
        try:
            df.to_excel(output_filename, index=False)
            print(f"[OK] Excel export completed! File saved to: {os.path.abspath(output_filename)}")
        except Exception as e:
            print(f"Error writing Excel file: {e}")
    else:
        print("No data found to export.")

def main():
    parser = argparse.ArgumentParser(description="Justdial Scraper & PDP Crawler Production CLI Interface")
    parser.add_argument("--scrape", action="store_true", help="Execute the primary listings search scraper")
    parser.add_argument("--crawl-pdp", action="store_true", help="Crawl detailed Product Detail Pages (PDP) for today's scraped leads")
    parser.add_argument("--export", type=str, nargs="?", const="today", help="Export primary listings table to Excel. Optional date argument (format: YYYY_MM_DD)")
    parser.add_argument("--export-pdp", type=str, nargs="?", const="today", help="Export detailed PDP table to Excel. Optional date argument (format: YYYY_MM_DD)")
    parser.add_argument("--test-db", action="store_true", help="Run database connection diagnostics")
    
    args = parser.parse_args()
    
    # Default behavior is to scrape if no specific flags are set
    if not (args.export or args.export_pdp or args.test_db or args.crawl_pdp):
        args.scrape = True
        
    if args.test_db:
        test_db_connection()
        
    elif args.export:
        date_param = None if args.export == "today" else args.export
        export_db_to_excel(date_param)
        
    elif args.export_pdp:
        date_param = None if args.export_pdp == "today" else args.export_pdp
        export_pdp_to_excel(date_param)
        
    elif args.crawl_pdp:
        crawl_pdp()
        
    elif args.scrape:
        print("Initializing database schemas...")
        pg_conn = init_databases()
        
        print("Starting Justdial parallel scraper...")
        try:
            run_scraper(pg_conn)
        finally:
            if pg_conn:
                pg_conn.close()

if __name__ == "__main__":
    main()
