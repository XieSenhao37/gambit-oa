"""Retail gateway: server-side store/actor scope; Go owns all transactions."""
from flask import Blueprint, current_app, g, jsonify, request, abort
import requests
from app.middlewares.auth import login_required
from app.security.policy import can_page

bp = Blueprint('retail', __name__)

def proxy(path, method='GET'):
    base = current_app.config.get('GAMBIT_SERVER_BASE_URL', '').rstrip('/')
    token = current_app.config.get('GAMBIT_INTERNAL_TOKEN', '')
    if not base or not token:
        return jsonify(Code=503, Message='商城后端尚未配置'), 503
    data = request.get_json(silent=True) if method != 'GET' else {}
    if not isinstance(data, dict):
        return jsonify(Code=400, Message='请求格式错误'), 400
    payload = {**data, 'StoreID': g.store_id, 'Actor': str(g.staff.user_id)}
    query = {k: request.args[k] for k in ('Page', 'PageSize', 'Keyword', 'CategoryID', 'Status', 'StockID', 'OrderID') if k in request.args}
    query['StoreID'] = g.store_id
    try:
        res = requests.request(method, f'{base}/microapp_api/admin/retail/v1/{path}',
            params=query if method == 'GET' else None,
            json=payload if method != 'GET' else None,
            headers={'X-GAMBIT-INTERNAL-TOKEN': token}, timeout=25)
        res.raise_for_status()
        result = res.json()
        if not isinstance(result, dict) or 'Code' not in result:
            raise ValueError('invalid upstream response')
        if result['Code'] != 0:
            return jsonify(Code=result['Code'], Message=result.get('Msg') or '操作失败'), 400
        return jsonify(Code=0, Data=result.get('Data'))
    except (requests.RequestException, ValueError):
        current_app.logger.warning('商城后端响应异常: %s %s', method, path)
        return jsonify(Code=502, Message='响应超时或异常，请刷新核对；重试将使用同一请求编号'), 502

@bp.get('/categories')
@login_required('retail-catalog', 'retail-management')
def categories(): return proxy('categories')

@bp.put('/categories')
@login_required('retail-catalog')
def save_category(): return proxy('categories', 'PUT')

@bp.get('/products')
@login_required('retail-catalog', 'retail-management')
def products(): return proxy('products')

@bp.get('/products/<int:product_id>')
@login_required('retail-catalog', 'retail-management')
def product(product_id): return proxy(f'products/{product_id}')

@bp.put('/products')
@login_required('retail-catalog')
def save_product(): return proxy('products', 'PUT')

@bp.put('/products/<int:product_id>/sort')
@login_required('retail-catalog')
def save_product_sort(product_id): return proxy(f'products/{product_id}/sort', 'PUT')

@bp.put('/stock')
@login_required('retail-management')
def save_stock(): return proxy('stock', 'PUT')

@bp.get('/stock/movements')
@login_required('retail-management')
def movements(): return proxy('stock/movements')

@bp.route('/policy', methods=['GET', 'PUT'])
@login_required('retail-management')
def policy(): return proxy('policy', request.method)

@bp.route('/coupon-templates', methods=['GET', 'PUT'])
@login_required('retail-management')
def coupon_templates(): return proxy('coupon-templates', request.method)

@bp.post('/coupons/issue')
@login_required('retail-management')
def issue_coupon(): return proxy('coupons/issue', 'POST')

@bp.get('/orders')
@login_required('retail-orders')
def orders(): return proxy('orders')

@bp.get('/orders/<int:order_id>')
@login_required('retail-orders')
def order(order_id): return proxy(f'orders/{order_id}')

@bp.post('/action')
@login_required('retail-orders')
def action():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict) or data.get('Action') not in ('ship', 'pickup'):
        abort(400, description='不支持的履约操作')
    return proxy('action', 'POST')

@bp.get('/after-sales')
@login_required('retail-orders')
def after_sales(): return proxy('after-sales')

def require_refund_permission():
    if not can_page('retail-management', g.store_id) or not can_page('refunds', g.store_id):
        abort(403, description='商城售后审核需要商城管理和退款管理权限')

@bp.post('/after-sales/review')
@login_required('retail-orders')
def review():
    require_refund_permission()
    return proxy('after-sales/review', 'POST')

@bp.post('/after-sales/<int:case_id>/retry-refund')
@login_required('retail-orders')
def retry_refund(case_id):
    require_refund_permission()
    return proxy(f'after-sales/{case_id}/retry-refund', 'POST')

@bp.post('/images')
@login_required('retail-catalog')
def image():
    from app.api.v1.point import _validate_and_upload_image
    file = request.files.get('file')
    if not file:
        return jsonify(Code=400, Message='请选择商品图片'), 400
    try:
        return jsonify(Code=0, Data={'URL': _validate_and_upload_image(file)})
    except ValueError as exc:
        return jsonify(Code=400, Message=str(exc)), 400


@bp.get('/recipients')
@login_required('retail-management')
def recipients():
    """Minimal recipient lookup; does not grant the full users/finance page."""
    from app.models import User
    from app.utils.crypto import encrypt_phone, decrypt_phone
    import re
    keyword = request.args.get('Keyword', '').strip()
    if len(keyword) < 2 or len(keyword) > 60:
        return jsonify(Code=0, Data={'Items': []})
    query = User.query.filter(User.deleted_at.is_(None))
    if keyword.startswith('#') and keyword[1:].isdigit():
        query = query.filter(User.id == int(keyword[1:]))
    elif re.fullmatch(r'\+?\d{7,15}', keyword):
        encrypted = encrypt_phone(keyword)
        if not encrypted:
            return jsonify(Code=503, Message='手机号查询暂不可用，请用昵称或用户编号查询'), 503
        query = query.filter(User.phone_number == encrypted)
    else:
        query = query.filter(User.nick_name.contains(keyword, autoescape=True))
    items = []
    for user in query.order_by(User.id.desc()).limit(20):
        phone = decrypt_phone(user.phone_number) if user.phone_number else ''
        items.append({'Id': user.id, 'NickName': user.nick_name, 'PhoneNumber': '***' + phone[-4:] if phone else ''})
    return jsonify(Code=0, Data={'Items': items})
