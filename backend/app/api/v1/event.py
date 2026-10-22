from app.utils.store import get_request_store_id
"""Store events: shared project configuration, result recording and cohort analytics.
Point mutations stay in GambitServer transactions; OA never independently awards points.
"""
from datetime import datetime
import json
from zoneinfo import ZoneInfo
from flask import Blueprint, jsonify, request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app import db
from app.middlewares.auth import login_required
from app.utils.crypto import decrypt_phone

event_bp = Blueprint('event', __name__)

def now():
    return datetime.now(ZoneInfo('Asia/Shanghai')).replace(tzinfo=None)

def rows(sql, **params):
    result = db.session.execute(text(sql), params).mappings().all()
    return [{k: v.strftime('%Y-%m-%d %H:%M:%S') if isinstance(v, datetime) else v for k, v in row.items()} for row in result]

def ok(data):
    return jsonify(Code=0, Message='操作成功', Data=data)

def bad(message):
    db.session.rollback()
    return jsonify(Code=1, Message=message, Data=None), 400

def number(value, minimum=1, maximum=2147483647):
    if isinstance(value, bool) or str(value).strip() != str(int(str(value))):
        raise ValueError('请输入整数')
    result = int(value)
    if not minimum <= result <= maximum:
        raise ValueError('数值超出范围')
    return result

def scope():
    project = number(request.args.get('project_id'))
    store = get_request_store_id()
    month = request.args.get('month') or now().strftime('%Y-%m')
    start = datetime.strptime(month, '%Y-%m')
    if start.strftime('%Y-%m') != month:
        raise ValueError('月份格式应为 YYYY-MM')
    end = datetime(start.year + (start.month == 12), start.month % 12 + 1, 1)
    previous = datetime(start.year - (start.month == 1), (start.month - 2) % 12 + 1, 1)
    return dict(project=project, store=store, start=start, end=end, previous=previous)

def profile(row):
    row['phone'] = decrypt_phone(row['phone_number']) if row.get('phone_number') else ''
    row.pop('phone_number', None)
    return row

@event_bp.route('/projects', methods=['GET', 'POST'])
@login_required('events')
def projects():
    if request.method == 'GET':
        return ok({'Items': rows('SELECT * FROM event_projects ORDER BY sort,id')})
    return save_config('event_projects')

@event_bp.route('/projects/<int:item_id>', methods=['PUT'])
@login_required('events')
def update_project(item_id):
    return save_config('event_projects', item_id)

@event_bp.route('/decks', methods=['GET', 'POST'])
@login_required('events')
def decks():
    if request.method == 'GET':
        try:
            p = number(request.args.get('project_id'))
        except (ValueError, TypeError):
            return bad('请选择项目')
        return ok({'Items': rows('SELECT * FROM event_decks WHERE project_id=:p ORDER BY sort,id', p=p)})
    return save_config('event_decks')

@event_bp.route('/decks/<int:item_id>', methods=['PUT'])
@login_required('events')
def update_deck(item_id):
    return save_config('event_decks', item_id)

def save_config(table, item_id=None):
    data = request.get_json(silent=True) or {}
    try:
        name = str(data.get('name') or '').strip()
        if not 1 <= len(name) <= 60:
            raise ValueError('名称需为1–60字')
        params = dict(name=name, sort=number(data.get('sort', 0), 0, 10000), status=number(data.get('status', 1), 0, 1), now=now())
        if table == 'event_decks':
            params['project_id'] = number(data.get('project_id'))
            if not rows('SELECT id FROM event_projects WHERE id=:p', p=params['project_id']):
                raise ValueError('项目不存在')
        if item_id:
            old = rows(f'SELECT * FROM {table} WHERE id=:id', id=item_id)
            if not old:
                raise ValueError('记录不存在')
            if table == 'event_decks' and old[0]['project_id'] != params['project_id']:
                raise ValueError('卡组不能移动到其他项目')
            db.session.execute(text(f'UPDATE {table} SET name=:name,sort=:sort,status=:status,updated_at=:now WHERE id=:id'), {**params, 'id':item_id})
        elif table == 'event_decks':
            db.session.execute(text('INSERT INTO event_decks(project_id,name,sort,status,created_at,updated_at) VALUES (:project_id,:name,:sort,:status,:now,:now)'), params)
        else:
            import uuid
            db.session.execute(text('INSERT INTO event_projects(code,name,sort,status,created_at,updated_at) VALUES (:code,:name,:sort,:status,:now,:now)'), {**params,'code':uuid.uuid4().hex})
        db.session.commit()
        return ok(None)
    except (ValueError, TypeError) as e:
        return bad(str(e))
    except IntegrityError:
        return bad('名称已存在，请使用其他名称')


