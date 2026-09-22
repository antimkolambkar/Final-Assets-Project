from datetime import datetime
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models.asset import Asset, AssetStatus, AssetAssignmentHistory
from app.models.employee import Employee, AccountStatus
from app.models.vendor import Vendor, VendorRepairTicket, RepairStatus
from app.services.audit_service import AuditService


assets_bp = Blueprint('assets', __name__, url_prefix='/assets')


# =========================================================
# ALLOWED VENDORS FOR VENDOR RETURN
# =========================================================

ALLOWED_VENDOR_RETURN_NAMES = {
    'Techvity',
    'Spurge',
    'WBG',
    'Exalogic Bangalore',
    'Exalogic Dubai',
}


def normalize_vendor_name(name):
    """Normalize a vendor name for case-insensitive comparison."""
    return ' '.join((name or '').strip().casefold().split())


ALLOWED_VENDOR_RETURN_NAMES_NORMALIZED = {
    normalize_vendor_name(name)
    for name in ALLOWED_VENDOR_RETURN_NAMES
}


# =========================================================
# DATE HELPER
# =========================================================

def parse_event_date(date_string, field_name='date'):
    """
    Convert HTML <input type="date"> value into datetime.

    Expected format:
        YYYY-MM-DD

    Returns:
        datetime object or None
    """
    date_string = (date_string or '').strip()

    if not date_string:
        return None

    try:
        return datetime.strptime(date_string, '%Y-%m-%d')
    except ValueError:
        return None


# =========================================================
# ID GENERATORS
# =========================================================

def generate_asset_id():
    year = datetime.utcnow().strftime('%Y')
    count = Asset.query.count() + 1
    return f"AST-{year}-{count:04d}"


def generate_asset_id():
    year = datetime.utcnow().strftime('%Y')
    prefix = f"AST-{year}-"

    # Find the highest existing Asset ID for this year
    existing_ids = (
        Asset.query
        .filter(Asset.asset_id.like(f"{prefix}%"))
        .with_entities(Asset.asset_id)
        .all()
    )

    max_number = 0

    for (asset_id,) in existing_ids:
        if not asset_id:
            continue

        try:
            number = int(asset_id.replace(prefix, ""))
            if number > max_number:
                max_number = number
        except ValueError:
            continue

    # Generate the next available Asset ID
    next_number = max_number + 1

    # Safety check to prevent duplicate Asset IDs
    while Asset.query.filter_by(
        asset_id=f"{prefix}{next_number:04d}"
    ).first():
        next_number += 1

    return f"{prefix}{next_number:04d}"

def generate_vendor_ticket_num():
    """Generate a unique vendor repair ticket number."""
    year = datetime.utcnow().strftime('%Y')
    prefix = f"VNR-{year}-"

    existing_tickets = (
        VendorRepairTicket.query
        .filter(
            VendorRepairTicket.vendor_ticket_number.like(f"{prefix}%")
        )
        .with_entities(VendorRepairTicket.vendor_ticket_number)
        .all()
    )

    max_number = 0

    for (ticket_number,) in existing_tickets:
        if not ticket_number:
            continue

        try:
            number = int(ticket_number.replace(prefix, ""))
            if number > max_number:
                max_number = number
        except ValueError:
            continue

    next_number = max_number + 1

    # Safety check against duplicate ticket numbers
    while VendorRepairTicket.query.filter_by(
        vendor_ticket_number=f"{prefix}{next_number:04d}"
    ).first():
        next_number += 1

    return f"{prefix}{next_number:04d}"



# =========================================================
# ASSET INVENTORY
# =========================================================

