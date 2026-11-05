#!/usr/bin/env python3
"""
FleetSync - Vehicle Service and Maintenance Tracker
Enterprise Flask Application with MySQL Backend
"""

import os
from datetime import datetime, date, timedelta
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, Response
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import io
import csv
import html
from markupsafe import Markup

from config import Config
from db import query_db, check_db_health, Error

app = Flask(__name__)
app.config.from_object(Config)

# Ensure uploads folder exists
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads', 'reports')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# -------------------------------------------------------------
# Context Processors & Template Filters
# -------------------------------------------------------------
@app.context_processor
def inject_global_vars():
    """Inject application branding, current user details, and live notifications globally."""
    user = None
    user_notifications = []
    unread_notifications_count = 0
    unread_available_parts_count = 0
    pending_parts_requests_count = 0
    low_stock_parts_count = 0

    if 'user_id' in session:
        try:
            user = query_db(
                "SELECT id, name, email, role, avatar FROM users WHERE id = %s",
                (session['user_id'],), one=True
            )
            if user:
                # Fetch notifications for this user
                user_notifications = query_db("""
                    SELECT * FROM notifications 
                    WHERE user_id = %s 
                    ORDER BY is_read ASC, created_at DESC 
                    LIMIT 8
                """, (user['id'],)) or []

                count_res = query_db("""
                    SELECT COUNT(*) as cnt FROM notifications 
                    WHERE user_id = %s AND is_read = 0
                """, (user['id'],), one=True)
                unread_notifications_count = count_res['cnt'] if count_res else 0

                # Count ready parts for technician
                if user['role'] == 'Technician':
                    part_ready = query_db("""
                        SELECT COUNT(*) as cnt FROM part_requests 
                        WHERE technician_id = %s AND status = 'Part Available'
                    """, (user['id'],), one=True)
                    unread_available_parts_count = part_ready['cnt'] if part_ready else 0

        except Exception:
            user = None

    # Get count of pending / overdue reminders for notification badge
    overdue_count = 0
    try:
        res = query_db("""
            SELECT COUNT(*) as cnt FROM maintenance_schedules
            WHERE status IN ('Overdue', 'Due Soon') OR next_due_date <= CURDATE()
        """, one=True)
        if res:
            overdue_count = res['cnt']
    except Exception:
        overdue_count = 0

    # Get Spare Parts global counts
    try:
        pending_req = query_db("""
            SELECT COUNT(*) as cnt FROM part_requests 
            WHERE status IN ('Waiting for Parts', 'Request Sent', 'Pending')
        """, one=True)
        if pending_req:
            pending_parts_requests_count = pending_req['cnt']

        low_stock = query_db("""
            SELECT COUNT(*) as cnt FROM spare_parts 
            WHERE quantity <= min_quantity OR status = 'Out of Stock'
        """, one=True)
        if low_stock:
            low_stock_parts_count = low_stock['cnt']
    except Exception:
        pass

    # Count of unpaid / pending invoices for navbar badge
    unpaid_invoices_count = 0
    try:
        unpaid_res = query_db("SELECT COUNT(*) as cnt FROM service_records WHERE payment_status != 'Paid' AND total_cost > 0", one=True)
        if unpaid_res:
            unpaid_invoices_count = unpaid_res['cnt']
    except Exception:
        unpaid_invoices_count = 0

    return {
        'app_name': Config.APP_NAME,
        'app_tagline': Config.APP_TAGLINE,
        'company_name': Config.COMPANY_NAME,
        'current_user': user,
        'overdue_count': overdue_count,
        'user_notifications': user_notifications,
        'unread_notifications_count': unread_notifications_count,
        'unread_available_parts_count': unread_available_parts_count,
        'pending_parts_requests_count': pending_parts_requests_count,
        'low_stock_parts_count': low_stock_parts_count,
        'unpaid_invoices_count': unpaid_invoices_count,
        'current_year': datetime.now().year,
        'now': datetime.now()
    }

@app.template_filter('currency')
@app.template_filter('format_currency')
def currency_filter(value):
    try:
        return f"₹{float(value):,.2f}"
    except (ValueError, TypeError):
        return "₹0.00"

@app.template_filter('format_date')
def format_date_filter(value):
    if not value:
        return "N/A"
    if isinstance(value, (datetime, date)):
        return value.strftime("%b %d, %Y")
    try:
        dt = datetime.strptime(str(value), "%Y-%m-%d")
        return dt.strftime("%b %d, %Y")
    except Exception:
        return str(value)

@app.template_filter('format_datetime')
def format_datetime_filter(value):
    if not value:
        return "N/A"
    if isinstance(value, (datetime, date)):
        return value.strftime("%b %d, %Y %I:%M %p")
    try:
        dt = datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%b %d, %Y %I:%M %p")
    except Exception:
        return str(value)

@app.template_filter('format_km')
def format_km_filter(value):
    try:
        return f"{int(value):,} km"
    except (ValueError, TypeError):
        return "0 km"

@app.template_filter('nl2br')
def nl2br_filter(s):
    if not s:
        return ""
    escaped = html.escape(str(s))
    formatted = escaped.replace('\r\n', '<br>').replace('\n', '<br>')
    return Markup(formatted)

# -------------------------------------------------------------
# Notification Helper
# -------------------------------------------------------------
def dispatch_notification(user_id, title, message, link=None, notif_type='general'):
    """Helper to dispatch live in-app notifications to any user role."""
    try:
        query_db("""
            INSERT INTO notifications (user_id, title, message, link, type, is_read)
            VALUES (%s, %s, %s, %s, %s, 0)
        """, (user_id, title, message, link, notif_type), commit=True)
    except Exception as e:
        app.logger.warning(f"Could not dispatch notification: {e}")

def dispatch_role_notification(role, title, message, link=None, notif_type='general'):
    """Helper to dispatch in-app notifications to all active users with a specified role."""
    try:
        users = query_db("SELECT id FROM users WHERE role = %s AND status = 'Active'", (role,)) or []
        for u in users:
            dispatch_notification(u['id'], title, message, link, notif_type)
    except Exception as e:
        app.logger.warning(f"Could not dispatch role notification for {role}: {e}")

