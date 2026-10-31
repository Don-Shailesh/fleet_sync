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
import io
import csv

from config import Config
from db import query_db, check_db_health, Error

app = Flask(__name__)
app.config.from_object(Config)

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
        'current_year': datetime.now().year,
        'now': datetime.now()
    }

@app.template_filter('currency')
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

@app.template_filter('format_km')
def format_km_filter(value):
    try:
        return f"{int(value):,} km"
    except (ValueError, TypeError):
        return "0 km"

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
        SELECT sr.*, v.plate_number, v.make, v.model, u.name as tech_name
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
    status_filter = request.args.get('status', '').strip()
    payment_filter = request.args.get('payment', '').strip()
    search = request.args.get('search', '').strip()

    sql = """
        SELECT sr.*, v.plate_number, v.make, v.model, c.name as customer_name, c.company_name, u.name as tech_name
        FROM service_records sr
        JOIN vehicles v ON sr.vehicle_id = v.id
        JOIN customers c ON v.customer_id = c.id
        LEFT JOIN users u ON sr.user_id = u.id
        WHERE 1=1
    """
    params = []

    if search:
        sql += " AND (sr.invoice_number LIKE %s OR v.plate_number LIKE %s OR c.name LIKE %s OR sr.service_type LIKE %s)"
        term = f"%{search}%"
        params.extend([term, term, term, term])

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
    if request.method == 'POST':
        vehicle_id = request.form.get('vehicle_id')
        user_id = request.form.get('user_id') or session.get('user_id')
        service_date = request.form.get('service_date', date.today().isoformat())
        odometer = int(request.form.get('odometer', 0))
        service_type = request.form.get('service_type', 'Preventive Maintenance')
        status = request.form.get('status', 'In Progress')
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
                    invoice_number, vehicle_id, user_id, service_date, odometer,
                    service_type, status, description, technician_notes,
                    parts_cost, labor_cost, tax_amount, total_cost, payment_status, completed_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                invoice_number, vehicle_id, user_id, service_date, odometer,
                service_type, status, description, technician_notes,
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

            flash(f"Work Order {invoice_number} created successfully!", "success")
            return redirect(url_for('service_detail', record_id=record_id))
        except Exception as e:
            flash(f"Error creating work order: {str(e)}", "danger")

    vehicles = query_db("SELECT id, plate_number, make, model, current_odometer FROM vehicles ORDER BY plate_number")
    technicians = query_db("SELECT id, name, role FROM users WHERE status = 'Active' ORDER BY name")
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

    return render_template('services/view.html', service=service, items=items, part_requests=part_requests, catalog_parts=catalog_parts)

@app.route('/services/<int:record_id>/invoice')
@login_required
def service_invoice(record_id):
    """Clean, printable professional invoice view suitable for PDF export or browser print."""
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

    items = query_db("SELECT * FROM service_items WHERE service_record_id = %s", (record_id,))

    return render_template('services/invoice.html', service=service, items=items)

@app.route('/services/<int:record_id>/edit', methods=['GET', 'POST'])
@login_required
def service_edit(record_id):
    service = query_db("SELECT * FROM service_records WHERE id = %s", (record_id,), one=True)
    if not service:
        flash("Work order not found.", "danger")
        return redirect(url_for('services_list'))

    if request.method == 'POST':
        user_id = request.form.get('user_id')
        service_date = request.form.get('service_date')
        odometer = int(request.form.get('odometer', 0))
        service_type = request.form.get('service_type')
        status = request.form.get('status')
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
                SET user_id=%s, service_date=%s, odometer=%s, service_type=%s,
                    status=%s, payment_status=%s, description=%s, technician_notes=%s,
                    parts_cost=%s, labor_cost=%s, tax_amount=%s, total_cost=%s, completed_at=%s
                WHERE id = %s
            """, (user_id, service_date, odometer, service_type, status, payment_status, description, technician_notes,
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

            flash(f"Work order {service['invoice_number']} updated successfully.", "success")
            return redirect(url_for('service_detail', record_id=record_id))
        except Exception as e:
            flash(f"Failed to update work order: {str(e)}", "danger")

    vehicles = query_db("SELECT id, plate_number, make, model FROM vehicles")
    technicians = query_db("SELECT id, name FROM users WHERE status = 'Active'")
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
def service_delete(record_id):
    try:
        query_db("DELETE FROM service_records WHERE id = %s", (record_id,), commit=True)
        flash("Work order deleted successfully.", "info")
    except Exception as e:
        flash(f"Failed to delete service record: {str(e)}", "danger")
    return redirect(url_for('services_list'))

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
    status = request.args.get('status', '').strip()

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

        if quantity <= 0:
            status = 'Out of Stock'
        elif quantity <= min_quantity:
            status = 'Low Stock'
        else:
            status = 'In Stock'

        try:
            query_db("""
                INSERT INTO spare_parts 
                (part_number, part_name, category, quantity, min_quantity, unit_price, cost_price, shelf_location, supplier, compatibility, status, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (part_number, part_name, category, quantity, min_quantity, unit_price, cost_price, shelf_location, supplier, compatibility, status, description), commit=True)
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

        if quantity <= 0:
            status = 'Out of Stock'
        elif quantity <= min_quantity:
            status = 'Low Stock'
        else:
            status = 'In Stock'

        try:
            query_db("""
                UPDATE spare_parts
                SET part_number=%s, part_name=%s, category=%s, quantity=%s, min_quantity=%s,
                    unit_price=%s, cost_price=%s, shelf_location=%s, supplier=%s,
                    compatibility=%s, status=%s, description=%s
                WHERE id = %s
            """, (part_number, part_name, category, quantity, min_quantity, unit_price, cost_price, shelf_location, supplier, compatibility, status, description, part_id), commit=True)
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

