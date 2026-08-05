"""
Excel Import Service
Parses uploaded .xlsx / .xls / .csv files and bulk-imports:
  - Employees (from HR Excel exports)
  - Assets / Laptops (from existing IT inventory Excel)

Supported Import Templates:
  - employees: Employee ID, Name, Email, Department, Designation, Manager, Office Location
  - assets: Brand, Model, Serial Number, Processor, RAM, SSD, Vendor Name, Assigned Employee Email
"""

import io
import csv
from datetime import datetime

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

from app.extensions import db
from app.models.employee import Employee, AccountStatus
from app.models.asset import Asset, AssetStatus, AssetAssignmentHistory
from app.models.vendor import Vendor
from app.services.audit_service import AuditService


class ImportResult:
    def __init__(self):
        self.success_count = 0
        self.skip_count = 0
        self.error_count = 0
        self.errors = []
        self.warnings = []
        self.created_records = []

    def add_error(self, row_num, message):
        self.errors.append(f"Row {row_num}: {message}")
        self.error_count += 1

    def add_warning(self, row_num, message):
        self.warnings.append(f"Row {row_num}: {message}")

    def add_success(self, record_id):
        self.created_records.append(record_id)
        self.success_count += 1

    def add_skip(self, row_num, message):
        self.warnings.append(f"Row {row_num} SKIPPED: {message}")
        self.skip_count += 1

    @property
    def summary(self):
        return {
            'success': self.success_count,
            'skipped': self.skip_count,
            'errors': self.error_count,
            'error_messages': self.errors,
            'warnings': self.warnings,
            'created_records': self.created_records
        }


