from .clock import now
"""Pure, rollbackable opening import. No historical settlement entries are generated."""
from datetime import datetime
from sqlalchemy import text
from app import db
from app.models import WalletAccount, WalletRechargeOrder, WalletTransaction, PointAccount, PointTransaction, PointRedeemOrder, MonthCardOrder, User, PlayOrder, PayOrder, Store
from .models import *
from .service import add_months, apportion
from .cards import term_boundary


def wallet_opening(cutoff,nanshan,payer):
    count=0
    for account in WalletAccount.query.filter(WalletAccount.deleted_at.is_(None)).order_by(WalletAccount.id):
        batches=[];allocs={};seen_recharges={};seen_bonuses=set();balance=0;frozen=0
        txs=WalletTransaction.query.filter_by(account_id=account.id).filter(WalletTransaction.created_at<cutoff,WalletTransaction.deleted_at.is_(None)).order_by(WalletTransaction.id).all()
        for t in txs:
            if t.amount<0 or (t.balance_before,t.frozen_before)!=(balance,frozen):raise ValueError(f'钱包账户 #{account.id} 流水余额不连续')
            if t.type in ('recharge','bonus','refund'):balance+=t.amount
            elif t.type=='consume':
                balance-=t.amount
                if t.frozen_after<t.frozen_before:frozen-=t.amount
            elif t.type=='freeze':frozen+=t.amount
            elif t.type=='unfreeze':frozen-=t.amount
            if (t.balance_after,t.frozen_after)!=(balance,frozen) or min(balance,frozen)<0 or frozen>balance:raise ValueError(f'钱包账户 #{account.id} 流水金额或冻结余额不一致')
            if t.type=='recharge':
                order=db.session.get(WalletRechargeOrder,t.related_recharge_order_id)
                if not order or order.open_id!=account.open_id or order.amount!=t.amount or order.amount<=0 or order.bonus_amount<0 or order.id in seen_recharges: raise ValueError(f'钱包账户 #{account.id} 缺少唯一有效的充值本金依据')
                b=SettlementBatch(kind='wallet',open_id=account.open_id,source_key=f'wallet:recharge:{order.id}',source_store_id=nanshan,responsible_store_id=payer,face_total=order.amount+order.bonus_amount,principal_total=order.amount,remaining=order.amount+order.bonus_amount,principal_remaining=order.amount,frozen=0,legacy=True,created_at=t.created_at)
                db.session.add(b);db.session.flush();batches.append(b);seen_recharges[order.id]=order.bonus_amount
            elif t.type=='bonus':
                if t.related_recharge_order_id in seen_bonuses or seen_recharges.get(t.related_recharge_order_id)!=t.amount: raise ValueError(f'钱包账户 #{account.id} 的赠送缺少唯一有效的充值来源')
                seen_bonuses.add(t.related_recharge_order_id)
            elif t.type in ('freeze','consume'):
                pay=db.session.get(PayOrder,t.related_pay_order_id)
                if not pay: raise ValueError(f'钱包账户 #{account.id} 缺少消费订单')
                ref=f'pay:{pay.id}';rows=allocs.setdefault(ref,[])
                reserved=[a for a in rows if a.state=='reserved']
                if t.type=='consume' and t.frozen_after<t.frozen_before:
                    if sum(a.amount for a in reserved)!=t.amount:raise ValueError(f'钱包账户 #{account.id} 冻结流水不完整')
                    for a in reserved:
                        b=next(b for b in batches if b.id==a.batch_id);b.frozen-=a.amount
                        a.principal=min(a.amount,max(0,b.principal_remaining-(b.remaining-a.amount)*b.principal_total//b.face_total));b.remaining-=a.amount;b.principal_remaining-=a.principal;a.state='consumed'
                else:
                    left=t.amount
                    for b in batches:
                        if not left:break
                        n=min(left,b.remaining-b.frozen)
                        if n<=0:continue
                        a=SettlementAllocation(biz_key=f'{t.biz_key}:batch:{b.id}',kind='wallet',open_id=account.open_id,batch_id=b.id,reference=ref,store_id=pay.store_id or nanshan,amount=n,principal=0,state='reserved',created_at=t.created_at)
                        if t.type=='freeze':b.frozen+=n
                        else:a.principal=min(n,max(0,b.principal_remaining-(b.remaining-n)*b.principal_total//b.face_total));b.remaining-=n;b.principal_remaining-=a.principal;a.state='consumed'
                        db.session.add(a);rows.append(a);left-=n
                    if left:raise ValueError(f'钱包账户 #{account.id} 历史流水无法对应余额')
            elif t.type in ('unfreeze','refund'):
                rows=allocs.get(f'pay:{t.related_pay_order_id}',[]);state='reserved' if t.type=='unfreeze' else 'consumed';rows=[a for a in rows if a.state==state]
                if sum(a.amount for a in rows)!=t.amount:raise ValueError(f'钱包账户 #{account.id} 退回流水缺少原扣款')
                for a in rows:
                    b=next(b for b in batches if b.id==a.batch_id)
                    if t.type=='unfreeze':b.frozen-=a.amount;a.state='released'
                    else:b.remaining+=a.amount;b.principal_remaining+=a.principal;a.state='returned'
            else:raise ValueError(f'钱包账户 #{account.id} 有未定义的期初调整类型 {t.type}')
        if sum(b.remaining for b in batches)!=account.balance or sum(b.frozen for b in batches)!=account.frozen_balance:
            raise ValueError(f'钱包账户 #{account.id} 期初批次与现有余额不一致，停止初始化')
        count+=1
    return count


def point_opening(cutoff,nanshan):
    from sqlalchemy import inspect
    has_raffles=inspect(db.session.connection()).has_table('raffle_entries')
    count=0
    for account in PointAccount.query.filter(PointAccount.deleted_at.is_(None)).order_by(PointAccount.id):
        spends=[]
        for order in PointRedeemOrder.query.filter_by(open_id=account.open_id,status=0).filter(PointRedeemOrder.deleted_at.is_(None),PointRedeemOrder.created_at<cutoff):
            key=f'redeem:{order.id}'
            db.session.add(SettlementExpense(expense_key=key,kind='redeem',source_id=order.id,status='pending',note='历史未提货兑换；履约后确认成本'))
            spends.append((f'point:redeem:{order.id}',key,order.total_points))
        if has_raffles:
            rows=db.session.execute(text("SELECT e.raffle_id,e.points_paid FROM raffle_entries e JOIN raffles r ON r.id=e.raffle_id WHERE e.open_id=:uid AND r.status='open' AND e.refunded_at IS NULL AND e.points_paid>0"),{'uid':account.open_id}).all()
            for rid,amount in rows:
                key=f'raffle:{rid}'
                if not SettlementExpense.query.filter_by(expense_key=key).first():
                    db.session.add(SettlementExpense(expense_key=key,kind='raffle',source_id=rid,status='pending',note='历史在途抽奖；开奖后确认成本'));db.session.flush()
                spends.append((f'raffle:{rid}:{account.open_id}:entry',key,amount))
        total=account.balance+sum(x[2] for x in spends)
        if total<0:raise ValueError(f'积分账户 #{account.id} 余额异常')
        if total:
            b=SettlementBatch(kind='point',open_id=account.open_id,source_key=f'opening:point:{account.id}',source_store_id=nanshan,responsible_store_id=nanshan,face_total=total,remaining=account.balance,legacy=True)
            db.session.add(b);db.session.flush()
            for ref,key,amount in spends:
                db.session.add(SettlementAllocation(biz_key=f'{ref}:batch:{b.id}',batch_id=b.id,kind='point',open_id=account.open_id,reference=ref,expense_key=key,amount=amount,state='consumed'))
        count+=1
    return count


def card_opening(cutoff,nanshan,policy,manifest):
    if policy not in ('full-period','prospective'):raise ValueError('必须明确跨期旧月卡的分配政策')
    imported=0
    for user in User.query.filter(User.deleted_at.is_(None),User.month_card_expire>cutoff):
        orders=MonthCardOrder.query.filter_by(open_id=user.open_id,settle_status=1).filter(MonthCardOrder.deleted_at.is_(None),MonthCardOrder.created_at<cutoff).order_by(MonthCardOrder.id).all()
        previous_end=None;pools=[]
        for order in orders:
            pay=PayOrder.query.filter_by(month_card_order_id=order.id).order_by(PayOrder.id.desc()).first()
            paid_at=(pay.pay_end_time if pay else None) or order.created_at
            start=order.effective_at or max(paid_at,previous_end or paid_at)
            previous_end=term_boundary(order,start,order.open_period)
            amounts=apportion(order.amount,{i:1 for i in range(order.open_period)})
            for i in range(order.open_period):
                begin,end=term_boundary(order,start,i),term_boundary(order,start,i+1)
                if end<=cutoff:continue
                key=f'card:{order.id}:{i}';item=manifest.get(key,{})
                # New production opening assigns legacy source and responsibility to Nanshan.
                payer=nanshan if policy=='prospective' else item.get('payer_id',0)
                if payer is None:raise ValueError(f'{key} 需在月卡清单指定历史实收款责任方 payer_id')
                if isinstance(payer,bool) or not isinstance(payer,int) or payer<0 or (payer and not db.session.get(Store,payer)):raise ValueError(f'{key} 历史实收款责任方无效')
                amount=amounts[i]
                if policy=='prospective' and begin<cutoff:
                    duration=int((end-begin).total_seconds())
                    elapsed=int((cutoff-begin).total_seconds())
                    # Remaining cents equal the original full-term allocation minus elapsed release.
                    amount=amounts[i]-amounts[i]*elapsed//duration
                    begin=cutoff
                p=SettlementCardPool(source_key=key,order_id=order.id,open_id=user.open_id,starts_at=begin,ends_at=end,amount=amount,payer_id=payer,status='open',legacy=True)
                db.session.add(p);db.session.flush();pools.append(p);imported+=1
        if previous_end!=user.month_card_expire or not pools:raise ValueError(f'用户 #{user.id} 有效月卡无法对应原始卡期，请先核对开卡记录')
        if policy=='full-period':
            from sqlalchemy import or_
            card_orders=db.session.query(PayOrder.play_order_id).filter(PayOrder.pay_type==1,PayOrder.play_order_id.isnot(None))
            uses=PlayOrder.query.filter_by(open_id=user.open_id,settle_status=1).filter(or_(PlayOrder.billing_mode==2,PlayOrder.id.in_(card_orders)),PlayOrder.in_time<cutoff,PlayOrder.deleted_at.is_(None)).all()
            for u in uses:
                if not u.out_time:raise ValueError(f'历史月卡核销 #{u.id} 缺少离场时间')
                for p in pools:
                    start,end=max(u.in_time,p.starts_at),min(u.out_time,p.ends_at)
                    if end<=start:continue
                    seconds=int((end-start).total_seconds());state='review' if (u.out_time-u.in_time).total_seconds()>86400 else 'valid'
                    db.session.add(SettlementCardUsage(pool_id=p.id,play_order_id=u.id,store_id=u.store_id or nanshan,started_at=start,ended_at=end,seconds=seconds,status=state,note='历史初始化；缺门店时归南山'))
    return imported


def initialize(cutoff,wallet_payer,card_policy,manifest=None):
    old=db.session.get(SettlementControl,1)
    if old and old.initialized_at:
        if old.cutoff!=cutoff or old.legacy_wallet_payer!=wallet_payer or old.legacy_card_policy!=card_policy:raise ValueError('已初始化，不能换规则重跑')
        return {'AlreadyInitialized':True,'Cutoff':str(old.cutoff)}
    if cutoff>now():raise ValueError('不能提前生成正式期初快照；测试预演请使用当前时间作为切换点')
    for cls in (WalletTransaction,PointTransaction,MonthCardOrder):
        if cls.query.filter(cls.created_at>=cutoff).first():raise ValueError('存在切换点之后的资产变动，请在维护窗口使用真实快照时间初始化，不能追溯覆盖新账')
    store=Store.query.filter_by(code='nanshan').one_or_none()
    if not store or store.deleted_at:raise ValueError('未找到可用的南山店，请核验 stores.code=nanshan')
    if card_policy=='prospective' and wallet_payer!=store.id:
        raise ValueError('新上线口径要求历史储值与旧月卡承担方统一为南山')
    # Never blend a fresh opening with an existing/partial settlement book.
    for cls in (SettlementBatch,SettlementAllocation,SettlementCardPool,SettlementCardUsage,SettlementCardPeriod,SettlementExpense,SettlementEntry,SettlementReport,SettlementStatement,SettlementPeriod):
        if cls.query.first():raise ValueError('结算账已有记录，不能覆盖或混合初始化；请先核对迁移状态')
    counts={'WalletAccounts':wallet_opening(cutoff,store.id,wallet_payer),'PointAccounts':point_opening(cutoff,store.id),'CardPools':card_opening(cutoff,store.id,card_policy,manifest or {})}
    control=old or SettlementControl(id=1)
    control.cutoff=cutoff;control.legacy_wallet_payer=wallet_payer;control.legacy_card_policy=card_policy;control.initialized_at=now();db.session.add(control);db.session.flush()
    counts.update(FirstSettlementMonth=cutoff.strftime('%Y-%m'),CardPolicy=card_policy,HistoricalEntries=0,WalletFace=sum(x.remaining for x in SettlementBatch.query.filter_by(kind='wallet')),WalletPrincipal=sum(x.principal_remaining for x in SettlementBatch.query.filter_by(kind='wallet')),Points=sum(x.remaining for x in SettlementBatch.query.filter_by(kind='point')),Cutoff=str(cutoff))
    return counts
