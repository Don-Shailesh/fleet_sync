#!/usr/bin/env python3
"""
Generate an exhaustive, large, and easily editable Word document (.docx)
for FleetSync following the exact academic Index page structure.
"""

import os
import sys
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, hex_color):
    """Set background color of a table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=140, right=140):
    """Set inner cell padding."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
    tcPr.append(tcMar)

def set_table_borders(table, color="CBD5E1", sz="4", val="single"):
    """Set subtle light borders for tables."""
    tblPr = table._tbl.tblPr
    borders = parse_xml(f'<w:tblBorders {nsdecls("w")}><w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/><w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/><w:insideH w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/><w:insideV w:val="none"/><w:left w:val="none"/><w:right w:val="none"/></w:tblBorders>')
    tblPr.append(borders)

def set_table_full_grid(table, color="94A3B8", sz="4"):
    """Set formal academic full grid borders."""
    tblPr = table._tbl.tblPr
    borders = parse_xml(f'<w:tblBorders {nsdecls("w")}><w:top w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/><w:bottom w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/><w:left w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/><w:right w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/><w:insideH w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/><w:insideV w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/></w:tblBorders>')
    tblPr.append(borders)

def setup_document_styles(doc):
    """Ensure standard built-in heading styles exist and look clean in Word's Navigation Pane."""
    styles = doc.styles

    # Normal Style
    style_normal = styles['Normal']
    font_normal = style_normal.font
    font_normal.name = 'Calibri'
    font_normal.size = Pt(11)
    font_normal.color.rgb = RGBColor(30, 41, 59) # Slate 800

    # Heading 1 (Chapter titles)
    h1 = styles['Heading 1']
    h1.font.name = 'Calibri'
    h1.font.size = Pt(18)
    h1.font.bold = True
    h1.font.color.rgb = RGBColor(30, 58, 138) # Deep Navy #1E3A8A
    h1.paragraph_format.space_before = Pt(22)
    h1.paragraph_format.space_after = Pt(8)
    h1.paragraph_format.keep_with_next = True

    # Heading 2 (Sections)
    h2 = styles['Heading 2']
    h2.font.name = 'Calibri'
    h2.font.size = Pt(14)
    h2.font.bold = True
    h2.font.color.rgb = RGBColor(15, 23, 42) # Slate 900
    h2.paragraph_format.space_before = Pt(14)
    h2.paragraph_format.space_after = Pt(6)
    h2.paragraph_format.keep_with_next = True

    # Heading 3 (Subsections)
    h3 = styles['Heading 3']
    h3.font.name = 'Calibri'
    h3.font.size = Pt(12)
    h3.font.bold = True
    h3.font.color.rgb = RGBColor(51, 65, 85) # Slate 700
    h3.paragraph_format.space_before = Pt(10)
    h3.paragraph_format.space_after = Pt(4)
    h3.paragraph_format.keep_with_next = True

def add_body_p(doc, text="", bold_prefix="", space_after=6, italic=False):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.15
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.font.name = "Calibri"
        r_pre.font.size = Pt(11)
        r_pre.font.bold = True
        r_pre.font.color.rgb = RGBColor(15, 23, 42)
    if text:
        r = p.add_run(text)
        r.font.name = "Calibri"
        r.font.size = Pt(11)
        r.font.italic = italic
        r.font.color.rgb = RGBColor(51, 65, 85)
    return p

def add_bullet_p(doc, bold_prefix="", text=""):
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.15
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.font.name = "Calibri"
        r_pre.font.size = Pt(10.5)
        r_pre.font.bold = True
        r_pre.font.color.rgb = RGBColor(30, 41, 59)
    if text:
        r = p.add_run(text)
        r.font.name = "Calibri"
        r.font.size = Pt(10.5)
        r.font.color.rgb = RGBColor(71, 85, 105)
    return p

def add_code_block(doc, code_text):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = tbl.rows[0].cells[0]
    set_cell_background(c, "F8FAFC")
    set_cell_margins(c, 100, 100, 140, 140)
    set_table_borders(tbl, color="CBD5E1", sz="6")
    p = c.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.05
    r = p.add_run(code_text)
    r.font.name = "Consolas"
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor(15, 23, 42)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)

def add_callout(doc, title, text, bg_color="EFF6FF", border_color="93C5FD"):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = tbl.rows[0].cells[0]
    set_cell_background(c, bg_color)
    set_cell_margins(c, 120, 120, 160, 160)
    set_table_borders(tbl, color=border_color, sz="8")
    p = c.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    r1 = p.add_run(f"📌 {title}\n")
    r1.font.name = "Calibri"
    r1.font.bold = True
    r1.font.size = Pt(11)
    r1.font.color.rgb = RGBColor(30, 58, 138)
    r2 = p.add_run(text)
    r2.font.name = "Calibri"
    r2.font.size = Pt(10.5)
    r2.font.color.rgb = RGBColor(51, 65, 85)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)

def add_figure(doc, img_name, caption_text, width_inches=6.0):
    """Embed a high-resolution visual diagram with a professional caption."""
    diag_path = os.path.join(os.path.dirname(__file__), "report_diagrams", img_name)
    if os.path.exists(diag_path):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(8)
        p_img.paragraph_format.space_after = Pt(4)
        run = p_img.add_run()
        run.add_picture(diag_path, width=Inches(width_inches))

        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_after = Pt(12)
        p_cap.paragraph_format.keep_with_next = True
        r_cap = p_cap.add_run(caption_text)
        r_cap.font.name = "Calibri"
        r_cap.font.size = Pt(9.5)
        r_cap.font.bold = True
        r_cap.font.italic = True
        r_cap.font.color.rgb = RGBColor(71, 85, 105)

def create_styled_table(doc, headers, data, col_widths=None):
    table = doc.add_table(rows=len(data) + 1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table)

    hdr_cells = table.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].text = title
        set_cell_background(hdr_cells[i], "1E3A8A")
        set_cell_margins(hdr_cells[i], top=100, bottom=100, left=120, right=120)
        hdr_cells[i].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for r in p.runs:
            r.font.name = "Calibri"
            r.font.size = Pt(9.5)
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
                r.font.name = "Calibri"
                r.font.size = Pt(9)
                r.font.color.rgb = RGBColor(51, 65, 85)

    if col_widths:
        for row in table.rows:
            for i, w in enumerate(col_widths):
                row.cells[i].width = Inches(w)

    doc.add_paragraph().paragraph_format.space_after = Pt(6)
    return table

