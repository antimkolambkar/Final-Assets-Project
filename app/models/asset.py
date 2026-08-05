from datetime import datetime
from app.extensions import db

class AssetStatus:
    AVAILABLE = 'Available'
    ASSIGNED = 'Assigned'
    REPAIR = 'Repair'

class Asset(db.Model):
    __tablename__ = 'assets'

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    brand = db.Column(db.String(100), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    serial_number = db.Column(db.String(100), unique=True, nullable=False, index=True)
    processor = db.Column(db.String(100), nullable=False)
    ram = db.Column(db.String(50), nullable=False)
    ssd = db.Column(db.String(50), nullable=False)
    
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=True)
    status = db.Column(db.String(30), nullable=False, default=AssetStatus.AVAILABLE, index=True)
    
    assigned_employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    assignment_date = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    assignment_history = db.relationship('AssetAssignmentHistory', 
                                          foreign_keys='AssetAssignmentHistory.asset_id',
                                          backref='asset', 
                                          lazy='dynamic', 
                                          cascade='all, delete-orphan')
    repair_tickets = db.relationship('VendorRepairTicket', backref='asset', lazy='dynamic')

    @property
    def assigned_user_name(self):
        """Returns the assigned Employee Name if assigned, else 'N/A'"""
        if self.assigned_employee:
            return self.assigned_employee.name
        return 'N/A'

    @property
    def assigned_employee_details(self):
        if self.assigned_employee:
            return {
                'id': self.assigned_employee.id,
                'employee_id': self.assigned_employee.employee_id,
                'name': self.assigned_employee.name,
                'email': self.assigned_employee.email,
                'department': self.assigned_employee.department
            }
        return None

    def __repr__(self):
        return f'<Asset {self.asset_id} - {self.brand} {self.model} ({self.status})>'


class AssetAssignmentHistory(db.Model):
    __tablename__ = 'asset_assignment_history'

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    employee_name = db.Column(db.String(120), nullable=True)
    action = db.Column(db.String(50), nullable=False) # Assigned, Returned, Replaced, Sent to Repair, Repaired
    
    # For multi-replacement tracking:
    old_asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=True)
    new_asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=True)
    replacement_reason = db.Column(db.Text, nullable=True)
    
    notes = db.Column(db.Text, nullable=True)
    performed_by = db.Column(db.String(100), nullable=True) # User/Admin name
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relationships for replacement tracking
    old_asset = db.relationship('Asset', foreign_keys=[old_asset_id])
    new_asset = db.relationship('Asset', foreign_keys=[new_asset_id])
    employee = db.relationship('Employee', foreign_keys=[employee_id])

    def __repr__(self):
        return f'<AssetAssignmentHistory {self.action} for Asset #{self.asset_id} by {self.performed_by}>'