@app.route('/parts/requests/<int:request_id>/update', methods=['POST'])
@login_required
@parts_required
def parts_request_update(request_id):
    """Updates request status (Part Available, Not Available, Pending, etc.) and triggers real-time technician notification."""
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

    new_status = request.form.get('status', 'Pending')
    quantity_available = max(0, parse_int_field(request.form.get('quantity_available'), 0))
    parts_dept_notes = request.form.get('parts_dept_notes', '').strip()
    deduct_stock = request.form.get('deduct_stock') == 'yes'

    try:
        query_db("""
            UPDATE part_requests
            SET status = %s, quantity_available = %s, parts_dept_notes = %s,
                fulfilled_at = CASE WHEN %s = 'Part Available' THEN NOW() ELSE fulfilled_at END
            WHERE id = %s
        """, (new_status, quantity_available, parts_dept_notes, new_status, request_id), commit=True)

        # Deduct from warehouse inventory catalog if requested and part exists
        if deduct_stock and req['part_id'] and quantity_available > 0:
            part = query_db("SELECT quantity, min_quantity FROM spare_parts WHERE id = %s", (req['part_id'],), one=True)
            if part:
                new_q = max(0, part['quantity'] - quantity_available)
                new_st = 'Out of Stock' if new_q <= 0 else ('Low Stock' if new_q <= part['min_quantity'] else 'In Stock')
                query_db("UPDATE spare_parts SET quantity = %s, status = %s WHERE id = %s", (new_q, new_st, req['part_id']), commit=True)

        recipient_id = req['requested_by'] or req['assigned_tech_id']

        if new_status == 'Part Available' and recipient_id:
            notif_title = f"Part Ready: {req['part_name']}"
            notif_msg = f"{quantity_available} unit(s) of '{req['part_name']}' is now available at the parts counter for Work Order {req['invoice_number']} ({req['plate_number']}). {parts_dept_notes}".strip()
            query_db("""
                INSERT INTO notifications (user_id, title, message, link, type, is_read)
                VALUES (%s, %s, %s, %s, 'part_available', 0)
            """, (recipient_id, notif_title, notif_msg, url_for('technician_parts_requests')), commit=True)
            flash(f"Request #REQ-{request_id} marked as 'Part Available'. In-app notification delivered to technician.", "success")
        elif new_status == 'Not Available' and recipient_id:
            notif_title = f"Part Unavailable: {req['part_name']}"
            notif_msg = f"'{req['part_name']}' for Work Order {req['invoice_number']} is currently out of stock / backordered. {parts_dept_notes}".strip()
            query_db("""
                INSERT INTO notifications (user_id, title, message, link, type, is_read)
                VALUES (%s, %s, %s, %s, 'part_unavailable', 0)
            """, (recipient_id, notif_title, notif_msg, url_for('technician_parts_requests')), commit=True)
            flash(f"Request #REQ-{request_id} marked as 'Not Available'. Notification sent to technician.", "warning")
        else:
            flash(f"Request #REQ-{request_id} status updated to '{new_status}'.", "info")

    except Exception as e:
        flash(f"Failed to update request: {str(e)}", "danger")

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
