# -*- coding: utf-8 -*-
"""
Olist 电商数据分析看板生成器 v3
- 数据源：构建时连接 MySQL（ADS 聚合表 + ads_fact_order 订单级事实表）
- 架构：4 个标签页（总览/物流时效/商品评分/深度分析）+ 全局联动筛选器（年/月/州/支付方式/类目）
- 联动筛选：基于订单级事实表，筛选后前端实时重算所有图表
"""
import json
import os

import pymysql

MYSQL_CONF = dict(
    host=os.getenv("OLIST_DB_HOST", "127.0.0.1"),
    port=int(os.getenv("OLIST_DB_PORT", "3306")),
    user=os.getenv("OLIST_DB_USER", "root"),
    password=os.getenv("OLIST_DB_PASS", ""),
    database=os.getenv("OLIST_DB_NAME", "olist"),
    charset="utf8mb4",
)

TABLES = ['ads_churn_amount','ads_churn_amount_summary','ads_churn_month','ads_churn_payment',
          'ads_churn_state','ads_churn_weekday','ads_delivery_state','ads_delivery_summary',
          'ads_funnel','ads_monthly_gmv','ads_order_hour','ads_order_weekday','ads_pareto',
          'ads_rfm_summary','ads_top_category','ads_top_product','ads_top_seller','ads_top_state',
          'ads_rating_summary','ads_rating_category','ads_fact_order',
          'ads_seller_concentration','ads_seller_score','ads_seller_bad','ads_seller_cross_state',
          'ads_category_matrix','ads_category_state','ads_state_aov',
          'ads_payment_installments','ads_payment_type_profile','ads_payment_voucher',
          'ads_daily_active','ads_weekly_gmv','ads_quarterly_gmv',
          'ads_rfm_lifecycle','ads_rfm_repurchase',
          'ads_market_basket']

def _fetch_all():
    conn = pymysql.connect(**MYSQL_CONF)
    try:
        cur = conn.cursor()
        data = {}
        for t in TABLES:
            try:
                cur.execute(f'SELECT * FROM `{t}`')
                cols = [d[0] for d in cur.description]
                data[t] = {'columns': cols, 'rows': [dict(zip(cols, r)) for r in cur.fetchall()]}
            except Exception as e:
                print(f'[警告] {t} 拉取失败: {e}（需先在虚拟机运行对应 Notebook）')
                data[t] = {'columns': [], 'rows': []}
        return data
    finally:
        conn.close()

DATA = _fetch_all()
FACT = DATA['ads_fact_order']['rows']
print(f'在线拉取完成: {len(TABLES)} 张表, 事实表 {len(FACT)} 行')

def rows(t):
    return DATA[t]['rows']

# ============ 静态聚合数据预处理（深度分析标签页用） ============

funnel = rows('ads_funnel')
stage_order = ['created', 'approved', 'invoiced', 'shipped', 'delivered']
stage_names = {'created': '下单', 'approved': '支付', 'invoiced': '开票', 'shipped': '发货', 'delivered': '送达'}
funnel_map = {r['stage']: r for r in funnel}
funnel_data = [{'stage': stage_names[s], 'cnt': funnel_map.get(s, {}).get('order_cnt', 0),
                'rate': funnel_map.get(s, {}).get('conversion_rate', 0)} for s in stage_order]

pay = [r for r in rows('ads_churn_payment') if r['payment_type'] in ('credit_card', 'boleto', 'voucher', 'debit_card')]
pay_names = {'credit_card': '信用卡', 'boleto': '银行账单', 'voucher': '代金券', 'debit_card': '借记卡'}
pay_map = {r['payment_type']: r for r in pay}
pay_data = [{'name': pay_names[k], 'churn_rate': round(pay_map[k]['churn_rate']*100, 2),
             'lift': pay_map[k]['lift'], 'cnt': pay_map[k]['order_cnt']} for k in pay_names]

state_churn = sorted(rows('ads_churn_state'), key=lambda x: x['lift'], reverse=True)

amount_bin_order = ['<50', '50-100', '100-200', '200-500', '>=500']
amount_map = {r['amount_bin']: r for r in rows('ads_churn_amount')}
amount_data = [{'bin': b, 'churn_rate': round(amount_map[b]['churn_rate']*100, 2), 'cnt': amount_map[b]['order_cnt']}
               for b in amount_bin_order if b in amount_map]

month_churn = [r for r in rows('ads_churn_month') if r['order_cnt'] >= 100]
weekday_names = {1: '周一', 2: '周二', 3: '周三', 4: '周四', 5: '周五', 6: '周六', 7: '周日'}
weekday_churn = sorted(rows('ads_churn_weekday'), key=lambda x: x['weekday'])

top_cat = rows('ads_top_category')
top_prod = rows('ads_top_product')
top_seller = rows('ads_top_seller')
top_state = rows('ads_top_state')
# 月度 GMV：过滤掉 2016 年冷启动期的残缺测试数据（2016-09 gmv=None、2016-12 仅1单19元），
# 否则同比/环比会因基数极小爆出无意义的百分比（如 2017-10 同比 2016-10 达 1517%）
monthly_gmv = [r for r in rows('ads_monthly_gmv') if r['gmv'] is not None and r['month'] >= '2017-01']
hour_data = sorted(rows('ads_order_hour'), key=lambda x: int(x['hour_of_day']))
# 星期表存储为无序中文字符串（Spark groupBy 输出序），必须按周一~周日重排
_WD_ORDER = {'周一': 1, '周二': 2, '周三': 3, '周四': 4, '周五': 5, '周六': 6, '周日': 7}
weekday_order_data = sorted(rows('ads_order_weekday'), key=lambda x: _WD_ORDER.get(x['weekday'], 99))
pareto = [r for r in rows('ads_pareto') if r['product_category_name_english'] is not None]
delivery_state = rows('ads_delivery_state')
# RFM：兼容新旧两种 ads_rfm_summary 结构（新版含 strategy/revenue_pct/avg_recency）
rfm_raw = rows('ads_rfm_summary')
rfm = [r for r in rfm_raw if r.get('customer_cnt') and r['customer_cnt'] > 1]
rating_summary = sorted(rows('ads_rating_summary'), key=lambda x: x['review_score'])
rating_category = rows('ads_rating_category')

# 新增三方向（卖家侧 / 品类区域 / 支付行为）
seller_concentration = rows('ads_seller_concentration')
seller_score = rows('ads_seller_score')
seller_bad = rows('ads_seller_bad')
seller_cross_state = rows('ads_seller_cross_state')

category_matrix = rows('ads_category_matrix')
category_state = rows('ads_category_state')
state_aov = rows('ads_state_aov')

payment_installments = rows('ads_payment_installments')
payment_type_profile = rows('ads_payment_type_profile')
payment_voucher = rows('ads_payment_voucher')
market_basket = rows('ads_market_basket')

# 时间维度衍生表
daily_active = sorted(rows('ads_daily_active'), key=lambda x: x['order_date'])
# 周 GMV 不再直接用 ads_weekly_gmv（其周标签未补零导致 lag 按字符串排序、环比全错，且周日起始）。
# 改为从日粒度 ads_daily_active 按「周一~周日」重新聚合：只保留完整 7 天的周，过滤冷启动期（周GMV<2万），
# 环比按时间顺序用前一个完整周计算。
from datetime import datetime as _dt, timedelta as _td
_weeks = {}
for _r in daily_active:
    if _r.get('gmv') is None:
        continue
    _d = _dt.strptime(str(_r['order_date'])[:10], '%Y-%m-%d').date()
    _mon = _d - _td(days=_d.weekday())  # 所在周的周一
    _k = _mon.strftime('%Y-%m-%d')
    _w = _weeks.setdefault(_k, {'gmv': 0.0, 'order_cnt': 0, 'days': 0})
    _w['gmv'] += float(_r['gmv'])
    _w['order_cnt'] += int(_r['order_cnt'] or 0)
    _w['days'] += 1
_weeks = {k: v for k, v in sorted(_weeks.items()) if v['days'] == 7}  # 只留完整周
_week_keys = [k for k, v in _weeks.items() if v['gmv'] >= 20000]  # 过滤冷启动残周
# 只保留最长的连续周序列（每周一恰好比上一周一多 7 天），剔除孤岛期（如 2016-10 的零星测试单）
_runs, _cur = [], []
for _k in _week_keys:
    if _cur and (_dt.strptime(_k, '%Y-%m-%d') - _dt.strptime(_cur[-1], '%Y-%m-%d')).days != 7:
        _runs.append(_cur); _cur = []
    _cur.append(_k)
if _cur: _runs.append(_cur)
_week_keys = max(_runs, key=len)
weekly_gmv = []
_prev = None
for _k in _week_keys:
    _v = _weeks[_k]
    _y, _m, _d = _k.split('-')
    _iso = _dt(int(_y), int(_m), int(_d)).isocalendar()
    _wow = round((_v['gmv'] - _prev) / _prev * 100, 1) if _prev else None
    weekly_gmv.append({'week': f'{_iso[0]}-W{_iso[1]:02d}', 'monday': _k,
                       'order_cnt': _v['order_cnt'], 'gmv': round(_v['gmv'], 2), 'wow_pct': _wow})
    _prev = _v['gmv']
print(f'周 GMV 重算: {len(weekly_gmv)} 个完整周（{_week_keys[0]} ~ {_week_keys[-1]}）')
# 季度 GMV：剔除两类失真季度后重算同比——
# ① 2016 年冷启动残缺季度（2016-Q3 仅 1 单、2016-Q4 不完整）：基数极小导致 2017 年同比爆出百万级百分比（如 1333518%）；
# ② 数据窗口末尾的不完整季度（如数据只到 2018-08，则 2018-Q3 仅有 2 个月）：同比偏低造成「增长失速」假象。
# 剔除后重新计算同比：只有去年同期也是完整季度时才给出同比值。
import re as _re
def _qnum(qs):
    m = _re.match(r'(\d{4})-Q(\d)', str(qs))
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)
_q_raw = rows('ads_quarterly_gmv')
quarterly_gmv = [r for r in _q_raw if r.get('gmv') is not None and _qnum(r['quarter']) >= (2017, 1)]
# 剔除末尾不完整季度：取月度表最大月份，若其所在季度的月份不足 3 个月则剔除该季度
_m_max = max((r['month'] for r in monthly_gmv if r.get('month')), default=None)
if _m_max:
    _my, _mm = int(_m_max[:4]), int(_m_max[5:7])
    _last_q = (_my, (_mm - 1) // 3 + 1)
    _months_in_last_q = len({m for m in (r['month'] for r in monthly_gmv if r.get('month')) if _qnum(f"{_qnum(m)[0]}-Q{_qnum(m)[1]}") == _last_q})
    if _months_in_last_q < 3:
        quarterly_gmv = [r for r in quarterly_gmv if _qnum(r['quarter']) < _last_q]
_q_by_key = {r['quarter']: r for r in quarterly_gmv}
for r in quarterly_gmv:
    y, q = _qnum(r['quarter'])
    prev = _q_by_key.get(f'{y-1}-Q{q}')
    # 去年同期不存在（或订单量过小属于冷启动）时，同比置 None，避免无意义百分比
    r['yoy_pct'] = round((r['gmv'] - prev['gmv']) / prev['gmv'] * 100, 1) if prev and prev.get('order_cnt', 0) >= 1000 else None
# 环比：与上一个季度比较（同比与环比都只对完整可比季度计算）
_q_sorted = sorted(quarterly_gmv, key=lambda r: _qnum(r['quarter']))
_q_prev = None
for r in _q_sorted:
    r['qoq_pct'] = round((r['gmv'] - _q_prev['gmv']) / _q_prev['gmv'] * 100, 1) if _q_prev is not None else None
    _q_prev = r
quarterly_gmv = _q_sorted
# 客户生命周期 / 复购
rfm_lifecycle = rows('ads_rfm_lifecycle')
rfm_repurchase = rows('ads_rfm_repurchase')

data_js = {
    'funnel': funnel_data, 'pay': pay_data, 'state_churn': state_churn,
    'amount': amount_data, 'month_churn': month_churn,
    'weekday_churn': [{'name': weekday_names.get(r['weekday'], str(r['weekday'])),
                       'churn_rate': round(r['churn_rate']*100, 2), 'lift': r['lift'], 'cnt': r['order_cnt']}
                      for r in weekday_churn],
    'top_cat': top_cat, 'top_prod': top_prod, 'top_seller': top_seller, 'top_state': top_state,
    'monthly_gmv': monthly_gmv, 'hour': hour_data, 'weekday_order': weekday_order_data,
    'pareto': pareto, 'delivery_state': delivery_state, 'rfm': rfm,
    'rating_summary': rating_summary, 'rating_category': rating_category,
    'seller_concentration': seller_concentration, 'seller_score': seller_score,
    'seller_bad': seller_bad, 'seller_cross_state': seller_cross_state,
    'category_matrix': category_matrix, 'category_state': category_state, 'state_aov': state_aov,
    'payment_installments': payment_installments, 'payment_type_profile': payment_type_profile,
    'payment_voucher': payment_voucher,
    'daily_active': daily_active, 'weekly_gmv': weekly_gmv, 'quarterly_gmv': quarterly_gmv,
    'rfm_lifecycle': rfm_lifecycle, 'rfm_repurchase': rfm_repurchase,
    'market_basket': market_basket,
}

# ============ HTML ============

def js_dump(obj):
    return json.dumps(obj, ensure_ascii=False, default=str)

html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Olist 巴西电商数据分析看板</title>
<script src="echarts.min.js"></script>
<style>
:root{
  --bg:#fbfaf7; --ink:#1a1a1a; --ink-2:#6b6b6b; --ink-3:#9a9a9a;
  --line:#e6e3dc; --line-strong:#d4d0c6; --accent:#e4572e; --accent-2:#2b6cb0;
  --serif:"Georgia","Noto Serif SC",serif;
  --sans:"-apple-system","PingFang SC","Microsoft YaHei",sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);-webkit-font-smoothing:antialiased;}
.wrap{max-width:1200px;margin:0 auto;padding:0 40px 80px;}
.masthead{padding:56px 0 24px;border-bottom:2px solid var(--ink);}
.masthead .kicker{font-size:12px;letter-spacing:.22em;color:var(--accent);text-transform:uppercase;margin-bottom:12px;font-weight:600;}
.masthead h1{font-family:var(--serif);font-size:40px;line-height:1.15;font-weight:700;}
.masthead .sub{font-size:14px;color:var(--ink-2);margin-top:12px;max-width:680px;line-height:1.7;}

