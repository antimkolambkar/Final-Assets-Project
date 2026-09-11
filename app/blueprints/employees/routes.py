from datetime import datetime

from app.extensions import db


class AccountStatus:
    ONBOARDED = 'Onboarded'
    ACTIVE = 'Active'
    BLOCKED = 'Blocked'
    DISABLED = 'Disabled'
    OFFBOARDED = 'Offboarded'


class Employee(db.Model):
    __tablename__ = 'employees'

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    employee_id = db.Column(
        db.String(50),
        unique=True,
        nullable=False,
        index=True
    )

    name = db.Column(
        db.String(120),
        nullable=False,
        index=True
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=True,
        index=True
    )

    department = db.Column(
        db.String(100),
        nullable=True,
        index=True
    )

    designation = db.Column(
        db.String(100),
        nullable=True
    )

    manager = db.Column(
        db.String(120),
        nullable=True
    )

    office_location = db.Column(
        db.String(100),
        nullable=True
    )

    account_status = db.Column(
        db.String(30),
        nullable=False,
        default=AccountStatus.ACTIVE,
        index=True
    )

    # =========================================================
    # STATUS DATES
    # =========================================================

    onboarded_date = db.Column(
        db.Date,
        nullable=True
    )

    active_date = db.Column(
        db.Date,
        nullable=True
    )

    blocked_date = db.Column(
        db.Date,
        nullable=True
    )

    disabled_date = db.Column(
        db.Date,
        nullable=True
    )

    offboarded_date = db.Column(
        db.Date,
        nullable=True
    )

    # =========================================================
    # SYSTEM DATES
    # =========================================================

    last_synced_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    # =========================================================
    # RELATIONSHIPS
    # =========================================================

    assigned_assets = db.relationship(
        'Asset',
        backref='assigned_employee',
        lazy='dynamic'
    )

    tickets = db.relationship(
        'Ticket',
        backref='employee',
        lazy='dynamic'
    )

    # =========================================================
    # STATUS PROPERTIES
    # =========================================================

    @property
    def is_onboarded(self):
        return self.account_status == AccountStatus.ONBOARDED

    @property
    def is_active(self):
        return self.account_status == AccountStatus.ACTIVE

    @property
    def is_blocked(self):
        return self.account_status == AccountStatus.BLOCKED

    @property
    def is_disabled(self):
        return self.account_status == AccountStatus.DISABLED

    @property
    def is_offboarded(self):
        return self.account_status == AccountStatus.OFFBOARDED

    # =========================================================
    # REPRESENTATION
    # =========================================================

    def __repr__(self):
        return (
            f'<Employee {self.employee_id} - '
            f'{self.name} ({self.account_status})>'
        )
