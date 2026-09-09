from flask import Blueprint, render_template, request, Response, flash, redirect, url_for
from flask_login import login_required
from datetime import datetime

from app.extensions import db
from app.models.employee import Employee
from app.models.vendor import Vendor
from app.services.report_service import ReportService
from app.services.audit_service import AuditService

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')


def _get_report_filters():
    report_type = request.args.get('type', 'employee')
    department = request.args.get('department', '').strip()
    vendor_id = request.args.get('vendor_id', type=int)
    employee_id = request.args.get('employee_id', type=int)

    start_date = None
    end_date = None

    start_date_str = request.args.get('start_date', '').strip()
    end_date_str = request.args.get('end_date', '').strip()

    if start_date_str:
        try:
            start_date = datetime.strptime(
                start_date_str, '%Y-%m-%d'
            )
        except ValueError:
            start_date = None

    if end_date_str:
        try:
            # Include the complete selected end date.
            end_date = datetime.strptime(
                end_date_str + ' 23:59:59',
                '%Y-%m-%d %H:%M:%S'
            )
        except ValueError:
            end_date = None

    return (
        report_type,
        department,
        vendor_id,
        employee_id,
        start_date,
        end_date,
        start_date_str,
        end_date_str
    )


@reports_bp.route('/')
@login_required
def index():
    (
        report_type,
        department,
        vendor_id,
        employee_id,
        start_date,
        end_date,
        start_date_str,
        end_date_str
    ) = _get_report_filters()

    title, headers, rows = ReportService.fetch_report_data(
        report_type=report_type,
        start_date=start_date,
        end_date=end_date,
        department=department,
        vendor_id=vendor_id,
        employee_id=employee_id
    )

    departments = [
        d[0]
        for d in db.session.query(Employee.department).distinct().all()
        if d[0]
    ]
    vendors = Vendor.query.order_by(Vendor.name.asc()).all()
    employees = Employee.query.order_by(Employee.name.asc()).all()

    return render_template(
        'reports/index.html',
        report_types=ReportService.REPORT_TYPES,
        selected_type=report_type,
        report_title=title,
        headers=headers,
        rows=rows,
        departments=departments,
        vendors=vendors,
        employees=employees,
        selected_dept=department,
        selected_vendor=vendor_id,
        selected_employee=employee_id,
        selected_start_date=start_date_str,
        selected_end_date=end_date_str
    )


@reports_bp.route('/export/<string:fmt>')
@login_required
def export_report(fmt):
    (
        report_type,
        department,
        vendor_id,
        employee_id,
        start_date,
        end_date,
        start_date_str,
        end_date_str
    ) = _get_report_filters()

    AuditService.log(
        action='Report Exported',
        entity_type='Report',
        details=f'Exported {report_type} report in {fmt.upper()} format'
    )

    if fmt == 'excel':
        data = ReportService.generate_excel(
            report_type,
            start_date=start_date,
            end_date=end_date,
            department=department,
            vendor_id=vendor_id,
            employee_id=employee_id
        )
        return Response(
            data,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                'Content-Disposition':
                f'attachment; filename=itam_report_{report_type}.xlsx'
            }
        )

    elif fmt == 'pdf':
        data = ReportService.generate_pdf(
            report_type,
            start_date=start_date,
            end_date=end_date,
            department=department,
            vendor_id=vendor_id,
            employee_id=employee_id
        )
        return Response(
            data,
            mimetype='application/pdf',
            headers={
                'Content-Disposition':
                f'inline; filename=itam_report_{report_type}.pdf'
            }
        )

    elif fmt == 'csv':
        data = ReportService.generate_csv(
            report_type,
            start_date=start_date,
            end_date=end_date,
            department=department,
            vendor_id=vendor_id,
            employee_id=employee_id
        )
        return Response(
            data,
            mimetype='text/csv',
            headers={
                'Content-Disposition':
                f'attachment; filename=itam_report_{report_type}.csv'
            }
        )

    else:
        flash('Invalid export format requested.', 'danger')
        return redirect(url_for('reports.index'))
