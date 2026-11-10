-- =====================================================================
-- Olist MySQL 复现 · 数据质量检查
-- 作用：对 9 张 ODS 表做质量检测（行数/缺失/唯一性/分布）
-- 数据库：olist（MySQL 8.0）
-- =====================================================================

USE olist;

-- 一、各表行数
SELECT 'customers' AS tbl, COUNT(*) AS cnt FROM olist_customers_dataset
UNION ALL SELECT 'geolocation', COUNT(*) FROM olist_geolocation_dataset
UNION ALL SELECT 'order_items', COUNT(*) FROM olist_order_items_dataset
UNION ALL SELECT 'order_payments', COUNT(*) FROM olist_order_payments_dataset
UNION ALL SELECT 'order_reviews', COUNT(*) FROM olist_order_reviews_dataset
UNION ALL SELECT 'orders', COUNT(*) FROM olist_orders_dataset
UNION ALL SELECT 'products', COUNT(*) FROM olist_products_dataset
UNION ALL SELECT 'sellers', COUNT(*) FROM olist_sellers_dataset
UNION ALL SELECT 'category_translation', COUNT(*) FROM product_category_name_translation;

-- 二、关键字段缺失率
SELECT 'orders.order_approved_at' AS field,
       SUM(CASE WHEN order_approved_at IS NULL OR order_approved_at='' THEN 1 ELSE 0 END) AS missing,
       COUNT(*) AS total
FROM olist_orders_dataset
UNION ALL
SELECT 'orders.delivered_customer_date', SUM(order_delivered_customer_date IS NULL OR order_delivered_customer_date=''), COUNT(*) FROM olist_orders_dataset
UNION ALL
SELECT 'reviews.comment_title', SUM(review_comment_title IS NULL OR review_comment_title=''), COUNT(*) FROM olist_order_reviews_dataset
UNION ALL
SELECT 'reviews.comment_message', SUM(review_comment_message IS NULL OR review_comment_message=''), COUNT(*) FROM olist_order_reviews_dataset
UNION ALL
SELECT 'products.category_name', SUM(product_category_name IS NULL OR product_category_name=''), COUNT(*) FROM olist_products_dataset;

-- 三、主键唯一性
SELECT 'orders.order_id' AS pk, COUNT(*) AS total, COUNT(DISTINCT order_id) AS distinct_cnt FROM olist_orders_dataset
UNION ALL SELECT 'customers.customer_id', COUNT(*), COUNT(DISTINCT customer_id) FROM olist_customers_dataset
UNION ALL SELECT 'products.product_id', COUNT(*), COUNT(DISTINCT product_id) FROM olist_products_dataset
UNION ALL SELECT 'sellers.seller_id', COUNT(*), COUNT(DISTINCT seller_id) FROM olist_sellers_dataset
UNION ALL SELECT 'reviews.review_id', COUNT(*), COUNT(DISTINCT review_id) FROM olist_order_reviews_dataset;

-- 四、订单状态分布
SELECT order_status, COUNT(*) AS cnt FROM olist_orders_dataset GROUP BY order_status;

-- 五、支付类型分布
SELECT payment_type, COUNT(*) AS cnt FROM olist_order_payments_dataset GROUP BY payment_type;

-- 六、评分分布
SELECT review_score, COUNT(*) AS cnt FROM olist_order_reviews_dataset GROUP BY review_score;

-- 七、价格统计
SELECT MIN(price) AS min_price, MAX(price) AS max_price, ROUND(AVG(price),2) AS avg_price,
       SUM(price <= 0) AS non_positive_cnt
FROM olist_order_items_dataset;

-- ===== 质量检查结论 =====
-- 1. 各表行数正确，主键唯一（orders/customers/products/sellers）
-- 2. review_id 有 789 个重复（涉及1603行），但内容不同，是"伪重复"，不去重
-- 3. geolocation 有约28万完全重复行，DWD 去重
-- 4. 缺失都是业务正常（未送达订单无日期、未写评论）
