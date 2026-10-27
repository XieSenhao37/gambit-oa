"""餐品管理接口（OA 直连数据库）"""
import json
import hashlib
from datetime import datetime

from flask import Blueprint, abort, jsonify, request

from app import db
from app.middlewares.auth import login_required
from app.models import Dish, DishCategory, DishLibraryItem, DishOption, DishStoreItem
from app.services.cos_service import upload_file_to_cos
from app.utils.store import get_request_store_id

dish_bp = Blueprint('dish', __name__)

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5MB


def _format_time(value):
    return value.strftime('%Y-%m-%d %H:%M:%S') if value else None


def _normalize_json_field(value, default=None):
    """把 JSON 字段标准化成 list/dict，处理 SQLAlchemy 返回的 str 或已解析对象。"""
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


def _serialize_dish(dish):
    return {
        'Id': dish.id,
        'StoreId': dish.store_id,
        'Name': dish.name,
        'CategoryIds': _normalize_json_field(dish.category_ids, default=[]),
        'Description': dish.description or '',
        'Price': dish.price,
        'ImageUrl': dish.image_url or '',
        'Options': _normalize_json_field(dish.options, default=[]),
        'Tags': _normalize_json_field(dish.tags, default=[]),
        'Status': int(dish.status) if dish.status is not None else 1,
        'CreatedAt': _format_time(dish.created_at),
        'UpdatedAt': _format_time(dish.updated_at),
    }


def _serialize_category(category):
    return {
        'Id': category.id,
        'Name': category.name,
        'Sort': category.sort,
        'Revision': _category_revision(category),
    }


def _category_revision(category):
    content = [category.name, category.sort, str(category.updated_at)]
    return hashlib.sha256(json.dumps(content, ensure_ascii=False).encode()).hexdigest()


def _validate_category_ids(raw):
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            raise ValueError('分类格式错误，应为分类 ID 数组')
    ids = raw
    if not isinstance(ids, list) or any(type(value) is not int or value <= 0 for value in ids):
        raise ValueError('分类格式错误，应为分类 ID 数组')
    if not ids:
        raise ValueError('至少选择一个分类')
    # Share the category row lock with deletion until the dish write commits.
    categories = DishCategory.query.filter(
        DishCategory.id.in_(ids), DishCategory.deleted_at.is_(None),
    ).order_by(DishCategory.id).with_for_update().all()
    if set(ids) != {category.id for category in categories}:
        raise ValueError('所选分类已删除或不存在，请刷新后重新选择')
    return list(dict.fromkeys(ids))


@dish_bp.route('/categories', methods=['GET'])
@login_required('dish-categories', 'dish-library', 'dishes')
def list_categories():
    items = DishCategory.query.filter(DishCategory.deleted_at.is_(None)).order_by(
        DishCategory.sort.asc(), DishCategory.id.asc(),
    ).all()
    return jsonify(Code=0, Message='success', Data={'Items': [_serialize_category(c) for c in items]})


def _category_payload():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description='请提交分类名称和排序')
    name = body.get('Name')
    if not isinstance(name, str) or not name.strip():
        abort(400, description='请输入分类名称')
    name = name.strip()
    if len(name) > 60:
        abort(400, description='分类名称最多 60 字')
    sort = body.get('Sort', 0)
    if type(sort) is not int or not 0 <= sort <= 2147483647:
        abort(400, description='排序必须是 0 至 2147483647 的整数')
    return name, sort


def _require_unique_category(name, excluding=None):
    query = DishCategory.query.filter(DishCategory.deleted_at.is_(None), DishCategory.name == name)
    if excluding is not None:
        query = query.filter(DishCategory.id != excluding)
    if query.first():
        abort(400, description='已存在同名分类')


def _category_for_edit(category_id):
    item = DishCategory.query.filter(
        DishCategory.id == category_id, DishCategory.deleted_at.is_(None),
    ).with_for_update().populate_existing().first()
    if not item:
        abort(404, description='分类不存在或已删除')
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or body.get('Revision') != _category_revision(item):
        abort(409, description='分类已更新，请刷新后重试')
    return item


