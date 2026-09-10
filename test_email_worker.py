import requests

BASE_URL = "https://nexora-backend-eoof.onrender.com"

# 1. Login to get token
login_data = {
    "username": "meet_0001",
    "password": "9173739080@Meet"
}
try:
    print("Logging into Render API...")
    response = requests.post(f"{BASE_URL}/api/v1/auth/login", data=login_data)
    response.raise_for_status()
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Login successful.")
except Exception as e:
    print("Login Failed:", e)
    exit(1)

# 2. Inject test lead
target_email = "meetvaghasiya6@gmail.com"
print(f"Injecting test lead with email: {target_email}")
try:
    response = requests.post(f"{BASE_URL}/api/v1/scraped-leads/test-inject?email={target_email}", headers=headers)
    response.raise_for_status()
    lead_data = response.json()
    print("Successfully injected test lead!")
    print(lead_data)
except Exception as e:
    print("Failed to inject lead:", e)
    print(response.text if 'response' in locals() else "")
    exit(1)

print("\nLead has been injected! The background Email Worker on Render should pick it up automatically during its next cycle (within 1-5 minutes).")
print("Check your email inbox or the Admin Panel's Outreach status!")
