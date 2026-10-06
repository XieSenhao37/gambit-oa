"""Read-only batch metrics reconciled against the selected month's ledger/snapshot."""
import re
from collections import defaultdict
from app.settlement.models import SettlementAllocation


def monthly_wallet_metrics(batch_ids, entries):
    wanted = set(batch_ids)
    result = {key: dict(month_consumption=0, month_refund=0, month_consumption_principal=0,
                        month_refund_principal=0, month_settlement=0) for key in wanted}
    wallet_entries = [e for e in entries if e['kind'] in ('wallet', 'wallet_refund')]
    # Production entries carry batch IDs. Earlier MOCK fixtures aggregate multiple batches per payment.
    aggregated = [e for e in wallet_entries if not re.search(r':batch:(\d+)$', e['biz_key'])]
    references = {e['reference'] for e in aggregated}
    sources = defaultdict(list)
    if references:
        rows = SettlementAllocation.query.filter(SettlementAllocation.kind == 'wallet',
            SettlementAllocation.reference.in_(references),
            SettlementAllocation.state.in_(['consumed', 'returned'])).all()
        for row in rows:
            sources[(row.reference, row.store_id)].append(row)
    for entry in wallet_entries:
        match = re.search(r':batch:(\d+)$', entry['biz_key'])
        if match:
            portions = [(int(match[1]), abs(entry['face_amount']), abs(entry['amount']))]
        else:
            rows = sources[(entry['reference'], entry['receiver_id'])]
            if not any(row.batch_id in wanted for row in rows):
                continue
            if sum(row.amount for row in rows) != abs(entry['face_amount']) or sum(row.principal for row in rows) != abs(entry['amount']):
                raise ValueError('储值批次与结算明细金额不一致，无法安全展示本月金额，请核对原始扣款记录')
            portions = [(row.batch_id, row.amount, row.principal) for row in rows]
        refund = entry['kind'] == 'wallet_refund'
        for batch_id, face, principal in portions:
            if batch_id not in wanted:
                continue
            metrics = result[batch_id]
            metrics['month_refund' if refund else 'month_consumption'] += face
            metrics['month_refund_principal' if refund else 'month_consumption_principal'] += principal
            metrics['month_settlement'] += -principal if refund else principal
    return result
