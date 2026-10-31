#!/usr/bin/env python3
"""
FleetSync - Spare Parts Module Database Migration & Seeder
Adds 'Spare Parts' role, creates spare_parts, part_requests, and notifications tables.
"""

import sys
from werkzeug.security import generate_password_hash
from db import query_db, get_connection

def run_migration():
    print("=" * 65)
    print("  FleetSync - Spare Parts Module Migration")
    print("=" * 65)

    conn = get_connection(include_db=True)
    cursor = conn.cursor(dictionary=True)

    try:
        # 1. Update users.role to include 'Spare Parts'
        print("[*] Updating users.role ENUM...")
        cursor.execute("""
            ALTER TABLE `users` 
            MODIFY COLUMN `role` ENUM('Admin', 'Technician', 'Service Advisor', 'Spare Parts') 
            NOT NULL DEFAULT 'Technician';
        """)
        conn.commit()
        print("[OK] users.role ENUM updated.")

        # 2. Create spare_parts table
        print("[*] Creating spare_parts table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `spare_parts` (
                `id` INT AUTO_INCREMENT PRIMARY KEY,
                `part_number` VARCHAR(60) NOT NULL UNIQUE,
                `part_name` VARCHAR(150) NOT NULL,
                `category` VARCHAR(60) NOT NULL,
                `quantity` INT NOT NULL DEFAULT 0,
                `min_quantity` INT NOT NULL DEFAULT 5,
                `unit_price` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                `cost_price` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                `shelf_location` VARCHAR(60) DEFAULT 'Warehouse A - Bin 1',
                `supplier` VARCHAR(120) NULL,
                `compatibility` VARCHAR(255) NULL,
                `status` ENUM('In Stock', 'Low Stock', 'Out of Stock') NOT NULL DEFAULT 'In Stock',
                `description` TEXT NULL,
                `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX `idx_part_number` (`part_number`),
                INDEX `idx_part_category` (`category`),
                INDEX `idx_part_status` (`status`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        conn.commit()
        print("[OK] spare_parts table ready.")

        # 3. Create part_requests table
        print("[*] Creating part_requests table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `part_requests` (
                `id` INT AUTO_INCREMENT PRIMARY KEY,
                `service_record_id` INT NOT NULL,
                `technician_id` INT NOT NULL,
                `part_id` INT NULL,
                `part_name` VARCHAR(150) NOT NULL,
                `part_number` VARCHAR(60) NULL,
                `quantity_requested` INT NOT NULL DEFAULT 1,
                `quantity_available` INT NOT NULL DEFAULT 0,
                `status` ENUM(
                    'Waiting for Parts',
                    'Request Sent',
                    'Pending',
                    'Part Available',
                    'Not Available',
                    'Received by Technician',
                    'Repair In Progress',
                    'Completed'
                ) NOT NULL DEFAULT 'Pending',
                `priority` ENUM('Standard', 'Urgent', 'Low') NOT NULL DEFAULT 'Standard',
                `technician_notes` TEXT NULL,
                `parts_dept_notes` TEXT NULL,
                `requested_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX `idx_req_status` (`status`),
                FOREIGN KEY (`service_record_id`) REFERENCES `service_records`(`id`) ON DELETE CASCADE,
                FOREIGN KEY (`technician_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        conn.commit()
        print("[OK] part_requests table ready.")

        # 4. Create notifications table
        print("[*] Creating notifications table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `notifications` (
                `id` INT AUTO_INCREMENT PRIMARY KEY,
                `user_id` INT NOT NULL,
                `title` VARCHAR(150) NOT NULL,
                `message` TEXT NOT NULL,
                `link` VARCHAR(255) NULL,
                `type` VARCHAR(50) DEFAULT 'part_available',
                `is_read` TINYINT(1) NOT NULL DEFAULT 0,
                `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX `idx_notif_user` (`user_id`, `is_read`),
                FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        conn.commit()
        print("[OK] notifications table ready.")

        # 5. Insert or Update default Spare Parts Department User
        print("[*] Seeding default Spare Parts Department staff account...")
        cursor.execute("SELECT id FROM users WHERE email = 'parts@fleetsync.io'")
        existing_parts_user = cursor.fetchone()
        parts_pwd_hash = generate_password_hash("Parts@123")

        if not existing_parts_user:
            cursor.execute("""
                INSERT INTO `users` (`name`, `email`, `password_hash`, `role`, `phone`, `avatar`, `status`)
                VALUES (
                    'Rajesh Kumar',
                    'parts@fleetsync.io',
                    %s,
                    'Spare Parts',
                    '+91 98205 67890',
                    'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=250&q=80',
                    'Active'
                )
            """, (parts_pwd_hash,))
            conn.commit()
            print("[OK] Created 'parts@fleetsync.io' (Rajesh Kumar).")
        else:
            cursor.execute("""
                UPDATE `users` SET `role` = 'Spare Parts', `password_hash` = %s WHERE `email` = 'parts@fleetsync.io'
            """, (parts_pwd_hash,))
            conn.commit()
            print("[OK] Updated 'parts@fleetsync.io' to 'Spare Parts' role.")

        # 6. Seed initial Spare Parts inventory
        print("[*] Seeding initial Spare Parts inventory...")
        cursor.execute("SELECT COUNT(*) as cnt FROM spare_parts")
        parts_count = cursor.fetchone()['cnt']
        if parts_count == 0:
            initial_parts = [
                ('SP-BRK-001', 'OEM Electronic Brake Actuator Sensor Module', 'Brakes', 2, 2, 7800.00, 5200.00, 'Warehouse A - Bay 3', 'Bosch India Automotive', 'Mahindra Bolero / Scorpio-N', 'Low Stock', 'High-precision OEM electric actuator sensor module for ABS and electronic parking brake integration.'),
                ('SP-BRK-002', 'Ceramic Front Brake Pad Set - Commercial Fleet', 'Brakes', 16, 5, 2400.00, 1600.00, 'Warehouse A - Bay 1', 'Brembo India', 'Tata Winger / Force Traveller', 'In Stock', 'High durability fleet grade ceramic brake pads with integrated heat dissipators.'),
                ('SP-ROT-003', 'Brembo Premium UV Coated Vented Front Brake Rotors (Pair)', 'Brakes', 6, 4, 6200.00, 4100.00, 'Warehouse A - Bay 2', 'Brembo India', 'Force Traveller 3350 / Eicher Pro', 'In Stock', 'Anti-corrosion UV coated high-carbon cast iron brake discs for commercial vans.'),
                ('SP-FLT-101', 'High-Flow Heavy Duty Diesel Engine Oil Filter FL-2051S', 'Engine & Filters', 28, 10, 650.00, 420.00, 'Warehouse B - Bin 4', 'Tata Genuine Parts', 'Tata Winger / Intra V30', 'In Stock', 'Micro-glass synthetic blend media filter capturing 99% of engine wear particles.'),
                ('SP-FLT-102', 'Cabin Pollen & Activated Carbon Air Filter', 'Engine & Filters', 19, 8, 850.00, 550.00, 'Warehouse B - Bin 5', 'Mann+Hummel Filters', 'Toyota Innova / BMW 330i', 'In Stock', 'Electrostatic activated charcoal layer eliminating airborne allergens and noxious gases.'),
                ('SP-FLT-103', 'Commercial Dual Diesel Fuel Water Separator Cartridge', 'Engine & Filters', 3, 5, 3800.00, 2600.00, 'Warehouse B - Bin 6', 'Fleetguard India', 'Eicher Pro 2049 / BharatBenz', 'Low Stock', 'Two-stage coalescing fuel water separator kit preventing common-rail injector corrosion.'),
                ('SP-LUB-201', 'Castrol MAGNATEC 5W-30 Full Synthetic (4L Canister)', 'Fluids & Lubricants', 35, 10, 2800.00, 1950.00, 'Warehouse C - Drum Rack', 'Castrol Lubricants India', 'Universal Gasoline & Light Diesel', 'In Stock', 'Dualock molecule technology providing continuous engine protection from startup.'),
                ('SP-TIR-301', 'Apollo Altrust Commercial Highway Tire (235/65R16C)', 'Tires & Wheels', 8, 4, 7500.00, 5600.00, 'Tire Rack - Zone D', 'Apollo Tyres India', 'Tata Winger / Force Traveller / Bolero', 'In Stock', 'Reinforced steel-belted commercial radial tire designed for high mileage logistics.'),
                ('SP-SUS-401', 'Front Stabilizer Anti-Roll Bar Linkage Kit', 'Suspension', 12, 5, 3200.00, 2100.00, 'Warehouse A - Bin 8', 'Mahindra Genuine Parts', 'Mahindra Scorpio-N / Thar', 'In Stock', 'Heavy duty ball joint linkage preventing body roll on uneven transport routes.'),
                ('SP-ELC-501', 'Alternator Voltage Regulator & Heavy Duty Pulley', 'Electrical', 0, 3, 4900.00, 3300.00, 'Warehouse C - Shelf 2', 'Lucas-TVS Automotive', 'Universal 12V Fleet Alternator', 'Out of Stock', 'Solid state precision voltage regulator protecting sensitive fleet telematics hardware.')
            ]

            for p in initial_parts:
                cursor.execute("""
                    INSERT INTO `spare_parts` (
                        `part_number`, `part_name`, `category`, `quantity`, `min_quantity`,
                        `unit_price`, `cost_price`, `shelf_location`, `supplier`, `compatibility`,
                        `status`, `description`
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, p)
            conn.commit()
            print(f"[OK] Seeded {len(initial_parts)} initial spare parts catalog items.")

        # 7. Seed initial technician parts request for WO-2026-0107
        cursor.execute("SELECT id FROM part_requests WHERE service_record_id = 7")
        existing_req = cursor.fetchone()
        if not existing_req:
            cursor.execute("""
                INSERT INTO `part_requests` (
                    `service_record_id`, `technician_id`, `part_id`, `part_name`, `part_number`,
                    `quantity_requested`, `quantity_available`, `status`, `priority`,
                    `technician_notes`, `parts_dept_notes`, `requested_at`
                ) VALUES (
                    7, 2, 1, 'OEM Electronic Brake Actuator Sensor Module', 'SP-BRK-001',
                    1, 0, 'Waiting for Parts', 'Urgent',
                    'Customer vehicle MH-02-CW-8093 awaiting rear actuator module before final brake bleeding and calibration.',
                    'Order placed with Bosch Logistics. Estimated delivery in progress.',
                    '2026-10-02 11:30:00'
                )
            """)
            conn.commit()
            print("[OK] Seeded initial parts request for work order WO-2026-0107.")

        cursor.close()
        conn.close()
        print("=" * 65)
        print("  [SUCCESS] Spare Parts Module Setup Completed!")
        print("  New Login Credentials:")
        print("    Role:     Spare Parts Department")
        print("    Email:    parts@fleetsync.io")
        print("    Password: Parts@123")
        print("=" * 65)

    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        if conn:
            conn.rollback()
            conn.close()
        sys.exit(1)

if __name__ == '__main__':
    run_migration()
