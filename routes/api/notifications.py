from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import query

api_notifs = Blueprint('api_notifs', __name__, url_prefix='/api/notifications')

@api_notifs.get('')
@jwt_required()
def list_notifs():
    uid   = int(get_jwt_identity())
    notifs = query(
        "SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 50",
        (uid,), fetchall=True) or []
    query("UPDATE notifications SET is_read=1 WHERE user_id=?", (uid,), commit=True)
    return jsonify([dict(n) for n in notifs])

@api_notifs.get('/count')
@jwt_required()
def count():
    uid = int(get_jwt_identity())
    row = query("SELECT COUNT(*) as c FROM notifications WHERE user_id=? AND is_read=0",
                (uid,), fetchone=True)
    return jsonify({'count': int(row['c'] or 0)})

@api_notifs.post('/mark-all')
@jwt_required()
def mark_all():
    uid = int(get_jwt_identity())
    query("UPDATE notifications SET is_read=1 WHERE user_id=?", (uid,), commit=True)
    return jsonify({'ok': True})
