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
# STATUS HELPERS
# =========================================================

VALID_ACCOUNT_STATUSES = [
    AccountStatus.ONBOARDED,
    AccountStatus.ACTIVE,
    AccountStatus.BLOCKED,
    AccountStatus.OFFBOARDED
]


def status_date_field(status):
    """
    Return the Employee model date field for a given status.
    """

    mapping = {
        AccountStatus.ONBOARDED: 'onboarded_date',
        AccountStatus.ACTIVE: 'active_date',
        AccountStatus.BLOCKED: 'blocked_date',
        AccountStatus.OFFBOARDED: 'offboarded_date'
    }

    return mapping.get(status)


def parse_date(value):
    """
    Convert YYYY-MM-DD string to date.
    Returns None when empty.
    """

    if not value:
        return None

    try:
        return datetime.strptime(
            value,
            '%Y-%m-%d'
        ).date()

    except ValueError:
        return None


def date_to_string(value):
    """
    Convert date to YYYY-MM-DD.
    """

    if not value:
        return None

    return value.strftime('%Y-%m-%d')


def set_status_date(emp, status, date_value=None):
    """
    Set the date belonging to the employee's current status.

    If no date is supplied, today's date is used.
    """

    field = status_date_field(status)

    if not field:
        return

    parsed_date = parse_date(date_value)

    if parsed_date:
        setattr(emp, field, parsed_date)

    elif not getattr(emp, field):
        setattr(
            emp,
            field,
            datetime.utcnow().date()
        )


# =========================================================
# EMPLOYEE AUTOCOMPLETE
# =========================================================

@employees_bp.route('/autocomplete')
@login_required
def employee_autocomplete():

    query = request.args.get(
        'q',
        ''
    ).strip()

    if not query:
        return jsonify([])

    employees = (
        Employee.query
        .filter(
            (Employee.name.ilike(f'%{query}%')) |
            (Employee.employee_id.ilike(f'%{query}%')) |
            (Employee.email.ilike(f'%{query}%'))
        )
        .order_by(
            Employee.name.asc()
        )
        .limit(10)
        .all()
    )

    return jsonify([
        {
            'id': emp.id,
            'employee_id': emp.employee_id,
            'name': emp.name,
            'email': emp.email,
            'department': emp.department
        }
        for emp in employees
    ])


# =========================================================
# EMPLOYEE ID GENERATOR
# =========================================================

