from datetime import datetime
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
from app.models.vendor import Vendor, VendorRepairTicket, RepairStatus
from app.models.asset import Asset, AssetStatus, AssetAssignmentHistory
from app.services.audit_service import AuditService

vendors_bp = Blueprint('vendors', __name__, url_prefix='/vendors')

@vendors_bp.route('/')
@login_required
def index():
    vendors = Vendor.query.order_by(Vendor.name.asc()).all()
    repair_tickets = VendorRepairTicket.query.order_by(VendorRepairTicket.created_at.desc()).all()
    return render_template('vendors/index.html', vendors=vendors, repair_tickets=repair_tickets, repair_statuses=['Sent', 'In Repair', 'Repaired', 'Returned'])


@vendors_bp.route('/add', methods=['POST'])
@login_required
def add_vendor():
    if not current_user.is_it_admin:
        flash('Permission denied. Only IT Admins can manage vendors.', 'danger')
        return redirect(url_for('vendors.index'))

    name = request.form.get('name', '').strip()
    contact_person = request.form.get('contact_person', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()

    if not name:
        flash('Vendor Name is required.', 'danger')
        return redirect(url_for('vendors.index'))

    existing = Vendor.query.filter_by(name=name).first()
    if existing:
        flash(f'Vendor "{name}" already exists.', 'warning')
        return redirect(url_for('vendors.index'))

    vendor = Vendor(name=name, contact_person=contact_person, email=email, phone=phone, address=address)
    db.session.add(vendor)
    db.session.commit()

    AuditService.log(action='Vendor Added', entity_type='Vendor', entity_id=name, details=f'Added new vendor {name}')
    flash(f'Vendor "{name}" added successfully!', 'success')
    return redirect(url_for('vendors.index'))


@vendors_bp.route('/repair-ticket/<int:ticket_id>/update-status', methods=['POST'])
@login_required
def update_repair_status(ticket_id):
    ticket = VendorRepairTicket.query.get_or_404(ticket_id)
    new_status = request.form.get('repair_status', '').strip()
    notes = request.form.get('notes', '').strip()

    old_status = ticket.repair_status
    ticket.repair_status = new_status
    if notes:
        ticket.notes = (ticket.notes or '') + f"\n[{datetime.utcnow().strftime('%Y-%m-%d')}] Status update: {new_status}. {notes}"

    if new_status == RepairStatus.RETURNED:
        ticket.returned_date = datetime.utcnow()
        if ticket.asset:
            ticket.asset.status = AssetStatus.AVAILABLE
            hist = AssetAssignmentHistory(
                asset_id=ticket.asset.id,
                action='Repaired & Returned',
                notes=f'Returned from Vendor {ticket.vendor.name} under ticket #{ticket.vendor_ticket_number}',
                performed_by=current_user.full_name
            )
            db.session.add(hist)

    db.session.commit()

    AuditService.log(
        action='Vendor Repair Ticket Status Updated',
        entity_type='VendorRepairTicket',
        entity_id=ticket.vendor_ticket_number,
        details=f'Updated repair ticket {ticket.vendor_ticket_number} status from {old_status} to {new_status}'
    )

    flash(f'Vendor Repair Ticket {ticket.vendor_ticket_number} updated to {new_status}!', 'success')
    return redirect(url_for('vendors.index'))
