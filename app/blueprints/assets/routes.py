from datetime import datetime
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models.asset import Asset, AssetStatus, AssetAssignmentHistory
from app.models.employee import Employee, AccountStatus
from app.models.vendor import Vendor, VendorRepairTicket, RepairStatus
from app.services.audit_service import AuditService

assets_bp = Blueprint('assets', __name__, url_prefix='/assets')

def generate_asset_id():
    year = datetime.utcnow().strftime('%Y')
    count = Asset.query.count() + 1
    return f"AST-{year}-{count:04d}"

def generate_vendor_ticket_num():
    year = datetime.utcnow().strftime('%Y')
    count = VendorRepairTicket.query.count() + 1
    return f"VNR-{year}-{count:04d}"

@assets_bp.route('/')
@login_required
def index():
    search_q = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    vendor_filter = request.args.get('vendor_id', type=int)
    page = request.args.get('page', 1, type=int)

    query = Asset.query

    if search_q:
        query = query.join(Employee, Asset.assigned_employee_id == Employee.id, isouter=True).filter(
            (Asset.asset_id.ilike(f'%{search_q}%')) |
            (Asset.brand.ilike(f'%{search_q}%')) |
            (Asset.model.ilike(f'%{search_q}%')) |
            (Asset.serial_number.ilike(f'%{search_q}%')) |
            (Employee.name.ilike(f'%{search_q}%'))
        )

    if status_filter:
        query = query.filter(Asset.status == status_filter)

    if vendor_filter:
        query = query.filter(Asset.vendor_id == vendor_filter)

    pagination = query.order_by(Asset.id.desc()).paginate(page=page, per_page=10, error_out=False)
    assets = pagination.items

    vendors = Vendor.query.order_by(Vendor.name.asc()).all()
    active_employees = Employee.query.filter(Employee.account_status != AccountStatus.OFFBOARDED).order_by(Employee.name.asc()).all()
    available_assets = Asset.query.filter_by(status=AssetStatus.AVAILABLE).order_by(Asset.brand.asc()).all()
    assigned_assets = Asset.query.filter_by(status=AssetStatus.ASSIGNED).order_by(Asset.asset_id.asc()).all()

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
        assigned_assets=assigned_assets
    )


@assets_bp.route('/add', methods=['POST'])
@login_required
def add_asset():
    if not current_user.is_it_admin:
        flash('Permission denied. Only IT Admins can add assets.', 'danger')
        return redirect(url_for('assets.index'))

    brand = request.form.get('brand', '').strip()
    model = request.form.get('model', '').strip()
    serial_number = request.form.get('serial_number', '').strip()
    processor = request.form.get('processor', '').strip()
    ram = request.form.get('ram', '').strip()
    ssd = request.form.get('ssd', '').strip()
    vendor_id = request.form.get('vendor_id', type=int)

    if not all([brand, model, serial_number, processor, ram, ssd, vendor_id]):
        flash('All asset specification fields are required.', 'danger')
        return redirect(url_for('assets.index'))

    # Check serial number uniqueness
    existing = Asset.query.filter_by(serial_number=serial_number).first()
    if existing:
        flash(f'Asset with Serial Number "{serial_number}" already exists.', 'danger')
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
    db.session.commit()

    AuditService.log(
        action='Asset Created',
        entity_type='Asset',
        entity_id=new_asset.asset_id,
        details=f'Added new asset {new_asset.brand} {new_asset.model} (SN: {new_asset.serial_number})'
    )

    flash(f'Asset {new_asset.asset_id} added successfully!', 'success')
    return redirect(url_for('assets.index'))


@assets_bp.route('/edit/<int:asset_id>', methods=['POST'])
@login_required
def edit_asset(asset_id):
    if not current_user.is_it_admin:
        flash('Permission denied. Only IT Admins can edit assets.', 'danger')
        return redirect(url_for('assets.index'))

    asset = Asset.query.get_or_404(asset_id)
    
    asset.brand = request.form.get('brand', asset.brand).strip()
    asset.model = request.form.get('model', asset.model).strip()
    asset.processor = request.form.get('processor', asset.processor).strip()
    asset.ram = request.form.get('ram', asset.ram).strip()
    asset.ssd = request.form.get('ssd', asset.ssd).strip()
    asset.vendor_id = request.form.get('vendor_id', asset.vendor_id, type=int)

    db.session.commit()

    AuditService.log(
        action='Asset Updated',
        entity_type='Asset',
        entity_id=asset.asset_id,
        details=f'Updated specifications for asset {asset.asset_id}'
    )

    flash(f'Asset {asset.asset_id} updated successfully!', 'success')
    return redirect(url_for('assets.index'))


