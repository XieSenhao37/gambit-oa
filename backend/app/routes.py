from flask import Blueprint, jsonify
from app.api.v1.banner import banner_bp
from app.api.v1.promotion import promotion_bp
from app.api.v1.event import event_bp
from app.api.v1.user import user_bp
from app.api.v1.order import order_bp
from app.api.v1.game import game_bp
from app.api.v1.auth import auth_bp
from app.api.v1.catering import catering_bp
from app.api.v1.refund import refund_bp
from app.api.v1.dish import dish_bp
from app.api.v1.stats import stats_bp
from app.api.v1.wallet import wallet_bp
from app.api.v1.point import point_bp
from app.api.v1.store import store_bp
from app.api.v1.month_card import month_card_bp

# 主蓝图，用于基础路由
main = Blueprint('main', __name__)

# API v1 蓝图，用于所有 API 路由
api_v1 = Blueprint('api_v1', __name__, url_prefix='/admin_api')

# 注册各个模块的路由
api_v1.register_blueprint(banner_bp, url_prefix="/banner/v1")
api_v1.register_blueprint(promotion_bp, url_prefix="/promotion/v1")
api_v1.register_blueprint(event_bp, url_prefix="/event/v1")
api_v1.register_blueprint(user_bp, url_prefix='/user/v1')
api_v1.register_blueprint(order_bp, url_prefix='/order/v1')
api_v1.register_blueprint(game_bp, url_prefix='/game/v1')
api_v1.register_blueprint(auth_bp, url_prefix='/auth/v1')
api_v1.register_blueprint(catering_bp, url_prefix='/catering/v1')
api_v1.register_blueprint(refund_bp, url_prefix='/refund/v1')
api_v1.register_blueprint(dish_bp, url_prefix='/dish/v1')
api_v1.register_blueprint(stats_bp, url_prefix='/stats/v1')
api_v1.register_blueprint(wallet_bp, url_prefix='/wallet/v1')
api_v1.register_blueprint(point_bp, url_prefix='/point/v1')
api_v1.register_blueprint(store_bp, url_prefix='/store/v1')
api_v1.register_blueprint(month_card_bp, url_prefix='/month-card/v1')

@main.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        "status": "healthy",
        "message": "Service is running"
    }), 200
from app.api.v1.staff_access import staff_access_bp
api_v1.register_blueprint(staff_access_bp, url_prefix="/staff-access/v1")

from app.api.v1.settlement import settlement_bp
api_v1.register_blueprint(settlement_bp, url_prefix='/settlement/v1')

@api_v1.before_request
def enforce_api_registration():
    from flask import request, current_app, abort
    if request.method == 'OPTIONS':
        return
    public = {'api_v1.auth.status', 'api_v1.auth.send_code', 'api_v1.auth.login'}
    if request.endpoint in public:
        return
    view = current_app.view_functions.get(request.endpoint)
    if not view or not getattr(view, 'oa_pages', None):
        abort(403, description='接口尚未配置页面权限')