@dish_bp.route('/categories', methods=['POST'])
@login_required('dish-categories')
def create_category():
    name, sort = _category_payload()
    _require_unique_category(name)
    now = datetime.utcnow()
    item = DishCategory(name=name, sort=sort, created_at=now, updated_at=now)
    db.session.add(item)
    db.session.commit()
    return jsonify(Code=0, Message='创建成功', Data=_serialize_category(item))


@dish_bp.route('/categories/<int:category_id>', methods=['PUT'])
@login_required('dish-categories')
def update_category(category_id):
    name, sort = _category_payload()
    item = _category_for_edit(category_id)
    _require_unique_category(name, excluding=item.id)
    item.name, item.sort, item.updated_at = name, sort, datetime.utcnow()
    db.session.commit()
    return jsonify(Code=0, Message='更新成功', Data=_serialize_category(item))


@dish_bp.route('/categories/<int:category_id>', methods=['DELETE'])
@login_required('dish-categories')
def delete_category(category_id):
    item = _category_for_edit(category_id)
    # Include every store, down-shelf dishes, and legacy rows. Use a current
    # locking read rather than a repeatable-read snapshot before deleting.
    for model in (DishLibraryItem, Dish):
        rows = db.session.query(model.category_ids).execution_options(global_reference_check=True).filter(
            model.deleted_at.is_(None),
        ).with_for_update().all()
        if any(item.id in (_normalize_json_field(row[0], default=[]) or []) for row in rows):
            abort(400, description='该分类已被餐品引用，请先修改相关餐品分类')
    item.deleted_at = item.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(Code=0, Message='删除成功', Data=None)


def _serialize_option(option):
    return {
        'Id': option.id,
        'Name': option.name,
        'Type': option.type,
        'Items': _normalize_json_field(option.items, default=[]),
        'Description': option.description or '',
    }


def _serialize_library_item(item):
    return {
        'Id': item.id,
        'Name': item.name,
        'Description': item.description or '',
        'DefaultPrice': item.default_price or 0,
        'ImageUrl': item.image_url or '',
        'CategoryIds': _normalize_json_field(item.category_ids, default=[]),
        'Options': _normalize_json_field(item.options, default=[]),
        'Tags': _normalize_json_field(item.tags, default=[]),
        'CreatedAt': _format_time(item.created_at),
        'UpdatedAt': _format_time(item.updated_at),
    }


def _serialize_store_item(store_item, library_item=None):
    library_item = library_item or DishLibraryItem.query.get(store_item.dish_library_item_id)
    return {
        'Id': store_item.id,
        'StoreId': store_item.store_id,
        'LibraryItemId': store_item.dish_library_item_id,
        'DishId': store_item.dish_id,
        'Name': library_item.name if library_item else '',
        'Description': (library_item.description if library_item else '') or '',
        'Price': store_item.price or 0,
        'DefaultPrice': library_item.default_price if library_item else 0,
        'ImageUrl': (library_item.image_url if library_item else '') or '',
        'CategoryIds': _normalize_json_field(library_item.category_ids if library_item else None, default=[]),
        'Options': _normalize_json_field(library_item.options if library_item else None, default=[]),
        'Tags': _normalize_json_field(library_item.tags if library_item else None, default=[]),
        'Status': int(store_item.status) if store_item.status is not None else 1,
        'Sort': store_item.sort or 0,
        'CreatedAt': _format_time(store_item.created_at),
        'UpdatedAt': _format_time(store_item.updated_at),
    }


def _library_map(library_ids):
    ids = [int(item_id) for item_id in set(library_ids) if item_id]
    if not ids:
        return {}
    items = DishLibraryItem.query.filter(
        DishLibraryItem.id.in_(ids),
        DishLibraryItem.deleted_at.is_(None),
    ).all()
    return {item.id: item for item in items}


def _parse_int_list(raw):
    if raw is None or raw == '':
        return []
    if isinstance(raw, list):
        return [int(x) for x in raw]
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        raise ValueError('字段格式错误，应为 JSON 数组')
    if not isinstance(parsed, list):
        raise ValueError('字段格式错误，应为 JSON 数组')
    return [int(x) for x in parsed]


