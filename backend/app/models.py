from app import db
from datetime import datetime
from sqlalchemy.orm import foreign
import base64


class Store(db.Model):
    __tablename__ = 'stores'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='门店 id')
    code = db.Column(db.String(32), nullable=False, unique=True, comment='门店编码')
    name = db.Column(db.String(60), nullable=False, comment='门店名称')
    status = db.Column(db.SmallInteger, nullable=False, default=1, comment='状态')
    sort = db.Column(db.Integer, nullable=False, default=0, comment='排序')
    address = db.Column(db.String(255), comment='地址')
    latitude = db.Column(db.Numeric(10, 7), comment='纬度')
    longitude = db.Column(db.Numeric(10, 7), comment='经度')
    wifi_ssid = db.Column(db.String(120), comment='WiFi 名称')
    wifi_password = db.Column(db.String(120), comment='WiFi 密码')
    customer_service_phone = db.Column(db.String(60), comment='客服电话')
    customer_service_wechat = db.Column(db.String(120), comment='客服微信')
    business_hours = db.Column(db.String(120), comment='营业时间')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='用户表 id')
    open_id = db.Column(db.String(60), index=True, comment='小程序 open_id')
    user_type = db.Column(db.Integer, comment='用户类型，0-微信小程序用户')
    role = db.Column(db.Integer, nullable=False, default=0, comment='用户身份，0-普通用户，1-店员，2-兼职，126-管理员，127-超级管理员')
    nick_name = db.Column(db.String(60), comment='昵称')
    avatar = db.Column(db.String(255), comment='头像')
    gender = db.Column(db.Integer, comment='性别，0-未知，1-男性，2-女性')
    phone_number = db.Column(db.String(50), comment='手机号')
    month_card_id = db.Column(db.Integer, comment='月卡id')
    partner_id = db.Column(db.Integer, comment='搭子id')
    month_card_expire = db.Column(db.DateTime, comment='月卡过期时间')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')
    birthday = db.Column(db.DateTime, comment='生日')
    phone_number_change_time = db.Column(db.DateTime, comment='下次可修改手机号的时间')
    registered_store_id = db.Column(db.Integer, comment='首次注册来源门店')
    registered_store_source = db.Column(db.String(32), comment='注册来源门店口径')
    registered_store_distance_m = db.Column(db.Integer, comment='注册时距离门店米数')

    # 关联订单
    play_orders = db.relationship(
        'PlayOrder',
        primaryjoin="and_(User.open_id==foreign(PlayOrder.open_id), PlayOrder.deleted_at.is_(None))",
        backref='user',
        uselist=True,
        lazy='select'
    )



class PlayOrder(db.Model):
    __tablename__ = 'play_orders'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='游玩订单表 id')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')
    store_id = db.Column(db.Integer, nullable=False, default=1, comment='游玩发生门店')
    open_id = db.Column(db.String(60), nullable=False, comment='用户id')
    in_time = db.Column(db.DateTime, nullable=False, comment='入场时间')
    out_time = db.Column(db.DateTime, comment='出场时间')
    play_time = db.Column(db.Integer, comment='游玩时长，单位小时')
    amount = db.Column(db.Integer, comment='订单金额，单位分')
    settle_status = db.Column(db.Integer, comment='结算状态，0-待结算，1-已结算')
    billing_mode = db.Column(db.Integer, nullable=False, default=0, comment='计费模式，0-线上，1-线下，2-月卡')
    comment = db.Column(db.Text, comment='备注')
    unit_price = db.Column(db.Integer, comment='游玩单价，单位分')


