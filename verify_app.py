import re
import requests
from app import create_app, db
from app.models.user import User, Role

# Ensure test admin user exists for verification
app = create_app()
with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin', email='admin@company.com', full_name='System Admin', role=Role.SUPER_ADMIN, department='IT')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()

base_url = 'http://127.0.0.1:5000'
session = requests.Session()

print("1. Testing GET /auth/login...")
res = session.get(f"{base_url}/auth/login")
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
print("   /auth/login loaded successfully!")

# Extract CSRF token
csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', res.text)
csrf_token = csrf_match.group(1) if csrf_match else ''

print("2. Testing Credential Login (Admin)...")
res = session.post(f"{base_url}/auth/login", data={
    'csrf_token': csrf_token,
    'username': 'admin',
    'password': 'admin123'
}, allow_redirects=True)
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
assert "Dashboard" in res.text, "Dashboard heading not found in response!"
print("   Signed in successfully with local admin credentials!")

print("3. Testing GET /dashboard/api/metrics JSON on Clean Database...")
res = session.get(f"{base_url}/dashboard/api/metrics")
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
metrics = res.json()
print(f"   Metrics verified: Total Assets={metrics['cards']['total_assets']}, Active Employees={metrics['cards']['active_employees']}")

print("4. Testing GET /employees (Empty State)...")
res = session.get(f"{base_url}/employees/")
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
print("   Employees page verified!")

print("5. Testing GET /assets (Empty State)...")
res = session.get(f"{base_url}/assets/")
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
print("   Assets page verified!")

print("6. Testing GET /tickets (Empty State)...")
res = session.get(f"{base_url}/tickets/")
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
print("   Tickets page verified!")

print("7. Testing GET /vendors (Empty State)...")
res = session.get(f"{base_url}/vendors/")
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
print("   Vendors page verified!")

print("8. Testing GET /reports...")
res = session.get(f"{base_url}/reports/")
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
print("   Reports page verified!")

print("\n========================================================")
print("ALL CLEAN DATABASE VERIFICATION TESTS PASSED 100% SUCCESSFULLY!")
print("========================================================")
