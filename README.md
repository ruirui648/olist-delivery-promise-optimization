# Olist 巴西电商数据分析

Olist 是巴西的一个电商平台，公开了 2016-09 至 2018-08 脱敏后的交易数据。本仓库用 MySQL + Python 对这批数据做了一次完整分析：9 张原始 CSV 导入数据库，用 SQL 建清洗层和宽表，再在 notebook 里逐主题取数分析。

数据量不大（约 9.9 万订单），重点在取数口径和分析过程，不在算力。

> 仓库里 `legacy/` 是早期用 Hadoop + Hive + Spark 实现的版本，后来改成 MySQL + Python，旧代码留作备份。
> 当前可展示的产出是 `output/Olist电商数据分析看板.html`——6 页交互看板，覆盖经营、履约、客户、品类、物流、支付，
> 图表库与数据都已内联，一个文件即可打开，不需要联网。

## 数据

| 表 | 行数 | 说明 |
|---|---|---|
| orders | 99,441 | 订单主表，含下单、支付、发货、送达、承诺送达时间 |
| order_items | 112,650 | 订单商品明细 |
| order_payments | 103,886 | 支付记录，一单可多笔或分期 |
| order_reviews | 104,719 | 评分与评论 |
| customers | 99,441 | 客户，含真实客户标识 customer_unique_id |
| products | 32,951 | 商品，610 条缺类目 |
| sellers | 3,095 | 卖家 |
| geolocation | 1,000,163 | 邮编对应的经纬度，重复很多 |
| category_translation | 71 | 类目葡语到英语的对照 |

原始 CSV 打包在 `data.zip`（约 44MB，解压后 127MB）。解压到 `data/` 目录即可，该目录已被 git 忽略。

```bash
unzip data.zip        # 得到 data/ 下的 9 张 CSV
```

## 架构

```text
data.zip（9 张 CSV，解压 127MB）
  │  scripts/import_olist_mysql.py
  ▼
ODS 层 · 9 张原始表
  │  字段全为 TEXT，贴源不动：orders / order_items / order_payments /
  │  order_reviews / customers / products / sellers / geolocation / 类目翻译
  │  notebooks/01_数据清洗.ipynb
  ▼
DWD 层 · 8 张清洗表
  │  时间字段转 DATETIME、地理表按邮编聚合、支付与评价聚合到订单级
  │  notebooks/02_合表_订单宽表.ipynb
  ▼
DWS 层 · dws_order_wide（112,650 行）
  │  9 表关联，粒度 = 订单 × 商品
  │  派生 distance_km / delivered_days / promise_days / slack_days
  │  14 个 analysis notebook（只读，不写库）
  ▼
分析结果 → output/ 看板与报告
```

数据库实际 **18 张表**：9 张 ODS + 8 张 DWD + 1 张 DWS。ADS 层不单独落表，分析结果直接在 notebook 里出。

另外两条独立支线，不依赖上面的建模结果：

- `sql/`：同一套清洗与分析的**纯 SQL 实现**，只用 MySQL 客户端就能跑
- `scripts/promise_delay_model.py`：直接读 CSV 做承诺时效与延误预测，和数据库完全无关

## 目录

```
.
├── data.zip                原始 CSV 打包（解压后为 data/，不入库）
├── docs/                   设计与口径说明
├── notebooks/              SQL + Python 分析（18 个 notebook + db.py）
│   ├── db.py               数据库连接
│   ├── 00_数据质量检测.ipynb
│   ├── 01_数据清洗.ipynb        建 dwd 层
│   ├── 02_合表_订单宽表.ipynb   建 dws 层
│   └── analysis_01~14.ipynb     各分析主题
├── sql/                    同一套清洗与分析的纯 SQL 版
├── scripts/
│   ├── init_mysql.sql      建库
│   ├── import_olist_mysql.py
│   └── promise_delay_model.py   承诺日期偏差 + 延误预测
├── output/
│   ├── Olist电商数据分析看板.html   6 页交互看板，单文件自包含，双击即开
│   └── promise_and_delay_report.md  延误模型报告
└── legacy/                 早期 Hive/Spark 版本（代码 + 一份 PPT 备份）
```

## 环境

- MySQL 8.0
- Python 3.10+，依赖见 `requirements.txt`

数据库连接配置在 `notebooks/db.py`，默认连本机 `127.0.0.1:3306`、用户 `root`、库 `olist`，可以用环境变量覆盖：

