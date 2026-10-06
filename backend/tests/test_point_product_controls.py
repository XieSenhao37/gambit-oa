import unittest
from datetime import datetime, timedelta

from flask import Flask

from app.api.v1.point import (
    SHANGHAI_TZ,
    _build_product_from_form,
    _parse_max_redeem_per_user,
    _parse_product_status,
    _parse_redeem_start_at,
)


class PointProductControlsTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    def test_redeem_start_at_converts_epoch_ms_to_shanghai_naive_time(self):
        expected = datetime(2026, 9, 16, 12, 30, 45)
        timestamp_ms = int(
            expected.replace(tzinfo=SHANGHAI_TZ).timestamp() * 1000
        )

        actual = _parse_redeem_start_at(
            str(timestamp_ms),
            now=datetime(2026, 9, 16, 10, 0, 0),
        )

        self.assertEqual(actual, expected)
        self.assertIsNone(actual.tzinfo)

    def test_redeem_start_at_accepts_empty_and_rejects_invalid_or_past_values(self):
        now = datetime(2026, 9, 16, 10, 0, 0)
        past_ms = int(
            datetime(2026, 9, 16, 9, 59, 59, tzinfo=SHANGHAI_TZ).timestamp()
            * 1000
        )

        self.assertIsNone(_parse_redeem_start_at('', now=now))
        with self.assertRaisesRegex(ValueError, '13 位'):
            _parse_redeem_start_at('1750000000', now=now)
        with self.assertRaisesRegex(ValueError, '晚于当前时间'):
            _parse_redeem_start_at(str(past_ms), now=now)

    def test_max_redeem_per_user_and_status_validation(self):
        self.assertEqual(_parse_max_redeem_per_user('-1'), -1)
        self.assertEqual(_parse_max_redeem_per_user('3'), 3)
        for invalid in ('0', '-2', '1.5', ''):
            with self.assertRaises(ValueError):
                _parse_max_redeem_per_user(invalid)

        self.assertEqual(_parse_product_status('0'), 0)
        self.assertEqual(_parse_product_status('1'), 1)
        for invalid in ('2', '-1', ''):
            with self.assertRaises(ValueError):
                _parse_product_status(invalid)

    def test_product_form_defaults_new_product_to_offline(self):
        with self.app.test_request_context(
            '/products',
            method='POST',
            data={
                'Name': '测试商品',
                'PointsPrice': '500',
                'Stock': '-1',
                'Sort': '0',
            },
        ):
            payload = _build_product_from_form(require_image=False)

        self.assertEqual(payload['status'], 0)
        self.assertIsNone(payload['redeem_start_at'])
        self.assertEqual(payload['max_redeem_per_user'], -1)

    def test_product_form_honors_explicit_scheduled_status_and_limit(self):
        scheduled = datetime.now(SHANGHAI_TZ) + timedelta(days=1)
        scheduled_ms = int(scheduled.timestamp() * 1000)

        with self.app.test_request_context(
            '/products',
            method='POST',
            data={
                'Name': '限时商品',
                'PointsPrice': '800',
                'Stock': '10',
                'Sort': '1',
                'Status': '1',
                'RedeemStartAt': str(scheduled_ms),
                'MaxRedeemPerUser': '2',
            },
        ):
            payload = _build_product_from_form(require_image=False)

        self.assertEqual(payload['status'], 1)
        self.assertEqual(payload['max_redeem_per_user'], 2)
        self.assertEqual(
            payload['redeem_start_at'],
            datetime.fromtimestamp(
                scheduled_ms / 1000,
                tz=SHANGHAI_TZ,
            ).replace(tzinfo=None),
        )


if __name__ == '__main__':
    unittest.main()
