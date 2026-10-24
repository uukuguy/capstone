#!/usr/bin/env python3
"""Build ordinary simulated input files and a separate evaluator-only receipt."""
import csv
import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / 'inputs'
TRUTH = BASE / 'verification' / 'ground-truth.json'
OUT.mkdir(parents=True, exist_ok=True)
PROVINCES = ('甲省', '乙省', '丙省')
TZ = timezone(timedelta(hours=8))
prices, flows, renewable = [], [], []
start = datetime(2026, 8, 1, tzinfo=TZ)
end = datetime(2026, 10, 1, tzinfo=TZ)
moment = start
while moment < end:
    month, day, slot = moment.month, moment.day, moment.hour // 6
    quarter = moment.hour * 4 + moment.minute // 15
    midday = 46 <= quarter < 59
    time_fields = {'interval_start': moment.isoformat(timespec='minutes'),
                   'interval_end': (moment + timedelta(minutes=15)).isoformat(timespec='minutes'),
                   'duration_hours': 0.25}
    for index, province in enumerate(PROVINCES):
        price = (260, 290, 315)[index] + (-60, 10, -30, 90)[slot]
        price += ((day * 3 + index * 2) % 9 - 4) * 5
        price += (0 if month == 8 else (-10, -15, -5)[index])
        if moment.weekday() >= 5:
            price -= 15
        if month == 8 and 12 <= day <= 14 and midday:
            price = (-80, -35, 15)[index]
        if month == 9 and 8 <= day <= 10 and 48 <= quarter < 62:
            price = (-60, -20, 5)[index]
        if month == 9 and day == 15 and 47 <= quarter < 60:
            price = (-80, -80, -10)[index]
        if month == 8 and day == 26 and slot == 3:
            price = (760, 820, 900)[index]
        price += round(18 * math.sin(quarter * math.pi / 12 + index) + 9 * math.cos(quarter * math.pi / 3 + day), 2)
        price = round(max(-80, min(1200, price)), 2)
        prices.append({**time_fields, 'province': province, 'spot_price_cny_per_mwh': price,
            'price_floor_cny_per_mwh': -80, 'price_ceiling_cny_per_mwh': 1200,
            'simulation_marker': 'SIMULATED'})

        available = ((700, 900, 2000, 800), (500, 700, 1500, 600),
                     (450, 600, 1250, 500))[index][slot]
        available += ((day * 7 + index * 11 + month * 3) % 17 - 8) * 15
        if month == 9 and slot == 2:
            available += 100
        available += round(55 * math.sin(quarter * math.pi / 12 + index) + 20 * math.cos(quarter * math.pi / 4 + day), 2)
        available = round(available, 2)
        forecast = round(available + ((day * 5 + index * 3 + slot * 2) % 13 - 6) * 25, 2)
        curtail = 0
        if slot == 2 and day % (7 + index * 2) == 0:
            curtail = (80, 60, 40)[index]
        if month == 8 and 12 <= day <= 14 and midday:
            curtail = (300, 100, 0)[index]
        if month == 9 and 8 <= day <= 10 and 48 <= quarter < 62:
            curtail = (0, 240, 0)[index]
        if month == 9 and day == 15 and 47 <= quarter < 60:
            curtail = (380, 200, 70)[index]
        other = 20 + index * 10 if day % 11 == 0 and slot == 1 else 0
        if month == 8 and day == 20 and slot == 2 and index == 0:
            other = 120
        actual = round(available - curtail - other, 2)
        assert min(forecast, available, actual, curtail, other) >= 0
        actual_missing = day == 5 + index and 29 <= quarter < 33
        available_missing = day == 17 + index and 53 <= quarter < 55
        renewable.append({**time_fields, 'province': province,
            'technology_scope': 'wind_and_solar_total', 'forecast_mw': forecast,
            'available_mw': '' if available_missing else available,
            'actual_mw': '' if actual_missing else actual,
            'formal_curtailment_mw': curtail, 'other_reduction_mw': other,
            'other_reduction_reason': 'other_operating_constraint' if other else 'none',
            'quality_note': 'actual_missing' if actual_missing else 'available_missing' if available_missing else 'complete',
            'simulation_marker': 'SIMULATED'})

    for channel, source, target, index in (
            ('A_TO_B', '甲省', '乙省', 0), ('B_TO_C', '乙省', '丙省', 1)):
        limit = (900, 650)[index] + (50 if month == 9 else 0)
        limit += ((0, 50, -100, 0), (-50, 0, 50, 0))[index][slot]
        limit_note = 'normal_operating_limit'
        if index == 0 and month == 8 and 12 <= day <= 14 and midday:
            limit, limit_note = 400, 'scheduled_maintenance_limit'
        if index == 1 and month == 9 and 8 <= day <= 10 and 48 <= quarter < 62:
            limit, limit_note = 250, 'scheduled_maintenance_limit'
        desired = (530, 440)[index] + (30, 70, 150, -60)[slot]
        desired += ((day * 3 + index) % 9 - 4) * 5 + (30 if month == 9 else 0)
        desired += round(45 * math.sin(quarter * math.pi / 12 + index) + 12 * math.cos(quarter * math.pi / 3 + day), 2)
        desired = round(desired, 2)
        planned = round(desired + 15, 2)
        actual = min(desired, limit)
        missing = day == ((5 + index) if month == 8 else (9 + index)) and 31 <= quarter < 35
        flows.append({**time_fields, 'channel_id': channel, 'from_province': source, 'to_province': target,
            'planned_flow_mw': planned, 'actual_flow_mw': '' if missing else actual,
            'operating_limit_mw': limit, 'limit_note': limit_note,
            'quality_note': 'actual_missing' if missing else 'complete', 'simulation_marker': 'SIMULATED'})
    moment += timedelta(minutes=15)


