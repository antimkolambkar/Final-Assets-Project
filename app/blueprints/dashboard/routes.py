from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from sqlalchemy import func

from app.extensions import db
from app.models.asset import Asset, AssetStatus, AssetAssignmentHistory
from app.models.employee import Employee, AccountStatus
from app.models.ticket import Ticket, TicketStatus
from app.models.vendor import Vendor, VendorRepairTicket
from app.models.audit import AuditLog


dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():

    # =========================================================
    # ASSET COUNTS
    # =========================================================
    total_assets = Asset.query.count()

    assigned_assets = Asset.query.filter_by(
        status=AssetStatus.ASSIGNED
    ).count()

    available_assets = Asset.query.filter_by(
        status=AssetStatus.AVAILABLE
    ).count()

    repair_assets = Asset.query.filter_by(
        status=AssetStatus.REPAIR
    ).count()


    # =========================================================
    # EMPLOYEE COUNTS
    # =========================================================
    total_employees = Employee.query.count()

    active_employees = Employee.query.filter(
        Employee.account_status.in_([
            AccountStatus.ACTIVE,
            AccountStatus.ONBOARDED
        ])
    ).count()

    blocked_employees = Employee.query.filter_by(
        account_status=AccountStatus.BLOCKED
    ).count()

    # Disabled is currently not included because your
    # AccountStatus enum does not contain DISABLED.
    disabled_employees = 0

    offboarded_employees = Employee.query.filter_by(
        account_status=AccountStatus.OFFBOARDED
    ).count()


    # =========================================================
    # TICKET COUNTS
    # =========================================================
    open_tickets = Ticket.query.filter(
        Ticket.status.in_([
            TicketStatus.OPEN
        ])
    ).count()

    assigned_tickets = Ticket.query.filter(
        Ticket.status.in_([
            TicketStatus.ASSIGNED,
            TicketStatus.IN_PROGRESS
        ])
    ).count()

    closed_tickets = Ticket.query.filter(
        Ticket.status.in_([
            TicketStatus.RESOLVED,
            TicketStatus.CLOSED
        ])
    ).count()


    # =========================================================
    # VENDOR REPAIR COUNTS
    # =========================================================
    vendor_tickets = VendorRepairTicket.query.filter(
        VendorRepairTicket.repair_status.in_([
            'Sent',
            'In Repair'
        ])
    ).count()


    # =========================================================
    # RECENT ACTIVITIES
    # =========================================================
    recent_activities = (
        AuditLog.query
        .order_by(AuditLog.timestamp.desc())
        .limit(7)
        .all()
    )

    recently_assigned = (
        AssetAssignmentHistory.query
        .filter_by(action='Assigned')
        .order_by(AssetAssignmentHistory.timestamp.desc())
        .limit(5)
        .all()
    )

    recent_tickets = (
        Ticket.query
        .order_by(Ticket.created_at.desc())
        .limit(5)
        .all()
    )

    pending_repairs = (
        VendorRepairTicket.query
        .filter(
            VendorRepairTicket.repair_status.in_([
                'Sent',
                'In Repair'
            ])
        )
        .order_by(VendorRepairTicket.sent_date.desc())
        .limit(5)
        .all()
    )


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


