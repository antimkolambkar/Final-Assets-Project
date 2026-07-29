import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'e839f9a2b8471c3d9e0f6b5a4c3d2e1f8a7b6c5d4e3f2a1b0'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(BASE_DIR, 'itam.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    
    # Upload Configuration
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload limit
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'zip'}
    
    # Microsoft Entra ID (Azure AD) Settings
    AZURE_CLIENT_ID = os.environ.get('AZURE_CLIENT_ID', 'mock-client-id')
    AZURE_CLIENT_SECRET = os.environ.get('AZURE_CLIENT_SECRET', 'mock-client-secret')
    AZURE_TENANT_ID = os.environ.get('AZURE_TENANT_ID', 'common')
    AZURE_AUTHORITY = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}"
    AZURE_REDIRECT_PATH = "/auth/callback"
    AZURE_SCOPE = ["User.Read", "User.Read.All", "Mail.Read", "Mail.Send"]

    # Graph Integration Engine Mode: 'LIVE' or 'MOCK'
    GRAPH_INTEGRATION_MODE = os.environ.get('GRAPH_INTEGRATION_MODE', 'MOCK')

    # Entra ID Lifecycle Webhook Secret (validate incoming Azure notifications)
    ENTRA_WEBHOOK_SECRET = os.environ.get('ENTRA_WEBHOOK_SECRET', 'itam-entra-webhook-secret-2026')