class ExcelImportService:

    # -------------------------------------------------------
    # EMPLOYEE IMPORT
    # -------------------------------------------------------

    EMPLOYEE_COLUMNS = [
        'employee_id', 'name', 'email', 'department',
        'designation', 'manager', 'office_location', 'account_status'
    ]

    # -------------------------------------------------------
    # ASSET IMPORT
    # -------------------------------------------------------

    ASSET_COLUMNS = [
    'brand',
    'model',
    'serial_number',
    'processor',
    'ram',
    'ssd',
    'vendor_name',
    'user_name'
]

    @staticmethod
    def _read_file(file_obj, filename):
        """
        Reads uploaded file (xlsx, xls, or csv) and returns list of row dicts.
        Normalizes column headers: strip whitespace, lowercase, replace spaces with underscores.
        """
        filename_lower = filename.lower()
        rows = []

        if filename_lower.endswith('.csv'):
            try:
                content = file_obj.read().decode('utf-8-sig')
                reader = csv.DictReader(io.StringIO(content))
                for row in reader:
                    normalized = {k.strip().lower().replace(' ', '_'): (v.strip() if v else '') for k, v in row.items()}
                    rows.append(normalized)
                return rows, None
            except Exception as e:
                return [], f"CSV read error: {str(e)}"

        elif filename_lower.endswith('.xlsx') or filename_lower.endswith('.xls'):
            if not OPENPYXL_AVAILABLE:
                return [], "openpyxl is not installed. Run: pip install openpyxl"
            try:
                wb = openpyxl.load_workbook(file_obj, read_only=True, data_only=True)
                ws = wb.active
                headers = []
                for row_idx, row in enumerate(ws.iter_rows(values_only=True)):
                    if row_idx == 0:
                        headers = [str(c).strip().lower().replace(' ', '_') if c else f'col_{i}'
                                   for i, c in enumerate(row)]
                    else:
                        if all(cell is None for cell in row):
                            continue
                        row_dict = {}
                        for col_idx, val in enumerate(row):
                            if col_idx < len(headers):
                                row_dict[headers[col_idx]] = str(val).strip() if val is not None else ''
                        rows.append(row_dict)
                return rows, None
            except Exception as e:
                return [], f"Excel read error: {str(e)}"

        else:
            return [], "Unsupported file format. Please upload .xlsx, .xls, or .csv"

    @staticmethod
    def import_employees(file_obj, filename, performed_by='System Import'):
        """
        Bulk import employees from Excel/CSV.

        Expected columns (case-insensitive, spaces allowed):
            Employee ID | Name | Email | Department | Designation | Manager | Office Location | Account Status

        Rules:
        - If Employee ID already exists → UPDATE
        - If email already exists with different ID → SKIP with warning
        - Account Status defaults to 'Onboarded' if blank/invalid
        - All fields except Name and Email are optional
        """
        result = ImportResult()
        rows, error = ExcelImportService._read_file(file_obj, filename)

        if error:
            result.add_error(0, error)
            return result.summary

        if not rows:
            result.add_error(0, "File appears to be empty or has no data rows.")
            return result.summary

        valid_statuses = [AccountStatus.ONBOARDED, AccountStatus.ACTIVE,
                          AccountStatus.BLOCKED, AccountStatus.DISABLED, AccountStatus.OFFBOARDED]

        for row_num, row in enumerate(rows, start=2):
            name = row.get('name', '').strip()
            email = row.get('email', '').strip()
            emp_id_raw = row.get('employee_id', '').strip()
            department = row.get('department', '').strip()
            designation = row.get('designation', '').strip()
            manager = row.get('manager', '').strip()
            office_location = row.get('office_location', '').strip()
            status_raw = row.get('account_status', '').strip()

            if not name or not email:
                result.add_error(row_num, f"Name and Email are required. Got: name='{name}', email='{email}'")
                continue

            # Validate status
            status = AccountStatus.ONBOARDED
            if status_raw:
                matched = next((s for s in valid_statuses if s.lower() == status_raw.lower()), None)
                if matched:
                    status = matched
                else:
                    result.add_warning(row_num, f"Unknown status '{status_raw}' - defaulting to 'Onboarded'")

            # Auto-generate employee ID if blank
            if not emp_id_raw:
                count = Employee.query.count() + 1001 + row_num
                emp_id_raw = f"EMP-IMP-{count}"

            # Check if employee already exists by ID
            existing_by_id = Employee.query.filter_by(employee_id=emp_id_raw).first()
            existing_by_email = Employee.query.filter_by(email=email).first()

            if existing_by_id:
                # Update existing record
                existing_by_id.name = name
                existing_by_id.email = email
                existing_by_id.department = department
                existing_by_id.designation = designation
                existing_by_id.manager = manager
                existing_by_id.office_location = office_location
                existing_by_id.account_status = status
                existing_by_id.last_synced_at = datetime.utcnow()
                result.add_warning(row_num, f"Updated existing employee {emp_id_raw} - {name}")
                result.add_success(emp_id_raw)
                continue

            if existing_by_email and not existing_by_id:
                result.add_skip(row_num, f"Email '{email}' already exists for a different employee ID. Skipped.")
                continue

            # Create new employee
            new_emp = Employee(
                employee_id=emp_id_raw,
                name=name,
                email=email,
                department=department,
                designation=designation,
                manager=manager,
                office_location=office_location,
                account_status=status,
                created_at=datetime.utcnow(),
                last_synced_at=datetime.utcnow()
            )
            db.session.add(new_emp)
            result.add_success(emp_id_raw)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            result.add_error(0, f"Database commit error: {str(e)}")

        if result.success_count > 0:
            AuditService.log(
                action='Employee Bulk Import (Excel)',
                entity_type='EmployeeImport',
                details=f'Imported {result.success_count} employees from {filename}. Skipped: {result.skip_count}, Errors: {result.error_count}',
                user_name=performed_by
            )

        return result.summary

    @staticmethod
    def import_assets(file_obj, filename, performed_by='System Import'):
        """
        Bulk import assets/laptops from Excel/CSV.

        Expected columns (case-insensitive, spaces allowed):
            Brand | Model | Serial Number | Processor | RAM | SSD | Vendor Name | Assigned Employee Email

        Rules:
        - Serial Number must be unique - duplicates SKIP
        - Vendor Name is matched to existing vendors (case-insensitive). If not found → skip vendor
        - Assigned Employee Email is optional; if provided and found → auto-assign
        - Asset ID is auto-generated
        """
        result = ImportResult()
        rows, error = ExcelImportService._read_file(file_obj, filename)

        if error:
            result.add_error(0, error)
            return result.summary

        if not rows:
            result.add_error(0, "File appears to be empty or has no data rows.")
            return result.summary

        for row_num, row in enumerate(rows, start=2):
            brand = row.get('brand', '').strip()
            model = row.get('model', '').strip()
            serial_number = row.get('serial_number', '').strip()
            processor = row.get('processor', '').strip()
            ram = row.get('ram', '').strip()
            ssd = row.get('ssd', '').strip()
            vendor_name = row.get('vendor_name', '').strip()
            user_name = row.get('user_name', '').strip()

            if not brand or not model or not serial_number:
                result.add_error(row_num, f"Brand, Model, and Serial Number are required. Got: brand='{brand}', model='{model}', serial='{serial_number}'")
                continue

            # Check serial number uniqueness
            existing = Asset.query.filter_by(serial_number=serial_number).first()
            if existing:
                result.add_skip(row_num, f"Serial Number '{serial_number}' already exists (Asset {existing.asset_id}). Skipped.")
                continue

            # Match vendor
            vendor_id = None
            if vendor_name:
                vendor = Vendor.query.filter(Vendor.name.ilike(f'%{vendor_name}%')).first()
                if vendor:
                    vendor_id = vendor.id
                else:
                    result.add_warning(row_num, f"Vendor '{vendor_name}' not found in system. Asset added without vendor.")

            # Auto-generate Asset ID
            year = datetime.utcnow().strftime('%Y')
            count = Asset.query.count() + row_num
            asset_id = f"AST-{year}-{count:04d}"

            # Ensure unique asset_id
            while Asset.query.filter_by(asset_id=asset_id).first():
                count += 1
                asset_id = f"AST-{year}-{count:04d}"

            new_asset = Asset(
                asset_id=asset_id,
                brand=brand,
                model=model,
                serial_number=serial_number,
                processor=processor or 'N/A',
                ram=ram or 'N/A',
                ssd=ssd or 'N/A',
                vendor_id=vendor_id,
                status=AssetStatus.AVAILABLE
            )
            db.session.add(new_asset)
            db.session.flush()

            # Save username exactly as written in Excel