@assets_bp.route('/delete/<int:asset_id>', methods=['POST'])
@login_required
def delete_asset(asset_id):
    if not current_user.can_delete_assets():
        flash('Permission denied. IT Engineers cannot delete assets.', 'danger')
        return redirect(url_for('assets.index'))

    asset = Asset.query.get_or_404(asset_id)
    if asset.status == AssetStatus.ASSIGNED:
        flash(f'Cannot delete asset {asset.asset_id} while it is assigned to an employee. Return it first.', 'warning')
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

    flash(f'Asset {aid} deleted.', 'success')
    return redirect(url_for('assets.index'))


@assets_bp.route('/assign', methods=['POST'])
@login_required
def assign_asset():
    if not current_user.is_it_admin:
        flash('Permission denied. Only IT Admins can assign assets.', 'danger')
        return redirect(url_for('assets.index'))

    asset_id = request.form.get('asset_id', type=int)
    employee_id = request.form.get('employee_id', type=int)
    notes = request.form.get('notes', '').strip()

    asset = Asset.query.get_or_404(asset_id)
    employee = Employee.query.get_or_404(employee_id)

    if asset.status != AssetStatus.AVAILABLE:
        flash(f'Asset {asset.asset_id} is currently {asset.status} and cannot be assigned.', 'warning')
        return redirect(url_for('assets.index'))

    if employee.account_status == AccountStatus.OFFBOARDED:
        flash(f'Cannot assign asset to offboarded employee {employee.name}.', 'danger')
        return redirect(url_for('assets.index'))

    asset.status = AssetStatus.ASSIGNED
    asset.assigned_employee_id = employee.id
    asset.assignment_date = datetime.utcnow()

    # Log assignment history
    hist = AssetAssignmentHistory(
        asset_id=asset.id,
        employee_id=employee.id,
        employee_name=employee.name,
        action='Assigned',
        notes=notes or f'Assigned to {employee.name} ({employee.employee_id})',
        performed_by=current_user.full_name
    )
    db.session.add(hist)
    db.session.commit()

    AuditService.log(
        action='Asset Assigned',
        entity_type='Asset',
        entity_id=asset.asset_id,
        details=f'Assigned {asset.asset_id} ({asset.brand} {asset.model}) to employee {employee.name} ({employee.employee_id})'
    )

    flash(f'Asset {asset.asset_id} assigned to {employee.name}!', 'success')
    return redirect(url_for('assets.index'))


@assets_bp.route('/return/<int:asset_id>', methods=['POST'])
@login_required
def return_asset(asset_id):
    if not current_user.is_it_admin:
        flash('Permission denied. Only IT Admins can return assets.', 'danger')
        return redirect(url_for('assets.index'))

    asset = Asset.query.get_or_404(asset_id)
    if asset.status != AssetStatus.ASSIGNED or not asset.assigned_employee:
        flash(f'Asset {asset.asset_id} is not currently assigned.', 'warning')
        return redirect(url_for('assets.index'))

    emp_name = asset.assigned_employee.name
    emp_id = asset.assigned_employee.id
    notes = request.form.get('notes', '').strip()

    asset.status = AssetStatus.AVAILABLE
    asset.assigned_employee_id = None
    asset.assignment_date = None

    hist = AssetAssignmentHistory(
        asset_id=asset.id,
        employee_id=emp_id,
        employee_name=emp_name,
        action='Returned',
        notes=notes or f'Returned from {emp_name}',
        performed_by=current_user.full_name
    )
    db.session.add(hist)
    db.session.commit()

    AuditService.log(
        action='Asset Returned',
        entity_type='Asset',
        entity_id=asset.asset_id,
        details=f'Returned asset {asset.asset_id} from {emp_name}'
    )

    flash(f'Asset {asset.asset_id} returned to Available status.', 'success')
    return redirect(url_for('assets.index'))