class BoardGame(db.Model):
    __tablename__ = 'board_games'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='ID')
    name = db.Column(db.String(255), nullable=False, comment='名称')
    gstone_score = db.Column(db.Numeric(3,1), nullable=False, comment='集石评分')
    gstone_rank = db.Column(db.Integer, nullable=False, comment='集石排名')
    supported_players = db.Column(db.JSON, nullable=False, comment='支持人数列表')
    recommended_players = db.Column(db.JSON, nullable=False, comment='推荐人数列表')
    cover_url = db.Column(db.String(500), nullable=False, comment='封面图URL')
    complexity = db.Column(db.Integer, nullable=False, comment='上手难度(1-10级)')
    play_time = db.Column(db.Integer, nullable=False, comment='人均时长(分钟)')
    setup_time = db.Column(db.String(50), nullable=False, comment='设置时长')
    language_level = db.Column(db.String(50), nullable=False, comment='语言要求')
    description = db.Column(db.Text, nullable=False, comment='游戏简介')
    picture_list = db.Column(db.JSON, comment='图片列表')
    designer = db.Column(db.JSON, nullable=False, comment='设计师列表')
    publisher = db.Column(db.JSON, nullable=False, comment='出版商列表')
    publish_language = db.Column(db.JSON, nullable=False, comment='出版语言列表')
    publish_year = db.Column(db.SmallInteger, nullable=False, comment='出版年份')
    categories = db.Column(db.JSON, nullable=False, comment='游戏类别列表')
    modes = db.Column(db.JSON, nullable=False, comment='游戏模式列表')
    mechanisms = db.Column(db.JSON, comment='游戏机制列表')
    themes = db.Column(db.JSON, comment='游戏主题列表')
    table_requirement = db.Column(db.String(50), comment='桌面要求')
    portability = db.Column(db.String(50), comment='便携程度')
    suitable_age = db.Column(db.String(50), comment='适合年龄')
    rule_list = db.Column(db.JSON, comment='规则信息列表')
    count = db.Column(db.Integer, nullable=False, default=1, comment='数量')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment='修改时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')


class BoardGameStoreInventory(db.Model):
    __tablename__ = 'board_game_store_inventories'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='ID')
    store_id = db.Column(db.Integer, nullable=False, comment='门店 id')
    board_game_id = db.Column(db.Integer, db.ForeignKey('board_games.id'), nullable=False, comment='桌游 id')
    count = db.Column(db.Integer, nullable=False, default=0, comment='门店库存数量')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')

    board_game = db.relationship('BoardGame', foreign_keys=[board_game_id], lazy='joined')


class GroupActivity(db.Model):
    __tablename__ = 'group_activities'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='组局活动 id')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')
    creator_open_id = db.Column(db.String(60), nullable=False, comment='发起人 OpenID')
    organizer_participates = db.Column(db.Boolean, nullable=False, default=True, comment='发起人是否参与')
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False, comment='活动门店')
    activity_type_id = db.Column(db.Integer, nullable=False, comment='活动类型')
    title = db.Column(db.String(120), nullable=False, comment='活动名称')
    content = db.Column(db.Text, nullable=False, comment='活动内容')
    cover_url = db.Column(db.String(500), nullable=False, comment='活动封面')
    start_time = db.Column(db.DateTime, nullable=False, comment='开始时间')
    expected_end_time = db.Column(db.DateTime, comment='预计结束时间')
    capacity_enabled = db.Column(db.Boolean, nullable=False, default=False, comment='是否限制报名人数')
    min_participants = db.Column(db.Integer, comment='最低发车人数')
    max_participants = db.Column(db.Integer, comment='至多人数')
    intent_deposit_enabled = db.Column(db.Boolean, nullable=False, default=False, comment='是否开启意向金')
    intent_deposit_amount = db.Column(db.Integer, nullable=False, default=0, comment='意向金金额，单位分')
    group_qr_code_url = db.Column(db.String(500), comment='公开群二维码')
    show_contact = db.Column(db.Boolean, nullable=False, default=False, comment='是否公开联系方式')
    contact_phone = db.Column(db.String(32), comment='公开联系电话')
    status = db.Column(db.SmallInteger, nullable=False, default=1, comment='状态：1-已发布，2-已取消，3-已结束')

    store = db.relationship('Store', foreign_keys=[store_id], lazy='joined')
    participants = db.relationship(
        'GroupActivityParticipant',
        back_populates='activity',
        lazy='select',
    )


