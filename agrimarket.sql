-- ============================================================
-- AgriMarket Database Schema
-- ============================================================
CREATE DATABASE IF NOT EXISTS `agripy`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `agripy`;

-- ============================================================
-- USERS (all roles)
-- ============================================================
CREATE TABLE IF NOT EXISTS `users` (
  `id`              INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  `full_name`       VARCHAR(120)  NOT NULL,
  `email`           VARCHAR(150)  NOT NULL UNIQUE,
  `password_hash`   VARCHAR(255)  NOT NULL,
  `role`            ENUM('admin','farmer','buyer','driver') NOT NULL DEFAULT 'buyer',
  `phone`           VARCHAR(20)   NULL,
  `address`         TEXT          NULL,
  `lat`             DECIMAL(10,7) NULL,
  `lng`             DECIMAL(10,7) NULL,
  `profile_photo`   VARCHAR(255)  NULL,
  `is_approved`     TINYINT(1)    NOT NULL DEFAULT 0,
  `is_active`       TINYINT(1)    NOT NULL DEFAULT 1,
  `created_at`      TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_role` (`role`),
  INDEX `idx_approved` (`is_approved`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- FARMER PROFILES
-- ============================================================
CREATE TABLE IF NOT EXISTS `farmer_profiles` (
  `id`           INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id`      INT UNSIGNED NOT NULL UNIQUE,
  `farm_name`    VARCHAR(150) NOT NULL,
  `farm_location`TEXT         NULL,
  `lat`          DECIMAL(10,7) NULL,
  `lng`          DECIMAL(10,7) NULL,
  `product_type` VARCHAR(100) NULL,
  `valid_id_path`VARCHAR(255) NULL,
  `rating`       DECIMAL(3,2) DEFAULT 0.00,
  `rating_count` INT UNSIGNED DEFAULT 0,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_fp_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- DRIVER PROFILES
-- ============================================================
CREATE TABLE IF NOT EXISTS `driver_profiles` (
  `id`               INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id`          INT UNSIGNED NOT NULL UNIQUE,
  `vehicle_type`     VARCHAR(80)  NULL,
  `license_number`   VARCHAR(50)  NULL,
  `availability`     ENUM('available','busy','offline') DEFAULT 'available',
  `current_location` VARCHAR(255) NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_dp_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- CATEGORIES
-- ============================================================
CREATE TABLE IF NOT EXISTS `categories` (
  `id`    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name`  VARCHAR(80)  NOT NULL UNIQUE,
  `icon`  VARCHAR(10)  DEFAULT '🌿',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO `categories` (`name`, `icon`) VALUES
('Vegetables','🥦'),('Fruits','🍎'),('Grains','🌾'),
('Livestock','🐄'),('Dairy','🥛'),('Herbs','🌿'),
('Fertilizers','🧪'),('Seeds','🌱'),('Tools','🔧')
ON DUPLICATE KEY UPDATE `icon`=VALUES(`icon`);

-- ============================================================
-- PRODUCTS
-- ============================================================
CREATE TABLE IF NOT EXISTS `products` (
  `id`          INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  `farmer_id`   INT UNSIGNED  NOT NULL,
  `category_id` INT UNSIGNED  NULL,
  `name`        VARCHAR(150)  NOT NULL,
  `description` TEXT          NULL,
  `price`       DECIMAL(10,2) NOT NULL,
  `quantity`    INT UNSIGNED  NOT NULL DEFAULT 0,
  `unit`        VARCHAR(30)   DEFAULT 'kg',
  `image_path`  VARCHAR(255)  NULL,
  `is_featured` TINYINT(1)    DEFAULT 0,
  `status`      ENUM('active','inactive') DEFAULT 'active',
  `created_at`  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
  `updated_at`  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_farmer` (`farmer_id`),
  INDEX `idx_category` (`category_id`),
  INDEX `idx_featured` (`is_featured`),
  CONSTRAINT `fk_prod_farmer` FOREIGN KEY (`farmer_id`)   REFERENCES `users`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_prod_cat`    FOREIGN KEY (`category_id`) REFERENCES `categories`(`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- CART ITEMS
-- ============================================================
CREATE TABLE IF NOT EXISTS `cart_items` (
  `id`         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id`    INT UNSIGNED NOT NULL,
  `product_id` INT UNSIGNED NOT NULL,
  `quantity`   INT UNSIGNED NOT NULL DEFAULT 1,
  `created_at` TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_cart` (`user_id`,`product_id`),
  CONSTRAINT `fk_ci_user`    FOREIGN KEY (`user_id`)    REFERENCES `users`(`id`)    ON DELETE CASCADE,
  CONSTRAINT `fk_ci_product` FOREIGN KEY (`product_id`) REFERENCES `products`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- ORDERS
-- ============================================================
CREATE TABLE IF NOT EXISTS `orders` (
  `id`               INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  `buyer_id`         INT UNSIGNED  NOT NULL,
  `farmer_id`        INT UNSIGNED  NOT NULL,
  `driver_id`        INT UNSIGNED  NULL,
  `total_amount`     DECIMAL(10,2) NOT NULL,
  `payment_method`   ENUM('cod','online') DEFAULT 'cod',
  `payment_status`   ENUM('pending','paid','failed') DEFAULT 'pending',
  `shipping_address` TEXT          NOT NULL,
  `contact_number`   VARCHAR(20)   NOT NULL,
  `buyer_lat`        DECIMAL(10,7) NULL,
  `buyer_lng`        DECIMAL(10,7) NULL,
  `status`           ENUM('pending','confirmed','packed','shipped','delivered','cancelled') DEFAULT 'pending',
  `estimated_delivery` TIMESTAMP   NULL,
  `notes`            TEXT          NULL,
  `cancelled_reason` TEXT          NULL,
  `created_at`       TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
  `updated_at`       TIMESTAMP     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_buyer`  (`buyer_id`),
  INDEX `idx_farmer` (`farmer_id`),
  INDEX `idx_driver` (`driver_id`),
  INDEX `idx_status` (`status`),
  CONSTRAINT `fk_ord_buyer`  FOREIGN KEY (`buyer_id`)  REFERENCES `users`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_ord_farmer` FOREIGN KEY (`farmer_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_ord_driver` FOREIGN KEY (`driver_id`) REFERENCES `users`(`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- ORDER ITEMS
-- ============================================================
CREATE TABLE IF NOT EXISTS `order_items` (
  `id`         INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  `order_id`   INT UNSIGNED  NOT NULL,
  `product_id` INT UNSIGNED  NOT NULL,
  `quantity`   INT UNSIGNED  NOT NULL,
  `price`      DECIMAL(10,2) NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_oi_order`   FOREIGN KEY (`order_id`)   REFERENCES `orders`(`id`)   ON DELETE CASCADE,
  CONSTRAINT `fk_oi_product` FOREIGN KEY (`product_id`) REFERENCES `products`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- ORDER TRACKING
-- ============================================================
CREATE TABLE IF NOT EXISTS `order_tracking` (
  `id`         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `order_id`   INT UNSIGNED NOT NULL,
  `status`     VARCHAR(50)  NOT NULL,
  `note`       TEXT         NULL,
  `updated_by` INT UNSIGNED NULL,
  `created_at` TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_order` (`order_id`),
  CONSTRAINT `fk_ot_order` FOREIGN KEY (`order_id`) REFERENCES `orders`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- NOTIFICATIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS `notifications` (
  `id`         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id`    INT UNSIGNED NOT NULL,
  `title`      VARCHAR(200) NOT NULL,
  `message`    TEXT         NOT NULL,
  `type`       VARCHAR(50)  DEFAULT 'info',
  `is_read`    TINYINT(1)   DEFAULT 0,
  `related_order_id` INT UNSIGNED NULL,
  `created_at` TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_user_read` (`user_id`,`is_read`),
  CONSTRAINT `fk_notif_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- REVIEWS
-- ============================================================
CREATE TABLE IF NOT EXISTS `reviews` (
  `id`         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `order_id`   INT UNSIGNED NOT NULL,
  `buyer_id`   INT UNSIGNED NOT NULL,
  `farmer_id`  INT UNSIGNED NOT NULL,
  `rating`     TINYINT UNSIGNED NOT NULL,
  `comment`    TEXT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_review` (`order_id`,`buyer_id`),
  CONSTRAINT `fk_rev_order`  FOREIGN KEY (`order_id`)  REFERENCES `orders`(`id`)  ON DELETE CASCADE,
  CONSTRAINT `fk_rev_buyer`  FOREIGN KEY (`buyer_id`)  REFERENCES `users`(`id`)   ON DELETE CASCADE,
  CONSTRAINT `fk_rev_farmer` FOREIGN KEY (`farmer_id`) REFERENCES `users`(`id`)   ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- DEFAULT ADMIN
-- ============================================================
INSERT INTO `users` (`full_name`,`email`,`password_hash`,`role`,`is_approved`,`is_active`)
VALUES ('System Admin','admin@agrimarket.com','PLACEHOLDER','admin',1,1)
ON DUPLICATE KEY UPDATE `full_name`=VALUES(`full_name`);
