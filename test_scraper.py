import requests
import time

BASE_URL = "https://nexora-backend-eoof.onrender.com"
# Or use "http://127.0.0.1:8000" if you want to test your local backend server

print(f"Testing Scraper API on: {BASE_URL}")

# 1. Login to get token (make sure these admin credentials match your database!)
login_data = {
    "username": "meet_0001",
    "password": "9173739080@Meet"
}
try:
    response = requests.post(f"{BASE_URL}/api/v1/auth/login", data=login_data)
    response.raise_for_status()
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Login successful.")
except Exception as e:
    print("Login Failed:", e)
    print(response.text if 'response' in locals() else "")
    exit(1)

# 2. Trigger scraper
scraper_data = {
    "cities": ["Surat"],
    "keywords": ["dentist"],
    "max_pages": 1
}
print(f"Triggering Scraper for {scraper_data['keywords'][0]} in {scraper_data['cities'][0]}...")
trigger_resp = requests.post(f"{BASE_URL}/api/v1/scraper/run", json=scraper_data, headers=headers)
print("Trigger Response:", trigger_resp.json())

# 3. Check status and log history repeatedly
print("\nWaiting for scraper to run in background...\n")
for _ in range(5):
    time.sleep(4)
    status_resp = requests.get(f"{BASE_URL}/api/v1/scraper/status", headers=headers)
    state = status_resp.json()
    print("Status:", state.get("status"))
    if state.get("error"):
        print("Error:", state.get("error"))
        
    print("=== LATEST LOGS ===")
    # Print the last 6 lines of logs
    for line in state.get("log_history", [])[-6:]:
        print(line)
    print("-------------------\n")
