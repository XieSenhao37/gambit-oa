import os
import re
from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, request, jsonify, g, abort, Response
from sqlalchemy import or_
from app.settlement.clock import now
from app.settlement.entry_filters import filter_entries
from app.settlement.wallet_view import monthly_wallet_metrics
from app import db
from app.models import Store,User,PointRedeemOrder,MonthCardOrder
from app.middlewares.auth import login_required
from app.security.policy import audit
from app.settlement.models import *
from app.settlement import service, reports, cash
from app.services.cos_service import upload_private_receipt, read_private_receipt

settlement_bp = Blueprint('settlement', __name__)

def serialize(row):
    return {c.name: (v.isoformat(sep=' ',timespec='seconds') if isinstance(v,datetime) else v)
            for c in row.__table__.columns for v in [getattr(row,c.name)]}

def guard(fn):
    @wraps(fn)
    def call(*args,**kwargs):
        if os.getenv('STORE_SETTLEMENT_ENABLED')!='true':
            if request.method!='GET':return jsonify(Code=503,Message='结算尚未启用，未执行此操作'),503
            return jsonify(Code=0,Data={'Enabled':False,'Message':'当前 OA 服务的结算开关未启用。请检查部署配置 STORE_SETTLEMENT_ENABLED=true；已完成期初初始化的环境不要重复初始化。'})
        try:
            # Read endpoints never calculate a future month's carried-over balances.
            if request.method == 'GET' and request.args.get('Month'):
                _, end = service.month_bounds(request.args['Month'])
                if end > now():
                    raise ValueError('只能查看已结束自然月的结算，请选择上月或更早月份')
            if not service.enabled():
                if request.method!='GET':return jsonify(Code=503,Message='尚未到达结算启用时间，未执行此操作'),503
                return result({'Enabled':False,'Message':'尚未到达结算启用时间。'})
            if request.method != 'GET':
                service.lock_operations()
            return fn(*args,**kwargs)
        except ValueError as e:
            db.session.rollback();return jsonify(Code=400,Message=str(e)),400
    return call

def headquarters():
    if not g.staff.headquarters: abort(403,description='仅总部可确认成本、锁定结算或登记付款')

def scope():
    return None if g.staff.headquarters and request.args.get('Scope')=='all' else g.store_id

def page_rows(query, maximum=100):
    current=max(1, request.args.get('Current',1,type=int))
    size=min(maximum,max(1,request.args.get('PageSize',20,type=int)))
    return query.offset((current-1)*size).limit(size).all()

def entry_query(month,sid):
    q=SettlementEntry.query.filter_by(month=month)
    if sid is not None: q=q.filter(or_(SettlementEntry.payer_id==sid,SettlementEntry.receiver_id==sid))
    return q

def result(data): return jsonify(Code=0,Message='success',Data=data)

def selected_month():
    # A URL without Month must follow the same last-completed-month default as OA.
    previous=now().replace(day=1)-timedelta(days=1)
    return request.args.get('Month',previous.strftime('%Y-%m'))

def user_label(open_id):
    u=User.query.filter_by(open_id=open_id).first()
    return f'{u.nick_name or "用户"}（#{u.id}）' if u else '历史用户'

def as_money(v):
    if isinstance(v,bool) or not isinstance(v,int) or v<0 or v>100000000: raise ValueError('金额必须是 0 至 100000000 的整数分')
    return v