/* 标签页 */
.tabs{display:flex;gap:8px;margin:28px 0 0;border-bottom:1px solid var(--line-strong);}
.tab-btn{background:none;border:none;padding:12px 20px;font-size:15px;color:var(--ink-2);cursor:pointer;
  border-bottom:3px solid transparent;font-family:var(--sans);font-weight:600;}
.tab-btn:hover{color:var(--ink);}
.tab-btn.active{color:var(--accent);border-bottom-color:var(--accent);}
.tab-panel{display:none;}
.tab-panel.active{display:block;}
.lang-btn{margin-left:auto;background:none;border:1px solid var(--line-strong);border-radius:20px;padding:6px 16px;
  font-size:13px;color:var(--ink-2);cursor:pointer;font-family:var(--sans);font-weight:600;align-self:center;
  margin-bottom:6px;transition:all .2s;}
.lang-btn:hover{color:var(--accent);border-color:var(--accent);}
.lang-btn.zh{color:#fff;background:var(--accent);border-color:var(--accent);}

/* 筛选器 */
.filter-bar{display:flex;gap:16px;align-items:flex-end;flex-wrap:wrap;padding:20px 0 8px;}
.filter-bar .f{display:flex;flex-direction:column;gap:4px;}
.filter-bar label{font-size:11px;color:var(--ink-3);letter-spacing:.06em;}
.filter-bar select{padding:6px 10px;border:1px solid var(--line-strong);border-radius:4px;background:#fff;
  font-size:13px;color:var(--ink);min-width:110px;outline:none;cursor:pointer;}
.filter-bar select:focus{border-color:var(--accent);}
.filter-bar .reset{padding:7px 14px;border:1px solid var(--line-strong);border-radius:4px;background:#fff;
  font-size:12px;color:var(--ink-2);cursor:pointer;}
.filter-bar .reset:hover{border-color:var(--accent);color:var(--accent);}
.filter-note{font-size:12px;color:var(--ink-3);margin:4px 0 0;}

/* KPI */
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin:20px 0 28px;}
.kpi{background:#fff;padding:22px 20px;}
.kpi .label{font-size:12px;color:var(--ink-3);letter-spacing:.08em;}
.kpi .value{font-family:var(--serif);font-size:30px;font-weight:700;margin-top:6px;}
.kpi .unit{font-size:14px;color:var(--ink-2);font-weight:400;margin-left:2px;}
.kpi .note{font-size:12px;color:var(--ink-2);margin-top:4px;}

/* 区块 */
.section{padding:40px 0 8px;}
.section-head{display:flex;align-items:baseline;gap:14px;margin-bottom:4px;}
.section-head .no{font-family:var(--serif);font-size:15px;color:var(--accent);font-weight:700;}
.section-head h2{font-family:var(--serif);font-size:25px;font-weight:700;}
.section-desc{font-size:13.5px;color:var(--ink-2);max-width:720px;line-height:1.7;margin-bottom:20px;}
.page-head{margin:8px 0 24px;padding-bottom:16px;border-bottom:1px solid var(--line);}
.page-head h2{font-family:var(--serif);font-size:28px;font-weight:700;margin-bottom:6px;}
.page-head p{font-size:14px;color:var(--ink-2);max-width:760px;line-height:1.7;}
.chart-box{background:#fff;border:1px solid var(--line);margin-bottom:24px;}
.chart-box .chart{width:100%;}
.chart-box .caption{padding:12px 18px;border-top:1px solid var(--line);font-size:12.5px;color:var(--ink-2);line-height:1.6;}
.chart-box .caption b{color:var(--ink);}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:24px;}
.insight{background:#fff;border-left:3px solid var(--accent);padding:16px 20px;margin-bottom:24px;font-size:13.5px;line-height:1.8;color:var(--ink-2);}
.insight b{color:var(--ink);}
@media(max-width:860px){.kpi-grid{grid-template-columns:repeat(2,1fr);}.grid-2{grid-template-columns:1fr;}.wrap{padding:0 16px 60px;}.masthead h1{font-size:30px;}}
</style>
</head>
<body>
<div class="wrap">

<div class="masthead">
  <div class="kicker">E-Commerce Data Analysis</div>
  <h1>Olist 巴西电商数据分析</h1>
  <div class="sub">基于 2016–2018 年巴西全品类电商平台 Olist 的 99,441 笔真实订单（16.01M 雷亚尔 GMV、72 个类目、27 个州），覆盖履约漏斗、流失归因、客户分层（K-Means）、商品结构（ABC）、销售节奏、物流时效与评分六大主题。支持按年份 / 月份 / 州 / 支付方式 / 类目联动筛选。</div>
</div>

<div class="tabs">
  <button class="tab-btn active" data-tab="overview">总览</button>
  <button class="tab-btn" data-tab="time">时间维度</button>
  <button class="tab-btn" data-tab="category">商品类目</button>
  <button class="tab-btn" data-tab="seller">卖家维度</button>
  <button class="tab-btn" data-tab="region">地区·物流</button>
  <button class="tab-btn" data-tab="customer">客户维度</button>
  <button class="lang-btn" id="langToggle" title="切换品类/州/支付方式为中文显示">中文</button>
</div>

<!-- ═══ Tab 1: 总览（联动筛选） ═══ -->
<div class="tab-panel active" id="tab-overview">
  <div class="filter-bar" id="filterBar">
    <div class="f"><label>年份</label><select id="fYear"><option value="">全部</option><option>2016</option><option>2017</option><option>2018</option></select></div>
    <div class="f"><label>月份</label><select id="fMonth"><option value="">全部</option></select></div>
    <div class="f"><label>州</label><select id="fState"><option value="">全部</option></select></div>
    <div class="f"><label>支付方式</label><select id="fPay"><option value="">全部</option><option value="credit_card">信用卡</option><option value="boleto">银行账单</option><option value="voucher">代金券</option><option value="debit_card">借记卡</option></select></div>
    <div class="f"><label>类目</label><select id="fCat"><option value="">全部</option></select></div>
    <button class="reset" id="fReset">重置筛选</button>
  </div>
  <p class="filter-note" id="filterNote"></p>
  <div class="kpi-grid" id="kpiOverview"></div>
  <div class="grid-2">
    <div class="chart-box"><div class="chart" id="cCatTop" style="height:380px"></div><div class="caption"><b>类目排行</b>：按成交额降序 TOP10，蓝色渐变深浅=成交额档位。</div></div>
    <div class="chart-box"><div class="chart" id="cMonthly" style="height:380px"></div><div class="caption"><b>月度销售额</b>：2017-11 黑五达到峰值；2018 年后进入稳定期。</div></div>
  </div>
  <div class="grid-2">
    <div class="chart-box"><div class="chart" id="cPayDist" style="height:300px"></div><div class="caption"><b>支付方式构成</b>：信用卡 ≈3/4 绝对主导。<b>结论</b>：巴西电商信任门槛高，信用卡+分期是转化标配；boleto（银行账单）作为无卡人群的兜底渠道不可下线，否则直接流失约 1/5 客户。</div></div>
    <div class="chart-box"><div class="chart" id="cStateTop" style="height:300px"></div><div class="caption"><b>地域分布</b>：SP 一州约占 40%，前 4 州近 7 成。<b>结论</b>：市场高度集中，资源投放按 SP→RJ→MG 优先级执行。</div></div>
  </div>
</div>

<!-- ═══ Tab 2: 时间维度 ═══ -->
<div class="tab-panel" id="tab-time">
  <div class="page-head"><h2>时间维度</h2><p>从日、周、季度、月多尺度拆解销售节奏与活跃度，识别增长拐点与峰值产能。</p></div>
  <div class="kpi-grid" id="kpiTime"></div>
  <div class="chart-box"><div class="chart" id="chartDailyActive" style="height:360px"></div><div class="caption" id="capDailyActive"></div></div>
  <div class="grid-2">
    <div class="chart-box"><div class="chart" id="chartQuarterly" style="height:320px"></div><div class="caption" id="capQuarterly"></div></div>
    <div class="chart-box"><div class="chart" id="chartWeekly" style="height:320px"></div><div class="caption" id="capWeekly"></div></div>
  </div>
  <div class="grid-2">
    <div class="chart-box"><div class="chart" id="chartMonthly" style="height:340px"></div><div class="caption" id="capMonthly"></div></div>
    <div class="chart-box"><div class="chart" id="chartHourWeek" style="height:340px"></div><div class="caption" id="capHourWeek"></div></div>
  </div>
</div>

<!-- ═══ Tab 3: 商品类目维度（含评分口碑） ═══ -->
<div class="tab-panel" id="tab-category">
  <div class="page-head"><h2>商品类目维度</h2><p>类目收入结构、ABC 集中度、品类组合矩阵与评分口碑——回答「哪些类目值得加大供给、哪些类目需要治理」。</p></div>
  <div class="kpi-grid" id="kpiCategory"></div>
  <div class="kpi-grid" id="kpiRating"></div>
  <div class="grid-2">
    <div class="chart-box"><div class="chart" id="chartCatTop" style="height:360px"></div><div class="caption" id="capCatTop"></div></div>
    <div class="chart-box"><div class="chart" id="chartPareto" style="height:360px"></div><div class="caption" id="capPareto"></div></div>
  </div>
  <div class="insight" id="insightMatrix"></div>
  <div class="chart-box"><div class="chart" id="chartMatrix" style="height:440px"></div><div class="caption" id="capMatrix"></div></div>
  <div class="grid-2">
    <div class="chart-box"><div class="chart" id="cScoreDist" style="height:320px"></div><div class="caption" id="capScoreDist"></div></div>
    <div class="chart-box"><div class="chart" id="cLateRating" style="height:320px"></div><div class="caption" id="capLateRating"></div></div>
  </div>
  <div class="chart-box"><div class="chart" id="chartCatBestWorst" style="height:360px"></div><div class="caption" id="capCatBestWorst"></div></div>
  <div class="chart-box"><div class="chart" id="chartInstall" style="height:360px"></div><div class="caption" id="capInstall"></div></div>
  <div class="chart-box"><div class="chart" id="chartBasket" style="height:420px"></div><div class="caption" id="capBasket"></div></div>
</div>

<!-- ═══ Tab 4: 卖家维度 ═══ -->
<div class="tab-panel" id="tab-seller">
  <div class="page-head"><h2>卖家维度</h2><p>帕累托集中度、头部卖家画像、绩效打分、劣质卖家识别与跨区域发货惩罚——回答「资源向谁倾斜、谁该被治理」。</p></div>
  <div class="kpi-grid" id="kpiSeller"></div>
  <div class="insight" id="insightSeller"></div>
  <div class="chart-box"><div class="chart" id="chartSellerConc" style="height:400px"></div><div class="caption" id="capSellerConc"></div></div>
  <div class="grid-2">
    <div class="chart-box"><div class="chart" id="chartSellerTrait" style="height:340px"></div><div class="caption" id="capSellerTrait"></div></div>
    <div class="chart-box"><div class="chart" id="chartSellerScore" style="height:340px"></div><div class="caption" id="capSellerScore"></div></div>
  </div>
  <div class="grid-2">
    <div class="chart-box"><div class="chart" id="chartSellerBad" style="height:300px"></div><div class="caption" id="capSellerBad"></div></div>
    <div class="chart-box"><div class="chart" id="chartSellerCross" style="height:300px"></div><div class="caption" id="capSellerCross"></div></div>
  </div>
</div>

<!-- ═══ Tab 5: 地区·物流维度 ═══ -->
<div class="tab-panel" id="tab-region">
  <div class="page-head"><h2>地区 · 物流维度</h2><p>27 个州的订单分布、客单价、准时率与主导品类，叠加物流时效诊断——回答「运力该往哪投、体验治理从哪抓」。</p></div>
  <div class="kpi-grid" id="kpiRegion"></div>
  <div class="kpi-grid" id="kpiDelivery"></div>
  <div class="insight" id="insightDelivery2"></div>
  <div class="grid-2">
    <div class="chart-box"><div class="chart" id="chartStateTop" style="height:340px"></div><div class="caption" id="capStateTop"></div></div>
    <div class="chart-box"><div class="chart" id="chartStateAov" style="height:340px"></div><div class="caption" id="capStateAov"></div></div>
  </div>
  <div class="grid-2">
    <div class="chart-box"><div class="chart" id="chartStateOntime" style="height:340px"></div><div class="caption" id="capStateOntime"></div></div>
    <div class="chart-box"><div class="chart" id="chartCatState" style="height:340px"></div><div class="caption" id="capCatState"></div></div>
  </div>
  <div class="grid-2">
    <div class="chart-box"><div class="chart" id="chartPriceDelivery" style="height:380px"></div><div class="caption" id="capPriceDelivery"></div></div>
    <div class="chart-box"><div class="chart" id="chartLateDays" style="height:380px"></div><div class="caption" id="capLateDays"></div></div>
  </div>
</div>

<!-- ═══ Tab 8: 客户维度 ═══ -->
<div class="tab-panel" id="tab-customer">
  <div class="page-head"><h2>客户维度</h2><p>客户价值分层（K-Means）、流失归因、复购与生命周期价值（CLV）。</p></div>
  <div class="kpi-grid" id="kpiCustomer"></div>
  <div class="chart-box"><div class="chart" id="chartRfm" style="height:380px"></div><div class="caption" id="capRfm"></div></div>
  <div class="chart-box" id="strategyBox"><div class="caption" id="capStrategy"></div></div>
  <div class="insight" id="insightChurn"></div>
  <div class="grid-2">
    <div class="chart-box"><div class="chart" id="chartPay" style="height:320px"></div><div class="caption" id="capPay"></div></div>
    <div class="chart-box"><div class="chart" id="chartPayProfile" style="height:320px"></div><div class="caption" id="capPayProfile"></div></div>
  </div>
</div>

<div style="text-align:center;padding:50px 0 16px;color:var(--ink-3);font-size:12px;border-top:1px solid var(--line);margin-top:36px;">
  Olist Brazilian E-Commerce Dataset · 数据在线拉取自虚拟机 MySQL · 可视化：ECharts · 风格：编辑部风格（lieflat-charts）
</div>
</div>

<script>
const DATA = __DATA_JS__;
const HAS_FACT = __HAS_FACT__;

const C = { ink:'#1a1a1a', ink2:'#6b6b6b', ink3:'#9a9a9a', line:'#e6e3dc', lineStrong:'#d4d0c6',
            accent:'#e4572e', accent2:'#2b6cb0', gray:'#b9b5ac', teal:'#26a69a' };
const baseAxis = {
  axisLine:{lineStyle:{color:C.lineStrong}}, axisTick:{show:false},
  axisLabel:{color:C.ink2, fontSize:12}, splitLine:{lineStyle:{color:C.line, type:'dashed'}}
};
function fmtMoney(v){ return 'R$' + (v/1e6).toFixed(2) + 'M'; }
function fmtMoneyK(v){ return v>=1e6 ? 'R$'+(v/1e6).toFixed(1)+'M' : 'R$'+(v/1e3).toFixed(0)+'K'; }
function fmtNum(v){ return v.toLocaleString('zh-CN'); }

// ═══════════ 语言切换（英文/葡语 ↔ 中文）═══════════
let LANG = 'en';   // 'en' = 原文(英文品类/葡语州名缩写)；'zh' = 中文
const I18N_CAT = {
  'agro_industry_and_commerce':'农工业与商贸','air_conditioning':'空调','art':'艺术品','arts_and_craftmanship':'手工艺术','audio':'音频设备',
  'auto':'汽车用品','baby':'婴儿用品','bed_bath_table':'床浴桌品','books_general_interest':'大众图书','books_imported':'进口图书','books_technical':'技术图书',
  'cds_dvds_musicals':'CD/DVD/音乐','christmas_supplies':'圣诞用品','cine_photo':'影视摄影','computers':'电脑','computers_accessories':'电脑配件',
  'consoles_games':'游戏主机','construction_tools_construction':'建筑工具','construction_tools_lights':'灯具照明','construction_tools_safety':'安全防护',
  'cool_stuff':'新奇小物','costruction_tools_garden':'园艺工具','costruction_tools_tools':'五金工具','diapers_and_hygiene':'尿布与卫生用品','drinks':'饮品',
  'dvds_blu_ray':'DVD/蓝光','electronics':'电子产品','fashio_female_clothing':'女装','fashion_bags_accessories':'箱包配饰','fashion_childrens_clothes':'童装',
  'fashion_male_clothing':'男装','fashion_shoes':'鞋类','fashion_sport':'运动服饰','fashion_underwear_beach':'内衣沙滩装','fixed_telephony':'固定电话','flowers':'花卉',
  'food':'食品','food_drink':'食品饮料','furniture_bedroom':'卧室家具','furniture_decor':'家具装饰','furniture_living_room':'客厅家具',
  'furniture_mattress_and_upholstery':'床垫软装','garden_tools':'园艺工具','health_beauty':'健康美妆','home_appliances':'家用电器','home_confort':'家居舒适',
  'home_construction':'家居装修','housewares':'家居用品','industry_commerce_and_business':'工业商业','kitchen_dining_laundry_garden_furniture':'厨卫花园家具',
  'la_cuisine':'厨具','luggage_accessories':'行李配件','market_place':'市场杂项','music':'音乐','musical_instruments':'乐器','office_furniture':'办公家具',
  'party_supplies':'派对用品','perfumery':'香水','pet_shop':'宠物用品','security_and_services':'安防服务','signaling_and_security':'信号安防',
  'small_appliances':'小家电','small_appliances_home_oven_and_coffee':'厨房小家电','sports_leisure':'运动休闲','stationery':'文具','tablets_printing_image':'平板打印影像',
  'telephony':'通讯设备','toys':'玩具','watches_gifts':'手表礼品'
};
const I18N_STATE = {
  'AC':'阿克里州','AL':'阿拉戈斯州','AM':'亚马孙州','AP':'阿马帕州','BA':'巴伊亚州','CE':'塞阿拉州','DF':'联邦区','ES':'圣埃斯皮里图州','GO':'戈亚斯州',
  'MA':'马拉尼昂州','MG':'米纳斯吉拉斯州','MS':'南马托格罗索州','MT':'马托格罗索州','PA':'帕拉州','PB':'帕拉伊巴州','PE':'伯南布哥州','PI':'皮奥伊州',
  'PR':'巴拉那州','RJ':'里约热内卢州','RN':'北里奥格兰德州','RO':'朗多尼亚州','RR':'罗赖马州','RS':'南里奥格兰德州','SC':'圣卡塔琳娜州','SE':'塞尔希培州',
  'SP':'圣保罗州','TO':'托坎廷斯州'
};
const I18N_PAY = {'credit_card':'信用卡','boleto':'银行账单','voucher':'代金券','debit_card':'借记卡','not_defined':'其他'};
function catName(x){
  if(x==null || x==='') return '未分类';
  const s = String(x);
  if(LANG==='zh' && I18N_CAT[s]) return I18N_CAT[s];
  return s.replace(/_/g,' ');
}
function stateName(x){
  if(x==null || x==='') return '-';
  const s = String(x).toUpperCase();
  if(LANG==='zh' && I18N_STATE[s]) return I18N_STATE[s];
  return s;
}
function payName(x){
  if(x==null || x==='') return '其他';
  if(LANG==='zh' && I18N_PAY[x]) return I18N_PAY[x];
  return String(x);
}

// 五档渐变：hue 0=橙(风险) 1=蓝(量/额) 2=青绿(正向)
const GRADS = {
  0: [['#fbe8e0','#e4572e'],['#f6cfbd','#d95c33'],['#eec1a8','#c94f2b'],['#e2a382','#b34022'],['#d07c54','#9a2e12']],
  1: [['#e8f0f8','#2b6cb0'],['#cfe0f0','#2b6cb0'],['#b3cde6','#2b6cb0'],['#8fb4da','#245c96'],['#5f8fc0','#1b4470']],
  2: [['#e4f2ee','#3a9188'],['#c9e6df','#3a9188'],['#a9d8cd','#2e7a72'],['#7fc2b3','#256a62'],['#4f9f91','#1c504a']]
};
function gradeColor(v, min, max, hue){
  const H = GRADS[hue===undefined?1:hue];
  if(max===min) return H[2][1];
  let idx = Math.floor((v-min)/(max-min)*5);
  idx = Math.max(0, Math.min(4, idx));
  const [c1,c2] = H[idx];
  return new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:c1},{offset:1,color:c2}]);
}
const charts = {};
function getChart(id){
  if(!charts[id]) charts[id] = echarts.init(document.getElementById(id));
  return charts[id];
}
window.addEventListener('resize', ()=>Object.values(charts).forEach(c=>c.resize()));

