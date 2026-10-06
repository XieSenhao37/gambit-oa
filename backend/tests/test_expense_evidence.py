"""Optional expense evidence must not change financial confirmation boundaries."""
import copy
import io
import unittest
from unittest.mock import patch
from tests import test_manual_settlement_reports as base
from app import db
from app.security.models import AccessAudit
from app.settlement import reports
from app.settlement.models import SettlementReport, SettlementEntry


class ExpenseEvidenceTest(unittest.TestCase):
    setUp = base.ManualReportsTest.setUp
    tearDown = base.ManualReportsTest.tearDown
    headers = base.ManualReportsTest.headers
    cost = base.ManualReportsTest.cost
    generate = base.ManualReportsTest.generate
    confirm = base.ManualReportsTest.confirm
    void = base.ManualReportsTest.void

    def save_cost(self, row, **values):
        return self.client.post(f'/admin_api/settlement/v1/expenses/{row.id}/confirm',
            headers=self.headers(), json={'Amount':5000,'ProviderId':2,**values})

    def upload(self, row, **values):
        return self.client.post(f'/admin_api/settlement/v1/expenses/{row.id}/confirm',
            headers=self.headers(), data={'Amount':'5000','ProviderId':'2',
                'File':(io.BytesIO(b'\x89PNG\r\n\x1a\nmock'),'proof.png'),**values})

    def test_blank_evidence_saves_and_settles_without_changing_amounts(self):
        row=self.cost()
        for note in (None,'','   '):
            res=self.save_cost(row,Note=note)
            self.assertEqual(res.status_code,200,res.json)
            self.assertEqual(row.note,'');self.assertEqual(row.status,'ready')
        self.assertEqual(self.save_cost(row).status_code,200)
        self.assertEqual(SettlementEntry.query.count(),0)
        report=self.generate().json['Data']
        self.assertEqual({t['StoreId']:t['amount'] for t in report['Totals']},{1:-3000,2:3000})
        self.assertEqual(self.confirm(report).status_code,200)
        self.assertEqual(row.status,'posted')
        self.assertEqual(self.save_cost(row,Note='locked').status_code,400)

    def test_upload_replace_remove_and_private_access(self):
        row=self.cost()
        endpoint=f'/admin_api/settlement/v1/expenses/{row.id}'
        with patch('app.api.v1.settlement.upload_private_receipt',side_effect=['settlement-receipts/one.png','settlement-receipts/two.png']):
            response=self.upload(row)
            self.assertEqual(response.status_code,200,response.json)
            self.assertTrue(response.json['Data']['has_image'])
            self.assertNotIn('proof_image',response.json['Data'])
            self.assertEqual(self.upload(row,Note='更正').status_code,200)
        self.assertEqual(row.proof_image,'settlement-receipts/two.png')
        audit=AccessAudit.query.filter_by(action='settlement:expense').order_by(AccessAudit.id.desc()).first()
        self.assertEqual(audit.detail['before']['proof_image'],'settlement-receipts/one.png')
        # Store 2 is responsible for points but no longer the supplier.
        row.provider_id=0;db.session.commit()
        with patch('app.api.v1.settlement.read_private_receipt',return_value=(b'mock','image/png')) as read:
            res=self.client.get(endpoint+'/proof',headers=self.headers(2,2))
            self.assertEqual(res.status_code,200)
            self.assertEqual(res.headers['Cache-Control'],'private, no-store')
            self.assertEqual(self.client.get(endpoint+'/proof',headers=self.headers(2,1)).status_code,403)
            self.assertEqual(read.call_count,1)
        listing=self.client.get('/admin_api/settlement/v1/expenses?Scope=all',headers=self.headers()).json['Data']['Items'][0]
        self.assertNotIn('proof_image',listing);self.assertTrue(listing['has_image'])
        self.assertEqual(self.save_cost(row,RemoveImage=True).status_code,200)
        self.assertIsNone(row.proof_image)
        self.assertEqual(self.client.get(endpoint+'/proof',headers=self.headers()).status_code,404)

    def test_invalid_input_and_upload_failure_are_atomic(self):
        row=self.cost()
        for values in ({'Note':'x'*501},{'Note':123},{'Amount':None},{'Amount':-1},{'ProviderId':-1}):
            self.assertEqual(self.save_cost(row,**values).status_code,400)
        with patch('app.api.v1.settlement.upload_private_receipt',side_effect=RuntimeError('fake')):
            response=self.upload(row,Amount='3000',Note='must rollback')
        self.assertEqual(response.status_code,400)
        self.assertEqual(row.amount,5000);self.assertEqual(row.status,'needs_cost')
        self.assertIsNone(row.proof_image)
        response=self.client.post(f'/admin_api/settlement/v1/expenses/{row.id}/confirm',
            headers=self.headers(),data={'Amount':'3000','ProviderId':'2','File':(io.BytesIO(b'not an image'),'bad.png')})
        self.assertEqual(response.status_code,400)
        self.assertEqual(AccessAudit.query.filter_by(action='settlement:expense').count(),0)

    def test_generated_report_locks_image_and_void_allows_edit(self):
        row=self.cost();self.save_cost(row)
        report=self.generate().json['Data']
        with patch('app.api.v1.settlement.upload_private_receipt') as upload:
            self.assertEqual(self.upload(row).status_code,400);upload.assert_not_called()
        self.assertEqual(self.void(report).status_code,200)
        with patch('app.api.v1.settlement.upload_private_receipt',return_value='settlement-receipts/new.png'):
            self.assertEqual(self.upload(row).status_code,200)
        report=self.generate().json['Data'];self.assertEqual(self.confirm(report).status_code,200)
        self.assertEqual(SettlementReport.query.filter_by(status='confirmed').one().payload['expenses'][0]['proof_image'],'settlement-receipts/new.png')

    def test_pre_migration_draft_without_image_column_still_confirms(self):
        row=self.cost();self.save_cost(row)
        report=self.generate().json['Data']
        saved=db.session.get(SettlementReport,report['Id'])
        payload=copy.deepcopy(saved.payload)
        payload['expenses'][0].pop('proof_image')
        saved.payload=payload;saved.digest=reports.digest(payload);db.session.commit()
        report['Digest']=saved.digest
        # A new image cannot be silently smuggled into an old draft.
        row.proof_image='settlement-receipts/unexpected.png';db.session.commit()
        self.assertEqual(self.confirm(report).status_code,400)
        row.proof_image=None;db.session.commit()
        self.assertEqual(self.confirm(report).status_code,200)
