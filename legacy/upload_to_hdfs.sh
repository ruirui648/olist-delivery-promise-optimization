#!/bin/bash
# =====================================================================
# upload_to_hdfs.sh  数据上传 + HDFS 目录整理脚本
# 作用：
#   1. 在 HDFS 建库目录和分主题子目录
#   2. 把本地 Olist/data 下的 9 个 CSV 分别上传到对应子目录
# 前提：本地数据在 ~/Olist/data/，HDFS 服务已启动
# 执行：bash scripts/upload_to_hdfs.sh
# =====================================================================

set -e  # 遇到错误立即退出

# 本地数据目录（按你的实际路径改）
LOCAL_DATA="$HOME/Olist/data"

# HDFS 根目录
HDFS_ROOT="/olist/data"

echo "===== 1. 检查本地数据是否存在 ====="
if [ ! -d "$LOCAL_DATA" ]; then
    echo "错误：找不到 $LOCAL_DATA，请先确认数据已上传到虚拟机"
    exit 1
fi
ls -l "$LOCAL_DATA"

echo ""
echo "===== 2. 创建 HDFS 目录结构 ====="
hdfs dfs -mkdir -p \
    "$HDFS_ROOT/customers" \
    "$HDFS_ROOT/geolocation" \
    "$HDFS_ROOT/order_items" \
    "$HDFS_ROOT/order_payments" \
    "$HDFS_ROOT/order_reviews" \
    "$HDFS_ROOT/orders" \
    "$HDFS_ROOT/products" \
    "$HDFS_ROOT/sellers" \
    "$HDFS_ROOT/category_translation" \
    "/olist/warehouse"

echo "目录创建完成"
hdfs dfs -ls /olist/

echo ""
echo "===== 3. 上传 CSV 到对应子目录 ====="

upload() {
    local file="$1"
    local subdir="$2"
    if [ -f "$LOCAL_DATA/$file" ]; then
        echo "上传 $file -> $HDFS_ROOT/$subdir/"
        hdfs dfs -put -f "$LOCAL_DATA/$file" "$HDFS_ROOT/$subdir/"
    else
        echo "警告：本地缺少 $file，跳过"
    fi
}

upload olist_customers_dataset.csv           customers
upload olist_geolocation_dataset.csv         geolocation
upload olist_order_items_dataset.csv         order_items
upload olist_order_payments_dataset.csv      order_payments
upload olist_order_reviews_dataset.csv       order_reviews
upload olist_orders_dataset.csv              orders
upload olist_products_dataset.csv            products
upload olist_sellers_dataset.csv             sellers
upload product_category_name_translation.csv category_translation

echo ""
echo "===== 4. 验证上传结果 ====="
echo "--- 文件列表 ---"
hdfs dfs -ls -R "$HDFS_ROOT"
echo ""
echo "--- 数据总量 ---"
hdfs dfs -du -h "$HDFS_ROOT"

echo ""
echo "===== 完成！现在可以执行 hive -f sql/01_ods_init.sql ====="
