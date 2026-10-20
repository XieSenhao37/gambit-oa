"""Store-scoped PlayConfig editing; cents at the API/storage boundary."""
import copy
import hashlib
import json
import re
from datetime import date
from pathlib import Path

CALENDAR = json.loads(Path(__file__).with_name('play_calendar_2026.json').read_text())
KEY = 'PlayConfig'


def read_schedule(config, store_id):
    stores = config.get('StoreMap') or {}
    if stores:
        return copy.deepcopy(stores.get(str(store_id)))
    if 'Common' in config and 'Holiday' in config:
        return {key: copy.deepcopy(config[key]) for key in ('Common', 'Holiday', 'SpecialMap', 'HolidayWeekdays') if key in config}
    return None


def revision(config):
    return hashlib.sha256(json.dumps(config, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def valid_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('日期须为 YYYY-MM-DD')
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError('日期无效')


def validate_price(value):
    if not isinstance(value, dict):
        raise ValueError('请填写完整价格')
    result = {}
    for key in ('Price', 'AdditionPrice', 'MaxTotal'):
        n = value.get(key)
        if type(n) is not int or not 0 <= n <= 10000000:
            raise ValueError('价格须为 0–100000 元，精确到分')
        result[key] = n
    if type(value.get('MaxHour')) is not int or not 1 <= value['MaxHour'] <= 24:
        raise ValueError('优惠时长须为 1–24 小时')
    if type(value.get('BundlePricing', False)) is not bool:
        raise ValueError('计费公式无效')
    result.update(MaxHour=value['MaxHour'], BundlePricing=value.get('BundlePricing', False))
    if result['BundlePricing'] and result['MaxTotal'] > result['Price'] * result['MaxHour']:
        raise ValueError('优惠价不能高于对应时长的按小时价格')
    return result


def minutes(value, end=False):
    if end and value == '24:00':
        return 1440
    if not isinstance(value, str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value):
        raise ValueError('时段须为 HH:mm，结束时间可为 24:00')
    h, m = map(int, value.split(':'))
    return h * 60 + m


def intervals(rule):
    start, end = minutes(rule['StartTime']), minutes(rule['EndTime'], True)
    if start == end:
        raise ValueError('起止时间不能相同，全天请填写 00:00–24:00')
    return [(start, end)] if start < end else [(start, 1440), (0, end)]


def validate_schedule(value):
    if not isinstance(value, dict):
        raise ValueError('计价配置格式错误')
    result = {key: validate_price(value.get(key)) for key in ('Common', 'Holiday')}
    if type(value.get('UseAdjustedWorkdays', True)) is not bool:
        raise ValueError('调休补班配置无效')
    result['UseAdjustedWorkdays'] = value.get('UseAdjustedWorkdays', True)
    weekdays = value.get('HolidayWeekdays', [0, 5, 6])
    if not isinstance(weekdays, list) or any(type(n) is not int or not 0 <= n <= 6 for n in weekdays) or len(set(weekdays)) != len(weekdays):
        raise ValueError('适用星期须为周一至周日，不可重复')
    result['HolidayWeekdays'] = sorted(weekdays)
    dates, specials = value.get('DateTypes', {}), value.get('SpecialMap', {})
    if not isinstance(dates, dict) or not isinstance(specials, dict) or len(dates) > 3660 or len(specials) > 3660:
        raise ValueError('指定日期配置无效或过多')
    for day, kind in dates.items():
        valid_date(day)
        if kind not in ('common', 'holiday'):
            raise ValueError('指定日期须选择工作日价或周末节假日价')
    result['DateTypes'] = dict(sorted(dates.items()))
    result['SpecialMap'] = {}
    for day, price in specials.items():
        valid_date(day)
        result['SpecialMap'][day] = validate_price(price)
    rules = value.get('TimeRules', [])
    if not isinstance(rules, list) or len(rules) > 100:
        raise ValueError('最多配置 100 个时段')
    result['TimeRules'] = []
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError('时段格式错误')
        r = {key: rule.get(key, '') for key in ('Name', 'StartDate', 'EndDate', 'StartTime', 'EndTime', 'DayType')}
        if not isinstance(r['Name'], str) or not 1 <= len(r['Name'].strip()) <= 60:
            raise ValueError('时段名称须为 1–60 字')
        if r['DayType'] not in ('any', 'common', 'holiday'):
            raise ValueError('时段适用日期类型无效')
        if bool(r['StartDate']) != bool(r['EndDate']):
            raise ValueError('生效日期须同时填写起止日期或都留空')
        if r['StartDate'] and valid_date(r['StartDate']) > valid_date(r['EndDate']):
            raise ValueError('结束日期不能早于开始日期')
        r['Price'] = validate_price(rule.get('Price'))
        parts = intervals(r)
        for old in result['TimeRules']:
            dates_overlap = (r['StartDate'] or '0001-01-01') <= (old['EndDate'] or '9999-12-31') and (old['StartDate'] or '0001-01-01') <= (r['EndDate'] or '9999-12-31')
            types_overlap = r['DayType'] == 'any' or old['DayType'] == 'any' or r['DayType'] == old['DayType']
            times_overlap = any(a < d and c < b for a, b in parts for c, d in intervals(old))
            if dates_overlap and types_overlap and times_overlap:
                raise ValueError('同一日期类型的时段不能重叠：' + old['Name'] + ' / ' + r['Name'])
        result['TimeRules'].append(r)
    return result


def resolve_price(schedule, at):
    day = at.strftime('%Y-%m-%d')
    kind = 'holiday' if (at.weekday() + 1) % 7 in schedule.get('HolidayWeekdays', [0, 5, 6]) else 'common'
    if schedule.get('UseAdjustedWorkdays', True) and day in CALENDAR['Workdays']:
        kind = 'common'
    if any(h['Start'] <= day <= h['End'] for h in CALENDAR['Holidays']) or day[5:] in ('01-01', '05-01', '05-02', '10-01', '10-02', '10-03'):
        kind = 'holiday'
    kind = schedule.get('DateTypes', {}).get(day, kind)
    if day in schedule.get('SpecialMap', {}):
        return schedule['SpecialMap'][day], '指定日期价格', kind
    clock = at.strftime('%H:%M')
    for rule in schedule.get('TimeRules', []):
        if rule['StartDate'] and not rule['StartDate'] <= day <= rule['EndDate']:
            continue
        if rule['DayType'] not in ('any', kind):
            continue
        if any(a <= minutes(clock) < b for a, b in intervals(rule)):
            return rule['Price'], rule['Name'], kind
    return schedule['Holiday' if kind == 'holiday' else 'Common'], '周五至周日／节假日价' if kind == 'holiday' and set(schedule.get('HolidayWeekdays', [0, 5, 6])) == {0, 5, 6} else ('指定星期／节假日价' if kind == 'holiday' else '平日价'), kind


def total(price, hours):
    base_hours = min(hours, price['MaxHour']) if price.get('BundlePricing') else hours
    return min(price['MaxTotal'], base_hours * price['Price']) + max(0, hours - price['MaxHour']) * price['AdditionPrice']