# =============================================================
# LIVE DASHBOARD API
# =============================================================
@dashboard_bp.route('/dashboard/api/metrics')
@login_required
def get_metrics_json():
    """
    Returns live dashboard data for AJAX / Chart.js.

    This endpoint is used by dashboard charts and
    automatic dashboard refresh.
    """

    # =========================================================
    # ASSET STATUS DISTRIBUTION
    # =========================================================

    available_count = Asset.query.filter_by(
        status=AssetStatus.AVAILABLE
    ).count()

    assigned_count = Asset.query.filter_by(
        status=AssetStatus.ASSIGNED
    ).count()

    repair_count = Asset.query.filter_by(
        status=AssetStatus.REPAIR
    ).count()

    asset_distribution = {
        'Available': available_count,
        'Assigned': assigned_count,
        'Under Repair': repair_count
    }


    # =========================================================
    # DEPARTMENT-WISE ASSET ALLOCATION
    # =========================================================
    #
    # Only assigned laptops are included here.
    # The department comes from the employee currently
    # assigned to the asset.
    #

    dept_assets_query = (
        db.session.query(
            Employee.department,
            func.count(Asset.id)
        )
        .join(
            Asset,
            Asset.assigned_employee_id == Employee.id
        )
        .filter(
            Asset.status == AssetStatus.ASSIGNED
        )
        .group_by(
            Employee.department
        )
        .order_by(
            func.count(Asset.id).desc()
        )
        .all()
    )

    dept_assets = {}

    for department, count in dept_assets_query:

        department_name = (
            department.strip()
            if department and department.strip()
            else 'Unknown'
        )

        dept_assets[department_name] = count


    # =========================================================
    # VENDOR-WISE ASSET ALLOCATION
    # =========================================================

    vendor_assets_query = (
        db.session.query(
            Vendor.name,
            func.count(Asset.id)
        )
        .join(
            Asset,
            Asset.vendor_id == Vendor.id
        )
        .group_by(
            Vendor.name
        )
        .order_by(
            func.count(Asset.id).desc()
        )
        .all()
    )

    vendor_assets = {}

    for vendor_name, count in vendor_assets_query:

        name = (
            vendor_name.strip()
            if vendor_name and vendor_name.strip()
            else 'Unknown'
        )

        vendor_assets[name] = count


    # =========================================================
    # TICKET STATUS DISTRIBUTION
    # =========================================================

    ticket_status_query = (
        db.session.query(
            Ticket.status,
            func.count(Ticket.id)
        )
        .group_by(
            Ticket.status
        )
        .all()
    )

    ticket_status = {}

    for status, count in ticket_status_query:

        status_name = (
            status.value
            if hasattr(status, 'value')
            else str(status)
        )

        ticket_status[status_name] = count


    # =========================================================
    # TICKET CATEGORY DISTRIBUTION
    # =========================================================

    ticket_category_query = (
        db.session.query(
            Ticket.category,
            func.count(Ticket.id)
        )
        .group_by(
            Ticket.category
        )
        .all()
    )

    ticket_category = {}

    for category, count in ticket_category_query:

        category_name = (
            category.value
            if hasattr(category, 'value')
            else str(category)
        )

        ticket_category[category_name] = count


    # =========================================================
    # CARD COUNTS
    # =========================================================

    total_assets = Asset.query.count()

    total_employees = Employee.query.count()

    active_employees = Employee.query.filter(
        Employee.account_status.in_([
            AccountStatus.ACTIVE,
            AccountStatus.ONBOARDED
        ])
    ).count()

    blocked_employees = Employee.query.filter_by(
        account_status=AccountStatus.BLOCKED
    ).count()

    # AccountStatus.DISABLED does not exist in the current enum.
    disabled_employees = 0

    offboarded_employees = Employee.query.filter_by(
        account_status=AccountStatus.OFFBOARDED
    ).count()


    open_tickets = Ticket.query.filter(
        Ticket.status.in_([
            TicketStatus.OPEN
        ])
    ).count()

    assigned_tickets = Ticket.query.filter(
        Ticket.status.in_([
            TicketStatus.ASSIGNED,
            TicketStatus.IN_PROGRESS
        ])
    ).count()

    closed_tickets = Ticket.query.filter(
        Ticket.status.in_([
            TicketStatus.RESOLVED,
            TicketStatus.CLOSED
        ])
    ).count()

    vendor_tickets = VendorRepairTicket.query.filter(
        VendorRepairTicket.repair_status.in_([
            'Sent',
            'In Repair'
        ])
    ).count()


    # =========================================================
    # FINAL JSON RESPONSE
    # =========================================================

    return jsonify({

        'cards': {

            'total_assets': total_assets,

            'assigned_assets': assigned_count,

            'available_assets': available_count,

            'repair_assets': repair_count,

            'total_employees': total_employees,

            'active_employees': active_employees,

            'blocked_employees': blocked_employees,

            'disabled_employees': disabled_employees,

            'offboarded_employees': offboarded_employees,

            'open_tickets': open_tickets,

            'assigned_tickets': assigned_tickets,

            'closed_tickets': closed_tickets,

            'vendor_tickets': vendor_tickets
        },

        'charts': {

            'asset_distribution': asset_distribution,

            'dept_assets': dept_assets,

            'vendor_assets': vendor_assets,

            'ticket_status': ticket_status,

            'ticket_category': ticket_category
        }
    })
