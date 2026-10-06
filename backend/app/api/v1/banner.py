from datetime import datetime
from pathlib import PurePosixPath

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import IntegrityError

from app import db
from app.middlewares.auth import login_required
from app.models import Config
from app.services.cos_service import upload_file_to_cos
from app.services.home_banners import CONFIG_KEY, ITEMS_KEY, migrate_banners, revision, validate_items

banner_bp = Blueprint('banner', __name__)


def response(config):
    return jsonify(Code=0, Data={'Items': migrate_banners(config), 'Revision': revision(config), 'Migrated': ITEMS_KEY in config})


@banner_bp.route('', methods=['GET'])
@login_required('home-banners')
def list_banners():
    row = Config.query.filter_by(config_key=CONFIG_KEY, deleted_at=None).first()
    return response(row.config_value or {} if row else {})


@banner_bp.route('', methods=['PUT'])
@login_required('home-banners')
def save_banners():
    data = request.get_json(silent=True)
    try:
        if not isinstance(data, dict):
            raise ValueError('请求数据格式错误')
        items = validate_items(data.get('Items'))
        row = Config.query.filter_by(config_key=CONFIG_KEY).with_for_update().first()
        if row and row.deleted_at is not None:
            db.session.rollback()
            return jsonify(Code=409, Message='公共配置已停用，请先恢复公共配置'), 409
        config = dict(row.config_value or {}) if row else {}
        if data.get('Revision') != revision(config):
            db.session.rollback()
            return jsonify(Code=409, Message='配置已被其他人更新，请刷新后重试'), 409
        config[ITEMS_KEY] = items
        now = datetime.now()
        if row:
            row.config_value = config
            row.updated_at = now
        else:
            row = Config(config_key=CONFIG_KEY, config_value=config, created_at=now, updated_at=now)
            db.session.add(row)
        db.session.commit()
        return response(config)
    except ValueError as exc:
        db.session.rollback()
        return jsonify(Code=400, Message=str(exc)), 400
    except IntegrityError:
        db.session.rollback()
        return jsonify(Code=409, Message='配置已被其他人更新，请刷新后重试'), 409
    except Exception:
        db.session.rollback()
        current_app.logger.exception('保存首页 Banner 失败')
        return jsonify(Code=500, Message='保存失败，请稍后重试'), 500


@banner_bp.route('/image', methods=['POST'])
@login_required('home-banners')
def upload_image():
    file = request.files.get('File')
    if not file:
        return jsonify(Code=400, Message='请选择图片'), 400
    ext = PurePosixPath(file.filename or '').suffix.lower()
    content = file.read(10 * 1024 * 1024 + 1)
    matches = {
        '.jpg': content.startswith(b'\xff\xd8\xff'),
        '.jpeg': content.startswith(b'\xff\xd8\xff'),
        '.png': content.startswith(b'\x89PNG\r\n\x1a\n'),
        '.gif': content[:6] in (b'GIF87a', b'GIF89a'),
        '.webp': content[:4] == b'RIFF' and content[8:12] == b'WEBP',
    }
    if not content or len(content) > 10 * 1024 * 1024 or not matches.get(ext):
        return jsonify(Code=400, Message='请上传 10MB 以内的 JPG、PNG、GIF 或 WebP 图片'), 400
    try:
        url = upload_file_to_cos(content, 'banner'+ext, folder='home-banners')
        return jsonify(Code=0, Data={'Url': url})
    except Exception:
        current_app.logger.exception('上传首页 Banner 图片失败')
        return jsonify(Code=500, Message='图片上传失败，请重试'), 500
