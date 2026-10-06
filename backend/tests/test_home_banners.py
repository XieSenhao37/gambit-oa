import copy
import unittest
from unittest.mock import patch
from flask import Flask, g, request, abort
from types import SimpleNamespace
from app import db
from app.models import Config
from app.api.v1.banner import banner_bp
from app.services.home_banners import ITEMS_KEY, migrate_banners, validate_items


class HomeBannersTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite://', SQLALCHEMY_TRACK_MODIFICATIONS=False)
        db.init_app(self.app)
        self.app.register_blueprint(banner_bp, url_prefix='/banners')
        with self.app.app_context():
            Config.__table__.create(db.engine)
            self.legacy = {'HomeBanners': [{'Img': 'https://example.com/old.jpg', 'Preview': 'https://example.com/old-preview.jpg'}, {'Img': 'https://example.com/extra.jpg', 'Preview': None}], 'OtherSetting': {'Keep': True}}
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
        return self.client.get('/banners', headers=self.headers).json['Data']

    def test_migrate_preserves_visible_order_and_legacy_config(self):
        response = self.get()
        items = response['Items']
        self.assertEqual([b['Action'] for b in items], ['page', 'page', 'preview', 'none'])
        self.assertTrue(items[2]['Img'].endswith('/PriceBanner0519.jpg'))
        self.assertTrue(items[2]['Preview'].endswith('/PricePreview.jpg'))
        self.assertEqual(items[3]['Img'], self.legacy['HomeBanners'][1]['Img'])
        result = self.client.put('/banners', headers=self.headers, json={'Items': items, 'Revision': response['Revision']})
        self.assertEqual(result.status_code, 200)
        with self.app.app_context():
            value = Config.query.first().config_value
            self.assertEqual(value['HomeBanners'], self.legacy['HomeBanners'])
            self.assertEqual(value['OtherSetting'], {'Keep': True})
            self.assertEqual(value[ITEMS_KEY], items)
        self.assertEqual(migrate_banners({ITEMS_KEY: []}), [])
        self.assertEqual(migrate_banners({ITEMS_KEY: items}), items)

    def test_conflict_does_not_overwrite_new_configuration(self):
        first = self.get()
        items = first['Items'];items[0]['Enabled'] = False
        saved = self.client.put('/banners', headers=self.headers, json={'Items': items, 'Revision': first['Revision']})
        self.assertEqual(saved.status_code, 200)
        stale = self.client.put('/banners', headers=self.headers, json={'Items': [], 'Revision': first['Revision']})
        self.assertEqual(stale.status_code, 409)
        self.assertFalse(self.get()['Items'][0]['Enabled'])

    def test_validation_and_auth(self):
        self.assertEqual(self.client.get('/banners').status_code, 401)
        base = self.get()['Items']
        for update in ({'Img': 'javascript:alert(1)'}, {'Action': 'preview', 'Preview': ''}, {'Page': 'https://example.com/page'}, {'Sort': -1}, {'Enabled': 'false'}):
            items = copy.deepcopy(base);items[0].update(update)
            with self.assertRaises(ValueError):validate_items(items)
        with self.assertRaises(ValueError):validate_items([base[0], base[0]])
        state = self.get()
        result = self.client.put('/banners', headers=self.headers, json={'Items': [], 'Revision': state['Revision']})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.get()['Items'], [])

    def test_custom_page_path_round_trip_preserves_parameters(self):
        state = self.get()
        items = state['Items']
        items[0]['Page'] = ' pages/eventCalendar/index?storeId=1&name=a%20b '
        result = self.client.put('/banners', headers=self.headers, json={'Items': items, 'Revision': state['Revision']})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.get()['Items'][0]['Page'], '/pages/eventCalendar/index?storeId=1&name=a%20b')
        self.assertEqual(self.get()['Items'][1]['Page'], '/pages/joinGroup/index')
        items[0]['Page'] = '/packages/events/index?id=1'
        self.assertEqual(validate_items(items)[0]['Page'], '/packages/events/index?id=1')

    def test_reject_invalid_page_paths_without_changing_saved_config(self):
        state = self.get()
        for page in ('', None, 123, '//example.com/page', '/pages/../admin', '/pages/referral/index#hash', '/pages/referral/index?x=not encoded', '/pages\\referral/index', '/pages/referral/index?x=\x00', '/pages/referral/index?x=' + 'a' * 2048):
            with self.subTest(page=repr(page)):
                items = copy.deepcopy(state['Items'])
                items[0]['Page'] = page
                result = self.client.put('/banners', headers=self.headers, json={'Items': items, 'Revision': state['Revision']})
                self.assertEqual(result.status_code, 400)
                self.assertEqual(self.get()['Revision'], state['Revision'])

    def test_reject_image_payload_disguised_as_jpeg(self):
        import io
        result = self.client.post('/banners/image', headers=self.headers, data={'File': (io.BytesIO(b'<html>not an image</html>'), 'fake.jpg')})
        self.assertEqual(result.status_code, 400)

    def test_image_upload_returns_reusable_url(self):
        import io
        with patch('app.api.v1.banner.upload_file_to_cos', return_value='https://example.com/new.jpg') as upload:
            result = self.client.post('/banners/image', headers=self.headers, data={'File': (io.BytesIO(b'\xff\xd8\xff\xe0test'), 'new.JPG')})
            self.assertEqual(result.json['Data']['Url'], 'https://example.com/new.jpg')
            self.assertEqual(upload.call_args.kwargs['folder'], 'home-banners')

if __name__ == '__main__':
    unittest.main()
