"""Read-only filters on scoped report entries, applied before pagination."""
from datetime import date

KINDS = {'wechat_play', 'wechat_catering', 'wechat_refund', 'wallet', 'wallet_refund',
         'month_card', 'month_card_carry', 'point_cost', 'settlement_fee'}


def filter_entries(entries, args):
    kind = args.get('EntryKind', '')
    if kind and kind not in KINDS:
        raise ValueError('结算项目无效')
    raw_store = args.get('EntryStoreId', '')
    try:
        store = int(raw_store) if raw_store != '' else None
        if store is not None and store < 0:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError('门店筛选无效')
    start, end = args.get('EntryStart', ''), args.get('EntryEnd', '')
    try:
        for value in (start, end):
            if value:
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError()
        if start and end and start > end:
            raise ValueError()
    except ValueError:
        raise ValueError('业务日期筛选无效')
    keyword = args.get('EntryQuery', '').strip().casefold()
    field = args.get('EntrySort', 'event_at')
    order = args.get('EntryOrder', 'desc')
    if field not in ('event_at', 'amount', 'face_amount') or order not in ('asc', 'desc'):
        raise ValueError('排序字段或方向无效')
    rows = [e for e in entries if
            (not kind or e['kind'] == kind) and
            (store is None or store in (e['payer_id'], e['receiver_id'])) and
            (not start or str(e['event_at'])[:10] >= start) and
            (not end or str(e['event_at'])[:10] <= end) and
            (not keyword or keyword in str(e.get('reference', '')).casefold())]
    def key(e):
        value = str(e['event_at']).replace('T', ' ') if field == 'event_at' else abs(e.get(field) or 0)
        return value, str(e.get('biz_key') or e.get('id') or '')
    return sorted(rows, key=key, reverse=order == 'desc')
