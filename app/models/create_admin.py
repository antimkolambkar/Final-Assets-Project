from app import create_app
from app.extensions import db
from app.models.user import User, Role

app = create_app()

with app.app_context():
    existing = User.query.filter_by(email="admin@company.com").first()

    if existing:
        print("Admin user already exists.")
    else:
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

        print("=================================")
        print("Super Administrator created!")
        print("Username : admin")
        print("Email    : admin@company.com")
        print("Password : Admin@123")
        print("=================================")