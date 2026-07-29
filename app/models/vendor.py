from datetime import datetime
from app.extensions import db

class RepairStatus:
    SENT = 'Sent'
    IN_REPAIR = 'In Repair'
    REPAIRED = 'Repaired'
    RETURNED = 'Returned'

class Vendor(db.Model):
    __tablename__ = 'vendors'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    contact_person = db.Column(db.String(120), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    address = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    assets = db.relationship('Asset', backref='vendor', lazy='dynamic')
    repair_tickets = db.relationship('VendorRepairTicket', backref='vendor', lazy='dynamic')

    def __repr__(self):
        return f'<Vendor {self.name}>'


class VendorRepairTicket(db.Model):
    __tablename__ = 'vendor_repair_tickets'

    id = db.Column(db.Integer, primary_key=True)
    vendor_ticket_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False)
    repair_status = db.Column(db.String(30), nullable=False, default=RepairStatus.SENT, index=True)
    sent_date = db.Column(db.DateTime, default=datetime.utcnow)
    returned_date = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<VendorRepairTicket {self.vendor_ticket_number} - {self.repair_status}>'
