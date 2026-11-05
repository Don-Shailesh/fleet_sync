from app import app, query_db

def test_maintenance_intervals_removed_from_admin_and_tech():
    client = app.test_client()

    # 1. Test Admin View
    admin_user = query_db("SELECT id, name, email, role FROM users WHERE role = 'Admin' LIMIT 1", one=True)
    assert admin_user is not None
    with client.session_transaction() as sess:
        sess['user_id'] = admin_user['id']
        sess['user_email'] = admin_user['email']
        sess['user_role'] = 'Admin'
        sess['role'] = 'Admin'
        sess['user_name'] = admin_user['name']

    # Check Admin Dashboard
    resp = client.get('/dashboard')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert "Maintenance Intervals" not in html, "Maintenance Intervals still found in Admin dashboard/nav!"
    assert "Schedule Maintenance" not in html, "Schedule Maintenance still found in Admin Quick Action!"
    assert "Critical Maintenance Schedules Due" not in html, "Critical Maintenance banner still found in Admin dashboard!"
    assert "Due Maintenance" not in html, "Due Maintenance card still found in Admin dashboard!"
    assert "Total Customers" in html, "Total Customers card should be in Admin dashboard"
    assert "Invoice Paid" in html, "Invoice Paid should be in Admin nav"

    # Check another admin page like services_list
    resp = client.get('/services')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert "Maintenance Intervals" not in html, "Maintenance Intervals still found in Services nav!"
    assert "Schedule Maintenance" not in html, "Schedule Maintenance still found in Quick Action!"

    # Check vehicle detail page (/vehicles/<id>)
    veh = query_db("SELECT id FROM vehicles LIMIT 1", one=True)
    assert veh is not None
    resp = client.get(f"/vehicles/{veh['id']}")
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert "Preventive Maintenance Schedules" not in html, "Preventive Maintenance Schedules still found in Vehicle detail!"
    assert "Add Rule" not in html, "Add Rule button still found in Vehicle detail!"
    assert "Service History & Work Orders" in html, "Service History should remain intact in Vehicle detail"

    print("PASS: Admin panel successfully verified - Maintenance Intervals & Vehicle Schedules completely removed.")

    # 2. Test Technician View
    # Find a technician user
    tech_user = query_db("SELECT * FROM users WHERE role = 'Technician' LIMIT 1", one=True)
    assert tech_user is not None

    with client.session_transaction() as sess:
        sess['user_id'] = tech_user['id']
        sess['user_email'] = tech_user['email']
        sess['user_role'] = 'Technician'
        sess['role'] = 'Technician'
        sess['user_name'] = tech_user['name']

    # Check Technician Dashboard
    resp = client.get('/tech/dashboard')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert "Maintenance Intervals" not in html, "Maintenance Intervals still found in Technician dashboard/nav!"
    assert "Tech Dashboard" in html
    assert "My Assigned Jobs" in html
    assert "Parts Requisitions" in html

    # Check Technician Jobs page
    resp = client.get('/tech/jobs')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert "Maintenance Intervals" not in html, "Maintenance Intervals still found in Technician jobs nav!"

    print("PASS: Technician panel successfully verified - Maintenance Intervals completely removed.")

if __name__ == '__main__':
    test_maintenance_intervals_removed_from_admin_and_tech()
    print("\nALL VERIFICATIONS PASSED!")
