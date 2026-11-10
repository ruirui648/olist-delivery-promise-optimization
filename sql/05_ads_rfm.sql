-- =====================================================================
-- Olist MySQL 复现 · ADS 分析（3）RFM 客户价值分层
-- 作用：客户价值分层
-- 关键口径：
--   1. 用 customer_unique_id（真实客户），不是 customer_id（订单级匿名ID）
--   2. F维度失效（97%客户只买1次），改用 RM 二维分群
--   3. R中位数=267天，M中位数=111.02
-- 结论：
--   核心高价值 25.3% (R$354) / 沉睡高价值 24.7% (R$354)
--   流失低价值 25.6% (R$63) / 活跃低价值 24.4% (R$63)
--   高价值客户消费是低价值的5.6倍，但复购率极低(频次≈1)
-- =====================================================================

USE olist;

-- 1. RFM 基础表
DROP TABLE IF EXISTS ads_rfm;
CREATE TABLE ads_rfm AS
SELECT
    c.customer_unique_id,
    DATEDIFF('2018-10-17', MAX(o.order_purchase_timestamp)) AS recency,
    COUNT(DISTINCT o.order_id) AS frequency,
    ROUND(SUM(oi.order_payment_value / oi.payment_cnt), 2) AS monetary
FROM dws_order_wide oi
JOIN dwd_customers c ON oi.customer_id = c.customer_id
JOIN dwd_orders o ON oi.order_id = o.order_id
WHERE o.order_status = 'delivered'
GROUP BY c.customer_unique_id;

-- 2. F维度验证（97%只买1次，F失效）
SELECT frequency, COUNT(*) AS customer_cnt
FROM ads_rfm GROUP BY frequency ORDER BY frequency;

-- 3. RM 二维分群（中位数 R=267, M=111.02）
DROP TABLE IF EXISTS ads_rfm_segments;
CREATE TABLE ads_rfm_segments AS
SELECT
    CASE 
        WHEN recency < 267 AND monetary >= 111.02 THEN 'core_high_value'
        WHEN recency < 267 AND monetary < 111.02 THEN 'active_low_value'
        WHEN recency >= 267 AND monetary >= 111.02 THEN 'sleeping_high_value'
        ELSE 'lost_low_value'
    END AS segment,
    COUNT(*) AS customer_cnt,
    ROUND(AVG(monetary),2) AS avg_monetary,
    ROUND(AVG(frequency),2) AS avg_frequency
FROM ads_rfm
GROUP BY segment
ORDER BY customer_cnt DESC;
