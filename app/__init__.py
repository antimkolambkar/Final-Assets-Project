import os
from flask import Flask
from config import Config
from app.extensions import db, login_manager, csrf
from app.models.user import User


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register Blueprints
    from app.blueprints.auth import auth_bp
    from app.blueprints.dashboard import dashboard_bp
    from app.blueprints.employees import employees_bp
    from app.blueprints.assets import assets_bp
    from app.blueprints.tickets import tickets_bp
    from app.blueprints.vendors import vendors_bp
    from app.blueprints.reports import reports_bp
    from app.blueprints.audit import audit_bp
    from app.blueprints.settings import settings_bp
    from app.blueprints.imports import import_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(assets_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(vendors_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(import_bp)

    # Register CLI commands
    from app.commands import register_commands
    register_commands(app)

        with app.app_context():
        db.create_all()

        from app.models.user import User, Role

        if User.query.count() == 0:
            admin = User(
                username="admin",
                email="admin@company.com",
                full_name="System Administrator",
                role=Role.SUPER_ADMIN,
                department="IT Support",
                is_active=True
            )
            admin.set_password("Admin@123")

            db.session.add(admin)
            db.session.commit()

            print("Default Super Administrator created.")

    # Context processors
    @app.context_processor
    def inject_global_context():
        from app.models.ticket import TicketStatus
        from app.models.ticket import Ticket

        open_ticket_count = 0
        try:
            open_ticket_count = Ticket.query.filter(
                Ticket.status == TicketStatus.OPEN
            ).count()
        except Exception:
            pass

        return dict(global_open_ticket_count=open_ticket_count)

    return app