def _parse_str_list(raw, *, max_count=20):
    if raw is None or raw == '':
        return []
    if isinstance(raw, list):
        items = raw
    else:
        try:
            items = json.loads(raw)
        except (TypeError, ValueError):
            raise ValueError('字段格式错误，应为 JSON 数组')
    if not isinstance(items, list):
        raise ValueError('字段格式错误，应为 JSON 数组')
    if len(items) > max_count:
        raise ValueError(f'数量超出上限 {max_count}')
    return [str(x).strip() for x in items if str(x).strip()]


def _validate_and_upload_image(file_storage):
    """校验上传文件并写入 COS，返回访问 URL。"""
    filename = (file_storage.filename or '').lower()
    if '.' not in filename:
        raise ValueError('图片缺少扩展名')
    ext = '.' + filename.rsplit('.', 1)[-1]
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(f'图片格式不支持，仅支持 {", ".join(sorted(ALLOWED_IMAGE_EXTENSIONS))}')

    file_bytes = file_storage.read()
    if not file_bytes:
        raise ValueError('图片内容为空')
    if len(file_bytes) > MAX_IMAGE_BYTES:
        raise ValueError(f'图片大小超过 {MAX_IMAGE_BYTES // 1024 // 1024}MB')
    return upload_file_to_cos(file_bytes, file_storage.filename)


def _read_form_value(key, *, default=None):
    """form-data 或 JSON body 都能读到字段。"""
    if request.form and key in request.form:
        return request.form.get(key)
    if request.is_json:
        data = request.get_json(silent=True) or {}
        return data.get(key, default)
    return default


def _read_json_body():
    return request.get_json(silent=True) or {}


def _build_library_from_form(require_image=False):
    name = (_read_form_value('Name') or '').strip()
    if not name:
        raise ValueError('请输入餐品名称')

    price_raw = _read_form_value('DefaultPrice', default=_read_form_value('Price', default=0))
    try:
        default_price = int(round(float(price_raw or 0) * 100))
    except (TypeError, ValueError):
        raise ValueError('价格格式错误')
    if default_price < 0:
        raise ValueError('价格不能小于 0')

    image_url = (_read_form_value('ImageUrl') or '').strip()
    image_file = request.files.get('Image')
    if image_file:
        image_url = _validate_and_upload_image(image_file)
    if require_image and not image_url:
        raise ValueError('请上传餐品图片')

    return {
        'name': name,
        'description': (_read_form_value('Description') or '').strip(),
        'default_price': default_price,
        'image_url': image_url,
        'category_ids': _validate_category_ids(_read_form_value('CategoryIds')),
        'options': _parse_int_list(_read_form_value('Options')),
        'tags': _parse_str_list(_read_form_value('Tags')),
    }


def _build_store_payload(default_price=0):
    body = _read_json_body()
    raw_library_id = body.get('LibraryItemId') or body.get('DishLibraryItemId')
    library_item_id = int(raw_library_id) if raw_library_id else None
    price = body.get('Price', default_price)
    try:
        price = int(round(float(price or 0)))
    except (TypeError, ValueError):
        raise ValueError('价格格式错误')
    if price < 0:
        raise ValueError('价格不能小于 0')

    raw_status = body.get('Status', 1)
    try:
        status = int(raw_status)
    except (TypeError, ValueError):
        raise ValueError('Status 必须为 0 或 1')
    if status not in (0, 1):
        raise ValueError('Status 必须为 0 或 1')

    raw_sort = body.get('Sort', 0)
    try:
        sort = int(raw_sort or 0)
    except (TypeError, ValueError):
        raise ValueError('排序必须为整数')

    return {
        'library_item_id': library_item_id,
        'price': price,
        'status': status,
        'sort': sort,
    }