@settlement_bp.get('/overview')
@login_required('settlement')
@guard
def overview():
    month=selected_month();service.month_bounds(month)
    control=db.session.get(SettlementControl,1)
    first_month=control.cutoff.strftime('%Y-%m')
    start,end=service.month_bounds(month)
    blocked_reason=(f'结算从 {first_month} 启用，所选月份早于启用月份，请选择 {first_month} 或之后的月份。'
        if month < first_month else f'{month} 自然月尚未结束，请在 {end:%Y-%m-%d} 起生成报表。' if end > now() else '')
    eligibility={'FirstSettlementMonth':first_month,'GenerationBlockedReason':blocked_reason,
        'CoverageStart':max(start,control.cutoff).isoformat(timespec='seconds'),
        'PartialOpeningPeriod':start<control.cutoff<end}
    sid=scope();q=entry_query(month,sid)
    stores={s.id:s.name for s in Store.query.all()};stores[0]='总部'
    statements=SettlementStatement.query.filter_by(month=month)
    if sid is not None: statements=statements.filter_by(store_id=sid)
    period=db.session.get(SettlementPeriod,month)
    report=reports.current(month)
    if report:
        view=reports.public(report,sid)
        filtered=filter_entries(view['Entries'],request.args)
        current=max(1,request.args.get('Current',1,type=int));size=min(100,max(1,request.args.get('PageSize',20,type=int)))
        return result({**eligibility,'Enabled':True,'Headquarters':g.staff.headquarters,'Month':month,'Status':report.status,
            'Report':{k:v for k,v in view.items() if k not in ('Entries','Totals')},
            'Totals':view['Totals'],'Breakdown':view['Breakdown'],'CashIncluded':view['CashIncluded'],'FeesIncluded':view['FeesIncluded'],'Fees':view['Fees'],
            'Entries':filtered[(current-1)*size:current*size],
            'FilteredEntryCount':len(filtered),
            'EntryCount':len(view['Entries']),'Statements':[serialize(s) for s in statements.all()]})
    entries=[serialize(e) for e in q.all()] + cash.candidates(month,sid)
    entries.sort(key=lambda e:(e['event_at'],e['biz_key']),reverse=True)
    values=[t for t in reports.summarize(entries) if sid is None or t['StoreId']==sid]
    parts={k:v for k,v in cash.breakdown(entries).items() if sid is None or k==sid}
    filtered=filter_entries(entries,request.args)
    current=max(1,request.args.get('Current',1,type=int));size=min(100,max(1,request.args.get('PageSize',20,type=int)))
    return result({**eligibility,'Enabled':True,'Headquarters':g.staff.headquarters,'Month':month,'Status':period.status if period else 'draft',
        'Totals':values,'Breakdown':parts,'CashIncluded':True,'FeesIncluded':False,'Fees':[],
        'Entries':[dict(e,id=e['id'] or e['biz_key'],payer_name=stores.get(e['payer_id'],str(e['payer_id'])),receiver_name=stores.get(e['receiver_id'],str(e['receiver_id']))) for e in filtered[(current-1)*size:current*size]],
        'FilteredEntryCount':len(filtered),'EntryCount':len(entries),'Statements':[serialize(s) for s in statements.all()]})

@settlement_bp.get('/cash')
@login_required('settlement')
@guard
def cash_records():
    month=selected_month();service.month_bounds(month)
    sid=scope();report=reports.current(month)
    if report:
        rows=[e for e in reports.public(report,sid)['Entries'] if e['kind'] in cash.CASH_KINDS]
    else:
        rows=[serialize(e) for e in entry_query(month,sid).filter(SettlementEntry.kind.in_(cash.CASH_KINDS))] + cash.candidates(month,sid)
        stores={s.id:s.name for s in Store.query};stores[0]='总部'
        rows=[dict(e,id=e['id'] or e['biz_key'],payer_name=stores.get(e['payer_id'],str(e['payer_id'])),receiver_name=stores.get(e['receiver_id'],str(e['receiver_id']))) for e in rows]
    rows=filter_entries(rows,request.args)
    current=max(1,request.args.get('Current',1,type=int));size=min(100,max(1,request.args.get('PageSize',20,type=int)))
    return result({'Items':rows[(current-1)*size:current*size],'Total':len(rows)})