# -------------------------------------------------------------
# Workflow Audit History & Stage Tracking
# -------------------------------------------------------------
def log_workflow_action(service_record_id, from_status, to_status, action_by, action_role, action_title, comments=None):
    """Persists an immutable timestamped event in the workflow audit history."""
    try:
        query_db("""
            INSERT INTO service_workflow_history 
            (service_record_id, from_status, to_status, action_by, action_role, action_title, comments)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (service_record_id, from_status, to_status, action_by, action_role, action_title, comments), commit=True)
    except Exception as e:
        app.logger.warning(f"Could not log workflow action: {e}")

def log_pricing_change(item_type, item_id, item_name, action, old_value, new_value, user_id=None, notes=None):
    """Record an immutable audit trail entry for price catalog, labor rate, or bill item adjustments."""
    try:
        user = query_db("SELECT name, role FROM users WHERE id = %s", (user_id,), one=True) if user_id else None
        user_name = user['name'] if user else session.get('user_name', 'System / Admin')
        user_role = user['role'] if user else session.get('user_role', 'Admin')
        
        query_db("""
            INSERT INTO pricing_audit_logs (item_type, item_id, item_name, action, old_value, new_value, changed_by, changed_by_name, changed_by_role, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (item_type, item_id, item_name, action, str(old_value) if old_value is not None else '', str(new_value) if new_value is not None else '', user_id or session.get('user_id'), user_name, user_role, notes), commit=True)
    except Exception as e:
        app.logger.warning(f"Could not log pricing change: {e}")

def get_workflow_stage_info(status):
    """Returns stage metadata (stage number, display name, badge class, responsible role, next required action)."""
    status_clean = (status or '').strip()
    mapping = {
        'Pending': {
            'stage': 1, 'name': 'Inspection Required', 'badge_class': 'badge-unpaid',
            'responsible': 'Technician', 'next_action': 'Inspect vehicle & diagnose faults',
            'icon': 'fa-solid fa-clipboard-check'
        },
        'Accepted': {
            'stage': 1, 'name': 'Inspection Required', 'badge_class': 'badge-accepted',
            'responsible': 'Technician', 'next_action': 'Record inspection & list needed parts',
            'icon': 'fa-solid fa-clipboard-check'
        },
        'Inspection Submitted': {
            'stage': 2, 'name': 'Inspection Submitted', 'badge_class': 'badge-duesoon',
            'responsible': 'Admin / Parts Dept', 'next_action': 'Review inspection & requested parts',
            'icon': 'fa-solid fa-file-lines'
        },
        'Parts Under Review': {
            'stage': 2, 'name': 'Parts Under Review', 'badge_class': 'badge-duesoon',
            'responsible': 'Spare Parts Dept', 'next_action': 'Review availability & set supplier ETAs',
            'icon': 'fa-solid fa-boxes-packing'
        },
        'Waiting for Parts': {
            'stage': 2, 'name': 'Awaiting Parts', 'badge_class': 'badge-warning',
            'responsible': 'Spare Parts Dept', 'next_action': 'Await supplier delivery / notify on arrival',
            'icon': 'fa-solid fa-truck-clock'
        },
        'Awaiting Parts': {
            'stage': 2, 'name': 'Awaiting Parts', 'badge_class': 'badge-warning',
            'responsible': 'Spare Parts Dept', 'next_action': 'Await supplier delivery / notify on arrival',
            'icon': 'fa-solid fa-truck-clock'
        },
        'Ready to Schedule': {
            'stage': 3, 'name': 'Ready to Schedule', 'badge_class': 'badge-info',
            'responsible': 'Admin', 'next_action': 'Set planned work schedule & authorize repair',
            'icon': 'fa-solid fa-calendar-check'
        },
        'Scheduled': {
            'stage': 4, 'name': 'Scheduled', 'badge_class': 'badge-accepted',
            'responsible': 'Technician', 'next_action': 'Start repair work at scheduled time',
            'icon': 'fa-solid fa-calendar-day'
        },
        'In Progress': {
            'stage': 4, 'name': 'Repair In Progress', 'badge_class': 'badge-inservice',
            'responsible': 'Technician', 'next_action': 'Perform mechanical repair & complete work',
            'icon': 'fa-solid fa-wrench'
        },
        'On Hold': {
            'stage': 4, 'name': 'Repair On Hold', 'badge_class': 'badge-priority-low',
            'responsible': 'Technician', 'next_action': 'Resume repair work',
            'icon': 'fa-solid fa-pause'
        },
        'Awaiting Admin Approval': {
            'stage': 5, 'name': 'Awaiting Admin Approval', 'badge_class': 'badge-duesoon',
            'responsible': 'Admin', 'next_action': 'Review completed repair & approve/request revision',
            'icon': 'fa-solid fa-user-check'
        },
        'Revision Required': {
            'stage': 5, 'name': 'Revision Required', 'badge_class': 'badge-danger',
            'responsible': 'Technician', 'next_action': 'Address admin comments & resubmit repair',
            'icon': 'fa-solid fa-rotate-left'
        },
        'Approved - Pending Final Report': {
            'stage': 6, 'name': 'Admin Approved', 'badge_class': 'badge-active',
            'responsible': 'Technician', 'next_action': 'Submit certified final repair report',
            'icon': 'fa-solid fa-circle-check'
        },
        'Completed': {
            'stage': 7, 'name': 'Completed', 'badge_class': 'badge-active',
            'responsible': 'Closed', 'next_action': 'Work order finalized & closed',
            'icon': 'fa-solid fa-check-double'
        },
        'Cancelled': {
            'stage': 0, 'name': 'Cancelled', 'badge_class': 'badge-danger',
            'responsible': 'Closed', 'next_action': 'Work order cancelled',
            'icon': 'fa-solid fa-ban'
        }
    }
    return mapping.get(status_clean, {
        'stage': 1, 'name': status_clean or 'Pending', 'badge_class': 'badge-unpaid',
        'responsible': 'Staff', 'next_action': 'Review work order status',
        'icon': 'fa-solid fa-circle-info'
    })

@app.template_filter('workflow_meta')
def workflow_meta_filter(status):
    return get_workflow_stage_info(status)


# -------------------------------------------------------------
# Authentication Decorators
# -------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please sign in first.", "warning")
            return redirect(url_for('login'))
        if session.get('user_role') != 'Admin':
            flash("Administrator privileges required for this action.", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def technician_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please sign in first.", "warning")
            return redirect(url_for('login', next=request.url))
        if session.get('user_role') not in ('Technician', 'Admin'):
            flash("Technician workspace privileges required.", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def parts_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please sign in first.", "warning")
            return redirect(url_for('login'))
        if session.get('user_role') not in ('Spare Parts', 'Admin'):
            flash("Spare Parts Department privileges required.", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# -------------------------------------------------------------
# Error Handling
# -------------------------------------------------------------
@app.errorhandler(Error)
def handle_db_error(e):
    return render_template('db_error.html', error=str(e)), 500

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

# -------------------------------------------------------------
# Auth Routes
# -------------------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        if session.get('user_role') == 'Spare Parts':
            return redirect(url_for('parts_dashboard'))
        if session.get('user_role') == 'Technician':
            return redirect(url_for('tech_dashboard'))
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash("Email and password are required.", "danger")
            return render_template('auth/login.html')

        try:
            user = query_db(
                "SELECT id, name, email, password_hash, role, status FROM users WHERE email = %s",
                (email,), one=True
            )

            if user and check_password_hash(user['password_hash'], password):
                if user['status'] != 'Active':
                    flash("Your account has been deactivated. Please contact administrator.", "danger")
                    return render_template('auth/login.html')

                session.clear()
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                session['user_email'] = user['email']
                session['user_role'] = user['role']
                session.permanent = True

                flash(f"Welcome back, {user['name']}! System ready.", "success")
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                if user['role'] == 'Spare Parts':
                    return redirect(url_for('parts_dashboard'))
                if user['role'] == 'Technician':
                    return redirect(url_for('tech_dashboard'))
                return redirect(url_for('dashboard'))
            else:
                flash("Invalid email or password. Please try again.", "danger")
        except Exception as e:
            flash(f"Database error: {str(e)}. Please ensure XAMPP MySQL is running.", "danger")

    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'Technician')
        phone = request.form.get('phone', '').strip()

        if not name or not email or not password:
            flash("All required fields must be filled.", "danger")
            return render_template('auth/register.html')

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('auth/register.html')

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return render_template('auth/register.html')

        try:
            existing = query_db("SELECT id FROM users WHERE email = %s", (email,), one=True)
            if existing:
                flash("An account with this email already exists.", "warning")
                return render_template('auth/register.html')

            hashed = generate_password_hash(password)
            default_avatar = f"https://api.dicebear.com/7.x/initials/svg?seed={name}&backgroundColor=0284c7"

            user_id = query_db("""
                INSERT INTO users (name, email, password_hash, role, phone, avatar)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (name, email, hashed, role, phone, default_avatar), commit=True)

            flash("Registration successful! You can now log in.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"Error during registration: {str(e)}", "danger")

    return render_template('auth/register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been securely logged out.", "info")
    return redirect(url_for('login'))

# -------------------------------------------------------------
# Dashboard (Command Center)
# -------------------------------------------------------------
@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    if session.get('user_role') == 'Spare Parts':
        return redirect(url_for('parts_dashboard'))
    if session.get('user_role') == 'Technician':
        return redirect(url_for('tech_dashboard'))
    try:
        # Key Performance Indicators
        total_vehicles = query_db("SELECT COUNT(*) as cnt FROM vehicles", one=True)['cnt']
        active_services = query_db("SELECT COUNT(*) as cnt FROM service_records WHERE status IN ('In Progress', 'Waiting for Parts')", one=True)['cnt']
        due_schedules = query_db("SELECT COUNT(*) as cnt FROM maintenance_schedules WHERE status IN ('Overdue', 'Due Soon') OR next_due_date <= CURDATE()", one=True)['cnt']
        total_customers = query_db("SELECT COUNT(*) as cnt FROM customers", one=True)['cnt']
        total_revenue = query_db("SELECT COALESCE(SUM(total_cost), 0) as total FROM service_records WHERE status = 'Completed'", one=True)['total']

        # Urgent / Overdue schedules (top 5)
        urgent_schedules = query_db("""
            SELECT s.*, v.plate_number, v.make, v.model, v.current_odometer, c.name as customer_name, c.phone as customer_phone
            FROM maintenance_schedules s
            JOIN vehicles v ON s.vehicle_id = v.id
            JOIN customers c ON v.customer_id = c.id
            WHERE s.status IN ('Overdue', 'Due Soon') OR s.next_due_date <= CURDATE()
            ORDER BY s.next_due_date ASC
            LIMIT 5
        """)

        # Recent Service Work Orders (top 6)
        recent_services = query_db("""
            SELECT sr.*, v.plate_number, v.make, v.model, c.name as customer_name, u.name as tech_name
            FROM service_records sr
            JOIN vehicles v ON sr.vehicle_id = v.id
            JOIN customers c ON v.customer_id = c.id
            LEFT JOIN users u ON sr.user_id = u.id
            ORDER BY sr.service_date DESC, sr.id DESC
            LIMIT 6
        """)

        # Fleet Status Breakdown for Chart
        status_breakdown = query_db("""
            SELECT status, COUNT(*) as count FROM vehicles GROUP BY status
        """)

        # Service Types Breakdown
        service_types = query_db("""
            SELECT service_type, COUNT(*) as count, SUM(total_cost) as revenue
            FROM service_records
            GROUP BY service_type
            ORDER BY count DESC
            LIMIT 5
        """)

        return render_template(
            'dashboard.html',
            total_vehicles=total_vehicles,
            active_services=active_services,
            due_schedules=due_schedules,
            total_customers=total_customers,
            total_revenue=total_revenue,
            urgent_schedules=urgent_schedules,
            recent_services=recent_services,
            status_breakdown=status_breakdown,
            service_types=service_types
        )
    except Exception as e:
        status, msg = check_db_health()
        if not status:
            return render_template('db_error.html', error=msg)
        raise e

# -------------------------------------------------------------
# Vehicles Management
# -------------------------------------------------------------
@app.route('/vehicles')
@login_required
def vehicles_list():
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    type_filter = request.args.get('type', '').strip()

    sql = """
        SELECT v.*, c.name as customer_name, c.company_name, c.phone as customer_phone,
               (SELECT COUNT(*) FROM service_records sr WHERE sr.vehicle_id = v.id) as service_count,
               (SELECT COUNT(*) FROM maintenance_schedules ms WHERE ms.vehicle_id = v.id AND ms.status = 'Overdue') as overdue_count
        FROM vehicles v
        JOIN customers c ON v.customer_id = c.id
        WHERE 1=1
    """
    params = []

    if search:
        sql += " AND (v.plate_number LIKE %s OR v.vin LIKE %s OR v.make LIKE %s OR v.model LIKE %s OR c.name LIKE %s)"
        term = f"%{search}%"
        params.extend([term, term, term, term, term])

    if status_filter:
        sql += " AND v.status = %s"
        params.append(status_filter)

    if type_filter:
        sql += " AND v.vehicle_type = %s"
        params.append(type_filter)

    sql += " ORDER BY v.id DESC"
    vehicles = query_db(sql, tuple(params))

    return render_template(
        'vehicles/index.html',
        vehicles=vehicles,
        search=search,
        status_filter=status_filter,
        type_filter=type_filter
    )

@app.route('/vehicles/create', methods=['GET', 'POST'])
@login_required
def vehicle_create():
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        vin = request.form.get('vin', '').strip().upper()
        plate_number = request.form.get('plate_number', '').strip().upper()
        make = request.form.get('make', '').strip()
        model = request.form.get('model', '').strip()
        year = request.form.get('year', 2024)
        color = request.form.get('color', '').strip()
        fuel_type = request.form.get('fuel_type', 'Gasoline')
        vehicle_type = request.form.get('vehicle_type', 'Sedan')
        odometer = request.form.get('current_odometer', 0)
        status = request.form.get('status', 'Active')
        notes = request.form.get('notes', '').strip()
        image_url = request.form.get('image_url', '').strip()

        if not vin or not plate_number or not make or not model:
            flash("VIN, License Plate, Make, and Model are required.", "danger")
            customers = query_db("SELECT id, name, company_name FROM customers ORDER BY name")
            return render_template('vehicles/form.html', customers=customers, vehicle=None)

        try:
            # Check unique VIN / Plate
            existing = query_db(
                "SELECT id FROM vehicles WHERE vin = %s OR plate_number = %s",
                (vin, plate_number), one=True
            )
            if existing:
                flash("A vehicle with this VIN or License Plate already exists.", "warning")
                customers = query_db("SELECT id, name, company_name FROM customers ORDER BY name")
                return render_template('vehicles/form.html', customers=customers, vehicle=None)

            if not image_url:
                image_url = "https://images.unsplash.com/photo-1541899481282-d53bffe3c35d?auto=format&fit=crop&w=600&q=80"

            vehicle_id = query_db("""
                INSERT INTO vehicles (customer_id, vin, plate_number, make, model, year, color, fuel_type, vehicle_type, current_odometer, status, notes, image_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (customer_id, vin, plate_number, make, model, year, color, fuel_type, vehicle_type, odometer, status, notes, image_url), commit=True)

            # Auto-generate standard maintenance schedule intervals (Oil Change & Multi-Point Inspection)
            due_date_oil = (date.today() + timedelta(days=180)).isoformat()
            due_km_oil = int(odometer) + 8000
            query_db("""
                INSERT INTO maintenance_schedules (vehicle_id, service_name, interval_km, interval_months, next_due_date, next_due_odometer, priority, status, description)
                VALUES (%s, 'Engine Oil & Filter Service', 8000, 6, %s, %s, 'High', 'Upcoming', 'Full synthetic oil and OEM filter replacement')
            """, (vehicle_id, due_date_oil, due_km_oil), commit=True)

            flash(f"Vehicle '{make} {model}' ({plate_number}) successfully registered with standard schedules!", "success")
            return redirect(url_for('vehicle_detail', vehicle_id=vehicle_id))
        except Exception as e:
            flash(f"Failed to add vehicle: {str(e)}", "danger")

    customers = query_db("SELECT id, name, company_name FROM customers ORDER BY name")
    return render_template('vehicles/form.html', customers=customers, vehicle=None)

@app.route('/vehicles/<int:vehicle_id>')
@login_required
def vehicle_detail(vehicle_id):
    vehicle = query_db("""
        SELECT v.*, c.name as customer_name, c.company_name, c.email as customer_email, c.phone as customer_phone, c.address as customer_address, c.customer_type
        FROM vehicles v
        JOIN customers c ON v.customer_id = c.id
        WHERE v.id = %s
    """, (vehicle_id,), one=True)

    if not vehicle:
        flash("Vehicle not found.", "danger")
        return redirect(url_for('vehicles_list'))

    # Schedules for this vehicle
    schedules = query_db("""
        SELECT * FROM maintenance_schedules
        WHERE vehicle_id = %s
        ORDER BY next_due_date ASC
    """, (vehicle_id,))

    # Work order history
    service_history = query_db("""
        SELECT sr.*, u.name as tech_name
        FROM service_records sr
        LEFT JOIN users u ON sr.user_id = u.id
        WHERE sr.vehicle_id = %s
        ORDER BY sr.service_date DESC, sr.id DESC
    """, (vehicle_id,))

    # Total maintenance spent on this vehicle
    total_spent = sum([float(item['total_cost']) for item in service_history if item['status'] == 'Completed'])

    return render_template(
        'vehicles/view.html',
        vehicle=vehicle,
        schedules=schedules,
        service_history=service_history,
        total_spent=total_spent
    )

@app.route('/vehicles/<int:vehicle_id>/edit', methods=['GET', 'POST'])
@login_required
def vehicle_edit(vehicle_id):
    vehicle = query_db("SELECT * FROM vehicles WHERE id = %s", (vehicle_id,), one=True)
    if not vehicle:
        flash("Vehicle not found.", "danger")
        return redirect(url_for('vehicles_list'))

    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        vin = request.form.get('vin', '').strip().upper()
        plate_number = request.form.get('plate_number', '').strip().upper()
        make = request.form.get('make', '').strip()
        model = request.form.get('model', '').strip()
        year = request.form.get('year', 2024)
        color = request.form.get('color', '').strip()
        fuel_type = request.form.get('fuel_type', 'Gasoline')
        vehicle_type = request.form.get('vehicle_type', 'Sedan')
        odometer = request.form.get('current_odometer', 0)
        status = request.form.get('status', 'Active')
        notes = request.form.get('notes', '').strip()
        image_url = request.form.get('image_url', '').strip()

        try:
            query_db("""
                UPDATE vehicles
                SET customer_id=%s, vin=%s, plate_number=%s, make=%s, model=%s, year=%s,
                    color=%s, fuel_type=%s, vehicle_type=%s, current_odometer=%s, status=%s,
                    notes=%s, image_url=%s
                WHERE id = %s
            """, (customer_id, vin, plate_number, make, model, year, color, fuel_type, vehicle_type, odometer, status, notes, image_url, vehicle_id), commit=True)

            flash("Vehicle details updated successfully.", "success")
            return redirect(url_for('vehicle_detail', vehicle_id=vehicle_id))
        except Exception as e:
            flash(f"Error updating vehicle: {str(e)}", "danger")

    customers = query_db("SELECT id, name, company_name FROM customers ORDER BY name")
    return render_template('vehicles/form.html', customers=customers, vehicle=vehicle)

@app.route('/vehicles/<int:vehicle_id>/delete', methods=['POST'])
@login_required
def vehicle_delete(vehicle_id):
    try:
        query_db("DELETE FROM vehicles WHERE id = %s", (vehicle_id,), commit=True)
        flash("Vehicle and all associated history removed.", "info")
    except Exception as e:
        flash(f"Could not delete vehicle: {str(e)}", "danger")
    return redirect(url_for('vehicles_list'))

# -------------------------------------------------------------
# Customers Management
# -------------------------------------------------------------
@app.route('/customers')
@login_required
def customers_list():
    search = request.args.get('search', '').strip()
    type_filter = request.args.get('type', '').strip()

    sql = """
        SELECT c.*,
               COUNT(DISTINCT v.id) as vehicle_count,
               COALESCE(SUM(sr.total_cost), 0) as total_spent
        FROM customers c
        LEFT JOIN vehicles v ON c.id = v.customer_id
        LEFT JOIN service_records sr ON v.id = sr.vehicle_id AND sr.status = 'Completed'
        WHERE 1=1
    """
    params = []
    if search:
        sql += " AND (c.name LIKE %s OR c.company_name LIKE %s OR c.email LIKE %s OR c.phone LIKE %s)"
        term = f"%{search}%"
        params.extend([term, term, term, term])

    if type_filter:
        sql += " AND c.customer_type = %s"
        params.append(type_filter)

    sql += " GROUP BY c.id ORDER BY c.id DESC"
    customers = query_db(sql, tuple(params))

    return render_template(
        'customers/index.html',
        customers=customers,
        search=search,
        type_filter=type_filter
    )

@app.route('/customers/create', methods=['GET', 'POST'])
@login_required
def customer_create():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        company_name = request.form.get('company_name', '').strip()
        customer_type = request.form.get('customer_type', 'Individual')
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        postal_code = request.form.get('postal_code', '').strip()
        notes = request.form.get('notes', '').strip()

        if not name or not phone:
            flash("Customer Name and Phone Number are required.", "danger")
            return render_template('customers/form.html', customer=None)

        try:
            cid = query_db("""
                INSERT INTO customers (name, email, phone, company_name, customer_type, address, city, postal_code, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (name, email, phone, company_name if company_name else None, customer_type, address, city, postal_code, notes), commit=True)

            flash(f"Customer '{name}' successfully created!", "success")
            return redirect(url_for('customer_detail', customer_id=cid))
        except Exception as e:
            flash(f"Failed to create customer: {str(e)}", "danger")

    return render_template('customers/form.html', customer=None)

@app.route('/customers/<int:customer_id>')
@login_required
def customer_detail(customer_id):
    customer = query_db("SELECT * FROM customers WHERE id = %s", (customer_id,), one=True)
    if not customer:
        flash("Customer not found.", "danger")
        return redirect(url_for('customers_list'))

    vehicles = query_db("""
        SELECT v.*,
               (SELECT COUNT(*) FROM service_records sr WHERE sr.vehicle_id = v.id) as service_count
        FROM vehicles v
        WHERE v.customer_id = %s
        ORDER BY v.id DESC
    """, (customer_id,))

    services = query_db("""
        SELECT sr.*, v.plate_number, v.make, v.model, u.name as tech_name,
               (SELECT id FROM service_reports srep WHERE srep.service_record_id = sr.id LIMIT 1) as report_id
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        LEFT JOIN users u ON sr.user_id = u.id
        WHERE v.customer_id = %s
        ORDER BY sr.service_date DESC
    """, (customer_id,))

    total_spent = sum([float(item['total_cost']) for item in services if item['status'] == 'Completed'])

    return render_template(
        'customers/view.html',
        customer=customer,
        vehicles=vehicles,
        services=services,
        total_spent=total_spent
    )

@app.route('/customers/<int:customer_id>/edit', methods=['GET', 'POST'])
@login_required
def customer_edit(customer_id):
    customer = query_db("SELECT * FROM customers WHERE id = %s", (customer_id,), one=True)
    if not customer:
        flash("Customer not found.", "danger")
        return redirect(url_for('customers_list'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        company_name = request.form.get('company_name', '').strip()
        customer_type = request.form.get('customer_type', 'Individual')
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        postal_code = request.form.get('postal_code', '').strip()
        notes = request.form.get('notes', '').strip()

        try:
            query_db("""
                UPDATE customers
                SET name=%s, email=%s, phone=%s, company_name=%s, customer_type=%s,
                    address=%s, city=%s, postal_code=%s, notes=%s
                WHERE id = %s
            """, (name, email, phone, company_name if company_name else None, customer_type, address, city, postal_code, notes, customer_id), commit=True)

            flash("Customer updated successfully.", "success")
            return redirect(url_for('customer_detail', customer_id=customer_id))
        except Exception as e:
            flash(f"Failed to update customer: {str(e)}", "danger")

    return render_template('customers/form.html', customer=customer)

@app.route('/customers/<int:customer_id>/delete', methods=['POST'])
@login_required
def customer_delete(customer_id):
    try:
        query_db("DELETE FROM customers WHERE id = %s", (customer_id,), commit=True)
        flash("Customer profile and linked vehicles removed.", "info")
    except Exception as e:
        flash(f"Error deleting customer: {str(e)}", "danger")
    return redirect(url_for('customers_list'))

# -------------------------------------------------------------
# Maintenance Schedules & Tracking
# -------------------------------------------------------------
@app.route('/schedules')
@login_required
def schedules_list():
    status_filter = request.args.get('status', '').strip()
    priority_filter = request.args.get('priority', '').strip()

    sql = """
        SELECT ms.*, v.plate_number, v.make, v.model, v.current_odometer,
               c.name as customer_name, c.company_name, c.phone as customer_phone
        FROM maintenance_schedules ms
        JOIN vehicles v ON ms.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        WHERE 1=1
    """
    params = []

    if status_filter:
        sql += " AND ms.status = %s"
        params.append(status_filter)

    if priority_filter:
        sql += " AND ms.priority = %s"
        params.append(priority_filter)

    sql += " ORDER BY ms.next_due_date ASC, ms.priority DESC"
    schedules = query_db(sql, tuple(params))

    # Recalculate status dynamically based on current date and odometer
    for s in schedules:
        curr_odo = s['current_odometer'] or 0
        due_odo = s['next_due_odometer'] or 0
        due_date = s['next_due_date']

        # Determine dynamic status
        today = date.today()
        if due_date < today or curr_odo >= due_odo:
            calculated_status = 'Overdue'
        elif (due_date - today).days <= 14 or (due_odo - curr_odo) <= 1000:
            calculated_status = 'Due Soon'
        else:
            calculated_status = 'Upcoming'

        if calculated_status != s['status']:
            s['status'] = calculated_status
            query_db("UPDATE maintenance_schedules SET status = %s WHERE id = %s", (calculated_status, s['id']), commit=True)

    vehicles = query_db("SELECT id, plate_number, make, model FROM vehicles ORDER BY plate_number")

    return render_template(
        'schedules/index.html',
        schedules=schedules,
        vehicles=vehicles,
        status_filter=status_filter,
        priority_filter=priority_filter
    )

@app.route('/schedules/create', methods=['GET', 'POST'])
@login_required
def schedule_create():
    if request.method == 'POST':
        vehicle_id = request.form.get('vehicle_id')
        service_name = request.form.get('service_name', '').strip()
        interval_km = int(request.form.get('interval_km', 5000))
        interval_months = int(request.form.get('interval_months', 6))
        priority = request.form.get('priority', 'Medium')
        description = request.form.get('description', '').strip()

        # Fetch vehicle current odometer
        veh = query_db("SELECT current_odometer FROM vehicles WHERE id = %s", (vehicle_id,), one=True)
        curr_odo = veh['current_odometer'] if veh else 0

        next_due_date = (date.today() + timedelta(days=interval_months * 30)).isoformat()
        next_due_odometer = curr_odo + interval_km

        try:
            query_db("""
                INSERT INTO maintenance_schedules (vehicle_id, service_name, interval_km, interval_months,
                    last_service_date, last_service_odometer, next_due_date, next_due_odometer, priority, status, description)
                VALUES (%s, %s, %s, %s, CURDATE(), %s, %s, %s, %s, 'Upcoming', %s)
            """, (vehicle_id, service_name, interval_km, interval_months, curr_odo, next_due_date, next_due_odometer, priority, description), commit=True)

            flash("Maintenance schedule rule established successfully.", "success")
            return redirect(url_for('schedules_list'))
        except Exception as e:
            flash(f"Error creating schedule: {str(e)}", "danger")

    vehicles = query_db("SELECT id, plate_number, make, model, current_odometer FROM vehicles ORDER BY plate_number")
    return render_template('schedules/form.html', vehicles=vehicles, schedule=None)

@app.route('/schedules/<int:schedule_id>/edit', methods=['GET', 'POST'])
@login_required
def schedule_edit(schedule_id):
    schedule = query_db("SELECT * FROM maintenance_schedules WHERE id = %s", (schedule_id,), one=True)
    if not schedule:
        flash("Schedule not found.", "danger")
        return redirect(url_for('schedules_list'))

    if request.method == 'POST':
        service_name = request.form.get('service_name', '').strip()
        interval_km = int(request.form.get('interval_km', 5000))
        interval_months = int(request.form.get('interval_months', 6))
        next_due_date = request.form.get('next_due_date')
        next_due_odometer = int(request.form.get('next_due_odometer', 0))
        priority = request.form.get('priority', 'Medium')
        status = request.form.get('status', 'Upcoming')
        description = request.form.get('description', '').strip()

        try:
            query_db("""
                UPDATE maintenance_schedules
                SET service_name=%s, interval_km=%s, interval_months=%s, next_due_date=%s,
                    next_due_odometer=%s, priority=%s, status=%s, description=%s
                WHERE id = %s
            """, (service_name, interval_km, interval_months, next_due_date, next_due_odometer, priority, status, description, schedule_id), commit=True)

            flash("Schedule interval updated successfully.", "success")
            return redirect(url_for('schedules_list'))
        except Exception as e:
            flash(f"Error updating schedule: {str(e)}", "danger")

    vehicles = query_db("SELECT id, plate_number, make, model FROM vehicles ORDER BY plate_number")
    return render_template('schedules/form.html', vehicles=vehicles, schedule=schedule)

@app.route('/schedules/<int:schedule_id>/delete', methods=['POST'])
@login_required
def schedule_delete(schedule_id):
    try:
        query_db("DELETE FROM maintenance_schedules WHERE id = %s", (schedule_id,), commit=True)
        flash("Maintenance schedule deleted.", "info")
    except Exception as e:
        flash(f"Error deleting schedule: {str(e)}", "danger")
    return redirect(url_for('schedules_list'))

# -------------------------------------------------------------
# Work Orders & Service Records (History)
# -------------------------------------------------------------
@app.route('/services')
@login_required
def services_list():
    if session.get('user_role') == 'Technician':
        return redirect(url_for('tech_jobs'))

    status_filter = request.args.get('status', '').strip()
    payment_filter = request.args.get('payment', '').strip()
    search = request.args.get('search', '').strip()
    customer_id = request.args.get('customer_id', '').strip()
    vehicle_id = request.args.get('vehicle_id', '').strip()

    sql = """
        SELECT sr.*, v.plate_number, v.make, v.model, v.vin, c.name as customer_name, c.company_name, c.phone as customer_phone, u.name as tech_name
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        LEFT JOIN users u ON sr.user_id = u.id
        WHERE 1=1
    """
    params = []

    if search:
        sql += " AND (sr.invoice_number LIKE %s OR v.plate_number LIKE %s OR v.make LIKE %s OR v.model LIKE %s OR v.vin LIKE %s OR c.name LIKE %s OR c.company_name LIKE %s OR c.phone LIKE %s OR sr.service_type LIKE %s)"
        term = f"%{search}%"
        params.extend([term, term, term, term, term, term, term, term, term])

    if customer_id:
        sql += " AND v.customer_id = %s"
        params.append(customer_id)

    if vehicle_id:
        sql += " AND sr.vehicle_id = %s"
        params.append(vehicle_id)

    if status_filter:
        sql += " AND sr.status = %s"
        params.append(status_filter)

    if payment_filter:
        sql += " AND sr.payment_status = %s"
        params.append(payment_filter)

    sql += " ORDER BY sr.service_date DESC, sr.id DESC"
    services = query_db(sql, tuple(params))

    # Summary metrics
    total_rev = sum([float(s['total_cost']) for s in services if s['status'] == 'Completed'])
    in_progress_count = sum([1 for s in services if s['status'] in ('In Progress', 'Waiting for Parts')])

    return render_template(
        'services/index.html',
        services=services,
        search=search,
        status_filter=status_filter,
        payment_filter=payment_filter,
        total_rev=total_rev,
        in_progress_count=in_progress_count
    )

@app.route('/services/create', methods=['GET', 'POST'])
@login_required
def service_create():
    if session.get('user_role') == 'Technician':
        flash("Technicians do not have authority to create or edit cash and billing records. Work orders are assigned by Administration.", "warning")
        return redirect(url_for('tech_dashboard'))

    if request.method == 'POST':
        vehicle_id = request.form.get('vehicle_id')
        raw_user_id = request.form.get('user_id')
        user_id = int(raw_user_id) if raw_user_id and raw_user_id.strip() else None
        service_date = request.form.get('service_date', date.today().isoformat())
        appointment_date = request.form.get('appointment_date') or service_date
        appointment_time = request.form.get('appointment_time') or '10:00:00'
        odometer = int(request.form.get('odometer', 0))
        service_type = request.form.get('service_type', 'Preventive Maintenance')
        status = request.form.get('status', 'In Progress')
        priority = request.form.get('priority', 'Medium')
        payment_status = request.form.get('payment_status', 'Unpaid')
        description = request.form.get('description', '').strip()
        technician_notes = request.form.get('technician_notes', '').strip()

        # Parse line items
        item_types = request.form.getlist('item_type[]')
        item_names = request.form.getlist('item_name[]')
        quantities = request.form.getlist('item_quantity[]')
        unit_prices = request.form.getlist('item_price[]')

        parts_cost = 0.0
        labor_cost = 0.0
        items_data = []

        for i in range(len(item_names)):
            name = item_names[i].strip()
            if not name:
                continue
            itype = item_types[i] if i < len(item_types) else 'Part'
            try:
                qty = float(quantities[i]) if i < len(quantities) else 1.0
                price = float(unit_prices[i]) if i < len(unit_prices) else 0.0
            except ValueError:
                qty, price = 1.0, 0.0

            total = qty * price
            if itype == 'Labor':
                labor_cost += total
            else:
                parts_cost += total

            items_data.append((itype, name, qty, price, total))

        tax_amount = round((parts_cost + labor_cost) * 0.08, 2)  # 8% standard tax
        total_cost = round(parts_cost + labor_cost + tax_amount, 2)

        # Generate unique Work Order / Invoice Code: WO-YYYY-XXXX
        today_yr = datetime.now().year
        rand_suffix = int(datetime.now().strftime("%f")) % 9000 + 1000
        invoice_number = f"WO-{today_yr}-{rand_suffix}"

        completed_at = datetime.now() if status == 'Completed' else None

        try:
            record_id = query_db("""
                INSERT INTO service_records (
                    invoice_number, vehicle_id, user_id, service_date, appointment_date, appointment_time, odometer,
                    service_type, status, priority, description, technician_notes,
                    parts_cost, labor_cost, tax_amount, total_cost, payment_status, completed_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                invoice_number, vehicle_id, user_id, service_date, appointment_date, appointment_time, odometer,
                service_type, status, priority, description, technician_notes,
                parts_cost, labor_cost, tax_amount, total_cost, payment_status, completed_at
            ), commit=True)

            # Insert line items
            for item in items_data:
                query_db("""
                    INSERT INTO service_items (service_record_id, item_type, item_name, quantity, unit_price, total_price)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (record_id, item[0], item[1], item[2], item[3], item[4]), commit=True)

            # Update vehicle's current odometer and status
            veh_status = 'In Service' if status in ('In Progress', 'Waiting for Parts') else 'Active'
            query_db("""
                UPDATE vehicles
                SET current_odometer = GREATEST(current_odometer, %s), status = %s
                WHERE id = %s
            """, (odometer, veh_status, vehicle_id), commit=True)

            # Dispatch notification to assigned technician
            if user_id:
                veh = query_db("SELECT plate_number, make, model FROM vehicles WHERE id = %s", (vehicle_id,), one=True)
                plate_str = f"{veh['plate_number']} ({veh['make']} {veh['model']})" if veh else ""
                dispatch_notification(
                    user_id,
                    f"New Job Assignment: {invoice_number}",
                    f"You have been assigned to Work Order {invoice_number} for {plate_str}. Priority: {priority}. Scheduled for {appointment_date} at {appointment_time}.",
                    url_for('tech_job_detail', job_id=record_id),
                    notif_type='job_assigned'
                )

            flash(f"Work Order {invoice_number} created successfully!", "success")
            return redirect(url_for('service_detail', record_id=record_id))
        except Exception as e:
            flash(f"Error creating work order: {str(e)}", "danger")

    vehicles = query_db("SELECT id, plate_number, make, model, current_odometer FROM vehicles ORDER BY plate_number")
    preset_tech_id = request.args.get('tech_id', type=int)
    if preset_tech_id:
        technicians = query_db("""
            SELECT id, name, role, availability_status, specialization, skills 
            FROM users 
            WHERE role = 'Technician' 
              AND status = 'Active' 
              AND (availability_status = 'Available' OR id = %s) 
            ORDER BY name
        """, (preset_tech_id,))
    else:
        technicians = query_db("""
            SELECT id, name, role, availability_status, specialization, skills 
            FROM users 
            WHERE role = 'Technician' 
              AND status = 'Active' 
              AND availability_status = 'Available' 
            ORDER BY name
        """)
    preset_vehicle_id = request.args.get('vehicle_id', type=int)

    return render_template(
        'services/form.html',
        vehicles=vehicles,
        technicians=technicians,
        preset_vehicle_id=preset_vehicle_id,
        service=None,
        items=[]
    )

@app.route('/services/<int:record_id>')
@login_required
def service_detail(record_id):
    if session.get('user_role') == 'Technician':
        return redirect(url_for('tech_job_detail', job_id=record_id))

    service = query_db("""
        SELECT sr.*, v.plate_number, v.vin, v.make, v.model, v.year, v.color, v.fuel_type,
               c.id as customer_id, c.name as customer_name, c.company_name, c.email as customer_email,
               c.phone as customer_phone, c.address as customer_address, c.city as customer_city,
               u.name as tech_name, u.role as tech_role, u.email as tech_email
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        LEFT JOIN users u ON sr.user_id = u.id
        WHERE sr.id = %s
    """, (record_id,), one=True)

    if not service:
        flash("Work order not found.", "danger")
        return redirect(url_for('services_list'))

    items = query_db("SELECT * FROM service_items WHERE service_record_id = %s ORDER BY id", (record_id,))

    part_requests = query_db("""
        SELECT pr.*, sp.quantity as stock_qty, sp.shelf_location, u.name as tech_name
        FROM part_requests pr
        LEFT JOIN spare_parts sp ON pr.part_id = sp.id
        LEFT JOIN users u ON pr.requested_by = u.id
        WHERE pr.service_record_id = %s
        ORDER BY pr.id DESC
    """, (record_id,)) or []

    catalog_parts = query_db("""
        SELECT id, part_number, part_name, quantity, unit_price, shelf_location
        FROM spare_parts
        ORDER BY part_name ASC
    """) or []

    service_report = query_db("""
        SELECT sr.*, u.name as tech_name, u.technician_code
        FROM service_reports sr
        LEFT JOIN users u ON sr.technician_id = u.id
        WHERE sr.service_record_id = %s
    """, (record_id,), one=True)

    workflow_history = query_db("""
        SELECT swh.*, u.name as user_name, u.role as user_role_actual
        FROM service_workflow_history swh
        LEFT JOIN users u ON swh.action_by = u.id
        WHERE swh.service_record_id = %s
        ORDER BY swh.id ASC
    """, (record_id,)) or []

    return render_template(
        'services/view.html',
        service=service,
        items=items,
        part_requests=part_requests,
        catalog_parts=catalog_parts,
        service_report=service_report,
        workflow_history=workflow_history
    )

@app.route('/services/<int:record_id>/invoice')
@login_required
def service_invoice(record_id):
    """Clean, printable professional invoice view suitable for PDF export or browser print."""
    if session.get('user_role') == 'Technician':
        flash("Access denied: Customer billing invoices are restricted to Administrative review.", "danger")
        return redirect(url_for('tech_job_detail', job_id=record_id))

    service = query_db("""
        SELECT sr.*, v.plate_number, v.vin, v.make, v.model, v.year, v.color, v.vehicle_type,
               c.name as customer_name, c.company_name, c.email as customer_email, c.phone as customer_phone,
               c.address as customer_address, c.city as customer_city, c.postal_code as customer_postal,
               u.name as tech_name
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        LEFT JOIN users u ON sr.user_id = u.id
        WHERE sr.id = %s
    """, (record_id,), one=True)

    if not service:
        flash("Service record not found.", "danger")
        return redirect(url_for('services_list'))

    items = query_db("SELECT * FROM service_items WHERE service_record_id = %s ORDER BY id ASC", (record_id,))
    service_report = query_db("""
        SELECT sr.*, u.name as tech_name, u.technician_code
        FROM service_reports sr
        LEFT JOIN users u ON sr.technician_id = u.id
        WHERE sr.service_record_id = %s
    """, (record_id,), one=True)

    return render_template('services/invoice.html', service=service, items=items, service_report=service_report)

@app.route('/services/<int:record_id>/edit', methods=['GET', 'POST'])
@login_required
def service_edit(record_id):
    if session.get('user_role') == 'Technician':
        flash("Technicians do not have authority to edit cash, billing, or pricing details. Please report problem diagnostics through your assigned job workbench.", "warning")
        return redirect(url_for('tech_job_detail', job_id=record_id))

    service = query_db("SELECT * FROM service_records WHERE id = %s", (record_id,), one=True)
    if not service:
        flash("Work order not found.", "danger")
        return redirect(url_for('services_list'))

    if request.method == 'POST':
        raw_user_id = request.form.get('user_id')
        user_id = int(raw_user_id) if raw_user_id and raw_user_id.strip() else None
        service_date = request.form.get('service_date')
        appointment_date = request.form.get('appointment_date') or service['appointment_date'] or service_date
        appointment_time = request.form.get('appointment_time') or service['appointment_time'] or '10:00:00'
        odometer = int(request.form.get('odometer', 0))
        service_type = request.form.get('service_type')
        status = request.form.get('status')
        priority = request.form.get('priority') or service['priority'] or 'Medium'
        payment_status = request.form.get('payment_status')
        description = request.form.get('description', '').strip()
        technician_notes = request.form.get('technician_notes', '').strip()

        # Parse line items
        item_types = request.form.getlist('item_type[]')
        item_names = request.form.getlist('item_name[]')
        quantities = request.form.getlist('item_quantity[]')
        unit_prices = request.form.getlist('item_price[]')

        parts_cost = 0.0
        labor_cost = 0.0
        items_data = []

        for i in range(len(item_names)):
            name = item_names[i].strip()
            if not name:
                continue
            itype = item_types[i] if i < len(item_types) else 'Part'
            try:
                qty = float(quantities[i]) if i < len(quantities) else 1.0
                price = float(unit_prices[i]) if i < len(unit_prices) else 0.0
            except ValueError:
                qty, price = 1.0, 0.0

            total = qty * price
            if itype == 'Labor':
                labor_cost += total
            else:
                parts_cost += total

            items_data.append((itype, name, qty, price, total))

        tax_amount = round((parts_cost + labor_cost) * 0.08, 2)
        total_cost = round(parts_cost + labor_cost + tax_amount, 2)
        completed_at = datetime.now() if status == 'Completed' and not service['completed_at'] else service['completed_at']

        try:
            query_db("""
                UPDATE service_records
                SET user_id=%s, service_date=%s, appointment_date=%s, appointment_time=%s, priority=%s,
                    odometer=%s, service_type=%s, status=%s, payment_status=%s, description=%s, technician_notes=%s,
                    parts_cost=%s, labor_cost=%s, tax_amount=%s, total_cost=%s, completed_at=%s
                WHERE id = %s
            """, (user_id, service_date, appointment_date, appointment_time, priority,
                  odometer, service_type, status, payment_status, description, technician_notes,
                  parts_cost, labor_cost, tax_amount, total_cost, completed_at, record_id), commit=True)

            # Re-sync items: delete old items, insert updated
            query_db("DELETE FROM service_items WHERE service_record_id = %s", (record_id,), commit=True)
            for item in items_data:
                query_db("""
                    INSERT INTO service_items (service_record_id, item_type, item_name, quantity, unit_price, total_price)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (record_id, item[0], item[1], item[2], item[3], item[4]), commit=True)

            # If completed, set vehicle status to Active and resolve open parts requests
            if status == 'Completed':
                query_db("UPDATE vehicles SET status = 'Active', current_odometer = GREATEST(current_odometer, %s) WHERE id = %s",
                         (odometer, service['vehicle_id']), commit=True)
                query_db("""
                    UPDATE part_requests 
                    SET status = 'Completed' 
                    WHERE service_record_id = %s AND status NOT IN ('Not Available', 'Completed')
                """, (record_id,), commit=True)

            # Technician notifications on assignment, priority or schedule change
            if user_id:
                if not service['user_id'] or str(service['user_id']) != str(user_id):
                    dispatch_notification(
                        user_id,
                        f"Assigned to Job: {service['invoice_number']}",
                        f"You have been assigned to Work Order {service['invoice_number']} (Priority: {priority}). Scheduled on {appointment_date}.",
                        url_for('tech_job_detail', job_id=record_id),
                        notif_type='job_assigned'
                    )
                else:
                    if priority != service['priority']:
                        dispatch_notification(
                            user_id,
                            f"Job Priority Updated: {service['invoice_number']}",
                            f"Work Order {service['invoice_number']} priority updated from {service['priority']} to '{priority}'.",
                            url_for('tech_job_detail', job_id=record_id),
                            notif_type='priority_changed'
                        )
                    if str(appointment_date) != str(service['appointment_date']):
                        dispatch_notification(
                            user_id,
                            f"Appointment Date Updated: {service['invoice_number']}",
                            f"Work order {service['invoice_number']} appointment rescheduled to {appointment_date} at {appointment_time}.",
                            url_for('tech_job_detail', job_id=record_id),
                            notif_type='appointment_changed'
                        )

            flash(f"Work order {service['invoice_number']} updated successfully.", "success")
            return redirect(url_for('service_detail', record_id=record_id))
        except Exception as e:
            flash(f"Failed to update work order: {str(e)}", "danger")

    vehicles = query_db("SELECT id, plate_number, make, model FROM vehicles")
    curr_tech_id = service['user_id'] if (service and service['user_id']) else 0
    technicians = query_db("""
        SELECT id, name, role, availability_status, specialization, skills 
        FROM users 
        WHERE role = 'Technician' 
          AND status = 'Active' 
          AND (availability_status = 'Available' OR id = %s) 
        ORDER BY name
    """, (curr_tech_id,))
    items = query_db("SELECT * FROM service_items WHERE service_record_id = %s", (record_id,))

    return render_template(
        'services/form.html',
        vehicles=vehicles,
        technicians=technicians,
        service=service,
        items=items
    )

@app.route('/services/<int:record_id>/delete', methods=['POST'])
@login_required
@admin_required
def service_delete(record_id):
    try:
        query_db("DELETE FROM service_records WHERE id = %s", (record_id,), commit=True)
        flash("Work order deleted successfully.", "info")
    except Exception as e:
        flash(f"Failed to delete service record: {str(e)}", "danger")
    return redirect(url_for('services_list'))

@app.route('/services/<int:record_id>/reschedule-action', methods=['POST'])
@login_required
@admin_required
def service_reschedule_action(record_id):
    """Admin approves or declines a technician's appointment rescheduling request."""
    service = query_db("SELECT * FROM service_records WHERE id = %s", (record_id,), one=True)
    if not service:
        flash("Work order not found.", "danger")
        return redirect(url_for('services_list'))

    action = request.form.get('action', 'approve')
    tech_id = service['user_id']

    if action == 'approve':
        new_date = service['reschedule_date'] or service['appointment_date']
        new_time = service['reschedule_time'] or service['appointment_time']
        query_db("""
            UPDATE service_records 
            SET appointment_date = %s, appointment_time = %s, reschedule_requested = 0, reschedule_reason = NULL 
            WHERE id = %s
        """, (new_date, new_time, record_id), commit=True)

        if tech_id:
            dispatch_notification(
                tech_id,
                f"Reschedule Approved: {service['invoice_number']}",
                f"Your request to reschedule Work Order {service['invoice_number']} was APPROVED. New appointment: {new_date} at {new_time}.",
                url_for('tech_job_detail', job_id=record_id),
                notif_type='reschedule_response'
            )
        flash(f"Appointment rescheduled successfully to {new_date}. Technician notified.", "success")
    else:
        query_db("UPDATE service_records SET reschedule_requested = 0 WHERE id = %s", (record_id,), commit=True)
        if tech_id:
            dispatch_notification(
                tech_id,
                f"Reschedule Request Declined: {service['invoice_number']}",
                f"The rescheduling request for Work Order {service['invoice_number']} could not be approved. The original schedule ({service['appointment_date']}) remains active.",
                url_for('tech_job_detail', job_id=record_id),
                notif_type='reschedule_response'
            )
        flash(f"Reschedule request declined. Technician notified.", "info")

    return redirect(request.referrer or url_for('service_detail', record_id=record_id))

@app.route('/services/<int:record_id>/send-tech-message', methods=['POST'])
@login_required
@admin_required
def service_send_tech_message(record_id):
    """Admin dispatches an in-app priority communication or note to the assigned technician."""
    service = query_db("SELECT sr.*, u.name as tech_name FROM service_records sr LEFT JOIN users u ON sr.user_id = u.id WHERE sr.id = %s", (record_id,), one=True)
    if not service or not service['user_id']:
        flash("Assigned technician not found on this work order.", "danger")
        return redirect(url_for('service_detail', record_id=record_id))

    message = request.form.get('message', '').strip()
    if not message:
        flash("Message content is required.", "danger")
        return redirect(url_for('service_detail', record_id=record_id))

    dispatch_notification(
        service['user_id'],
        f"Admin Message: {service['invoice_number']}",
        f"Message from {session.get('user_name', 'Admin')} regarding {service['invoice_number']}: \"{message}\"",
        url_for('tech_job_detail', job_id=record_id),
        notif_type='admin_message'
    )
    flash(f"Message dispatched directly to technician {service['tech_name']}.", "success")
    return redirect(url_for('service_detail', record_id=record_id))

@app.route('/services/<int:record_id>/authorize-schedule', methods=['POST'])
@login_required
@admin_required
def admin_authorize_schedule(record_id):
    """Admin authorizes and schedules planned work taking technician diagnosis, lead times, and duration into account."""
    service = query_db("""
        SELECT sr.*, v.plate_number, v.make, v.model, u.name as tech_name
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        LEFT JOIN users u ON sr.user_id = u.id
        WHERE sr.id = %s
    """, (record_id,), one=True)
    if not service:
        flash("Work order not found.", "danger")
        return redirect(url_for('services_list'))

    scheduled_date = request.form.get('scheduled_date', '').strip()
    scheduled_time = request.form.get('scheduled_time', '10:00:00').strip()
    schedule_notes = request.form.get('schedule_notes', '').strip()

    if not scheduled_date:
        flash("Planned schedule date is required to authorize the work.", "danger")
        return redirect(url_for('service_detail', record_id=record_id))

    try:
        prev_status = service['status']
        query_db("""
            UPDATE service_records
            SET status = 'Scheduled',
                admin_scheduled_date = %s,
                admin_scheduled_time = %s,
                appointment_date = %s,
                appointment_time = %s,
                admin_schedule_notes = %s,
                admin_approved_at = NOW(),
                admin_approved_by = %s
            WHERE id = %s
        """, (scheduled_date, scheduled_time, scheduled_date, scheduled_time, schedule_notes, session['user_id'], record_id), commit=True)

        admin_name = session.get('user_name', 'Admin')
        log_workflow_action(
            record_id,
            prev_status,
            'Scheduled',
            session['user_id'],
            'Admin',
            'Repair Authorized & Scheduled by Admin',
            f"Planned Date: {scheduled_date} at {scheduled_time}. Notes: {schedule_notes}" if schedule_notes else f"Planned Date: {scheduled_date} at {scheduled_time}."
        )

        # Notify assigned technician
        if service['user_id']:
            dispatch_notification(
                service['user_id'],
                f"Work Authorized & Scheduled: {service['invoice_number']}",
                f"{admin_name} authorized and scheduled repair for {scheduled_date} at {scheduled_time}. {schedule_notes}".strip(),
                url_for('tech_job_detail', job_id=record_id),
                notif_type='job_scheduled'
            )

        flash(f"Work Order {service['invoice_number']} successfully AUTHORIZED and scheduled for {scheduled_date} at {scheduled_time}. Assigned technician notified.", "success")
    except Exception as e:
        flash(f"Failed to authorize and schedule work: {str(e)}", "danger")

    return redirect(url_for('service_detail', record_id=record_id))

@app.route('/services/<int:record_id>/admin-review', methods=['POST'])
@login_required
@admin_required
def admin_review_repair(record_id):
    """Admin reviews completed repair: either approves it for final reporting or returns with revision comments."""
    service = query_db("""
        SELECT sr.*, v.plate_number, v.make, v.model, u.name as tech_name
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        LEFT JOIN users u ON sr.user_id = u.id
        WHERE sr.id = %s
    """, (record_id,), one=True)
    if not service:
        flash("Work order not found.", "danger")
        return redirect(url_for('services_list'))

    decision = request.form.get('decision', '').strip()
    review_comments = request.form.get('review_comments', '').strip()
    admin_name = session.get('user_name', 'Admin')
    prev_status = service['status']

    if decision == 'approve':
        try:
            existing_report = query_db("SELECT * FROM service_reports WHERE service_record_id = %s", (record_id,), one=True)
            discount_raw = request.form.get('discount_amount', '').strip()
            discount = max(0.0, parse_float_field(discount_raw, float(service.get('discount_amount', 0.0) or 0.0)))

            if existing_report or service.get('bill_status') == 'Under Review':
                parts_cost = float(service.get('parts_cost') or 0.0)
                labor_cost = float(service.get('labor_cost') or 0.0)
                tax_amount = float(service.get('tax_amount') or 0.0)
                total_cost = max(0.0, round(parts_cost + labor_cost + tax_amount - discount, 2))

                query_db("""
                    UPDATE service_records
                    SET status = 'Completed',
                        bill_status = 'Approved',
                        discount_amount = %s,
                        total_cost = %s,
                        completed_at = COALESCE(completed_at, NOW()),
                        admin_approved_at = NOW(),
                        admin_approved_by = %s,
                        admin_review_comments = %s
                    WHERE id = %s
                """, (discount, total_cost, session['user_id'], review_comments or 'Completed repair report and itemized bill verified and approved by Admin.', record_id), commit=True)

                if discount > 0:
                    log_pricing_change('Bill Discount', record_id, f"Work Order {service['invoice_number']}", 'Discount Applied', "₹0.00", f"₹{discount:.2f}", session['user_id'], f"Admin promotional discount of ₹{discount:.2f} applied to final bill")

                query_db("UPDATE vehicles SET status = 'Active' WHERE id = %s", (service['vehicle_id'],), commit=True)

                log_workflow_action(
                    record_id,
                    prev_status,
                    'Completed',
                    session['user_id'],
                    'Admin',
                    'Work Order Completion & Final Itemized Bill Approved',
                    f"Report and bill approved by Admin {admin_name}. Total Billed: ₹{total_cost:,.2f} (Discount: ₹{discount:,.2f}). Work order closed and saved to customer history."
                )

                if service['user_id']:
                    dispatch_notification(
                        service['user_id'],
                        f"Work Order & Bill Approved: {service['invoice_number']}",
                        f"{admin_name} approved your repair report and itemized bill for {service['invoice_number']}. Total Billed: ₹{total_cost:,.2f}.",
                        url_for('tech_job_detail', job_id=record_id),
                        notif_type='job_completed'
                    )

                flash(f"Work Order {service['invoice_number']} and itemized bill (₹{total_cost:,.2f}) APPROVED! Vehicle returned to Active service and records saved to customer history.", "success")
            else:
                query_db("""
                    UPDATE service_records
                    SET status = 'Approved - Pending Final Report',
                        admin_review_comments = %s
                    WHERE id = %s
                """, (review_comments or 'Completed repair verified and approved.', record_id), commit=True)

                log_workflow_action(
                    record_id,
                    prev_status,
                    'Approved - Pending Final Report',
                    session['user_id'],
                    'Admin',
                    'Completed Repair Quality Approved by Admin',
                    review_comments or 'Work completed satisfactorily. Authorized for final certified reporting.'
                )

                if service['user_id']:
                    dispatch_notification(
                        service['user_id'],
                        f"Repair Approved by Admin: {service['invoice_number']}",
                        f"{admin_name} approved your repair work for Work Order {service['invoice_number']}. Please proceed to submit the certified Final Repair Report.",
                        url_for('tech_job_report_form', job_id=record_id),
                        notif_type='repair_approved'
                    )

                flash(f"Repair work for {service['invoice_number']} APPROVED! Technician notified to submit the final certified report.", "success")
        except Exception as e:
            flash(f"Failed to approve repair: {str(e)}", "danger")

    elif decision == 'revision':
        if not review_comments:
            flash("Please provide detailed comments explaining what additional work or revision is required.", "danger")
            return redirect(url_for('service_detail', record_id=record_id))

        try:
            query_db("""
                UPDATE service_records
                SET status = 'Revision Required',
                    bill_status = 'Revision Requested',
                    admin_review_comments = %s
                WHERE id = %s
            """, (review_comments, record_id), commit=True)

            log_workflow_action(
                record_id,
                prev_status,
                'Revision Required',
                session['user_id'],
                'Admin',
                'Revision Required - Returned to Technician',
                review_comments
            )

            if service['user_id']:
                dispatch_notification(
                    service['user_id'],
                    f"Revision Required: {service['invoice_number']}",
                    f"Admin {admin_name} returned Work Order {service['invoice_number']} for revisions: \"{review_comments}\"",
                    url_for('tech_job_detail', job_id=record_id),
                    notif_type='revision_required'
                )

            flash(f"Work order returned to technician with revision instructions.", "warning")
        except Exception as e:
            flash(f"Failed to request revision: {str(e)}", "danger")

    else:
        flash("Invalid review decision.", "danger")

    return redirect(url_for('service_detail', record_id=record_id))

# -------------------------------------------------------------
# Automated Reminders & Customer Outreach Center
# -------------------------------------------------------------
@app.route('/reminders')
@login_required
def reminders_list():
    status_filter = request.args.get('status', '').strip()

    sql = """
        SELECT r.*, v.plate_number, v.make, v.model,
               c.name as customer_name, c.email as customer_email, c.phone as customer_phone, c.company_name
        FROM reminders r
        JOIN vehicles v ON r.vehicle_id = v.id
        JOIN customers c ON r.customer_id = c.id
        WHERE 1=1
    """
    params = []
    if status_filter:
        sql += " AND r.status = %s"
        params.append(status_filter)

    sql += " ORDER BY r.status DESC, r.reminder_date ASC, r.id DESC"
    reminders = query_db(sql, tuple(params))

    # Also detect schedules that are due but don't have pending reminders yet
    unreminded_schedules = query_db("""
        SELECT ms.*, v.plate_number, v.make, v.model, c.name as customer_name, c.email as customer_email
        FROM maintenance_schedules ms
        JOIN vehicles v ON ms.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        WHERE ms.status IN ('Overdue', 'Due Soon')
        AND ms.id NOT IN (SELECT schedule_id FROM reminders WHERE schedule_id IS NOT NULL AND status = 'Scheduled')
        LIMIT 5
    """)

    return render_template(
        'reminders/index.html',
        reminders=reminders,
        unreminded_schedules=unreminded_schedules,
        status_filter=status_filter
    )

@app.route('/reminders/scan-and-generate', methods=['POST'])
@login_required
def reminders_scan():
    """
    Automated engine: Scans all maintenance schedules and automatically queues
    reminders for any vehicles with upcoming or overdue services.
    """
    try:
        due_schedules = query_db("""
            SELECT ms.id as schedule_id, ms.service_name, ms.next_due_date, ms.next_due_odometer,
                   v.id as vehicle_id, v.plate_number, v.make, v.model,
                   c.id as customer_id, c.name as customer_name, c.phone, c.email
            FROM maintenance_schedules ms
            JOIN vehicles v ON ms.vehicle_id = v.id
            JOIN customers c ON v.customer_id = c.id
            WHERE ms.status IN ('Overdue', 'Due Soon') OR ms.next_due_date <= DATE_ADD(CURDATE(), INTERVAL 14 DAY)
        """)

        created_count = 0
        for s in due_schedules:
            # Check if active scheduled reminder already exists
            existing = query_db(
                "SELECT id FROM reminders WHERE schedule_id = %s AND status = 'Scheduled'",
                (s['schedule_id'],), one=True
            )
            if not existing:
                msg = f"Reminder for {s['customer_name']}: Your {s['make']} {s['model']} ({s['plate_number']}) is due for {s['service_name']} by {s['next_due_date']}. Please contact FleetSync Service Center to book an appointment."
                query_db("""
                    INSERT INTO reminders (vehicle_id, customer_id, schedule_id, reminder_type, channel, status, reminder_date, message_preview)
                    VALUES (%s, %s, %s, 'Service Due', 'Email', 'Scheduled', CURDATE(), %s)
                """, (s['vehicle_id'], s['customer_id'], s['schedule_id'], msg), commit=True)
                created_count += 1

        flash(f"Automated scan completed! Generated {created_count} new service reminders.", "success")
    except Exception as e:
        flash(f"Scan error: {str(e)}", "danger")

    return redirect(url_for('reminders_list'))

@app.route('/reminders/<int:reminder_id>/send', methods=['POST'])
@login_required
def reminder_send(reminder_id):
    try:
        query_db("""
            UPDATE reminders
            SET status = 'Sent', sent_at = NOW()
            WHERE id = %s
        """, (reminder_id,), commit=True)

        flash("Automated reminder dispatched successfully to customer!", "success")
    except Exception as e:
        flash(f"Failed to dispatch reminder: {str(e)}", "danger")

    return redirect(url_for('reminders_list'))

# -------------------------------------------------------------
# Reports & Analytics
# -------------------------------------------------------------
@app.route('/reports')
@login_required
@admin_required
def reports():
    try:
        # Monthly Revenue trends (last 6 months)
        monthly_revenue = query_db("""
            SELECT DATE_FORMAT(service_date, '%b %Y') as month_label,
                   COUNT(*) as work_orders_count,
                   SUM(parts_cost) as total_parts,
                   SUM(labor_cost) as total_labor,
                   SUM(total_cost) as total_revenue
            FROM service_records
            WHERE status = 'Completed'
            GROUP BY DATE_FORMAT(service_date, '%Y-%m')
            ORDER BY DATE_FORMAT(service_date, '%Y-%m') DESC
            LIMIT 6
        """)

        # Top 5 most serviced vehicles
        top_vehicles = query_db("""
            SELECT v.plate_number, v.make, v.model, c.name as customer_name,
                   COUNT(sr.id) as service_count,
                   SUM(sr.total_cost) as total_spent
            FROM vehicles v
            JOIN customers c ON v.customer_id = c.id
            JOIN service_records sr ON v.id = sr.vehicle_id
            WHERE sr.status = 'Completed'
            GROUP BY v.id
            ORDER BY total_spent DESC
            LIMIT 5
        """)

        # Technician work performance
        tech_performance = query_db("""
            SELECT u.name as tech_name,
                   COUNT(sr.id) as total_jobs,
                   SUM(sr.labor_cost) as total_labor_billed
            FROM users u
            LEFT JOIN service_records sr ON u.id = sr.user_id AND sr.status = 'Completed'
            GROUP BY u.id
            ORDER BY total_jobs DESC
        """)

        return render_template(
            'reports/index.html',
            monthly_revenue=monthly_revenue,
            top_vehicles=top_vehicles,
            tech_performance=tech_performance
        )
    except Exception as e:
        flash(f"Error loading analytics: {str(e)}", "danger")
        return redirect(url_for('dashboard'))

@app.route('/reports/export/csv')
@login_required
def export_csv():
    """Generates downloadable CSV report of all service records."""
    records = query_db("""
        SELECT sr.invoice_number, sr.service_date, v.plate_number, v.make, v.model,
               c.name as customer_name, sr.service_type, sr.status,
               sr.parts_cost, sr.labor_cost, sr.tax_amount, sr.total_cost, sr.payment_status
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        ORDER BY sr.service_date DESC
    """)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Invoice Number', 'Service Date', 'Plate Number', 'Vehicle',
        'Customer Name', 'Service Type', 'Status',
        'Parts Cost (₹)', 'Labor Cost (₹)', 'Tax (₹)', 'Total Cost (₹)', 'Payment Status'
    ])

    for r in records:
        writer.writerow([
            r['invoice_number'], r['service_date'], r['plate_number'],
            f"{r['make']} {r['model']}", r['customer_name'],
            r['service_type'], r['status'],
            r['parts_cost'], r['labor_cost'], r['tax_amount'], r['total_cost'], r['payment_status']
        ])

    output.seek(0)
    filename = f"fleetsync_services_export_{datetime.now().strftime('%Y%m%d')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

@app.route('/admin/invoices')
@app.route('/reports/invoices')
@login_required
@admin_required
def invoice_report():
    """Admin Invoice Report with multi-criteria filtering by Date, Customer, and Name."""
    customer_id = (request.args.get('customer_id') or request.args.get('customer') or request.args.get('customer_name') or '').strip()
    name = request.args.get('name', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    payment_status = request.args.get('payment_status', 'All').strip()
    service_status = request.args.get('service_status', 'All').strip()

    query = """
        SELECT sr.*, DATE_ADD(sr.service_date, INTERVAL 30 DAY) as due_date,
               v.plate_number, v.make, v.model,
               c.id as customer_id, c.name as customer_name, c.company_name, c.phone as customer_phone, c.email as customer_email,
               u.name as tech_name
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        LEFT JOIN users u ON sr.user_id = u.id
        WHERE 1=1
    """
    params = []

    # Dedicated Customer ID Filter (applies strictly before fetching invoices)
    if customer_id and customer_id != 'All':
        if customer_id.isdigit():
            query += " AND c.id = %s"
            params.append(int(customer_id))
        else:
            query += " AND (c.name LIKE %s OR c.company_name LIKE %s)"
            params.extend([f"%{customer_id}%", f"%{customer_id}%"])

    # General Name / Company / Invoice # / Vehicle Search
    if name:
        query += """ AND (
            c.name LIKE %s OR 
            c.company_name LIKE %s OR 
            sr.invoice_number LIKE %s OR 
            v.plate_number LIKE %s OR 
            v.make LIKE %s OR 
            v.model LIKE %s
        )"""
        params.extend([f"%{name}%", f"%{name}%", f"%{name}%", f"%{name}%", f"%{name}%", f"%{name}%"])

    if start_date:
        query += " AND sr.service_date >= %s"
        params.append(start_date)

    if end_date:
        query += " AND sr.service_date <= %s"
        params.append(end_date)

    if payment_status and payment_status != 'All':
        query += " AND sr.payment_status = %s"
        params.append(payment_status)

    if service_status and service_status != 'All':
        query += " AND sr.status = %s"
        params.append(service_status)

    query += " ORDER BY sr.service_date DESC, sr.id DESC"

    try:
        invoices = query_db(query, tuple(params)) or []
    except Exception as e:
        flash(f"Error querying invoice report: {str(e)}", "danger")
        invoices = []

    # Retrieve all items and calculate complete financial details for every matched invoice
    for inv in invoices:
        items = query_db("""
            SELECT item_type, item_name, quantity, unit_price, total_price 
            FROM service_items 
            WHERE service_record_id = %s 
            ORDER BY id ASC
        """, (inv['id'],)) or []
        inv['line_items'] = items

        parts_cost = float(inv.get('parts_cost', 0) or 0)
        labor_cost = float(inv.get('labor_cost', 0) or 0)
        tax_amount = float(inv.get('tax_amount', 0) or 0)
        total_cost = float(inv.get('total_cost', 0) or 0)

        inv['subtotal'] = parts_cost + labor_cost
        inv['tax_amount'] = tax_amount
        inv['total_amount'] = total_cost

        # Exact Paid vs Pending amounts
        p_status = inv.get('payment_status', 'Unpaid')
        if p_status == 'Paid':
            inv['paid_amount'] = total_cost
            inv['pending_amount'] = 0.0
        elif p_status == 'Partially Paid':
            inv['paid_amount'] = round(total_cost * 0.5, 2)
            inv['pending_amount'] = round(total_cost - inv['paid_amount'], 2)
        else: # Unpaid
            inv['paid_amount'] = 0.0
            inv['pending_amount'] = total_cost

    # Retrieve all customers for the dropdown filter
    all_customers = query_db("SELECT id, name, company_name FROM customers ORDER BY name ASC") or []

    # Compute Aggregate Financial Metrics based ONLY on filtered invoices
    total_count = len(invoices)
    total_billed = sum(i['total_amount'] for i in invoices)
    total_parts = sum(float(i.get('parts_cost', 0) or 0) for i in invoices)
    total_labor = sum(float(i.get('labor_cost', 0) or 0) for i in invoices)
    total_tax = sum(float(i.get('tax_amount', 0) or 0) for i in invoices)
    total_paid = sum(i['paid_amount'] for i in invoices)
    total_unpaid = sum(i['pending_amount'] for i in invoices)

    return render_template(
        'reports/invoices.html',
        invoices=invoices,
        all_customers=all_customers,
        customer_id=customer_id,
        name=name,
        start_date=start_date,
        end_date=end_date,
        payment_status=payment_status,
        service_status=service_status,
        total_count=total_count,
        total_billed=total_billed,
        total_parts=total_parts,
        total_labor=total_labor,
        total_tax=total_tax,
        total_paid=total_paid,
        total_unpaid=total_unpaid
    )

@app.route('/admin/invoices/export')
@login_required
@admin_required
def export_invoice_report_csv():
    """Generates filtered CSV download based on applied date, customer & name filters."""
    customer_id = (request.args.get('customer_id') or request.args.get('customer') or request.args.get('customer_name') or '').strip()
    name = request.args.get('name', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    payment_status = request.args.get('payment_status', 'All').strip()
    service_status = request.args.get('service_status', 'All').strip()

    query = """
        SELECT sr.*, DATE_ADD(sr.service_date, INTERVAL 30 DAY) as due_date,
               v.plate_number, v.make, v.model,
               c.name as customer_name, c.company_name,
               u.name as tech_name
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        LEFT JOIN users u ON sr.user_id = u.id
        WHERE 1=1
    """
    params = []

    if customer_id and customer_id != 'All':
        if customer_id.isdigit():
            query += " AND c.id = %s"
            params.append(int(customer_id))
        else:
            query += " AND (c.name LIKE %s OR c.company_name LIKE %s)"
            params.extend([f"%{customer_id}%", f"%{customer_id}%"])

    if name:
        query += """ AND (
            c.name LIKE %s OR 
            c.company_name LIKE %s OR 
            sr.invoice_number LIKE %s OR 
            v.plate_number LIKE %s OR 
            v.make LIKE %s OR 
            v.model LIKE %s
        )"""
        params.extend([f"%{name}%", f"%{name}%", f"%{name}%", f"%{name}%", f"%{name}%", f"%{name}%"])

    if start_date:
        query += " AND sr.service_date >= %s"
        params.append(start_date)

    if end_date:
        query += " AND sr.service_date <= %s"
        params.append(end_date)

    if payment_status and payment_status != 'All':
        query += " AND sr.payment_status = %s"
        params.append(payment_status)

    if service_status and service_status != 'All':
        query += " AND sr.status = %s"
        params.append(service_status)

    query += " ORDER BY sr.service_date DESC, sr.id DESC"

    records = query_db(query, tuple(params)) or []

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Invoice Number', 'Customer Name', 'Company Name', 'Invoice Date', 'Due Date',
        'Item Details (Name, Qty, Rate, Total)', 'Subtotal (₹)', 'Tax Amount (₹)',
        'Total Amount (₹)', 'Paid Amount (₹)', 'Pending Amount (₹)',
        'Payment Status', 'Job Status', 'Vehicle Plate', 'Vehicle Make/Model'
    ])

    for r in records:
        items = query_db("""
            SELECT item_type, item_name, quantity, unit_price, total_price 
            FROM service_items 
            WHERE service_record_id = %s 
            ORDER BY id ASC
        """, (r['id'],)) or []

        parts_cost = float(r.get('parts_cost', 0) or 0)
        labor_cost = float(r.get('labor_cost', 0) or 0)
        tax_amount = float(r.get('tax_amount', 0) or 0)
        total_cost = float(r.get('total_cost', 0) or 0)
        subtotal = parts_cost + labor_cost

        p_status = r.get('payment_status', 'Unpaid')
        if p_status == 'Paid':
            paid_amount = total_cost
            pending_amount = 0.0
        elif p_status == 'Partially Paid':
            paid_amount = round(total_cost * 0.5, 2)
            pending_amount = round(total_cost - paid_amount, 2)
        else:
            paid_amount = 0.0
            pending_amount = total_cost

        item_str = "; ".join([f"{it['item_name']} (Qty: {it['quantity']}, Rate: ₹{it['unit_price']}, Total: ₹{it['total_price']})" for it in items])

        writer.writerow([
            r['invoice_number'], r['customer_name'], r['company_name'] or 'N/A',
            r['service_date'], r['due_date'],
            item_str, subtotal, tax_amount, total_cost, paid_amount, pending_amount,
            r['payment_status'], r['status'], r['plate_number'], f"{r['make']} {r['model']}"
        ])

    output.seek(0)
    filename = f"fleetsync_invoices_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

# =============================================================
# Admin Invoice Payments & Settlement Center ("Invoice Paid")
# =============================================================

@app.route('/admin/invoices/payments')
@app.route('/admin/invoice-paid')
@login_required
@admin_required
def admin_invoice_payments():
    """
    Invoice Paid & Payment Management Center for Administrators.
    Provides current/latest invoice registry, 1-click submit payment, and mark invoices as Paid or Unpaid.
    """
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'All').strip()
    date_filter = request.args.get('date_filter', 'All').strip()

    sql = """
        SELECT sr.id, sr.invoice_number, sr.service_date, sr.service_type, sr.status as job_status,
               sr.parts_cost, sr.labor_cost, sr.tax_amount, sr.discount_amount, sr.total_cost,
               sr.payment_status, sr.payment_method, sr.payment_date, sr.payment_notes,
               sr.bill_status, sr.bill_generated_at, sr.created_at, sr.completed_at,
               DATE_ADD(COALESCE(sr.service_date, DATE(sr.created_at)), INTERVAL 30 DAY) as due_date,
               v.plate_number, v.make, v.model,
               c.id as customer_id, c.name as customer_name, c.phone as customer_phone,
               c.email as customer_email, c.company_name,
               u.name as technician_name
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        LEFT JOIN users u ON sr.user_id = u.id
        WHERE 1=1
    """
    params = []

    if search:
        sql += """ AND (
            sr.invoice_number LIKE %s OR 
            c.name LIKE %s OR 
            c.company_name LIKE %s OR 
            c.phone LIKE %s OR 
            v.plate_number LIKE %s OR 
            v.make LIKE %s OR 
            v.model LIKE %s
        )"""
        term = f"%{search}%"
        params.extend([term, term, term, term, term, term, term])

    if status_filter and status_filter != 'All':
        sql += " AND sr.payment_status = %s"
        params.append(status_filter)

    if date_filter == 'Today':
        sql += " AND DATE(COALESCE(sr.service_date, sr.created_at)) = CURDATE()"
    elif date_filter == 'This Month':
        sql += " AND YEAR(COALESCE(sr.service_date, sr.created_at)) = YEAR(CURDATE()) AND MONTH(COALESCE(sr.service_date, sr.created_at)) = MONTH(CURDATE())"

    # Always sort by newest / current invoice first
    sql += " ORDER BY sr.id DESC"

    invoices = query_db(sql, tuple(params)) or []

    # Calculate metrics across all current invoices
    total_invoices = query_db("SELECT COUNT(*) as cnt FROM service_records", one=True)['cnt'] or 0
    paid_count = query_db("SELECT COUNT(*) as cnt FROM service_records WHERE payment_status = 'Paid'", one=True)['cnt'] or 0
    unpaid_count = query_db("SELECT COUNT(*) as cnt FROM service_records WHERE payment_status != 'Paid'", one=True)['cnt'] or 0

    total_billed = query_db("SELECT COALESCE(SUM(total_cost), 0) as total FROM service_records", one=True)['total'] or 0.0
    total_paid = query_db("SELECT COALESCE(SUM(total_cost), 0) as total FROM service_records WHERE payment_status = 'Paid'", one=True)['total'] or 0.0
    total_unpaid = query_db("SELECT COALESCE(SUM(total_cost), 0) as total FROM service_records WHERE payment_status != 'Paid'", one=True)['total'] or 0.0

    return render_template(
        'admin/invoices/payments.html',
        invoices=invoices,
        search=search,
        status_filter=status_filter,
        date_filter=date_filter,
        total_invoices=total_invoices,
        paid_count=paid_count,
        unpaid_count=unpaid_count,
        total_billed=float(total_billed),
        total_paid=float(total_paid),
        total_unpaid=float(total_unpaid)
    )

@app.route('/admin/invoices/<int:record_id>/payment', methods=['POST'])
@login_required
@admin_required
def admin_invoice_submit_payment(record_id):
    """
    Allows Admin to submit payment for an invoice (marking it Paid with method & notes)
    or revert an invoice back to Unpaid.
    """
    invoice = query_db("""
        SELECT sr.*, c.name as customer_name, v.plate_number
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        WHERE sr.id = %s
    """, (record_id,), one=True)

    if not invoice:
        flash("Invoice / Service Record not found.", "danger")
        return redirect(url_for('admin_invoice_payments'))

    action = request.form.get('action', 'submit_payment').strip()
    payment_status = request.form.get('payment_status', '').strip()

    if action == 'mark_unpaid' or payment_status == 'Unpaid':
        try:
            query_db("""
                UPDATE service_records
                SET payment_status = 'Unpaid',
                    payment_method = NULL,
                    payment_date = NULL,
                    payment_notes = CONCAT(COALESCE(payment_notes, ''), ' [Reverted to Unpaid by Admin on ', NOW(), ']')
                WHERE id = %s
            """, (record_id,), commit=True)
            flash(f"Invoice '{invoice['invoice_number']}' has been marked as Unpaid successfully.", "warning")
        except Exception as e:
            flash(f"Failed to update payment status: {str(e)}", "danger")

    else:
        # Submit / Record payment
        payment_method = request.form.get('payment_method', 'Cash').strip()
        custom_date = request.form.get('payment_date', '').strip()
        payment_notes = request.form.get('payment_notes', '').strip()
        new_status = 'Paid' if payment_status in ('', 'Paid') else payment_status

        pay_date = custom_date if custom_date else datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            query_db("""
                UPDATE service_records
                SET payment_status = %s,
                    payment_method = %s,
                    payment_date = %s,
                    payment_notes = %s
                WHERE id = %s
            """, (new_status, payment_method, pay_date, payment_notes or None, record_id), commit=True)

            flash(f"Payment for Invoice '{invoice['invoice_number']}' (₹{float(invoice['total_cost'] or 0):,.2f}) submitted successfully! Marked as '{new_status}' via {payment_method}.", "success")
        except Exception as e:
            flash(f"Failed to submit payment: {str(e)}", "danger")

    return redirect(request.referrer or url_for('admin_invoice_payments'))

# -------------------------------------------------------------
# Spare Parts Department & Inventory Management
# -------------------------------------------------------------
def parse_int_field(val, default=0):
    try:
        if val is None or str(val).strip() == '':
            return default
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return default

def parse_float_field(val, default=0.0):
    try:
        if val is None or str(val).strip() == '':
            return default
        cleaned = str(val).replace('₹', '').replace(',', '').strip()
        return round(float(cleaned), 2)
    except (ValueError, TypeError):
        return default

@app.route('/parts/dashboard')
@login_required
@parts_required
def parts_dashboard():
    """Command Center Dashboard for Spare Parts Department staff and Admins."""
    total_parts = query_db("SELECT COUNT(*) as cnt FROM spare_parts", one=True)['cnt'] or 0
    total_units = query_db("SELECT COALESCE(SUM(quantity), 0) as total FROM spare_parts", one=True)['total'] or 0
    total_inventory_value = query_db("SELECT COALESCE(SUM(quantity * unit_price), 0.0) as val FROM spare_parts", one=True)['val'] or 0.0
    low_stock_count = query_db("SELECT COUNT(*) as cnt FROM spare_parts WHERE quantity <= min_quantity OR status = 'Out of Stock'", one=True)['cnt'] or 0
    out_of_stock_count = query_db("SELECT COUNT(*) as cnt FROM spare_parts WHERE quantity = 0 OR status = 'Out of Stock'", one=True)['cnt'] or 0
    pending_count = query_db("SELECT COUNT(*) as cnt FROM part_requests WHERE status IN ('Waiting for Parts', 'Pending', 'Request Sent')", one=True)['cnt'] or 0
    all_requests_count = query_db("SELECT COUNT(*) as cnt FROM part_requests", one=True)['cnt'] or 0

    requests = query_db("""
        SELECT pr.*, sr.invoice_number, sr.service_date,
               v.plate_number, v.make, v.model,
               c.name as customer_name, c.company_name,
               u.name as tech_name,
               sp.quantity as stock_qty, sp.shelf_location, sp.unit_price as catalog_price
        FROM part_requests pr
        JOIN service_records sr ON pr.service_record_id = sr.id
        JOIN vehicles v ON sr.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        LEFT JOIN users u ON pr.requested_by = u.id
        LEFT JOIN spare_parts sp ON pr.part_id = sp.id
        ORDER BY pr.id DESC
        LIMIT 10
    """) or []

    low_stock_parts = query_db("""
        SELECT * FROM spare_parts 
        WHERE quantity <= min_quantity OR status = 'Out of Stock'
        ORDER BY quantity ASC, min_quantity DESC
        LIMIT 8
    """) or []

    return render_template(
        'parts/dashboard.html',
        total_parts=total_parts,
        total_units=total_units,
        total_inventory_value=total_inventory_value,
        low_stock_count=low_stock_count,
        out_of_stock_count=out_of_stock_count,
        pending_count=pending_count,
        all_requests_count=all_requests_count,
        requests=requests,
        recent_requests=requests,
        low_stock_parts=low_stock_parts
    )

@app.route('/parts/inventory')
@login_required
@parts_required
def parts_inventory():
    """Full inventory catalog search and filtering."""
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    status = (request.args.get('status') or request.args.get('availability', '')).strip()

    # Map status aliases
    if status == 'Available':
        status = 'In Stock'
    elif status == 'Unavailable':
        status = 'Out of Stock'

    sql = "SELECT * FROM spare_parts WHERE 1=1"
    params = []

    if search:
        sql += " AND (part_name LIKE %s OR part_number LIKE %s OR supplier LIKE %s OR compatibility LIKE %s OR shelf_location LIKE %s OR category LIKE %s)"
        term = f"%{search}%"
        params.extend([term, term, term, term, term, term])

    if category and category != 'All':
        sql += " AND category = %s"
        params.append(category)

    if status and status != 'All':
        sql += " AND status = %s"
        params.append(status)

    sql += " ORDER BY part_name ASC"
    parts = query_db(sql, tuple(params)) or []

    categories = query_db("SELECT DISTINCT category FROM spare_parts WHERE category IS NOT NULL AND category != '' ORDER BY category ASC") or []
    category_list = [c['category'] for c in categories]

    # Availability Metrics
    total_parts = query_db("SELECT COUNT(*) as cnt FROM spare_parts", one=True)['cnt'] or 0
    in_stock_count = query_db("SELECT COUNT(*) as cnt FROM spare_parts WHERE status = 'In Stock' AND quantity > 0", one=True)['cnt'] or 0
    low_stock_count = query_db("SELECT COUNT(*) as cnt FROM spare_parts WHERE status = 'Low Stock' OR (quantity > 0 AND quantity <= min_quantity)", one=True)['cnt'] or 0
    out_of_stock_count = query_db("SELECT COUNT(*) as cnt FROM spare_parts WHERE status = 'Out of Stock' OR quantity = 0", one=True)['cnt'] or 0

    total_units = sum(p['quantity'] for p in parts)
    total_inventory_value = sum(float(p['quantity']) * float(p['unit_price']) for p in parts)

    return render_template(
        'parts/inventory.html',
        parts=parts,
        categories=category_list,
        search=search,
        category=category,
        selected_category=category,
        status=status,
        selected_status=status,
        total_parts=total_parts,
        in_stock_count=in_stock_count,
        low_stock_count=low_stock_count,
        out_of_stock_count=out_of_stock_count,
        total_units=total_units,
        total_inventory_value=total_inventory_value
    )

@app.route('/parts/create', methods=['GET', 'POST'])
@login_required
@parts_required
def parts_create():
    """Register a new spare part into the warehouse catalog."""
    if request.method == 'POST':
        part_number = request.form.get('part_number', '').strip().upper()
        part_name = request.form.get('part_name', '').strip()
        category = request.form.get('category', 'General')
        shelf_location = request.form.get('shelf_location', '').strip()
        quantity = max(0, parse_int_field(request.form.get('quantity'), 0))
        min_quantity = max(1, parse_int_field(request.form.get('min_quantity'), 5))
        unit_price = max(0.0, parse_float_field(request.form.get('unit_price'), 0.0))
        tax_rate = max(0.0, parse_float_field(request.form.get('tax_rate'), 18.0))
        cost_price = max(0.0, parse_float_field(request.form.get('cost_price'), 0.0))
        supplier = request.form.get('supplier', '').strip()
        compatibility = request.form.get('compatibility', '').strip()
        description = request.form.get('description', '').strip()

        if not part_number or not part_name:
            flash("Part Number and Component Name are required.", "danger")
            return render_template('parts/form.html', part=None)

        existing = query_db("SELECT id FROM spare_parts WHERE part_number = %s", (part_number,), one=True)
        if existing:
            flash(f"A part with part number '{part_number}' already exists in catalog.", "danger")
            return render_template('parts/form.html', part=None)

        form_status = request.form.get('status', '').strip()
        if form_status in ('In Stock', 'Low Stock', 'Out of Stock'):
            status = form_status
        elif quantity <= 0:
            status = 'Out of Stock'
        elif quantity <= min_quantity:
            status = 'Low Stock'
        else:
            status = 'In Stock'

        try:
            query_db("""
                INSERT INTO spare_parts 
                (part_number, part_name, category, quantity, min_quantity, unit_price, tax_rate, cost_price, shelf_location, supplier, compatibility, status, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (part_number, part_name, category, quantity, min_quantity, unit_price, tax_rate, cost_price, shelf_location, supplier, compatibility, status, description), commit=True)
            flash(f"Spare part '{part_name}' ({part_number}) registered successfully!", "success")
            return redirect(url_for('parts_inventory'))
        except Exception as e:
            flash(f"Failed to register spare part: {str(e)}", "danger")

    return render_template('parts/form.html', part=None)

@app.route('/parts/<int:part_id>/edit', methods=['GET', 'POST'])
@login_required
@parts_required
def parts_edit(part_id):
    """Edit existing spare part specifications, pricing, and stock limits."""
    part = query_db("SELECT * FROM spare_parts WHERE id = %s", (part_id,), one=True)
    if not part:
        flash("Spare part not found.", "danger")
        return redirect(url_for('parts_inventory'))

    if request.method == 'POST':
        part_number = request.form.get('part_number', '').strip().upper()
        part_name = request.form.get('part_name', '').strip()
        category = request.form.get('category', 'General')
        shelf_location = request.form.get('shelf_location', '').strip()
        quantity = max(0, parse_int_field(request.form.get('quantity'), 0))
        min_quantity = max(1, parse_int_field(request.form.get('min_quantity'), 5))
        unit_price = max(0.0, parse_float_field(request.form.get('unit_price'), 0.0))
        tax_rate = max(0.0, parse_float_field(request.form.get('tax_rate'), 18.0))
        cost_price = max(0.0, parse_float_field(request.form.get('cost_price'), 0.0))
        supplier = request.form.get('supplier', '').strip()
        compatibility = request.form.get('compatibility', '').strip()
        description = request.form.get('description', '').strip()

        if not part_number or not part_name:
            flash("Part Number and Component Name are required.", "danger")
            return render_template('parts/form.html', part=part)

        existing = query_db("SELECT id FROM spare_parts WHERE part_number = %s AND id != %s", (part_number, part_id), one=True)
        if existing:
            flash(f"A different part with part number '{part_number}' already exists.", "danger")
            return render_template('parts/form.html', part=part)

        form_status = request.form.get('status', '').strip()
        if form_status in ('In Stock', 'Low Stock', 'Out of Stock'):
            status = form_status
        elif quantity <= 0:
            status = 'Out of Stock'
        elif quantity <= min_quantity:
            status = 'Low Stock'
        else:
            status = 'In Stock'

        old_unit_price = float(part.get('unit_price') or 0.0)
        old_tax_rate = float(part.get('tax_rate') or 18.0)

        try:
            query_db("""
                UPDATE spare_parts
                SET part_number=%s, part_name=%s, category=%s, quantity=%s, min_quantity=%s,
                    unit_price=%s, tax_rate=%s, cost_price=%s, shelf_location=%s, supplier=%s,
                    compatibility=%s, status=%s, description=%s
                WHERE id = %s
            """, (part_number, part_name, category, quantity, min_quantity, unit_price, tax_rate, cost_price, shelf_location, supplier, compatibility, status, description, part_id), commit=True)

            if abs(old_unit_price - unit_price) > 0.001 or abs(old_tax_rate - tax_rate) > 0.001:
                log_pricing_change(
                    'Spare Part',
                    part_id,
                    part_name,
                    'Catalog Price / Tax Updated',
                    f"Price: ₹{old_unit_price:,.2f}, Tax: {old_tax_rate}%",
                    f"Price: ₹{unit_price:,.2f}, Tax: {tax_rate}%",
                    session.get('user_id'),
                    f"Standard catalog price updated by {session.get('user_name', 'Staff')} ({session.get('user_role', 'Admin')})"
                )

            flash(f"Spare part '{part_name}' updated successfully.", "success")
            return redirect(url_for('parts_inventory'))
        except Exception as e:
            flash(f"Failed to update spare part: {str(e)}", "danger")

    return render_template('parts/form.html', part=part)

@app.route('/parts/<int:part_id>/delete', methods=['POST'])
@login_required
@parts_required
def parts_delete(part_id):
    """Delete a spare part from the inventory catalog safely preserving request history."""
    try:
        # Preserve requisition records by unlinking part_id
        query_db("UPDATE part_requests SET part_id = NULL WHERE part_id = %s", (part_id,), commit=True)
        query_db("DELETE FROM spare_parts WHERE id = %s", (part_id,), commit=True)
        flash("Spare part removed from catalog successfully.", "info")
    except Exception as e:
        flash(f"Failed to delete spare part: {str(e)}", "danger")
    return redirect(url_for('parts_inventory'))

@app.route('/parts/<int:part_id>/quick-stock', methods=['POST'])
@login_required
@parts_required
def parts_quick_stock(part_id):
    """Quick stock adjustment from inventory table with instant validation."""
    try:
        part = query_db("SELECT * FROM spare_parts WHERE id = %s", (part_id,), one=True)
        if not part:
            flash("Part not found.", "danger")
            return redirect(url_for('parts_inventory'))

        adjustment_qty = parse_int_field(request.form.get('adjustment_qty'), 0)
        if adjustment_qty == 0:
            flash("No stock quantity adjustment specified.", "warning")
            return redirect(request.referrer or url_for('parts_inventory'))

        new_quantity = max(0, part['quantity'] + adjustment_qty)

        if new_quantity <= 0:
            status = 'Out of Stock'
        elif new_quantity <= part['min_quantity']:
            status = 'Low Stock'
        else:
            status = 'In Stock'

        query_db("""
            UPDATE spare_parts
            SET quantity = %s, status = %s
            WHERE id = %s
        """, (new_quantity, status, part_id), commit=True)

        delta_str = f"+{adjustment_qty}" if adjustment_qty > 0 else str(adjustment_qty)
        flash(f"Stock for '{part['part_name']}' adjusted: {delta_str} units (New total: {new_quantity} on hand).", "success")
    except Exception as e:
        flash(f"Failed to update stock: {str(e)}", "danger")

    return redirect(request.referrer or url_for('parts_inventory'))

@app.route('/parts/<int:part_id>/status', methods=['POST'])
@app.route('/parts/<int:part_id>/availability', methods=['POST'])
@login_required
@parts_required
def parts_update_availability(part_id):
    """1-Click quick update for spare part inventory availability status."""
    part = query_db("SELECT * FROM spare_parts WHERE id = %s", (part_id,), one=True)
    if not part:
        flash("Spare part not found in inventory catalog.", "danger")
        return redirect(url_for('parts_inventory'))

    new_status = (request.form.get('status') or request.form.get('availability', '')).strip()

    if new_status in ('Available', 'In Stock'):
        status_val = 'In Stock'
    elif new_status in ('Low Stock', 'Low'):
        status_val = 'Low Stock'
    elif new_status in ('Out of Stock', 'Unavailable', 'Out'):
        status_val = 'Out of Stock'
    else:
        flash("Invalid availability status selected. Permitted values: Available (In Stock), Low Stock, Out of Stock.", "danger")
        return redirect(request.referrer or url_for('parts_inventory'))

    try:
        if status_val == 'In Stock':
            if part['quantity'] <= 0:
                new_qty = max(part['min_quantity'], 5)
                query_db("UPDATE spare_parts SET status = %s, quantity = %s WHERE id = %s", (status_val, new_qty, part_id), commit=True)
            else:
                query_db("UPDATE spare_parts SET status = %s WHERE id = %s", (status_val, part_id), commit=True)
        elif status_val == 'Low Stock':
            new_qty = max(1, part['min_quantity'])
            query_db("UPDATE spare_parts SET status = %s, quantity = %s WHERE id = %s", (status_val, new_qty, part_id), commit=True)
        elif status_val == 'Out of Stock':
            query_db("UPDATE spare_parts SET status = %s, quantity = 0 WHERE id = %s", (status_val, part_id), commit=True)

        flash(f"Availability status for '{part['part_name']}' ({part['part_number']}) updated to '{status_val}' successfully!", "success")
    except Exception as e:
        flash(f"Failed to update part availability: {str(e)}", "danger")

    return redirect(request.referrer or url_for('parts_inventory'))

@app.route('/services/<int:record_id>/request-part', methods=['POST'])
@login_required
def service_request_part(record_id):
    """Allows Technicians or Admins to requisition parts for a work order, triggering 'Waiting for Parts' status."""
    service = query_db("""
        SELECT sr.*, c.name as customer_name, v.plate_number, v.make, v.model
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        WHERE sr.id = %s
    """, (record_id,), one=True)

    if not service:
        flash("Work order not found.", "danger")
        return redirect(url_for('services_list'))

    part_id_raw = request.form.get('part_id')
    part_id = int(part_id_raw) if part_id_raw and part_id_raw.isdigit() else None
    part_name = request.form.get('part_name', '').strip()
    part_number = request.form.get('part_number', '').strip().upper()
    quantity_requested = max(1, parse_int_field(request.form.get('quantity_requested'), 1))
    priority = request.form.get('priority', 'Standard')
    technician_notes = request.form.get('technician_notes', '').strip()

    if not part_name:
        flash("Component name is required to submit a requisition.", "danger")
        return redirect(url_for('service_detail', record_id=record_id))

    # Match SKU with inventory catalog if part_id not provided
    if not part_id and part_number:
        matched = query_db("SELECT id FROM spare_parts WHERE part_number = %s", (part_number,), one=True)
        if matched:
            part_id = matched['id']

    # Prevent accidental duplicate submissions within 30 seconds
    duplicate_check = query_db("""
        SELECT id FROM part_requests 
        WHERE service_record_id = %s AND (part_name = %s OR (part_number IS NOT NULL AND part_number = %s))
          AND status IN ('Waiting for Parts', 'Pending', 'Request Sent')
          AND requested_at >= NOW() - INTERVAL 30 SECOND
    """, (record_id, part_name, part_number), one=True)
    if duplicate_check:
        flash(f"A request for '{part_name}' is already pending for this work order (#REQ-{duplicate_check['id']}).", "warning")
        return redirect(url_for('service_detail', record_id=record_id))

    try:
        req_id = query_db("""
            INSERT INTO part_requests 
            (service_record_id, technician_id, requested_by, part_id, part_name, part_number, quantity_requested, quantity_available, priority, technician_notes, status, requested_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s, %s, 'Waiting for Parts', NOW())
        """, (record_id, session['user_id'], session['user_id'], part_id, part_name, part_number, quantity_requested, priority, technician_notes), commit=True)

        # Set work order status to "Waiting for Parts"
        query_db("UPDATE service_records SET status = 'Waiting for Parts' WHERE id = %s", (record_id,), commit=True)

        # Send in-app notification to all Spare Parts staff and Admin
        parts_recipients = query_db("SELECT id FROM users WHERE role IN ('Spare Parts', 'Admin') AND status = 'Active'") or []
        for pr_user in parts_recipients:
            query_db("""
                INSERT INTO notifications (user_id, title, message, link, type, is_read)
                VALUES (%s, %s, %s, %s, 'part_requested', 0)
            """, (
                pr_user['id'],
                f"New Part Request: {part_name}",
                f"{session.get('user_name', 'Technician')} requested {quantity_requested}x {part_name} for {service['invoice_number']} ({service['plate_number']}).",
                url_for('parts_requests')
            ), commit=True)

        flash(f"Requisition for '{part_name}' (Qty: {quantity_requested}) dispatched to Spare Parts Department. Work order status is now 'Waiting for Parts'.", "success")
    except Exception as e:
        flash(f"Failed to submit parts request: {str(e)}", "danger")

    return redirect(url_for('service_detail', record_id=record_id))

@app.route('/parts/requests')
@login_required
@parts_required
def parts_requests():
    """Spare Parts Requisition Pipeline: view, review, search, and fulfill incoming technician requests."""
    search = request.args.get('search', '').strip()
    status = (request.args.get('status') or request.args.get('status_filter') or '').strip()
    priority = (request.args.get('priority') or request.args.get('priority_filter') or '').strip()

    sql = """
        SELECT pr.*, sr.invoice_number, sr.service_date, sr.status as service_status,
               v.plate_number, v.make, v.model,
               c.name as customer_name, c.company_name,
               u.name as tech_name,
               sp.quantity as stock_qty, sp.shelf_location, sp.unit_price as catalog_price
        FROM part_requests pr
        JOIN service_records sr ON pr.service_record_id = sr.id
        JOIN vehicles v ON sr.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        LEFT JOIN users u ON pr.requested_by = u.id
        LEFT JOIN spare_parts sp ON pr.part_id = sp.id
        WHERE 1=1
    """
    params = []

    if search:
        sql += """ AND (
            pr.part_name LIKE %s OR 
            pr.part_number LIKE %s OR 
            sr.invoice_number LIKE %s OR 
            v.plate_number LIKE %s OR 
            v.make LIKE %s OR 
            v.model LIKE %s OR 
            c.name LIKE %s OR 
            c.company_name LIKE %s OR 
            u.name LIKE %s
        )"""
        term = f"%{search}%"
        params.extend([term, term, term, term, term, term, term, term, term])

    if status and status != 'All':
        sql += " AND pr.status = %s"
        params.append(status)

    if priority and priority != 'All':
        sql += " AND pr.priority = %s"
        params.append(priority)

    sql += " ORDER BY pr.id DESC"
    requests_list = query_db(sql, tuple(params)) or []

    counts = query_db("""
        SELECT 
            COUNT(*) as total,
            COALESCE(SUM(CASE WHEN status IN ('Waiting for Parts', 'Pending', 'Request Sent') THEN 1 ELSE 0 END), 0) as pending_cnt,
            COALESCE(SUM(CASE WHEN status = 'Part Available' THEN 1 ELSE 0 END), 0) as available_cnt,
            COALESCE(SUM(CASE WHEN status = 'Not Available' THEN 1 ELSE 0 END), 0) as not_available_cnt,
            COALESCE(SUM(CASE WHEN status = 'Received by Technician' THEN 1 ELSE 0 END), 0) as received_cnt
        FROM part_requests
    """, one=True) or {}

    return render_template(
        'parts/requests.html',
        requests=requests_list,
        search=search,
        status=status,
        status_filter=status,
        priority=priority,
        priority_filter=priority,
        counts=counts
    )

@app.route('/parts/requests/<int:request_id>/approve', methods=['POST'])
@login_required
@parts_required
def parts_request_approve(request_id):
    """1-Click Quick Approval: Marks requested part as 'Part Available', auto-deducts stock if available, and alerts technician."""
    req = query_db("""
        SELECT pr.*, sr.invoice_number, sr.user_id as assigned_tech_id,
               v.plate_number, v.make, v.model,
               sp.quantity as stock_qty, sp.min_quantity
        FROM part_requests pr
        JOIN service_records sr ON pr.service_record_id = sr.id
        JOIN vehicles v ON sr.vehicle_id = v.id
        LEFT JOIN spare_parts sp ON pr.part_id = sp.id
        WHERE pr.id = %s
    """, (request_id,), one=True)

    if not req:
        flash("Parts request record not found.", "danger")
        return redirect(url_for('parts_requests'))

    try:
        qty_to_fulfill = req['quantity_requested']
        # If part is linked to warehouse catalog, deduct stock
        if req['part_id'] and req['stock_qty'] is not None:
            new_stock = max(0, req['stock_qty'] - qty_to_fulfill)
            new_status = 'Out of Stock' if new_stock <= 0 else ('Low Stock' if new_stock <= req['min_quantity'] else 'In Stock')
            query_db("UPDATE spare_parts SET quantity = %s, status = %s WHERE id = %s", (new_stock, new_status, req['part_id']), commit=True)

        dept_notes = request.form.get('parts_dept_notes', 'Component approved and ready for collection at the parts counter.').strip()

        query_db("""
            UPDATE part_requests
            SET status = 'Part Available', quantity_available = %s, parts_dept_notes = %s, fulfilled_at = NOW()
            WHERE id = %s
        """, (qty_to_fulfill, dept_notes, request_id), commit=True)

        recipient_id = req['requested_by'] or req['assigned_tech_id']
        if recipient_id:
            notif_title = f"Part Approved & Ready: {req['part_name']}"
            notif_msg = f"{qty_to_fulfill} unit(s) of '{req['part_name']}' is now available at the parts counter for Work Order {req['invoice_number']} ({req['plate_number']}). {dept_notes}".strip()
            query_db("""
                INSERT INTO notifications (user_id, title, message, link, type, is_read)
                VALUES (%s, %s, %s, %s, 'part_available', 0)
            """, (recipient_id, notif_title, notif_msg, url_for('technician_parts_requests')), commit=True)

        flash(f"Request #REQ-{request_id} for '{req['part_name']}' APPROVED! Component marked as 'Part Available' and technician notified.", "success")
    except Exception as e:
        flash(f"Failed to approve request: {str(e)}", "danger")

    return redirect(request.referrer or url_for('parts_requests'))

@app.route('/parts/requests/<int:request_id>/reject', methods=['POST'])
@login_required
@parts_required
def parts_request_reject(request_id):
    """1-Click Quick Reject: Marks request as 'Not Available', notifies the technician, and logs reason."""
    req = query_db("""
        SELECT pr.*, sr.invoice_number, sr.user_id as assigned_tech_id,
               v.plate_number, v.make, v.model
        FROM part_requests pr
        JOIN service_records sr ON pr.service_record_id = sr.id
        JOIN vehicles v ON sr.vehicle_id = v.id
        WHERE pr.id = %s
    """, (request_id,), one=True)

    if not req:
        flash("Parts request record not found.", "danger")
        return redirect(url_for('parts_requests'))

    try:
        reject_reason = request.form.get('reject_reason') or request.form.get('parts_dept_notes') or 'Component is currently out of stock / backordered from supplier.'
        reject_reason = reject_reason.strip()

        query_db("""
            UPDATE part_requests
            SET status = 'Not Available', parts_dept_notes = %s, fulfilled_at = NOW()
            WHERE id = %s
        """, (reject_reason, request_id), commit=True)

        recipient_id = req['requested_by'] or req['assigned_tech_id']
        if recipient_id:
            notif_title = f"Part Unavailable: {req['part_name']}"
            notif_msg = f"'{req['part_name']}' for Work Order {req['invoice_number']} could not be fulfilled: {reject_reason}".strip()
            query_db("""
                INSERT INTO notifications (user_id, title, message, link, type, is_read)
                VALUES (%s, %s, %s, %s, 'part_unavailable', 0)
            """, (recipient_id, notif_title, notif_msg, url_for('technician_parts_requests')), commit=True)

        flash(f"Request #REQ-{request_id} for '{req['part_name']}' marked as 'Not Available'. Notification sent to technician.", "warning")
    except Exception as e:
        flash(f"Failed to reject request: {str(e)}", "danger")

    return redirect(request.referrer or url_for('parts_requests'))

@app.route('/parts/requests/<int:request_id>/issue', methods=['POST'])
@login_required
@parts_required
def parts_request_issue(request_id):
    """Marks part request as 'Issued', updates warehouse stock, records issued timestamp, and notifies technician."""
    req = query_db("""
        SELECT pr.*, sr.invoice_number, sr.user_id as assigned_tech_id,
               v.plate_number, v.make, v.model,
               sp.quantity as stock_qty, sp.min_quantity
        FROM part_requests pr
        JOIN service_records sr ON pr.service_record_id = sr.id
        JOIN vehicles v ON sr.vehicle_id = v.id
        LEFT JOIN spare_parts sp ON pr.part_id = sp.id
        WHERE pr.id = %s
    """, (request_id,), one=True)

    if not req:
        flash("Parts request record not found.", "danger")
        return redirect(url_for('parts_requests'))

    try:
        qty_to_issue = req['quantity_requested']
        # If stock wasn't deducted yet, deduct it now
        if req['status'] not in ('Part Available', 'Issued') and req['part_id'] and req['stock_qty'] is not None:
            new_stock = max(0, req['stock_qty'] - qty_to_issue)
            new_status = 'Out of Stock' if new_stock <= 0 else ('Low Stock' if new_stock <= req['min_quantity'] else 'In Stock')
            query_db("UPDATE spare_parts SET quantity = %s, status = %s WHERE id = %s", (new_stock, new_status, req['part_id']), commit=True)

        dept_notes = request.form.get('parts_dept_notes', 'Component officially issued and handed over at the parts counter.').strip()

        query_db("""
            UPDATE part_requests
            SET status = 'Issued', quantity_available = %s, parts_dept_notes = %s, issued_at = NOW(), fulfilled_at = COALESCE(fulfilled_at, NOW())
            WHERE id = %s
        """, (qty_to_issue, dept_notes, request_id), commit=True)

        recipient_id = req['requested_by'] or req['assigned_tech_id']
        if recipient_id:
            dispatch_notification(
                recipient_id,
                f"Part Issued: {req['part_name']}",
                f"{qty_to_issue} unit(s) of '{req['part_name']}' has been officially ISSUED for Work Order {req['invoice_number']} ({req['plate_number']}).",
                url_for('technician_parts_requests'),
                notif_type='part_issued'
            )

        flash(f"Request #REQ-{request_id} for '{req['part_name']}' ISSUED! Component handed over and technician notified.", "success")
    except Exception as e:
        flash(f"Failed to issue part: {str(e)}", "danger")

    return redirect(request.referrer or url_for('parts_requests'))

@app.route('/parts/requests/<int:request_id>/update', methods=['POST'])
@app.route('/parts/requests/<int:request_id>/review', methods=['POST'])
@login_required
@parts_required
def parts_request_update(request_id):
    """Updates request status (Part Available, Unavailable - Ordered, Clarification, etc.) and coordinates workflow."""
    req = query_db("""
        SELECT pr.*, sr.invoice_number, sr.user_id as assigned_tech_id, sr.status as service_status,
               v.plate_number, v.make, v.model
        FROM part_requests pr
        JOIN service_records sr ON pr.service_record_id = sr.id
        JOIN vehicles v ON sr.vehicle_id = v.id
        WHERE pr.id = %s
    """, (request_id,), one=True)

    if not req:
        flash("Parts request record not found.", "danger")
        return redirect(url_for('parts_requests'))

    new_status = request.form.get('status', 'Pending').strip()
    quantity_available = max(0, parse_int_field(request.form.get('quantity_available'), 0))
    parts_dept_notes = request.form.get('parts_dept_notes', '').strip()
    deduct_stock = request.form.get('deduct_stock') == 'yes'

    # Lead time & supplier order fields
    estimated_days = max(0, parse_int_field(request.form.get('estimated_days'), 0))
    order_placed = 1 if (request.form.get('order_placed') in ('1', 'yes', 'on') or estimated_days > 0 or new_status in ('Unavailable - Ordered', 'Not Available')) else 0
    estimated_delivery_date = (date.today() + timedelta(days=estimated_days)).isoformat() if estimated_days > 0 else request.form.get('estimated_delivery_date') or None

    clarification_requested = request.form.get('clarification_requested', '').strip()
    if new_status == 'Clarification Requested' and clarification_requested:
        parts_dept_notes = f"Clarification Requested: {clarification_requested} | {parts_dept_notes}".strip(' |')

    try:
        query_db("""
            UPDATE part_requests
            SET status = %s, quantity_available = %s, parts_dept_notes = %s,
                estimated_days = %s, estimated_delivery_date = %s, order_placed = %s,
                clarification_requested = %s,
                fulfilled_at = CASE WHEN %s IN ('Part Available', 'Approved') THEN NOW() ELSE fulfilled_at END
            WHERE id = %s
        """, (new_status, quantity_available, parts_dept_notes, estimated_days,
              estimated_delivery_date, order_placed, clarification_requested, new_status, request_id), commit=True)

        # Deduct from warehouse inventory catalog if requested and part exists
        if deduct_stock and req['part_id'] and quantity_available > 0:
            part = query_db("SELECT quantity, min_quantity FROM spare_parts WHERE id = %s", (req['part_id'],), one=True)
            if part:
                new_q = max(0, part['quantity'] - quantity_available)
                new_st = 'Out of Stock' if new_q <= 0 else ('Low Stock' if new_q <= part['min_quantity'] else 'In Stock')
                query_db("UPDATE spare_parts SET quantity = %s, status = %s WHERE id = %s", (new_q, new_st, req['part_id']), commit=True)

        recipient_id = req['requested_by'] or req['assigned_tech_id']

        # Notify based on status
        if new_status in ('Part Available', 'Approved'):
            if recipient_id:
                notif_title = f"Part Ready for Collection: {req['part_name']}"
                notif_msg = f"{quantity_available or req['quantity_requested']} unit(s) of '{req['part_name']}' is ready for collection at the parts counter for Work Order {req['invoice_number']} ({req['plate_number']}). {parts_dept_notes}".strip()
                dispatch_notification(recipient_id, notif_title, notif_msg, url_for('tech_job_detail', job_id=req['service_record_id']), notif_type='part_available')
            flash(f"Request #REQ-{request_id} marked as 'Part Available'. Technician notified for collection.", "success")

        elif new_status in ('Unavailable - Ordered', 'Not Available'):
            eta_str = f"Estimated availability: {estimated_delivery_date} (~{estimated_days} days)" if estimated_delivery_date else "Lead time pending confirmation"
            if recipient_id:
                notif_title = f"Part On Order / Unavailable: {req['part_name']}"
                notif_msg = f"'{req['part_name']}' for Work Order {req['invoice_number']} is on order from supplier. {eta_str}. {parts_dept_notes}".strip()
                dispatch_notification(recipient_id, notif_title, notif_msg, url_for('tech_job_detail', job_id=req['service_record_id']), notif_type='part_unavailable')
            # Also notify Admins of lead times
            admins = query_db("SELECT id FROM users WHERE role = 'Admin' AND status = 'Active'") or []
            for adm in admins:
                dispatch_notification(adm['id'], f"Part Ordered: {req['part_name']} (WO {req['invoice_number']})", f"Supplier order placed for '{req['part_name']}'. {eta_str}.", url_for('service_detail', record_id=req['service_record_id']), notif_type='part_ordered')
            flash(f"Request #REQ-{request_id} marked as '{new_status}' ({eta_str}). Technician and Admin notified.", "warning")

        elif new_status == 'Clarification Requested':
            if recipient_id:
                dispatch_notification(recipient_id, f"Clarification Needed: {req['part_name']}", f"Parts Dept needs clarification on '{req['part_name']}' for WO {req['invoice_number']}: \"{clarification_requested}\"", url_for('tech_job_detail', job_id=req['service_record_id']), notif_type='clarification_needed')
            flash(f"Clarification request sent to technician for #{req['part_name']}.", "info")

        elif new_status == 'Rejected':
            if recipient_id:
                dispatch_notification(recipient_id, f"Part Request Rejected: {req['part_name']}", f"Requisition for '{req['part_name']}' was rejected: {parts_dept_notes}", url_for('tech_job_detail', job_id=req['service_record_id']), notif_type='part_rejected')
            flash(f"Request #REQ-{request_id} rejected.", "info")

        # Automatic Work Order Stage Coordination
        all_reqs = query_db("SELECT status FROM part_requests WHERE service_record_id = %s", (req['service_record_id'],)) or []
        has_waiting = any(r['status'] in ('Unavailable - Ordered', 'Not Available', 'Waiting for Parts', 'Pending', 'Clarification Requested') for r in all_reqs)
        all_available = all(r['status'] in ('Part Available', 'Approved', 'Issued', 'Received by Technician', 'Used in Service', 'Completed') for r in all_reqs)

        if has_waiting and req['service_status'] in ('Parts Under Review', 'Inspection Submitted'):
            query_db("UPDATE service_records SET status = 'Awaiting Parts' WHERE id = %s", (req['service_record_id'],), commit=True)
            log_workflow_action(req['service_record_id'], req['service_status'], 'Awaiting Parts', session['user_id'], 'Spare Parts', 'Parts Requisition Reviewed - Awaiting Supplier Arrival', f"Part '{req['part_name']}' ordered. ETA: {estimated_delivery_date or 'TBD'}.")

        elif all_available and req['service_status'] in ('Parts Under Review', 'Awaiting Parts', 'Waiting for Parts', 'Inspection Submitted'):
            query_db("UPDATE service_records SET status = 'Ready to Schedule' WHERE id = %s", (req['service_record_id'],), commit=True)
            log_workflow_action(req['service_record_id'], req['service_status'], 'Ready to Schedule', session['user_id'], 'Spare Parts', 'All Requested Parts Confirmed Available', 'All requested parts are ready at parts counter. Work order is ready for duration estimation & scheduling.')
            if recipient_id:
                dispatch_notification(recipient_id, f"All Parts Ready: WO {req['invoice_number']}", f"All requested parts for Work Order {req['invoice_number']} are now available! Please submit your estimated repair duration.", url_for('tech_job_detail', job_id=req['service_record_id']), notif_type='ready_for_estimate')

    except Exception as e:
        flash(f"Failed to update request: {str(e)}", "danger")

    return redirect(request.referrer or url_for('parts_requests'))

    return redirect(request.referrer or url_for('parts_requests'))

@app.route('/parts/my-requests')
@login_required
def technician_parts_requests():
    """Dedicated screen for Technicians to monitor status of all their requisitioned parts."""
    user_id = session['user_id']
    user_role = session.get('user_role')
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '').strip()

    params = []
    if user_role == 'Admin':
        sql = """
            SELECT pr.*, sr.invoice_number, sr.service_date, sr.status as service_status,
                   v.plate_number, v.make, v.model,
                   c.name as customer_name, c.company_name,
                   u.name as tech_name
            FROM part_requests pr
            JOIN service_records sr ON pr.service_record_id = sr.id
            JOIN vehicles v ON sr.vehicle_id = v.id
            JOIN customers c ON v.customer_id = c.id
            LEFT JOIN users u ON pr.requested_by = u.id
            WHERE 1=1
        """
    else:
        sql = """
            SELECT pr.*, sr.invoice_number, sr.service_date, sr.status as service_status,
                   v.plate_number, v.make, v.model,
                   c.name as customer_name, c.company_name,
                   u.name as tech_name
            FROM part_requests pr
            JOIN service_records sr ON pr.service_record_id = sr.id
            JOIN vehicles v ON sr.vehicle_id = v.id
            JOIN customers c ON v.customer_id = c.id
            LEFT JOIN users u ON pr.requested_by = u.id
            WHERE (pr.requested_by = %s OR sr.user_id = %s)
        """
        params.extend([user_id, user_id])

    if search:
        sql += " AND (pr.part_name LIKE %s OR pr.part_number LIKE %s OR sr.invoice_number LIKE %s OR v.plate_number LIKE %s)"
        term = f"%{search}%"
        params.extend([term, term, term, term])

    if status and status != 'All':
        sql += " AND pr.status = %s"
        params.append(status)

    sql += " ORDER BY pr.id DESC"
    my_requests = query_db(sql, tuple(params)) or []

    return render_template(
        'parts/my_requests.html',
        my_requests=my_requests,
        search=search,
        status=status
    )

@app.route('/parts/requests/<int:request_id>/mark-received', methods=['POST'])
@login_required
def parts_request_mark_received(request_id):
    """Technician receives available part, automatically resuming work order to 'In Progress'."""
    req = query_db("SELECT * FROM part_requests WHERE id = %s", (request_id,), one=True)
    if not req:
        flash("Requisition record not found.", "danger")
        return redirect(url_for('technician_parts_requests'))

    try:
        query_db("UPDATE part_requests SET status = 'Received by Technician' WHERE id = %s", (request_id,), commit=True)
        query_db("""
            UPDATE service_records 
            SET status = 'In Progress' 
            WHERE id = %s AND status = 'Waiting for Parts'
        """, (req['service_record_id'],), commit=True)

        flash(f"Spare part '{req['part_name']}' marked as received! Work order resumed to 'In Progress'.", "success")
    except Exception as e:
        flash(f"Failed to update requisition status: {str(e)}", "danger")

    return redirect(request.referrer or url_for('service_detail', record_id=req['service_record_id']))

@app.route('/notifications/read-all', methods=['POST'])
@login_required
def notifications_mark_all_read():
    """Dismisses all unread in-app notifications for the active user."""
    try:
        query_db("UPDATE notifications SET is_read = 1 WHERE user_id = %s", (session['user_id'],), commit=True)
    except Exception:
        pass
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/notifications/read/<int:notif_id>', methods=['POST'])
@login_required
def notification_mark_read(notif_id):
    """Marks a single in-app notification as read."""
    try:
        query_db("UPDATE notifications SET is_read = 1 WHERE id = %s AND user_id = %s", (notif_id, session['user_id']), commit=True)
    except Exception:
        pass
    return redirect(request.referrer or url_for('dashboard'))

# =============================================================
# Technician Panel Module
# =============================================================

@app.route('/tech/dashboard')
@login_required
@technician_required
def tech_dashboard():
    """Technician Command Center: KPIs, today's schedule, assigned jobs workbench, and parts pipeline."""
    user_id = session['user_id']
    user_role = session.get('user_role')

    tech_profile = query_db("""
        SELECT id, name, email, phone, role, technician_code, skills, specialization, availability_status, avatar
        FROM users WHERE id = %s
    """, (user_id,), one=True) or {}

    tech_filter_sql = "" if user_role == 'Admin' else "AND sr.user_id = %s"
    tech_filter_params = () if user_role == 'Admin' else (user_id,)

    total_assigned = query_db(f"SELECT COUNT(*) as cnt FROM service_records sr WHERE 1=1 {tech_filter_sql}", tech_filter_params, one=True)['cnt']
    pending_count = query_db(f"SELECT COUNT(*) as cnt FROM service_records sr WHERE sr.status IN ('Pending', 'Accepted') {tech_filter_sql}", tech_filter_params, one=True)['cnt']
    in_progress_count = query_db(f"SELECT COUNT(*) as cnt FROM service_records sr WHERE sr.status IN ('In Progress', 'Waiting for Parts', 'On Hold') {tech_filter_sql}", tech_filter_params, one=True)['cnt']
    completed_count = query_db(f"SELECT COUNT(*) as cnt FROM service_records sr WHERE sr.status = 'Completed' {tech_filter_sql}", tech_filter_params, one=True)['cnt']

    workflow_counts = query_db(f"""
        SELECT 
            COALESCE(SUM(CASE WHEN sr.status IN ('Pending', 'Accepted') THEN 1 ELSE 0 END), 0) as inspect_count,
            COALESCE(SUM(CASE WHEN sr.status IN ('Inspection Submitted', 'Parts Under Review', 'Awaiting Parts', 'Waiting for Parts') THEN 1 ELSE 0 END), 0) as parts_review_count,
            COALESCE(SUM(CASE WHEN sr.status = 'Ready to Schedule' THEN 1 ELSE 0 END), 0) as ready_schedule_count,
            COALESCE(SUM(CASE WHEN sr.status = 'Scheduled' THEN 1 ELSE 0 END), 0) as scheduled_count,
            COALESCE(SUM(CASE WHEN sr.status IN ('In Progress', 'On Hold') THEN 1 ELSE 0 END), 0) as in_progress_count,
            COALESCE(SUM(CASE WHEN sr.status IN ('Awaiting Admin Approval', 'Revision Required', 'Approved - Pending Final Report') THEN 1 ELSE 0 END), 0) as approval_count,
            COALESCE(SUM(CASE WHEN sr.status = 'Completed' THEN 1 ELSE 0 END), 0) as completed_count
        FROM service_records sr
        WHERE 1=1 {tech_filter_sql}
    """, tech_filter_params, one=True) or {}

    today_schedule = query_db(f"""
        SELECT sr.*, v.plate_number, v.make, v.model, v.year, v.fuel_type, v.vehicle_type,
               c.name as customer_name, c.phone as customer_phone, c.address as customer_address, c.city as customer_city
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        WHERE sr.appointment_date = CURDATE() {tech_filter_sql}
        ORDER BY sr.appointment_time ASC, sr.id DESC
    """, tech_filter_params) or []

    upcoming_schedule = query_db(f"""
        SELECT sr.*, v.plate_number, v.make, v.model, v.year,
               c.name as customer_name, c.phone as customer_phone
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        WHERE sr.appointment_date > CURDATE() {tech_filter_sql}
        ORDER BY sr.appointment_date ASC, sr.appointment_time ASC
        LIMIT 6
    """, tech_filter_params) or []

    active_jobs = query_db(f"""
        SELECT sr.*, v.plate_number, v.make, v.model, v.year,
               c.name as customer_name, c.phone as customer_phone
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        WHERE sr.status NOT IN ('Completed', 'Cancelled') {tech_filter_sql}
        ORDER BY CASE sr.priority WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END,
                 sr.appointment_date ASC
        LIMIT 8
    """, tech_filter_params) or []

    parts_summary = query_db("""
        SELECT 
            COUNT(*) as total_requested,
            COALESCE(SUM(CASE WHEN status IN ('Waiting for Parts', 'Pending', 'Request Sent') THEN 1 ELSE 0 END), 0) as pending_count,
            COALESCE(SUM(CASE WHEN status IN ('Part Available', 'Approved') THEN 1 ELSE 0 END), 0) as available_count,
            COALESCE(SUM(CASE WHEN status = 'Issued' THEN 1 ELSE 0 END), 0) as issued_count
        FROM part_requests
        WHERE technician_id = %s OR requested_by = %s
    """, (user_id, user_id), one=True) or {'total_requested': 0, 'pending_count': 0, 'available_count': 0, 'issued_count': 0}

    return render_template(
        'technician/dashboard.html',
        tech_profile=tech_profile,
        total_assigned=total_assigned,
        pending_count=pending_count,
        in_progress_count=in_progress_count,
        completed_count=completed_count,
        workflow_counts=workflow_counts,
        today_schedule=today_schedule,
        upcoming_schedule=upcoming_schedule,
        active_jobs=active_jobs,
        parts_summary=parts_summary
    )

@app.route('/tech/jobs')
@login_required
@technician_required
def tech_jobs():
    """Assigned jobs repository with search, status & priority filtering, sorting, and full job details."""
    user_id = session['user_id']
    user_role = session.get('user_role')

    search = request.args.get('search', '').strip()
    status = request.args.get('status', '').strip()
    priority = request.args.get('priority', '').strip()
    sort = request.args.get('sort', 'appointment').strip()
    selected_tech_id = request.args.get('tech_id', type=int)

    sql = """
        SELECT sr.*, v.plate_number, v.vin, v.make, v.model, v.year, v.color, v.fuel_type, v.vehicle_type,
               c.name as customer_name, c.company_name, c.phone as customer_phone, c.email as customer_email,
               c.address as customer_address, c.city as customer_city,
               u.name as tech_name
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        LEFT JOIN users u ON sr.user_id = u.id
        WHERE 1=1
    """
    params = []

    if user_role != 'Admin':
        sql += " AND sr.user_id = %s"
        params.append(user_id)
    elif selected_tech_id:
        sql += " AND sr.user_id = %s"
        params.append(selected_tech_id)

    if search:
        sql += """ AND (
            sr.invoice_number LIKE %s OR 
            v.plate_number LIKE %s OR 
            v.make LIKE %s OR 
            v.model LIKE %s OR 
            c.name LIKE %s OR 
            c.phone LIKE %s OR 
            sr.description LIKE %s OR 
            sr.service_type LIKE %s
        )"""
        term = f"%{search}%"
        params.extend([term, term, term, term, term, term, term, term])

    if status and status != 'All':
        sql += " AND sr.status = %s"
        params.append(status)

    if priority and priority != 'All':
        sql += " AND sr.priority = %s"
        params.append(priority)

    if sort == 'priority':
        sql += " ORDER BY CASE sr.priority WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END, sr.appointment_date ASC"
    elif sort == 'newest':
        sql += " ORDER BY sr.id DESC"
    else:
        sql += " ORDER BY sr.appointment_date ASC, sr.appointment_time ASC, sr.id DESC"

    jobs = query_db(sql, tuple(params)) or []
    all_technicians = query_db("SELECT id, name FROM users WHERE role = 'Technician' AND status = 'Active'") or []

    return render_template(
        'technician/jobs.html',
        jobs=jobs,
        search=search,
        status=status,
        priority=priority,
        sort=sort,
        all_technicians=all_technicians,
        selected_tech_id=selected_tech_id
    )

@app.route('/tech/jobs/<int:job_id>')
@login_required
@technician_required
def tech_job_detail(job_id):
    """Full Job Workbench: customer communication, vehicle diagnostics, parts tracking, and status controls."""
    user_id = session['user_id']
    user_role = session.get('user_role')

    job = query_db("""
        SELECT sr.*, v.plate_number, v.vin, v.make, v.model, v.year, v.color, v.fuel_type, v.vehicle_type,
               c.name as customer_name, c.company_name, c.email as customer_email, c.phone as customer_phone,
               c.customer_type, c.address as customer_address, c.city as customer_city, c.postal_code as customer_postal,
               u.name as tech_name, u.role as tech_role, u.technician_code, u.specialization
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        LEFT JOIN users u ON sr.user_id = u.id
        WHERE sr.id = %s
    """, (job_id,), one=True)

    if not job:
        flash("Assigned work order not found.", "danger")
        return redirect(url_for('tech_jobs'))

    if user_role != 'Admin' and job['user_id'] != user_id:
        flash("You are not authorized to access this job. It is assigned to another technician.", "danger")
        return redirect(url_for('tech_jobs'))

    part_requests = query_db("""
        SELECT pr.*, sp.quantity as stock_qty, sp.shelf_location, sp.unit_price as catalog_price
        FROM part_requests pr
        LEFT JOIN spare_parts sp ON pr.part_id = sp.id
        WHERE pr.service_record_id = %s
        ORDER BY pr.id DESC
    """, (job_id,)) or []

    catalog_parts = query_db("""
        SELECT id, part_number, part_name, quantity, unit_price, shelf_location
        FROM spare_parts
        ORDER BY part_name ASC
    """) or []

    service_report = query_db("""
        SELECT sr.*, u.name as tech_name, u.technician_code
        FROM service_reports sr
        LEFT JOIN users u ON sr.technician_id = u.id
        WHERE sr.service_record_id = %s
    """, (job_id,), one=True)

    # Complete vehicle service and diagnostic history (excluding cash/financial data)
    vehicle_history = query_db("""
        SELECT sr.id, sr.invoice_number, sr.service_date, sr.appointment_date, sr.appointment_time,
               sr.odometer, sr.service_type, sr.status, sr.priority, sr.description, sr.technician_notes,
               sr.completed_at,
               u.name as past_tech_name, u.technician_code as past_tech_code,
               rep.diagnosis as past_diagnosis, rep.work_performed as past_work_performed,
               rep.solution_provided as past_solution, rep.parts_used_summary as past_parts_used,
               rep.remarks as past_remarks
        FROM service_records sr
        LEFT JOIN users u ON sr.user_id = u.id
        LEFT JOIN service_reports rep ON sr.id = rep.service_record_id
        WHERE sr.vehicle_id = %s AND sr.id != %s
        ORDER BY sr.service_date DESC, sr.id DESC
    """, (job['vehicle_id'], job_id)) or []

    past_parts_history = query_db("""
        SELECT pr.*, sr.invoice_number, sr.service_date, u.name as tech_name
        FROM part_requests pr
        JOIN service_records sr ON pr.service_record_id = sr.id
        LEFT JOIN users u ON pr.technician_id = u.id
        WHERE sr.vehicle_id = %s AND sr.id != %s
        ORDER BY pr.id DESC
        LIMIT 25
    """, (job['vehicle_id'], job_id)) or []

    workflow_history = query_db("""
        SELECT swh.*, u.name as user_name, u.role as user_role_actual
        FROM service_workflow_history swh
        LEFT JOIN users u ON swh.action_by = u.id
        WHERE swh.service_record_id = %s
        ORDER BY swh.id ASC
    """, (job_id,)) or []

    return render_template(
        'technician/job_detail.html',
        job=job,
        part_requests=part_requests,
        catalog_parts=catalog_parts,
        service_report=service_report,
        vehicle_history=vehicle_history,
        past_parts_history=past_parts_history,
        workflow_history=workflow_history
    )

@app.route('/tech/jobs/<int:job_id>/inspect', methods=['GET', 'POST'])
@login_required
@technician_required
def tech_job_inspect(job_id):
    """Step 1: Technician inspects vehicle, records symptoms & diagnosis, and lists required spare parts."""
    user_id = session['user_id']
    user_role = session.get('user_role')

    job = query_db("""
        SELECT sr.*, v.plate_number, v.vin, v.make, v.model, v.year, v.color, v.fuel_type, v.vehicle_type,
               c.name as customer_name, c.company_name, c.phone as customer_phone, c.email as customer_email,
               u.name as tech_name
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        LEFT JOIN users u ON sr.user_id = u.id
        WHERE sr.id = %s
    """, (job_id,), one=True)

    if not job:
        flash("Work order not found.", "danger")
        return redirect(url_for('tech_jobs'))

    if user_role != 'Admin' and job['user_id'] != user_id:
        flash("You are not authorized to inspect jobs assigned to another technician.", "danger")
        return redirect(url_for('tech_jobs'))

    catalog_parts = query_db("SELECT id, part_number, part_name, quantity, shelf_location FROM spare_parts ORDER BY part_name ASC") or []

    if request.method == 'POST':
        inspection_symptoms = request.form.get('inspection_symptoms', '').strip()
        inspection_diagnosis = request.form.get('inspection_diagnosis', '').strip()
        inspection_notes = request.form.get('inspection_notes', '').strip()
        inspection_photos = request.form.get('inspection_photos', '').strip()

        # Handle photo upload
        photo_file = request.files.get('inspection_photo_file')
        if photo_file and photo_file.filename:
            fname = secure_filename(f"inspect_{job_id}_{int(datetime.now().timestamp())}_{photo_file.filename}")
            fpath = os.path.join(app.config['UPLOAD_FOLDER'], fname)
            photo_file.save(fpath)
            inspection_photos = f"/static/uploads/reports/{fname}"

        if not inspection_diagnosis:
            flash("Inspection diagnosis and findings are required.", "danger")
            return render_template('technician/inspection_form.html', job=job, catalog_parts=catalog_parts)

        # Parse dynamic parts list
        part_names = request.form.getlist('part_name[]')
        part_numbers = request.form.getlist('part_number[]')
        quantities = request.form.getlist('quantity[]')
        urgencies = request.form.getlist('urgency[]')
        part_notes_list = request.form.getlist('part_notes[]')

        requested_parts_count = 0
        for i in range(len(part_names)):
            p_name = part_names[i].strip() if i < len(part_names) else ''
            if not p_name:
                continue
            p_num = part_numbers[i].strip() if i < len(part_numbers) else ''
            p_qty = max(1, parse_int_field(quantities[i] if i < len(quantities) else '1', 1))
            p_urg = urgencies[i].strip() if i < len(urgencies) else 'Standard'
            p_note = part_notes_list[i].strip() if i < len(part_notes_list) else ''

            match_part = query_db("SELECT id FROM spare_parts WHERE part_name = %s OR (part_number = %s AND %s != '') LIMIT 1", (p_name, p_num, p_num), one=True)
            p_id = match_part['id'] if match_part else None

            query_db("""
                INSERT INTO part_requests 
                (service_record_id, technician_id, requested_by, part_id, part_name, part_number, quantity_requested, priority, technician_notes, status, requested_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'Pending', NOW())
            """, (job_id, user_id, user_id, p_id, p_name, p_num, p_qty, p_urg, p_note), commit=True)
            requested_parts_count += 1

        new_status = 'Parts Under Review' if requested_parts_count > 0 else 'Inspection Submitted'
        prev_status = job['status']

        query_db("""
            UPDATE service_records
            SET status = %s,
                inspection_symptoms = %s,
                inspection_diagnosis = %s,
                inspection_notes = %s,
                inspection_photos = %s,
                technician_notes = %s,
                inspection_completed_at = NOW()
            WHERE id = %s
        """, (new_status, inspection_symptoms, inspection_diagnosis, inspection_notes, inspection_photos,
              inspection_notes or inspection_diagnosis, job_id), commit=True)

        tech_name = session.get('user_name', 'Technician')
        log_workflow_action(
            job_id,
            prev_status,
            new_status,
            user_id,
            'Technician',
            'Vehicle Inspection & Parts Requisition Submitted',
            f"Diagnosis: {inspection_diagnosis[:100]}... | Requested Parts: {requested_parts_count} component(s)."
        )

        if requested_parts_count > 0:
            dispatch_role_notification(
                'Spare Parts',
                f"New Parts Request: WO {job['invoice_number']}",
                f"{tech_name} completed inspection on {job['plate_number']} and requested {requested_parts_count} spare part(s).",
                url_for('parts_requests'),
                notif_type='parts_requested'
            )

        dispatch_role_notification(
            'Admin',
            f"Inspection Submitted: WO {job['invoice_number']}",
            f"{tech_name} recorded vehicle inspection for {job['plate_number']}. Status: {new_status}.",
            url_for('service_detail', record_id=job_id),
            notif_type='inspection_submitted'
        )

        flash(f"Vehicle inspection for {job['invoice_number']} recorded! {requested_parts_count} spare part(s) dispatched to Spare Parts Department.", "success")
        return redirect(url_for('tech_job_detail', job_id=job_id))

    return render_template('technician/inspection_form.html', job=job, catalog_parts=catalog_parts)

@app.route('/tech/jobs/<int:job_id>/estimate-duration', methods=['POST'])
@login_required
@technician_required
def tech_job_estimate_duration(job_id):
    """Step 3: Technician estimates hands-on repair duration and submits to Admin for scheduling."""
    user_id = session['user_id']
    user_role = session.get('user_role')

    job = query_db("SELECT * FROM service_records WHERE id = %s", (job_id,), one=True)
    if not job:
        flash("Work order not found.", "danger")
        return redirect(url_for('tech_jobs'))

    if user_role != 'Admin' and job['user_id'] != user_id:
        flash("You are not authorized to estimate jobs assigned to another technician.", "danger")
        return redirect(url_for('tech_jobs'))

    duration_raw = request.form.get('estimated_duration_hours', '').strip()
    try:
        duration_hours = float(duration_raw) if duration_raw else 0.0
    except ValueError:
        flash("Please enter a valid numeric estimated duration in hours (e.g. 3.5).", "danger")
        return redirect(url_for('tech_job_detail', job_id=job_id))

    tech_notes = request.form.get('estimate_notes', '').strip()
    prev_status = job['status']

    try:
        query_db("""
            UPDATE service_records
            SET estimated_duration_hours = %s,
                status = 'Ready to Schedule',
                technician_notes = CASE WHEN %s != '' THEN %s ELSE technician_notes END
            WHERE id = %s
        """, (duration_hours, tech_notes, tech_notes, job_id), commit=True)

        tech_name = session.get('user_name', 'Technician')
        log_workflow_action(
            job_id,
            prev_status,
            'Ready to Schedule',
            user_id,
            'Technician',
            'Technician Estimated Repair Duration',
            f"Estimated Hands-on Duration: {duration_hours} hours. Notes: {tech_notes}".strip()
        )

        dispatch_role_notification(
            'Admin',
            f"Ready to Schedule: WO {job['invoice_number']}",
            f"{tech_name} submitted repair duration estimate ({duration_hours} hrs) for Work Order {job['invoice_number']}. Ready for scheduling & authorization.",
            url_for('service_detail', record_id=job_id),
            notif_type='ready_to_schedule'
        )

        flash(f"Repair duration estimate ({duration_hours} hrs) submitted! Work order is now Ready to Schedule by Admin.", "success")
    except Exception as e:
        flash(f"Failed to submit duration estimate: {str(e)}", "danger")

    return redirect(url_for('tech_job_detail', job_id=job_id))

@app.route('/tech/jobs/<int:job_id>/start-repair', methods=['POST'])
@login_required
@technician_required
def tech_start_repair(job_id):
    """Step 5: Technician starts repair once scheduled by Admin AND required parts are available."""
    user_id = session['user_id']
    user_role = session.get('user_role')

    job = query_db("""
        SELECT sr.*, v.plate_number, v.make, v.model
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        WHERE sr.id = %s
    """, (job_id,), one=True)

    if not job:
        flash("Work order not found.", "danger")
        return redirect(url_for('tech_jobs'))

    if user_role != 'Admin' and job['user_id'] != user_id:
        flash("You are not authorized to start jobs assigned to another technician.", "danger")
        return redirect(url_for('tech_jobs'))

    # GUARD 1: Must be scheduled / authorized by Admin
    if job['status'] not in ('Scheduled', 'In Progress', 'Accepted', 'On Hold', 'Revision Required'):
        flash(f"Repair cannot begin: Work order must be Authorized and Scheduled by Admin first (Current Status: {job['status']}).", "danger")
        return redirect(url_for('tech_job_detail', job_id=job_id))

    # GUARD 2: Required parts must be available
    pending_parts = query_db("""
        SELECT part_name, status, estimated_delivery_date, estimated_days 
        FROM part_requests 
        WHERE service_record_id = %s 
          AND status IN ('Waiting for Parts', 'Pending', 'Unavailable - Ordered', 'Not Available', 'Clarification Requested')
    """, (job_id,)) or []

    if pending_parts:
        part_names = ", ".join([p['part_name'] for p in pending_parts[:3]])
        flash(f"Repair cannot begin: Required parts ({part_names}) are not yet available. All required parts must be confirmed available before starting repair.", "danger")
        return redirect(url_for('tech_job_detail', job_id=job_id))

    try:
        prev_status = job['status']
        query_db("UPDATE service_records SET status = 'In Progress' WHERE id = %s", (job_id,), commit=True)
        query_db("UPDATE vehicles SET status = 'In Service' WHERE id = %s", (job['vehicle_id'],), commit=True)

        tech_name = session.get('user_name', 'Technician')
        log_workflow_action(
            job_id,
            prev_status,
            'In Progress',
            user_id,
            'Technician',
            'Repair Work Commenced by Technician',
            f"Technician {tech_name} started mechanical repair."
        )

        dispatch_role_notification(
            'Admin',
            f"Repair In Progress: {job['invoice_number']}",
            f"{tech_name} commenced repair on {job['plate_number']} ({job['invoice_number']}).",
            url_for('service_detail', record_id=job_id),
            notif_type='repair_started'
        )

        flash(f"Repair work started for Work Order {job['invoice_number']}. Vehicle marked as 'In Service'.", "success")
    except Exception as e:
        flash(f"Failed to start repair: {str(e)}", "danger")

    return redirect(url_for('tech_job_detail', job_id=job_id))

@app.route('/tech/jobs/<int:job_id>/complete-repair', methods=['POST'])
@login_required
@technician_required
def tech_complete_repair(job_id):
    """Step 5: Technician marks repair complete and submits for Admin quality review."""
    user_id = session['user_id']
    user_role = session.get('user_role')

    job = query_db("""
        SELECT sr.*, v.plate_number, v.make, v.model
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        WHERE sr.id = %s
    """, (job_id,), one=True)

    if not job:
        flash("Work order not found.", "danger")
        return redirect(url_for('tech_jobs'))

    if user_role != 'Admin' and job['user_id'] != user_id:
        flash("You are not authorized to update jobs assigned to another technician.", "danger")
        return redirect(url_for('tech_jobs'))

    repair_notes = request.form.get('repair_completion_notes', '').strip()
    prev_status = job['status']

    try:
        query_db("""
            UPDATE service_records
            SET status = 'Awaiting Admin Approval',
                technician_notes = CASE WHEN %s != '' THEN %s ELSE technician_notes END
            WHERE id = %s
        """, (repair_notes, repair_notes, job_id), commit=True)

        tech_name = session.get('user_name', 'Technician')
        log_workflow_action(
            job_id,
            prev_status,
            'Awaiting Admin Approval',
            user_id,
            'Technician',
            'Repair Completed & Submitted for Admin Review',
            repair_notes or 'All mechanical work completed. Vehicle ready for Admin quality check.'
        )

        dispatch_role_notification(
            'Admin',
            f"Review Needed: Repair Completed on {job['invoice_number']}",
            f"{tech_name} completed repair work on {job['plate_number']} ({job['invoice_number']}). Please review and authorize for final reporting.",
            url_for('service_detail', record_id=job_id),
            notif_type='awaiting_admin_approval'
        )

        flash(f"Repair marked as complete and sent to Admin for quality review and approval.", "info")
    except Exception as e:
        flash(f"Failed to submit completed repair: {str(e)}", "danger")

    return redirect(url_for('tech_job_detail', job_id=job_id))

@app.route('/tech/jobs/<int:job_id>/status', methods=['POST'])
@login_required
@technician_required
def tech_job_status_update(job_id):
    """Updates job status with automatic sync, guard checks, and audit logging."""
    user_id = session['user_id']
    user_role = session.get('user_role')

    job = query_db("SELECT * FROM service_records WHERE id = %s", (job_id,), one=True)
    if not job:
        flash("Work order not found.", "danger")
        return redirect(url_for('tech_jobs'))

    if user_role != 'Admin' and job['user_id'] != user_id:
        flash("You are only authorized to update jobs assigned to you.", "danger")
        return redirect(url_for('tech_jobs'))

    new_status = request.form.get('status', '').strip()
    valid_statuses = ('Accepted', 'In Progress', 'On Hold', 'Completed', 'Awaiting Admin Approval')
    if new_status not in valid_statuses:
        flash("Invalid status selected.", "danger")
        return redirect(url_for('tech_job_detail', job_id=job_id))

    if new_status == 'In Progress':
        # Guard: check pending parts
        pending_parts = query_db("""
            SELECT part_name FROM part_requests 
            WHERE service_record_id = %s 
              AND status IN ('Waiting for Parts', 'Unavailable - Ordered', 'Not Available')
        """, (job_id,)) or []
        if pending_parts:
            part_names = ", ".join([p['part_name'] for p in pending_parts[:3]])
            flash(f"Notice: Parts ({part_names}) are still pending. Parts must be available to complete full repair.", "warning")

    if new_status == 'Completed':
        existing_report = query_db("SELECT id FROM service_reports WHERE service_record_id = %s", (job_id,), one=True)
        if not existing_report:
            flash("Before completing this job, please fill out and submit the official Service Report.", "warning")
            return redirect(url_for('tech_job_report_form', job_id=job_id))

    try:
        prev_status = job['status']
        completed_at = datetime.now() if new_status == 'Completed' else job['completed_at']
        query_db("""
            UPDATE service_records 
            SET status = %s, completed_at = %s 
            WHERE id = %s
        """, (new_status, completed_at, job_id), commit=True)

        if new_status == 'In Progress':
            query_db("UPDATE vehicles SET status = 'In Service' WHERE id = %s", (job['vehicle_id'],), commit=True)
        elif new_status == 'Completed':
            query_db("UPDATE vehicles SET status = 'Active' WHERE id = %s", (job['vehicle_id'],), commit=True)

        tech_name = session.get('user_name', 'Technician')
        log_workflow_action(
            job_id,
            prev_status,
            new_status,
            user_id,
            'Technician',
            f'Job Status Updated to {new_status}',
            f"Status changed from {prev_status} to {new_status} by {tech_name}."
        )

        admins = query_db("SELECT id FROM users WHERE role = 'Admin' AND status = 'Active'") or []
        for admin in admins:
            dispatch_notification(
                admin['id'],
                f"Job Status Updated: {job['invoice_number']}",
                f"{tech_name} marked Work Order {job['invoice_number']} as '{new_status}'.",
                url_for('service_detail', record_id=job_id),
                notif_type='job_status_changed'
            )

        flash(f"Work order status updated to '{new_status}'.", "success")
    except Exception as e:
        flash(f"Failed to update status: {str(e)}", "danger")

    return redirect(request.referrer or url_for('tech_job_detail', job_id=job_id))

@app.route('/tech/jobs/<int:job_id>/request-part', methods=['POST'])
@login_required
@technician_required
def tech_job_request_part(job_id):
    """Technicians requisition spare parts directly from their job workbench."""
    user_id = session['user_id']
    user_role = session.get('user_role')

    job = query_db("""
        SELECT sr.*, c.name as customer_name, v.plate_number, v.make, v.model
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        WHERE sr.id = %s
    """, (job_id,), one=True)

    if not job:
        flash("Work order not found.", "danger")
        return redirect(url_for('tech_jobs'))

    if user_role != 'Admin' and job['user_id'] != user_id:
        flash("You can only request parts for jobs assigned to you.", "danger")
        return redirect(url_for('tech_jobs'))

    part_id_raw = request.form.get('part_id')
    part_id = int(part_id_raw) if part_id_raw and part_id_raw.isdigit() else None
    part_name = request.form.get('part_name', '').strip()
    part_number = request.form.get('part_number', '').strip().upper()
    quantity_requested = max(1, parse_int_field(request.form.get('quantity_requested'), 1))
    priority = request.form.get('priority', 'Standard')
    technician_notes = request.form.get('technician_notes', '').strip()

    if not part_name:
        flash("Component name is required to submit a requisition.", "danger")
        return redirect(url_for('tech_job_detail', job_id=job_id))

    if not part_id and part_number:
        matched = query_db("SELECT id FROM spare_parts WHERE part_number = %s", (part_number,), one=True)
        if matched:
            part_id = matched['id']

    duplicate_check = query_db("""
        SELECT id FROM part_requests 
        WHERE service_record_id = %s AND (part_name = %s OR (part_number IS NOT NULL AND part_number = %s))
          AND status IN ('Waiting for Parts', 'Pending', 'Request Sent')
          AND requested_at >= NOW() - INTERVAL 30 SECOND
    """, (job_id, part_name, part_number), one=True)
    if duplicate_check:
        flash(f"A requisition for '{part_name}' is already pending (#REQ-{duplicate_check['id']}).", "warning")
        return redirect(url_for('tech_job_detail', job_id=job_id))

    try:
        req_id = query_db("""
            INSERT INTO part_requests 
            (service_record_id, technician_id, requested_by, part_id, part_name, part_number, quantity_requested, quantity_available, priority, technician_notes, status, requested_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s, %s, 'Waiting for Parts', NOW())
        """, (job_id, user_id, user_id, part_id, part_name, part_number, quantity_requested, priority, technician_notes), commit=True)

        query_db("UPDATE service_records SET status = 'Waiting for Parts' WHERE id = %s", (job_id,), commit=True)

        parts_recipients = query_db("SELECT id FROM users WHERE role IN ('Spare Parts', 'Admin') AND status = 'Active'") or []
        for pr_user in parts_recipients:
            dispatch_notification(
                pr_user['id'],
                f"New Part Request: {part_name}",
                f"{session.get('user_name', 'Technician')} requested {quantity_requested}x {part_name} for {job['invoice_number']} ({job['plate_number']}).",
                url_for('parts_requests'),
                notif_type='part_requested'
            )

        flash(f"Requisition for '{part_name}' (Qty: {quantity_requested}) dispatched to Spare Parts Department. Job status set to 'Waiting for Parts'.", "success")
    except Exception as e:
        flash(f"Failed to submit requisition: {str(e)}", "danger")

    return redirect(url_for('tech_job_detail', job_id=job_id))

@app.route('/tech/jobs/<int:job_id>/report', methods=['GET', 'POST'])
@login_required
@technician_required
def tech_job_report_form(job_id):
    """File official certified Service Report before completing a job."""
    user_id = session['user_id']
    user_role = session.get('user_role')

    job = query_db("""
        SELECT sr.*, v.plate_number, v.make, v.model, v.year, v.fuel_type, v.vehicle_type,
               c.name as customer_name, c.phone as customer_phone
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        WHERE sr.id = %s
    """, (job_id,), one=True)

    if not job:
        flash("Work order not found.", "danger")
        return redirect(url_for('tech_jobs'))

    if user_role != 'Admin' and job['user_id'] != user_id:
        flash("You are not authorized to file a report for this work order.", "danger")
        return redirect(url_for('tech_jobs'))

    report = query_db("SELECT * FROM service_reports WHERE service_record_id = %s", (job_id,), one=True)

    if request.method == 'POST':
        diagnosis = request.form.get('diagnosis', '').strip()
        work_performed = request.form.get('work_performed', '').strip()
        solution_provided = request.form.get('solution_provided', '').strip()
        parts_used_summary = request.form.get('parts_used_summary', '').strip()
        remarks = request.form.get('remarks', '').strip()
        completion_date = request.form.get('completion_date') or date.today().isoformat()
        final_odometer = parse_int_field(request.form.get('final_odometer'), job['odometer'])

        # Additional Step 6 fields
        unused_parts_explanation = request.form.get('unused_parts_explanation', '').strip()
        labor_hours_raw = request.form.get('labor_hours', '').strip()
        try:
            labor_hours = float(labor_hours_raw) if labor_hours_raw else None
        except ValueError:
            labor_hours = None

        test_results = request.form.get('test_results', '').strip()
        final_vehicle_condition = request.form.get('final_vehicle_condition', 'Road-Ready & Excellent').strip()
        follow_up_recommendations = request.form.get('follow_up_recommendations', '').strip()

        if not diagnosis or not work_performed or not solution_provided:
            flash("Diagnosis, Work Performed, and Solution Provided are required.", "danger")
            req_parts = query_db("""
                SELECT pr.*, sp.unit_price as catalog_price, sp.tax_rate, sp.part_number as cat_part_number
                FROM part_requests pr
                LEFT JOIN spare_parts sp ON pr.part_id = sp.id
                WHERE pr.service_record_id = %s
                ORDER BY pr.id ASC
            """, (job_id,)) or []
            labor_rates = query_db("SELECT * FROM labor_rates WHERE status = 'Active' ORDER BY service_type ASC") or []
            return render_template('technician/service_report_form.html', job=job, report=report, req_parts=req_parts, labor_rates=labor_rates, default_parts_used="")

        # Handle Before Image
        before_image_url = request.form.get('before_image_url', '').strip() or None
        before_file = request.files.get('before_image_file')
        if before_file and before_file.filename:
            fname = secure_filename(f"before_{job_id}_{int(datetime.now().timestamp())}_{before_file.filename}")
            fpath = os.path.join(app.config['UPLOAD_FOLDER'], fname)
            photo_file = before_file
            photo_file.save(fpath)
            before_image_url = f"/static/uploads/reports/{fname}"
        elif report and report['before_image_url'] and not before_image_url:
            before_image_url = report['before_image_url']

        # Handle After Image
        after_image_url = request.form.get('after_image_url', '').strip() or None
        after_file = request.files.get('after_image_file')
        if after_file and after_file.filename:
            fname = secure_filename(f"after_{job_id}_{int(datetime.now().timestamp())}_{after_file.filename}")
            fpath = os.path.join(app.config['UPLOAD_FOLDER'], fname)
            after_file.save(fpath)
            after_image_url = f"/static/uploads/reports/{fname}"
        elif report and report['after_image_url'] and not after_image_url:
            after_image_url = report['after_image_url']

        try:
            # 1. Labor Calculation from configured labor rates
            labor_rate_id_raw = request.form.get('labor_rate_id')
            labor_rate_id = int(labor_rate_id_raw) if labor_rate_id_raw and labor_rate_id_raw.isdigit() else None
            lr = query_db("SELECT * FROM labor_rates WHERE id = %s", (labor_rate_id,), one=True) if labor_rate_id else None
            if not lr:
                lr = query_db("SELECT * FROM labor_rates WHERE status = 'Active' ORDER BY id ASC LIMIT 1", one=True)

            if lr:
                labor_service_type = lr['service_type']
                labor_charge_type = lr['charge_type']
                labor_tax_rate = float(lr.get('tax_rate', 18.0) or 18.0)
                labor_std_hrs = float(lr.get('standard_hours', 1.0) or 1.0)
                effective_labor_hours = labor_hours if labor_hours else labor_std_hrs
                if labor_charge_type == 'Fixed':
                    labor_cost = float(lr['fixed_price'])
                    labor_rate_applied = float(lr['fixed_price'])
                    labor_qty = 1.0
                else:
                    labor_rate_applied = float(lr['hourly_rate'])
                    labor_cost = round(effective_labor_hours * labor_rate_applied, 2)
                    labor_qty = effective_labor_hours
                labor_tax_total = round(labor_cost * (labor_tax_rate / 100.0), 2)
            else:
                labor_service_type = 'General Mechanical Labor'
                labor_charge_type = 'Hourly'
                labor_rate_applied = 800.0
                effective_labor_hours = labor_hours if labor_hours else 2.0
                labor_cost = round(effective_labor_hours * labor_rate_applied, 2)
                labor_tax_rate = 18.0
                labor_tax_total = round(labor_cost * 0.18, 2)
                labor_qty = effective_labor_hours

            # 2. Parts Calculation & Requisition update
            req_parts_list = query_db("""
                SELECT pr.*, sp.unit_price as catalog_price, sp.tax_rate
                FROM part_requests pr
                LEFT JOIN spare_parts sp ON pr.part_id = sp.id
                WHERE pr.service_record_id = %s
            """, (job_id,)) or []

            parts_subtotal = 0.0
            parts_tax_total = 0.0
            items_to_save = []

            for pr in req_parts_list:
                used_qty = parse_int_field(request.form.get(f"part_used_qty_{pr['id']}"), pr['quantity_requested'])
                unused_reason = request.form.get(f"part_unused_reason_{pr['id']}", '').strip()
                pr_status = 'Used in Service' if used_qty > 0 else 'Unused'
                query_db("""
                    UPDATE part_requests
                    SET quantity_used = %s, unused_explanation = %s, status = %s
                    WHERE id = %s
                """, (used_qty, unused_reason or None, pr_status, pr['id']), commit=True)

                if used_qty > 0:
                    p_unit = float(pr.get('catalog_price') or 0.0)
                    p_tax_rate = float(pr.get('tax_rate') if pr.get('tax_rate') is not None else 18.0)
                    line_total = round(used_qty * p_unit, 2)
                    line_tax = round(line_total * (p_tax_rate / 100.0), 2)
                    parts_subtotal += line_total
                    parts_tax_total += line_tax
                    items_to_save.append(('Part', pr['part_name'], used_qty, p_unit, p_tax_rate, line_tax, line_total, pr.get('part_id'), None))

            # Add labor line item
            items_to_save.append(('Labor', labor_service_type, labor_qty, labor_rate_applied, labor_tax_rate, labor_tax_total, labor_cost, None, lr['id'] if lr else None))

            # 3. Insert into service_items
            query_db("DELETE FROM service_items WHERE service_record_id = %s", (job_id,), commit=True)
            for it in items_to_save:
                query_db("""
                    INSERT INTO service_items (service_record_id, item_type, item_name, quantity, unit_price, tax_rate, tax_amount, total_price, part_id, labor_rate_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (job_id, it[0], it[1], it[2], it[3], it[4], it[5], it[6], it[7], it[8]), commit=True)

            # 4. Total Calculation
            total_tax = round(parts_tax_total + labor_tax_total, 2)
            grand_total = round(parts_subtotal + labor_cost + total_tax, 2)

            # Update service_reports with cost totals
            if report:
                query_db("""
                    UPDATE service_reports
                    SET diagnosis=%s, work_performed=%s, solution_provided=%s,
                        parts_used_summary=%s, remarks=%s, before_image_url=%s, after_image_url=%s,
                        completion_date=%s, labor_hours=%s, test_results=%s,
                        unused_parts_explanation=%s, final_vehicle_condition=%s,
                        follow_up_recommendations=%s, labor_service_type=%s,
                        labor_rate_applied=%s, labor_charge_type=%s,
                        parts_cost_total=%s, labor_cost_total=%s, tax_cost_total=%s, grand_total=%s,
                        updated_at=NOW()
                    WHERE id = %s
                """, (diagnosis, work_performed, solution_provided, parts_used_summary,
                      remarks, before_image_url, after_image_url, completion_date,
                      effective_labor_hours, test_results, unused_parts_explanation,
                      final_vehicle_condition, follow_up_recommendations,
                      labor_service_type, labor_rate_applied, labor_charge_type,
                      parts_subtotal, labor_cost, total_tax, grand_total, report['id']), commit=True)
            else:
                query_db("""
                    INSERT INTO service_reports 
                    (service_record_id, technician_id, diagnosis, work_performed, solution_provided,
                     parts_used_summary, remarks, before_image_url, after_image_url, completion_date,
                     labor_hours, test_results, unused_parts_explanation, final_vehicle_condition, follow_up_recommendations,
                     labor_service_type, labor_rate_applied, labor_charge_type, parts_cost_total, labor_cost_total, tax_cost_total, grand_total)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (job_id, user_id, diagnosis, work_performed, solution_provided,
                      parts_used_summary, remarks, before_image_url, after_image_url, completion_date,
                      effective_labor_hours, test_results, unused_parts_explanation, final_vehicle_condition, follow_up_recommendations,
                      labor_service_type, labor_rate_applied, labor_charge_type, parts_subtotal, labor_cost, total_tax, grand_total), commit=True)

            prev_status = job['status']
            submit_action = request.form.get('submit_action', '').strip()
            tech_name = session.get('user_name', 'Technician')

            # Check if workflow should submit for admin review OR complete directly
            if submit_action == 'submit_for_approval' or (job['status'] in ('In Progress', 'Scheduled', 'Revision Required') and job['admin_approved_at'] is None and submit_action != 'complete_direct'):
                query_db("""
                    UPDATE service_records
                    SET status = 'Awaiting Admin Approval',
                        bill_status = 'Under Review',
                        bill_generated_at = NOW(),
                        parts_cost = %s,
                        labor_cost = %s,
                        tax_amount = %s,
                        total_cost = %s,
                        labor_rate_id = %s,
                        labor_charge_type = %s,
                        labor_rate_applied = %s,
                        labor_hours_billed = %s,
                        odometer = %s
                    WHERE id = %s
                """, (parts_subtotal, labor_cost, total_tax, grand_total, lr['id'] if lr else None, labor_charge_type, labor_rate_applied, effective_labor_hours, final_odometer, job_id), commit=True)

                log_workflow_action(
                    job_id,
                    prev_status,
                    'Awaiting Admin Approval',
                    user_id,
                    'Technician',
                    'Final Work Report Submitted & Bill Generated for Admin Review',
                    f"Labor: {effective_labor_hours} hrs ({labor_service_type}). Final work report filed and itemized bill generated for Admin review."
                )

                dispatch_role_notification(
                    'Admin',
                    f"Final Report & Bill Ready: {job['invoice_number']}",
                    f"{tech_name} completed work and submitted the final report for {job['invoice_number']}. Auto-generated bill of ₹{grand_total:,.2f} is ready for review.",
                    url_for('service_detail', record_id=job_id),
                    notif_type='report_submitted'
                )

                flash("Certified Final Service Report and parts usage submitted to Admin for review & approval!", "success")
                return redirect(url_for('tech_job_detail', job_id=job_id))
            else:
                # Direct completion (Admin approved or standalone legacy test)
                query_db("""
                    UPDATE service_records 
                    SET status = 'Completed',
                        bill_status = 'Approved',
                        completed_at = NOW(),
                        parts_cost = %s,
                        labor_cost = %s,
                        tax_amount = %s,
                        total_cost = %s,
                        labor_rate_id = %s,
                        labor_charge_type = %s,
                        labor_rate_applied = %s,
                        labor_hours_billed = %s,
                        odometer = %s
                    WHERE id = %s
                """, (parts_subtotal, labor_cost, total_tax, grand_total, lr['id'] if lr else None, labor_charge_type, labor_rate_applied, effective_labor_hours, final_odometer, job_id), commit=True)

                query_db("UPDATE vehicles SET status = 'Active', current_odometer = GREATEST(current_odometer, %s) WHERE id = %s",
                         (final_odometer, job['vehicle_id']), commit=True)

                log_workflow_action(
                    job_id,
                    prev_status,
                    'Completed',
                    user_id,
                    'Technician',
                    'Final Certified Repair Report Submitted & Work Order Closed',
                    f"Labor Time: {effective_labor_hours or 'N/A'} hrs ({labor_service_type}). Vehicle Condition: {final_vehicle_condition}. Final Odometer: {final_odometer} km."
                )

                dispatch_role_notification(
                    'Admin',
                    f"Service Report Submitted: {job['invoice_number']}",
                    f"{tech_name} submitted the certified Service Report for Work Order {job['invoice_number']} ({job['plate_number']}). Work Order finalized & closed. Total: ₹{grand_total:,.2f}.",
                    url_for('service_detail', record_id=job_id),
                    notif_type='job_completed'
                )

                dispatch_role_notification(
                    'Spare Parts',
                    f"Work Order Closed: {job['invoice_number']}",
                    f"Repairs finalized for Work Order {job['invoice_number']}. Spare parts consumption reconciled.",
                    url_for('parts_requests'),
                    notif_type='parts_reconciled'
                )

                flash(f"Certified Final Service Report for {job['invoice_number']} submitted successfully! Work order is now Completed & Closed.", "success")
                return redirect(url_for('tech_job_report_view', job_id=job_id))
        except Exception as e:
            flash(f"Failed to submit service report: {str(e)}", "danger")

    req_parts = query_db("""
        SELECT pr.*, sp.unit_price as catalog_price, sp.tax_rate, sp.part_number as cat_part_number
        FROM part_requests pr
        LEFT JOIN spare_parts sp ON pr.part_id = sp.id
        WHERE pr.service_record_id = %s
        ORDER BY pr.id ASC
    """, (job_id,)) or []
    labor_rates = query_db("SELECT * FROM labor_rates WHERE status = 'Active' ORDER BY service_type ASC") or []
    default_parts_used = ", ".join([f"{p['quantity_available'] or p['quantity_requested']}x {p['part_name']}" for p in req_parts])

    return render_template(
        'technician/service_report_form.html',
        job=job,
        report=report,
        req_parts=req_parts,
        labor_rates=labor_rates,
        default_parts_used=default_parts_used
    )

@app.route('/tech/jobs/<int:job_id>/report/view')
@app.route('/services/<int:job_id>/report/print')
@login_required
def tech_job_report_view(job_id):
    """Printable certified official Service Report view."""
    user_id = session.get('user_id')
    user_role = session.get('user_role')

    job = query_db("""
        SELECT sr.*, v.plate_number, v.vin, v.make, v.model, v.year, v.color, v.fuel_type, v.vehicle_type,
               c.name as customer_name, c.company_name, c.phone as customer_phone, c.email as customer_email,
               c.address as customer_address, c.city as customer_city,
               u.name as tech_name, u.role as tech_role, u.technician_code, u.specialization
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        LEFT JOIN users u ON sr.user_id = u.id
        WHERE sr.id = %s
    """, (job_id,), one=True)

    if not job:
        flash("Work order not found.", "danger")
        return redirect(url_for('tech_jobs'))

    if user_role == 'Technician' and job['user_id'] != user_id:
        flash("You are not authorized to view reports for jobs assigned to another technician.", "danger")
        return redirect(url_for('tech_jobs'))

    report = query_db("SELECT * FROM service_reports WHERE service_record_id = %s", (job_id,), one=True)
    if not report:
        flash("A service report has not been submitted for this work order yet.", "warning")
        return redirect(url_for('tech_job_detail', job_id=job_id))

    parts_used = query_db("""
        SELECT pr.id, pr.part_name, pr.part_number, pr.quantity_requested,
               COALESCE(pr.quantity_used, pr.quantity_requested) as quantity_used, pr.status
        FROM part_requests pr
        WHERE pr.service_record_id = %s AND (pr.quantity_used > 0 OR pr.status IN ('Used in Service', 'Issued', 'Received by Technician', 'Part Available', 'Approved'))
        ORDER BY pr.id ASC
    """, (job_id,)) or []

    return render_template('technician/service_report_view.html', job=job, report=report, parts_used=parts_used)

@app.route('/tech/jobs/<int:job_id>/reschedule', methods=['POST'])
@login_required
@technician_required
def tech_job_reschedule(job_id):
    """Technician submits a formal appointment reschedule request with reason."""
    user_id = session['user_id']
    user_role = session.get('user_role')

    job = query_db("SELECT * FROM service_records WHERE id = %s", (job_id,), one=True)
    if not job:
        flash("Work order not found.", "danger")
        return redirect(url_for('tech_jobs'))

    if user_role != 'Admin' and job['user_id'] != user_id:
        flash("You can only request rescheduling for your assigned jobs.", "danger")
        return redirect(url_for('tech_jobs'))

    reschedule_date = request.form.get('reschedule_date')
    reschedule_time = request.form.get('reschedule_time', '10:00:00')
    reschedule_reason = request.form.get('reschedule_reason', '').strip()

    if not reschedule_date or not reschedule_reason:
        flash("Proposed date and reason for rescheduling are required.", "danger")
        return redirect(url_for('tech_job_detail', job_id=job_id))

    try:
        query_db("""
            UPDATE service_records
            SET reschedule_requested = 1, reschedule_date = %s, reschedule_time = %s, reschedule_reason = %s
            WHERE id = %s
        """, (reschedule_date, reschedule_time, reschedule_reason, job_id), commit=True)

        admins = query_db("SELECT id FROM users WHERE role = 'Admin' AND status = 'Active'") or []
        tech_name = session.get('user_name', 'Technician')
        for admin in admins:
            dispatch_notification(
                admin['id'],
                f"Reschedule Requested: {job['invoice_number']}",
                f"{tech_name} requested to reschedule {job['invoice_number']} to {reschedule_date} ({reschedule_time}). Reason: {reschedule_reason}",
                url_for('service_detail', record_id=job_id),
                notif_type='reschedule_request'
            )

        flash(f"Reschedule request submitted for {job['invoice_number']}. Admin notified for approval.", "success")
    except Exception as e:
        flash(f"Failed to submit reschedule request: {str(e)}", "danger")

    return redirect(url_for('tech_job_detail', job_id=job_id))

@app.route('/tech/jobs/<int:job_id>/feedback', methods=['POST'])
@login_required
def tech_job_feedback(job_id):
    """Records customer feedback and star satisfaction rating."""
    rating = parse_int_field(request.form.get('customer_rating'), 5)
    feedback = request.form.get('customer_feedback', '').strip()

    try:
        query_db("""
            UPDATE service_records
            SET customer_rating = %s, customer_feedback = %s
            WHERE id = %s
        """, (rating, feedback, job_id), commit=True)
        flash("Customer feedback and rating recorded successfully.", "success")
    except Exception as e:
        flash(f"Failed to record feedback: {str(e)}", "danger")

    return redirect(request.referrer or url_for('tech_job_detail', job_id=job_id))

@app.route('/tech/profile', methods=['GET', 'POST'])
@login_required
@technician_required
def tech_profile():
    """Technician profile management: skills, specialization, availability status, and credentials."""
    user_id = session['user_id']
    user = query_db("SELECT * FROM users WHERE id = %s", (user_id,), one=True)

    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'update_profile':
            name = request.form.get('name', '').strip()
            phone = request.form.get('phone', '').strip()
            skills = request.form.get('skills', '').strip()
            specialization = request.form.get('specialization', '').strip()
            availability_status = request.form.get('availability_status', 'Available')

            if not name or not phone:
                flash("Name and Phone Number are required.", "danger")
            else:
                try:
                    query_db("""
                        UPDATE users
                        SET name = %s, phone = %s, skills = %s, specialization = %s, availability_status = %s
                        WHERE id = %s
                    """, (name, phone, skills, specialization, availability_status, user_id), commit=True)
                    session['user_name'] = name
                    flash(f"Profile updated! Duty availability status set to '{availability_status}'.", "success")
                    return redirect(url_for('tech_profile'))
                except Exception as e:
                    flash(f"Failed to update profile: {str(e)}", "danger")

        elif form_type == 'change_password':
            current_pwd = request.form.get('current_password', '')
            new_pwd = request.form.get('new_password', '')
            confirm_pwd = request.form.get('confirm_password', '')

            if not check_password_hash(user['password_hash'], current_pwd):
                flash("Current password entered is incorrect.", "danger")
            elif new_pwd != confirm_pwd:
                flash("New passwords do not match.", "danger")
            elif len(new_pwd) < 6:
                flash("New password must be at least 6 characters.", "danger")
            else:
                try:
                    new_hash = generate_password_hash(new_pwd)
                    query_db("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user_id), commit=True)
                    flash("Password successfully changed! Please use your new credentials on next login.", "success")
                    return redirect(url_for('tech_profile'))
                except Exception as e:
                    flash(f"Failed to change password: {str(e)}", "danger")

    stats = query_db("""
        SELECT 
            COUNT(*) as total_assigned,
            COALESCE(SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END), 0) as completed,
            COALESCE(SUM(CASE WHEN status NOT IN ('Completed', 'Cancelled') THEN 1 ELSE 0 END), 0) as in_progress
        FROM service_records
        WHERE user_id = %s
    """, (user_id,), one=True) or {'total_assigned': 0, 'completed': 0, 'in_progress': 0}

    return render_template('technician/profile.html', user=user, stats=stats)

@app.route('/tech/notifications')
@login_required
@technician_required
def tech_notifications():
    """Complete alerts & communications log for the technician."""
    all_notifications = query_db("""
        SELECT * FROM notifications 
        WHERE user_id = %s 
        ORDER BY is_read ASC, created_at DESC
    """, (session['user_id'],)) or []

    return render_template('technician/notifications.html', all_notifications=all_notifications)

# =============================================================
# Admin Multiple Technicians Management Module
# =============================================================

@app.route('/admin/technicians')
@login_required
@admin_required
def admin_technicians():
    """Technicians Roster & Workload Management Center for Administrators."""
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    availability_filter = request.args.get('availability', '').strip()

    sql = """
        SELECT u.id, u.name, u.email, u.phone, u.address, u.role, u.status,
               u.technician_code, u.specialization, u.skills, u.availability_status, u.created_at,
               COALESCE(COUNT(sr.id), 0) as total_assigned,
               COALESCE(SUM(CASE WHEN sr.status = 'Pending' THEN 1 ELSE 0 END), 0) as pending_count,
               COALESCE(SUM(CASE WHEN sr.status IN ('Accepted', 'In Progress', 'Waiting for Parts', 'On Hold') THEN 1 ELSE 0 END), 0) as ongoing_count,
               COALESCE(SUM(CASE WHEN sr.status = 'Completed' THEN 1 ELSE 0 END), 0) as completed_count,
               ROUND(AVG(sr.customer_rating), 1) as avg_rating
        FROM users u
        LEFT JOIN service_records sr ON u.id = sr.user_id
        WHERE u.role = 'Technician'
    """
    params = []

    if search:
        sql += """ AND (
            u.name LIKE %s OR 
            u.email LIKE %s OR 
            u.phone LIKE %s OR 
            u.technician_code LIKE %s OR 
            u.specialization LIKE %s OR
            u.skills LIKE %s
        )"""
        term = f"%{search}%"
        params.extend([term, term, term, term, term, term])

    if status_filter and status_filter != 'All':
        sql += " AND u.status = %s"
        params.append(status_filter)

    if availability_filter and availability_filter != 'All':
        sql += " AND u.availability_status = %s"
        params.append(availability_filter)

    sql += " GROUP BY u.id ORDER BY u.status ASC, u.name ASC"

    technicians = query_db(sql, tuple(params)) or []

    # Overall metrics
    total_technicians = query_db("SELECT COUNT(*) as cnt FROM users WHERE role = 'Technician'", one=True)['cnt'] or 0
    active_technicians = query_db("SELECT COUNT(*) as cnt FROM users WHERE role = 'Technician' AND status = 'Active'", one=True)['cnt'] or 0
    available_now = query_db("SELECT COUNT(*) as cnt FROM users WHERE role = 'Technician' AND status = 'Active' AND availability_status = 'Available'", one=True)['cnt'] or 0
    busy_now = query_db("SELECT COUNT(*) as cnt FROM users WHERE role = 'Technician' AND status = 'Active' AND availability_status = 'Busy'", one=True)['cnt'] or 0
    on_leave_now = query_db("SELECT COUNT(*) as cnt FROM users WHERE role = 'Technician' AND status = 'Active' AND availability_status = 'On Leave'", one=True)['cnt'] or 0
    total_active_jobs = query_db("""
        SELECT COUNT(*) as cnt FROM service_records sr 
        JOIN users u ON sr.user_id = u.id 
        WHERE u.role = 'Technician' AND sr.status NOT IN ('Completed', 'Cancelled')
    """, one=True)['cnt'] or 0

    return render_template(
        'admin/technicians/index.html',
        technicians=technicians,
        search=search,
        status_filter=status_filter,
        availability_filter=availability_filter,
        total_technicians=total_technicians,
        active_technicians=active_technicians,
        available_now=available_now,
        busy_now=busy_now,
        on_leave_now=on_leave_now,
        total_active_jobs=total_active_jobs
    )

@app.route('/admin/technicians/create', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_technician_create():
    """Allows Admin to register a new technician with independent login credentials, contact, and profile."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        technician_code = request.form.get('technician_code', '').strip().upper()
        specialization = request.form.get('specialization', '').strip()
        skills = request.form.get('skills', '').strip()
        availability_status = request.form.get('availability_status', 'Available')
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Required validation
        if not name or not email or not phone or not password:
            flash("Name, Email, Mobile Contact, and Password are required fields.", "danger")
            return render_template('admin/technicians/form.html', technician=None, suggested_code=technician_code)

        if password != confirm_password:
            flash("Passwords entered do not match.", "danger")
            return render_template('admin/technicians/form.html', technician=None, suggested_code=technician_code)

        if len(password) < 6:
            flash("Password must be at least 6 characters in length.", "danger")
            return render_template('admin/technicians/form.html', technician=None, suggested_code=technician_code)

        # Duplicate Email check
        existing_email = query_db("SELECT id, name FROM users WHERE email = %s", (email,), one=True)
        if existing_email:
            flash(f"A user account with email '{email}' already exists ({existing_email['name']}). Duplicate emails are not permitted.", "danger")
            return render_template('admin/technicians/form.html', technician=None, suggested_code=technician_code)

        # Duplicate Phone check
        existing_phone = query_db("SELECT id, name FROM users WHERE phone = %s", (phone,), one=True)
        if existing_phone:
            flash(f"A user with mobile number '{phone}' already exists ({existing_phone['name']}). Duplicate mobile numbers are not permitted.", "danger")
            return render_template('admin/technicians/form.html', technician=None, suggested_code=technician_code)

        # Duplicate Code check
        if technician_code:
            existing_code = query_db("SELECT id, name FROM users WHERE technician_code = %s", (technician_code,), one=True)
            if existing_code:
                flash(f"Technician Code '{technician_code}' is already assigned to {existing_code['name']}. Please assign a unique code.", "danger")
                return render_template('admin/technicians/form.html', technician=None, suggested_code=technician_code)

        try:
            pwd_hash = generate_password_hash(password)
            tech_id = query_db("""
                INSERT INTO users 
                (name, email, password_hash, role, status, technician_code, specialization, skills, availability_status, phone, address)
                VALUES (%s, %s, %s, 'Technician', 'Active', %s, %s, %s, %s, %s, %s)
            """, (name, email, pwd_hash, technician_code or None, specialization, skills, availability_status, phone, address), commit=True)

            flash(f"Technician '{name}' ({technician_code or email}) successfully registered with active login access!", "success")
            return redirect(url_for('admin_technicians'))
        except Exception as e:
            flash(f"Failed to register technician: {str(e)}", "danger")

    # Calculate auto-suggested code
    last_tech = query_db("SELECT technician_code FROM users WHERE role = 'Technician' AND technician_code LIKE 'TECH-%' ORDER BY id DESC LIMIT 1", one=True)
    next_num = 101
    if last_tech and last_tech['technician_code']:
        try:
            curr = int(last_tech['technician_code'].replace('TECH-', ''))
            next_num = curr + 1
        except ValueError:
            next_num = 101
    suggested_code = f"TECH-{next_num}"

    return render_template('admin/technicians/form.html', technician=None, suggested_code=suggested_code)

@app.route('/admin/technicians/<int:tech_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_technician_edit(tech_id):
    """Allows Admin to modify technician details, credentials, availability, and account status."""
    tech = query_db("SELECT * FROM users WHERE id = %s AND role = 'Technician'", (tech_id,), one=True)
    if not tech:
        flash("Technician profile not found.", "danger")
        return redirect(url_for('admin_technicians'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        technician_code = request.form.get('technician_code', '').strip().upper()
        specialization = request.form.get('specialization', '').strip()
        skills = request.form.get('skills', '').strip()
        availability_status = request.form.get('availability_status', 'Available')
        status = request.form.get('status', 'Active')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not name or not email or not phone:
            flash("Name, Email, and Phone number are required.", "danger")
            return render_template('admin/technicians/form.html', technician=tech, suggested_code='')

        # Duplicate email check excluding self
        existing_email = query_db("SELECT id, name FROM users WHERE email = %s AND id != %s", (email, tech_id), one=True)
        if existing_email:
            flash(f"Email '{email}' is already in use by {existing_email['name']}.", "danger")
            return render_template('admin/technicians/form.html', technician=tech, suggested_code='')

        # Duplicate phone check excluding self
        existing_phone = query_db("SELECT id, name FROM users WHERE phone = %s AND id != %s", (phone, tech_id), one=True)
        if existing_phone:
            flash(f"Mobile number '{phone}' is already in use by {existing_phone['name']}.", "danger")
            return render_template('admin/technicians/form.html', technician=tech, suggested_code='')

        # Duplicate code check excluding self
        if technician_code:
            existing_code = query_db("SELECT id, name FROM users WHERE technician_code = %s AND id != %s", (technician_code, tech_id), one=True)
            if existing_code:
                flash(f"Technician Code '{technician_code}' is already used by {existing_code['name']}.", "danger")
                return render_template('admin/technicians/form.html', technician=tech, suggested_code='')

        # Password validation if provided
        password_clause = ""
        params = [name, email, phone, address, technician_code or None, specialization, skills, availability_status, status]

        if new_password:
            if new_password != confirm_password:
                flash("New passwords do not match.", "danger")
                return render_template('admin/technicians/form.html', technician=tech, suggested_code='')
            if len(new_password) < 6:
                flash("New password must be at least 6 characters in length.", "danger")
                return render_template('admin/technicians/form.html', technician=tech, suggested_code='')
            password_clause = ", password_hash = %s"
            params.append(generate_password_hash(new_password))

        params.append(tech_id)

        try:
            query_db(f"""
                UPDATE users
                SET name = %s, email = %s, phone = %s, address = %s, technician_code = %s,
                    specialization = %s, skills = %s, availability_status = %s, status = %s
                    {password_clause}
                WHERE id = %s
            """, tuple(params), commit=True)
            flash(f"Technician '{name}' ({technician_code or email}) details updated successfully.", "success")
            return redirect(url_for('admin_technicians'))
        except Exception as e:
            flash(f"Failed to update technician: {str(e)}", "danger")

    return render_template('admin/technicians/form.html', technician=tech, suggested_code='')

@app.route('/admin/technicians/<int:tech_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def admin_technician_toggle_status(tech_id):
    """1-Click toggle between Active and Inactive authorization states."""
    tech = query_db("SELECT id, name, status, technician_code FROM users WHERE id = %s AND role = 'Technician'", (tech_id,), one=True)
    if not tech:
        flash("Technician profile not found.", "danger")
        return redirect(url_for('admin_technicians'))

    new_status = 'Inactive' if tech['status'] == 'Active' else 'Active'
    try:
        query_db("UPDATE users SET status = %s WHERE id = %s", (new_status, tech_id), commit=True)
        if new_status == 'Inactive':
            flash(f"Technician '{tech['name']}' has been Deactivated. Login access revoked and removed from active assignment roster.", "warning")
        else:
            flash(f"Technician '{tech['name']}' has been Reactivated and can now log in and accept jobs.", "success")
    except Exception as e:
        flash(f"Failed to toggle technician status: {str(e)}", "danger")

    return redirect(request.referrer or url_for('admin_technicians'))

@app.route('/admin/technicians/<int:tech_id>/duty-status', methods=['POST'])
@login_required
@admin_required
def admin_technician_duty_status(tech_id):
    """1-Click quick update for technician duty availability status (Available, Busy, On Leave)."""
    tech = query_db("SELECT id, name, availability_status FROM users WHERE id = %s AND role = 'Technician'", (tech_id,), one=True)
    if not tech:
        flash("Technician profile not found.", "danger")
        return redirect(url_for('admin_technicians'))

    new_status = request.form.get('availability_status', '').strip()
    if new_status not in ('Available', 'Busy', 'On Leave'):
        flash("Invalid duty status selected. Permitted values: Available, Busy, On Leave.", "danger")
        return redirect(request.referrer or url_for('admin_technicians'))

    try:
        query_db("UPDATE users SET availability_status = %s WHERE id = %s", (new_status, tech_id), commit=True)
        flash(f"Duty status for technician '{tech['name']}' has been updated to '{new_status}' successfully!", "success")
    except Exception as e:
        flash(f"Failed to update duty status: {str(e)}", "danger")

    return redirect(request.referrer or url_for('admin_technicians'))

@app.route('/admin/technicians/<int:tech_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_technician_delete(tech_id):
    """Safely deletes technician account, preventing historical record corruption."""
    tech = query_db("SELECT id, name, technician_code FROM users WHERE id = %s AND role = 'Technician'", (tech_id,), one=True)
    if not tech:
        flash("Technician profile not found.", "danger")
        return redirect(url_for('admin_technicians'))

    # Audit associated records
    sr_count = query_db("SELECT COUNT(*) as cnt FROM service_records WHERE user_id = %s", (tech_id,), one=True)['cnt']
    rep_count = query_db("SELECT COUNT(*) as cnt FROM service_reports WHERE technician_id = %s", (tech_id,), one=True)['cnt']
    pr_count = query_db("SELECT COUNT(*) as cnt FROM part_requests WHERE technician_id = %s OR requested_by = %s", (tech_id, tech_id), one=True)['cnt']
    total_records = sr_count + rep_count + pr_count

    if total_records > 0:
        # Cannot hard-delete without destroying foreign keys & customer audit trails
        query_db("UPDATE users SET status = 'Inactive' WHERE id = %s", (tech_id,), commit=True)
        flash(f"Cannot permanently delete '{tech['name']}' because they are linked to {total_records} historical record(s) ({sr_count} work orders, {rep_count} certified reports, {pr_count} part requests). To protect audit trails, the account was automatically Deactivated instead.", "warning")
    else:
        try:
            # Safe to delete cleanly
            query_db("DELETE FROM notifications WHERE user_id = %s", (tech_id,), commit=True)
            query_db("DELETE FROM users WHERE id = %s", (tech_id,), commit=True)
            flash(f"Technician '{tech['name']}' has been permanently deleted from the system.", "info")
        except Exception as e:
            flash(f"Failed to delete technician: {str(e)}", "danger")

    return redirect(url_for('admin_technicians'))

@app.route('/admin/technicians/<int:tech_id>/workload')
@login_required
@admin_required
def admin_technician_workload(tech_id):
    """Deep tracking view of an individual technician's assigned jobs, ongoing work, and part requisitions."""
    tech = query_db("SELECT * FROM users WHERE id = %s AND role = 'Technician'", (tech_id,), one=True)
    if not tech:
        flash("Technician profile not found.", "danger")
        return redirect(url_for('admin_technicians'))

    stats = query_db("""
        SELECT 
            COUNT(*) as total_assigned,
            COALESCE(SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END), 0) as pending_count,
            COALESCE(SUM(CASE WHEN status IN ('Accepted', 'In Progress', 'Waiting for Parts', 'On Hold') THEN 1 ELSE 0 END), 0) as ongoing_count,
            COALESCE(SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END), 0) as completed_count,
            ROUND(AVG(customer_rating), 1) as avg_rating
        FROM service_records
        WHERE user_id = %s
    """, (tech_id,), one=True) or {'total_assigned': 0, 'pending_count': 0, 'ongoing_count': 0, 'completed_count': 0, 'avg_rating': 5.0}

    jobs = query_db("""
        SELECT sr.*, v.plate_number, v.make, v.model, v.year,
               c.name as customer_name, c.phone as customer_phone,
               rep.id as report_id
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        LEFT JOIN service_reports rep ON sr.id = rep.service_record_id
        WHERE sr.user_id = %s
        ORDER BY sr.service_date DESC, sr.id DESC
    """, (tech_id,)) or []

    part_requests = query_db("""
        SELECT pr.*, sr.invoice_number, v.plate_number
        FROM part_requests pr
        JOIN service_records sr ON pr.service_record_id = sr.id
        JOIN vehicles v ON sr.vehicle_id = v.id
        WHERE pr.technician_id = %s OR pr.requested_by = %s
        ORDER BY pr.id DESC
    """, (tech_id, tech_id)) or []

    return render_template(
        'admin/technicians/workload.html',
        tech=tech,
        stats=stats,
        jobs=jobs,
        part_requests=part_requests
    )

# -------------------------------------------------------------
# Admin Labor Rates & Pricing Standards Management
# -------------------------------------------------------------
@app.route('/admin/labor-rates')
@login_required
@admin_required
def admin_labor_rates():
    """Manage standardized labor charges and pre-configured service work packages."""
    search = request.args.get('search', '').strip()
    charge_type = request.args.get('charge_type', '').strip()
    status = request.args.get('status', '').strip()

    sql = "SELECT * FROM labor_rates WHERE 1=1"
    params = []

    if search:
        sql += " AND (service_type LIKE %s OR description LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])

    if charge_type:
        sql += " AND charge_type = %s"
        params.append(charge_type)

    if status:
        sql += " AND status = %s"
        params.append(status)

    sql += " ORDER BY service_type ASC"
    rates = query_db(sql, tuple(params)) or []

    total_rates = query_db("SELECT COUNT(*) as c FROM labor_rates", one=True)['c']
    active_rates_count = query_db("SELECT COUNT(*) as c FROM labor_rates WHERE status = 'Active'", one=True)['c']
    hourly_rates_count = query_db("SELECT COUNT(*) as c FROM labor_rates WHERE charge_type = 'Hourly'", one=True)['c']
    fixed_rates_count = query_db("SELECT COUNT(*) as c FROM labor_rates WHERE charge_type = 'Fixed'", one=True)['c']

    return render_template(
        'admin/labor_rates.html',
        rates=rates,
        total_rates=total_rates,
        active_rates_count=active_rates_count,
        hourly_rates_count=hourly_rates_count,
        fixed_rates_count=fixed_rates_count,
        search=search,
        charge_type_filter=charge_type,
        status_filter=status
    )

@app.route('/admin/labor-rates/add', methods=['POST'])
@login_required
@admin_required
def admin_labor_rate_add():
    service_type = request.form.get('service_type', '').strip()
    charge_type = request.form.get('charge_type', 'Hourly').strip()
    standard_hours = max(0.25, parse_float_field(request.form.get('standard_hours'), 1.0))
    hourly_rate = max(0.0, parse_float_field(request.form.get('hourly_rate'), 0.0))
    fixed_price = max(0.0, parse_float_field(request.form.get('fixed_price'), 0.0))
    tax_rate = max(0.0, parse_float_field(request.form.get('tax_rate'), 18.0))
    description = request.form.get('description', '').strip()

    if not service_type:
        flash("Service Category / Operation Name is required.", "danger")
        return redirect(url_for('admin_labor_rates'))

    try:
        rate_id = query_db("""
            INSERT INTO labor_rates (service_type, charge_type, hourly_rate, fixed_price, standard_hours, tax_rate, description, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'Active')
        """, (service_type, charge_type, hourly_rate, fixed_price, standard_hours, tax_rate, description), commit=True)

        new_val = f"₹{hourly_rate:.2f}/hr" if charge_type == 'Hourly' else f"₹{fixed_price:.2f} Fixed"
        log_pricing_change('Labor Rate', rate_id, service_type, 'Labor Standard Created', None, f"{new_val} (Tax: {tax_rate}%)", session.get('user_id'), f"New {charge_type} labor rate standard established")

        flash(f"Labor rate standard for '{service_type}' created successfully!", "success")
    except Exception as e:
        flash(f"Failed to create labor standard: {str(e)}", "danger")

    return redirect(url_for('admin_labor_rates'))

@app.route('/admin/labor-rates/<int:rate_id>/edit', methods=['POST'])
@login_required
@admin_required
def admin_labor_rate_edit(rate_id):
    lr = query_db("SELECT * FROM labor_rates WHERE id = %s", (rate_id,), one=True)
    if not lr:
        flash("Labor rate standard not found.", "danger")
        return redirect(url_for('admin_labor_rates'))

    service_type = request.form.get('service_type', '').strip()
    charge_type = request.form.get('charge_type', 'Hourly').strip()
    standard_hours = max(0.25, parse_float_field(request.form.get('standard_hours'), 1.0))
    hourly_rate = max(0.0, parse_float_field(request.form.get('hourly_rate'), 0.0))
    fixed_price = max(0.0, parse_float_field(request.form.get('fixed_price'), 0.0))
    tax_rate = max(0.0, parse_float_field(request.form.get('tax_rate'), 18.0))
    description = request.form.get('description', '').strip()
    status = request.form.get('status', 'Active').strip()

    if not service_type:
        flash("Service Category / Operation Name is required.", "danger")
        return redirect(url_for('admin_labor_rates'))

    old_val = f"₹{float(lr['hourly_rate']):.2f}/hr" if lr['charge_type'] == 'Hourly' else f"₹{float(lr['fixed_price']):.2f} Fixed"
    new_val = f"₹{hourly_rate:.2f}/hr" if charge_type == 'Hourly' else f"₹{fixed_price:.2f} Fixed"

    try:
        query_db("""
            UPDATE labor_rates
            SET service_type=%s, charge_type=%s, hourly_rate=%s, fixed_price=%s,
                standard_hours=%s, tax_rate=%s, description=%s, status=%s
            WHERE id = %s
        """, (service_type, charge_type, hourly_rate, fixed_price, standard_hours, tax_rate, description, status, rate_id), commit=True)

        if old_val != new_val or float(lr.get('tax_rate') or 18.0) != tax_rate:
            log_pricing_change('Labor Rate', rate_id, service_type, 'Labor Rate Changed', f"{old_val} ({lr.get('tax_rate', 18)}%)", f"{new_val} ({tax_rate}%)", session.get('user_id'), f"Labor rate changed by Admin {session.get('user_name', 'Admin')}")

        flash(f"Labor standard for '{service_type}' updated successfully.", "success")
    except Exception as e:
        flash(f"Failed to update labor standard: {str(e)}", "danger")

    return redirect(url_for('admin_labor_rates'))

@app.route('/admin/labor-rates/<int:rate_id>/toggle', methods=['POST'])
@login_required
@admin_required
def admin_labor_rate_toggle(rate_id):
    lr = query_db("SELECT id, service_type, status FROM labor_rates WHERE id = %s", (rate_id,), one=True)
    if not lr:
        flash("Labor standard not found.", "danger")
        return redirect(url_for('admin_labor_rates'))

    new_status = 'Inactive' if lr['status'] == 'Active' else 'Active'
    try:
        query_db("UPDATE labor_rates SET status = %s WHERE id = %s", (new_status, rate_id), commit=True)
        log_pricing_change('Labor Rate', rate_id, lr['service_type'], f"Labor Standard {new_status}", lr['status'], new_status, session.get('user_id'), f"Status toggled to {new_status}")
        flash(f"Labor standard '{lr['service_type']}' is now {new_status}.", "success")
    except Exception as e:
        flash(f"Failed to toggle status: {str(e)}", "danger")

    return redirect(request.referrer or url_for('admin_labor_rates'))

@app.route('/admin/labor-rates/<int:rate_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_labor_rate_delete(rate_id):
    lr = query_db("SELECT id, service_type FROM labor_rates WHERE id = %s", (rate_id,), one=True)
    if not lr:
        flash("Labor standard not found.", "danger")
        return redirect(url_for('admin_labor_rates'))

    try:
        used_count = query_db("SELECT COUNT(*) as c FROM service_items WHERE labor_rate_id = %s", (rate_id,), one=True)['c']
        if used_count > 0:
            query_db("UPDATE labor_rates SET status = 'Inactive' WHERE id = %s", (rate_id,), commit=True)
            flash(f"Labor standard '{lr['service_type']}' is referenced by {used_count} historical work order(s); safely set to Inactive instead of deleting.", "warning")
        else:
            query_db("DELETE FROM labor_rates WHERE id = %s", (rate_id,), commit=True)
            flash(f"Labor standard '{lr['service_type']}' removed from catalog.", "info")
    except Exception as e:
        flash(f"Failed to delete labor standard: {str(e)}", "danger")

    return redirect(url_for('admin_labor_rates'))

@app.route('/admin/pricing-audit-logs')
@login_required
@admin_required
def admin_pricing_audit_logs():
    """View immutable audit trail of changes to spare parts prices, labor standards, and work order bill adjustments."""
    search = request.args.get('search', '').strip()
    item_type = request.args.get('item_type', '').strip()

    sql = "SELECT * FROM pricing_audit_logs WHERE 1=1"
    params = []

    if search:
        sql += " AND (item_name LIKE %s OR action LIKE %s OR changed_by_name LIKE %s OR notes LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])

    if item_type:
        sql += " AND item_type = %s"
        params.append(item_type)

    sql += " ORDER BY id DESC LIMIT 200"
    logs = query_db(sql, tuple(params)) or []

    return render_template(
        'admin/pricing_audit.html',
        logs=logs,
        search=search,
        item_type_filter=item_type
    )

@app.route('/services/<int:record_id>/bill/item-adjust', methods=['POST'])
@login_required
@admin_required
def admin_adjust_bill_item(record_id):
    """Allow Admin to adjust line items or apply discount on an active work order bill with audit trail."""
    service = query_db("SELECT * FROM service_records WHERE id = %s", (record_id,), one=True)
    if not service:
        flash("Work order not found.", "danger")
        return redirect(url_for('services_list'))

    item_id = parse_int_field(request.form.get('item_id'), 0)
    new_price = parse_float_field(request.form.get('unit_price'), -1.0)
    new_qty = parse_float_field(request.form.get('quantity'), -1.0)
    reason = request.form.get('reason', '').strip()

    item = query_db("SELECT * FROM service_items WHERE id = %s AND service_record_id = %s", (item_id, record_id), one=True)
    if not item:
        flash("Line item not found.", "danger")
        return redirect(url_for('service_detail', record_id=record_id))

    old_price = float(item['unit_price'])
    old_qty = float(item['quantity'])
    updated_price = new_price if new_price >= 0 else old_price
    updated_qty = new_qty if new_qty > 0 else old_qty

    tax_rate = float(item.get('tax_rate') or 18.0)
    total_price = round(updated_qty * updated_price, 2)
    tax_amount = round(total_price * (tax_rate / 100.0), 2)

    query_db("""
        UPDATE service_items
        SET unit_price = %s, quantity = %s, total_price = %s, tax_amount = %s
        WHERE id = %s
    """, (updated_price, updated_qty, total_price, tax_amount, item_id), commit=True)

    all_items = query_db("SELECT * FROM service_items WHERE service_record_id = %s", (record_id,)) or []
    parts_cost = sum(float(it['total_price']) for it in all_items if it['item_type'] != 'Labor')
    labor_cost = sum(float(it['total_price']) for it in all_items if it['item_type'] == 'Labor')
    tax_amount_total = sum(float(it.get('tax_amount', 0.0) or 0.0) for it in all_items)
    discount = float(service.get('discount_amount', 0.0) or 0.0)
    total_cost = max(0.0, round(parts_cost + labor_cost + tax_amount_total - discount, 2))

    query_db("""
        UPDATE service_records
        SET parts_cost = %s, labor_cost = %s, tax_amount = %s, total_cost = %s
        WHERE id = %s
    """, (parts_cost, labor_cost, tax_amount_total, total_cost, record_id), commit=True)

    log_pricing_change('Service Bill Item', item_id, f"{service['invoice_number']} - {item['item_name']}", 'Bill Item Corrected by Admin', f"Qty {old_qty} @ ₹{old_price:.2f}", f"Qty {updated_qty} @ ₹{updated_price:.2f}", session.get('user_id'), reason or 'Admin billing adjustment')

    flash(f"Line item '{item['item_name']}' updated. Bill recalculated to ₹{total_cost:,.2f}.", "success")
    return redirect(url_for('service_detail', record_id=record_id))

# -------------------------------------------------------------
# AJAX API Endpoints
# -------------------------------------------------------------
@app.route('/api/vehicles/<int:vehicle_id>')
@login_required
def api_vehicle_info(vehicle_id):
    veh = query_db("""
        SELECT v.*, c.name as customer_name, c.company_name
        FROM vehicles v
        JOIN customers c ON v.customer_id = c.id
        WHERE v.id = %s
    """, (vehicle_id,), one=True)
    if veh:
        return jsonify({'success': True, 'vehicle': veh})
    return jsonify({'success': False, 'message': 'Vehicle not found'}), 404

if __name__ == '__main__':
    # Verify DB on launch
    status, msg = check_db_health()
    print("-" * 65)
    print(f"[*] FleetSync Server Starting...")
    print(f"[*] MySQL Health Check: {msg}")
    print(f"[*] URL: http://127.0.0.1:5000")
    print("-" * 65)
    app.run(host='127.0.0.1', port=5000, debug=True)
