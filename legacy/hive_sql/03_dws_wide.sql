-- =====================================================================
-- 03_dws_wide.sql  DWS 汇总层：订单主题宽表
-- 作用：多表 join 生成 dws_order_wide，供后续所有分析复用
-- 执行：hive -f 03_dws_wide.sql
--
-- 宽表设计：以订单商品明细为主干，关联订单、客户、卖家、商品、类目
-- 粒度：一笔订单中的一件商品（order_id + order_item_id）
-- =====================================================================

USE olist;

-- 1. 订单金额汇总（一笔订单多条支付记录 -> 聚合到订单级）
DROP VIEW IF EXISTS tmp_order_payment;
CREATE VIEW tmp_order_payment AS
SELECT
    order_id,
    SUM(payment_value) AS total_payment_value,
    COUNT(*) AS payment_cnt
FROM dwd_order_payments
GROUP BY order_id;

-- 2. 订单主题宽表
DROP TABLE IF EXISTS dws_order_wide;
CREATE TABLE dws_order_wide AS
SELECT
    -- 订单商品维度
    oi.order_id,
    oi.order_item_id,
    oi.product_id,
    oi.seller_id,
    oi.price,
    oi.freight_value,
    oi.price + oi.freight_value AS item_total_value,

    -- 订单维度
    o.customer_id,
    o.order_status,
    o.order_purchase_timestamp,
    o.order_approved_at,
    o.order_delivered_carrier_date,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,

    -- 订单级金额（聚合后关联）
    COALESCE(op.total_payment_value, 0) AS order_payment_value,
    op.payment_cnt,

    -- 客户维度
    c.customer_unique_id,
    c.customer_zip_code_prefix,
    c.customer_city,
    c.customer_state,

    -- 卖家维度
    s.seller_zip_code_prefix,
    s.seller_city,
    s.seller_state,

    -- 商品维度
    p.product_category_name,
    p.product_weight_g,
    p.product_photos_qty,
    ct.product_category_name_english AS product_category_english

FROM dwd_order_items oi
LEFT JOIN dwd_orders o
    ON oi.order_id = o.order_id
LEFT JOIN dwd_customers c
    ON o.customer_id = c.customer_id
LEFT JOIN dwd_sellers s
    ON oi.seller_id = s.seller_id
LEFT JOIN dwd_products p
    ON oi.product_id = p.product_id
LEFT JOIN dwd_category_translation ct
    ON p.product_category_name = ct.product_category_name
LEFT JOIN tmp_order_payment op
    ON oi.order_id = op.order_id;

DROP VIEW IF EXISTS tmp_order_payment;

-- 验证
SELECT COUNT(*) AS row_cnt FROM dws_order_wide;
