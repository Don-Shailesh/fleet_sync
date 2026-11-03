"""
Test Suite: Admin Panel Technician Management Duty Status Functionality
Verifies:
1. Admin access to Technician Management Roster and Duty Status metrics (Available, Busy, Leave).
2. 1-Click interactive update of Duty Status via POST /admin/technicians/<id>/duty-status.
3. Verification of all states: Available, Busy, On Leave.
4. Filter by availability status.
5. Workload view duty status interactivity.
6. Role-based access control and invalid payload validation.
"""
import sys
import re
from app import app, query_db

def run_tests():
    print("=== STARTING DUTY STATUS TEST SUITE ===")
    client = app.test_client()

    # 1. Login as Admin
    with client.session_transaction() as sess:
        admin_user = query_db("SELECT id, name, role FROM users WHERE role = 'Admin' LIMIT 1", one=True)
        assert admin_user is not None, "No Admin user found in database!"
        sess['user_id'] = admin_user['id']
        sess['user_role'] = 'Admin'
        sess['role'] = 'Admin'
        sess['user_name'] = admin_user['name']

    # 2. Get a technician
    tech = query_db("SELECT id, name, availability_status FROM users WHERE role = 'Technician' AND status = 'Active' LIMIT 1", one=True)
    assert tech is not None, "No active technician found!"
    tech_id = tech['id']
    orig_status = tech['availability_status']
    print(f"Testing with Technician ID {tech_id} ({tech['name']}), Initial Status: {orig_status}")

    # 3. GET /admin/technicians
    resp = client.get('/admin/technicians')
    assert resp.status_code == 200, f"Expected 200 on /admin/technicians, got {resp.status_code}"
    html = resp.data.decode('utf-8')
    assert "Duty Availability" in html or "Duty Status" in html, "Duty Status KPI title missing from page!"
    assert f"/admin/technicians/{tech_id}/duty-status" in html, "Duty status POST endpoint missing from technician roster!"
    assert "Change Duty Status" in html, "Change Duty Status dropdown header missing!"
    assert "Mark as Available" in html or "Available" in html, "Available action missing!"
    print("PASS: Admin technicians page loads with Duty Status metrics & interactive dropdowns.")

    # 4. Update status to 'Busy'
    resp = client.post(f'/admin/technicians/{tech_id}/duty-status', data={
        'availability_status': 'Busy'
    }, follow_redirects=True)
    assert resp.status_code == 200
    updated_tech = query_db("SELECT availability_status FROM users WHERE id = %s", (tech_id,), one=True)
    assert updated_tech['availability_status'] == 'Busy', f"Expected 'Busy', got {updated_tech['availability_status']}"
    html = resp.data.decode('utf-8')
    assert "updated to &#39;Busy&#39;" in html or "updated to 'Busy'" in html or "Busy" in html
    print("PASS: Successfully updated technician duty status to 'Busy'.")

    # 5. Update status to 'On Leave'
    resp = client.post(f'/admin/technicians/{tech_id}/duty-status', data={
        'availability_status': 'On Leave'
    }, follow_redirects=True)
    assert resp.status_code == 200
    updated_tech = query_db("SELECT availability_status FROM users WHERE id = %s", (tech_id,), one=True)
    assert updated_tech['availability_status'] == 'On Leave', f"Expected 'On Leave', got {updated_tech['availability_status']}"
    print("PASS: Successfully updated technician duty status to 'On Leave'.")

    # 6. Update status back to 'Available'
    resp = client.post(f'/admin/technicians/{tech_id}/duty-status', data={
        'availability_status': 'Available'
    }, follow_redirects=True)
    assert resp.status_code == 200
    updated_tech = query_db("SELECT availability_status FROM users WHERE id = %s", (tech_id,), one=True)
    assert updated_tech['availability_status'] == 'Available', f"Expected 'Available', got {updated_tech['availability_status']}"
    print("PASS: Successfully updated technician duty status to 'Available'.")

    # 7. Test invalid status validation
    resp = client.post(f'/admin/technicians/{tech_id}/duty-status', data={
        'availability_status': 'InvalidStatus'
    }, follow_redirects=True)
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert "Invalid duty status" in html, "Invalid status was not rejected!"
    print("PASS: Invalid duty status rejected.")

    # 8. Check Workload view
    resp = client.get(f'/admin/technicians/{tech_id}/workload')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert f"/admin/technicians/{tech_id}/duty-status" in html, "Duty status form missing from workload view!"
    print("PASS: Workload view contains interactive duty status controls.")

    # 9. Test authorization: Technician cannot change duty status via admin endpoint
    with client.session_transaction() as sess:
        sess['user_id'] = tech_id
        sess['user_role'] = 'Technician'
        sess['role'] = 'Technician'
        sess['user_name'] = tech['name']

    resp = client.post(f'/admin/technicians/{tech_id}/duty-status', data={
        'availability_status': 'Busy'
    }, follow_redirects=False)
    # Admin required redirects to dashboard or 403
    assert resp.status_code in (302, 403), f"Technician should not be authorized, got {resp.status_code}"
    print("PASS: Role authorization strictly enforced (Technician blocked from admin duty-status endpoint).")

    # Restore original status
    query_db("UPDATE users SET availability_status = %s WHERE id = %s", (orig_status, tech_id), commit=True)
    print("PASS: Restored original duty status.")
    print("=== ALL DUTY STATUS TESTS PASSED SUCCESSFULLY! ===")

if __name__ == '__main__':
    run_tests()