@settlement_bp.get('/assets')
@login_required('settlement')
@guard
def assets():
    sid=scope();kind=request.args.get('Kind','wallet')
    if kind not in ('wallet','point'):raise ValueError('资产类型无效')
    q=SettlementBatch.query.filter_by(kind=kind)
    if sid is not None:q=q.filter_by(responsible_store_id=sid)
    rows=page_rows(q.order_by(SettlementBatch.id.desc()))
    metrics={};report=None
    if kind=='wallet':
        month=selected_month();report=reports.current(month)
        entries=(reports.public(report,sid)['Entries'] if report else
                 [serialize(e) for e in entry_query(month,sid).filter(SettlementEntry.kind.in_(['wallet','wallet_refund']))])
        metrics=monthly_wallet_metrics([x.id for x in rows],entries)
    return result({'Items':[dict(serialize(x),user_name=user_label(x.open_id),**metrics.get(x.id,{})) for x in rows],
        'Total':q.count(),'Month':selected_month(),'ReportStatus':report.status if report else None})

@settlement_bp.get('/allocations')
@login_required('settlement')
@guard
def allocations():
    ref=request.args.get('Reference','');sid=scope()
    if not ref:raise ValueError('请指定业务单号')
    rows=db.session.query(SettlementAllocation,SettlementBatch).join(SettlementBatch,SettlementBatch.id==SettlementAllocation.batch_id).filter(or_(SettlementAllocation.reference==ref,SettlementAllocation.expense_key==ref))
    if sid is not None: rows=rows.filter(or_(SettlementAllocation.store_id==sid,SettlementBatch.responsible_store_id==sid))
    data={'Total':rows.count(),'Items':[dict(serialize(a),source_key=b.source_key,principal_total=b.principal_total,face_total=b.face_total,responsible_store_id=b.responsible_store_id) for a,b in page_rows(rows.order_by(SettlementAllocation.id))]}
    expense=SettlementExpense.query.filter_by(expense_key=ref).first()
    if expense and (sid is None or expense.provider_id==sid or data['Total']):
        report=reports.current(request.args['Month']) if request.args.get('Month') else None
        saved=next((e for e in report.payload['expenses'] if e['id']==expense.id),None) if report else None
        if saved:
            expense=SettlementExpense(**reports.restore(SettlementExpense,saved))
        from sqlalchemy import func
        weights=dict(db.session.query(SettlementBatch.responsible_store_id,func.sum(SettlementAllocation.amount)).join(SettlementAllocation,SettlementAllocation.batch_id==SettlementBatch.id).filter(SettlementAllocation.expense_key==ref,SettlementAllocation.state=='consumed').group_by(SettlementBatch.responsible_store_id).all())
        shares=service.apportion(expense.amount,weights) if expense.amount is not None and weights else {}
        if saved:
            shares={e['payer_id']:e['amount'] for e in report.payload['entries'] if e['kind']=='point_cost' and e['reference']==ref}
        data['Expense']=dict(serialize(expense),total_points=sum(weights.values()),shares=[{'store_id':k,'points':v,'amount':shares.get(k)} for k,v in weights.items() if sid is None or sid==k])
        data['Expense'].pop('proof_image',None)
        data['Expense']['report_status']=report.status if saved else None
    return result(data)

