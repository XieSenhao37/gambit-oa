"""Expose unavailable global metrics as null, never as store income or zero."""
from flask import g, request

def redact_global_metrics(response):
    if not getattr(g, 'staff', None) or g.staff.headquarters or (not request.path.startswith('/admin_api/stats/')):
        return response
    payload = response.get_json(silent=True)
    if not payload or payload.get('Code') != 0:
        return response
    data = payload.get('Data', {})
    hidden = []

    def hide(mapping, key):
        if key in mapping:
            mapping[key] = None
            hidden.append(key)
    summary = data.get('Summary', {})
    for key in ('BalanceTotal', 'WalletRechargeAmount', 'ActiveMonthCardUsers'):
        hide(summary, key)
    if '/wallet/' in request.path:
        for key in list(summary):
            if key != 'ConsumeAmount':
                hide(summary, key)
        data['Trend'] = []
        data['TierDistribution'] = []
    if '/referral/' in request.path:
        for key in list(summary):
            hide(summary, key)
        data['Trend'] = []
        data['ShareRanking'] = []
    if '/coupon/' in request.path:
        hide(summary, 'ReceivedCount')
        hide(summary, 'UseRate')
        for row in data.get('Promotions', []):
            hide(row, 'ReceivedCount')
            hide(row, 'UseRate')
    if '/user/insights' in request.path:
        for row in data.get('Items', []):
            hide(row, 'WalletRechargeAmount')
            hide(row, 'CouponUsedCount')
            row['Tags'] = [tag for tag in row.get('Tags', []) if tag not in ('储值用户', '优惠券敏感')]
    data['UnavailableMetrics'] = sorted(set(hidden))
    data['ScopeNotice'] = '当前授权门店数据；标记为 — 的全品牌指标尚无可靠门店归属，不展示、不计为零。'
    response.set_data(__import__('json').dumps(payload, ensure_ascii=False))
    return response
