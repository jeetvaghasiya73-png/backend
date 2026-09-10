import os
import sys
import json
import time
import urllib.parse
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from curl_cffi import requests

# Ensure sibling imports work correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from parser import get_cookies
from db import columns_index, init_databases, save_lead_to_db

browser_lock = threading.Lock()

def get_cache_path():
    if os.path.exists('intercepted_api.json'):
        return 'intercepted_api.json'
    parent_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'intercepted_api.json')
    if os.path.exists(parent_path):
        return parent_path
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'intercepted_api.json')

def load_cached_data():
    cache_path = get_cache_path()
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading cache file: {e}")
            return None
    return None

# Load configuration dynamically from config/config.json
def load_scraper_config():
    project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    config_path = os.path.join(project_root, "config", "config.json")
    if not os.path.exists(config_path):
        config_path = os.path.join(project_root, "config.json")
    if not os.path.exists(config_path):
        # Return fallback configuration
        return {
            "cities": ["Ahmedabad", "Surat", "Rajkot"],
            "services": ["Pest Control Services", "Plumbers"],
            "page_chunk_size": 5,
            "max_empty_pages_limit": 2,
            "pagesave_directory": r"C:\Users\meetv\OneDrive\Desktop\big files\justdial\business"
        }
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            full_config = json.load(f)
            return full_config.get("scraper", {})
    except Exception as e:
        print(f"Error loading config.json in scraper.py: {e}")
        return {}

def refresh_session(city, business):
    # Lock the browser initialization to ensure thread-safety
    with browser_lock:
        print(f"\n--- Session expired or cache missing. Refreshing cookies via Playwright for '{business}' in '{city}' ---")
        try:
            response, cookies = get_cookies(
                search=business,
                lat=21.14204978942871,
                lng=72.7733383178711,
                city=city
            )
        except Exception as e:
            print(f"[ERROR] Playwright session refresh failed for '{business}' in '{city}': {e}")
            return None
        
        # Reload the newly written cache file
        data = load_cached_data()
        if data:
            return data
        else:
            cookie_dict = {c['name']: c['value'] for c in cookies}
            return {
                "url": "https://www.justdial.com/api/resultsPageListing?bids=07082026&searchReferer=gen%7Clst",
                "headers": response['body']['headers'],
                "json_data": response['body']['json_data'],
                "cookies": cookies
            }

# Fetch a single page's data and write compressed JSON files
def fetch_single_page(url, headers, json_data, cookie_dict, page_num, city, business, pagesave_dir):
    payload = json_data.copy()
    payload["pg_no"] = page_num
    
    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            cookies=cookie_dict,
            impersonate="chrome",
            timeout=15
        )
        text = response.text.strip()
    except Exception as e:
        return None, True, f"Connection error: {e}"

    if text.startswith("<HTML>") or text.startswith("<!DOCTYPE html>") or text.startswith("<html>") or text.startswith("<html"):
        return None, True, "Block page detected"

    try:
        res_json = response.json()
        
        # Save page response as gzip compressed JSON
        if pagesave_dir:
            try:
                import gzip
                os.makedirs(pagesave_dir, exist_ok=True)
                safe_business = business.lower().replace(" ", "_")
                safe_city = city.lower().replace(" ", "_")
                filename = f"{safe_business}_{safe_city}_{page_num}.json.gz"
                filepath = os.path.join(pagesave_dir, filename)
                with gzip.open(filepath, 'wt', encoding='utf-8') as gf:
                    json.dump(res_json, gf)
            except Exception as save_err:
                print(f"Error saving gzip page file: {save_err}")
                
        return res_json, False, ""
    except Exception as e:
        return None, False, f"JSON decode error: {e}"

