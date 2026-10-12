"""Regressions for immutable card price, 30-day terms and monthly settlement."""
import hashlib
import os
import unittest
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch
from app import create_app, db
from app.models import Config, Store, User, MonthCardOrder, PlayOrder, PayOrder
from app.security.models import StaffAccount, StaffGrant, OASession, AccessAudit
from app.utils.crypto import encrypt_phone
from app.settlement.models import *
from app.settlement import service
from app.settlement.cards import window, prepare_cards, card_view


class MonthlyCardsTest(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'STORE_SETTLEMENT_ENABLED':'true'});self.env.start()
        self.app=create_app({'TESTING':True,'OA_LOGIN_MODE':'sms','SQLALCHEMY_DATABASE_URI':'sqlite://'})
        self.ctx=self.app.app_context();self.ctx.push();db.create_all()
        db.session.add_all([Store(id=1,code='nanshan',name='南山'),Store(id=2,code='b',name='B店'),User(id=1,open_id='hq'),User(id=2,open_id='manager'),User(id=3,open_id='customer'),Config(config_key='MonthCardConfig',config_value={'CommonPrice':39900,'MonthLimit':100})])
        for uid,hq in [(1,True),(2,False)]:
            db.session.add(StaffAccount(user_id=uid,phone_cipher=encrypt_phone(f'1380000000{uid}'),enabled=True,headquarters=hq,version=1))
            db.session.add(OASession(token_digest=hashlib.sha256(f'cards-{uid}'.encode()).hexdigest(),user_id=uid,account_version=1,expires_at=datetime.utcnow()+timedelta(hours=1)))
        db.session.add(StaffGrant(user_id=2,store_id=2,role='manager'))
        db.session.add(SettlementControl(id=1,cutoff=datetime(2026,1,1),initialized_at=datetime(2026,1,1),legacy_wallet_payer=0,legacy_card_policy='full-period'));db.session.commit()
        self.client=self.app.test_client()

    def tearDown(self):
        db.session.remove();db.drop_all();self.ctx.pop();self.env.stop()

    def headers(self,user=1,store=1):return {'Authorization':f'Bearer cards-{user}','X-Store-ID':str(store)}
    def post(self,path,data,user=1,store=1):return self.client.post('/admin_api/'+path,json=data,headers=self.headers(user,store))

    def pool(self,start=datetime(2026,1,17),amount=39900):
        p=SettlementCardPool(source_key='card:1:0',order_id=1,open_id='customer',starts_at=start,ends_at=start+timedelta(days=30),amount=amount,payer_id=0,status='open');db.session.add(p);db.session.flush();return p

    def usage(self,p,start,store=1,seconds=3600,status='valid'):
        u=SettlementCardUsage(pool_id=p.id,play_order_id=SettlementCardUsage.query.count()+1,store_id=store,started_at=start,ended_at=start+timedelta(seconds=seconds),seconds=seconds,status=status,note='');db.session.add(u);db.session.flush();return u

    def open_card(self, **changes):
        data=dict(UserId=3,OpenMonths=1,ExpectedPrice=39900,RequestKey=str(uuid.uuid4()))
        data.update(changes)
        return self.post('month-card/v1/manual-open', data)

    def test_manual_open_is_headquarters_only_and_rejects_channel_override(self):
        before = db.session.get(User,3).month_card_expire
        for source in ('gift', 'third_party', 'wechat'):
            self.assertEqual(self.open_card(Source=source).status_code,400)
        self.assertEqual(self.post('month-card/v1/manual-open',dict(UserId=3,OpenMonths=1,
            ExpectedPrice=39900,RequestKey=str(uuid.uuid4())),2,2).status_code,403)
        self.assertEqual(self.client.post('/admin_api/month-card/v1/manual-open',json={}).status_code,401)
        self.assertEqual(MonthCardOrder.query.count(),0)
        self.assertEqual(SettlementCardPool.query.count(),0)
        self.assertEqual(db.session.get(User,3).month_card_expire,before)
        self.assertEqual(self.post('month-card/v1/config',dict(Price=49900,ExpectedPrice=39900,Note='无权限'),2,2).status_code,403)

    def test_manual_open_fixed_terms_hq_pools_no_payment_or_remittance(self):
        at=datetime(2026,1,31,12)
        with patch('app.api.v1.month_card._now',return_value=at.replace(microsecond=750000)):
            response=self.open_card(OpenMonths=2)
        self.assertEqual(response.status_code,200,response.json)
        order=MonthCardOrder.query.one()
        self.assertEqual((order.source,order.open_type,order.settle_status,order.amount,order.duration_days),
                         ('gift',2,1,79800,60))
        self.assertEqual(order.operator,'1')
        self.assertEqual(db.session.get(User,3).month_card_expire,at+timedelta(days=60))
        pools=SettlementCardPool.query.order_by(SettlementCardPool.starts_at).all()
        self.assertEqual(len(pools),2)
        self.assertTrue(all(p.payer_id==0 and p.amount==39900 for p in pools))
        self.assertEqual(pools[0].starts_at,at)
        self.assertEqual(pools[0].ends_at,pools[1].starts_at)
        self.assertEqual(pools[1].ends_at,at+timedelta(days=60))
        self.assertEqual(PayOrder.query.count(),0)
        self.assertEqual(SettlementCardRemittance.query.count(),0)
        self.assertEqual(AccessAudit.query.filter_by(action='month-card:manual-open').count(),1)

    def test_manual_renewal_starts_at_existing_expiry_or_now(self):
        at=datetime(2026,1,31,12)
        user=db.session.get(User,3)
        user.month_card_expire=at+timedelta(days=5);db.session.commit()
        with patch('app.api.v1.month_card._now',return_value=at):
            self.assertEqual(self.open_card().status_code,200)
        self.assertEqual(user.month_card_expire,at+timedelta(days=35))
        user.month_card_expire=at-timedelta(days=5);db.session.commit()
        with patch('app.api.v1.month_card._now',return_value=at):
            self.assertEqual(self.open_card().status_code,200)
        self.assertEqual(user.month_card_expire,at+timedelta(days=30))

    def test_manual_retry_after_price_change_or_store_switch_does_not_extend(self):
        key=str(uuid.uuid4())
        first=self.open_card(RequestKey=key)
        before=db.session.get(User,3).month_card_expire
        row=Config.query.filter_by(config_key='MonthCardConfig').one()
        row.config_value={'CommonPrice':49900};db.session.commit()
        second=self.post('month-card/v1/manual-open',dict(UserId=3,OpenMonths=1,
            ExpectedPrice=39900,RequestKey=key),store=2)
        self.assertEqual(second.status_code,200,second.json)
        self.assertEqual(first.json['Data']['Id'],second.json['Data']['Id'])
        self.assertEqual(db.session.get(User,3).month_card_expire,before)
        self.assertEqual(MonthCardOrder.query.count(),1)
        self.assertEqual(SettlementCardPool.query.count(),1)
        self.assertEqual(self.open_card(RequestKey=key,OpenMonths=2).status_code,400)
        self.assertEqual(self.open_card(RequestKey=key,UserId=2).status_code,400)

    def test_manual_open_rejects_invalid_parameters_and_stale_price_atomically(self):
        for changes in [dict(UserId=True),dict(UserId=999),dict(OpenMonths=0),dict(OpenMonths=13),
                        dict(OpenMonths=1.5),dict(OpenMonths=True),dict(ExpectedPrice=True),
                        dict(ExpectedPrice=49900),dict(RequestKey='bad'),dict(Amount=1),dict(StoreId=2)]:
            self.assertEqual(self.open_card(**changes).status_code,400,changes)
        self.assertEqual(MonthCardOrder.query.count(),0)
        self.assertEqual(SettlementCardPool.query.count(),0)
        self.assertIsNone(db.session.get(User,3).month_card_expire)

    def test_manual_pool_failure_rolls_back_card_and_expiry(self):
        with patch('app.api.v1.month_card.settlement.create_card_pools',side_effect=ValueError('模拟失败')):
            self.assertEqual(self.open_card().status_code,400)
        self.assertEqual(MonthCardOrder.query.count(),0)
        self.assertEqual(SettlementCardPool.query.count(),0)
        self.assertIsNone(db.session.get(User,3).month_card_expire)

    def test_manual_card_is_subsidy_not_revenue_and_allocates_without_fee(self):
        from app.api.v1.stats import _membership_summary
        from app.settlement import fees
        at=datetime(2026,1,1)
        with patch('app.api.v1.month_card._now',return_value=at):
            self.assertEqual(self.open_card().status_code,200)
        summary=_membership_summary(at,datetime(2026,2,1))
        self.assertEqual(summary['Revenue'],0)
        self.assertEqual(summary['SubsidyAmount'],399)
        p=SettlementCardPool.query.one();self.usage(p,datetime(2026,1,5),2)
        prepare_cards('2026-01');db.session.flush()
        entry=SettlementEntry.query.one()
        self.assertEqual((entry.payer_id,entry.receiver_id,entry.amount),(0,2,39900))
        disclosure,charges=fees.calculate('2026-01',[dict(kind=entry.kind,reference=entry.reference,
            payer_id=entry.payer_id,receiver_id=entry.receiver_id,amount=entry.amount)])
        self.assertEqual(disclosure[0]['Fee'],0)
        self.assertEqual(charges,[])

    def batch(self, **changes):
        data = dict(UserIds=[2,3], OpenMonths=2, ExpectedPrice=39900, RequestKey=str(uuid.uuid4()))
        data.update(changes)
        return self.post('month-card/v1/manual-open-batch', data)

    def test_batch_opens_all_users_with_individual_expiry_and_hq_pools(self):
        at = datetime(2026,1,31,12)
        db.session.get(User,2).month_card_expire = at + timedelta(days=10)
        db.session.commit()
        with patch('app.api.v1.month_card._now', return_value=at):
            response = self.batch()
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(len(response.json['Data']['Items']),2)
        self.assertEqual(db.session.get(User,2).month_card_expire,at+timedelta(days=70))
        self.assertEqual(db.session.get(User,3).month_card_expire,at+timedelta(days=60))
        self.assertEqual(MonthCardOrder.query.count(),2)
        self.assertEqual(SettlementCardPool.query.count(),4)
        self.assertTrue(all(p.payer_id == 0 and p.amount == 39900 for p in SettlementCardPool.query))
        self.assertEqual(sum(o.amount for o in MonthCardOrder.query),159600)
        self.assertEqual(PayOrder.query.count(),0)
        self.assertEqual(SettlementCardRemittance.query.count(),0)

    def test_batch_retry_keeps_identity_across_order_price_and_store_changes(self):
        key = str(uuid.uuid4())
        first = self.batch(RequestKey=key)
        expiries = [db.session.get(User,uid).month_card_expire for uid in (2,3)]
        Config.query.filter_by(config_key='MonthCardConfig').one().config_value={'CommonPrice':49900}
        db.session.commit()
        second = self.post('month-card/v1/manual-open-batch',dict(UserIds=[3,2],OpenMonths=2,
            ExpectedPrice=39900,RequestKey=key),store=2)
        self.assertEqual(second.status_code,200,second.json)
        self.assertEqual(first.json['Data'],second.json['Data'])
        self.assertEqual([db.session.get(User,uid).month_card_expire for uid in (2,3)],expiries)
        for changes in [dict(UserIds=[3]),dict(UserIds=[1,2,3]),dict(OpenMonths=1),dict(ExpectedPrice=49900)]:
            self.assertEqual(self.batch(RequestKey=key,**changes).status_code,400)
        self.assertEqual(MonthCardOrder.query.count(),2)
        self.assertEqual(SettlementCardPool.query.count(),4)

    def test_batch_invalid_user_or_parameters_never_partially_open(self):
        for changes in [dict(UserIds=[]),dict(UserIds=[3,3]),dict(UserIds=[3,999]),dict(UserIds=[True]),
            dict(UserIds=3),dict(UserIds=[3]*101),dict(UserIds=[2**63]),dict(OpenMonths=13),
            dict(ExpectedPrice=49900),dict(Source='wechat'),dict(RequestKey='bad')]:
            self.assertEqual(self.batch(**changes).status_code,400,changes)
        self.assertEqual(MonthCardOrder.query.count(),0)
        self.assertTrue(all(db.session.get(User,uid).month_card_expire is None for uid in (2,3)))
        self.assertEqual(self.post('month-card/v1/manual-open-batch',dict(UserIds=[3],OpenMonths=1,
            ExpectedPrice=39900,RequestKey=str(uuid.uuid4())),user=2,store=2).status_code,403)
        self.assertEqual(self.client.post('/admin_api/month-card/v1/manual-open-batch',json={}).status_code,401)

    def test_batch_later_pool_failure_rolls_back_earlier_order_pool_and_expiry(self):
        create_pools = service.create_card_pools
        def fail_second(order, start, payer):
            if order.open_id == 'customer':
                raise ValueError('模拟第二位用户失败')
            return create_pools(order,start,payer)
        with patch('app.api.v1.month_card.settlement.create_card_pools',side_effect=fail_second):
            response=self.batch()
        self.assertEqual(response.status_code,400,response.json)
        self.assertEqual(MonthCardOrder.query.count(),0)
        self.assertEqual(SettlementCardPool.query.count(),0)
        self.assertEqual(AccessAudit.query.filter_by(action='month-card:manual-open').count(),0)
        self.assertTrue(all(db.session.get(User,uid).month_card_expire is None for uid in (2,3)))

    def test_half_term_per_month_uses_each_months_play_weights(self):
        p=self.pool();self.usage(p,datetime(2026,1,20),1,3600);self.usage(p,datetime(2026,2,5),2,7200)
        prepare_cards('2026-01');prepare_cards('2026-01');db.session.commit()
        self.assertEqual(p.status,'open');self.assertEqual(service.totals('2026-01')[1]['income'],19950)
        view=card_view(p,'2026-01',SettlementCardUsage.query.all())
        self.assertEqual((view['released_amount'],view['distributed_total'],view['future_amount']),(19950,19950,19950))
        prepare_cards('2026-02');prepare_cards('2026-02');db.session.commit()
        self.assertEqual(service.totals('2026-02')[2]['income'],19950)
        self.assertEqual(SettlementCardPeriod.query.count(),2);self.assertEqual(sum(e.amount for e in SettlementEntry.query),39900)
        self.assertEqual(p.status,'closed')
        own=self.client.get('/admin_api/settlement/v1/cards?Scope=all&Month=2026-01',headers=self.headers(2,2)).json['Data']['Items'][0]
        self.assertEqual(own['estimated'],[])
        self.assertTrue(all(x['store_id']==2 for period in own['periods'] for x in period['shares']+period['carry_shares']))

    def test_cross_month_visit_and_exact_cent_conservation(self):
        p=self.pool(datetime(2026,1,31,23,30),amount=10001)
        self.usage(p,datetime(2026,1,31,23,45),seconds=3600)
        self.assertEqual(sum(window(p,m)[2] for m in ['2026-01','2026-02','2026-03']),10001)
        prepare_cards('2026-01');self.assertEqual(SettlementCardPeriod.query.one().shares[0]['seconds'],900)
        prepare_cards('2026-03');db.session.flush()
        self.assertEqual(SettlementCardPeriod.query.filter_by(month='2026-02').one().shares[0]['seconds'],2700)
        self.assertEqual(sum(x.amount for x in SettlementEntry.query),10001)

    def test_carry_then_allocate_at_expiry_and_unused_card_goes_hq(self):
        p=self.pool();self.usage(p,datetime(2026,1,20),1)
        prepare_cards('2026-02');db.session.flush()
        final=SettlementCardPeriod.query.filter_by(month='2026-02').one()
        self.assertEqual(final.carry_amount,19950);self.assertEqual(final.carry_shares[0]['store_id'],1)
        self.assertEqual(sum(e.amount for e in SettlementEntry.query),39900)
        p2=SettlementCardPool(source_key='card:2:0',order_id=2,open_id='customer',starts_at=datetime(2026,3,17),ends_at=datetime(2026,4,16),amount=39900,payer_id=0,status='open');db.session.add(p2);db.session.flush()
        prepare_cards('2026-03');self.assertEqual(SettlementEntry.query.filter_by(reference=f'card:{p2.id}').count(),0)
        prepare_cards('2026-04');db.session.flush()
        e=SettlementEntry.query.filter_by(reference=f'card:{p2.id}').one();self.assertEqual((e.receiver_id,e.amount),(0,39900))

    def test_future_month_and_unreviewed_or_unfinished_usage_block(self):
        p=self.pool();u=self.usage(p,datetime(2026,1,20),status='review')
        with self.assertRaisesRegex(ValueError,'待核验'):prepare_cards('2026-01')
        u.status='valid'
        db.session.add(PlayOrder(open_id='customer',store_id=1,in_time=datetime(2026,1,31),out_time=None));db.session.flush()
        with self.assertRaisesRegex(ValueError,'未离场'):prepare_cards('2026-01')
        with patch('app.settlement.cards.now',return_value=datetime(2026,1,31,23,59)):
            with self.assertRaisesRegex(ValueError,'尚未结束'):prepare_cards('2026-01')

    def test_retired_monthly_worker_cannot_change_any_financial_state(self):
        from scripts.settle_monthly import run_once
        p=self.pool();self.usage(p,datetime(2026,1,20));db.session.commit()
        with self.assertRaisesRegex(RuntimeError,'停用'):run_once(self.app)
        self.assertEqual(SettlementCardPeriod.query.count(),0)
        self.assertEqual(SettlementPeriod.query.count(),0)
        self.assertEqual(SettlementStatement.query.count(),0)
