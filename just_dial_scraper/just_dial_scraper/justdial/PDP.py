import os
import sys
import json
import time
import threading
import mysql.connector
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from lxml import html
from curl_cffi import requests

# Ensure sibling imports work correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from db import init_pdp_database, save_pdp_to_db, load_config, get_table_name

# Thread-safe lock for MySQL writes (mysql.connector is NOT thread-safe)
db_lock = threading.Lock()

def make_re(url, cookie_dict=None):
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'priority': 'u=0, i',
        'sec-ch-ua': '"Not=A?Brand";v="99", "Google Chrome";v="151", "Chromium";v="151"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36',
    }

    try:
        response = requests.get(
            f'https://www.justdial.com/{url}',
            headers=headers,
            cookies=cookie_dict,
            impersonate="chrome",
            timeout=15
        )
        if response.status_code == 200:
            return response.text
        else:
            print(f"Non-200 HTTP response code: {response.status_code}")
    except Exception as e:
        print(f"Error fetching URL '{url}': {e}")
    return ""

def load_cached_data():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "intercepted_api.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading cache file in PDP.py: {e}")
    return None

def parse_pdp_page(html_content, name):
    """Parse a single PDP page HTML and return the record dict, or None on failure."""
    try:
        tree = html.fromstring(html_content)
        script = tree.xpath("//script[@id='__NEXT_DATA__']//text()")
        json_data = None
        if script:
            for s in script:
                json_data = json.loads(s)
                break
                
        if not json_data:
            return None, f"Could not parse __NEXT_DATA__ script tag for '{name}'."
            
        props = json_data.get('props', {})
        main_path = props.get('pageProps', {}).get('results', {}).get('results', {})
        if not main_path:
            for k, v in props.items():
                if isinstance(v, dict) and 'results' in v:
                    main_path = v['results'].get('results', {})
                    if main_path:
                        break
        
        if not main_path:
            return None, f"Result details path is empty for '{name}'."
            
        bussiness_name = main_path.get('name') or name or ""
        email_raw = main_path.get('email') or ""
        # Clean and separate emails with a semicolon and space
        normalized_email = email_raw.replace(';', ',').replace('|', ',')
        bussiness_email = "; ".join([e.strip() for e in normalized_email.split(',') if e.strip()])
        
        # Extract business number / mobile number from various possible fields
        numbers_list = []
        
        # 1. Try VNumber
        vnum = main_path.get('VNumber') or ""
        # 2. Try mobile
        mobile = main_path.get('mobile') or ""
        # 3. Try contact
        contact = main_path.get('contact') or ""
        
        # 4. Try msg_num (which is a JSON string of WhatsApp/message numbers)
        msg_num = main_path.get('msg_num') or ""
        wup_num = ""
        if msg_num and isinstance(msg_num, str):
            try:
                msg_data = json.loads(msg_num)
                if isinstance(msg_data, dict) and 'wup' in msg_data:
                    wups = msg_data['wup']
                    if isinstance(wups, list) and wups:
                        wup_num = "; ".join([str(x).strip() for x in wups if str(x).strip()])
            except Exception:
                pass
                
        # 5. Try other_city_num
        other_num = ""
        other_city = main_path.get('other_city_num')
        if other_city and isinstance(other_city, list):
            other_num = "; ".join([str(x).strip() for x in other_city if str(x).strip()])
            
        # 6. Try wpnumber (exclude obfuscated 'xxxxxxx')
        wp_num = main_path.get('wpnumber')
        wp_num_str = ""
        if wp_num:
            if isinstance(wp_num, list):
                wp_num_str = "; ".join([str(x).strip() for x in wp_num if isinstance(x, str) and 'x' not in x.lower()])
            elif isinstance(wp_num, str) and 'x' not in wp_num.lower():
                wp_num_str = wp_num.strip()

        for num in [mobile, contact, vnum, wup_num, other_num, wp_num_str]:
            if num:
                parts = str(num).replace(',', ';').split(';')
                for part in parts:
                    part_clean = part.strip()
                    digit_only = ''.join(c for c in part_clean if c.isdigit())
                    if len(digit_only) >= 5 and part_clean not in numbers_list:
                        numbers_list.append(part_clean)
                    
        bussiness_number = "; ".join(numbers_list)
        bussiness_area = main_path.get('area') or ""
        rating = main_path.get('rating') or ""
        landmark = main_path.get('landmark') or ""
        total_review = main_path.get('totalReviews') or ""
        building = main_path.get('building') or ""
        pincode = main_path.get('pincode') or ""
        bussiness_website = main_path.get('website') or ""
        pop_cat = main_path.get('pop_cat')
        category = " | ".join([c.get('category') for c in pop_cat if c.get('category')]) if pop_cat else ""
        bussiness_address = main_path.get('addressln') or ""
        services_raw = main_path.get('services')
        if isinstance(services_raw, list):
            service = " | ".join([str(s) for s in services_raw if s])
        elif isinstance(services_raw, dict):
            service = " | ".join([str(k) for k, v in services_raw.items() if k])
        else:
            service = str(services_raw) if services_raw else ""
        
        record = {
            "bussiness_name": bussiness_name,
            "bussiness_email": bussiness_email,
            "bussiness_number": bussiness_number,
            "bussiness_area": bussiness_area,
            "rating": rating,
            "landmark": landmark,
            "total_review": total_review,
            "building": building,
            "pincode": pincode,
            "bussiness_website": bussiness_website,
            "category": category,
            "bussiness_address": bussiness_address,
            "service": service,
        }
        return record, None
    except Exception as e:
        return None, f"Parse error for '{name}': {e}"

