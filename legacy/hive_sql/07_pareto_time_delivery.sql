-- =====================================================================
-- 07_pareto_time_delivery.sql  帕累托 + 下单时段 + 物流时效
-- 作用：三个分析主题合一
--   1. 帕累托（类目销售集中度 80/20）
--   2. 下单时段分布（24小时 + 星期）
--   3. 物流时效（准时率、平均延误）
-- 执行：spark-sql -f 07_pareto_time_delivery.sql
-- =====================================================================

USE olist;

-- ---------------------------------------------------------------------
-- 1. 帕累托分析：类目销售额累计占比
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS tmp_category_rev;
CREATE TABLE tmp_category_rev AS
SELECT
    product_category_english AS category,
    SUM(price + freight_value)    AS revenue
FROM dws_order_wide
WHERE order_status = 'delivered'
GROUP BY product_category_english;

DROP TABLE IF EXISTS ads_pareto;
CREATE TABLE ads_pareto AS
SELECT
    category,
    revenue,
    revenue / SUM(revenue) OVER () AS revenue_pct,
    SUM(revenue) OVER (ORDER BY revenue DESC) AS cum_revenue,
    SUM(revenue) OVER (ORDER BY revenue DESC) / SUM(revenue) OVER () AS cum_pct
FROM tmp_category_rev
ORDER BY revenue DESC;

DROP TABLE IF EXISTS tmp_category_rev;

-- ---------------------------------------------------------------------
-- 2. 下单时段分布
-- ---------------------------------------------------------------------
-- 2.1 24 小时下单分布
DROP TABLE IF EXISTS ads_order_hour;
CREATE TABLE ads_order_hour AS
SELECT
    HOUR(order_purchase_timestamp) AS hour_of_day,
    COUNT(*) AS order_cnt
FROM dwd_orders
GROUP BY HOUR(order_purchase_timestamp)
ORDER BY hour_of_day;

-- 2.2 星期几下单分布
DROP TABLE IF EXISTS ads_order_weekday;
CREATE TABLE ads_order_weekday AS
SELECT
    CASE DAYOFWEEK(order_purchase_timestamp)
        WHEN 1 THEN '周日'
        WHEN 2 THEN '周一'
        WHEN 3 THEN '周二'
        WHEN 4 THEN '周三'
        WHEN 5 THEN '周四'
        WHEN 6 THEN '周五'
        WHEN 7 THEN '周六'
    END AS weekday,
    COUNT(*) AS order_cnt
FROM dwd_orders
GROUP BY DAYOFWEEK(order_purchase_timestamp)
ORDER BY DAYOFWEEK(order_purchase_timestamp);

-- ---------------------------------------------------------------------
-- 3. 物流时效分析（只统计 delivered 订单）
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS ads_delivery;
CREATE TABLE ads_delivery AS
SELECT
    order_id,
    order_purchase_timestamp,
    order_delivered_customer_date,
    order_estimated_delivery_date,
    -- 实际送达天数
    DATEDIFF(order_delivered_customer_date, order_purchase_timestamp) AS delivery_days,
    -- 延误天数（正数=延误，负数=提前）
    DATEDIFF(order_delivered_customer_date, order_estimated_delivery_date) AS delay_days,
    -- 是否准时
    CASE WHEN order_delivered_customer_date <= order_estimated_delivery_date
        THEN 1 ELSE 0 END AS is_on_time
FROM dwd_orders
WHERE order_status = 'delivered';

-- 准时率汇总
DROP TABLE IF EXISTS ads_delivery_summary;
CREATE TABLE ads_delivery_summary AS
SELECT
    COUNT(*)                                        AS delivered_cnt,
    SUM(is_on_time)                                 AS on_time_cnt,
    ROUND(SUM(is_on_time) / COUNT(*), 4)            AS on_time_rate,
    ROUND(AVG(delivery_days), 2)                    AS avg_delivery_days,
    ROUND(AVG(CASE WHEN delay_days > 0 THEN delay_days ELSE 0 END), 2) AS avg_delay_days
FROM ads_delivery;

SELECT * FROM ads_delivery_summary;
