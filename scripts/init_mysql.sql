-- 建库脚本，表由 scripts/import_olist_mysql.py 导入
-- 执行：mysql -u root -p < scripts/init_mysql.sql

CREATE DATABASE IF NOT EXISTS olist
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_general_ci;

USE olist;