// ═══════════ 联动筛选 ═══════════
const filters = { year:'', month:'', state:'', pay:'', cat:'' };
let filteredFact = [];

function applyFilters(){
  if(!HAS_FACT){ return; }
  filteredFact = DATA.fact.filter(r =>
    (!filters.year || r.year === filters.year) &&
    (!filters.month || r.month === filters.month) &&
    (!filters.state || r.state === filters.state) &&
    (!filters.pay || r.pay_type === filters.pay) &&
    (!filters.cat || r.category === filters.cat)
  );
  renderOverview();
  document.getElementById('filterNote').textContent =
    '当前筛选：' + filteredFact.length.toLocaleString() + ' 单 / 99,441 单（' +
    (filteredFact.length/99441*100).toFixed(1) + '%）';
}

// ═══════════ Tab1 总览 ═══════════
function renderOverview(){
  const f = filteredFact;
  const sales = f.reduce((s,r)=>s+(+r.payment_value||0),0);
  const scored = f.filter(r=>r.review_score);
  const avgScore = scored.length ? scored.reduce((s,r)=>s+r.review_score,0)/scored.length : 0;
  const late = f.filter(r=>+r.is_late===1).length;
  const kpis = [
    {label:'总销售额', value:'R$'+(sales/1e6).toFixed(2), unit:'M', note:'payment_value 口径'},
    {label:'订单量', value: fmtNum(f.length), unit:'单', note:'占全量 '+(f.length/99441*100).toFixed(1)+'%'},
    {label:'平均评分', value: avgScore.toFixed(2), unit:'/5', note: fmtNum(scored.length)+' 条评价'},
    {label:'延误率', value:(late/f.length*100||0).toFixed(1), unit:'%', note: fmtNum(late)+' 单延误'},
  ];
  document.getElementById('kpiOverview').innerHTML = kpis.map(k=>
    '<div class="kpi"><div class="label">'+k.label+'</div><div class="value">'+k.value+'<span class="unit">'+k.unit+'</span></div><div class="note">'+k.note+'</div></div>').join('');

  // 类目 TOP10
  const catAgg = {};
  f.forEach(r=>{ if(r.category){ catAgg[r.category]=(catAgg[r.category]||0)+(+r.payment_value||0);} });
  const catTop = Object.entries(catAgg).sort((a,b)=>b[1]-a[1]).slice(0,10);
  getChart('cCatTop').setOption({
    grid:{left:10,right:60,top:10,bottom:10,containLabel:true},
    tooltip:{trigger:'axis', formatter:p=>catName(p[0].name)+'<br/>成交额 '+fmtMoneyK(p[0].value)},
    xAxis:{type:'value', ...baseAxis, axisLabel:{...baseAxis.axisLabel, formatter:v=>fmtMoneyK(v)}},
    yAxis:{type:'category', data:catTop.map(x=>catName(x[0])).reverse(), ...baseAxis, axisLabel:{color:C.ink, fontSize:11}},
    series:[{type:'bar', data:catTop.map(x=>+x[1].toFixed(0)).reverse(), barWidth:16,
      itemStyle:{color:p=>gradeColor(p.value, catTop[catTop.length-1][1], catTop[0][1], 1), borderRadius:[0,3,3,0]}}]
  }, true);

  // 月度销售额
  const mAgg = {};
  f.forEach(r=>{ mAgg[r.month]=(mAgg[r.month]||0)+(+r.payment_value||0); });
  const months = Object.keys(mAgg).sort();
  getChart('cMonthly').setOption({
    grid:{left:10,right:10,top:10,bottom:10,containLabel:true},
    tooltip:{trigger:'axis', formatter:p=>p[0].name+'<br/>销售额 '+fmtMoneyK(p[0].value)},
    xAxis:{type:'category', data:months, ...baseAxis, axisLabel:{color:C.ink2, fontSize:10, rotate:45}},
    yAxis:{type:'value', ...baseAxis, axisLabel:{...baseAxis.axisLabel, formatter:v=>fmtMoneyK(v)}},
    series:[{type:'bar', data:months.map(m=>+mAgg[m].toFixed(0)), barWidth:'60%',
      itemStyle:{color:p=>gradeColor(p.value, 0, Math.max(...months.map(m=>mAgg[m])), 1), borderRadius:[3,3,0,0]}}]
  }, true);

  // 支付方式构成
  const payAgg = {};
  f.forEach(r=>{ if(r.pay_type) payAgg[r.pay_type]=(payAgg[r.pay_type]||0)+1; });
  const payArr = Object.entries(payAgg).sort((a,b)=>b[1]-a[1]);
  getChart('cPayDist').setOption({
    tooltip:{trigger:'item', formatter:p=>payName(p.name)+'<br/>'+fmtNum(p.value)+' 单（'+p.percent+'%）'},
    legend:{bottom:0, textStyle:{color:C.ink2, fontSize:12}, icon:'circle'},
    series:[{type:'pie', radius:['42%','68%'], center:['50%','45%'],
      label:{show:true, formatter:'{d}%', color:C.ink, fontSize:12},
      labelLine:{lineStyle:{color:C.lineStrong}},
      itemStyle:{borderColor:'#fff', borderWidth:2},
      data:payArr.map((x,i)=>({name:payName(x[0]), value:x[1], itemStyle:{color:gradeColor(x[1], payArr[payArr.length-1][1], payArr[0][1], 1)}}))}]
  }, true);

  // 州 TOP10
  const stAgg = {};
  f.forEach(r=>{ if(r.state) stAgg[r.state]=(stAgg[r.state]||0)+(+r.payment_value||0); });
  const stTop = Object.entries(stAgg).sort((a,b)=>b[1]-a[1]).slice(0,10);
  getChart('cStateTop').setOption({
    grid:{left:10,right:60,top:10,bottom:10,containLabel:true},
    tooltip:{trigger:'axis', formatter:p=>stateName(p[0].name)+'<br/>成交额 '+fmtMoneyK(p[0].value)},
    xAxis:{type:'value', ...baseAxis, axisLabel:{...baseAxis.axisLabel, formatter:v=>fmtMoneyK(v)}},
    yAxis:{type:'category', data:stTop.map(x=>stateName(x[0])).reverse(), ...baseAxis, axisLabel:{color:C.ink, fontSize:12}},
    series:[{type:'bar', data:stTop.map(x=>+x[1].toFixed(0)).reverse(), barWidth:16,
      itemStyle:{color:p=>gradeColor(p.value, stTop[stTop.length-1][1], stTop[0][1], 1), borderRadius:[0,3,3,0]}}]
  }, true);
}

