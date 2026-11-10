#!/bin/bash
# =====================================================================
# run_all.sh  一键执行全流程（按用户确认的顺序）
# 用法：bash scripts/run_all.sh
# 前置：数据已在 HDFS /olist/data（平铺）、Hive/Spark 已启动
#
# 执行顺序：
#   1. ODS 建表 (01)
#   2. 数据质量检测 (00)  -> 输出数据质量报告
#   3. DWD 清洗 (02)
#   4. 验证清洗结果 (02b)
#   5. DWS 合表 (03)
#   6. 分析主题 (04~07)  -> 结果存 Hive ADS 表
#   7. 可视化（本地单独跑 build_dashboard.py 连 HiveServer2）
# =====================================================================

set -e

echo "========== 1/7: ODS 建表 =========="
hive -f sql/01_ods_init.sql

echo "========== 2/7: 数据质量检测 =========="
hive -f sql/00_data_quality_check.sql

echo "========== 3/7: DWD 清洗 =========="
hive -f sql/02_dwd_etl.sql

echo "========== 4/7: 验证清洗结果 =========="
hive -f sql/02b_verify_clean.sql

echo "========== 5/7: DWS 合表（订单宽表） =========="
hive -f sql/03_dws_wide.sql

echo "========== 6/7: 分析主题（结果存 Hive ADS 表） =========="
spark-sql -f sql/04_funnel.sql
spark-sql -f sql/05_topn.sql
spark-sql -f sql/06_rfm.sql
spark-sql -f sql/07_pareto_time_delivery.sql

echo ""
echo "========== 完成！ =========="
echo "分析结果表已存入 Hive olist 库：ads_funnel / ads_top_* / ads_rfm_* / ads_pareto / ads_order_hour / ads_delivery"
echo ""
echo "下一步（本地 Windows）："
echo "  1. 虚拟机启动 HiveServer2: hive --service hiveserver2 &"
echo "  2. 本地 pip install pyhive thrift thrift-sasl pandas matplotlib"
echo "  3. 修改 visualization/build_dashboard.py 里的 HIVE_HOST 为虚拟机 IP"
echo "  4. 本地运行: python visualization/build_dashboard.py"
