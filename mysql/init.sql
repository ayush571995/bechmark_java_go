CREATE DATABASE IF NOT EXISTS benchmark;
USE benchmark;

CREATE TABLE IF NOT EXISTS kv_store (
  `key`   VARCHAR(64)   NOT NULL,
  `value` VARCHAR(256)  NOT NULL,
  PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Seed 10 000 key-value pairs (~50-byte JSON values)
DROP PROCEDURE IF EXISTS seed_data;
DELIMITER $$
CREATE PROCEDURE seed_data()
BEGIN
  DECLARE i INT DEFAULT 0;
  WHILE i < 10000 DO
    INSERT IGNORE INTO kv_store (`key`, `value`)
    VALUES (
      CONCAT('key_', LPAD(i, 5, '0')),
      CONCAT('{"id":', i, ',"name":"item_', LPAD(i, 5, '0'), '","val":', i * 2, '}')
    );
    SET i = i + 1;
  END WHILE;
END$$
DELIMITER ;

CALL seed_data();
DROP PROCEDURE IF EXISTS seed_data;
