from datetime import timedelta
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from flask import Flask, abort, g, request

from app import db
from app.api.v1.coupon import bp, now
from app.models import CouponPromotion, CouponRecord, User


class CouponManagementTest(TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite://')
        app.register_blueprint(bp, url_prefix='/coupon')
        db.init_app(app)
        self.app, self.client = app, app.test_client()
        with app.app_context():
            for model in (CouponPromotion, CouponRecord, User):
                model.__table__.create(db.engine)

        def authenticate():
            mode = request.headers.get('Authorization')
            if not mode:
                abort(401)
            g.staff = SimpleNamespace(user_id=1, headquarters=mode == 'headquarters')
            g.grants = {1: 'manager'}
            request.user = {'user_id': 1}

        for patcher in (
            patch('app.middlewares.auth.authenticate', side_effect=authenticate),
            patch('app.middlewares.auth.audit'),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.hq = {'Authorization': 'headquarters', 'X-Store-ID': '1'}
        current = now()
        self.config = {
            'ActivityName': '抽奖活动', 'Title': '桌游抵扣券', 'CouponType': 1, 'Amount': 1000,
            'MinimumAmount': 5000, 'Expire': 7 * 86400, 'ApplicableScenes': [0], 'CanReReceive': 0,
            'StartDate': (current - timedelta(hours=1)).isoformat(sep=' '),
            'EndDate': (current + timedelta(hours=1)).isoformat(sep=' '), 'Description': '',
            'Count': 10, 'ControlRoles': [127, 125],
        }

    def create(self):
        result = self.client.post('/coupon/activities', headers=self.hq, json=self.config)
        self.assertEqual(result.status_code, 200, result.json)
        return result.json['Data']['ID']

    def activity(self):
        result = self.client.get('/coupon/activities?Status=active&Keyword=桌游', headers=self.hq)
        self.assertEqual(result.status_code, 200, result.json)
        return result.json['Data']['Items'][0]

    def test_only_headquarters_can_read_and_write_coupon_activities(self):
        self.assertEqual(self.client.get('/coupon/activities').status_code, 401)
        manager = {'Authorization': 'store-manager', 'X-Store-ID': '1'}
        self.assertEqual(self.client.get('/coupon/activities', headers=manager).status_code, 403)
        self.assertEqual(self.client.post('/coupon/activities', headers=manager, json=self.config).status_code, 403)
        self.assertEqual(self.client.get('/coupon/activities/1/records', headers=manager).status_code, 403)

    def test_create_edit_and_validate_coupon_rules(self):
        for override in (
            {'ControlRoles': [0]}, {'StartDate': self.config['EndDate']},
            {'CouponType': 0, 'Amount': 2, 'ApplicableScenes': [1]}, {'Amount': 10.5},
        ):
            result = self.client.post('/coupon/activities', headers=self.hq, json={**self.config, **override})
            self.assertEqual(result.status_code, 400, result.json)
        id = self.create()
        item = self.activity()
        self.assertEqual(item['Available'], 10)
        self.assertEqual(item['ControlRoles'], [125, 127])
        self.assertFalse(item['TermsLocked'])
        self.assertEqual(
            self.client.get('/coupon/activities?Keyword=不存在', headers=self.hq).json['Data']['Total'], 0,
        )
        request_data = {**self.config, 'Title': '新名称', 'Revision': item['Revision']}
        self.assertEqual(self.client.put(f'/coupon/activities/{id}', headers=self.hq, json=request_data).status_code, 200)
        self.assertEqual(self.client.put(f'/coupon/activities/{id}', headers=self.hq, json=request_data).status_code, 409)

    def test_reserved_and_issued_coupons_keep_terms_and_expose_sources(self):
        id = self.create()
        with self.app.app_context():
            coupon = db.session.get(CouponPromotion, id)
            coupon.raffle_reserved = 3
            db.session.add(User(open_id='test-user', nick_name='测试玩家'))
            db.session.add(CouponRecord(promotion_id=id, open_id='test-user', status=0, raffle_entry_id=71,
                                        received_at=now(), expire_at=now() + timedelta(days=7)))
            db.session.commit()
        item = self.activity()
        self.assertEqual((item['Issued'], item['Reserved'], item['Available']), (1, 3, 6))
        save = lambda **changes: self.client.put(f'/coupon/activities/{id}', headers=self.hq, json={
            'Count': 10, 'ControlRoles': [1], 'Revision': item['Revision'], **changes,
        })
        self.assertEqual(save(Count=3).status_code, 409)
        self.assertEqual(save(MinimumAmount=1000).status_code, 409)
        self.assertEqual(save(Count=4).status_code, 200)
        self.assertEqual(self.activity()['ControlRoles'], [1])
        self.assertEqual(self.activity()['Available'], 0)
        records = self.client.get(f'/coupon/activities/{id}/records', headers=self.hq).json['Data']['Items']
        self.assertEqual(records[0]['Source'], '抽奖')
        self.assertEqual(records[0]['NickName'], '测试玩家')
        self.assertNotIn('OpenID', records[0])

    def test_referral_coupon_stays_read_only(self):
        self.assertEqual(self.client.put('/coupon/activities/11', headers=self.hq, json=self.config).status_code, 409)
