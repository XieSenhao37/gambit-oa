"""Isolated SQLite checks; no real database or COS calls."""
import io
import unittest
from unittest.mock import patch
from tests import test_settlement as fixtures
from app import db
from app.models import BoardGame, PointAccount, User

class OALoadingAndGamesTest(unittest.TestCase):
    setUp = fixtures.SettlementTest.setUp
    tearDown = fixtures.SettlementTest.tearDown
    headers = fixtures.SettlementTest.headers

    def test_user_list_pagination_and_balance_sort(self):
        db.session.add(PointAccount(open_id='p', balance=120))
        db.session.commit()
        r = self.client.get('/admin_api/user/v1/list?SortField=PointBalance&SortOrder=desc&PageSize=1', headers=self.headers())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json['Data']['Total'], 3)
        self.assertEqual(r.json['Data']['Items'][0]['OpenId'], 'p')
        self.assertEqual(r.json['Data']['Items'][0]['PointBalance'], 120)

    def test_store_user_list_keeps_other_store_private(self):
        db.session.get(User, 3).registered_store_id = 2
        db.session.commit()
        r = self.client.get('/admin_api/user/v1/list', headers=self.headers(2, 2))
        self.assertEqual(r.status_code, 200)
        self.assertEqual([u['OpenId'] for u in r.json['Data']['Items']], ['p'])

    def test_mysql_zero_dates_do_not_crash_user_list(self):
        from datetime import datetime
        from types import SimpleNamespace
        from pymysql.converters import convert_datetime
        from flask_sqlalchemy.pagination import QueryPagination
        fake=SimpleNamespace(id=3,open_id='p',user_type=0,role=0,nick_name='test',gender=0,phone_number=None,
            month_card_expire=convert_datetime('0000-00-00 00:00:00'),
            created_at=convert_datetime('2026-01-02 12:34:56'),updated_at=convert_datetime('0000-00-00 00:00:00'))
        def invalid_dates(pagination):
            return [(fake,0,0,0)]
        with patch.object(QueryPagination,'_query_items',invalid_dates):
            response=self.client.get('/admin_api/user/v1/list',headers=self.headers())
        self.assertEqual(response.status_code,200)
        row=response.json['Data']['Items'][0]
        self.assertIsNone(row['MonthCardExpire'])
        self.assertIsNone(row['UpdatedAt'])
        self.assertEqual(row['CreatedAt'],'2026-01-02 12:34:56')

    def test_user_failure_has_safe_error_reference(self):
        with patch('app.api.v1.user._consumption_subquery',side_effect=RuntimeError('private-data')):
            with self.assertLogs(self.app.logger,level='ERROR') as logged:
                response=self.client.get('/admin_api/user/v1/list',headers=self.headers())
        self.assertEqual(response.status_code,500)
        self.assertEqual(len(response.json['ErrorId']),12)
        self.assertNotIn('private-data',str(response.json))
        self.assertNotIn('private-data',' '.join(logged.output))
        self.assertIn(response.json['ErrorId'],' '.join(logged.output))

    def test_invalid_game_does_not_upload(self):
        with patch('app.api.v1.game.upload_file_to_cos') as upload:
            r = self.client.post('/admin_api/game/v1/library', headers=self.headers(), data={
                'Name': '隔离测试', 'Description': '测试简介', 'Complexity': '99',
                'CoverImage': (io.BytesIO(b'image'), 'cover.png'),
            })
        self.assertEqual(r.status_code, 400)
        upload.assert_not_called()
        self.assertEqual(BoardGame.query.count(), 0)

    def test_game_upload_failure_leaves_no_created_game(self):
        with patch('app.api.v1.game.upload_file_to_cos', side_effect=RuntimeError('mock upload failure')):
            r = self.client.post('/admin_api/game/v1/library', headers=self.headers(), data={
                'Name': '隔离测试', 'Description': '测试简介',
                'CoverImage': (io.BytesIO(b'image'), 'cover.png'),
            })
        self.assertEqual(r.status_code, 500)
        self.assertEqual(BoardGame.query.count(), 0)

    def test_game_cover_and_picture_saved_once(self):
        with patch('app.api.v1.game.upload_file_to_cos', side_effect=['https://example.invalid/cover.png', 'https://example.invalid/detail.png']):
            r = self.client.post('/admin_api/game/v1/library', headers=self.headers(), data={
                'Name': '隔离测试', 'Description': '测试简介',
                'CoverImage': (io.BytesIO(b'image'), 'cover.png'),
                'PictureImages': (io.BytesIO(b'detail'), 'detail.png'),
            })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(BoardGame.query.count(), 1)
        self.assertEqual(r.json['Data']['PictureList'], ['https://example.invalid/detail.png'])


    def test_separate_image_upload_creates_no_game(self):
        with patch('app.api.v1.game.upload_file_to_cos', return_value='https://example.invalid/new.png') as upload:
            r = self.client.post('/admin_api/game/v1/library/image', headers=self.headers(), data={
                'Image': (io.BytesIO(b'image'), 'new.png'),
            })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json['Data']['Url'], 'https://example.invalid/new.png')
        upload.assert_called_once()
        self.assertEqual(BoardGame.query.count(), 0)

    def test_save_uploaded_urls_does_not_upload_again(self):
        with patch('app.api.v1.game.upload_file_to_cos') as upload:
            r = self.client.post('/admin_api/game/v1/library', headers=self.headers(), data={
                'Name': '预上传测试', 'Description': '测试简介',
                'CoverUrl': 'https://example.invalid/cover.png',
                'PictureList': '["https://example.invalid/detail.png"]',
            })
        self.assertEqual(r.status_code, 200)
        upload.assert_not_called()
        self.assertEqual(BoardGame.query.count(), 1)
        self.assertEqual(r.json['Data']['CoverUrl'], 'https://example.invalid/cover.png')

    def test_image_upload_validation_and_permission(self):
        self.assertEqual(self.client.post('/admin_api/game/v1/library/image', headers=self.headers()).status_code, 400)
        with patch('app.api.v1.game.upload_file_to_cos') as upload:
            r = self.client.post('/admin_api/game/v1/library/image', headers=self.headers(), data={
                'Image': (io.BytesIO(b'bad'), 'bad.txt'),
            })
            self.assertEqual(r.status_code, 400)
            upload.assert_not_called()
        self.assertEqual(self.client.post('/admin_api/game/v1/library/image').status_code, 401)