def write_csv(name, rows):
    with (OUT / name).open('w', encoding='utf-8', newline='') as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


write_csv('spot-prices.csv', prices)
write_csv('interprovincial-flows.csv', flows)
write_csv('renewable-generation.csv', renewable)
(OUT / 'README.md').write_text('''# 模拟省级电力市场分析资料（非真实业务数据）

**全部资料均为人工构造的模拟样例。省名、通道、价格、功率和限发记录均不对应真实省份或市场。**
用途是验证普通资料理解、数据分析、图表与报告交付链路。不得据此形成真实经营或调度结论。
本目录只有四个普通输入文件，没有 Capstone 专用查询接口或固定分析流程。
资料版本：SIM-POWER-MARKET-20260809-v2-15MIN；生成规则和验收核对值不属于本输入包。

## 时间、范围与通用规则

- 范围：2026-08-01 00:00 至 2026-10-01 00:00，采用中国标准时间 UTC+08:00。
- 覆盖甲省、乙省、丙省；八月和九月分别分析，再比较变化。
- 一个时段为15分钟，每日96个时段，duration_hours=0.25。起点含、终点不含；按起点月份归属。
- 功率列为该15分钟的平均 MW；电量 MWh = 平均 MW × duration_hours。不能把 MW 直接当电量。
- 所有文件为 UTF-8 CSV，首行为字段名。空字段表示缺失，不是零；不插值、不以预测补实际。
- 没有重复主键。除明确的实际/可用功率空值外，价格、计划、动态限额、预测和正式限发记录完整。
- 所有行 simulation_marker=SIMULATED。时段标签和单位相同，可按 interval_start 对齐。

## 1. spot-prices.csv

主键：(interval_start, province)。spot_price_cny_per_mwh 为15分钟时段的模拟现货价格，单位元/MWh。
price_floor_cny_per_mwh 和 price_ceiling_cny_per_mwh 是该行适用的模拟市场价底/价顶。
价格均值按 duration_hours 加权；等时长时也可算术平均。负价为价格严格小于零；触底为价格等于该行价底，二者不能混用。
可计算月均、极值、负价小时、触底小时及同时间省际价差。没有成交电量，因此不能声称这是成交电量加权电价、购售电收入或利润。

## 2. interprovincial-flows.csv

主键：(interval_start, channel_id)。A_TO_B 方向为甲省→乙省；B_TO_C 方向为乙省→丙省。
planned_flow_mw、actual_flow_mw 为该方向的非负计划/实际平均功率；本包没有反向交易，不得给乙→甲另造一条通道。
operating_limit_mw 为同一方向、同一时段的运行限额，会随月份、时段及检修改变。limit_note 是限额台账说明。
时段利用率 = actual_flow_mw / operating_limit_mw。近限额检查可使用实际利用率 ≥95%，必须写明阈值。
月度能量口径利用率 = Σ(实际 MW×小时) / Σ(限额 MW×小时)，分母只取实际非缺失的同一组时段。
另列全月限额能量及实际数据覆盖小时。不得把缺实际时段的限额留在成对比率分母，也不能把时段利用率简单相加。
计划偏差在实际非缺失时段内比较实际与计划。计划高于限额不等于实际越限，实际越限须检查实际值。
不能仅据通道利用率证明网架安全、N-1约束、阻塞定价因果或全省电力平衡。本包没有损耗、负荷或完整网架模型。

## 3. renewable-generation.csv

主键：(interval_start, province)。technology_scope=wind_and_solar_total，表示风电与光伏合计，不可分别臆算风/光贡献。
forecast_mw 为预测功率；available_mw 为本样例调度台账的可用发电功率，尚未扣除正式限发和另列其他运行减发；actual_mw 为实际并网功率。
formal_curtailment_mw 为正式调度限发台账记录，是本包唯一可用于计算“正式限发电量”的功率字段。
other_reduction_mw 是另外登记的其他运行约束减发，不属于正式限发。完整观测行满足：
available_mw = actual_mw + formal_curtailment_mw + other_reduction_mw。
正式限发电量 = Σ(formal_curtailment_mw×小时)，该字段全量完整；正式限发率的本包定义为：
Σ(正式限发 MW×小时) / Σ((实际 MW+正式限发 MW)×小时)，分子、分母只取实际值非缺失的同一组时段。
该成对观测率须标注覆盖小时，不能冒称缺数情况下的精确全月正式限发率。完整的全月实际发电量也无法从缺数记录精确恢复。
available_mw 缺失时，不能算该行可用电量或可用-实际差，但不影响该行已知正式限发台账值。
forecast_mw-actual_mw 是预测偏差，**不是弃电/限发**；available_mw-actual_mw 也可能含其他运行减发。
样例特意含有预测误差但正式限发为零的记录，以及非限发的其他运行减发记录。
价格、通道与出力的同时间关系可作描述性对照；本包不足以独立识别因果、反事实收益或全口径新能源消纳率。

## 资料用途

请仅依据这四份资料，分析2026年8月和9月甲、乙、丙三省的现货价格、省间通道运行与新能源出力及限发情况，比较两个月的变化。
先检查资料覆盖、单位、业务口径和缺失值。识别有依据的价格异常/触底与负价时段、通道利用及计划偏差，结合同时段数据讨论新能源出力和正式限发的关联与限制。
用实际数据核算关键指标，选择适合问题的专业图表，并生成可独立打开的中文研究报告、图表及关键计算数据；注明模拟性质、资料来源、方法、单位、覆盖范围、检查结果和未解决问题。
不要把预测偏差当作弃电，不要由相关性声称因果，不要编造缺失记录或真实省级结论。不联网，不调用电网仿真；保留可复核的实际文件。
''', encoding='utf-8')

