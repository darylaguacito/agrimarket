from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import query, get_db
from notifs import push

api_messages = Blueprint('api_messages', __name__, url_prefix='/api/messages')

def _can_access(uid, oid):
    return query("SELECT * FROM orders WHERE id=? AND (buyer_id=? OR farmer_id=?)",
                 (oid, uid, uid), fetchone=True)

@api_messages.get('/inbox')
@jwt_required()
def inbox():
    uid = int(get_jwt_identity())
    convos = query("""
        SELECT o.id as order_id, o.status, o.total_amount,
            CASE WHEN o.buyer_id=:uid THEN f.full_name ELSE b.full_name END as other_name,
            CASE WHEN o.buyer_id=:uid THEN o.farmer_id ELSE o.buyer_id END as other_id,
            (SELECT body FROM messages WHERE order_id=o.id ORDER BY created_at DESC LIMIT 1) as last_msg,
            (SELECT created_at FROM messages WHERE order_id=o.id ORDER BY created_at DESC LIMIT 1) as last_at,
            (SELECT COUNT(*) FROM messages WHERE order_id=o.id AND receiver_id=:uid AND is_read=0) as unread
        FROM orders o
        JOIN users b ON o.buyer_id=b.id
        JOIN users f ON o.farmer_id=f.id
        WHERE (o.buyer_id=:uid OR o.farmer_id=:uid)
          AND EXISTS (SELECT 1 FROM messages WHERE order_id=o.id)
        ORDER BY last_at DESC
    """, {'uid': uid}, fetchall=True) or []
    return jsonify([dict(c) for c in convos])

@api_messages.get('/order/<int:oid>')
@jwt_required()
def thread(oid):
    uid   = int(get_jwt_identity())
    order = _can_access(uid, oid)
    if not order:
        return jsonify({'error': 'Not found'}), 404
    query("UPDATE messages SET is_read=1 WHERE order_id=? AND receiver_id=?",
          (oid, uid), commit=True)
    msgs = query(
        "SELECT m.*,u.full_name as sender_name FROM messages m "
        "JOIN users u ON m.sender_id=u.id WHERE m.order_id=? ORDER BY m.created_at ASC",
        (oid,), fetchall=True) or []
    other_id = order['farmer_id'] if uid == order['buyer_id'] else order['buyer_id']
    other    = query("SELECT id,full_name,role FROM users WHERE id=?", (other_id,), fetchone=True)
    return jsonify({'messages': [dict(m) for m in msgs], 'other': dict(other) if other else {},
                    'order': dict(order)})

@api_messages.post('/order/<int:oid>')
@jwt_required()
def send(oid):
    uid   = int(get_jwt_identity())
    order = _can_access(uid, oid)
    if not order:
        return jsonify({'error': 'Not found'}), 404
    body = (request.get_json() or {}).get('body', '').strip()
    if not body:
        return jsonify({'error': 'Message cannot be empty'}), 400
    if len(body) > 1000:
        return jsonify({'error': 'Message too long'}), 400
    other_id = order['farmer_id'] if uid == order['buyer_id'] else order['buyer_id']
    db = get_db()
    cur = db.execute("INSERT INTO messages (order_id,sender_id,receiver_id,body) VALUES (?,?,?,?)",
                     (oid, uid, other_id, body))
    db.commit()
    me = query("SELECT full_name FROM users WHERE id=?", (uid,), fetchone=True)
    push(other_id, f'💬 New message from {me["full_name"]}',
         body[:80] + ('…' if len(body) > 80 else ''), 'info', oid)
    msg = query("SELECT m.*,u.full_name as sender_name FROM messages m "
                "JOIN users u ON m.sender_id=u.id WHERE m.id=?", (cur.lastrowid,), fetchone=True)
    return jsonify(dict(msg)), 201

@api_messages.get('/order/<int:oid>/poll')
@jwt_required()
def poll(oid):
    uid   = int(get_jwt_identity())
    if not _can_access(uid, oid):
        return jsonify([])
    after = request.args.get('after', 0, type=int)
    query("UPDATE messages SET is_read=1 WHERE order_id=? AND receiver_id=?",
          (oid, uid), commit=True)
    msgs = query(
        "SELECT m.id,m.body,m.sender_id,m.created_at,u.full_name as sender_name "
        "FROM messages m JOIN users u ON m.sender_id=u.id "
        "WHERE m.order_id=? AND m.id>? ORDER BY m.created_at ASC",
        (oid, after), fetchall=True) or []
    return jsonify([dict(m) for m in msgs])

@api_messages.get('/unread')
@jwt_required()
def unread():
    uid = int(get_jwt_identity())
    row = query("SELECT COUNT(*) as c FROM messages WHERE receiver_id=? AND is_read=0",
                (uid,), fetchone=True)
    return jsonify({'count': int(row['c'] or 0)})