def _sync_legacy_dish(store_item, library_item):
    """同步旧 dishes 行，保证小程序菜单和下单兼容。"""
    now = datetime.utcnow()
    dish = None
    if store_item.dish_id:
        dish = Dish.query.filter(
            Dish.id == store_item.dish_id,
            Dish.store_id == store_item.store_id,
        ).first()
    if not dish:
        dish = Dish(
            created_at=now,
            store_id=store_item.store_id,
            library_item_id=library_item.id,
        )
        db.session.add(dish)

    dish.name = library_item.name
    dish.library_item_id = library_item.id
    dish.description = library_item.description or ''
    dish.price = store_item.price
    dish.image_url = library_item.image_url or ''
    dish.category_ids = library_item.category_ids or []
    dish.options = library_item.options or []
    dish.tags = library_item.tags or []
    dish.status = store_item.status
    dish.deleted_at = store_item.deleted_at
    dish.updated_at = now
    db.session.flush()
    store_item.dish_id = dish.id


@dish_bp.route('/list', methods=['GET'])
@login_required('dishes')
def list_dishes():
    page = request.args.get('current', 1, type=int)
    page_size = request.args.get('pageSize', 20, type=int)
    keyword = (request.args.get('Keyword') or '').strip()
    store_id = get_request_store_id()

    query = DishStoreItem.query.join(
        DishLibraryItem,
        DishLibraryItem.id == DishStoreItem.dish_library_item_id,
    ).filter(
        DishStoreItem.deleted_at.is_(None),
        DishStoreItem.store_id == store_id,
        DishLibraryItem.deleted_at.is_(None),
    )
    if keyword:
        query = query.filter(DishLibraryItem.name.like(f'%{keyword}%'))

    pagination = query.order_by(DishStoreItem.sort.asc(), DishStoreItem.id.desc()).paginate(
        page=page,
        per_page=page_size,
        error_out=False,
    )
    libraries = _library_map([item.dish_library_item_id for item in pagination.items])

    categories = DishCategory.query.filter(
        DishCategory.deleted_at.is_(None),
    ).order_by(
        DishCategory.sort.asc(), DishCategory.id.asc()
    ).all()
    options = DishOption.query.filter(
        DishOption.deleted_at.is_(None),
    ).order_by(
        DishOption.id.asc()
    ).all()

    return jsonify({
        'Code': 0,
        'Message': 'success',
        'Data': {
            'Total': pagination.total,
            'CurrentPage': pagination.page,
            'PageSize': page_size,
            'Items': [
                _serialize_store_item(item, libraries.get(item.dish_library_item_id))
                for item in pagination.items
            ],
            'Categories': [_serialize_category(c) for c in categories],
            'Options': [_serialize_option(o) for o in options],
        },
    })


def _build_dish_from_form(*, require_image):
    name = (_read_form_value('Name') or '').strip()
    if not name:
        raise ValueError('餐品名称不能为空')
    if len(name) > 60:
        raise ValueError('餐品名称过长，最多 60 字')

    price_raw = _read_form_value('Price')
    if price_raw is None or price_raw == '':
        raise ValueError('价格不能为空')
    try:
        price = int(price_raw)
    except (TypeError, ValueError):
        raise ValueError('价格必须是整数（单位：分）')
    if price < 0:
        raise ValueError('价格不能为负数')

    description = (_read_form_value('Description') or '').strip()
    if len(description) > 255:
        raise ValueError('描述过长，最多 255 字')

    category_ids = _validate_category_ids(_read_form_value('CategoryIds'))

    option_ids = _parse_int_list(_read_form_value('Options'))
    tags = _parse_str_list(_read_form_value('Tags'), max_count=10)

    image_url = None
    image_file = request.files.get('Image') if request.files else None
    if image_file:
        image_url = _validate_and_upload_image(image_file)
    elif require_image:
        raise ValueError('请上传餐品图片')

    return {
        'name': name,
        'price': price,
        'description': description,
        'category_ids': category_ids,
        'options': option_ids,
        'tags': tags,
        'image_url': image_url,
    }