# Evaluator-only truth is recomputed from the saved CSVs, not the output text
# of any model and not the in-memory generation rows.
def load(name):
    with (OUT / name).open(encoding='utf-8', newline='') as source:
        return list(csv.DictReader(source))


def d(row, key):
    return None if row[key] == '' else Decimal(row[key])


def num(value):
    return float(value) if value is not None else None


price_rows = load('spot-prices.csv')
flow_rows = load('interprovincial-flows.csv')
renew_rows = load('renewable-generation.csv')
truth = {'schema': 'simulated-demo1-evaluator/1', 'simulation_only': True,
    'not_agent_input': True, 'units': {'power': 'MW', 'energy': 'MWh', 'price': 'CNY/MWh'},
    'interval_hours': 0.25, 'timezone': 'UTC+08:00', 'price': [], 'flow': [], 'renewable': [],
    'files': {}, 'counterexamples': {}}
for month in ('2026-08', '2026-09'):
    for province in PROVINCES:
        rows = [row for row in price_rows if row['interval_start'].startswith(month) and row['province'] == province]
        hours = sum(d(row, 'duration_hours') for row in rows)
        truth['price'].append({'month': month, 'province': province, 'rows': len(rows), 'covered_hours': num(hours),
            'time_weighted_mean_cny_per_mwh': num(sum(d(row, 'spot_price_cny_per_mwh') * d(row, 'duration_hours') for row in rows) / hours),
            'min_cny_per_mwh': num(min(d(row, 'spot_price_cny_per_mwh') for row in rows)),
            'max_cny_per_mwh': num(max(d(row, 'spot_price_cny_per_mwh') for row in rows)),
            'negative_hours': num(sum(d(row, 'duration_hours') for row in rows if d(row, 'spot_price_cny_per_mwh') < 0)),
            'floor_hours': num(sum(d(row, 'duration_hours') for row in rows if d(row, 'spot_price_cny_per_mwh') == d(row, 'price_floor_cny_per_mwh')))})
        rows = [row for row in renew_rows if row['interval_start'].startswith(month) and row['province'] == province]
        actual = [row for row in rows if d(row, 'actual_mw') is not None]
        available = [row for row in rows if d(row, 'available_mw') is not None]
        known_energy = sum(d(row, 'actual_mw') * d(row, 'duration_hours') for row in actual)
        paired_curtail = sum(d(row, 'formal_curtailment_mw') * d(row, 'duration_hours') for row in actual)
        truth['renewable'].append({'month': month, 'province': province, 'rows': len(rows),
            'actual_missing_rows': len(rows) - len(actual), 'available_missing_rows': len(rows) - len(available),
            'actual_covered_hours': num(sum(d(row, 'duration_hours') for row in actual)),
            'available_covered_hours': num(sum(d(row, 'duration_hours') for row in available)),
            'actual_known_mwh': num(known_energy),
            'forecast_full_mwh': num(sum(d(row, 'forecast_mw') * d(row, 'duration_hours') for row in rows)),
            'available_known_mwh': num(sum(d(row, 'available_mw') * d(row, 'duration_hours') for row in available)),
            'formal_curtailment_full_mwh': num(sum(d(row, 'formal_curtailment_mw') * d(row, 'duration_hours') for row in rows)),
            'formal_curtailment_paired_mwh': num(paired_curtail),
            'formal_curtailment_observed_rate_pct': num(100 * paired_curtail / (known_energy + paired_curtail)),
            'other_reduction_full_mwh': num(sum(d(row, 'other_reduction_mw') * d(row, 'duration_hours') for row in rows)),
            'forecast_minus_actual_known_mwh': num(sum((d(row, 'forecast_mw') - d(row, 'actual_mw')) * d(row, 'duration_hours') for row in actual)),
            'full_actual_mwh': None, 'full_month_curtailment_rate_pct': None})
    for channel in ('A_TO_B', 'B_TO_C'):
        rows = [row for row in flow_rows if row['interval_start'].startswith(month) and row['channel_id'] == channel]
        actual = [row for row in rows if d(row, 'actual_flow_mw') is not None]
        energy = sum(d(row, 'actual_flow_mw') * d(row, 'duration_hours') for row in actual)
        limit_energy = sum(d(row, 'operating_limit_mw') * d(row, 'duration_hours') for row in actual)
        truth['flow'].append({'month': month, 'channel_id': channel, 'rows': len(rows), 'actual_missing_rows': len(rows)-len(actual),
            'actual_covered_hours': num(sum(d(row, 'duration_hours') for row in actual)), 'actual_known_mwh': num(energy),
            'paired_limit_mwh': num(limit_energy), 'observed_energy_utilization_pct': num(100 * energy / limit_energy),
            'limit_min_mw': num(min(d(row, 'operating_limit_mw') for row in rows)),
            'limit_max_mw': num(max(d(row, 'operating_limit_mw') for row in rows)),
            'near_limit_known_hours': num(sum(d(row, 'duration_hours') for row in actual if d(row, 'actual_flow_mw') >= Decimal('.95') * d(row, 'operating_limit_mw'))),
            'actual_over_limit_known_hours': num(sum(d(row, 'duration_hours') for row in actual if d(row, 'actual_flow_mw') > d(row, 'operating_limit_mw'))),
            'planned_over_limit_hours': num(sum(d(row, 'duration_hours') for row in rows if d(row, 'planned_flow_mw') > d(row, 'operating_limit_mw'))),
            'actual_minus_plan_paired_mwh': num(sum((d(row, 'actual_flow_mw')-d(row, 'planned_flow_mw')) * d(row, 'duration_hours') for row in actual))})

