"""Store-scoped OA gateway. Go owns all stock, order and financial transitions."""
from flask import Blueprint, current_app, g, jsonify, request, abort
import requests
from app.middlewares.auth import login_required
from app.security.policy import can_page, available_stores

bp = Blueprint('game_services', __name__)

def proxy(path, method='GET', query=None):
    base = current_app.config.get('GAMBIT_SERVER_BASE_URL', '').rstrip('/')
    token = current_app.config.get('GAMBIT_INTERNAL_TOKEN', '')
    if not base or not token:
        return jsonify(Code=503, Message='桌游服务后端连接尚未配置'), 503
    data = request.get_json(silent=True) if method != 'GET' else None
    if method != 'GET' and not isinstance(data, dict):
        return jsonify(Code=400, Message='请求格式错误'), 400
    # Never trust browser-provided identity, action store or forwarded headers.
    payload = dict(data or {})
    payload['StoreID'] = getattr(g, 'store_id', None)
    payload['Actor'] = str(g.staff.user_id)
    # Financial authorization is decided here, never by client-supplied flags.
    payload['AutoRefund'] = bool(path == 'action' and (payload.get('Action') == 'return_complete' or (payload.get('Action') == 'settle_deposit' and can_page('refunds', g.store_id))))
    try:
        res = requests.request(method, f'{base}/microapp_api/admin/game-service/v1/{path}',
            params=(query if query is not None else {**request.args.to_dict(), 'StoreID': g.store_id}) if method == 'GET' else None,
            json=payload if method != 'GET' else None,
            headers={'X-GAMBIT-INTERNAL-TOKEN': token}, timeout=25)
        res.raise_for_status()
        result = res.json()
        if not isinstance(result, dict) or 'Code' not in result:
            raise ValueError('invalid response')
        if result['Code'] != 0:
            return jsonify(Code=result['Code'], Message=result.get('Msg', '操作失败')), 400
        return jsonify(Code=0, Data=result.get('Data'))
    except (requests.RequestException, ValueError):
        current_app.logger.warning('桌游服务调用失败: %s %s', method, path)
        # Do not claim failure means rollback: a timed-out write may already have committed.
        return jsonify(Code=502, Message='后端响应超时或异常，请刷新确认结果；重试请保留同一请求编号'), 502

@bp.route('/policy', methods=['GET'])
@login_required('game-services')
def policy():
    return proxy('policy')

@bp.route('/policy', methods=['PUT'])
@login_required('game-services')
def save_policy():
    return proxy('policy', 'PUT')

@bp.route('/stock', methods=['GET'])
@login_required('game-services')
def stocks():
    return proxy('stock')

@bp.route('/stock', methods=['PUT'])
@login_required('game-services')
def save_stock():
    return proxy('stock', 'PUT')

@bp.route('/stock/batch', methods=['POST'])
@login_required('game-services')
def save_stock_batch():
    return proxy('stock/batch', 'POST')

@bp.route('/orders', methods=['GET'])
@login_required('game-service-orders')
def orders():
    return proxy('orders')

@bp.route('/orders/<int:order_id>', methods=['GET'])
@login_required('game-service-orders')
def order(order_id):
    return proxy(f'orders/{order_id}')

@bp.route('/action', methods=['POST'])
@login_required('game-service-orders')
def action():
    data = request.get_json(silent=True) or {}
    if data.get('Action') in ('settle_deposit', 'purchase_return', 'declare_loss') and not can_page('game-services', g.store_id):
        abort(403, description='押金结算、售后退回与遗失登记需要管理权限')
    return proxy('action', 'POST')

@bp.route('/refund', methods=['POST'])
@login_required('game-service-orders')
def refund():
    if not can_page('refunds', g.store_id):
        abort(403, description='退款发起需要退款管理权限')
    return proxy('refund', 'POST')

@bp.route('/community', methods=['GET'])
@login_required('session')
def community():
    # Aggregate only fresh server-side grants; ignore any browser-supplied store list.
    stores = [s.id for s in available_stores(g.staff, g.grants) if can_page('game-community', s.id)]
    if not stores:
        abort(403, description='无该页面权限')
    query = {key: request.args[key] for key in ('Page', 'IntentPage', 'Keyword', 'ShareKeyword', 'ShareStatus') if key in request.args}
    query['StoreIDs'] = ','.join(map(str, stores))
    return proxy('community', query=query)

@bp.route('/review', methods=['POST'])
@login_required('game-community')
def review():
    if not can_page('game-services', g.store_id):
        abort(403, description='分享管理与奖励需要管理权限')
    return proxy('review', 'POST')

@bp.route('/inventory', methods=['GET'])
@login_required('games')
def inventory():
    return proxy('inventory')

@bp.route('/inventory', methods=['PUT'])
@login_required('game-services')
def save_inventory():
    return proxy('inventory', 'PUT')


@bp.route('/todos', methods=['GET'])
@login_required('session')
def todos():
    # Counts are actionable orders, not read/unread messages. No customer identity is returned.
    stores = [s for s in available_stores(g.staff, g.grants) if can_page('game-service-orders', s.id)]
    base = current_app.config.get('GAMBIT_SERVER_BASE_URL', '').rstrip('/')
    token = current_app.config.get('GAMBIT_INTERNAL_TOKEN', '')
    if not stores:
        return jsonify(Code=0, Data={'Total': 0, 'Items': []})
    if not base or not token:
        return jsonify(Code=503, Message='待办服务暂不可用'), 503
    items, total = [], 0
    try:
        for store in stores:
            res = requests.request('GET', f'{base}/microapp_api/admin/game-service/v1/orders',
                params={'StoreID': store.id, 'Status': 'todo', 'Page': 1},
                headers={'X-GAMBIT-INTERNAL-TOKEN': token}, timeout=8)
            res.raise_for_status()
            result = res.json()
            if result.get('Code') != 0 or not isinstance(result.get('Data'), dict):
                raise ValueError('invalid response')
            data = result['Data']
            total += int(data['Total'])
            for order in data.get('Orders') or []:
                if order['RequestedStoreID'] != store.id:
                    raise ValueError('store mismatch')
                status = order['Status']
                label = {'pending_confirm': '待确认', 'pending_accept': '待接单', 'accepted': '待交付', 'inspection': '归还待检查'}.get(status)
                if not label:
                    label = '归还待处理' if order.get('ReturnRequestedAt') else '到期／逾期提醒' if status == 'rented' else '退款待处理'
                items.append({'ID': order['ID'], 'StoreID': store.id, 'StoreName': store.name,
                    'Label': label, 'CreatedAt': order.get('CreatedAt'),
                    'Games': '、'.join(line['GameName'] for line in order.get('Lines', []))})
        items.sort(key=lambda item: item['ID'], reverse=True)
        return jsonify(Code=0, Data={'Total': total, 'Items': items[:30]})
    except (requests.RequestException, ValueError, KeyError, TypeError):
        current_app.logger.warning('桌游待办读取失败')
        return jsonify(Code=502, Message='待办暂未更新，请重试'), 502
