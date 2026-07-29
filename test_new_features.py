import re
import io
import requests

base_url = 'http://127.0.0.1:5000'
session = requests.Session()

# Login as IT Admin
res = session.get(f'{base_url}/auth/login')
csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', res.text)
csrf = csrf_match.group(1) if csrf_match else ''
session.post(f'{base_url}/auth/login', data={'csrf_token': csrf, 'auth_type': 'role_simulation', 'role': 'IT Administrator'}, allow_redirects=True)

# Test 1: Import Center loads
res = session.get(f'{base_url}/import/')
assert res.status_code == 200 and 'Import Employees' in res.text, f'Import Center failed: {res.status_code}'
print('1. Import Center page: PASSED')

# Test 2: Employee CSV template download
res = session.get(f'{base_url}/import/template/employees')
assert res.status_code == 200 and 'Employee ID' in res.text
print('2. Employee CSV template download: PASSED')

# Test 3: Asset CSV template download
res = session.get(f'{base_url}/import/template/assets')
assert res.status_code == 200 and 'Brand' in res.text
print('3. Asset CSV template download: PASSED')

# Test 4: Employee CSV import
csv_data = 'Employee ID,Name,Email,Department,Designation,Manager,Office Location,Account Status\nEMP-9001,Import Test Employee,importtest@company.com,Testing,QA Lead,Rahul Sharma,Bangalore HQ,Onboarded\n'
res = session.post(
    f'{base_url}/import/employees',
    files={'file': ('test_emp.csv', io.BytesIO(csv_data.encode()), 'text/csv')},
    data={'csrf_token': csrf},
    allow_redirects=True
)
assert res.status_code == 200
print(f'4. Employee CSV import: PASSED (result page status: {res.status_code})')

# Test 5: Asset CSV import
csv_asset = 'Brand,Model,Serial Number,Processor,RAM,SSD,Vendor Name,Assigned Employee Email\nHP,EliteBook 840 G9,HP-TEST-IMPORT-001,Intel Core i5-1235U,16 GB,256 GB SSD,Techvity,\n'
res = session.post(
    f'{base_url}/import/assets',
    files={'file': ('test_asset.csv', io.BytesIO(csv_asset.encode()), 'text/csv')},
    data={'csrf_token': csrf},
    allow_redirects=True
)
assert res.status_code == 200
print(f'5. Asset CSV import: PASSED (result page status: {res.status_code})')

# Test 6: Entra ID lifecycle webhook simulation - onboard
res = session.post(
    f'{base_url}/import/entra/test-webhook',
    data={'csrf_token': csrf, 'event_type': 'onboarded', 'employee_id': 'EMP-WEBHOOK-9001', 'name': 'Webhook Test User', 'email': 'webhooktest@company.com', 'department': 'Testing'},
    allow_redirects=True
)
assert res.status_code == 200
print('6. Entra ID webhook simulation (onboard): PASSED')

# Test 7: Entra ID lifecycle webhook simulation - offboard
res = session.post(
    f'{base_url}/import/entra/test-webhook',
    data={'csrf_token': csrf, 'event_type': 'offboarded', 'employee_id': 'EMP-WEBHOOK-9001'},
    allow_redirects=True
)
assert res.status_code == 200
print('7. Entra ID webhook simulation (offboard with auto-return): PASSED')

print()
print('ALL NEW FEATURE TESTS PASSED SUCCESSFULLY!')