@settlement_bp.get('/cards')
@login_required('settlement')
@guard
def cards():
    from app.settlement.cards import card_view
    from app.api.v1.month_card import SOURCE_LABELS
    month=selected_month();service.month_bounds(month)
    sid=scope();q=SettlementCardPool.query
    report=reports.current(month)
    snapshots={p['id']:p for p in report.payload['pools']} if report else {}
    if report:
        q=q.filter(SettlementCardPool.id.in_(snapshots))
    else:
        _,end=service.month_bounds(month)
        q=q.filter(SettlementCardPool.starts_at < end)
    if sid is not None:
        if report:
            visible_ids={u['pool_id'] for u in report.payload['usages'] if u['store_id']==sid}
            q=q.filter(SettlementCardPool.id.in_(visible_ids))
        else:
            q=q.filter(SettlementCardPool.id.in_(db.session.query(SettlementCardUsage.pool_id).filter_by(store_id=sid)))
    items=[]
    def visible(shares):return [x for x in shares if sid is None or x['store_id']==sid]
    for p in page_rows(q.order_by(SettlementCardPool.id.desc())):
        uses=SettlementCardUsage.query.filter_by(pool_id=p.id).all()
        periods=None
        if p.id in snapshots:
            # Render the exact saved calculation before confirmation too; no writes.
            p=SettlementCardPool(**reports.restore(SettlementCardPool,snapshots[p.id]))
            uses=[SettlementCardUsage(**reports.restore(SettlementCardUsage,u)) for u in report.payload['usages'] if u['pool_id']==p.id]
            saved=[x for x in report.payload['periods'] if x['pool_id']==p.id]
            saved_months={x['month'] for x in saved}
            periods=[x for x in SettlementCardPeriod.query.filter_by(pool_id=p.id).all() if x.month not in saved_months and x.month<=month]
            periods += [SettlementCardPeriod(**reports.restore(SettlementCardPeriod,x)) for x in saved]
            periods.sort(key=lambda x:x.month)
        view=card_view(p,month,uses,periods)
        view['report_status']=report.status if report else None
        if report and report.status=='draft':
            view['period_status']='draft'
        order=MonthCardOrder.query.execution_options(global_reference_check=True).filter_by(id=p.order_id).first()
        view['source_text']=SOURCE_LABELS.get(order.source or 'wechat','历史开卡') if order else '历史开卡'
        view['funding_type']=('总部补贴' if order and order.source=='gift' else '总部统一承担') if p.payer_id==0 else '门店承担'
        view['estimated']=visible(view['estimated']);view['carry_shares']=visible(view['carry_shares'])
        view['periods']=[dict(serialize(x),shares=visible(x.shares),carry_shares=visible(x.carry_shares)) for x in view['periods']]
        items.append(dict(serialize(p),**view,user_name=user_label(p.open_id),uses=[serialize(u) for u in uses if sid is None or u.store_id==sid]))
    return result({'Items':items,'Total':q.count()})

@settlement_bp.post('/prepare')
@login_required('settlement')
@guard
def prepare():
    headquarters();data=request.get_json() or {}
    report=reports.generate(data.get('Month',''),g.staff.user_id,data.get('RequestKey',''))
    audit('settlement:report-generate',str(report.id),{'month':report.month,'version':report.version,'digest':report.digest})
    db.session.commit();return result(reports.public(report))

@settlement_bp.post('/reports/<int:id>/void')
@login_required('settlement')
@guard
def void_report(id):
    headquarters();data=request.get_json() or {}
    if data.get('NoTransfersStarted') is not True:raise ValueError('请确认尚未按此报表开始收付款；已开始转账的报表不可作废重算')
    report=reports.void(id,data.get('Digest'))
    audit('settlement:report-void',str(id),{'month':report.month,'version':report.version})
    db.session.commit();return result(reports.public(report))

def uploaded_proof(existing_key,data):
    file=request.files.get('File');key=existing_key
    remove=data.get('RemoveImage') in (True,'true')
    if file and remove:raise ValueError('不能同时上传和删除凭证图片')
    if file:
        content=file.read(5*1024*1024+1)
        ext='.png' if content.startswith(b'\x89PNG\r\n\x1a\n') else '.jpg' if content.startswith(b'\xff\xd8\xff') else None
        if not ext or len(content)>5*1024*1024:raise ValueError('请上传 5MB 以内的 JPG 或 PNG 图片')
        try:key=upload_private_receipt(content,ext)
        except Exception:raise ValueError('凭证图片上传失败，登记尚未保存，请重试') from None
    elif remove:key=None
    return key


