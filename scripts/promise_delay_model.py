"""
Olist 承诺日期偏差分析 + 延误预测模型

输入：data/ 下 9 张 CSV
输出：output/promise_deviation_summary.md
      output/delay_model_report.md
      output/ads_promise_deviation.csv
      output/delay_model_feature_importance.csv

运行：python scripts/promise_delay_model.py
"""
import json
import os

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import average_precision_score, roc_auc_score

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "output")
os.makedirs(OUT, exist_ok=True)

DATE_COLS = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]


def load():
    orders = pd.read_csv(os.path.join(DATA, "olist_orders_dataset.csv"))
    for c in DATE_COLS:
        orders[c] = pd.to_datetime(orders[c], errors="coerce")

    items = pd.read_csv(os.path.join(DATA, "olist_order_items_dataset.csv"))
    cust = pd.read_csv(os.path.join(DATA, "olist_customers_dataset.csv"))
    sellers = pd.read_csv(os.path.join(DATA, "olist_sellers_dataset.csv"))
    products = pd.read_csv(os.path.join(DATA, "olist_products_dataset.csv"))
    geo = pd.read_csv(os.path.join(DATA, "olist_geolocation_dataset.csv"))

    # 每个邮编前缀取经纬度中位数（原表 100 万行有大量重复坐标）
    geo_med = (
        geo.groupby("geolocation_zip_code_prefix")[["geolocation_lat", "geolocation_lng"]]
        .median()
        .reset_index()
        .rename(columns={"geolocation_zip_code_prefix": "zip"})
    )
    return orders, items, cust, sellers, products, geo_med


def build_order_level(orders, items, cust, sellers, products, geo_med):
    # 订单级商品聚合
    agg = (
        items.groupby("order_id")
        .agg(
            n_items=("order_item_id", "count"),
            n_sellers=("seller_id", "nunique"),
            total_price=("price", "sum"),
            total_freight=("freight_value", "sum"),
            seller_id=("seller_id", "first"),
            product_id=("product_id", "first"),
        )
        .reset_index()
    )

    df = orders.merge(agg, on="order_id", how="left")
    df = df.merge(cust, on="customer_id", how="left")
    df = df.merge(
        sellers.rename(columns={"seller_zip_code_prefix": "seller_zip", "seller_state": "seller_state"}),
        on="seller_id",
        how="left",
    )
    df = df.merge(products[["product_id", "product_category_name", "product_weight_g"]], on="product_id", how="left")

    df = df.merge(
        geo_med.rename(columns={"zip": "customer_zip_code_prefix", "geolocation_lat": "c_lat", "geolocation_lng": "c_lng"}),
        on="customer_zip_code_prefix",
        how="left",
    )
    df = df.merge(
        geo_med.rename(columns={"zip": "seller_zip", "geolocation_lat": "s_lat", "geolocation_lng": "s_lng"}),
        on="seller_zip",
        how="left",
    )

    # 距离（haversine）
    lat1, lon1, lat2, lon2 = map(np.radians, [df.c_lat, df.c_lng, df.s_lat, df.s_lng])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    df["distance_km"] = 6371 * 2 * np.arcsin(np.sqrt(a))

    # 时间口径
    day = 86400.0
    df["delivered_days"] = (df.order_delivered_customer_date - df.order_purchase_timestamp).dt.total_seconds() / day
    df["promise_days"] = (df.order_estimated_delivery_date - df.order_purchase_timestamp).dt.total_seconds() / day
    # slack > 0 表示比承诺早到
    df["slack_days"] = (df.order_estimated_delivery_date - df.order_delivered_customer_date).dt.total_seconds() / day
    df["is_late"] = (df.slack_days < 0).astype(int)
    return df


