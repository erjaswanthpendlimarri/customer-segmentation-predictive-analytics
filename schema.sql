CREATE DATABASE IF NOT EXISTS ecommerce_bi;
USE ecommerce_bi;

CREATE TABLE IF NOT EXISTS products (
    product_id INT PRIMARY KEY,
    product_name VARCHAR(120) NOT NULL,
    category VARCHAR(80) NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id INT PRIMARY KEY,
    order_date DATE NOT NULL,
    order_status VARCHAR(30) NOT NULL,
    region VARCHAR(80) NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    item_id INT PRIMARY KEY,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(12,2) NOT NULL,
    discount_amount DECIMAL(12,2) DEFAULT 0,
    return_amount DECIMAL(12,2) DEFAULT 0,
    CONSTRAINT fk_items_order FOREIGN KEY (order_id) REFERENCES orders(order_id),
    CONSTRAINT fk_items_product FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- DEMONSTRATION DATA ONLY. Replace with your own verified records before reporting actual business results.
INSERT IGNORE INTO products VALUES
(1, 'Rice 5 kg', 'Rice & Grains'),
(2, 'Toor Dal 1 kg', 'Pulses'),
(3, 'Green Gram 1 kg', 'Pulses'),
(4, 'Wheat Flour 5 kg', 'Flour'),
(5, 'Groundnut Seeds 1 kg', 'Seeds'),
(6, 'Red Chilli Powder 200 g', 'Spices');

INSERT IGNORE INTO orders VALUES
(1001, '2026-01-05', 'Completed', 'Tirupati'),
(1002, '2026-01-18', 'Completed', 'Kadapa'),
(1003, '2026-02-02', 'Completed', 'Tirupati'),
(1004, '2026-02-12', 'Cancelled', 'Nellore'),
(1005, '2026-02-22', 'Completed', 'Chittoor'),
(1006, '2026-03-04', 'Completed', 'Kadapa'),
(1007, '2026-03-17', 'Completed', 'Tirupati'),
(1008, '2026-04-08', 'Completed', 'Nellore'),
(1009, '2026-04-21', 'Completed', 'Chittoor'),
(1010, '2026-05-03', 'Completed', 'Tirupati'),
(1011, '2026-05-19', 'Completed', 'Kadapa'),
(1012, '2026-06-11', 'Completed', 'Nellore'),
(1013, '2026-06-26', 'Completed', 'Tirupati'),
(1014, '2026-07-09', 'Completed', 'Chittoor'),
(1015, '2026-07-23', 'Completed', 'Kadapa'),
(1016, '2026-08-14', 'Completed', 'Tirupati'),
(1017, '2026-09-02', 'Completed', 'Nellore'),
(1018, '2026-09-18', 'Completed', 'Kadapa'),
(1019, '2026-10-04', 'Completed', 'Tirupati'),
(1020, '2026-10-12', 'Completed', 'Chittoor');

INSERT IGNORE INTO order_items VALUES
(1,1001,1,2,320,0,0),(2,1001,2,1,145,5,0),
(3,1002,3,2,130,0,0),(4,1002,5,1,180,0,0),
(5,1003,1,1,320,10,0),(6,1003,4,1,260,0,0),
(7,1004,2,3,145,0,0),
(8,1005,3,2,130,0,0),(9,1005,6,2,85,0,0),
(10,1006,1,3,320,20,0),(11,1006,2,2,145,0,0),
(12,1007,4,2,260,0,0),(13,1007,5,2,180,0,0),
(14,1008,1,2,320,0,0),(15,1008,6,3,85,0,0),
(16,1009,2,4,145,15,0),(17,1009,3,2,130,0,0),
(18,1010,1,3,320,0,0),(19,1010,4,1,260,0,0),
(20,1011,5,3,180,10,0),(21,1011,2,2,145,0,0),
(22,1012,3,4,130,0,0),(23,1012,6,4,85,5,0),
(24,1013,1,2,320,0,0),(25,1013,2,3,145,0,0),
(26,1014,4,3,260,0,0),(27,1014,5,1,180,0,0),
(28,1015,3,3,130,0,0),(29,1015,6,2,85,0,0),
(30,1016,1,4,320,25,0),(31,1016,2,2,145,0,0),
(32,1017,5,2,180,0,0),(33,1017,4,2,260,0,0),
(34,1018,1,1,320,0,0),(35,1018,3,3,130,0,0),
(36,1019,2,3,145,0,0),(37,1019,6,2,85,0,0),
(38,1020,1,2,320,0,0),(39,1020,5,2,180,0,0);
