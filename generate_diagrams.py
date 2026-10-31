#!/usr/bin/env python3
"""
Generate professional, high-resolution diagrams for FleetSync project report:
1. dfd_level_0.png - Data Flow Diagram Level 0 (Context Diagram)
2. dfd_level_1.png - Data Flow Diagram Level 1 (System Decomposition)
3. erd_diagram.png - Entity Relationship Diagram (7 Relational Tables)
4. uml_usecase.png - UML Use Case Diagram
5. system_architecture.png - 3-Tier MVC Architecture Diagram
"""

import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Ensure diagrams directory
DIAG_DIR = os.path.join(os.path.dirname(__file__), "report_diagrams")
os.makedirs(DIAG_DIR, exist_ok=True)

# Common styling palette
NAVY = "#1E3A8A"
BLUE = "#2563EB"
LIGHT_BLUE = "#EFF6FF"
BORDER_BLUE = "#93C5FD"
DARK_SLATE = "#0F172A"
MID_SLATE = "#334155"
LIGHT_SLATE = "#F8FAFC"
TEAL = "#0D9488"
LIGHT_TEAL = "#CCFBF1"
AMBER = "#D97706"
LIGHT_AMBER = "#FEF3C7"
GREEN = "#16A34A"
LIGHT_GREEN = "#DCFCE7"
PURPLE = "#7C3AED"
LIGHT_PURPLE = "#EDE9FE"

def draw_rounded_rect(ax, x, y, width, height, text, bg_color, border_color, title_color=DARK_SLATE, font_size=10, bold=True, subtext=""):
    """Draw a professional rounded rectangle with title and optional subtext."""
    box = patches.FancyBboxPatch(
        (x, y), width, height,
        boxstyle="round,pad=0.03,rounding_size=0.04",
        facecolor=bg_color,
        edgecolor=border_color,
        linewidth=1.5,
        zorder=3
    )
    ax.add_patch(box)
    
    cy = y + height / 2.0
    cx = x + width / 2.0
    
    if subtext:
        ax.text(cx, cy + height*0.15, text, ha='center', va='center', fontsize=font_size, fontweight='bold' if bold else 'normal', color=title_color, zorder=4)
        ax.text(cx, cy - height*0.18, subtext, ha='center', va='center', fontsize=font_size-1.5, color=MID_SLATE, zorder=4)
    else:
        ax.text(cx, cy, text, ha='center', va='center', fontsize=font_size, fontweight='bold' if bold else 'normal', color=title_color, zorder=4)

def draw_arrow(ax, start, end, label="", label_pos=0.5, color="#475569", rad=0.0, lw=1.5):
    """Draw an arrow with an optional label along the trajectory."""
    ax.annotate(
        "",
        xy=end, xycoords='data',
        xytext=start, textcoords='data',
        arrowprops=dict(
            arrowstyle="-|>",
            color=color,
            lw=lw,
            shrinkA=4, shrinkB=4,
            connectionstyle=f"arc3,rad={rad}",
            mutation_scale=14
        ),
        zorder=2
    )
    if label:
        # Midpoint estimation
        mx = start[0] + (end[0] - start[0]) * label_pos
        my = start[1] + (end[1] - start[1]) * label_pos
        # offset slightly
        ax.text(mx, my + 0.02, label, ha='center', va='bottom', fontsize=8, color="#1E293B",
                bbox=dict(boxstyle="square,pad=0.15", fc="white", ec="none", alpha=0.9), zorder=5)