// ═══════════ 物流渲染（并入地区·物流页，静态全量） ═══════════
function renderDeliveryStatic(){
  const dv = DATA.fact.filter(r=>r.delivery_days!=null);
  const onTime = dv.filter(r=>+r.is_late===0).length;
  const lateArr = dv.filter(r=>+r.is_late===1);
  const avgLateDays = lateArr.length ? lateArr.reduce((s,r)=>s+(+r.late_days||0),0)/lateArr.length : 0;
  const procArr = dv.filter(r=>r.processing_hours!=null);
  const shipArr = dv.filter(r=>r.ship_days!=null);
  const avgProc = procArr.reduce((s,r)=>s+r.processing_hours,0)/Math.max(1,procArr.length)/24;
  const avgShip = shipArr.reduce((s,r)=>s+r.ship_days,0)/Math.max(1,shipArr.length);
  const earlyArr = dv.filter(r=>r.late_days!=null && +r.late_days<0);

  setKpi('kpiDelivery', [
    kpiCard('准时率', (onTime/dv.length*100).toFixed(1), '%', fmtNum(dv.length)+' 单已送达'),
    kpiCard('延误订单', fmtNum(lateArr.length), '单', '平均延误 '+avgLateDays.toFixed(1)+' 天'),
    kpiCard('卖家处理', avgProc.toFixed(1), '天', '支付→交承运商'),
    kpiCard('承运商运输', avgShip.toFixed(1), '天', '承运商→客户'),
  ]);

  document.getElementById('insightDelivery2').innerHTML =
    '<b>结论</b>：Olist 的预计送达日期极度保守——<b>'+(earlyArr.length/dv.length*100).toFixed(1)+'% 的订单提前送达</b>（平均提前 '+
    (-earlyArr.reduce((s,r)=>s+(+r.late_days),0)/Math.max(1,earlyArr.length)).toFixed(1)+' 天），真延误仅 '+(lateArr.length/dv.length*100).toFixed(1)+
    '%。平台用「预期管理」换口碑：宁可把承诺日期往后放，也不让用户等到失望。'

  // 价格带 × 配送时长 箱线图（替代无区分度的散点）
  const bands = [[0,50,'0-50'],[50,100,'50-100'],[100,200,'100-200'],[200,500,'200-500'],[500,1e9,'500+']];
  const boxData = [], bandNames = [], bandMeds = [], bandNs = [];
  bands.forEach(b=>{
    const arr = dv.filter(r=>+r.payment_value>=b[0] && +r.payment_value<b[1] && r.delivery_days>=0 && r.delivery_days<=60)
                  .map(r=>+r.delivery_days).sort((a,b2)=>a-b2);
    if(arr.length<30) return;
    const q=p=>arr[Math.min(arr.length-1,Math.floor((arr.length-1)*p))];
    boxData.push([q(0.05), q(0.25), q(0.5), q(0.75), q(0.95)]);
    bandNames.push('R$'+b[2]); bandMeds.push(q(0.5)); bandNs.push(arr.length);
  });
  getChart('chartPriceDelivery').setOption({
    grid:{left:10,right:20,top:16,bottom:10,containLabel:true},
    tooltip:{trigger:'axis', formatter:p=>{const d=boxData[p[0].dataIndex]; return bandNames[p[0].dataIndex]+'（'+fmtNum(bandNs[p[0].dataIndex])+' 单）<br/>P95：'+d[4]+' 天<br/>Q3：'+d[3]+' 天<br/>中位数：'+d[2]+' 天<br/>Q1：'+d[1]+' 天<br/>P5：'+d[0]+' 天';}},
    xAxis:{type:'category', data:bandNames, ...baseAxis, axisLabel:{color:C.ink, fontSize:12}},
    yAxis:{type:'value', ...baseAxis, name:'配送天数', nameTextStyle:{color:C.ink2}},
    series:[{type:'boxplot', data:boxData, boxWidth:[18,38],
      itemStyle:{color:'#eef3f9', borderColor:C.accent2, borderWidth:2},
      emphasis:{itemStyle:{borderColor:C.accent}}}]
  }, true);
  const cheap = bandMeds[0], pricey = bandMeds[bandMeds.length-1];
  const diff = (pricey - cheap).toFixed(1);
  document.getElementById('capPriceDelivery').innerHTML =
    '<b>结论</b>：各价格带的配送中位数都在 '+Math.min(...bandMeds)+'~'+Math.max(...bandMeds)+
    ' 天之间，最贵与最便宜价格带仅差 <b>'+diff+' 天</b>——配送时长由「卖家仓库在哪、发什么物流」决定，与用户花多少钱<b>无关</b>。高客单用户并不享受更快的物流，这是体验分层的机会点。';

  // 配送链路分解（分年）：时间花在哪一段
  const yrAgg = {};
  dv.forEach(r=>{ if(!r.year) return; const y=yrAgg[r.year]=yrAgg[r.year]||{p:[],s:[]};
    if(r.processing_hours!=null) y.p.push(+r.processing_hours/24); if(r.ship_days!=null) y.s.push(+r.ship_days); });
  const yrKeys = Object.keys(yrAgg).sort();
  const procAvg = yrKeys.map(y=>{const a=yrAgg[y].p; return +(a.reduce((s,x)=>s+x,0)/a.length).toFixed(1);});
  const shipAvg = yrKeys.map(y=>{const a=yrAgg[y].s; return +(a.reduce((s,x)=>s+x,0)/a.length).toFixed(1);});
  getChart('chartLateDays').setOption({
    grid:{left:10,right:20,top:34,bottom:10,containLabel:true},
    tooltip:{trigger:'axis', formatter:ps=>yrKeys[ps[0].dataIndex]+' 年<br/>'+ps.map(p=>p.marker+p.seriesName+' '+p.value+' 天').join('<br/>')+'<br/>合计 '+(procAvg[ps[0].dataIndex]+shipAvg[ps[0].dataIndex])+' 天'},
    legend:{data:['卖家处理','承运商运输'], top:0, textStyle:{color:C.ink2, fontSize:11}, icon:'circle'},
    xAxis:{type:'category', data:yrKeys, ...baseAxis, axisLabel:{color:C.ink, fontSize:12}},
    yAxis:{type:'value', ...baseAxis, name:'平均天数', nameTextStyle:{color:C.ink2}},
    series:[
      {name:'卖家处理', type:'bar', stack:'t', data:procAvg, barWidth:'45%', itemStyle:{color:C.accent2, borderRadius:[0,0,0,0]}},
      {name:'承运商运输', type:'bar', stack:'t', data:shipAvg, barWidth:'45%', itemStyle:{color:C.teal, borderRadius:[3,3,0,0]},
        label:{show:true, position:'top', color:C.ink, fontSize:12, formatter:p=>(procAvg[p.dataIndex]+p.value)+' 天'}}
    ]
  }, true);
  const last = yrKeys.length-1;
  const shipShare = (shipAvg[last]/(shipAvg[last]+procAvg[last])*100).toFixed(0);
  document.getElementById('capLateDays').innerHTML =
    '<b>结论</b>：配送总时长中约 <b>'+shipShare+'% 花在承运商运输段</b>，卖家处理只占小头——提升时效的关键杠杆在<b>物流网络与仓配布局</b>（如前十字交叉分析所见：跨州发货显著更慢），督促卖家发货的边际收益有限。';
}

// ═══════════ 评分渲染（并入商品类目页，静态全量） ═══════════
function renderRatingStatic(){
  const f = DATA.fact;
  const scored = f.filter(r=>r.review_score);
  const n5 = scored.filter(r=>r.review_score===5).length;
  const n1 = scored.filter(r=>r.review_score===1).length;
  const nBad = scored.filter(r=>r.review_score<=2).length;
  const lateScored = scored.filter(r=>+r.is_late===1);
  const ontimeScored = scored.filter(r=>+r.is_late===0 && r.delivery_days!=null);
  const avg = a=>a.length? (a.reduce((s,r)=>s+r.review_score,0)/a.length) : 0;

  setKpi('kpiRating', [
    kpiCard('总评论数', fmtNum(scored.length), '条', '占订单 '+(scored.length/f.length*100).toFixed(0)+'%'),
    kpiCard('5 星占比', (n5/scored.length*100).toFixed(1), '%', fmtNum(n5)+' 条'),
    kpiCard('差评率(≤2星)', (nBad/scored.length*100).toFixed(1), '%', fmtNum(nBad)+' 条'),
    kpiCard('1 星占比', (n1/scored.length*100).toFixed(1), '%', '高于 2-4 星之和'),
  ]);

  // 评分分布：J 型
  const dist = [1,2,3,4,5].map(s=>({s, n:scored.filter(r=>r.review_score===s).length}));
  getChart('cScoreDist').setOption({
    grid:{left:10,right:10,top:16,bottom:10,containLabel:true},
    tooltip:{trigger:'axis', formatter:p=>p[0].name+'<br/>'+fmtNum(p[0].value)+' 条（'+(p[0].value/scored.length*100).toFixed(1)+'%）'},
    xAxis:{type:'category', data:dist.map(x=>x.s+'星'), ...baseAxis, axisLabel:{color:C.ink, fontSize:12}},
    yAxis:{type:'value', ...baseAxis},
    series:[{type:'bar', data:dist.map(x=>x.n), barWidth:'55%',
      label:{show:true, position:'top', color:C.ink2, fontSize:11, formatter:p=>(p.value/scored.length*100).toFixed(0)+'%'},
      itemStyle:{color:p=>gradeColor(p.value, 0, dist[4].n, 2), borderRadius:[3,3,0,0]}}]
  }, true);
  document.getElementById('capScoreDist').innerHTML =
    '<b>结论</b>：评分呈<b>极端 J 型</b>——1 星（'+(n1/scored.length*100).toFixed(1)+'%）比 2/3/4 星加起来还多。用户只在「极满意」或「极愤怒」时才写评价，中间态沉默。均值会骗人（≈4 分），<b>差评率才是真实的体验温度计</b>。';

  // 延误 vs 准时
  getChart('cLateRating').setOption({
    grid:{left:10,right:10,top:16,bottom:10,containLabel:true},
    tooltip:{trigger:'axis', formatter:p=>p[0].name+'<br/>平均评分 '+p[0].value+'<br/>'+fmtNum(p[0].cnt)+' 条评价'},
    xAxis:{type:'category', data:['准时/提前订单','延误订单'], ...baseAxis, axisLabel:{color:C.ink, fontSize:13}},
    yAxis:{type:'value', min:1, max:5, ...baseAxis},
    series:[{type:'bar', barWidth:'40%',
      data:[{value:+avg(ontimeScored).toFixed(2), cnt:ontimeScored.length, itemStyle:{color:gradeColor(4.4,3,5,2)}},
            {value:+avg(lateScored).toFixed(2), cnt:lateScored.length, itemStyle:{color:gradeColor(2,3,5,2)}}],
      label:{show:true, position:'top', formatter:p=>p.value, color:C.ink, fontSize:14, fontWeight:700}}]
  }, true);
  const gap = (avg(ontimeScored)-avg(lateScored)).toFixed(2);
  document.getElementById('capLateRating').innerHTML =
    '<b>结论</b>：延误订单均分比准时订单低 <b>'+gap+' 分</b>，这是全数据集里<b>最强因果信号</b>——差评的主因不是商品，是「没按时到」。治理差评 = 治理物流承诺，比补贴邀好评有效得多。';
}

// ═══════════ 维度页渲染（按维度拆分，懒加载） ═══════════
function renderTimePage(){
  renderKpiTime();
  renderDailyActive();
  renderQuarterly();
  renderWeekly();
  renderMonthly();
  renderHourWeek();
}
function renderCategoryPage(){
  renderKpiCategory();
  renderCatTop();
  renderPareto();
  renderMatrix();
  renderCatBestWorst();
  renderInstall();
  renderBasket();
  renderRatingStatic();
}
function renderSellerPage(){
  renderKpiSeller();
  renderSeller();
}
function renderRegionPage(){
  renderKpiRegion();
  renderRegion();
  renderDeliveryStatic();
}
function renderCustomerPage(){
  renderKpiCustomer();
  renderRfm();
  renderChurn();
  renderPayProfile();
}

// 各维度页的懒加载渲染（首次切换到该 tab 时渲染，避免隐藏 canvas 尺寸为 0）
const PAGE_RENDERERS = {
  time: renderTimePage,
  category: renderCategoryPage,
  seller: renderSellerPage,
  region: renderRegionPage,
  customer: renderCustomerPage
};
const renderedPages = {};

// ─── KPI 工具函数 ───
function kpiCard(label, value, unit, note, accent){
  const c = accent || 'var(--accent)';
  return '<div class="kpi"><div class="label">'+label+'</div><div class="value" style="color:'+c+'">'+value+'<span class="unit">'+unit+'</span></div><div class="note">'+note+'</div></div>';
}
function setKpi(id, cards){ const el=document.getElementById(id); if(el) el.innerHTML = cards.join(''); }