# Read both immutable report snapshots and legacy check-ins without writing back
# or awarding points. Source is part of the event identity (IDs can overlap).
EVENT_SOURCE = """(SELECT id,code,project_id,store_id,points,status,created_at,started_at,ended_at,
    'checkin' source,NULL total_points FROM store_events
    UNION ALL
    SELECT id,event_key,project_id,store_id,NULL,status,created_at,issued_at,issued_at,
    'report' source,total_points FROM event_reports WHERE status='issued' AND issued_at IS NOT NULL)"""

def participation_source():
    # Official player IDs are snapshot identities. A later Gambit binding must not
    # change cohorts. Legacy check-ins without a card retain a separate GB identity.
    sqlite = db.engine.dialect.name == 'sqlite'
    if sqlite:
        report_rows = """SELECT r.id event_id,'report' source,
          CAST(json_extract(j.value,'$.UserID') AS INTEGER) user_id,
          CAST(json_extract(j.value,'$.Rank') AS INTEGER) `rank`,'' deck_name,
          json_extract(j.value,'$.CardID') card_id,
          COALESCE(NULLIF(json_extract(j.value,'$.NickName'),''),json_extract(j.value,'$.Name'),'') nick_name,
          CAST(j.key AS TEXT) row_id
          FROM event_reports r JOIN json_each(r.snapshot,'$.Rows') j WHERE r.status='issued'"""
        identity = "CASE WHEN NULLIF(TRIM(card_id),'') IS NOT NULL THEN 'card:' || LOWER(TRIM(card_id)) WHEN user_id>0 THEN 'gb:' || user_id ELSE source || ':' || event_id || ':' || row_id END"
    else:
        report_rows = """SELECT r.id event_id,'report' source,j.user_id,j.rank_value `rank`,'' deck_name,
          j.card_id,COALESCE(NULLIF(j.nick_name,''),j.screenshot_name,'') nick_name,j.row_id
          FROM event_reports r JOIN JSON_TABLE(r.snapshot,'$.Rows[*]' COLUMNS(
            row_id FOR ORDINALITY,user_id INT PATH '$.UserID',rank_value INT PATH '$.Rank',
            card_id VARCHAR(80) PATH '$.CardID',nick_name VARCHAR(255) PATH '$.NickName',
            screenshot_name VARCHAR(255) PATH '$.Name')) j ON TRUE WHERE r.status='issued'"""
        identity = "CASE WHEN NULLIF(TRIM(card_id),'') IS NOT NULL THEN CONCAT('card:',LOWER(TRIM(card_id))) WHEN user_id>0 THEN CONCAT('gb:',user_id) ELSE CONCAT(source,':',event_id,':',row_id) END"
    base = "SELECT c.event_id,'checkin' source,c.user_id,c.`rank`,c.deck_name,c.card_id,COALESCE(u.nick_name,'') nick_name,c.id row_id FROM event_checkins c LEFT JOIN users u ON u.id=c.user_id UNION ALL " + report_rows
    # Defensive per-event dedup also handles overlapping legacy report snapshots.
    return f"""(SELECT event_id,source,{identity} identity_key,MAX(user_id) user_id,
      MIN(`rank`) `rank`,MAX(deck_name) deck_name,MAX(TRIM(card_id)) card_id,MAX(nick_name) nick_name
      FROM ({base}) raw_participants GROUP BY event_id,source,{identity})"""

def attendance_join(participant='c', event='e'):
    return f"{participation_source()} {participant} JOIN {EVENT_SOURCE} {event} ON {event}.id={participant}.event_id AND {event}.source={participant}.source"

EVENT_FILTER = 'e.project_id=:project AND (:store=0 OR e.store_id=:store)'