def crawl_single_lead(lead, cookie_dict):
    """Fetch and parse a single lead's PDP. Returns (record, lead) or (None, lead)."""
    name = lead.get("name", "Unknown")
    
    # Check if we already have a valid phone number from the listing search page
    vnum = (lead.get("VNumber") or "").strip()
    wp_num = lead.get("wpnumber") or ""
    wp_num_str = ""
    if wp_num:
        try:
            if isinstance(wp_num, str) and wp_num.startswith("["):
                wp_data = json.loads(wp_num)
                if isinstance(wp_data, list):
                    wp_num_str = "; ".join([str(x).strip() for x in wp_data if 'x' not in str(x).lower()])
            elif isinstance(wp_num, list):
                wp_num_str = "; ".join([str(x).strip() for x in wp_num if 'x' not in str(x).lower()])
            elif 'x' not in str(wp_num).lower():
                wp_num_str = str(wp_num).strip()
        except Exception:
            pass
            
    # Clean and check number validity
    numbers = []
    for num in [vnum, wp_num_str]:
        if num:
            parts = str(num).replace(',', ';').split(';')
            for part in parts:
                part_clean = part.strip()
                digit_only = ''.join(c for c in part_clean if c.isdigit())
                if len(digit_only) >= 5 and part_clean not in numbers:
                    numbers.append(part_clean)
                    
    phone_number = "; ".join(numbers)
    
    # Do NOT bypass detailed requests because we need to fetch the email and website details from the PDP pages
    # which are not available in the initial listings search page.

    weburl = lead.get("weburl")
    if not weburl:
        return None, lead, f"No detail URL for '{name}'."
    
    url_path = weburl.lstrip('/')
    html_content = make_re(url_path, cookie_dict)
    
    if not html_content:
        return None, lead, f"Failed to fetch content for '{name}'."
    
    record, err = parse_pdp_page(html_content, name)
    if record:
        record["scraped_city"] = lead.get("scraped_city", "")
        record["scraped_service"] = lead.get("scraped_service", "")
        return record, lead, None
    else:
        return None, lead, err

def update_lead_status(mysql_conn, table_name, docid, status):
    if not mysql_conn or not docid:
        return
    try:
        cursor = mysql_conn.cursor()
        sql = f"UPDATE `{table_name}` SET `status` = %s WHERE `docid` = %s"
        cursor.execute(sql, (status, docid))
        mysql_conn.commit()
        cursor.close()
    except Exception as e:
        print(f"Error updating lead status in MySQL: {e}")

