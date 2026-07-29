from datetime import datetime
from app.extensions import db
from app.models.ticket import Ticket, TicketCategory, TicketPriority, TicketStatus, TicketComment, TicketAttachment
from app.models.employee import Employee
from app.models.user import User
from app.services.audit_service import AuditService

class TicketService:
    @staticmethod
    def generate_ticket_id():
        year = datetime.utcnow().strftime('%Y')
        count = Ticket.query.count() + 1
        return f"TKT-{year}-{count:04d}"

    @staticmethod
    def create_ticket_from_email(sender_email, subject, description, category=TicketCategory.OTHER, priority=TicketPriority.MEDIUM):
        # Find employee by email
        employee = Employee.query.filter_by(email=sender_email).first()
        if not employee:
            # Fallback or create unassigned employee reference
            employee = Employee(
                employee_id=f"TEMP-{datetime.utcnow().strftime('%M%S')}",
                name=sender_email.split('@')[0].replace('.', ' ').title(),
                email=sender_email,
                department='General',
                account_status='Active'
            )
            db.session.add(employee)
            db.session.flush()

        ticket = Ticket(
            ticket_id=TicketService.generate_ticket_id(),
            subject=subject,
            description=description,
            employee_id=employee.id,
            department=employee.department,
            category=category,
            priority=priority,
            status=TicketStatus.OPEN,
            created_at=datetime.utcnow()
        )
        db.session.add(ticket)
        db.session.commit()

        # Log audit & auto acknowledgement
        AuditService.log(
            action='Ticket Created via Email',
            entity_type='Ticket',
            entity_id=ticket.ticket_id,
            details=f'Ticket {ticket.ticket_id} created for employee {employee.name} ({employee.email})'
        )

        return ticket

    @staticmethod
    def assign_engineer(ticket_id_val, engineer_id, assigned_by_name):
        ticket = Ticket.query.filter_by(ticket_id=ticket_id_val).first()
        if not ticket:
            return False, "Ticket not found"

        engineer = User.query.get(engineer_id)
        if not engineer:
            return False, "Engineer not found"

        ticket.assigned_engineer_id = engineer.id
        if ticket.status == TicketStatus.OPEN:
            ticket.status = TicketStatus.ASSIGNED

        db.session.commit()

        AuditService.log(
            action='Ticket Assigned',
            entity_type='Ticket',
            entity_id=ticket.ticket_id,
            details=f'Ticket {ticket.ticket_id} assigned to IT Engineer {engineer.full_name} by {assigned_by_name}'
        )

        return True, f"Ticket assigned to {engineer.full_name}"

    @staticmethod
    def update_status(ticket_id_val, new_status, updated_by_name):
        ticket = Ticket.query.filter_by(ticket_id=ticket_id_val).first()
        if not ticket:
            return False, "Ticket not found"

        old_status = ticket.status
        ticket.status = new_status

        if new_status in [TicketStatus.RESOLVED, TicketStatus.CLOSED] and not ticket.closed_at:
            ticket.closed_at = datetime.utcnow()
            ticket.resolution_time_hours = ticket.calculate_resolution_time()

        db.session.commit()

        AuditService.log(
            action='Ticket Status Updated',
            entity_type='Ticket',
            entity_id=ticket.ticket_id,
            details=f'Ticket {ticket.ticket_id} status changed from {old_status} to {new_status} by {updated_by_name}'
        )

        return True, f"Status updated to {new_status}"

    @staticmethod
    def add_comment(ticket_id_val, author_name, comment_text, user_id=None, is_internal=False):
        ticket = Ticket.query.filter_by(ticket_id=ticket_id_val).first()
        if not ticket:
            return False, "Ticket not found"

        comment = TicketComment(
            ticket_id=ticket.id,
            user_id=user_id,
            author_name=author_name,
            comment_text=comment_text,
            is_internal=is_internal,
            created_at=datetime.utcnow()
        )
        db.session.add(comment)
        db.session.commit()

        return True, comment