@assets_bp.route('/')
@login_required
def index():

    search_q = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    vendor_filter = request.args.get('vendor_id', type=int)
    page = request.args.get('page', 1, type=int)

    query = Asset.query

    if search_q:
        query = query.join(
            Employee,
            Asset.assigned_employee_id == Employee.id,
            isouter=True
        ).filter(
            (Asset.asset_id.ilike(f'%{search_q}%')) |
            (Asset.brand.ilike(f'%{search_q}%')) |
            (Asset.model.ilike(f'%{search_q}%')) |
            (Asset.serial_number.ilike(f'%{search_q}%')) |
            (Employee.name.ilike(f'%{search_q}%'))
        )

    if status_filter:
        query = query.filter(
            Asset.status == status_filter
        )

    if vendor_filter:
        query = query.filter(
            Asset.vendor_id == vendor_filter
        )

    pagination = query.order_by(
        Asset.id.desc()
    ).paginate(
        page=page,
        per_page=10,
        error_out=False
    )

    assets = pagination.items

    # =====================================================
    # REPAIR DATES
    # =====================================================

    repair_start_dates = {}
    repair_completion_dates = {}

    # Values used by assets/index.html
    available_dates = {}
    available_returned_by = {}
    repair_descriptions = {}

    for asset in assets:

        # Latest repair start date
        repair_start_history = AssetAssignmentHistory.query.filter_by(
            asset_id=asset.id,
            action='Sent to Repair'
        ).order_by(
            AssetAssignmentHistory.event_date.desc(),
            AssetAssignmentHistory.timestamp.desc()
        ).first()

        if repair_start_history and repair_start_history.event_date:
            repair_start_dates[asset.id] = repair_start_history.event_date

        # Latest repair completion date
        repair_completion_history = AssetAssignmentHistory.query.filter_by(
            asset_id=asset.id,
            action='Repair Completed'
        ).order_by(
            AssetAssignmentHistory.event_date.desc(),
            AssetAssignmentHistory.timestamp.desc()
        ).first()

        if repair_completion_history and repair_completion_history.event_date:
            repair_completion_dates[asset.id] = repair_completion_history.event_date

        # Latest event that made the asset Available.
        available_history = AssetAssignmentHistory.query.filter(
            AssetAssignmentHistory.asset_id == asset.id,
            AssetAssignmentHistory.action.in_([
                'Stock',
                'Returned',
                'Repair Completed'
            ])
        ).order_by(
            AssetAssignmentHistory.event_date.desc(),
            AssetAssignmentHistory.timestamp.desc()
        ).first()

        if available_history and available_history.event_date:
            available_dates[asset.id] = available_history.event_date

        # Employee who most recently returned the asset.
        returned_history = AssetAssignmentHistory.query.filter_by(
            asset_id=asset.id,
            action='Returned'
        ).order_by(
            AssetAssignmentHistory.event_date.desc(),
            AssetAssignmentHistory.timestamp.desc()
        ).first()

        if returned_history and returned_history.employee_name:
            available_returned_by[asset.id] = returned_history.employee_name

        # Latest repair description/notes.
        repair_history = AssetAssignmentHistory.query.filter_by(
            asset_id=asset.id,
            action='Sent to Repair'
        ).order_by(
            AssetAssignmentHistory.event_date.desc(),
            AssetAssignmentHistory.timestamp.desc()
        ).first()

        if repair_history and repair_history.notes:
            repair_descriptions[asset.id] = repair_history.notes

    vendors = Vendor.query.order_by(
        Vendor.name.asc()
    ).all()

    active_employees = Employee.query.filter(
        Employee.account_status != AccountStatus.OFFBOARDED
    ).order_by(
        Employee.name.asc()
    ).all()

    available_assets = Asset.query.filter_by(
        status=AssetStatus.AVAILABLE
    ).order_by(
        Asset.brand.asc()
    ).all()

    assigned_assets = Asset.query.filter_by(
        status=AssetStatus.ASSIGNED
    ).order_by(
        Asset.asset_id.asc()
    ).all()

    return render_template(
        'assets/index.html',
        assets=assets,
        pagination=pagination,
        search_q=search_q,
        status_filter=status_filter,
        vendor_filter=vendor_filter,
        vendors=vendors,
        active_employees=active_employees,
        available_assets=available_assets,
        assigned_assets=assigned_assets,
        repair_start_dates=repair_start_dates,
        repair_completion_dates=repair_completion_dates,
        available_dates=available_dates,
        available_returned_by=available_returned_by,
        repair_descriptions=repair_descriptions
    )


# =========================================================
# LIVE ASSET AUTOCOMPLETE
# =========================================================

@assets_bp.route('/autocomplete')
@login_required
def asset_autocomplete():
    """Live asset search for autocomplete dropdown."""

    search_q = request.args.get('q', '').strip()

    # Start searching after 2 characters
    if len(search_q) < 2:
        return jsonify([])

    search_pattern = f'%{search_q}%'

    assets = Asset.query.outerjoin(
        Employee,
        Asset.assigned_employee_id == Employee.id
    ).filter(
        (Asset.asset_id.ilike(search_pattern)) |
        (Asset.brand.ilike(search_pattern)) |
        (Asset.model.ilike(search_pattern)) |
        (Asset.serial_number.ilike(search_pattern)) |
        (Employee.name.ilike(search_pattern)) |
        (Employee.employee_id.ilike(search_pattern))
    ).order_by(
        Asset.asset_id.asc()
    ).limit(10).all()

    results = []

    for asset in assets:

        status_value = (
            asset.status.value
            if hasattr(asset.status, 'value')
            else str(asset.status)
        )

        assigned_user = ''

        if asset.assigned_employee:
            assigned_user = asset.assigned_employee.name

        results.append({
            'id': asset.id,
            'asset_id': asset.asset_id,
            'brand': asset.brand or '',
            'model': asset.model or '',
            'serial_number': asset.serial_number or '',
            'status': status_value,
            'assigned_user': assigned_user
        })

    return jsonify(results)


# =========================================================
# ADD ASSET
# =========================================================

