-- =====================================================================
-- 02b_verify_clean.sql  验证清洗结果
-- 作用：对比 ODS 与 DWD 的数据量/缺失/重复，验证清洗是否达标
-- 前置：已执行 01_ods_init.sql 和 02_dwd_etl.sql
-- 执行：hive -f 02b_verify_clean.sql
-- =====================================================================

USE olist;

-- =====================================================================
-- 一、清洗前后行数对比（重点看 geolocation 去重效果）
-- =====================================================================
DROP TABLE IF EXISTS verify_row_cmp;
CREATE TABLE verify_row_cmp AS
SELECT 'geolocation' AS table_name,
       (SELECT COUNT(*) FROM ods_geolocation) AS ods_cnt,
       (SELECT COUNT(*) FROM dwd_geolocation) AS dwd_cnt
UNION ALL
SELECT 'customers',
       (SELECT COUNT(*) FROM ods_customers),
       (SELECT COUNT(*) FROM dwd_customers)
UNION ALL
SELECT 'order_items',
       (SELECT COUNT(*) FROM ods_order_items),
       (SELECT COUNT(*) FROM dwd_order_items)
UNION ALL
SELECT 'order_payments',
       (SELECT COUNT(*) FROM ods_order_payments),
       (SELECT COUNT(*) FROM dwd_order_payments)
UNION ALL
SELECT 'order_reviews',
       (SELECT COUNT(*) FROM ods_order_reviews),
       (SELECT COUNT(*) FROM dwd_order_reviews)
UNION ALL
SELECT 'orders',
       (SELECT COUNT(*) FROM ods_orders),
       (SELECT COUNT(*) FROM dwd_orders)
UNION ALL
SELECT 'products',
       (SELECT COUNT(*) FROM ods_products),
       (SELECT COUNT(*) FROM dwd_products)
UNION ALL
SELECT 'sellers',
       (SELECT COUNT(*) FROM ods_sellers),
       (SELECT COUNT(*) FROM dwd_sellers);

SELECT * FROM verify_row_cmp;

-- =====================================================================
-- 二、清洗后 geolocation 是否还有重复（应为 0）
-- =====================================================================
SELECT COUNT(*) - COUNT(DISTINCT geolocation_zip_code_prefix, geolocation_lat,
    geolocation_lng, geolocation_city, geolocation_state) AS remaining_dup
FROM dwd_geolocation;

-- =====================================================================
-- 三、类型转换验证（orders 时间戳是否可正常解析）
-- =====================================================================
SELECT
    COUNT(*) AS total_orders,
    SUM(CASE WHEN order_purchase_timestamp IS NOT NULL THEN 1 ELSE 0 END) AS parsed_time_cnt
FROM dwd_orders;

-- =====================================================================
-- 四、products 缺失类目是否已填充为 unknown
-- =====================================================================
SELECT
    SUM(CASE WHEN product_category_name = 'unknown' THEN 1 ELSE 0 END) AS unknown_category_cnt
FROM dwd_products;

-- =====================================================================
-- 五、数值字段类型验证（价格应为 DOUBLE，无负数）
-- =====================================================================
SELECT
    MIN(price) AS min_price,
    MAX(price) AS max_price,
    SUM(CASE WHEN price < 0 THEN 1 ELSE 0 END) AS negative_price_cnt,
    SUM(CASE WHEN freight_value < 0 THEN 1 ELSE 0 END) AS negative_freight_cnt
FROM dwd_order_items;
