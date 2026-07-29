import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app, send_from_directory
from flask_login import login_required, current_user
from app.extensions import db
from app.models.ticket import Ticket, TicketCategory, TicketPriority, TicketStatus, TicketComment, TicketAttachment
from app.models.employee import Employee, AccountStatus
from app.models.user import User, Role
from app.models.vendor import Vendor, VendorRepairTicket, RepairStatus
from app.models.asset import Asset, AssetStatus
from app.services.ticket_service import TicketService
from app.services.audit_service import AuditService

tickets_bp = Blueprint('tickets', __name__, url_prefix='/tickets')

@tickets_bp.route('/')
@login_required
def index():
    search_q = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    category_filter = request.args.get('category', '').strip()
    priority_filter = request.args.get('priority', '').strip()
    engineer_filter = request.args.get('engineer_id', type=int)
    page = request.args.get('page', 1, type=int)

    query = Ticket.query

    # IT Engineers only see their assigned tickets unless Super Admin / IT Admin
    if current_user.role == Role.IT_ENGINEER:
        query = query.filter_by(assigned_engineer_id=current_user.id)
    elif engineer_filter:
        query = query.filter_by(assigned_engineer_id=engineer_filter)

    if search_q:
        query = query.join(Employee, Ticket.employee_id == Employee.id).filter(
            (Ticket.ticket_id.ilike(f'%{search_q}%')) |
            (Ticket.subject.ilike(f'%{search_q}%')) |
            (Employee.name.ilike(f'%{search_q}%'))
        )

    if status_filter:
        query = query.filter_by(status=status_filter)

    if category_filter:
        query = query.filter_by(category=category_filter)

    if priority_filter:
        query = query.filter_by(priority=priority_filter)

    pagination = query.order_by(Ticket.created_at.desc()).paginate(page=page, per_page=10, error_out=False)
    tickets = pagination.items

    engineers = User.query.filter(User.role.in_([Role.IT_ENGINEER, Role.IT_ADMIN, Role.SUPER_ADMIN])).order_by(User.full_name.asc()).all()
    employees = Employee.query.filter(Employee.account_status != AccountStatus.OFFBOARDED).order_by(Employee.name.asc()).all()

    return render_template(
        'tickets/index.html',
        tickets=tickets,
        pagination=pagination,
        search_q=search_q,
        status_filter=status_filter,
        category_filter=category_filter,
        priority_filter=priority_filter,
        engineer_filter=engineer_filter,
        engineers=engineers,
        employees=employees,
        categories=TicketCategory.CHOICES,
        priorities=TicketPriority.CHOICES,
        statuses=TicketStatus.CHOICES
    )


@tickets_bp.route('/create', methods=['POST'])
@login_required
def create_ticket():
    subject = request.form.get('subject', '').strip()
    description = request.form.get('description', '').strip()
    employee_id = request.form.get('employee_id', type=int)
    category = request.form.get('category', TicketCategory.OTHER)
    priority = request.form.get('priority', TicketPriority.MEDIUM)

    if not all([subject, description, employee_id]):
        flash('Subject, description, and employee selection are required.', 'danger')
        return redirect(url_for('tickets.index'))

    employee = Employee.query.get_or_404(employee_id)

    ticket = Ticket(
        ticket_id=TicketService.generate_ticket_id(),
        subject=subject,
        description=description,
        employee_id=employee.id,
        department=employee.department,
        category=category,
        priority=priority,
        status=TicketStatus.OPEN,
        created_at=datetime.utcnow()
    )
    db.session.add(ticket)
    db.session.commit()

    AuditService.log(
        action='Ticket Created',
        entity_type='Ticket',
        entity_id=ticket.ticket_id,
        details=f'Created ticket {ticket.ticket_id} for employee {employee.name}'
    )

    flash(f'Ticket {ticket.ticket_id} created successfully!', 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket.ticket_id))


