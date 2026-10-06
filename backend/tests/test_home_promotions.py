import copy
import unittest
from unittest.mock import patch
from flask import Flask, g, request, abort
from types import SimpleNamespace
from app import db
from app.models import Config
from app.api.v1.promotion import promotion_bp
from app.api.v1.banner import banner_bp
from app.services.home_promotions import DEFAULT_PROMOTIONS, validate_promotions


class HomePromotionsTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite://', SQLALCHEMY_TRACK_MODIFICATIONS=False)
        db.init_app(self.app)
        self.app.register_blueprint(promotion_bp, url_prefix='/promotions')
        self.app.register_blueprint(banner_bp, url_prefix='/banners')
        self.legacy = {'HomeBanners': [], 'HomeBannerItems': [], 'OtherSetting': {'Keep': True}}
        with self.app.app_context():
            Config.__table__.create(db.engine)
            db.session.add(Config(config_key='CommonConfig', config_value=self.legacy))
            db.session.commit()
        self.client = self.app.test_client()
        def authenticated():
            if not request.headers.get("Authorization"): abort(401)
            g.staff = SimpleNamespace(user_id=1, headquarters=True)
            g.grants = {}
            request.user = {'user_id':1}
        self.auth = patch('app.middlewares.auth.authenticate', side_effect=authenticated)
        self.audit = patch('app.middlewares.auth.audit')
        self.audit.start()
        self.addCleanup(self.audit.stop)
        self.auth.start()
        self.addCleanup(self.auth.stop)
        self.headers = {'Authorization': 'Bearer test', 'X-Store-ID':'1'}

    def get(self):
        return self.client.get('/promotions', headers=self.headers).json['Data']

    def put(self, config, revision=None):
        return self.client.put('/promotions', headers=self.headers, json={
            'Config': config, 'Revision': self.get()['Revision'] if revision is None else revision})

    def configured(self):
        result = copy.deepcopy(DEFAULT_PROMOTIONS)
        result['Splash'].update(Img='https://example.com/splash.jpg', Enabled=True, Frequency='entry')
        result['Popup'].update(Enabled=True, Items=[
            {'Id': 'b', 'Title': 'B', 'Img': 'https://example.com/b.jpg', 'Enabled': True, 'Sort': 20},
            {'Id': 'a', 'Title': 'A', 'Img': 'https://example.com/a.jpg', 'Enabled': False, 'Sort': 10},
        ])
        return result

    def test_defaults_off_and_read_does_not_write(self):
        self.assertEqual(self.get()['Config'], DEFAULT_PROMOTIONS)
        with self.app.app_context():
            self.assertEqual(Config.query.first().config_value, self.legacy)
        self.assertEqual(self.client.get('/promotions').status_code, 401)
        self.assertEqual(self.client.put('/promotions', json={}).status_code, 401)

    def test_save_preserves_other_common_config_and_independent_frequencies(self):
        result = self.put(self.configured())
        self.assertEqual(result.status_code, 200)
        saved = self.get()['Config']
        self.assertEqual(saved['Splash']['Frequency'], 'entry')
        self.assertEqual(saved['Popup']['Frequency'], 'daily')
        self.assertEqual([i['Id'] for i in saved['Popup']['Items']], ['a', 'b'])
        with self.app.app_context():
            value = Config.query.first().config_value
            for key, expected in self.legacy.items():
                self.assertEqual(value[key], expected)

    def test_single_splash_slot_and_validation(self):
        invalid = []
        for key, value in [('Seconds', 0), ('Seconds', 6), ('Seconds', True), ('Frequency', 'hourly'),
                           ('Enabled', 'false'), ('Img', ''), ('Img', 'javascript:alert(1)')]:
            data = self.configured()
            data['Splash'][key] = value
            invalid.append(data)
        data = self.configured()
        data['Splash'] = [data['Splash'], data['Splash']]
        invalid.append(data)
        data = self.configured()
        data['Popup']['Items'] = [data['Popup']['Items'][0]] * 2
        invalid.append(data)
        data = self.configured()
        data['Popup']['Frequency'] = 'hourly'
        invalid.append(data)
        for data in invalid:
            with self.subTest(data=data):
                self.assertEqual(self.put(data).status_code, 400)
        self.assertEqual(self.get()['Config'], DEFAULT_PROMOTIONS)

    def test_stale_revision_rejected_and_banner_edits_do_not_conflict(self):
        old = self.get()
        banners = self.client.get('/banners', headers=self.headers).json['Data']
        banner = dict(Id='banner', Title='Banner', Img='https://example.com/banner.jpg', Preview='',
                      Action='none', Page='', Enabled=True, Sort=1)
        response = self.client.put('/banners', headers=self.headers,
                                   json={'Items': [banner], 'Revision': banners['Revision']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.put(self.configured(), old['Revision']).status_code, 200)
        self.assertEqual(self.put(DEFAULT_PROMOTIONS, old['Revision']).status_code, 409)
        with self.app.app_context():
            value = Config.query.first().config_value
            self.assertEqual(value['HomeBannerItems'], [banner])
            self.assertTrue(value['HomePromotions']['Splash']['Enabled'])

    def test_disable_group_keeps_images_and_ignores_click_actions(self):
        data = self.configured()
        data['Popup']['Enabled'] = False
        data['Popup']['Items'][0]['Action'] = 'page'
        data['Splash']['Page'] = '/pages/test/index'
        self.assertEqual(self.put(data).status_code, 200)
        result = self.get()['Config']
        self.assertFalse(result['Popup']['Enabled'])
        self.assertEqual(len(result['Popup']['Items']), 2)
        self.assertNotIn('Action', result['Popup']['Items'][1])
        self.assertNotIn('Page', result['Splash'])
        self.assertEqual(validate_promotions(DEFAULT_PROMOTIONS), DEFAULT_PROMOTIONS)


if __name__ == '__main__':
    unittest.main()