# ==============================================================================
# 1. DFD LEVEL 0 (CONTEXT DIAGRAM)
# ==============================================================================
def create_dfd_level_0():
    fig, ax = plt.subplots(figsize=(10, 6.5), dpi=300)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    
    # Title
    ax.text(0.5, 0.95, "Figure 3.1: Data Flow Diagram (DFD) — Level 0 Context Diagram", ha='center', va='top', fontsize=13, fontweight='bold', color=NAVY)
    
    # Central Process: 0.0 FleetSync System
    p_box = patches.Circle((0.5, 0.5), 0.16, facecolor=LIGHT_BLUE, edgecolor=BLUE, linewidth=2.5, zorder=3)
    ax.add_patch(p_box)
    ax.text(0.5, 0.53, "0.0\nFleetSync™ Enterprise", ha='center', va='center', fontsize=11, fontweight='bold', color=NAVY, zorder=4)
    ax.text(0.5, 0.44, "Vehicle Service & Fleet\nMaintenance System", ha='center', va='center', fontsize=8.5, color=MID_SLATE, zorder=4)

    # External Entities
    # 1. System Administrator (Top Left)
    draw_rounded_rect(ax, 0.05, 0.72, 0.22, 0.14, "System Administrator", "#FEF3C7", AMBER, subtext="(Shailesh Dongare / Admin)")
    
    # 2. Service Technician (Bottom Left)
    draw_rounded_rect(ax, 0.05, 0.14, 0.22, 0.14, "Service Technician", "#EDE9FE", PURPLE, subtext="(Workshop Bay Mechanic)")
    
    # 3. Customer / Fleet Owner (Top Right)
    draw_rounded_rect(ax, 0.73, 0.72, 0.22, 0.14, "Customer / Fleet Client", "#DCFCE7", GREEN, subtext="(Corporate / Individual)")
    
    # 4. MySQL Relational DB (Bottom Right)
    draw_rounded_rect(ax, 0.73, 0.14, 0.22, 0.14, "MySQL Database", "#CCFBF1", TEAL, subtext="(fleetsync_db 7 Tables)")

    # Data Flows (Arrows)
    # Admin <-> System
    draw_arrow(ax, (0.27, 0.81), (0.40, 0.63), label="Staff & Schedule Rules", label_pos=0.45)
    draw_arrow(ax, (0.42, 0.59), (0.27, 0.74), label="KPIs & Revenue Analytics", label_pos=0.55)

    # Technician <-> System
    draw_arrow(ax, (0.27, 0.23), (0.40, 0.40), label="Job Cards, Parts & Labor", label_pos=0.45)
    draw_arrow(ax, (0.42, 0.37), (0.27, 0.17), label="Assigned Tasks & Specs", label_pos=0.55)

    # System <-> Customer
    draw_arrow(ax, (0.58, 0.63), (0.73, 0.81), label="Invoices (₹) & Reminders", label_pos=0.5)
    draw_arrow(ax, (0.73, 0.74), (0.60, 0.59), label="Service Bookings & Assets", label_pos=0.5)

    # System <-> MySQL DB
    draw_arrow(ax, (0.58, 0.40), (0.73, 0.23), label="Parameterized Transactions", label_pos=0.45)
    draw_arrow(ax, (0.73, 0.17), (0.60, 0.37), label="Recordsets & Audits", label_pos=0.55)

    plt.tight_layout()
    out_path = os.path.join(DIAG_DIR, "dfd_level_0.png")
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[OK] Saved {out_path}")

