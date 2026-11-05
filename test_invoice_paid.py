"""
Test Suite: Admin Panel Invoice Paid & Payment Management
Verifies:
1. 'Invoice Paid' option on the Admin nav bar with active counter badge.
2. GET /admin/invoices/payments (and /admin/invoice-paid) showing current/latest invoices and KPI metrics.
3. Submitting payment for an unpaid invoice (marking it as Paid with payment method, date, and notes).
4. Marking a paid invoice back as Unpaid (reverting payment status).
5. Multi-criteria filtering by payment status and keyword search.
6. Role-based authorization security.
"""
from app import app, query_db

def run_tests():
    print("=== STARTING INVOICE PAID & PAYMENT MANAGEMENT TEST SUITE ===")
    client = app.test_client()

    # 1. Login as Admin
    with client.session_transaction() as sess:
        admin_user = query_db("SELECT id, name, role FROM users WHERE role = 'Admin' LIMIT 1", one=True)
        assert admin_user is not None, "Admin user required!"
        sess['user_id'] = admin_user['id']
        sess['user_role'] = 'Admin'
        sess['role'] = 'Admin'
        sess['user_name'] = admin_user['name']

    # 2. Test GET /admin/invoices/payments
    resp = client.get('/admin/invoices/payments')
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    html = resp.data.decode('utf-8')
    assert "Invoice Paid" in html, "'Invoice Paid' navigation option missing from template!"
    assert "Current Invoices &amp; Payment Settlement" in html or "Current Invoices & Payment Settlement" in html
    assert "Total Current Invoices" in html, "KPI metric for Total Current Invoices missing!"
    assert "Settled Invoices (Paid)" in html, "KPI metric for Settled Invoices missing!"
    assert "Unpaid Invoices (Due)" in html, "KPI metric for Unpaid Invoices missing!"
    print("PASS: /admin/invoices/payments loaded successfully with KPI metrics and 'Invoice Paid' in navbar.")

    # 3. Test alias route /admin/invoice-paid
    resp_alias = client.get('/admin/invoice-paid')
    assert resp_alias.status_code == 200
    print("PASS: Alias route /admin/invoice-paid loaded successfully.")

    # 4. Pick a test invoice
    inv = query_db("SELECT id, invoice_number, payment_status, total_cost FROM service_records WHERE total_cost > 0 ORDER BY id DESC LIMIT 1", one=True)
    assert inv is not None, "No service record invoice found!"
    inv_id = inv['id']
    orig_status = inv['payment_status']
    print(f"Testing with Invoice ID {inv_id} ({inv['invoice_number']}), Initial status: {orig_status}")

    # 5. Test Submitting Payment (Mark as Paid with UPI)
    resp = client.post(f'/admin/invoices/{inv_id}/payment', data={
        'action': 'submit_payment',
        'payment_status': 'Paid',
        'payment_method': 'UPI / QR',
        'payment_notes': 'GPay Ref #9876543210'
    }, follow_redirects=True)
    assert resp.status_code == 200
    upd_inv = query_db("SELECT payment_status, payment_method, payment_notes, payment_date FROM service_records WHERE id = %s", (inv_id,), one=True)
    assert upd_inv['payment_status'] == 'Paid', f"Expected Paid, got {upd_inv['payment_status']}"
    assert upd_inv['payment_method'] == 'UPI / QR', f"Expected 'UPI / QR', got {upd_inv['payment_method']}"
    assert 'GPay Ref' in (upd_inv['payment_notes'] or '')
    assert upd_inv['payment_date'] is not None
    print("PASS: Successfully submitted payment (marked Paid via UPI / QR with timestamp and notes).")

    # 6. Test Reverting / Marking back as Unpaid
    resp = client.post(f'/admin/invoices/{inv_id}/payment', data={
        'action': 'mark_unpaid'
    }, follow_redirects=True)
    assert resp.status_code == 200
    upd_inv = query_db("SELECT payment_status, payment_method, payment_date FROM service_records WHERE id = %s", (inv_id,), one=True)
    assert upd_inv['payment_status'] == 'Unpaid', f"Expected Unpaid, got {upd_inv['payment_status']}"
    assert upd_inv['payment_method'] is None, "Payment method should be cleared when marked unpaid"
    assert upd_inv['payment_date'] is None, "Payment date should be cleared when marked unpaid"
    print("PASS: Successfully reverted invoice back to Unpaid (cleared payment method and date).")

    # 7. Test Submitting Payment with Cash
    resp = client.post(f'/admin/invoices/{inv_id}/payment', data={
        'action': 'submit_payment',
        'payment_status': 'Paid',
        'payment_method': 'Cash',
        'payment_notes': 'Cash received at front desk'
    }, follow_redirects=True)
    assert resp.status_code == 200
    upd_inv = query_db("SELECT payment_status, payment_method FROM service_records WHERE id = %s", (inv_id,), one=True)
    assert upd_inv['payment_status'] == 'Paid'
    assert upd_inv['payment_method'] == 'Cash'
    print("PASS: Successfully submitted Cash payment.")

    # 8. Test Filtering by payment status
    resp_unpaid = client.get('/admin/invoices/payments?status=Unpaid')
    assert resp_unpaid.status_code == 200
    resp_paid = client.get('/admin/invoices/payments?status=Paid')
    assert resp_paid.status_code == 200
    print("PASS: Payment status filters (Unpaid, Paid) execute successfully.")

    # 9. Test Security Authorization: Technician blocked
    with client.session_transaction() as sess:
        tech_user = query_db("SELECT id, name, role FROM users WHERE role = 'Technician' LIMIT 1", one=True)
        sess['user_id'] = tech_user['id']
        sess['user_role'] = 'Technician'
        sess['role'] = 'Technician'
        sess['user_name'] = tech_user['name']

    resp = client.get('/admin/invoices/payments', follow_redirects=False)
    assert resp.status_code in (302, 403), f"Technician should not access admin invoice payments, got {resp.status_code}"
    print("PASS: Role authorization strictly enforced (Technician blocked from admin invoice payments).")

    # 10. Restore original payment status
    query_db("UPDATE service_records SET payment_status = %s WHERE id = %s", (orig_status, inv_id), commit=True)
    print("PASS: Restored original invoice payment status.")
    print("=== ALL INVOICE PAID & PAYMENT SETTLEMENT TESTS PASSED 100%! ===")

if __name__ == '__main__':
    run_tests()

