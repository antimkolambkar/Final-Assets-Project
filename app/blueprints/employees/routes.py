from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    flash,
    redirect,
    url_for
)

from flask_login import login_required, current_user

from app.extensions import db

from app.models.employee import Employee, AccountStatus

from app.models.asset import (
    Asset,
    AssetStatus,
    AssetAssignmentHistory
)

from app.services.graph_service import MicrosoftGraphService
from app.services.audit_service import AuditService


employees_bp = Blueprint(
    'employees',
    __name__,
    url_prefix='/employees'
)


# =========================================================
# EMPLOYEE ID GENERATOR
# =========================================================

def generate_employee_id():
    count = Employee.query.count() + 1001
    return f"EMP-{count}"


# =========================================================
# VALID ACCOUNT STATUSES
# =========================================================

VALID_ACCOUNT_STATUSES = {
    AccountStatus.ONBOARDED,
    AccountStatus.ACTIVE,
    AccountStatus.BLOCKED,
    AccountStatus.DISABLED,
    AccountStatus.OFFBOARDED
}


# =========================================================
# STATUS DATE HELPERS
# =========================================================

def status_date_field(status):
    """
    Returns the Employee model field name belonging
    to the selected account status.
    """

    return {
        AccountStatus.ONBOARDED: 'onboarded_date',
        AccountStatus.ACTIVE: 'active_date',
        AccountStatus.BLOCKED: 'blocked_date',
        AccountStatus.DISABLED: 'disabled_date',
        AccountStatus.OFFBOARDED: 'offboarded_date'
    }.get(status)


def set_status_date(employee, status, date_value=None):
    """
    Set the date for the selected status.

    If date_value is supplied, it is used.
    Otherwise today's UTC date is used.
    """

    field = status_date_field(status)

    if not field:
        return

    if date_value is None:
        date_value = datetime.utcnow().date()

    setattr(employee, field, date_value)


def parse_date(value, field_name):
    """
    Convert YYYY-MM-DD string into date object.
    """

    if not value:
        return None

    try:
        return datetime.strptime(
            value,
            '%Y-%m-%d'
        ).date()

    except ValueError:
        raise ValueError(
            f'Invalid {field_name}.'
        )


def date_to_string(value):
    """
    Convert date to YYYY-MM-DD.
    """

    if not value:
        return None

    return value.strftime('%Y-%m-%d')


# =========================================================
# EMPLOYEE INDEX
# =========================================================

@employees_bp.route('/')
@login_required
def index():

    search_q = request.args.get(
        'q',
        ''
    ).strip()

    status_filter = request.args.get(
        'status',
        ''
    ).strip()

    dept_filter = request.args.get(
        'department',
        ''
    ).strip()

    page = request.args.get(
        'page',
        1,
        type=int
    )

    query = Employee.query

    # -----------------------------------------------------
    # Search
    # -----------------------------------------------------

    if search_q:

        query = query.filter(
            (Employee.name.ilike(f'%{search_q}%')) |
            (Employee.employee_id.ilike(f'%{search_q}%')) |
            (Employee.email.ilike(f'%{search_q}%')) |
            (Employee.designation.ilike(f'%{search_q}%'))
        )

    # -----------------------------------------------------
    # Status Filter
    # -----------------------------------------------------

    if status_filter in VALID_ACCOUNT_STATUSES:

        query = query.filter(
            Employee.account_status == status_filter
        )

    # -----------------------------------------------------
    # Department Filter
    # -----------------------------------------------------

    if dept_filter:

        query = query.filter(
            Employee.department == dept_filter
        )

    # -----------------------------------------------------
    # Pagination
    # -----------------------------------------------------

    pagination = (
        query
        .order_by(
            Employee.created_at.desc(),
            Employee.name.asc()
        )
        .paginate(
            page=page,
            per_page=10,
            error_out=False
        )
    )

    employees = pagination.items

    # -----------------------------------------------------
    # Department Dropdown
    # -----------------------------------------------------

    departments = [
        d[0]
        for d in (
            db.session
            .query(Employee.department)
            .distinct()
            .all()
        )
        if d[0]
    ]

    departments.sort()

    # -----------------------------------------------------
    # Available Assets
    # -----------------------------------------------------

    available_assets = (
        Asset.query
        .filter(
            Asset.status == AssetStatus.AVAILABLE
        )
        .order_by(
            Asset.brand.asc()
        )
        .all()
    )

    # -----------------------------------------------------
    # Render
    # -----------------------------------------------------

    return render_template(
        'employees/index.html',

        employees=employees,

        pagination=pagination,

        search_q=search_q,

        status_filter=status_filter,

        dept_filter=dept_filter,

        departments=departments,

        available_assets=available_assets,

        account_statuses=[
            AccountStatus.ONBOARDED,
            AccountStatus.ACTIVE,
            AccountStatus.BLOCKED,
            AccountStatus.DISABLED,
            AccountStatus.OFFBOARDED
        ]
    )


