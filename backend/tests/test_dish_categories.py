import hashlib
import unittest
from datetime import datetime, timedelta

from app import create_app, db
from app.models import Dish, DishCategory, DishLibraryItem, Store, User
from app.security.models import OASession, StaffAccount, StaffGrant


class DishCategoriesTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            'TESTING': True, 'OA_LOGIN_MODE': 'sms',
            'SQLALCHEMY_DATABASE_URI': 'sqlite://',
            'GAMBIT_SERVER_BASE_URL': '', 'GAMBIT_INTERNAL_TOKEN': '',
        })
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        db.session.add_all([
            Store(id=1, code='a', name='A'), Store(id=2, code='b', name='B'),
            User(id=1, open_id='hq'), User(id=2, open_id='manager'),
            StaffAccount(user_id=1, phone_cipher='test', enabled=True, headquarters=True, version=1),
            StaffAccount(user_id=2, phone_cipher='test2', enabled=True, headquarters=False, version=1),
            StaffGrant(user_id=2, store_id=1, role='manager'),
        ])
        for uid in (1, 2):
            db.session.add(OASession(
                token_digest=hashlib.sha256(f'category-test-{uid}'.encode()).hexdigest(),
                user_id=uid, account_version=1, expires_at=datetime.utcnow() + timedelta(hours=1),
            ))
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def call(self, method='get', path='', data=None, uid=1):
        return getattr(self.client, method)(
            '/admin_api/dish/v1/categories' + path, json=data,
            headers={'Authorization': f'Bearer category-test-{uid}', 'X-Store-ID': '1'},
        )

    def create(self, name='咖啡', sort=0):
        response = self.call('post', data={'Name': name, 'Sort': sort})
        self.assertEqual(response.status_code, 200, response.json)
        return response.json['Data']

    def test_create_rename_sort_and_soft_delete(self):
        first = self.create(' 咖啡 ', 5)
        second = self.create('小食', 1)
        self.assertEqual(first['Name'], '咖啡')
        updated = self.call('put', f"/{first['Id']}", {**first, 'Name': '饮品', 'Sort': 0})
        self.assertEqual(updated.status_code, 200, updated.json)
        self.assertEqual([x['Name'] for x in self.call().json['Data']['Items']], ['饮品', '小食'])
        result = self.call('delete', f"/{second['Id']}", second)
        self.assertEqual(result.status_code, 200)
        self.assertIsNotNone(db.session.get(DishCategory, second['Id']).deleted_at)
        self.assertEqual(len(self.call().json['Data']['Items']), 1)
        self.create('小食')  # Soft-deleted names may be reused.

    def test_validation_and_duplicate_names(self):
        first = self.create()
        for data in ({'Name': ''}, {'Name': '  '}, {'Name': 42}, {'Name': '长' * 61},
                     {'Name': '茶', 'Sort': -1}, {'Name': '茶', 'Sort': 0.5},
                     {'Name': '茶', 'Sort': True}, {'Name': '茶', 'Sort': 2147483648},
                     {'Name': ' 咖啡 '}, []):
            with self.subTest(data=data):
                self.assertEqual(self.call('post', data=data).status_code, 400)
        second = self.create('茶')
        self.assertEqual(self.call('put', f"/{second['Id']}", {**second, 'Name': first['Name']}).status_code, 400)

    def test_conflicts_and_deleted_rows_cannot_be_edited(self):
        item = self.create()
        self.assertEqual(self.call('put', f"/{item['Id']}", {**item, 'Sort': 2}).status_code, 200)
        self.assertEqual(self.call('put', f"/{item['Id']}", {**item, 'Sort': 3}).status_code, 409)
        self.assertEqual(self.call('delete', f"/{item['Id']}", item).status_code, 409)
        latest = self.call().json['Data']['Items'][0]
        self.assertEqual(self.call('delete', f"/{item['Id']}", latest).status_code, 200)
        self.assertEqual(self.call('put', f"/{item['Id']}", latest).status_code, 404)

    def test_library_reference_prevents_delete_even_without_store_menu(self):
        item = self.create()
        db.session.add(DishLibraryItem(name='拿铁', category_ids=[item['Id']], default_price=100))
        db.session.commit()
        response = self.call('delete', f"/{item['Id']}", item)
        self.assertEqual(response.status_code, 400)
        self.assertIn('引用', response.json['Message'])
        self.assertIsNone(db.session.get(DishCategory, item['Id']).deleted_at)

    def test_other_store_and_down_shelf_legacy_reference_prevents_delete(self):
        item = self.create()
        db.session.add(Dish(name='旧菜单餐品', category_ids=[item['Id']], price=100, store_id=2, status=0))
        db.session.commit()
        self.assertEqual(self.call('delete', f"/{item['Id']}", item).status_code, 400)

    def test_deleted_dishes_do_not_block_delete(self):
        item = self.create()
        db.session.add(Dish(name='已删除餐品', category_ids=[item['Id']], price=100, store_id=2, deleted_at=datetime.utcnow()))
        db.session.commit()
        self.assertEqual(self.call('delete', f"/{item['Id']}", item).status_code, 200)

    def test_auth_and_headquarters_permissions(self):
        item = self.create()
        self.assertEqual(self.client.get('/admin_api/dish/v1/categories').status_code, 401)
        self.assertEqual(self.call(uid=2).status_code, 200)  # Menu editors can read choices.
        for method, path, data in [('post', '', {'Name': '茶'}), ('put', f"/{item['Id']}", item), ('delete', f"/{item['Id']}", item)]:
            self.assertEqual(self.call(method, path, data, uid=2).status_code, 403)
        me = self.client.get('/admin_api/auth/v1/me', headers={'Authorization': 'Bearer category-test-2'}).json['Data']
        self.assertNotIn('dish-categories', me['Stores'][0]['Pages'])

    def test_dish_save_rejects_missing_deleted_categories(self):
        item = self.create()
        self.call('delete', f"/{item['Id']}", item)
        for ids in ([item['Id']], [999], [], [True], [1.5], 'not-json'):
            response = self.client.post('/admin_api/dish/v1/library', json={
                'Name': '拿铁', 'DefaultPrice': 18, 'ImageUrl': 'https://example.test/latte.png', 'CategoryIds': ids,
            }, headers={'Authorization': 'Bearer category-test-1', 'X-Store-ID': '1'})
            self.assertEqual(response.status_code, 400, response.json)
        valid = self.create('茶')
        response = self.client.post('/admin_api/dish/v1/library', json={
            'Name': '茶饮', 'DefaultPrice': 18, 'ImageUrl': 'https://example.test/tea.png', 'CategoryIds': [valid['Id']],
        }, headers={'Authorization': 'Bearer category-test-1', 'X-Store-ID': '1'})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['Data']['CategoryIds'], [valid['Id']])