@assets_bp.route('/replace', methods=['POST'])
@login_required
def replace_asset():
    """
    Multi-replacement workflow:
    Swaps an existing assigned laptop (old asset) with a new available laptop for an employee.
    Logs explicit linked replacement history tracking old & new assets and replacement reason.
    """
    if not current_user.is_it_admin:
        flash('Permission denied. Only IT Admins can replace assets.', 'danger')
        return redirect(url_for('assets.index'))

    old_asset_id = request.form.get('old_asset_id', type=int)
    new_asset_id = request.form.get('new_asset_id', type=int)
    reason = request.form.get('reason', '').strip()
    return_to_repair = request.form.get('return_to_repair') == 'on'

    old_asset = Asset.query.get_or_404(old_asset_id)
    new_asset = Asset.query.get_or_404(new_asset_id)

    if old_asset.status != AssetStatus.ASSIGNED or not old_asset.assigned_employee:
        flash(f'Old asset {old_asset.asset_id} must be currently assigned.', 'warning')
        return redirect(url_for('assets.index'))

    if new_asset.status != AssetStatus.AVAILABLE:
        flash(f'Replacement asset {new_asset.asset_id} must be Available.', 'warning')
        return redirect(url_for('assets.index'))

    employee = old_asset.assigned_employee

    # 1. Unassign old asset
    old_asset.status = AssetStatus.REPAIR if return_to_repair else AssetStatus.AVAILABLE
    old_asset.assigned_employee_id = None
    old_asset.assignment_date = None

    # 2. Assign new asset
    new_asset.status = AssetStatus.ASSIGNED
    new_asset.assigned_employee_id = employee.id
    new_asset.assignment_date = datetime.utcnow()

    # 3. Log linked replacement history
    hist = AssetAssignmentHistory(
        asset_id=new_asset.id,
        employee_id=employee.id,
        employee_name=employee.name,
        action='Replaced',
        old_asset_id=old_asset.id,
        new_asset_id=new_asset.id,
        replacement_reason=reason or 'Laptop replacement request',
        notes=f'Replaced laptop {old_asset.asset_id} with {new_asset.asset_id} for {employee.name}. Reason: {reason or "N/A"}',
        performed_by=current_user.full_name
    )
    db.session.add(hist)
    db.session.commit()

    AuditService.log(
        action='Asset Replaced',
        entity_type='Asset',
        entity_id=new_asset.asset_id,
        details=f'Replaced asset {old_asset.asset_id} with {new_asset.asset_id} for employee {employee.name}'
    )

    flash(f'Successfully replaced asset {old_asset.asset_id} with {new_asset.asset_id} for {employee.name}!', 'success')
    return redirect(url_for('assets.index'))


@assets_bp.route('/repair', methods=['POST'])
@login_required
def send_to_repair():
    asset_id = request.form.get('asset_id', type=int)
    vendor_id = request.form.get('vendor_id', type=int)
    notes = request.form.get('notes', '').strip()

    asset = Asset.query.get_or_404(asset_id)
    vendor = Vendor.query.get_or_404(vendor_id)

    if asset.status == AssetStatus.ASSIGNED:
        flash(f'Cannot send assigned asset {asset.asset_id} directly to repair. Return it or replace it first.', 'warning')
        return redirect(url_for('assets.index'))

    asset.status = AssetStatus.REPAIR

    repair_ticket = VendorRepairTicket(
        vendor_ticket_number=generate_vendor_ticket_num(),
        asset_id=asset.id,
        vendor_id=vendor.id,
        repair_status=RepairStatus.SENT,
        sent_date=datetime.utcnow(),
        notes=notes
    )
    db.session.add(repair_ticket)

    hist = AssetAssignmentHistory(
        asset_id=asset.id,
        action='Sent to Repair',
        notes=f'Sent to Vendor {vendor.name} under repair ticket #{repair_ticket.vendor_ticket_number}. Notes: {notes}',
        performed_by=current_user.full_name
    )
    db.session.add(hist)
    db.session.commit()

    AuditService.log(
        action='Asset Sent to Repair',
        entity_type='Asset',
        entity_id=asset.asset_id,
        details=f'Dispatched asset {asset.asset_id} to vendor {vendor.name} (Repair Ticket: {repair_ticket.vendor_ticket_number})'
    )

    flash(f'Asset {asset.asset_id} sent to Vendor {vendor.name} for repair. (Ticket: {repair_ticket.vendor_ticket_number})', 'success')
    return redirect(url_for('assets.index'))


@assets_bp.route('/<int:asset_id>/history')
@login_required
def get_asset_history(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    history = AssetAssignmentHistory.query.filter_by(asset_id=asset.id).order_by(AssetAssignmentHistory.timestamp.desc()).all()

    h_data = []
    for h in history:
        h_data.append({
            'id': h.id,
            'action': h.action,
            'employee_name': h.employee_name or '-',
            'old_asset': h.old_asset.asset_id if h.old_asset else None,
            'new_asset': h.new_asset.asset_id if h.new_asset else None,
            'replacement_reason': h.replacement_reason or '-',
            'notes': h.notes or '-',
            'performed_by': h.performed_by or 'System',
            'timestamp': h.timestamp.strftime('%Y-%m-%d %H:%M')
        })

    return jsonify({
        'asset_id': asset.asset_id,
        'brand_model': f"{asset.brand} {asset.model}",
        'serial_number': asset.serial_number,
        'assigned_user': asset.assigned_user_name,
        'history': h_data
    })