# =========================================================
# DIRECT EMPLOYEE ONBOARDING
# =========================================================

@employees_bp.route(
    '/onboard',
    methods=['POST']
)
@login_required
def onboard_employee():

    """Direct Employee Onboarding & Laptop Allocation"""

    # -----------------------------------------------------
    # Permission
    # -----------------------------------------------------

    if not current_user.is_it_admin:

        flash(
            'Permission denied. Only IT Admins can onboard new employees.',
            'danger'
        )

        return redirect(
            url_for('employees.index')
        )

    # -----------------------------------------------------
    # Form Data
    # -----------------------------------------------------

    name = request.form.get(
        'name',
        ''
    ).strip()

    email = request.form.get(
        'email',
        ''
    ).strip()

    emp_code = request.form.get(
        'employee_id',
        ''
    ).strip()

    department = request.form.get(
        'department',
        ''
    ).strip()

    designation = request.form.get(
        'designation',
        ''
    ).strip()

    office_location = request.form.get(
        'office_location',
        ''
    ).strip()

    manager = request.form.get(
        'manager',
        ''
    ).strip()

    status = request.form.get(
        'status',
        AccountStatus.ONBOARDED
    ).strip()

    asset_id = request.form.get(
        'asset_id',
        type=int
    )

    # -----------------------------------------------------
    # Required Fields
    # -----------------------------------------------------

    if not name or not email:

        flash(
            'Employee Name and Email Address are required for onboarding.',
            'danger'
        )

        return redirect(
            url_for('employees.index')
        )

    # -----------------------------------------------------
    # Validate Status
    # -----------------------------------------------------

    if status not in VALID_ACCOUNT_STATUSES:

        flash(
            'Invalid employee account status selected.',
            'danger'
        )

        return redirect(
            url_for('employees.index')
        )

    # -----------------------------------------------------
    # Uniqueness Check
    # -----------------------------------------------------

    existing_email = Employee.query.filter(
        Employee.email == email
    ).first()

    if existing_email:

        flash(
            f'An employee with email "{email}" already exists.',
            'danger'
        )

        return redirect(
            url_for('employees.index')
        )

    if emp_code:

        existing_id = Employee.query.filter(
            Employee.employee_id == emp_code
        ).first()

        if existing_id:

            flash(
                f'Employee ID "{emp_code}" already exists.',
                'danger'
            )

            return redirect(
                url_for('employees.index')
            )

    # -----------------------------------------------------
    # Generate Employee ID
    # -----------------------------------------------------

    if not emp_code:

        emp_code = generate_employee_id()

    # -----------------------------------------------------
    # Status Date
    # -----------------------------------------------------

    today = datetime.utcnow().date()

    status_dates = {
        'onboarded_date': None,
        'active_date': None,
        'blocked_date': None,
        'disabled_date': None,
        'offboarded_date': None
    }

    selected_date_field = status_date_field(status)

    if selected_date_field:
        status_dates[selected_date_field] = today

    # -----------------------------------------------------
    # Create Employee
    # -----------------------------------------------------

    new_emp = Employee(
        employee_id=emp_code,
        name=name,
        email=email,
        department=department,
        designation=designation,
        office_location=office_location,
        manager=manager,
        account_status=status,
        onboarded_date=status_dates['onboarded_date'],
        active_date=status_dates['active_date'],
        blocked_date=status_dates['blocked_date'],
        disabled_date=status_dates['disabled_date'],
        offboarded_date=status_dates['offboarded_date'],
        created_at=datetime.utcnow()
    )

    db.session.add(new_emp)

    db.session.flush()

    # -----------------------------------------------------
    # Laptop Allocation
    # -----------------------------------------------------

    assigned_asset_msg = ""

    if asset_id:

        asset = db.session.get(
            Asset,
            asset_id
        )

        if asset and asset.status == AssetStatus.AVAILABLE:

            asset.status = AssetStatus.ASSIGNED

            asset.assigned_employee_id = new_emp.id

            asset.assignment_date = datetime.utcnow()

            hist = AssetAssignmentHistory(
                asset_id=asset.id,
                employee_id=new_emp.id,
                employee_name=new_emp.name,
                action='Assigned Onboarding',
                notes=(
                    'Direct laptop assignment during employee '
                    f'onboarding ({new_emp.employee_id})'
                ),
                performed_by=current_user.full_name
            )

            db.session.add(hist)

            assigned_asset_msg = (
                f" Assigned laptop {asset.asset_id} "
                f"({asset.brand} {asset.model})."
            )

        else:

            db.session.rollback()

            flash(
                'Selected laptop is no longer available.',
                'danger'
            )

            return redirect(
                url_for('employees.index')
            )

    # -----------------------------------------------------
    # Save
    # -----------------------------------------------------

    try:

        db.session.commit()

    except Exception as e:

        db.session.rollback()

        flash(
            f'Failed to onboard employee: {str(e)}',
            'danger'
        )

        return redirect(
            url_for('employees.index')
        )

    # -----------------------------------------------------
    # Audit
    # -----------------------------------------------------

    try:

        AuditService.log(
            action='Employee Onboarded',
            entity_type='Employee',
            entity_id=new_emp.employee_id,
            details=(
                f'Employee {new_emp.name} '
                f'({new_emp.employee_id}) created with status '
                f'{new_emp.account_status}. '
                f'Status date: {today}.'
                f'{assigned_asset_msg}'
            )
        )

    except Exception:

        pass

    # -----------------------------------------------------
    # Success
    # -----------------------------------------------------

    flash(
        f'Employee {new_emp.name} '
        f'({new_emp.employee_id}) onboarded successfully!'
        f'{assigned_asset_msg}',
        'success'
    )

    return redirect(
        url_for('employees.index')
    )


