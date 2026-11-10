-- =====================================================================
-- 01_ods_init.sql  ODS 贴源层初始化（适配平铺目录版）
-- 作用：建库 + 9 张 ODS 外部表
-- 关键：LOCATION 直接指向单个 CSV 文件（HDFS 平铺在 /olist/data）
-- 执行：hive -f 01_ods_init.sql
--
-- 技术点：
--   1. OpenCSVSerde 处理「逗号分隔 + 双引号包裹 + 文本含逗号」
--   2. skip.header.line.count=1 跳过表头
--   3. 外部表不复制数据，直接读 HDFS 原文件
-- =====================================================================

CREATE DATABASE IF NOT EXISTS olist
COMMENT 'Olist 巴西电商分析数仓'
LOCATION '/olist/warehouse';

USE olist;

-- 1. 客户表
DROP TABLE IF EXISTS ods_customers;
CREATE EXTERNAL TABLE ods_customers (
    customer_id             STRING,
    customer_unique_id      STRING,
    customer_zip_code_prefix STRING,
    customer_city           STRING,
    customer_state          STRING
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar'=',','quoteChar'='"','escapeChar'='\\')
STORED AS TEXTFILE
LOCATION '/olist/data/olist_customers_dataset.csv'
TBLPROPERTIES ('skip.header.line.count'='1');

-- 2. 地理位置表
DROP TABLE IF EXISTS ods_geolocation;
CREATE EXTERNAL TABLE ods_geolocation (
    geolocation_zip_code_prefix STRING,
    geolocation_lat             STRING,
    geolocation_lng             STRING,
    geolocation_city            STRING,
    geolocation_state           STRING
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar'=',','quoteChar'='"','escapeChar'='\\')
STORED AS TEXTFILE
LOCATION '/olist/data/olist_geolocation_dataset.csv'
TBLPROPERTIES ('skip.header.line.count'='1');

-- 3. 订单商品明细表
DROP TABLE IF EXISTS ods_order_items;
CREATE EXTERNAL TABLE ods_order_items (
    order_id            STRING,
    order_item_id       STRING,
    product_id          STRING,
    seller_id           STRING,
    shipping_limit_date STRING,
    price               STRING,
    freight_value       STRING
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar'=',','quoteChar'='"','escapeChar'='\\')
STORED AS TEXTFILE
LOCATION '/olist/data/olist_order_items_dataset.csv'
TBLPROPERTIES ('skip.header.line.count'='1');

-- 4. 支付表
DROP TABLE IF EXISTS ods_order_payments;
CREATE EXTERNAL TABLE ods_order_payments (
    order_id             STRING,
    payment_sequential   STRING,
    payment_type         STRING,
    payment_installments STRING,
    payment_value        STRING
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar'=',','quoteChar'='"','escapeChar'='\\')
STORED AS TEXTFILE
LOCATION '/olist/data/olist_order_payments_dataset.csv'
TBLPROPERTIES ('skip.header.line.count'='1');

-- 5. 评论表
DROP TABLE IF EXISTS ods_order_reviews;
CREATE EXTERNAL TABLE ods_order_reviews (
    review_id               STRING,
    order_id                STRING,
    review_score            STRING,
    review_comment_title    STRING,
    review_comment_message  STRING,
    review_creation_date    STRING,
    review_answer_timestamp STRING
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar'=',','quoteChar'='"','escapeChar'='\\')
STORED AS TEXTFILE
LOCATION '/olist/data/olist_order_reviews_dataset.csv'
TBLPROPERTIES ('skip.header.line.count'='1');

-- 6. 订单主表
DROP TABLE IF EXISTS ods_orders;
CREATE EXTERNAL TABLE ods_orders (
    order_id                      STRING,
    customer_id                   STRING,
    order_status                  STRING,
    order_purchase_timestamp      STRING,
    order_approved_at             STRING,
    order_delivered_carrier_date  STRING,
    order_delivered_customer_date STRING,
    order_estimated_delivery_date STRING
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar'=',','quoteChar'='"','escapeChar'='\\')
STORED AS TEXTFILE
LOCATION '/olist/data/olist_orders_dataset.csv'
TBLPROPERTIES ('skip.header.line.count'='1');

-- 7. 商品表
DROP TABLE IF EXISTS ods_products;
CREATE EXTERNAL TABLE ods_products (
    product_id                 STRING,
    product_category_name      STRING,
    product_name_lenght        STRING,
    product_description_lenght STRING,
    product_photos_qty         STRING,
    product_weight_g           STRING,
    product_length_cm          STRING,
    product_height_cm          STRING,
    product_width_cm           STRING
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar'=',','quoteChar'='"','escapeChar'='\\')
STORED AS TEXTFILE
LOCATION '/olist/data/olist_products_dataset.csv'
TBLPROPERTIES ('skip.header.line.count'='1');

-- 8. 卖家表
DROP TABLE IF EXISTS ods_sellers;
CREATE EXTERNAL TABLE ods_sellers (
    seller_id              STRING,
    seller_zip_code_prefix STRING,
    seller_city            STRING,
    seller_state           STRING
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar'=',','quoteChar'='"','escapeChar'='\\')
STORED AS TEXTFILE
LOCATION '/olist/data/olist_sellers_dataset.csv'
TBLPROPERTIES ('skip.header.line.count'='1');

-- 9. 类目翻译表
DROP TABLE IF EXISTS ods_category_translation;
CREATE EXTERNAL TABLE ods_category_translation (
    product_category_name         STRING,
    product_category_name_english STRING
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES ('separatorChar'=',','quoteChar'='"','escapeChar'='\\')
STORED AS TEXTFILE
LOCATION '/olist/data/product_category_name_translation.csv'
TBLPROPERTIES ('skip.header.line.count'='1');

-- 验证
SHOW TABLES;