@tickets_bp.route('/<string:ticket_id>')
@login_required
def detail(ticket_id):
    ticket = Ticket.query.filter_by(ticket_id=ticket_id).first_or_404()
    
    # Check engineer permission
    if current_user.role == Role.IT_ENGINEER and ticket.assigned_engineer_id != current_user.id:
        flash('Permission denied. You can only view tickets assigned to you.', 'danger')
        return redirect(url_for('tickets.index'))

    engineers = User.query.filter(User.role.in_([Role.IT_ENGINEER, Role.IT_ADMIN, Role.SUPER_ADMIN])).order_by(User.full_name.asc()).all()
    vendors = Vendor.query.order_by(Vendor.name.asc()).all()
    assigned_assets = Asset.query.filter_by(assigned_employee_id=ticket.employee_id).all()

    return render_template(
        'tickets/detail.html',
        ticket=ticket,
        engineers=engineers,
        vendors=vendors,
        assigned_assets=assigned_assets,
        statuses=TicketStatus.CHOICES,
        priorities=TicketPriority.CHOICES,
        categories=TicketCategory.CHOICES
    )


@tickets_bp.route('/<string:ticket_id>/assign', methods=['POST'])
@login_required
def assign_ticket(ticket_id):
    if not current_user.can_assign_tickets():
        flash('Permission denied. Only IT Administrators can assign tickets.', 'danger')
        return redirect(url_for('tickets.detail', ticket_id=ticket_id))

    engineer_id = request.form.get('engineer_id', type=int)
    success, msg = TicketService.assign_engineer(ticket_id, engineer_id, current_user.full_name)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')

    return redirect(url_for('tickets.detail', ticket_id=ticket_id))


@tickets_bp.route('/<string:ticket_id>/status', methods=['POST'])
@login_required
def update_status(ticket_id):
    new_status = request.form.get('status', '').strip()
    success, msg = TicketService.update_status(ticket_id, new_status, current_user.full_name)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')

    return redirect(url_for('tickets.detail', ticket_id=ticket_id))


@tickets_bp.route('/<string:ticket_id>/comment', methods=['POST'])
@login_required
def add_comment(ticket_id):
    comment_text = request.form.get('comment_text', '').strip()
    is_internal = request.form.get('is_internal') == 'on'

    if comment_text:
        TicketService.add_comment(
            ticket_id_val=ticket_id,
            author_name=current_user.full_name,
            comment_text=comment_text,
            user_id=current_user.id,
            is_internal=is_internal
        )
        flash('Comment added to ticket thread.', 'success')

    return redirect(url_for('tickets.detail', ticket_id=ticket_id))


@tickets_bp.route('/<string:ticket_id>/upload', methods=['POST'])
@login_required
def upload_attachment(ticket_id):
    ticket = Ticket.query.filter_by(ticket_id=ticket_id).first_or_404()
    
    if 'file' not in request.files:
        flash('No file selected.', 'warning')
        return redirect(url_for('tickets.detail', ticket_id=ticket_id))

    file = request.files['file']
    if file and file.filename:
        filename = secure_filename(file.filename)
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        
        saved_path = os.path.join(upload_folder, f"{ticket.ticket_id}_{filename}")
        file.save(saved_path)

        attachment = TicketAttachment(
            ticket_id=ticket.id,
            filename=filename,
            file_path=saved_path,
            file_size=os.path.getsize(saved_path),
            uploaded_at=datetime.utcnow()
        )
        db.session.add(attachment)
        db.session.commit()

        flash(f'Attachment {filename} uploaded successfully.', 'success')

    return redirect(url_for('tickets.detail', ticket_id=ticket_id))


@tickets_bp.route('/attachment/<int:attachment_id>')
@login_required
def download_attachment(attachment_id):
    attachment = TicketAttachment.query.get_or_404(attachment_id)
    upload_folder = current_app.config['UPLOAD_FOLDER']
    filename = os.path.basename(attachment.file_path)
    return send_from_directory(upload_folder, filename, as_attachment=True)
