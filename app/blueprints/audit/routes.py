from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from app.models.audit import AuditLog
from app.models.user import Role

audit_bp = Blueprint('audit', __name__, url_prefix='/audit')

@audit_bp.route('/')
@login_required
def index():
    if not current_user.is_super_admin:
        # IT Admins and Engineers cannot access audit logs if super admin restricted
        # Super Admins only
        pass

    search_q = request.args.get('q', '').strip()
    action_filter = request.args.get('action', '').strip()
    page = request.args.get('page', 1, type=int)

    query = AuditLog.query

    if search_q:
        query = query.filter(
            (AuditLog.user_name.ilike(f'%{search_q}%')) |
            (AuditLog.action.ilike(f'%{search_q}%')) |
            (AuditLog.details.ilike(f'%{search_q}%')) |
            (AuditLog.ip_address.ilike(f'%{search_q}%'))
        )

    if action_filter:
        query = query.filter_by(action=action_filter)

    pagination = query.order_by(AuditLog.timestamp.desc()).paginate(page=page, per_page=15, error_out=False)
    logs = pagination.items

    actions = [a[0] for a in AuditLog.query.with_entities(AuditLog.action).distinct().all() if a[0]]

    return render_template('audit/index.html', logs=logs, pagination=pagination, search_q=search_q, action_filter=action_filter, actions=actions)
