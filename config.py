import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'fleetsync-enterprise-secret-key-2026-secure')
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # MySQL Database Configuration (Default XAMPP settings)
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3307))
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')  # XAMPP default is empty
    MYSQL_DB = os.environ.get('MYSQL_DB', 'fleetsync_db')

    # Service Center Branding
    APP_NAME = 'FleetSync'
    APP_TAGLINE = 'Vehicle Service & Fleet Maintenance Management System'
    COMPANY_NAME = 'FleetSync Technologies Pro'
    COMPANY_PHONE = '+91 (022) 6555-3533'
    COMPANY_EMAIL = 'support@fleetsync.io'
    COMPANY_ADDRESS = '742 Cyber City, Phase 2, Tech District, Mumbai - 400051'