@dish_bp.route('/create', methods=['POST'])
@login_required('dishes')
def create_dish():
    try:
        payload = _build_dish_from_form(require_image=True)
    except ValueError as exc:
        return jsonify({'Code': 1, 'Message': str(exc), 'Data': None}), 400
    except Exception as exc:
        return jsonify({'Code': 500, 'Message': f'图片上传失败：{exc}', 'Data': None}), 500

    now = datetime.utcnow()
    store_id = get_request_store_id()
    library_item = DishLibraryItem(
        name=payload['name'],
        default_price=payload['price'],
        description=payload['description'],
        category_ids=payload['category_ids'],
        options=payload['options'],
        tags=payload['tags'],
        image_url=payload['image_url'],
        created_at=now,
        updated_at=now,
    )
    db.session.add(library_item)
    db.session.flush()

    store_item = DishStoreItem(
        store_id=store_id,
        dish_library_item_id=library_item.id,
        price=payload['price'],
        status=1,
        sort=0,
        created_at=now,
        updated_at=now,
    )
    db.session.add(store_item)
    db.session.flush()
    _sync_legacy_dish(store_item, library_item)
    db.session.commit()

    return jsonify({
        'Code': 0,
        'Message': '创建成功',
        'Data': _serialize_store_item(store_item, library_item),
    })


@dish_bp.route('/library/list', methods=['GET'])
@login_required('dish-library', 'dishes')
def list_library_items():
    page = request.args.get('current', 1, type=int)
    page_size = request.args.get('pageSize', 20, type=int)
    keyword = (request.args.get('Keyword') or '').strip()
    query = DishLibraryItem.query.filter(DishLibraryItem.deleted_at.is_(None))
    if keyword:
        query = query.filter(DishLibraryItem.name.like(f'%{keyword}%'))
    pagination = query.order_by(DishLibraryItem.id.desc()).paginate(
        page=page,
        per_page=page_size,
        error_out=False,
    )
    categories = DishCategory.query.filter(
        DishCategory.deleted_at.is_(None),
    ).order_by(DishCategory.sort.asc(), DishCategory.id.asc()).all()
    options = DishOption.query.filter(
        DishOption.deleted_at.is_(None),
    ).order_by(DishOption.id.asc()).all()
    return jsonify({
        'Code': 0,
        'Message': 'success',
        'Data': {
            'Total': pagination.total,
            'CurrentPage': pagination.page,
            'PageSize': page_size,
            'Items': [_serialize_library_item(item) for item in pagination.items],
            'Categories': [_serialize_category(c) for c in categories],
            'Options': [_serialize_option(o) for o in options],
        },
    })


@dish_bp.route('/library/<int:item_id>', methods=['GET'])
@login_required('dish-library', 'dishes')
def get_library_item(item_id):
    item = DishLibraryItem.query.filter(
        DishLibraryItem.id == item_id,
        DishLibraryItem.deleted_at.is_(None),
    ).first()
    if not item:
        return jsonify({'Code': 404, 'Message': '餐品不存在', 'Data': None}), 404
    return jsonify({'Code': 0, 'Message': 'success', 'Data': _serialize_library_item(item)})


