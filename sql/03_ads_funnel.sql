-- =====================================================================
-- Olist MySQL 复现 · ADS 分析（1）履约漏斗
-- 作用：订单从下单到送达的转化率
-- 口径：累计口径（某环节及之后的订单都算"到达过"该环节）
-- 结论：送达率 97.02%，最大流失在"下单→支付"(1.55%)
-- =====================================================================

USE olist;

-- 1. 各状态订单数
DROP TABLE IF EXISTS ads_funnel_status;
CREATE TABLE ads_funnel_status AS
SELECT order_status, COUNT(*) AS order_cnt
FROM dwd_orders GROUP BY order_status;

-- 2. 漏斗转化率（每层显示实际到达订单数）
DROP TABLE IF EXISTS ads_funnel;
CREATE TABLE ads_funnel AS
SELECT 'created' AS stage, COUNT(*) AS orders_cnt, 100.0 AS conv_rate FROM dwd_orders
UNION ALL
SELECT 'approved', SUM(order_status IN ('approved','invoiced','shipped','delivered')), 
       ROUND(SUM(order_status IN ('approved','invoiced','shipped','delivered'))*100.0/COUNT(*),2) FROM dwd_orders
UNION ALL
SELECT 'shipped', SUM(order_status IN ('shipped','delivered')), 
       ROUND(SUM(order_status IN ('shipped','delivered'))*100.0/COUNT(*),2) FROM dwd_orders
UNION ALL
SELECT 'delivered', SUM(order_status='delivered'), 
       ROUND(SUM(order_status='delivered')*100.0/COUNT(*),2) FROM dwd_orders;

-- 3. 流失订单分布
SELECT order_status, COUNT(*) AS cnt FROM dwd_orders 
WHERE order_status IN ('canceled','unavailable') GROUP BY order_status;
