import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Columns index mapping provided by the user representing Justdial's API row format
columns_index = {
    "docid": 0,
    "name": 1,
    "distance": 2,
    "NewAddress": 3,
    "lat": 4,
    "lon": 5,
    "compRating": 7,
    "verified": 8,
    "area": 12,
    "type": 14,
    "VNumber": 15,
    "totalReviews": 16,
    "city": 18,
    "vertical": 26,
    "vertical_name": 27,
    "wpnumber": 34,
    "weburl": 59,
    "resp_rate": 67,
    "pincode": 68,
    "loccity": 73,
    "service_catalog": 77,
    "price_tagline": 79,
    "logo": 82,
}

# Resolve date-based table name: justdial_leads_YYYY_MM_DD
def get_table_name(date_str=None):
    if not date_str:
        date_str = datetime.now().strftime('%Y_%m_%d')
    return f"justdial_leads_{date_str}"

# Resolve date-based PDP table name: justdial_pdp_YYYY_MM_DD
def get_pdp_table_name(date_str=None):
    if not date_str:
        date_str = datetime.now().strftime('%Y_%m_%d')
    return f"justdial_pdp_{date_str}"

def get_connection():
    """Get a psycopg2 connection using DATABASE_URL or fallback config."""
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        # If the URL is SQLAlchemy style (postgresql://), convert to postgres:// for psycopg2 just in case
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgres://", 1)
        return psycopg2.connect(db_url)
    
    # Fallback to local config if no DATABASE_URL
    project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    config_path = os.path.join(project_root, "config", "config.json")
    if not os.path.exists(config_path):
        config_path = os.path.join(project_root, "config.json")
    
    cfg = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f).get("database", {})
        except Exception as e:
            print(f"Error loading config.json in db.py: {e}")

    host = cfg.get("host", "localhost")
    port = cfg.get("port", 5432)
    user = cfg.get("user", "postgres")
    password = cfg.get("password", "")
    database_name = cfg.get("database_name", "leads")
    
    return psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=database_name
    )

# Initialize PostgreSQL database for leads scraping
def init_databases():
    table_name = get_table_name()
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        sorted_cols = sorted(columns_index.items(), key=lambda x: x[1])
        cols_sql = []
        for col_name, idx in sorted_cols:
            if col_name == 'docid':
                cols_sql.append('"docid" VARCHAR(100) PRIMARY KEY')
            else:
                cols_sql.append(f'"{col_name}" TEXT')
        
        cols_sql.append('"scraped_city" VARCHAR(100)')
        cols_sql.append('"scraped_service" VARCHAR(100)')
        cols_sql.append('"status" VARCHAR(50) DEFAULT \'pending\'')
        cols_sql.append('"created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        
        create_table_query = f"CREATE TABLE IF NOT EXISTS {table_name} (\n" + ",\n".join(cols_sql) + "\n)"
        cursor.execute(create_table_query)
        conn.commit()
        
        # Ensure status column exists (for backward compatibility)
        try:
            cursor.execute(f'ALTER TABLE {table_name} ADD COLUMN "status" VARCHAR(50) DEFAULT \'pending\'')
            conn.commit()
        except psycopg2.errors.DuplicateColumn:
            conn.rollback() # Column already exists
            
        cursor.close()
        print(f"[OK] PostgreSQL table '{table_name}' initialized successfully.")
        return conn
    except Exception as e:
        print(f"[FATAL] PostgreSQL connection failed: {e}")
        return None

# Initialize PostgreSQL database for PDP crawling
def init_pdp_database():
    table_name = get_pdp_table_name()
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        create_query = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id SERIAL PRIMARY KEY,
            bussiness_name TEXT,
            bussiness_email TEXT,
            bussiness_number TEXT,
            bussiness_area TEXT,
            rating TEXT,
            landmark TEXT,
            total_review TEXT,
            building TEXT,
            pincode TEXT,
            bussiness_website TEXT,
            category TEXT,
            bussiness_address TEXT,
            service TEXT,
            scraped_city VARCHAR(100),
            scraped_service VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        cursor.execute(create_query)
        conn.commit()
        cursor.close()
        print(f"[OK] PostgreSQL PDP table '{table_name}' initialized successfully.")
        return conn
    except Exception as e:
        print(f"[FATAL] PostgreSQL connection failed for PDP: {e}")
        return None

# Save a single lead row to PostgreSQL
def save_lead_to_db(pg_conn, row, columns_map, city, service, commit=False):
    if not pg_conn:
        return
    
    sorted_cols = sorted(columns_index.items(), key=lambda x: x[1])
    record = {}
    table_name = get_table_name()
    
    for col_name, default_idx in sorted_cols:
        idx = columns_map.get(col_name, default_idx)
        val = ""
        if idx < len(row):
            raw_val = row[idx]
            if isinstance(raw_val, (dict, list)):
                val = json.dumps(raw_val)
            else:
                val = str(raw_val) if raw_val is not None else ""
        record[col_name] = val
        
    record["scraped_city"] = city
    record["scraped_service"] = service
    
    docid = record.get("docid")
    if not docid:
        return
        
    try:
        cursor = pg_conn.cursor()
        fields = list(record.keys())
        placeholders = [f"%s" for _ in fields]
        
        # Build ON CONFLICT DO UPDATE SET
        update_parts = [f'"{f}" = EXCLUDED."{f}"' for f in fields if f != "docid"]
        
        sql = f'INSERT INTO {table_name} ({", ".join([f"{chr(34)}{f}{chr(34)}" for f in fields])}) VALUES ({", ".join(placeholders)}) ON CONFLICT ("docid") DO UPDATE SET {", ".join(update_parts)}'
        values = tuple(record[f] for f in fields)
        cursor.execute(sql, values)
        if commit:
            pg_conn.commit()
        cursor.close()
    except Exception as e:
        pg_conn.rollback()
        print(f"Error inserting row into PostgreSQL: {e}")

# Save parsed PDP details to PostgreSQL
def save_pdp_to_db(pg_conn, record, commit=False):
    if not pg_conn:
        return
    
    table_name = get_pdp_table_name()
    
    try:
        cursor = pg_conn.cursor()
        fields = list(record.keys())
        placeholders = [f"%s" for _ in fields]
        
        sql = f'INSERT INTO {table_name} ({", ".join([f"{chr(34)}{f}{chr(34)}" for f in fields])}) VALUES ({", ".join(placeholders)})'
        values = tuple(record[f] for f in fields)
        cursor.execute(sql, values)
        if commit:
            pg_conn.commit()
        cursor.close()
    except Exception as e:
        pg_conn.rollback()
        print(f"Error inserting PDP row into PostgreSQL: {e}")

# Load all docids ever scraped across all daily leads tables to prevent duplicate scraping across different days
def load_all_scraped_docids(pg_conn):
    existing_docids = set()
    if not pg_conn:
        return existing_docids
    try:
        cursor = pg_conn.cursor()
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        tables = [r[0] for r in cursor.fetchall()]
        leads_tables = [t for t in tables if t.startswith("justdial_leads_")]
        
        for table in leads_tables:
            cursor.execute(f'SELECT "docid" FROM {table}')
            for row in cursor.fetchall():
                if row[0]:
                    existing_docids.add(str(row[0]))
        cursor.close()
        print(f"[OK] Loaded {len(existing_docids)} unique existing docids from database to prevent duplicates.")
    except Exception as e:
        pg_conn.rollback()
        print(f"Error loading existing docids: {e}")
    return existing_docids