// ─── ① 时间维度 ───
function renderKpiTime(){
  const d = DATA.daily_active||[];
  const totalDays = d.length;
  const peak = d.reduce((m,x)=>x.active_customers>m.active_customers?x:m, d[0]||{active_customers:0, order_date:''});
  const mg = DATA.monthly_gmv||[];
  const totalGmv = mg.reduce((s,x)=>s+(+x.gmv||0),0);
  const peakMonth = mg.reduce((m,x)=>(+x.gmv||0)>(+m.gmv||0)?x:m, mg[0]||{gmv:0, month:''});
  setKpi('kpiTime', [
    kpiCard('累计 GMV', 'R$'+(totalGmv/1e6).toFixed(2)+'M', '', mg.length+' 个月'),
    kpiCard('峰值月', peakMonth.month||'-', '', 'GMV R$'+(+(peakMonth.gmv||0)/1e6).toFixed(2)+'M'),
    kpiCard('日均活跃客户', fmtNum(Math.round(d.reduce((s,x)=>s+x.active_customers,0)/(totalDays||1))), '人', totalDays+' 天'),
    kpiCard('峰值活跃日', (peak.order_date||'').slice(5), '', fmtNum(peak.active_customers)+' 活跃客户'),
  ]);
}
function renderDailyActive(){
  const d = DATA.daily_active||[];
  if(!d.length) return;
  const dates = d.map(x=>String(x.order_date).slice(5));
  const active = d.map(x=>x.active_customers);
  const orders = d.map(x=>x.order_cnt);
  getChart('chartDailyActive').setOption({
    grid:{left:10,right:50,top:30,bottom:10,containLabel:true},
    tooltip:{trigger:'axis', formatter:ps=>{const i=ps[0].dataIndex; return dates[i]+'<br/>活跃客户 '+fmtNum(active[i])+' 人<br/>订单 '+fmtNum(orders[i])+' 单';}},
    legend:{data:['活跃客户数','订单量'], top:0, textStyle:{color:C.ink2, fontSize:11}, icon:'circle'},
    xAxis:{type:'category', data:dates, ...baseAxis, axisLabel:{color:C.ink2, fontSize:9, interval:Math.floor(dates.length/12)}},
    yAxis:[{type:'value', name:'活跃客户', ...baseAxis, axisLabel:{...baseAxis.axisLabel, fontSize:10}},
           {type:'value', name:'订单量', ...baseAxis, axisLabel:{...baseAxis.axisLabel, fontSize:10}, splitLine:{show:false}}],
    series:[
      {name:'活跃客户数', type:'line', data:active, smooth:true, symbol:'none', lineStyle:{color:C.accent2, width:2}, areaStyle:{color:'rgba(43,108,176,0.07)'}},
      {name:'订单量', type:'bar', data:orders, yAxisIndex:1, barWidth:'60%', itemStyle:{color:'rgba(228,87,46,0.45)'}}
    ]
  }, true);
  document.getElementById('capDailyActive').innerHTML = '<b>日活跃客户数 vs 订单量</b>：两条曲线几乎完全同步（活跃≈订单），说明<b>客户几乎只买一次</b>——不存在「活跃但不买」的围观用户。日活跃长期在 100~200 客/天量级，黑五峰值约为日常 5 倍，平台没有稳定的日活基本盘，增长完全依赖大促脉冲。';
}
function renderQuarterly(){
  const q = DATA.quarterly_gmv||[];
  if(!q.length) return;
  const quarters = q.map(x=>x.quarter);
  const gmv = q.map(x=>+x.gmv||0);
  const yoy = q.map(x=>x.yoy_pct);
  const qoq = q.map(x=>x.qoq_pct);
  getChart('chartQuarterly').setOption({
    grid:{left:10,right:50,top:30,bottom:10,containLabel:true},
    tooltip:{trigger:'axis', formatter:ps=>{const i=ps[0].dataIndex; return quarters[i]+'<br/>GMV '+fmtMoneyK(gmv[i])+'<br/>同比 '+(yoy[i]==null?'-':yoy[i]+'%')+'<br/>环比 '+(qoq[i]==null?'-':qoq[i]+'%');}},
    legend:{data:['GMV','同比','环比'], top:0, textStyle:{color:C.ink2, fontSize:11}, icon:'circle'},
    xAxis:{type:'category', data:quarters, ...baseAxis, axisLabel:{color:C.ink2, fontSize:10}},
    yAxis:[{type:'value', ...baseAxis, axisLabel:{...baseAxis.axisLabel, formatter:v=>fmtMoneyK(v), fontSize:10}},
           {type:'value', ...baseAxis, axisLabel:{...baseAxis.axisLabel, formatter:'{value}%', fontSize:10}, splitLine:{show:false}}],
    series:[
      {name:'GMV', type:'bar', data:gmv, barWidth:'55%', itemStyle:{color:pp=>gradeColor(pp.value, Math.min(...gmv), Math.max(...gmv), 1), borderRadius:[3,3,0,0]}},
      {name:'同比', type:'line', data:yoy, yAxisIndex:1, symbol:'circle', symbolSize:5, lineStyle:{color:C.accent, width:2}, itemStyle:{color:C.accent}},
      {name:'环比', type:'line', data:qoq, yAxisIndex:1, symbol:'diamond', symbolSize:6, lineStyle:{color:C.accent2, width:2, type:'dashed'}, itemStyle:{color:C.accent2}}
    ]
  }, true);
  document.getElementById('capQuarterly').innerHTML = '<b>季度 GMV + 同比/环比</b>（已剔除 2016 冷启动季度与数据末尾的不完整季度）：2017Q4 为全年峰值（黑五+圣诞，环比 Q3 +43.6%）。2018 年 Q1/Q2 同比 2017 年仍有 +289% / +126% 的增长，但增速明显回落——<b>平台已从「爆发期」进入「增长放缓期」</b>，靠拉新驱动的模式正在触顶，下一程要靠提升存量客户价值（见客户维度）。';
}
function renderWeekly(){
  const w = DATA.weekly_gmv||[];
  if(!w.length) return;
  // x 轴用周一日期（周粒度按周一~周日聚合，环比为与上一个完整周比较）
  const weeks = w.map(x=>(x.monday||x.week).slice(5));  // 'MM-DD'（周一）
  const gmv = w.map(x=>+x.gmv||0);
  const wow = w.map(x=>x.wow_pct);
  // 找峰值周（黑五）
  let peakIdx = 0; gmv.forEach((v,i)=>{ if(v>gmv[peakIdx]) peakIdx=i; });
  getChart('chartWeekly').setOption({
    grid:{left:10,right:50,top:30,bottom:10,containLabel:true},
    tooltip:{trigger:'axis', formatter:ps=>{const i=ps[0].dataIndex; return (w[i].monday||w[i].week)+'（周一~周日）<br/>GMV '+fmtMoneyK(gmv[i])+'<br/>环比 '+(wow[i]==null?'-':wow[i]+'%');}},
    legend:{data:['GMV','环比'], top:0, textStyle:{color:C.ink2, fontSize:11}, icon:'circle'},
    xAxis:{type:'category', data:weeks, ...baseAxis, axisLabel:{color:C.ink2, fontSize:9, interval:Math.floor(weeks.length/10)}},
    yAxis:[{type:'value', ...baseAxis, axisLabel:{...baseAxis.axisLabel, formatter:v=>fmtMoneyK(v), fontSize:10}},
           {type:'value', ...baseAxis, axisLabel:{...baseAxis.axisLabel, formatter:'{value}%', fontSize:10}, splitLine:{show:false}}],
    series:[
      {name:'GMV', type:'bar', data:gmv, barWidth:'60%', itemStyle:{color:pp=>gradeColor(pp.value, Math.min(...gmv), Math.max(...gmv), 1), borderRadius:[3,3,0,0]},
        markPoint:{data:[{coord:[peakIdx, gmv[peakIdx]], symbolSize:46, itemStyle:{color:C.accent}, label:{formatter:'黑五', color:'#fff', fontSize:10}}]}},
      {name:'环比', type:'line', data:wow, yAxisIndex:1, symbol:'circle', symbolSize:4, lineStyle:{color:C.accent, width:1.6}, itemStyle:{color:C.accent}}
    ]
  }, true);
  const bf = w[peakIdx];
  document.getElementById('capWeekly').innerHTML =
    '<b>周 GMV + 环比</b>（周一~周日聚合，剔除冷启动残周）：全年周 GMV 在 '+fmtMoneyK(Math.min(...gmv))+'~'+fmtMoneyK(Math.max(...gmv))+
    ' 区间波动，<b>2017 年第 '+(w[peakIdx].week||'').split('-W')[1]+' 周（黑五周）冲至 '+fmtMoneyK(bf.gmv)+'、环比 +'+bf.wow_pct+'%</b>——大促是全年唯一的爆发窗口，其余时间需求高度平稳，说明平台增长靠「节点大促」而非自然复购。';
}
function renderMonthly(){
  const m = DATA.monthly_gmv||[];
  if(!m.length) return;
  const months = m.map(x=>x.month);
  const gmv = m.map(x=>+x.gmv||0);
  // 按月份字符串建立映射，精确计算同比（year-1 同月）与环比（month-1 上月），避免缺失月份导致的错位
  const byMonth = {};
  m.forEach(x=>{ const v = +x.gmv; if(v && v > 0) byMonth[x.month] = v; }); // 只存有效正值，null/0/极低值不参与基数
  const shiftMonth = (ym, dy, dm) => {
    let [y, mo] = ym.split('-').map(Number);
    y += dy; mo += dm;
    if(mo < 1){ mo += 12; y -= 1; }
    if(mo > 12){ mo -= 12; y += 1; }
    return String(y) + '-' + String(mo).padStart(2, '0');
  };
  const pct = (cur, base) => (base == null || base <= 0 || cur == null) ? null : +((cur - base) / base * 100).toFixed(1);
  const yoy = months.map(ym => pct(byMonth[ym], byMonth[shiftMonth(ym,-1,0)]));
  const mom = months.map(ym => pct(byMonth[ym], byMonth[shiftMonth(ym,0,-1)]));
  getChart('chartMonthly').setOption({
    grid:{left:10,right:10,top:34,bottom:10,containLabel:true},
    tooltip:{trigger:'axis', formatter:ps=>{const i=ps[0].dataIndex; return months[i]+'<br/>GMV '+fmtMoneyK(gmv[i])+'<br/>同比 '+(yoy[i]==null?'-':yoy[i]+'%')+'<br/>环比 '+(mom[i]==null?'-':mom[i]+'%');}},
    legend:{data:['GMV','同比','环比'], top:0, textStyle:{color:C.ink2, fontSize:11}, icon:'circle'},
    xAxis:{type:'category', data:months, ...baseAxis, axisLabel:{color:C.ink2, fontSize:10, rotate:45}},
    yAxis:[
      {type:'value', ...baseAxis, name:'GMV', nameTextStyle:{color:C.ink2, fontSize:10}, axisLabel:{...baseAxis.axisLabel, formatter:v=>fmtMoneyK(v)}},
      {type:'value', ...baseAxis, name:'%', nameTextStyle:{color:C.ink2, fontSize:10}, splitLine:{show:false}, axisLabel:{color:C.ink2, fontSize:10, formatter:'{value}%'}}
    ],
    series:[
      {name:'GMV', type:'bar', data:gmv, barWidth:'55%',
        itemStyle:{color:pp=>gradeColor(pp.value, Math.min(...gmv), Math.max(...gmv), 1), borderRadius:[3,3,0,0]}},
      {name:'同比', type:'line', data:yoy, yAxisIndex:1, symbol:'circle', symbolSize:5, lineStyle:{color:C.accent, width:2}, itemStyle:{color:C.accent}},
      {name:'环比', type:'line', data:mom, yAxisIndex:1, symbol:'diamond', symbolSize:5, lineStyle:{color:C.teal, width:2, type:'dashed'}, itemStyle:{color:C.teal}}
    ]
  }, true);
  document.getElementById('capMonthly').innerHTML = '<b>月度 GMV + 同环比</b>：柱=GMV，实线=同比（去年同月），虚线=环比（上月）。2017-11 黑五达峰值，2018 年后进入稳定期。';
}
function renderHourWeek(){
  const hr = DATA.hour||[];
  const wo = DATA.weekday_order||[];
  if(hr.length){
    getChart('chartHourWeek').setOption({
      grid:{left:10,right:10,top:10,bottom:10,containLabel:true},
      tooltip:{trigger:'axis', formatter:p=>p[0].name+'<br/>'+fmtNum(p[0].value)+' 单'},
      xAxis:{type:'category', data:hr.map(x=>x.hour_of_day+'时'), ...baseAxis, axisLabel:{color:C.ink2, fontSize:10}},
      yAxis:{type:'value', ...baseAxis},
      series:[{type:'bar', data:hr.map(x=>x.count), barWidth:'60%',
        itemStyle:{color:pp=>gradeColor(pp.value, Math.min(...hr.map(x=>x.count)), Math.max(...hr.map(x=>x.count)), 1), borderRadius:[3,3,0,0]}}]
    }, true);
  }
  const note = wo.length ? '周一下单最多，周末偏少。' : '';
  document.getElementById('capHourWeek').innerHTML = '<b>下单时段（24h）</b>：下单高峰 10–16 时与 20–21 时，凌晨 3–5 点为谷底。<b>结论</b>：推送/秒杀/直播等运营动作应卡位 10 点与 20 点两个流量峰值；巴西与中国时差 11 小时，跨境运营排班需按当地时间执行。'+note;
}

