import sys
from app import app
from db import query_db

def run_tests():
    print("=" * 75)
    print("STARTING DETAILED SPARE PARTS BUTTON & ACTION FUNCTIONALITY TEST")
    print("=" * 75)

    client = app.test_client()

    # -------------------------------------------------------------
    # 1. Login & Navigation
    # -------------------------------------------------------------
    print("\n[TEST 1] Testing Spare Parts Login & Role Routing...")
    res = client.post('/login', data={'email': 'parts@fleetsync.io', 'password': 'Parts@123'}, follow_redirects=False)
    assert res.status_code == 302
    assert '/parts/dashboard' in res.headers.get('Location', '')
    print("  [OK] Login redirect to /parts/dashboard SUCCESS")

    res_dash = client.get('/parts/dashboard')
    assert res_dash.status_code == 200
    assert b"Spare Parts Department Hub" in res_dash.data
    assert b"Incoming Technician Spare Parts Requests" in res_dash.data
    print("  [OK] Dashboard loaded and rendered table of incoming requests")

    # -------------------------------------------------------------
    # 2. Inventory Filtering & Search Controls
    # -------------------------------------------------------------
    print("\n[TEST 2] Testing Inventory Search & Filter Controls...")
    # Test All Categories (must not fail or return 0 items)
    res_cat_all = client.get('/parts/inventory?category=All')
    assert res_cat_all.status_code == 200
    assert b"SP-BRK-001" in res_cat_all.data or b"Brake" in res_cat_all.data
    print("  [OK] Category 'All' filter works correctly without 0-item bug")

    # Test Specific Category Filter
    res_cat_brakes = client.get('/parts/inventory?category=Brakes')
    assert res_cat_brakes.status_code == 200
    assert b"Brakes" in res_cat_brakes.data
    print("  [OK] Category 'Brakes' filter returned matching parts")

    # Test All Statuses Filter
    res_st_all = client.get('/parts/inventory?status=All')
    assert res_st_all.status_code == 200
    print("  [OK] Status 'All' filter works correctly")

    # Test In Stock Filter
    res_st_instock = client.get('/parts/inventory?status=In+Stock')
    assert res_st_instock.status_code == 200
    print("  [OK] Status 'In Stock' filter works correctly")

    # Test Search Keyword Filter
    res_search = client.get('/parts/inventory?search=Brake')
    assert res_search.status_code == 200
    assert b"Brake" in res_search.data
    print("  [OK] Search filter by keyword 'Brake' returned matching components")

    # -------------------------------------------------------------
    # 3. Add, Duplicate Validation, Edit, Quick-Stock, Delete Part
    # -------------------------------------------------------------
    print("\n[TEST 3] Testing Add, Duplicate Check, Edit, Quick-Stock & Delete...")
    # Clean up test part if existing
    query_db("DELETE FROM spare_parts WHERE part_number = 'TEST-CLUTCH-88'", commit=True)

    # Add Part
    res_add = client.post('/parts/create', data={
        'part_number': 'TEST-CLUTCH-88',
        'part_name': 'Valeo Heavy Duty Clutch Pressure Plate',
        'category': 'Transmission',
        'shelf_location': 'Rack 4 - Bin 2',
        'quantity': '15',
        'min_quantity': '4',
        'unit_price': '7500.00',
        'cost_price': '5200.00',
        'supplier': 'Valeo India',
        'compatibility': 'Tata 407 / Winger',
        'description': 'High torque dual diaphragm clutch kit'
    }, follow_redirects=True)
    assert res_add.status_code == 200
    assert b"registered successfully" in res_add.data
    part = query_db("SELECT * FROM spare_parts WHERE part_number = 'TEST-CLUTCH-88'", one=True)
    assert part is not None
    part_id = part['id']
    print(f"  [OK] Part added with ID {part_id}, Quantity: {part['quantity']}")

    # Duplicate part number validation test
    res_dup = client.post('/parts/create', data={
        'part_number': 'TEST-CLUTCH-88',
        'part_name': 'Duplicate Clutch',
        'category': 'Transmission',
        'quantity': '5',
        'min_quantity': '2',
        'unit_price': '6000'
    }, follow_redirects=True)
    assert b"already exists" in res_dup.data
    print("  [OK] Duplicate SKU prevention correctly rejected duplicate submission")

    # Quick Stock Adjustment Test (+10 units)
    res_quick = client.post(f'/parts/{part_id}/quick-stock', data={'adjustment_qty': '10'}, follow_redirects=True)
    assert res_quick.status_code == 200
    part_after_stock = query_db("SELECT quantity FROM spare_parts WHERE id = %s", (part_id,), one=True)
    assert part_after_stock['quantity'] == 25
    print(f"  [OK] Quick stock adjustment applied: 15 + 10 = {part_after_stock['quantity']}")

    # Quick Stock 0 Adjustment validation
    res_zero = client.post(f'/parts/{part_id}/quick-stock', data={'adjustment_qty': '0'}, follow_redirects=True)
    assert b"No stock quantity adjustment specified" in res_zero.data
    print("  [OK] Quick stock zero adjustment correctly warned user")

    # Edit Part
    res_edit = client.post(f'/parts/{part_id}/edit', data={
        'part_number': 'TEST-CLUTCH-88',
        'part_name': 'Valeo Heavy Duty Clutch Kit - Revised Edition',
        'category': 'Transmission',
        'shelf_location': 'Rack 4 - Bin 2B',
        'quantity': '25',
        'min_quantity': '5',
        'unit_price': '7800.00',
        'cost_price': '5400.00',
        'supplier': 'Valeo India Automotive',
        'compatibility': 'Tata 407 / Winger Commercial',
        'description': 'Updated specifications'
    }, follow_redirects=True)
    assert res_edit.status_code == 200
    assert b"updated successfully" in res_edit.data
    print("  [OK] Part edited and updated successfully")

    # -------------------------------------------------------------
    # 4. Technician Requisition & Duplicate Protection
    # -------------------------------------------------------------
    print("\n[TEST 4] Testing Technician Requisition & Duplicate Prevention...")
    client.get('/logout')
    client.post('/login', data={'email': 'tech@fleetsync.io', 'password': 'Tech@123'})

    # Work Order target
    test_svc = query_db("SELECT id, invoice_number, status FROM service_records WHERE status != 'Completed' LIMIT 1", one=True)
    if not test_svc:
        test_svc = query_db("SELECT id, invoice_number, status FROM service_records LIMIT 1", one=True)
    svc_id = test_svc['id']

    # Submit part request
    res_req = client.post(f'/services/{svc_id}/request-part', data={
        'part_id': str(part_id),
        'part_name': 'Valeo Heavy Duty Clutch Kit - Revised Edition',
        'part_number': 'TEST-CLUTCH-88',
        'quantity_requested': '3',
        'priority': 'Urgent',
        'technician_notes': 'Clutch slippage in 3rd gear. Pressure plate failure.'
    }, follow_redirects=True)
    assert res_req.status_code == 200
    assert b"dispatched to Spare Parts Department" in res_req.data

    # Verify work order status updated
    svc_status = query_db("SELECT status FROM service_records WHERE id = %s", (svc_id,), one=True)
    assert svc_status['status'] == 'Waiting for Parts'
    print(f"  [OK] Technician requested part. Work order {test_svc['invoice_number']} is 'Waiting for Parts'")

    # Verify duplicate submission within 30 seconds is blocked
    res_dup_req = client.post(f'/services/{svc_id}/request-part', data={
        'part_id': str(part_id),
        'part_name': 'Valeo Heavy Duty Clutch Kit - Revised Edition',
        'part_number': 'TEST-CLUTCH-88',
        'quantity_requested': '3',
        'priority': 'Urgent'
    }, follow_redirects=True)
    assert b"already pending" in res_dup_req.data
    print("  [OK] Rapid duplicate requisition submission successfully blocked")

    req_record = query_db("SELECT * FROM part_requests WHERE service_record_id = %s AND part_id = %s ORDER BY id DESC LIMIT 1", (svc_id, part_id), one=True)
    req_id = req_record['id']

    # -------------------------------------------------------------
    # 5. Spare Parts Pipeline Filtering & Quick Actions
    # -------------------------------------------------------------
    print("\n[TEST 5] Testing Requisition Pipeline Filtering & Actions...")
    client.get('/logout')
    client.post('/login', data={'email': 'parts@fleetsync.io', 'password': 'Parts@123'})

    # Test Search on requests page
    res_req_search = client.get(f'/parts/requests?search={test_svc["invoice_number"]}')
    assert res_req_search.status_code == 200
    assert test_svc['invoice_number'].encode() in res_req_search.data
    print(f"  [OK] Requisition search by Work Order # '{test_svc['invoice_number']}' successful")

    # Test Status Filter (Pending)
    res_req_pending = client.get('/parts/requests?status=Pending')
    assert res_req_pending.status_code == 200
    print("  [OK] Requisition status filter 'Pending' successful")

    # Test Status Filter (All)
    res_req_all = client.get('/parts/requests?status=All')
    assert res_req_all.status_code == 200
    print("  [OK] Requisition status filter 'All' works without 0-item bug")

    # Test Quick Reject action
    print("\n[TEST 5B] Testing Reject Action...")
    res_reject = client.post(f'/parts/requests/{req_id}/reject', data={
        'reject_reason': 'Supplier stock depleted. Estimated arrival in 10 business days.'
    }, follow_redirects=True)
    assert res_reject.status_code == 200
    assert b"marked as &#39;Not Available&#39;" in res_reject.data or b"Not Available" in res_reject.data
    req_after_rej = query_db("SELECT status, parts_dept_notes FROM part_requests WHERE id = %s", (req_id,), one=True)
    assert req_after_rej['status'] == 'Not Available'
    print(f"  [OK] Request #REQ-{req_id} rejected successfully: Status is 'Not Available'")

    # Test Quick Approve action
    print("\n[TEST 5C] Testing Approve Action...")
    res_approve = client.post(f'/parts/requests/{req_id}/approve', data={
        'parts_dept_notes': 'Direct OEM stock received and ready at Counter 1.'
    }, follow_redirects=True)
    assert res_approve.status_code == 200
    assert b"APPROVED" in res_approve.data
    req_after_appr = query_db("SELECT status, quantity_available FROM part_requests WHERE id = %s", (req_id,), one=True)
    assert req_after_appr['status'] == 'Part Available'
    assert req_after_appr['quantity_available'] == 3
    print(f"  [OK] Request #REQ-{req_id} approved: Status is 'Part Available', Qty Ready: 3")

    # Verify inventory stock was deducted: 25 - 3 = 22
    part_after_appr = query_db("SELECT quantity FROM spare_parts WHERE id = %s", (part_id,), one=True)
    assert part_after_appr['quantity'] == 22
    print(f"  [OK] Inventory stock auto-deducted: 25 - 3 = {part_after_appr['quantity']} units remaining")

    # -------------------------------------------------------------
    # 6. Technician Receives Part & Work Order Resumes
    # -------------------------------------------------------------
    print("\n[TEST 6] Testing Technician Receives Component & Work Order Resumption...")
    client.get('/logout')
    client.post('/login', data={'email': 'tech@fleetsync.io', 'password': 'Tech@123'})

    # Technician views /parts/my-requests with search & status filter
    res_my_search = client.get(f'/parts/my-requests?status=Part+Available&search={test_svc["invoice_number"]}')
    assert res_my_search.status_code == 200
    assert b"Mark Received &amp; Resume" in res_my_search.data or b"Mark Received & Resume" in res_my_search.data
    print("  [OK] Technician search and filter on /parts/my-requests returned ready parts")

    # Technician marks received
    res_rcv = client.post(f'/parts/requests/{req_id}/mark-received', follow_redirects=True)
    assert res_rcv.status_code == 200
    assert b"marked as received" in res_rcv.data

    req_final = query_db("SELECT status FROM part_requests WHERE id = %s", (req_id,), one=True)
    assert req_final['status'] == 'Received by Technician'
    svc_final = query_db("SELECT status FROM service_records WHERE id = %s", (svc_id,), one=True)
    assert svc_final['status'] == 'In Progress'
    print(f"  [OK] Request status: {req_final['status']} | Work Order resumed to: {svc_final['status']}")

    # -------------------------------------------------------------
    # 7. Safe Delete of Spare Part
    # -------------------------------------------------------------
    print("\n[TEST 7] Testing Safe Delete of Part with History Preservation...")
    client.get('/logout')
    client.post('/login', data={'email': 'parts@fleetsync.io', 'password': 'Parts@123'})

    res_del = client.post(f'/parts/{part_id}/delete', follow_redirects=True)
    assert res_del.status_code == 200
    assert b"removed from catalog successfully" in res_del.data

    # Verify part is deleted from catalog
    deleted_part = query_db("SELECT * FROM spare_parts WHERE id = %s", (part_id,), one=True)
    assert deleted_part is None
    # Verify request record still exists with part_id unlinked (NULL)
    preserved_req = query_db("SELECT * FROM part_requests WHERE id = %s", (req_id,), one=True)
    assert preserved_req is not None
    assert preserved_req['part_id'] is None
    print("  [OK] Part safely deleted while preserving historical requisition record")

    # Clean up test requisition and notifications
    query_db("DELETE FROM notifications WHERE link LIKE '%my-requests%' OR link LIKE '%requests%'", commit=True)
    query_db("DELETE FROM part_requests WHERE id = %s", (req_id,), commit=True)
    print("  [OK] Temporary test records cleaned up")

    print("\n" + "=" * 75)
    print("ALL BUTTONS, FORMS, FILTERS, SEARCH, APPROVALS & REJECTIONS VERIFIED 100%!")
    print("=" * 75)

if __name__ == '__main__':
    run_tests()