class GroupActivityParticipant(db.Model):
    __tablename__ = 'group_activity_participants'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='组局报名记录 id')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')
    activity_id = db.Column(
        db.Integer,
        db.ForeignKey('group_activities.id'),
        nullable=False,
        comment='组局活动 id',
    )
    open_id = db.Column(db.String(60), nullable=False, comment='报名用户 OpenID')
    is_organizer = db.Column(db.Boolean, nullable=False, default=False, comment='是否为发起人')
    status = db.Column(db.SmallInteger, nullable=False, default=0, comment='状态：0-待支付，1-已报名，2-已取消')
    contact_type = db.Column(db.String(16), comment='报名联系方式类型')
    contact_value = db.Column(db.String(64), comment='报名联系方式')
    wallet_recharge_order_id = db.Column(db.Integer, comment='意向金储值订单 id')
    pay_order_id = db.Column(db.Integer, comment='微信支付订单 id')
    registered_at = db.Column(db.DateTime, comment='报名成功时间')
    cancelled_at = db.Column(db.DateTime, comment='取消时间')

    activity = db.relationship(
        'GroupActivity',
        back_populates='participants',
        foreign_keys=[activity_id],
        lazy='joined',
    )
    user = db.relationship(
        'User',
        primaryjoin='foreign(GroupActivityParticipant.open_id)==User.open_id',
        uselist=False,
        viewonly=True,
        lazy='select',
    )


class PayOrder(db.Model):
    __tablename__ = 'pay_orders'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='支付订单表 id')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')
    store_id = db.Column(db.Integer, comment='消费发生门店')
    open_id = db.Column(db.String(60), nullable=False, comment='用户id')
    play_order_id = db.Column(db.Integer, db.ForeignKey('play_orders.id'), comment='游玩订单id')
    month_card_order_id = db.Column(db.Integer, comment='月卡订单id')
    wallet_recharge_order_id = db.Column(db.Integer, comment='储值充值订单id')
    group_activity_participant_id = db.Column(db.Integer, comment='组局报名记录id')
    prepay_id = db.Column(db.String(255), comment='预支付订单id')
    pay_id = db.Column(db.String(255), comment='支付订单id')
    amount = db.Column(db.Integer, nullable=False, comment='支付金额，单位分')
    wallet_amount = db.Column(db.Integer, nullable=False, default=0, comment='储值钱包支付金额，单位分')
    wechat_amount = db.Column(db.Integer, nullable=False, default=0, comment='微信支付金额，单位分')
    discount_amount = db.Column(db.Integer, comment='优惠金额，单位分')
    total_amount = db.Column(db.Integer, comment='优惠前总金额，单位分')
    refund_amount = db.Column(db.Integer, comment='退款金额，单位分')
    wallet_refund_amount = db.Column(db.Integer, nullable=False, default=0, comment='已退回钱包金额，单位分')
    wechat_refund_amount = db.Column(db.Integer, nullable=False, default=0, comment='已微信退款金额，单位分')
    pay_status = db.Column(db.Integer, comment='支付状态，0-待支付，1-已支付，2-已关闭，3-已退款')
    pay_type = db.Column(db.Integer, comment='支付类型，0-游玩支付，1-月卡支付，2-其他支付')
    description = db.Column(db.Text, comment='支付描述信息')
    expire_time = db.Column(db.DateTime, comment='订单过期时间')
    pay_end_time = db.Column(db.DateTime, comment='支付完成时间')
    catering_id = db.Column(db.Integer, comment='餐饮订单id')
    coupon_id = db.Column(db.Integer, comment='优惠券记录 id')
    order_id = db.Column(db.String(255), comment='商户订单号')