# =========================================================
# ENTRA ID SYNC
# =========================================================

@employees_bp.route(
    '/sync',
    methods=['POST']
)
@login_required
def sync_employees():

    """Trigger Microsoft Entra ID employee synchronization"""

    if not current_user.is_it_admin:

        flash(
            'Permission denied.',
            'danger'
        )

        return redirect(
            url_for('employees.index')
        )

    try:

        res = MicrosoftGraphService.sync_entra_employees()

        flash(
            f"Entra ID Sync Complete! "
            f"Synced {res['total']} employees. "
            f"(Created: {res.get('created', 0)}, "
            f"Updated: {res.get('updated', 0)}, "
            f"Onboarded: {res.get('onboarded', 0)}, "
            f"Active: {res.get('active', 0)}, "
            f"Blocked: {res.get('blocked', 0)}, "
            f"Disabled: {res.get('disabled', 0)}, "
            f"Offboarded: {res.get('offboarded', 0)}, "
            f"Laptops Returned: {res.get('returned_assets', 0)})",
            'success'
        )

    except Exception as e:

        flash(
            f'Entra ID Sync failed: {str(e)}',
            'danger'
        )

    return redirect(
        url_for('employees.index')
    )


# =========================================================
# EMPLOYEE JSON / PROFILE
# =========================================================

