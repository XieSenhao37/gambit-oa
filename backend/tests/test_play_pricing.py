import hashlib
import unittest
from datetime import datetime, timedelta
from app import create_app, db
from app.models import Config, Store, User
from app.security.models import StaffAccount, StaffGrant, OASession
from app.utils.crypto import encrypt_phone
from app.services.play_pricing import validate_schedule, resolve_price, total, CALENDAR
from sqlalchemy import text


def schedule(bundle=False):
    return {'Common': {'Price': 2000, 'AdditionPrice': 0, 'MaxHour': 3, 'MaxTotal': 6800, 'BundlePricing': bundle},
            'Holiday': {'Price': 2800, 'AdditionPrice': 1000, 'MaxHour': 3, 'MaxTotal': 7800, 'BundlePricing': bundle},
            'SpecialMap': {}}


class PlayPricingTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({'TESTING': True, 'OA_LOGIN_MODE': 'sms', 'SQLALCHEMY_DATABASE_URI': 'sqlite://'})
        self.ctx = self.app.app_context(); self.ctx.push()
        db.create_all()
        db.session.add_all([Store(id=1, code='a', name='A'), Store(id=2, code='b', name='B'), User(id=1, open_id='staff')])
        db.session.add(StaffAccount(user_id=1, phone_cipher=encrypt_phone('13800138001'), enabled=True, headquarters=False, version=1))
        db.session.add_all([StaffGrant(user_id=1, store_id=1, role='manager'), StaffGrant(user_id=1, store_id=2, role='worker')])
        db.session.add(OASession(token_digest=hashlib.sha256(b'test').hexdigest(), user_id=1, account_version=1, expires_at=datetime.utcnow()+timedelta(hours=1)))
        self.original = {'Common': schedule()['Common'], 'Holiday': schedule()['Holiday'], 'Other': {'Keep': True}, 'StoreMap': {'1': schedule(), '2': schedule()}}
        db.session.add(Config(config_key='PlayConfig', config_value=self.original)); db.session.commit()
        self.client = self.app.test_client()
        self.headers = {'Authorization': 'Bearer test', 'X-Store-ID': '1'}

    def tearDown(self):
        db.session.remove(); db.drop_all(); self.ctx.pop()

    def get(self):
        return self.client.get('/admin_api/play-pricing/v1', headers=self.headers).json['Data']

    def put(self, value, revision=None):
        return self.client.put('/admin_api/play-pricing/v1', headers=self.headers, json={'Config': value, 'Revision': self.get()['Revision'] if revision is None else revision})

    def test_scope_auth_and_read_only(self):
        self.assertEqual(self.client.get('/admin_api/play-pricing/v1').status_code, 401)
        for method, path in [('get',''), ('put',''), ('post','/preview')]:
            r = getattr(self.client, method)('/admin_api/play-pricing/v1'+path, headers={**self.headers, 'X-Store-ID':'2'}, json={})
            self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.get('/admin_api/play-pricing/v1', headers={**self.headers, 'X-Store-ID':'3'}).status_code, 403)
        self.assertEqual(self.get()['Config'], schedule())
        self.assertEqual(Config.query.first().config_value, self.original)

    def test_save_preserves_other_store_and_conflict(self):
        old = self.get(); value = schedule(); value['Common']['Price'] = 2200
        self.assertEqual(self.put(value, old['Revision']).status_code, 200)
        self.assertEqual(self.put(schedule(), old['Revision']).status_code, 409)
        saved = Config.query.first().config_value
        self.assertEqual(saved['StoreMap']['2'], self.original['StoreMap']['2'])
        self.assertEqual(saved['Other'], {'Keep': True})
        self.assertEqual(saved['StoreMap']['1']['Common']['Price'], 2200)

    def test_legacy_migration_keeps_other_store(self):
        row=Config.query.first(); row.config_value={k:v for k,v in self.original.items() if k!='StoreMap'}; db.session.commit()
        value=schedule(); value['Common']['Price']=2200
        self.assertEqual(self.put(value).status_code,200)
        self.assertEqual(Config.query.first().config_value['StoreMap']['2']['Common']['Price'],2000)

    def test_all_national_holiday_dates_and_adjusted_workdays(self):
        value = validate_schedule(schedule())
        for holiday in CALENDAR['Holidays']:
            day = datetime.fromisoformat(holiday['Start'])
            while day.strftime('%Y-%m-%d') <= holiday['End']:
                self.assertEqual(resolve_price(value, day)[2], 'holiday', day)
                day += timedelta(days=1)
        day = datetime(2026,10,10)
        self.assertEqual(resolve_price(value,day)[2],'common')
        value['UseAdjustedWorkdays']=False
        self.assertEqual(resolve_price(value,day)[2],'holiday')
        value['UseAdjustedWorkdays']=True
        self.assertEqual(resolve_price(value,day)[2],'common')
        value['DateTypes']['2026-10-01']='common'
        self.assertEqual(resolve_price(value,datetime(2026,10,1))[2],'common')

    def test_time_boundaries_and_date_priority(self):
        value=schedule()
        value['TimeRules']=[dict(Name='晚间',StartDate='',EndDate='',StartTime='22:00',EndTime='02:00',DayType='holiday',Price=schedule()['Common'])]
        value=validate_schedule(value)
        for h,kind in [(1,'晚间'),(2,'周五至周日／节假日价'),(21,'周五至周日／节假日价'),(22,'晚间')]:
            self.assertEqual(resolve_price(value,datetime(2026,10,1,h))[1],kind)
        value['SpecialMap']['2026-10-01']=schedule()['Holiday']
        self.assertEqual(resolve_price(value,datetime(2026,10,1,23))[1],'指定日期价格')
        value['SpecialMap']={}; value['TimeRules'][0]['StartDate']='2026-09-01'; value['TimeRules'][0]['EndDate']='2026-09-30'
        self.assertEqual(resolve_price(value,datetime(2026,10,1,23))[1],'周五至周日／节假日价')

    def test_validation_and_overlap(self):
        bad=[]
        for key,n in [('Price',-1),('Price',True),('Price',1.5),('MaxTotal',10000001),('MaxHour',0),('BundlePricing','true')]:
            v=schedule();v['Common'][key]=n;bad.append(v)
        v=schedule();v['DateTypes']={'2026-02-30':'holiday'};bad.append(v)
        v=schedule();v['SpecialMap']={'2026-10-01':{}};bad.append(v)
        r=dict(Name='夜间',StartDate='',EndDate='',StartTime='22:00',EndTime='02:00',DayType='any',Price=schedule()['Holiday'])
        v=schedule();v['TimeRules']=[r,{**r,'Name':'冲突','StartTime':'01:00','EndTime':'03:00'}];bad.append(v)
        for value in bad:
            with self.subTest(value=value): self.assertEqual(self.put(value).status_code,400)
        self.assertEqual(self.get()['Config'],schedule())
        v=schedule();v['TimeRules']=[{**r,'EndTime':'24:00'},{**r,'StartTime':'00:00'}]
        validate_schedule(v)

    def test_preview_matches_bundle_and_legacy_does_not_save(self):
        v=schedule();v['Holiday'].update(Price=2000,MaxTotal=6800)
        self.assertEqual(total(v['Holiday'],4),7800)
        v['Holiday'].update(BundlePricing=True,MaxTotal=5800)
        self.assertEqual([total(v['Holiday'],h) for h in [1,2,3,4,10]],[2000,4000,5800,6800,12800])
        r=self.client.post('/admin_api/play-pricing/v1/preview',headers=self.headers,json={'Config':v,'InTime':'2026-10-01 14:00','Hours':4})
        self.assertEqual(r.status_code,200,r.json);self.assertEqual(r.json['Data']['Amount'],6800)
        self.assertEqual(Config.query.first().config_value,self.original)
        v['Holiday']['MaxTotal']=6800
        self.assertEqual(self.put(v).status_code,400)

    def test_regular_policy_weekdays_and_selection(self):
        v=schedule(True)
        v['Common'].update(Price=2800,MaxTotal=7800,BundlePricing=False)
        v=validate_schedule(v)
        capped=[2800,5600,7800,7800,7800]
        continued=[2800,5600,7800,8800,10800]
        for day,want in [('2026-07-27',capped),('2026-07-28',capped),('2026-07-29',capped),('2026-07-30',capped),('2026-07-31',continued),('2026-08-01',continued),('2026-08-02',continued),('2026-10-05',continued),('2026-10-10',capped)]:
            price=resolve_price(v,datetime.fromisoformat(day))[0]
            self.assertEqual([total(price,h) for h in [1,2,3,4,6]],want,day)
        v['HolidayWeekdays']=[0,6]
        self.assertEqual(resolve_price(v,datetime(2026,7,31))[2],'common')
        v['HolidayWeekdays']=[]
        self.assertEqual(resolve_price(v,datetime(2026,8,1))[2],'common')
        self.assertEqual(resolve_price(v,datetime(2026,10,5))[2],'holiday')
        self.assertEqual(self.put(v).status_code,200)
        self.assertEqual(self.get()['Config']['HolidayWeekdays'],[])
        for bad in [None,[7],[-1],[True],[5,5],'5,6,0']:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError): validate_schedule({**v,'HolidayWeekdays':bad})

    def test_save_uses_active_config_with_legacy_deleted_duplicate(self):
        # Production's legacy table allows repeated keys across historical rows.
        # Reproduce that schema only in this isolated SQLite database.
        db.session.remove()
        Config.__table__.drop(db.engine)
        db.session.execute(text('CREATE TABLE configs (id INTEGER PRIMARY KEY, config_key VARCHAR(30) NOT NULL, config_value JSON NOT NULL, created_at DATETIME, updated_at DATETIME, deleted_at DATETIME)'))
        old = {'Common': {**schedule()['Common'], 'MaxTotal': 8400}, 'Holiday': schedule()['Holiday']}
        deleted_at = datetime(2026, 8, 2, 13, 46, 47)
        db.session.add_all([
            Config(id=2, config_key='PlayConfig', config_value=old, deleted_at=deleted_at),
            Config(id=6, config_key='PlayConfig', config_value=self.original),
        ])
        db.session.commit()
        self.assertEqual(self.get()['Config'], schedule())
        value = schedule(); value['Common']['Price'] = 2200
        self.assertEqual(self.put(value).status_code, 200)
        active = db.session.get(Config, 6)
        self.assertEqual(active.config_value['StoreMap']['1']['Common']['Price'], 2200)
        self.assertEqual(active.config_value['StoreMap']['2'], self.original['StoreMap']['2'])
        historical = db.session.get(Config, 2)
        self.assertEqual(historical.config_value, old)
        self.assertEqual(historical.deleted_at, deleted_at)

    def test_missing_store_and_deleted_config(self):
        row=Config.query.first();row.config_value={'StoreMap':{'2':schedule()}};db.session.commit()
        self.assertIsNone(self.get()['Config'])
        self.assertEqual(self.put(schedule()).status_code,200)
        row.deleted_at=datetime.now();db.session.commit()
        self.assertEqual(self.put(schedule()).status_code,409)

if __name__ == '__main__': unittest.main()