class MonthCardOrder(db.Model):
    __tablename__ = 'month_card_orders'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='月卡订单 id')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')
    open_id = db.Column(db.String(60), nullable=False, comment='用户 OpenID')
    open_period = db.Column(db.Integer, nullable=False, comment='开通周期')
    request_key = db.Column(db.String(64), unique=True)
    duration_days = db.Column(db.Integer, nullable=False, default=0, server_default='0', comment='卡期快照天数；0为旧日历月，新开每期30天')
    amount = db.Column(db.Integer, nullable=False, comment='订单金额，单位分')
    open_type = db.Column(db.Integer, nullable=False, comment='开通类型')
    settle_status = db.Column(db.Integer, nullable=False, comment='结算状态')
    source = db.Column(db.String(32), nullable=False, default='wechat', comment='开通来源')
    operator = db.Column(db.String(64), comment='OA 操作人标识')
    external_no = db.Column(db.String(128), comment='外部凭证号')
    store_id = db.Column(db.Integer, comment='操作门店')
    effective_at = db.Column(db.DateTime, comment='本次权益生效基准时间')
    remark = db.Column(db.String(255), comment='运营备注')


class CouponPromotion(db.Model):
    __tablename__ = 'coupon_promotions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='券活动 id')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')
    activity_name = db.Column(db.String(30), nullable=False, comment='券活动名称')
    coupon_type = db.Column(db.Integer, nullable=False, comment='券类型')
    title = db.Column(db.String(30), nullable=False, comment='券标题')
    amount = db.Column(db.Integer, nullable=False, comment='券额度')
    minimum_amount = db.Column(db.Integer, nullable=False, comment='券门槛额度')
    count = db.Column(db.Integer, nullable=False, comment='券数量')
    expire = db.Column(db.Integer, nullable=False, comment='券有效期')
    start_date = db.Column(db.DateTime, nullable=False, comment='活动开始日期')
    end_date = db.Column(db.DateTime, nullable=False, comment='活动截止日期')
    control_roles = db.Column(db.JSON, nullable=False, comment='可操作角色')
    can_re_receive = db.Column(db.Integer, nullable=False, comment='是否可重复领取')
    applicable_scenes = db.Column(db.JSON, comment='适用场景')
    description = db.Column(db.String(255), comment='描述')


class CouponRecord(db.Model):
    __tablename__ = 'coupon_records'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='券记录 id')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')
    promotion_id = db.Column(db.Integer, nullable=False, comment='关联活动 id')
    open_id = db.Column(db.String(60), nullable=False, comment='领取人 OpenID')
    status = db.Column(db.Integer, nullable=False, comment='券状态')
    expire_at = db.Column(db.DateTime, comment='过期时间')
    received_at = db.Column(db.DateTime, nullable=False, comment='领取时间')
    used_at = db.Column(db.DateTime, comment='使用时间')
    verified_store_id = db.Column(db.Integer, comment='手动亮码核销门店')
    verifier_open_id = db.Column(db.String(60), comment='手动亮码核销员工')
    issuer = db.Column(db.String(60), comment='发放人')
    share_id = db.Column(db.String(255), comment='分享渠道 id')


class ReferralRecord(db.Model):
    __tablename__ = 'referral_records'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='老带新记录 id')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')
    inviter_open_id = db.Column(db.String(60), nullable=False, comment='邀请人 OpenID')
    invitee_open_id = db.Column(db.String(60), nullable=False, comment='被邀请人 OpenID')
    status = db.Column(db.Integer, nullable=False, default=0, comment='状态')
    new_user_coupon_id = db.Column(db.Integer, comment='新人券记录 id')
    inviter_coupon_id = db.Column(db.Integer, comment='邀请人奖励券记录 id')
    share_id = db.Column(db.String(255), comment='分享渠道 id')
    registered_at = db.Column(db.DateTime, comment='绑定/注册时间')
    first_order_completed_at = db.Column(db.DateTime, comment='新人首单完成时间')
    rewarded_at = db.Column(db.DateTime, comment='邀请人奖励发放时间')


