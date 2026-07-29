from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db

class Role:
    SUPER_ADMIN = 'Super Administrator'
    IT_ADMIN = 'IT Administrator'
    IT_ENGINEER = 'IT Engineer'

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), nullable=False, default=Role.IT_ENGINEER)
    department = db.Column(db.String(100), default='IT Support')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    assigned_tickets = db.relationship('Ticket', backref='assigned_engineer', lazy='dynamic', foreign_keys='Ticket.assigned_engineer_id')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_super_admin(self):
        return self.role == Role.SUPER_ADMIN

    @property
    def is_it_admin(self):
        return self.role == Role.IT_ADMIN or self.role == Role.SUPER_ADMIN

    @property
    def is_it_engineer(self):
        return self.role == Role.IT_ENGINEER or self.role == Role.IT_ADMIN or self.role == Role.SUPER_ADMIN

    def can_manage_users(self):
        return self.is_super_admin

    def can_change_settings(self):
        return self.is_super_admin

    def can_delete_assets(self):
        return self.is_super_admin or self.is_it_admin

    def can_assign_tickets(self):
        return self.is_super_admin or self.is_it_admin

    def __repr__(self):
        return f'<User {self.username} - {self.role}>'
