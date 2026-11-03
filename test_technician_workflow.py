import sys
from app import app
from db import query_db
from werkzeug.security import generate_password_hash

def run_technician_tests():
    print("=" * 75)
    print("STARTING END-TO-END TECHNICIAN PANEL & WORKFLOW VERIFICATION SUITE")
    print("=" * 75)

    client = app.test_client()

    # Ensure baseline technician exists
    tech = query_db("SELECT * FROM users WHERE email = 'tech@fleetsync.io'", one=True)
    if not tech:
        pwd_hash = generate_password_hash("Tech@123")
        tech_id = query_db("""
            INSERT INTO users (name, email, password_hash, role, status, technician_code, skills, specialization, availability_status)
            VALUES ('Suresh Verma', 'tech@fleetsync.io', %s, 'Technician', 'Active', 'TECH-101', 'Engine, Transmission, Diagnostics', 'Powertrain Specialist', 'Available')
        """, (pwd_hash,), commit=True)
        print(f"Created baseline technician Suresh Verma (ID {tech_id})")
    else:
        tech_id = tech['id']
        # Reset password to known default if changed
        pwd_hash = generate_password_hash("Tech@123")
        query_db("UPDATE users SET password_hash = %s, availability_status = 'Available' WHERE id = %s", (pwd_hash, tech_id), commit=True)

    # Ensure secondary technician exists for authorization tests
    tech2 = query_db("SELECT * FROM users WHERE email = 'amit.tech@fleetsync.io'", one=True)
    if not tech2:
        pwd_hash = generate_password_hash("Tech@123")
        tech2_id = query_db("""
            INSERT INTO users (name, email, password_hash, role, status, technician_code, skills, specialization, availability_status)
            VALUES ('Amit Sharma', 'amit.tech@fleetsync.io', %s, 'Technician', 'Active', 'TECH-102', 'Electrical, Brakes, AC Repair', 'Auto Electrical Specialist', 'Available')
        """, (pwd_hash,), commit=True)
    else:
        tech2_id = tech2['id']

    # Ensure at least one customer and vehicle exists
    cust = query_db("SELECT * FROM customers LIMIT 1", one=True)
    if not cust:
        cust_id = query_db("INSERT INTO customers (name, email, phone, address, city) VALUES ('Ramesh Patil', 'ramesh@example.com', '9876543210', '123 MG Road', 'Pune')", commit=True)
    else:
        cust_id = cust['id']

    veh = query_db("SELECT * FROM vehicles WHERE customer_id = %s LIMIT 1", (cust_id,), one=True)
    if not veh:
        veh_id = query_db("INSERT INTO vehicles (customer_id, make, model, year, plate_number, vehicle_type) VALUES (%s, 'Tata', 'Nexon EV', 2023, 'MH-12-AB-9999', 'Car')", (cust_id,), commit=True)
    else:
        veh_id = veh['id']

    # -------------------------------------------------------------
    # TEST 1: Technician Authentication & Automatic Redirection
    # -------------------------------------------------------------
    print("\n[TEST 1] Testing Technician Authentication & Automatic Redirection...")
    res = client.post('/login', data={'email': 'tech@fleetsync.io', 'password': 'Tech@123'}, follow_redirects=False)
    assert res.status_code == 302, f"Expected 302, got {res.status_code}"
    assert '/tech/dashboard' in res.headers.get('Location', ''), f"Unexpected location: {res.headers.get('Location')}"
    print("  [OK] Login redirects directly to /tech/dashboard")

    # Access tech dashboard
    res_dash = client.get('/tech/dashboard')
    assert res_dash.status_code == 200
    assert b"Technician Command Center" in res_dash.data or b"Suresh Verma" in res_dash.data
    assert b"Assigned Jobs" in res_dash.data
    print("  [OK] Technician Dashboard rendered with KPI metrics and active schedule")

    # -------------------------------------------------------------
    # TEST 2: Create Test Service Job Assigned to Technician
    # -------------------------------------------------------------
    print("\n[TEST 2] Creating Work Order assigned to Suresh Verma with Priority & Appointment...")
    # Clean up any leftover test record
    test_inv = "WO-TEST-TECH-889"
    existing_job = query_db("SELECT id FROM service_records WHERE invoice_number = %s", (test_inv,), one=True)
    if existing_job:
        query_db("DELETE FROM service_reports WHERE service_record_id = %s", (existing_job['id'],), commit=True)
        query_db("DELETE FROM part_requests WHERE service_record_id = %s", (existing_job['id'],), commit=True)
        query_db("DELETE FROM service_records WHERE id = %s", (existing_job['id'],), commit=True)

    job_id = query_db("""
        INSERT INTO service_records 
        (vehicle_id, user_id, service_type, description, status, priority, appointment_date, appointment_time, parts_cost, labor_cost, total_cost, invoice_number, payment_status, created_at)
        VALUES (%s, %s, 'Brake & Suspension Overhaul', 'Severe brake noise and front suspension vibration', 'Pending', 'High', CURDATE(), '11:00:00', 2500.00, 2000.00, 4500.00, %s, 'Unpaid', NOW())
    """, (veh_id, tech_id, test_inv), commit=True)
    assert job_id is not None
    print(f"  [OK] Service Job created with ID {job_id}, Priority: High, Appointment: Today at 11:00:00")

    # -------------------------------------------------------------
    # TEST 3: Technician Assigned Jobs Queue & Filtering
    # -------------------------------------------------------------
    print("\n[TEST 3] Testing Assigned Jobs Queue, Filters, and Search...")
    res_jobs = client.get('/tech/jobs')
    assert res_jobs.status_code == 200
    assert test_inv.encode() in res_jobs.data
    print(f"  [OK] Job {test_inv} appears in Technician's assigned jobs queue")

    # Test Status Filter
    res_filter_status = client.get('/tech/jobs?status=Pending')
    assert res_filter_status.status_code == 200
    assert test_inv.encode() in res_filter_status.data
    print("  [OK] Status filter 'Pending' successfully displayed matching job")

    # Test Priority Filter
    res_filter_prio = client.get('/tech/jobs?priority=High')
    assert res_filter_prio.status_code == 200
    assert test_inv.encode() in res_filter_prio.data
    print("  [OK] Priority filter 'High' successfully displayed matching job")

    # Test Search Query
    res_search = client.get(f'/tech/jobs?search={test_inv}')
    assert res_search.status_code == 200
    assert test_inv.encode() in res_search.data
    print("  [OK] Search filter by Invoice Number matched correctly")

    # -------------------------------------------------------------
    # TEST 4: Job Detail Workbench & Role Authorization
    # -------------------------------------------------------------
    print("\n[TEST 4] Testing Job Detail Workbench & Access Security...")
    res_detail = client.get(f'/tech/jobs/{job_id}')
    assert res_detail.status_code == 200
    assert test_inv.encode() in res_detail.data
    assert b"Brake" in res_detail.data and b"Suspension" in res_detail.data
    assert b"Call Customer" in res_detail.data or b"tel:" in res_detail.data
    assert b"Navigate" in res_detail.data or b"google.com/maps" in res_detail.data
    print("  [OK] Full Job Workbench rendered with Customer contact actions and diagnostics")

    # Create job assigned to Tech 2 and verify Tech 1 cannot access it
    job2_id = query_db("""
        INSERT INTO service_records (vehicle_id, user_id, service_type, description, status, priority, total_cost, invoice_number)
        VALUES (%s, %s, 'AC Repair', 'Gas leak', 'Pending', 'Medium', 2000.00, 'WO-TEST-OTHER-99')
    """, (veh_id, tech2_id), commit=True)
    res_unauth = client.get(f'/tech/jobs/{job2_id}', follow_redirects=True)
    assert b"You are not authorized to access this job" in res_unauth.data
    print("  [OK] Role-based isolation confirmed: Technician cannot access jobs assigned to other technicians")
    query_db("DELETE FROM service_records WHERE id = %s", (job2_id,), commit=True)

    # -------------------------------------------------------------
    # TEST 5: Job Status Lifecycle (Accepted -> In Progress -> On Hold)
    # -------------------------------------------------------------
    print("\n[TEST 5] Testing Job Status Progression (Accepted -> In Progress -> On Hold)...")
    # Transition to Accepted
    res_acc = client.post(f'/tech/jobs/{job_id}/status', data={'status': 'Accepted'}, follow_redirects=True)
    assert res_acc.status_code == 200
    job_rec = query_db("SELECT status FROM service_records WHERE id = %s", (job_id,), one=True)
    assert job_rec['status'] == 'Accepted'
    print("  [OK] Status updated to 'Accepted'")

    # Transition to In Progress
    res_inp = client.post(f'/tech/jobs/{job_id}/status', data={'status': 'In Progress'}, follow_redirects=True)
    assert res_inp.status_code == 200
    job_rec = query_db("SELECT status FROM service_records WHERE id = %s", (job_id,), one=True)
    assert job_rec['status'] == 'In Progress'
    veh_rec = query_db("SELECT status FROM vehicles WHERE id = %s", (veh_id,), one=True)
    assert veh_rec['status'] == 'In Service'
    print("  [OK] Status updated to 'In Progress' and Vehicle status updated to 'In Service'")

    # Transition to On Hold
    res_hld = client.post(f'/tech/jobs/{job_id}/status', data={'status': 'On Hold'}, follow_redirects=True)
    assert res_hld.status_code == 200
    job_rec = query_db("SELECT status FROM service_records WHERE id = %s", (job_id,), one=True)
    assert job_rec['status'] == 'On Hold'
    print("  [OK] Status updated to 'On Hold'")

    # Test Attempt to Complete without Report (Must be blocked and redirected to Report Form)
    res_comp_block = client.post(f'/tech/jobs/{job_id}/status', data={'status': 'Completed'}, follow_redirects=False)
    assert res_comp_block.status_code == 302
    assert f'/tech/jobs/{job_id}/report' in res_comp_block.headers.get('Location', '')
    print("  [OK] Completion Guard Verified: Direct completion blocked, redirected to mandatory Service Report form")

    # -------------------------------------------------------------
    # TEST 6: Technician Spare Parts Requisition & Department Fulfillment
    # -------------------------------------------------------------
    print("\n[TEST 6] Testing Spare Parts Requisition & Fulfillment Lifecycle...")
    # Find or create a catalog spare part
    part = query_db("SELECT * FROM spare_parts LIMIT 1", one=True)
    if not part:
        part_id = query_db("""
            INSERT INTO spare_parts (part_number, part_name, category, quantity, unit_price)
            VALUES ('BRK-PAD-101', 'Ceramic Front Brake Pads', 'Brakes', 10, 1850.00)
        """, commit=True)
        part = query_db("SELECT * FROM spare_parts WHERE id = %s", (part_id,), one=True)

    # Technician requisitions spare part
    res_req = client.post(f'/tech/jobs/{job_id}/request-part', data={
        'part_id': part['id'],
        'part_name': part['part_name'],
        'part_number': part['part_number'],
        'quantity_requested': '2',
        'priority': 'Urgent',
        'technician_notes': 'Rotors damaged, requires ceramic brake pad set'
    }, follow_redirects=True)
    assert res_req.status_code == 200
    assert b"dispatched to Spare Parts Department" in res_req.data

    # Verify part request was recorded
    req_rec = query_db("SELECT * FROM part_requests WHERE service_record_id = %s ORDER BY id DESC LIMIT 1", (job_id,), one=True)
    assert req_rec is not None
    assert req_rec['quantity_requested'] == 2
    assert req_rec['status'] == 'Waiting for Parts'
    req_id = req_rec['id']
    print(f"  [OK] Requisition #{req_id} generated. Job status shifted to 'Waiting for Parts'")

    # Test Duplicate Submission Guard
    res_dup = client.post(f'/tech/jobs/{job_id}/request-part', data={
        'part_id': part['id'],
        'part_name': part['part_name'],
        'part_number': part['part_number'],
        'quantity_requested': '2'
    }, follow_redirects=True)
    assert b"already pending" in res_dup.data
    print("  [OK] Duplicate requisition prevention handled correctly")

    # Login as Spare Parts Department to Approve and Issue
    client.get('/logout')
    client.post('/login', data={'email': 'parts@fleetsync.io', 'password': 'Parts@123'}, follow_redirects=True)
    
    # Spare parts department approves
    res_approve = client.post(f'/parts/requests/{req_id}/approve', data={
        'parts_dept_notes': 'Stock verified in Rack A2. Ready for pickup.'
    }, follow_redirects=True)
    assert res_approve.status_code == 200
    req_rec = query_db("SELECT status FROM part_requests WHERE id = %s", (req_id,), one=True)
    assert req_rec['status'] == 'Part Available'
    print("  [OK] Spare Parts Dept approved request (Status -> Part Available)")

    # Spare parts department marks issued
    res_issue = client.post(f'/parts/requests/{req_id}/issue', follow_redirects=True)
    assert res_issue.status_code == 200
    req_rec = query_db("SELECT status FROM part_requests WHERE id = %s", (req_id,), one=True)
    assert req_rec['status'] == 'Issued'
    print("  [OK] Spare Parts Dept issued part to technician (Status -> Issued)")

    # -------------------------------------------------------------
    # TEST 7: Appointment Reschedule Request & Admin Approval
    # -------------------------------------------------------------
    print("\n[TEST 7] Testing Appointment Rescheduling & Admin Approval...")
    # Login back as technician
    client.get('/logout')
    client.post('/login', data={'email': 'tech@fleetsync.io', 'password': 'Tech@123'}, follow_redirects=True)

    # Submit reschedule request
    res_resched = client.post(f'/tech/jobs/{job_id}/reschedule', data={
        'reschedule_date': '2026-11-05',
        'reschedule_time': '14:30:00',
        'reschedule_reason': 'Awaiting specialized calibration torque wrench'
    }, follow_redirects=True)
    assert res_resched.status_code == 200
    assert b"Reschedule request submitted" in res_resched.data
    job_rec = query_db("SELECT reschedule_requested, reschedule_date, reschedule_reason FROM service_records WHERE id = %s", (job_id,), one=True)
    assert job_rec['reschedule_requested'] == 1
    assert str(job_rec['reschedule_date']) == '2026-11-05'
    print("  [OK] Reschedule request submitted with date and reason")

    # Login as Admin to approve reschedule
    client.get('/logout')
    client.post('/login', data={'email': 'admin@fleetsync.io', 'password': 'Admin@123'}, follow_redirects=True)
    res_approve_sched = client.post(f'/services/{job_id}/reschedule-action', data={'action': 'approve'}, follow_redirects=True)
    assert res_approve_sched.status_code == 200
    job_rec = query_db("SELECT appointment_date, appointment_time, reschedule_requested FROM service_records WHERE id = %s", (job_id,), one=True)
    assert str(job_rec['appointment_date']) == '2026-11-05'
    assert job_rec['reschedule_requested'] == 0
    print("  [OK] Admin approved reschedule. Work order schedule updated to 2026-11-05 14:30:00")

    # Admin sends direct message to Technician
    res_msg = client.post(f'/services/{job_id}/send-tech-message', data={'message': 'Please calibrate before road test.'}, follow_redirects=True)
    assert res_msg.status_code == 200
    print("  [OK] Admin dispatched direct message to Technician")

    # -------------------------------------------------------------
    # TEST 8: Official Certified Service Report Submission
    # -------------------------------------------------------------
    print("\n[TEST 8] Testing Official Certified Service Report Filing & Job Completion...")
    # Login back as technician
    client.get('/logout')
    client.post('/login', data={'email': 'tech@fleetsync.io', 'password': 'Tech@123'}, follow_redirects=True)

    # Load report form
    res_rep_form = client.get(f'/tech/jobs/{job_id}/report')
    assert res_rep_form.status_code == 200
    assert b"Official Vehicle Service & Inspection Report" in res_rep_form.data or b"Submit Official Service Report" in res_rep_form.data

    # Submit report
    res_rep_post = client.post(f'/tech/jobs/{job_id}/report', data={
        'diagnosis': 'Front brake pads worn to 1.5mm causing rotor scouring. Caliper slide pins seized.',
        'work_performed': 'Replaced front ceramic brake pads, resurfaced disc rotors, lubricated caliper slide pins, bled hydraulic system.',
        'solution_provided': 'Clean braking achieved with zero judder or noise. Brake pedal travel restored to OEM specs.',
        'parts_used_summary': '2x Ceramic Front Brake Pads (BRK-PAD-101), 500ml DOT4 Brake Fluid',
        'remarks': 'Recommended rear pad inspection at next 10,000 km interval.',
        'completion_date': '2026-11-01',
        'final_odometer': '45200'
    }, follow_redirects=True)
    assert res_rep_post.status_code == 200
    assert b"Certified Vehicle Service" in res_rep_post.data or b"Return to Workbench" in res_rep_post.data

    # Verify database state after report submission
    job_rec = query_db("SELECT status, completed_at, odometer FROM service_records WHERE id = %s", (job_id,), one=True)
    assert job_rec['status'] == 'Completed'
    assert job_rec['odometer'] == 45200
    assert job_rec['completed_at'] is not None

    veh_rec = query_db("SELECT status, current_odometer FROM vehicles WHERE id = %s", (veh_id,), one=True)
    assert veh_rec['status'] == 'Active'

    report_rec = query_db("SELECT * FROM service_reports WHERE service_record_id = %s", (job_id,), one=True)
    assert report_rec is not None
    assert "Front brake pads worn" in report_rec['diagnosis']
    assert "Replaced front ceramic" in report_rec['work_performed']

    # Verify part request was updated to 'Used in Service'
    req_rec = query_db("SELECT status FROM part_requests WHERE id = %s", (req_id,), one=True)
    assert req_rec['status'] == 'Used in Service'
    print("  [OK] Service Report persisted, Job marked Completed, Vehicle marked Active, Parts marked 'Used in Service'")

    # Test Certified Printable Report View
    res_rep_view = client.get(f'/tech/jobs/{job_id}/report/view')
    assert res_rep_view.status_code == 200
    assert b"Certified Vehicle Service" in res_rep_view.data or b"Print / Save as PDF" in res_rep_view.data
    assert b"WORK ORDER #" in res_rep_view.data or test_inv.encode() in res_rep_view.data
    print("  [OK] Printable certified Service Report rendered successfully")

    # -------------------------------------------------------------
    # TEST 9: Customer Satisfaction Rating & Feedback
    # -------------------------------------------------------------
    print("\n[TEST 9] Testing Customer Rating & Feedback Recording...")
    res_feed = client.post(f'/tech/jobs/{job_id}/feedback', data={
        'customer_rating': '5',
        'customer_feedback': 'Brakes feel brand new! Exceptional and fast turnaround by Suresh Verma.'
    }, follow_redirects=True)
    assert res_feed.status_code == 200
    job_rec = query_db("SELECT customer_rating, customer_feedback FROM service_records WHERE id = %s", (job_id,), one=True)
    assert job_rec['customer_rating'] == 5
    assert "Exceptional and fast" in job_rec['customer_feedback']
    print("  [OK] Customer 5-star rating and positive feedback recorded in database")

    # -------------------------------------------------------------
    # TEST 10: Technician Notifications Center
    # -------------------------------------------------------------
    print("\n[TEST 10] Testing Notifications Center...")
    res_notif = client.get('/tech/notifications')
    assert res_notif.status_code == 200
    assert b"Notifications" in res_notif.data
    print("  [OK] Notifications Center rendered with event alerts")

    # -------------------------------------------------------------
    # TEST 11: Technician Profile Management & Password Change
    # -------------------------------------------------------------
    print("\n[TEST 11] Testing Technician Profile & Availability Status...")
    res_prof = client.get('/tech/profile')
    assert res_prof.status_code == 200
    assert b"Suresh Verma" in res_prof.data

    # Update profile details & availability status
    res_upd = client.post('/tech/profile', data={
        'form_type': 'update_profile',
        'name': 'Suresh Verma',
        'phone': '9811223344',
        'skills': 'Engine Tuning, Advanced Braking Systems, OBD-II Diagnostics, Hybrid Powertrain',
        'specialization': 'Senior Master Diagnostic Technician',
        'availability_status': 'Busy'
    }, follow_redirects=True)
    assert res_upd.status_code == 200
    tech_rec = query_db("SELECT * FROM users WHERE id = %s", (tech_id,), one=True)
    assert tech_rec['availability_status'] == 'Busy'
    assert tech_rec['specialization'] == 'Senior Master Diagnostic Technician'
    print("  [OK] Technician profile updated and Duty Availability Status set to 'Busy'")

    # Reset availability to Available for production cleanliness
    query_db("UPDATE users SET availability_status = 'Available' WHERE id = %s", (tech_id,), commit=True)

    # -------------------------------------------------------------
    # TEST 12: Admin & Customer Panel Visibility
    # -------------------------------------------------------------
    print("\n[TEST 12] Verifying Service Report visibility in Admin and Customer panels...")
    # Admin view
    client.get('/logout')
    client.post('/login', data={'email': 'admin@fleetsync.io', 'password': 'Admin@123'}, follow_redirects=True)
    res_admin_srv = client.get(f'/services/{job_id}')
    assert res_admin_srv.status_code == 200
    assert b"Official Certified Service Report" in res_admin_srv.data or b"Service Report" in res_admin_srv.data
    print("  [OK] Admin panel displays official service report and technician attribution")

    # Customer view
    res_cust = client.get(f'/customers/{cust_id}')
    assert res_cust.status_code == 200
    assert b"View Report" in res_cust.data
    print("  [OK] Customer profile links directly to certified service report")

    print("\n" + "=" * 75)
    print("ALL 12 TEST SUITES PASSED FLAWLESSLY! 100% SUCCESS.")
    print("=" * 75)

if __name__ == '__main__':
    run_technician_tests()
