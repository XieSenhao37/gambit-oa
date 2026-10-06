"""Temporary OA-only administrator; SMS remains a separate, selectable login mode."""
import hmac
from types import SimpleNamespace
from flask import abort, current_app

# User-requested temporary credential. Never expose it through status or frontend assets.
ADMIN_USERNAME = 'admin'
ADMIN_ID = 0
ADMIN_SESSION_VERSION = 0


def login_mode():
    mode = current_app.config.get('OA_LOGIN_MODE', 'password')
    if mode not in ('password', 'sms'):
        abort(503, description='登录方式配置无效，请联系管理员')
    return mode


def verify_admin(username, password):
    if not isinstance(username, str) or not isinstance(password, str):
        return False
    configured_password = current_app.config.get("OA_ADMIN_PASSWORD", "")
    if not configured_password:
        return False
    # compare_digest requires byte strings for arbitrary Unicode input.
    return (hmac.compare_digest(username.encode(), ADMIN_USERNAME.encode())
            & hmac.compare_digest(password.encode(), configured_password.encode()))


def temporary_admin():
    # ID 0 is reserved for this OA identity, not a miniapp user or staff grant.
    account = SimpleNamespace(user_id=ADMIN_ID, version=ADMIN_SESSION_VERSION,
                              headquarters=True, enabled=True)
    user = SimpleNamespace(id=ADMIN_ID, nick_name='超级管理员（admin）')
    return account, user, {}
