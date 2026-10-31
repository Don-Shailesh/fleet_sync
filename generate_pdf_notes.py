#!/usr/bin/env python3
"""
Generate a professional PDF document:
'FleetSync_Project_Documentation_and_Notes.pdf'
"""

import os
import sys
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

# -------------------------------------------------------------
# Numbered Canvas for "Page X of Y" and Running Header/Footer
# -------------------------------------------------------------
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Skip running header on first page
        if self._pageNumber > 1:
            self.drawString(40, 810, "FleetSync Enterprise — Project Technical Notes & Database Guide")
            self.drawRightString(555, 810, "Vehicle Maintenance System")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.75)
            self.line(40, 804, 555, 804)

        # Footer on all pages
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(555, 30, page_str)
        self.drawString(40, 30, "Confidential — FleetSync Engineering Documentation & Internship Guide")
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.75)
        self.line(40, 42, 555, 42)

        self.restoreState()


def create_notes_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=50,
        bottomMargin=50
    )

    styles = getSampleStyleSheet()

    # Custom Palette
    c_primary = colors.HexColor("#0F172A")    # Slate 900
    c_brand = colors.HexColor("#1D4ED8")      # Blue 700
    c_brand_dark = colors.HexColor("#1E3A8A") # Blue 900
    c_secondary = colors.HexColor("#334155")  # Slate 700
    c_muted = colors.HexColor("#64748B")      # Slate 500
    c_bg_light = colors.HexColor("#F8FAFC")   # Slate 50
    c_code_bg = colors.HexColor("#F1F5F9")    # Slate 100
    c_border = colors.HexColor("#CBD5E1")     # Slate 300
    c_accent = colors.HexColor("#0D9488")     # Teal 600

    # Typography styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=c_brand_dark,
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=c_muted,
        spaceAfter=15
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=c_brand,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=c_primary,
        spaceBefore=10,
        spaceAfter=6,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=c_secondary,
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4
    )

    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#0F172A")
    )

    note_style = ParagraphStyle(
        'Note_Custom',
        parent=body_style,
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1E293B")
    )

    th_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white
    )

    td_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=c_secondary
    )

    story = []

    # -------------------------------------------------------------
    # Cover / Header Banner
    # -------------------------------------------------------------
    story.append(Paragraph("FleetSync Enterprise", title_style))
    story.append(Paragraph("Vehicle Service & Maintenance Tracker — Comprehensive Engineering Notes", subtitle_style))

    # Meta banner box
    meta_data = [
        [
            Paragraph("<b>Author / Role:</b> Engineering & Internship Team", td_style),
            Paragraph("<b>Backend:</b> Python 3.10+ & Flask", td_style),
            Paragraph("<b>Database:</b> MySQL 8.0 (XAMPP)", td_style)
        ],
        [
            Paragraph("<b>Document Version:</b> 1.0 (Comprehensive)", td_style),
            Paragraph("<b>Local Server:</b> http://127.0.0.1:5000", td_style),
            Paragraph("<b>Target Audience:</b> Developers / Interns", td_style)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[170, 170, 175])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_bg_light),
        ('BOX', (0,0), (-1,-1), 1, c_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, c_border),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 14))

    # -------------------------------------------------------------
    # SECTION 1: Project Overview
    # -------------------------------------------------------------
    story.append(Paragraph("1. Executive Project Overview", h1_style))
    story.append(Paragraph(
        "<b>FleetSync</b> is an enterprise web application designed for automotive service centers, dealerships, "
        "and fleet maintenance managers. It replaces manual paperwork with a centralized digital dashboard tracking "
        "vehicles, corporate customers, scheduled maintenance intervals, repair work orders, and billing invoices.",
        body_style
    ))
    story.append(Paragraph("<b>Core Capabilities:</b>", body_style))
    story.append(Paragraph("• <b>Fleet & Vehicle Inventory:</b> Records VIN, registration plate, odometer, fuel type, engine specs, and vehicle photos.", bullet_style))
    story.append(Paragraph("• <b>Maintenance Interval Engine:</b> Calculates dynamic due dates based on kilometer intervals and months elapsed; flags 'Due Soon' and 'Overdue' statuses.", bullet_style))
    story.append(Paragraph("• <b>Work Orders & Service Records:</b> Multi-item repair invoices detailing individual parts, labor hours, technician assignment, tax calculations, and status transitions.", bullet_style))
    story.append(Paragraph("• <b>Role-Based Access Control:</b> Strict separation between Administrators (financial reports, system setup) and Technicians (work order execution).", bullet_style))
    story.append(Paragraph("• <b>Automated Reminders:</b> Notifications queue for upcoming or overdue services.", bullet_style))
    story.append(Spacer(1, 10))

    # -------------------------------------------------------------
    # SECTION 2: Architecture & Data Flow
    # -------------------------------------------------------------
    story.append(Paragraph("2. System Architecture & Request Lifecycle", h1_style))
    story.append(Paragraph(
        "The application follows a clean <b>Model-View-Controller (MVC)</b> architectural pattern using Python Flask:",
        body_style
    ))

    arch_data = [
        [Paragraph("Layer", th_style), Paragraph("Component", th_style), Paragraph("Role & Responsibilities", th_style)],
        [
            Paragraph("<b>Presentation (Client)</b>", td_style),
            Paragraph("Web Browser (Chrome/Edge)", td_style),
            Paragraph("Renders responsive HTML5/CSS3, executes client-side charts (Chart.js) and triggers AJAX API requests.", td_style)
        ],
        [
            Paragraph("<b>Routing & Controller</b>", td_style),
            Paragraph("Flask App (<code>app.py</code>)", td_style),
            Paragraph("Parses HTTP GET/POST requests, enforces authentication/session guards, invokes business logic, and renders Jinja2 templates.", td_style)
        ],
        [
            Paragraph("<b>Data Access Layer</b>", td_style),
            Paragraph("DB Helper (<code>db.py</code>)", td_style),
            Paragraph("Manages MySQL connections, executes safe parameterized queries, returns dictionary records, and handles commits/rollbacks.", td_style)
        ],
        [
            Paragraph("<b>Storage Layer</b>", td_style),
            Paragraph("MySQL Server (XAMPP)", td_style),
            Paragraph("Listens on Port 3306; maintains ACID relational integrity across 7 normalized database tables.", td_style)
        ],
    ]
    arch_table = Table(arch_data, colWidths=[110, 120, 285])
    arch_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_brand),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOX', (0,0), (-1,-1), 1, c_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, c_border),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_bg_light]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(arch_table)
    story.append(Spacer(1, 14))

    # -------------------------------------------------------------
    # SECTION 3: Networking & URL Explanation
    # -------------------------------------------------------------
    story.append(Paragraph("3. Demystifying 'http://127.0.0.1:5000'", h1_style))
    story.append(Paragraph(
        "A common point of confusion for new developers is understanding the URL used to access local applications. "
        "Every local development address consists of three distinct elements:",
        body_style
    ))

    url_data = [
        [Paragraph("URL Element", th_style), Paragraph("Technical Meaning", th_style), Paragraph("Real-World Analogy", th_style)],
        [
            Paragraph("<b><code>http://</code></b>", td_style),
            Paragraph("<b>HyperText Transfer Protocol:</b> The communication rules governing how browsers request and receive web documents.", td_style),
            Paragraph("The agreed language (e.g. English) used between two people talking.", td_style)
        ],
        [
            Paragraph("<b><code>127.0.0.1</code></b><br/>(or <code>localhost</code>)", td_style),
            Paragraph("<b>Loopback IP Address:</b> A globally reserved network address pointing exclusively to <i>this exact physical computer</i>. Data packets never leave the machine.", td_style),
            Paragraph("The street address of the building you are currently standing inside.", td_style)
        ],
        [
            Paragraph("<b><code>:5000</code></b>", td_style),
            Paragraph("<b>Port Number:</b> A virtual channel (1-65535) allocated to a specific running software process. Flask listens on port 5000 by default.", td_style),
            Paragraph("The specific apartment or room door number inside that building.", td_style)
        ]
    ]
    url_table = Table(url_data, colWidths=[90, 220, 205])
    url_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_brand_dark),
        ('BOX', (0,0), (-1,-1), 1, c_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, c_border),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_bg_light]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(url_table)
    story.append(Spacer(1, 8))

    story.append(Paragraph(
        "<b>Port Distinction in this Project:</b><br/>"
        "• <b>Port 5000:</b> Handled by Python/Flask (delivers the web pages).<br/>"
        "• <b>Port 3306:</b> Handled by MySQL in XAMPP (delivers the database queries).",
        body_style
    ))
    story.append(Spacer(1, 10))

    # -------------------------------------------------------------
    # SECTION 4: Database Architecture & Setup
    # -------------------------------------------------------------
    story.append(PageBreak()) # Clean page break for technical deep dive
    story.append(Paragraph("4. Database Architecture & Schema Design", h1_style))
    story.append(Paragraph(
        "The system uses a relational database schema named <code>fleetsync_db</code>, running on MySQL. "
        "The schema guarantees data integrity via foreign keys, cascading constraints, and indexed identifiers.",
        body_style
    ))

    schema_data = [
        [Paragraph("Table Name", th_style), Paragraph("Primary Key & Foreign Keys", th_style), Paragraph("Purpose & Key Attributes", th_style)],
        [
            Paragraph("<code>users</code>", td_style),
            Paragraph("<code>id</code> (PK)", td_style),
            Paragraph("Staff credentials, name, email, hashed password (bcrypt), role ('Admin', 'Technician').", td_style)
        ],
        [
            Paragraph("<code>customers</code>", td_style),
            Paragraph("<code>id</code> (PK)", td_style),
            Paragraph("Vehicle owners & corporate fleet accounts (name, email, phone, company, address).", td_style)
        ],
        [
            Paragraph("<code>vehicles</code>", td_style),
            Paragraph("<code>id</code> (PK)<br/><code>customer_id</code> &rarr; customers(id)", td_style),
            Paragraph("Vehicle records: VIN, license plate, make, model, year, fuel type, odometer, image path.", td_style)
        ],
        [
            Paragraph("<code>maintenance_schedules</code>", td_style),
            Paragraph("<code>id</code> (PK)<br/><code>vehicle_id</code> &rarr; vehicles(id)", td_style),
            Paragraph("Scheduled services: service type, interval km/months, last performed date, next due date, status.", td_style)
        ],
        [
            Paragraph("<code>service_records</code>", td_style),
            Paragraph("<code>id</code> (PK)<br/><code>vehicle_id</code>, <code>technician_id</code>", td_style),
            Paragraph("Work orders: invoice number, service type, labor cost, parts cost, tax, total, payment status.", td_style)
        ],
        [
            Paragraph("<code>service_items</code>", td_style),
            Paragraph("<code>id</code> (PK)<br/><code>service_record_id</code>", td_style),
            Paragraph("Line items: item description, quantity, unit price, item type ('part' or 'labor').", td_style)
        ],
        [
            Paragraph("<code>reminders</code>", td_style),
            Paragraph("<code>id</code> (PK)<br/><code>vehicle_id</code>, <code>customer_id</code>", td_style),
            Paragraph("Automated alerts queue: reminder type, message, status ('Pending', 'Sent').", td_style)
        ]
    ]
    schema_table = Table(schema_data, colWidths=[120, 140, 255])
    schema_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_brand),
        ('BOX', (0,0), (-1,-1), 1, c_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, c_border),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_bg_light]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(schema_table)
    story.append(Spacer(1, 14))

    # -------------------------------------------------------------
    # SECTION 5: How Flask Connects to Database (Code Deep Dive)
    # -------------------------------------------------------------
    story.append(Paragraph("5. Connecting Flask to MySQL: Step-by-Step Code Analysis", h1_style))
    story.append(Paragraph(
        "The project connects Flask to MySQL through a modular 4-tier pattern. Here is how each module functions:",
        body_style
    ))

    # Step A: config.py
    story.append(Paragraph("Step A: Centralized Configuration (<code>config.py</code>)", h2_style))
    story.append(Paragraph(
        "All database parameters and credentials are abstracted into a single <code>Config</code> class. "
        "This allows seamless environment switching (e.g. Docker, production vs local XAMPP):",
        body_style
    ))
    code_config = (
        "# config.py\n"
        "import os\n"
        "class Config:\n"
        "    SECRET_KEY = os.environ.get('SECRET_KEY', 'fleetsync-secure-key-2026')\n"
        "    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')\n"
        "    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))\n"
        "    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')\n"
        "    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')  # XAMPP default is empty\n"
        "    MYSQL_DB = os.environ.get('MYSQL_DB', 'fleetsync_db')"
    )
    code_table = Table([[Paragraph(code_config.replace('\n', '<br/>').replace(' ', '&nbsp;'), code_style)]], colWidths=[515])
    code_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_code_bg),
        ('BOX', (0,0), (-1,-1), 1, c_border),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(code_table)
    story.append(Spacer(1, 8))

    # Step B: db.py connection manager
    story.append(Paragraph("Step B: The Database Manager (<code>db.py</code>)", h2_style))
    story.append(Paragraph(
        "Instead of opening raw connections inside individual views, <code>db.py</code> exposes a unified helper "
        "<code>query_db()</code>. This design provides critical engineering benefits:<br/>"
        "1. <b>SQL Injection Prevention:</b> Uses parameterized queries (<code>%s</code> placeholders).<br/>"
        "2. <b>Dictionary Cursors:</b> Columns are returned as Python dictionaries (e.g., <code>row['name']</code>) rather than tuples.<br/>"
        "3. <b>Transaction Safety:</b> Automatically executes <code>conn.commit()</code> for inserts/updates, and <code>conn.rollback()</code> if an exception occurs.<br/>"
        "4. <b>Leak Prevention:</b> Closes cursors and connections inside a <code>finally:</code> block.",
        body_style
    ))

    code_db = (
        "# db.py (Core execution engine)\n"
        "def query_db(query, params=(), one=False, commit=False):\n"
        "    conn = None\n"
        "    cursor = None\n"
        "    try:\n"
        "        conn = get_connection(include_db=True)\n"
        "        cursor = conn.cursor(dictionary=True)   # Dictionary rows\n"
        "        cursor.execute(query, params)          # Safe parameterized binding\n"
        "        if commit:\n"
        "            conn.commit()\n"
        "            return cursor.lastrowid or cursor.rowcount\n"
        "        result = cursor.fetchall()\n"
        "        return (result[0] if result else None) if one else result\n"
        "    except Error as e:\n"
        "        if conn and commit:\n"
        "            conn.rollback()                   # Rollback on failure\n"
        "        raise e\n"
        "    finally:\n"
        "        if cursor: cursor.close()\n"
        "        if conn: conn.close()                 # Connection safely released"
    )
    code_table_db = Table([[Paragraph(code_db.replace('\n', '<br/>').replace(' ', '&nbsp;'), code_style)]], colWidths=[515])
    code_table_db.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_code_bg),
        ('BOX', (0,0), (-1,-1), 1, c_border),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(code_table_db)
    story.append(Spacer(1, 10))

    # Step C: Flask Route Usage
    story.append(PageBreak())
    story.append(Paragraph("Step C: Consuming Data in Flask Routes (<code>app.py</code>)", h2_style))
    story.append(Paragraph(
        "Flask routes call <code>query_db()</code> to fetch or update data, then pass results into Jinja2 templates. "
        "Here are two real examples from the codebase:",
        body_style
    ))

    code_flask = (
        "# Example 1: Secure Login Verification (app.py)\n"
        "@app.route('/login', methods=['GET', 'POST'])\n"
        "def login():\n"
        "    if request.method == 'POST':\n"
        "        email = request.form.get('email', '').strip()\n"
        "        password = request.form.get('password', '')\n"
        "        # Parameterized query protects against SQL injection\n"
        "        user = query_db('SELECT * FROM users WHERE email = %s', (email,), one=True)\n"
        "        if user and check_password_hash(user['password_hash'], password):\n"
        "            session['user_id'] = user['id']\n"
        "            return redirect(url_for('dashboard'))\n"
        "        flash('Invalid email or password', 'danger')\n"
        "    return render_template('auth/login.html')\n\n"
        "# Example 2: Creating a Vehicle Record with Auto-Commit (app.py)\n"
        "@app.route('/vehicles/new', methods=['POST'])\n"
        "@login_required\n"
        "def vehicles_create():\n"
        "    new_id = query_db('''\n"
        "        INSERT INTO vehicles (customer_id, vin, license_plate, make, model, year, odometer)\n"
        "        VALUES (%s, %s, %s, %s, %s, %s, %s)\n"
        "    ''', (customer_id, vin, plate, make, model, year, odometer), commit=True)\n"
        "    flash('Vehicle successfully registered!', 'success')\n"
        "    return redirect(url_for('vehicle_detail', vehicle_id=new_id))"
    )
    code_table_flask = Table([[Paragraph(code_flask.replace('\n', '<br/>').replace(' ', '&nbsp;'), code_style)]], colWidths=[515])
    code_table_flask.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_code_bg),
        ('BOX', (0,0), (-1,-1), 1, c_border),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(code_table_flask)
    story.append(Spacer(1, 8))

    # Step D: Context Processor
    story.append(Paragraph("Step D: Global State Injection (Context Processors)", h2_style))
    story.append(Paragraph(
        "Flask's <code>@app.context_processor</code> runs before any template renders. It queries the database "
        "to inject common variables (such as the logged-in user profile and overdue reminder badges) into every template automatically, "
        "without needing to pass them manually in every <code>render_template()</code> call.",
        body_style
    ))
    story.append(Spacer(1, 10))

    # -------------------------------------------------------------
    # SECTION 6: Manual Setup & Execution Guide
    # -------------------------------------------------------------
    story.append(Paragraph("6. Step-by-Step Manual Execution Guide (Windows)", h1_style))
    story.append(Paragraph(
        "Whenever you start working on this project, follow this 5-step operational workflow:",
        body_style
    ))

    steps_data = [
        [Paragraph("Step", th_style), Paragraph("Action", th_style), Paragraph("Exact Command / Procedure", th_style)],
        [
            Paragraph("<b>1</b>", td_style),
            Paragraph("<b>Start MySQL</b>", td_style),
            Paragraph("Open <b>XAMPP Control Panel</b> &rarr; Click <b>Start</b> next to MySQL. Ensure port 3306 is highlighted green.", td_style)
        ],
        [
            Paragraph("<b>2</b>", td_style),
            Paragraph("<b>Open Terminal</b>", td_style),
            Paragraph("Open terminal in your editor (<kbd>Ctrl + `</kbd>) and ensure you are in: <code>d:\\internship 2</code>", td_style)
        ],
        [
            Paragraph("<b>3</b>", td_style),
            Paragraph("<b>Init Database</b><br/><i>(Once only)</i>", td_style),
            Paragraph("Run: <code>python setup_db.py</code><br/>Creates database, executes <code>schema.sql</code>, and seeds demo records.", td_style)
        ],
        [
            Paragraph("<b>4</b>", td_style),
            Paragraph("<b>Launch Flask</b>", td_style),
            Paragraph("Run: <code>python app.py</code><br/>Keep this terminal active! Do not close it while using the website.", td_style)
        ],
        [
            Paragraph("<b>5</b>", td_style),
            Paragraph("<b>Access in Browser</b>", td_style),
            Paragraph("Navigate to: <b><code>http://127.0.0.1:5000</code></b><br/>Login with <code>admin@fleetsync.io</code> / <code>Admin@123</code>", td_style)
        ]
    ]
    steps_table = Table(steps_data, colWidths=[45, 120, 350])
    steps_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_brand),
        ('BOX', (0,0), (-1,-1), 1, c_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, c_border),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_bg_light]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(steps_table)
    story.append(Spacer(1, 14))

    # -------------------------------------------------------------
    # SECTION 7: Troubleshooting Cheatsheet
    # -------------------------------------------------------------
    story.append(Paragraph("7. Troubleshooting & Common Gotchas", h1_style))
    trouble_data = [
        [Paragraph("Symptom", th_style), Paragraph("Root Cause", th_style), Paragraph("Resolution", th_style)],
        [
            Paragraph("<b>Site Can't Be Reached</b>", td_style),
            Paragraph("Flask web server is not running.", td_style),
            Paragraph("Run <code>python app.py</code> in terminal and leave it running.", td_style)
        ],
        [
            Paragraph("<b>Can't connect to MySQL server</b>", td_style),
            Paragraph("XAMPP MySQL service is stopped or port 3306 blocked.", td_style),
            Paragraph("Open XAMPP Control Panel & click Start next to MySQL.", td_style)
        ],
        [
            Paragraph("<b>Database 'fleetsync_db' does not exist</b>", td_style),
            Paragraph("Schema has not been seeded yet.", td_style),
            Paragraph("Run <code>python setup_db.py</code> once in terminal.", td_style)
        ],
        [
            Paragraph("<b>Address already in use (Port 5000)</b>", td_style),
            Paragraph("A previous Flask instance is still running in background.", td_style),
            Paragraph("Kill port 5000 via PowerShell: <code>Stop-Process -Id (Get-NetTCPConnection -LocalPort 5000).OwningProcess</code>", td_style)
        ]
    ]
    trouble_table = Table(trouble_data, colWidths=[120, 160, 235])
    trouble_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_brand_dark),
        ('BOX', (0,0), (-1,-1), 1, c_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, c_border),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_bg_light]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(trouble_table)

    # Build document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[SUCCESS] PDF successfully created at: {output_path}")

if __name__ == '__main__':
    target = os.path.join(os.path.dirname(__file__), 'FleetSync_Project_Documentation_and_Notes.pdf')
    create_notes_pdf(target)
