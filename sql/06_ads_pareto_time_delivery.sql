-- =====================================================================
-- Olist MySQL 复现 · ADS 分析 45 帕累托 + 时段 + 物流
-- 结论：
--   帕累托：前17类目贡献80%销售额（头部集中）
--   时段：下单高峰11-16点，周一~周三最多
--   物流：准时率91.89%，平均提前11.88天
-- =====================================================================

USE olist;

-- 1. 帕累托（类目销售累计占比）
SELECT 
    product_category_english AS category,
    ROUND(SUM(price),2) AS revenue,
    ROUND(SUM(SUM(price)) OVER (ORDER BY SUM(price) DESC) / SUM(SUM(price)) OVER () * 100, 2) AS cum_pct
FROM dws_order_wide
WHERE order_status = 'delivered'
GROUP BY product_category_english
ORDER BY revenue DESC
LIMIT 20;

-- 2. 下单小时分布
SELECT HOUR(order_purchase_timestamp) AS hour, COUNT(*) AS order_cnt
FROM dwd_orders
GROUP BY HOUR(order_purchase_timestamp)
ORDER BY order_cnt DESC;

-- 3. 星期分布
SELECT DAYOFWEEK(order_purchase_timestamp) AS dow, COUNT(*) AS order_cnt
FROM dwd_orders
GROUP BY DAYOFWEEK(order_purchase_timestamp)
ORDER BY order_cnt DESC;

-- 4. 物流时效（准时率 + 平均延误天数）
SELECT 
    COUNT(*) AS delivered_cnt,
    SUM(order_delivered_customer_date <= order_estimated_delivery_date) AS on_time_cnt,
    ROUND(SUM(order_delivered_customer_date <= order_estimated_delivery_date)*100.0/COUNT(*),2) AS on_time_rate,
    ROUND(AVG(DATEDIFF(order_delivered_customer_date, order_estimated_delivery_date)),2) AS avg_delay_days
FROM dwd_orders
WHERE order_status = 'delivered'
  AND order_delivered_customer_date IS NOT NULL
  AND order_estimated_delivery_date IS NOT NULL;