# ==============================================================================
# 2. DFD LEVEL 1 (SYSTEM DECOMPOSITION)
# ==============================================================================
def create_dfd_level_1():
    fig, ax = plt.subplots(figsize=(11, 7.5), dpi=300)
    ax.set_xlim(0, 1.1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    
    # Title
    ax.text(0.55, 0.96, "Figure 3.2: Data Flow Diagram (DFD) — Level 1 Functional Decomposition", ha='center', va='top', fontsize=13, fontweight='bold', color=NAVY)

    # 6 Core Processes (Circles / Rounded Pills)
    p_defs = [
        (0.18, 0.75, "1.0", "Authentication\n& Security", LIGHT_BLUE, BLUE),
        (0.55, 0.75, "2.0", "Customer & Fleet\nAsset Intake", LIGHT_BLUE, BLUE),
        (0.92, 0.75, "3.0", "Preventive OEM\nInterval Engine", LIGHT_BLUE, BLUE),
        (0.18, 0.28, "4.0", "Work Orders &\nBilling Engine (₹)", LIGHT_BLUE, BLUE),
        (0.55, 0.28, "5.0", "Automated Customer\nOutreach Queue", LIGHT_BLUE, BLUE),
        (0.92, 0.28, "6.0", "Telematics & Financial\nReporting", LIGHT_BLUE, BLUE),
    ]
    
    for cx, cy, num, name, bg, border in p_defs:
        circle = patches.FancyBboxPatch((cx-0.10, cy-0.08), 0.20, 0.16, boxstyle="round,pad=0.02,rounding_size=0.05", facecolor=bg, edgecolor=border, linewidth=2, zorder=3)
        ax.add_patch(circle)
        ax.text(cx, cy+0.03, num, ha='center', va='center', fontsize=10, fontweight='bold', color=NAVY, zorder=4)
        ax.text(cx, cy-0.03, name, ha='center', va='center', fontsize=8.5, fontweight='bold', color=DARK_SLATE, zorder=4)

    # 4 Data Stores (Open-ended rects / shelves)
    stores = [
        (0.18, 0.52, "D1: users | D2: customers", "#F1F5F9", MID_SLATE),
        (0.55, 0.52, "D3: vehicles | D4: maintenance_schedules", "#F1F5F9", MID_SLATE),
        (0.92, 0.52, "D5: service_records | D6: service_items", "#F1F5F9", MID_SLATE),
        (0.55, 0.06, "D7: reminders", "#F1F5F9", MID_SLATE),
    ]
    for sx, sy, sname, sbg, sborder in stores:
        sbox = patches.Rectangle((sx-0.12, sy-0.035), 0.24, 0.07, facecolor=sbg, edgecolor=sborder, linewidth=1.5, zorder=3)
        ax.add_patch(sbox)
        ax.text(sx, sy, sname, ha='center', va='center', fontsize=8, fontweight='bold', color=DARK_SLATE, zorder=4)

    # Key Data Flow Interconnections
    # 1.0 -> D1
    draw_arrow(ax, (0.18, 0.67), (0.18, 0.56), label="Credentials / Role", label_pos=0.5)
    # 2.0 -> D1 / D2 / D3
    draw_arrow(ax, (0.55, 0.67), (0.55, 0.56), label="Vehicle Specs & VIN", label_pos=0.5)
    # D3 -> 3.0
    draw_arrow(ax, (0.67, 0.52), (0.83, 0.70), label="Odometer Logs", label_pos=0.5)
    # 3.0 -> D4
    draw_arrow(ax, (0.92, 0.67), (0.92, 0.56), label="Next Due Km/Date", label_pos=0.5)
    # D4 -> 4.0
    draw_arrow(ax, (0.80, 0.52), (0.28, 0.33), label="Urgent Due Triggers", label_pos=0.5)
    # 4.0 -> D5/D6
    draw_arrow(ax, (0.28, 0.28), (0.80, 0.50), label="Line Items & Tax (₹)", label_pos=0.5)
    # 3.0 -> 5.0
    draw_arrow(ax, (0.88, 0.70), (0.62, 0.36), label="Due Service Alerts", label_pos=0.5)
    # 5.0 -> D7
    draw_arrow(ax, (0.55, 0.20), (0.55, 0.10), label="Queue Reminders", label_pos=0.5)
    # D5 -> 6.0
    draw_arrow(ax, (0.92, 0.48), (0.92, 0.36), label="Revenue & Job Counts", label_pos=0.5)

    plt.tight_layout()
    out_path = os.path.join(DIAG_DIR, "dfd_level_1.png")
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[OK] Saved {out_path}")

# ==============================================================================
# 3. ERD (ENTITY RELATIONSHIP DIAGRAM)
# ==============================================================================
def create_erd_diagram():
    fig, ax = plt.subplots(figsize=(11, 8.5), dpi=300)
    ax.set_xlim(0, 1.1)
    ax.set_ylim(0, 1)
    ax.axis('off')

    ax.text(0.55, 0.97, "Figure 3.3: Entity Relationship Diagram (ERD) — 7 Relational Tables", ha='center', va='top', fontsize=13, fontweight='bold', color=NAVY)

    # Entity definition: (x, y, w, h, table_name, [attrs])
    tables = [
        (0.05, 0.68, 0.26, 0.22, "USERS", [
            "PK  id : INT",
            "    name : VARCHAR(100)",
            "    email : VARCHAR(150)",
            "    password_hash : VARCHAR",
            "    role : ENUM(Admin,Tech)",
            "    status : ENUM"
        ]),
        (0.42, 0.68, 0.26, 0.22, "CUSTOMERS", [
            "PK  id : INT",
            "    name : VARCHAR(120)",
            "    email : VARCHAR(150)",
            "    phone : VARCHAR(30)",
            "    company_name : VARCHAR",
            "    customer_type : ENUM"
        ]),
        (0.79, 0.68, 0.26, 0.22, "VEHICLES", [
            "PK  id : INT",
            "FK  customer_id : INT",
            "    vin : VARCHAR(20)",
            "    plate_number : VARCHAR",
            "    make, model, year",
            "    current_odometer : INT",
            "    status : ENUM"
        ]),
        (0.79, 0.36, 0.26, 0.22, "MAINTENANCE_SCHED", [
            "PK  id : INT",
            "FK  vehicle_id : INT",
            "    service_name : VARCHAR",
            "    interval_km, months",
            "    next_due_date : DATE",
            "    next_due_odometer : INT",
            "    priority, status : ENUM"
        ]),
        (0.42, 0.36, 0.26, 0.22, "SERVICE_RECORDS", [
            "PK  id : INT",
            "FK  vehicle_id : INT",
            "FK  user_id : INT",
            "    invoice_number : VARCHAR",
            "    service_date : DATE",
            "    parts_cost, labor_cost (₹)",
            "    total_cost, status"
        ]),
        (0.05, 0.36, 0.26, 0.22, "SERVICE_ITEMS", [
            "PK  id : INT",
            "FK  service_record_id : INT",
            "    item_type : ENUM",
            "    item_name : VARCHAR(150)",
            "    quantity : DECIMAL",
            "    unit_price : DECIMAL(₹)",
            "    total_price : DECIMAL(₹)"
        ]),
        (0.42, 0.05, 0.26, 0.20, "REMINDERS", [
            "PK  id : INT",
            "FK  vehicle_id : INT",
            "FK  customer_id : INT",
            "FK  schedule_id : INT",
            "    reminder_type : ENUM",
            "    channel : ENUM(Email,SMS,WA)",
            "    status : ENUM"
        ])
    ]

    for x, y, w, h, tname, attrs in tables:
        # Table container
        box = patches.Rectangle((x, y), w, h, facecolor="#FFFFFF", edgecolor="#CBD5E1", linewidth=1.5, zorder=3)
        ax.add_patch(box)
        # Header banner
        hdr = patches.Rectangle((x, y + h - 0.045), w, 0.045, facecolor="#1E3A8A", edgecolor="#1E3A8A", linewidth=1.5, zorder=4)
        ax.add_patch(hdr)
        ax.text(x + w/2.0, y + h - 0.022, tname, ha='center', va='center', fontsize=9.5, fontweight='bold', color="#FFFFFF", zorder=5)

        # Attribute lines
        start_y = y + h - 0.075
        for a_idx, attr in enumerate(attrs):
            color = "#1E3A8A" if "PK" in attr else ("#0D9488" if "FK" in attr else "#334155")
            weight = "bold" if ("PK" in attr or "FK" in attr) else "normal"
            ax.text(x + 0.015, start_y - a_idx * 0.024, attr, ha='left', va='center', fontsize=7.8, fontweight=weight, color=color, zorder=5)

    # Relationship connectors with Cardinalities
    # 1. CUSTOMERS (1) -> VEHICLES (M)
    draw_arrow(ax, (0.68, 0.79), (0.79, 0.79), label="1 : M  (Owns)", label_pos=0.5, color="#1D4ED8", lw=2)

    # 2. VEHICLES (1) -> MAINTENANCE_SCHED (M)
    draw_arrow(ax, (0.92, 0.68), (0.92, 0.58), label="1 : M (Tracks)", label_pos=0.5, color="#1D4ED8", lw=2)

    # 3. VEHICLES (1) -> SERVICE_RECORDS (M)
    draw_arrow(ax, (0.79, 0.72), (0.68, 0.48), label="1 : M (Undergoes)", label_pos=0.5, color="#1D4ED8", lw=2)

    # 4. USERS (1) -> SERVICE_RECORDS (M)
    draw_arrow(ax, (0.31, 0.75), (0.42, 0.52), label="1 : M (Assigns)", label_pos=0.5, color="#1D4ED8", lw=2)

    # 5. SERVICE_RECORDS (1) -> SERVICE_ITEMS (M)
    draw_arrow(ax, (0.42, 0.47), (0.31, 0.47), label="1 : M (Contains)", label_pos=0.5, color="#1D4ED8", lw=2)

    # 6. VEHICLES (1) -> REMINDERS (M)
    draw_arrow(ax, (0.85, 0.68), (0.68, 0.15), label="1 : M (Triggers)", label_pos=0.4, color="#1D4ED8", lw=1.8, rad=0.2)

    # 7. CUSTOMERS (1) -> REMINDERS (M)
    draw_arrow(ax, (0.55, 0.68), (0.55, 0.25), label="1 : M (Receives)", label_pos=0.6, color="#1D4ED8", lw=1.8)

    plt.tight_layout()
    out_path = os.path.join(DIAG_DIR, "erd_diagram.png")
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[OK] Saved {out_path}")

# ==============================================================================
# 4. UML USE CASE DIAGRAM
# ==============================================================================
def create_uml_usecase():
    fig, ax = plt.subplots(figsize=(10.5, 7), dpi=300)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')

    ax.text(0.5, 0.96, "Figure 3.4: UML Use Case Diagram — System Roles & Boundaries", ha='center', va='top', fontsize=13, fontweight='bold', color=NAVY)

    # Boundary Box (FleetSync System)
    bound = patches.FancyBboxPatch((0.26, 0.05), 0.52, 0.86, boxstyle="round,pad=0.02,rounding_size=0.03", facecolor="#F8FAFC", edgecolor="#94A3B8", linewidth=1.8, zorder=1)
    ax.add_patch(bound)
    ax.text(0.52, 0.88, "FleetSync™ Enterprise Boundary", ha='center', va='center', fontsize=10.5, fontweight='bold', color=MID_SLATE, zorder=2)

    # Use Cases (Ellipses)
    usecases = [
        (0.52, 0.81, "UC-01: User Login & Session Auth"),
        (0.52, 0.70, "UC-02: Manage Fleet Assets & VIN"),
        (0.52, 0.59, "UC-03: Manage Customer Accounts"),
        (0.52, 0.48, "UC-04: Configure OEM Service Rules"),
        (0.52, 0.37, "UC-05: Execute Work Order & Line Items (₹)"),
        (0.52, 0.26, "UC-06: Print Commercial Tax Invoice"),
        (0.52, 0.15, "UC-07: Scan Due Services & Queue Alerts"),
        (0.52, 0.08, "UC-08: View Telematics & Export CSV")
    ]
    for ux, uy, uname in usecases:
        ellipse = patches.FancyBboxPatch((ux-0.20, uy-0.035), 0.40, 0.07, boxstyle="round,pad=0.02,rounding_size=0.035", facecolor=LIGHT_BLUE, edgecolor=BLUE, linewidth=1.5, zorder=3)
        ax.add_patch(ellipse)
        ax.text(ux, uy, uname, ha='center', va='center', fontsize=8.5, fontweight='bold', color=NAVY, zorder=4)

    # Actors
    # Actor 1: System Administrator (Left Top)
    ax.plot([0.12], [0.65], marker='o', markersize=14, color=AMBER, zorder=4)
    ax.text(0.12, 0.58, "Administrator\n(Shailesh Dongare)", ha='center', va='top', fontsize=9, fontweight='bold', color=DARK_SLATE)

    # Actor 2: Service Technician (Left Bottom)
    ax.plot([0.12], [0.25], marker='o', markersize=14, color=PURPLE, zorder=4)
    ax.text(0.12, 0.18, "Technician\n(Suresh Verma)", ha='center', va='top', fontsize=9, fontweight='bold', color=DARK_SLATE)

    # Actor 3: Customer / Fleet Client (Right Center)
    ax.plot([0.90], [0.45], marker='o', markersize=14, color=GREEN, zorder=4)
    ax.text(0.90, 0.38, "Client / Fleet Owner\n(Invoice & Reminders)", ha='center', va='top', fontsize=9, fontweight='bold', color=DARK_SLATE)

    # Associations
    # Admin -> UC-01, UC-02, UC-03, UC-04, UC-05, UC-07, UC-08
    for uy in [0.81, 0.70, 0.59, 0.48, 0.15, 0.08]:
        ax.plot([0.14, 0.32], [0.65, uy], color="#64748B", linewidth=1.2, zorder=2)

    # Technician -> UC-01, UC-02, UC-05, UC-06
    for uy in [0.81, 0.70, 0.37, 0.26]:
        ax.plot([0.14, 0.32], [0.25, uy], color="#64748B", linewidth=1.2, zorder=2)

    # Customer -> UC-06, UC-07
    for uy in [0.26, 0.15]:
        ax.plot([0.88, 0.72], [0.45, uy], color="#64748B", linewidth=1.2, linestyle='--', zorder=2)

    plt.tight_layout()
    out_path = os.path.join(DIAG_DIR, "uml_usecase.png")
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[OK] Saved {out_path}")

# ==============================================================================
# 5. SYSTEM ARCHITECTURE (3-TIER MVC)
# ==============================================================================
def create_system_architecture():
    fig, ax = plt.subplots(figsize=(10.5, 6.5), dpi=300)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')

    ax.text(0.5, 0.95, "Figure 3.5: 3-Tier Model-View-Controller (MVC) System Architecture", ha='center', va='top', fontsize=13, fontweight='bold', color=NAVY)

    # 3 Layers (Presentation, Application, Data)
    layers = [
        (0.06, 0.65, 0.88, 0.22, "1. PRESENTATION TIER (View Layer — Client Browser)", "#EFF6FF", "#93C5FD", [
            "Bootstrap 5.3 Responsive Grid",
            "Jinja2 Server Template Rendering",
            "Dynamic JS Invoicing Calculator (main.js)",
            "Chart.js Telematics Visualizations (charts.js)",
            "SweetAlert2 Modal Dialogs"
        ]),
        (0.06, 0.35, 0.88, 0.22, "2. APPLICATION TIER (Controller Layer — Flask WSGI Engine)", "#F8FAFC", "#94A3B8", [
            "Python 3.14 Core Runtime",
            "RESTful Route Controllers (app.py)",
            "Session Security & @login_required / @admin_required",
            "Dual-Trigger OEM Maintenance Countdown Algorithms",
            "Currency Formatter Filters (₹ INR) & CSV Data Exporter"
        ]),
        (0.06, 0.05, 0.88, 0.22, "3. DATA PERSISTENCE TIER (Model Layer — MySQL Database)", "#CCFBF1", "#5EEAD4", [
            "MySQL 8.0 InnoDB Storage Engine (XAMPP localhost:3306)",
            "Pure-Python Connection Pooling (db.py)",
            "Parameterized Query Execution & Automatic Rollback on Failure",
            "7 Relational Tables (users, customers, vehicles, schedules, records, items, reminders)",
            "Cascading Referential Integrity (ON DELETE CASCADE)"
        ])
    ]

    for lx, ly, lw, lh, ltitle, lbg, lborder, items in layers:
        lbox = patches.FancyBboxPatch((lx, ly), lw, lh, boxstyle="round,pad=0.02,rounding_size=0.04", facecolor=lbg, edgecolor=lborder, linewidth=1.8, zorder=2)
        ax.add_patch(lbox)
        ax.text(lx + 0.03, ly + lh - 0.035, ltitle, ha='left', va='center', fontsize=9.5, fontweight='bold', color=NAVY, zorder=3)
        
        # Add pills
        for i_idx, itm in enumerate(items):
            ix = lx + 0.03 + (i_idx % 3) * 0.29
            iy = ly + 0.08 if i_idx >= 3 else ly + 0.13
            pill = patches.Rectangle((ix, iy - 0.02), 0.27, 0.045, facecolor="#FFFFFF", edgecolor="#CBD5E1", linewidth=1, zorder=3)
            ax.add_patch(pill)
            ax.text(ix + 0.135, iy + 0.002, itm, ha='center', va='center', fontsize=7.2, color=DARK_SLATE, zorder=4)

    # Inter-tier communication arrows
    # Presentation <-> Application
    draw_arrow(ax, (0.35, 0.65), (0.35, 0.57), label="HTTP POST / AJAX Requests", label_pos=0.5, color="#1D4ED8", lw=2)
    draw_arrow(ax, (0.65, 0.57), (0.65, 0.65), label="HTML5 Views & JSON Payloads", label_pos=0.5, color="#1D4ED8", lw=2)

    # Application <-> Database
    draw_arrow(ax, (0.35, 0.35), (0.35, 0.27), label="Parameterized SQL Execution", label_pos=0.5, color="#0D9488", lw=2)
    draw_arrow(ax, (0.65, 0.27), (0.65, 0.35), label="Dictionary Resultsets & Rollbacks", label_pos=0.5, color="#0D9488", lw=2)

    plt.tight_layout()
    out_path = os.path.join(DIAG_DIR, "system_architecture.png")
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[OK] Saved {out_path}")

if __name__ == '__main__':
    create_dfd_level_0()
    create_dfd_level_1()
    create_erd_diagram()
    create_uml_usecase()
    create_system_architecture()
    print("[ALL DIAGRAMS SUCCESSFULLY GENERATED IN report_diagrams/]")