def crawl_pdp():
    print("\n========================================================")
    print("[*] STARTING DETAILED PDP CRAWLER (THREADED)")
    print("========================================================")
    
    # 1. Initialize PDP database (MySQL only)
    mysql_pdp = init_pdp_database()
    
    # 2. Get today's leads table name
    leads_table = get_table_name()
    print(f"Loading leads from today's table: '{leads_table}'...")
    
    # 3. Retrieve database config to query leads
    config = load_config()
    db_config = config.get("database", {})
    host = db_config.get("host", "localhost")
    port = db_config.get("port", 3306)
    user = db_config.get("user", "root")
    password = db_config.get("password", "meet@001")
    database_name = db_config.get("database_name", "leads")
    
    # Configurable thread pool size
    max_workers = int(os.environ.get("PDP_WORKERS", 5))
    
    # Load cookies from cache
    session_data = load_cached_data()
    cookie_dict = {}
    if session_data:
        cookies = session_data.get("cookies", [])
        if isinstance(cookies, list):
            cookie_dict = {c['name']: c['value'] for c in cookies}
        else:
            cookie_dict = cookies
        print("Loaded active session cookies successfully.")
    
    leads = []
    
    # Load leads from MySQL
    mysql_conn = None
    try:
        mysql_conn = mysql.connector.connect(
            host=host, port=port, user=user,
            password=password, database=database_name
        )
        cursor = mysql_conn.cursor(dictionary=True)
        cursor.execute(f"SELECT docid, name, weburl, scraped_city, scraped_service, VNumber, wpnumber, compRating, NewAddress, area, pincode FROM {leads_table} WHERE status = 'pending' OR status IS NULL")
        leads = cursor.fetchall()
        cursor.close()
        mysql_conn.close()
        print(f"Successfully loaded {len(leads)} pending/un-crawled leads from MySQL.")
    except Exception as e:
        print(f"MySQL leads load failed: {e}")
                
    if not leads:
        print("No leads found in today's table to crawl detailed pages.")
        return

    # 4. Crawl leads in parallel using ThreadPoolExecutor
    crawled_count = 0
    failed_count = 0
    total = len(leads)
    
    print(f"\n---> Starting parallel PDP crawl with {max_workers} workers for {total} leads...\n")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(crawl_single_lead, lead, cookie_dict): idx 
            for idx, lead in enumerate(leads)
        }
        
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            lead = leads[idx]
            name = lead.get("name", "Unknown")
            docid = lead.get("docid")
            
            try:
                record, lead_data, err = future.result()
                
                if record:
                    # Thread-safe DB write
                    with db_lock:
                        save_pdp_to_db(mysql_pdp, record, commit=True)
                        update_lead_status(mysql_pdp, leads_table, docid, "done")
                    crawled_count += 1
                    # Real-time stdout streaming of lead data
                    email = (record.get("bussiness_email") or "").strip().lower()
                    if email and "@" in email:
                        print(f"[DATA] {json.dumps(record)}", flush=True)
                    print(f"[{crawled_count + failed_count}/{total}] [OK] Saved '{record['bussiness_name']}' (Email: '{record['bussiness_email']}', Web: '{record['bussiness_website']}')", flush=True)
                else:
                    with db_lock:
                        update_lead_status(mysql_pdp, leads_table, docid, "failed")
                    failed_count += 1
                    print(f"[{crawled_count + failed_count}/{total}] [FAIL] {err}")
                    
            except Exception as exc:
                with db_lock:
                    update_lead_status(mysql_pdp, leads_table, docid, "failed")
                failed_count += 1
                print(f"[{crawled_count + failed_count}/{total}] [FAIL] Exception for '{name}': {exc}")
        
    print(f"\n========================================================")
    print(f"[Finished] PDP Crawl completed: {crawled_count} saved, {failed_count} failed out of {total} leads.")
    print(f"========================================================")
    
    # Close PDP database connection
    if mysql_pdp:
        mysql_pdp.close()

if __name__ == "__main__":
    crawl_pdp()