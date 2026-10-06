from datetime import datetime
from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import IntegrityError
from app import db
from app.middlewares.auth import login_required
from app.models import Config
from app.services.home_banners import CONFIG_KEY
from app.services.home_promotions import PROMOTIONS_KEY, read_promotions, promotion_revision, validate_promotions

promotion_bp = Blueprint('promotion', __name__)


def response(config):
    return jsonify(Code=0, Data={'Config': read_promotions(config), 'Revision': promotion_revision(config)})


@promotion_bp.route('', methods=['GET'])
@login_required('home-banners')
def get_promotions():
    row = Config.query.filter_by(config_key=CONFIG_KEY, deleted_at=None).first()
    return response((row.config_value or {}) if row else {})


@promotion_bp.route('', methods=['PUT'])
@login_required('home-banners')
def save_promotions():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict): raise ValueError('请求格式错误')
        value = validate_promotions(data.get('Config'))
        row = Config.query.filter_by(config_key=CONFIG_KEY).with_for_update().first()
        if row and row.deleted_at is not None:
            db.session.rollback()
            return jsonify(Code=409, Message='公共配置已停用'), 409
        config = dict(row.config_value or {}) if row else {}
        if data.get('Revision') != promotion_revision(config):
            db.session.rollback()
            return jsonify(Code=409, Message='配置已被其他人更新，请刷新后重试'), 409
        config[PROMOTIONS_KEY] = value
        now = datetime.now()
        if row:
            row.config_value, row.updated_at = config, now
        else:
            db.session.add(Config(config_key=CONFIG_KEY, config_value=config, created_at=now, updated_at=now))
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
        current_app.logger.exception('保存展示配置失败')
        return jsonify(Code=500, Message='保存失败，请重试'), 500
