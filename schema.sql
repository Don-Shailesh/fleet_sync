-- ==========================================================
-- FleetSync: Professional Vehicle Service & Maintenance Tracker
-- Database Schema & Comprehensive Demo Data for MySQL (XAMPP)
-- ==========================================================

CREATE DATABASE IF NOT EXISTS `fleetsync_db` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `fleetsync_db`;

-- Drop tables in reverse order of foreign key dependencies
DROP TABLE IF EXISTS `reminders`;
DROP TABLE IF EXISTS `service_items`;
DROP TABLE IF EXISTS `service_records`;
DROP TABLE IF EXISTS `maintenance_schedules`;
DROP TABLE IF EXISTS `vehicles`;
DROP TABLE IF EXISTS `customers`;
DROP TABLE IF EXISTS `users`;

-- ----------------------------------------------------------
-- 1. Users Table (Authentication & Service Roles)
-- ----------------------------------------------------------
CREATE TABLE `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(100) NOT NULL,
    `email` VARCHAR(150) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `role` ENUM('Admin', 'Technician', 'Service Advisor') NOT NULL DEFAULT 'Technician',
    `phone` VARCHAR(30) NULL,
    `avatar` VARCHAR(255) NULL,
    `status` ENUM('Active', 'Inactive') NOT NULL DEFAULT 'Active',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------
-- 2. Customers Table (Fleet Owners & Individual Clients)
-- ----------------------------------------------------------
CREATE TABLE `customers` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(120) NOT NULL,
    `email` VARCHAR(150) NOT NULL,
    `phone` VARCHAR(30) NOT NULL,
    `company_name` VARCHAR(150) NULL,
    `customer_type` ENUM('Fleet / Corporate', 'Individual') NOT NULL DEFAULT 'Individual',
    `address` TEXT NULL,
    `city` VARCHAR(80) NULL,
    `postal_code` VARCHAR(20) NULL,
    `notes` TEXT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_customer_name` (`name`),
    INDEX `idx_customer_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------
-- 3. Vehicles Table
-- ----------------------------------------------------------
CREATE TABLE `vehicles` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `customer_id` INT NOT NULL,
    `vin` VARCHAR(20) NOT NULL UNIQUE,
    `plate_number` VARCHAR(20) NOT NULL UNIQUE,
    `make` VARCHAR(60) NOT NULL,
    `model` VARCHAR(60) NOT NULL,
    `year` INT NOT NULL,
    `color` VARCHAR(40) NULL,
    `fuel_type` ENUM('Gasoline', 'Diesel', 'Electric', 'Hybrid', 'CNG') NOT NULL DEFAULT 'Gasoline',
    `vehicle_type` ENUM('Sedan', 'SUV', 'Pickup Truck', 'Fleet Van', 'Box Truck', 'Hatchback', 'Motorcycle') NOT NULL DEFAULT 'Sedan',
    `current_odometer` INT NOT NULL DEFAULT 0,
    `status` ENUM('Active', 'In Service', 'Maintenance Due', 'Out of Service') NOT NULL DEFAULT 'Active',
    `notes` TEXT NULL,
    `image_url` VARCHAR(255) NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`customer_id`) REFERENCES `customers`(`id`) ON DELETE CASCADE,
    INDEX `idx_vehicle_plate` (`plate_number`),
    INDEX `idx_vehicle_vin` (`vin`),
    INDEX `idx_vehicle_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------