@employees_bp.route(
    '/<int:emp_id>/json'
)
@login_required
def get_employee_json(emp_id):

    emp = Employee.query.get_or_404(emp_id)

    # -----------------------------------------------------
    # Assigned Assets
    # -----------------------------------------------------

    assigned_assets = (
        Asset.query
        .filter(
            Asset.assigned_employee_id == emp.id
        )
        .all()
    )

    assets_data = []

    for a in assigned_assets:

        assets_data.append({

            'id': a.id,

            'asset_id': a.asset_id,

            'brand': a.brand,

            'model': a.model,

            'serial_number': a.serial_number,

            'processor': a.processor,

            'ram': a.ram,

            'ssd': a.ssd,

            'vendor_name': (
                a.vendor.name
                if a.vendor
                else '-'
            ),

            'status': a.status,

            'assignment_date': (
                a.assignment_date.strftime('%Y-%m-%d')
                if a.assignment_date
                else '-'
            )
        })

    # -----------------------------------------------------
    # Employee JSON
    # -----------------------------------------------------

    return jsonify({

        'id': emp.id,

        'employee_id': emp.employee_id,

        'name': emp.name,

        'email': emp.email,

        'department': (
            emp.department
            or '-'
        ),

        'designation': (
            emp.designation
            or '-'
        ),

        'manager': (
            emp.manager
            or '-'
        ),

        'office_location': (
            emp.office_location
            or '-'
        ),

        'account_status': (
            emp.account_status
            or AccountStatus.ACTIVE
        ),

        # -------------------------------------------------
        # ALL FIVE STATUS DATES
        # -------------------------------------------------

        'onboarded_date': date_to_string(
            emp.onboarded_date
        ),

        'active_date': date_to_string(
            emp.active_date
        ),

        'blocked_date': date_to_string(
            emp.blocked_date
        ),

        'disabled_date': date_to_string(
            emp.disabled_date
        ),

        'offboarded_date': date_to_string(
            emp.offboarded_date
        ),

        'assigned_assets': assets_data
    })


# =========================================================
# EDIT EMPLOYEE
# =========================================================