def fetch_listings(city, business, mysql_conn, existing_docids=None):
    # Load settings from config
    scraper_settings = load_scraper_config()
    chunk_size = scraper_settings.get("page_chunk_size", 5)
    max_empty_pages_limit = scraper_settings.get("max_empty_pages_limit", 2)
    pagesave_dir = scraper_settings.get("pagesave_directory", "")

    # 1. Load cached session data and validate if it matches the request
    session_data = load_cached_data()
    cache_valid = False
    
    if session_data:
        cached_json = session_data.get("json_data", {})
        cached_search_raw = cached_json.get("search", "")
        cached_search = urllib.parse.unquote(cached_search_raw).strip().lower()
        cached_city = cached_json.get("city", "").strip().lower()
        
        # Compare search terms
        search_match = (business.lower() in cached_search) or (cached_search in business.lower())
        city_match = cached_city == city.lower()
        
        if search_match and city_match:
            cache_valid = True
            print(f"Reusing valid cached session for '{business}' in '{city}'.")
        else:
            print(f"Cache query mismatch (cached search: '{cached_search}' in '{cached_city}', requested search: '{business.lower()}' in '{city.lower()}').")

    if not cache_valid:
        session_data = refresh_session(city, business)

    if not session_data:
        print(f"[SKIP] Could not establish session for '{business}' in '{city}'. Skipping...")
        return []

    url = session_data.get("url")
    headers = session_data.get("headers", {})
    json_data = session_data.get("json_data", {})
    cookies = session_data.get("cookies", [])

    pg_no = 1
    all_results = []
    consecutive_empty_pages = 0
    
    # Filter for essential HTTP headers
    essential_headers = {}
    for key, val in headers.items():
        lower_key = key.lower()
        if lower_key in ["securitytoken", "jdpk", "referer", "content-type", "requesttime"]:
            essential_headers[key] = val

    while True:
        if isinstance(cookies, list):
            cookie_dict = {c['name']: c['value'] for c in cookies}
        else:
            cookie_dict = cookies

        # Chunked pagination in parallel
        pages_to_fetch = list(range(pg_no, pg_no + chunk_size))
        print(f"\n---> Fetching pages {pages_to_fetch} in parallel for '{business}' in '{city}'...")
        
        chunk_results = [None] * chunk_size
        session_expired = False
        expired_reason = ""
        
        with ThreadPoolExecutor(max_workers=chunk_size) as executor:
            futures = {executor.submit(fetch_single_page, url, essential_headers, json_data, cookie_dict, page, city, business, pagesave_dir): i for i, page in enumerate(pages_to_fetch)}
            
            for future in as_completed(futures):
                idx = futures[future]
                page_num = pages_to_fetch[idx]
                try:
                    res_json, is_block, err_msg = future.result()
                    if is_block:
                        session_expired = True
                        expired_reason = f"Page {page_num} block/captcha: {err_msg}"
                        break
                    
                    if res_json:
                        if "results" not in res_json:
                            session_expired = True
                            expired_reason = f"Page {page_num} response missing 'results' key: {json.dumps(res_json)[:200]}"
                            break
                        
                        results_obj = res_json.get("results")
                        data_list = results_obj.get("data") if results_obj else None
                        
                        # Get exact columns indexes dynamically from this API response
                        columns_map = {}
                        if results_obj and "columns" in results_obj:
                            for c_idx, c_name in enumerate(results_obj["columns"]):
                                columns_map[c_name] = c_idx
                        
                        chunk_results[idx] = (data_list, columns_map)
                    else:
                        chunk_results[idx] = ([], {})
                except Exception as e:
                    session_expired = True
                    expired_reason = f"Exception on page {page_num}: {e}"
                    break
        
        if session_expired:
            print(f"Session expired or blocked during parallel fetch ({expired_reason}). Refreshing session...")
            session_data = refresh_session(city, business)
            if not session_data:
                print(f"[SKIP] Could not re-establish session for '{business}' in '{city}'. Stopping pagination.")
                break
            url = session_data.get("url")
            headers = session_data.get("headers", {})
            json_data = session_data.get("json_data", {})
            cookies = session_data.get("cookies", [])
            
            essential_headers = {}
            for key, val in headers.items():
                lower_key = key.lower()
                if lower_key in ["securitytoken", "jdpk", "referer", "content-type", "requesttime"]:
                    essential_headers[key] = val
            continue
            
        empty_page_encountered = False
        scraped_in_chunk = 0
        duplicates_in_chunk = 0
        
        for idx in range(chunk_size):
            page_num = pages_to_fetch[idx]
            data_list, columns_map = chunk_results[idx] if chunk_results[idx] else (None, {})
            
            if not data_list:
                print(f"Page {page_num} is empty.")
                empty_page_encountered = True
                consecutive_empty_pages += 1
                break
            else:
                consecutive_empty_pages = 0
                page_items_count = len(data_list)
                print(f"Success: Fetched {page_items_count} items from page {page_num}")
                
                # Save each lead to MySQL database
                for row in data_list:
                    # Get docid of the row to prevent duplicates
                    docid_idx = columns_map.get("docid", columns_index.get("docid", 0))
                    docid = None
                    if docid_idx < len(row):
                        docid = str(row[docid_idx])
                    
                    if docid and existing_docids is not None:
                        if docid in existing_docids:
                            duplicates_in_chunk += 1
                            continue  # Skip duplicate lead
                        existing_docids.add(docid)
                        
                    save_lead_to_db(mysql_conn, row, columns_map, city, business, commit=False)
                    all_results.append(row)
                
                # Commit once per page
                if mysql_conn:
                    try:
                        mysql_conn.commit()
                    except Exception:
                        pass
                        
                scraped_in_chunk += page_items_count

        if duplicates_in_chunk:
            print(f"[Info] Skipped {duplicates_in_chunk} existing listings in this batch; saved {scraped_in_chunk - duplicates_in_chunk} new listings.")
                
        if empty_page_encountered or consecutive_empty_pages >= max_empty_pages_limit:
            break
            
        pg_no += chunk_size
        time.sleep(1)
        
    return all_results

def run_scraper(mysql_conn):
    settings = load_scraper_config()
    cities = settings.get("cities", ["Ahmedabad", "Surat", "Rajkot"])
    services = settings.get("services", ["Pest Control Services", "Plumbers"])
    
    # Load all existing docids from past tables to prevent duplicates
    from db import load_all_scraped_docids
    existing_docids = load_all_scraped_docids(mysql_conn)
    
    total_scraped_all = []
    
    for city in cities:
        for service in services:
            print(f"\n========================================================")
            print(f"[*] SCRAPING: '{service}' in '{city}'")
            print(f"========================================================")
            results = fetch_listings(city, service, mysql_conn, existing_docids)
            print(f"[Done] Scraped {len(results)} listings for '{service}' in '{city}'.")
            total_scraped_all.extend(results)
            
    print(f"\n========================================================")
    print(f"[Done] ALL JOBS COMPLETED! Total listings scraped across all runs: {len(total_scraped_all)}")
    print(f"========================================================")
    
    # Save consolidated JSON output
    output_filename = 'scraped_listings.json'
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(total_scraped_all, f, indent=4)
    print(f"Backup data saved to {output_filename}")
    
    return total_scraped_all