def part_a_promise(df, lines):
    d = df[(df.order_status == "delivered") & df.delivered_days.notna() & df.promise_days.notna()].copy()
    n = len(d)

    lines.append("## 一、承诺日期偏差分析\n")
    lines.append(f"- 样本：{n:,} 笔已送达订单（2016-09 至 2018-08）")
    lines.append(f"- 平均承诺时长：{d.promise_days.mean():.1f} 天")
    lines.append(f"- 平均实际送达：{d.delivered_days.mean():.1f} 天")
    lines.append(f"- 平均提前：{d.slack_days.mean():.1f} 天（中位 {d.slack_days.median():.1f} 天）")
    lines.append(f"- **提前送达占比：{(d.slack_days >= 0).mean():.1%}**")
    lines.append(f"- **违约（晚于承诺）占比：{d.is_late.mean():.1%}**")
    lines.append("")

    # 按承诺时长的违约率
    d["promise_bucket"] = pd.cut(
        d.promise_days, [-1, 7, 14, 21, 30, 45, 1e9],
        labels=["<=7天", "8-14天", "15-21天", "22-30天", "31-45天", ">45天"],
    )
    bucket = d.groupby("promise_bucket", observed=True).agg(
        订单数=("order_id", "count"), 违约率=("is_late", "mean"), 平均提前天数=("slack_days", "mean")
    ).reset_index()
    lines.append("### 1.1 承诺越宽松，违约率越低（承诺时长分档）\n")
    lines.append(bucket.to_markdown(index=False, floatfmt=".3f"))
    lines.append("")

    # 按州
    state = (
        d.groupby("customer_state")
        .agg(订单数=("order_id", "count"), 违约率=("is_late", "mean"), 平均提前天数=("slack_days", "mean"))
        .sort_values("订单数", ascending=False)
        .head(10)
        .reset_index()
    )
    lines.append("### 1.2 分州表现（订单量 Top10）\n")
    lines.append(state.to_markdown(index=False, floatfmt=".3f"))
    lines.append("")

    # 按距离
    d["dist_bucket"] = pd.cut(
        d.distance_km, [-1, 100, 300, 700, 1200, 1e9],
        labels=["<=100km", "100-300km", "300-700km", "700-1200km", ">1200km"],
    )
    dist = d.groupby("dist_bucket", observed=True).agg(
        订单数=("order_id", "count"), 违约率=("is_late", "mean"), 平均提前天数=("slack_days", "mean")
    ).reset_index()
    lines.append("### 1.3 距离越远，承诺越不可靠\n")
    lines.append(dist.to_markdown(index=False, floatfmt=".3f"))
    lines.append("")

    # 收紧模拟
    lines.append("### 1.4 收紧承诺的代价模拟（承诺日整体前移）\n")
    lines.append("| 承诺前移 | 新违约率 | 新增违约订单 | 新增违约占比 |")
    lines.append("|---|---|---|---|")
    base = d.is_late.mean()
    base_n = int(d.is_late.sum())
    sim_rows = []
    for k in range(0, 8):
        # 承诺前移 k 天：原本“提前不足 k 天”的订单也会变成违约，即 slack < k
        new_late = (d.slack_days < k).mean()
        new_n = int((d.slack_days < k).sum())
        added = new_late - base
        sim_rows.append(dict(k=k, new_late=new_late, added_n=new_n - base_n, added_pct=added))
        lines.append(f"| {k} 天 | {new_late:.2%} | {new_n - base_n:,} | {added:+.2%} |")
    lines.append("")

    # 落盘
    d[["order_id", "customer_state", "delivered_days", "promise_days", "slack_days", "is_late", "distance_km"]] \
        .to_csv(os.path.join(OUT, "ads_promise_deviation.csv"), index=False)
    return dict(n=n, early_rate=float((d.slack_days >= 0).mean()), late_rate=float(base),
                mean_slack=float(d.slack_days.mean()), mean_promise=float(d.promise_days.mean()),
                sim=sim_rows), d


