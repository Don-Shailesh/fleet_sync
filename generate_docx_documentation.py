import os
import sys
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, hex_color):
    """Set background color of a table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Set inner padding for a table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
    tcPr.append(tcMar)

def set_table_borders(table, color="D1D5DB", sz="4", val="single"):
    """Set subtle light gray borders for the entire table."""
    tblPr = table._tbl.tblPr
    borders = parse_xml(f'<w:tblBorders {nsdecls("w")}><w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/><w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/><w:insideH w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/><w:insideV w:val="none"/><w:left w:val="none"/><w:right w:val="none"/></w:tblBorders>')
    tblPr.append(borders)

def style_heading(p, text, font_size, color_rgb, bold=True, space_before=14, space_after=6):
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = "Arial"
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = color_rgb
    return run

def add_body_p(doc, text="", bold_prefix="", space_after=6, italic=False):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.15
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.font.name = "Arial"
        r_pre.font.size = Pt(10)
        r_pre.font.bold = True
        r_pre.font.color.rgb = RGBColor(15, 23, 42)
    if text:
        r = p.add_run(text)
        r.font.name = "Arial"
        r.font.size = Pt(10)
        r.font.italic = italic
        r.font.color.rgb = RGBColor(51, 65, 85)
    return p

def add_bullet_p(doc, bold_prefix="", text=""):
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.15
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.font.name = "Arial"
        r_pre.font.size = Pt(9.5)
        r_pre.font.bold = True
        r_pre.font.color.rgb = RGBColor(30, 41, 59)
    if text:
        r = p.add_run(text)
        r.font.name = "Arial"
        r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor(71, 85, 105)
    return p

def create_styled_table(doc, headers, data, col_widths=None):
    table = doc.add_table(rows=len(data) + 1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table)

    # Style Header Row
    hdr_cells = table.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].text = title
        set_cell_background(hdr_cells[i], "1E3A8A") # Navy Blue
        set_cell_margins(hdr_cells[i], top=120, bottom=120, left=150, right=150)
        hdr_cells[i].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for r in p.runs:
            r.font.name = "Arial"
            r.font.size = Pt(9)
            r.font.bold = True
            r.font.color.rgb = RGBColor(255, 255, 255)

    # Style Data Rows
    for r_idx, row_data in enumerate(data):
        row_cells = table.rows[r_idx + 1].cells
        bg_color = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(row_data):
            row_cells[c_idx].text = str(val)
            set_cell_background(row_cells[c_idx], bg_color)
            set_cell_margins(row_cells[c_idx], top=90, bottom=90, left=150, right=150)
            row_cells[c_idx].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = row_cells[c_idx].paragraphs[0]
            for r in p.runs:
                r.font.name = "Arial"
                r.font.size = Pt(8.5)
                r.font.color.rgb = RGBColor(51, 65, 85)

    if col_widths:
        for row in table.rows:
            for i, w in enumerate(col_widths):
                row.cells[i].width = Inches(w)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)
    return table

def generate_documentation_docx(filename="FleetSync_Project_Documentation.docx"):
    doc = Document()

    # Set Margins (1 inch all around)
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

        # Header / Footer
        header = section.header
        hp = header.paragraphs[0]
        hp.text = "FleetSync™ Enterprise — Vehicle Service & Fleet Maintenance Tracker"
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        hp.runs[0].font.name = "Arial"
        hp.runs[0].font.size = Pt(8)
        hp.runs[0].font.color.rgb = RGBColor(148, 163, 184)

        footer = section.footer
        fp = footer.paragraphs[0]
        fp.text = "Confidential — Engineering Documentation & Technical Report  |  Lead Developer: Shailesh Dongare"
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        fp.runs[0].font.name = "Arial"
        fp.runs[0].font.size = Pt(8)
        fp.runs[0].font.color.rgb = RGBColor(148, 163, 184)

    # -------------------------------------------------------------
    # COVER / TITLE SECTION
    # -------------------------------------------------------------
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(36)
    title_p.paragraph_format.space_after = Pt(8)
    r_title = title_p.add_run("FleetSync™ Enterprise")
    r_title.font.name = "Arial"
    r_title.font.size = Pt(28)
    r_title.font.bold = True
    r_title.font.color.rgb = RGBColor(30, 58, 138) # Deep Navy

    sub_p = doc.add_paragraph()
    sub_p.paragraph_format.space_after = Pt(16)
    r_sub = sub_p.add_run("Vehicle Service & Maintenance Management System\nComprehensive Technical Documentation & Internship Report")
    r_sub.font.name = "Arial"
    r_sub.font.size = Pt(13)
    r_sub.font.color.rgb = RGBColor(71, 85, 105)

    # Metadata callout box table
    meta_table = doc.add_table(rows=4, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(meta_table, color="93C5FD", sz="8")
    meta_data = [
        ("Lead Developer / Author", "Shailesh Dongare (Full Stack Python Developer)"),
        ("Technology Stack", "Python 3.14 | Flask 3.1 | MySQL 8.x (XAMPP) | Bootstrap 5.3"),
        ("System Architecture", "Model-View-Controller (MVC) with Parameterized Query Engine"),
        ("Document Version / Date", "Version 2.0 (Indian Localization Edition) | October 2026")
    ]
    for idx, (label, val) in enumerate(meta_data):
        r0 = meta_table.rows[idx].cells[0]
        r1 = meta_table.rows[idx].cells[1]
        r0.text = label
        r1.text = val
        set_cell_background(r0, "EFF6FF")
        set_cell_background(r1, "F8FAFC")
        set_cell_margins(r0, 80, 80, 120, 120)
        set_cell_margins(r1, 80, 80, 120, 120)
        r0.paragraphs[0].runs[0].font.bold = True
        r0.paragraphs[0].runs[0].font.size = Pt(9.5)
        r0.paragraphs[0].runs[0].font.color.rgb = RGBColor(30, 58, 138)
        r1.paragraphs[0].runs[0].font.size = Pt(9.5)
        r1.paragraphs[0].runs[0].font.color.rgb = RGBColor(30, 41, 59)
        r0.width = Inches(2.2)
        r1.width = Inches(4.3)

    doc.add_page_break()

    # -------------------------------------------------------------
    # 1. EXECUTIVE SUMMARY & PROBLEM STATEMENT
    # -------------------------------------------------------------
    style_heading(doc.add_paragraph(), "1. Executive Summary & Problem Statement", 16, RGBColor(30, 58, 138))

    add_body_p(doc,
        "Modern automotive repair workshops, authorized service centers, and commercial fleet operators face significant "
        "operational bottlenecks when tracking preventative maintenance, recording itemized billing, and ensuring customer "
        "retention. Conventional reliance on disparate spreadsheets or handwritten job cards leads to missed maintenance "
        "windows, critical engine and brake failures, inaccurate parts cost tracking, and revenue leakage.",
        bold_prefix="Background: "
    )
    add_body_p(doc,
        "FleetSync™ is an enterprise web-based vehicle service lifecycle management platform designed to automate end-to-end "
        "workshop operations. Built upon high-performance Python Flask and MySQL, FleetSync delivers real-time operations telemetry, "
        "automated OEM preventive maintenance interval countdowns, dynamic parts-and-labor invoicing in Indian Rupees (₹), "
        "and multi-channel customer reminder dispatches.",
        bold_prefix="The Solution: "
    )

    add_body_p(doc, bold_prefix="Key Value Propositions:")
    add_bullet_p(doc, "Zero Missed Services: ", "Dual-trigger OEM maintenance logic continuously computes due status using both elapsed calendar days and accumulated odometer mileage.")
    add_bullet_p(doc, "Itemized Accurate Billing: ", "Interactive line-item calculator for parts, materials, technician labor hours, and statutory tax (8%), with real-time browser calculation.")
    add_bullet_p(doc, "Multi-Tenant & Role Security: ", "Strict cryptographic authentication with scrypt password hashing separating System Administrators from Workshop Service Technicians.")
    add_bullet_p(doc, "Localized for Indian Fleets: ", "Full Indian currency localization (₹ INR), regional customer corporate profiles, and popular commercial fleet vehicles (Tata Winger, Force Traveller, Mahindra Bolero, Innova HyCross).")

    # -------------------------------------------------------------
    # 2. SYSTEM ARCHITECTURE & TECHNICAL SPECIFICATION
    # -------------------------------------------------------------
    style_heading(doc.add_paragraph(), "2. System Architecture & Tech Stack", 16, RGBColor(30, 58, 138))

    add_body_p(doc,
        "FleetSync adheres strictly to the classic Model-View-Controller (MVC) software architectural pattern, "
        "ensuring clean separation of concerns, high maintainability, and rapid feature extensibility:"
    )

    add_bullet_p(doc, "Model Layer (db.py & config.py): ", "Encapsulates direct MySQL database connections via mysql-connector-python. Implements centralized connection management, parameterized SQL execution with automatic rollback on failure, and automated database health diagnostic checks.")
    add_bullet_p(doc, "Controller Layer (app.py): ", "Houses modular REST-like route handlers, authentication guards (@login_required, @admin_required), context processors for global data injection, template filters, and business validation rules.")
    add_bullet_p(doc, "View Layer (Jinja2 & Bootstrap 5.3): ", "Responsive SaaS frontend styled with modern typography (Plus Jakarta Sans), FontAwesome 6 icons, SweetAlert2 modal dialogs, and Chart.js dynamic telematics charts.")

    style_heading(doc.add_paragraph(), "Technology Stack Breakdown", 12, RGBColor(15, 23, 42))

    tech_headers = ["Layer", "Technology", "Version", "Role / Implementation Purpose"]
    tech_data = [
        ["Backend Core", "Python", "3.14 / 3.10+", "Primary runtime environment and business logic execution"],
        ["Web Framework", "Flask", "3.1.x", "Lightweight WSGI routing, HTTP sessions, and template rendering engine"],
        ["Database", "MySQL / MariaDB", "8.x / 10.4 (XAMPP)", "ACID-compliant relational storage with strict foreign keys & cascade constraints"],
        ["Database Driver", "mysql-connector-python", "9.x", "Native pure-Python database driver supporting connection pooling & parameterization"],
        ["Security / Hashing", "Werkzeug Security", "3.1.x", "scrypt key derivation function for enterprise credential encryption"],
        ["Frontend UI", "Bootstrap", "5.3.3", "Responsive grid system, modal overlays, off-canvas navigation, and utility classes"],
        ["Data Visualization", "Chart.js", "4.4.x", "Dynamic HTML5 Canvas charting for fleet status breakdown and revenue analytics"],
        ["Icons & Visuals", "FontAwesome & AOS", "6.5.1 / 2.3", "Automotive vector iconography and fluid entrance scroll animations"]
    ]
    create_styled_table(doc, tech_headers, tech_data, [1.1, 1.3, 1.0, 3.1])

    # -------------------------------------------------------------
    # 3. CORE SYSTEM MODULES
    # -------------------------------------------------------------
    style_heading(doc.add_paragraph(), "3. Core Functional Modules", 16, RGBColor(30, 58, 138))

    style_heading(doc.add_paragraph(), "3.1 Operations Command Center (Dashboard)", 12, RGBColor(15, 23, 42))
    add_body_p(doc,
        "The Command Center serves as the primary operational telemetry dashboard for service managers and shop supervisors. "
        "It provides real-time visibility into key performance indicators (KPIs) calculated directly from relational tables on every request:"
    )
    add_bullet_p(doc, "Active Fleet Asset Count: ", "Total registered vehicles actively serviced by the maintenance center.")
    add_bullet_p(doc, "Workshop Bay Occupancy: ", "Count of work orders currently marked 'In Progress' or 'Waiting for Parts'.")
    add_bullet_p(doc, "Due & Overdue Counter: ", "Immediate count of vehicles requiring urgent preventative attention based on dynamic date and mileage thresholds.")
    add_bullet_p(doc, "Cumulative Revenue Metric: ", "Total billed and realized service revenue formatted in Indian Rupees (₹).")
    add_bullet_p(doc, "Urgent Alert Banner: ", "A reactive notification surface highlighting vehicles whose service intervals have elapsed, offering one-click work order dispatch.")

    style_heading(doc.add_paragraph(), "3.2 360° Fleet & Customer Asset Management", 12, RGBColor(15, 23, 42))
    add_body_p(doc,
        "The Fleet module provides unified lifecycle tracking for all client assets. Each vehicle record includes 17-character VIN, "
        "registration plate number, make, model, manufacturing year, fuel type (Diesel, Petrol, Hybrid, Electric, CNG), body configuration, "
        "odometer reading, and high-resolution vehicle imagery. Vehicles are linked via foreign keys to either corporate fleet accounts or individual clients."
    )

    style_heading(doc.add_paragraph(), "3.3 Preventive Maintenance Dual-Trigger Automation Engine", 12, RGBColor(15, 23, 42))
    add_body_p(doc,
        "Unlike basic reminders that rely solely on static dates, FleetSync implements a dual-trigger algorithm simulating OEM factory intervals. "
        "A service status is dynamically categorized into one of three operational states:"
    )
    add_bullet_p(doc, "Upcoming: ", "Vehicle is within normal operational window (> 14 days and > 1,000 km until next interval).")
    add_bullet_p(doc, "Due Soon: ", "Vehicle is within 14 calendar days of next_due_date OR within 1,000 km of next_due_odometer.")
    add_bullet_p(doc, "Overdue: ", "Current date exceeds next_due_date OR current odometer exceeds next_due_odometer. Triggers immediate high-priority alerts across the system.")

    style_heading(doc.add_paragraph(), "3.4 Work Orders & Itemized Billing Engine (₹ INR)", 12, RGBColor(15, 23, 42))
    add_body_p(doc,
        "Work orders represent the billable service job card. Each record features standardized identifiers (e.g. WO-2026-0101), "
        "technician assignment, odometer log, description of work, and detailed technician diagnostic notes. "
        "The billing calculation engine supports dynamic line-items for Parts, Labor hours, Inspections, and Miscellaneous fees. "
        "An in-browser JavaScript engine dynamically recalculates sub-totals, computes 8% statutory tax, and renders print-ready commercial tax invoices."
    )

    style_heading(doc.add_paragraph(), "3.5 Customer Outreach & Reminders Hub", 12, RGBColor(15, 23, 42))
    add_body_p(doc,
        "The Reminders engine provides multi-channel customer engagement via Email, SMS, and WhatsApp previews. "
        "Service advisors can trigger an automated background scan that audits all maintenance schedules, identifies due vehicles, "
        "and stages customized communication payloads with timestamps and delivery audit trails."
    )

    doc.add_page_break()

    # -------------------------------------------------------------
    # 4. DATABASE ARCHITECTURE & SCHEMA SPECIFICATION
    # -------------------------------------------------------------
    style_heading(doc.add_paragraph(), "4. Database Architecture & Relational Schema", 16, RGBColor(30, 58, 138))

    add_body_p(doc,
        "The FleetSync database (fleetsync_db) consists of 7 normalized relational tables enforcing referential integrity "
        "via foreign key constraints, cascading deletions, and indexed lookups for high query performance:"
    )

    # 4.1 Users Table
    style_heading(doc.add_paragraph(), "Table 1: users (Authentication & Staff Profiles)", 11, RGBColor(15, 23, 42))
    user_headers = ["Field Name", "Data Type", "Constraints", "Description"]
    user_data = [
        ["id", "INT", "PRIMARY KEY, AUTO_INCREMENT", "Unique internal user identifier"],
        ["name", "VARCHAR(100)", "NOT NULL", "Full staff name (e.g. Shailesh Dongare)"],
        ["email", "VARCHAR(150)", "NOT NULL, UNIQUE", "Login email address"],
        ["password_hash", "VARCHAR(255)", "NOT NULL", "scrypt-hashed secure password"],
        ["role", "ENUM", "NOT NULL, DEFAULT 'Technician'", "'Admin' or 'Technician' access level"],
        ["phone", "VARCHAR(30)", "NULL", "Contact phone number"],
        ["avatar", "VARCHAR(255)", "NULL", "Profile picture URL"],
        ["status", "ENUM", "DEFAULT 'Active'", "'Active' or 'Inactive' account status"],
        ["created_at", "TIMESTAMP", "DEFAULT CURRENT_TIMESTAMP", "Record creation timestamp"]
    ]
    create_styled_table(doc, user_headers, user_data, [1.2, 1.4, 1.8, 2.1])

    # 4.2 Customers Table
    style_heading(doc.add_paragraph(), "Table 2: customers (Fleet Accounts & Individual Clients)", 11, RGBColor(15, 23, 42))
    cust_headers = ["Field Name", "Data Type", "Constraints", "Description"]
    cust_data = [
        ["id", "INT", "PRIMARY KEY, AUTO_INCREMENT", "Unique customer identifier"],
        ["name", "VARCHAR(120)", "NOT NULL, INDEXED", "Primary contact person name"],
        ["email", "VARCHAR(150)", "NOT NULL, INDEXED", "Customer communication email"],
        ["phone", "VARCHAR(30)", "NOT NULL", "Primary mobile / contact number"],
        ["company_name", "VARCHAR(150)", "NULL", "Corporate organization or fleet entity name"],
        ["customer_type", "ENUM", "DEFAULT 'Individual'", "'Fleet / Corporate' or 'Individual'"],
        ["address", "TEXT", "NULL", "Billing and street address"],
        ["city", "VARCHAR(80)", "NULL", "City location (e.g. Mumbai, New Delhi, Bengaluru)"],
        ["postal_code", "VARCHAR(20)", "NULL", "PIN / Postal code"]
    ]
    create_styled_table(doc, cust_headers, cust_data, [1.2, 1.4, 1.8, 2.1])

    # 4.3 Vehicles Table
    style_heading(doc.add_paragraph(), "Table 3: vehicles (Fleet Assets)", 11, RGBColor(15, 23, 42))
    veh_headers = ["Field Name", "Data Type", "Constraints", "Description"]
    veh_data = [
        ["id", "INT", "PRIMARY KEY, AUTO_INCREMENT", "Internal vehicle asset identifier"],
        ["customer_id", "INT", "FOREIGN KEY (customers.id) ON DELETE CASCADE", "Associated asset owner / organization"],
        ["vin", "VARCHAR(20)", "NOT NULL, UNIQUE, INDEXED", "17-character Vehicle Identification Number"],
        ["plate_number", "VARCHAR(20)", "NOT NULL, UNIQUE, INDEXED", "RTO Registration Plate (e.g. MH-02-CW-8092)"],
        ["make", "VARCHAR(60)", "NOT NULL", "Manufacturer (Tata, Mahindra, Force, Toyota, BMW)"],
        ["model", "VARCHAR(60)", "NOT NULL", "Model name (Winger, Traveller, Bolero, Scorpio-N)"],
        ["year", "INT", "NOT NULL", "Manufacturing model year"],
        ["fuel_type", "ENUM", "DEFAULT 'Gasoline'", "Diesel, Gasoline, Electric, Hybrid, CNG"],
        ["current_odometer", "INT", "NOT NULL, DEFAULT 0", "Current recorded mileage in kilometers"],
        ["status", "ENUM", "DEFAULT 'Active'", "'Active', 'In Service', 'Maintenance Due', 'Out of Service'"]
    ]
    create_styled_table(doc, veh_headers, veh_data, [1.2, 1.4, 1.8, 2.1])

    # 4.4 Maintenance Schedules Table
    style_heading(doc.add_paragraph(), "Table 4: maintenance_schedules (Preventive Service Rules)", 11, RGBColor(15, 23, 42))
    sched_headers = ["Field Name", "Data Type", "Constraints", "Description"]
    sched_data = [
        ["id", "INT", "PRIMARY KEY, AUTO_INCREMENT", "Unique schedule checkpoint identifier"],
        ["vehicle_id", "INT", "FOREIGN KEY (vehicles.id) ON DELETE CASCADE", "Vehicle under maintenance rule"],
        ["service_name", "VARCHAR(120)", "NOT NULL", "Check item (Engine Oil, Brake Pads, DPF Regen)"],
        ["interval_km", "INT", "DEFAULT 5000", "OEM recommended kilometer recurrence interval"],
        ["interval_months", "INT", "DEFAULT 6", "OEM recommended calendar month interval"],
        ["last_service_date", "DATE", "NULL", "Date of last verified service completion"],
        ["next_due_date", "DATE", "NOT NULL, INDEXED", "Calculated upcoming service due date"],
        ["next_due_odometer", "INT", "NOT NULL", "Calculated upcoming service due kilometer mark"],
        ["priority", "ENUM", "DEFAULT 'Medium'", "Low, Medium, High, Critical severity level"],
        ["status", "ENUM", "DEFAULT 'Upcoming', INDEXED", "Upcoming, Due Soon, Overdue, Completed"]
    ]
    create_styled_table(doc, sched_headers, sched_data, [1.2, 1.4, 1.8, 2.1])

    # 4.5 Service Records Table
    style_heading(doc.add_paragraph(), "Table 5: service_records (Work Orders & Invoices)", 11, RGBColor(15, 23, 42))
    sr_headers = ["Field Name", "Data Type", "Constraints", "Description"]
    sr_data = [
        ["id", "INT", "PRIMARY KEY, AUTO_INCREMENT", "Work order internal primary key"],
        ["invoice_number", "VARCHAR(30)", "NOT NULL, UNIQUE, INDEXED", "Standardized invoice number (e.g. WO-2026-0101)"],
        ["vehicle_id", "INT", "FOREIGN KEY (vehicles.id) ON DELETE CASCADE", "Serviced vehicle record"],
        ["user_id", "INT", "FOREIGN KEY (users.id) ON DELETE SET NULL", "Assigned service technician"],
        ["service_date", "DATE", "NOT NULL, INDEXED", "Date service was conducted"],
        ["service_type", "VARCHAR(100)", "NOT NULL", "Category (Preventive, Brake Overhaul, Diagnostics)"],
        ["parts_cost", "DECIMAL(10,2)", "DEFAULT 0.00", "Subtotal of parts and consumables in ₹ INR"],
        ["labor_cost", "DECIMAL(10,2)", "DEFAULT 0.00", "Subtotal of technician labor charges in ₹ INR"],
        ["tax_amount", "DECIMAL(10,2)", "DEFAULT 0.00", "Calculated statutory tax (8%) in ₹ INR"],
        ["total_cost", "DECIMAL(10,2)", "DEFAULT 0.00", "Grand total billed invoice amount in ₹ INR"],
        ["status", "ENUM", "DEFAULT 'In Progress'", "Pending, In Progress, Waiting for Parts, Completed"],
        ["payment_status", "ENUM", "DEFAULT 'Unpaid'", "Unpaid, Partially Paid, Paid"]
    ]
    create_styled_table(doc, sr_headers, sr_data, [1.2, 1.4, 1.8, 2.1])

    # 4.6 Service Items Table
    style_heading(doc.add_paragraph(), "Table 6: service_items (Parts & Labor Line Items)", 11, RGBColor(15, 23, 42))
    item_headers = ["Field Name", "Data Type", "Constraints", "Description"]
    item_data = [
        ["id", "INT", "PRIMARY KEY, AUTO_INCREMENT", "Unique line item identifier"],
        ["service_record_id", "INT", "FOREIGN KEY (service_records.id) ON DELETE CASCADE", "Parent work order job card"],
        ["item_type", "ENUM", "DEFAULT 'Part'", "Part, Labor, Inspection, Fee"],
        ["item_name", "VARCHAR(150)", "NOT NULL", "Item description (e.g. Castrol MAGNATEC 5W-30)"],
        ["quantity", "DECIMAL(8,2)", "DEFAULT 1.00", "Quantity or billed labor hours"],
        ["unit_price", "DECIMAL(10,2)", "DEFAULT 0.00", "Unit price per item / hour in ₹ INR"],
        ["total_price", "DECIMAL(10,2)", "DEFAULT 0.00", "Line total (quantity × unit_price) in ₹ INR"]
    ]
    create_styled_table(doc, item_headers, item_data, [1.2, 1.4, 1.8, 2.1])

    # 4.7 Reminders Table
    style_heading(doc.add_paragraph(), "Table 7: reminders (Automated Communication Log)", 11, RGBColor(15, 23, 42))
    rem_headers = ["Field Name", "Data Type", "Constraints", "Description"]
    rem_data = [
        ["id", "INT", "PRIMARY KEY, AUTO_INCREMENT", "Unique reminder notification ID"],
        ["vehicle_id", "INT", "FOREIGN KEY (vehicles.id) ON DELETE CASCADE", "Vehicle requiring maintenance outreach"],
        ["customer_id", "INT", "FOREIGN KEY (customers.id) ON DELETE CASCADE", "Recipient customer profile"],
        ["reminder_type", "ENUM", "DEFAULT 'Service Due'", "Service Due, Inspection Expiry, General Follow-up"],
        ["channel", "ENUM", "DEFAULT 'Email'", "Email, SMS, WhatsApp, System"],
        ["status", "ENUM", "DEFAULT 'Scheduled'", "Scheduled, Sent, Failed, Cancelled"],
        ["message_preview", "TEXT", "NOT NULL", "Formatted communication payload text"]
    ]
    create_styled_table(doc, rem_headers, rem_data, [1.2, 1.4, 1.8, 2.1])

    doc.add_page_break()

    # -------------------------------------------------------------
    # 5. PRE-SEEDED ENTERPRISE DATA & REGIONAL LOCALIZATION
    # -------------------------------------------------------------
    style_heading(doc.add_paragraph(), "5. Pre-Seeded Enterprise Data (Indian Region)", 16, RGBColor(30, 58, 138))

    add_body_p(doc,
        "To provide an authentic and production-grade demonstration environment, FleetSync includes realistic sample records "
        "customized for Indian automotive operations with Indian names, enterprise logistics firms, and localized vehicle assets:"
    )

    style_heading(doc.add_paragraph(), "Staff Accounts & Access Credentials", 11, RGBColor(15, 23, 42))
    staff_headers = ["Role", "Assigned Name", "Email Address", "Default Password", "Permissions & Privileges"]
    staff_data = [
        ["System Administrator", "Shailesh Dongare", "admin@fleetsync.io", "Admin@123", "Full system access, user management, financial reports, record deletions"],
        ["Service Technician", "Suresh Verma", "tech@fleetsync.io", "Tech@123", "Work order execution, line items logging, odometer updates, inspections"]
    ]
    create_styled_table(doc, staff_headers, staff_data, [1.3, 1.2, 1.3, 1.0, 1.7])

    style_heading(doc.add_paragraph(), "Corporate & Individual Clients", 11, RGBColor(15, 23, 42))
    client_headers = ["Customer Name", "Company / Fleet Entity", "Location / City", "Contact Phone"]
    client_data = [
        ["Ananya Deshmukh", "Apex Logistics India Pvt Ltd", "Andheri East, Mumbai", "+91 98210 12345"],
        ["Rohan Kapoor", "Metro Fast Express Logistics Ltd", "Connaught Place, New Delhi", "+91 98112 34567"],
        ["Pooja Iyer", "Individual Client", "Koramangala, Bengaluru", "+91 98450 98765"],
        ["Vikram Malhotra", "Horizon National Transport Carriers", "Vatva GIDC, Ahmedabad", "+91 98791 43210"],
        ["Arjun Nair", "Individual Client", "Banjara Hills, Hyderabad", "+91 98490 54321"]
    ]
    create_styled_table(doc, client_headers, client_data, [1.4, 2.1, 1.5, 1.5])

    style_heading(doc.add_paragraph(), "Fleet Assets & Indian Vehicle Registrations", 11, RGBColor(15, 23, 42))
    fleet_headers = ["Registration Plate", "Make & Model", "Body Style", "Powertrain", "Operational Status"]
    fleet_data = [
        ["MH-02-CW-8092", "Tata Winger Maxi Van", "Fleet Van", "Diesel", "Active (Mumbai-Pune Courier)"],
        ["MH-02-CW-8093", "Mahindra Bolero Maxi Truck Plus", "Pickup Truck", "Diesel", "Maintenance Due (Brakes)"],
        ["DL-01-AX-4011", "Force Motors Traveller 3350", "Fleet Van", "Diesel", "In Service (30k Service)"],
        ["DL-01-AX-4012", "Force Motors Traveller Cargo", "Fleet Van", "Diesel", "Active (Routine Route)"],
        ["KA-03-MY-9921", "Toyota Innova HyCross", "SUV", "Petrol Hybrid", "Active (VIP Client)"],
        ["KA-03-NB-3301", "BMW 330i Gran Limousine M Sport", "Sedan", "Petrol", "Active (Wheel Alignment)"],
        ["GJ-01-ZZ-7019", "Eicher Pro 2049 Commercial Truck", "Box Truck", "Diesel", "Maintenance Due (DPF Filter)"],
        ["TS-09-UB-5541", "Mahindra Scorpio-N 4Xplor", "SUV", "Diesel", "Active (Tour Package)"]
    ]
    create_styled_table(doc, fleet_headers, fleet_data, [1.4, 2.0, 1.1, 1.0, 1.0])

    style_heading(doc.add_paragraph(), "Sample Work Orders & Indian Rupee (₹) Financials", 11, RGBColor(15, 23, 42))
    wo_headers = ["Invoice #", "Vehicle Plate", "Service Package", "Parts (₹)", "Labor (₹)", "Total (₹)", "Status"]
    wo_data = [
        ["WO-2026-0101", "MH-02-CW-8092", "Tata Winger 40k Service Package", "₹4,300.00", "₹1,500.00", "₹6,264.00", "Paid"],
        ["WO-2026-0102", "MH-02-CW-8093", "4 Commercial Apollo Tires Replacement", "₹30,000.00", "₹2,000.00", "₹34,560.00", "Paid"],
        ["WO-2026-0103", "DL-01-AX-4011", "Force Traveller Brake Overhaul", "₹11,000.00", "₹2,500.00", "₹14,580.00", "In Progress"],
        ["WO-2026-0104", "KA-03-MY-9921", "Innova HyCross Hybrid Inspection", "₹3,500.00", "₹1,800.00", "₹5,724.00", "Paid"],
        ["WO-2026-0105", "GJ-01-ZZ-7019", "Commercial Eicher DPF Regeneration", "₹10,300.00", "₹4,200.00", "₹15,660.00", "Paid"]
    ]
    create_styled_table(doc, wo_headers, wo_data, [1.1, 1.2, 1.9, 0.8, 0.8, 0.8, 0.9])

    # -------------------------------------------------------------
    # 6. STEP-BY-STEP DEPLOYMENT & EXECUTION GUIDE
    # -------------------------------------------------------------
    style_heading(doc.add_paragraph(), "6. Installation, Configuration & Execution Guide", 16, RGBColor(30, 58, 138))

    add_body_p(doc,
        "Running FleetSync locally requires Python 3.10+ and a standard XAMPP environment with MySQL running:"
    )

    style_heading(doc.add_paragraph(), "Step 1: Install Required Python Packages", 11, RGBColor(15, 23, 42))
    add_body_p(doc, "Execute the following command in the project root directory:")
    add_bullet_p(doc, "Command: ", "pip install -r requirements.txt")

    style_heading(doc.add_paragraph(), "Step 2: Start MySQL Server in XAMPP", 11, RGBColor(15, 23, 42))
    add_body_p(doc,
        "1. Open the XAMPP Control Panel (C:\\xampp\\xampp-control.exe).\n"
        "2. Click 'Start' next to MySQL. Ensure port 3306 turns green."
    )

    style_heading(doc.add_paragraph(), "Step 3: Initialize & Seed Database Schema", 11, RGBColor(15, 23, 42))
    add_body_p(doc,
        "Run the automated database setup script to create fleetsync_db and seed all tables:\n"
        "python setup_db.py"
    )

    style_heading(doc.add_paragraph(), "Step 4: Launch Web Server", 11, RGBColor(15, 23, 42))
    add_body_p(doc,
        "Start the Flask WSGI development server:\n"
        "python app.py\n\n"
        "Once active, navigate your browser to: http://127.0.0.1:5000"
    )

    # -------------------------------------------------------------
    # 7. CONCLUSION & FUTURE ENHANCEMENTS
    # -------------------------------------------------------------
    style_heading(doc.add_paragraph(), "7. Conclusion & Roadmap", 16, RGBColor(30, 58, 138))

    add_body_p(doc,
        "FleetSync successfully bridges the gap between mechanical automotive maintenance and modern cloud enterprise software. "
        "Through responsive frontend design, dynamic OEM interval automation, itemized rupee invoicing, and role-based access control, "
        "it modernizes workshop job-card execution and eliminates costly fleet downtime."
    )
    add_body_p(doc, bold_prefix="Future Roadmap Enhancements:")
    add_bullet_p(doc, "IoT / OBD-II Telematics: ", "Live GPS vehicle location tracking and real-time remote odometer telemetry streaming via MQTT.")
    add_bullet_p(doc, "Payment Gateway: ", "Direct integration with Razorpay and UPI QR codes for seamless customer invoice clearance.")
    add_bullet_p(doc, "AI Predictive Maintenance: ", "Machine learning models predicting part wear and component failures based on driving patterns.")

    # Save Document
    doc.save(filename)
    print(f"[SUCCESS] Generated Word documentation file at: {filename}")

if __name__ == '__main__':
    output_file = "FleetSync_Project_Documentation.docx"
    if len(sys.argv) > 1:
        output_file = sys.argv[1]
    generate_documentation_docx(output_file)

