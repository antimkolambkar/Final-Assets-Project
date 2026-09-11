import os
import io
import random

from datetime import datetime

from flask import current_app

from app.extensions import db

from app.models.employee import (
    Employee,
    AccountStatus
)

from app.models.asset import (
    Asset,
    AssetStatus,
    AssetAssignmentHistory
)

from app.services.audit_service import AuditService


class MicrosoftGraphService:
    """
    Microsoft Graph API Integration Service.

    Handles:

    - Entra ID employee synchronization
    - Automatic employee creation
    - Automatic status synchronization
    - Status date tracking
    - Automatic laptop return on Offboarded
    - Entra webhook events
    - Outlook polling placeholder
    """

    # =====================================================
    # STATUS DATE HELPER
    # =====================================================

    @staticmethod
    def _status_date_field(status):

        return {
            AccountStatus.ONBOARDED: 'onboarded_date',
            AccountStatus.ACTIVE: 'active_date',
            AccountStatus.BLOCKED: 'blocked_date',
            AccountStatus.DISABLED: 'disabled_date',
            AccountStatus.OFFBOARDED: 'offboarded_date'
        }.get(status)

    # =====================================================
    # APPLY STATUS
    # =====================================================

    @staticmethod
    def _apply_status(emp, new_status):

        if new_status not in {
            AccountStatus.ONBOARDED,
            AccountStatus.ACTIVE,
            AccountStatus.BLOCKED,
            AccountStatus.DISABLED,
            AccountStatus.OFFBOARDED
        }:
            return False

        old_status = emp.account_status

        # No status change
        if old_status == new_status:
            return False

        emp.account_status = new_status

        # -------------------------------------------------
        # Set corresponding status date
        # -------------------------------------------------

        field = MicrosoftGraphService._status_date_field(
            new_status
        )

        if field:

            current_date = getattr(
                emp,
                field,
                None
            )

            # Keep existing historical date.
            # Only create date when status is entered
            # for the first time.
            if not current_date:

                setattr(
                    emp,
                    field,
                    datetime.utcnow().date()
                )

        return True

    # =====================================================
    # AUTO RETURN LAPTOPS
    # =====================================================

    @staticmethod
    def _return_employee_assets(emp):

        returned_assets_count = 0

        assigned_laptops = (
            Asset.query
            .filter_by(
                assigned_employee_id=emp.id
            )
            .all()
        )

        for laptop in assigned_laptops:

            laptop.status = AssetStatus.AVAILABLE

            laptop.assigned_employee_id = None

            laptop.assignment_date = None

            returned_assets_count += 1

            history = AssetAssignmentHistory(
                asset_id=laptop.id,
                employee_id=emp.id,
                employee_name=emp.name,
                action='Returned (Auto Offboarded)',
                notes=(
                    'Automated laptop return triggered by '
                    f'Microsoft Entra ID offboarding for '
                    f'{emp.name} ({emp.employee_id}).'
                ),
                performed_by='Microsoft Entra Sync Engine'
            )

            db.session.add(history)

            try:

                AuditService.log(
                    action='Asset Auto Returned',
                    entity_type='Asset',
                    entity_id=laptop.asset_id,
                    details=(
                        f'Asset {laptop.asset_id} automatically '
                        f'returned because employee {emp.name} '
                        f'({emp.employee_id}) was offboarded.'
                    )
                )

            except Exception:

                pass

        return returned_assets_count

    # =====================================================
    # MAIN SYNC
    # =====================================================

    @staticmethod
    def sync_entra_employees():

        mode = current_app.config.get(
            'GRAPH_INTEGRATION_MODE',
            'MOCK'
        )

        if mode == 'LIVE':

            return MicrosoftGraphService._sync_live_employees()

        return MicrosoftGraphService._sync_mock_employees()

    # =====================================================
    # LIVE GRAPH SYNC
    # =====================================================

    @staticmethod
    def _sync_live_employees():

        try:

            import msal
            import requests as http_requests

            client_id = current_app.config.get(
                'AZURE_CLIENT_ID',
                ''
            )

            client_secret = current_app.config.get(
                'AZURE_CLIENT_SECRET',
                ''
            )

            tenant_id = current_app.config.get(
                'AZURE_TENANT_ID',
                ''
            )

            if not all([
                client_id,
                client_secret,
                tenant_id
            ]):

                current_app.logger.warning(
                    'Azure credentials not configured. '
                    'Falling back to MOCK mode.'
                )

                return MicrosoftGraphService._sync_mock_employees()

            if 'YOUR_' in client_id:

                current_app.logger.warning(
                    'Placeholder Azure credentials detected. '
                    'Falling back to MOCK mode.'
                )

                return MicrosoftGraphService._sync_mock_employees()

            authority = (
                f'https://login.microsoftonline.com/'
                f'{tenant_id}'
            )

            app_msal = msal.ConfidentialClientApplication(
                client_id,
                authority=authority,
                client_credential=client_secret
            )

            token_response = app_msal.acquire_token_for_client(
                scopes=[
                    'https://graph.microsoft.com/.default'
                ]
            )

            if 'access_token' not in token_response:

                current_app.logger.error(
                    'Microsoft Graph token acquisition failed.'
                )

                return MicrosoftGraphService._sync_mock_employees()

            access_token = token_response[
                'access_token'
            ]

            headers = {
                'Authorization': (
                    f'Bearer {access_token}'
                )
            }

            # -------------------------------------------------
            # First Graph request
            # -------------------------------------------------

            url = (
                'https://graph.microsoft.com/v1.0/users'
                '?$select='
                'id,employeeId,displayName,mail,'
                'department,jobTitle,officeLocation,'
                'accountEnabled'
                '&$top=999'
            )

            entra_directory = []

            # -------------------------------------------------
            # Handle Graph pagination
            # -------------------------------------------------

            while url:

                response = http_requests.get(
                    url,
                    headers=headers,
                    timeout=30
                )

                response.raise_for_status()

                payload = response.json()

                users_data = payload.get(
                    'value',
                    []
                )

                for user in users_data:

                    entra_object_id = user.get(
                        'id'
                    )

                    emp_id = (
                        user.get('employeeId')
                        or (
                            f'ENTRA-'
                            f'{entra_object_id[:8].upper()}'
                            if entra_object_id
                            else ''
                        )
                    )

                    if not emp_id:
                        continue

                    # -------------------------------------------------
                    # Graph currently exposes accountEnabled reliably.
                    #
                    # True  = Active
                    # False = Disabled
                    #
                    # Onboarded is used only for NEW users.
                    # -------------------------------------------------

                    status = (
                        AccountStatus.ACTIVE
                        if user.get('accountEnabled')
                        else AccountStatus.DISABLED
                    )

                    entra_directory.append({

                        'entra_id': entra_object_id,

                        'employee_id': emp_id,

                        'name': (
                            user.get(
                                'displayName'
                            )
                            or ''
                        ),

                        'email': (
                            user.get(
                                'mail'
                            )
                            or ''
                        ),

                        'department': (
                            user.get(
                                'department'
                            )
                            or ''
                        ),

                        'designation': (
                            user.get(
                                'jobTitle'
                            )
                            or ''
                        ),

                        'manager': '',

                        'office_location': (
                            user.get(
                                'officeLocation'
                            )
                            or ''
                        ),

                        'account_status': status
                    })

                # -------------------------------------------------
                # Microsoft Graph pagination
                # -------------------------------------------------

                url = payload.get(
                    '@odata.nextLink'
                )

            return MicrosoftGraphService._process_directory(
                entra_directory
            )

        except ImportError:

            current_app.logger.warning(
                'MSAL or requests is not installed. '
                'Using MOCK mode.'
            )

            return MicrosoftGraphService._sync_mock_employees()

        except Exception as e:

            current_app.logger.error(
                f'Graph API sync error: {e}. '
                f'Falling back to MOCK.'
            )

            return MicrosoftGraphService._sync_mock_employees()

    # =====================================================
    # MOCK SYNC
    # =====================================================

    @staticmethod
    def _sync_mock_employees():

        # IMPORTANT:
        # Empty by default.
        # This prevents fake/sample employees being created.

        mock_entra_directory = []

        return MicrosoftGraphService._process_directory(
            mock_entra_directory
        )

    # =====================================================
    # PROCESS DIRECTORY
    # =====================================================

    @staticmethod
    def _process_directory(entra_directory):

        created_count = 0
        updated_count = 0

        onboarded_count = 0
        active_count = 0
        blocked_count = 0
        disabled_count = 0
        offboarded_count = 0

        returned_assets_count = 0

        for item in entra_directory:

            emp = (
                Employee.query
                .filter_by(
                    employee_id=item['employee_id']
                )
                .first()
            )

            # =================================================
            # NEW EMPLOYEE
            # =================================================

            if not emp:

                # -------------------------------------------------
                # New Microsoft user starts as ONBOARDED.
                # -------------------------------------------------

                emp = Employee(

                    employee_id=item[
                        'employee_id'
                    ],

                    name=item[
                        'name'
                    ],

                    email=item[
                        'email'
                    ],

                    department=item[
                        'department'
                    ],

                    designation=item[
                        'designation'
                    ],

                    manager=item[
                        'manager'
                    ],

                    office_location=item[
                        'office_location'
                    ],

                    account_status=(
                        AccountStatus.ONBOARDED
                    ),

                    onboarded_date=(
                        datetime.utcnow().date()
                    ),

                    last_synced_at=(
                        datetime.utcnow()
                    )
                )

                db.session.add(emp)

                db.session.flush()

                created_count += 1

                onboarded_count += 1

                try:

                    AuditService.log(
                        action=(
                            'Employee Auto-Onboarded '
                            '(Entra ID)'
                        ),
                        entity_type='Employee',
                        entity_id=emp.employee_id,
                        details=(
                            f'New Microsoft Entra user '
                            f'{emp.name} '
                            f'({emp.employee_id}) '
                            f'created as Onboarded. '
                            f'Onboarded Date: '
                            f'{emp.onboarded_date}.'
                        )
                    )

                except Exception:

                    pass

            # =================================================
            # EXISTING EMPLOYEE
            # =================================================

            else:

                old_status = emp.account_status

                # -------------------------------------------------
                # Update profile information
                # -------------------------------------------------

                emp.name = item['name']

                emp.email = item['email']

                emp.department = item['department']

                emp.designation = item['designation']

                emp.manager = item['manager']

                emp.office_location = item[
                    'office_location'
                ]

                emp.last_synced_at = (
                    datetime.utcnow()
                )

                updated_count += 1

                # -------------------------------------------------
                # Determine Microsoft status
                # -------------------------------------------------

                microsoft_status = item[
                    'account_status'
                ]

                status_changed = (
                    old_status != microsoft_status
                )

                if status_changed:

                    MicrosoftGraphService._apply_status(
                        emp,
                        microsoft_status
                    )

                    # -------------------------------------------------
                    # Count status change
                    # -------------------------------------------------

                    if microsoft_status == AccountStatus.ACTIVE:
                        active_count += 1

                    elif microsoft_status == AccountStatus.BLOCKED:
                        blocked_count += 1

                    elif microsoft_status == AccountStatus.DISABLED:
                        disabled_count += 1

                    elif microsoft_status == AccountStatus.OFFBOARDED:
                        offboarded_count += 1

                    elif microsoft_status == AccountStatus.ONBOARDED:
                        onboarded_count += 1

                    # -------------------------------------------------
                    # Audit
                    # -------------------------------------------------

                    try:

                        field = (
                            MicrosoftGraphService
                            ._status_date_field(
                                microsoft_status
                            )
                        )

                        status_date = getattr(
                            emp,
                            field,
                            None
                        )

                        AuditService.log(
                            action=(
                                'Employee Status Changed '
                                '(Entra ID)'
                            ),
                            entity_type='Employee',
                            entity_id=emp.employee_id,
                            details=(
                                f'Employee {emp.name} '
                                f'({emp.employee_id}) '
                                f'status changed from '
                                f'{old_status} to '
                                f'{microsoft_status}. '
                                f'Status Date: '
                                f'{status_date}.'
                            )
                        )

                    except Exception:

                        pass

            # =================================================
            # AUTO RETURN ON OFFBOARDED
            # =================================================

            if (
                emp.account_status
                == AccountStatus.OFFBOARDED
            ):

                returned_assets_count += (
                    MicrosoftGraphService
                    ._return_employee_assets(emp)
                )

        # =====================================================
        # COMMIT
        # =====================================================

        db.session.commit()

        # =====================================================
        # FINAL AUDIT
        # =====================================================

        try:

            AuditService.log(
                action='Entra ID Sync Completed',
                entity_type='EmployeeSync',
                details=(
                    f'Synced {len(entra_directory)} '
                    f'Entra ID records. '
                    f'Created: {created_count}, '
                    f'Updated: {updated_count}, '
                    f'Onboarded: {onboarded_count}, '
                    f'Active: {active_count}, '
                    f'Blocked: {blocked_count}, '
                    f'Disabled: {disabled_count}, '
                    f'Offboarded: {offboarded_count}, '
                    f'Laptops Returned: '
                    f'{returned_assets_count}.'
                )
            )

        except Exception:

            pass

        return {

            'total': len(
                entra_directory
            ),

            'created': created_count,

            'updated': updated_count,

            'onboarded': onboarded_count,

            'active': active_count,

            'blocked': blocked_count,

            'disabled': disabled_count,

            'offboarded': offboarded_count,

            'returned_assets': (
                returned_assets_count
            ),

            'synced_at': (
                datetime.utcnow()
                .strftime(
                    '%Y-%m-%d %H:%M:%S'
                )
            )
        }

    # =====================================================
    # WEBHOOK EVENT PROCESSOR
    # =====================================================

    @staticmethod
    def process_webhook_event(
        event_type,
        employee_id,
        attributes=None
    ):

        attributes = attributes or {}

        emp = (
            Employee.query
            .filter_by(
                employee_id=employee_id
            )
            .first()
        )

        # =================================================
        # ONBOARDED
        # =================================================

        if event_type == 'onboarded':

            if not emp:

                today = datetime.utcnow().date()

                emp = Employee(

                    employee_id=employee_id,

                    name=attributes.get(
                        'name',
                        ''
                    ),

                    email=attributes.get(
                        'email',
                        ''
                    ),

                    department=attributes.get(
                        'department',
                        ''
                    ),

                    designation=attributes.get(
                        'designation',
                        ''
                    ),

                    manager=attributes.get(
                        'manager',
                        ''
                    ),

                    office_location=attributes.get(
                        'office_location',
                        ''
                    ),

                    account_status=(
                        AccountStatus.ONBOARDED
                    ),

                    onboarded_date=today,

                    last_synced_at=(
                        datetime.utcnow()
                    )
                )

                db.session.add(emp)

                db.session.commit()

                try:

                    AuditService.log(
                        action=(
                            'Employee Onboarded '
                            '(Entra Webhook)'
                        ),
                        entity_type='Employee',
                        entity_id=employee_id,
                        details=(
                            f'Employee {emp.name} '
                            f'created from Entra webhook. '
                            f'Onboarded Date: {today}.'
                        )
                    )

                except Exception:

                    pass

                return {
                    'status': 'created',
                    'employee_id': employee_id
                }

            return {
                'status': 'already_exists',
                'employee_id': employee_id
            }

        # =================================================
        # ACTIVE
        # =================================================

        elif event_type == 'active':

            if not emp:

                return {
                    'status': 'employee_not_found',
                    'employee_id': employee_id
                }

            old_status = emp.account_status

            changed = (
                MicrosoftGraphService
                ._apply_status(
                    emp,
                    AccountStatus.ACTIVE
                )
            )

            emp.last_synced_at = (
                datetime.utcnow()
            )

            db.session.commit()

            return {
                'status': (
                    'active'
                    if changed
                    else 'already_active'
                ),
                'employee_id': employee_id,
                'old_status': old_status
            }

        # =================================================
        # BLOCKED
        # =================================================

        elif event_type == 'blocked':

            if not emp:

                return {
                    'status': 'employee_not_found',
                    'employee_id': employee_id
                }

            old_status = emp.account_status

            changed = (
                MicrosoftGraphService
                ._apply_status(
                    emp,
                    AccountStatus.BLOCKED
                )
            )

            emp.last_synced_at = (
                datetime.utcnow()
            )

            db.session.commit()

            return {
                'status': (
                    'blocked'
                    if changed
                    else 'already_blocked'
                ),
                'employee_id': employee_id,
                'old_status': old_status
            }

        # =================================================
        # DISABLED
        # =================================================

        elif event_type == 'disabled':

            if not emp:

                return {
                    'status': 'employee_not_found',
                    'employee_id': employee_id
                }

            old_status = emp.account_status

            changed = (
                MicrosoftGraphService
                ._apply_status(
                    emp,
                    AccountStatus.DISABLED
                )
            )

            emp.last_synced_at = (
                datetime.utcnow()
            )

            db.session.commit()

            return {
                'status': (
                    'disabled'
                    if changed
                    else 'already_disabled'
                ),
                'employee_id': employee_id,
                'old_status': old_status
            }

        # =================================================
        # OFFBOARDED
        # =================================================

        elif event_type == 'offboarded':

            if not emp:

                return {
                    'status': 'employee_not_found',
                    'employee_id': employee_id
                }

            old_status = emp.account_status

            changed = (
                MicrosoftGraphService
                ._apply_status(
                    emp,
                    AccountStatus.OFFBOARDED
                )
            )

            emp.last_synced_at = (
                datetime.utcnow()
            )

            returned = 0

            if changed:

                returned = (
                    MicrosoftGraphService
                    ._return_employee_assets(
                        emp
                    )
                )

            db.session.commit()

            try:

                AuditService.log(
                    action=(
                        'Employee Offboarded '
                        '(Entra Webhook)'
                    ),
                    entity_type='Employee',
                    entity_id=employee_id,
                    details=(
                        f'Employee {emp.name} '
                        f'offboarded through Entra webhook. '
                        f'Laptops returned: {returned}.'
                    )
                )

            except Exception:

                pass

            return {
                'status': (
                    'offboarded'
                    if changed
                    else 'already_offboarded'
                ),
                'employee_id': employee_id,
                'old_status': old_status,
                'returned_assets': returned
            }

        # =================================================
        # UPDATED
        # =================================================

        elif event_type == 'updated':

            if not emp:

                return {
                    'status': 'employee_not_found',
                    'employee_id': employee_id
                }

            for field in [
                'name',
                'email',
                'department',
                'designation',
                'manager',
                'office_location'
            ]:

                if field in attributes:

                    setattr(
                        emp,
                        field,
                        attributes[field]
                    )

            if 'account_status' in attributes:

                new_status = attributes[
                    'account_status'
                ]

                if new_status in {
                    AccountStatus.ONBOARDED,
                    AccountStatus.ACTIVE,
                    AccountStatus.BLOCKED,
                    AccountStatus.DISABLED,
                    AccountStatus.OFFBOARDED
                }:

                    old_status = (
                        emp.account_status
                    )

                    changed = (
                        MicrosoftGraphService
                        ._apply_status(
                            emp,
                            new_status
                        )
                    )

                    if (
                        changed
                        and new_status
                        == AccountStatus.OFFBOARDED
                    ):

                        MicrosoftGraphService \
                            ._return_employee_assets(
                                emp
                            )

            emp.last_synced_at = (
                datetime.utcnow()
            )

            db.session.commit()

            return {
                'status': 'updated',
                'employee_id': employee_id
            }

        # =================================================
        # UNKNOWN EVENT
        # =================================================

        return {
            'status': 'no_action',
            'employee_id': employee_id
        }

    # =====================================================
    # OUTLOOK
    # =====================================================

    @staticmethod
    def poll_outlook_inbox():

        return {
            'processed_emails': 0,
            'new_tickets': 0
        }
