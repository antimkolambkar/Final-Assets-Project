from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
from sqlalchemy import func
from app.extensions import db
from app.models.asset import Asset, AssetStatus, AssetAssignmentHistory
from app.models.employee import Employee, AccountStatus
from app.models.ticket import Ticket, TicketStatus, TicketCategory
from app.models.vendor import Vendor, VendorRepairTicket, RepairStatus
from app.models.audit import AuditLog

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    # Card Counts
    total_assets = Asset.query.count()
    assigned_assets = Asset.query.filter_by(status=AssetStatus.ASSIGNED).count()
    available_assets = Asset.query.filter_by(status=AssetStatus.AVAILABLE).count()
    repair_assets = Asset.query.filter_by(status=AssetStatus.REPAIR).count()

    total_employees = Employee.query.count()
    active_employees = Employee.query.filter_by(account_status=AccountStatus.ACTIVE).count()
    blocked_employees = Employee.query.filter_by(account_status=AccountStatus.BLOCKED).count()
    disabled_employees = Employee.query.filter_by(account_status=AccountStatus.DISABLED).count()
    offboarded_employees = Employee.query.filter_by(account_status=AccountStatus.OFFBOARDED).count()

    open_tickets = Ticket.query.filter(Ticket.status.in_([TicketStatus.OPEN])).count()
    assigned_tickets = Ticket.query.filter(Ticket.status.in_([TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS])).count()
    closed_tickets = Ticket.query.filter(Ticket.status.in_([TicketStatus.RESOLVED, TicketStatus.CLOSED])).count()
    vendor_tickets = VendorRepairTicket.query.filter(VendorRepairTicket.repair_status.in_(['Sent', 'In Repair'])).count()

    # Widgets
    recent_activities = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(7).all()
    recently_assigned = AssetAssignmentHistory.query.filter_by(action='Assigned').order_by(AssetAssignmentHistory.timestamp.desc()).limit(5).all()
    recent_tickets = Ticket.query.order_by(Ticket.created_at.desc()).limit(5).all()
    pending_repairs = VendorRepairTicket.query.filter(VendorRepairTicket.repair_status.in_(['Sent', 'In Repair'])).order_by(VendorRepairTicket.sent_date.desc()).limit(5).all()

    return render_template(
        'dashboard/index.html',
        total_assets=total_assets,
        assigned_assets=assigned_assets,
        available_assets=available_assets,
        repair_assets=repair_assets,
        total_employees=total_employees,
        active_employees=active_employees,
        blocked_employees=blocked_employees,
        disabled_employees=disabled_employees,
        offboarded_employees=offboarded_employees,
        open_tickets=open_tickets,
        assigned_tickets=assigned_tickets,
        closed_tickets=closed_tickets,
        vendor_tickets=vendor_tickets,
        recent_activities=recent_activities,
        recently_assigned=recently_assigned,
        recent_tickets=recent_tickets,
        pending_repairs=pending_repairs
    )


@dashboard_bp.route('/dashboard/api/metrics')
@login_required
def get_metrics_json():
    """API endpoint for live dashboard AJAX auto-refresh and Chart.js feeds"""
    # Asset Distribution by Status
    asset_dist = {
        'Available': Asset.query.filter_by(status=AssetStatus.AVAILABLE).count(),
        'Assigned': Asset.query.filter_by(status=AssetStatus.ASSIGNED).count(),
        'Under Repair': Asset.query.filter_by(status=AssetStatus.REPAIR).count()
    }

    # Department-wise Assets
    dept_assets_query = db.session.query(Employee.department, func.count(Asset.id))\
        .join(Asset, Asset.assigned_employee_id == Employee.id)\
        .group_by(Employee.department).all()
    dept_assets = {dept or 'Unassigned': cnt for dept, cnt in dept_assets_query}

    # Vendor-wise Assets
    vendor_assets_query = db.session.query(Vendor.name, func.count(Asset.id))\
        .join(Asset, Asset.vendor_id == Vendor.id)\
        .group_by(Vendor.name).all()
    vendor_assets = {vname: cnt for vname, cnt in vendor_assets_query}

    # Ticket Status Distribution
    tkt_status_query = db.session.query(Ticket.status, func.count(Ticket.id))\
        .group_by(Ticket.status).all()
    tkt_status = {st: cnt for st, cnt in tkt_status_query}

    # Ticket Category Distribution
    tkt_cat_query = db.session.query(Ticket.category, func.count(Ticket.id))\
        .group_by(Ticket.category).all()
    tkt_cat = {cat: cnt for cat, cnt in tkt_cat_query}

    return jsonify({
        'cards': {
            'total_assets': Asset.query.count(),
            'assigned_assets': asset_dist['Assigned'],
            'available_assets': asset_dist['Available'],
            'repair_assets': asset_dist['Under Repair'],
            'total_employees': Employee.query.count(),
            'active_employees': Employee.query.filter_by(account_status=AccountStatus.ACTIVE).count(),
            'blocked_employees': Employee.query.filter_by(account_status=AccountStatus.BLOCKED).count(),
            'disabled_employees': Employee.query.filter_by(account_status=AccountStatus.DISABLED).count(),
            'offboarded_employees': Employee.query.filter_by(account_status=AccountStatus.OFFBOARDED).count(),
            'open_tickets': Ticket.query.filter(Ticket.status.in_([TicketStatus.OPEN])).count(),
            'assigned_tickets': Ticket.query.filter(Ticket.status.in_([TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS])).count(),
            'closed_tickets': Ticket.query.filter(Ticket.status.in_([TicketStatus.RESOLVED, TicketStatus.CLOSED])).count(),
            'vendor_tickets': VendorRepairTicket.query.filter(VendorRepairTicket.repair_status.in_(['Sent', 'In Repair'])).count()
        },
        'charts': {
            'asset_distribution': asset_dist,
            'dept_assets': dept_assets,
            'vendor_assets': vendor_assets,
            'ticket_status': tkt_status,
            'ticket_category': tkt_cat
        }
    })
