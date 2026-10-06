import json

from flask import Blueprint, jsonify, request
from app.models import BoardGame, BoardGameStoreInventory
from app import db
from datetime import datetime
from app.middlewares.auth import login_required
from sqlalchemy import or_
from app.services.cos_service import upload_file_to_cos
from app.utils.store import get_request_store_id

game_bp = Blueprint('game', __name__)

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
MAX_IMAGE_BYTES = 5 * 1024 * 1024

def _format_time(value):
    return value.strftime('%Y-%m-%d %H:%M:%S') if value else None


def _normalize_json(value, default=None):
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return default
    return default


def _parse_str_list(value, *, max_count=40):
    if value in (None, ''):
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            raise ValueError('字段格式错误，应为 JSON 数组')
    if not isinstance(value, list):
        raise ValueError('字段格式错误，应为数组')
    if len(value) > max_count:
        raise ValueError(f'数组长度不能超过 {max_count}')
    return [str(item).strip() for item in value if str(item).strip()]


def _parse_int_list(value, *, max_count=20):
    if value in (None, ''):
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            raise ValueError('字段格式错误，应为 JSON 数组')
    if not isinstance(value, list):
        raise ValueError('字段格式错误，应为数组')
    if len(value) > max_count:
        raise ValueError(f'数组长度不能超过 {max_count}')
    result = []
    for item in value:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            raise ValueError('数组内必须是数字')
    return result


def _read_body():
    if request.form:
        return request.form
    return request.get_json(silent=True) or {}


def _validate_and_upload_image(file_storage):
    filename = (file_storage.filename or '').lower()
    if '.' not in filename:
        raise ValueError('图片缺少扩展名')
    ext = '.' + filename.rsplit('.', 1)[-1]
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(f'图片格式不支持，仅支持 {", ".join(sorted(ALLOWED_IMAGE_EXTENSIONS))}')

    file_bytes = file_storage.read(MAX_IMAGE_BYTES + 1)
    if not file_bytes:
        raise ValueError('图片内容为空')
    if len(file_bytes) > MAX_IMAGE_BYTES:
        raise ValueError(f'图片大小超过 {MAX_IMAGE_BYTES // 1024 // 1024}MB')
    return upload_file_to_cos(file_bytes, file_storage.filename, folder='board-game-images')


def _serialize_game(game, *, store_id=None, inventory=None):
    return {
        'Id': game.id,
        'StoreId': store_id,
        'Name': game.name,
        'GstoneScore': float(game.gstone_score) if game.gstone_score is not None else None,
        'GstoneRank': game.gstone_rank,
        'SupportedPlayers': _normalize_json(game.supported_players, default=[]),
        'RecommendedPlayers': _normalize_json(game.recommended_players, default=[]),
        'CoverUrl': game.cover_url,
        'Complexity': game.complexity,
        'PlayTime': game.play_time,
        'SetupTime': game.setup_time,
        'LanguageLevel': game.language_level,
        'Description': game.description,
        'PictureList': _normalize_json(game.picture_list, default=[]),
        'Designer': _normalize_json(game.designer, default=[]),
        'Publisher': _normalize_json(game.publisher, default=[]),
        'PublishLanguage': _normalize_json(game.publish_language, default=[]),
        'PublishYear': game.publish_year,
        'Categories': _normalize_json(game.categories, default=[]),
        'Modes': _normalize_json(game.modes, default=[]),
        'Mechanisms': _normalize_json(game.mechanisms, default=[]),
        'Themes': _normalize_json(game.themes, default=[]),
        'TableRequirement': game.table_requirement or '',
        'Portability': game.portability or '',
        'SuitableAge': game.suitable_age or '',
        'Count': inventory.count if inventory else game.count,
        'CreatedAt': _format_time(game.created_at),
        'UpdatedAt': _format_time(game.updated_at),
    }