-- 4. Maintenance Schedules (Preventive Service Rules)
-- ----------------------------------------------------------
CREATE TABLE `maintenance_schedules` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `vehicle_id` INT NOT NULL,
    `service_name` VARCHAR(120) NOT NULL,
    `interval_km` INT NOT NULL DEFAULT 5000,
    `interval_months` INT NOT NULL DEFAULT 6,
    `last_service_date` DATE NULL,
    `last_service_odometer` INT NULL DEFAULT 0,
    `next_due_date` DATE NOT NULL,
    `next_due_odometer` INT NOT NULL,
    `priority` ENUM('Low', 'Medium', 'High', 'Critical') NOT NULL DEFAULT 'Medium',
    `status` ENUM('Upcoming', 'Due Soon', 'Overdue', 'Completed') NOT NULL DEFAULT 'Upcoming',
    `description` TEXT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`vehicle_id`) REFERENCES `vehicles`(`id`) ON DELETE CASCADE,
    INDEX `idx_schedule_status` (`status`),
    INDEX `idx_schedule_due_date` (`next_due_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------
-- 5. Service Records / Work Orders
-- ----------------------------------------------------------
CREATE TABLE `service_records` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `invoice_number` VARCHAR(30) NOT NULL UNIQUE,
    `vehicle_id` INT NOT NULL,
    `user_id` INT NULL,
    `service_date` DATE NOT NULL,
    `odometer` INT NOT NULL,
    `service_type` VARCHAR(100) NOT NULL,
    `status` ENUM('Pending', 'In Progress', 'Waiting for Parts', 'Completed', 'Cancelled') NOT NULL DEFAULT 'In Progress',
    `description` TEXT NULL,
    `technician_notes` TEXT NULL,
    `parts_cost` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    `labor_cost` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    `tax_amount` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    `total_cost` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    `payment_status` ENUM('Unpaid', 'Partially Paid', 'Paid') NOT NULL DEFAULT 'Unpaid',
    `completed_at` DATETIME NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`vehicle_id`) REFERENCES `vehicles`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE SET NULL,
    INDEX `idx_service_invoice` (`invoice_number`),
    INDEX `idx_service_status` (`status`),
    INDEX `idx_service_date` (`service_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------
-- 6. Service Line Items (Parts & Labor Detail)
-- ----------------------------------------------------------
CREATE TABLE `service_items` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `service_record_id` INT NOT NULL,
    `item_type` ENUM('Part', 'Labor', 'Inspection', 'Fee') NOT NULL DEFAULT 'Part',
    `item_name` VARCHAR(150) NOT NULL,
    `quantity` DECIMAL(8,2) NOT NULL DEFAULT 1.00,
    `unit_price` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    `total_price` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    FOREIGN KEY (`service_record_id`) REFERENCES `service_records`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ----------------------------------------------------------
-- 7. Automated Reminders Log
-- ----------------------------------------------------------
CREATE TABLE `reminders` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `vehicle_id` INT NOT NULL,
    `customer_id` INT NOT NULL,
    `schedule_id` INT NULL,
    `reminder_type` ENUM('Service Due', 'Inspection Expiry', 'General Follow-up', 'Custom Alert') NOT NULL DEFAULT 'Service Due',
    `channel` ENUM('Email', 'SMS', 'WhatsApp', 'System') NOT NULL DEFAULT 'Email',
    `status` ENUM('Scheduled', 'Sent', 'Failed', 'Cancelled') NOT NULL DEFAULT 'Scheduled',
    `reminder_date` DATE NOT NULL,
    `message_preview` TEXT NOT NULL,
    `sent_at` DATETIME NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`vehicle_id`) REFERENCES `vehicles`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`customer_id`) REFERENCES `customers`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`schedule_id`) REFERENCES `maintenance_schedules`(`id`) ON DELETE SET NULL,
    INDEX `idx_reminder_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ==========================================================
-- SEED DATA: Realistic Enterprise Data (Indian Region)
-- ==========================================================

-- Seed Users (Passwords: Admin@123 / Tech@123)
INSERT INTO `users` (`id`, `name`, `email`, `password_hash`, `role`, `phone`, `avatar`, `status`) VALUES
(1, 'Shailesh Dongare', 'admin@fleetsync.io', 'scrypt:32768:8:1$QeIbAPNuCWJeXA3U$ced6ec2ef7f93ffe760afc5549c37c0b710dc8f61a0cba05edf0462e2f793b29acc20a3e23f04418f79647adb6ab1f14a98dbe4daa7238f562f60f655e83873c', 'Admin', '+91 98201 23456', 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=250&q=80', 'Active'),
(2, 'Suresh Verma', 'tech@fleetsync.io', 'scrypt:32768:8:1$pHKJL6n6rkSHUBA6$579c9f612b6340468ade321592242fec7e603a4e44795d78158e4472fa43ba2de3f9dda0eedc7ae148005e68f528786e253138ef6c2ee6da9b238c670ddec145', 'Technician', '+91 98334 56789', 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=250&q=80', 'Active');

-- Seed Customers
INSERT INTO `customers` (`id`, `name`, `email`, `phone`, `company_name`, `customer_type`, `address`, `city`, `postal_code`, `notes`) VALUES
(1, 'Ananya Deshmukh', 'ananya.deshmukh@apexlogistics.in', '+91 98210 12345', 'Apex Logistics India Pvt Ltd', 'Fleet / Corporate', 'Plot C-14, MIDC Industrial Area, Andheri East', 'Mumbai', '400093', 'Enterprise account with 15 delivery vans. Priority turnaround needed.'),
(2, 'Rohan Kapoor', 'rohan.kapoor@metrocargo.in', '+91 98112 34567', 'Metro Fast Express Logistics Ltd', 'Fleet / Corporate', '45 Barakhamba Road, Connaught Place', 'New Delhi', '110001', 'Bimonthly scheduled maintenance contract.'),
(3, 'Pooja Iyer', 'pooja.iyer@gmail.com', '+91 98450 98765', NULL, 'Individual', '822 4th Cross, Koramangala 4th Block', 'Bengaluru', '560034', 'VIP customer, family fleet of 2 luxury vehicles.'),
(4, 'Vikram Malhotra', 'vikram.malhotra@horizonhaul.in', '+91 98791 43210', 'Horizon National Transport Carriers', 'Fleet / Corporate', 'Phase II, GIDC Industrial Estate, Vatva', 'Ahmedabad', '382445', 'Heavy duty diesel fleet accounts.'),
(5, 'Arjun Nair', 'arjun.nair@outlook.com', '+91 98490 54321', NULL, 'Individual', 'Flat 402, Banjara Greens, Road No. 12, Banjara Hills', 'Hyderabad', '500034', 'Personal SUV regular commuter maintenance.');

-- Seed Vehicles
INSERT INTO `vehicles` (`id`, `customer_id`, `vin`, `plate_number`, `make`, `model`, `year`, `color`, `fuel_type`, `vehicle_type`, `current_odometer`, `status`, `notes`, `image_url`) VALUES
(1, 1, '1FTNE3Y89KDB41092', 'MH-02-CW-8092', 'Tata', 'Winger Maxi Van', 2023, 'Frozen White', 'Diesel', 'Fleet Van', 48250, 'Active', 'Route vehicle #04. High daily mileage Mumbai-Pune run.', 'https://images.unsplash.com/photo-1559297434-fae8a1916a79?auto=format&fit=crop&w=600&q=80'),
(2, 1, '1FTNE3Y88KDB41093', 'MH-02-CW-8093', 'Mahindra', 'Bolero Maxi Truck Plus', 2023, 'Frozen White', 'Diesel', 'Pickup Truck', 52100, 'Maintenance Due', 'Route vehicle #05. Brake pads sensor flagged.', 'https://images.unsplash.com/photo-1541899481282-d53bffe3c35d?auto=format&fit=crop&w=600&q=80'),
(3, 2, 'WD4PF4CC5LT128471', 'DL-01-AX-4011', 'Force Motors', 'Traveller 3350 Delivery Van', 2024, 'Obsidian Black', 'Diesel', 'Fleet Van', 31500, 'In Service', 'Undergoing 30,000 km comprehensive service.', 'https://images.unsplash.com/photo-1563720223185-11003d516935?auto=format&fit=crop&w=600&q=80'),
(4, 2, 'WD4PF4CC7LT128499', 'DL-01-AX-4012', 'Force Motors', 'Traveller Cargo Express', 2022, 'Arctic White', 'Diesel', 'Fleet Van', 74800, 'Active', 'Scheduled for transmission flush next month.', 'https://images.unsplash.com/photo-1517524008697-84bbe3c3fd98?auto=format&fit=crop&w=600&q=80'),
(5, 3, '4T1C11AK8PU192847', 'KA-03-MY-9921', 'Toyota', 'Innova HyCross Hybrid', 2024, 'Blueprint Blue', 'Hybrid', 'SUV', 18400, 'Active', 'Maintained strictly with OEM synthetic oils.', 'https://images.unsplash.com/photo-1617814076367-b759c7d7e738?auto=format&fit=crop&w=600&q=80'),
(6, 3, 'WBA33AY09NFP82014', 'KA-03-NB-3301', 'BMW', '330i Gran Limousine M Sport', 2023, 'Mineral Grey', 'Gasoline', 'Sedan', 24100, 'Active', 'Performance tire alignment requested.', 'https://images.unsplash.com/photo-1555215695-3004980ad54e?auto=format&fit=crop&w=600&q=80'),
(7, 4, '1HTMMAAL9NH839102', 'GJ-01-ZZ-7019', 'Eicher', 'Pro 2049 Commercial Box Truck', 2021, 'White', 'Diesel', 'Box Truck', 112400, 'Maintenance Due', 'Heavy hauling. Annual RTO commercial fitness inspection due.', 'https://images.unsplash.com/photo-1601584115197-04ecc0da31d7?auto=format&fit=crop&w=600&q=80'),
(8, 5, '3C6UR5DL7MG649201', 'TS-09-UB-5541', 'Mahindra', 'Scorpio-N 4Xplor Diesel', 2022, 'Granite Crystal', 'Diesel', 'SUV', 41200, 'Active', 'Towing package installed. Clean history.', 'https://images.unsplash.com/photo-1583121274602-3e2820c69888?auto=format&fit=crop&w=600&q=80');

-- Seed Maintenance Schedules
INSERT INTO `maintenance_schedules` (`id`, `vehicle_id`, `service_name`, `interval_km`, `interval_months`, `last_service_date`, `last_service_odometer`, `next_due_date`, `next_due_odometer`, `priority`, `status`, `description`) VALUES
(1, 1, 'Full Synthetic Engine Oil & Filter Change', 8000, 6, '2026-05-15', 40000, '2026-11-15', 48000, 'High', 'Due Soon', 'Mobil 1 Full Synthetic 5W-30 + OEM filter cartridge'),
(2, 2, 'Front & Rear Ceramic Brake Pads Replacement', 25000, 12, '2025-09-10', 27000, '2026-09-10', 52000, 'Critical', 'Overdue', 'Rotor thickness check and sensor harness replacement'),
(3, 3, 'Comprehensive 30k Inspection & Diagnostics', 30000, 12, '2025-10-20', 1000, '2026-10-20', 31000, 'High', 'Due Soon', 'Fluids, steering rack, suspension bushings, and battery test'),
(4, 4, 'Automatic Transmission Fluid & Filter Flush', 40000, 24, '2024-11-01', 35000, '2026-11-01', 75000, 'Medium', 'Upcoming', 'Full ATF fluid replacement and pan gasket seal'),
(5, 5, 'Hybrid Battery Air Intake Cleaning & Tire Rotation', 10000, 6, '2026-04-12', 10000, '2026-10-12', 20000, 'Low', 'Upcoming', 'Rotate and balance 4 tires, check hybrid cooling duct'),
(6, 6, 'Brake Fluid Flush & Multi-Point Tech Scan', 20000, 24, '2025-06-18', 12000, '2026-06-18', 32000, 'Medium', 'Upcoming', 'DOT 4 high-temp brake fluid flush'),
(7, 7, 'Commercial Diesel DPF Regeneration & Fuel Filter', 15000, 6, '2026-03-01', 97000, '2026-09-01', 112000, 'Critical', 'Overdue', 'Primary & secondary fuel filters and DPF soot burn cycle'),
(8, 8, 'Differential Fluid Service & Wheel Alignment', 30000, 24, '2025-08-05', 25000, '2026-08-05', 55000, 'Medium', 'Upcoming', '75W-90 synthetic gear lube and computerized 4-wheel alignment');

-- Seed Work Orders / Service Records
INSERT INTO `service_records` (`id`, `invoice_number`, `vehicle_id`, `user_id`, `service_date`, `odometer`, `service_type`, `status`, `description`, `technician_notes`, `parts_cost`, `labor_cost`, `tax_amount`, `total_cost`, `payment_status`, `completed_at`) VALUES
(1, 'WO-2026-0101', 1, 1, '2026-05-15', 40120, 'Preventive Maintenance', 'Completed', 'Standard 40k fleet service package. Oil, filters, inspection.', 'Vehicle in excellent condition. Tires have 7mm tread depth remaining.', 4300.00, 1500.00, 464.00, 6264.00, 'Paid', '2026-05-15 15:30:00'),
(2, 'WO-2026-0102', 2, 2, '2026-07-02', 49200, 'Tire Replacement & Balancing', 'Completed', 'Replaced all 4 all-season commercial highway tires.', 'Mounted Apollo Altrust commercial grade tires. Torque set to 148 ft-lbs.', 30000.00, 2000.00, 2560.00, 34560.00, 'Paid', '2026-07-02 17:15:00'),
(3, 'WO-2026-0103', 3, 2, '2026-10-01', 31500, 'Brake System Overhaul', 'In Progress', 'Customer reported slight vibration during heavy payload braking.', 'Inspecting front rotors for heat warping. Calipers cleaned and lubricated.', 11000.00, 2500.00, 1080.00, 14580.00, 'Unpaid', NULL),
(4, 'WO-2026-0104', 5, 1, '2026-04-12', 10150, 'Scheduled 10k Warranty Check', 'Completed', 'First warranty inspection, tire rotation, fluid top-up.', 'ECU software updated to version 4.2. Hybrid battery state of health 99.4%.', 3500.00, 1800.00, 424.00, 5724.00, 'Paid', '2026-04-12 11:45:00'),
(5, 'WO-2026-0105', 7, 2, '2026-03-01', 97200, 'Heavy Commercial Service', 'Completed', 'DPF soot burn, oil service, hydraulic brake bleed.', 'Replaced secondary fuel filter due to water separation indicator light.', 10300.00, 4200.00, 1160.00, 15660.00, 'Paid', '2026-03-01 18:00:00'),
(6, 'WO-2026-0106', 8, 1, '2026-08-05', 38900, 'Suspension Inspection & Service', 'Completed', 'Front stabilizer link replacement and realignment.', 'Test drove 8 km on outer ring road, alignment centered, zero drift.', 3200.00, 2400.00, 448.00, 6048.00, 'Paid', '2026-08-05 16:30:00'),
(7, 'WO-2026-0107', 2, 2, '2026-10-02', 52100, 'Emergency Brake Service', 'Waiting for Parts', 'Awaiting OEM rear electronic parking brake actuator module.', 'Parts ordered via express courier. Expected arrival tomorrow 9 AM.', 7800.00, 2200.00, 800.00, 10800.00, 'Unpaid', NULL);

-- Seed Service Line Items
INSERT INTO `service_items` (`id`, `service_record_id`, `item_type`, `item_name`, `quantity`, `unit_price`, `total_price`) VALUES
(1, 1, 'Part', 'Castrol MAGNATEC 5W-30 Full Synthetic (4 Liters)', 1.00, 2800.00, 2800.00),
(2, 1, 'Part', 'Tata Genuine High-Flow Engine Oil Filter FL-2051S', 1.00, 650.00, 650.00),
(3, 1, 'Part', 'Cabin Pollen & Activated Carbon Air Filter', 1.00, 850.00, 850.00),
(4, 1, 'Labor', 'Standard Lube, Oil & Multi-Point Inspection Labor', 1.00, 1500.00, 1500.00),
(5, 2, 'Part', 'Apollo Altrust Commercial Highway Tire (235/65R16C)', 4.00, 7500.00, 30000.00),
(6, 2, 'Labor', 'Mount, Dynamic Digital Road-Force Balance, & Disposal', 4.00, 500.00, 2000.00),
(7, 3, 'Part', 'Genuine Force Traveller Front Brake Pad Set', 1.00, 4800.00, 4800.00),
(8, 3, 'Part', 'Brembo Premium UV Coated Vented Front Brake Rotors (Pair)', 1.00, 6200.00, 6200.00),
(9, 3, 'Labor', 'Front Brake Rotors & Pads R&R + Caliper Slide Lube', 2.00, 1250.00, 2500.00),
(10, 4, 'Part', 'Toyota Genuine 0W-16 Advanced Fuel Economy Synthetic Oil (5L)', 1.00, 3500.00, 3500.00),
(11, 4, 'Labor', 'Multi-Point Hybrid Systems Diagnostic Scan & Service', 1.00, 1800.00, 1800.00),
(12, 5, 'Part', 'Eicher Commercial Dual Fuel Filter Cartridge Kit', 1.00, 3800.00, 3800.00),
(13, 5, 'Part', 'Servo Pride Heavy Duty Diesel Engine Oil (15L Canister)', 1.00, 6500.00, 6500.00),
(14, 5, 'Labor', 'Commercial Diesel Maintenance & Forced DPF Regeneration', 1.00, 4200.00, 4200.00),
(15, 6, 'Part', 'Mahindra Genuine Front Stabilizer Bar Link Kit', 1.00, 3200.00, 3200.00),
(16, 6, 'Labor', 'Suspension R&R and Hunter Digital Alignment', 1.00, 2400.00, 2400.00),
(17, 7, 'Part', 'OEM Electronic Brake Actuator Sensor Module', 1.00, 7800.00, 7800.00),
(18, 7, 'Labor', 'Rear Caliper Actuator Replacement & Computer Calibration', 1.00, 2200.00, 2200.00);

-- Seed Reminders
INSERT INTO `reminders` (`id`, `vehicle_id`, `customer_id`, `schedule_id`, `reminder_type`, `channel`, `status`, `reminder_date`, `message_preview`, `sent_at`) VALUES
(1, 2, 1, 2, 'Service Due', 'Email', 'Scheduled', '2026-10-02', 'URGENT MAINTENANCE: Vehicle MH-02-CW-8093 (Mahindra Bolero Maxi Truck) is overdue for Ceramic Brake Pads Replacement at 52,100 km. Please schedule service immediately.', NULL),
(2, 7, 4, 7, 'Service Due', 'Email', 'Scheduled', '2026-10-02', 'CRITICAL FLEET NOTICE: Truck GJ-01-ZZ-7019 (Eicher Pro 2049) is overdue for Diesel DPF & Fuel Filter service (Odometer: 112,400 km).', NULL),
(3, 1, 1, 1, 'Service Due', 'WhatsApp', 'Scheduled', '2026-10-05', 'FleetSync Alert: Tata Winger MH-02-CW-8092 is approaching scheduled 48,000 km oil service. Click to book technician appointment.', NULL),
(4, 3, 2, 3, 'Service Due', 'SMS', 'Sent', '2026-09-28', 'FleetSync: Force Traveller DL-01-AX-4011 30k Inspection is due on Oct 20. Your appointment is confirmed for today.', '2026-09-28 09:15:00'),
(5, 5, 3, 5, 'General Follow-up', 'Email', 'Sent', '2026-09-15', 'Dear Pooja, Your Toyota Innova HyCross Hybrid (KA-03-MY-9921) has an upcoming service in 1,600 km. Book anytime at FleetSync Portal.', '2026-09-15 14:20:00');
