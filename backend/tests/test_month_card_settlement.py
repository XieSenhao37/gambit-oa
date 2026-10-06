"""Regressions for immutable card price, 30-day terms and monthly settlement."""
import hashlib
import os
import unittest
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch
from app import create_app, db
from app.models import Config, Store, User, MonthCardOrder, PlayOrder
from app.security.models import StaffAccount, StaffGrant, OASession
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

    def test_manual_open_removed_and_config_permissions_retained(self):
        before = db.session.get(User,3).month_card_expire
        for source in ('gift', 'third_party', 'wechat'):
            response=self.post('month-card/v1/manual-open',dict(UserId=3,Source=source,OpenMonths=1))
            self.assertEqual(response.status_code,404)
        self.assertEqual(MonthCardOrder.query.count(),0)
        self.assertEqual(SettlementCardPool.query.count(),0)
        self.assertEqual(db.session.get(User,3).month_card_expire,before)
        self.assertEqual(self.post('month-card/v1/config',dict(Price=49900,ExpectedPrice=39900,Note='无权限'),2,2).status_code,403)

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