@dish_bp.route('/library', methods=['POST'])
@login_required('dish-library')
def create_library_item():
    try:
        payload = _build_library_from_form(require_image=True)
    except ValueError as exc:
        return jsonify({'Code': 1, 'Message': str(exc), 'Data': None}), 400
    except Exception as exc:
        return jsonify({'Code': 500, 'Message': f'图片上传失败：{exc}', 'Data': None}), 500

    now = datetime.utcnow()
    item = DishLibraryItem(
        name=payload['name'],
        description=payload['description'],
        default_price=payload['default_price'],
        image_url=payload['image_url'],
        category_ids=payload['category_ids'],
        options=payload['options'],
        tags=payload['tags'],
        created_at=now,
        updated_at=now,
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({'Code': 0, 'Message': '创建成功', 'Data': _serialize_library_item(item)})


@dish_bp.route('/library/<int:item_id>', methods=['PUT'])
@login_required('dish-library')
def update_library_item(item_id):
    item = DishLibraryItem.query.filter(
        DishLibraryItem.id == item_id,
        DishLibraryItem.deleted_at.is_(None),
    ).first()
    if not item:
        return jsonify({'Code': 404, 'Message': '餐品不存在', 'Data': None}), 404
    try:
        payload = _build_library_from_form(require_image=False)
    except ValueError as exc:
        return jsonify({'Code': 1, 'Message': str(exc), 'Data': None}), 400
    except Exception as exc:
        return jsonify({'Code': 500, 'Message': f'图片上传失败：{exc}', 'Data': None}), 500

    item.name = payload['name']
    item.description = payload['description']
    item.default_price = payload['default_price']
    item.category_ids = payload['category_ids']
    item.options = payload['options']
    item.tags = payload['tags']
    if payload['image_url']:
        item.image_url = payload['image_url']
    item.updated_at = datetime.utcnow()
    store_items = DishStoreItem.query.filter(
        DishStoreItem.dish_library_item_id == item.id,
        DishStoreItem.deleted_at.is_(None),
    ).all()
    for store_item in store_items:
        _sync_legacy_dish(store_item, item)
    db.session.commit()
    return jsonify({'Code': 0, 'Message': '更新成功', 'Data': _serialize_library_item(item)})


@dish_bp.route('/library/<int:item_id>', methods=['DELETE'])
@login_required('dish-library')
def delete_library_item(item_id):
    item = DishLibraryItem.query.filter(
        DishLibraryItem.id == item_id,
        DishLibraryItem.deleted_at.is_(None),
    ).first()
    if not item:
        return jsonify({'Code': 404, 'Message': '餐品不存在', 'Data': None}), 404
    exists_store_item = DishStoreItem.query.execution_options(global_reference_check=True).filter(
        DishStoreItem.dish_library_item_id == item.id,
        DishStoreItem.deleted_at.is_(None),
    ).first()
    if exists_store_item:
        return jsonify({'Code': 1, 'Message': '该餐品已被门店菜单引用，请先从门店菜单移除', 'Data': None}), 400
    item.deleted_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'Code': 0, 'Message': '删除成功', 'Data': None})


@dish_bp.route('/store-items', methods=['POST'])
@login_required('dishes')
def create_store_item():
    store_id = get_request_store_id()
    try:
        payload = _build_store_payload()
    except ValueError as exc:
        return jsonify({'Code': 1, 'Message': str(exc), 'Data': None}), 400
    if not payload['library_item_id']:
        return jsonify({'Code': 1, 'Message': '请选择餐品信息库餐品', 'Data': None}), 400

    library_item = DishLibraryItem.query.filter(
        DishLibraryItem.id == payload['library_item_id'],
        DishLibraryItem.deleted_at.is_(None),
    ).first()
    if not library_item:
        return jsonify({'Code': 404, 'Message': '餐品不存在', 'Data': None}), 404
    exists = DishStoreItem.query.filter(
        DishStoreItem.store_id == store_id,
        DishStoreItem.dish_library_item_id == library_item.id,
        DishStoreItem.deleted_at.is_(None),
    ).first()
    if exists:
        return jsonify({'Code': 1, 'Message': '当前门店菜单已添加该餐品', 'Data': None}), 400

    now = datetime.utcnow()
    store_item = DishStoreItem(
        store_id=store_id,
        dish_library_item_id=library_item.id,
        price=payload['price'] if payload['price'] is not None else library_item.default_price,
        status=payload['status'],
        sort=payload['sort'],
        created_at=now,
        updated_at=now,
    )
    db.session.add(store_item)
    db.session.flush()
    _sync_legacy_dish(store_item, library_item)
    db.session.commit()
    return jsonify({'Code': 0, 'Message': '添加成功', 'Data': _serialize_store_item(store_item, library_item)})