def _build_game_payload(body, *, require_cover=False):
    name = (body.get('Name') or '').strip()
    if not name:
        raise ValueError('桌游名称不能为空')

    cover_url = (body.get('CoverUrl') or '').strip()
    cover_file = request.files.get('CoverImage') if request.files else None
    if require_cover and not cover_file and not cover_url:
        raise ValueError('请上传封面图')

    description = (body.get('Description') or '').strip()
    if not description:
        raise ValueError('简介不能为空')

    def int_value(key, default=0, minimum=None, maximum=None):
        try:
            value = int(body.get(key, default))
        except (TypeError, ValueError):
            raise ValueError(f'{key} 必须是整数')
        if minimum is not None and value < minimum:
            raise ValueError(f'{key} 不能小于 {minimum}')
        if maximum is not None and value > maximum:
            raise ValueError(f'{key} 不能大于 {maximum}')
        return value

    def score_value():
        raw = body.get('GstoneScore')
        if raw in (None, ''):
            return 0
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise ValueError('评分必须是数字')
        if value < 0 or value > 10:
            raise ValueError('评分需要在 0-10 之间')
        return round(value, 1)

    picture_list = _parse_str_list(body.get('PictureList'))

    payload = {
        'name': name,
        'description': description,
        'gstone_score': score_value(),
        'gstone_rank': int_value('GstoneRank', 0, minimum=0),
        'supported_players': _parse_int_list(body.get('SupportedPlayers')),
        'recommended_players': _parse_int_list(body.get('RecommendedPlayers')),
        'complexity': int_value('Complexity', 1, minimum=1, maximum=10),
        'play_time': int_value('PlayTime', 0, minimum=0),
        'setup_time': (body.get('SetupTime') or '').strip(),
        'language_level': (body.get('LanguageLevel') or '').strip(),
        'picture_list': picture_list,
        'designer': _parse_str_list(body.get('Designer')),
        'publisher': _parse_str_list(body.get('Publisher')),
        'publish_language': _parse_str_list(body.get('PublishLanguage')),
        'publish_year': int_value('PublishYear', 0, minimum=0),
        'categories': _parse_str_list(body.get('Categories')),
        'modes': _parse_str_list(body.get('Modes')),
        'mechanisms': _parse_str_list(body.get('Mechanisms')),
        'themes': _parse_str_list(body.get('Themes')),
        'table_requirement': (body.get('TableRequirement') or '').strip(),
        'portability': (body.get('Portability') or '').strip(),
        'suitable_age': (body.get('SuitableAge') or '').strip(),
    }
    # 先校验所有业务字段，再上传，避免无效表单也等待 COS。
    if cover_file:
        cover_url = _validate_and_upload_image(cover_file)
    if request.files:
        for image_file in request.files.getlist('PictureImages'):
            picture_list.append(_validate_and_upload_image(image_file))
    if cover_url:
        payload['cover_url'] = cover_url
    return payload


def _apply_game_payload(game, payload):
    for key, value in payload.items():
        setattr(game, key, value)


def _inventory_query(store_id):
    return BoardGame.query.join(
        BoardGameStoreInventory,
        BoardGameStoreInventory.board_game_id == BoardGame.id,
    ).filter(
        BoardGame.deleted_at.is_(None),
        BoardGameStoreInventory.deleted_at.is_(None),
        BoardGameStoreInventory.store_id == store_id,
    )


def _list_inventory_games():
    # 获取查询参数
    page = request.args.get('PageNum', 1, type=int)
    page_size = request.args.get('PageSize', 10, type=int)
    keyword = request.args.get('Keyword', '')
    store_id = get_request_store_id()

    query = _inventory_query(store_id)

    # 关键词搜索
    if keyword:
        query = query.filter(or_(
            BoardGame.name.like(f'%{keyword}%'),
            BoardGame.description.like(f'%{keyword}%')
        ))

    # 分页查询
    pagination = query.order_by(BoardGame.id.desc()).paginate(
        page=page,
        per_page=page_size,
        error_out=False
    )

    inventory_map = {
        inventory.board_game_id: inventory
        for inventory in BoardGameStoreInventory.query.filter(
            BoardGameStoreInventory.store_id == store_id,
            BoardGameStoreInventory.deleted_at.is_(None),
            BoardGameStoreInventory.board_game_id.in_([game.id for game in pagination.items] or [0]),
        ).all()
    }
    games = [
        _serialize_game(
            game,
            store_id=store_id,
            inventory=inventory_map.get(game.id),
        )
        for game in pagination.items
    ]

    return jsonify({
        'Code': 0,
        'Message': 'success',
        'Data': {
            'Total': pagination.total,
            'CurrentPage': pagination.page,
            'PageSize': page_size,
            'Items': games
        }
    })