@settlement_bp.get('/expenses')
@login_required('settlement')
@guard
def expenses():
    sid=scope();q=SettlementExpense.query
    report=reports.current(request.args['Month']) if request.args.get('Month') else None
    snapshots={e['id']:e for e in report.payload['expenses']} if report else {}
    if report:
        q=q.filter(SettlementExpense.id.in_(snapshots))
    elif request.args.get('Month'):
        _,end=service.month_bounds(request.args['Month'])
        q=q.filter(or_(SettlementExpense.completed_at < end,
            (SettlementExpense.completed_at.is_(None) & (SettlementExpense.created_at < end))))
    if sid is not None:
        refs=db.session.query(SettlementAllocation.expense_key).join(SettlementBatch,SettlementBatch.id==SettlementAllocation.batch_id).filter(SettlementBatch.responsible_store_id==sid)
        q=q.filter(or_(SettlementExpense.provider_id==sid,SettlementExpense.expense_key.in_(refs)))
    items=[]
    for e in page_rows(q.order_by(SettlementExpense.id.desc())):
        if e.id in snapshots:
            e=SettlementExpense(**reports.restore(SettlementExpense,snapshots[e.id]))
        label=f'抽奖活动 #{e.source_id}'
        if e.kind=='redeem':
            order=PointRedeemOrder.query.execution_options(global_reference_check=True).filter_by(id=e.source_id).first()
            label=f'{order.product_name} × {order.quantity}' if order else f'积分兑换 #{e.source_id}'
        items.append(dict(expense_view(e),source_name=label,report_status=report.status if report else None))
    return result({'Items':items,'Total':q.count()})

@settlement_bp.get('/cost-rules')
@login_required('settlement')
@guard
def rules():
    headquarters()
    from app.models import PointProduct
    return result({'Items':[serialize(x) for x in SettlementCostRule.query.order_by(SettlementCostRule.key)],'Products':[{'id':p.id,'name':p.name} for p in PointProduct.query.filter(PointProduct.deleted_at.is_(None)).all()]})

@settlement_bp.post('/cost-rules')
@login_required('settlement')
@guard
def save_rule():
    headquarters();data=request.get_json() or {};key=data.get('Key','')
    if not re.fullmatch(r'(product|raffle):[1-9][0-9]*',key):raise ValueError('成本对象格式无效')
    from app.models import PointProduct
    from sqlalchemy import text
    kind,source_id=key.split(':')
    source=db.session.get(PointProduct,int(source_id)) if kind=='product' else db.session.execute(text('SELECT id FROM raffles WHERE id=:id'),{'id':int(source_id)}).first()
    if not source or getattr(source,'deleted_at',None):raise ValueError('成本对象不存在或已删除')
    amount=as_money(data.get('Amount'));note=str(data.get('Note','')).strip()
    if not note or len(note)>500:raise ValueError('请填写 1 至 500 字成本依据')
    rule=db.session.get(SettlementCostRule,key) or SettlementCostRule(key=key)
    rule.amount=amount;rule.note=note;rule.updated_at=now();db.session.add(rule)
    audit('settlement:cost-rule',key,{'amount':amount,'note':note});db.session.commit();return result(serialize(rule))

def expense_view(e):
    data=serialize(e);data.pop('proof_image',None)
    data['has_image']=bool(e.proof_image)
    return data


@settlement_bp.get('/expenses/<int:id>/proof')
@login_required('settlement')
@guard
def expense_proof(id):
    e=SettlementExpense.query.filter_by(id=id).first_or_404()
    if not g.staff.headquarters and e.provider_id!=g.store_id:
        allowed=db.session.query(SettlementAllocation.id).join(SettlementBatch,SettlementBatch.id==SettlementAllocation.batch_id).filter(
            SettlementAllocation.expense_key==e.expense_key,SettlementBatch.responsible_store_id==g.store_id).first()
        if not allowed:abort(403)
    if not e.proof_image:abort(404)
    try:content,mime=read_private_receipt(e.proof_image)
    except Exception:raise ValueError('凭证图片读取失败，请稍后重试') from None
    return Response(content,content_type=mime,headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})


