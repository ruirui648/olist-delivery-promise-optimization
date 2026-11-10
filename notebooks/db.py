"""Olist 项目数据库访问。

默认连本机 MySQL 的 olist 库，可用环境变量覆盖：
    OLIST_DB_HOST / OLIST_DB_PORT / OLIST_DB_USER / OLIST_DB_PASS / OLIST_DB_NAME
"""
import os

import pandas as pd
import pymysql

CONF = dict(
    host=os.getenv("OLIST_DB_HOST", "127.0.0.1"),
    port=int(os.getenv("OLIST_DB_PORT", "3306")),
    user=os.getenv("OLIST_DB_USER", "root"),
    password=os.getenv("OLIST_DB_PASS", "123456"),
    database=os.getenv("OLIST_DB_NAME", "olist"),
    charset="utf8mb4",
)


def query(sql, params=None):
    """跑查询，返回 DataFrame。"""
    conn = pymysql.connect(**CONF)
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description] if cur.description else []
        return pd.DataFrame(rows, columns=cols)
    finally:
        conn.close()


def execute(sql):
    """执行一段可能包含多条语句的 SQL（建表、清洗用）。"""
    conn = pymysql.connect(**CONF, autocommit=True)
    try:
        with conn.cursor() as cur:
            for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
                cur.execute(stmt)
    finally:
        conn.close()
