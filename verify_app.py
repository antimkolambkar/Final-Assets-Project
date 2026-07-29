import re
import requests

base_url = 'http://127.0.0.1:5000'
session = requests.Session()

print("1. Testing GET /auth/login...")
res = session.get(f"{base_url}/auth/login")
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
print("   /auth/login loaded successfully!")

# Extract CSRF token
csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', res.text)
csrf_token = csrf_match.group(1) if csrf_match else ''

print("2. Testing Role Simulation Login (IT Administrator)...")
res = session.post(f"{base_url}/auth/login", data={
    'csrf_token': csrf_token,
    'auth_type': 'role_simulation',
    'role': 'IT Administrator'
}, allow_redirects=True)
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
assert "Dashboard" in res.text, "Dashboard heading not found in response!"
print("   Signed in successfully as IT Administrator!")

print("3. Testing GET /dashboard/api/metrics JSON...")
res = session.get(f"{base_url}/dashboard/api/metrics")
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
metrics = res.json()
print(f"   Metrics loaded: Total Assets={metrics['cards']['total_assets']}, Active Employees={metrics['cards']['active_employees']}")

print("4. Testing GET /employees...")
res = session.get(f"{base_url}/employees/")
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
assert "Rahul Sharma" in res.text, "Employee Rahul Sharma not found!"
print("   Employees page verified!")

print("5. Testing GET /assets...")
res = session.get(f"{base_url}/assets/")
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
assert "AST-2026-0001" in res.text, "Asset AST-2026-0001 not found!"
assert "Rahul Sharma" in res.text, "Assigned User Name Rahul Sharma not found on Asset record!"
print("   Assets page verified with assigned User Name display!")

print("6. Testing GET /assets/1/history JSON (Multi-Replacement Tracking)...")
res = session.get(f"{base_url}/assets/1/history")
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
hist_data = res.json()
print(f"   Asset History Loaded for {hist_data['asset_id']}: {len(hist_data['history'])} history entries.")
print(f"   Assigned User: {hist_data['assigned_user']}")

print("7. Testing GET /tickets...")
res = session.get(f"{base_url}/tickets/")
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
assert "TKT-2026-0001" in res.text, "Ticket TKT-2026-0001 not found!"
print("   Tickets page verified!")

print("8. Testing GET /vendors...")
res = session.get(f"{base_url}/vendors/")
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
assert "Techvity" in res.text, "Default vendor Techvity not found!"
print("   Vendors page verified!")

print("9. Testing GET /reports...")
res = session.get(f"{base_url}/reports/")
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
print("   Reports page verified!")

print("10. Testing Excel Report Export...")
res = session.get(f"{base_url}/reports/export/excel?type=asset")
assert res.status_code == 200 and len(res.content) > 1000, "Excel export failed!"
print("    Excel export verified!")

print("\n========================================================")
print("ALL BACKEND & UI VERIFICATION TESTS PASSED 100% SUCCESSFULLY!")
print("========================================================")
