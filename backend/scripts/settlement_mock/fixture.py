"""Deterministic July/August 2026 settlement fixture. All money is integer cents."""
import json
from datetime import datetime, timedelta
from collections import Counter

PREFIX = 'MOCK_SETTLE_20260927'
BASE = 870927000
START = datetime(2026,7,1)
A,B,C,D = [BASE+i for i in range(1,5)]


def build(metadata):
    rows=[]; serial=BASE+100; labels={}; fixes=[]
    def add(table, label=None, **values):
        nonlocal serial
        serial+=1
        if table != 'settlement_periods': values.setdefault('id',serial)
        model=metadata.tables.get(table)
        if model is not None:
            for col in model.columns:
                if col.name in values: continue
                if col.name in ('created_at','updated_at'): values[col.name]=START
                elif col.default is not None:
                    values[col.name]=col.default.arg(None) if col.default.is_callable else col.default.arg
                elif not col.nullable and not col.primary_key and col.server_default is None:
                    raise ValueError(f'Missing fixture value: {table}.{col.name}')
        rows.append((table,values))
        if label: labels[label]=(table,values)
        return values
    def user(number,name):
        return add('users',id=BASE+10+number,open_id=f'{PREFIX}_u{number}',nick_name='MOCK-'+name,
            role=0,user_type=0,gender=0,registered_store_id=A,registered_store_source='mock')
    for sid,code,name in ((A,'a','A-收款店'),(B,'b','B-跨店履约'),(C,'c','C-当期补款'),(D,'d','D-零净额')):
        add('stores',id=sid,code=f'mock-settle-{code}',name='MOCK-'+name,status=1,sort=9000+sid-BASE,
            address='仅测试环境模拟门店，无真实地址',business_hours='模拟数据')
    for month in ('2026-07','2026-08'): add('settlement_periods',month=month,status='draft')
    cash_user=user(1,'微信消费');wallet_user=user(2,'储值跨批次退款')
    dish=add('dishes',store_id=B,name='MOCK-测试饮料',price=2000,status=0,category_ids=[],options=[],tags=[])
    def payment(label,store,amount,at,wallet=0,food=False,who=None,status=1):
        who=who or cash_user
        if food:
            order=add('caterings',store_id=store,open_id=who['open_id'],total_price=amount,
                status=1,settle_status=1,code=PREFIX+'-'+label,created_at=at,updated_at=at,comment='MOCK模拟订单')
            add('catering_items',catering_id=order['id'],dish_id=dish['id'],count=1,total_price=amount,selections=[])
            link={'catering_id':order['id']}
        else:
            order=add('play_orders',store_id=store,open_id=who['open_id'],in_time=at-timedelta(hours=2),
                out_time=at,play_time=2,amount=amount,settle_status=1,unit_price=amount//2,comment='MOCK模拟订单',created_at=at)
            link={'play_order_id':order['id']}
        return add('pay_orders',label,store_id=store,open_id=who['open_id'],amount=amount,total_amount=amount,
            wallet_amount=wallet,wechat_amount=amount-wallet,pay_type=(3 if amount==wallet else 4 if wallet else 0),
            pay_status=status,pay_end_time=at,created_at=at,order_id=f'{PREFIX}_{label}',description='MOCK模拟支付',**link)
    def refund(pay,at):
        pay.update(pay_status=3,refund_amount=pay['amount'],wallet_refund_amount=pay['wallet_amount'],wechat_refund_amount=pay['wechat_amount'])
        return add('refund_requests',open_id=pay['open_id'],order_type='catering' if pay.get('catering_id') else 'play',
            order_id=pay.get('catering_id') or pay['play_order_id'],pay_order_id=pay['id'],amount=pay['amount'],
            status='refunded',created_at=at,reviewed_at=at,refunded_at=at,out_refund_no=PREFIX+str(pay['id']),review_remark='MOCK已成功退款，无外部调用')
    payment('july-play',A,10000,datetime(2026,7,5,12))
    payment('july-food',B,6000,datetime(2026,7,6,12),food=True)
    refund(payment('same-month-refund',A,2000,datetime(2026,7,7,12)),datetime(2026,7,8,12))
    refund(payment('cross-month-refund',B,5000,datetime(2026,7,25,12)),datetime(2026,8,3,12))
    refund(payment('zero-net',D,1000,datetime(2026,7,9,12)),datetime(2026,7,10,12))
    payment('aug-play',A,3000,datetime(2026,8,8,12));payment('aug-food',B,8000,datetime(2026,8,9,12),food=True)
    payment('unpaid-excluded',A,99900,datetime(2026,7,12,12),status=0)
    account=add('wallet_accounts',open_id=wallet_user['open_id'],balance=13000,frozen_balance=0)
    def wallet_tx(kind,amount,before,after,at,**links):
        return add('wallet_transactions',open_id=wallet_user['open_id'],account_id=account['id'],type=kind,
            direction='in' if after>before else 'out',amount=amount,balance_before=before,balance_after=after,
            frozen_before=0,frozen_after=0,biz_key=PREFIX+f':wallet:{len(rows)}',remark='MOCK储值流水',created_at=at,**links)
    batches=[]; balance=0
    for num,(principal,bonus,remaining,premaining) in enumerate(((10000,2000,6000,5000),(5000,5000,7000,3500))):
        at=datetime(2026,7,2+num,12)
        recharge=add('wallet_recharge_orders',open_id=wallet_user['open_id'],amount=principal,bonus_amount=bonus,status=1,paid_at=at,created_at=at)
        pay=add('pay_orders',store_id=A,open_id=wallet_user['open_id'],amount=principal,wechat_amount=principal,pay_type=0,pay_status=1,
            pay_end_time=at,created_at=at,wallet_recharge_order_id=recharge['id'],order_id=PREFIX+f'_recharge{num}')
        recharge['pay_order_id']=pay['id']
        wallet_tx('recharge',principal,balance,balance+principal,at,related_recharge_order_id=recharge['id']);balance+=principal
        wallet_tx('bonus',bonus,balance,balance+bonus,at,related_recharge_order_id=recharge['id']);balance+=bonus
        batches.append(add('settlement_batches',kind='wallet',open_id=wallet_user['open_id'],source_key=f"wallet:recharge:{recharge['id']}",
            source_store_id=A,responsible_store_id=0,face_total=principal+bonus,principal_total=principal,remaining=remaining,principal_remaining=premaining,created_at=at))
    mixed=payment('mixed',A,12000,datetime(2026,7,15,12),wallet=6000,who=wallet_user)
    second=payment('cross-batch',B,9000,datetime(2026,7,20,12),wallet=9000,who=wallet_user)
    mixed_refund=refund(mixed,datetime(2026,8,5,12))
    for pay,batch,face,principal,state in ((mixed,batches[0],6000,5000,'returned'),(second,batches[0],6000,5000,'consumed'),(second,batches[1],3000,1500,'consumed')):
        add('settlement_allocations',biz_key=f'{PREFIX}:wallet:{pay["id"]}:{batch["id"]}',batch_id=batch['id'],kind='wallet',
            open_id=wallet_user['open_id'],reference=f'pay:{pay["id"]}',store_id=pay['store_id'],amount=face,principal=principal,state=state,created_at=pay['pay_end_time'])
    for pay,principal in ((mixed,5000),(second,6500)):
        wallet_tx('consume',pay['wallet_amount'],balance,balance-pay['wallet_amount'],pay['pay_end_time'],related_pay_order_id=pay['id']);balance-=pay['wallet_amount']
        add('settlement_entries',biz_key=f'{PREFIX}:wallet:pay:{pay["id"]}',month='2026-07',event_at=pay['pay_end_time'],kind='wallet',reference=f'pay:{pay["id"]}',
            payer_id=0,receiver_id=pay['store_id'],amount=principal,face_amount=pay['wallet_amount'],detail='MOCK按原批次本金比例折算')
    wallet_tx('refund',6000,balance,balance+6000,datetime(2026,8,5,12),related_pay_order_id=mixed['id'],related_refund_request_id=mixed_refund['id'])
    add('settlement_entries',biz_key=PREFIX+':wallet:refund',month='2026-08',event_at=datetime(2026,8,5,12),kind='wallet_refund',reference=f'pay:{mixed["id"]}',payer_id=0,receiver_id=A,amount=-5000,face_amount=-6000,detail='MOCK跨月退款，退回原本金')
    def card(num,name,source,start,uses):
        who=user(3+num,name);end=start+timedelta(days=30);who['month_card_expire']=end
        order=add('month_card_orders',open_id=who['open_id'],open_period=1,duration_days=30,amount=39900,open_type=1,settle_status=1,source=source,
            store_id=A,effective_at=start,created_at=start,request_key=f'{PREFIX}-card{num}',operator='MOCK',remark='MOCK历史卡期，不代表真实收款')
        pool=add('settlement_card_pools',source_key=f'card:{order["id"]}:0',order_id=order['id'],open_id=who['open_id'],starts_at=start,ends_at=end,amount=39900,payer_id=0,status='open')
        if source=='wechat':
            add('pay_orders',open_id=who['open_id'],store_id=A,month_card_order_id=order['id'],amount=39900,wechat_amount=39900,pay_type=1,pay_status=1,pay_end_time=start,created_at=start,order_id=f'{PREFIX}-cardpay{num}')
        if source=='third_party':
            rem=add('settlement_card_remittances','voucher',order_id=order['id'],voucher_key='9'*64,channel='MOCK美团',external_no=PREFIX+'-voucher',store_id=A,amount=39900,created_at=start,status='pending')
            fixes.append(('settlement_card_remittances',rem['id'],dict(status='confirmed',payment_ref='MOCK演练凭证',submitted_at=start,confirmed_at=start)))
        for i,(sid,at,hours,review) in enumerate(uses):
            play=add('play_orders',store_id=sid,open_id=who['open_id'],in_time=at,out_time=at+timedelta(hours=hours),play_time=hours,amount=0,settle_status=1,billing_mode=2,created_at=at,comment='MOCK月卡核销')
            use=add('settlement_card_usages',pool_id=pool['id'],play_order_id=play['id'],store_id=sid,started_at=at,ended_at=play['out_time'],seconds=hours*3600,status='review' if review else 'valid',note='MOCK待核验' if review else 'MOCK正常核销')
            if review: fixes.append(('settlement_card_usages',use['id'],dict(status='valid',note='MOCK核验通过')))
    card(0,'跨月线上卡','wechat',datetime(2026,7,17),[(A,datetime(2026,7,20),1,True),(B,datetime(2026,7,21),2,False),(A,datetime(2026,8,2),3,False),(B,datetime(2026,8,3),1,False)])
    card(1,'总部赠卡','gift',START,[(C,datetime(2026,7,18),1,False)])
    card(2,'第三方验券','third_party',START,[(A,datetime(2026,7,18),1,False)])
    card(3,'从未使用归总部','wechat',START,[])
    card(4,'七月未用八月补分','wechat',datetime(2026,7,17),[(B,datetime(2026,8,4),1,False)])
    category=add('point_product_categories',name='MOCK结算测试',status=0)
    product=add('point_products',name='MOCK积分礼品',category_id=category['id'],points_price=100,stock=10,status=0)
    raffle=add('raffles',created_at=datetime(2026,7,10),updated_at=datetime(2026,7,23),title='MOCK-积分抽奖已开奖',description='MOCK仅结算测试，不发送通知',cover_url='',store_id=B,store_name='MOCK-B-跨店履约',pickup_instructions='模拟已领取',entry_mode='points',points_cost=100,draw_mode='manual',max_participants=2,participant_count=2,status='drawn',drawn_at=datetime(2026,7,23),cancel_reason='',creator_id=cash_user['id'],operator_id=cash_user['id'],request_key=PREFIX+'-raffle',request_hash='8'*64)
    prize=add('raffle_prizes',raffle_id=raffle['id'],name='MOCK奖品',quantity=1,sort=1)
    def point_expense(num,kind,cost,provider,weights,at,missing=False):
        who=user(10+num,'积分场景'+str(num));pa=add('point_accounts',open_id=who['open_id'],balance=0,status=0)
        total=sum(weights.values());balance=0
        if kind=='redeem':
            origin=add('point_redeem_orders',order_no=PREFIX+f'-redeem{num}',request_key=PREFIX+f'-redeem{num}',open_id=who['open_id'],product_id=product['id'],product_name='MOCK积分礼品',points_price=total,quantity=1,total_points=total,status=1,pickup_store_id=provider,verified_at=at,created_at=at)
        else: origin=raffle
        key=f'{kind}:{origin["id"]}'
        for sid,points in weights.items():
            tx=add('point_transactions',open_id=who['open_id'],account_id=pa['id'],type='mock_earn',direction='in',amount=points,balance_before=balance,balance_after=balance+points,biz_key=PREFIX+f':earn:{num}:{sid}',remark='MOCK来源积分',created_at=at-timedelta(days=1));balance+=points
            batch=add('settlement_batches',kind='point',open_id=who['open_id'],source_key=tx['biz_key'],source_store_id=sid,responsible_store_id=sid,face_total=points,remaining=0,created_at=at-timedelta(days=1))
            add('settlement_allocations',biz_key=PREFIX+f':spend:{num}:{sid}',batch_id=batch['id'],kind='point',open_id=who['open_id'],reference=key,expense_key=key,store_id=provider,amount=points,state='consumed',created_at=at)
        add('point_transactions',open_id=who['open_id'],account_id=pa['id'],type=kind,direction='out',amount=total,balance_before=total,balance_after=0,biz_key=PREFIX+f':spent:{num}',related_redeem_order_id=origin['id'] if kind=='redeem' else None,remark='MOCK积分消费',created_at=at)
        expense=add('settlement_expenses',f'cost{num}',expense_key=key,kind=kind,source_id=origin['id'],created_at=at,completed_at=at,amount=None if missing else cost,provider_id=provider,status='needs_cost' if missing else 'ready',note='' if missing else 'MOCK成本已核对')
        if missing: fixes.append(('settlement_expenses',expense['id'],dict(amount=cost,status='ready',note='MOCK确认成本150元')))
        return who
    point_expense(0,'redeem',10000,A,{B:60,C:40},datetime(2026,7,22))
    winner=point_expense(1,'raffle',30000,B,{C:100},datetime(2026,7,23))
    # One participant is sufficient; no subscription or notification jobs are seeded.
    raffle['participant_count']=1
    add('raffle_entries',created_at=datetime(2026,7,23),updated_at=datetime(2026,7,23),raffle_id=raffle['id'],user_id=winner['id'],number=1,open_id=winner['open_id'],nick_name=winner['nick_name'],avatar='',points_paid=100,subscribed=0,prize_id=prize['id'])
    point_expense(2,'redeem',15000,A,{C:100},datetime(2026,7,24),missing=True)
    point_expense(3,'redeem',5000,B,{C:100},datetime(2026,8,10))
    # A HQ-awarded unspent balance demonstrates the headquarters source tab.
    who=user(20,'总部赠分余额');pa=add('point_accounts',open_id=who['open_id'],balance=200,status=0)
    add('point_transactions',open_id=who['open_id'],account_id=pa['id'],type='mock_earn',direction='in',amount=200,balance_before=0,balance_after=200,biz_key=PREFIX+':hq-points',remark='MOCK总部活动赠分')
    add('settlement_batches',kind='point',open_id=who['open_id'],source_key=PREFIX+':hq-points',source_store_id=0,responsible_store_id=0,face_total=200,remaining=200)
    return rows,fixes,labels


def sql_value(value):
    if value is None:return 'NULL'
    if isinstance(value,bool):return str(int(value))
    if isinstance(value,(int,float)):return str(value)
    if isinstance(value,datetime):value=value.isoformat(' ')
    if isinstance(value,(dict,list)):value=json.dumps(value,ensure_ascii=False)
    return "'"+str(value).replace('\\','\\\\').replace("'","''")+"'"


def insert_sql(table,row):
    return 'INSERT INTO `'+table+'` ('+', '.join('`'+k+'`' for k in row)+') VALUES ('+', '.join(sql_value(v) for v in row.values())+');'