class WalletAccount(db.Model):
    __tablename__ = 'wallet_accounts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='储值账户 id')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')
    open_id = db.Column(db.String(60), nullable=False, unique=True, comment='用户 OpenID')
    balance = db.Column(db.Integer, nullable=False, default=0, comment='钱包余额，单位分')
    frozen_balance = db.Column(db.Integer, nullable=False, default=0, comment='冻结余额，单位分')
    status = db.Column(db.Integer, nullable=False, default=0, comment='账户状态')


class WalletRechargeOrder(db.Model):
    __tablename__ = 'wallet_recharge_orders'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='储值充值订单 id')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')
    open_id = db.Column(db.String(60), nullable=False, comment='用户 OpenID')
    amount = db.Column(db.Integer, nullable=False, comment='充值金额，单位分')
    bonus_amount = db.Column(db.Integer, nullable=False, default=0, comment='赠送金额，单位分')
    pay_order_id = db.Column(db.Integer, comment='关联 pay_orders.id')
    status = db.Column(db.Integer, nullable=False, default=0, comment='充值订单状态')
    paid_at = db.Column(db.DateTime, comment='支付完成时间')


class WalletTransaction(db.Model):
    __tablename__ = 'wallet_transactions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='储值流水 id')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')
    open_id = db.Column(db.String(60), nullable=False, comment='用户 OpenID')
    account_id = db.Column(db.Integer, nullable=False, comment='关联 wallet_accounts.id')
    type = db.Column(db.String(32), nullable=False, comment='流水类型')
    direction = db.Column(db.String(8), nullable=False, comment='余额方向')
    amount = db.Column(db.Integer, nullable=False, comment='变动金额，单位分')
    balance_before = db.Column(db.Integer, nullable=False, comment='变动前余额')
    frozen_before = db.Column(db.Integer, nullable=False, comment='变动前冻结余额')
    balance_after = db.Column(db.Integer, nullable=False, comment='变动后余额')
    frozen_after = db.Column(db.Integer, nullable=False, comment='变动后冻结余额')
    related_pay_order_id = db.Column(db.Integer, comment='关联 pay_orders.id')
    related_recharge_order_id = db.Column(db.Integer, comment='关联 wallet_recharge_orders.id')
    related_refund_request_id = db.Column(db.Integer, comment='关联 refund_requests.id')
    biz_key = db.Column(db.String(128), nullable=False, unique=True, comment='幂等键')
    remark = db.Column(db.String(255), comment='流水备注')


class RefundRequest(db.Model):
    __tablename__ = 'refund_requests'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='退款申请 id')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')
    open_id = db.Column(db.String(60), nullable=False, index=True, comment='用户 open_id')
    order_type = db.Column(db.String(20), nullable=False, comment='订单类型')
    order_id = db.Column(db.Integer, nullable=False, comment='业务订单 id')
    pay_order_id = db.Column(db.Integer, db.ForeignKey('pay_orders.id'), nullable=False, comment='支付订单 id')
    amount = db.Column(db.Integer, nullable=False, comment='退款金额，单位分')
    status = db.Column(db.String(30), nullable=False, comment='退款状态')
    out_refund_no = db.Column(db.String(255), comment='商户退款单号')
    wx_refund_id = db.Column(db.String(255), comment='微信退款单号')
    review_remark = db.Column(db.Text, comment='审核备注')
    refund_error = db.Column(db.Text, comment='退款错误信息')
    reviewed_at = db.Column(db.DateTime, comment='审核时间')
    refunded_at = db.Column(db.DateTime, comment='退款成功时间')

    pay_order = db.relationship('PayOrder', foreign_keys=[pay_order_id], lazy='joined')
    user = db.relationship(
        'User',
        primaryjoin='RefundRequest.open_id==foreign(User.open_id)',
        uselist=False,
        lazy='select'
    )


class Table(db.Model):
    __tablename__ = 'tables'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='桌台 id')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')
    store_id = db.Column(db.Integer, nullable=False, default=1, comment='所属门店')
    status = db.Column(db.Integer, nullable=False, default=0, comment='桌台状态')
    name = db.Column(db.String(255), comment='桌台名称')
    area = db.Column(db.Integer, nullable=False, default=0, comment='区域')


