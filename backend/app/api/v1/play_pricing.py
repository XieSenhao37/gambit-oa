from datetime import datetime, timedelta, timezone
import copy
from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy.exc import IntegrityError
from app import db
from app.middlewares.auth import login_required
from app.models import Config, Store
from app.services.play_pricing import KEY, CALENDAR, read_schedule, revision, validate_schedule, resolve_price, total

play_pricing_bp = Blueprint('play_pricing', __name__)


def response(config):
    return jsonify(Code=0, Data={'Config': read_schedule(config, g.store_id), 'Revision': revision(config), 'Calendar': CALENDAR})


@play_pricing_bp.route('', methods=['GET'])
@login_required('play-pricing')
def get_pricing():
    row = Config.query.filter_by(config_key=KEY, deleted_at=None).first()
    return response(row.config_value or {} if row else {})


@play_pricing_bp.route('', methods=['PUT'])
@login_required('play-pricing')
def save_pricing():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError('请求格式错误')
        schedule = validate_schedule(data.get('Config'))
        if not Store.query.filter_by(id=g.store_id, deleted_at=None, status=1).first():
            raise ValueError('门店无效或已停用')
        # Legacy databases retain deleted rows with the same key. Lock the
        # active record used by GET and Go instead of selecting an old tombstone.
        row = Config.query.filter_by(config_key=KEY, deleted_at=None).with_for_update().first()
        if row is None and Config.query.filter_by(config_key=KEY).with_for_update().first():
            db.session.rollback()
            return jsonify(Code=409, Message='计价配置已停用'), 409
        config = copy.deepcopy(row.config_value or {}) if row else {}
        if data.get('Revision') != revision(config):
            db.session.rollback()
            return jsonify(Code=409, Message='价格已被其他人更新，请刷新后重试'), 409
        # Migrating global legacy pricing must retain every other active store's effective price.
        if not config.get('StoreMap') and read_schedule(config, g.store_id):
            legacy = read_schedule(config, g.store_id)
            config['StoreMap'] = {str(s.id): copy.deepcopy(legacy) for s in Store.query.filter_by(deleted_at=None, status=1).all()}
        config.setdefault('StoreMap', {})[str(g.store_id)] = schedule
        now = datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)
        if row:
            row.config_value, row.updated_at = config, now
        else:
            db.session.add(Config(config_key=KEY, config_value=config, created_at=now, updated_at=now))
        db.session.commit()
        return response(config)
    except ValueError as exc:
        db.session.rollback()
        return jsonify(Code=400, Message=str(exc)), 400
    except IntegrityError:
        db.session.rollback()
        return jsonify(Code=409, Message='配置已更新，请刷新后重试'), 409
    except Exception:
        db.session.rollback()
        current_app.logger.exception('保存桌游计价失败')
        return jsonify(Code=500, Message='保存失败，请重试'), 500


@play_pricing_bp.route('/preview', methods=['POST'])
@login_required('play-pricing')
def preview_pricing():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError('请求格式错误')
        schedule = validate_schedule(data.get('Config'))
        at = datetime.strptime(data.get('InTime', ''), '%Y-%m-%d %H:%M')
        hours = data.get('Hours')
        if type(hours) is not int or not 1 <= hours <= 720:
            raise ValueError('试算小时数须为 1–720')
        price, rule, kind = resolve_price(schedule, at)
        return jsonify(Code=0, Data={'Amount': total(price, hours), 'Rule': rule, 'DayType': kind, 'Price': price})
    except (ValueError, TypeError) as exc:
        return jsonify(Code=400, Message=str(exc)), 400
