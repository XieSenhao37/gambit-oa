import hashlib
import json
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request
from sqlalchemy import case, func
from sqlalchemy.orm import undefer

from app import db
from app.middlewares.auth import login_required
from app.models import CouponPromotion, CouponRecord, User


bp = Blueprint('coupon', __name__)
BEIJING = timezone(timedelta(hours=8))
STAFF_ROLES = {1, 2, 125, 126, 127}
REFERRAL_PROMOTION_ID = 11
TERM_FIELDS = {
    'ActivityName': 'activity_name',
    'Title': 'title',
    'CouponType': 'coupon_type',
    'Amount': 'amount',
    'MinimumAmount': 'minimum_amount',
    'Expire': 'expire',
    'StartDate': 'start_date',
    'EndDate': 'end_date',
    'CanReReceive': 'can_re_receive',
    'ApplicableScenes': 'applicable_scenes',
    'Description': 'description',
}


def now():
    return datetime.now(BEIJING).replace(tzinfo=None, microsecond=0)


def date_text(value):
    return value.isoformat(sep=' ', timespec='seconds') if value else None


def coupon_config(coupon):
    result = {key: getattr(coupon, field) for key, field in TERM_FIELDS.items()}
    result.update(
        Count=coupon.count, ControlRoles=coupon.control_roles,
        StartDate=date_text(coupon.start_date), EndDate=date_text(coupon.end_date),
    )
    return result


def revision(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def issued_records(promotion_id):
    return CouponRecord.query.filter_by(promotion_id=promotion_id, deleted_at=None)


def activity_item(coupon, issued, used, current):
    config = coupon_config(coupon)
    status = 'scheduled' if current < coupon.start_date else 'active' if current < coupon.end_date else 'ended'
    return {
        **config, 'ID': coupon.id, 'Status': status, 'Revision': revision(config),
        'Issued': issued, 'Used': used, 'Reserved': coupon.raffle_reserved,
        'Available': max(0, coupon.count - issued - coupon.raffle_reserved),
        'TermsLocked': issued > 0 or coupon.raffle_reserved > 0,
        'SystemLocked': coupon.id == REFERRAL_PROMOTION_ID,
    }


def page_number():
    page = request.args.get('Page', default=1, type=int)
    return max(1, min(page, 10000))


def error(message, status=400):
    return jsonify(Code=status, Message=message), status


@bp.get('/activities')
@login_required('coupons')
def activities():
    current = now()
    query = CouponPromotion.query.options(undefer(CouponPromotion.raffle_reserved)).filter_by(deleted_at=None)
    keyword = request.args.get('Keyword', '').strip()[:30]
    if keyword:
        query = query.filter(CouponPromotion.title.contains(keyword, autoescape=True) |
                             CouponPromotion.activity_name.contains(keyword, autoescape=True))
    status = request.args.get('Status')
    if status == 'active':
        query = query.filter(CouponPromotion.start_date <= current, CouponPromotion.end_date > current)
    elif status == 'scheduled':
        query = query.filter(CouponPromotion.start_date > current)
    elif status == 'ended':
        query = query.filter(CouponPromotion.end_date <= current)
    page = query.order_by(CouponPromotion.id.desc()).paginate(page=page_number(), per_page=20, error_out=False)
    ids = [coupon.id for coupon in page.items]
    totals = {
        id: (count, used) for id, count, used in db.session.query(
            CouponRecord.promotion_id, func.count(CouponRecord.id),
            func.sum(case((CouponRecord.status == 1, 1), else_=0))
        ).filter(CouponRecord.promotion_id.in_(ids), CouponRecord.deleted_at.is_(None)).
        group_by(CouponRecord.promotion_id).all()
    } if ids else {}
    return jsonify(Code=0, Data={
        'Items': [activity_item(coupon, *totals.get(coupon.id, (0, 0)), current) for coupon in page.items],
        'Total': page.total,
    })


def number(data, key, label, minimum, maximum):
    value = data.get(key)
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f'{label}须为 {minimum}–{maximum} 的整数')
    return value


def label(data, key, name, max_length, required=True):
    value = data.get(key, '')
    if not isinstance(value, str) or len(value.strip()) > max_length or (required and not value.strip()):
        raise ValueError(f'请填写有效的{name}（最多 {max_length} 字）')
    return value.strip()


def choice_list(data, key, choices, name, required=True):
    values = data.get(key)
    if not isinstance(values, list) or (required and not values) or any(
        type(value) is not int or value not in choices for value in values
    ):
        raise ValueError(f'请选择有效的{name}')
    return sorted(set(values))


def dates(data):
    try:
        start, end = (datetime.fromisoformat(data[key]) for key in ('StartDate', 'EndDate'))
    except (KeyError, TypeError, ValueError):
        raise ValueError('请选择发放起止时间') from None
    if start.tzinfo or end.tzinfo:
        raise ValueError('请使用北京时间填写发放时间')
    start, end = start.replace(microsecond=0), end.replace(microsecond=0)
    if not start < end or start.year < 2000 or end.year > 2099:
        raise ValueError('发放结束时间须晚于开始时间')
    return start, end