```bash
export OLIST_DB_HOST=127.0.0.1
export OLIST_DB_USER=root
export OLIST_DB_PASS=你的密码
export OLIST_DB_NAME=olist
```

## 运行

```bash
# 1. 解压数据并建库
unzip data.zip                       # 得到 data/ 下 9 张 CSV
mysql -u root -p < scripts/init_mysql.sql
python scripts/import_olist_mysql.py

# 2. 按顺序跑 notebook
#    00 质检 → 01 建 dwd → 02 建 dws → analysis_01 ~ 14
jupyter notebook notebooks/

# 3. 承诺日期偏差与延误预测（直接读 CSV，不依赖上面的表）
python scripts/promise_delay_model.py
```

01 和 02 会重建 `dwd_*`、`dws_order_wide`，其余 notebook 只读不写。

## 分层

| 层 | 表 | 说明 |
|---|---|---|
| ODS | 9 张原始表 | 直接由 CSV 导入，字段全是文本 |
| DWD | dwd_orders / items / customers / sellers / products / geo / order_payment / reviews | 时间转 DATETIME，地理表按邮编聚合，支付与评价聚合到订单级 |
| DWS | dws_order_wide | 订单 × 商品粒度的宽表，9 表关联，补距离与时效字段 |
| ADS | — | 分析结果在各 notebook 里直接出，不单独落表 |

## 主要结论

| 主题 | 结果 |
|---|---|
| 履约 | 支付转化 98.45%，送达率 97.02%，取消与不可用 1,234 单（1.24%） |
| 流失归因 | 代金券订单流失率 3.62%，是信用卡（1.15%）的 3 倍 |
| 客户 | 93,358 名客户，97% 只买过一次；核心高价值人群占 25.3%，贡献 42% 收入 |
| 类目集中度 | 74 个类目里，前 18 个贡献 80% 的销售额 |
| 增长结构 | 2018 年 GMV 739 万雷亚尔，新客首单占 96.7%-97.7%，复购长期不到 4% |
| 承诺时效 | 96,478 单已送达，平均 12.6 天送达、承诺 23.7 天，平均提前 11.2 天，准时率 91.9% |
| 延误与评分 | 提前 7 天以上平均 4.32 分、差评率 8.9%；延迟 7 天以上平均 1.74 分、差评率 78.2% |
| 距离 | 1000km 以上延误率 11.69%，是 100km 内（6.39%）的近两倍 |
| 承诺优化 | 按送达时长建模承诺日（评估集 MAE 3.72 天），90% 服务水位下平均承诺可由 23.7 天压到 16.5 天，违约率 <5% |
| 分层承诺 | 各州履约能力差异明显：SP 可承诺 15 天、RJ 需 19 天、RS 需 20 天，全国统一承诺等于按最慢线路给所有人定价 |

延误对评分的影响非常直接：延迟超过一周的订单，近八成给了差评。

承诺这件事也不是「要不要收紧」，而是「按订单算」：用训练 / 校准 / 评估三段时序切分，
先预测每笔订单的送达时长，再用残差分位数把业务要求的服务水位翻译成缓冲天数，
最后按州给出承诺。全国统一 23.7 天的做法，保守了约 7 天。

## 踩过的坑

1. **评论字段把 CSV 切错位**。`review_comment_message` 里有英文逗号，直接按逗号分割会把一条记录切成多段。导入时用带引号解析的方式处理。
2. **geolocation 重复严重**。100 万行里同一邮编有几十条坐标，按邮编取平均后降到 1.9 万行，再拿去算距离。
3. **用错客户标识导致复购率算成 0**。`customer_id` 是订单级匿名 ID，一单一个，真正区分客户的是 `customer_unique_id`。第一版 RFM 频次全是 1，换字段后才发现。
4. **支付金额挂到明细行会重复计算**。宽表是订单 × 商品粒度，而支付金额是订单级字段，每个商品行都带一遍。按订单求和时金额被放大过 24%，所以支付金额要先聚合到订单再关联。

## 已知问题

- 单机 MySQL，10 万级数据，没有做索引和性能优化，部分聚合查询要几秒。
- 承诺日期里的「收紧 N 天」是在历史分布上做的模拟，不是真实实验，只能说明量级。
- 评价表按 order_id 聚合过了，一个订单多条评价时取平均分。
- 类目翻译表只覆盖 71 个类目，其余标记为 unknown。

## 参考

- 数据集：[Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
- 口径说明见 `docs/设计文档.md`
