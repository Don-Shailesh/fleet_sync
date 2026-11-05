from app import app, query_db

def test_available_technicians_selection():
    client = app.test_client()

    # 1. Login as Admin
    admin_user = query_db("SELECT id, name, email, role FROM users WHERE role = 'Admin' LIMIT 1", one=True)
    assert admin_user is not None
    with client.session_transaction() as sess:
        sess['user_id'] = admin_user['id']
        sess['user_email'] = admin_user['email']
        sess['user_role'] = 'Admin'
        sess['role'] = 'Admin'
        sess['user_name'] = admin_user['name']

    import re
    # 2. Check GET /services/create
    resp = client.get('/services/create')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')

    tech_select = re.search(r'<select id="wo-tech".*?</select>', html, re.DOTALL)
    assert tech_select is not None, "Technician dropdown <select id='wo-tech'> not found!"
    select_html = tech_select.group(0)

    # Shailesh Dongare (Admin) must NOT be in the technician dropdown!
    assert "Shailesh Dongare" not in select_html, "Admin 'Shailesh Dongare' should NOT be listed as a technician!"

    # Spare parts staff must NOT be in technician dropdown!
    assert "Rajesh Kumar" not in select_html, "Spare parts staff should NOT be listed as a technician!"

    # Vikram S. Rao (Inactive / Busy) must NOT be in technician dropdown!
    assert "Vikram S. Rao" not in select_html, "Inactive/Busy technician should NOT be listed as available!"

    # Available technicians should be present
    assert "Suresh Verma" in select_html, "Active available technician Suresh Verma should be listed"
    assert "Amit Sharma" in select_html, "Active available technician Amit Sharma should be listed"
    assert "Sneha Patil" in select_html, "Active available technician Sneha Patil should be listed"
    print("PASS: /services/create correctly lists only available technicians, excluding admins and inactive/busy staff.")

    # 3. Test dynamic availability filtering
    # Change Suresh Verma to 'Busy'
    query_db("UPDATE users SET availability_status = 'Busy' WHERE id = 2", commit=True)
    try:
        resp2 = client.get('/services/create')
        html2 = resp2.data.decode('utf-8')
        tech_select2 = re.search(r'<select id="wo-tech".*?</select>', html2, re.DOTALL)
        assert tech_select2 is not None
        select_html2 = tech_select2.group(0)
        assert "Suresh Verma" not in select_html2, "Busy technician Suresh Verma should NOT be shown in available technicians list!"
        print("PASS: Technician set to 'Busy' is properly excluded from assignment dropdown.")
    finally:
        # Revert Suresh Verma to 'Available'
        query_db("UPDATE users SET availability_status = 'Available' WHERE id = 2", commit=True)

    # 4. Test Unassigned creation: user_id must be NULL and not defaulted to Admin
    veh = query_db("SELECT id, current_odometer FROM vehicles LIMIT 1", one=True)
    post_data = {
        'vehicle_id': veh['id'],
        'user_id': '',  # Unassigned
        'service_date': '2026-11-03',
        'appointment_date': '2026-11-03',
        'appointment_time': '10:00',
        'odometer': veh['current_odometer'] + 10,
        'service_type': 'Oil Change',
        'status': 'Pending',
        'priority': 'Medium',
        'payment_status': 'Unpaid',
        'description': 'Test Unassigned Creation',
        'technician_notes': '',
        'item_type[]': ['Labor'],
        'item_name[]': ['General Inspection'],
        'item_quantity[]': ['1'],
        'item_price[]': ['100']
    }
    resp_create = client.post('/services/create', data=post_data, follow_redirects=False)
    assert resp_create.status_code == 302, f"Expected 302 redirect, got {resp_create.status_code}"
    
    # Check the created record in DB
    created_rec = query_db("SELECT id, user_id FROM service_records WHERE description = 'Test Unassigned Creation' ORDER BY id DESC LIMIT 1", one=True)
    assert created_rec is not None
    assert created_rec['user_id'] is None, f"Expected user_id to be None for Unassigned, got {created_rec['user_id']}"
    print("PASS: Unassigned work order correctly stores user_id as NULL (not defaulted to Admin).")

    # Clean up test record
    query_db("DELETE FROM service_items WHERE service_record_id = %s", (created_rec['id'],), commit=True)
    query_db("DELETE FROM service_records WHERE id = %s", (created_rec['id'],), commit=True)

if __name__ == '__main__':
    test_available_technicians_selection()
    print("\nALL AVAILABLE TECHNICIAN SELECTION TESTS PASSED 100%!")
