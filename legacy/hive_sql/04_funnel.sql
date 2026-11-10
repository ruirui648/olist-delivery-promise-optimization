-- =====================================================================
-- 04_funnel.sql  履约转化漏斗分析
-- 作用：分析订单从下单到送达的各环节转化率、流失率
-- 执行：spark-sql -f 04_funnel.sql
--
-- 漏斗环节（基于 order_status 状态机）：
--   created(下单) -> approved(支付) -> invoiced(开票)
--     -> shipped(发货) -> delivered(送达)
-- 流失：canceled(取消) / unavailable(不可用)
-- =====================================================================

USE olist;

-- 1. 各状态订单数（漏斗各层）
DROP TABLE IF EXISTS ads_funnel_status;
CREATE TABLE ads_funnel_status AS
SELECT
    order_status,
    COUNT(*) AS order_cnt
FROM dwd_orders
GROUP BY order_status;

-- 2. 漏斗转化率（关键指标）
-- 口径说明：approved 包含 approved + invoiced + shipped + delivered
--           即「已进入支付环节及之后」的订单都算 approved 过
DROP TABLE IF EXISTS ads_funnel;
CREATE TABLE ads_funnel AS
SELECT
    'created'   AS stage,
    COUNT(*)    AS orders_cnt,
    1.0         AS conversion_rate
FROM dwd_orders
UNION ALL
SELECT
    'approved',
    COUNT(*),
    SUM(CASE WHEN order_status IN ('approved','invoiced','shipped','delivered') THEN 1 ELSE 0 END)
        / COUNT(*)
FROM dwd_orders
UNION ALL
SELECT
    'invoiced',
    COUNT(*),
    SUM(CASE WHEN order_status IN ('invoiced','shipped','delivered') THEN 1 ELSE 0 END)
        / COUNT(*)
FROM dwd_orders
UNION ALL
SELECT
    'shipped',
    COUNT(*),
    SUM(CASE WHEN order_status IN ('shipped','delivered') THEN 1 ELSE 0 END)
        / COUNT(*)
FROM dwd_orders
UNION ALL
SELECT
    'delivered',
    SUM(CASE WHEN order_status='delivered' THEN 1 ELSE 0 END),
    SUM(CASE WHEN order_status='delivered' THEN 1 ELSE 0 END)
        / COUNT(*)
FROM dwd_orders;

-- 3. 取消订单原因分布（流失分析）
DROP TABLE IF EXISTS ads_funnel_cancel;
CREATE TABLE ads_funnel_cancel AS
SELECT
    order_status,
    COUNT(*) AS cnt
FROM dwd_orders
WHERE order_status IN ('canceled','unavailable')
GROUP BY order_status;

SELECT * FROM ads_funnel ORDER BY orders_cnt DESC;
