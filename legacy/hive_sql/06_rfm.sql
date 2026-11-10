-- =====================================================================
-- 06_rfm.sql  RFM 客户价值分层分析
-- 作用：计算每个客户的 R(最近购买)/F(购买频次)/M(消费金额)，做 8 类价值分层
-- 执行：spark-sql -f 06_rfm.sql
--
-- 口径：
--   R = 数据集中最后一天 - 客户最近一次下单日期（天数，越小越好）
--   F = 客户下单次数（去重 order_id）
--   M = 客户累计实付金额（payment_value 按订单聚合）
--
-- 分层方法：对 R/F/M 各取中位数，高于/低于中位数分成 2^3 = 8 类
--   R 低(好)=1, F 高(好)=1, M 高(好)=1  -> 重要价值客户
-- =====================================================================

USE olist;

-- 1. 客户粒度 RFM 原始值
DROP TABLE IF EXISTS tmp_rfm;
CREATE TABLE tmp_rfm AS
SELECT
    o.customer_id,
    -- R: 距最后一天的天数
    DATEDIFF(MAX_DATE.max_d, MAX(o.order_purchase_timestamp)) AS recency_days,
    -- F: 下单次数
    COUNT(DISTINCT o.order_id) AS frequency,
    -- M: 累计实付金额（join 订单级支付金额）
    SUM(pay.total_payment_value) AS monetary
FROM dwd_orders o
JOIN (
    SELECT order_id, SUM(payment_value) AS total_payment_value
    FROM dwd_order_payments
    GROUP BY order_id
) pay ON o.order_id = pay.order_id
CROSS JOIN (
    SELECT MAX(order_purchase_timestamp) AS max_d
    FROM dwd_orders
) MAX_DATE
WHERE o.order_status = 'delivered'
GROUP BY o.customer_id, MAX_DATE.max_d;

-- 2. 计算中位数（Hive 用 percentile）
DROP VIEW IF EXISTS tmp_rfm_med;
CREATE VIEW tmp_rfm_med AS
SELECT
    percentile(recency_days, 0.5) AS r_med,
    percentile(frequency, 0.5)     AS f_med,
    percentile(monetary, 0.5)      AS m_med
FROM tmp_rfm;

-- 3. 8 类客户分层
DROP TABLE IF EXISTS ads_rfm_segment;
CREATE TABLE ads_rfm_segment AS
SELECT
    r.customer_id,
    r.recency_days,
    r.frequency,
    r.monetary,
    -- R 低为佳 -> 1；F 高为佳 -> 1；M 高为佳 -> 1
    CASE WHEN r.recency_days <= m.r_med THEN 1 ELSE 0 END AS r_score,
    CASE WHEN r.frequency     >= m.f_med THEN 1 ELSE 0 END AS f_score,
    CASE WHEN r.monetary      >= m.m_med THEN 1 ELSE 0 END AS m_score,
    CASE
        WHEN r.recency_days <= m.r_med AND r.frequency >= m.f_med AND r.monetary >= m.m_med
            THEN '重要价值客户'
        WHEN r.recency_days <= m.r_med AND r.frequency >= m.f_med AND r.monetary <  m.m_med
            THEN '重要发展客户'
        WHEN r.recency_days <= m.r_med AND r.frequency <  m.f_med AND r.monetary >= m.m_med
            THEN '重要保持客户'
        WHEN r.recency_days <= m.r_med AND r.frequency <  m.f_med AND r.monetary <  m.m_med
            THEN '重要挽留客户'
        WHEN r.recency_days >  m.r_med AND r.frequency >= m.f_med AND r.monetary >= m.m_med
            THEN '一般价值客户'
        WHEN r.recency_days >  m.r_med AND r.frequency >= m.f_med AND r.monetary <  m.m_med
            THEN '一般发展客户'
        WHEN r.recency_days >  m.r_med AND r.frequency <  m.f_med AND r.monetary >= m.m_med
            THEN '一般保持客户'
        ELSE '一般挽留客户'
    END AS rfm_segment
FROM tmp_rfm r
CROSS JOIN tmp_rfm_med m;

-- 4. 各分层客户数与金额汇总（核心结论表）
DROP TABLE IF EXISTS ads_rfm_summary;
CREATE TABLE ads_rfm_summary AS
SELECT
    rfm_segment,
    COUNT(*) AS customer_cnt,
    ROUND(SUM(monetary), 2) AS total_monetary,
    ROUND(AVG(monetary), 2) AS avg_monetary
FROM ads_rfm_segment
GROUP BY rfm_segment
ORDER BY customer_cnt DESC;

DROP VIEW IF EXISTS tmp_rfm_med;
DROP TABLE IF EXISTS tmp_rfm;

SELECT * FROM ads_rfm_summary;
