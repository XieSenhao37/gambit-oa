from functools import wraps
import traceback
import uuid
from pathlib import Path
from werkzeug.exceptions import HTTPException
from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import and_, func, or_

from app.models import PayOrder, PointAccount, User, WalletAccount
from app import db
from datetime import datetime
from app.utils.crypto import decrypt_phone, encrypt_phone
from app.middlewares.auth import login_required

user_bp = Blueprint('user', __name__)

USER_LIST_SORT_FIELDS = {
    'PointBalance': 'point_balance',
    'WalletBalance': 'wallet_balance',
    'TotalConsumptionAmount': 'total_consumption_amount',
}


def _user_list_errors(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except HTTPException:
            raise
        except Exception as exc:
            db.session.rollback()
            error_id=uuid.uuid4().hex[:12]
            original=getattr(exc,'orig',exc)
            args_value=getattr(original,'args',())
            code=args_value[0] if args_value and isinstance(args_value[0],int) else None
            # Frames only: never log SQL parameters, phone numbers or credential-bearing messages.
            frames=' > '.join(f'{Path(f.filename).name}:{f.lineno}:{f.name}' for f in traceback.extract_tb(exc.__traceback__))
            current_app.logger.error('user_list_failed error_id=%s type=%s database_code=%s frames=%s',error_id,type(exc).__name__,code,frames)
            return jsonify(Code=500,Message='用户列表加载失败，请提供错误编号以核对服务端日志',ErrorId=error_id,Data=None),500
    return wrapped


def _format_user_time(value):
    # PyMySQL returns zero/invalid MySQL DATETIME values as strings.
    # A single legacy date must not crash the entire customer list.
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            current_app.logger.warning('user_list invalid_datetime omitted')
            return None
    return value.strftime('%Y-%m-%d %H:%M:%S')


def _consumption_subquery():
    return db.session.query(
        PayOrder.open_id.label('open_id'),
        func.sum(PayOrder.amount).label('total_consumption_amount'),
    ).filter(
        PayOrder.deleted_at.is_(None),
        PayOrder.pay_status == 1,
        or_(
            PayOrder.play_order_id.isnot(None),
            PayOrder.catering_id.isnot(None),
        ),
    ).group_by(PayOrder.open_id).subquery()


@user_bp.route('/list', methods=['GET'])
@login_required('users')
@_user_list_errors
def get_user_list():
    page = request.args.get('Current', 1, type=int)  # 改为小写 current
    page_size = request.args.get('PageSize', 10, type=int)  # 改为小写 pageSize
    id = request.args.get('Id', type=int)
    open_id = request.args.get('OpenId')
    role = request.args.get('Role', type=int)
    user_type = request.args.get('UserType', type=int)
    nick_name = request.args.get('NickName')
    phone_number = request.args.get('PhoneNumber')

    # 添加月卡用户筛选
    is_month_card_user = request.args.get('IsMonthCardUser')
    sort_field = request.args.get('SortField')
    sort_order = request.args.get('SortOrder', 'asc')

    if sort_field not in USER_LIST_SORT_FIELDS:
        sort_field = None
    if sort_order not in ('asc', 'desc'):
        sort_order = 'asc'
    if sort_field is None:
        sort_order = 'asc'

    consumption_subquery = _consumption_subquery()
    point_balance = func.coalesce(PointAccount.balance, 0).label('point_balance')
    wallet_balance = func.coalesce(WalletAccount.balance, 0).label('wallet_balance')
    total_consumption_amount = func.coalesce(
        consumption_subquery.c.total_consumption_amount,
        0,
    ).label('total_consumption_amount')

    # 构建查询条件
    query = db.session.query(
        User,
        point_balance,
        wallet_balance,
        total_consumption_amount,
    ).outerjoin(
        PointAccount,
        and_(
            PointAccount.open_id == User.open_id,
            PointAccount.deleted_at.is_(None),
        ),
    ).outerjoin(
        WalletAccount,
        and_(
            WalletAccount.open_id == User.open_id,
            WalletAccount.deleted_at.is_(None),
        ),
    ).outerjoin(
        consumption_subquery,
        consumption_subquery.c.open_id == User.open_id,
    ).filter(User.deleted_at.is_(None))

    from flask import g
    if not g.staff.headquarters:
        from app.models import PlayOrder, Catering
        from app.utils.store import get_request_store_id
        sid = get_request_store_id()
        query = query.filter(or_(User.registered_store_id == sid,
            User.open_id.in_(db.session.query(PlayOrder.open_id).filter(PlayOrder.store_id == sid)),
            User.open_id.in_(db.session.query(Catering.open_id).filter(Catering.store_id == sid))))

    if id:
        query = query.filter(User.id == id)
    if open_id:
        query = query.filter(User.open_id == open_id)
    if role is not None:
        query = query.filter(User.role == role)
    if user_type is not None:
        query = query.filter(User.user_type == user_type)
    if nick_name:
        query = query.filter(User.nick_name.like(f'%{nick_name}%'))
    if phone_number:
        # 对输入的手机号进行加密，然后用加密后的值进行筛选
        encrypted_phone = encrypt_phone(phone_number)
        query = query.filter(User.phone_number == encrypted_phone)
    # 月卡用户筛选逻辑：有效月卡需有到期时间且尚未到期。
    if is_month_card_user is not None:
        if is_month_card_user == '1':  # 是月卡用户
            query = query.filter(
                User.month_card_expire.isnot(None),
                User.month_card_expire > datetime.now(),
            )
        elif is_month_card_user == '0':  # 不是月卡用户
            query = query.filter(or_(
                User.month_card_expire.is_(None),
                User.month_card_expire <= datetime.now(),
            ))

    sort_columns = {
        'PointBalance': point_balance,
        'WalletBalance': wallet_balance,
        'TotalConsumptionAmount': total_consumption_amount,
    }
    sort_column = sort_columns.get(sort_field, User.id)
    query = query.order_by(
        sort_column.asc() if sort_order == 'asc' else sort_column.desc()
    )
    if sort_field:
        query = query.order_by(User.id.asc())

    # 分页查询
    pagination = query.paginate(
        page=page,
        per_page=page_size,
        error_out=False
    )

    # 格式化返回数据
    users = [{
        'Id': user.id,
        'OpenId': user.open_id,
        'UserType': user.user_type,
        'Role': user.role,
        'NickName': user.nick_name,
        'Gender': user.gender,
        'PhoneNumber': decrypt_phone(user.phone_number) if user.phone_number else None,
        'MonthCardExpire': _format_user_time(user.month_card_expire),
        'PointBalance': int(point_balance_value or 0),
        'WalletBalance': int(wallet_balance_value or 0),
        'TotalConsumptionAmount': int(total_consumption_value or 0),
        'CreatedAt': _format_user_time(user.created_at),
        'UpdatedAt': _format_user_time(user.updated_at)
    } for user, point_balance_value, wallet_balance_value, total_consumption_value in pagination.items]

    return jsonify({
        'Code': 0,
        'Message': 'success',
        'Data': {
            'Total': pagination.total,
            'CurrentPage': pagination.page,
            'PageSize': page_size,
            'Items': users
        }
    })

@user_bp.route('/<int:user_id>', methods=['PUT'])
@login_required('staff-access')
def update_user(user_id):
    return jsonify(Code=400, Message='请在员工及门店授权管理中修改角色', Data=None), 400