@assets_bp.route('/add', methods=['POST'])
@login_required
def add_asset():

    if not current_user.is_it_admin:
        flash(
            'Permission denied. Only IT Admins can add assets.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    brand = request.form.get('brand', '').strip()
    model = request.form.get('model', '').strip()
    serial_number = request.form.get('serial_number', '').strip()
    processor = request.form.get('processor', '').strip()
    ram = request.form.get('ram', '').strip()
    ssd = request.form.get('ssd', '').strip()
    vendor_id = request.form.get('vendor_id', type=int)

    # Stock / received date
    stock_date_str = request.form.get(
        'stock_date',
        ''
    ).strip()

    stock_date = parse_event_date(stock_date_str)

    if not all([
        brand,
        model,
        serial_number,
        processor,
        ram,
        ssd,
        vendor_id
    ]):
        flash(
            'All asset specification fields are required.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    if not stock_date_str:
        flash(
            'Please select the stock/received date.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    if not stock_date:
        flash(
            'Invalid stock/received date.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    # Check serial number uniqueness
    existing = Asset.query.filter_by(
        serial_number=serial_number
    ).first()

    if existing:
        flash(
            f'Asset with Serial Number "{serial_number}" already exists.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    asset_id = generate_asset_id()

    new_asset = Asset(
        asset_id=asset_id,
        brand=brand,
        model=model,
        serial_number=serial_number,
        processor=processor,
        ram=ram,
        ssd=ssd,
        vendor_id=vendor_id,
        status=AssetStatus.AVAILABLE
    )

    db.session.add(new_asset)
    db.session.flush()

    # -----------------------------------------------------
    # STOCK HISTORY
    # -----------------------------------------------------

    hist = AssetAssignmentHistory(
        asset_id=new_asset.id,
        action='Stock',
        event_date=stock_date,
        notes=(
            f'Asset received and added to stock '
            f'on {stock_date_str}.'
        ),
        performed_by=current_user.full_name
    )

    db.session.add(hist)

    db.session.commit()

    AuditService.log(
        action='Asset Created',
        entity_type='Asset',
        entity_id=new_asset.asset_id,
        details=(
            f'Added new asset {new_asset.brand} '
            f'{new_asset.model} '
            f'(SN: {new_asset.serial_number}) '
            f'to stock on {stock_date_str}'
        )
    )

    flash(
        f'Asset {new_asset.asset_id} added successfully!',
        'success'
    )

    return redirect(url_for('assets.index'))


# =========================================================
# EDIT ASSET
# =========================================================

@assets_bp.route('/edit/<int:asset_id>', methods=['POST'])
@login_required
def edit_asset(asset_id):

    if not current_user.is_it_admin:
        flash(
            'Permission denied. Only IT Admins can edit assets.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    asset = Asset.query.get_or_404(asset_id)

    asset.brand = request.form.get(
        'brand',
        asset.brand
    ).strip()

    asset.model = request.form.get(
        'model',
        asset.model
    ).strip()

    asset.serial_number = request.form.get(
        'serial_number',
        asset.serial_number
    ).strip()

    asset.processor = request.form.get(
        'processor',
        asset.processor
    ).strip()

    asset.ram = request.form.get(
        'ram',
        asset.ram
    ).strip()

    asset.ssd = request.form.get(
        'ssd',
        asset.ssd
    ).strip()

    asset.vendor_id = request.form.get(
        'vendor_id',
        asset.vendor_id,
        type=int
    )

    db.session.commit()

    AuditService.log(
        action='Asset Updated',
        entity_type='Asset',
        entity_id=asset.asset_id,
        details=(
            f'Updated specifications for asset '
            f'{asset.asset_id}'
        )
    )

    flash(
        f'Asset {asset.asset_id} updated successfully!',
        'success'
    )

    return redirect(url_for('assets.index'))


# =========================================================
# MARK AS NON-REPAIRABLE
# =========================================================

@assets_bp.route('/mark-non-repairable/<int:asset_id>', methods=['POST'])
@login_required
def mark_non_repairable(asset_id):
    """Move an asset to Non-Repairable status."""

    if not current_user.is_it_admin:
        flash(
            'Permission denied. Only IT Admins can mark assets '
            'as non-repairable.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    asset = Asset.query.get_or_404(asset_id)

    if asset.status == AssetStatus.ASSIGNED:
        flash(
            f'Cannot mark assigned asset {asset.asset_id} '
            'as non-repairable. Return it first.',
            'warning'
        )
        return redirect(url_for('assets.index'))

    if asset.status == 'Non-Repairable':
        flash(
            f'Asset {asset.asset_id} is already marked '
            'as non-repairable.',
            'warning'
        )
        return redirect(url_for('assets.index'))

    if asset.status == 'Donated Assets':
        flash(
            f'Asset {asset.asset_id} has already been sent to charity.',
            'warning'
        )
        return redirect(url_for('assets.index'))

    previous_status = str(asset.status)

    asset.status = 'Non-Repairable'
    asset.assigned_employee_id = None
    asset.assignment_date = None

    history = AssetAssignmentHistory(
        asset_id=asset.id,
        action='Marked Non-Repairable',
        event_date=datetime.utcnow(),
        notes=(
            f'Asset marked as Non-Repairable from '
            f'{previous_status} status.'
        ),
        performed_by=current_user.full_name
    )

    db.session.add(history)
    db.session.commit()

    AuditService.log(
        action='Asset Marked Non-Repairable',
        entity_type='Asset',
        entity_id=asset.asset_id,
        details=(
            f'Asset {asset.asset_id} marked as Non-Repairable '
            f'by {current_user.full_name}.'
        )
    )

    flash(
        f'Asset {asset.asset_id} marked as Non-Repairable.',
        'success'
    )
    return redirect(url_for('assets.index'))


# =========================================================
# SEND TO CHARITY
# =========================================================

@assets_bp.route('/send-to-charity/<int:asset_id>', methods=['POST'])
@login_required
def send_to_charity(asset_id):
    """Move an asset to Donated Assets status."""

    if not current_user.is_it_admin:
        flash(
            'Permission denied. Only IT Admins can send assets '
            'to charity.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    asset = Asset.query.get_or_404(asset_id)

    if asset.status == AssetStatus.ASSIGNED:
        flash(
            f'Cannot send assigned asset {asset.asset_id} '
            'to charity. Return it first.',
            'warning'
        )
        return redirect(url_for('assets.index'))

    if asset.status == 'Donated Assets':
        flash(
            f'Asset {asset.asset_id} has already been sent to charity.',
            'warning'
        )
        return redirect(url_for('assets.index'))

    previous_status = str(asset.status)

    asset.status = 'Donated Assets'
    asset.assigned_employee_id = None
    asset.assignment_date = None

    history = AssetAssignmentHistory(
        asset_id=asset.id,
        action='Sent to Charity',
        event_date=datetime.utcnow(),
        notes=(
            f'Asset sent to charity from '
            f'{previous_status} status.'
        ),
        performed_by=current_user.full_name
    )

    db.session.add(history)
    db.session.commit()

    AuditService.log(
        action='Asset Sent to Charity',
        entity_type='Asset',
        entity_id=asset.asset_id,
        details=(
            f'Asset {asset.asset_id} sent to charity '
            f'by {current_user.full_name}.'
        )
    )

    flash(
        f'Asset {asset.asset_id} sent to Charity.',
        'success'
    )
    return redirect(url_for('assets.index'))


# =========================================================
# DELETE ASSET
# =========================================================

@assets_bp.route('/delete/<int:asset_id>', methods=['POST'])
@login_required
def delete_asset(asset_id):

    if not current_user.can_delete_assets():
        flash(
            'Permission denied. IT Engineers cannot delete assets.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    asset = Asset.query.get_or_404(asset_id)

    if asset.status == AssetStatus.ASSIGNED:
        flash(
            f'Cannot delete asset {asset.asset_id} while it is '
            'assigned to an employee. Return it first.',
            'warning'
        )
        return redirect(url_for('assets.index'))

    aid = asset.asset_id

    db.session.delete(asset)
    db.session.commit()

    AuditService.log(
        action='Asset Deleted',
        entity_type='Asset',
        entity_id=aid,
        details=f'Deleted asset {aid}'
    )

    flash(
        f'Asset {aid} deleted.',
        'success'
    )

    return redirect(url_for('assets.index'))


# =========================================================
# ASSIGN ASSET
# =========================================================

@assets_bp.route('/assign', methods=['POST'])
@login_required
def assign_asset():

    if not current_user.is_it_admin:
        flash(
            'Permission denied. Only IT Admins can assign assets.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    asset_id = request.form.get(
        'asset_id',
        type=int
    )

    employee_id = request.form.get(
        'employee_id',
        type=int
    )

    notes = request.form.get(
        'notes',
        ''
    ).strip()

    assignment_date_str = request.form.get(
        'assignment_date',
        ''
    ).strip()

    assignment_date = parse_event_date(
        assignment_date_str
    )

    if not assignment_date_str:
        flash(
            'Please select the assignment date.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    if not assignment_date:
        flash(
            'Invalid assignment date.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    asset = Asset.query.get_or_404(asset_id)
    employee = Employee.query.get_or_404(employee_id)

    if asset.status != AssetStatus.AVAILABLE:
        flash(
            f'Asset {asset.asset_id} is currently '
            f'{asset.status} and cannot be assigned.',
            'warning'
        )
        return redirect(url_for('assets.index'))

    if employee.account_status == AccountStatus.OFFBOARDED:
        flash(
            f'Cannot assign asset to offboarded employee '
            f'{employee.name}.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    # -----------------------------------------------------
    # UPDATE ASSET
    # -----------------------------------------------------

    asset.status = AssetStatus.ASSIGNED
    asset.assigned_employee_id = employee.id
    asset.assignment_date = assignment_date

    # -----------------------------------------------------
    # HISTORY
    # -----------------------------------------------------

    hist = AssetAssignmentHistory(
        asset_id=asset.id,
        employee_id=employee.id,
        employee_name=employee.name,
        action='Assigned',
        event_date=assignment_date,
        notes=notes or (
            f'Assigned to {employee.name} '
            f'({employee.employee_id})'
        ),
        performed_by=current_user.full_name
    )

    db.session.add(hist)
    db.session.commit()

    AuditService.log(
        action='Asset Assigned',
        entity_type='Asset',
        entity_id=asset.asset_id,
        details=(
            f'Assigned {asset.asset_id} '
            f'({asset.brand} {asset.model}) '
            f'to employee {employee.name} '
            f'({employee.employee_id}) '
            f'on {assignment_date_str}'
        )
    )

    flash(
        f'Asset {asset.asset_id} assigned to '
        f'{employee.name} on {assignment_date_str}!',
        'success'
    )

    return redirect(url_for('assets.index'))


# =========================================================
# RETURN ASSET FROM EMPLOYEE
# =========================================================

@assets_bp.route('/return/<int:asset_id>', methods=['POST'])
@login_required
def return_asset(asset_id):

    if not current_user.is_it_admin:
        flash(
            'Permission denied. Only IT Admins can return assets.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    asset = Asset.query.get_or_404(asset_id)

    if asset.status != AssetStatus.ASSIGNED or not asset.assigned_employee:
        flash(
            f'Asset {asset.asset_id} is not currently assigned.',
            'warning'
        )
        return redirect(url_for('assets.index'))

    return_date_str = request.form.get(
        'return_date',
        ''
    ).strip()

    notes = request.form.get(
        'notes',
        ''
    ).strip()

    return_date = parse_event_date(
        return_date_str
    )

    if not return_date_str:
        flash(
            'Please select the return date.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    if not return_date:
        flash(
            'Invalid return date.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    emp_name = asset.assigned_employee.name
    emp_id = asset.assigned_employee.id

    # -----------------------------------------------------
    # UPDATE ASSET
    # -----------------------------------------------------

    asset.status = AssetStatus.AVAILABLE
    asset.assigned_employee_id = None
    asset.assignment_date = None

    # -----------------------------------------------------
    # RETURN HISTORY
    # -----------------------------------------------------

    hist = AssetAssignmentHistory(
        asset_id=asset.id,
        employee_id=emp_id,
        employee_name=emp_name,
        action='Returned',
        event_date=return_date,
        notes=notes or f'Returned from {emp_name}',
        performed_by=current_user.full_name
    )

    db.session.add(hist)
    db.session.commit()

    AuditService.log(
        action='Asset Returned',
        entity_type='Asset',
        entity_id=asset.asset_id,
        details=(
            f'Returned asset {asset.asset_id} '
            f'from {emp_name} '
            f'on {return_date_str}'
        )
    )

    flash(
        f'Asset {asset.asset_id} returned to Available '
        f'on {return_date_str}.',
        'success'
    )

    return redirect(url_for('assets.index'))


# =========================================================
# REPLACE ASSET
# =========================================================

@assets_bp.route('/replace', methods=['POST'])
@login_required
def replace_asset():

    if not current_user.is_it_admin:
        flash(
            'Permission denied. Only IT Admins can replace assets.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    old_asset_id = request.form.get(
        'old_asset_id',
        type=int
    )

    new_asset_id = request.form.get(
        'new_asset_id',
        type=int
    )

    reason = request.form.get(
        'reason',
        ''
    ).strip()

    return_to_repair = (
        request.form.get('return_to_repair') == 'on'
    )

    send_old_to_vendor = (
        request.form.get('send_old_to_vendor') == 'on'
    )

    replacement_vendor_id = request.form.get(
        'replacement_vendor_id',
        type=int
    )

    vendor_return_reason = request.form.get(
        'vendor_return_reason',
        ''
    ).strip()

    replacement_date_str = request.form.get(
        'replacement_date',
        ''
    ).strip()

    replacement_date = parse_event_date(
        replacement_date_str
    )

    if not replacement_date_str:
        flash(
            'Please select the replacement date.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    if not replacement_date:
        flash(
            'Invalid replacement date.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    # Repair and Vendor are mutually exclusive destinations.
    if return_to_repair and send_old_to_vendor:
        flash(
            'Please select either Repair or Vendor for the old laptop, not both.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    # Vendor details are mandatory when the old laptop is sent to a vendor.
    replacement_vendor = None
    if send_old_to_vendor:
        if not replacement_vendor_id:
            flash(
                'Please select a vendor for the old replaced laptop.',
                'danger'
            )
            return redirect(url_for('assets.index'))

        if not vendor_return_reason:
            flash(
                'Please provide a reason for sending the old replaced laptop to the vendor.',
                'danger'
            )
            return redirect(url_for('assets.index'))

        replacement_vendor = Vendor.query.get_or_404(
            replacement_vendor_id
        )

        normalized_vendor_name = normalize_vendor_name(
            replacement_vendor.name
        )

        if normalized_vendor_name not in ALLOWED_VENDOR_RETURN_NAMES_NORMALIZED:
            flash(
                f'Vendor "{replacement_vendor.name}" is not allowed for vendor return.',
                'danger'
            )
            return redirect(url_for('assets.index'))

    old_asset = Asset.query.get_or_404(
        old_asset_id
    )

    new_asset = Asset.query.get_or_404(
        new_asset_id
    )

    if old_asset.status != AssetStatus.ASSIGNED or not old_asset.assigned_employee:
        flash(
            f'Old asset {old_asset.asset_id} must be '
            'currently assigned.',
            'warning'
        )
        return redirect(url_for('assets.index'))

    if new_asset.status != AssetStatus.AVAILABLE:
        flash(
            f'Replacement asset {new_asset.asset_id} '
            'must be Available.',
            'warning'
        )
        return redirect(url_for('assets.index'))

    employee = old_asset.assigned_employee

    # -----------------------------------------------------
    # OLD ASSET
    # -----------------------------------------------------

    old_asset.replacement_date = replacement_date

    if send_old_to_vendor:
        old_asset.status = AssetStatus.RETURNED_TO_VENDOR
        old_asset.vendor_id = replacement_vendor.id
        old_asset.vendor_return_date = replacement_date
        old_asset.vendor_return_reason = vendor_return_reason
    elif return_to_repair:
        old_asset.status = AssetStatus.REPAIR
        old_asset.vendor_return_date = None
        old_asset.vendor_return_reason = None
    else:
        old_asset.status = AssetStatus.AVAILABLE
        old_asset.vendor_return_date = None
        old_asset.vendor_return_reason = None

    old_asset.assigned_employee_id = None
    old_asset.assignment_date = None

    # -----------------------------------------------------
    # NEW ASSET
    # -----------------------------------------------------

    new_asset.status = AssetStatus.ASSIGNED
    new_asset.assigned_employee_id = employee.id
    new_asset.assignment_date = replacement_date
    new_asset.replacement_date = replacement_date

    # -----------------------------------------------------
    # REPLACEMENT HISTORY
    # -----------------------------------------------------

    replacement_notes = (
        f'Replaced laptop {old_asset.serial_number or "N/A"} '
        f'({old_asset.brand} {old_asset.model}) '
        f'with {new_asset.serial_number or "N/A"} '
        f'({new_asset.brand} {new_asset.model}) '
        f'for {employee.name}. '
        f'Replacement Date: {replacement_date_str}. '
        f'Reason: {reason or "N/A"}'
    )

    if send_old_to_vendor:
        replacement_notes += (
            f' Old laptop sent to Vendor {replacement_vendor.name}. '
            f'Vendor Return Date: {replacement_date_str}. '
            f'Vendor Reason: {vendor_return_reason}'
        )

    hist = AssetAssignmentHistory(
        asset_id=new_asset.id,
        employee_id=employee.id,
        employee_name=employee.name,
        action='Replaced',
        event_date=replacement_date,
        old_asset_id=old_asset.id,
        new_asset_id=new_asset.id,
        replacement_reason=(
            reason or 'Laptop replacement request'
        ),
        notes=replacement_notes,
        performed_by=current_user.full_name
    )

    db.session.add(hist)

    # Keep a separate lifecycle entry on the old asset so its own history
    # clearly shows that it was sent to the vendor as part of the replacement.
    if send_old_to_vendor:
        vendor_hist = AssetAssignmentHistory(
            asset_id=old_asset.id,
            employee_id=employee.id,
            employee_name=employee.name,
            action='Send Back to Vendor',
            event_date=replacement_date,
            old_asset_id=old_asset.id,
            new_asset_id=new_asset.id,
            replacement_reason=vendor_return_reason,
            notes=(
                f'Old laptop {old_asset.asset_id} was replaced with '
                f'{new_asset.asset_id} for {employee.name} and sent to '
                f'Vendor {replacement_vendor.name}. '
                f'Return Date: {replacement_date_str}. '
                f'Reason: {vendor_return_reason}'
            ),
            performed_by=current_user.full_name
        )
        db.session.add(vendor_hist)

    db.session.commit()

    audit_details = (
        f'Replaced asset {old_asset.asset_id} '
        f'with {new_asset.asset_id} '
        f'for employee {employee.name} '
        f'on {replacement_date_str}'
    )

    if send_old_to_vendor:
        audit_details += (
            f'. Old asset sent to vendor {replacement_vendor.name}. '
            f'Reason: {vendor_return_reason}'
        )
    elif return_to_repair:
        audit_details += '. Old asset moved to Repair status.'
    else:
        audit_details += '. Old asset moved to Available status.'

    AuditService.log(
        action='Asset Replaced',
        entity_type='Asset',
        entity_id=new_asset.asset_id,
        details=audit_details
    )

    if send_old_to_vendor:
        flash(
            f'Successfully replaced asset {old_asset.asset_id} with '
            f'{new_asset.asset_id} for {employee.name}. Old laptop was '
            f'sent to Vendor {replacement_vendor.name}.',
            'success'
        )
    else:
        flash(
            f'Successfully replaced asset '
            f'{old_asset.asset_id} with '
            f'{new_asset.asset_id} for '
            f'{employee.name}!',
            'success'
        )

    return redirect(url_for('assets.index'))


# =========================================================
# SEND ASSET TO REPAIR
# =========================================================

@assets_bp.route('/repair', methods=['POST'])
@login_required
def send_to_repair():

    if not current_user.is_it_admin:
        flash(
            'Permission denied. Only IT Admins can send assets '
            'to repair.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    asset_id = request.form.get(
        'asset_id',
        type=int
    )

    vendor_id = request.form.get(
        'vendor_id',
        type=int
    )

    notes = request.form.get(
        'notes',
        ''
    ).strip()

    repair_start_date_str = request.form.get(
        'repair_start_date',
        ''
    ).strip()

    repair_start_date = parse_event_date(
        repair_start_date_str
    )

    if not asset_id:
        flash(
            'Asset ID is missing.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    if not vendor_id:
        flash(
            'Please select a vendor.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    if not repair_start_date_str:
        flash(
            'Please select the repair start date.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    if not repair_start_date:
        flash(
            'Invalid repair start date.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    asset = Asset.query.get_or_404(asset_id)
    vendor = Vendor.query.get_or_404(vendor_id)

    if asset.status == AssetStatus.ASSIGNED:
        flash(
            f'Cannot send assigned asset {asset.asset_id} '
            'directly to repair. Return it or replace it first.',
            'warning'
        )
        return redirect(url_for('assets.index'))

    if asset.status == AssetStatus.RETURNED_TO_VENDOR:
        flash(
            f'Asset {asset.asset_id} has already been '
            'returned to vendor.',
            'warning'
        )
        return redirect(url_for('assets.index'))

    # -----------------------------------------------------
    # UPDATE ASSET
    # -----------------------------------------------------

    asset.status = AssetStatus.REPAIR

    # -----------------------------------------------------
    # CREATE VENDOR REPAIR TICKET
    # -----------------------------------------------------

    repair_ticket = VendorRepairTicket(
        vendor_ticket_number=generate_vendor_ticket_num(),
        asset_id=asset.id,
        vendor_id=vendor.id,
        repair_status=RepairStatus.SENT,
        sent_date=repair_start_date,
        notes=notes
    )

    db.session.add(repair_ticket)

    # -----------------------------------------------------
    # REPAIR HISTORY
    # -----------------------------------------------------

    hist = AssetAssignmentHistory(
        asset_id=asset.id,
        action='Sent to Repair',
        event_date=repair_start_date,
        notes=(
            f'Sent to Vendor {vendor.name} '
            f'under repair ticket '
            f'#{repair_ticket.vendor_ticket_number}. '
            f'Repair Start Date: {repair_start_date_str}. '
            f'Notes: {notes}'
        ),
        performed_by=current_user.full_name
    )

    db.session.add(hist)
    db.session.commit()

    AuditService.log(
        action='Asset Sent to Repair',
        entity_type='Asset',
        entity_id=asset.asset_id,
        details=(
            f'Dispatched asset {asset.asset_id} '
            f'to vendor {vendor.name} '
            f'on {repair_start_date_str} '
            f'(Repair Ticket: '
            f'{repair_ticket.vendor_ticket_number})'
        )
    )

    flash(
        f'Asset {asset.asset_id} sent to Vendor '
        f'{vendor.name} for repair. '
        f'(Ticket: {repair_ticket.vendor_ticket_number})',
        'success'
    )

    return redirect(url_for('assets.index'))


# =========================================================
# COMPLETE REPAIR
# =========================================================

@assets_bp.route('/repair/complete/<int:asset_id>', methods=['POST'])
@login_required
def complete_repair(asset_id):

    if not current_user.is_it_admin:
        flash(
            'Permission denied. Only IT Admins can complete repairs.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    asset = Asset.query.get_or_404(asset_id)

    if asset.status != AssetStatus.REPAIR:
        flash(
            f'Asset {asset.asset_id} is not currently '
            'under repair.',
            'warning'
        )
        return redirect(url_for('assets.index'))

    notes = request.form.get(
        'notes',
        ''
    ).strip()

    repair_completed_date_str = request.form.get(
        'repair_completed_date',
        ''
    ).strip()

    repair_completed_date = parse_event_date(
        repair_completed_date_str
    )

    if not repair_completed_date_str:
        flash(
            'Please select the repair completion date.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    if not repair_completed_date:
        flash(
            'Invalid repair completion date.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    # -----------------------------------------------------
    # REPAIR -> AVAILABLE
    # -----------------------------------------------------

    asset.status = AssetStatus.AVAILABLE

    asset.assigned_employee_id = None
    asset.assignment_date = None

    # -----------------------------------------------------
    # REPAIR COMPLETION HISTORY
    # -----------------------------------------------------

    hist = AssetAssignmentHistory(
        asset_id=asset.id,
        action='Repair Completed',
        event_date=repair_completed_date,
        notes=notes or (
            'Repair completed and laptop moved '
            'to Available.'
        ),
        performed_by=current_user.full_name
    )

    db.session.add(hist)

    # -----------------------------------------------------
    # AVAILABLE / STOCK HISTORY
    # -----------------------------------------------------

    available_hist = AssetAssignmentHistory(
        asset_id=asset.id,
        action='Available',
        event_date=repair_completed_date,
        notes=(
            f'Laptop became Available after repair '
            f'on {repair_completed_date_str}.'
        ),
        performed_by=current_user.full_name
    )

    db.session.add(available_hist)

    # -----------------------------------------------------
    # AUDIT
    # -----------------------------------------------------

    AuditService.log(
        action='Asset Repair Completed',
        entity_type='Asset',
        entity_id=asset.asset_id,
        details=(
            f'Asset {asset.asset_id} repair completed '
            f'on {repair_completed_date_str} '
            'and moved to Available status.'
        )
    )

    db.session.commit()

    flash(
        f'Asset {asset.asset_id} is now Available '
        f'from {repair_completed_date_str}.',
        'success'
    )

    return redirect(url_for('assets.index'))


# =========================================================
# ASSET HISTORY
# =========================================================

@assets_bp.route('/<int:asset_id>/history')
@login_required
def get_asset_history(asset_id):

    asset = Asset.query.get_or_404(asset_id)

    history = AssetAssignmentHistory.query.filter_by(
        asset_id=asset.id
    ).order_by(
        AssetAssignmentHistory.event_date.desc(),
        AssetAssignmentHistory.timestamp.desc()
    ).all()

    h_data = []

    for h in history:

        old_asset_data = None
        if h.old_asset:
            old_asset_data = {
                'serial_number': h.old_asset.serial_number or '-',
                'brand_model': (
                    f'{h.old_asset.brand} {h.old_asset.model}'
                ).strip(),
                'vendor': (
                    h.old_asset.vendor.name
                    if h.old_asset.vendor
                    else None
                )
            }

        new_asset_data = None
        if h.new_asset:
            new_asset_data = {
                'serial_number': h.new_asset.serial_number or '-',
                'brand_model': (
                    f'{h.new_asset.brand} {h.new_asset.model}'
                ).strip(),
                'vendor': (
                    h.new_asset.vendor.name
                    if h.new_asset.vendor
                    else None
                )
            }

        history_vendor = None
        if old_asset_data and old_asset_data['vendor']:
            history_vendor = old_asset_data['vendor']
        elif new_asset_data and new_asset_data['vendor']:
            history_vendor = new_asset_data['vendor']
        elif asset.vendor:
            history_vendor = asset.vendor.name

        display_notes = h.notes or '-'

        # Replace internal Asset IDs in older history notes with
        # user-friendly serial numbers so the history never exposes
        # AST-XXXX identifiers.
        if h.old_asset and h.old_asset.asset_id:
            display_notes = display_notes.replace(
                h.old_asset.asset_id,
                h.old_asset.serial_number or h.old_asset.asset_id
            )
        if h.new_asset and h.new_asset.asset_id:
            display_notes = display_notes.replace(
                h.new_asset.asset_id,
                h.new_asset.serial_number or h.new_asset.asset_id
            )

        h_data.append({
            'id': h.id,
            'action': h.action,
            'employee_name': h.employee_name or '-',

            'old_asset': old_asset_data,
            'new_asset': new_asset_data,
            'vendor': history_vendor,

            'replacement_reason': (
                h.replacement_reason or '-'
            ),

            'notes': display_notes,

            'performed_by': (
                h.performed_by or 'System'
            ),

            # Actual asset event date
            'event_date': (
                h.event_date.strftime('%Y-%m-%d')
                if h.event_date
                else '-'
            ),

            # System record creation timestamp
            'timestamp': (
                h.timestamp.strftime('%Y-%m-%d %H:%M')
                if h.timestamp
                else '-'
            )
        })

    return jsonify({
        'brand_model': (
            f"{asset.brand} {asset.model}"
        ),
        'serial_number': asset.serial_number or '-',
        'assigned_user': asset.assigned_user_name or '-',
        'vendor': (
            asset.vendor.name
            if asset.vendor
            else None
        ),
        'history': h_data
    })


# =========================================================
# RETURN TO VENDOR
# =========================================================

@assets_bp.route('/return-to-vendor', methods=['POST'])
@login_required
def return_to_vendor():

    # -----------------------------------------------------
    # IT ADMIN PERMISSION
    # -----------------------------------------------------

    if not current_user.is_it_admin:
        flash(
            'Permission denied. Only IT Admins can return '
            'assets to vendors.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    # -----------------------------------------------------
    # FORM DATA
    # -----------------------------------------------------

    asset_id = request.form.get(
        'asset_id',
        type=int
    )

    vendor_id = request.form.get(
        'vendor_id',
        type=int
    )

    reason = request.form.get(
        'reason',
        ''
    ).strip()

    vendor_return_date_str = request.form.get(
        'vendor_return_date',
        ''
    ).strip()

    vendor_return_date = parse_event_date(
        vendor_return_date_str
    )

    # -----------------------------------------------------
    # VALIDATE ASSET
    # -----------------------------------------------------

    if not asset_id:
        flash(
            'Asset ID is missing.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    asset = Asset.query.get_or_404(asset_id)

    # -----------------------------------------------------
    # VALIDATE VENDOR
    # -----------------------------------------------------

    if not vendor_id:
        flash(
            'Please select a vendor.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    vendor = Vendor.query.get_or_404(vendor_id)

    # -----------------------------------------------------
    # ALLOWED VENDOR
    # -----------------------------------------------------

    normalized_vendor_name = normalize_vendor_name(
        vendor.name
    )

    if normalized_vendor_name not in ALLOWED_VENDOR_RETURN_NAMES_NORMALIZED:
        flash(
            f'Vendor "{vendor.name}" is not allowed '
            'for vendor return.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    # -----------------------------------------------------
    # STATUS CHECK
    # -----------------------------------------------------

    if asset.status == AssetStatus.ASSIGNED:
        flash(
            f'Cannot return assigned asset '
            f'{asset.asset_id} to vendor. '
            'Return it from the employee first.',
            'warning'
        )
        return redirect(url_for('assets.index'))

    if asset.status == AssetStatus.RETURNED_TO_VENDOR:
        flash(
            f'Asset {asset.asset_id} has already been '
            'returned to vendor.',
            'warning'
        )
        return redirect(url_for('assets.index'))

    # -----------------------------------------------------
    # DATE VALIDATION
    # -----------------------------------------------------

    if not vendor_return_date_str:
        flash(
            'Please select the vendor return date.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    if not vendor_return_date:
        flash(
            'Invalid vendor return date.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    # -----------------------------------------------------
    # REASON VALIDATION
    # -----------------------------------------------------

    if not reason:
        flash(
            'Please provide a reason for returning '
            'the asset to vendor.',
            'danger'
        )
        return redirect(url_for('assets.index'))

    # -----------------------------------------------------
    # UPDATE ASSET
    # -----------------------------------------------------

    asset.vendor_id = vendor.id

    asset.status = AssetStatus.RETURNED_TO_VENDOR

    asset.vendor_return_date = vendor_return_date

    asset.vendor_return_reason = reason

    asset.assigned_employee_id = None

    asset.assignment_date = None

    # -----------------------------------------------------
    # HISTORY
    # -----------------------------------------------------

    hist = AssetAssignmentHistory(
        asset_id=asset.id,
        action='Send Back to Vendor',
        event_date=vendor_return_date,
        notes=(
            f'Asset returned to Vendor '
            f'{vendor.name}. '
            f'Return Date: {vendor_return_date_str}. '
            f'Reason: {reason}'
        ),
        performed_by=current_user.full_name
    )

    db.session.add(hist)

    # -----------------------------------------------------
    # AUDIT
    # -----------------------------------------------------

    AuditService.log(
        action='Asset Returned to Vendor',
        entity_type='Asset',
        entity_id=asset.asset_id,
        details=(
            f'Asset {asset.asset_id} returned to vendor '
            f'{vendor.name} on '
            f'{vendor_return_date_str}. '
            f'Reason: {reason}'
        )
    )

    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    db.session.commit()

    # -----------------------------------------------------
    # SUCCESS
    # -----------------------------------------------------

    flash(
        f'Asset {asset.asset_id} successfully returned '
        f'to {vendor.name} on '
        f'{vendor_return_date_str}.',
        'success'
    )

    return redirect(url_for('assets.index'))
