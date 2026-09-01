import time
import sys
from curl_cffi import requests

BASE_URL = "http://127.0.0.1:8000"
API_PREFIX = "/api/v1"

def print_result(name, response, elapsed_ms):
    status = response.status_code
    status_str = "OK" if status in (200, 201, 204) else "FAIL"
    print(f"[{status_str:<4}] {name:<30} | Status: {status} | Time: {elapsed_ms:>6.2f} ms")
    if status not in (200, 201, 204):
        try:
            print(f"    Detail: {response.json()}")
        except Exception:
            print(f"    Raw content: {response.text[:200]}")

def run_diagnostics():
    print("======================================================================")
    print("STARTING API DIAGNOSTICS & PERFORMANCE TEST")
    print("======================================================================\n")

    session = requests.Session()
    
    # 1. Test Root endpoint
    t0 = time.time()
    try:
        r = session.get(f"{BASE_URL}/")
        dt = (time.time() - t0) * 1000
        print_result("Root Welcome API", r, dt)
    except Exception as e:
        print(f"[FAIL] Failed to connect to server at {BASE_URL}: {e}")
        sys.exit(1)

    # 2. Test Public endpoints
    public_endpoints = [
        ("Public Services", f"{API_PREFIX}/public/services"),
        ("Public FAQs", f"{API_PREFIX}/public/faqs"),
        ("Public Testimonials", f"{API_PREFIX}/public/testimonials"),
        ("Public Portfolio", f"{API_PREFIX}/public/portfolio"),
    ]
    
    for name, path in public_endpoints:
        t0 = time.time()
        r = session.get(f"{BASE_URL}{path}")
        dt = (time.time() - t0) * 1000
        print_result(name, r, dt)

    # 3. Test Authentication (Form-based Login)
    login_data = {
        "username": "meet_0001",
        "password": "9173739080@Meet"
    }
    t0 = time.time()
    r = session.post(f"{BASE_URL}{API_PREFIX}/auth/login", data=login_data)
    dt = (time.time() - t0) * 1000
    print_result("Admin Form Login", r, dt)
    
    token = None
    if r.status_code == 200:
        token = r.json().get("access_token")
        
    # Test Authentication (JSON Login)
    t0 = time.time()
    r_json = session.post(f"{BASE_URL}{API_PREFIX}/auth/login/json", json=login_data)
    dt = (time.time() - t0) * 1000
    print_result("Admin JSON Login", r_json, dt)

    if not token and r_json.status_code == 200:
        token = r_json.json().get("access_token")

    if not token:
        print("\n[!] Skipping authenticated endpoints tests because login failed.")
        sys.exit(1)

    # Set Auth Header for subsequent tests
    headers = {"Authorization": f"Bearer {token}"}
    session.headers.update(headers)

    # 4. Test Authenticated endpoints
    auth_endpoints = [
        ("Auth Profile (Me)", f"{API_PREFIX}/auth/me"),
        ("Scraper Status", f"{API_PREFIX}/scraper/status"),
        ("Scraped Leads List", f"{API_PREFIX}/scraped-leads/"),
        ("Leads (CRM)", f"{API_PREFIX}/leads/"),
        ("Contacts Messages", f"{API_PREFIX}/contacts/"),
        ("Blogs Workspace", f"{API_PREFIX}/blogs/"),
        ("Portfolio Items Workspace", f"{API_PREFIX}/portfolio/"),
        ("Services Workspace", f"{API_PREFIX}/services/"),
        ("FAQs Workspace", f"{API_PREFIX}/faqs/"),
        ("Testimonials Workspace", f"{API_PREFIX}/testimonials/"),
        ("SEO Settings Workspace", f"{API_PREFIX}/seo/"),
    ]

    for name, path in auth_endpoints:
        t0 = time.time()
        r = session.get(f"{BASE_URL}{path}")
        dt = (time.time() - t0) * 1000
        print_result(name, r, dt)

    print("\n======================================================================")
    print("DIAGNOSTICS COMPLETE")
    print("======================================================================")

if __name__ == "__main__":
    run_diagnostics()
