import click
from datetime import datetime, timedelta
from flask.cli import with_appcontext
from app.extensions import db
from app.models.user import User, Role
from app.models.vendor import Vendor, VendorRepairTicket, RepairStatus
from app.models.employee import Employee, AccountStatus
from app.models.asset import Asset, AssetStatus, AssetAssignmentHistory
from app.models.ticket import Ticket, TicketCategory, TicketPriority, TicketStatus, TicketComment
from app.services.graph_service import MicrosoftGraphService

def register_commands(app):
    @app.cli.command('seed-db')
    @with_appcontext
    def seed_db():
        """Seed initial database tables with enterprise roles, vendors, employees, assets, and tickets."""
        click.echo("Initializing database tables...")
        db.create_all()

        click.echo("Seeding Users & Roles...")
        # Super Admin
        admin = User.query.filter_by(email='admin@company.com').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@company.com',
                full_name='Enterprise Super Admin',
                role=Role.SUPER_ADMIN,
                department='IT Governance'
            )
            admin.set_password('admin123')
            db.session.add(admin)

        # IT Admin
        it_admin = User.query.filter_by(email='itadmin@company.com').first()
        if not it_admin:
            it_admin = User(
                username='itadmin',
                email='itadmin@company.com',
                full_name='Suresh Kumar (IT Admin)',
                role=Role.IT_ADMIN,
                department='IT Operations'
            )
            it_admin.set_password('admin123')
            db.session.add(it_admin)

        # IT Engineer
        it_eng = User.query.filter_by(email='engineer@company.com').first()
        if not it_eng:
            it_eng = User(
                username='engineer',
                email='engineer@company.com',
                full_name='Anish Verma (IT Engineer)',
                role=Role.IT_ENGINEER,
                department='Helpdesk Support'
            )
            it_eng.set_password('admin123')
            db.session.add(it_eng)

        db.session.commit()

        click.echo("Seeding Default Enterprise Vendors...")
        default_vendors = [
            {'name': 'Techvity', 'contact': 'Rajesh Sharma', 'email': 'support@techvity.com', 'phone': '+91 98765 43210', 'address': 'Tech Park, Bangalore'},
            {'name': 'Spurge', 'contact': 'Amit Patel', 'email': 'sales@spurge.com', 'phone': '+91 98123 45678', 'address': 'Business Hub, Mumbai'},
            {'name': 'WBG', 'contact': 'David Miller', 'email': 'service@wbg.com', 'phone': '+1 800 555 0199', 'address': 'Financial Center, New York'},
            {'name': 'Exalogic Bangalore', 'contact': 'Suresh Rao', 'email': 'it.blr@exalogic.com', 'phone': '+91 80 4123 8888', 'address': 'Electronic City, Bangalore'},
            {'name': 'Exalogic Dubai', 'contact': 'Tariq Al-Mansoor', 'email': 'it.dxb@exalogic.com', 'phone': '+971 4 391 0000', 'address': 'Internet City, Dubai'}
        ]

        vendor_objs = {}
        for vdata in default_vendors:
            v = Vendor.query.filter_by(name=vdata['name']).first()
            if not v:
                v = Vendor(
                    name=vdata['name'],
                    contact_person=vdata['contact'],
                    email=vdata['email'],
                    phone=vdata['phone'],
                    address=vdata['address']
                )
                db.session.add(v)
                db.session.flush()
            vendor_objs[vdata['name']] = v

        db.session.commit()

        click.echo("Synchronizing Microsoft Entra ID Employees...")
        MicrosoftGraphService.sync_entra_employees()

        click.echo("Seeding Enterprise IT Assets & Multi-Replacement History...")
        techvity = vendor_objs['Techvity']
        spurge = vendor_objs['Spurge']
        ex_dxb = vendor_objs['Exalogic Dubai']
        ex_blr = vendor_objs['Exalogic Bangalore']

        emp_rahul = Employee.query.filter_by(employee_id='EMP-1001').first()
        emp_priya = Employee.query.filter_by(employee_id='EMP-1002').first()
        emp_amit = Employee.query.filter_by(employee_id='EMP-1003').first()
        emp_arjun = Employee.query.filter_by(employee_id='EMP-1008').first()

        sample_assets = [
            {
                'asset_id': 'AST-2026-0001',
                'brand': 'Dell',
                'model': 'Latitude 7420',
                'serial_number': 'DL-7420-9981',
                'processor': 'Intel Core i7-1185G7',
                'ram': '16 GB',
                'ssd': '512 GB SSD',
                'vendor_id': techvity.id,
                'status': AssetStatus.ASSIGNED,
                'assigned_employee_id': emp_rahul.id if emp_rahul else None,
                'assignment_date': datetime.utcnow() - timedelta(days=120)
            },
            {
                'asset_id': 'AST-2026-0002',
                'brand': 'Lenovo',
                'model': 'ThinkPad X1 Carbon Gen 9',
                'serial_number': 'LNV-X1C-4412',
                'processor': 'Intel Core i7-1165G7',
                'ram': '32 GB',
                'ssd': '1 TB SSD',
                'vendor_id': spurge.id,
                'status': AssetStatus.ASSIGNED,
                'assigned_employee_id': emp_priya.id if emp_priya else None,
                'assignment_date': datetime.utcnow() - timedelta(days=90)
            },
            {
                'asset_id': 'AST-2026-0003',
                'brand': 'Apple',
                'model': 'MacBook Pro 16"',
                'serial_number': 'APL-MBP16-8821',
                'processor': 'Apple M1 Max 10-core',
                'ram': '32 GB Unified',
                'ssd': '1 TB SSD',
                'vendor_id': ex_dxb.id,
                'status': AssetStatus.ASSIGNED,
                'assigned_employee_id': emp_amit.id if emp_amit else None,
                'assignment_date': datetime.utcnow() - timedelta(days=45)
            },
            {
                'asset_id': 'AST-2026-0004',
                'brand': 'HP',
                'model': 'EliteBook 840 G8',
                'serial_number': 'HP-EB840-3311',
                'processor': 'Intel Core i5-1135G7',
                'ram': '16 GB',
                'ssd': '256 GB SSD',
                'vendor_id': ex_blr.id,
                'status': AssetStatus.AVAILABLE,
                'assigned_employee_id': None,
                'assignment_date': None
            },
            {
                'asset_id': 'AST-2026-0005',
                'brand': 'Dell',
                'model': 'XPS 15 9510',
                'serial_number': 'DL-XPS15-7712',
                'processor': 'Intel Core i9-11900H',
                'ram': '32 GB',
                'ssd': '1 TB SSD',
                'vendor_id': techvity.id,
                'status': AssetStatus.REPAIR,
                'assigned_employee_id': None,
                'assignment_date': None
            },
            {
                'asset_id': 'AST-2026-0006',
                'brand': 'Lenovo',
                'model': 'ThinkPad T14s Gen 2',
                'serial_number': 'LNV-T14S-5529',
                'processor': 'AMD Ryzen 7 PRO 5850U',
                'ram': '16 GB',
                'ssd': '512 GB SSD',
                'vendor_id': spurge.id,
                'status': AssetStatus.ASSIGNED,
                'assigned_employee_id': emp_arjun.id if emp_arjun else None,
                'assignment_date': datetime.utcnow() - timedelta(days=15)
            }
        ]

        asset_objs = {}
        for adata in sample_assets:
            ast = Asset.query.filter_by(serial_number=adata['serial_number']).first()
            if not ast:
                ast = Asset(
                    asset_id=adata['asset_id'],
                    brand=adata['brand'],
                    model=adata['model'],
                    serial_number=adata['serial_number'],
                    processor=adata['processor'],
                    ram=adata['ram'],
                    ssd=adata['ssd'],
                    vendor_id=adata['vendor_id'],
                    status=adata['status'],
                    assigned_employee_id=adata['assigned_employee_id'],
                    assignment_date=adata['assignment_date']
                )
                db.session.add(ast)
                db.session.flush()

                # Add initial assignment history if assigned
                if ast.assigned_employee:
                    hist = AssetAssignmentHistory(
                        asset_id=ast.id,
                        employee_id=ast.assigned_employee.id,
                        employee_name=ast.assigned_employee.name,
                        action='Assigned',
                        notes=f'Initial allocation to {ast.assigned_employee.name}',
                        performed_by='Suresh Kumar (IT Admin)'
                    )
                    db.session.add(hist)
            asset_objs[adata['asset_id']] = ast

        db.session.commit()

        # Add sample Multi-Replacement history record for demonstration
        if 'AST-2026-0001' in asset_objs and 'AST-2026-0004' in asset_objs and emp_rahul:
            ast_1 = asset_objs['AST-2026-0001']
            ast_4 = asset_objs['AST-2026-0004']
            repl_hist = AssetAssignmentHistory.query.filter_by(action='Replaced').first()
            if not repl_hist:
                repl_hist = AssetAssignmentHistory(
                    asset_id=ast_1.id,
                    employee_id=emp_rahul.id,
                    employee_name=emp_rahul.name,
                    action='Replaced',
                    old_asset_id=ast_4.id,
                    new_asset_id=ast_1.id,
                    replacement_reason='Upgraded to Intel Core i7 with 16GB RAM for high performance development tasks',
                    notes=f'Swapped old HP EliteBook ({ast_4.asset_id}) with new Dell Latitude ({ast_1.asset_id}) for {emp_rahul.name}',
                    performed_by='Suresh Kumar (IT Admin)',
                    timestamp=datetime.utcnow() - timedelta(days=30)
                )
                db.session.add(repl_hist)

        click.echo("Seeding Helpdesk Tickets & Vendor Repair Records...")
        if emp_priya and it_eng:
            tkt1 = Ticket.query.filter_by(ticket_id='TKT-2026-0001').first()
            if not tkt1:
                tkt1 = Ticket(
                    ticket_id='TKT-2026-0001',
                    subject='Outlook Sync Failure on MacOS',
                    description='Unable to send or receive emails via Outlook desktop client. Authentication error prompt keeps appearing.',
                    employee_id=emp_priya.id,
                    department=emp_priya.department,
                    category=TicketCategory.OUTLOOK,
                    priority=TicketPriority.HIGH,
                    status=TicketStatus.IN_PROGRESS,
                    assigned_engineer_id=it_eng.id,
                    created_at=datetime.utcnow() - timedelta(days=2)
                )
                db.session.add(tkt1)
                db.session.flush()

                c1 = TicketComment(
                    ticket_id=tkt1.id,
                    user_id=it_eng.id,
                    author_name=it_eng.full_name,
                    comment_text='Inspected OAuth token cache. Cleared Keychain credentials and re-authenticated M365 account.',
                    is_internal=False,
                    created_at=datetime.utcnow() - timedelta(days=1)
                )
                db.session.add(c1)

        if emp_rahul:
            tkt2 = Ticket.query.filter_by(ticket_id='TKT-2026-0002').first()
            if not tkt2:
                tkt2 = Ticket(
                    ticket_id='TKT-2026-0002',
                    subject='GlobalProtect VPN Access Request for Dubai Project',
                    description='Require corporate VPN profile enabled for accessing Dubai regional staging servers.',
                    employee_id=emp_rahul.id,
                    department=emp_rahul.department,
                    category=TicketCategory.VPN,
                    priority=TicketPriority.MEDIUM,
                    status=TicketStatus.OPEN,
                    created_at=datetime.utcnow() - timedelta(hours=5)
                )
                db.session.add(tkt2)

        # Vendor Repair Ticket for AST-2026-0005
        if 'AST-2026-0005' in asset_objs:
            ast_rep = asset_objs['AST-2026-0005']
            vrep = VendorRepairTicket.query.filter_by(asset_id=ast_rep.id).first()
            if not vrep:
                vrep = VendorRepairTicket(
                    vendor_ticket_number='VNR-2026-0001',
                    asset_id=ast_rep.id,
                    vendor_id=techvity.id,
                    repair_status=RepairStatus.IN_REPAIR,
                    sent_date=datetime.utcnow() - timedelta(days=5),
                    notes='Screen backlight flickering and battery drain issue under diagnostics at Techvity service center.'
                )
                db.session.add(vrep)

        db.session.commit()
        click.echo("Database Seeding Completed Successfully!")
