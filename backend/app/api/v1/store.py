from flask import Blueprint, jsonify, g

from app.middlewares.auth import login_required
from app.models import Store

store_bp = Blueprint('store', __name__)


def _serialize_store(store):
    return {
        'Id': store.id,
        'Code': store.code,
        'Name': store.name,
        'Status': store.status,
        'Sort': store.sort,
        'Address': store.address,
    }


@store_bp.route('/list', methods=['GET'])
@login_required('session')
def list_stores():
    from app.security.policy import available_stores
    stores = available_stores(g.staff, g.grants)
    return jsonify(Code=0, Message='success', Data={'Items': [_serialize_store(s) for s in stores]})