def part_b_model(df, lines):
    d = df[(df.order_status == "delivered") & df.delivered_days.notna() & df.promise_days.notna()].copy()
    d = d[d.order_purchase_timestamp >= "2017-01-01"]  # 剔除早期样本量过少的月份

    d["purchase_month"] = d.order_purchase_timestamp.dt.month
    d["purchase_dow"] = d.order_purchase_timestamp.dt.dayofweek
    d["purchase_hour"] = d.order_purchase_timestamp.dt.hour
    d["approval_hours"] = (d.order_approved_at - d.order_purchase_timestamp).dt.total_seconds() / 3600

    top_cat = d.product_category_name.value_counts().head(20).index
    d["category"] = np.where(d.product_category_name.isin(top_cat), d.product_category_name, "other")

    feat_cols = [
        "promise_days", "purchase_month", "purchase_dow", "purchase_hour",
        "total_price", "total_freight", "n_items", "n_sellers",
        "product_weight_g", "distance_km", "approval_hours",
    ]
    cat_cols = ["customer_state", "seller_state", "category"]

    d = d.dropna(subset=["is_late", "promise_days", "distance_km"])
    d["total_price"] = d.total_price.fillna(d.total_price.median())
    d["total_freight"] = d.total_freight.fillna(0)
    d["n_items"] = d.n_items.fillna(1)
    d["n_sellers"] = d.n_sellers.fillna(1)
    d["product_weight_g"] = d.product_weight_g.fillna(d.product_weight_g.median())
    d["approval_hours"] = d.approval_hours.fillna(d.approval_hours.median())

    for c in cat_cols:
        d[c] = d[c].fillna("unknown").astype("category").cat.codes

    X = d[feat_cols + cat_cols].astype(float).values
    y = d.is_late.values

    # 时间切分：用历史预测未来
    split_date = pd.Timestamp("2018-06-01")
    tr = d.order_purchase_timestamp < split_date
    te = ~tr
    Xtr, ytr, Xte, yte = X[tr.values], y[tr.values], X[te.values], y[te.values]

    clf = HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.06, max_depth=None, min_samples_leaf=40,
        l2_regularization=1.0, early_stopping=True, validation_fraction=0.15, random_state=42,
    )
    clf.fit(Xtr, ytr)
    p = clf.predict_proba(Xte)[:, 1]
    auc = roc_auc_score(yte, p)
    ap = average_precision_score(yte, p)

    # 基线：全部预测为“不延误”
    base_auc = 0.5
    lines.append("## 二、延误预测模型\n")
    lines.append(f"- 样本：{len(d):,} 笔（训练 {tr.sum():,} / 测试 {te.sum():,}，按时间切分，测试集为 2018-06 之后）")
    lines.append(f"- 目标：**是否晚于承诺日期送达**（测试集正例率 {yte.mean():.1%}）")
    lines.append(f"- 模型：HistGradientBoosting（LightGBM 同类实现），300 轮、学习率 0.06")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|---|---|")
    lines.append(f"| ROC-AUC | **{auc:.3f}** |")
    lines.append(f"| PR-AUC | {ap:.3f} |")
    lines.append(f"| 正例基准率 | {yte.mean():.3f} |")
    lines.append("")

    # 置换重要性（在测试集上，抽样加速）
    idx = np.random.RandomState(0).choice(len(Xte), size=min(8000, len(Xte)), replace=False)
    names = feat_cols + cat_cols
    r = permutation_importance(clf, Xte[idx], yte[idx], n_repeats=5, random_state=42, scoring="roc_auc")
    imp = pd.DataFrame({"feature": names, "importance": r.importances_mean}).sort_values(
        "importance", ascending=False
    )
    lines.append("### 2.1 特征重要性（测试集置换重要性，Top10）\n")
    lines.append(imp.head(10).to_markdown(index=False, floatfmt=".4f"))
    lines.append("")

    # 阈值效果：取 top10% 高风险订单
    thr = np.quantile(p, 0.9)
    mask = p >= thr
    lines.append("### 2.2 业务用法：抓 Top10% 高风险订单\n")
    lines.append(f"- 阈值 {thr:.3f}，命中 {mask.sum():,} 单（占测试集 {mask.mean():.1%}）")
    lines.append(f"- 该组实际延误率 **{yte[mask].mean():.1%}**，是整体（{yte.mean():.1%}）的 "
                 f"{yte[mask].mean() / yte.mean():.2f} 倍")
    lines.append(f"- 覆盖了全部延误订单的 **{yte[mask].sum() / yte.sum():.1%}**")
    lines.append("")

    imp.to_csv(os.path.join(OUT, "delay_model_feature_importance.csv"), index=False)
    return dict(auc=float(auc), pr_auc=float(ap), n=int(len(d)), n_train=int(tr.sum()), n_test=int(te.sum()),
                pos_rate=float(yte.mean()), top10_lift=float(yte[mask].mean() / yte.mean()),
                top10_capture=float(yte[mask].sum() / yte.sum()),
                top_feats=imp.head(5).feature.tolist(), top_imp=imp.head(5).importance.round(4).tolist())


def main():
    orders, items, cust, sellers, products, geo_med = load()
    df = build_order_level(orders, items, cust, sellers, products, geo_med)

    lines = ["# Olist 承诺日期偏差 & 延误预测\n", f"生成时间：{pd.Timestamp.now():%Y-%m-%d %H:%M}\n"]
    a, d = part_a_promise(df, lines)
    lines.append("\n---\n")
    b = part_b_model(df, lines)

    report = "\n".join(lines)
    with open(os.path.join(OUT, "promise_and_delay_report.md"), "w", encoding="utf-8") as f:
        f.write(report)

    print(report)
    print("\n=== JSON ===")
    print(json.dumps({"promise": a, "model": b}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
