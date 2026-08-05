import click
from flask.cli import with_appcontext
from app.extensions import db
from app.models.user import User, Role

def register_commands(app):
    @app.cli.command('init-db')
    @with_appcontext
    def init_db():
        """Initialize database tables cleanly with zero records."""
        click.echo("Creating database tables...")
        db.create_all()
        click.echo("Database tables created successfully! All tables are empty.")

    @app.cli.command('create-admin')
    @click.option('--username', default='admin', help='Admin username')
    @click.option('--email', default='admin@company.com', help='Admin email address')
    @click.option('--password', default='admin123', help='Admin password')
    @click.option('--full-name', default='Enterprise Super Admin', help='Full name of admin user')
    @click.option('--department', default='IT Governance', help='Department of admin user')
    @with_appcontext
    def create_admin(username, email, password, full_name, department):
        """Optionally create an initial Super Admin account for production system setup."""
        db.create_all()
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            click.echo(f"User with username '{username}' or email '{email}' already exists.")
            return

        admin = User(
            username=username,
            email=email,
            full_name=full_name,
            role=Role.SUPER_ADMIN,
            department=department
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Super Admin account '{username}' ({email}) created successfully!")
