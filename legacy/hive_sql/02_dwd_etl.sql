-- =====================================================================
-- 02_dwd_etl.sql  DWD 明细层清洗 ETL
-- 作用：ODS -> DWD，做类型转换、去重、缺失值处理
-- 执行：hive -f 02_dwd_etl.sql
--
-- 清洗要点（对应数据质量体检结论）：
--   1. geolocation 去重（100万 -> 73.8万）
--   2. 时间戳 STRING -> TIMESTAMP/日期类型
--   3. 数值 STRING -> DOUBLE/INT
--   4. products 缺失类目 -> 'unknown'
--   5. 金额/价格类型统一为 DOUBLE
-- =====================================================================

USE olist;

-- ---------------------------------------------------------------------
-- 1. 客户表
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS dwd_customers;
CREATE TABLE dwd_customers AS
SELECT
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix,
    customer_city,
    customer_state
FROM ods_customers;

-- ---------------------------------------------------------------------
-- 2. 地理位置表（重点：去重）
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS dwd_geolocation;
CREATE TABLE dwd_geolocation AS
SELECT
    geolocation_zip_code_prefix,
    CAST(geolocation_lat AS DOUBLE) AS geolocation_lat,
    CAST(geolocation_lng AS DOUBLE) AS geolocation_lng,
    geolocation_city,
    geolocation_state
FROM ods_geolocation
GROUP BY
    geolocation_zip_code_prefix,
    geolocation_lat,
    geolocation_lng,
    geolocation_city,
    geolocation_state;

-- ---------------------------------------------------------------------
-- 3. 订单商品明细表
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS dwd_order_items;
CREATE TABLE dwd_order_items AS
SELECT
    order_id,
    CAST(order_item_id AS INT) AS order_item_id,
    product_id,
    seller_id,
    CAST(shipping_limit_date AS TIMESTAMP) AS shipping_limit_date,
    CAST(price AS DOUBLE) AS price,
    CAST(freight_value AS DOUBLE) AS freight_value
FROM ods_order_items;

-- ---------------------------------------------------------------------
-- 4. 支付表
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS dwd_order_payments;
CREATE TABLE dwd_order_payments AS
SELECT
    order_id,
    CAST(payment_sequential AS INT) AS payment_sequential,
    payment_type,
    CAST(payment_installments AS INT) AS payment_installments,
    CAST(payment_value AS DOUBLE) AS payment_value
FROM ods_order_payments;

-- ---------------------------------------------------------------------
-- 5. 评论表
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS dwd_order_reviews;
CREATE TABLE dwd_order_reviews AS
SELECT
    review_id,
    order_id,
    CAST(review_score AS INT) AS review_score,
    review_comment_title,
    review_comment_message,
    CAST(review_creation_date AS TIMESTAMP) AS review_creation_date,
    CAST(review_answer_timestamp AS TIMESTAMP) AS review_answer_timestamp
FROM ods_order_reviews;

-- ---------------------------------------------------------------------
-- 6. 订单主表（核心：时间戳转换）
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS dwd_orders;
CREATE TABLE dwd_orders AS
SELECT
    order_id,
    customer_id,
    order_status,
    CAST(order_purchase_timestamp AS TIMESTAMP) AS order_purchase_timestamp,
    CAST(order_approved_at AS TIMESTAMP) AS order_approved_at,
    CAST(order_delivered_carrier_date AS TIMESTAMP) AS order_delivered_carrier_date,
    CAST(order_delivered_customer_date AS TIMESTAMP) AS order_delivered_customer_date,
    CAST(order_estimated_delivery_date AS TIMESTAMP) AS order_estimated_delivery_date
FROM ods_orders;

-- ---------------------------------------------------------------------
-- 7. 商品表（缺失类目 -> unknown）
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS dwd_products;
CREATE TABLE dwd_products AS
SELECT
    product_id,
    COALESCE(NULLIF(product_category_name,''), 'unknown') AS product_category_name,
    CAST(product_name_lenght AS INT) AS product_name_length,
    CAST(product_description_lenght AS INT) AS product_description_length,
    CAST(product_photos_qty AS INT) AS product_photos_qty,
    CAST(product_weight_g AS DOUBLE) AS product_weight_g,
    CAST(product_length_cm AS DOUBLE) AS product_length_cm,
    CAST(product_height_cm AS DOUBLE) AS product_height_cm,
    CAST(product_width_cm AS DOUBLE) AS product_width_cm
FROM ods_products;

-- ---------------------------------------------------------------------
-- 8. 卖家表
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS dwd_sellers;
CREATE TABLE dwd_sellers AS
SELECT
    seller_id,
    seller_zip_code_prefix,
    seller_city,
    seller_state
FROM ods_sellers;

-- ---------------------------------------------------------------------
-- 9. 类目翻译表
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS dwd_category_translation;
CREATE TABLE dwd_category_translation AS
SELECT
    product_category_name,
    product_category_name_english
FROM ods_category_translation;

-- 验证
SHOW TABLES;
