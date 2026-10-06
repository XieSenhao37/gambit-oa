import unittest
from unittest.mock import patch
from app import create_app, db
from app.models import Store, PointProduct
from app.settlement.models import SettlementCostRule, SettlementExpense
from app.security.login_mode import ADMIN_USERNAME

ADMIN_PASSWORD = "local-only-test-password"


class PointSettlementPriceTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite://', 'OA_LOGIN_MODE': 'password', 'OA_ADMIN_PASSWORD': ADMIN_PASSWORD})
        self.ctx = self.app.app_context(); self.ctx.push(); db.create_all()
        db.session.add(Store(id=1, code='test', name='测试店')); db.session.commit()
        self.client = self.app.test_client()
        token = self.client.post('/admin_api/auth/v1/login', json={'username': ADMIN_USERNAME, 'password': ADMIN_PASSWORD}).json['Data']['token']
        self.headers = {'Authorization': 'Bearer ' + token, 'X-Store-ID': '1'}

    def tearDown(self):
        db.session.remove(); db.drop_all(); self.ctx.pop()

    def create_product(self, **extra):
        import io
        with patch('app.api.v1.point._validate_and_upload_image', return_value='https://example.test/product.png'):
            return self.client.post('/admin_api/point/v1/products', data={'Name':'积分商品', 'PointsPrice':'100', 'Status':'1', 'Image':(io.BytesIO(b'fixture'), 'test.png'), **extra}, headers=self.headers)

    def test_optional_price_blank_zero_and_changes_preserve_existing_expense(self):
        r = self.create_product()
        self.assertEqual(r.status_code,200,r.json)
        self.assertIsNone(r.json['Data']['SettlementPrice'])
        id = r.json['Data']['Id']; key = f'product:{id}'
        self.assertIsNone(db.session.get(SettlementCostRule,key))
        db.session.add(SettlementExpense(expense_key='redeem:1',kind='redeem',source_id=1,amount=5000,status='pending')); db.session.commit()
        url=f'/admin_api/point/v1/products/{id}'
        for value, expected in [('1234',1234),('0',0),('',None)]:
            r=self.client.put(url,json={'Name':'积分商品','PointsPrice':100,'SettlementPrice':value},headers=self.headers)
            self.assertEqual(r.status_code,200,r.json)
            self.assertEqual(r.json['Data']['SettlementPrice'],expected)
            rule=db.session.get(SettlementCostRule,key)
            self.assertEqual(rule.amount if rule else None,expected)
            self.assertEqual(SettlementExpense.query.one().amount,5000)
        r=self.create_product(SettlementPrice='800')
        id2=r.json['Data']['Id']
        self.client.put(f'/admin_api/point/v1/products/{id2}',json={'Name':'只修改名字','PointsPrice':100},headers=self.headers)
        self.assertEqual(db.session.get(SettlementCostRule,f'product:{id2}').amount,800)
        rows=self.client.get('/admin_api/point/v1/products',headers=self.headers).json['Data']['Items']
        self.assertEqual(next(x for x in rows if x['Id']==id2)['SettlementPrice'],800)

    def test_invalid_price_rejected_without_changing_product(self):
        r=self.create_product(SettlementPrice='1234'); id=r.json['Data']['Id']
        for value in (-1,True,1.5,'1.1','NaN',100000001):
            r=self.client.put(f'/admin_api/point/v1/products/{id}',json={'Name':'应回滚','PointsPrice':100,'SettlementPrice':value},headers=self.headers)
            self.assertEqual(r.status_code,400,r.json)
            self.assertEqual(db.session.get(PointProduct,id).name,'积分商品')
            self.assertEqual(db.session.get(SettlementCostRule,f'product:{id}').amount,1234)
