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

# IMPORTANT: Employee and AccountStatus belong here
from app.models.employee import Employee, AccountStatus

from app.models.asset import (
    Asset,
    AssetStatus,
    AssetAssignmentHistory
)

# IMPORTANT: Graph service is used by the route, NOT by employee.py
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
# EMPLOYEE INDEX
# =========================================================

@employees_bp.route('/')
@login_required
def index():

    search_q = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    dept_filter = request.args.get('department', '').strip()

    page = request.args.get(
        'page',
        1,
        type=int
    )

    query = Employee.query

    # -----------------------------------------------------
    # SEARCH
    # -----------------------------------------------------

    if search_q:
        query = query.filter(
            (Employee.name.ilike(f'%{search_q}%')) |
            (Employee.employee_id.ilike(f'%{search_q}%')) |
            (Employee.email.ilike(f'%{search_q}%')) |
            (Employee.designation.ilike(f'%{search_q}%'))
        )

    # -----------------------------------------------------
    # STATUS FILTER
    # -----------------------------------------------------

    if status_filter in VALID_ACCOUNT_STATUSES:
        query = query.filter(
            Employee.account_status == status_filter
        )

    # -----------------------------------------------------
    # DEPARTMENT FILTER
    # -----------------------------------------------------

    if dept_filter:
        query = query.filter(
            Employee.department == dept_filter
        )

    # -----------------------------------------------------
    # PAGINATION
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
    # DEPARTMENTS
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
    # AVAILABLE ASSETS
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
    # RENDER
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

    if not current_user.is_it_admin:

        flash(
            'Permission denied. Only IT Admins can onboard new employees.',
            'danger'
        )

        return redirect(
            url_for('employees.index')
        )

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
    # REQUIRED FIELDS
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
    # STATUS VALIDATION
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
    # EMAIL CHECK
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

    # -----------------------------------------------------
    # EMPLOYEE ID CHECK
    # -----------------------------------------------------

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
    # GENERATE EMPLOYEE ID
    # -----------------------------------------------------

    if not emp_code:
        emp_code = generate_employee_id()

    # -----------------------------------------------------
    # STATUS DATES
    # -----------------------------------------------------

    disabled_date = None
    offboarded_date = None

    today = datetime.utcnow().date()

    if status == AccountStatus.DISABLED:
        disabled_date = today

    elif status == AccountStatus.OFFBOARDED:
        offboarded_date = today

    # -----------------------------------------------------
    # CREATE EMPLOYEE
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
        disabled_date=disabled_date,
        offboarded_date=offboarded_date,
        created_at=datetime.utcnow()
    )

    db.session.add(new_emp)

    try:

        db.session.flush()

        assigned_asset_msg = ""

        # -------------------------------------------------
        # LAPTOP ALLOCATION
        # -------------------------------------------------

        if asset_id:

            asset = Asset.query.get(asset_id)

            if not asset:

                db.session.rollback()

                flash(
                    'Selected laptop was not found.',
                    'danger'
                )

                return redirect(
                    url_for('employees.index')
                )

            if asset.status != AssetStatus.AVAILABLE:

                db.session.rollback()

                flash(
                    'Selected laptop is no longer available.',
                    'danger'
                )

                return redirect(
                    url_for('employees.index')
                )

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
    # AUDIT
    # -----------------------------------------------------

    try:

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

    except Exception:
        pass

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
            f"Synced {res.get('total', 0)} employees. "
            f"(Auto-Onboarded: {res.get('onboarded', 0)}, "
            f"Updated: {res.get('updated', 0)}, "
            f"Auto-Offboarded: {res.get('offboarded', 0)}, "
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

    return jsonify({

        'id': emp.id,

        'employee_id': emp.employee_id,

        'name': emp.name,

        'email': emp.email,

        'department': emp.department or '-',

        'designation': emp.designation or '-',

        'manager': emp.manager or '-',

        'office_location': emp.office_location or '-',

        'account_status': (
            emp.account_status
            or AccountStatus.ACTIVE
        ),

        'disabled_date': (
            emp.disabled_date.strftime('%Y-%m-%d')
            if emp.disabled_date
            else None
        ),

        'offboarded_date': (
            emp.offboarded_date.strftime('%Y-%m-%d')
            if emp.offboarded_date
            else None
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

    if not current_user.is_it_admin:

        return jsonify({
            "success": False,
            "message": "Permission denied"
        }), 403

    emp = Employee.query.get_or_404(emp_id)

    old_status = emp.account_status

    # -----------------------------------------------------
    # BASIC INFORMATION
    # -----------------------------------------------------

    name = request.form.get(
        'name',
        ''
    ).strip()

    if not name:

        return jsonify({
            "success": False,
            "message": "Employee Name is required."
        }), 400

    emp.name = name

    emp.department = request.form.get(
        'department',
        ''
    ).strip()

    emp.designation = request.form.get(
        'designation',
        ''
    ).strip()

    emp.manager = request.form.get(
        'manager',
        ''
    ).strip()

    emp.office_location = request.form.get(
        'office_location',
        ''
    ).strip()

    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------

    new_status = request.form.get(
        'account_status',
        ''
    ).strip()

    if new_status not in VALID_ACCOUNT_STATUSES:

        return jsonify({
            "success": False,
            "message": "Please select a valid employee account status."
        }), 400

    # -----------------------------------------------------
    # DATES
    # -----------------------------------------------------

    disabled_date_value = request.form.get(
        'disabled_date',
        ''
    ).strip()

    offboarded_date_value = request.form.get(
        'offboarded_date',
        ''
    ).strip()

    # -----------------------------------------------------
    # ONBOARDED
    # -----------------------------------------------------

    if new_status == AccountStatus.ONBOARDED:

        emp.account_status = AccountStatus.ONBOARDED
        emp.disabled_date = None
        emp.offboarded_date = None

    # -----------------------------------------------------
    # ACTIVE
    # -----------------------------------------------------

    elif new_status == AccountStatus.ACTIVE:

        emp.account_status = AccountStatus.ACTIVE
        emp.disabled_date = None
        emp.offboarded_date = None

    # -----------------------------------------------------
    # BLOCKED
    # -----------------------------------------------------

    elif new_status == AccountStatus.BLOCKED:

        emp.account_status = AccountStatus.BLOCKED
        emp.disabled_date = None
        emp.offboarded_date = None

    # -----------------------------------------------------
    # DISABLED
    # -----------------------------------------------------

    elif new_status == AccountStatus.DISABLED:

        if not disabled_date_value:

            return jsonify({
                "success": False,
                "message": "Please select the Disabled Date."
            }), 400

        try:

            emp.disabled_date = datetime.strptime(
                disabled_date_value,
                '%Y-%m-%d'
            ).date()

        except ValueError:

            return jsonify({
                "success": False,
                "message": "Invalid Disabled Date."
            }), 400

        emp.account_status = AccountStatus.DISABLED
        emp.offboarded_date = None

    # -----------------------------------------------------
    # OFFBOARDED
    # -----------------------------------------------------

    elif new_status == AccountStatus.OFFBOARDED:

        if not offboarded_date_value:

            return jsonify({
                "success": False,
                "message": "Please select the Offboarded Date."
            }), 400

        try:

            emp.offboarded_date = datetime.strptime(
                offboarded_date_value,
                '%Y-%m-%d'
            ).date()

        except ValueError:

            return jsonify({
                "success": False,
                "message": "Invalid Offboarded Date."
            }), 400

        emp.account_status = AccountStatus.OFFBOARDED
        emp.disabled_date = None

    # -----------------------------------------------------
    # COMMIT
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
    # AUDIT
    # -----------------------------------------------------

    if old_status != new_status:

        disabled_date_text = (
            emp.disabled_date.strftime('%Y-%m-%d')
            if emp.disabled_date
            else '-'
        )

        offboarded_date_text = (
            emp.offboarded_date.strftime('%Y-%m-%d')
            if emp.offboarded_date
            else '-'
        )

        try:

            AuditService.log(
                action='Employee Status Changed',
                entity_type='Employee',
                entity_id=emp.employee_id,
                details=(
                    f'Employee {emp.name} '
                    f'({emp.employee_id}) status changed '
                    f'from {old_status} to {new_status}. '
                    f'Disabled Date: {disabled_date_text}, '
                    f'Offboarded Date: {offboarded_date_text}'
                )
            )

        except Exception:
            pass

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return jsonify({

        "success": True,

        "message": "Employee updated successfully",

        "account_status": emp.account_status,

        "disabled_date": (
            emp.disabled_date.strftime('%Y-%m-%d')
            if emp.disabled_date
            else None
        ),

        "offboarded_date": (
            emp.offboarded_date.strftime('%Y-%m-%d')
            if emp.offboarded_date
            else None
        )

    })
