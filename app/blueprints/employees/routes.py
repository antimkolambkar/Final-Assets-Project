from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    flash,
    redirect,
    url_for
)

from flask_login import login_required, current_user

from app.extensions import db

from app.models.employee import Employee, AccountStatus
from app.models.asset import (
    Asset,
    AssetStatus,
    AssetAssignmentHistory
)

from app.services.graph_service import MicrosoftGraphService
from app.services.audit_service import AuditService
