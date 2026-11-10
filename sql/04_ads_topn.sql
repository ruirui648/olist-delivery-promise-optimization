-- =====================================================================
-- Olist MySQL 复现 · ADS 分析（2）TOP N
-- 作用：类目/州/卖家 三个维度的销售额排行
-- 结论：
--   类目：health_beauty(123万) 第一，watches_gifts(117万) 第二
--   州：SP 一州约 507万，占约 1/3，市场集中东南部
-- =====================================================================

USE olist;

-- 1. 类目销售额 TOP 10
SELECT product_category_english AS category, 
       COUNT(*) AS order_cnt,
       ROUND(SUM(price),2) AS revenue
FROM dws_order_wide
WHERE order_status = 'delivered'
GROUP BY product_category_english
ORDER BY revenue DESC
LIMIT 10;

-- 2. 州销售额 TOP 10
SELECT customer_state AS state, 
       COUNT(DISTINCT order_id) AS order_cnt,
       ROUND(SUM(price),2) AS revenue
FROM dws_order_wide
WHERE order_status = 'delivered'
GROUP BY customer_state
ORDER BY revenue DESC
LIMIT 10;

-- 3. 卖家销售额 TOP 10
SELECT seller_id, 
       COUNT(*) AS item_cnt,
       ROUND(SUM(price),2) AS revenue
FROM dws_order_wide
WHERE order_status = 'delivered'
GROUP BY seller_id
ORDER BY revenue DESC
LIMIT 10;
