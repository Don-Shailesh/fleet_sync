import sys
from app import app
from db import query_db
from werkzeug.security import generate_password_hash, check_password_hash

def run_multiple_technicians_tests():
    print("=" * 75)
    print("STARTING MULTIPLE TECHNICIAN MANAGEMENT COMPREHENSIVE TEST SUITE")
    print("=" * 75)

    client = app.test_client()

    # -------------------------------------------------------------
    # 1. Admin Authentication
    # -------------------------------------------------------------
    print("\n[TEST 1] Testing Admin Login & Authorization...")
    res = client.post('/login', data={'email': 'admin@fleetsync.io', 'password': 'Admin@123'}, follow_redirects=True)
    assert res.status_code == 200
    print("  [OK] Admin successfully authenticated")

    # -------------------------------------------------------------
    # 2. View Technicians Management Roster
    # -------------------------------------------------------------
    print("\n[TEST 2] Testing Technicians Management Roster List & Filtering...")
    res_list = client.get('/admin/technicians')
    assert res_list.status_code == 200
    assert b"Technicians Management Roster" in res_list.data
    assert b"Add New Technician" in res_list.data
    assert b"Suresh Verma" in res_list.data
    print("  [OK] Technicians Management Roster rendered with existing technicians and KPI overview")

    # Test Search
    res_search = client.get('/admin/technicians?search=Suresh')
    assert res_search.status_code == 200
    assert b"Suresh Verma" in res_search.data
    print("  [OK] Search filter by name 'Suresh' returned matching technician")

    # Test Status Filter
    res_filter_act = client.get('/admin/technicians?status=Active')
    assert res_filter_act.status_code == 200
    assert b"Suresh Verma" in res_filter_act.data
    print("  [OK] Status filter 'Active' verified")

    # -------------------------------------------------------------
    # 3. Add Multiple Technicians with Unique Credentials
    # -------------------------------------------------------------
    print("\n[TEST 3] Adding Multiple New Technicians (Vikram Rao & Sneha Patil)...")
    # Clean up test accounts if previously existing
    for email in ('vikram.tech@fleetsync.io', 'sneha.tech@fleetsync.io'):
        t = query_db("SELECT id FROM users WHERE email = %s", (email,), one=True)
        if t:
            query_db("DELETE FROM notifications WHERE user_id = %s", (t['id'],), commit=True)
            query_db("DELETE FROM service_reports WHERE technician_id = %s", (t['id'],), commit=True)
            query_db("DELETE FROM part_requests WHERE technician_id = %s OR requested_by = %s", (t['id'], t['id']), commit=True)
            query_db("DELETE FROM service_records WHERE user_id = %s", (t['id'],), commit=True)
            query_db("DELETE FROM users WHERE id = %s", (t['id'],), commit=True)

    # 3A: Add Technician 1: Vikram Rao (TECH-105)
    res_add1 = client.post('/admin/technicians/create', data={
        'name': 'Vikram Rao',
        'email': 'vikram.tech@fleetsync.io',
        'phone': '+91 98220 55441',
        'address': 'Workshop Bay 2, South Garage, Pune',
        'technician_code': 'TECH-105',
        'specialization': 'Advanced Transmission & Clutch Specialist',
        'skills': 'Manual Gearbox Overhaul, Dual-Clutch Transmission, Torque Converters',
        'availability_status': 'Available',
        'password': 'TechVikram@123',
        'confirm_password': 'TechVikram@123'
    }, follow_redirects=True)
    assert res_add1.status_code == 200
    assert b"successfully registered" in res_add1.data

    tech_vikram = query_db("SELECT * FROM users WHERE email = 'vikram.tech@fleetsync.io'", one=True)
    assert tech_vikram is not None
    assert tech_vikram['technician_code'] == 'TECH-105'
    assert tech_vikram['address'] == 'Workshop Bay 2, South Garage, Pune'
    assert tech_vikram['status'] == 'Active'
    vikram_id = tech_vikram['id']
    print(f"  [OK] Technician Vikram Rao created with ID {vikram_id}, Code: TECH-105")

    # 3B: Add Technician 2: Sneha Patil (TECH-106)
    res_add2 = client.post('/admin/technicians/create', data={
        'name': 'Sneha Patil',
        'email': 'sneha.tech@fleetsync.io',
        'phone': '+91 98220 55442',
        'address': 'Workshop Bay 5, Diagnostic Lab, Pune',
        'technician_code': 'TECH-106',
        'specialization': 'Auto Electronics & EV Battery Diagnostics',
        'skills': 'High Voltage Safety, CAN Bus Diagnostics, BMS Calibration',
        'availability_status': 'Available',
        'password': 'TechSneha@123',
        'confirm_password': 'TechSneha@123'
    }, follow_redirects=True)
    assert res_add2.status_code == 200
    assert b"successfully registered" in res_add2.data

    tech_sneha = query_db("SELECT * FROM users WHERE email = 'sneha.tech@fleetsync.io'", one=True)
    assert tech_sneha is not None
    assert tech_sneha['technician_code'] == 'TECH-106'
    sneha_id = tech_sneha['id']
    print(f"  [OK] Technician Sneha Patil created with ID {sneha_id}, Code: TECH-106")

    # -------------------------------------------------------------
    # 4. Duplicate Account Prevention (Email, Phone, Code)
    # -------------------------------------------------------------
    print("\n[TEST 4] Testing Duplicate Account Prevention Guards...")
    # 4A: Duplicate Email Test
    res_dup_email = client.post('/admin/technicians/create', data={
        'name': 'Duplicate Person',
        'email': 'vikram.tech@fleetsync.io', # Already exists
        'phone': '+91 90000 11111',
        'technician_code': 'TECH-999',
        'password': 'Password@123',
        'confirm_password': 'Password@123'
    }, follow_redirects=True)
    assert b"already exists" in res_dup_email.data
    print("  [OK] Duplicate email rejected correctly")

    # 4B: Duplicate Mobile Number Test
    res_dup_phone = client.post('/admin/technicians/create', data={
        'name': 'Duplicate Phone Person',
        'email': 'new.unique@fleetsync.io',
        'phone': '+91 98220 55441', # Belongs to Vikram
        'technician_code': 'TECH-998',
        'password': 'Password@123',
        'confirm_password': 'Password@123'
    }, follow_redirects=True)
    assert b"already exists" in res_dup_phone.data
    print("  [OK] Duplicate mobile number rejected correctly")

    # 4C: Duplicate Technician Code Test
    res_dup_code = client.post('/admin/technicians/create', data={
        'name': 'Duplicate Code Person',
        'email': 'new.unique2@fleetsync.io',
        'phone': '+91 90000 22222',
        'technician_code': 'TECH-105', # Belongs to Vikram
        'password': 'Password@123',
        'confirm_password': 'Password@123'
    }, follow_redirects=True)
    assert b"already assigned" in res_dup_code.data
    print("  [OK] Duplicate technician code rejected correctly")

    # -------------------------------------------------------------
    # 5. Edit Technician Details & Change Password
    # -------------------------------------------------------------
    print("\n[TEST 5] Testing Admin Edit Technician & Credentials Update...")
    res_edit = client.post(f'/admin/technicians/{vikram_id}/edit', data={
        'name': 'Vikram S. Rao',
        'email': 'vikram.tech@fleetsync.io',
        'phone': '+91 98220 55441',
        'address': 'Main Regional Workshop Bay 1, Pune',
        'technician_code': 'TECH-105',
        'specialization': 'Lead Master Transmission Specialist',
        'skills': 'Manual, Automatic & Dual-Clutch Transmissions, Heavy Duty Gearboxes',
        'availability_status': 'Busy',
        'status': 'Active',
        'new_password': 'NewPassword@456',
        'confirm_password': 'NewPassword@456'
    }, follow_redirects=True)
    assert res_edit.status_code == 200
    assert b"details updated successfully" in res_edit.data

    upd_vikram = query_db("SELECT * FROM users WHERE id = %s", (vikram_id,), one=True)
    assert upd_vikram['name'] == 'Vikram S. Rao'
    assert upd_vikram['specialization'] == 'Lead Master Transmission Specialist'
    assert upd_vikram['availability_status'] == 'Busy'
    assert check_password_hash(upd_vikram['password_hash'], 'NewPassword@456')
    print("  [OK] Technician details and updated password verified in database")

    # -------------------------------------------------------------
    # 6. Activate & Deactivate Technician (Toggle Status)
    # -------------------------------------------------------------
    print("\n[TEST 6] Testing Activate / Deactivate (Toggle Status)...")
    # Deactivate Vikram
    res_deact = client.post(f'/admin/technicians/{vikram_id}/toggle-status', follow_redirects=True)
    assert res_deact.status_code == 200
    assert b"Deactivated" in res_deact.data
    upd_vikram = query_db("SELECT status FROM users WHERE id = %s", (vikram_id,), one=True)
    assert upd_vikram['status'] == 'Inactive'
    print("  [OK] Technician Vikram Rao deactivated (status -> Inactive)")

    # Test that Deactivated technician cannot log in
    client.get('/logout')
    res_deact_login = client.post('/login', data={'email': 'vikram.tech@fleetsync.io', 'password': 'NewPassword@456'}, follow_redirects=True)
    assert b"account has been deactivated" in res_deact_login.data
    print("  [OK] Login blocked for deactivated technician with clear security message")

    # Login back as Admin to reactivate
    client.post('/login', data={'email': 'admin@fleetsync.io', 'password': 'Admin@123'}, follow_redirects=True)
    res_react = client.post(f'/admin/technicians/{vikram_id}/toggle-status', follow_redirects=True)
    assert res_react.status_code == 200
    assert b"Reactivated" in res_react.data
    upd_vikram = query_db("SELECT status FROM users WHERE id = %s", (vikram_id,), one=True)
    assert upd_vikram['status'] == 'Active'
    print("  [OK] Technician Vikram Rao reactivated (status -> Active)")

    # -------------------------------------------------------------
    # 7. Independent Logins & Strict Job Isolation
    # -------------------------------------------------------------
    print("\n[TEST 7] Testing Independent Logins & Strict Job Isolation...")
    # Find a vehicle
    veh = query_db("SELECT id FROM vehicles LIMIT 1", one=True)
    veh_id = veh['id']

    # Create Job A for Vikram
    inv_vikram = "WO-TEST-VIKRAM-001"
    query_db("DELETE FROM service_records WHERE invoice_number = %s", (inv_vikram,), commit=True)
    job_vikram_id = query_db("""
        INSERT INTO service_records (vehicle_id, user_id, service_type, description, status, priority, appointment_date, invoice_number, total_cost)
        VALUES (%s, %s, 'Transmission Gearbox Overhaul', 'Gear slipping in 3rd gear', 'Accepted', 'High', CURDATE(), %s, 7500.00)
    """, (veh_id, vikram_id, inv_vikram), commit=True)

    # Create Job B for Sneha
    inv_sneha = "WO-TEST-SNEHA-002"
    query_db("DELETE FROM service_records WHERE invoice_number = %s", (inv_sneha,), commit=True)
    job_sneha_id = query_db("""
        INSERT INTO service_records (vehicle_id, user_id, service_type, description, status, priority, appointment_date, invoice_number, total_cost)
        VALUES (%s, %s, 'High Voltage Battery Diagnostics', 'BMS throwing Cell Imbalance error', 'In Progress', 'Critical', CURDATE(), %s, 9200.00)
    """, (veh_id, sneha_id, inv_sneha), commit=True)

    # Login as Vikram Rao
    client.get('/logout')
    res_vikram_login = client.post('/login', data={'email': 'vikram.tech@fleetsync.io', 'password': 'NewPassword@456'}, follow_redirects=True)
    assert res_vikram_login.status_code == 200
    assert b"Vikram S. Rao" in res_vikram_login.data

    # Vikram views job queue
    res_v_jobs = client.get('/tech/jobs')
    assert inv_vikram.encode() in res_v_jobs.data
    assert inv_sneha.encode() not in res_v_jobs.data # MUST NOT SEE SNEHA'S JOB!
    print("  [OK] Vikram sees only his assigned work order (Job A). Sneha's job is hidden")

    # Vikram attempts to view Sneha's job directly by ID (Unauthorized)
    res_v_hack = client.get(f'/tech/jobs/{job_sneha_id}', follow_redirects=True)
    assert b"not authorized to access this job" in res_v_hack.data
    print("  [OK] Direct cross-technician access blocked with 403/Forbidden redirect")

    # Login as Sneha Patil
    client.get('/logout')
    res_sneha_login = client.post('/login', data={'email': 'sneha.tech@fleetsync.io', 'password': 'TechSneha@123'}, follow_redirects=True)
    assert res_sneha_login.status_code == 200
    assert b"Sneha Patil" in res_sneha_login.data

    # Sneha views job queue
    res_s_jobs = client.get('/tech/jobs')
    assert inv_sneha.encode() in res_s_jobs.data
    assert inv_vikram.encode() not in res_s_jobs.data # MUST NOT SEE VIKRAM'S JOB!
    print("  [OK] Sneha sees only her assigned work order (Job B). Vikram's job is hidden")

    # -------------------------------------------------------------
    # 8. Technician Actions (Status Update & Service Report)
    # -------------------------------------------------------------
    print("\n[TEST 8] Testing Technician Work Description, Status & Report Filing...")
    # Sneha updates status to On Hold then back to In Progress
    res_s_status = client.post(f'/tech/jobs/{job_sneha_id}/status', data={'status': 'On Hold'}, follow_redirects=True)
    assert res_s_status.status_code == 200
    job_rec = query_db("SELECT status FROM service_records WHERE id = %s", (job_sneha_id,), one=True)
    assert job_rec['status'] == 'On Hold'
    print("  [OK] Sneha updated work order status to 'On Hold'")

    # Sneha files official Service Report with photos and completes work order
    res_s_report = client.post(f'/tech/jobs/{job_sneha_id}/report', data={
        'diagnosis': 'Cell #14 was reading 3.2V while pack average was 3.8V. Thermal sensor connector loose.',
        'work_performed': 'Cleaned and re-pinned BMS thermal sensor harness. Performed active balancing cycle across pack.',
        'solution_provided': 'Pack balance restored within 15mV tolerance across all 96 modules. High voltage test passed.',
        'parts_used_summary': '1x BMS Harness Terminal Clip, 2x Thermal Interface Gel packs',
        'remarks': 'Advised customer to avoid fast charging above 80% for the next 3 charge cycles.',
        'completion_date': '2026-11-01',
        'final_odometer': '28400'
    }, follow_redirects=True)
    assert res_s_report.status_code == 200
    job_rec = query_db("SELECT status, completed_at FROM service_records WHERE id = %s", (job_sneha_id,), one=True)
    assert job_rec['status'] == 'Completed'
    print("  [OK] Sneha submitted certified Service Report and completed Job B")

    # -------------------------------------------------------------
    # 9. Admin Tracking & Workload Performance Detail
    # -------------------------------------------------------------
    print("\n[TEST 9] Testing Admin Workload Tracking (/admin/technicians/<id>/workload)...")
    client.get('/logout')
    client.post('/login', data={'email': 'admin@fleetsync.io', 'password': 'Admin@123'}, follow_redirects=True)

    # View Sneha's Workload Detail
    res_workload = client.get(f'/admin/technicians/{sneha_id}/workload')
    assert res_workload.status_code == 200
    assert b"Sneha Patil" in res_workload.data
    assert b"Auto Electronics" in res_workload.data and b"EV Battery" in res_workload.data
    assert inv_sneha.encode() in res_workload.data
    assert b"Completed" in res_workload.data
    print("  [OK] Admin workload detail tracks Sneha's completed work order and diagnosis")

    # View Vikram's Workload Detail
    res_v_workload = client.get(f'/admin/technicians/{vikram_id}/workload')
    assert res_v_workload.status_code == 200
    assert b"Vikram S. Rao" in res_v_workload.data
    assert inv_vikram.encode() in res_v_workload.data
    print("  [OK] Admin workload detail tracks Vikram's ongoing work order")

    # -------------------------------------------------------------
    # 10. Safe Deletion Audit Check
    # -------------------------------------------------------------
    print("\n[TEST 10] Testing Safe Deletion with Audit Trail Protection...")
    # Attempt to delete Vikram (who has linked Job A)
    res_del_v = client.post(f'/admin/technicians/{vikram_id}/delete', follow_redirects=True)
    assert res_del_v.status_code == 200
    assert b"Cannot permanently delete" in res_del_v.data or b"Deactivated" in res_del_v.data
    # Vikram must NOT have been hard deleted
    v_still_exists = query_db("SELECT id, status FROM users WHERE id = %s", (vikram_id,), one=True)
    assert v_still_exists is not None
    assert v_still_exists['status'] == 'Inactive'
    print("  [OK] Historical record safety confirmed: Technician with work history was safely deactivated, not hard deleted")

    # Add a temporary disposable technician with 0 jobs and verify permanent deletion
    client.post('/admin/technicians/create', data={
        'name': 'Disposable Tech',
        'email': 'disposable.tech@fleetsync.io',
        'phone': '+91 99999 88888',
        'technician_code': 'TECH-999',
        'password': 'Password@123',
        'confirm_password': 'Password@123'
    }, follow_redirects=True)
    disp = query_db("SELECT id FROM users WHERE email = 'disposable.tech@fleetsync.io'", one=True)
    assert disp is not None
    disp_id = disp['id']

    # Delete disposable technician (0 jobs)
    res_del_disp = client.post(f'/admin/technicians/{disp_id}/delete', follow_redirects=True)
    assert res_del_disp.status_code == 200
    assert b"permanently deleted" in res_del_disp.data
    disp_gone = query_db("SELECT id FROM users WHERE id = %s", (disp_id,), one=True)
    assert disp_gone is None
    print("  [OK] Technician with 0 jobs successfully permanently deleted")

    print("\n" + "=" * 75)
    print("ALL 10 MULTIPLE TECHNICIAN MANAGEMENT TEST SUITES PASSED FLAWLESSLY!")
    print("=" * 75)

if __name__ == '__main__':
    run_multiple_technicians_tests()
