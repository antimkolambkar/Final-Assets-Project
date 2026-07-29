from flask import Blueprint, render_template, request, Response, flash, redirect, url_for
from flask_login import login_required
from app.extensions import db
from app.models.employee import Employee
from app.models.vendor import Vendor
from app.services.report_service import ReportService
from app.services.audit_service import AuditService

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('/')
@login_required
def index():
    report_type = request.args.get('type', 'employee')
    department = request.args.get('department', '').strip()
    vendor_id = request.args.get('vendor_id', type=int)
    employee_id = request.args.get('employee_id', type=int)

    title, headers, rows = ReportService.fetch_report_data(
        report_type=report_type,
        department=department,
        vendor_id=vendor_id,
        employee_id=employee_id
    )

    departments = [d[0] for d in db.session.query(Employee.department).distinct().all() if d[0]]
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
        selected_employee=employee_id
    )


@reports_bp.route('/export/<string:fmt>')
@login_required
def export_report(fmt):
    report_type = request.args.get('type', 'employee')
    department = request.args.get('department', '').strip()
    vendor_id = request.args.get('vendor_id', type=int)
    employee_id = request.args.get('employee_id', type=int)

    AuditService.log(
        action='Report Exported',
        entity_type='Report',
        details=f'Exported {report_type} report in {fmt.upper()} format'
    )

    if fmt == 'excel':
        data = ReportService.generate_excel(report_type, department=department, vendor_id=vendor_id, employee_id=employee_id)
        return Response(
            data,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': f'attachment; filename=itam_report_{report_type}.xlsx'}
        )
    elif fmt == 'pdf':
        data = ReportService.generate_pdf(report_type, department=department, vendor_id=vendor_id, employee_id=employee_id)
        return Response(
            data,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'inline; filename=itam_report_{report_type}.pdf'}
        )
    elif fmt == 'csv':
        data = ReportService.generate_csv(report_type, department=department, vendor_id=vendor_id, employee_id=employee_id)
        return Response(
            data,
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=itam_report_{report_type}.csv'}
        )
    else:
        flash('Invalid export format requested.', 'danger')
        return redirect(url_for('reports.index'))
