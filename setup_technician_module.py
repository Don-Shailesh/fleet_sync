#!/usr/bin/env python3
"""
FleetSync - Technician Module Database Migration & Seeder
Extends users, service_records, part_requests, creates service_reports table,
and updates existing technician records with rich profile data.
"""

from db import query_db, get_connection

def run_migration():
    print("=" * 65)
    print("  FleetSync - Technician Module Database Migration")
    print("=" * 65)

    conn = get_connection(include_db=True)
    cursor = conn.cursor(dictionary=True)

    try:
        # 1. Update users table with technician profile fields
        print("[*] Adding technician profile fields to 'users' table...")
        cursor.execute("DESCRIBE users")
        user_cols = [c['Field'] for c in cursor.fetchall()]

        if 'technician_code' not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN technician_code VARCHAR(30) NULL AFTER role")
        if 'skills' not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN skills VARCHAR(255) NULL AFTER technician_code")
        if 'specialization' not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN specialization VARCHAR(150) NULL AFTER skills")
        if 'availability_status' not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN availability_status ENUM('Available', 'Busy', 'On Leave') NOT NULL DEFAULT 'Available' AFTER specialization")

        conn.commit()
        print("[OK] 'users' table updated with technician fields.")

        # 2. Update service_records status ENUM & appointment/priority/reschedule fields
        print("[*] Updating 'service_records' table with priority, appointment & reschedule fields...")
        cursor.execute("""
            ALTER TABLE service_records 
            MODIFY COLUMN `status` ENUM('Pending', 'Accepted', 'In Progress', 'Waiting for Parts', 'On Hold', 'Completed', 'Cancelled') 
            NOT NULL DEFAULT 'Pending';
        """)

        cursor.execute("DESCRIBE service_records")
        sr_cols = [c['Field'] for c in cursor.fetchall()]

        if 'priority' not in sr_cols:
            cursor.execute("ALTER TABLE service_records ADD COLUMN priority ENUM('Low', 'Medium', 'High', 'Critical') NOT NULL DEFAULT 'Medium' AFTER status")
        if 'appointment_date' not in sr_cols:
            cursor.execute("ALTER TABLE service_records ADD COLUMN appointment_date DATE NULL AFTER service_date")
        if 'appointment_time' not in sr_cols:
            cursor.execute("ALTER TABLE service_records ADD COLUMN appointment_time TIME NULL AFTER appointment_date")
        if 'reschedule_requested' not in sr_cols:
            cursor.execute("ALTER TABLE service_records ADD COLUMN reschedule_requested TINYINT(1) NOT NULL DEFAULT 0 AFTER technician_notes")
        if 'reschedule_date' not in sr_cols:
            cursor.execute("ALTER TABLE service_records ADD COLUMN reschedule_date DATE NULL AFTER reschedule_requested")
        if 'reschedule_time' not in sr_cols:
            cursor.execute("ALTER TABLE service_records ADD COLUMN reschedule_time TIME NULL AFTER reschedule_date")
        if 'reschedule_reason' not in sr_cols:
            cursor.execute("ALTER TABLE service_records ADD COLUMN reschedule_reason TEXT NULL AFTER reschedule_time")
        if 'customer_feedback' not in sr_cols:
            cursor.execute("ALTER TABLE service_records ADD COLUMN customer_feedback TEXT NULL AFTER reschedule_reason")
        if 'customer_rating' not in sr_cols:
            cursor.execute("ALTER TABLE service_records ADD COLUMN customer_rating TINYINT NULL AFTER customer_feedback")

        # Backfill appointment_date with service_date where NULL
        cursor.execute("UPDATE service_records SET appointment_date = service_date WHERE appointment_date IS NULL")
        # Backfill appointment_time with default 10:00:00 where NULL
        cursor.execute("UPDATE service_records SET appointment_time = '10:00:00' WHERE appointment_time IS NULL")

        conn.commit()
        print("[OK] 'service_records' table updated.")

        # 3. Create service_reports table
        print("[*] Creating 'service_reports' table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `service_reports` (
                `id` INT AUTO_INCREMENT PRIMARY KEY,
                `service_record_id` INT NOT NULL UNIQUE,
                `technician_id` INT NOT NULL,
                `diagnosis` TEXT NOT NULL,
                `work_performed` TEXT NOT NULL,
                `solution_provided` TEXT NOT NULL,
                `parts_used_summary` TEXT NULL,
                `remarks` TEXT NULL,
                `before_image_url` VARCHAR(255) NULL,
                `after_image_url` VARCHAR(255) NULL,
                `completion_date` DATE NOT NULL,
                `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX `idx_report_service` (`service_record_id`),
                INDEX `idx_report_tech` (`technician_id`),
                FOREIGN KEY (`service_record_id`) REFERENCES `service_records`(`id`) ON DELETE CASCADE,
                FOREIGN KEY (`technician_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        conn.commit()
        print("[OK] 'service_reports' table ready.")

        # 4. Update part_requests status ENUM and fields
        print("[*] Updating 'part_requests' table...")
        cursor.execute("""
            ALTER TABLE part_requests 
            MODIFY COLUMN `status` ENUM(
                'Waiting for Parts',
                'Request Sent',
                'Pending',
                'Approved',
                'Part Available',
                'Issued',
                'Not Available',
                'Rejected',
                'Received by Technician',
                'Repair In Progress',
                'Used in Service',
                'Completed'
            ) NOT NULL DEFAULT 'Pending';
        """)

        cursor.execute("DESCRIBE part_requests")
        pr_cols = [c['Field'] for c in cursor.fetchall()]

        if 'quantity_used' not in pr_cols:
            cursor.execute("ALTER TABLE part_requests ADD COLUMN quantity_used INT NOT NULL DEFAULT 0 AFTER quantity_available")
        if 'reason' not in pr_cols:
            cursor.execute("ALTER TABLE part_requests ADD COLUMN reason TEXT NULL AFTER priority")
        if 'issued_at' not in pr_cols:
            cursor.execute("ALTER TABLE part_requests ADD COLUMN issued_at DATETIME NULL AFTER fulfilled_at")

        conn.commit()
        print("[OK] 'part_requests' table updated.")

        # 5. Seed / update Technician profiles
        print("[*] Seeding technician profile info...")
        cursor.execute("""
            UPDATE users 
            SET technician_code = 'TECH-101',
                skills = 'Brake Systems, Multi-Point Electronic Diagnostics, Suspension & Steering',
                specialization = 'Commercial Fleets & Heavy Duty Diesels',
                availability_status = 'Available'
            WHERE email = 'tech@fleetsync.io'
        """)

        # Add second technician for assignment testing if not present
        cursor.execute("SELECT id FROM users WHERE email = 'amit.tech@fleetsync.io'")
        if not cursor.fetchone():
            from werkzeug.security import generate_password_hash
            pwd_hash = generate_password_hash("Tech@123")
            cursor.execute("""
                INSERT INTO users (name, email, password_hash, role, phone, avatar, status, technician_code, skills, specialization, availability_status)
                VALUES (
                    'Amit Sharma',
                    'amit.tech@fleetsync.io',
                    %s,
                    'Technician',
                    '+91 98450 11223',
                    'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=250&q=80',
                    'Active',
                    'TECH-102',
                    'Engine Overhaul, Hybrid Powertrain, Transmission Flush, HVAC Servicing',
                    'Hybrid & High-Efficiency Powertrains',
                    'Available'
                )
            """, (pwd_hash,))
            print("[OK] Added second technician 'amit.tech@fleetsync.io' (Amit Sharma).")

        # 6. Seed demo service reports for completed service records (WO-2026-0101, WO-2026-0102) if not already present
        cursor.execute("SELECT id FROM service_records WHERE invoice_number = 'WO-2026-0101'")
        wo1 = cursor.fetchone()
        if wo1:
            cursor.execute("SELECT id FROM service_reports WHERE service_record_id = %s", (wo1['id'],))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO service_reports 
                    (service_record_id, technician_id, diagnosis, work_performed, solution_provided, parts_used_summary, remarks, completion_date)
                    VALUES (%s, 1, 
                        'Routine 40,000 km preventive inspection. Oil degradation observed as normal for mileage.',
                        'Drained engine oil, replaced oil filter cartridge, installed new activated carbon cabin filter, performed 32-point safety inspection.',
                        'Vehicle restored to factory operating parameters with full synthetic Castrol 5W-30.',
                        '1x Castrol MAGNATEC 5W-30, 1x High-Flow Filter FL-2051S, 1x Cabin Air Filter',
                        'Customer advised to check tire pressures monthly. Next service due at 48,000 km.',
                        '2026-05-15'
                    )
                """, (wo1['id'],))

        conn.commit()
        print("[SUCCESS] Technician module database migration complete!")

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Migration failed: {e}")
        raise e
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    run_migration()