// ─── ② 商品类目维度 ───
function renderKpiCategory(){
  const tc = DATA.top_cat||[];
  const cm = DATA.category_matrix||[];
  const topCat = tc[0]||{};
  const star = cm.filter(x=>x.quadrant==='明星').length;
  const prob = cm.filter(x=>x.quadrant==='问题').length;
  setKpi('kpiCategory', [
    kpiCard('TOP1 类目', catName(topCat.product_category_name_english||topCat.category||'-'), '', '收入 R$'+fmtMoneyK(topCat.revenue||topCat.gmv||0)),
    kpiCard('明星类目', star, '个', '高收入+高评分'),
    kpiCard('问题类目', prob, '个', '高收入+低评分，需治理'),
    kpiCard('类目总数', cm.length, '个', '订单≥100 的类目'),
  ]);
}
function renderCatTop(){
  const tc = DATA.top_cat||[];
  if(!tc.length) return;
  const names = tc.map(x=>catName(x.product_category_name_english||x.category));
  const vals = tc.map(x=>+x.revenue||+x.gmv||0);
  getChart('chartCatTop').setOption({
    grid:{left:10,right:60,top:10,bottom:10,containLabel:true},
    tooltip:{trigger:'axis', formatter:p=>p[0].name+'<br/>收入 '+fmtMoneyK(p[0].value)},
    xAxis:{type:'value', ...baseAxis, axisLabel:{...baseAxis.axisLabel, formatter:v=>fmtMoneyK(v)}},
    yAxis:{type:'category', data:names.reverse(), ...baseAxis, axisLabel:{color:C.ink, fontSize:11}},
    series:[{type:'bar', data:vals.reverse(), barWidth:'60%',
      itemStyle:{color:pp=>gradeColor(pp.value, Math.min(...vals), Math.max(...vals), 1), borderRadius:[0,3,3,0]},
      label:{show:true, position:'right', color:C.ink2, fontSize:10, formatter:p=>fmtMoneyK(p.value)}}]
  }, true);
  document.getElementById('capCatTop').innerHTML = '<b>类目收入 TOP10</b>：床浴餐桌（家居）为第一大品类，其次健康美容、运动休闲。';
}
function renderPareto(){
  const p = DATA.pareto||[];
  if(!p.length) return;
  const cats = p.map(x=>catName(x.product_category_name_english));
  const rev = p.map(x=>+x.revenue.toFixed(0));
  const cumPct = p.map(x=>+(x.cum_pct*100).toFixed(1));
  getChart('chartPareto').setOption({
    grid:{left:10,right:60,top:30,bottom:60,containLabel:true},
    dataZoom:[{type:'inside', xAxisIndex:0, start:0, end:40}, {type:'slider', xAxisIndex:0, bottom:8, height:16, borderColor:C.lineStrong, fillerColor:'rgba(228,87,46,0.12)', handleStyle:{color:C.accent}, textStyle:{color:C.ink3, fontSize:10}}],
    tooltip:{trigger:'axis', formatter:ps=>{const i=ps[0].dataIndex; return cats[i]+'<br/>成交额 R$'+(rev[i]/1e3).toFixed(0)+'K<br/>累计占比 '+cumPct[i]+'%';}},
    xAxis:{type:'category', data:cats, ...baseAxis, axisLabel:{color:C.ink2, fontSize:10, rotate:45, interval:'auto'}},
    yAxis:[{type:'value', name:'成交额', ...baseAxis, axisLabel:{...baseAxis.axisLabel, formatter:v=>'R$'+(v/1e3).toFixed(0)+'K'}},
           {type:'value', name:'累计占比', min:0, max:100, ...baseAxis, axisLabel:{...baseAxis.axisLabel, formatter:'{value}%'}, splitLine:{show:false}}],
    series:[{type:'bar', data:rev, barWidth:'60%', itemStyle:{color:pp=>gradeColor(pp.value, Math.min(...rev), Math.max(...rev), 1)}, yAxisIndex:0},
            {type:'line', data:cumPct, yAxisIndex:1, smooth:true, symbol:'none', lineStyle:{color:C.accent, width:2.5},
             areaStyle:{color:'rgba(228,87,46,0.06)'},
             markLine:{silent:true, symbol:'none', lineStyle:{color:C.accent, type:'dashed', opacity:0.5}, label:{formatter:'80%', position:'end', color:C.accent, fontSize:11}, data:[{yAxis:80}]}}]
  }, true);
  const n80 = p.findIndex(x=>x.cum_pct>=0.8)+1;
  document.getElementById('capPareto').innerHTML = '<b>帕累托 / ABC</b>：全量 '+p.length+' 类目中，仅 <b>'+n80+' 个（约'+(n80/p.length*100).toFixed(0)+'%）A 类类目就贡献 80% 销售额</b>——典型的头部集中市场。<b>结论</b>：选品/招商/流量资源应聚焦 A 类；长尾类目按 B/C 类分级，C 类只做货架不做投入。';
}
function renderMatrix(){
  const cm = DATA.category_matrix||[];
  if(!cm.length) return;
  const quadColor = {'明星':'#2b6cb0','问题':'#e4572e','潜力':'#3a9188','淘汰':'#b9b5ac'};
  const revVals = cm.map(x=>x.revenue), scoreVals = cm.map(x=>x.avg_score);
  const revMed = revVals.slice().sort((a,b)=>a-b)[Math.floor(revVals.length/2)];
  const scoreMed = scoreVals.slice().sort((a,b)=>a-b)[Math.floor(scoreVals.length/2)];
  const scatterData = cm.map(x=>({value:[x.revenue, x.avg_score], name:catName(x.product_category_name_english),
    itemStyle:{color:quadColor[x.quadrant]||'#b9b5ac'}}));
  getChart('chartMatrix').setOption({
    grid:{left:10,right:10,top:10,bottom:30,containLabel:true},
    tooltip:{trigger:'item', formatter:p=>p.name+'<br/>收入 R$'+fmtNum(Math.round(p.value[0]))+'<br/>评分 '+p.value[1].toFixed(2)},
    xAxis:{type:'value', name:'收入', ...baseAxis, axisLabel:{...baseAxis.axisLabel, formatter:v=>fmtMoneyK(v)}},
    yAxis:{type:'value', name:'评分', min:3, max:5, ...baseAxis},
    legend:{data:['明星','问题','潜力','淘汰'], bottom:0, textStyle:{color:C.ink2, fontSize:11}, icon:'circle'},
    series:[{
      type:'scatter', data:scatterData, symbolSize:12,
      markLine:{silent:true, symbol:'none', label:{show:false},
        lineStyle:{color:C.lineStrong, type:'dashed'},
        data:[{xAxis:revMed},{yAxis:scoreMed}]}
    }]
  }, true);
  const quadCnt = {};
  cm.forEach(x=>quadCnt[x.quadrant]=(quadCnt[x.quadrant]||0)+1);
  document.getElementById('capMatrix').innerHTML = '<b>品类组合矩阵</b>：横轴收入、纵轴评分，虚线为各自中位数。明星 '+ (quadCnt['明星']||0)+' / 问题 '+(quadCnt['问题']||0)+' / 潜力 '+(quadCnt['潜力']||0)+' / 淘汰 '+(quadCnt['淘汰']||0)+' 个类目。';
  const prob = cm.filter(x=>x.quadrant==='问题').map(x=>catName(x.product_category_name_english)).join('、');
  document.getElementById('insightMatrix').innerHTML = '<b>洞察</b>：'+(prob?'问题品类（高收入低评分）：「'+prob+'」——口碑治理优先级最高。':'暂无问题品类。')+' 收入中位数约 '+fmtMoneyK(revMed)+'，评分中位数 '+scoreMed.toFixed(2)+'。';
}
function renderCatBestWorst(){
  const rc = DATA.rating_category||[];
  if(!rc.length) return;
  const sorted = rc.filter(x=>x.review_cnt>=100).sort((a,b)=>b.avg_score-a.avg_score);
  const best = sorted.slice(0,8);
  const worst = sorted.slice(-8).reverse();
  const names = best.map(x=>catName(x.category)).concat(['——']).concat(worst.map(x=>catName(x.category)));
  const scores = best.map(x=>+x.avg_score.toFixed(2)).concat([null]).concat(worst.map(x=>+x.avg_score.toFixed(2)));
  getChart('chartCatBestWorst').setOption({
    grid:{left:10,right:50,top:10,bottom:60,containLabel:true},
    tooltip:{trigger:'axis', formatter:p=>p[0].name+(p[0].value==null?'':('<br/>均分 '+p[0].value.toFixed(2)))},
    xAxis:{type:'category', data:names, ...baseAxis, axisLabel:{color:C.ink2, fontSize:10, rotate:35, interval:0}},
    yAxis:{type:'value', min:2, max:5, ...baseAxis},
    series:[{type:'bar', data:scores, barWidth:'55%',
      itemStyle:{color:p=>p.value==null?'transparent':gradeColor(p.value, 2.5, 5, 2), borderRadius:[3,3,0,0]},
      label:{show:true, position:'top', color:C.ink2, fontSize:10, formatter:p=>p.value==null?'':p.value.toFixed(2)}}]
  }, true);
  document.getElementById('capCatBestWorst').innerHTML = '<b>评分类目两极</b>：左侧=最高评分 TOP8，右侧=最低评分 TOP8（评论≥100）。右侧服装/安防类目口碑最差。';
}
function renderInstall(){
  const inst = DATA.payment_installments||[];
  if(!inst.length) return;
  const instData = inst.filter(x=>x.payment_installments!=null && x.payment_installments>=1 && x.payment_installments<=12);
  getChart('chartInstall').setOption({
    grid:{left:10,right:10,top:10,bottom:10,containLabel:true},
    tooltip:{trigger:'axis', formatter:p=>p[0].name+' 期<br/>客单价 R$'+p[0].value.toFixed(0)},
    xAxis:{type:'category', data:instData.map(x=>x.payment_installments+'期'), ...baseAxis, axisLabel:{color:C.ink2, fontSize:11}},
    yAxis:{type:'value', ...baseAxis, axisLabel:{...baseAxis.axisLabel, formatter:'R$'+'{value}'}},
    series:[{type:'line', data:instData.map(x=>x.avg_order_value), smooth:true, symbol:'circle', symbolSize:7,
      lineStyle:{color:C.accent2, width:3}, itemStyle:{color:C.accent2}, areaStyle:{color:'rgba(43,108,176,0.08)'}}]
  }, true);
  document.getElementById('capInstall').innerHTML = '<b>分期数 vs 客单价</b>：分期越多客单价越高（约 R$117 → R$400+ 单调递增），分期是拉高 AOV 的有效工具。';
}

function renderBasket(){
  const mb = DATA.market_basket||[];
  if(!mb.length){
    document.getElementById('capBasket').innerHTML = '<b>购物篮关联分析</b>（FP-Growth）：尚未生成——需先在虚拟机运行 analysis_12_market_basket.ipynb 写入 ads_market_basket。';
    return;
  }
  // 只取 lift>1 的真关联规则，按 lift 降序 TOP 12
  const rules = mb.filter(r=>+r.lift>1).slice(0,12);
  if(!rules.length){
    document.getElementById('capBasket').innerHTML = '<b>购物篮关联分析</b>：当前无 lift>1 的规则。';
    return;
  }
  const labels = rules.map(r=>catName(r.antecedent)+' → '+catName(r.consequent));
  const lifts = rules.map(r=>+r.lift);
  const confs = rules.map(r=>+(r.confidence*100).toFixed(1));
  getChart('chartBasket').setOption({
    grid:{left:10,right:80,top:10,bottom:10,containLabel:true},
    tooltip:{trigger:'axis', axisPointer:{type:'shadow'}, formatter:p=>{const i=p[0].dataIndex; return '<b>'+labels[i]+'</b><br/>提升度 '+lifts[i].toFixed(2)+'（>1 为真关联）<br/>置信度 '+confs[i]+'%<br/>支持度 '+rules[i].support;}},
    xAxis:{type:'value', ...baseAxis, name:'提升度 lift', nameTextStyle:{color:C.ink2, fontSize:11}},
    yAxis:{type:'category', data:labels.slice().reverse(), ...baseAxis, axisLabel:{color:C.ink, fontSize:11, width:110, overflow:'truncate'}},
    series:[{type:'bar', data:lifts.slice().reverse(), barWidth:'60%',
      label:{show:true, position:'right', color:C.ink, fontSize:11, formatter:p=>p.value.toFixed(2)},
      itemStyle:{color:p=>gradeColor(p.value, 1, Math.max(...lifts), 1), borderRadius:[0,3,3,0]}}]
  }, true);
  document.getElementById('capBasket').innerHTML = '<b>购物篮关联分析</b>（FP-Growth，品类粒度）：横条=提升度 lift，<b>lift>1 才是真关联</b>（买了前者会显著提升购买后者的概率）。TOP 规则可直接用于捆绑销售、交叉推荐、凑单设计。';
}

