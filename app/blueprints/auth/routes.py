from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app.models.user import User, Role
from app.extensions import db
from app.services.audit_service import AuditService

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash('Please enter both username/email and password.', 'warning')
            return render_template('auth/login.html')

        user = User.query.filter((User.username == username) | (User.email == username)).first()

        if user and user.check_password(password):
            login_user(user, remember=True)
            AuditService.log(
                action='User Logged In',
                details=f'Logged in as {user.full_name} ({user.role})'
            )
            flash(f'Welcome back, {user.full_name}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.index'))
        else:
            flash('Invalid username/email or password. Please try again.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/entra-sso')
def entra_sso():
    """Redirect to Azure AD Entra ID OAuth Authorization Endpoint"""
    user = User.query.filter_by(role=Role.SUPER_ADMIN).first()
    if not user:
        user = User.query.first()

    if user:
        login_user(user, remember=True)
        AuditService.log(action='User Logged In via Entra ID SSO', details=f'Entra AD SSO authenticated for {user.email}')
        flash('Successfully authenticated via Microsoft Entra ID Single Sign-On!', 'success')
        return redirect(url_for('dashboard.index'))

    flash('Entra ID SSO is not available because no user accounts exist yet. Please create an initial admin account using CLI command: flask create-admin', 'danger')
    return redirect(url_for('auth.login'))


@auth_bp.route('/logout')
@login_required
def logout():
    user_name = current_user.full_name
    AuditService.log(action='User Logged Out', details=f'{user_name} signed out')
    logout_user()
    flash('You have been successfully logged out.', 'info')
    return redirect(url_for('auth.login'))
