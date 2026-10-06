import unittest
from unittest.mock import Mock, patch

from flask import Flask

from app.api.v1.order import (
    _amount_yuan_to_cents,
    _call_gambit_server_play,
    order_bp,
)


class PlayWorkbenchProxyTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            GAMBIT_SERVER_BASE_URL='http://gambit-server',
            GAMBIT_INTERNAL_TOKEN='test-token',
        )

    def test_amount_yuan_to_cents_is_exact(self):
        self.assertEqual(_amount_yuan_to_cents('0'), 0)
        self.assertEqual(_amount_yuan_to_cents('468'), 46800)
        self.assertEqual(_amount_yuan_to_cents('624.50'), 62450)
        with self.assertRaises(ValueError):
            _amount_yuan_to_cents('1.001')
        with self.assertRaises(ValueError):
            _amount_yuan_to_cents('-1')
        with self.assertRaises(ValueError):
            _amount_yuan_to_cents('NaN')

    @patch('app.api.v1.order.requests.request')
    def test_internal_request_forwards_token_and_payload(self, request_mock):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {'Code': 0, 'Data': {'Orders': []}}
        request_mock.return_value = response

        with self.app.app_context():
            result = _call_gambit_server_play(
                'POST',
                'settle',
                data={'PlayOrderID': 12, 'StoreID': 2, 'Amount': 46800},
            )

        self.assertEqual(result['Code'], 0)
        request_mock.assert_called_once_with(
            'POST',
            'http://gambit-server/microapp_api/admin/play/v1/settle',
            params=None,
            json={'PlayOrderID': 12, 'StoreID': 2, 'Amount': 46800},
            headers={'X-GAMBIT-INTERNAL-TOKEN': 'test-token'},
            timeout=10,
        )

    @patch('app.api.v1.order.requests.request')
    def test_internal_business_error_is_propagated(self, request_mock):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {'Code': 1, 'Msg': '订单门店不一致'}
        request_mock.return_value = response

        with self.app.app_context():
            with self.assertRaisesRegex(RuntimeError, '订单门店不一致'):
                _call_gambit_server_play('GET', 'workbench', params={'StoreID': 2})

    def test_legacy_direct_settlement_route_is_removed(self):
        app = Flask(__name__)
        app.register_blueprint(order_bp, url_prefix='/admin_api/order/v1')
        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertNotIn('/admin_api/order/v1/settle/<int:order_id>', rules)
        self.assertIn(
            '/admin_api/order/v1/workbench/settle/<int:order_id>',
            rules,
        )


if __name__ == '__main__':
    unittest.main()