@settlement_bp.post('/expenses/<int:id>/confirm')
@login_required('settlement')
@guard
def confirm_cost(id):
    headquarters()
    multipart=request.mimetype=='multipart/form-data'
    data=request.form if multipart else (request.get_json(silent=True) or {})
    e=SettlementExpense.query.filter_by(id=id).populate_existing().with_for_update().first_or_404()
    if e.status in ('posted','cancelled'):raise ValueError('已入账或已取消成本不可修改')
    reports.assert_editable('expense',e.id)
    note=data.get('Note','')
    if note is None:note=''
    if not isinstance(note,str) or len(note.strip())>500:raise ValueError('文字备注最多 500 字')
    note=note.strip()
    amount=data.get('Amount');provider=data.get('ProviderId',e.provider_id)
    if multipart:
        if not isinstance(amount,str) or not re.fullmatch(r'[0-9]+',amount):raise ValueError('成本金额格式无效')
        amount=int(amount)
        if isinstance(provider,str):
            if not re.fullmatch(r'[0-9]+',provider):raise ValueError('成本提供方无效')
            provider=int(provider)
    amount=as_money(amount)
    if isinstance(provider,bool) or not isinstance(provider,int) or provider<0 or (provider and not db.session.get(Store,provider)):raise ValueError('成本提供方无效')
    before={'amount':e.amount,'provider_id':e.provider_id,'note':e.note,'status':e.status,'proof_image':e.proof_image}
    key=uploaded_proof(e.proof_image,data)
    e.amount=amount;e.note=note;e.provider_id=provider;e.proof_image=key
    if e.completed_at:e.status='ready'
    audit('settlement:expense',str(id),{'before':before,'after':{'amount':e.amount,'provider_id':e.provider_id,'note':e.note,'status':e.status,'proof_image':e.proof_image}})
    db.session.commit();return result(expense_view(e))

@settlement_bp.post('/cards/<int:id>/close')
@login_required('settlement')
@guard
def close_card(id):
    headquarters();raise ValueError('不再支持单卡直接结算，请生成月度报表并在收付款完成后统一确认')

@settlement_bp.post('/usages/<int:id>/review')
@login_required('settlement')
@guard
def review_usage(id):
    headquarters();data=request.get_json() or {};u=SettlementCardUsage.query.filter_by(id=id).first_or_404()
    # Match close_card's pool → usage lock order.
    reports.assert_editable('pool',u.pool_id)
    p=SettlementCardPool.query.filter_by(id=u.pool_id).populate_existing().with_for_update().one()
    u=SettlementCardUsage.query.filter_by(id=id).populate_existing().with_for_update().one()
    if p.status!='open' or u.status!='review':raise ValueError('仅可核验未关闭卡池中的异常记录')
    seconds=data.get('Seconds');note=str(data.get('Note','')).strip()
    if not isinstance(seconds,int) or isinstance(seconds,bool) or seconds<0 or seconds>u.seconds or not note or len(note)>500:raise ValueError('请输入不超过原记录的有效秒数和核验依据')
    u.seconds=seconds;u.status='valid' if seconds else 'excluded';u.note=note
    audit('settlement:review-usage',str(id),{'seconds':seconds,'note':note});db.session.commit();return result(serialize(u))

@settlement_bp.post('/lock')
@login_required('settlement')
@guard
def lock():
    headquarters();data=request.get_json() or {}
    report=reports.confirm(data.get('ReportId'),data.get('Digest'),g.staff.user_id,
        data.get('References'),data.get('AllTransfersCompleted'))
    audit('settlement:report-confirm',str(report.id),{'month':report.month,'version':report.version,'digest':report.digest})
    db.session.commit();return result(reports.public(report))

@settlement_bp.post('/statements/<int:id>/paid')
@login_required('settlement')
@guard
def paid(id):
    headquarters();raise ValueError('收付款与确认结算已合并，请在月度报表确认时统一填写凭证')

