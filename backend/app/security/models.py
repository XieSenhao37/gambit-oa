from datetime import datetime
from app import db

class StaffAccount(db.Model):
    __tablename__ = 'staff_accounts'
    user_id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    phone_cipher = db.Column(db.String(100), nullable=False, unique=True)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    headquarters = db.Column(db.Boolean, nullable=False, default=False)
    phone_verified_at = db.Column(db.DateTime)
    version = db.Column(db.Integer, nullable=False, default=1)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class StaffGrant(db.Model):
    __tablename__ = 'staff_store_grants'
    user_id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    store_id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(20), nullable=False)

class RolePage(db.Model):
    __tablename__ = 'staff_role_pages'
    role = db.Column(db.String(20), primary_key=True)
    page_id = db.Column(db.String(80), primary_key=True)
    allowed = db.Column(db.Boolean, nullable=False)

class LoginChallenge(db.Model):
    __tablename__ = 'oa_login_challenges'
    id = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    account_version = db.Column(db.Integer, nullable=False)
    code_digest = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    consumed = db.Column(db.Boolean, nullable=False, default=False)
    sent = db.Column(db.Boolean, nullable=False, default=False)

class LoginThrottle(db.Model):
    __tablename__ = 'oa_login_throttles'
    key = db.Column(db.String(64), primary_key=True)
    window_start = db.Column(db.DateTime, nullable=False)
    count = db.Column(db.Integer, nullable=False)

class OASession(db.Model):
    __tablename__ = 'oa_sessions'
    token_digest = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    account_version = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked = db.Column(db.Boolean, nullable=False, default=False)

class AccessAudit(db.Model):
    __tablename__ = 'oa_access_audits'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    actor_id = db.Column(db.Integer, nullable=False)
    store_id = db.Column(db.Integer)
    action = db.Column(db.String(160), nullable=False)
    target = db.Column(db.String(255))
    detail = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
