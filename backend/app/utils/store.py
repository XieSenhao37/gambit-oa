from flask import request, g, abort
DEFAULT_STORE_ID = 1

def get_request_store_id(default=DEFAULT_STORE_ID):
    if getattr(g, 'store_id', None): return g.store_id
    body = request.get_json(silent=True)
    sources = [request.args, request.form, body if isinstance(body, dict) else {}]
    values = [request.headers.get('X-Store-ID')]
    for source in sources:
        for key in ('StoreID', 'StoreId', 'store_id'):
            value = source.get(key)
            if value is not None: values.append(value)
    try:
        ids = {int(v) for v in values if v not in (None, '')}
    except (ValueError, TypeError): abort(400, description='门店参数不正确')
    if any(i <= 0 for i in ids) or len(ids) > 1: abort(400, description='请选择单个门店，且门店参数必须一致')
    if not ids: abort(400, description='请选择门店')
    return ids.pop()
