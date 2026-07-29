import io
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, Response, current_app
from flask_login import login_required, current_user
from app.services.import_service import ExcelImportService
from app.services.graph_service import MicrosoftGraphService
from app.services.audit_service import AuditService
from app.extensions import db

import_bp = Blueprint('imports', __name__, url_prefix='/import')

ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@import_bp.route('/')
@login_required
def index():
    """Excel Import Center - upload employee or asset spreadsheets"""
    if not current_user.is_it_admin:
        flash('Permission denied. Only IT Administrators can import data.', 'danger')
        return redirect(url_for('dashboard.index'))
    return render_template('imports/index.html')


@import_bp.route('/employees', methods=['POST'])
@login_required
def import_employees():
    """Process uploaded employee Excel/CSV file"""
    if not current_user.is_it_admin:
        flash('Permission denied.', 'danger')
        return redirect(url_for('imports.index'))

    if 'file' not in request.files or not request.files['file'].filename:
        flash('Please select a file to upload.', 'warning')
        return redirect(url_for('imports.index'))

    file = request.files['file']
    if not _allowed_file(file.filename):
        flash('Invalid file format. Please upload an .xlsx, .xls, or .csv file.', 'danger')
        return redirect(url_for('imports.index'))

    result = ExcelImportService.import_employees(
        file_obj=file,
        filename=file.filename,
        performed_by=current_user.full_name
    )

    return render_template('imports/result.html', result=result, import_type='Employee', filename=file.filename)


@import_bp.route('/assets', methods=['POST'])
@login_required
def import_assets():
    """Process uploaded asset Excel/CSV file"""
    if not current_user.is_it_admin:
        flash('Permission denied.', 'danger')
        return redirect(url_for('imports.index'))

    if 'file' not in request.files or not request.files['file'].filename:
        flash('Please select a file to upload.', 'warning')
        return redirect(url_for('imports.index'))

    file = request.files['file']
    if not _allowed_file(file.filename):
        flash('Invalid file format. Please upload an .xlsx, .xls, or .csv file.', 'danger')
        return redirect(url_for('imports.index'))

    result = ExcelImportService.import_assets(
        file_obj=file,
        filename=file.filename,
        performed_by=current_user.full_name
    )

    return render_template('imports/result.html', result=result, import_type='Asset', filename=file.filename)


@import_bp.route('/template/employees')
@login_required
def download_employee_template():
    """Download CSV template for employee import"""
    csv_data = ExcelImportService.generate_employee_template()
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=employee_import_template.csv'}
    )


@import_bp.route('/template/assets')
@login_required
def download_asset_template():
    """Download CSV template for asset import"""
    csv_data = ExcelImportService.generate_asset_template()
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=asset_import_template.csv'}
    )


# ============================================================
# MICROSOFT ENTRA ID LIFECYCLE WEBHOOK ENDPOINT
# ============================================================

@import_bp.route('/entra/webhook', methods=['POST'])
def entra_webhook():
    """
    Microsoft Entra ID Graph Change Notification Webhook.

    Azure AD calls this endpoint automatically when:
      - A new user is provisioned (onboarded)
      - A user is deprovisioned (offboarded)
      - User attributes are updated

    Register this URL in Azure Portal:
      Azure AD → Enterprise Applications → Lifecycle Workflows → Webhook URL

    The endpoint validates the Azure validation token on first call.
    Subsequent calls contain change notification payloads.

    Security: Azure signs requests with a client state secret.
    """
    # Azure sends a validation token on subscription creation
    validation_token = request.args.get('validationToken')
    if validation_token:
        # Return token as plain text to confirm subscription
        current_app.logger.info("Entra ID webhook validation request received.")
        return Response(validation_token, mimetype='text/plain', status=200)

    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({'error': 'Empty payload'}), 400

        # Validate client state for security
        expected_state = current_app.config.get('ENTRA_WEBHOOK_SECRET', '')
        notifications = data.get('value', [])

        results = []
        for notification in notifications:
            client_state = notification.get('clientState', '')
            if expected_state and client_state != expected_state:
                current_app.logger.warning("Webhook notification with invalid clientState received.")
                continue

            resource = notification.get('resource', '')
            change_type = notification.get('changeType', '').lower()

            # Extract employee ID from resource path (e.g., "users/EMP-1001")
            employee_id = resource.split('/')[-1] if '/' in resource else resource

            # Map Entra change types to our event types
            event_map = {
                'created': 'onboarded',
                'updated': 'updated',
                'deleted': 'offboarded'
            }
            event_type = event_map.get(change_type, 'updated')

            # Pull additional attributes from the notification if available
            resource_data = notification.get('resourceData', {})
            attributes = {
                'name': resource_data.get('displayName', ''),
                'email': resource_data.get('mail', ''),
                'department': resource_data.get('department', ''),
                'designation': resource_data.get('jobTitle', ''),
                'office_location': resource_data.get('officeLocation', ''),
            }

            result = MicrosoftGraphService.process_webhook_event(
                event_type=event_type,
                employee_id=employee_id,
                attributes=attributes
            )
            results.append(result)
            current_app.logger.info(f"Entra webhook processed: {event_type} for {employee_id} → {result['status']}")

        return jsonify({'processed': len(results), 'results': results}), 200

    except Exception as e:
        current_app.logger.error(f"Entra webhook error: {e}")
        return jsonify({'error': str(e)}), 500


@import_bp.route('/entra/test-webhook', methods=['POST'])
@login_required
def test_webhook():
    """
    Simulate an Entra ID lifecycle webhook event for testing purposes.
    Only available to IT Administrators for configuration validation.
    """
    if not current_user.is_it_admin:
        flash('Permission denied.', 'danger')
        return redirect(url_for('imports.index'))

    event_type = request.form.get('event_type', 'onboarded')
    employee_id = request.form.get('employee_id', '').strip()
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    department = request.form.get('department', '').strip()

    if not employee_id:
        flash('Employee ID is required for webhook simulation.', 'danger')
        return redirect(url_for('imports.index'))

    result = MicrosoftGraphService.process_webhook_event(
        event_type=event_type,
        employee_id=employee_id,
        attributes={
            'name': name,
            'email': email,
            'department': department
        }
    )

    status_map = {
        'created': ('success', f'Employee {employee_id} auto-onboarded successfully from Entra ID lifecycle event!'),
        'already_exists': ('warning', f'Employee {employee_id} already exists in the system.'),
        'offboarded': ('warning', f'Employee {employee_id} has been auto-offboarded. Laptops returned: {result.get("returned_assets", 0)}'),
        'updated': ('info', f'Employee {employee_id} attributes updated from Entra ID.'),
        'blocked': ('warning', f'Employee {employee_id} account blocked via Entra ID event.'),
        'disabled': ('info', f'Employee {employee_id} account disabled via Entra ID event.'),
        'no_action': ('secondary', f'No action taken for employee {employee_id}. Employee may not exist yet.')
    }

    category, message = status_map.get(result.get('status', 'no_action'), ('info', 'Event processed.'))
    flash(message, category)
    return redirect(url_for('imports.index'))