class Dish(db.Model):
    __tablename__ = 'dishes'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='菜品 id')
    store_id = db.Column(db.Integer, nullable=False, default=1, comment='所属门店')
    library_item_id = db.Column(db.Integer, comment='关联餐品信息库 id')
    name = db.Column(db.String(60), nullable=False, comment='餐品名称')
    category_ids = db.Column(db.JSON, comment='分类 id 列表')
    description = db.Column(db.String(255), comment='描述')
    price = db.Column(db.Integer, nullable=False, comment='价格，单位分')
    image_url = db.Column(db.String(255), comment='图片')
    options = db.Column(db.JSON, comment='选项 id 列表')
    tags = db.Column(db.JSON, comment='标签')
    status = db.Column(db.SmallInteger, nullable=False, default=1, comment='上架状态，0-下架，1-上架')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')


class DishLibraryItem(db.Model):
    __tablename__ = 'dish_library_items'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='餐品信息库 id')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')
    name = db.Column(db.String(60), nullable=False, comment='餐品名称')
    category_ids = db.Column(db.JSON, comment='分类 id 列表')
    description = db.Column(db.String(255), comment='描述')
    default_price = db.Column(db.Integer, nullable=False, default=0, comment='默认价格，单位分')
    image_url = db.Column(db.String(255), comment='图片')
    options = db.Column(db.JSON, comment='选项 id 列表')
    tags = db.Column(db.JSON, comment='默认标签')


class DishStoreItem(db.Model):
    __tablename__ = 'dish_store_items'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='门店菜单项 id')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')
    store_id = db.Column(db.Integer, nullable=False, comment='门店 id')
    dish_library_item_id = db.Column(db.Integer, nullable=False, comment='餐品信息库 id')
    dish_id = db.Column(db.Integer, comment='兼容旧 dishes.id')
    price = db.Column(db.Integer, nullable=False, comment='门店售价，单位分')
    status = db.Column(db.SmallInteger, nullable=False, default=1, comment='门店上下架状态')
    sort = db.Column(db.Integer, nullable=False, default=0, comment='排序')


class DishCategory(db.Model):
    __tablename__ = 'dish_categories'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='分类 id')
    name = db.Column(db.String(60), nullable=False, comment='分类名称')
    sort = db.Column(db.Integer, nullable=False, default=0, comment='排序')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')


class DishOption(db.Model):
    __tablename__ = 'options'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='选项 id')
    name = db.Column(db.String(60), nullable=False, comment='选项名称')
    type = db.Column(db.SmallInteger, nullable=False, default=0, comment='0-单选，1-多选')
    items = db.Column(db.JSON, comment='选项条目')
    description = db.Column(db.String(255), comment='描述')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')


class Catering(db.Model):
    __tablename__ = 'caterings'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='餐饮订单 id')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')
    store_id = db.Column(db.Integer, nullable=False, default=1, comment='消费发生门店')
    open_id = db.Column(db.String(60), nullable=False, index=True, comment='用户 open_id')
    total_price = db.Column(db.Integer, nullable=False, comment='订单金额，单位分')
    status = db.Column(db.Integer, nullable=False, default=0, comment='制作状态，0-制作中，1-已完成')
    settle_status = db.Column(db.Integer, nullable=False, comment='支付状态')
    table_id = db.Column(db.Integer, db.ForeignKey('tables.id'), comment='桌台 id')
    takeaway = db.Column(db.Boolean, nullable=False, default=False, comment='是否外带')
    code = db.Column(db.String(60), nullable=False, comment='取餐号')
    comment = db.Column(db.Text, comment='备注')

    table = db.relationship('Table', foreign_keys=[table_id], lazy='joined')
    items = db.relationship(
        'CateringItem',
        primaryjoin='and_(Catering.id==foreign(CateringItem.catering_id), CateringItem.deleted_at.is_(None))',
        lazy='select'
    )
    pay_order = db.relationship(
        'PayOrder',
        primaryjoin='and_(Catering.id==foreign(PayOrder.catering_id), PayOrder.deleted_at.is_(None))',
        uselist=False,
        lazy='select'
    )
    user = db.relationship(
        'User',
        primaryjoin='Catering.open_id==foreign(User.open_id)',
        uselist=False,
        lazy='select'
    )


