from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from app.models.user import User, Role
from app.extensions import db
from app.services.audit_service import AuditService

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

@settings_bp.route('/')
@login_required
def index():
    if not current_user.can_change_settings():
        flash('Access denied. Only Super Administrators can view system settings.', 'danger')
        return redirect(url_for('dashboard.index'))

    users = User.query.order_by(User.full_name.asc()).all()

    return render_template(
        'settings/index.html',
        users=users,
        roles=[Role.SUPER_ADMIN, Role.IT_ADMIN, Role.IT_ENGINEER],
        config=current_app.config
    )


@settings_bp.route('/users/add', methods=['POST'])
@login_required
def add_user():
    if not current_user.can_manage_users():
        flash('Access denied. Only Super Administrators can manage system users.', 'danger')
        return redirect(url_for('settings.index'))

    username = request.form.get('username', '').strip()
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip()
    role = request.form.get('role', Role.IT_ENGINEER)
    password = request.form.get('password', '').strip()

    if not all([username, full_name, email, password]):
        flash('All fields are required to create a system user.', 'danger')
        return redirect(url_for('settings.index'))

    existing = User.query.filter((User.username == username) | (User.email == email)).first()
    if existing:
        flash(f'User with username/email already exists.', 'warning')
        return redirect(url_for('settings.index'))

    user = User(username=username, full_name=full_name, email=email, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    AuditService.log(
        action='User Account Created',
        entity_type='User',
        entity_id=username,
        details=f'Super Admin created system account for {full_name} ({role})'
    )

    flash(f'System user {full_name} ({role}) created successfully!', 'success')
    return redirect(url_for('settings.index'))


@settings_bp.route('/users/<int:user_id>/role', methods=['POST'])
@login_required
def update_user_role(user_id):
    if not current_user.can_manage_users():
        flash('Access denied.', 'danger')
        return redirect(url_for('settings.index'))

    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role')
    old_role = user.role

    user.role = new_role
    db.session.commit()

    AuditService.log(
        action='User Role Changed',
        entity_type='User',
        entity_id=user.username,
        details=f'Changed role for {user.full_name} from {old_role} to {new_role}'
    )

    flash(f'Role for {user.full_name} updated to {new_role}.', 'success')
    return redirect(url_for('settings.index'))
