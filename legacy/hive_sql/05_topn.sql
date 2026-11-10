-- =====================================================================
-- 05_topn.sql  热销 TOP N 多维分析
-- 作用：从类目/商品/卖家/州四个维度找出销量和销售额排行
-- 执行：spark-sql -f 05_topn.sql
-- =====================================================================

USE olist;

-- 1. 热销类目 TOP 10（按销售额，含销量）
DROP TABLE IF EXISTS ads_top_category;
CREATE TABLE ads_top_category AS
SELECT
    product_category_english AS category,
    COUNT(DISTINCT order_id) AS order_cnt,
    SUM(price + freight_value)    AS revenue
FROM dws_order_wide
WHERE order_status = 'delivered'
GROUP BY product_category_english
ORDER BY revenue DESC
LIMIT 10;

-- 2. 热销商品 TOP 10（按销售额）
DROP TABLE IF EXISTS ads_top_product;
CREATE TABLE ads_top_product AS
SELECT
    product_id,
    COUNT(DISTINCT order_id) AS order_cnt,
    SUM(price + freight_value)    AS revenue
FROM dws_order_wide
WHERE order_status = 'delivered'
GROUP BY product_id
ORDER BY revenue DESC
LIMIT 10;

-- 3. TOP 卖家 TOP 10（按销售额）
DROP TABLE IF EXISTS ads_top_seller;
CREATE TABLE ads_top_seller AS
SELECT
    seller_id,
    seller_state,
    COUNT(DISTINCT order_id) AS order_cnt,
    SUM(price + freight_value)    AS revenue
FROM dws_order_wide
WHERE order_status = 'delivered'
GROUP BY seller_id, seller_state
ORDER BY revenue DESC
LIMIT 10;

-- 4. 各州销售排行 TOP 10（按销售额，地域维度）
DROP TABLE IF EXISTS ads_top_state;
CREATE TABLE ads_top_state AS
SELECT
    customer_state,
    COUNT(DISTINCT order_id) AS order_cnt,
    SUM(price + freight_value)    AS revenue
FROM dws_order_wide
WHERE order_status = 'delivered'
GROUP BY customer_state
ORDER BY revenue DESC
LIMIT 10;

-- 5. 月度 GMV 趋势（供趋势分析）
-- 口径修正：宽表 dws_order_wide 是「订单×商品」粒度，order_payment_value 是订单级字段，
-- 直接 SUM 会按商品数重复累加（虚高约 24%）。改用商品级字段 price + freight_value 求和，
-- 与上方 TOP 各表口径一致，才是正确的 GMV。
DROP TABLE IF EXISTS ads_monthly_gmv;
CREATE TABLE ads_monthly_gmv AS
SELECT
    SUBSTR(CAST(order_purchase_timestamp AS STRING), 1, 7) AS month,
    COUNT(DISTINCT order_id) AS order_cnt,
    SUM(price + freight_value) AS gmv
FROM dws_order_wide
WHERE order_status = 'delivered'
GROUP BY SUBSTR(CAST(order_purchase_timestamp AS STRING), 1, 7)
ORDER BY month;

SELECT * FROM ads_top_category;