class CateringItem(db.Model):
    __tablename__ = 'catering_items'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='餐饮订单项 id')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')
    catering_id = db.Column(db.Integer, db.ForeignKey('caterings.id'), nullable=False, comment='餐饮订单 id')
    dish_id = db.Column(db.Integer, db.ForeignKey('dishes.id'), nullable=False, comment='菜品 id')
    count = db.Column(db.Integer, nullable=False, comment='数量')
    selections = db.Column(db.JSON, comment='选项')
    total_price = db.Column(db.Integer, nullable=False, comment='小计，单位分')

    dish = db.relationship('Dish', foreign_keys=[dish_id], lazy='joined')


class WalletRechargeTier(db.Model):
    __tablename__ = 'wallet_recharge_tiers'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='档位 id')
    amount = db.Column(db.Integer, nullable=False, comment='充值金额，单位分')
    bonus_amount = db.Column(db.Integer, nullable=False, default=0, comment='赠送金额，单位分')
    label = db.Column(db.String(64), comment='档位展示文案')
    sort = db.Column(db.Integer, nullable=False, default=0, comment='排序，越小越靠前')
    enabled = db.Column(db.SmallInteger, nullable=False, default=1, comment='是否启用，0-停用，1-启用')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')


class Config(db.Model):
    __tablename__ = 'configs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='配置 id')
    config_key = db.Column(db.String(30), nullable=False, unique=True, comment='配置键')
    config_value = db.Column(db.JSON, nullable=False, comment='配置值（JSON）')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')


class PointAccount(db.Model):
    __tablename__ = 'point_accounts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='积分账户 id')
    open_id = db.Column(db.String(60), nullable=False, unique=True, comment='用户 OpenID')
    balance = db.Column(db.Integer, nullable=False, default=0, comment='积分余额')
    status = db.Column(db.SmallInteger, nullable=False, default=0, comment='账户状态：0-正常，1-冻结')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')


class PointTransaction(db.Model):
    __tablename__ = 'point_transactions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='积分流水 id')
    open_id = db.Column(db.String(60), nullable=False, comment='用户 OpenID')
    account_id = db.Column(db.Integer, nullable=False, comment='关联 point_accounts.id')
    type = db.Column(db.String(32), nullable=False, comment='流水类型')
    direction = db.Column(db.String(8), nullable=False, comment='积分方向：in/out')
    amount = db.Column(db.Integer, nullable=False, comment='本次变动积分')
    balance_before = db.Column(db.Integer, nullable=False, comment='变动前积分余额')
    balance_after = db.Column(db.Integer, nullable=False, comment='变动后积分余额')
    related_pay_order_id = db.Column(db.Integer, comment='关联 pay_orders.id')
    related_withdraw_id = db.Column(db.Integer, comment='关联 point_withdraw_records.id')
    related_redeem_order_id = db.Column(db.Integer, comment='关联 point_redeem_orders.id')
    biz_key = db.Column(db.String(128), nullable=False, unique=True, comment='幂等键')
    remark = db.Column(db.String(255), comment='流水备注')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')


class PointProductCategory(db.Model):
    __tablename__ = 'point_product_categories'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='积分商品分类 id')
    name = db.Column(db.String(60), nullable=False, comment='分类名称')
    sort = db.Column(db.Integer, nullable=False, default=0, comment='排序，越小越靠前')
    status = db.Column(db.SmallInteger, nullable=False, default=1, comment='状态：0-停用，1-启用')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')