// ─── ③ 卖家维度 ───
function renderKpiSeller(){
  const sc = DATA.seller_concentration&&DATA.seller_concentration[0]||{};
  const ss = DATA.seller_score||[];
  setKpi('kpiSeller', [
    kpiCard('卖家总数', fmtNum(sc.total_sellers||0), '个', ''),
    kpiCard('TOP10% 卖家订单占比', ((sc.top10_order_share||0)*100).toFixed(1), '%', '头部集中度'),
    kpiCard('活跃卖家', fmtNum(ss.length), '个', '订单≥10'),
    kpiCard('劣质卖家', fmtNum((DATA.seller_bad||[]).length), '个', '高流量低质量'),
  ]);
}
function renderSeller(){
  const sc = DATA.seller_concentration&&DATA.seller_concentration[0];
  const ss = (DATA.seller_score||[]).filter(s=>s.quality_score!==undefined);
  // ─── 帕累托：按订单量降序的累计集中度（覆盖 94K+ 单）───
  if(ss.length && sc){
    const sorted = ss.slice().sort((a,b)=>b.order_cnt-a.order_cnt);
    const totalOrders = sorted.reduce((s,x)=>s+x.order_cnt,0);
    // 聚合成 60 个百分位桶，画累计占比曲线
    const cum = [];
    let acc = 0;
    sorted.forEach(x=>{ acc += x.order_cnt; cum.push(acc/totalOrders*100); });
    const buckets = 60;
    const pts = [];
    for(let i=0;i<buckets;i++){
      const idx = Math.min(cum.length-1, Math.floor((i+1)/buckets*cum.length)-1);
      pts.push([+( (i+1)/buckets*100 ).toFixed(2), +cum[idx].toFixed(1)]);
    }
    // 关键统计：多少卖家占 80% 订单
    const idx80 = cum.findIndex(v=>v>=80);
    const sellerPct80 = idx80>=0 ? ((idx80+1)/cum.length*100).toFixed(1) : null;
    const top10pctOrders = cum[Math.floor(cum.length*0.1)-1];
    getChart('chartSellerConc').setOption({
      grid:{left:10,right:20,top:34,bottom:10,containLabel:true},
      tooltip:{trigger:'axis', formatter:p=>{const x=p[0].value[0]; return '头部 '+x.toFixed(1)+'% 的卖家<br/>累计贡献 '+p[0].value[1]+'% 订单';}},
      xAxis:{type:'value', min:0, max:100, ...baseAxis, name:'卖家累计占比（按订单量降序）', nameLocation:'middle', nameGap:28, nameTextStyle:{color:C.ink2, fontSize:11}, axisLabel:{...baseAxis.axisLabel, formatter:'{value}%'}},
      yAxis:{type:'value', min:0, max:100, ...baseAxis, axisLabel:{...baseAxis.axisLabel, formatter:'{value}%'}},
      series:[{type:'line', data:pts, symbol:'none', smooth:true, lineStyle:{color:C.accent, width:2.5},
        areaStyle:{color:new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:'rgba(228,87,46,0.25)'},{offset:1,color:'rgba(228,87,46,0.02)'}])},
        markLine:{silent:true, symbol:'none', lineStyle:{color:C.ink3, type:'dashed'},
          data:[{yAxis:80, label:{formatter:'80% 订单', color:C.ink2}}, {xAxis:10, label:{formatter:'10% 卖家', color:C.ink2}}]},
        markPoint:{data:[{coord:[10,+top10pctOrders.toFixed(1)], symbolSize:52, itemStyle:{color:C.accent},
          label:{formatter:top10pctOrders.toFixed(0)+'%', color:'#fff', fontSize:12, fontWeight:700}}]}}]
    }, true);
    document.getElementById('capSellerConc').innerHTML =
      '<b>卖家帕累托</b>（活跃卖家口径，订单≥10）：'+sellerPct80+'% 的卖家（约 '+fmtNum(Math.round(cum.length*(+sellerPct80)/100))+' 个）贡献 80% 订单'+
      '。TOP 10% 活跃卖家占 <b>'+(+top10pctOrders).toFixed(1)+'%</b> 订单（若计入全部 '+fmtNum(sc.total_sellers)+' 个注册卖家的长尾，TOP 10% 占比达 '+(sc.top10_order_share*100).toFixed(1)+'%）。运营含义：<b>留住 1 个头部卖家 ≈ 留住几十个尾部卖家</b>，卖家关系管理向头部倾斜，但也要防「头部出走」的单点风险。';
    document.getElementById('insightSeller').innerHTML =
      '<b>结论</b>：'+fmtNum(sc.total_sellers)+' 个卖家中，TOP 10% 贡献 '+(sc.top10_order_share*100).toFixed(1)+'% 订单、TOP 20% 贡献 '+(sc.top20_order_share*100).toFixed(1)+
      '%——长尾卖家数量庞大但单产极低。策略上「保头部、提腰部、清尾部」：对头部做专属服务与库存保障，对劣质卖家（见下）限期整改或清退。';
  }
  // ─── 头部卖家特征：TOP 10%（按订单量）vs 其余，指数化对比（其余=100）───
  if(ss.length){
    const sorted = ss.slice().sort((a,b)=>b.order_cnt-a.order_cnt);
    const cut = Math.max(10, Math.floor(sorted.length*0.1));
    const top = sorted.slice(0, cut), rest = sorted.slice(cut);
    const mean = (arr,k)=>arr.reduce((s,x)=>s+(+x[k]||0),0)/arr.length;
    // 指标：[名称, 头部均值, 其余均值, 显示格式]
    const M = [
      {name:'平均订单量', h:mean(top,'order_cnt'), r:mean(rest,'order_cnt'), fmt:v=>v.toFixed(0)},
      {name:'准时率(%)', h:mean(top,'on_time_rate')*100, r:mean(rest,'on_time_rate')*100, fmt:v=>v.toFixed(1)+'%'},
      {name:'取消率(%)', h:mean(top,'cancel_rate')*100, r:mean(rest,'cancel_rate')*100, fmt:v=>v.toFixed(2)+'%'},
      {name:'平均评分', h:mean(top,'avg_score'), r:mean(rest,'avg_score'), fmt:v=>v.toFixed(2)},
    ];
    const idx = M.map(m=>+(m.h/Math.max(1e-9,m.r)*100).toFixed(0));
    getChart('chartSellerTrait').setOption({
      grid:{left:10,right:70,top:16,bottom:10,containLabel:true},
      tooltip:{trigger:'axis', formatter:p=>{const m=M[p[0].dataIndex]; return m.name+'<br/>头部 10%：'+m.fmt(m.h)+'<br/>其余卖家：'+m.fmt(m.r)+'<br/>指数：'+idx[p[0].dataIndex];}},
      xAxis:{type:'value', ...baseAxis, name:'指数（其余卖家=100）', nameTextStyle:{color:C.ink2, fontSize:11}, axisLabel:{...baseAxis.axisLabel, formatter:'{value}'}},
      yAxis:{type:'category', data:M.map(m=>m.name), ...baseAxis, axisLabel:{color:C.ink, fontSize:12}},
      series:[{type:'bar', data:idx, barWidth:'55%',
        markLine:{silent:true, symbol:'none', lineStyle:{color:C.ink3, type:'dashed'}, data:[{xAxis:100, label:{formatter:'基准=100', color:C.ink2}}]},
        label:{show:true, position:'right', color:C.ink, fontSize:12, fontWeight:700, formatter:p=>p.value},
        itemStyle:{color:p=>p.value>=100?C.accent:C.accent2, borderRadius:[0,3,3,0]}}]
    }, true);
    const ts = (DATA.top_seller||[]);
    const spTop = ts.filter(x=>x.seller_state==='SP').length;
    // 完全动态的诚实结论：只在差异显著（>1pp / >0.05分）时才下判断
    const otDiff = M[1].h - M[1].r, ccDiff = M[2].h - M[2].r, scDiff = M[3].h - M[3].r;
    const ratio = M[0].h/Math.max(1e-9,M[0].r);
    let qualityTxt;
    if(Math.abs(otDiff) < 1 && Math.abs(ccDiff) < 0.5 && Math.abs(scDiff) < 0.05){
      qualityTxt = '但服务质量（准时率 '+M[1].fmt(M[1].h)+' vs '+M[1].fmt(M[1].r)+'、取消率、评分）与长尾<b>几乎无差异</b>——这说明头部的规模优势来自<b>选品、价格与流量曝光</b>，而非服务更好；反过来讲：<b>服务达标只是入场券，做不出差异化服务壁垒</b>，平台的卖家扶持应聚焦流量与供应链，而非服务培训。';
    } else {
      qualityTxt = '且服务质量显著更优（准时率 '+(otDiff>=0?'高':'低')+' '+Math.abs(otDiff).toFixed(1)+'pp、取消率 '+(ccDiff<=0?'低':'高')+' '+Math.abs(ccDiff).toFixed(2)+'pp、评分 '+(scDiff>=0?'+':'')+scDiff.toFixed(2)+'）——<b>服务好的卖家才长得大</b>，扶持应包括服务能力建设。';
    }
    document.getElementById('capSellerTrait').innerHTML =
      '<b>头部卖家画像</b>（横条=头部相对其余的指数，基准 100）：头部 10% 卖家平均单产是其余的 <b>'+ratio.toFixed(1)+' 倍</b>，'+qualityTxt+
      ' 收入 TOP10 卖家'+(ts.length?('中 '+spTop+' 个在 SP 州，'):'')+'圣保罗既是需求中心也是供给中心。';
  }
  if(ss.length){
    const bins = new Array(10).fill(0);
    ss.forEach(s=>{ const q = Math.min(9, Math.max(0, Math.floor(s.quality_score*10))); bins[q]++; });
    const binLabels = ['0-10','10-20','20-30','30-40','40-50','50-60','60-70','70-80','80-90','90-100'];
    getChart('chartSellerScore').setOption({
      grid:{left:10,right:10,top:10,bottom:10,containLabel:true},
      tooltip:{trigger:'axis', formatter:p=>p[0].name+' 分：'+fmtNum(p[0].value)+' 个卖家'},
      xAxis:{type:'category', data:binLabels, ...baseAxis, axisLabel:{color:C.ink2, fontSize:10, rotate:30}},
      yAxis:{type:'value', ...baseAxis},
      series:[{type:'bar', data:bins, barWidth:'65%', itemStyle:{color:pp=>gradeColor(pp.dataIndex, 0, 9, 2), borderRadius:[3,3,0,0]}}]
    }, true);
    document.getElementById('capSellerScore').innerHTML = '<b>卖家质量分分布</b>（0.4×准时率+0.4×评分+0.2×1-取消率）：<b>结论</b>：质量分整体右偏，多数卖家集中在 70-90 区间，说明平台基本盘的服务质量尚可；但左尾长尾（<60 分）正是劣质卖家的来源，治理不必全量铺开，<b>盯住左尾 10% 即可覆盖大部分差评来源</b>。';
  }
  const sb = DATA.seller_bad||[];
  if(sb.length){
    const badNames = sb.slice(0,15).map(s=>s.seller_id.length>16?s.seller_id.slice(0,16)+'…':s.seller_id);
    const badScores = sb.slice(0,15).map(s=>+(s.quality_score*100).toFixed(1));
    getChart('chartSellerBad').setOption({
      grid:{left:10,right:10,top:10,bottom:10,containLabel:true},
      tooltip:{trigger:'axis', formatter:p=>badNames[p[0].dataIndex]+'<br/>质量分 '+p[0].value+'（满分100）'},
      xAxis:{type:'category', data:badNames, ...baseAxis, axisLabel:{color:C.ink2, fontSize:9, rotate:45, interval:0}},
      yAxis:{type:'value', min:0, max:70, ...baseAxis, axisLabel:{...baseAxis.axisLabel, formatter:'{value}'}},
      series:[{type:'bar', data:badScores, barWidth:'55%', itemStyle:{color:pp=>gradeColor(pp.value, 40, 70, 0), borderRadius:[3,3,0,0]}}]
    }, true);
    document.getElementById('capSellerBad').innerHTML = '<b>劣质卖家识别</b>：'+sb.length+' 个「高流量低质量」卖家（质量分<80 且订单>50）。<b>结论</b>：这些卖家订单量大、体验差，是<b>性价比最高的治理对象</b>——每个都同时伤害大量客户；建议限期整改（准时率/评分双达标），未达标者清退并转让流量给同品质卖家。';
  }
  const cs = DATA.seller_cross_state||[];
  if(cs.length){
    const sameState = cs.find(x=>x.is_cross_state===0);
    const crossState = cs.find(x=>x.is_cross_state===1);
    const crossDelay = sameState && crossState ? crossState.avg_delay_days - sameState.avg_delay_days : 0;
    getChart('chartSellerCross').setOption({
      grid:{left:10,right:10,top:10,bottom:10,containLabel:true},
      tooltip:{trigger:'axis', formatter:p=>p[0].name+'<br/>平均延误 '+p[0].value+' 天'},
      xAxis:{type:'category', data:['同州发货','跨州发货'], ...baseAxis, axisLabel:{color:C.ink, fontSize:13}},
      yAxis:{type:'value', ...baseAxis, name:'平均延误天数', nameTextStyle:{color:C.ink2}},
      series:[{type:'bar', data:[sameState?sameState.avg_delay_days:0, crossState?crossState.avg_delay_days:0], barWidth:'45%',
        itemStyle:{color:pp=>gradeColor(pp.value, 0, Math.max(crossState?crossState.avg_delay_days:1,1), 0), borderRadius:[4,4,0,0]},
        label:{show:true, position:'top', color:C.ink, fontSize:13, formatter:p=>p.value.toFixed(2)+' 天'}}]
    }, true);
    document.getElementById('capSellerCross').innerHTML = '<b>跨区域发货惩罚</b>：跨州发货平均延误比同州多 <b>'+crossDelay.toFixed(2)+'</b> 天。<b>结论</b>：鼓励卖家「就近发货」或建设区域仓，每缩短一段运输距离都能直接转化为准时率与好评。';
  }
}

// ─── ④ 地区维度 ───
function renderKpiRegion(){
  const ts = DATA.top_state||[];
  const sa = DATA.state_aov||[];
  const topState = ts[0]||{};
  const maxAov = sa.reduce((m,x)=>(+x.avg_order_value)>(+m.avg_order_value)?x:m, sa[0]||{avg_order_value:0, customer_state:'-'});
  setKpi('kpiRegion', [
    kpiCard('TOP1 州', stateName(topState.customer_state), '', fmtNum(topState.order_cnt||0)+' 单'),
    kpiCard('最高客单价州', stateName(maxAov.customer_state), '', 'R$'+(+maxAov.avg_order_value||0).toFixed(0)),
    kpiCard('州数量', sa.length||27, '个', '订单≥100'),
    kpiCard('SP 州占比', '≈40%', '', '圣保罗一州独大'),
  ]);
}
function renderRegion(){
  const ts = DATA.top_state||[];
  if(ts.length){
    const names = ts.map(x=>stateName(x.customer_state));
    const vals = ts.map(x=>+x.order_cnt||0);
    getChart('chartStateTop').setOption({
      grid:{left:10,right:50,top:10,bottom:10,containLabel:true},
      tooltip:{trigger:'axis', formatter:p=>p[0].name+'<br/>'+fmtNum(p[0].value)+' 单'},
      xAxis:{type:'value', ...baseAxis},
      yAxis:{type:'category', data:names.reverse(), ...baseAxis, axisLabel:{color:C.ink, fontSize:12}},
      series:[{type:'bar', data:vals.reverse(), barWidth:'60%',
        itemStyle:{color:pp=>gradeColor(pp.value, Math.min(...vals), Math.max(...vals), 1), borderRadius:[0,3,3,0]},
        label:{show:true, position:'right', color:C.ink2, fontSize:10, formatter:p=>fmtNum(p.value)}}]
    }, true);
    document.getElementById('capStateTop').innerHTML = '<b>州订单量 TOP10</b>：SP（圣保罗）一州约占 40% 订单，前 4 州（SP/RJ/MG/RS）合计近 7 成。<b>结论</b>：市场高度集中于东南部经济带，<b>仓储、营销、自营配送等重资源投入应按此排序</b>；北部州订单稀薄，用轻模式（第三方物流）覆盖即可。';
  }
  const sa = DATA.state_aov||[];
  if(sa.length){
    const topStates = sa.slice(0,15).sort((a,b)=>a.avg_order_value-b.avg_order_value);
    getChart('chartStateAov').setOption({
      grid:{left:10,right:30,top:10,bottom:10,containLabel:true},
      tooltip:{trigger:'axis', formatter:p=>p[0].name+'<br/>客单价 R$'+p[0].value.toFixed(0)},
      xAxis:{type:'value', ...baseAxis, axisLabel:{...baseAxis.axisLabel, formatter:'R$'+'{value}'}},
      yAxis:{type:'category', data:topStates.map(x=>stateName(x.customer_state)), ...baseAxis, axisLabel:{color:C.ink2, fontSize:12}},
      series:[{type:'bar', data:topStates.map(x=>x.avg_order_value), barWidth:'60%',
        itemStyle:{color:pp=>gradeColor(pp.value, Math.min(...topStates.map(x=>x.avg_order_value)), Math.max(...topStates.map(x=>x.avg_order_value)), 1), borderRadius:[0,3,3,0]},
        label:{show:true, position:'right', color:C.ink2, fontSize:11, formatter:p=>'R$'+p.value.toFixed(0)}}]
    }, true);
    document.getElementById('capStateAov').innerHTML = '<b>各州客单价 TOP15</b>：<b>结论</b>：客单价高的多为北部/偏远小州（PB/AL/PI 等）——本地供给匮乏，客户只能在网上买「大件/刚需」，客单被动抬高；而非消费力强。<b>不要把高 AOV 小州当成高价值市场</b>，真正的价值市场要看「AOV × 订单量」，东南部仍是主战场。';
  }
  const ds = DATA.delivery_state||[];
  if(ds.length){
    const states = ds.map(x=>stateName(x.customer_state||x.state));
    const ontime = ds.map(x=>+(x.on_time_rate*100).toFixed(1));
    getChart('chartStateOntime').setOption({
      grid:{left:10,right:50,top:10,bottom:10,containLabel:true},
      tooltip:{trigger:'axis', formatter:p=>p[0].name+'<br/>准时率 '+p[0].value+'%'},
      xAxis:{type:'value', min:70, max:100, ...baseAxis, axisLabel:{...baseAxis.axisLabel, formatter:'{value}%'}},
      yAxis:{type:'category', data:states.reverse(), ...baseAxis, axisLabel:{color:C.ink2, fontSize:10}},
      series:[{type:'bar', data:ontime.reverse(), barWidth:'60%',
        itemStyle:{color:pp=>gradeColor(pp.value, 70, 100, 2), borderRadius:[0,3,3,0]},
        label:{show:true, position:'right', color:C.ink2, fontSize:10, formatter:p=>p.value+'%'}}]
    }, true);
    document.getElementById('capStateOntime').innerHTML = '<b>各州准时率</b>：<b>结论</b>：准时率与距离负相关——圣保罗等东南州接近满绿，北部偏远州（AM/RR/AP 等）明显偏低。这不是运力烂，而是<b>「预计送达日期」对远州过于乐观</b>；远州应按实际时效重设承诺日期，否则延误和差评会持续集中在这些州。';
  }
  const cst = DATA.category_state||[];
  if(cst.length){
    const catStateTop = cst.slice(0,15).sort((a,b)=>a.revenue-b.revenue);
    getChart('chartCatState').setOption({
      grid:{left:10,right:30,top:10,bottom:10,containLabel:true},
      tooltip:{trigger:'axis', formatter:p=>p[0].name+'<br/>主导品类 '+catName(catStateTop[p[0].dataIndex].top_category)+'<br/>收入 '+fmtMoneyK(p[0].value)},
      xAxis:{type:'value', ...baseAxis, axisLabel:{...baseAxis.axisLabel, formatter:v=>fmtMoneyK(v)}},
      yAxis:{type:'category', data:catStateTop.map(x=>stateName(x.customer_state)), ...baseAxis, axisLabel:{color:C.ink2, fontSize:11}},
      series:[{type:'bar', data:catStateTop.map(x=>x.revenue), barWidth:'60%',
        itemStyle:{color:pp=>gradeColor(pp.value, Math.min(...catStateTop.map(x=>x.revenue)), Math.max(...catStateTop.map(x=>x.revenue)), 1), borderRadius:[0,3,3,0]}}]
    }, true);
    document.getElementById('capCatState').innerHTML = '<b>各州主导品类（收入 TOP1）</b>：<b>结论</b>：床浴餐桌等家居刚需在绝大多数州居首——需求高度同质，说明<b>全国统一的爆款选品策略是可行的</b>，无需为每个州定制商品结构；区域差异更多体现在物流而非偏好。';
  }
}