def terms(data):
    kind = number(data, 'CouponType', '券类型', 0, 3)
    minimum = number(data, 'MinimumAmount', '使用门槛', 0, 100000000)
    amount = {0: (1, 2147483647), 1: (1, 100000000), 2: (1, 99), 3: (0, 0)}[kind]
    scenes = choice_list(data, 'ApplicableScenes', {0, 1}, '适用场景')
    if kind == 0 and scenes != [0]:
        raise ValueError('时长券仅适用于桌游')
    start, end = dates(data)
    return dict(
        activity_name=label(data, 'ActivityName', '活动名称', 30),
        title=label(data, 'Title', '券名称', 30), coupon_type=kind,
        amount=number(data, 'Amount', '优惠值', *amount), minimum_amount=minimum,
        expire=number(data, 'Expire', '领取后有效时长（秒）', 0, 2147483647),
        start_date=start, end_date=end, applicable_scenes=scenes,
        can_re_receive=number(data, 'CanReReceive', '分享领取规则', 0, 1),
        description=label(data, 'Description', '内部备注', 255, required=False) or None,
    )


@bp.post('/activities')
@bp.put('/activities/<int:promotion_id>')
@login_required('coupons')
def save_activity(promotion_id=None):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error('请求格式错误')
    if promotion_id == REFERRAL_PROMOTION_ID:
        return error('邀请奖励券由邀请流程管理', 409)
    current = now()
    try:
        count = number(data, 'Count', '总名额', 1, 2147483647)
        roles = choice_list(data, 'ControlRoles', STAFF_ROLES, '发券角色', required=False)
        if promotion_id is None:
            config = terms(data)
            if config['end_date'] <= current:
                return error('发放结束时间须晚于当前时间')
            coupon = CouponPromotion(**config, count=count, control_roles=roles,
                                     created_at=current, updated_at=current)
            db.session.add(coupon)
        else:
            coupon = CouponPromotion.query.filter_by(id=promotion_id, deleted_at=None).with_for_update().first()
            if coupon is None:
                db.session.rollback()
                return error('优惠券活动不存在', 404)
            if data.get('Revision') != revision(coupon_config(coupon)):
                db.session.rollback()
                return error('优惠券活动已更新，请刷新后重试', 409)
            # Read current issuance after acquiring the same row lock used by Go.
            issued = db.session.query(func.count(CouponRecord.id)).filter(
                CouponRecord.promotion_id == coupon.id, CouponRecord.deleted_at.is_(None),
            ).with_for_update().scalar()
            reserved = coupon.raffle_reserved
            if count != coupon.count and count < issued + reserved:
                db.session.rollback()
                return error(f'总名额至少为 {issued + reserved} 份（已发放 {issued}，抽奖预留 {reserved}）', 409)
            if issued or reserved:
                original = coupon_config(coupon)
                if any(key in data and data[key] != original[key] for key in TERM_FIELDS):
                    db.session.rollback()
                    return error('已有发放或预留，只能调整总名额和发券角色，请刷新后重试', 409)
            else:
                # An older form may still submit quota and roles only after all reservations are released.
                if any(key in data for key in TERM_FIELDS):
                    for key, value in terms(data).items():
                        setattr(coupon, key, value)
            coupon.count, coupon.control_roles, coupon.updated_at = count, roles, current
        db.session.flush()
        id = coupon.id
        db.session.commit()
        return jsonify(Code=0, Data={'ID': id})
    except ValueError as exc:
        db.session.rollback()
        return error(str(exc))


@bp.get('/activities/<int:promotion_id>/records')
@login_required('coupons')
def records(promotion_id):
    coupon = CouponPromotion.query.filter_by(id=promotion_id, deleted_at=None).first()
    if coupon is None:
        return error('优惠券活动不存在', 404)
    page = issued_records(promotion_id).options(undefer(CouponRecord.raffle_entry_id)).order_by(
        CouponRecord.id.desc()
    ).paginate(page=page_number(), per_page=20, error_out=False)
    users = {}
    if page.items:
        open_ids = {entry.open_id for entry in page.items}
        for open_id, id, name in db.session.query(User.open_id, User.id, User.nick_name).filter(
            User.open_id.in_(open_ids), User.deleted_at.is_(None)
        ).order_by(User.id):
            users.setdefault(open_id, (id, name))
    current = now()
    items = []
    for entry in page.items:
        user_id, name = users.get(entry.open_id, (None, None))
        if entry.raffle_entry_id is not None:
            source = '抽奖'
        elif promotion_id == REFERRAL_PROMOTION_ID:
            source = '邀请活动'
        elif entry.share_id:
            source = '分享领取'
        else:
            source = '员工发放' if entry.issuer else '直接领取'
        expired = (entry.expire_at is not None and entry.expire_at <= current) or (
            entry.raffle_entry_id is None and coupon.end_date <= current
        )
        items.append({
            'ID': entry.id, 'UserID': user_id, 'NickName': name, 'Source': source,
            'ReceivedAt': date_text(entry.received_at), 'ExpireAt': date_text(entry.expire_at),
            'UsedAt': date_text(entry.used_at),
            'Status': '已使用' if entry.status == 1 else '已过期' if expired else '未使用',
        })
    return jsonify(Code=0, Data={'Items': items, 'Total': page.total})