class PointProduct(db.Model):
    __tablename__ = 'point_products'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='积分商品 id')
    name = db.Column(db.String(120), nullable=False, comment='商品名称')
    category_id = db.Column(db.Integer, comment='关联 point_product_categories.id')
    description = db.Column(db.String(255), comment='描述')
    points_price = db.Column(db.Integer, nullable=False, comment='兑换所需积分')
    original_price = db.Column(db.Integer, comment='市场参考价，单位分，可空')
    image_url = db.Column(db.String(255), comment='图片')
    stock = db.Column(db.Integer, nullable=False, default=-1, comment='库存，-1 表示不限')
    sort = db.Column(db.Integer, nullable=False, default=0, comment='排序，越小越靠前')
    status = db.Column(db.SmallInteger, nullable=False, default=1, comment='上架状态：0-下架，1-上架')
    redeem_start_at = db.Column(db.DateTime, comment='开兑时间；NULL 表示立即开兑')
    max_redeem_per_user = db.Column(db.Integer, nullable=False, default=-1, comment='每位玩家累计限兑；-1 表示不限')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')


class PointWithdrawRecord(db.Model):
    __tablename__ = 'point_withdraw_records'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='积分提取记录 id')
    open_id = db.Column(db.String(60), nullable=False, index=True, comment='申请提取的用户 OpenID')
    points = db.Column(db.Integer, nullable=False, comment='提取积分数')
    status = db.Column(db.SmallInteger, nullable=False, default=0, comment='状态：0-待发放，1-已发放，2-已过期，3-已取消')
    issuer_open_id = db.Column(db.String(60), comment='发放员工 OpenID')
    issued_at = db.Column(db.DateTime, comment='发放时间')
    store_id = db.Column(db.Integer, comment='积分发放门店')
    expire_at = db.Column(db.DateTime, nullable=False, comment='过期时间')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')

    user = db.relationship(
        'User',
        primaryjoin='PointWithdrawRecord.open_id==foreign(User.open_id)',
        uselist=False,
        lazy='select'
    )
    issuer = db.relationship(
        'User',
        primaryjoin='PointWithdrawRecord.issuer_open_id==foreign(User.open_id)',
        uselist=False,
        lazy='select'
    )


class PointRedeemOrder(db.Model):
    __tablename__ = 'point_redeem_orders'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='积分兑换订单 id')
    order_no = db.Column(db.String(64), nullable=False, unique=True, comment='兑换订单号')
    request_key = db.Column(db.String(64), comment='客户端兑换请求幂等键')
    open_id = db.Column(db.String(60), nullable=False, index=True, comment='兑换用户 OpenID')
    product_id = db.Column(db.Integer, nullable=False, comment='关联 point_products.id')
    product_name = db.Column(db.String(120), nullable=False, comment='商品名称快照')
    product_image_url = db.Column(db.String(255), comment='商品图片快照')
    points_price = db.Column(db.Integer, nullable=False, comment='单价积分')
    quantity = db.Column(db.Integer, nullable=False, default=1, comment='兑换数量')
    total_points = db.Column(db.Integer, nullable=False, comment='总消耗积分')
    status = db.Column(db.SmallInteger, nullable=False, default=0, comment='状态：0-待领取，1-已完成，2-已取消')
    verifier_open_id = db.Column(db.String(60), comment='核销员工 OpenID')
    verified_at = db.Column(db.DateTime, comment='核销完成时间')
    pickup_store_id = db.Column(db.Integer, comment='积分兑换领取门店')
    created_at = db.Column(db.DateTime, comment='创建时间')
    updated_at = db.Column(db.DateTime, comment='更新时间')
    deleted_at = db.Column(db.DateTime, comment='删除时间')

    user = db.relationship(
        'User',
        primaryjoin='PointRedeemOrder.open_id==foreign(User.open_id)',
        uselist=False,
        lazy='select'
    )
    verifier = db.relationship(
        'User',
        primaryjoin='PointRedeemOrder.verifier_open_id==foreign(User.open_id)',
        uselist=False,
        lazy='select'
    )