@settlement_bp.get('/export')
@login_required('settlement')
@guard
def export():
    import csv,io
    from flask import Response
    month=request.args.get('Month',now().strftime('%Y-%m'));service.month_bounds(month)
    report=reports.current(month)
    if not report:raise ValueError('请先生成固定版本的结算报表，再导出给各方核对')
    expected=request.args.get('ReportId',type=int)
    if expected!=report.id:raise ValueError('报表版本已变化，请刷新后重新导出')
    view=reports.public(report,scope())
    out=io.StringIO();writer=csv.writer(out)
    def safe(v):
        s=str(v)
        return "'"+s if s.lstrip().startswith(('=','+','-','@')) or s.startswith(('\t','\r','\n')) else s
    writer.writerow(['报表编号',view['Number'],'状态','已结算' if report.status=='confirmed' else '待确认','生成时间',view['CreatedAt'],'摘要',report.digest])
    writer.writerow(['口径','北京时间自然月；正数总部付门店，负数门店当期转回总部；完成收付款后确认结算'])
    start,end=service.month_bounds(month)
    coverage_start=report.payload.get('coverage_start',start.isoformat())
    writer.writerow(['结算周期',coverage_start,f'至 {end:%Y-%m-%d} 00:00:00（不含）',
                     '微信消费按支付成功时间；退款按退款成功时间；充值和购卡不重复计入普通消费'])
    writer.writerow(['手续费口径','微信消费净额、储值本金净额、线上月卡分配逐店汇总 × 0.6%；免费赠卡、第三方验券及积分不计费；退款冲减基数，负手续费表示冲回'])
    writer.writerow(['门店','收益及补偿（元）','承担金额（元）','净额（元）','收付款方向'])
    for t in view['Totals']:
        writer.writerow([safe(t['StoreName']),f'{t["income"]/100:.2f}',f'{t["deduction"]/100:.2f}',f'{t["amount"]/100:.2f}',
            '总部净额（对账汇总）' if t['StoreId']==0 else '总部付门店' if t['amount']>0 else '门店转回总部' if t['amount']<0 else '无需转账'])
    writer.writerow([])
    categories=[('wechat_play','游玩微信收款'),('wechat_catering','餐饮微信收款'),('wechat_refund','微信退款'),
        ('wallet','储值本金净额'),('month_card','月卡分配'),('point_compensation','积分成本补偿'),('point_cost','积分承担成本'),('adjustment','其他调整'),('settlement_fee','手续费对净额的影响')]
    writer.writerow(['门店']+[label+'（元）' for _,label in categories]+['结算净额（元）'])
    for t in view['Totals']:
        parts=view['Breakdown'].get(t['StoreId'],{})
        writer.writerow([safe(t['StoreName'])]+[f'{parts.get(key,0)/100:.2f}' for key,_ in categories]+[f'{t["amount"]/100:.2f}'])
    writer.writerow([])
    writer.writerow(['门店','手续费计费基数（元）','统一结算费率','手续费（元，正数扣减/负数冲回）','扣费后结算净额（元）'])
    totals={t['StoreId']:t for t in view['Totals']}
    for f in view['Fees']:
        t=totals[f['StoreId']]
        writer.writerow([safe(t['StoreName']),f"{f['Base']/100:.2f}",f"{f['RateBps']/100:.1f}%",f"{f['Fee']/100:.2f}",f"{t['amount']/100:.2f}"])
    if not view['FeesIncluded']: writer.writerow(['旧版报表未计算统一手续费，原金额保持不变'])
    writer.writerow([])
    writer.writerow(['结算月','发生时间','类型','原始业务','结算出款方','结算收款方','金额（元）','钱包面额（元）','计算说明'])
    labels=dict(categories)|{'wallet_refund':'储值消费退款','month_card_carry':'月卡暂留款补分','point_cost':'积分成本分摊'}
    for e in view['Entries']:
        writer.writerow([month,e['event_at'],labels.get(e['kind'],e['kind']),safe(e['reference']),safe(e['receiver_name'] if e['amount']<0 else e['payer_name']),safe(e['payer_name'] if e['amount']<0 else e['receiver_name']),f'{abs(e["amount"])/100:.2f}',f'{e["face_amount"]/100:.2f}',safe(e['detail'])])
    return Response('\ufeff'+out.getvalue(),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename="settlement-{view["Number"]}.csv"'})

@settlement_bp.post('/adjustments')
@login_required('settlement')
@guard
def adjustment():
    headquarters()
    raise ValueError('补记调整功能已停用')