@employees_bp.route(
    '/<int:emp_id>/edit',
    methods=['POST']
)
@login_required
def edit_employee(emp_id):

    # -----------------------------------------------------
    # Permission
    # -----------------------------------------------------

    if not current_user.is_it_admin:

        return jsonify({
            "success": False,
            "message": "Permission denied"
        }), 403

    # -----------------------------------------------------
    # Employee
    # -----------------------------------------------------

    emp = Employee.query.get_or_404(emp_id)

    old_status = emp.account_status

    # -----------------------------------------------------
    # Basic Information
    # -----------------------------------------------------

    name = request.form.get(
        'name',
        emp.name
    ).strip()

    if not name:

        return jsonify({
            "success": False,
            "message": "Employee Name is required."
        }), 400

    emp.name = name

    emp.department = request.form.get(
        'department',
        emp.department or ''
    ).strip()

    emp.designation = request.form.get(
        'designation',
        emp.designation or ''
    ).strip()

    emp.manager = request.form.get(
        'manager',
        emp.manager or ''
    ).strip()

    emp.office_location = request.form.get(
        'office_location',
        emp.office_location or ''
    ).strip()

    # -----------------------------------------------------
    # Status
    # -----------------------------------------------------

    new_status = request.form.get(
        'account_status',
        emp.account_status
    ).strip()

    if new_status not in VALID_ACCOUNT_STATUSES:

        return jsonify({
            "success": False,
            "message": "Please select a valid employee account status."
        }), 400

    # -----------------------------------------------------
    # Status Dates From Form
    # -----------------------------------------------------

    date_values = {
        AccountStatus.ONBOARDED: request.form.get(
            'onboarded_date',
            ''
        ).strip(),

        AccountStatus.ACTIVE: request.form.get(
            'active_date',
            ''
        ).strip(),

        AccountStatus.BLOCKED: request.form.get(
            'blocked_date',
            ''
        ).strip(),

        AccountStatus.DISABLED: request.form.get(
            'disabled_date',
            ''
        ).strip(),

        AccountStatus.OFFBOARDED: request.form.get(
            'offboarded_date',
            ''
        ).strip()
    }

    # -----------------------------------------------------
    # Status Change
    # -----------------------------------------------------

    if old_status != new_status:

        selected_date_value = date_values.get(
            new_status
        )

        # If UI sends a date, use it.
        # Otherwise automatically use today's date.
        if selected_date_value:

            try:

                selected_date = parse_date(
                    selected_date_value,
                    f'{new_status} Date'
                )

            except ValueError as e:

                return jsonify({
                    "success": False,
                    "message": str(e)
                }), 400

        else:

            selected_date = datetime.utcnow().date()

        set_status_date(
            emp,
            new_status,
            selected_date
        )

        emp.account_status = new_status

    else:

        # -------------------------------------------------
        # Same status:
        # allow user to edit the selected status date
        # -------------------------------------------------

        selected_date_value = date_values.get(
            new_status
        )

        if selected_date_value:

            try:

                selected_date = parse_date(
                    selected_date_value,
                    f'{new_status} Date'
                )

                set_status_date(
                    emp,
                    new_status,
                    selected_date
                )

            except ValueError as e:

                return jsonify({
                    "success": False,
                    "message": str(e)
                }), 400

    # -----------------------------------------------------
    # Offboarded = Automatic Laptop Return
    # -----------------------------------------------------

    returned_assets = 0

    if (
        new_status == AccountStatus.OFFBOARDED
        and old_status != AccountStatus.OFFBOARDED
    ):

        assigned_laptops = (
            Asset.query
            .filter_by(
                assigned_employee_id=emp.id
            )
            .all()
        )

        for laptop in assigned_laptops:

            laptop.status = AssetStatus.AVAILABLE

            laptop.assigned_employee_id = None

            laptop.assignment_date = None

            returned_assets += 1

            history = AssetAssignmentHistory(
                asset_id=laptop.id,
                employee_id=emp.id,
                employee_name=emp.name,
                action='Returned (Employee Offboarded)',
                notes=(
                    f'Laptop automatically returned because '
                    f'{emp.name} ({emp.employee_id}) was offboarded.'
                ),
                performed_by=current_user.full_name
            )

            db.session.add(history)

    # -----------------------------------------------------
    # Save
    # -----------------------------------------------------

    try:

        db.session.commit()

    except Exception as e:

        db.session.rollback()

        return jsonify({
            "success": False,
            "message": f"Failed to update employee: {str(e)}"
        }), 500

    # -----------------------------------------------------
    # Audit
    # -----------------------------------------------------

    if old_status != new_status:

        status_field = status_date_field(
            new_status
        )

        status_date = getattr(
            emp,
            status_field,
            None
        )

        status_date_text = date_to_string(
            status_date
        ) or '-'

        try:

            AuditService.log(
                action='Employee Status Changed',
                entity_type='Employee',
                entity_id=emp.employee_id,
                details=(
                    f'Employee {emp.name} '
                    f'({emp.employee_id}) status changed '
                    f'from {old_status} to {new_status}. '
                    f'{new_status} Date: {status_date_text}. '
                    f'Laptops Returned: {returned_assets}.'
                )
            )

        except Exception:

            pass

    # -----------------------------------------------------
    # Response
    # -----------------------------------------------------

    return jsonify({

        "success": True,

        "message": (
            "Employee updated successfully"
            + (
                f". {returned_assets} laptop(s) automatically returned."
                if returned_assets
                else ""
            )
        ),

        "account_status": emp.account_status,

        "onboarded_date": date_to_string(
            emp.onboarded_date
        ),

        "active_date": date_to_string(
            emp.active_date
        ),

        "blocked_date": date_to_string(
            emp.blocked_date
        ),

        "disabled_date": date_to_string(
            emp.disabled_date
        ),

        "offboarded_date": date_to_string(
            emp.offboarded_date
        ),

        "returned_assets": returned_assets
    })
