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

def set_table_full_grid_borders(table, color="94A3B8", sz="4"):
    """Set full grid borders for formal index and academic tables."""
    tblPr = table._tbl.tblPr
    borders = parse_xml(f'<w:tblBorders {nsdecls("w")}><w:top w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/><w:bottom w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/><w:left w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/><w:right w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/><w:insideH w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/><w:insideV w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/></w:tblBorders>')
    tblPr.append(borders)

def add_chapter_heading(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(20)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = "Arial"
    run.font.size = Pt(16)
    run.font.bold = True
    run.font.color.rgb = RGBColor(30, 58, 138) # Dark Navy
    return p

def add_section_heading(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = "Arial"
    run.font.size = Pt(12)
    run.font.bold = True
    run.font.color.rgb = RGBColor(15, 23, 42) # Slate 900
    return p

def add_sub_heading(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = "Arial"
    run.font.size = Pt(10.5)
    run.font.bold = True
    run.font.color.rgb = RGBColor(51, 65, 85) # Slate 700
    return p

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

def add_callout(doc, title, text, bg_color="EFF6FF", border_color="93C5FD"):
    """Add a highlighted info box."""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = tbl.rows[0].cells[0]
    set_cell_background(c, bg_color)
    set_cell_margins(c, 100, 100, 150, 150)
    set_table_borders(tbl, color=border_color, sz="8")
    
    p = c.paragraphs[0]
    p.paragraph_format.space_after = Pt(3)
    r1 = p.add_run(f"📌 {title}\n")
    r1.font.name = "Arial"
    r1.font.bold = True
    r1.font.size = Pt(10)
    r1.font.color.rgb = RGBColor(30, 58, 138)
    
    r2 = p.add_run(text)
    r2.font.name = "Arial"
    r2.font.size = Pt(9.5)
    r2.font.color.rgb = RGBColor(51, 65, 85)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)

def create_styled_table(doc, headers, data, col_widths=None):
    table = doc.add_table(rows=len(data) + 1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table)

    hdr_cells = table.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].text = title
        set_cell_background(hdr_cells[i], "1E3A8A") # Navy Blue
        set_cell_margins(hdr_cells[i], top=100, bottom=100, left=120, right=120)
        hdr_cells[i].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for r in p.runs:
            r.font.name = "Arial"
            r.font.size = Pt(9)
            r.font.bold = True
            r.font.color.rgb = RGBColor(255, 255, 255)

    for r_idx, row_data in enumerate(data):
        row_cells = table.rows[r_idx + 1].cells
        bg_color = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(row_data):
            row_cells[c_idx].text = str(val)
            set_cell_background(row_cells[c_idx], bg_color)
            set_cell_margins(row_cells[c_idx], top=70, bottom=70, left=120, right=120)
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

    doc.add_paragraph().paragraph_format.space_after = Pt(6)
    return table

def generate_report():
    doc = Document()

    # Set 1-inch margins
    for sec in doc.sections:
        sec.top_margin = Inches(1)
        sec.bottom_margin = Inches(1)
        sec.left_margin = Inches(1)
        sec.right_margin = Inches(1)

        # Header / Footer
        header = sec.header
        hp = header.paragraphs[0]
        hp.text = "FleetSync™ Enterprise — Vehicle Service & Fleet Maintenance Management System"
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        hp.runs[0].font.name = "Arial"
        hp.runs[0].font.size = Pt(8)
        hp.runs[0].font.color.rgb = RGBColor(148, 163, 184)

        footer = sec.footer
        fp = footer.paragraphs[0]
        fp.text = "Project Documentation & Technical Internship Report | Developer: Shailesh Dongare"
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        fp.runs[0].font.name = "Arial"
        fp.runs[0].font.size = Pt(8)
        fp.runs[0].font.color.rgb = RGBColor(148, 163, 184)

    # =============================================================
    # TITLE / COVER PAGE
    # =============================================================
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(40)
    p_title.paragraph_format.space_after = Pt(10)
    r1 = p_title.add_run("A PROJECT REPORT ON\n")
    r1.font.name = "Arial"
    r1.font.size = Pt(13)
    r1.font.bold = True
    r1.font.color.rgb = RGBColor(71, 85, 105)

    r2 = p_title.add_run("FleetSync™ Enterprise\nVehicle Service & Fleet Maintenance Management System\n")
    r2.font.name = "Arial"
    r2.font.size = Pt(22)
    r2.font.bold = True
    r2.font.color.rgb = RGBColor(30, 58, 138)

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_after = Pt(36)
    r_sub = p_sub.add_run("Submitted in partial fulfillment of the requirements\nfor the Degree of Bachelor of Computer Engineering / Information Technology\n(Internship Project Report)")
    r_sub.font.name = "Arial"
    r_sub.font.size = Pt(11)
    r_sub.font.italic = True
    r_sub.font.color.rgb = RGBColor(100, 116, 139)

    # Candidate & Organization Table
    meta_table = doc.add_table(rows=5, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_full_grid_borders(meta_table, color="93C5FD", sz="6")
    cover_data = [
        ("Student Name", "Shailesh Dongare"),
        ("Project Title", "FleetSync — Vehicle Service & Fleet Maintenance Tracker"),
        ("Technology Stack", "Python 3.14, Flask Framework, MySQL (XAMPP), Bootstrap 5"),
        ("Organization Profile", "FleetSync Technologies Pro (Mumbai, India)"),
        ("Academic Year", "2026 - 2027")
    ]
    for idx, (label, val) in enumerate(cover_data):
        c0 = meta_table.rows[idx].cells[0]
        c1 = meta_table.rows[idx].cells[1]
        c0.text = label
        c1.text = val
        set_cell_background(c0, "EFF6FF")
        set_cell_background(c1, "FFFFFF")
        set_cell_margins(c0, 90, 90, 140, 140)
        set_cell_margins(c1, 90, 90, 140, 140)
        c0.paragraphs[0].runs[0].font.bold = True
        c0.paragraphs[0].runs[0].font.size = Pt(10)
        c0.paragraphs[0].runs[0].font.color.rgb = RGBColor(30, 58, 138)
        c1.paragraphs[0].runs[0].font.size = Pt(10)
        c1.paragraphs[0].runs[0].font.color.rgb = RGBColor(30, 41, 59)
        c0.width = Inches(2.2)
        c1.width = Inches(4.3)

    doc.add_page_break()

    # =============================================================
    # CERTIFICATES & PRELIMINARY PAGES
    # =============================================================
    style_heading(doc.add_paragraph(), "Certificate of Project Work", 16, RGBColor(30, 58, 138))
    add_body_p(doc,
        "This is to certify that the project entitled \"FleetSync™ Enterprise: Vehicle Service & Fleet Maintenance Management System\" "
        "has been successfully developed and submitted by Shailesh Dongare in partial fulfillment of the requirements for "
        "the award of the degree during the academic session 2026-2027.",
        bold_prefix="TO WHOMSOEVER IT MAY CONCERN:\n\n"
    )
    add_body_p(doc,
        "The project work carried out under industry and academic mentorship embodies a comprehensive, production-ready "
        "automotive software solution adhering to software engineering best practices, relational database normalization, "
        "responsive UI/UX design, and role-based access control."
    )
    
    # Signature blocks
    sig_table = doc.add_table(rows=2, cols=3)
    sig_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(sig_table, color="FFFFFF")
    sigs = [
        ["\n\n____________________\nProject Guide", "\n\n____________________\nHead of Department", "\n\n____________________\nPrincipal / Director"],
        ["Date: ____________", "Date: ____________", "Seal of Institute"]
    ]
    for r_i, r_data in enumerate(sigs):
        for c_i, text in enumerate(r_data):
            cell = sig_table.rows[r_i].cells[c_i]
            cell.text = text
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            cell.paragraphs[0].runs[0].font.size = Pt(9.5)
            cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(71, 85, 105)

    doc.add_page_break()

    # =============================================================
    # INDEX (MATCHING USER'S UPLOADED IMAGE EXACTLY)
    # =============================================================
    p_idx_title = doc.add_paragraph()
    p_idx_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_idx_title.paragraph_format.space_before = Pt(10)
    p_idx_title.paragraph_format.space_after = Pt(14)
    r_idx = p_idx_title.add_run("INDEX")
    r_idx.font.name = "Arial"
    r_idx.font.size = Pt(18)
    r_idx.font.bold = True
    r_idx.font.color.rgb = RGBColor(30, 58, 138)

    index_table = doc.add_table(rows=9, cols=3)
    index_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_full_grid_borders(index_table, color="64748B", sz="6")

    # Header
    hdr = index_table.rows[0].cells
    hdr[0].text = "Sr.\nNo."
    hdr[1].text = "Chapter"
    hdr[2].text = "Page\nNo."
    for c in hdr:
        set_cell_background(c, "F1F5F9")
        set_cell_margins(c, 100, 100, 120, 120)
        c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.bold = True
        p.runs[0].font.size = Pt(10)
        p.runs[0].font.color.rgb = RGBColor(15, 23, 42)

    hdr[0].width = Inches(0.8)
    hdr[1].width = Inches(4.8)
    hdr[2].width = Inches(0.9)

    index_rows = [
        ("1", "Introduction to Project\n  • Introduction\n  • Existing System\n  • Need and scope of Computer System\n  • Organization Profile", "1"),
        ("2", "Proposed System\n  • Objectives\n  • Requirement Engineering\n  • Requirement Gathering\n  • Software Requirements", "4"),
        ("3", "System Analysis\n  System Diagram\n  • DFD (Data Flow Diagram - Level 0, 1, 2)\n  • ERD (Entity Relationship Diagram)\n  • UML (Use Case, Class, Sequence & Activity Diagrams)", "7"),
        ("4", "System Design\n  • Database Design (Schema, Constraints, Tables)\n  • Input Design & its samples\n  • Output Design (on screen)", "12"),
        ("5", "Implementation\n  • System Requirement\n    - Hardware\n    - Software\n  • Installation process\n  • User Guideline", "18"),
        ("6", "Reports (with valid Data)", "22"),
        ("7", "Conclusion and Suggestions\n  • Conclusion\n  • Limitations\n  • Suggestion", "26"),
        ("8", "Annexure\n  • References\n  • Joining Report\n  • Progress Reports\n  • Student Guide Meet Record", "28")
    ]

    for idx, (sr, chapter_text, pg) in enumerate(index_rows):
        row = index_table.rows[idx + 1]
        c_sr = row.cells[0]
        c_ch = row.cells[1]
        c_pg = row.cells[2]

        c_sr.text = sr
        c_ch.text = chapter_text
        c_pg.text = pg

        set_cell_margins(c_sr, 90, 90, 100, 100)
        set_cell_margins(c_ch, 90, 90, 120, 120)
        set_cell_margins(c_pg, 90, 90, 100, 100)

        c_sr.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        c_ch.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        c_pg.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

        c_sr.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        c_pg.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

        c_sr.paragraphs[0].runs[0].font.size = Pt(9.5)
        c_sr.paragraphs[0].runs[0].font.bold = True
        c_pg.paragraphs[0].runs[0].font.size = Pt(9.5)

        p_ch = c_ch.paragraphs[0]
        p_ch.runs[0].font.size = Pt(9.5)
        p_ch.runs[0].font.color.rgb = RGBColor(30, 41, 59)

        c_sr.width = Inches(0.8)
        c_ch.width = Inches(4.8)
        c_pg.width = Inches(0.9)

    doc.add_page_break()

    # =============================================================
    # CHAPTER 1: INTRODUCTION TO PROJECT
    # =============================================================
    add_chapter_heading(doc, "Chapter 1: Introduction to Project")

    add_section_heading(doc, "1.1 Introduction")
    add_body_p(doc,
        "FleetSync™ is an enterprise-grade vehicle service and maintenance tracking web application engineered to digitally "
        "transform and automate automotive workshop operations, authorized dealership service bays, and commercial fleet logistics. "
        "In modern automotive operations, managing fleets of delivery vans, corporate utility trucks, executive sedans, and personal "
        "vehicles requires meticulous scheduling of preventative checkups, precise itemization of parts and labor billings, "
        "and proactive outreach to asset owners before mechanical failures take place."
    )
    add_body_p(doc,
        "FleetSync unites fleet asset inventories, dual-trigger OEM preventative service algorithms, dynamic line-item billing "
        "calculated in Indian Rupees (₹ INR), automated customer reminder dispatching, and role-based operational permissions "
        "under a clean, cloud-ready web interface built with Python Flask and MySQL."
    )

    add_section_heading(doc, "1.2 Existing System")
    add_body_p(doc,
        "In the conventional workflow practiced across most service centers and mid-sized transport companies, workshop "
        "records are maintained through manual paper-based job cards, physical logbooks, or disconnected Excel spreadsheets."
    )
    add_body_p(doc, bold_prefix="Drawbacks and Bottlenecks of the Existing System:")
    add_bullet_p(doc, "Manual Error & Data Duplication: ", "Technicians manually transcribe odometer readings, parts part-numbers, and labor hours onto physical paper slips, frequently resulting in calculation errors and unbilled parts.")
    add_bullet_p(doc, "Unpredictable Maintenance Overruns: ", "Because vehicle odometers change daily while calendar days elapse concurrently, manual tracking fails to predict when a vehicle has surpassed its safe operational threshold. This causes premature brake wear, engine seizing, and roadside breakdowns.")
    add_bullet_p(doc, "Lack of Real-Time Bay Visibility: ", "Service managers cannot instantly discern how many vehicles are currently 'In Progress', 'Waiting for Parts', or overdue without physically checking workshop bays.")
    add_bullet_p(doc, "No Automated Customer Notification: ", "Customers and corporate fleet liaisons are rarely notified of impending maintenance milestones until severe faults arise, resulting in customer dissatisfaction and lost workshop revenue.")
    add_bullet_p(doc, "Absence of Role Separation: ", "Physical papers or open spreadsheets lack cryptographic access control. Anyone can inadvertently alter prices, edit technician logs, or view confidential company billing totals.")

    add_section_heading(doc, "1.3 Need and Scope of Computer System")
    add_body_p(doc,
        "The imperative for a computerized, database-driven automotive operations system arises from the need for absolute operational "
        "reliability, financial transparency, and preventive health tracking for commercial and private vehicles."
    )
    add_body_p(doc, bold_prefix="Need for Computerization:")
    add_bullet_p(doc, "Real-Time Telematics & KPIs: ", "Immediate access to critical operational indicators including active fleet size, service bay utilization, upcoming revenue, and overdue schedules.")
    add_bullet_p(doc, "Intelligent Dual-Trigger Automation: ", "Automated background algorithms evaluating both elapsed time (months) and accumulated distance (kilometers) to accurately predict maintenance urgency.")
    add_bullet_p(doc, "Financial Precision: ", "Automatic in-browser calculations of line-item costs, parts markups, technician hourly labor, and statutory taxation with instant printable invoice generation.")
    add_bullet_p(doc, "Data Security & Traceability: ", "Role-based privileges safeguarding administrative billing records while empowering workshop technicians to log repair tasks seamlessly.")

    add_body_p(doc, bold_prefix="Scope of the System:")
    add_bullet_p(doc, "Multi-Tenant Fleet Tracking: ", "Supports both corporate fleet entities managing high-volume delivery vehicles (Tata Winger, Force Traveller, Mahindra Bolero) and individual vehicle owners.")
    add_bullet_p(doc, "Preventative Service Library: ", "Pre-configurable OEM maintenance rules for engine oil replacement, ceramic brake pads, DPF soot regenerations, transmission flushes, and suspension checks.")
    add_bullet_p(doc, "Automated Notification Queue: ", "Multi-channel reminder staging across Email, SMS, and WhatsApp previews.")
    add_bullet_p(doc, "Scalable Deployment: ", "Standard WSGI architecture deployable on local on-premise workshop servers (via XAMPP) or cloud enterprise containers (AWS, Azure, Docker).")

    add_section_heading(doc, "1.4 Organization Profile")
    add_body_p(doc,
        "FleetSync Technologies Pro is an automotive technology and enterprise SaaS development venture established to deliver "
        "next-generation digital tools to commercial transport operators, fleet logistics firms, and authorized service centers across India."
    )
    add_bullet_p(doc, "Headquarters: ", "742 Cyber City, Phase 2, Tech District, Mumbai - 400051, Maharashtra, India")
    add_bullet_p(doc, "Core Business: ", "Enterprise Fleet Management Software, Telematics Integrations, Automotive ERP Systems")
    add_bullet_p(doc, "Industry Verticals: ", "Last-mile Logistics, Inter-city Courier Services, Commercial Transport, Dealership Workshops")
    add_bullet_p(doc, "Support Channels: ", "Phone: +91 (022) 6555-3533 | Email: support@fleetsync.io | Web: https://fleetsync.io")

    doc.add_page_break()

    # =============================================================
    # CHAPTER 2: PROPOSED SYSTEM
    # =============================================================
    add_chapter_heading(doc, "Chapter 2: Proposed System")

    add_section_heading(doc, "2.1 Objectives")
    add_body_p(doc, "The primary objectives achieved by the FleetSync computerized platform include:")
    add_bullet_p(doc, "1. Centralized Asset Repository: ", "Provide a single source of truth for all vehicle specifications (VIN, registration plate number, make, model, year, fuel type, odometer).")
    add_bullet_p(doc, "2. Automated Service Escalation: ", "Eliminate human oversight by calculating countdowns to maintenance intervals and flagging vehicles as Upcoming, Due Soon, or Overdue.")
    add_bullet_p(doc, "3. Interactive Itemized Invoicing: ", "Enable dynamic job-card creation with instant in-browser parts and labor calculations formatted in Indian Rupees (₹).")
    add_bullet_p(doc, "4. Cryptographic Role Separation: ", "Enforce strict separation between System Administrators (full access) and Service Technicians (work order execution).")
    add_bullet_p(doc, "5. Automated Customer Outreach: ", "Generate scheduled reminder logs to notify vehicle owners via Email, SMS, and WhatsApp.")
    add_bullet_p(doc, "6. Financial Reporting: ", "Generate exportable service audits (CSV, printable invoices) for workshop accounting and tax compliance.")

    add_section_heading(doc, "2.2 Requirement Engineering")
    add_body_p(doc,
        "Requirement Engineering was executed through an iterative lifecycle consisting of feasibility analysis, user profiling, "
        "functional specification synthesis, and validation against real-world automotive workshop workflows:"
    )
    add_bullet_p(doc, "Feasibility Study: ", "Evaluated technical feasibility (Python Flask and MySQL on Windows/Linux environments), economic feasibility (zero recurring licensing fees using open-source web stack), and operational feasibility (intuitive UI for mechanics and technicians).")
    add_bullet_p(doc, "Traceability Matrix: ", "Mapped each workshop problem statement directly to software functional modules (e.g. Unbilled Parts -> Dynamic JavaScript Line Items Table).")
    add_bullet_p(doc, "Risk Management: ", "Implemented database rollback safety nets (transactions) and client-side form validations to prevent incomplete work orders from corrupting inventory logs.")

    add_section_heading(doc, "2.3 Requirement Gathering")
    add_body_p(doc,
        "Requirements were gathered through structured on-site interviews, observation of workshop service advisors, "
        "and scrutiny of commercial automotive job-cards:"
    )
    add_bullet_p(doc, "Technician Interviews: ", "Identified the need for quick-fill options, pre-filled common parts (oil filters, wiper blades, synthetic oil cans), and one-click status transitions.")
    add_bullet_p(doc, "Customer & Fleet Manager Feedback: ", "Emphasized transparent tax invoices itemizing exact labor hours versus parts costs, alongside mobile-friendly reminder notifications.")
    add_bullet_p(doc, "Administrative Review: ", "Highlighted the requirement for monthly revenue charts, top serviced vehicle models, and CSV export capabilities for accounting.")

    add_section_heading(doc, "2.4 Software Requirements")
    add_body_p(doc, bold_prefix="Functional Requirements:")
    add_bullet_p(doc, "FR-01 User Authentication: ", "Secure login/registration with scrypt password verification, session management, and role-based route guards.")
    add_bullet_p(doc, "FR-02 Customer Management: ", "Create, read, update, and search corporate fleet accounts and individual vehicle owners.")
    add_bullet_p(doc, "FR-03 Vehicle Inventory: ", "Track complete vehicle profiles, 17-character VIN codes, RTO plates, fuel types, and mileage.")
    add_bullet_p(doc, "FR-04 Preventive Maintenance: ", "Configure custom recurring service intervals (in km and months) with automated status updates.")
    add_bullet_p(doc, "FR-05 Work Orders & Line Items: ", "Generate unique job cards (e.g. WO-2026-0101) with multi-row parts and labor calculators.")
    add_bullet_p(doc, "FR-06 Invoice Generation: ", "Render print-optimized commercial tax invoices with customer signature blocks and shop branding.")
    add_bullet_p(doc, "FR-07 Automated Reminders: ", "Scan schedules with one click and dispatch queued notifications across multiple channels.")

    add_body_p(doc, bold_prefix="Non-Functional Requirements:")
    add_bullet_p(doc, "NFR-01 Performance: ", "Sub-second response times for dashboard KPI queries through indexed foreign keys and database pooling.")
    add_bullet_p(doc, "NFR-02 Security: ", "Protection against SQL Injection via parameterized queries, XSS sanitization via Jinja2 auto-escaping, and CSRF protection.")
    add_bullet_p(doc, "NFR-03 Reliability & ACID Compliance: ", "MySQL InnoDB storage engine guaranteeing atomic transactions and rollback on execution errors.")
    add_bullet_p(doc, "NFR-04 Usability & Responsiveness: ", "Mobile-friendly Bootstrap 5 interface fully accessible across smartphones, tablets, and workshop workstations.")

    doc.add_page_break()

    # =============================================================
    # CHAPTER 3: SYSTEM ANALYSIS
    # =============================================================
    add_chapter_heading(doc, "Chapter 3: System Analysis")

    add_section_heading(doc, "3.1 System Diagram & Architecture Overview")
    add_body_p(doc,
        "FleetSync is architected as a layered Model-View-Controller (MVC) system ensuring complete decoupling between "
        "data persistence, business routing, and frontend representation:"
    )
    
    add_callout(doc, "Architecture Tier Breakdown",
        "• Presentation Tier (View): HTML5, Bootstrap 5.3, Chart.js 4.4, SweetAlert2 modal dialogs.\n"
        "• Application Tier (Controller): Python 3.14 Flask WSGI engine handling routing, decorators, session auth.\n"
        "• Persistence Tier (Model): MySQL 8.x relational database communicating through mysql-connector-python with pure-Python connection pooling."
    )

    add_section_heading(doc, "3.2 Data Flow Diagrams (DFD)")
    add_sub_heading(doc, "Level 0 DFD (Context Diagram)")
    add_body_p(doc,
        "The Level 0 Context Diagram represents the entire FleetSync system as a single central process interacting with "
        "external entities: System Administrator, Service Technician, Customer, and the Automated Notification Engine:"
    )
    
    dfd0_headers = ["Source Entity", "Input Data Flow to System", "Output Data Flow to Entity"]
    dfd0_data = [
        ["System Administrator", "Credentials, user accounts, system configuration, schedule rules", "Operational telemetry, financial reports, user audits, database health"],
        ["Service Technician", "Job card updates, line items, parts used, labor hours, odometer logs", "Assigned work orders, vehicle specifications, parts checklists"],
        ["Customer / Fleet Owner", "Service requests, vehicle registration details, contact info", "Itemized tax invoices, service completion alerts, maintenance reminders"],
        ["MySQL Database", "Query result sets, record counts, authentication hashes", "Parameterized INSERT/UPDATE queries, commit/rollback instructions"]
    ]
    create_styled_table(doc, dfd0_headers, dfd0_data, [1.5, 2.7, 2.7])

    add_sub_heading(doc, "Level 1 DFD (Decomposed Functional Processes)")
    add_body_p(doc,
        "The Level 1 DFD decomposes the system into six core operational processes:"
    )
    add_bullet_p(doc, "Process 1.0 (Authentication & Authorization): ", "Validates email and scrypt password hash; issues session cookie with user_id and role.")
    add_bullet_p(doc, "Process 2.0 (Customer & Asset Onboarding): ", "Stores customer profiles (Table D1: customers) and links vehicle assets (Table D2: vehicles).")
    add_bullet_p(doc, "Process 3.0 (Schedule Maintenance Computation): ", "Compares vehicle current odometer and current date against schedule interval rules (Table D3: maintenance_schedules). Flags status as Upcoming, Due Soon, or Overdue.")
    add_bullet_p(doc, "Process 4.0 (Work Order & Billing Engine): ", "Generates work order header (Table D4: service_records) and attaches line items (Table D5: service_items). Computes parts subtotal, labor subtotal, 8% tax, and grand total.")
    add_bullet_p(doc, "Process 5.0 (Customer Outreach & Reminders): ", "Scans due vehicles, formats message templates, and logs reminder records (Table D6: reminders).")
    add_bullet_p(doc, "Process 6.0 (Analytics & Reporting): ", "Aggregates revenue, status counts, and bay activity into visual charts and exportable CSV documents.")

    add_section_heading(doc, "3.3 Entity Relationship Diagram (ERD)")
    add_body_p(doc,
        "The database architecture consists of 7 normalized relational tables enforcing referential integrity "
        "via foreign key constraints with cascading deletes:"
    )

    erd_headers = ["Relationship Name", "Primary Entity (1)", "Foreign Entity (M)", "Cardinality", "Integrity Action"]
    erd_data = [
        ["Customer Owns Vehicles", "customers (id)", "vehicles (customer_id)", "1 : M", "ON DELETE CASCADE"],
        ["Vehicle Has Schedules", "vehicles (id)", "maintenance_schedules (vehicle_id)", "1 : M", "ON DELETE CASCADE"],
        ["Vehicle Undergoes Services", "vehicles (id)", "service_records (vehicle_id)", "1 : M", "ON DELETE CASCADE"],
        ["Staff Assigned Work Order", "users (id)", "service_records (user_id)", "1 : M", "ON DELETE SET NULL"],
        ["Work Order Contains Items", "service_records (id)", "service_items (service_record_id)", "1 : M", "ON DELETE CASCADE"],
        ["Vehicle Generates Reminders", "vehicles (id)", "reminders (vehicle_id)", "1 : M", "ON DELETE CASCADE"],
        ["Customer Receives Reminders", "customers (id)", "reminders (customer_id)", "1 : M", "ON DELETE CASCADE"]
    ]
    create_styled_table(doc, erd_headers, erd_data, [1.6, 1.4, 1.7, 0.9, 1.3])

    add_section_heading(doc, "3.4 Unified Modeling Language (UML) Diagrams")
    add_sub_heading(doc, "3.4.1 Use Case Diagram Description")
    add_body_p(doc,
        "The Use Case model defines the interactions between the two primary human actors and the automated system actor:"
    )
    add_bullet_p(doc, "Actor: Administrator: ", "Manage Users, Configure System Branding, View Financial Reports, Export CSV Audits, Full CRUD on Customers, Vehicles, Work Orders, and Schedules.")
    add_bullet_p(doc, "Actor: Technician: ", "View Dashboard, Update Vehicle Odometer, Create Work Orders, Add Parts & Labor Line Items, Update Job Card Status ('In Progress' -> 'Waiting for Parts' -> 'Completed').")
    add_bullet_p(doc, "Actor: System Timer / Scheduler: ", "Audit Maintenance Schedules Daily, Detect Overdue Milestones, Stage Customer Reminders.")

    add_sub_heading(doc, "3.4.2 Sequence Diagram (Work Order Creation & Invoicing)")
    add_body_p(doc,
        "1. Technician navigates to /services/create and selects Vehicle Asset.\n"
        "2. Browser AJAX requests GET /api/vehicles/<id>; App returns vehicle current odometer and customer details.\n"
        "3. Technician adds line items; JavaScript calculates line totals, parts cost, labor cost, and 8% tax in real-time.\n"
        "4. Form POST submitted to /services/create; app.py initiates database transaction.\n"
        "5. Record inserted into service_records; generated service_record_id used to batch insert rows into service_items.\n"
        "6. Transaction committed; Technician redirected to /services/<id> rendering the printable invoice in Indian Rupees (₹)."
    )

    doc.add_page_break()

    # =============================================================
    # CHAPTER 4: SYSTEM DESIGN
    # =============================================================
    add_chapter_heading(doc, "Chapter 4: System Design")

    add_section_heading(doc, "4.1 Database Design")
    add_body_p(doc,
        "The relational database fleetsync_db is designed to 3rd Normal Form (3NF) to eliminate data redundancy "
        "and update anomalies. Below are the physical data dictionary specifications for all 7 relational tables:"
    )

    # Tables 1 to 7
    style_heading(doc.add_paragraph(), "4.1.1 Table: users (System Staff & Roles)", 11, RGBColor(15, 23, 42))
    u_h = ["Column Name", "Data Type", "Constraints", "Description"]
    u_d = [
        ["id", "INT", "PK, AUTO_INCREMENT", "Unique internal user identifier"],
        ["name", "VARCHAR(100)", "NOT NULL", "Staff full name (e.g. Shailesh Dongare)"],
        ["email", "VARCHAR(150)", "NOT NULL, UNIQUE", "Staff authentication email"],
        ["password_hash", "VARCHAR(255)", "NOT NULL", "scrypt-hashed encrypted password"],
        ["role", "ENUM", "NOT NULL, DEFAULT 'Technician'", "Role: 'Admin', 'Technician', 'Service Advisor'"],
        ["phone", "VARCHAR(30)", "NULL", "Contact phone number"],
        ["avatar", "VARCHAR(255)", "NULL", "Profile image URL or avatar initials"],
        ["status", "ENUM", "DEFAULT 'Active'", "'Active' or 'Inactive' account status"],
        ["created_at", "TIMESTAMP", "DEFAULT CURRENT_TIMESTAMP", "Account creation timestamp"]
    ]
    create_styled_table(doc, u_h, u_d, [1.2, 1.4, 1.8, 2.5])

    style_heading(doc.add_paragraph(), "4.1.2 Table: customers (Fleet Accounts & Individual Owners)", 11, RGBColor(15, 23, 42))
    c_h = ["Column Name", "Data Type", "Constraints", "Description"]
    c_d = [
        ["id", "INT", "PK, AUTO_INCREMENT", "Unique customer identifier"],
        ["name", "VARCHAR(120)", "NOT NULL, INDEXED", "Primary contact person name"],
        ["email", "VARCHAR(150)", "NOT NULL, INDEXED", "Customer email address"],
        ["phone", "VARCHAR(30)", "NOT NULL", "Primary mobile / phone number"],
        ["company_name", "VARCHAR(150)", "NULL", "Corporate organization or fleet entity name"],
        ["customer_type", "ENUM", "DEFAULT 'Individual'", "'Fleet / Corporate' or 'Individual'"],
        ["address", "TEXT", "NULL", "Street and premises address"],
        ["city", "VARCHAR(80)", "NULL", "City (Mumbai, New Delhi, Bengaluru, etc.)"],
        ["postal_code", "VARCHAR(20)", "NULL", "PIN / Postal code"]
    ]
    create_styled_table(doc, c_h, c_d, [1.2, 1.4, 1.8, 2.5])

    style_heading(doc.add_paragraph(), "4.1.3 Table: vehicles (Fleet Assets)", 11, RGBColor(15, 23, 42))
    v_h = ["Column Name", "Data Type", "Constraints", "Description"]
    v_d = [
        ["id", "INT", "PK, AUTO_INCREMENT", "Vehicle asset identifier"],
        ["customer_id", "INT", "FK (customers.id) ON DELETE CASCADE", "Owning customer or corporate fleet"],
        ["vin", "VARCHAR(20)", "NOT NULL, UNIQUE, INDEXED", "17-character VIN identifier"],
        ["plate_number", "VARCHAR(20)", "NOT NULL, UNIQUE, INDEXED", "Registration plate (e.g. MH-02-CW-8092)"],
        ["make", "VARCHAR(60)", "NOT NULL", "Manufacturer (Tata, Mahindra, Force, Toyota)"],
        ["model", "VARCHAR(60)", "NOT NULL", "Model name (Winger, Traveller, Bolero)"],
        ["year", "INT", "NOT NULL", "Manufacturing year (1980 - 2030)"],
        ["fuel_type", "ENUM", "DEFAULT 'Gasoline'", "Diesel, Gasoline, Electric, Hybrid, CNG"],
        ["current_odometer", "INT", "DEFAULT 0", "Current recorded mileage in km"],
        ["status", "ENUM", "DEFAULT 'Active'", "'Active', 'In Service', 'Maintenance Due', 'Out of Service'"]
    ]
    create_styled_table(doc, v_h, v_d, [1.2, 1.4, 1.8, 2.5])

    style_heading(doc.add_paragraph(), "4.1.4 Table: maintenance_schedules (Preventative Intervals)", 11, RGBColor(15, 23, 42))
    m_h = ["Column Name", "Data Type", "Constraints", "Description"]
    m_d = [
        ["id", "INT", "PK, AUTO_INCREMENT", "Unique schedule rule identifier"],
        ["vehicle_id", "INT", "FK (vehicles.id) ON DELETE CASCADE", "Associated vehicle"],
        ["service_name", "VARCHAR(120)", "NOT NULL", "Service checkpoint title"],
        ["interval_km", "INT", "DEFAULT 5000", "Kilometer recurrence frequency"],
        ["interval_months", "INT", "DEFAULT 6", "Calendar month recurrence frequency"],
        ["last_service_date", "DATE", "NULL", "Date of last completed service"],
        ["next_due_date", "DATE", "NOT NULL, INDEXED", "Computed upcoming service date"],
        ["next_due_odometer", "INT", "NOT NULL", "Computed upcoming service odometer threshold"],
        ["priority", "ENUM", "DEFAULT 'Medium'", "Priority: Low, Medium, High, Critical"],
        ["status", "ENUM", "DEFAULT 'Upcoming'", "Status: Upcoming, Due Soon, Overdue, Completed"]
    ]
    create_styled_table(doc, m_h, m_d, [1.2, 1.4, 1.8, 2.5])

    style_heading(doc.add_paragraph(), "4.1.5 Table: service_records (Work Order Headers)", 11, RGBColor(15, 23, 42))
    s_h = ["Column Name", "Data Type", "Constraints", "Description"]
    s_d = [
        ["id", "INT", "PK, AUTO_INCREMENT", "Unique job card internal ID"],
        ["invoice_number", "VARCHAR(30)", "NOT NULL, UNIQUE, INDEXED", "Standardized invoice number (WO-2026-0101)"],
        ["vehicle_id", "INT", "FK (vehicles.id) ON DELETE CASCADE", "Serviced vehicle asset"],
        ["user_id", "INT", "FK (users.id) ON DELETE SET NULL", "Assigned service technician"],
        ["service_date", "DATE", "NOT NULL, INDEXED", "Service execution date"],
        ["service_type", "VARCHAR(100)", "NOT NULL", "Category (Preventive, Brake Overhaul, etc.)"],
        ["parts_cost", "DECIMAL(10,2)", "DEFAULT 0.00", "Subtotal of parts in ₹ INR"],
        ["labor_cost", "DECIMAL(10,2)", "DEFAULT 0.00", "Subtotal of labor in ₹ INR"],
        ["tax_amount", "DECIMAL(10,2)", "DEFAULT 0.00", "Computed 8% tax in ₹ INR"],
        ["total_cost", "DECIMAL(10,2)", "DEFAULT 0.00", "Grand total billed invoice amount in ₹ INR"],
        ["status", "ENUM", "DEFAULT 'In Progress'", "Pending, In Progress, Waiting for Parts, Completed"],
        ["payment_status", "ENUM", "DEFAULT 'Unpaid'", "Payment: Unpaid, Partially Paid, Paid"]
    ]
    create_styled_table(doc, s_h, s_d, [1.2, 1.4, 1.8, 2.5])

    style_heading(doc.add_paragraph(), "4.1.6 Table: service_items (Parts & Labor Detail)", 11, RGBColor(15, 23, 42))
    i_h = ["Column Name", "Data Type", "Constraints", "Description"]
    i_d = [
        ["id", "INT", "PK, AUTO_INCREMENT", "Unique line item identifier"],
        ["service_record_id", "INT", "FK (service_records.id) ON DELETE CASCADE", "Parent work order"],
        ["item_type", "ENUM", "DEFAULT 'Part'", "Item category: Part, Labor, Inspection, Fee"],
        ["item_name", "VARCHAR(150)", "NOT NULL", "Part or labor description"],
        ["quantity", "DECIMAL(8,2)", "DEFAULT 1.00", "Quantity or hours billed"],
        ["unit_price", "DECIMAL(10,2)", "DEFAULT 0.00", "Unit price per item/hour in ₹ INR"],
        ["total_price", "DECIMAL(10,2)", "DEFAULT 0.00", "Line total (quantity × unit_price) in ₹ INR"]
    ]
    create_styled_table(doc, i_h, i_d, [1.2, 1.4, 1.8, 2.5])

    style_heading(doc.add_paragraph(), "4.1.7 Table: reminders (Communication Audit Queue)", 11, RGBColor(15, 23, 42))
    r_h = ["Column Name", "Data Type", "Constraints", "Description"]
    r_d = [
        ["id", "INT", "PK, AUTO_INCREMENT", "Unique reminder notification ID"],
        ["vehicle_id", "INT", "FK (vehicles.id) ON DELETE CASCADE", "Target vehicle requiring maintenance"],
        ["customer_id", "INT", "FK (customers.id) ON DELETE CASCADE", "Recipient customer"],
        ["schedule_id", "INT", "FK (schedules.id) ON DELETE SET NULL", "Triggering maintenance rule"],
        ["reminder_type", "ENUM", "DEFAULT 'Service Due'", "Service Due, Inspection Expiry, Custom Alert"],
        ["channel", "ENUM", "DEFAULT 'Email'", "Channel: Email, SMS, WhatsApp, System"],
        ["status", "ENUM", "DEFAULT 'Scheduled'", "Status: Scheduled, Sent, Failed, Cancelled"],
        ["message_preview", "TEXT", "NOT NULL", "Outreach message text"]
    ]
    create_styled_table(doc, r_h, r_d, [1.2, 1.4, 1.8, 2.5])

    add_section_heading(doc, "4.2 Input Design & Its Samples")
    add_body_p(doc,
        "Input forms across FleetSync are designed with strict data validation, helpful placeholder formatting, "
        "and client-side event listeners to ensure high input ergonomics:"
    )
    add_bullet_p(doc, "Authentication Form (/login): ", "Clean split-screen form with email validation, password masking, and one-click 'Quick-Fill Admin' and 'Quick-Fill Tech' shortcuts.")
    add_bullet_p(doc, "Vehicle Asset Entry (/vehicles/create): ", "Validates 17-character VIN, RTO registration format (e.g. MH-02-CW-8092), model year (1980-2030), powertrain dropdown, and initial odometer reading in kilometers.")
    add_bullet_p(doc, "Customer Profile Form (/customers/create): ", "Captures corporate organization name, contact person, Indian mobile number (+91), email address, street address, and PIN code.")
    add_bullet_p(doc, "Work Order Entry (/services/create): ", "Dynamic AJAX form; selecting a vehicle auto-populates its current odometer and customer details. The technician dynamically adds line-item rows specifying item type, part name, quantity, and unit price in ₹.")

    add_section_heading(doc, "4.3 Output Design (On Screen)")
    add_body_p(doc,
        "The system's graphical outputs prioritize high legibility, visual status indicators, and print-ready presentation:"
    )
    add_bullet_p(doc, "Command Center Dashboard: ", "Stat cards with color-coded KPI badges, Chart.js doughnut chart of fleet health distribution, horizontal bar chart of revenue by service category, and urgent alert banners.")
    add_bullet_p(doc, "Commercial Tax Invoice Screen (/services/<id>): ", "Clean, printable layout optimized with @media print CSS rules. Features workshop header, invoice number, vehicle specs, itemized table of parts and labor in ₹, 8% tax calculation, and authorized signature block.")
    add_bullet_p(doc, "Preventative Service Board (/schedules): ", "Table with visual priority pills ('Critical', 'High', 'Medium', 'Low') and dynamic status badges ('Upcoming', 'Due Soon', 'Overdue') with remaining days and kilometers displayed.")

    doc.add_page_break()

    # =============================================================
    # CHAPTER 5: IMPLEMENTATION
    # =============================================================
    add_chapter_heading(doc, "Chapter 5: Implementation")

    add_section_heading(doc, "5.1 System Requirements")
    add_sub_heading(doc, "5.1.1 Hardware Requirements")
    hw_headers = ["Component", "Minimum Requirement", "Recommended Specification"]
    hw_data = [
        ["Processor", "Intel Core i3 / AMD Ryzen 3 (Dual Core 2.0 GHz)", "Intel Core i5 / AMD Ryzen 5 or higher"],
        ["RAM", "4 GB DDR3 / DDR4", "8 GB DDR4 or higher"],
        ["Storage Space", "2 GB available hard drive / SSD space", "10 GB SSD storage for database and media"],
        ["Display Resolution", "1280 x 720 (HD)", "1920 x 1080 (Full HD) responsive display"],
        ["Network Interface", "Standard Ethernet / Wi-Fi adapter (10 Mbps)", "100 Mbps LAN for local workshop network access"]
    ]
    create_styled_table(doc, hw_headers, hw_data, [1.5, 2.7, 2.7])

    add_sub_heading(doc, "5.1.2 Software Requirements")
    sw_headers = ["Software Layer", "Environment / Technology", "Supported Version"]
    sw_data = [
        ["Operating System", "Microsoft Windows 10 / 11, Linux (Ubuntu 20.04+), macOS", "64-bit Architecture"],
        ["Backend Runtime", "Python", "Version 3.10, 3.11, 3.12, 3.13, 3.14"],
        ["Web Framework", "Flask (WSGI compliant)", "Version 3.1.x"],
        ["Database Server", "MySQL Community Server (via XAMPP)", "Version 8.0+ / MariaDB 10.4+"],
        ["Web Browser", "Google Chrome, Microsoft Edge, Mozilla Firefox, Safari", "Latest modern HTML5/ES6 browser"],
        ["Python Libraries", "mysql-connector-python, Werkzeug, python-docx, reportlab", "Specified in requirements.txt"]
    ]
    create_styled_table(doc, sw_headers, sw_data, [1.5, 2.7, 2.7])

    add_section_heading(doc, "5.2 Installation & Setup Process")
    add_body_p(doc, "Follow the sequential steps below to deploy FleetSync in a fresh development or workshop environment:")
    
    add_bullet_p(doc, "Step 1: Install Dependencies: ", "Open a command prompt in the project root directory and run:\n   pip install -r requirements.txt")
    add_bullet_p(doc, "Step 2: Start MySQL Server in XAMPP: ", "Open the XAMPP Control Panel and start the MySQL module (verifying port 3306 is active in green).")
    add_bullet_p(doc, "Step 3: Initialize Database Schema: ", "Execute the automated schema creation and seeding script:\n   python setup_db.py\n   (This automatically creates fleetsync_db, establishes all 7 relational tables, and populates realistic Indian fleet records).")
    add_bullet_p(doc, "Step 4: Launch Web Application: ", "Start the Flask application server:\n   python app.py\n   The application will bind to http://127.0.0.1:5000.")
    add_bullet_p(doc, "Step 5: Access via Web Browser: ", "Open Google Chrome or Microsoft Edge and navigate to http://127.0.0.1:5000.")

    add_section_heading(doc, "5.3 User Guidelines (Role-Based Operation)")
    add_sub_heading(doc, "Administrator Role (User: Shailesh Dongare | admin@fleetsync.io)")
    add_body_p(doc,
        "1. Login using Admin credentials (or click 'Quick-Fill Admin').\n"
        "2. Access the complete Operations Command Center featuring top-level revenue metrics in ₹.\n"
        "3. Manage staff members under User Management (create new Technicians or Service Advisors).\n"
        "4. Generate financial analytics, review technician billing efficiency, and export service records to CSV.\n"
        "5. Authorize record deletions and oversee corporate fleet agreements."
    )
    add_sub_heading(doc, "Service Technician Role (User: Suresh Verma | tech@fleetsync.io)")
    add_body_p(doc,
        "1. Login using Technician credentials (or click 'Quick-Fill Tech').\n"
        "2. Open the active service queue to identify work orders in bay.\n"
        "3. Open vehicle profiles to inspect scheduled maintenance countdowns and historical job cards.\n"
        "4. Create new service records, add parts used and labor hours billed, and transition status to 'Completed'.\n"
        "5. Print customer tax invoices upon service completion."
    )

    doc.add_page_break()

    # =============================================================
    # CHAPTER 6: REPORTS (WITH VALID DATA)
    # =============================================================
    add_chapter_heading(doc, "Chapter 6: Reports (with valid Data)")

    add_section_heading(doc, "6.1 Customer & Corporate Account Directory")
    c_rep_h = ["ID", "Customer Name", "Company / Fleet Organization", "City", "Phone Number", "Classification"]
    c_rep_d = [
        ["1", "Ananya Deshmukh", "Apex Logistics India Pvt Ltd", "Mumbai", "+91 98210 12345", "Fleet / Corporate"],
        ["2", "Rohan Kapoor", "Metro Fast Express Logistics Ltd", "New Delhi", "+91 98112 34567", "Fleet / Corporate"],
        ["3", "Pooja Iyer", "Individual Client", "Bengaluru", "+91 98450 98765", "Individual Client"],
        ["4", "Vikram Malhotra", "Horizon National Transport Carriers", "Ahmedabad", "+91 98791 43210", "Fleet / Corporate"],
        ["5", "Arjun Nair", "Individual Client", "Hyderabad", "+91 98490 54321", "Individual Client"]
    ]
    create_styled_table(doc, c_rep_h, c_rep_d, [0.5, 1.4, 2.0, 1.0, 1.1, 0.9])

    add_section_heading(doc, "6.2 Active Fleet Asset & Odometer Audit Report")
    v_rep_h = ["ID", "Plate Number", "Make & Model", "Year", "Fuel Type", "Current Odometer", "Status"]
    v_rep_d = [
        ["1", "MH-02-CW-8092", "Tata Winger Maxi Van", "2023", "Diesel", "48,250 km", "Active"],
        ["2", "MH-02-CW-8093", "Mahindra Bolero Maxi Truck", "2023", "Diesel", "52,100 km", "Maintenance Due"],
        ["3", "DL-01-AX-4011", "Force Motors Traveller 3350", "2024", "Diesel", "31,500 km", "In Service"],
        ["4", "DL-01-AX-4012", "Force Motors Traveller Cargo", "2022", "Diesel", "74,800 km", "Active"],
        ["5", "KA-03-MY-9921", "Toyota Innova HyCross", "2024", "Hybrid", "18,400 km", "Active"],
        ["6", "KA-03-NB-3301", "BMW 330i Gran Limousine", "2023", "Gasoline", "24,100 km", "Active"],
        ["7", "GJ-01-ZZ-7019", "Eicher Pro 2049 Box Truck", "2021", "Diesel", "112,400 km", "Maintenance Due"],
        ["8", "TS-09-UB-5541", "Mahindra Scorpio-N 4Xplor", "2022", "Diesel", "41,200 km", "Active"]
    ]
    create_styled_table(doc, v_rep_h, v_rep_d, [0.4, 1.2, 1.9, 0.6, 0.8, 1.1, 0.9])

    add_section_heading(doc, "6.3 Work Orders & Itemized Billing Invoice Report (₹ INR)")
    wo_rep_h = ["Invoice #", "Vehicle Plate", "Customer", "Service Type", "Parts (₹)", "Labor (₹)", "Total (₹)", "Payment"]
    wo_rep_d = [
        ["WO-2026-0101", "MH-02-CW-8092", "Ananya Deshmukh", "Preventive Maintenance", "₹4,300.00", "₹1,500.00", "₹6,264.00", "Paid"],
        ["WO-2026-0102", "MH-02-CW-8093", "Ananya Deshmukh", "Tire Replacement", "₹30,000.00", "₹2,000.00", "₹34,560.00", "Paid"],
        ["WO-2026-0103", "DL-01-AX-4011", "Rohan Kapoor", "Brake System Overhaul", "₹11,000.00", "₹2,500.00", "₹14,580.00", "Unpaid"],
        ["WO-2026-0104", "KA-03-MY-9921", "Pooja Iyer", "Warranty Check", "₹3,500.00", "₹1,800.00", "₹5,724.00", "Paid"],
        ["WO-2026-0105", "GJ-01-ZZ-7019", "Vikram Malhotra", "Heavy Commercial DPF", "₹10,300.00", "₹4,200.00", "₹15,660.00", "Paid"],
        ["WO-2026-0106", "TS-09-UB-5541", "Arjun Nair", "Suspension Service", "₹3,200.00", "₹2,400.00", "₹6,048.00", "Paid"],
        ["WO-2026-0107", "MH-02-CW-8093", "Ananya Deshmukh", "Emergency Brake Part", "₹7,800.00", "₹2,200.00", "₹10,800.00", "Unpaid"]
    ]
    create_styled_table(doc, wo_rep_h, wo_rep_d, [1.0, 1.1, 1.2, 1.4, 0.7, 0.7, 0.8, 0.5])

    add_section_heading(doc, "6.4 Preventive Maintenance Interval Status Report")
    sched_rep_h = ["Vehicle Plate", "Maintenance Task", "Next Due Date", "Due Odometer", "Priority", "Status"]
    sched_rep_d = [
        ["MH-02-CW-8092", "Synthetic Engine Oil & Filter Change", "Nov 15, 2026", "48,000 km", "High", "Due Soon"],
        ["MH-02-CW-8093", "Ceramic Brake Pads Replacement", "Sep 10, 2026", "52,000 km", "Critical", "Overdue"],
        ["DL-01-AX-4011", "Comprehensive 30k Inspection", "Oct 20, 2026", "31,000 km", "High", "Due Soon"],
        ["DL-01-AX-4012", "Transmission Fluid & Flush", "Nov 01, 2026", "75,000 km", "Medium", "Upcoming"],
        ["KA-03-MY-9921", "Hybrid Battery Intake & Tire Rotation", "Oct 12, 2026", "20,000 km", "Low", "Upcoming"],
        ["GJ-01-ZZ-7019", "Commercial Diesel DPF Regeneration", "Sep 01, 2026", "112,000 km", "Critical", "Overdue"]
    ]
    create_styled_table(doc, sched_rep_h, sched_rep_d, [1.2, 2.0, 1.0, 1.1, 0.8, 0.8])

    doc.add_page_break()

    # =============================================================
    # CHAPTER 7: CONCLUSION AND SUGGESTIONS
    # =============================================================
    add_chapter_heading(doc, "Chapter 7: Conclusion and Suggestions")

    add_section_heading(doc, "7.1 Conclusion")
    add_body_p(doc,
        "The FleetSync™ Vehicle Service & Fleet Maintenance Management System was conceived, engineered, and tested to address "
        "the pressing operational bottlenecks faced by modern automotive workshops, commercial logistics carriers, and authorized "
        "service centers. By transitioning manual, error-prone paper workflows into a modern, centralized digital architecture, "
        "the project has achieved all of its established engineering objectives:"
    )
    add_bullet_p(doc, "Elimination of Unscheduled Downtime: ", "The dual-trigger OEM maintenance countdown accurately flags vehicles approaching critical mileage or date thresholds, preventing costly roadside failures.")
    add_bullet_p(doc, "Financial Accuracy & Billing Transparency: ", "The interactive line-items calculator automates parts and labor pricing in Indian Rupees (₹), enforces standard taxation, and produces commercial-grade printable tax invoices.")
    add_bullet_p(doc, "Operational Velocity: ", "Technicians and shop supervisors experience streamlined job card creation, immediate bay occupancy status, and rapid search filtering across high-volume fleet records.")
    add_bullet_p(doc, "Scalable & Secure Design: ", "The application demonstrates high resilience through parameterized query execution, atomic transactions, and cryptographically secure user authentication.")

    add_section_heading(doc, "7.2 Limitations")
    add_body_p(doc, "While FleetSync delivers an enterprise-ready feature suite, the current release exhibits the following constraints:")
    add_bullet_p(doc, "1. Manual Odometer Updates: ", "Mileage logs currently rely on technicians entering vehicle odometer readings at workshop check-in rather than automated real-time hardware telemetry.")
    add_bullet_p(doc, "2. Simulated Messaging Dispatch: ", "Customer reminder dispatches via SMS and WhatsApp are currently simulated and staged in database audit logs rather than interfaced with paid third-party SMS gateways (Twilio, Gupshup).")
    add_bullet_p(doc, "3. Localized Single-Server Deployment: ", "The current deployment configuration is optimized for local workshop area networks (LAN / XAMPP) rather than distributed multi-region geo-replicated clusters.")

    add_section_heading(doc, "7.3 Suggestions for Future Enhancements")
    add_body_p(doc, "Based on real-world workshop feedback, the following roadmap enhancements are suggested for future iterations:")
    add_bullet_p(doc, "1. OBD-II / IoT Telematics Integration: ", "Equip fleet vehicles with cellular OBD-II dongles streaming real-time GPS locations, engine error trouble codes (DTCs), and automated odometer readings over MQTT/WebSockets.")
    add_bullet_p(doc, "2. Integrated Payment Gateway: ", "Incorporate Razorpay / UPI QR code generation directly onto invoices for instant customer settlement via Google Pay, PhonePe, and Net Banking.")
    add_bullet_p(doc, "3. AI Predictive Component Health: ", "Implement Machine Learning models analyzing driving severity, route topography, and vehicle age to predict mechanical component failures before symptoms emerge.")
    add_bullet_p(doc, "4. Dedicated Mobile PWA: ", "Develop a Progressive Web Application (PWA) with offline barcode/QR scanning allowing technicians to scan vehicle registration plates directly using smartphone cameras.")

    doc.add_page_break()

    # =============================================================
    # CHAPTER 8: ANNEXURE
    # =============================================================
    add_chapter_heading(doc, "Chapter 8: Annexure")

    add_section_heading(doc, "8.1 References")
    add_body_p(doc, bold_prefix="Academic & Technical Documentation:")
    add_bullet_p(doc, "1. Python Software Foundation: ", "Python 3.14 Official Language Reference & Documentation (https://docs.python.org/3/)")
    add_bullet_p(doc, "2. Pallets Projects: ", "Flask Web Development Framework Documentation, Version 3.1 (https://flask.palletsprojects.com/)")
    add_bullet_p(doc, "3. Oracle Corporation: ", "MySQL 8.0 Reference Manual, High Availability & InnoDB Storage Engine Architecture (https://dev.mysql.com/doc/)")
    add_bullet_p(doc, "4. Bootstrap Community: ", "Bootstrap 5.3 Responsive Front-End Framework Documentation (https://getbootstrap.com/)")
    add_bullet_p(doc, "5. Chart.js Team: ", "Chart.js HTML5 Interactive Data Visualization API Guide (https://www.chartjs.org/)")
    add_bullet_p(doc, "6. Pressman, R. S.: ", "Software Engineering: A Practitioner's Approach, McGraw-Hill Higher Education, 9th Edition.")

    add_section_heading(doc, "8.2 Internship Joining Report")
    join_table = doc.add_table(rows=7, cols=2)
    join_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_full_grid_borders(join_table, color="94A3B8", sz="6")
    join_data = [
        ("Student Name", "Shailesh Dongare"),
        ("College / Department", "Department of Computer Engineering / Information Technology"),
        ("Host Organization", "FleetSync Technologies Pro"),
        ("Project Title Assigned", "FleetSync — Vehicle Service & Fleet Maintenance Tracker"),
        ("Internship Role", "Full Stack Python Web Development Intern"),
        ("Date of Joining", "01 August 2026"),
        ("Industry Mentor / Guide", "Engineering Lead, FleetSync Technologies Pro")
    ]
    for idx, (lbl, val) in enumerate(join_data):
        r0 = join_table.rows[idx].cells[0]
        r1 = join_table.rows[idx].cells[1]
        r0.text = lbl
        r1.text = val
        set_cell_background(r0, "EFF6FF")
        set_cell_background(r1, "FFFFFF")
        set_cell_margins(r0, 80, 80, 120, 120)
        set_cell_margins(r1, 80, 80, 120, 120)
        r0.paragraphs[0].runs[0].font.bold = True
        r0.paragraphs[0].runs[0].font.size = Pt(9.5)
        r1.paragraphs[0].runs[0].font.size = Pt(9.5)
        r0.width = Inches(2.2)
        r1.width = Inches(4.7)

    add_section_heading(doc, "8.3 Weekly Progress Reports (Milestones)")
    prog_h = ["Week", "Duration", "Technical Tasks Accomplished", "Status / Guide Sign"]
    prog_d = [
        ["Week 1-2", "Aug 01 - Aug 14", "Problem formulation, literature review, existing system analysis & requirement gathering", "Completed [Sign]"],
        ["Week 3-4", "Aug 15 - Aug 28", "System architecture design, DFD Level 0/1/2 synthesis, and 3NF MySQL relational database schema formulation", "Completed [Sign]"],
        ["Week 5-6", "Aug 29 - Sep 11", "Backend Flask API routing development, database connection pooling, and scrypt authentication guards", "Completed [Sign]"],
        ["Week 7-8", "Sep 12 - Sep 25", "Frontend UI design using Bootstrap 5.3, responsive layouts, dynamic JavaScript line-item billing calculator", "Completed [Sign]"],
        ["Week 9-10", "Sep 26 - Oct 09", "Preventive maintenance dual-trigger interval engine implementation and reminder staging module", "Completed [Sign]"],
        ["Week 11-12", "Oct 10 - Oct 25", "Indian region localization (₹ INR, fleet vehicles), integration testing, report generation, and final documentation", "Completed [Sign]"]
    ]
    create_styled_table(doc, prog_h, prog_d, [0.8, 1.3, 3.6, 1.2])

    add_section_heading(doc, "8.4 Student Guide Meet Record")
    meet_h = ["Date", "Discussion Topic / Milestones Reviewed", "Suggestions / Guidance Given", "Guide Signature"]
    meet_d = [
        ["05-Aug-2026", "Problem Definition & Requirement Finalization", "Focus on dual-trigger (km + date) maintenance logic", "Approved"],
        ["20-Aug-2026", "Relational Database Schema (ERD & Constraints)", "Enforce ON DELETE CASCADE for clean line-item purges", "Approved"],
        ["05-Sep-2026", "Flask Controller Routing & Role Authentication", "Implement separate @admin_required and @login_required guards", "Approved"],
        ["22-Sep-2026", "Interactive Invoicing & Line Item Billing", "Calculate 8% tax dynamically via client JavaScript", "Approved"],
        ["08-Oct-2026", "Indian Fleet Localization & Indian Rupee (₹)", "Update models to Tata, Mahindra, Force and seed ₹ costs", "Approved"],
        ["24-Oct-2026", "Final Project Testing & Documentation Review", "Verified against university index format; ready for submission", "Approved"]
    ]
    create_styled_table(doc, meet_h, meet_d, [1.0, 2.3, 2.5, 1.1])

    # Save document
    filename = "FleetSync_Academic_Project_Report.docx"
    doc.save(filename)
    print(f"[SUCCESS] Complete academic project report generated: {filename}")

if __name__ == '__main__':
    generate_report()