@game_bp.route('/list', methods=['GET'])
@login_required('games')
def get_game_list():
    return _list_inventory_games()


@game_bp.route('/inventory/list', methods=['GET'])
@login_required('games')
def list_inventory_games():
    return _list_inventory_games()


@game_bp.route('/library/list', methods=['GET'])
@login_required('game-library', 'games')
def list_library_games():
    page = request.args.get('PageNum', 1, type=int)
    page_size = request.args.get('PageSize', 10, type=int)
    keyword = (request.args.get('Keyword') or '').strip()

    query = BoardGame.query.filter(BoardGame.deleted_at.is_(None))
    if keyword:
        query = query.filter(or_(
            BoardGame.name.like(f'%{keyword}%'),
            BoardGame.description.like(f'%{keyword}%'),
        ))

    pagination = query.order_by(BoardGame.id.desc()).paginate(
        page=page,
        per_page=page_size,
        error_out=False,
    )
    return jsonify({
        'Code': 0,
        'Message': 'success',
        'Data': {
            'Total': pagination.total,
            'CurrentPage': pagination.page,
            'PageSize': page_size,
            'Items': [_serialize_game(game) for game in pagination.items],
        },
    })


@game_bp.route('/library/<int:game_id>', methods=['GET'])
@login_required('game-library', 'games')
def get_library_game(game_id):
    game = BoardGame.query.filter(
        BoardGame.id == game_id,
        BoardGame.deleted_at.is_(None),
    ).first()
    if not game:
        return jsonify({'Code': 404, 'Message': '桌游不存在', 'Data': None}), 404
    return jsonify({'Code': 0, 'Message': 'success', 'Data': _serialize_game(game)})


@game_bp.route('/library/image', methods=['POST'])
@login_required('game-library')
def upload_library_image():
    image = request.files.get('Image')
    if not image:
        return jsonify(Code=400, Message='请选择图片', Data=None), 400
    try:
        url = _validate_and_upload_image(image)
    except ValueError as exc:
        return jsonify(Code=400, Message=str(exc), Data=None), 400
    except Exception:
        return jsonify(Code=500, Message='图片上传失败，请重试', Data=None), 500
    return jsonify(Code=0, Message='上传成功', Data={'Url': url})


@game_bp.route('/library', methods=['POST'])
@login_required('game-library')
def create_library_game():
    try:
        payload = _build_game_payload(_read_body(), require_cover=True)
    except ValueError as exc:
        return jsonify({'Code': 1, 'Message': str(exc), 'Data': None}), 400
    except Exception as exc:
        return jsonify({'Code': 500, 'Message': f'图片上传失败：{exc}', 'Data': None}), 500

    now = datetime.utcnow()
    game = BoardGame(created_at=now, updated_at=now, count=1)
    _apply_game_payload(game, payload)
    db.session.add(game)
    db.session.commit()
    return jsonify({'Code': 0, 'Message': '创建成功', 'Data': _serialize_game(game)})


@game_bp.route('/library/<int:game_id>', methods=['PUT'])
@login_required('game-library')
def update_library_game(game_id):
    game = BoardGame.query.filter(
        BoardGame.id == game_id,
        BoardGame.deleted_at.is_(None),
    ).first()
    if not game:
        return jsonify({'Code': 404, 'Message': '桌游不存在', 'Data': None}), 404
    try:
        payload = _build_game_payload(_read_body(), require_cover=False)
    except ValueError as exc:
        return jsonify({'Code': 1, 'Message': str(exc), 'Data': None}), 400
    except Exception as exc:
        return jsonify({'Code': 500, 'Message': f'图片上传失败：{exc}', 'Data': None}), 500

    _apply_game_payload(game, payload)
    game.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'Code': 0, 'Message': '更新成功', 'Data': _serialize_game(game)})


