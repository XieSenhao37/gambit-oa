import os
import unittest
from unittest.mock import patch
from flask import Flask, g, request, abort
from types import SimpleNamespace
from sqlalchemy import text
from app import db
from app.api.v1.event import event_bp

@unittest.skipUnless(os.getenv('GAMBIT_EVENT_OA_TEST') == '1', 'requires disposable MySQL on 13319')
class EventAnalyticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=Flask(__name__)
        cls.app.config.update(SQLALCHEMY_DATABASE_URI='mysql+pymysql://root:local-event-test@127.0.0.1:13319/gambit_event_test',SQLALCHEMY_TRACK_MODIFICATIONS=False,TESTING=True)
        db.init_app(cls.app)
        cls.app.register_blueprint(event_bp,url_prefix='/events')
        with cls.app.app_context():
            for table in ('event_checkins','store_events','event_decks','player_card_ids'):
                db.session.execute(text(f'DELETE FROM {table} WHERE project_id IN (501,502)'))
            db.session.execute(text('DELETE FROM event_projects WHERE id IN (501,502)'))
            db.session.execute(text("DELETE FROM users WHERE open_id LIKE 'oa-event-%'"))
            for p in (501,502):
                db.session.execute(text("INSERT INTO event_projects(id,code,name,status,sort,created_at,updated_at) VALUES (:p,:code,:name,1,0,NOW(),NOW())"),dict(p=p,code=f'oa-{p}',name=f'OA测试{p}'))
            cls.store=db.session.execute(text('SELECT id FROM stores ORDER BY id LIMIT 1')).scalar_one()
            cls.u={}
            for name in ('A','B','C','D','Z'):
                res=db.session.execute(text('INSERT INTO users(open_id,nick_name,role,created_at,updated_at) VALUES (:o,:n,0,NOW(),NOW())'),dict(o='oa-event-'+name,n=name))
                cls.u[name]=res.lastrowid
            def event(n,date,names,project=501):
                res=db.session.execute(text("INSERT INTO store_events(code,token,request_key,store_id,project_id,points,status,creator_id,created_at,updated_at,started_at) VALUES (:code,:token,:code,:store,:p,2,'open',1,:dt,:dt,:dt)"),dict(code='oa-'+n,token=n.ljust(32,'0'),store=cls.store,p=project,dt=date))
                for name in names:
                    db.session.execute(text('INSERT INTO event_checkins(event_id,project_id,store_id,user_id,card_id,points,return_points,created_at,updated_at) VALUES (:e,:p,:s,:u,:card,2,0,:dt,:dt)'),dict(e=res.lastrowid,p=project,s=cls.store,u=cls.u[name],card=name,dt=date))
                return res.lastrowid
            cls.current=event('one','2026-09-03 12:00:00','ABCD')
            event('two','2026-09-07 12:00:00','ABCD')
            event('past','2026-08-07 12:00:00','ACZ')
            event('other','2026-09-10 12:00:00','Z',502)
            db.session.execute(text("INSERT INTO store_events(code,token,request_key,store_id,project_id,points,status,creator_id,created_at,updated_at) VALUES ('oa-empty',RPAD('empty',32,'0'),'oa-empty',:s,501,2,'open',1,'2026-09-11','2026-09-11')"),dict(s=cls.store))
            db.session.commit()
        def authenticated():
            if not request.headers.get('Authorization'): abort(401)
            g.staff=SimpleNamespace(user_id=1,headquarters=True)
            g.grants={}
            request.user={'user_id':1}
        cls.auth=patch('app.middlewares.auth.authenticate',side_effect=authenticated);cls.auth.start()
        cls.audit=patch('app.middlewares.auth.audit');cls.audit.start()
    @classmethod
    def tearDownClass(cls): cls.auth.stop(); cls.audit.stop()
    def get(self,path):return self.app.test_client().get('/events/'+path,headers={'Authorization':'Bearer test','X-Store-ID':str(self.store)})
    def test_cohorts(self):
        r=self.get('dashboard?project_id=501&month=2026-09')
        self.assertEqual(r.status_code,200,r.get_data(as_text=True))
        d=r.json['Data'];m=d['Metrics']
        self.assertEqual((m['events'],m['mau'],m['uu'],m['continuous_uu']),(2,8,4,2))
        self.assertEqual(m['new_players'],2);self.assertEqual(m['return_rate'],66.7)
        self.assertEqual([u['nick_name'] for u in d['RecallPlayers']],['Z'])
        self.assertEqual(len(d['ActivePlayers']),4)
        self.assertTrue(all(u['events']==2 for u in d['ActivePlayers']))
        self.assertEqual(self.get('dashboard?project_id=502&month=2026-09').json['Data']['Metrics']['mau'],1)
        self.assertEqual(self.get('dashboard?project_id=501&store_id=2147483647&month=2026-09').json['Data']['Metrics']['mau'],0)
    def test_event_list_hides_empty_events(self):
        for store in (0, self.store):
            r = self.get(f'events?project_id=501&store_id={store}&month=2026-09')
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
            items = r.json['Data']['Items']
            self.assertEqual({row['code'] for row in items}, {'oa-one', 'oa-two'})
            self.assertTrue(all(row['participants'] == 4 for row in items))
        self.assertEqual(len(self.get('events?project_id=502&month=2026-09').json['Data']['Items']), 1)

    def test_deck_results(self):
        with self.app.app_context():
            original = db.session.execute(text('SELECT id,deck_name,`rank` FROM event_checkins WHERE project_id IN (501,502)')).mappings().all()
            current = db.session.execute(text("SELECT c.id FROM event_checkins c JOIN store_events e ON e.id=c.event_id WHERE c.project_id=501 AND e.code IN ('oa-one','oa-two') ORDER BY c.id")).scalars().all()
            values = [('测试卡组A',1),('测试卡组A',2),('测试卡组A',4),('测试卡组A',8),('测试卡组B',9),('测试卡组B',None),('',1),('   ',2)]
            for ident, (name, rank) in zip(current, values):
                db.session.execute(text('UPDATE event_checkins SET deck_name=:name,`rank`=:rank WHERE id=:id'),dict(name=name,rank=rank,id=ident))
            db.session.execute(text("UPDATE event_checkins c JOIN store_events e ON e.id=c.event_id SET c.deck_name='测试卡组A',c.`rank`=1 WHERE e.code IN ('oa-past','oa-other')"))
            db.session.commit()
        try:
            for store in (0,self.store):
                r=self.get(f'dashboard?project_id=501&store_id={store}&month=2026-09')
                self.assertEqual(r.status_code,200,r.get_data(as_text=True))
                decks=r.json['Data']['Decks']
                self.assertEqual(decks,[dict(name='测试卡组A',count=4,champions=1,runners_up=1,top_four=3,top_eight=4),dict(name='测试卡组B',count=2,champions=0,runners_up=0,top_four=0,top_eight=0)])
            self.assertEqual(self.get('dashboard?project_id=501&store_id=2147483647&month=2026-09').status_code,400)
        finally:
            with self.app.app_context():
                for row in original:
                    db.session.execute(text('UPDATE event_checkins SET deck_name=:deck_name,`rank`=:rank WHERE id=:id'),dict(row))
                db.session.commit()

    def test_participant_deck_scope(self):
        client=self.app.test_client();headers={'Authorization':'Bearer test','X-Store-ID':str(self.store)}
        item=self.get(f'events/{self.current}').json['Data']['Items'][0]
        self.assertNotIn('token',self.get(f'events/{self.current}').json['Data']['Event'])
        r=client.post('/events/decks',json={'project_id':502,'name':'异项目卡组'},headers=headers);self.assertEqual(r.status_code,200)
        deck=self.get('decks?project_id=502').json['Data']['Items'][0]
        r=client.put('/events/participants/'+str(item['id']),json={'rank':1,'deck_id':deck['id']},headers=headers);self.assertEqual(r.status_code,400)
        r=client.put('/events/participants/'+str(item['id']),json={'rank':1,'deck_id':None},headers=headers);self.assertEqual(r.status_code,200)
        self.assertEqual(self.get(f'events/{self.current}').json['Data']['Items'][0]['rank'],1)
    def test_auth_and_invalid_parameters(self):
        self.assertEqual(self.app.test_client().get('/events/projects').status_code,401)
        self.assertEqual(self.get('dashboard?project_id=501&month=2026-13').status_code,400)
        self.assertEqual(self.get('dashboard?project_id=-1').status_code,400)
