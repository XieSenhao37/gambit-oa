import copy
import unittest
from datetime import datetime
from tests import test_settlement as fixtures
from app import db
from app.settlement import service, reports
from app.settlement.models import SettlementEntry


class EntryFiltersTest(unittest.TestCase):
    setUp = fixtures.SettlementTest.setUp
    tearDown = fixtures.SettlementTest.tearDown
    headers = fixtures.SettlementTest.headers

    def prepare(self):
        for i in range(27):
            service.add_entry(biz_key=f'filter:{i:02}', kind='wallet', reference=f'pay:{100+i}',
                payer_id=0, receiver_id=1, amount=(i+1)*100, face_amount=(i+1)*120,
                event_at=datetime(2026,1,i+1), detail='filter fixture')
        service.add_entry(biz_key='other-store', kind='wallet', reference='pay:other',
            payer_id=0,receiver_id=2,amount=9999,face_amount=12000,event_at=datetime(2026,1,1),detail='other store')
        service.add_entry(biz_key='refund', kind='wallet_refund', reference='refund:1',
            payer_id=0,receiver_id=1,amount=-300,face_amount=-360,event_at=datetime(2026,1,5),detail='refund')
        db.session.commit()
        self.report=reports.generate('2026-01',1,'entry-filter-test')

    def get(self, query='', user=1, store=1):
        return self.client.get('/admin_api/settlement/v1/overview?Month=2026-01&Scope=all&'+query,headers=self.headers(user,store))

    def test_filters_precede_pagination_and_preserve_totals_and_snapshot(self):
        self.prepare()
        original=copy.deepcopy(self.report.payload)
        count=SettlementEntry.query.count()
        all_data=self.get().json['Data']
        data=self.get('EntryKind=wallet&EntryStoreId=1&EntrySort=amount&EntryOrder=asc&Current=2&PageSize=5').json['Data']
        self.assertEqual(data['FilteredEntryCount'],27)
        self.assertEqual([e['amount'] for e in data['Entries']],[600,700,800,900,1000])
        self.assertEqual(data['EntryCount'],all_data['EntryCount'])
        self.assertEqual(data['Totals'],all_data['Totals'])
        self.assertEqual(data['Fees'],all_data['Fees'])
        self.assertEqual(SettlementEntry.query.count(),count)
        self.assertEqual(self.report.payload,original)

    def test_date_reference_filter_and_refund_direction(self):
        self.prepare()
        data=self.get('EntryKind=wallet&EntryStart=2026-01-11&EntryEnd=2026-01-13&EntryQuery=pay:11&EntryOrder=asc').json['Data']
        self.assertEqual(data['FilteredEntryCount'],3)
        self.assertEqual([e['reference'] for e in data['Entries']],['pay:110','pay:111','pay:112'])
        refund=self.get('EntryKind=wallet_refund').json['Data']['Entries'][0]
        self.assertEqual(refund['amount'],-300)
        self.assertEqual(refund['face_amount'],-360)

    def test_store_filter_does_not_expand_permissions(self):
        self.prepare()
        own=self.get('EntryKind=wallet',2,2).json['Data']
        self.assertEqual(own['FilteredEntryCount'],1)
        other=self.get('EntryKind=wallet&EntryStoreId=1',2,2).json['Data']
        self.assertEqual(other['FilteredEntryCount'],0)
        self.assertEqual(other['Entries'],[])

    def test_invalid_filters_are_rejected(self):
        for query in ('EntryKind=invalid','EntryStoreId=bad','EntrySort=detail','EntryOrder=bad',
                      'EntryStart=2026-02-30','EntryStart=2026-01-20&EntryEnd=2026-01-01'):
            self.assertEqual(self.get(query).status_code,400,query)