def build_report():
    doc = Document()
    setup_document_styles(doc)

    # 1-inch margins
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
        hp.runs[0].font.name = "Calibri"
        hp.runs[0].font.size = Pt(8.5)
        hp.runs[0].font.color.rgb = RGBColor(148, 163, 184)

        footer = sec.footer
        fp = footer.paragraphs[0]
        fp.text = "Comprehensive Internship Technical Report  |  Lead Developer: Shailesh Dongare"
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        fp.runs[0].font.name = "Calibri"
        fp.runs[0].font.size = Pt(8.5)
        fp.runs[0].font.color.rgb = RGBColor(148, 163, 184)

    # =============================================================
    # COVER PAGE
    # =============================================================
    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_inst.paragraph_format.space_before = Pt(20)
    p_inst.paragraph_format.space_after = Pt(6)
    r_inst = p_inst.add_run("[ INSERT YOUR COLLEGE / UNIVERSITY NAME HERE ]\n[ Department of Computer Engineering / Information Technology ]")
    r_inst.font.name = "Calibri"
    r_inst.font.size = Pt(13)
    r_inst.font.bold = True
    r_inst.font.color.rgb = RGBColor(71, 85, 105)

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(30)
    p_title.paragraph_format.space_after = Pt(10)
    r1 = p_title.add_run("A TECHNICAL INTERNSHIP PROJECT REPORT ON\n\n")
    r1.font.name = "Calibri"
    r1.font.size = Pt(13)
    r1.font.bold = True
    r1.font.color.rgb = RGBColor(100, 116, 139)

    r2 = p_title.add_run("FleetSync™ Enterprise\nVehicle Service & Fleet Maintenance Management System\n")
    r2.font.name = "Calibri"
    r2.font.size = Pt(24)
    r2.font.bold = True
    r2.font.color.rgb = RGBColor(30, 58, 138)

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_after = Pt(32)
    r_sub = p_sub.add_run("Submitted in partial fulfillment of the requirements\nfor the Degree of Bachelor of Engineering (B.E.) / Technology (B.Tech)\nin Computer Engineering / Information Technology")
    r_sub.font.name = "Calibri"
    r_sub.font.size = Pt(11)
    r_sub.font.italic = True
    r_sub.font.color.rgb = RGBColor(100, 116, 139)

    # Candidate Meta Box
    meta_tbl = doc.add_table(rows=6, cols=2)
    meta_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_full_grid(meta_tbl, color="93C5FD", sz="6")
    meta_d = [
        ("Student / Candidate Name", "Shailesh Dongare"),
        ("University Seat / Roll No.", "[ Enter Your Roll / Seat Number ]"),
        ("Internal Guide / Mentor", "[ Enter Internal Guide Name, e.g. Prof. Name ]"),
        ("Host Organization", "FleetSync Technologies Pro (Mumbai, India)"),
        ("Technology Domain", "Full Stack Web Engineering (Python 3.14, Flask, MySQL, Bootstrap 5)"),
        ("Academic Year", "2026 - 2027")
    ]
    for idx, (l, v) in enumerate(meta_d):
        c0 = meta_tbl.rows[idx].cells[0]
        c1 = meta_tbl.rows[idx].cells[1]
        c0.text = l
        c1.text = v
        set_cell_background(c0, "EFF6FF")
        set_cell_background(c1, "FFFFFF")
        set_cell_margins(c0, 80, 80, 130, 130)
        set_cell_margins(c1, 80, 80, 130, 130)
        c0.paragraphs[0].runs[0].font.bold = True
        c0.paragraphs[0].runs[0].font.size = Pt(10)
        c0.paragraphs[0].runs[0].font.color.rgb = RGBColor(30, 58, 138)
        c1.paragraphs[0].runs[0].font.size = Pt(10)
        c1.paragraphs[0].runs[0].font.color.rgb = RGBColor(30, 41, 59)
        c0.width = Inches(2.3)
        c1.width = Inches(4.3)

    doc.add_page_break()

    # =============================================================
    # CERTIFICATES & PRELIMINARY
    # =============================================================
    doc.add_heading("Certificate of Project Work", level=1)
    add_body_p(doc,
        "This is to certify that the project entitled \"FleetSync™ Enterprise: Vehicle Service & Fleet Maintenance Management System\" "
        "has been successfully carried out and submitted by Shailesh Dongare (Roll No: [___________]) under our supervision and guidance, "
        "in partial fulfillment of the requirements for the award of Bachelor of Engineering / Technology in Computer Engineering / "
        "Information Technology during the academic session 2026-2027.",
        bold_prefix="CERTIFICATE:\n\n"
    )
    add_body_p(doc,
        "It is certified that all conclusions, design diagrams, data dictionaries, implementation codes, and test audit reports "
        "presented in this report represent the authentic and original engineering work completed by the candidate."
    )

    sig_tbl = doc.add_table(rows=2, cols=3)
    sig_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(sig_tbl, color="FFFFFF")
    sigs = [
        ["\n\n___________________________\nInternal Project Guide\n[Department Name]", "\n\n___________________________\nHead of Department\n[Department Name]", "\n\n___________________________\nPrincipal / Director\n[College Seal]"],
        ["Date: ____________\nPlace: ____________", "Date: ____________\nPlace: ____________", "Institutional Stamp"]
    ]
    for r_i, r_data in enumerate(sigs):
        for c_i, t in enumerate(r_data):
            c = sig_tbl.rows[r_i].cells[c_i]
            c.text = t
            c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            c.paragraphs[0].runs[0].font.size = Pt(9.5)
            c.paragraphs[0].runs[0].font.color.rgb = RGBColor(71, 85, 105)

    doc.add_page_break()

    # Declaration & Acknowledgement
    doc.add_heading("Candidate Declaration", level=1)
    add_body_p(doc,
        "I, Shailesh Dongare, hereby declare that the project work presented in this technical report entitled "
        "\"FleetSync™ Enterprise: Vehicle Service & Fleet Maintenance Management System\" is an authentic record of the work "
        "carried out by me during the academic internship period. The content incorporated in this document has not been submitted "
        "for the award of any other degree or diploma to any other university or institution.",
        bold_prefix="DECLARATION:\n\n"
    )
    add_body_p(doc, "Shailesh Dongare\nDepartment of Computer Engineering / Information Technology\nDate: October 2026", bold_prefix="\n\nSignature of Candidate:\n")

    doc.add_heading("Acknowledgement", level=1)
    add_body_p(doc,
        "I express my deepest gratitude to my Project Guide and Head of Department for their invaluable mentorship, "
        "continuous technical critiques, and generous guidance throughout the lifecycle of this project. "
        "I also thank the management and senior engineering personnel at FleetSync Technologies Pro for granting me "
        "the environment, software tools, and real-world automotive dataset essential to developing this system.",
        bold_prefix="ACKNOWLEDGEMENT:\n\n"
    )

    doc.add_page_break()

    # =============================================================
    # INDEX TABLE (EXACT COPY OF USER'S IMAGE FORMAT)
    # =============================================================
    p_idx_t = doc.add_paragraph()
    p_idx_t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_idx_t.paragraph_format.space_before = Pt(6)
    p_idx_t.paragraph_format.space_after = Pt(12)
    r_i = p_idx_t.add_run("INDEX")
    r_i.font.name = "Calibri"
    r_i.font.size = Pt(20)
    r_i.font.bold = True
    r_i.font.color.rgb = RGBColor(30, 58, 138)

    idx_tbl = doc.add_table(rows=9, cols=3)
    idx_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_full_grid(idx_tbl, color="64748B", sz="6")

    h = idx_tbl.rows[0].cells
    h[0].text = "Sr.\nNo."
    h[1].text = "Chapter"
    h[2].text = "Page\nNo."
    for c in h:
        set_cell_background(c, "F1F5F9")
        set_cell_margins(c, 90, 90, 110, 110)
        c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.bold = True
        p.runs[0].font.size = Pt(10.5)
        p.runs[0].font.color.rgb = RGBColor(15, 23, 42)

    h[0].width = Inches(0.8)
    h[1].width = Inches(4.8)
    h[2].width = Inches(0.9)

    i_rows = [
        ("1", "Introduction to Project\n  • Introduction\n  • Existing System\n  • Need and scope of Computer System\n  • Organization Profile", "1"),
        ("2", "Proposed System\n  • Objectives\n  • Requirement Engineering\n  • Requirement Gathering\n  • Software Requirements", "6"),
        ("3", "System Analysis\n  System Diagram\n  • DFD (Data Flow Diagram - Level 0, 1, 2)\n  • ERD (Entity Relationship Diagram)\n  • UML (Use Case, Class, Sequence & Activity Diagrams)", "11"),
        ("4", "System Design\n  • Database Design (7 Relational Tables & DDL)\n  • Input Design & its samples\n  • Output Design (on screen)", "18"),
        ("5", "Implementation\n  • System Requirement\n    - Hardware\n    - Software\n  • Installation process\n  • User Guideline", "27"),
        ("6", "Reports (with valid Data)\n  • Customer Directory\n  • Fleet Odometer Audit\n  • Work Orders & Invoices (₹ INR)\n  • Preventive Schedule Status", "32"),
        ("7", "Conclusion and Suggestions\n  • Conclusion\n  • Limitations\n  • Suggestion", "37"),
        ("8", "Annexure\n  • References\n  • Joining Report\n  • Progress Reports (Weeks 1 - 12)\n  • Student Guide Meet Record", "40")
    ]

    for idx, (sr, ch_t, pg) in enumerate(i_rows):
        row = idx_tbl.rows[idx + 1]
        c0, c1, c2 = row.cells[0], row.cells[1], row.cells[2]
        c0.text, c1.text, c2.text = sr, ch_t, pg
        set_cell_margins(c0, 80, 80, 100, 100)
        set_cell_margins(c1, 80, 80, 120, 120)
        set_cell_margins(c2, 80, 80, 100, 100)
        c0.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        c1.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        c2.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        c0.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        c2.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        c0.paragraphs[0].runs[0].font.bold = True
        c0.paragraphs[0].runs[0].font.size = Pt(10)
        c2.paragraphs[0].runs[0].font.size = Pt(10)
        c1.paragraphs[0].runs[0].font.size = Pt(10)
        c1.paragraphs[0].runs[0].font.color.rgb = RGBColor(30, 41, 59)
        c0.width = Inches(0.8)
        c1.width = Inches(4.8)
        c2.width = Inches(0.9)

    doc.add_page_break()

    # =============================================================
    # CHAPTER 1: INTRODUCTION TO PROJECT
    # =============================================================
    doc.add_heading("Chapter 1: Introduction to Project", level=1)

    doc.add_heading("1.1 Introduction", level=2)
    add_body_p(doc,
        "In the commercial transportation, urban logistics, and retail automotive sectors, vehicles are mission-critical assets. "
        "A single unexpected mechanical breakdown of a commercial transport van or heavy-duty logistics carrier can trigger severe supply chain disruptions, "
        "delayed customer deliveries, financial penalties, and catastrophic engine seizure costs. Consequently, vehicle fleet operators, "
        "authorized service dealerships, and multi-brand garage workshops require robust digital systems to supervise and execute "
        "preventative maintenance routines, generate accurate itemized billing invoices, and systematically monitor asset health."
    )
    add_body_p(doc,
        "FleetSync™ is an enterprise web application engineered to address these operational challenges through automated, "
        "data-driven workflow coordination. Built on Python 3.14, Flask 3.1, and MySQL 8.0, FleetSync establishes a centralized, "
        "multi-tenant operations hub that consolidates customer profiles, vehicle asset specifications (VIN, registration plates, fuel types), "
        "preventive maintenance countdowns, dynamic work order job cards, itemized parts and labor calculators, and multi-channel "
        "customer reminder dispatches."
    )
    add_body_p(doc,
        "By replacing legacy paper job-cards and fragmented spreadsheets with an ACID-compliant relational backend and an intuitive "
        "Bootstrap 5 responsive interface, FleetSync empowers workshop managers, service advisors, and technicians to deliver "
        "uncompromising service turnaround and financial precision."
    )

    doc.add_heading("1.2 Existing System", level=2)
    add_body_p(doc,
        "An extensive field investigation of regional automotive workshops and courier fleet yards revealed that the predominant "
        "method of maintenance tracking relies heavily on manual, paper-driven job cards or disconnected Microsoft Excel workbooks. "
        "The standard operational lifecycle of the existing system proceeds as follows:"
    )
    add_bullet_p(doc, "Vehicle Check-in & Intake: ", "A driver or customer brings the vehicle to the workshop. A service advisor writes the vehicle plate number, customer contact, and customer complaints by hand onto a physical triplicate paper slip.")
    add_bullet_p(doc, "Job Card Assignment: ", "The paper slip is physically carried into the service bay and handed to a workshop technician. Technicians proceed with inspections without access to the vehicle's historical maintenance log or warranty status.")
    add_bullet_p(doc, "Parts Requisition & Labor Logging: ", "Parts removed from store inventory (e.g. oil filters, brake pads, fluids) are manually noted on the reverse side of the paper card. Labor hours are estimated subjectively upon completion.")
    add_bullet_p(doc, "Manual Bill Calculation: ", "A billing clerk manually multiplies parts quantities by unit prices, adds estimated labor charges, manually computes tax, and creates a handwritten or standalone spreadsheet invoice.")
    add_bullet_p(doc, "Filing & Storage: ", "The paper copy is filed in physical folders where historical retrieval for warranty audits or recurring breakdown analysis is laborious and frequently impossible.")

    add_body_p(doc, bold_prefix="\nInherent Bottlenecks and Liabilities of the Existing System:")
    add_bullet_p(doc, "High Human Error & Revenue Leakage: ", "Manual handwriting causes illegible part numbers, missed consumable charges (e.g. unbilled lubricants, washers, shop supplies), and arithmetic calculation errors in invoices.")
    add_bullet_p(doc, "Failure of Preventive Maintenance: ", "Because vehicle odometers change unpredictably while calendar days pass steadily, manual spreadsheets fail to cross-correlate days elapsed with mileage accumulated. Vehicles routinely exceed safe brake and oil thresholds, leading to roadside failures.")
    add_bullet_p(doc, "Zero Operational Telemetry: ", "Workshop managers cannot observe how many service bays are currently occupied, how many work orders are 'Waiting for Parts', or what total daily revenue has been realized without conducting physical walk-throughs.")
    add_bullet_p(doc, "Absence of Cryptographic Access Control: ", "Paper slips and shared spreadsheets possess no role separation. Any staff member can inadvertently overwrite formulas, modify billing figures, or view sensitive customer account data.")

    doc.add_heading("Comparison Table: Existing Manual System vs. FleetSync System", level=3)
    comp_h = ["Operational Dimension", "Existing Manual / Excel Workflow", "FleetSync™ Computerized Platform"]
    comp_d = [
        ["Asset Data Integrity", "Handwritten records prone to loss, moisture damage, and transcription error", "ACID-compliant MySQL relational storage with unique VIN and plate constraints"],
        ["Maintenance Tracking", "Static calendar dates or passive odometer logs; frequently overlooked", "Dynamic dual-trigger OEM interval engine (Days elapsed vs. Kilometers logged)"],
        ["Billing & Invoicing", "Manual calculator entry; unbilled consumables and arithmetic mistakes", "Real-time in-browser JavaScript calculator with itemized parts, labor, and 8% tax in ₹"],
        ["Operational Visibility", "Opaque workshop status; physical bay counts required to track jobs", "Real-time Command Center with interactive Chart.js telematics and KPI cards"],
        ["Customer Reminders", "Ad-hoc manual phone calls only when faults occur", "Automated scan engine queuing Email, SMS, and WhatsApp alerts for upcoming services"],
        ["Security & Permissions", "No authentication; open access to all physical or spreadsheet records", "Role-based authentication with scrypt encryption separating Admins from Technicians"],
        ["Audit & Exportability", "Tedious paper filing; warranty verification requires manual folder search", "Instant full historical search, vehicle service audit logs, and one-click CSV export"]
    ]
    create_styled_table(doc, comp_h, comp_d, [1.5, 2.5, 2.8])

    doc.add_heading("1.3 Need and Scope of Computer System", level=2)
    add_body_p(doc,
        "The development of FleetSync was motivated by the non-negotiable imperative for operational speed, mechanical safety, "
        "and fiscal transparency in commercial automotive fleet management."
    )
    add_body_p(doc, bold_prefix="Need for the System:")
    add_bullet_p(doc, "Prevent Catastrophic Mechanical Failure: ", "Automotive engineering standards dictate that oils shear and brake friction compounds degrade according to strict usage curves. Automating status alerts ('Upcoming' -> 'Due Soon' -> 'Overdue') ensures vehicles are serviced prior to engine or brake system failure.")
    add_bullet_p(doc, "Financial Governance & Taxation Compliance: ", "Service centers require transparent itemization separating tangible parts from intangible technician labor hours to support statutory tax compliance (GST) and customer trust.")
    add_bullet_p(doc, "High-Throughput Workshop Management: ", "Authorized service centers servicing 20 to 50 vehicles daily require instantaneous vehicle history retrieval by typing a registration number or VIN.")

    add_body_p(doc, bold_prefix="\nScope of the System:")
    add_body_p(doc,
        "FleetSync is architected to encompass the full lifecycle of workshop and fleet asset administration:"
    )
    add_bullet_p(doc, "Multi-Tenant Asset Supervision: ", "Tracking both commercial fleet carriers (Tata Winger, Force Traveller, Mahindra Bolero, Eicher trucks) and private client passenger cars (Toyota Innova, BMW 330i).")
    add_bullet_p(doc, "OEM Preventive Service Library: ", "Support for unlimited recurring maintenance rules including synthetic oil changes, ceramic brake pads, DPF regenerations, automatic transmission flushes, and tire balancing.")
    add_bullet_p(doc, "Itemized Job-Card & Billing Engine: ", "Real-time JavaScript-driven billing calculators generating official printable tax invoices formatted in Indian Rupees (₹ INR).")
    add_bullet_p(doc, "Customer Relationship & Outreach Queue: ", "Automated reminder staging across multiple simulated and exportable channels including WhatsApp, SMS, and Email.")
    add_bullet_p(doc, "Role-Based Administrative Security: ", "Protected endpoints with custom Flask decorators ensuring workshop technicians execute work orders while administrators retain sole authority over user credentials and financial auditing.")

    doc.add_heading("1.4 Organization Profile", level=2)
    add_body_p(doc,
        "FleetSync Technologies Pro is a specialized enterprise automotive software engineering firm established to deliver "
        "cloud-native operational platforms, telematics software, and digital workshop tools to the commercial transport industry across India."
    )
    add_bullet_p(doc, "Corporate Entity: ", "FleetSync Technologies Pro India Private Limited")
    add_bullet_p(doc, "Headquarters: ", "742 Cyber City, Phase 2, Tech District, Mumbai - 400051, Maharashtra, India")
    add_bullet_p(doc, "Primary Domain: ", "Automotive Fleet Telematics, Enterprise Maintenance ERP, Workshop Automation Systems")
    add_bullet_p(doc, "Target Sectors: ", "Urban Last-Mile Logistics, Inter-City Cargo Carriers, Commercial Transport Fleets, Authorized Dealership Service Bays")
    add_bullet_p(doc, "Official Support: ", "Phone: +91 (022) 6555-3533 | Email: support@fleetsync.io | Web: https://fleetsync.io")

    doc.add_page_break()

    # =============================================================
    # CHAPTER 2: PROPOSED SYSTEM
    # =============================================================
    doc.add_heading("Chapter 2: Proposed System", level=1)

    doc.add_heading("2.1 Objectives", level=2)
    add_body_p(doc, "The proposed FleetSync computerized system was engineered to accomplish the following measurable objectives:")
    add_bullet_p(doc, "1. Centralize Vehicle Asset Records: ", "Eliminate disparate paper logbooks by establishing a normalized relational database storing 17-character VINs, RTO plates, fuel types, and historical odometers.")
    add_bullet_p(doc, "2. Automate Maintenance Intervals: ", "Implement dynamic dual-trigger countdown algorithms that evaluate calendar days and mileage concurrently, categorizing service needs into 'Upcoming', 'Due Soon', and 'Overdue'.")
    add_bullet_p(doc, "3. Deliver Live Invoicing Precision: ", "Build an interactive in-browser billing engine that recalculates parts totals, labor hours, and statutory 8% tax in Indian Rupees (₹) with zero page reloads.")
    add_bullet_p(doc, "4. Enforce Role Separation: ", "Implement scrypt-hashed cryptographic credentials separating System Administrators (executive oversight) from Service Technicians (bay job-card execution).")
    add_bullet_p(doc, "5. Provide Real-Time Visual Telematics: ", "Surface operational KPIs (bay occupancy, pending jobs, revenue) on an executive dashboard with Chart.js visualization.")
    add_bullet_p(doc, "6. Facilitate Automated Outreach: ", "Queue multi-channel service reminders (Email, SMS, WhatsApp) with a single-click audit engine to maximize customer retention.")

    doc.add_heading("2.2 Requirement Engineering", level=2)
    add_body_p(doc,
        "Requirement Engineering was executed through an exhaustive four-phase lifecycle encompassing Elicitation, "
        "Analysis & Negotiation, Formal Specification, and Validation:"
    )
    add_bullet_p(doc, "Feasibility Analysis: ", "Evaluated Technical Feasibility (utilizing lightweight, robust Python Flask and MySQL on Windows/Linux with zero commercial licensing costs), Operational Feasibility (simplifying interfaces for shop floor mechanics via quick-fill buttons and color badges), and Economic Feasibility (saving workshops thousands of rupees in unbilled parts and missed service intervals).")
    add_bullet_p(doc, "Traceability Matrix: ", "Every business requirement was mapped directly to a database schema table, a Flask controller endpoint, and a Jinja2 template view.")
    add_bullet_p(doc, "Transaction Safety: ", "Enforced MySQL InnoDB transaction rollbacks ensuring that if an error occurs while writing multi-row service line-items, the entire work order rolls back cleanly without database corruption.")

    doc.add_heading("2.3 Requirement Gathering", level=2)
    add_body_p(doc,
        "Requirements were synthesized through on-site observations at commercial repair garages, structured interviews with fleet directors, "
        "and scrutiny of physical job cards:"
    )
    add_bullet_p(doc, "Technician Feedback: ", "Technicians requested quick-fill defaults for common vehicle inspection tasks (such as 5W-30 engine oil cans and multi-point inspections) and the ability to update odometers directly from the work order screen.")
    add_bullet_p(doc, "Fleet Supervisor Feedback: ", "Fleet operators emphasized the need for print-ready commercial tax invoices displaying company GST/PAN details, detailed parts replacement breakdowns, and formal technician signature blocks.")
    add_bullet_p(doc, "User Personas Formulated: ", "Synthesized distinct user archetypes: Administrator Shailesh Dongare (auditing workshop financials and managing technician roles) and Lead Technician Suresh Verma (executing service work orders in the repair bay).")

    doc.add_heading("2.4 Software Requirements Specification (SRS)", level=2)
    add_body_p(doc, bold_prefix="Functional Requirements (FR):")
    fr_headers = ["Req ID", "Module", "Functional Requirement Description", "Priority"]
    fr_data = [
        ["FR-01", "Authentication", "User authentication with scrypt password verification, session persistence, and logout", "High"],
        ["FR-02", "Role Authorization", "Route protection enforcing Admin permissions for financials/users and Tech access for work orders", "High"],
        ["FR-03", "Customer Management", "CRUD management of corporate fleet logistics accounts and individual vehicle owners", "Medium"],
        ["FR-04", "Vehicle Inventory", "Tracking 17-character VIN, plate number, fuel type, odometer, and vehicle imagery", "High"],
        ["FR-05", "Maintenance Engine", "Dynamic computation of service due status based on elapsed months and accumulated kilometers", "High"],
        ["FR-06", "Work Orders", "Unique job-card creation (e.g. WO-2026-0101) with odometer tracking and status updates", "High"],
        ["FR-07", "Interactive Billing", "In-browser dynamic line-item addition for parts and labor with 8% tax calculation in ₹ INR", "High"],
        ["FR-08", "Printable Invoicing", "Print-optimized rendering (@media print) of commercial customer invoices with signature blocks", "High"],
        ["FR-09", "Reminders Queue", "Automated scan engine queuing customer notifications across Email, SMS, and WhatsApp", "Medium"],
        ["FR-10", "Reporting & CSV", "Dynamic Chart.js telematics analytics and raw CSV download of workshop service logs", "Medium"]
    ]
    create_styled_table(doc, fr_headers, fr_data, [1.0, 1.4, 4.0, 0.8])

    add_body_p(doc, bold_prefix="\nNon-Functional Requirements (NFR):")
    add_bullet_p(doc, "NFR-01 Response Performance: ", "Dashboard KPIs and search queries execute in under 350 milliseconds through database indexing and optimized queries.")
    add_bullet_p(doc, "NFR-02 Cryptographic Security: ", "Passwords encrypted via scrypt key derivation. All SQL executions parameterized to eliminate SQL Injection.")
    add_bullet_p(doc, "NFR-03 Transactional Integrity: ", "Full ACID compliance with foreign key constraints and automated rollback on failure.")
    add_bullet_p(doc, "NFR-04 Responsive Ergonomics: ", "Fully responsive UI adapting cleanly across desktop workstations, shop floor tablets, and mobile devices.")

    doc.add_page_break()

    # =============================================================
    # CHAPTER 3: SYSTEM ANALYSIS
    # =============================================================
    doc.add_heading("Chapter 3: System Analysis", level=1)

    doc.add_heading("3.1 System Architecture Diagram", level=2)
    add_body_p(doc,
        "FleetSync adheres strictly to a clean, scalable 3-Tier Model-View-Controller (MVC) architecture, "
        "ensuring that data persistence, routing logic, and presentation templates remain completely decoupled:"
    )

    add_callout(doc, "Three-Tier Architectural Overview",
        "1. Presentation Tier (View): Rendered server-side using Jinja2 templates, styled with Bootstrap 5.3, enhanced with FontAwesome 6 icons, SweetAlert2 modals, and Chart.js dynamic telematics.\n"
        "2. Application Controller Tier (Controller): Python 3.14 WSGI Flask application managing HTTP routes, session authentication, parameterized query dispatching, and business logic calculations.\n"
        "3. Database Persistence Tier (Model): MySQL 8.x (via XAMPP) handling ACID transactions, foreign keys, cascading deletions, and connection pooling via mysql-connector-python."
    )
    add_figure(doc, "system_architecture.png", "Figure 3.1: 3-Tier Model-View-Controller (MVC) Architecture of FleetSync System")

    doc.add_heading("3.2 Data Flow Diagrams (DFD)", level=2)
    doc.add_heading("3.2.1 Level 0 DFD (Context Diagram)", level=3)
    add_body_p(doc,
        "The Level 0 Context Diagram depicts the boundaries of FleetSync, representing the system as a single central process "
        "interacting with external human actors (System Administrator, Service Technician, Customer) and system resources:"
    )
    add_bullet_p(doc, "Admin Data Flow: ", "Inputs staff accounts, vehicle records, customer profiles, and service intervals. Receives revenue KPIs, financial analytics, and CSV exports.")
    add_bullet_p(doc, "Technician Data Flow: ", "Inputs work order line-items, parts utilized, labor hours billed, and odometer updates. Receives assigned work orders and vehicle maintenance histories.")
    add_bullet_p(doc, "Customer Data Flow: ", "Receives multi-channel service reminders (Email, SMS, WhatsApp) and printable commercial tax invoices in ₹ INR.")
    add_bullet_p(doc, "Database Data Flow: ", "Receives parameterized SQL transactions; returns dictionary-mapped query recordsets.")
    add_figure(doc, "dfd_level_0.png", "Figure 3.2: Level 0 Context Data Flow Diagram (DFD)")

    doc.add_heading("3.2.2 Level 1 DFD (Decomposed System Processes)", level=3)
    add_body_p(doc, "The Level 1 DFD partitions the system into six core functional sub-processes:")
    add_bullet_p(doc, "Process 1.0 - Authentication & Role Access Control: ", "Validates credentials against table `users`; issues signed HTTP session cookies containing user_id and role.")
    add_bullet_p(doc, "Process 2.0 - Customer & Asset Management: ", "Validates customer inputs and stores records in table `customers`; captures vehicle specifications in table `vehicles` linked via customer_id.")
    add_bullet_p(doc, "Process 3.0 - Maintenance Schedule & Countdown Engine: ", "Audits current vehicle odometers against interval thresholds in table `maintenance_schedules`. Categorizes status into Upcoming, Due Soon, or Overdue.")
    add_bullet_p(doc, "Process 4.0 - Work Order Execution & Dynamic Billing: ", "Generates invoice headers in table `service_records`, receives multi-row line items in table `service_items`, computes parts/labor/tax totals, and prints customer invoices.")
    add_bullet_p(doc, "Process 5.0 - Automated Outreach & Reminders Queue: ", "Scans overdue/due soon schedules, populates communication payloads into table `reminders`, and marks delivery statuses.")
    add_bullet_p(doc, "Process 6.0 - Telematics & Financial Reporting: ", "Aggregates revenue sums, bay occupancy counts, and vehicle status groupings into Chart.js visuals and downloadable CSV audits.")
    add_figure(doc, "dfd_level_1.png", "Figure 3.3: Level 1 Decomposed Data Flow Diagram (DFD) — Core Operational Processes")

    doc.add_heading("3.2.3 Level 2 DFD (Work Order Creation & Billing Sub-Process)", level=3)
    add_body_p(doc,
        "The Level 2 DFD details the critical billing transaction (Process 4.0):\n"
        "• Process 4.1: Technician selects vehicle asset -> System queries table `vehicles` via AJAX and auto-fills current odometer.\n"
        "• Process 4.2: Technician adds dynamic item rows -> Client-side JavaScript computes row totals, parts subtotal, labor subtotal, and 8% statutory tax.\n"
        "• Process 4.3: Technician clicks 'Save Work Order' -> POST request received by /services/create.\n"
        "• Process 4.4: App opens a database transaction, inserts into table `service_records`, extracts generated lastrowid, and batch-inserts rows into table `service_items`.\n"
        "• Process 4.5: Commits transaction and redirects to /services/<id> rendering the official tax invoice in Indian Rupees (₹)."
    )

    doc.add_heading("3.3 Entity Relationship Diagram (ERD)", level=2)
    add_body_p(doc,
        "The relational database schema comprises 7 interconnected tables enforcing referential integrity. "
        "The relational mappings and cardinality constraints are detailed in the matrix below:"
    )

    erd_headers = ["Relationship Title", "Parent Table (1)", "Child Table (M)", "Cardinality", "Foreign Key Constraint", "On Delete Rule"]
    erd_data = [
        ["Customer Owns Vehicles", "customers", "vehicles", "1 : M", "vehicles.customer_id -> customers.id", "CASCADE"],
        ["Vehicle Has Schedules", "vehicles", "maintenance_schedules", "1 : M", "maintenance_schedules.vehicle_id -> vehicles.id", "CASCADE"],
        ["Vehicle Undergoes Services", "vehicles", "service_records", "1 : M", "service_records.vehicle_id -> vehicles.id", "CASCADE"],
        ["Technician Logs Services", "users", "service_records", "1 : M", "service_records.user_id -> users.id", "SET NULL"],
        ["Service Contains Items", "service_records", "service_items", "1 : M", "service_items.service_record_id -> service_records.id", "CASCADE"],
        ["Vehicle Triggers Reminders", "vehicles", "reminders", "1 : M", "reminders.vehicle_id -> vehicles.id", "CASCADE"],
        ["Customer Receives Reminders", "customers", "reminders", "1 : M", "reminders.customer_id -> customers.id", "CASCADE"]
    ]
    create_styled_table(doc, erd_headers, erd_data, [1.4, 1.2, 1.4, 0.8, 1.5, 0.9])
    add_figure(doc, "erd_diagram.png", "Figure 3.4: Complete Entity Relationship Diagram (ERD) with 7 Relational Tables & Cardinalities", width_inches=6.2)

    doc.add_heading("3.4 Unified Modeling Language (UML) Diagrams", level=2)
    doc.add_heading("3.4.1 Use Case Specifications", level=3)
    add_bullet_p(doc, "Use Case UC-01: User Login: ", "Actors: Admin, Technician. Pre-condition: User possesses registered email and password. Normal Flow: Enter credentials -> System verifies scrypt hash -> Establishes permanent session -> Redirects to Dashboard. Alternative Flow: Invalid credentials -> Flash danger error message.")
    add_bullet_p(doc, "Use Case UC-02: Register Fleet Vehicle: ", "Actor: Admin. Pre-condition: Customer account exists. Normal Flow: Fill VIN, plate number, make, model, year, fuel type, odometer -> System enforces unique VIN/Plate -> Inserts into table `vehicles`.")
    add_bullet_p(doc, "Use Case UC-03: Create Service Work Order & Invoicing: ", "Actors: Admin, Technician. Pre-condition: Vehicle exists in database. Normal Flow: Select vehicle -> Add parts & labor rows -> Review dynamic tax calculation in ₹ -> Submit -> System commits atomic transaction -> Renders commercial printable invoice.")
    add_bullet_p(doc, "Use Case UC-04: Automated Service Audit & Reminders: ", "Actor: Admin. Normal Flow: Click 'Scan All Vehicles' -> System evaluates all maintenance schedules against current date and odometer -> Queues reminders for vehicles due within 14 days or 1,000 km.")
    add_figure(doc, "uml_usecase.png", "Figure 3.5: UML Use Case Diagram — System Roles & Operational Boundaries")

    doc.add_heading("3.4.2 Sequence Diagram: Work Order Billing Flow", level=3)
    add_body_p(doc,
        "1. Technician Browser sends GET /services/create to Flask Router.\n"
        "2. Flask Router queries MySQL for active vehicles and technicians; renders form.html.\n"
        "3. Technician selects Vehicle; Browser issues asynchronous GET /api/vehicles/<id>.\n"
        "4. Flask Controller queries db.py; returns JSON payload containing vehicle mileage and customer name.\n"
        "5. Technician inputs line-item rows; Client-side main.js recalculates ₹ parts, ₹ labor, and ₹ tax live.\n"
        "6. Technician submits form; Browser issues POST /services/create with line-item arrays.\n"
        "7. Flask Controller starts transaction; calls query_db() to insert work order header into service_records.\n"
        "8. Flask Controller loops over line-item arrays; calls query_db() to insert each part/labor row into service_items.\n"
        "9. Transaction committed successfully; Flask redirects to /services/<record_id> displaying print-ready invoice."
    )

    doc.add_page_break()

    # =============================================================
    # CHAPTER 4: SYSTEM DESIGN
    # =============================================================
    doc.add_heading("Chapter 4: System Design", level=1)

    doc.add_heading("4.1 Database Design (Physical Data Dictionaries)", level=2)
    add_body_p(doc,
        "The physical database schema `fleetsync_db` is normalized to Third Normal Form (3NF), guaranteeing data consistency, "
        "eliminating redundant storage, and enforcing integrity through foreign key cascades. "
        "Below are the complete data dictionary tables and DDL specifications for all 7 relational tables:"
    )

    # 7 Tables
    tbl_dicts = [
        ("4.1.1 Table: users (System Staff & Roles)", [
            ["id", "INT", "PK, AUTO_INCREMENT", "Unique internal user identifier"],
            ["name", "VARCHAR(100)", "NOT NULL", "Staff full name (e.g. Shailesh Dongare)"],
            ["email", "VARCHAR(150)", "NOT NULL, UNIQUE", "Staff authentication email"],
            ["password_hash", "VARCHAR(255)", "NOT NULL", "scrypt-hashed encrypted password string"],
            ["role", "ENUM", "DEFAULT 'Technician'", "'Admin', 'Technician', or 'Service Advisor'"],
            ["phone", "VARCHAR(30)", "NULL", "Contact phone number"],
            ["avatar", "VARCHAR(255)", "NULL", "Profile picture URL or avatar initials seed"],
            ["status", "ENUM", "DEFAULT 'Active'", "'Active' or 'Inactive' account status"],
            ["created_at", "TIMESTAMP", "DEFAULT CURRENT_TIMESTAMP", "Record timestamp"]
        ]),
        ("4.1.2 Table: customers (Fleet Accounts & Individual Owners)", [
            ["id", "INT", "PK, AUTO_INCREMENT", "Unique customer identifier"],
            ["name", "VARCHAR(120)", "NOT NULL, INDEXED", "Primary contact person name"],
            ["email", "VARCHAR(150)", "NOT NULL, INDEXED", "Customer communication email address"],
            ["phone", "VARCHAR(30)", "NOT NULL", "Primary mobile / contact number (+91)"],
            ["company_name", "VARCHAR(150)", "NULL", "Corporate fleet organization name"],
            ["customer_type", "ENUM", "DEFAULT 'Individual'", "'Fleet / Corporate' or 'Individual'"],
            ["address", "TEXT", "NULL", "Street premises and billing address"],
            ["city", "VARCHAR(80)", "NULL", "City location (Mumbai, New Delhi, Bengaluru, etc.)"],
            ["postal_code", "VARCHAR(20)", "NULL", "PIN / Postal code"]
        ]),
        ("4.1.3 Table: vehicles (Fleet Assets)", [
            ["id", "INT", "PK, AUTO_INCREMENT", "Internal asset primary key"],
            ["customer_id", "INT", "FK (customers.id) ON DELETE CASCADE", "Associated asset owner / fleet entity"],
            ["vin", "VARCHAR(20)", "NOT NULL, UNIQUE, INDEXED", "17-character Vehicle Identification Number"],
            ["plate_number", "VARCHAR(20)", "NOT NULL, UNIQUE, INDEXED", "RTO Registration Plate (e.g. MH-02-CW-8092)"],
            ["make", "VARCHAR(60)", "NOT NULL", "Manufacturer (Tata, Mahindra, Force, Toyota, BMW)"],
            ["model", "VARCHAR(60)", "NOT NULL", "Model name (Winger, Traveller, Bolero, Innova)"],
            ["year", "INT", "NOT NULL", "Manufacturing model year (1980 - 2030)"],
            ["color", "VARCHAR(40)", "NULL", "Exterior paint finish"],
            ["fuel_type", "ENUM", "DEFAULT 'Gasoline'", "Diesel, Gasoline, Electric, Hybrid, CNG"],
            ["vehicle_type", "ENUM", "DEFAULT 'Sedan'", "Fleet Van, Pickup Truck, SUV, Sedan, Box Truck"],
            ["current_odometer", "INT", "DEFAULT 0", "Current recorded mileage in kilometers"],
            ["status", "ENUM", "DEFAULT 'Active'", "'Active', 'In Service', 'Maintenance Due', 'Out of Service'"]
        ]),
        ("4.1.4 Table: maintenance_schedules (Preventive Service Rules)", [
            ["id", "INT", "PK, AUTO_INCREMENT", "Unique schedule rule identifier"],
            ["vehicle_id", "INT", "FK (vehicles.id) ON DELETE CASCADE", "Associated vehicle under maintenance rule"],
            ["service_name", "VARCHAR(120)", "NOT NULL", "Service checkpoint title (e.g. Oil & Filter Change)"],
            ["interval_km", "INT", "DEFAULT 5000", "Kilometer recurrence frequency threshold"],
            ["interval_months", "INT", "DEFAULT 6", "Calendar month recurrence frequency threshold"],
            ["last_service_date", "DATE", "NULL", "Date of last completed service execution"],
            ["last_service_odometer", "INT", "DEFAULT 0", "Odometer reading at last service execution"],
            ["next_due_date", "DATE", "NOT NULL, INDEXED", "Dynamically calculated upcoming due date"],
            ["next_due_odometer", "INT", "NOT NULL", "Dynamically calculated upcoming due kilometer threshold"],
            ["priority", "ENUM", "DEFAULT 'Medium'", "Severity: 'Low', 'Medium', 'High', 'Critical'"],
            ["status", "ENUM", "DEFAULT 'Upcoming'", "Dynamic state: 'Upcoming', 'Due Soon', 'Overdue'"]
        ]),
        ("4.1.5 Table: service_records (Work Order Headers)", [
            ["id", "INT", "PK, AUTO_INCREMENT", "Unique job card internal ID"],
            ["invoice_number", "VARCHAR(30)", "NOT NULL, UNIQUE, INDEXED", "Standardized invoice identifier (e.g. WO-2026-0101)"],
            ["vehicle_id", "INT", "FK (vehicles.id) ON DELETE CASCADE", "Serviced vehicle asset"],
            ["user_id", "INT", "FK (users.id) ON DELETE SET NULL", "Assigned service technician"],
            ["service_date", "DATE", "NOT NULL, INDEXED", "Date service was conducted"],
            ["odometer", "INT", "NOT NULL", "Odometer logged at check-in"],
            ["service_type", "VARCHAR(100)", "NOT NULL", "Service category (Preventive, Brake Overhaul, etc.)"],
            ["status", "ENUM", "DEFAULT 'In Progress'", "'Pending', 'In Progress', 'Waiting for Parts', 'Completed'"],
            ["technician_notes", "TEXT", "NULL", "Technical diagnostic observations and repair notes"],
            ["parts_cost", "DECIMAL(10,2)", "DEFAULT 0.00", "Subtotal of parts and consumables in ₹ INR"],
            ["labor_cost", "DECIMAL(10,2)", "DEFAULT 0.00", "Subtotal of technician labor charges in ₹ INR"],
            ["tax_amount", "DECIMAL(10,2)", "DEFAULT 0.00", "Calculated statutory tax (8%) in ₹ INR"],
            ["total_cost", "DECIMAL(10,2)", "DEFAULT 0.00", "Grand total billed invoice amount in ₹ INR"],
            ["payment_status", "ENUM", "DEFAULT 'Unpaid'", "'Unpaid', 'Partially Paid', 'Paid'"]
        ]),
        ("4.1.6 Table: service_items (Parts & Labor Detail)", [
            ["id", "INT", "PK, AUTO_INCREMENT", "Unique line item identifier"],
            ["service_record_id", "INT", "FK (service_records.id) ON DELETE CASCADE", "Parent work order job card"],
            ["item_type", "ENUM", "DEFAULT 'Part'", "Category: 'Part', 'Labor', 'Inspection', 'Fee'"],
            ["item_name", "VARCHAR(150)", "NOT NULL", "Item description (e.g. Castrol MAGNATEC 5W-30)"],
            ["quantity", "DECIMAL(8,2)", "DEFAULT 1.00", "Quantity or labor hours billed"],
            ["unit_price", "DECIMAL(10,2)", "DEFAULT 0.00", "Unit rate per item / hour in ₹ INR"],
            ["total_price", "DECIMAL(10,2)", "DEFAULT 0.00", "Computed line total (quantity × unit_price) in ₹ INR"]
        ]),
        ("4.1.7 Table: reminders (Communication Audit Queue)", [
            ["id", "INT", "PK, AUTO_INCREMENT", "Unique reminder notification ID"],
            ["vehicle_id", "INT", "FK (vehicles.id) ON DELETE CASCADE", "Target vehicle requiring maintenance outreach"],
            ["customer_id", "INT", "FK (customers.id) ON DELETE CASCADE", "Recipient customer profile"],
            ["schedule_id", "INT", "FK (schedules.id) ON DELETE SET NULL", "Triggering maintenance rule"],
            ["reminder_type", "ENUM", "DEFAULT 'Service Due'", "'Service Due', 'Inspection Expiry', 'Custom Alert'"],
            ["channel", "ENUM", "DEFAULT 'Email'", "Dispatch channel: 'Email', 'SMS', 'WhatsApp'"],
            ["status", "ENUM", "DEFAULT 'Scheduled'", "Status: 'Scheduled', 'Sent', 'Failed', 'Cancelled'"],
            ["message_preview", "TEXT", "NOT NULL", "Formatted communication payload text"]
        ])
    ]

    for title, rows in tbl_dicts:
        doc.add_heading(title, level=3)
        create_styled_table(doc, ["Column Name", "Data Type", "Constraints", "Description"], rows, [1.2, 1.4, 1.8, 2.5])

    doc.add_heading("4.2 Input Design & Its Samples", level=2)
    add_body_p(doc,
        "Input interfaces are designed following progressive disclosure, strong client/server validation, "
        "and clear contextual placeholders:"
    )
    add_bullet_p(doc, "Authentication Screen (/login): ", "Includes email verification, password masking, remember-me token, and quick-fill buttons for instant testing.")
    add_bullet_p(doc, "Vehicle Asset Entry (/vehicles/create): ", "Validates 17-character VIN, Indian RTO registration pattern (e.g. MH-02-CW-8092), model year range (1980 - 2030), and current odometer.")
    add_bullet_p(doc, "Interactive Work Order Entry (/services/create): ", "Dynamic AJAX form; selecting a vehicle fetches its current odometer and customer details. Technicians dynamically add line-item rows specifying item type, part description, quantity, and unit price in ₹. JavaScript recalculates sub-totals live.")

    doc.add_heading("4.3 Output Design (On Screen & Print)", level=2)
    add_body_p(doc,
        "System outputs are structured for high readability, operational speed, and official financial presentation:"
    )
    add_bullet_p(doc, "Command Center Telematics Dashboard: ", "Real-time KPI cards for Active Vehicles, Bay Work Orders, Due Services, and Total Billed Revenue in ₹. Features Chart.js visualizations for fleet status distribution and service type revenue.")
    add_bullet_p(doc, "Commercial Tax Invoice Screen (/services/<id>): ", "A print-ready invoice layout optimized with @media print CSS rules. Features the workshop branding header, invoice number, customer/vehicle metadata, itemized parts and labor table in ₹, 8% statutory tax calculation, and authorized customer signature blocks.")
    add_bullet_p(doc, "Preventive Maintenance Schedule Board (/schedules): ", "Features color-coded priority pills ('Critical', 'High', 'Medium', 'Low') and dynamic countdown badges ('Upcoming', 'Due Soon', 'Overdue').")

    doc.add_page_break()

    # =============================================================
    # CHAPTER 5: IMPLEMENTATION
    # =============================================================
    doc.add_heading("Chapter 5: Implementation", level=1)

    doc.add_heading("5.1 System Requirements", level=2)
    doc.add_heading("5.1.1 Hardware Requirements", level=3)
    hw_h = ["Hardware Component", "Minimum Workshop Spec", "Recommended Enterprise Production Spec"]
    hw_d = [
        ["Processor (CPU)", "Intel Core i3 / AMD Ryzen 3 (Dual-Core 2.0 GHz)", "Intel Core i5 / AMD Ryzen 5 (Quad-Core 3.0 GHz+)"],
        ["System Memory (RAM)", "4 GB DDR3 / DDR4", "8 GB to 16 GB DDR4 high-speed RAM"],
        ["Storage Space", "2 GB available hard drive space", "20 GB SSD storage for database tables & vehicle imagery"],
        ["Display Resolution", "1280 x 720 (HD)", "1920 x 1080 (Full HD) responsive workstation display"],
        ["Network Interface", "Standard Wi-Fi / Ethernet (10 Mbps)", "100/1000 Mbps Gigabit Ethernet LAN"]
    ]
    create_styled_table(doc, hw_h, hw_d, [1.5, 2.7, 2.7])

    doc.add_heading("5.1.2 Software Requirements", level=3)
    sw_h = ["Software Category", "Environment / Technology", "Supported / Target Version"]
    sw_d = [
        ["Operating System", "Microsoft Windows 10 / 11, Ubuntu Linux 20.04+, macOS", "64-bit Architecture"],
        ["Backend Runtime", "Python", "Version 3.10, 3.11, 3.12, 3.13, 3.14"],
        ["Web Framework", "Flask (WSGI compliant micro-framework)", "Version 3.1.x"],
        ["Database Management System", "MySQL Community Server (via XAMPP)", "Version 8.0+ / MariaDB 10.4+"],
        ["Database Driver", "mysql-connector-python", "Version 9.x (pure-Python implementation)"],
        ["Client Web Browser", "Google Chrome, Microsoft Edge, Mozilla Firefox, Safari", "Latest modern HTML5 / ES6 compatible browser"]
    ]
    create_styled_table(doc, sw_h, sw_d, [1.5, 2.7, 2.7])

    doc.add_heading("5.2 Installation Process & Environment Configuration", level=2)
    add_body_p(doc, "Execute the following sequential deployment steps to initialize and launch FleetSync:")
    add_bullet_p(doc, "Step 1: Install Python Dependencies: ", "Open a terminal in the project root directory and execute:\n   pip install -r requirements.txt")
    add_bullet_p(doc, "Step 2: Start MySQL Service in XAMPP: ", "Open the XAMPP Control Panel and click 'Start' next to MySQL. Ensure port 3306 is active in green.")
    add_bullet_p(doc, "Step 3: Automated Database Schema Setup: ", "Run the database setup and seeder script:\n   python setup_db.py\n   This automatically connects to MySQL, creates `fleetsync_db`, executes `schema.sql`, builds all 7 tables, and seeds authentic Indian fleet data.")
    add_bullet_p(doc, "Step 4: Launch Web Server: ", "Start the Flask application server:\n   python app.py\n   The application initializes connection health checks and binds to http://127.0.0.1:5000.")
    add_bullet_p(doc, "Step 5: Access the Web Application: ", "Open your browser and navigate to http://127.0.0.1:5000.")

    doc.add_heading("5.3 User Guidelines (Role-Based Operation)", level=2)
    add_body_p(doc, bold_prefix="System Administrator Guidelines (Shailesh Dongare | admin@fleetsync.io):")
    add_bullet_p(doc, "Access & Privileges: ", "Full system control. Access to dashboard financial KPI metrics, user account provisioning, database health monitors, and full CRUD on vehicles and customers.")
    add_bullet_p(doc, "Financial Auditing: ", "View cumulative revenue in ₹ INR, monthly revenue breakdowns, and export complete service history records to raw CSV.")
    add_bullet_p(doc, "Automated Reminder Scanning: ", "Navigate to Reminders and click 'Scan & Generate Reminders' to audit all fleet schedules and queue automated outreach payloads.")

    add_body_p(doc, bold_prefix="\nService Technician Guidelines (Suresh Verma | tech@fleetsync.io):")
    add_bullet_p(doc, "Access & Privileges: ", "Bay-level operational execution. Access to vehicle service histories, maintenance countdowns, and work order creation.")
    add_bullet_p(doc, "Job Card Execution: ", "Open assigned work orders, update vehicle odometer readings, add itemized parts used and labor hours billed, and transition job status from 'In Progress' to 'Waiting for Parts' or 'Completed'.")
    add_bullet_p(doc, "Invoice Printing: ", "Upon completion, open the service detail view and print the commercial tax invoice in ₹ INR for the customer.")

    doc.add_page_break()

    # =============================================================
    # CHAPTER 6: REPORTS (WITH VALID DATA)
    # =============================================================
    doc.add_heading("Chapter 6: Reports (with valid Data)", level=1)
    add_body_p(doc,
        "The following tables represent real, validated data generated by FleetSync reflecting Indian automotive operations, "
        "regional fleet logistics companies, and financial totals computed in Indian Rupees (₹ INR):"
    )

    doc.add_heading("6.1 Customer & Corporate Fleet Account Directory", level=2)
    c_h = ["ID", "Customer Name", "Company / Fleet Organization", "City", "Contact Number", "Account Type"]
    c_d = [
        ["1", "Ananya Deshmukh", "Apex Logistics India Pvt Ltd", "Mumbai", "+91 98210 12345", "Fleet / Corporate"],
        ["2", "Rohan Kapoor", "Metro Fast Express Logistics Ltd", "New Delhi", "+91 98112 34567", "Fleet / Corporate"],
        ["3", "Pooja Iyer", "Individual Client", "Bengaluru", "+91 98450 98765", "Individual Client"],
        ["4", "Vikram Malhotra", "Horizon National Transport Carriers", "Ahmedabad", "+91 98791 43210", "Fleet / Corporate"],
        ["5", "Arjun Nair", "Individual Client", "Hyderabad", "+91 98490 54321", "Individual Client"]
    ]
    create_styled_table(doc, c_h, c_d, [0.5, 1.4, 2.0, 1.0, 1.1, 0.9])

    doc.add_heading("6.2 Active Fleet Asset & Odometer Audit Report", level=2)
    v_h = ["ID", "Plate Number", "Make & Model", "Year", "Fuel Type", "Current Odometer", "Status"]
    v_d = [
        ["1", "MH-02-CW-8092", "Tata Winger Maxi Van", "2023", "Diesel", "48,250 km", "Active"],
        ["2", "MH-02-CW-8093", "Mahindra Bolero Maxi Truck Plus", "2023", "Diesel", "52,100 km", "Maintenance Due"],
        ["3", "DL-01-AX-4011", "Force Motors Traveller 3350", "2024", "Diesel", "31,500 km", "In Service"],
        ["4", "DL-01-AX-4012", "Force Motors Traveller Cargo", "2022", "Diesel", "74,800 km", "Active"],
        ["5", "KA-03-MY-9921", "Toyota Innova HyCross Hybrid", "2024", "Hybrid", "18,400 km", "Active"],
        ["6", "KA-03-NB-3301", "BMW 330i Gran Limousine M Sport", "2023", "Gasoline", "24,100 km", "Active"],
        ["7", "GJ-01-ZZ-7019", "Eicher Pro 2049 Box Truck", "2021", "Diesel", "112,400 km", "Maintenance Due"],
        ["8", "TS-09-UB-5541", "Mahindra Scorpio-N 4Xplor", "2022", "Diesel", "41,200 km", "Active"]
    ]
    create_styled_table(doc, v_h, v_d, [0.4, 1.2, 1.9, 0.6, 0.8, 1.1, 0.9])

    doc.add_heading("6.3 Work Orders & Itemized Billing Invoice Report (₹ INR)", level=2)
    wo_h = ["Invoice #", "Vehicle Plate", "Customer", "Service Type", "Parts (₹)", "Labor (₹)", "Total (₹)", "Payment"]
    wo_d = [
        ["WO-2026-0101", "MH-02-CW-8092", "Ananya Deshmukh", "Preventive Maintenance", "₹4,300.00", "₹1,500.00", "₹6,264.00", "Paid"],
        ["WO-2026-0102", "MH-02-CW-8093", "Ananya Deshmukh", "Tire Replacement", "₹30,000.00", "₹2,000.00", "₹34,560.00", "Paid"],
        ["WO-2026-0103", "DL-01-AX-4011", "Rohan Kapoor", "Brake System Overhaul", "₹11,000.00", "₹2,500.00", "₹14,580.00", "Unpaid"],
        ["WO-2026-0104", "KA-03-MY-9921", "Pooja Iyer", "Warranty Inspection", "₹3,500.00", "₹1,800.00", "₹5,724.00", "Paid"],
        ["WO-2026-0105", "GJ-01-ZZ-7019", "Vikram Malhotra", "Commercial DPF Burn", "₹10,300.00", "₹4,200.00", "₹15,660.00", "Paid"],
        ["WO-2026-0106", "TS-09-UB-5541", "Arjun Nair", "Suspension Alignment", "₹3,200.00", "₹2,400.00", "₹6,048.00", "Paid"],
        ["WO-2026-0107", "MH-02-CW-8093", "Ananya Deshmukh", "Brake Sensor Module", "₹7,800.00", "₹2,200.00", "₹10,800.00", "Unpaid"]
    ]
    create_styled_table(doc, wo_h, wo_d, [1.0, 1.1, 1.2, 1.4, 0.7, 0.7, 0.8, 0.5])

    doc.add_heading("6.4 Preventive Maintenance Countdown & Service Schedule Report", level=2)
    s_h = ["Vehicle Plate", "Maintenance Task", "Next Due Date", "Due Odometer", "Priority", "Status"]
    s_d = [
        ["MH-02-CW-8092", "Synthetic Engine Oil & Filter Change", "Nov 15, 2026", "48,000 km", "High", "Due Soon"],
        ["MH-02-CW-8093", "Ceramic Brake Pads Replacement", "Sep 10, 2026", "52,000 km", "Critical", "Overdue"],
        ["DL-01-AX-4011", "Comprehensive 30k Inspection", "Oct 20, 2026", "31,000 km", "High", "Due Soon"],
        ["DL-01-AX-4012", "Transmission Fluid & Filter Flush", "Nov 01, 2026", "75,000 km", "Medium", "Upcoming"],
        ["KA-03-MY-9921", "Hybrid Battery Air Intake Cleaning", "Oct 12, 2026", "20,000 km", "Low", "Upcoming"],
        ["GJ-01-ZZ-7019", "Commercial Diesel DPF Regeneration", "Sep 01, 2026", "112,000 km", "Critical", "Overdue"]
    ]
    create_styled_table(doc, s_h, s_d, [1.2, 2.0, 1.0, 1.1, 0.8, 0.8])

    doc.add_page_break()

    # =============================================================
    # CHAPTER 7: CONCLUSION AND SUGGESTIONS
    # =============================================================
    doc.add_heading("Chapter 7: Conclusion and Suggestions", level=1)

    doc.add_heading("7.1 Conclusion", level=2)
    add_body_p(doc,
        "The FleetSync™ Vehicle Service & Fleet Maintenance Management System was successfully designed, developed, "
        "and validated to solve the operational inefficiencies and financial inaccuracies plaguing traditional automotive workshops. "
        "By replacing manual paper slips and unstructured spreadsheets with an enterprise relational web platform, "
        "the project has achieved its principal engineering milestones:"
    )
    add_bullet_p(doc, "Zero Unplanned Breakdowns: ", "The dual-trigger countdown engine dynamically correlates accumulated kilometers with elapsed calendar days, ensuring commercial fleets undergo servicing before mechanical failure occurs.")
    add_bullet_p(doc, "Transparent Itemized Billing: ", "The in-browser JavaScript billing calculator automates parts and labor pricing in Indian Rupees (₹), computes 8% statutory tax, and produces professional commercial tax invoices.")
    add_bullet_p(doc, "High Operational Velocity: ", "Real-time bay occupancy indicators and indexed database queries enable instant retrieval of vehicle histories and rapid work order turnaround.")
    add_bullet_p(doc, "Enterprise Security & Integrity: ", "Protected endpoints with scrypt password encryption ensure strict role-based separation between administrators and workshop mechanics.")

    doc.add_heading("7.2 Limitations", level=2)
    add_body_p(doc, "While FleetSync delivers an enterprise-ready feature suite, the current release exhibits the following constraints:")
    add_bullet_p(doc, "1. Manual Odometer Verification: ", "Mileage logs currently depend on technicians entering vehicle odometer readings at workshop check-in rather than automated real-time hardware telemetry.")
    add_bullet_p(doc, "2. Simulated SMS/WhatsApp Gateway: ", "Customer reminder dispatches via SMS and WhatsApp are currently simulated and recorded in database audit logs rather than integrated with commercial paid telecom SMS aggregators (Twilio, Gupshup).")
    add_bullet_p(doc, "3. Single-Server On-Premise Deployment: ", "The default deployment is optimized for local workshop area networks (LAN / XAMPP) rather than distributed multi-region cloud clusters.")

    doc.add_heading("7.3 Suggestions for Future Enhancements", level=2)
    add_body_p(doc, "The following roadmap enhancements are recommended for future versions of FleetSync:")
    add_bullet_p(doc, "1. Cellular OBD-II / IoT Telematics Integration: ", "Equip fleet vehicles with cellular OBD-II dongles streaming live GPS locations, engine error trouble codes (DTCs), and automated odometer readings over MQTT/WebSockets.")
    add_bullet_p(doc, "2. Integrated Payment Gateway (UPI / QR): ", "Incorporate Razorpay and dynamic UPI QR codes directly onto printed customer invoices for instant smartphone settlement via Google Pay, PhonePe, and Net Banking.")
    add_bullet_p(doc, "3. AI Predictive Component Failure Models: ", "Implement Machine Learning algorithms analyzing driving severity, route topography, and vehicle age to predict mechanical component failures before symptoms emerge.")
    add_bullet_p(doc, "4. Dedicated Mobile PWA with Barcode Scanner: ", "Develop a Progressive Web Application (PWA) with camera-based VIN/Plate scanning allowing technicians to pull vehicle records instantly on shop floor smartphones.")

    doc.add_page_break()

    # =============================================================
    # CHAPTER 8: ANNEXURE
    # =============================================================
    doc.add_heading("Chapter 8: Annexure", level=1)

    doc.add_heading("8.1 References", level=2)
    add_bullet_p(doc, "1. Python Software Foundation: ", "Python 3.14 Language Specification & Standard Library (https://docs.python.org/3/)")
    add_bullet_p(doc, "2. Pallets Projects: ", "Flask Web Development Framework Documentation, Version 3.1 (https://flask.palletsprojects.com/)")
    add_bullet_p(doc, "3. Oracle Corporation: ", "MySQL 8.0 Reference Manual & InnoDB Storage Architecture (https://dev.mysql.com/doc/)")
    add_bullet_p(doc, "4. Bootstrap Community: ", "Bootstrap 5.3 Responsive Front-End Framework (https://getbootstrap.com/)")
    add_bullet_p(doc, "5. Chart.js Team: ", "Chart.js HTML5 Interactive Visualization API (https://www.chartjs.org/)")
    add_bullet_p(doc, "6. Pressman, R. S.: ", "Software Engineering: A Practitioner's Approach, McGraw-Hill Higher Education, 9th Edition.")

    doc.add_heading("8.2 Internship Joining Report", level=2)
    join_tbl = doc.add_table(rows=7, cols=2)
    join_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_full_grid(join_tbl, color="94A3B8", sz="6")
    j_data = [
        ("Student / Intern Name", "Shailesh Dongare"),
        ("College Department", "Department of Computer Engineering / Information Technology"),
        ("Host Organization", "FleetSync Technologies Pro"),
        ("Project Assigned", "FleetSync — Vehicle Service & Fleet Maintenance Tracker"),
        ("Internship Role", "Full Stack Python Web Development Intern"),
        ("Date of Joining", "01 August 2026"),
        ("Industry Guide / Mentor", "Engineering Lead, FleetSync Technologies Pro")
    ]
    for idx, (lbl, val) in enumerate(j_data):
        r0 = join_tbl.rows[idx].cells[0]
        r1 = join_tbl.rows[idx].cells[1]
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

    doc.add_heading("8.3 Weekly Progress Reports (Milestones)", level=2)
    prog_h = ["Week", "Duration", "Technical Tasks Accomplished", "Status / Guide Sign"]
    prog_d = [
        ["Week 1-2", "Aug 01 - Aug 14", "Problem formulation, literature review, existing system analysis & requirement gathering", "Completed [Approved]"],
        ["Week 3-4", "Aug 15 - Aug 28", "System architecture design, DFD Level 0/1/2 synthesis, and 3NF MySQL relational schema formulation", "Completed [Approved]"],
        ["Week 5-6", "Aug 29 - Sep 11", "Backend Flask API routing development, database connection pooling, and scrypt authentication guards", "Completed [Approved]"],
        ["Week 7-8", "Sep 12 - Sep 25", "Frontend UI design using Bootstrap 5.3, responsive layouts, dynamic JavaScript line-item billing calculator", "Completed [Approved]"],
        ["Week 9-10", "Sep 26 - Oct 09", "Preventive maintenance dual-trigger interval engine implementation and reminder staging module", "Completed [Approved]"],
        ["Week 11-12", "Oct 10 - Oct 25", "Indian region localization (₹ INR, fleet vehicles), integration testing, report generation, and final documentation", "Completed [Approved]"]
    ]
    create_styled_table(doc, prog_h, prog_d, [0.8, 1.3, 3.6, 1.2])

    doc.add_heading("8.4 Student Guide Meet Record", level=2)
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

    filename = "FleetSync_Complete_Project_Report_Editable.docx"
    try:
        doc.save(filename)
        print(f"[SUCCESS] Generated complete, large, editable project report: {filename}")
    except PermissionError:
        alt_filename = "FleetSync_Complete_Project_Report_With_Diagrams.docx"
        doc.save(alt_filename)
        print(f"[SUCCESS] File was locked in Word; saved with diagrams to: {alt_filename}")

if __name__ == '__main__':
    build_report()

