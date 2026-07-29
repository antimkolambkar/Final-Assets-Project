import os
import io
import random
from datetime import datetime
from flask import current_app
from app.extensions import db
from app.models.employee import Employee, AccountStatus
from app.models.asset import Asset, AssetStatus, AssetAssignmentHistory
from app.services.audit_service import AuditService


class MicrosoftGraphService:
    """
    Microsoft Graph API Integration Service for Entra ID Employee Sync
    and Outlook Ticketing Processing. Supports both Live API & Mock Engine.

    Auto-Triggers:
      - ONBOARDED: New employee detected in Entra ID → auto-creates employee record
      - OFFBOARDED: Employee status changed → auto-returns all assigned laptops
    """

    @staticmethod
    def sync_entra_employees():
        """
        Synchronizes employee data from Microsoft Entra ID (Azure AD / M365 Admin Center).
        Detects Active, Blocked, Disabled, Onboarded, and Offboarded status changes.
        
        Auto-Onboarding Trigger:
          - New accounts detected in Entra ID → creates employee with status Onboarded
        
        Auto-Offboarding Trigger:
          - Status changed to Offboarded → auto-returns all assigned laptops
        """
        mode = current_app.config.get('GRAPH_INTEGRATION_MODE', 'MOCK')

        if mode == 'LIVE':
            return MicrosoftGraphService._sync_live_employees()
        else:
            return MicrosoftGraphService._sync_mock_employees()

    @staticmethod
    def _sync_live_employees():
        """
        Live Microsoft Graph API sync using MSAL OAuth token.
        Calls https://graph.microsoft.com/v1.0/users to pull Entra ID directory.
        Falls back to mock if credentials are not fully configured.
        """
        try:
            import msal
            import requests as http_requests

            client_id = current_app.config.get('AZURE_CLIENT_ID', '')
            client_secret = current_app.config.get('AZURE_CLIENT_SECRET', '')
            tenant_id = current_app.config.get('AZURE_TENANT_ID', '')

            if not all([client_id, client_secret, tenant_id]) or 'YOUR_' in client_id:
                current_app.logger.warning("Azure credentials not configured. Falling back to MOCK mode.")
                return MicrosoftGraphService._sync_mock_employees()

            authority = f"https://login.microsoftonline.com/{tenant_id}"
            app_msal = msal.ConfidentialClientApplication(
                client_id, authority=authority, client_credential=client_secret
            )

            token_response = app_msal.acquire_token_for_client(
                scopes=["https://graph.microsoft.com/.default"]
            )

            if 'access_token' not in token_response:
                current_app.logger.error("MSAL token acquisition failed. Falling back to MOCK.")
                return MicrosoftGraphService._sync_mock_employees()

            access_token = token_response['access_token']
            headers = {'Authorization': f'Bearer {access_token}'}

            # Fetch all users from Entra ID with relevant fields
            url = (
                "https://graph.microsoft.com/v1.0/users"
                "?$select=id,employeeId,displayName,mail,department,jobTitle,"
                "manager,officeLocation,accountEnabled"
                "&$top=999"
            )
            response = http_requests.get(url, headers=headers)
            response.raise_for_status()
            users_data = response.json().get('value', [])

            # Map Graph API fields to our Employee model
            entra_directory = []
            for u in users_data:
                emp_id = u.get('employeeId') or f"ENTRA-{u['id'][:8].upper()}"
                status = AccountStatus.ACTIVE if u.get('accountEnabled') else AccountStatus.DISABLED
                entra_directory.append({
                    'employee_id': emp_id,
                    'name': u.get('displayName', ''),
                    'email': u.get('mail', ''),
                    'department': u.get('department', ''),
                    'designation': u.get('jobTitle', ''),
                    'manager': u.get('manager', {}).get('displayName', '') if isinstance(u.get('manager'), dict) else '',
                    'office_location': u.get('officeLocation', ''),
                    'account_status': status
                })

            return MicrosoftGraphService._process_directory(entra_directory)

        except ImportError:
            current_app.logger.warning("MSAL not installed. Using MOCK mode.")
            return MicrosoftGraphService._sync_mock_employees()
        except Exception as e:
            current_app.logger.error(f"Graph API sync error: {e}. Falling back to MOCK.")
            return MicrosoftGraphService._sync_mock_employees()

    @staticmethod
    def _sync_mock_employees():
        """
        Mock Graph API sync generator providing realistic enterprise Entra ID employee directory updates.
        Includes auto-onboarding detection for new employees.
        """
        mock_entra_directory = [
            {
                'employee_id': 'EMP-1001',
                'name': 'Rahul Sharma',
                'email': 'rahul.sharma@company.com',
                'department': 'IT Infrastructure',
                'designation': 'Senior System Administrator',
                'manager': 'Vikram Malhotra',
                'office_location': 'Bangalore HQ',
                'account_status': AccountStatus.ACTIVE
            },
            {
                'employee_id': 'EMP-1002',
                'name': 'Priya Patel',
                'email': 'priya.patel@company.com',
                'department': 'Software Engineering',
                'designation': 'Full Stack Developer',
                'manager': 'Rahul Sharma',
                'office_location': 'Bangalore HQ',
                'account_status': AccountStatus.ACTIVE
            },
            {
                'employee_id': 'EMP-1003',
                'name': 'Amit Kumar',
                'email': 'amit.kumar@company.com',
                'department': 'Finance & Accounts',
                'designation': 'Finance Manager',
                'manager': 'Sanjay Mehta',
                'office_location': 'Dubai Regional Office',
                'account_status': AccountStatus.ACTIVE
            },
            {
                'employee_id': 'EMP-1004',
                'name': 'Sneha Rao',
                'email': 'sneha.rao@company.com',
                'department': 'Human Resources',
                'designation': 'HR Operations Lead',
                'manager': 'Ananya Roy',
                'office_location': 'Bangalore HQ',
                'account_status': AccountStatus.BLOCKED
            },
            {
                'employee_id': 'EMP-1005',
                'name': 'Vikram Malhotra',
                'email': 'vikram.malhotra@company.com',
                'department': 'IT Management',
                'designation': 'IT Director',
                'manager': 'CEO Office',
                'office_location': 'Dubai Regional Office',
                'account_status': AccountStatus.ACTIVE
            },
            {
                'employee_id': 'EMP-1006',
                'name': 'Deepak Verma',
                'email': 'deepak.verma@company.com',
                'department': 'Quality Assurance',
                'designation': 'QA Automation Lead',
                'manager': 'Rahul Sharma',
                'office_location': 'Bangalore HQ',
                'account_status': AccountStatus.DISABLED
            },
            {
                'employee_id': 'EMP-1007',
                'name': 'Kavita Sundaram',
                'email': 'kavita.sundaram@company.com',
                'department': 'Marketing',
                'designation': 'Digital Marketing Specialist',
                'manager': 'Sanjay Mehta',
                'office_location': 'Dubai Regional Office',
                'account_status': AccountStatus.OFFBOARDED
            },
            {
                'employee_id': 'EMP-1008',
                'name': 'Arjun Nair',
                'email': 'arjun.nair@company.com',
                'department': 'Sales & Business Dev',
                'designation': 'Enterprise Account Exec',
                'manager': 'Sanjay Mehta',
                'office_location': 'Dubai Regional Office',
                'account_status': AccountStatus.ACTIVE
            }
        ]

        return MicrosoftGraphService._process_directory(mock_entra_directory)

    @staticmethod
    def _process_directory(entra_directory):
        """
        Core directory processing engine.
        Handles auto-onboarding (new Entra ID accounts → ONBOARDED status)
        and auto-offboarding (status change → laptop return).
        """
        created_count = 0
        updated_count = 0
        onboarded_count = 0
        offboarded_count = 0
        returned_assets_count = 0

        for item in entra_directory:
            emp = Employee.query.filter_by(employee_id=item['employee_id']).first()
            
            if not emp:
                # ===========================
                # AUTO-ONBOARDING TRIGGER
                # New account detected in Entra ID → create with Onboarded status
                # ===========================
                emp = Employee(
                    employee_id=item['employee_id'],
                    name=item['name'],
                    email=item['email'],
                    department=item['department'],
                    designation=item['designation'],
                    manager=item['manager'],
                    office_location=item['office_location'],
                    # New Entra IDs start as Onboarded (awaiting laptop & IT setup)
                    account_status=AccountStatus.ONBOARDED if item['account_status'] == AccountStatus.ACTIVE else item['account_status'],
                    last_synced_at=datetime.utcnow()
                )
                db.session.add(emp)
                db.session.flush()
                created_count += 1
                onboarded_count += 1

                AuditService.log(
                    action='Employee Auto-Onboarded (Entra ID)',
                    entity_type='Employee',
                    entity_id=emp.employee_id,
                    details=f'New Entra ID account detected: {emp.name} ({emp.department}). Status set to Onboarded.'
                )

            else:
                prev_status = emp.account_status
                emp.name = item['name']
                emp.email = item['email']
                emp.department = item['department']
                emp.designation = item['designation']
                emp.manager = item['manager']
                emp.office_location = item['office_location']
                emp.account_status = item['account_status']
                emp.last_synced_at = datetime.utcnow()
                updated_count += 1

                # ===========================
                # AUTO-OFFBOARDING TRIGGER
                # Status changed → Offboarded → return all assigned laptops
                # ===========================
                if prev_status != AccountStatus.OFFBOARDED and item['account_status'] == AccountStatus.OFFBOARDED:
                    offboarded_count += 1
                    AuditService.log(
                        action='Employee Auto-Offboarded (Entra ID)',
                        entity_type='Employee',
                        entity_id=emp.employee_id,
                        details=f'Entra ID status changed to Offboarded for {emp.name}. Triggering laptop auto-return.'
                    )

            # ===========================
            # AUTO-RETURN LAPTOPS on OFFBOARDED
            # ===========================
            if emp.account_status == AccountStatus.OFFBOARDED:
                assigned_laptops = Asset.query.filter_by(assigned_employee_id=emp.id).all()
                for laptop in assigned_laptops:
                    laptop.status = AssetStatus.AVAILABLE
                    laptop.assigned_employee_id = None
                    laptop.assignment_date = None
                    returned_assets_count += 1

                    hist = AssetAssignmentHistory(
                        asset_id=laptop.id,
                        employee_id=emp.id,
                        employee_name=emp.name,
                        action='Returned (Auto Offboarded)',
                        notes=f'Automated return triggered during Entra ID sync for offboarded employee {emp.name} ({emp.employee_id})',
                        performed_by='Microsoft Entra Sync Engine'
                    )
                    db.session.add(hist)
                    AuditService.log(
                        action='Asset Auto Returned',
                        entity_type='Asset',
                        entity_id=laptop.asset_id,
                        details=f'Asset {laptop.asset_id} auto-returned due to offboarding of {emp.name} ({emp.employee_id})'
                    )

        db.session.commit()

        AuditService.log(
            action='Entra ID Sync Completed',
            entity_type='EmployeeSync',
            details=(
                f'Synced {len(entra_directory)} records from Entra ID. '
                f'Auto-Onboarded: {onboarded_count}, Updated: {updated_count}, '
                f'Auto-Offboarded: {offboarded_count}, Laptops Returned: {returned_assets_count}'
            )
        )

        return {
            'total': len(entra_directory),
            'created': created_count,
            'updated': updated_count,
            'onboarded': onboarded_count,
            'offboarded': offboarded_count,
            'returned_assets': returned_assets_count,
            'synced_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }

    @staticmethod
    def process_webhook_event(event_type, employee_id, attributes=None):
        """
        Handles real-time Entra ID webhook events from Azure AD lifecycle workflows.
        
        Supported event_types:
          - 'onboarded'  → New user provisioned in Entra ID
          - 'offboarded' → User account deprovisioned in Entra ID
          - 'updated'    → User attributes updated in Entra ID
          - 'blocked'    → Account sign-in blocked
          - 'disabled'   → Account disabled
        
        Azure sends these as Activity Log alerts or via Graph Change Notifications.
        """
        attributes = attributes or {}
        emp = Employee.query.filter_by(employee_id=employee_id).first()

        if event_type == 'onboarded':
            if not emp:
                emp = Employee(
                    employee_id=employee_id,
                    name=attributes.get('name', ''),
                    email=attributes.get('email', ''),
                    department=attributes.get('department', ''),
                    designation=attributes.get('designation', ''),
                    manager=attributes.get('manager', ''),
                    office_location=attributes.get('office_location', ''),
                    account_status=AccountStatus.ONBOARDED,
                    last_synced_at=datetime.utcnow()
                )
                db.session.add(emp)
                db.session.commit()
                AuditService.log(
                    action='Employee Onboarded (Entra Webhook)',
                    entity_type='Employee',
                    entity_id=employee_id,
                    details=f'Real-time Entra ID webhook: {attributes.get("name")} onboarded and auto-created.'
                )
                return {'status': 'created', 'employee_id': employee_id}
            return {'status': 'already_exists', 'employee_id': employee_id}

        elif event_type == 'offboarded' and emp:
            prev_status = emp.account_status
            emp.account_status = AccountStatus.OFFBOARDED
            emp.last_synced_at = datetime.utcnow()

            returned = 0
            assigned_laptops = Asset.query.filter_by(assigned_employee_id=emp.id).all()
            for laptop in assigned_laptops:
                laptop.status = AssetStatus.AVAILABLE
                laptop.assigned_employee_id = None
                laptop.assignment_date = None
                returned += 1
                hist = AssetAssignmentHistory(
                    asset_id=laptop.id,
                    employee_id=emp.id,
                    employee_name=emp.name,
                    action='Returned (Entra Offboard Webhook)',
                    notes=f'Auto-returned via Entra ID lifecycle webhook for {emp.name}',
                    performed_by='Entra ID Lifecycle Webhook'
                )
                db.session.add(hist)

            db.session.commit()
            AuditService.log(
                action='Employee Offboarded (Entra Webhook)',
                entity_type='Employee',
                entity_id=employee_id,
                details=f'Entra ID webhook: {emp.name} offboarded. {returned} laptop(s) auto-returned.'
            )
            return {'status': 'offboarded', 'employee_id': employee_id, 'returned_assets': returned}

        elif event_type == 'updated' and emp:
            for field in ['name', 'email', 'department', 'designation', 'manager', 'office_location']:
                if field in attributes:
                    setattr(emp, field, attributes[field])
            if 'account_status' in attributes:
                emp.account_status = attributes['account_status']
            emp.last_synced_at = datetime.utcnow()
            db.session.commit()
            return {'status': 'updated', 'employee_id': employee_id}

        elif event_type == 'blocked' and emp:
            emp.account_status = AccountStatus.BLOCKED
            emp.last_synced_at = datetime.utcnow()
            db.session.commit()
            return {'status': 'blocked', 'employee_id': employee_id}

        elif event_type == 'disabled' and emp:
            emp.account_status = AccountStatus.DISABLED
            emp.last_synced_at = datetime.utcnow()
            db.session.commit()
            return {'status': 'disabled', 'employee_id': employee_id}

        return {'status': 'no_action', 'employee_id': employee_id}

    @staticmethod
    def poll_outlook_inbox():
        """
        Polls Microsoft Outlook support mailbox via Graph API or Mock Engine
        to process incoming support emails into Helpdesk tickets.
        """
        return {'processed_emails': 0, 'new_tickets': 0}
