"""Expense evidence regression against the dedicated disposable local MySQL."""
import os
import unittest
from unittest.mock import patch
from sqlalchemy.engine import make_url
from app import db
from tests import test_expense_evidence as evidence
from tests import test_settlement as fixtures


@unittest.skipUnless(os.getenv('MANUAL_SETTLEMENT_TEST_URL'), 'isolated MySQL not configured')
class ExpenseEvidenceMySQLTest(evidence.ExpenseEvidenceTest):
    def setUp(self):
        uri=make_url(os.environ['MANUAL_SETTLEMENT_TEST_URL'])
        if (uri.host,uri.port,uri.database)!=('127.0.0.1',33317,'gambit_manual_settlement_test'):
            raise RuntimeError('Only the dedicated local report database may be reset')
        create=fixtures.create_app
        with create({'SQLALCHEMY_DATABASE_URI':uri,'TESTING':True}).app_context():
            db.drop_all()
        with patch.object(fixtures,'create_app',side_effect=lambda cfg:create({**cfg,'SQLALCHEMY_DATABASE_URI':uri})):
            super().setUp()