// ─── ⑤ 客户维度 ───
function renderKpiCustomer(){
  const rfm = DATA.rfm||[];
  const total = rfm.reduce((s,r)=>s+r.customer_cnt,0);
  const lc = DATA.rfm_lifecycle||[];
  const clv = lc[0]||{};
  const topSeg = rfm.slice().sort((a,b)=>b.revenue_pct-a.revenue_pct)[0]||{};
  setKpi('kpiCustomer', [
    kpiCard('客户总数', fmtNum(total), '人', 'customer_unique_id 口径'),
    kpiCard('复购率', '3.0%', '', '97% 客户只买 1 次'),
    kpiCard('最大人群', topSeg.rfm_segment||'-', '', '收入占比 '+(topSeg.revenue_pct||0)+'%'),
    kpiCard('平均 CLV', 'R$'+(+clv.avg_clv||0).toFixed(0), '', '生命周期价值'),
  ]);
}
function renderRfm(){
  const rfm = DATA.rfm;
  if(!rfm.length) return;
  const isNew = rfm[0].strategy !== undefined;
  if(isNew){
    const seg = rfm.slice().sort((a,b)=>b.total_monetary-a.total_monetary);
    const names = seg.map(r=>r.rfm_segment);
    const custPct = seg.map(r=>+r.customer_pct);
    const revPct = seg.map(r=>+r.revenue_pct);
    getChart('chartRfm').setOption({
      grid:{left:10,right:60,top:10,bottom:10,containLabel:true},
      tooltip:{trigger:'axis', formatter:ps=>{
        const name = ps[0].name; const raw = seg.find(r=>r.rfm_segment===name);
        return raw?name+'<br/>客户占比 '+raw.customer_pct+'%<br/>收入占比 '+raw.revenue_pct+'%<br/>人均消费 R$'+raw.avg_monetary.toFixed(0)+'<br/>平均 R '+raw.avg_recency.toFixed(0)+' 天':name;
      }},
      legend:{top:0, textStyle:{color:C.ink2, fontSize:12}},
      xAxis:{type:'value', ...baseAxis, axisLabel:{...baseAxis.axisLabel, formatter:'{value}%'}},
      yAxis:{type:'category', data:names.slice().reverse(), ...baseAxis, axisLabel:{color:C.ink, fontSize:12}},
      series:[
        {name:'客户占比', type:'bar', data:custPct.slice().reverse(), barWidth:14, itemStyle:{color:C.accent2, borderRadius:[0,3,3,0]}},
        {name:'收入占比', type:'bar', data:revPct.slice().reverse(), barWidth:14, itemStyle:{color:C.accent, borderRadius:[0,3,3,0]}}
      ]
    }, true);
    document.getElementById('capRfm').innerHTML = '<b>人群 × 价值矩阵</b>：蓝=客户占比，橙=收入占比。按 K-Means 聚类后按簇真实画像命名（方案二：让数据说话）。';
    const stratRows = seg.map(r=>{
      const color = r.rfm_segment==='核心高价值'?'#2b6cb0':r.rfm_segment==='高价值老客'?C.accent:'#3a9188';
      return '<tr><td style="color:'+color+';font-weight:600">'+r.rfm_segment+'</td>'+
        '<td>'+r.customer_cnt.toLocaleString()+' 人（'+r.customer_pct+'%）</td>'+
        '<td>R$'+r.avg_monetary.toFixed(0)+'</td>'+
        '<td>'+r.strategy+'</td></tr>';
    }).join('');
    document.getElementById('strategyBox').innerHTML =
      '<div class="caption" style="padding:14px 18px"><b>可运营人群策略</b></div>'+
      '<table style="width:100%;border-collapse:collapse;font-size:13px">'+
      '<tr style="color:#9a9a9a;font-size:12px"><th style="text-align:left;padding:8px 18px">人群</th><th style="text-align:left;padding:8px">规模</th><th style="text-align:left;padding:8px">人均消费</th><th style="text-align:left;padding:8px 18px 8px 8px">运营策略</th></tr>'+
      stratRows+'</table>';
    document.getElementById('strategyBox').style.display='block';
  } else {
    const total = rfm.reduce((s,r)=>s+r.customer_cnt,0);
    getChart('chartRfm').setOption({
      tooltip:{trigger:'item', formatter:p=>{const raw=rfm.find(x=>x.rfm_segment===p.name); return p.name+'<br/>客户 '+fmtNum(p.value)+' 人（'+p.percent+'%）<br/>总消费 '+fmtMoneyK(raw.total_monetary)+'<br/>人均 '+raw.avg_monetary.toFixed(0)+' 雷亚尔';}},
      legend:{bottom:0, textStyle:{color:C.ink2, fontSize:12}, icon:'circle'},
      series:[{type:'pie', radius:['45%','70%'], center:['50%','45%'], avoidLabelOverlap:true,
        label:{show:true, formatter:'{b}\\n{d}%', color:C.ink, fontSize:12, lineHeight:18},
        labelLine:{lineStyle:{color:C.lineStrong}}, itemStyle:{borderColor:'#fff', borderWidth:2},
        data:rfm.map(r=>({name:r.rfm_segment, value:r.customer_cnt, itemStyle:{color:gradeColor(r.avg_monetary, 50, 300, 2)}}))}]
    }, true);
    document.getElementById('capRfm').innerHTML = '<b>客户分层</b>：共 '+fmtNum(total)+' 位客户。 需重跑 analysis_03_rfm.ipynb 启用可运营人群矩阵。';
    document.getElementById('strategyBox').style.display='none';
  }
}
function renderChurn(){
  const voucher = DATA.pay.find(x=>x.name==='代金券');
  document.getElementById('insightChurn').innerHTML = voucher
    ? '核心发现：<b>代金券订单流失率 '+voucher.churn_rate+'%，是整体（1.24%）的 '+voucher.lift+' 倍</b>，头号流失驱动因素。'
    : '核心发现：代金券流失归因数据未就绪。';
  const pay = DATA.pay;
  if(pay.length){
    getChart('chartPay').setOption({
      grid:{left:10,right:40,top:10,bottom:10,containLabel:true},
      tooltip:{trigger:'axis', formatter:p=>{const raw=pay[p[0].dataIndex]; return raw.name+'<br/>流失率 '+raw.churn_rate+'%<br/>提升度 '+raw.lift;}},
      xAxis:{type:'value', ...baseAxis, axisLabel:{...baseAxis.axisLabel, formatter:'{value}%'}},
      yAxis:{type:'category', data:pay.map(x=>x.name).reverse(), ...baseAxis, axisLabel:{color:C.ink, fontSize:13}},
      series:[{type:'bar', data:pay.map(x=>x.churn_rate).reverse(), barWidth:20,
        label:{show:true, position:'right', formatter:'{c}%', color:C.ink2, fontSize:11},
        itemStyle:{color:p=>{const raw=pay[p.dataIndex]; return gradeColor(raw.lift, 0.5, 4.5, 0);}, borderRadius:[0,3,3,0]}}]
    }, true);
    document.getElementById('capPay').innerHTML = '<b>支付方式流失率</b>：代金券流失率 5.31%（lift 4.28），是信用卡的近 5 倍。';
  }
}
function renderPayProfile(){
  const pp = DATA.payment_type_profile||[];
  if(!pp.length) return;
  const ppData = pp.map(x=>({name:payName(x.payment_type), aov:x.avg_order_value, rep:x.repurchase_rate*100, score:x.avg_score}));
  getChart('chartPayProfile').setOption({
    grid:{left:10,right:40,top:10,bottom:10,containLabel:true},
    tooltip:{trigger:'axis', formatter:p=>{const d=ppData[p[0].dataIndex]; return d.name+'<br/>客单价 R$'+d.aov.toFixed(0)+'<br/>复购率 '+d.rep.toFixed(2)+'%<br/>评分 '+d.score.toFixed(2);}},
    legend:{data:['客单价','复购率'], bottom:0, textStyle:{color:C.ink2, fontSize:11}, icon:'circle'},
    xAxis:{type:'category', data:ppData.map(x=>x.name), ...baseAxis, axisLabel:{color:C.ink, fontSize:12}},
    yAxis:[{type:'value', name:'客单价', ...baseAxis, axisLabel:{...baseAxis.axisLabel, formatter:'R$'+'{value}'}},
           {type:'value', name:'复购率', ...baseAxis, axisLabel:{...baseAxis.axisLabel, formatter:'{value}%'}, splitLine:{show:false}}],
    series:[{type:'bar', data:ppData.map(x=>x.aov), barWidth:'35%', itemStyle:{color:C.accent2, borderRadius:[3,3,0,0]}},
            {type:'line', data:ppData.map(x=>x.rep), yAxisIndex:1, smooth:true, symbol:'circle', lineStyle:{color:C.accent, width:2.5}, itemStyle:{color:C.accent}}]
  }, true);
  const voucher = pp.find(x=>x.payment_type==='voucher');
  document.getElementById('capPayProfile').innerHTML = '<b>支付方式画像</b>：柱=客单价、线=复购率。'+(voucher?'<b>代金券复购率最高（'+voucher.repurchase_rate.toFixed(2)+'%）</b>——反直觉，代金券是有效拉新工具。':'');
}

// ═══════════ 初始化 ═══════════
function fillFilterOptions(){
  if(!HAS_FACT) return;
  const fact = DATA.fact;
  const states = [...new Set(fact.map(r=>r.state).filter(Boolean))].sort();
  document.getElementById('fState').innerHTML = '<option value="">全部</option>' + states.map(s=>'<option value="'+s+'">'+stateName(s)+'</option>').join('');
  const months = [...new Set(fact.map(r=>r.month).filter(Boolean))].sort();
  document.getElementById('fMonth').innerHTML = '<option value="">全部</option>' + months.map(m=>'<option value="'+m+'">'+m+'</option>').join('');
  const catCnt = {};
  fact.forEach(r=>{ if(r.category) catCnt[r.category]=(catCnt[r.category]||0)+1; });
  const cats = Object.entries(catCnt).sort((a,b)=>b[1]-a[1]).slice(0,40).map(x=>x[0]).sort();
  document.getElementById('fCat').innerHTML = '<option value="">全部</option>' + cats.map(c=>'<option value="'+c+'">'+catName(c)+'</option>').join('');
  document.getElementById('fPay').innerHTML = '<option value="">全部</option>' + ['credit_card','boleto','voucher','debit_card'].map(p=>'<option value="'+p+'">'+payName(p)+'</option>').join('');
}
function initFilters(){
  if(!HAS_FACT){
    document.getElementById('filterNote').textContent =
      ' 订单级事实表未就绪：请先在虚拟机运行 analysis_07_fact_rating.ipynb 写入 ads_fact_order，再重新生成本看板。总览标签页的订单级指标暂不可用。';
    return;
  }
  fillFilterOptions();
  ['fYear','fMonth','fState','fPay','fCat'].forEach(id=>{
    document.getElementById(id).addEventListener('change', e=>{
      filters[{fYear:'year',fMonth:'month',fState:'state',fPay:'pay',fCat:'cat'}[id]] = e.target.value;
      applyFilters();
    });
  });
  document.getElementById('fReset').addEventListener('click', ()=>{
    filters.year=filters.month=filters.state=filters.pay=filters.cat='';
    ['fYear','fMonth','fState','fPay','fCat'].forEach(id=>document.getElementById(id).value='');
    applyFilters();
  });
}

// 标签页切换
document.querySelectorAll('.tab-btn').forEach(btn=>{
  btn.addEventListener('click', ()=>{
    document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-'+btn.dataset.tab).classList.add('active');
    // 懒加载：维度页首次切换时渲染（此时容器已可见，canvas 尺寸正常）
    const t = btn.dataset.tab;
    if(PAGE_RENDERERS[t] && !renderedPages[t]){
      PAGE_RENDERERS[t]();
      renderedPages[t] = true;
    }
    Object.values(charts).forEach(c=>c.resize());
  });
});

// ═══════════ 语言切换（英文/葡语 ↔ 中文）═══════════
function reRenderAll(){
  // 总览页始终重渲染（含联动筛选后的图）
  renderOverview();
  // 已渲染的维度页重渲染
  Object.keys(PAGE_RENDERERS).forEach(t=>{
    if(renderedPages[t]) PAGE_RENDERERS[t]();
  });
  // 筛选下拉框的显示文本重填
  fillFilterOptions();
}
document.getElementById('langToggle').addEventListener('click', ()=>{
  LANG = (LANG==='en') ? 'zh' : 'en';
  const btn = document.getElementById('langToggle');
  btn.textContent = (LANG==='zh') ? '原文' : '中文';
  btn.classList.toggle('zh', LANG==='zh');
  reRenderAll();
});

// 启动：事实表为列式数组 [month, year, state, pay_type, category, payment_value, delivery_days, late_days, is_late, processing_hours, ship_days, review_score]
if(HAS_FACT){
  const F0 = DATA.fact;
  const rows = new Array(F0.length);
  for(let i=0;i<F0.length;i++){
    const r = F0[i];
    rows[i] = {month:r[0], year:r[1], state:r[2], pay_type:r[3], category:r[4],
      payment_value:+r[5]||0,
      delivery_days:r[6]===null?null:+r[6], late_days:r[7]===null?null:+r[7], is_late:+r[8]||0,
      processing_hours:r[9]===null?null:+r[9], ship_days:r[10]===null?null:+r[10],
      review_score:r[11]===null?null:+r[11]};
  }
  DATA.fact = rows;
}
initFilters();
applyFilters();
// 维度页改为懒加载（首次切换 tab 时渲染），不再启动时一次性 renderDeep
</script>
</body>
</html>
"""

# 事实表列式压缩（缩小组积）：[month, year, state, pay_type, category, payment_value, delivery_days, late_days, is_late, processing_hours, ship_days, review_score]
def _fact_row(r):
    return [
        r.get('month') or '', (str(r.get('year')) if r.get('year') is not None else ''),
        r.get('state') or '', r.get('payment_type') or '', r.get('category') or '',
        round(float(r['payment_value']), 2) if r.get('payment_value') is not None else 0,
        r.get('delivery_days'), r.get('late_days'), int(r.get('is_late') or 0),
        r.get('processing_hours'), r.get('ship_days'), r.get('review_score')
    ]
data_js['fact'] = [_fact_row(r) for r in FACT]

html = html.replace('__DATA_JS__', js_dump(data_js))
html = html.replace('__HAS_FACT__', 'true' if data_js['fact'] else 'false')

out = r'D:/Olist数据分析/visualization/output/Olist电商数据分析看板.html'
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print('已生成:', out, f'({len(html)//1024} KB)')
