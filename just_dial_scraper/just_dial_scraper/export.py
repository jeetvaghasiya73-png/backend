import os
import sys
import pandas as pd
import mysql.connector

# Ensure sibling imports work correctly
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "justdial"))
from db import load_config, get_pdp_table_name


def export_pdp(date_str=None, output_format="excel"):
    """
    Export the PDP table for a given date (defaults to today).
    Removes duplicate rows and saves as Excel (.xlsx) or CSV.
    """
    # 1. Resolve table name
    table_name = get_pdp_table_name(date_str)
    print(f"[*] Exporting PDP table: '{table_name}'")

    # 2. Connect to MySQL
    config = load_config()
    db_cfg = config.get("database", {})

    try:
        conn = mysql.connector.connect(
            host=db_cfg.get("host", "localhost"),
            port=db_cfg.get("port", 3306),
            user=db_cfg.get("user", "root"),
            password=db_cfg.get("password", "meet@001"),
            database=db_cfg.get("database_name", "leads"),
        )
    except Exception as e:
        print(f"[FATAL] MySQL connection failed: {e}")
        return

    # 3. Read the entire PDP table into a DataFrame
    try:
        query = f"SELECT * FROM `{table_name}`"
        df = pd.read_sql(query, conn)
        print(f"[OK] Loaded {len(df)} rows from MySQL.")
    except Exception as e:
        print(f"[ERROR] Failed to read table '{table_name}': {e}")
        conn.close()
        return

    conn.close()

    if df.empty:
        print("[!] Table is empty. Nothing to export.")
        return

    # 4. Drop the auto-increment 'id' and 'created_at' columns (not useful in export)
    drop_cols = [c for c in ("id", "created_at") if c in df.columns]
    if drop_cols:
        df.drop(columns=drop_cols, inplace=True)

    # 5. Remove rows without email
    if "bussiness_email" in df.columns:
        rows_before_email = len(df)
        df = df[df["bussiness_email"].astype(str).str.strip().replace("", pd.NA).notna()]
        removed_no_email = rows_before_email - len(df)
        print(f"[OK] Removed {removed_no_email} rows without email. ({rows_before_email} -> {len(df)})")

        # Clean and format emails with a semicolon and space
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
        # Filter out rows that became empty after cleaning
        df = df[df["bussiness_email"].astype(str).str.strip() != ""]

    # 6. Remove duplicate rows
    rows_before = len(df)
    # Deduplicate on business-critical columns (name + number + email + area)
    dedup_cols = ["bussiness_name", "bussiness_number", "bussiness_email", "bussiness_area"]
    # Only use columns that actually exist in the DataFrame
    dedup_cols = [c for c in dedup_cols if c in df.columns]
    df.drop_duplicates(subset=dedup_cols, keep="first", inplace=True)
    rows_after = len(df)
    removed = rows_before - rows_after
    print(f"[OK] Removed {removed} duplicate rows. ({rows_before} -> {rows_after})")

    # 7. Clean up: strip whitespace from string columns
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.strip()

    # 8. Build output file path
    output_dir = os.path.dirname(os.path.abspath(__file__))
    if output_format == "csv":
        filename = f"{table_name}.csv"
    else:
        filename = f"{table_name}.xlsx"
    filepath = os.path.join(output_dir, filename)

    try:
        if output_format == "csv":
            df.to_csv(filepath, index=False, encoding="utf-8-sig")
        else:
            df.to_excel(filepath, index=False, sheet_name="PDP Data", engine="openpyxl")
        print(f"[OK] Exported {len(df)} rows -> {filepath}")
    except PermissionError:
        print(f"[ERROR] Permission denied: The file '{filepath}' is open in Excel or another program. Please close it.")
        fallback_filename = f"{table_name}_fixed.xlsx" if output_format == "excel" else f"{table_name}_fixed.csv"
        fallback_filepath = os.path.join(output_dir, fallback_filename)
        try:
            if output_format == "csv":
                df.to_csv(fallback_filepath, index=False, encoding="utf-8-sig")
            else:
                df.to_excel(fallback_filepath, index=False, sheet_name="PDP Data", engine="openpyxl")
            print(f"[WARNING] Saved copy to fallback location: {fallback_filepath}")
        except Exception as e2:
            print(f"[ERROR] Failed to save fallback copy: {e2}")
    except Exception as e:
        print(f"[ERROR] Failed to export file: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Export JustDial PDP data from MySQL to Excel/CSV.")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Date string for the table name (YYYY_MM_DD). Defaults to today.",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["excel", "csv"],
        default="excel",
        help="Output format: 'excel' (default) or 'csv'.",
    )
    args = parser.parse_args()

    export_pdp(date_str=args.date, output_format=args.format)