def generate_employee_id():

    count = Employee.query.count() + 1001

    return f"EMP-{count}"


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
    # Supports:
    #
    # ?status=Active
    #
    # and:
    #
    # ?status=Active,Onboarded
    # -----------------------------------------------------

    if status_filter:
        statuses = [
            status.strip()
            for status in status_filter.split(',')
            if status.strip()
        ]

        if len(statuses) == 1:
            query = query.filter(
                Employee.account_status == statuses[0]
            )
        elif statuses:
            query = query.filter(
                Employee.account_status.in_(statuses)
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

    # -----------------------------------------------------
    # Available Assets
    # -----------------------------------------------------

    available_assets = (
        Asset.query
        .filter_by(
            status=AssetStatus.AVAILABLE
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
        account_statuses=VALID_ACCOUNT_STATUSES
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

    # Status is controlled by Microsoft Entra ID.
    status = AccountStatus.ONBOARDED

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
    # Uniqueness Check
    # -----------------------------------------------------

    existing = Employee.query.filter(
        (Employee.email == email) |
        (
            Employee.employee_id == emp_code
            if emp_code
            else False
        )
    ).first()

    if existing:

        flash(
            f'An employee with email "{email}" or ID '
            f'"{emp_code}" already exists in the system.',
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
        created_at=datetime.utcnow()
    )

    # -----------------------------------------------------
    # Set Initial Status Date
    # -----------------------------------------------------

    set_status_date(
        new_emp,
        status
    )

    db.session.add(new_emp)

    db.session.flush()

    # -----------------------------------------------------
    # Laptop Allocation
    # -----------------------------------------------------

    assigned_asset_msg = ""

    if asset_id:

        asset = Asset.query.get(asset_id)

        if asset and asset.status == AssetStatus.AVAILABLE:

            asset.status = AssetStatus.ASSIGNED

            asset.assigned_employee_id = new_emp.id

            asset.assignment_date = datetime.utcnow()

            # -------------------------------------------------
            # Assignment History
            # -------------------------------------------------

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

    # -----------------------------------------------------
    # Save
    # -----------------------------------------------------

    db.session.commit()

    # -----------------------------------------------------
    # Audit
    # -----------------------------------------------------

    AuditService.log(
        action='Employee Onboarded',
        entity_type='Employee',
        entity_id=new_emp.employee_id,
        details=(
            f'Onboarded new employee {new_emp.name} '
            f'({new_emp.department} - '
            f'{new_emp.account_status}).'
            f'{assigned_asset_msg}'
        )
    )

    # -----------------------------------------------------
    # Success Message
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

    res = MicrosoftGraphService.sync_entra_employees()

    flash(
        f"Entra ID Sync Complete! "
        f"Synced {res['total']} employees. "
        f"(Auto-Onboarded: {res.get('onboarded', 0)}, "
        f"Updated: {res.get('updated', 0)}, "
        f"Auto-Offboarded: {res.get('offboarded', 0)}, "
        f"Laptops Returned: {res.get('returned_assets', 0)})",
        'success'
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

    assigned_assets = (
        Asset.query
        .filter_by(
            assigned_employee_id=emp.id
        )
        .all()
    )

    assets_data = []

    for asset in assigned_assets:

        assets_data.append({
            'id': asset.id,
            'asset_id': asset.asset_id,
            'brand': asset.brand,
            'model': asset.model,
            'serial_number': asset.serial_number,
            'processor': asset.processor,
            'ram': asset.ram,
            'ssd': asset.ssd,
            'vendor_name': (
                asset.vendor.name
                if asset.vendor
                else '-'
            ),
            'status': asset.status,
            'assignment_date': (
                asset.assignment_date.strftime('%Y-%m-%d')
                if asset.assignment_date
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

        'department': emp.department or '-',

        'designation': emp.designation or '-',

        'manager': emp.manager or '-',

        'office_location': emp.office_location or '-',

        'account_status': emp.account_status,

        # -------------------------------------------------
        # ALL STATUS DATES
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


        'offboarded_date': date_to_string(
            emp.offboarded_date
        ),

        # -------------------------------------------------
        # Assets
        # -------------------------------------------------

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
    # Permission Check
    # -----------------------------------------------------

    if not current_user.is_it_admin:

        return jsonify({
            "success": False,
            "message": "Permission denied"
        }), 403

    # -----------------------------------------------------
    # Get Employee
    # -----------------------------------------------------

    emp = Employee.query.get_or_404(emp_id)

    returned_assets = []

    # -----------------------------------------------------
    # Basic Information
    # -----------------------------------------------------

    emp.name = request.form.get(
        "name",
        emp.name
    ).strip()

    emp.department = request.form.get(
        "department",
        emp.department
    ).strip()

    emp.designation = request.form.get(
        "designation",
        emp.designation
    ).strip()

    emp.manager = request.form.get(
        "manager",
        emp.manager
    ).strip()

    emp.office_location = request.form.get(
        "office_location",
        emp.office_location
    ).strip()

    # -----------------------------------------------------
    # STATUS / STATUS DATES
    # -----------------------------------------------------
    # Status and status dates are read-only in ITAM and are
    # controlled exclusively by Microsoft Entra ID sync.
    # -----------------------------------------------------

    # Status changes and offboarding actions are handled by Entra sync.

    # -----------------------------------------------------
    # Save Changes
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
    # Response
    # -----------------------------------------------------

    return jsonify({

        "success": True,

        "message": (
            "Employee updated successfully"
            + (
                f". Returned {len(returned_assets)} laptop(s)."
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


        "offboarded_date": date_to_string(
            emp.offboarded_date
        ),

        "returned_assets": returned_assets
    })
