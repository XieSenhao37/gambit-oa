import hashlib
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
import requests
from sqlalchemy import text
from app import create_app, db
from app.models import Store, User, PayOrder
from app.security.models import StaffAccount, StaffGrant, OASession
from app.utils.crypto import encrypt_phone
from app.services.game_stock_guard import require_unallocated_inventory

class GameServicesTest(unittest.TestCase):
    def setUp(self):
        self.app=create_app({'TESTING':True,'OA_LOGIN_MODE':'sms','SQLALCHEMY_DATABASE_URI':'sqlite://','GAMBIT_SERVER_BASE_URL':'https://isolated-backend.invalid','GAMBIT_INTERNAL_TOKEN':'test-private-token'})
        self.ctx=self.app.app_context();self.ctx.push();db.create_all()
        db.session.add_all([Store(id=1,code='a',name='A'),Store(id=2,code='b',name='B'),User(id=1,open_id='staff')])
        db.session.add(StaffAccount(user_id=1,phone_cipher=encrypt_phone('13800138001'),enabled=True,headquarters=False,version=1))
        db.session.add_all([StaffGrant(user_id=1,store_id=1,role='manager'),StaffGrant(user_id=1,store_id=2,role='worker')])
        db.session.add(OASession(token_digest=hashlib.sha256(b'test').hexdigest(),user_id=1,account_version=1,expires_at=datetime.utcnow()+timedelta(hours=1)))
        db.session.commit();self.client=self.app.test_client();self.headers={'Authorization':'Bearer test','X-Store-ID':'1'}
        self.response=Mock();self.response.json.return_value={'Code':0,'Data':{'OK':True}}
    def tearDown(self):
        db.session.remove();db.drop_all();self.ctx.pop()
    def test_login_scope_and_backend_identity(self):
        self.assertEqual(self.client.get('/admin_api/game-service/v1/orders').status_code,401)
        with patch('app.api.v1.game_services.requests.request',return_value=self.response) as send:
            self.assertEqual(self.client.post('/admin_api/game-service/v1/action',headers=self.headers,json={'StoreID':1,'Actor':'impostor','Action':'accept','RequestKey':'stable-key'}).status_code,200)
            kwargs=send.call_args.kwargs
            self.assertEqual(kwargs['json']['StoreID'],1);self.assertEqual(kwargs['json']['Actor'],'1')
            self.assertEqual(kwargs['headers'],{'X-GAMBIT-INTERNAL-TOKEN':'test-private-token'})
            self.client.get('/admin_api/game-service/v1/orders?StoreID=1',headers=self.headers)
            self.assertEqual(send.call_args.kwargs['params']['StoreID'],1)
            self.assertEqual(self.client.get('/admin_api/game-service/v1/orders',headers={**self.headers,'X-Store-ID':'3'}).status_code,403)
    def test_todos_aggregate_authorized_stores_without_customer_data(self):
        path = '/admin_api/game-service/v1/todos'
        self.assertEqual(self.client.get(path).status_code, 401)
        def response(method, url, **kwargs):
            sid = kwargs['params']['StoreID']
            self.assertEqual(kwargs['params'], {'StoreID': sid, 'Status': 'todo', 'Page': 1})
            result = Mock()
            result.json.return_value = {'Code': 0, 'Data': {'Total': 1, 'Orders': [{'ID': sid, 'RequestedStoreID': sid, 'Status': 'pending_confirm', 'ContactPhone': 'private', 'OpenID': 'private', 'Lines': [{'GameName': '桌游'}]}]}}
            return result
        with patch('app.api.v1.game_services.requests.request', side_effect=response) as send:
            res = self.client.get(path+'?StoreID=999', headers={**self.headers, 'X-Store-ID': '999'})
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json['Data']['Total'], 2)
            self.assertEqual({i['StoreID'] for i in res.json['Data']['Items']}, {1,2})
            self.assertNotIn('private', res.get_data(as_text=True))
            self.assertEqual(send.call_count, 2)
            db.session.get(Store, 2).status = 0
            db.session.commit()
            self.assertEqual(self.client.get(path, headers=self.headers).json['Data']['Total'], 1)

    def test_todos_permission_revocation_and_upstream_failure(self):
        from app.security.models import RolePage
        path = '/admin_api/game-service/v1/todos'
        with patch('app.api.v1.game_services.requests.request', side_effect=requests.Timeout):
            self.assertEqual(self.client.get(path, headers=self.headers).status_code, 502)
        db.session.add_all([RolePage(role='manager', page_id='game-service-orders', allowed=False), RolePage(role='worker', page_id='game-service-orders', allowed=False)])
        db.session.commit()
        with patch('app.api.v1.game_services.requests.request') as send:
            self.assertEqual(self.client.get(path, headers=self.headers).json['Data'], {'Total': 0, 'Items': []})
            send.assert_not_called()

    def test_worker_financial_and_config_boundaries(self):
        worker={**self.headers,'X-Store-ID':'2'}
        with patch('app.api.v1.game_services.requests.request',return_value=self.response) as send:
            self.assertEqual(self.client.get('/admin_api/game-service/v1/orders',headers=worker).status_code,200)
            for a in ['settle_deposit','purchase_return','declare_loss']:
                self.assertEqual(self.client.post('/admin_api/game-service/v1/action',headers=worker,json={'Action':a}).status_code,403)
            self.assertEqual(self.client.put('/admin_api/game-service/v1/stock',headers=worker,json={}).status_code,403)
            self.assertEqual(self.client.post('/admin_api/game-service/v1/refund',headers=worker,json={}).status_code,403)
            self.assertEqual(self.client.post('/admin_api/game-service/v1/review',headers=worker,json={}).status_code,403)
            self.assertEqual(send.call_count,1)
    def test_community_aggregates_only_authorized_stores(self):
        path = '/admin_api/game-service/v1/community'
        self.assertEqual(self.client.get(path).status_code, 401)
        db.session.add(Store(id=3, code='c', name='C'))
        db.session.commit()
        with patch('app.api.v1.game_services.requests.request', return_value=self.response) as send:
            response = self.client.get(path + '?StoreIDs=3&StoreID=3&Keyword=game&ShareKeyword=player&Page=2', headers={'Authorization': 'Bearer test', 'X-Store-ID': '3'})
            self.assertEqual(response.status_code, 200)
            params = send.call_args.kwargs['params']
            self.assertEqual(params['StoreIDs'], '1,2')
            self.assertNotIn('StoreID', params)
            self.assertEqual(params['ShareKeyword'], 'player')
            self.assertEqual(params['Page'], '2')
            db.session.get(Store, 2).status = 0
            db.session.commit()
            self.assertEqual(self.client.get(path, headers={'Authorization': 'Bearer test'}).status_code, 200)
            self.assertEqual(send.call_args.kwargs['params']['StoreIDs'], '1')

    def test_community_honors_page_revocation_and_headquarters(self):
        from app.security.models import RolePage
        path = '/admin_api/game-service/v1/community'
        db.session.add_all([RolePage(role='manager', page_id='game-community', allowed=False), RolePage(role='worker', page_id='game-community', allowed=False)])
        db.session.commit()
        with patch('app.api.v1.game_services.requests.request', return_value=self.response) as send:
            self.assertEqual(self.client.get(path, headers=self.headers).status_code, 403)
            send.assert_not_called()
            db.session.get(StaffAccount, 1).headquarters = True
            db.session.add(Store(id=3, code='c', name='C', status=1))
            db.session.commit()
            self.assertEqual(self.client.get(path, headers=self.headers).status_code, 200)
            self.assertEqual(send.call_args.kwargs['params']['StoreIDs'], '1,2,3')

    def test_share_write_uses_record_store_and_checks_management(self):
        path = '/admin_api/game-service/v1/review'
        with patch('app.api.v1.game_services.requests.request', return_value=self.response) as send:
            self.assertEqual(self.client.post(path, headers={**self.headers, 'X-Store-ID': '2'}, json={'ID': 2, 'Status': 'rejected'}).status_code, 403)
            self.assertEqual(self.client.post(path, headers=self.headers, json={'ID': 1, 'Status': 'rejected'}).status_code, 200)
            self.assertEqual(send.call_args.kwargs['json']['StoreID'], 1)
            self.assertEqual(self.client.post(path, headers=self.headers, json={'StoreID': 2, 'ID': 2}).status_code, 400)

    def test_batch_stock_scope_permission_and_retry(self):
        payload={'StoreID':2,'Actor':'impostor','Mode':'quantity','Quantity':2,'Items':[{'ID':10,'BoardGameID':42,'Version':1}],'RequestKey':'batch-stable-key'}
        path='/admin_api/game-service/v1/stock/batch'
        self.assertEqual(self.client.post(path,json=payload).status_code,401)
        with patch('app.api.v1.game_services.requests.request',return_value=self.response) as send:
            self.assertEqual(self.client.post(path,headers={**self.headers,'X-Store-ID':'2'},json=payload).status_code,403)
            send.assert_not_called()
            self.assertEqual(self.client.post(path,headers=self.headers,json=payload).status_code,400)
            payload['StoreID']=1
            self.assertEqual(self.client.post(path,headers=self.headers,json=payload).status_code,200)
            data=send.call_args.kwargs['json']
            self.assertEqual(data['StoreID'],1);self.assertEqual(data['Actor'],'1')
            self.assertEqual(data['Items'],payload['Items']);self.assertEqual(data['RequestKey'],'batch-stable-key')
            self.assertTrue(send.call_args.args[1].endswith('/stock/batch'))
        with patch('app.api.v1.game_services.requests.request',side_effect=requests.Timeout) as send:
            self.assertEqual(self.client.post(path,headers=self.headers,json=payload).status_code,502)
            self.assertEqual(send.call_args.kwargs['json']['RequestKey'],'batch-stable-key')

    def test_inventory_scope_and_automatic_refund_authorization(self):
        worker={**self.headers,'X-Store-ID':'2'}
        with patch('app.api.v1.game_services.requests.request',return_value=self.response) as send:
            self.assertEqual(self.client.put('/admin_api/game-service/v1/inventory',headers=worker,json={'Items':[]}).status_code,403)
            self.assertEqual(self.client.put('/admin_api/game-service/v1/inventory',headers=self.headers,json={'Items':[]}).status_code,200)
            self.assertEqual(send.call_args.kwargs['json']['StoreID'],1)
            self.assertEqual(self.client.post('/admin_api/game-service/v1/action',headers=worker,json={'Action':'return_complete','AutoRefund':False}).status_code,200)
            self.assertTrue(send.call_args.kwargs['json']['AutoRefund'])
            self.assertEqual(self.client.post('/admin_api/game-service/v1/action',headers=self.headers,json={'Action':'return_complete','AutoRefund':False}).status_code,200)
            self.assertTrue(send.call_args.kwargs['json']['AutoRefund'])

    def test_normal_return_does_not_grant_general_refund_access(self):
        worker={**self.headers,'X-Store-ID':'2'}
        with patch('app.api.v1.game_services.requests.request',return_value=self.response) as send:
            for action in ['accept', 'return', 'inspect', 'request_return']:
                self.assertEqual(self.client.post('/admin_api/game-service/v1/action',headers=worker,json={'Action':action,'AutoRefund':True}).status_code,200)
                self.assertFalse(send.call_args.kwargs['json']['AutoRefund'])
            send.reset_mock()
            for path, payload in [('action', {'Action':'settle_deposit','AutoRefund':True}), ('refund', {'Action':'approve'})]:
                self.assertEqual(self.client.post('/admin_api/game-service/v1/'+path,headers=worker,json=payload).status_code,403)
            send.assert_not_called()

    def test_timeout_preserves_idempotent_key(self):
        with patch('app.api.v1.game_services.requests.request',side_effect=requests.Timeout) as send:
            r=self.client.post('/admin_api/game-service/v1/action',headers=self.headers,json={'RequestKey':'stable-key','Action':'accept'})
            self.assertEqual(r.status_code,502);self.assertIn('刷新确认',r.json['Message'])
            self.assertEqual(send.call_args.kwargs['json']['RequestKey'],'stable-key')
    def test_legacy_stock_cannot_delete_allocated_pools(self):
        require_unallocated_inventory(1,42,0) # pre-migration installations remain readable
        db.session.execute(text('CREATE TABLE game_service_stocks (store_id INT, board_game_id INT, quantity INT)'))
        db.session.execute(text('INSERT INTO game_service_stocks VALUES (1,42,3),(2,42,5)'))
        db.session.commit()
        require_unallocated_inventory(1,42,3)
        with self.assertRaises(ValueError):require_unallocated_inventory(1,42,2)
        require_unallocated_inventory(1,99,0)
        db.session.execute(text('DROP TABLE game_service_stocks'));db.session.commit()
