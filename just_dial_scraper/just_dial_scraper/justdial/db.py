import os
import json
import mysql.connector
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

# Load configuration dynamically from config/config.json
def load_config():
    project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    config_path = os.path.join(project_root, "config", "config.json")
    if not os.path.exists(config_path):
        # Fallback to root-level config.json for backward compatibility
        config_path = os.path.join(project_root, "config.json")
    if not os.path.exists(config_path):
        return {
            "database": {
                "host": "localhost",
                "port": 3306,
                "user": "root",
                "password": "meet@001",
                "database_name": "leads"
            }
        }
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config.json in db.py: {e}")
        return {}

def _get_db_config():
    config = load_config()
    db_config = config.get("database", {})
    return {
        "host": db_config.get("host", "localhost"),
        "port": db_config.get("port", 3306),
        "user": db_config.get("user", "root"),
        "password": db_config.get("password", "meet@001"),
        "database_name": db_config.get("database_name", "leads")
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

# Initialize MySQL database for leads scraping
def init_databases():
    table_name = get_table_name()
    cfg = _get_db_config()
    
    try:
        conn = mysql.connector.connect(
            host=cfg["host"], port=cfg["port"],
            user=cfg["user"], password=cfg["password"]
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {cfg['database_name']}")
        conn.commit()
        cursor.close()
        conn.close()
        
        mysql_conn = mysql.connector.connect(
            host=cfg["host"], port=cfg["port"],
            user=cfg["user"], password=cfg["password"],
            database=cfg["database_name"]
        )
        cursor = mysql_conn.cursor()
        
        sorted_cols = sorted(columns_index.items(), key=lambda x: x[1])
        cols_sql = []
        for col_name, idx in sorted_cols:
            if col_name == 'docid':
                cols_sql.append("docid VARCHAR(100) PRIMARY KEY")
            else:
                cols_sql.append(f"`{col_name}` TEXT")
        
        cols_sql.append("`scraped_city` VARCHAR(100)")
        cols_sql.append("`scraped_service` VARCHAR(100)")
        cols_sql.append("`status` VARCHAR(50) DEFAULT 'pending'")
        cols_sql.append("`created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
        
        create_table_query = f"CREATE TABLE IF NOT EXISTS {table_name} (\n" + ",\n".join(cols_sql) + "\n)"
        cursor.execute(create_table_query)
        mysql_conn.commit()
        
        # Ensure status column exists (for backward compatibility with tables already created)
        try:
            cursor.execute(f"ALTER TABLE `{table_name}` ADD COLUMN `status` VARCHAR(50) DEFAULT 'pending'")
            mysql_conn.commit()
        except Exception:
            pass # Column already exists
            
        cursor.close()
        print(f"[OK] MySQL database '{cfg['database_name']}' and table '{table_name}' initialized successfully.")
        return mysql_conn
    except Exception as e:
        print(f"[FATAL] MySQL connection failed: {e}")
        return None

# Initialize MySQL database for PDP crawling
def init_pdp_database():
    table_name = get_pdp_table_name()
    cfg = _get_db_config()
    
    try:
        conn = mysql.connector.connect(
            host=cfg["host"], port=cfg["port"],
            user=cfg["user"], password=cfg["password"]
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {cfg['database_name']}")
        conn.commit()
        cursor.close()
        conn.close()
        
        mysql_conn = mysql.connector.connect(
            host=cfg["host"], port=cfg["port"],
            user=cfg["user"], password=cfg["password"],
            database=cfg["database_name"]
        )
        cursor = mysql_conn.cursor()
        
        create_query = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INT AUTO_INCREMENT PRIMARY KEY,
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """
        cursor.execute(create_query)
        mysql_conn.commit()
        cursor.close()
        print(f"[OK] MySQL database '{cfg['database_name']}' and PDP table '{table_name}' initialized successfully.")
        return mysql_conn
    except Exception as e:
        print(f"[FATAL] MySQL connection failed for PDP: {e}")
        return None

# Save a single lead row to MySQL
def save_lead_to_db(mysql_conn, row, columns_map, city, service, commit=False):
    if not mysql_conn:
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
        cursor = mysql_conn.cursor()
        fields = list(record.keys())
        placeholders = [f"%s" for _ in fields]
        update_parts = [f"`{f}` = VALUES(`{f}`)" for f in fields if f != "docid"]
        
        sql = f"INSERT INTO {table_name} ({', '.join([f'`{f}`' for f in fields])}) VALUES ({', '.join(placeholders)}) ON DUPLICATE KEY UPDATE {', '.join(update_parts)}"
        values = tuple(record[f] for f in fields)
        cursor.execute(sql, values)
        if commit:
            mysql_conn.commit()
        cursor.close()
    except Exception as e:
        print(f"Error inserting row into MySQL: {e}")

# Save parsed PDP details to MySQL
def save_pdp_to_db(mysql_conn, record, commit=False):
    if not mysql_conn:
        return
    
    table_name = get_pdp_table_name()
    
    try:
        cursor = mysql_conn.cursor()
        fields = list(record.keys())
        placeholders = [f"%s" for _ in fields]
        
        sql = f"INSERT INTO {table_name} ({', '.join([f'`{f}`' for f in fields])}) VALUES ({', '.join(placeholders)})"
        values = tuple(record[f] for f in fields)
        cursor.execute(sql, values)
        if commit:
            mysql_conn.commit()
        cursor.close()
    except Exception as e:
        print(f"Error inserting PDP row into MySQL: {e}")

# Load all docids ever scraped across all daily leads tables to prevent duplicate scraping across different days
def load_all_scraped_docids(mysql_conn):
    existing_docids = set()
    if not mysql_conn:
        return existing_docids
    try:
        cursor = mysql_conn.cursor()
        cursor.execute("SHOW TABLES")
        tables = [r[0] for r in cursor.fetchall()]
        leads_tables = [t for t in tables if t.startswith("justdial_leads_")]
        
        for table in leads_tables:
            cursor.execute(f"SELECT `docid` FROM `{table}`")
            # Fetch all docids and add them to the set
            for row in cursor.fetchall():
                if row[0]:
                    existing_docids.add(str(row[0]))
        cursor.close()
        print(f"[OK] Loaded {len(existing_docids)} unique existing docids from database to prevent duplicates.")
    except Exception as e:
        print(f"Error loading existing docids: {e}")
    return existing_docids