@event_bp.route('/events', methods=['GET'])
@login_required('events')
def events():
    try:
        args = scope()
    except (ValueError, TypeError):
        return bad('项目、门店或月份无效')
    return ok({'Items':rows(f'''SELECT e.id,e.code,e.project_id,e.store_id,s.name store_name,e.points,e.status,
      e.created_at,e.started_at,e.ended_at,e.source,e.total_points,COUNT(*) participants
      FROM {attendance_join()} JOIN stores s ON s.id=e.store_id
      WHERE {EVENT_FILTER} AND COALESCE(e.started_at,e.created_at)>=:start AND COALESCE(e.started_at,e.created_at)<:end
      GROUP BY e.id,e.source,e.code,e.project_id,e.store_id,e.points,e.status,e.created_at,e.started_at,e.ended_at,e.total_points,s.name ORDER BY COALESCE(e.started_at,e.created_at) DESC,e.id DESC''', **args)})

@event_bp.route('/events/<int:event_id>', methods=['GET'])
@login_required('events')
def event_detail(event_id):
    event = rows('SELECT e.*,s.name store_name,p.name project_name FROM store_events e JOIN stores s ON s.id=e.store_id JOIN event_projects p ON p.id=e.project_id WHERE e.id=:id AND e.store_id=:sid', id=event_id, sid=get_request_store_id())
    if not event:
        return bad('赛事不存在')
    event[0].pop('token', None)
    event[0].pop('request_key', None)
    participants = rows('''SELECT c.*,u.nick_name,u.avatar,u.phone_number FROM event_checkins c
      JOIN users u ON u.id=c.user_id WHERE c.event_id=:id ORDER BY c.rank IS NULL,c.rank,c.created_at,c.id''', id=event_id)
    return ok({'Event':event[0], 'Items':[profile(p) for p in participants]})

@event_bp.route('/reports/<int:report_id>', methods=['GET'])
@login_required('events')
def report_detail(report_id):
    reports = rows('''SELECT r.id,r.event_key code,r.project_id,r.store_id,r.status,
      r.total_points,r.player_count,r.created_at,r.issued_at started_at,r.snapshot,
      s.name store_name,p.name project_name FROM event_reports r
      JOIN stores s ON s.id=r.store_id JOIN event_projects p ON p.id=r.project_id
      WHERE r.id=:id AND r.store_id=:sid AND r.status='issued' ''',
      id=report_id, sid=get_request_store_id())
    if not reports:
        return bad('赛事回传记录不存在')
    event = reports[0]
    snapshot = json.loads(event.pop('snapshot'))
    event['source'] = 'report'
    items = [dict(id=i, user_id=r['UserID'], nick_name=r.get('NickName', '') or '未匹配',
                  screenshot_name=r.get('Name', ''), card_id=r['CardID'], rank=r['Rank'],
                  points=r['Points'], created_at=event['started_at']) for i,r in enumerate(snapshot['Rows'], 1)]
    return ok({'Event':event, 'Items':sorted(items, key=lambda r:(r['rank'],r['user_id']))})

@event_bp.route('/participants/<int:checkin_id>', methods=['PUT'])
@login_required('events')
def participant(checkin_id):
    data = request.get_json(silent=True) or {}
    try:
        c = rows('SELECT c.* FROM event_checkins c JOIN store_events e ON e.id=c.event_id WHERE c.id=:id AND e.store_id=:sid FOR UPDATE', id=checkin_id, sid=get_request_store_id())
        if not c:
            raise ValueError('参赛记录不存在')
        rank = None if data.get('rank') in (None,'') else number(data['rank'], 1, 100000)
        deck_id = None if data.get('deck_id') in (None,'') else number(data['deck_id'])
        deck_name = ''
        if deck_id:
            deck = rows('SELECT * FROM event_decks WHERE id=:id AND project_id=:project', id=deck_id,project=c[0]['project_id'])
            if not deck or (not deck[0]['status'] and deck_id != c[0]['deck_id']):
                raise ValueError('卡组不属于该项目或已停用')
            deck_name = deck[0]['name']
        actor = str(getattr(request,'user',{}).get('user_id','admin'))[:80]
        db.session.execute(text('UPDATE event_checkins SET `rank`=:rank,deck_id=:deck_id,deck_name=:deck_name,edited_by=:actor,updated_at=:now WHERE id=:id'),dict(rank=rank,deck_id=deck_id,deck_name=deck_name,actor=actor,now=now(),id=checkin_id))
        db.session.commit()
        return ok(None)
    except (ValueError,TypeError) as e:
        return bad(str(e))