if user_name:

    new_asset.status = AssetStatus.ASSIGNED

    # Save the username only
    new_asset.assigned_to = user_name

    new_asset.assignment_date = datetime.utcnow()

    hist = AssetAssignmentHistory(
        asset_id=new_asset.id,
        employee_name=user_name,
        action="Assigned (Excel Import)",
        notes=f"Imported and assigned to {user_name}",
        performed_by=performed_by
    )

    db.session.add(hist)

            result.add_success(asset_id)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            result.add_error(0, f"Database commit error: {str(e)}")

        if result.success_count > 0:
            AuditService.log(
                action='Asset Bulk Import (Excel)',
                entity_type='AssetImport',
                details=f'Imported {result.success_count} assets from {filename}. Skipped: {result.skip_count}, Errors: {result.error_count}',
                user_name=performed_by
            )

        return result.summary

    @staticmethod
    def generate_employee_template():
        """Returns a CSV template string for employee import"""
        headers = ['Employee ID', 'Name', 'Email', 'Department', 'Designation', 'Manager', 'Office Location', 'Account Status']
        sample = [
            'EMP-2001', 'Vikramaditya Singh', 'vikram@company.com', 'Software Engineering',
            'Senior Developer', 'Rahul Sharma', 'Bangalore HQ', 'Onboarded'
        ]
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerow(sample)
        return output.getvalue()

    @staticmethod
    def generate_asset_template():
        """Returns a CSV template string for asset import"""
        headers = [
    'Brand',
    'Model',
    'Serial Number',
    'Processor',
    'RAM',
    'SSD',
    'Vendor Name',
    'User Name'
]
        sample = [
    'Dell',
    'Latitude 7430',
    'DL-7430-XXXX',
    'Intel Core i7-1265U',
    '16 GB',
    '512 GB SSD',
    'Techvity',
    'Vikram Singh'
]
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerow(sample)
        return output.getvalue()
