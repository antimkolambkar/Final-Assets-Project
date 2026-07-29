from datetime import datetime
from app.extensions import db

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    user_name = db.Column(db.String(120), nullable=False, default='System')
    user_role = db.Column(db.String(50), nullable=True)
    
    action = db.Column(db.String(100), nullable=False, index=True)
    entity_type = db.Column(db.String(50), nullable=True, index=True)
    entity_id = db.Column(db.String(50), nullable=True)
    
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', foreign_keys=[user_id])

    def __repr__(self):
        return f'<AuditLog {self.action} by {self.user_name} at {self.timestamp}>'