@event_bp.route('/dashboard', methods=['GET'])
@login_required('events')
def dashboard():
    try:
        args=scope()
    except (ValueError,TypeError):
        return bad('请选择有效的项目、门店和月份')
    # Only the two cohort months are loaded; first attendance is aggregated in SQL.
    pairs=rows(f'''SELECT c.*,u.phone_number,e.started_at FROM {attendance_join()}
      LEFT JOIN users u ON u.id=c.user_id
      WHERE {EVENT_FILTER} AND e.started_at>=:previous AND e.started_at<:end
      ORDER BY e.started_at,c.event_id,c.source''',**args)
    start=args['start'].strftime('%Y-%m-%d %H:%M:%S')
    current=[p for p in pairs if p['started_at']>=start]
    previous=[p for p in pairs if p['started_at']<start]
    before={p['identity_key'] for p in previous}
    users={p['identity_key'] for p in current}
    continuous=users&before
    event_rank=rows(f'''SELECT e.id,e.source,e.code,e.started_at,s.name store_name,COUNT(*) participants FROM {attendance_join()} JOIN stores s ON s.id=e.store_id
      WHERE {EVENT_FILTER} AND e.started_at>=:start AND e.started_at<:end
      GROUP BY e.id,e.source,e.code,e.started_at,s.name ORDER BY participants DESC,e.started_at DESC''',**args)
    def cohorts(participants, count_key):
        grouped={}
        for p in participants:
            key=p['identity_key']
            count=grouped.get(key,{}).get(count_key,0)+1
            grouped[key]=dict(identity_key=key,card_id=p['card_id'] or '',
              user_id=p['user_id'] or 0,nick_name=p['nick_name'],phone_number=p['phone_number'],
              last_event_at=p['started_at'],**{count_key:count})
        return list(grouped.values())
    active=cohorts(current,'events')
    active.sort(key=lambda r:(-r['events'],r['identity_key']))
    for r in active: r.pop('phone_number',None)
    recall=cohorts([p for p in previous if p['identity_key'] not in users],'previous_events')
    recall.sort(key=lambda r:(r['last_event_at'],r['identity_key']),reverse=True)
    new=rows(f'''SELECT COUNT(*) count FROM (SELECT c.identity_key FROM {attendance_join()}
      WHERE {EVENT_FILTER} GROUP BY c.identity_key HAVING MIN(e.started_at)>=:start AND MIN(e.started_at)<:end) first_players''',**args)[0]['count']
    decks=rows(f'''SELECT TRIM(c.deck_name) name,COUNT(*) count,
      COUNT(CASE WHEN c.`rank`=1 THEN 1 END) champions,
      COUNT(CASE WHEN c.`rank`=2 THEN 1 END) runners_up,
      COUNT(CASE WHEN c.`rank` BETWEEN 1 AND 4 THEN 1 END) top_four,
      COUNT(CASE WHEN c.`rank` BETWEEN 1 AND 8 THEN 1 END) top_eight
      FROM {attendance_join()} WHERE {EVENT_FILTER}
      AND e.started_at>=:start AND e.started_at<:end
      AND NULLIF(TRIM(c.deck_name),'') IS NOT NULL
      GROUP BY TRIM(c.deck_name) ORDER BY count DESC,name ASC''',**args)
    return ok({'Metrics':{'events':len(event_rank),'mau':len(current),'uu':len(users),'continuous_uu':len(continuous),
      'new_players':int(new),'return_rate':round(len(continuous)/len(before)*100,1) if before else None,
      'events_per_player':round(len(current)/len(users),2) if users else 0},
      'EventRanking':event_rank,'ActivePlayers':active,'RecallPlayers':[profile(r) for r in recall],'Decks':decks})

@event_bp.route('/claims', methods=['GET'])
@login_required('events')
def claims():
    try:
        args=scope()
    except (ValueError,TypeError):
        return bad('请选择有效的项目、门店和月份')
    return ok({'Items':rows('''SELECT c.id,c.user_id,u.nick_name,c.points,c.verified_at,v.nick_name verifier,s.name store_name
      FROM event_referral_claims c JOIN users u ON u.id=c.user_id LEFT JOIN users v ON v.id=c.verifier_id LEFT JOIN stores s ON s.id=c.store_id
      WHERE c.project_id=:project AND (:store=0 OR c.store_id=:store) AND c.status='verified'
      AND c.verified_at>=:start AND c.verified_at<:end ORDER BY c.id DESC''',**args)})
