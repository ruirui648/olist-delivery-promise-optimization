-- =====================================================================
-- Olist MySQL 复现 · DWD 明细层（清洗 + 类型转换）
-- 作用：ODS -> DWD，做类型转换、去重、缺失处理
-- 关键：
--   1. ID 字段 text -> varchar(32)（32位十六进制）
--   2. 时间字段 text -> datetime
--   3. geolocation 去重 100万 -> 72万
--   4. products 缺类目 -> 'unknown'
--   5. review_id 重复是"伪重复"（内容不同），不去重
-- =====================================================================

USE olist;

-- 1. 订单表
DROP TABLE IF EXISTS dwd_orders;
CREATE TABLE dwd_orders AS
SELECT
    CAST(order_id AS CHAR(32)) AS order_id,
    CAST(customer_id AS CHAR(32)) AS customer_id,
    order_status,
    STR_TO_DATE(order_purchase_timestamp, '%Y-%m-%d %H:%i:%s') AS order_purchase_timestamp,
    STR_TO_DATE(order_approved_at, '%Y-%m-%d %H:%i:%s') AS order_approved_at,
    STR_TO_DATE(order_delivered_carrier_date, '%Y-%m-%d %H:%i:%s') AS order_delivered_carrier_date,
    STR_TO_DATE(order_delivered_customer_date, '%Y-%m-%d %H:%i:%s') AS order_delivered_customer_date,
    STR_TO_DATE(order_estimated_delivery_date, '%Y-%m-%d %H:%i:%s') AS order_estimated_delivery_date
FROM olist_orders_dataset;

-- 2. 订单明细表
DROP TABLE IF EXISTS dwd_order_items;
CREATE TABLE dwd_order_items AS
SELECT
    CAST(order_id AS CHAR(32)) AS order_id,
    order_item_id,
    CAST(product_id AS CHAR(32)) AS product_id,
    CAST(seller_id AS CHAR(32)) AS seller_id,
    STR_TO_DATE(shipping_limit_date, '%Y-%m-%d %H:%i:%s') AS shipping_limit_date,
    price,
    freight_value,
    price + freight_value AS item_total_value
FROM olist_order_items_dataset;

-- 3. 客户表
DROP TABLE IF EXISTS dwd_customers;
CREATE TABLE dwd_customers AS
SELECT
    CAST(customer_id AS CHAR(32)) AS customer_id,
    CAST(customer_unique_id AS CHAR(32)) AS customer_unique_id,
    customer_zip_code_prefix,
    customer_city,
    customer_state
FROM olist_customers_dataset;

-- 4. 商品表（缺类目 -> unknown）
DROP TABLE IF EXISTS dwd_products;
CREATE TABLE dwd_products AS
SELECT
    CAST(product_id AS CHAR(32)) AS product_id,
    COALESCE(NULLIF(product_category_name,''), 'unknown') AS product_category_name,
    product_name_lenght,
    product_description_lenght,
    product_photos_qty,
    product_weight_g,
    product_length_cm,
    product_height_cm,
    product_width_cm
FROM olist_products_dataset;

-- 5. 卖家表
DROP TABLE IF EXISTS dwd_sellers;
CREATE TABLE dwd_sellers AS
SELECT
    CAST(seller_id AS CHAR(32)) AS seller_id,
    seller_zip_code_prefix, seller_city, seller_state
FROM olist_sellers_dataset;

-- 6. 支付表
DROP TABLE IF EXISTS dwd_order_payments;
CREATE TABLE dwd_order_payments AS
SELECT
    CAST(order_id AS CHAR(32)) AS order_id,
    payment_sequential, payment_type, payment_installments, payment_value
FROM olist_order_payments_dataset;

-- 7. 评论表（review_id 伪重复，不去重）
DROP TABLE IF EXISTS dwd_order_reviews;
CREATE TABLE dwd_order_reviews AS
SELECT
    CAST(review_id AS CHAR(32)) AS review_id,
    CAST(order_id AS CHAR(32)) AS order_id,
    review_score,
    review_comment_title,
    review_comment_message,
    STR_TO_DATE(review_creation_date, '%Y-%m-%d %H:%i:%s') AS review_creation_date,
    STR_TO_DATE(review_answer_timestamp, '%Y-%m-%d %H:%i:%s') AS review_answer_timestamp
FROM olist_order_reviews_dataset;

-- 8. 地理表（真去重 100万 -> 72万）
DROP TABLE IF EXISTS dwd_geolocation;
CREATE TABLE dwd_geolocation AS
SELECT DISTINCT
    geolocation_zip_code_prefix, geolocation_lat, geolocation_lng, geolocation_city, geolocation_state
FROM olist_geolocation_dataset;

-- 9. 类目翻译表
DROP TABLE IF EXISTS dwd_category_translation;
CREATE TABLE dwd_category_translation AS
SELECT product_category_name, product_category_name_english
FROM product_category_name_translation;
