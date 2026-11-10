# -*- coding: utf-8 -*-
"""把 9 张原始 CSV 导入 MySQL。

几个处理点：
1. 评论文本里有换行，导入前替换成空格
2. 分块写入，避免一次占满内存
3. 表已存在时直接覆盖
"""
import os
import time

import pandas as pd
from sqlalchemy import create_engine

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")

USER = os.getenv("OLIST_DB_USER", "root")
PASS = os.getenv("OLIST_DB_PASS", "123456")
HOST = os.getenv("OLIST_DB_HOST", "127.0.0.1")
PORT = os.getenv("OLIST_DB_PORT", "3306")
DB = os.getenv("OLIST_DB_NAME", "olist")

engine = create_engine(f"mysql+pymysql://{USER}:{PASS}@{HOST}:{PORT}/{DB}?charset=utf8mb4")

# 表名 -> (csv 文件, 需要清理换行的字段)
TABLES = {
    "olist_customers_dataset": ("olist_customers_dataset.csv", None),
    "olist_geolocation_dataset": ("olist_geolocation_dataset.csv", None),
    "olist_order_items_dataset": ("olist_order_items_dataset.csv", None),
    "olist_order_payments_dataset": ("olist_order_payments_dataset.csv", None),
    "olist_order_reviews_dataset": ("olist_order_reviews_dataset.csv",
                                    ["review_comment_message", "review_comment_title"]),
    "olist_orders_dataset": ("olist_orders_dataset.csv", None),
    "olist_products_dataset": ("olist_products_dataset.csv", None),
    "olist_sellers_dataset": ("olist_sellers_dataset.csv", None),
    "product_category_name_translation": ("product_category_name_translation.csv", None),
}

t0 = time.time()
for table, (csv_file, clean_cols) in TABLES.items():
    t1 = time.time()
    print(f"导入 {table} ...")

    df = pd.read_csv(os.path.join(DATA, csv_file), encoding="utf-8")

    if clean_cols:
        for col in clean_cols:
            if col in df.columns:
                df[col] = (df[col].fillna("").astype(str)
                           .str.replace("\n", " ").str.replace("\r", " "))

    df.to_sql(table, engine, if_exists="replace", index=False, chunksize=5000)
    print(f"  {table}: {len(df)} 行，耗时 {time.time() - t1:.1f}s")

print(f"全部导入完成，总耗时 {time.time() - t0:.1f}s")
