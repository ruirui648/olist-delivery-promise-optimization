-- =====================================================================
-- 00_data_quality_check.sql  数据质量检测（在 Hive 环境执行）
-- 作用：对 ODS 9 张表做系统质量检测，生成数据质量报告
-- 前置：已执行 01_ods_init.sql 建好 ODS 表
-- 执行：hive -f 00_data_quality_check.sql
-- =====================================================================

USE olist;

-- =====================================================================
-- 一、各表行数总览（对照官方数据量验证完整性）
-- =====================================================================
DROP TABLE IF EXISTS report_row_count;
CREATE TABLE report_row_count AS
SELECT 'customers' AS table_name, COUNT(*) AS row_cnt FROM ods_customers
UNION ALL SELECT 'geolocation', COUNT(*) FROM ods_geolocation
UNION ALL SELECT 'order_items', COUNT(*) FROM ods_order_items
UNION ALL SELECT 'order_payments', COUNT(*) FROM ods_order_payments
UNION ALL SELECT 'order_reviews', COUNT(*) FROM ods_order_reviews
UNION ALL SELECT 'orders', COUNT(*) FROM ods_orders
UNION ALL SELECT 'products', COUNT(*) FROM ods_products
UNION ALL SELECT 'sellers', COUNT(*) FROM ods_sellers
UNION ALL SELECT 'category_translation', COUNT(*) FROM ods_category_translation;

SELECT * FROM report_row_count;

-- =====================================================================
-- 二、关键字段缺失率检测
-- =====================================================================
DROP TABLE IF EXISTS report_missing;
CREATE TABLE report_missing AS
SELECT 'orders.order_approved_at' AS field,
       SUM(CASE WHEN order_approved_at IS NULL OR order_approved_at='' THEN 1 ELSE 0 END) AS missing_cnt,
       COUNT(*) AS total_cnt
FROM ods_orders
UNION ALL
SELECT 'orders.order_delivered_customer_date',
       SUM(CASE WHEN order_delivered_customer_date IS NULL OR order_delivered_customer_date='' THEN 1 ELSE 0 END),
       COUNT(*)
FROM ods_orders
UNION ALL
SELECT 'reviews.review_comment_title',
       SUM(CASE WHEN review_comment_title IS NULL OR review_comment_title='' THEN 1 ELSE 0 END),
       COUNT(*)
FROM ods_order_reviews
UNION ALL
SELECT 'reviews.review_comment_message',
       SUM(CASE WHEN review_comment_message IS NULL OR review_comment_message='' THEN 1 ELSE 0 END),
       COUNT(*)
FROM ods_order_reviews
UNION ALL
SELECT 'products.product_category_name',
       SUM(CASE WHEN product_category_name IS NULL OR product_category_name='' THEN 1 ELSE 0 END),
       COUNT(*)
FROM ods_products;

SELECT * FROM report_missing;

-- =====================================================================
-- 三、重复值检测
-- =====================================================================
-- geolocation 完全重复行数
DROP TABLE IF EXISTS report_dup;
CREATE TABLE report_dup AS
SELECT 'geolocation' AS table_name, t.dup_cnt
FROM (
    SELECT COUNT(*) - COUNT(DISTINCT geolocation_zip_code_prefix, geolocation_lat,
        geolocation_lng, geolocation_city, geolocation_state) AS dup_cnt
    FROM ods_geolocation
) t;

SELECT * FROM report_dup;

-- =====================================================================
-- 四、主键唯一性检测
-- =====================================================================
DROP TABLE IF EXISTS report_pk;
CREATE TABLE report_pk AS
SELECT 'orders.order_id' AS pk_field,
       COUNT(*) AS total, COUNT(DISTINCT order_id) AS distinct_cnt
FROM ods_orders
UNION ALL
SELECT 'customers.customer_id', COUNT(*), COUNT(DISTINCT customer_id) FROM ods_customers
UNION ALL
SELECT 'products.product_id', COUNT(*), COUNT(DISTINCT product_id) FROM ods_products
UNION ALL
SELECT 'sellers.seller_id', COUNT(*), COUNT(DISTINCT seller_id) FROM ods_sellers
UNION ALL
SELECT 'reviews.review_id', COUNT(*), COUNT(DISTINCT review_id) FROM ods_order_reviews;

SELECT * FROM report_pk;

-- =====================================================================
-- 五、核心字段分布检测
-- =====================================================================
-- 5.1 订单状态分布
DROP TABLE IF EXISTS report_order_status;
CREATE TABLE report_order_status AS
SELECT order_status, COUNT(*) AS cnt
FROM ods_orders GROUP BY order_status;

SELECT * FROM report_order_status;

-- 5.2 支付类型分布
DROP TABLE IF EXISTS report_payment_type;
CREATE TABLE report_payment_type AS
SELECT payment_type, COUNT(*) AS cnt
FROM ods_order_payments GROUP BY payment_type;

SELECT * FROM report_payment_type;

-- 5.3 评分分布
DROP TABLE IF EXISTS report_review_score;
CREATE TABLE report_review_score AS
SELECT review_score, COUNT(*) AS cnt
FROM ods_order_reviews GROUP BY review_score;

SELECT * FROM report_review_score;

-- 5.4 价格统计（异常值检测）
DROP TABLE IF EXISTS report_price;
CREATE TABLE report_price AS
SELECT
    MIN(CAST(price AS DOUBLE)) AS min_price,
    MAX(CAST(price AS DOUBLE)) AS max_price,
    AVG(CAST(price AS DOUBLE)) AS avg_price,
    SUM(CASE WHEN CAST(price AS DOUBLE) <= 0 THEN 1 ELSE 0 END) AS non_positive_cnt
FROM ods_order_items;

SELECT * FROM report_price;

-- 5.5 下单时间范围
DROP TABLE IF EXISTS report_time_range;
CREATE TABLE report_time_range AS
SELECT
    MIN(order_purchase_timestamp) AS min_time,
    MAX(order_purchase_timestamp) AS max_time
FROM ods_orders;

SELECT * FROM report_time_range;
