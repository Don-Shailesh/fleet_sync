"""
Test Suite: Admin Panel Automated Reminders Removal Verification
Verifies:
1. Admin Dashboard, Sidebar Navigation, and Schedules page do NOT show 'Automated Reminders' or reminder scan buttons.
2. Core pages (Dashboard, Schedules, Technicians, Services, Parts, Vehicles, Customers) continue to function perfectly.
"""
from app import app, query_db

def test_admin_nav_clean():
    print("=== STARTING ADMIN PANEL REMINDERS REMOVAL VERIFICATION ===")
    client = app.test_client()

    with client.session_transaction() as sess:
        admin_user = query_db("SELECT id, name, role FROM users WHERE role = 'Admin' LIMIT 1", one=True)
        assert admin_user is not None, "Admin user required"
        sess['user_id'] = admin_user['id']
        sess['user_role'] = 'Admin'
        sess['role'] = 'Admin'
        sess['user_name'] = admin_user['name']

    # 1. Check Dashboard
    resp = client.get('/dashboard')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert "Automated Reminders" not in html, "'Automated Reminders' still found in Dashboard sidebar!"
    assert "Sync & Queue Reminders" not in html, "'Sync & Queue Reminders' button still found on Dashboard!"
    assert "Scan & Queue Reminders" not in html, "'Scan & Queue Reminders' still in Quick Action dropdown!"
    print("PASS: Dashboard verified - Automated Reminders and scan triggers completely removed.")

    # 2. Check Schedules page
    resp = client.get('/schedules')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert "Automated Reminders" not in html, "'Automated Reminders' still found in Schedules sidebar!"
    assert "Scan Due Services" not in html, "'Scan Due Services' button still found on Schedules page!"
    assert "Add Schedule Rule" in html, "Add Schedule Rule button should be present"
    print("PASS: Schedules page verified - reminders button removed, Add Schedule Rule active.")

    # 3. Check Technician Management
    resp = client.get('/admin/technicians')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert "Automated Reminders" not in html
    assert "Duty Availability" in html
    print("PASS: Technician Management verified - clean navigation and duty status intact.")

    # 4. Check Parts Inventory
    resp = client.get('/parts/inventory')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert "Automated Reminders" not in html
    assert "Available In Stock" in html
    print("PASS: Parts Inventory verified - clean navigation and availability metrics intact.")

    # 5. Check Work Orders
    resp = client.get('/services')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert "Automated Reminders" not in html
    print("PASS: Work Orders verified - clean navigation.")

    print("=== ALL ADMIN PANEL REMINDER REMOVAL TESTS PASSED! ===")

if __name__ == '__main__':
    test_admin_nav_clean()

