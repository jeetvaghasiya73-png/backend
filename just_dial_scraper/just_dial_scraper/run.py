import os
import sys
import argparse
from datetime import datetime

# Adjust path to find justdial package
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "justdial"))
from justdial.db import init_databases, get_table_name, load_config, get_pdp_table_name
from justdial.scraper import run_scraper
from justdial.PDP import crawl_pdp

def test_db_connection():
    import mysql.connector
    config = load_config()
    db_config = config.get("database", {})
    host = db_config.get("host", "localhost")
    port = db_config.get("port", 3306)
    user = db_config.get("user", "root")
    password = db_config.get("password", "meet@001")
    database_name = db_config.get("database_name", "leads")
    
    print(f"Testing connection to MySQL server at {host}:{port}...")
    try:
        conn = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password
        )
        print(f"[SUCCESS] MySQL connection succeeded using user: '{user}'.")
        
        cursor = conn.cursor()
        cursor.execute("SHOW DATABASES")
        dbs = [r[0] for r in cursor.fetchall()]
        print(f"Available Databases: {dbs}")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[FAILED] MySQL connection failed: {e}")

def export_db_to_excel(date_str=None):
    try:
        import pandas as pd
        import openpyxl
    except ImportError:
        print("Required dependencies 'pandas' and 'openpyxl' are missing.")
        print("Please install them using: pip install pandas openpyxl")
        return

    import mysql.connector
    config = load_config()
    db_config = config.get("database", {})
    host = db_config.get("host", "localhost")
    port = db_config.get("port", 3306)
    user = db_config.get("user", "root")
    password = db_config.get("password", "meet@001")
    database_name = db_config.get("database_name", "leads")
    
    table_name = get_table_name(date_str)
    print(f"Attempting to export table '{table_name}' to Excel...")

    df = None
    
    try:
        mysql_conn = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database_name
        )
        query = f"SELECT * FROM {table_name}"
        df = pd.read_sql(query, mysql_conn)
        print(f"Successfully loaded {len(df)} rows from MySQL table '{table_name}'.")
        mysql_conn.close()
    except Exception as e:
        print(f"MySQL export failed: {e}")
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

    import mysql.connector
    config = load_config()
    db_config = config.get("database", {})
    host = db_config.get("host", "localhost")
    port = db_config.get("port", 3306)
    user = db_config.get("user", "root")
    password = db_config.get("password", "meet@001")
    database_name = db_config.get("database_name", "leads")
    
    table_name = get_pdp_table_name(date_str)
    print(f"Attempting to export PDP table '{table_name}' to Excel...")

    df = None
    
    try:
        mysql_conn = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database_name
        )
        query = f"SELECT * FROM {table_name}"
        df = pd.read_sql(query, mysql_conn)
        print(f"Successfully loaded {len(df)} rows from MySQL table '{table_name}'.")
        mysql_conn.close()
    except Exception as e:
        print(f"MySQL export failed: {e}")
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
        mysql_conn = init_databases()
        
        print("Starting Justdial parallel scraper...")
        try:
            run_scraper(mysql_conn)
        finally:
            if mysql_conn:
                mysql_conn.close()

if __name__ == "__main__":
    main()
