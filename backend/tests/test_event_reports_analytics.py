"""Merged attendance read model; isolated SQLite or disposable MySQL only."""
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from flask import Flask, g, request, abort
from sqlalchemy import text
from sqlalchemy.engine import make_url
from app import db
from app.api.v1.event import event_bp


class EventReportAnalyticsTest(unittest.TestCase):
    def setUp(self):
        url = os.environ.get('OA_REPORT_TEST_DB', 'sqlite://')
        parsed = make_url(url)
        if parsed.drivername != 'sqlite':
            self.assertEqual((parsed.host, parsed.port, parsed.database),
                             ('127.0.0.1', 13319, 'gambit_event_report_test'))
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI=url,
                               SQLALCHEMY_TRACK_MODIFICATIONS=False)
        db.init_app(self.app)
        self.app.register_blueprint(event_bp, url_prefix='/events')
        self.ctx = self.app.app_context(); self.ctx.push()
        tables = {
            'stores': 'id INT PRIMARY KEY,name VARCHAR(100)',
            'event_projects': 'id INT PRIMARY KEY,name VARCHAR(100)',
            'users': 'id INT PRIMARY KEY,nick_name VARCHAR(100),phone_number VARCHAR(100),deleted_at DATETIME',
            'player_card_ids': 'user_id INT,project_id INT,card_id VARCHAR(100)',
            'store_events': 'id INT PRIMARY KEY,code VARCHAR(100),project_id INT,store_id INT,points INT,status VARCHAR(20),created_at DATETIME,started_at DATETIME,ended_at DATETIME',
            'event_checkins': 'id INT PRIMARY KEY,event_id INT,user_id INT,`rank` INT,deck_name VARCHAR(100),card_id VARCHAR(80)',
            'event_reports': 'id INT PRIMARY KEY,event_key VARCHAR(100),project_id INT,store_id INT,total_points INT,status VARCHAR(20),created_at DATETIME,issued_at DATETIME,snapshot TEXT,player_count INT',
        }
        self.tables = tables
        for name, ddl in tables.items():
            db.session.execute(text(f'DROP TABLE IF EXISTS {name}'))
            db.session.execute(text(f'CREATE TABLE {name} ({ddl})'))
        for name in ('stores','event_projects'):
            db.session.execute(text(f"INSERT INTO {name} VALUES (1,'One'),(2,'Two')"))
        db.session.execute(text("INSERT INTO users VALUES (1,'A',NULL,NULL),(2,'B',NULL,NULL),(3,'C',NULL,NULL)"))
        db.session.execute(text("INSERT INTO player_card_ids VALUES (1,1,'card-1'),(2,1,'card-2'),(3,1,'card-3')"))
        # Legacy ID 1 intentionally overlaps report ID 1.
        db.session.execute(text("INSERT INTO store_events VALUES (1,'checkin',1,1,2,'ended','2026-10-02','2026-10-02',NULL),(2,'empty',1,1,2,'open','2026-10-03',NULL,NULL)"))
        db.session.execute(text("INSERT INTO event_checkins VALUES (1,1,1,1,'Deck A','card-1')"))
        self.report(1, [1,2], '2026-10-22')
        self.report(2, [1,3], '2026-09-22')
        self.report(3, [3], None, status='draft')
        self.report(4, [3], '2026-10-22', store=2)
        self.report(5, [3], '2026-10-22', project=2)
        db.session.commit()
        def authenticated():
            g.pop('store_id', None)
            g.pop('scope_store', None)
            if not request.headers.get('Authorization'): abort(401)
            g.staff=SimpleNamespace(user_id=1,headquarters=True)
            g.grants={}
            request.user={'user_id':1}
        self.auth=patch('app.middlewares.auth.authenticate',side_effect=authenticated)
        self.auth.start()
        self.client=self.app.test_client()

    def report(self, ident, users, date, status='issued', store=1, project=1):
        snapshot={'Rows':[dict(UserID=u,CardID=f'card-{u}',Rank=i+1,Points=i,NickName=f'Player {u}',Name=f'Screenshot {u}') for i,u in enumerate(users)]}
        db.session.execute(text('INSERT INTO event_reports VALUES (:id,:key,:p,:s,:points,:status,:created,:issued,:snapshot,:count)'),
          dict(id=ident,key=f'report-{ident}',p=project,s=store,points=sum(range(len(users))),status=status,
               created='2026-08-01',issued=date,snapshot=json.dumps(snapshot),count=len(users)))

    def tearDown(self):
        self.auth.stop()
        db.session.rollback()
        for name in reversed(self.tables): db.session.execute(text(f'DROP TABLE {name}'))
        db.session.commit(); db.session.remove(); db.engine.dispose(); self.ctx.pop()

    def get(self, path, store=1):
        return self.client.get('/events/'+path,headers={'Authorization':'Bearer isolated','X-Store-ID':str(store)})

    def test_merged_cohorts_and_zero_point_participant(self):
        r=self.get('dashboard?project_id=1&month=2026-10')
        self.assertEqual(r.status_code,200,r.get_data(as_text=True))
        d=r.json['Data']; m=d['Metrics']
        self.assertEqual(m,dict(events=2,mau=3,uu=2,continuous_uu=1,new_players=1,return_rate=50.0,events_per_player=1.5))
        self.assertEqual([(r['user_id'],r['events']) for r in d['ActivePlayers']],[(1,2),(2,1)])
        self.assertEqual([r['user_id'] for r in d['RecallPlayers']],[3])
        self.assertEqual({(r['source'],r['id']) for r in d['EventRanking']},{('checkin',1),('report',1)})
        self.assertEqual(d['Decks'][0]['name'],'Deck A')
        self.assertEqual(d['Decks'][0]['count'],1)

    def test_list_excludes_drafts_empty_and_other_scopes(self):
        items=self.get('events?project_id=1&month=2026-10').json['Data']['Items']
        self.assertEqual([(r['source'],r['participants']) for r in items],[('report',2),('checkin',1)])
        self.assertEqual(items[0]['total_points'],1)
        self.assertEqual(len(self.get('events?project_id=1&month=2026-10',store=2).json['Data']['Items']),1)
        self.assertEqual(len(self.get('events?project_id=2&month=2026-10').json['Data']['Items']),1)
        self.assertEqual(len(self.get('events?project_id=1&month=2026-09').json['Data']['Items']),1)

    def test_report_detail_is_snapshot_and_store_scoped(self):
        r=self.get('reports/1'); self.assertEqual(r.status_code,200)
        d=r.json['Data']; self.assertNotIn('snapshot',d['Event'])
        self.assertEqual(d['Items'][0]['nick_name'],'Player 1')
        self.assertEqual(d['Items'][0]['screenshot_name'],'Screenshot 1')
        self.assertEqual(d['Items'][0]['points'],0)
        self.assertEqual(self.get('reports/1',store=2).status_code,400)
        self.assertEqual(self.get('reports/3').status_code,400)
        self.assertEqual(self.get('reports/999').status_code,400)
        self.assertEqual(self.client.get('/events/reports/1').status_code,401)
        self.assertEqual(self.client.put('/events/reports/1',json={'rank':9}).status_code,405)

    def test_unmatched_official_identity_cohorts_and_complete_roster(self):
        # Same official ID now unbound: still returning, not a new player.
        self.report(6, [0], '2026-10-23')
        roster = [dict(UserID=0,CardID=card,Rank=i+1,Points=0,NickName='',Name='Guest '+card)
                  for i,card in enumerate(['card-3','unknown-a','unknown-b','UNKNOWN-A'])]
        db.session.execute(text('UPDATE event_reports SET snapshot=:s,total_points=0,player_count=4 WHERE id=6'),
                           {'s':json.dumps({'Rows':roster})})
        # Live bindings do not affect snapshot identity, including check-ins.
        db.session.execute(text("UPDATE player_card_ids SET card_id='changed-live-id'"))
        db.session.commit()
        d=self.get('dashboard?project_id=1&month=2026-10').json['Data']
        self.assertEqual(d['Metrics'],dict(events=3,mau=6,uu=5,continuous_uu=2,new_players=3,return_rate=100.0,events_per_player=1.2))
        self.assertEqual(d['RecallPlayers'],[])
        guest=next(p for p in d['ActivePlayers'] if p['identity_key']=='card:card-3')
        self.assertEqual(guest['user_id'],0)
        self.assertEqual(guest['events'],1)
        detail=self.get('reports/6').json['Data']['Items']
        self.assertEqual(len({p['id'] for p in detail}),4)
        self.assertTrue(all(p['points']==0 for p in detail))
        events=self.get('events?project_id=1&month=2026-10').json['Data']['Items']
        self.assertEqual(events[0]['participants'],3)
        self.assertEqual(events[0]['total_points'],0)
        self.assertEqual(len(self.get('events?project_id=1&month=2026-10',store=2).json['Data']['Items']),1)

    def test_two_official_ids_for_same_gambit_user_remain_distinct(self):
        self.report(6,[1],'2026-10-23')
        snapshot={'Rows':[dict(UserID=1,CardID='another-official-id',Rank=1,Points=0,NickName='A',Name='Other')]}
        db.session.execute(text('UPDATE event_reports SET snapshot=:s WHERE id=6'),{'s':json.dumps(snapshot)})
        db.session.commit()
        d=self.get('dashboard?project_id=1&month=2026-10').json['Data']
        self.assertEqual(d['Metrics']['uu'],3)
        self.assertEqual(d['Metrics']['mau'],4)
        self.assertEqual(len({p['identity_key'] for p in d['ActivePlayers']}),3)

    def test_profiles_refresh_after_binding_rename_and_unbinding(self):
        # Historical snapshots contain nicknames, but unbound identities display unmatched.
        db.session.execute(text('DELETE FROM player_card_ids'))
        db.session.commit()
        original_snapshot=db.session.execute(text('SELECT snapshot FROM event_reports WHERE id=1')).scalar()
        before=self.get('dashboard?project_id=1&month=2026-10').json['Data']
        self.assertTrue(all(p['nick_name']=='未匹配' and p['user_id']==0 for p in before['ActivePlayers']+before['RecallPlayers']))
        db.session.execute(text("INSERT INTO player_card_ids VALUES (2,1,' CARD-1 '),(1,1,'card-3')"))
        db.session.execute(text("UPDATE users SET nick_name='Latest B',phone_number='encrypted-b' WHERE id=2"))
        db.session.execute(text("UPDATE users SET nick_name='Latest A',phone_number='encrypted-a' WHERE id=1"))
        db.session.commit()
        with patch('app.api.v1.event.decrypt_phone',side_effect=lambda value:'decoded-'+value):
            current=self.get('dashboard?project_id=1&month=2026-10').json['Data']
        active={p['identity_key']:p for p in current['ActivePlayers']}
        self.assertEqual((active['card:card-1']['user_id'],active['card:card-1']['nick_name']),(2,'Latest B'))
        self.assertNotIn('phone_number',active['card:card-1'])
        recalled=current['RecallPlayers'][0]
        self.assertEqual((recalled['user_id'],recalled['nick_name'],recalled['phone']),(1,'Latest A','decoded-encrypted-a'))
        self.assertEqual(current['Metrics'],before['Metrics'])
        self.assertEqual(db.session.execute(text('SELECT snapshot FROM event_reports WHERE id=1')).scalar(),original_snapshot)
        # Every subsequent read picks up nickname changes, then drops unbound contacts.
        db.session.execute(text("UPDATE users SET nick_name='Renamed B' WHERE id=2"))
        db.session.execute(text("DELETE FROM player_card_ids WHERE user_id=1"))
        db.session.commit()
        changed=self.get('dashboard?project_id=1&month=2026-10').json['Data']
        self.assertEqual(changed['ActivePlayers'][0]['nick_name'],'Renamed B')
        self.assertEqual(changed['RecallPlayers'][0]['nick_name'],'未匹配')
        self.assertEqual(changed['RecallPlayers'][0]['phone'],'')
        self.assertEqual(changed['Metrics'],before['Metrics'])

    def test_live_profiles_ignore_other_projects_deleted_users_and_ambiguous_bindings(self):
        db.session.execute(text("DELETE FROM player_card_ids WHERE card_id='card-1'"))
        db.session.execute(text("INSERT INTO player_card_ids VALUES (1,2,'card-1'),(1,1,'card-2')"))
        db.session.execute(text("UPDATE users SET deleted_at='2026-10-23' WHERE id=3"))
        db.session.commit()
        d=self.get('dashboard?project_id=1&month=2026-10').json['Data']
        self.assertTrue(all(p['user_id']==0 and p['nick_name']=='未匹配' for p in d['ActivePlayers']+d['RecallPlayers']))
        self.assertEqual(d['Metrics']['uu'],2)

    def test_legacy_without_official_id_uses_current_gambit_profile(self):
        db.session.execute(text("UPDATE event_checkins SET card_id=''"))
        db.session.execute(text("UPDATE users SET nick_name='Current A' WHERE id=1"))
        db.session.commit()
        d=self.get('dashboard?project_id=1&month=2026-10').json['Data']
        legacy=next(p for p in d['ActivePlayers'] if p['identity_key']=='gb:1')
        self.assertEqual((legacy['user_id'],legacy['nick_name']),(1,'Current A'))
