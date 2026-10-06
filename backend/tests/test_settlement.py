import hashlib
import os
import random
import uuid
import unittest
from datetime import datetime,timedelta
from unittest.mock import patch
from app import create_app,db
from app.models import Store,User,WalletAccount,WalletRechargeOrder,WalletTransaction,PayOrder,PointAccount,PointRedeemOrder,MonthCardOrder,PlayOrder
from app.security.models import StaffAccount,StaffGrant,OASession,AccessAudit
from app.utils.crypto import encrypt_phone
from app.settlement.models import *
from app.settlement import service, reports
from app.settlement.opening import initialize

class SettlementTest(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'STORE_SETTLEMENT_ENABLED':'true'});self.env.start()
        self.app=create_app({'TESTING':True,'OA_LOGIN_MODE':'sms','SQLALCHEMY_DATABASE_URI':'sqlite://'})
        self.ctx=self.app.app_context();self.ctx.push();db.create_all()
        db.session.add_all([Store(id=1,code='nanshan',name='南山'),Store(id=2,code='b',name='B店'),User(id=1,open_id='admin'),User(id=2,open_id='manager'),User(id=3,open_id='p')])
        for uid,hq in ((1,True),(2,False)):
            db.session.add(StaffAccount(user_id=uid,phone_cipher=encrypt_phone(f'1380013800{uid}'),enabled=True,headquarters=hq,version=1))
            db.session.add(OASession(token_digest=hashlib.sha256(f'settlement-{uid}'.encode()).hexdigest(),user_id=uid,account_version=1,expires_at=datetime.utcnow()+timedelta(hours=1)))
        db.session.add_all([StaffGrant(user_id=2,store_id=1,role='worker'),StaffGrant(user_id=2,store_id=2,role='manager')]);db.session.commit()
        db.session.add(SettlementControl(id=1,cutoff=datetime(2026,1,1),initialized_at=datetime(2026,1,1),legacy_wallet_payer=1,legacy_card_policy='full-period'));db.session.commit()
        self.client=self.app.test_client()
    def tearDown(self):
        db.session.remove();db.drop_all();self.ctx.pop();self.env.stop()
    def headers(self,user=1,store=1):return {'Authorization':f'Bearer settlement-{user}','X-Store-ID':str(store)}
    def pool(self,amount=39900):
        # Allocator fixtures use exempt gift cards; online fee behavior has its own tests.
        db.session.add(MonthCardOrder(id=1,open_id='p',open_period=1,amount=amount,open_type=1,settle_status=1,source='gift'))
        db.session.flush()
        p=SettlementCardPool(source_key='card:1:0',order_id=1,open_id='p',starts_at=datetime(2026,1,1),ends_at=datetime(2026,2,1),amount=amount,payer_id=0,status='open');db.session.add(p);db.session.flush();return p
    def usage(self,p,store,seconds=3600,status='valid'):
        u=SettlementCardUsage(pool_id=p.id,play_order_id=store,store_id=store,started_at=p.starts_at,ended_at=p.starts_at+timedelta(seconds=seconds),seconds=seconds,status=status,note='');db.session.add(u);db.session.flush();return u
    def settle_report(self,month='2026-01'):
        r=reports.current(month) or reports.generate(month,1,str(uuid.uuid4()))
        references={str(t['StoreId']):'本地模拟回单' for t in r.payload['totals'] if t['StoreId'] and t['amount']}
        reports.confirm(r.id,r.digest,1,references,True)
        return r
    def test_apportion_conserves_every_cent(self):
        rng=random.Random(7)
        for _ in range(300):
            weights={i:rng.randint(1,10000) for i in range(rng.randint(1,30))};amount=rng.randint(0,10000000)
            result=service.apportion(amount,weights)
            self.assertEqual(sum(result.values()),amount)
            self.assertTrue(all(abs(result[k]-amount*weights[k]/sum(weights.values()))<1 for k in weights))
        self.assertEqual(service.apportion(39900,{}),{0:39900})
    def test_month_card_weighted_and_idempotent(self):
        p=self.pool();self.usage(p,1,3600);self.usage(p,2,7200)
        service.close_card(p.id);service.close_card(p.id);db.session.commit()
        self.assertEqual([(x.receiver_id,x.amount) for x in SettlementEntry.query.order_by(SettlementEntry.receiver_id)],[(1,13300),(2,26600)])
    def test_zero_use_goes_headquarters_and_anomaly_blocks(self):
        p=self.pool();u=self.usage(p,1,90000,'review')
        with self.assertRaises(ValueError):service.close_card(p.id)
        u.status='excluded';service.close_card(p.id);db.session.flush();self.assertEqual(SettlementEntry.query.one().receiver_id,0)
    def test_point_cost_both_responsibility_and_provider(self):
        for store,points in ((1,60),(2,40)):
            b=SettlementBatch(kind='point',open_id='p',source_key=f'point:{store}',source_store_id=store,responsible_store_id=store,face_total=points,remaining=0);db.session.add(b);db.session.flush()
            db.session.add(SettlementAllocation(biz_key=f'debit:{store}',batch_id=b.id,kind='point',open_id='p',reference='redeem:1',expense_key='redeem:1',amount=points,state='consumed'))
        e=SettlementExpense(expense_key='redeem:1',kind='redeem',source_id=1,amount=5000,provider_id=2,status='ready',completed_at=datetime(2026,1,20));db.session.add(e);db.session.flush()
        service.post_expense(e.id);service.post_expense(e.id);db.session.flush()
        totals=service.totals('2026-01');self.assertEqual(totals[1]['amount'],-3000);self.assertEqual(totals[2]['amount'],3000)
        db.session.commit()
        detail=self.client.get('/admin_api/settlement/v1/allocations?Reference=redeem:1&Scope=all',headers=self.headers()).json['Data']['Expense']
        self.assertEqual(detail['total_points'],100)
        self.assertEqual({x['store_id']:x['amount'] for x in detail['shares']},{1:3000,2:2000})
        own=self.client.get('/admin_api/settlement/v1/allocations?Reference=redeem:1&Scope=all',headers=self.headers(2,2)).json['Data']['Expense']
        self.assertEqual(own['shares'],[{'store_id':2,'amount':2000,'points':40}])
    def test_locked_period_immutable_and_statement_idempotent(self):
        service.add_entry(biz_key='one',kind='wallet',reference='pay:1',payer_id=0,receiver_id=1,amount=10000,event_at=datetime(2026,1,2),detail='test')
        self.settle_report();self.settle_report();db.session.flush()
        self.assertEqual(SettlementStatement.query.count(),1)
        service.add_entry(biz_key='refund',kind='wallet_refund',reference='pay:1',payer_id=0,receiver_id=1,amount=-10000,event_at=datetime(2026,1,3),detail='refund');db.session.flush()
        self.assertEqual(SettlementEntry.query.filter_by(biz_key='refund').one().month,'2026-02')
        self.assertEqual(SettlementStatement.query.one().amount,9940)
    def test_missing_cost_blocks_month_lock(self):
        db.session.add(SettlementExpense(expense_key='redeem:1',kind='redeem',source_id=1,status='needs_cost',completed_at=datetime(2026,1,2)));db.session.flush()
        with self.assertRaises(ValueError):self.settle_report()

    def test_disabled_service_rejects_mutation_and_details_are_paginated(self):
        with patch.dict(os.environ,{'STORE_SETTLEMENT_ENABLED':'false'}):
            r=self.client.post('/admin_api/settlement/v1/lock',json={'Month':'2026-01'},headers=self.headers())
            self.assertEqual(r.status_code,503)
        b=SettlementBatch(kind='point',open_id='p',source_key='pagination',face_total=30,remaining=0)
        db.session.add(b);db.session.flush()
        for i in range(30):
            db.session.add(SettlementAllocation(biz_key=f'page:{i}',batch_id=b.id,kind='point',open_id='p',reference='raffle:1',expense_key='raffle:1',amount=1,state='consumed'))
        db.session.commit()
        r=self.client.get('/admin_api/settlement/v1/allocations?Reference=raffle:1&Scope=all&Current=2',headers=self.headers()).json['Data']
        self.assertEqual(r['Total'],30);self.assertEqual(len(r['Items']),10)
    def test_store_scope_and_headquarters_only_actions(self):
        service.add_entry(biz_key='a',kind='wallet',reference='pay:1',payer_id=0,receiver_id=1,amount=100,event_at=datetime(2026,1,1),detail='A')
        service.add_entry(biz_key='b',kind='wallet',reference='pay:2',payer_id=0,receiver_id=2,amount=200,event_at=datetime(2026,1,1),detail='B');db.session.commit()
        self.assertEqual(self.client.get('/admin_api/settlement/v1/overview',headers=self.headers(2,1)).status_code,403)
        r=self.client.get('/admin_api/settlement/v1/overview?Month=2026-01&Scope=all',headers=self.headers(2,2)).json['Data']
        self.assertEqual([x['reference'] for x in r['Entries']],['pay:2'])
        self.assertEqual(self.client.post('/admin_api/settlement/v1/lock',json={'Month':'2026-01'},headers=self.headers(2,2)).status_code,403)
    def test_opening_preserves_balances_and_rollback(self):
        db.session.delete(db.session.get(SettlementControl,1));db.session.commit()
        at=datetime(2026,1,1);cutoff=datetime(2026,2,1)
        db.session.add_all([WalletAccount(id=1,open_id='p',balance=60000,frozen_balance=0),WalletRechargeOrder(id=1,open_id='p',amount=100000,bonus_amount=20000,status=1),PayOrder(id=1,open_id='p',store_id=1,amount=60000,pay_status=1,pay_type=3),PointAccount(id=1,open_id='p',balance=70)])
        def wt(id,typ,amount,before,after,**kwargs):return WalletTransaction(id=id,created_at=at,open_id='p',account_id=1,type=typ,direction='out' if typ=='consume' else 'in',amount=amount,balance_before=before,balance_after=after,frozen_before=0,frozen_after=0,biz_key=f'wallet:{id}',**kwargs)
        db.session.add_all([wt(1,'recharge',100000,0,100000,related_recharge_order_id=1),wt(2,'bonus',20000,100000,120000,related_recharge_order_id=1),wt(3,'consume',60000,120000,60000,related_pay_order_id=1)])
        db.session.commit()
        report=initialize(cutoff,1,'full-period');self.assertEqual(report['WalletPrincipal'],50000);self.assertEqual(report['WalletFace'],60000);self.assertEqual(report['Points'],70)
        db.session.rollback();self.assertEqual(SettlementBatch.query.count(),0);self.assertEqual(WalletAccount.query.one().balance,60000)
        initialize(cutoff,1,'full-period');db.session.commit();self.assertTrue(initialize(cutoff,1,'full-period')['AlreadyInitialized']);self.assertEqual(SettlementEntry.query.count(),0)
        with self.assertRaises(ValueError):initialize(cutoff,0,'full-period')

    def test_disabled_adjustment_cannot_change_confirmed_finances(self):
        service.add_entry(biz_key='original',kind='wallet',reference='pay:9',payer_id=0,receiver_id=1,amount=10000,event_at=datetime(2026,1,1),detail='original')
        self.settle_report();db.session.commit()
        e=SettlementEntry.query.filter_by(biz_key='original').one()
        data={'EntryId':e.id,'Amount':-1000,'Note':'核验后冲减','RequestKey':'local-adjustment-0001'}
        for _ in range(2):self.assertEqual(self.client.post('/admin_api/settlement/v1/adjustments',json=data,headers=self.headers()).status_code,400)
        self.assertEqual(SettlementEntry.query.filter_by(kind='adjustment').count(),0)
        self.assertEqual(AccessAudit.query.filter_by(action='settlement:adjustment').count(),0)
        statement=SettlementStatement.query.one()
        self.assertEqual(self.client.post(f'/admin_api/settlement/v1/statements/{statement.id}/paid',json={'PaymentRef':'本地模拟回单'},headers=self.headers()).status_code,400)
        self.assertEqual(statement.amount,9940)
        self.assertIsNotNone(db.session.get(SettlementStatement,statement.id).paid_at)

    def test_provisional_cost_can_be_revised_but_only_hq_confirmation_posts_it(self):
        b=SettlementBatch(kind='point',open_id='p',source_key='cost-review',source_store_id=1,responsible_store_id=1,face_total=100,remaining=0)
        db.session.add(b);db.session.flush()
        db.session.add(SettlementAllocation(biz_key='cost-review',batch_id=b.id,kind='point',open_id='p',reference='redeem:901',expense_key='redeem:901',amount=100,state='consumed'))
        e=SettlementExpense(expense_key='redeem:901',kind='redeem',source_id=901,amount=5000,provider_id=2,status='needs_cost',completed_at=datetime(2026,1,20))
        db.session.add(e);db.session.commit()
        with self.assertRaisesRegex(ValueError,'停用'):service.prepare_month('2026-01')
        self.assertEqual(SettlementEntry.query.count(),0)
        with self.assertRaisesRegex(ValueError,'资料'):self.settle_report()
        db.session.rollback()
        url=f'/admin_api/settlement/v1/expenses/{e.id}/confirm'
        body={'Amount':3000,'ProviderId':2,'Note':'核对实际奖品采购成本后修改'}
        self.assertEqual(self.client.post(url,json=body,headers=self.headers(2,2)).status_code,403)
        r=self.client.post(url,json=body,headers=self.headers())
        self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(db.session.get(SettlementExpense,e.id).amount,3000)
        self.assertEqual(SettlementEntry.query.count(),0)
        audit=AccessAudit.query.filter_by(action='settlement:expense').one().detail
        self.assertEqual(audit['before']['amount'],5000)
        self.assertEqual(audit['after']['amount'],3000)
        self.assertEqual(audit['after']['status'],'ready')
        self.settle_report();db.session.commit()
        self.assertEqual(self.client.post(url,json={**body,'Amount':1000},headers=self.headers()).status_code,400)
        self.settle_report();db.session.commit()
        self.assertEqual(SettlementStatement.query.filter_by(store_id=2).one().amount,3000)

    def test_pending_cost_estimate_can_be_saved_without_posting(self):
        e=SettlementExpense(expense_key='raffle:902',kind='raffle',source_id=902,amount=None,status='pending')
        db.session.add(e);db.session.commit()
        url=f'/admin_api/settlement/v1/expenses/{e.id}/confirm'
        for price in (3000,0,1200):
            r=self.client.post(url,json={'Amount':price,'ProviderId':2,'Note':'暂估，待开奖后再次核对'},headers=self.headers())
            self.assertEqual(r.status_code,200,r.json)
            self.assertEqual(db.session.get(SettlementExpense,e.id).amount,price)
            self.assertEqual(db.session.get(SettlementExpense,e.id).status,'pending')
            self.assertEqual(SettlementEntry.query.count(),0)