@dish_bp.route('/store-items/<int:dish_id>', methods=['PUT'])
@dish_bp.route('/<int:dish_id>', methods=['PUT'])
@login_required('dishes')
def update_dish(dish_id):
    store_id = get_request_store_id()
    store_item = DishStoreItem.query.filter(
        DishStoreItem.id == dish_id,
        DishStoreItem.store_id == store_id,
        DishStoreItem.deleted_at.is_(None),
    ).first()
    if not store_item:
        return jsonify({'Code': 404, 'Message': '菜单项不存在', 'Data': None}), 404
    library_item = DishLibraryItem.query.filter(
        DishLibraryItem.id == store_item.dish_library_item_id,
        DishLibraryItem.deleted_at.is_(None),
    ).first()
    if not library_item:
        return jsonify({'Code': 404, 'Message': '餐品信息不存在', 'Data': None}), 404

    try:
        if request.is_json:
            payload = _build_store_payload(default_price=store_item.price)
        else:
            legacy_payload = _build_dish_from_form(require_image=False)
            payload = {
                'price': legacy_payload['price'],
                'status': store_item.status,
                'sort': store_item.sort,
            }
            library_item.name = legacy_payload['name']
            library_item.description = legacy_payload['description']
            library_item.category_ids = legacy_payload['category_ids']
            library_item.options = legacy_payload['options']
            library_item.tags = legacy_payload['tags']
            if legacy_payload['image_url']:
                library_item.image_url = legacy_payload['image_url']
            library_item.updated_at = datetime.utcnow()
    except ValueError as exc:
        return jsonify({'Code': 1, 'Message': str(exc), 'Data': None}), 400
    except Exception as exc:
        return jsonify({'Code': 500, 'Message': f'图片上传失败：{exc}', 'Data': None}), 500

    store_item.price = payload['price']
    store_item.status = payload['status']
    store_item.sort = payload['sort']
    store_item.updated_at = datetime.utcnow()
    _sync_legacy_dish(store_item, library_item)
    db.session.commit()

    return jsonify({
        'Code': 0,
        'Message': '更新成功',
        'Data': _serialize_store_item(store_item, library_item),
    })


@dish_bp.route('/store-items/<int:dish_id>', methods=['DELETE'])
@login_required('dishes')
def delete_store_item(dish_id):
    store_id = get_request_store_id()
    store_item = DishStoreItem.query.filter(
        DishStoreItem.id == dish_id,
        DishStoreItem.store_id == store_id,
        DishStoreItem.deleted_at.is_(None),
    ).first()
    if not store_item:
        return jsonify({'Code': 404, 'Message': '菜单项不存在', 'Data': None}), 404
    library_item = DishLibraryItem.query.get(store_item.dish_library_item_id)
    now = datetime.utcnow()
    store_item.deleted_at = now
    store_item.updated_at = now
    if library_item:
        _sync_legacy_dish(store_item, library_item)
    db.session.commit()
    return jsonify({'Code': 0, 'Message': '移除成功', 'Data': None})


@dish_bp.route('/store-items/<int:dish_id>/status', methods=['PATCH'])
@dish_bp.route('/<int:dish_id>/status', methods=['PATCH'])
@login_required('dishes')
def update_dish_status(dish_id):
    store_id = get_request_store_id()
    store_item = DishStoreItem.query.filter(
        DishStoreItem.id == dish_id,
        DishStoreItem.store_id == store_id,
        DishStoreItem.deleted_at.is_(None),
    ).first()
    if not store_item:
        return jsonify({'Code': 404, 'Message': '菜单项不存在', 'Data': None}), 404

    body = request.get_json(silent=True) or {}
    raw_status = body.get('Status')
    if raw_status is None:
        return jsonify({'Code': 1, 'Message': '缺少 Status 字段', 'Data': None}), 400
    try:
        status = int(raw_status)
    except (TypeError, ValueError):
        return jsonify({'Code': 1, 'Message': 'Status 必须为 0 或 1', 'Data': None}), 400
    if status not in (0, 1):
        return jsonify({'Code': 1, 'Message': 'Status 必须为 0 或 1', 'Data': None}), 400

    library_item = DishLibraryItem.query.get(store_item.dish_library_item_id)
    store_item.status = status
    store_item.updated_at = datetime.utcnow()
    if library_item:
        _sync_legacy_dish(store_item, library_item)
    db.session.commit()

    return jsonify({
        'Code': 0,
        'Message': '上架成功' if status == 1 else '下架成功',
        'Data': _serialize_store_item(store_item, library_item),
    })
