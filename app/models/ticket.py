from datetime import datetime
from app.extensions import db

class TicketCategory:
    LAPTOP = 'Laptop'
    OUTLOOK = 'Outlook'
    PASSWORD_RESET = 'Password Reset'
    SOFTWARE = 'Software'
    HARDWARE = 'Hardware'
    VPN = 'VPN'
    PRINTER = 'Printer'
    NETWORK = 'Network'
    OTHER = 'Other'
    
    CHOICES = [LAPTOP, OUTLOOK, PASSWORD_RESET, SOFTWARE, HARDWARE, VPN, PRINTER, NETWORK, OTHER]

class TicketPriority:
    LOW = 'Low'
    MEDIUM = 'Medium'
    HIGH = 'High'
    CRITICAL = 'Critical'
    
    CHOICES = [LOW, MEDIUM, HIGH, CRITICAL]

class TicketStatus:
    OPEN = 'Open'
    ASSIGNED = 'Assigned'
    IN_PROGRESS = 'In Progress'
    WAITING_FOR_USER = 'Waiting for User'
    WAITING_FOR_VENDOR = 'Waiting for Vendor'
    RESOLVED = 'Resolved'
    CLOSED = 'Closed'
    
    CHOICES = [OPEN, ASSIGNED, IN_PROGRESS, WAITING_FOR_USER, WAITING_FOR_VENDOR, RESOLVED, CLOSED]

class Ticket(db.Model):
    __tablename__ = 'tickets'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    subject = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    department = db.Column(db.String(100), nullable=True)
    
    category = db.Column(db.String(50), nullable=False, default=TicketCategory.OTHER, index=True)
    priority = db.Column(db.String(30), nullable=False, default=TicketPriority.MEDIUM, index=True)
    status = db.Column(db.String(30), nullable=False, default=TicketStatus.OPEN, index=True)
    
    assigned_engineer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    vendor_repair_ticket_id = db.Column(db.Integer, db.ForeignKey('vendor_repair_tickets.id'), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)
    resolution_time_hours = db.Column(db.Float, nullable=True)

    # Relationships
    comments = db.relationship('TicketComment', backref='ticket', lazy='dynamic', cascade='all, delete-orphan')
    attachments = db.relationship('TicketAttachment', backref='ticket', lazy='dynamic', cascade='all, delete-orphan')
    vendor_repair_ticket = db.relationship('VendorRepairTicket', backref='tickets')

    def calculate_resolution_time(self):
        if self.closed_at and self.created_at:
            delta = self.closed_at - self.created_at
            return round(delta.total_seconds() / 3600.0, 2)
        return None

    def __repr__(self):
        return f'<Ticket {self.ticket_id} - {self.subject} ({self.status})>'


class TicketComment(db.Model):
    __tablename__ = 'ticket_comments'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    author_name = db.Column(db.String(120), nullable=False)
    comment_text = db.Column(db.Text, nullable=False)
    is_internal = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id])

    def __repr__(self):
        return f'<TicketComment #{self.id} by {self.author_name}>'


class TicketAttachment(db.Model):
    __tablename__ = 'ticket_attachments'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<TicketAttachment {self.filename}>'