@game_bp.route('/library/<int:game_id>', methods=['DELETE'])
@login_required('game-library')
def delete_library_game(game_id):
    game = BoardGame.query.filter(
        BoardGame.id == game_id,
        BoardGame.deleted_at.is_(None),
    ).first()
    if not game:
        return jsonify({'Code': 404, 'Message': '桌游不存在', 'Data': None}), 404
    active_inventory_count = BoardGameStoreInventory.query.execution_options(global_reference_check=True).filter(
        BoardGameStoreInventory.board_game_id == game_id,
        BoardGameStoreInventory.deleted_at.is_(None),
    ).count()
    if active_inventory_count > 0:
        return jsonify({
            'Code': 1,
            'Message': '该桌游仍存在门店库存，请先从各门店库存移除',
            'Data': None,
        }), 400
    game.deleted_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'Code': 0, 'Message': '删除成功', 'Data': None})


@game_bp.route('/inventory', methods=['POST'])
@login_required('games')
def add_inventory_game():
    body = _read_body()
    store_id = get_request_store_id()
    try:
        board_game_id = int(body.get('BoardGameId'))
        count = int(body.get('Count', 1))
    except (TypeError, ValueError):
        return jsonify({'Code': 1, 'Message': '请选择桌游并填写数量', 'Data': None}), 400
    if count < 0:
        return jsonify({'Code': 1, 'Message': '数量不能为负数', 'Data': None}), 400
    game = BoardGame.query.filter(
        BoardGame.id == board_game_id,
        BoardGame.deleted_at.is_(None),
    ).first()
    if not game:
        return jsonify({'Code': 404, 'Message': '桌游不存在', 'Data': None}), 404

    now = datetime.utcnow()
    inventory = BoardGameStoreInventory.query.filter(
        BoardGameStoreInventory.store_id == store_id,
        BoardGameStoreInventory.board_game_id == board_game_id,
    ).first()
    if inventory:
        inventory.count = count
        inventory.deleted_at = None
        inventory.updated_at = now
    else:
        inventory = BoardGameStoreInventory(
            store_id=store_id,
            board_game_id=board_game_id,
            count=count,
            created_at=now,
            updated_at=now,
        )
        db.session.add(inventory)
    db.session.commit()
    return jsonify({
        'Code': 0,
        'Message': '添加成功',
        'Data': _serialize_game(game, store_id=store_id, inventory=inventory),
    })


@game_bp.route('/inventory/<int:game_id>', methods=['PUT'])
@login_required('games')
def update_inventory_game(game_id):
    body = _read_body()
    store_id = get_request_store_id()
    try:
        count = int(body.get('Count', 0))
    except (TypeError, ValueError):
        return jsonify({'Code': 1, 'Message': '数量必须是整数', 'Data': None}), 400
    if count < 0:
        return jsonify({'Code': 1, 'Message': '数量不能为负数', 'Data': None}), 400
    inventory = BoardGameStoreInventory.query.filter(
        BoardGameStoreInventory.store_id == store_id,
        BoardGameStoreInventory.board_game_id == game_id,
        BoardGameStoreInventory.deleted_at.is_(None),
    ).first()
    if not inventory:
        return jsonify({'Code': 404, 'Message': '当前门店库存不存在', 'Data': None}), 404
    inventory.count = count
    inventory.updated_at = datetime.utcnow()
    db.session.commit()
    game = BoardGame.query.get(game_id)
    return jsonify({
        'Code': 0,
        'Message': '更新成功',
        'Data': _serialize_game(game, store_id=store_id, inventory=inventory),
    })


@game_bp.route('/inventory/<int:game_id>', methods=['DELETE'])
@login_required('games')
def delete_inventory_game(game_id):
    store_id = get_request_store_id()
    inventory = BoardGameStoreInventory.query.filter(
        BoardGameStoreInventory.store_id == store_id,
        BoardGameStoreInventory.board_game_id == game_id,
        BoardGameStoreInventory.deleted_at.is_(None),
    ).first()
    if not inventory:
        return jsonify({'Code': 404, 'Message': '当前门店库存不存在', 'Data': None}), 404
    inventory.deleted_at = datetime.utcnow()
    inventory.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'Code': 0, 'Message': '删除成功', 'Data': None})

@game_bp.route('/<int:game_id>', methods=['DELETE'])
@login_required('game-library')
def delete_game(game_id):
    return delete_library_game(game_id)
