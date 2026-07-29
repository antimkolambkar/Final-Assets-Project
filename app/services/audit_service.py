from flask import request
from flask_login import current_user
from app.extensions import db
from app.models.audit import AuditLog

class AuditService:
    @staticmethod
    def log(action, entity_type=None, entity_id=None, details=None, user_id=None, user_name=None, user_role=None):
        try:
            ip_addr = request.remote_addr if request else '127.0.0.1'
        except Exception:
            ip_addr = '127.0.0.1'

        if not user_name:
            if current_user and current_user.is_authenticated:
                user_id = current_user.id
                user_name = current_user.full_name
                user_role = current_user.role
            else:
                user_name = 'System / Automated Sync'
                user_role = 'System'

        audit_entry = AuditLog(
            user_id=user_id,
            user_name=user_name,
            user_role=user_role,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            details=details,
            ip_address=ip_addr
        )
        db.session.add(audit_entry)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return audit_entry
