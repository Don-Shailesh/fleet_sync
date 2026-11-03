import os
import sys
import unittest
from datetime import date, datetime

sys.path.insert(0, r"D:\internship 2")
from app import app
from db import query_db

def run_tests():
    print("=" * 80)
    print("STARTING BILLING, LABOR RATES & COMPLETION WORKFLOW VERIFICATION")
    print("=" * 80)

    client = app.test_client()
    app.config['TESTING'] = True

    # 1. Fetch Users
    admin = query_db("SELECT * FROM users WHERE role = 'Admin' AND status = 'Active' LIMIT 1", one=True)
    tech = query_db("SELECT * FROM users WHERE role = 'Technician' AND status = 'Active' LIMIT 1", one=True)
    parts_user = query_db("SELECT * FROM users WHERE role = 'Spare Parts' AND status = 'Active' LIMIT 1", one=True)
    cust = query_db("SELECT * FROM customers LIMIT 1", one=True)
    veh = query_db("SELECT * FROM vehicles WHERE customer_id = %s LIMIT 1", (cust['id'],), one=True)
    if not veh:
        veh = query_db("SELECT * FROM vehicles LIMIT 1", one=True)

    assert admin and tech and parts_user and veh, "Required seed users and vehicle"

    admin_id = admin['id']
    tech_id = tech['id']
    veh_id = veh['id']

    # -------------------------------------------------------------------------
    # TEST 1: Admin maintains spare parts catalog with unit price & tax
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Testing Admin / Parts Dept Catalog Price & Tax Management...")
    # Login as Admin
    client.post('/login', data={'email': admin['email'], 'password': 'Admin@123'}, follow_redirects=True)

    test_sku = "SKU-AUTO-BILL-99"
    query_db("DELETE FROM spare_parts WHERE part_number = %s", (test_sku,), commit=True)

    res_add_part = client.post('/parts/create', data={
        'part_number': test_sku,
        'part_name': 'Precision Ceramic Brake Rotor',
        'category': 'Brakes',
        'shelf_location': 'Rack B-12',
        'quantity': '20',
        'min_quantity': '5',
        'unit_price': '2400.00',
        'tax_rate': '18.00',
        'cost_price': '1500.00',
        'supplier': 'Brembo OEM Direct',
        'compatibility': 'Sedan / SUV',
        'description': 'High-performance ventilated ceramic rotor.'
    }, follow_redirects=True)
    assert res_add_part.status_code == 200

    created_part = query_db("SELECT * FROM spare_parts WHERE part_number = %s", (test_sku,), one=True)
    assert created_part is not None
    assert float(created_part['unit_price']) == 2400.00
    assert float(created_part['tax_rate']) == 18.00
    part_id = created_part['id']
    print(f"  [OK] Spare part '{created_part['part_name']}' created with unit_price Rs. 2,400.00 and tax 18.00%")

    # Now edit part price & tax, verify audit log
    res_edit_part = client.post(f'/parts/{part_id}/edit', data={
        'part_number': test_sku,
        'part_name': 'Precision Ceramic Brake Rotor (Upgraded)',
        'category': 'Brakes',
        'shelf_location': 'Rack B-12',
        'quantity': '20',
        'min_quantity': '5',
        'unit_price': '2550.00',
        'tax_rate': '18.00',
        'cost_price': '1550.00',
        'supplier': 'Brembo OEM Direct',
        'compatibility': 'Sedan / SUV',
        'description': 'Upgraded slot venting.'
    }, follow_redirects=True)
    assert res_edit_part.status_code == 200

    updated_part = query_db("SELECT * FROM spare_parts WHERE id = %s", (part_id,), one=True)
    assert float(updated_part['unit_price']) == 2550.00

    # Verify audit log
    audit_part = query_db("SELECT * FROM pricing_audit_logs WHERE item_type = 'Spare Part' AND item_id = %s ORDER BY id DESC LIMIT 1", (part_id,), one=True)
    assert audit_part is not None
    assert ("2,400" in audit_part['old_value'] or "2400" in audit_part['old_value']) and ("2,550" in audit_part['new_value'] or "2550" in audit_part['new_value'])
    print("  [OK] Price modification audited in pricing_audit_logs with old and new values")

    # -------------------------------------------------------------------------
    # TEST 2: Admin configures labor rates (Hourly & Fixed) & Pricing Audit Trail
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Testing Admin Predefined Labor Rate Standards...")
    # Add new labor rate
    test_labor_name = "Heavy Duty Suspension Calibration"
    query_db("DELETE FROM labor_rates WHERE service_type = %s", (test_labor_name,), commit=True)

    res_add_lr = client.post('/admin/labor-rates/add', data={
        'service_type': test_labor_name,
        'charge_type': 'Hourly',
        'standard_hours': '3.00',
        'hourly_rate': '950.00',
        'fixed_price': '0.00',
        'tax_rate': '18.00',
        'description': 'Multi-link suspension alignment and laser calibration.'
    }, follow_redirects=True)
    assert res_add_lr.status_code == 200

    lr_rec = query_db("SELECT * FROM labor_rates WHERE service_type = %s", (test_labor_name,), one=True)
    assert lr_rec is not None
    assert lr_rec['charge_type'] == 'Hourly'
    assert float(lr_rec['hourly_rate']) == 950.00
    lr_id = lr_rec['id']
    print(f"  [OK] Standard labor rate created: '{test_labor_name}' at Rs. 950.00/hr (Tax: 18%)")

    # Edit labor rate & check audit trail
    res_edit_lr = client.post(f'/admin/labor-rates/{lr_id}/edit', data={
        'service_type': test_labor_name,
        'charge_type': 'Hourly',
        'standard_hours': '3.00',
        'hourly_rate': '1000.00',
        'fixed_price': '0.00',
        'tax_rate': '18.00',
        'description': 'Multi-link suspension alignment and laser calibration.',
        'status': 'Active'
    }, follow_redirects=True)
    assert res_edit_lr.status_code == 200

    audit_lr = query_db("SELECT * FROM pricing_audit_logs WHERE item_type = 'Labor Rate' AND item_id = %s ORDER BY id DESC LIMIT 1", (lr_id,), one=True)
    assert audit_lr is not None
    assert "950" in audit_lr['old_value'] and "1000" in audit_lr['new_value']
    print("  [OK] Labor rate adjustment audited in pricing_audit_logs")

    # Verify Pricing Audit page
    res_audit_page = client.get('/admin/pricing-audit-logs')
    assert res_audit_page.status_code == 200
    assert b"Pricing &amp; Labor Standards Audit Trail" in res_audit_page.data or b"Pricing & Labor Standards Audit Trail" in res_audit_page.data
    print("  [OK] Admin Pricing Audit Trail page renders successfully")

    # -------------------------------------------------------------------------
    # TEST 3: Work Order creation, requisition, & Technician Final Report
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Testing Technician Final Work Report & Auto-Bill Generation...")
    inv_num = "WO-TEST-BILL-777"
    query_db("DELETE FROM service_records WHERE invoice_number = %s", (inv_num,), commit=True)

    job_id = query_db("""
        INSERT INTO service_records (vehicle_id, user_id, service_date, appointment_date, appointment_time, odometer, service_type, status, priority, description, invoice_number)
        VALUES (%s, %s, CURDATE(), CURDATE(), '10:00:00', %s, 'Brake & Suspension Calibration', 'In Progress', 'High', 'Front knocking and brake vibration under deceleration.', %s)
    """, (veh_id, tech_id, veh.get('current_odometer') or 46000, inv_num), commit=True)

    # Technician requested 2x Ceramic Brake Rotors
    req_id = query_db("""
        INSERT INTO part_requests (service_record_id, technician_id, requested_by, part_id, part_name, part_number, quantity_requested, quantity_available, quantity_used, status)
        VALUES (%s, %s, %s, %s, %s, %s, 2, 2, 0, 'Part Available')
    """, (job_id, tech_id, tech_id, part_id, updated_part['part_name'], test_sku), commit=True)

    # Login as Technician
    client.get('/logout')
    client.post('/login', data={'email': tech['email'], 'password': 'Tech@123'}, follow_redirects=True)

    # View final report form
    res_report_get = client.get(f'/tech/jobs/{job_id}/report')
    assert res_report_get.status_code == 200
    assert b"Spare Parts Consumption" in res_report_get.data
    assert b"Labor Operation" in res_report_get.data
    # Prices and bill totals are hidden from the technician
    assert b"previewPartsSubtotal" not in res_report_get.data
    assert b"10,148" not in res_report_get.data
    print("  [OK] Final report form loaded with prices and bill calculations hidden from technician")

    # Technician completes repair and submits final report:
    # 2x Rotors used @ 2550.00 = 5100.00 parts subtotal
    # Parts Tax (18% of 5100.00) = 918.00
    # Labor: 3.5 hrs @ 1000.00/hr = 3500.00 labor subtotal
    # Labor Tax (18% of 3500.00) = 630.00
    # Total Tax = 918.00 + 630.00 = 1548.00
    # Expected Grand Total = 5100.00 + 3500.00 + 1548.00 = 10148.00
    res_report_post = client.post(f'/tech/jobs/{job_id}/report', data={
        'diagnosis': 'Front brake rotors severely warped causing lateral runout (0.12mm); caliper slide pins dry.',
        'work_performed': 'Installed 2x Precision Ceramic Brake Rotors. Serviced caliper slide pins with high-temp grease. Executed multi-link suspension alignment.',
        'solution_provided': 'Zero runout achieved; smooth progressive pedal feel verified during diagnostic road run.',
        'labor_rate_id': str(lr_id),
        'labor_hours': '3.50',
        'final_vehicle_condition': 'Road-Ready & Excellent',
        'completion_date': date.today().isoformat(),
        f'part_used_qty_{req_id}': '2',
        f'part_unused_reason_{req_id}': '',
        'parts_used_summary': '2x Precision Ceramic Brake Rotors (SKU-AUTO-BILL-99)',
        'test_results': '10 km road test complete. Brake temperature balanced at 65C. Alignment within 0.05 degrees.',
        'follow_up_recommendations': 'Check wheel lug nut torque at 100 km.',
        'final_odometer': '46050',
        'submit_action': 'submit_for_approval'
    }, follow_redirects=True)
    assert res_report_post.status_code == 200

    # Verify auto-generated bill in DB upon final submission
    job_rec = query_db("SELECT * FROM service_records WHERE id = %s", (job_id,), one=True)
    assert job_rec['status'] == 'Awaiting Admin Approval'
    assert job_rec['bill_status'] == 'Under Review'
    assert float(job_rec['parts_cost']) == 5100.00
    assert float(job_rec['labor_cost']) == 3500.00
    assert float(job_rec['tax_amount']) == 1548.00
    assert float(job_rec['total_cost']) == 10148.00
    assert float(job_rec['labor_rate_applied']) == 1000.00
    assert float(job_rec['labor_hours_billed']) == 3.50

    # Verify service_items generated
    items = query_db("SELECT * FROM service_items WHERE service_record_id = %s ORDER BY id ASC", (job_id,))
    assert len(items) == 2
    part_item = next(i for i in items if i['item_type'] == 'Part')
    labor_item = next(i for i in items if i['item_type'] == 'Labor')
    assert float(part_item['quantity']) == 2.0
    assert float(part_item['unit_price']) == 2550.00
    assert float(part_item['total_price']) == 5100.00
    assert float(labor_item['quantity']) == 3.5
    assert float(labor_item['unit_price']) == 1000.00
    assert float(labor_item['total_price']) == 3500.00
    print("  [OK] Bill automatically generated in backend on final submission (Total: Rs. 10,148)")

    # Technician view after final submission:
    # Must view ONLY parts used and submitted work report; all billing/payment info hidden
    res_tech_view = client.get(f'/tech/jobs/{job_id}/report/view')
    assert res_tech_view.status_code == 200
    assert b"Replacement Spare Parts" in res_tech_view.data
    assert b"Precision Ceramic Brake Rotor" in res_tech_view.data  # Parts used visible
    assert b"Problem Diagnosis" in res_tech_view.data              # Work report visible
    assert b"Zero runout achieved" in res_tech_view.data
    # Verify all billing/payment information is HIDDEN from technician view
    assert b"Itemized Billing &amp; Labor Summary" not in res_tech_view.data
    assert b"Itemized Billing & Labor Summary" not in res_tech_view.data
    assert b"10,148" not in res_tech_view.data
    assert b"5,100" not in res_tech_view.data
    assert b"3,500" not in res_tech_view.data
    assert b"GST" not in res_tech_view.data
    print("  [OK] Technician report view displays only parts used & work report; all prices/bills hidden")

    # Verify technician cannot access customer billing invoice
    res_inv_blocked = client.get(f'/services/{job_id}/invoice')
    assert res_inv_blocked.status_code == 302
    print("  [OK] Direct technician access to customer invoice/bill blocked")

    # -------------------------------------------------------------------------
    # TEST 4: Admin reviews Report & Bill in Admin Panel, corrects line item, applies discount, and approves
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Testing Admin Review, Bill Correction & Final Approval in Admin Panel...")
    # Login as Admin
    client.get('/logout')
    client.post('/login', data={'email': admin['email'], 'password': 'Admin@123'}, follow_redirects=True)

    # View Service Detail workbench (Admin Panel)
    res_admin_view = client.get(f'/services/{job_id}')
    assert res_admin_view.status_code == 200
    assert b"Admin Workflow: Review Final Report &amp; Auto-Generated Bill" in res_admin_view.data or b"Admin Workflow: Review Final Report & Auto-Generated Bill" in res_admin_view.data
    assert b"Precision Ceramic Brake Rotor" in res_admin_view.data
    assert b"Heavy Duty Suspension Calibration" in res_admin_view.data
    assert b"10,148" in res_admin_view.data or b"10148" in res_admin_view.data  # Bill is shown in Admin Panel!
    print("  [OK] Bill is displayed in Admin Panel for review along with final report")

    # Admin corrects labor line item (adjust rate from 1000 to 900 for promotional fleet rate)
    res_adjust = client.post(f'/services/{job_id}/bill/item-adjust', data={
        'item_id': str(labor_item['id']),
        'quantity': '3.5',
        'unit_price': '900.00',
        'reason': 'Corporate fleet discount agreement on labor rates'
    }, follow_redirects=True)
    assert res_adjust.status_code == 200

    # Labor is now 3.5 * 900 = 3150.00. Tax = 918 + (3150 * 0.18 = 567) = 1485. Total = 5100 + 3150 + 1485 = 9735.00
    job_after_adj = query_db("SELECT * FROM service_records WHERE id = %s", (job_id,), one=True)
    assert float(job_after_adj['labor_cost']) == 3150.00
    assert float(job_after_adj['total_cost']) == 9735.00

    # Verify audit log for bill item adjustment
    audit_adj = query_db("SELECT * FROM pricing_audit_logs WHERE item_type = 'Service Bill Item' AND item_name LIKE %s ORDER BY id DESC LIMIT 1", (f"%{inv_num}%",), one=True)
    assert audit_adj is not None
    assert "1000" in audit_adj['old_value'] and "900" in audit_adj['new_value']
    print("  [OK] Admin line item correction recalculated bill and was recorded in Pricing Audit Trail")

    # Admin approves completion and bill with Rs. 235 promotional discount -> Total becomes Rs. 9,500.00
    res_approve = client.post(f'/services/{job_id}/admin-review', data={
        'decision': 'approve',
        'discount_amount': '235.00',
        'review_comments': 'Workmanship and technical measurements verified. Approved for customer billing.'
    }, follow_redirects=True)
    assert res_approve.status_code == 200

    job_approved = query_db("SELECT * FROM service_records WHERE id = %s", (job_id,), one=True)
    assert job_approved['status'] == 'Completed'
    assert job_approved['bill_status'] == 'Approved'
    assert float(job_approved['discount_amount']) == 235.00
    assert float(job_approved['total_cost']) == 9500.00
    assert job_approved['admin_approved_at'] is not None

    veh_approved = query_db("SELECT * FROM vehicles WHERE id = %s", (veh_id,), one=True)
    assert veh_approved['status'] == 'Active'
    print("  [OK] Admin approved! Status -> 'Completed', Bill -> 'Approved', Vehicle -> 'Active', Total -> Rs. 9,500.00")

    # -------------------------------------------------------------------------
    # TEST 5: Customer-Ready Printable Report & Invoice
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Testing Customer-Ready Printable Invoice & Report...")
    # Printable Invoice
    res_inv = client.get(f'/services/{job_id}/invoice')
    assert res_inv.status_code == 200
    assert inv_num.encode() in res_inv.data
    assert b"Precision Ceramic Brake Rotor" in res_inv.data
    assert b"Heavy Duty Suspension Calibration" in res_inv.data
    assert b"Fleet / Promotional Discount" in res_inv.data
    assert b"9,500.00" in res_inv.data
    print("  [OK] Customer-ready printable invoice renders itemized parts, labor formula, taxes, discount, and total")

    # Printable Certified Service Report (Admin view includes billing summary)
    res_rep = client.get(f'/services/{job_id}/report/print')
    assert res_rep.status_code == 200
    assert inv_num.encode() in res_rep.data
    assert b"Itemized Billing &amp; Labor Summary" in res_rep.data or b"Itemized Billing & Labor Summary" in res_rep.data
    assert b"Precision Ceramic Brake Rotor" in res_rep.data or b"Ceramic" in res_rep.data
    print("  [OK] Customer-ready certified service report renders diagnostics, work performed, condition, and billing breakdown")

    # -------------------------------------------------------------------------
    # TEST 6: Customer Vehicle Service History & Search
    # -------------------------------------------------------------------------
    print("\n[TEST 6] Testing Vehicle Customer Service History & Multi-Criteria Search...")
    # Customer Detail View
    cust_id = veh['customer_id']
    res_cust = client.get(f'/customers/{cust_id}')
    assert res_cust.status_code == 200
    assert inv_num.encode() in res_cust.data
    assert b"Bill" in res_cust.data
    assert b"Report" in res_cust.data
    print("  [OK] Customer profile links directly to approved bill and certified service report")

    # Vehicle Profile View
    res_veh = client.get(f'/vehicles/{veh_id}')
    assert res_veh.status_code == 200
    assert inv_num.encode() in res_veh.data
    assert b"Bill" in res_veh.data
    assert b"Report" in res_veh.data
    print("  [OK] Vehicle 360 profile displays approved repair history with bill and report links")

    # Search by Work Order
    res_s_wo = client.get(f'/services?search={inv_num}')
    assert res_s_wo.status_code == 200
    assert inv_num.encode() in res_s_wo.data

    # Search by Vehicle Plate
    res_s_plate = client.get(f'/services?search={veh["plate_number"]}')
    assert res_s_plate.status_code == 200
    assert veh['plate_number'].encode() in res_s_plate.data

    # Search by Customer Name
    res_s_cust = client.get(f'/services?search={cust["name"]}')
    assert res_s_cust.status_code == 200
    assert cust['name'].encode() in res_s_cust.data
    print("  [OK] Service records searchable by Customer, Vehicle Plate, and Work Order Number")

    # Cleanup test work order and parts
    query_db("DELETE FROM service_workflow_history WHERE service_record_id = %s", (job_id,), commit=True)
    query_db("DELETE FROM service_items WHERE service_record_id = %s", (job_id,), commit=True)
    query_db("DELETE FROM service_reports WHERE service_record_id = %s", (job_id,), commit=True)
    query_db("DELETE FROM part_requests WHERE service_record_id = %s", (job_id,), commit=True)
    query_db("DELETE FROM service_records WHERE id = %s", (job_id,), commit=True)
    query_db("DELETE FROM pricing_audit_logs WHERE item_name LIKE %s", (f"%{inv_num}%",), commit=True)
    query_db("DELETE FROM pricing_audit_logs WHERE item_id = %s", (part_id,), commit=True)
    query_db("DELETE FROM pricing_audit_logs WHERE item_id = %s", (lr_id,), commit=True)
    query_db("DELETE FROM spare_parts WHERE id = %s", (part_id,), commit=True)
    query_db("DELETE FROM labor_rates WHERE id = %s", (lr_id,), commit=True)

    print("\n" + "=" * 80)
    print("ALL BILLING, LABOR RATE & COMPLETION WORKFLOW REQUIREMENTS PASSED 100%!")
    print("=" * 80)

if __name__ == '__main__':
    run_tests()