truth['counterexamples']['forecast_error_with_zero_formal_curtailment_rows'] = sum(
    row['actual_mw'] != '' and d(row, 'forecast_mw') != d(row, 'actual_mw') and d(row, 'formal_curtailment_mw') == 0 for row in renew_rows)
truth['counterexamples']['non_curtailment_operating_reduction_rows'] = sum(d(row, 'other_reduction_mw') > 0 for row in renew_rows)
lookup = {(row['interval_start'], row['province']): row for row in price_rows}
truth['counterexamples']['negative_price_without_formal_curtailment_rows'] = sum(
    d(lookup[row['interval_start'], row['province']], 'spot_price_cny_per_mwh') < 0 and d(row, 'formal_curtailment_mw') == 0 for row in renew_rows)
for name, rows, keys in [('spot-prices.csv', price_rows, ('interval_start', 'province')),
                        ('interprovincial-flows.csv', flow_rows, ('interval_start', 'channel_id')),
                        ('renewable-generation.csv', renew_rows, ('interval_start', 'province'))]:
    assert len({tuple(row[key] for key in keys) for row in rows}) == len(rows)
    assert all(row['simulation_marker'] == 'SIMULATED' and row['duration_hours'] == '0.25' for row in rows)
    assert len(rows) == (11712 if name == 'interprovincial-flows.csv' else 17568)
for row in renew_rows:
    if row['available_mw'] != '' and row['actual_mw'] != '':
        assert d(row, 'available_mw') == d(row, 'actual_mw') + d(row, 'formal_curtailment_mw') + d(row, 'other_reduction_mw')
for path in sorted(OUT.iterdir()):
    data = path.read_bytes()
    truth['files'][path.name] = {'bytes': len(data), 'sha256': sha256(data).hexdigest()}
truth['total_upload_bytes'] = sum(item['bytes'] for item in truth['files'].values())
assert len(truth['files']) == 4 and truth['total_upload_bytes'] < 8 * 1024 * 1024
assert all(item['actual_over_limit_known_hours'] == 0 for item in truth['flow'])
assert truth['counterexamples']['forecast_error_with_zero_formal_curtailment_rows'] > 0
TRUTH.write_text(json.dumps(truth, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'upload_path': str(OUT), 'truth_path': str(TRUTH), 'total_bytes': truth['total_upload_bytes'],
                  'files': truth['files'], 'counterexamples': truth['counterexamples']}, ensure_ascii=False, indent=2))
