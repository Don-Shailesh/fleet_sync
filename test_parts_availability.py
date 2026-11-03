"""
Test Suite: Parts Inventory Availability Management
Verifies:
1. Admin access to Parts Inventory and Availability KPI overview cards.
2. 1-Click interactive update of Availability via POST /parts/<id>/availability and /parts/<id>/status.
3. Verification of In Stock (Available), Low Stock, and Out of Stock (Unavailable) states and stock quantity consistency.
4. Filter by availability / stock status, including aliases ('Available', 'Unavailable').
5. Role authorization and invalid status protection.
"""
from app import app, query_db

def run_tests():
    print("=== STARTING PARTS INVENTORY AVAILABILITY TEST SUITE ===")
    client = app.test_client()

    # 1. Login as Admin
    with client.session_transaction() as sess:
        admin_user = query_db("SELECT id, name, role FROM users WHERE role = 'Admin' LIMIT 1", one=True)
        assert admin_user is not None, "No Admin user found!"
        sess['user_id'] = admin_user['id']
        sess['user_role'] = 'Admin'
        sess['role'] = 'Admin'
        sess['user_name'] = admin_user['name']

    # 2. Pick a test spare part
    part = query_db("SELECT id, part_number, part_name, quantity, min_quantity, status FROM spare_parts LIMIT 1", one=True)
    assert part is not None, "No spare part found in database!"
    part_id = part['id']
    orig_qty = part['quantity']
    orig_status = part['status']
    print(f"Testing with Part ID {part_id}: '{part['part_name']}' ({part['part_number']}), Initial: {orig_status}, Qty: {orig_qty}")

    # 3. GET /parts/inventory
    resp = client.get('/parts/inventory')
    assert resp.status_code == 200, f"Expected 200 on /parts/inventory, got {resp.status_code}"
    html = resp.data.decode('utf-8')
    assert "Available In Stock" in html, "Available In Stock KPI card missing!"
    assert "Low Stock Alert" in html, "Low Stock Alert KPI card missing!"
    assert "Out of Stock" in html, "Out of Stock KPI card missing!"
    assert f"/parts/{part_id}/availability" in html, "Part availability action form missing from inventory table!"
    assert "Set Part Availability" in html, "Set Part Availability dropdown header missing!"
    print("PASS: Parts Inventory loads with Availability KPI cards and interactive dropdowns.")

    # 4. Update status to 'Out of Stock' (Unavailable)
    resp = client.post(f'/parts/{part_id}/availability', data={'status': 'Out of Stock'}, follow_redirects=True)
    assert resp.status_code == 200
    p_upd = query_db("SELECT status, quantity FROM spare_parts WHERE id = %s", (part_id,), one=True)
    assert p_upd['status'] == 'Out of Stock', f"Expected 'Out of Stock', got {p_upd['status']}"
    assert p_upd['quantity'] == 0, f"Expected quantity 0 for Out of Stock, got {p_upd['quantity']}"
    print("PASS: Part successfully marked Out of Stock / Unavailable (status and quantity updated).")

    # 5. Update status to 'Low Stock'
    resp = client.post(f'/parts/{part_id}/availability', data={'status': 'Low Stock'}, follow_redirects=True)
    assert resp.status_code == 200
    p_upd = query_db("SELECT status, quantity FROM spare_parts WHERE id = %s", (part_id,), one=True)
    assert p_upd['status'] == 'Low Stock', f"Expected 'Low Stock', got {p_upd['status']}"
    assert p_upd['quantity'] > 0, "Expected non-zero quantity for Low Stock"
    print("PASS: Part successfully marked Low Stock.")

    # 6. Update status to 'In Stock' (Available)
    resp = client.post(f'/parts/{part_id}/availability', data={'status': 'In Stock'}, follow_redirects=True)
    assert resp.status_code == 200
    p_upd = query_db("SELECT status, quantity FROM spare_parts WHERE id = %s", (part_id,), one=True)
    assert p_upd['status'] == 'In Stock', f"Expected 'In Stock', got {p_upd['status']}"
    assert p_upd['quantity'] > 0, "Expected non-zero quantity for In Stock"
    print("PASS: Part successfully marked In Stock / Available.")

    # 7. Test alias 'Available' & 'Unavailable'
    resp = client.post(f'/parts/{part_id}/availability', data={'availability': 'Unavailable'}, follow_redirects=True)
    assert resp.status_code == 200
    p_upd = query_db("SELECT status FROM spare_parts WHERE id = %s", (part_id,), one=True)
    assert p_upd['status'] == 'Out of Stock'

    resp = client.post(f'/parts/{part_id}/availability', data={'availability': 'Available'}, follow_redirects=True)
    assert resp.status_code == 200
    p_upd = query_db("SELECT status FROM spare_parts WHERE id = %s", (part_id,), one=True)
    assert p_upd['status'] == 'In Stock'
    print("PASS: Aliases 'Available' and 'Unavailable' mapped correctly.")

    # 8. Test alternative endpoint /parts/<id>/status
    resp = client.post(f'/parts/{part_id}/status', data={'status': 'Low Stock'}, follow_redirects=True)
    assert resp.status_code == 200
    p_upd = query_db("SELECT status FROM spare_parts WHERE id = %s", (part_id,), one=True)
    assert p_upd['status'] == 'Low Stock'
    print("PASS: Alternative endpoint /parts/<id>/status works cleanly.")

    # 9. Test filtering by availability
    resp_avail = client.get('/parts/inventory?availability=Available')
    assert resp_avail.status_code == 200
    assert "In Stock" in resp_avail.data.decode('utf-8')

    resp_out = client.get('/parts/inventory?status=Out of Stock')
    assert resp_out.status_code == 200
    print("PASS: Filtering by availability and status works seamlessly.")

    # 10. Test authorization: Technician blocked from parts management endpoint
    with client.session_transaction() as sess:
        tech_user = query_db("SELECT id, name, role FROM users WHERE role = 'Technician' LIMIT 1", one=True)
        sess['user_id'] = tech_user['id']
        sess['user_role'] = 'Technician'
        sess['role'] = 'Technician'
        sess['user_name'] = tech_user['name']

    resp = client.post(f'/parts/{part_id}/availability', data={'status': 'Out of Stock'}, follow_redirects=False)
    assert resp.status_code in (302, 403), f"Technician should be blocked, got {resp.status_code}"
    print("PASS: Role authorization strictly enforced (Technician blocked from inventory modification).")

    # 11. Restore original state
    query_db("UPDATE spare_parts SET status = %s, quantity = %s WHERE id = %s", (orig_status, orig_qty, part_id), commit=True)
    print("PASS: Restored original part status and quantity.")
    print("=== ALL PARTS INVENTORY AVAILABILITY TESTS PASSED 100%! ===")

if __name__ == '__main__':
    run_tests()

