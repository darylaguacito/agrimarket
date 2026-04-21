from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from db import query, get_db
from notifs import push

msg_bp = Blueprint('msg', __name__, url_prefix='/messages')


def _can_access_order(oid):
    """Return the order if current user is buyer or farmer of it, else None."""
    return query(
        "SELECT * FROM orders WHERE id=? AND (buyer_id=? OR farmer_id=?)",
        (oid, current_user.id, current_user.id), fetchone=True)


@msg_bp.route('/')
@login_required
def inbox():
    """List all conversations (one per order) for the current user."""
    convos = query("""
        SELECT
            o.id as order_id,
            o.status,
            o.total_amount,
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
    """, {'uid': current_user.id}, fetchall=True) or []
    return render_template('shared/inbox.html', convos=convos)


@msg_bp.route('/order/<int:oid>', methods=['GET', 'POST'])
@login_required
def thread(oid):
    order = _can_access_order(oid)
    if not order:
        flash('Conversation not found.', 'error')
        return redirect(url_for('msg.inbox'))

    # Determine the other party
    other_id = order['farmer_id'] if current_user.id == order['buyer_id'] else order['buyer_id']
    other = query("SELECT id, full_name, role FROM users WHERE id=?", (other_id,), fetchone=True)

    if request.method == 'POST':
        body = request.form.get('body', '').strip()
        if not body:
            flash('Message cannot be empty.', 'error')
            return redirect(url_for('msg.thread', oid=oid))
        if len(body) > 1000:
            flash('Message too long (max 1000 characters).', 'error')
            return redirect(url_for('msg.thread', oid=oid))
        db = get_db()
        db.execute(
            "INSERT INTO messages (order_id, sender_id, receiver_id, body) VALUES (?,?,?,?)",
            (oid, current_user.id, other_id, body))
        db.commit()
        push(other_id, f'💬 New message from {current_user.full_name}',
             body[:80] + ('…' if len(body) > 80 else ''), 'info', oid)
        return redirect(url_for('msg.thread', oid=oid))

    # Mark incoming messages as read
    query("UPDATE messages SET is_read=1 WHERE order_id=? AND receiver_id=?",
          (oid, current_user.id), commit=True)

    msgs = query(
        "SELECT m.*, u.full_name as sender_name FROM messages m "
        "JOIN users u ON m.sender_id=u.id WHERE m.order_id=? ORDER BY m.created_at ASC",
        (oid,), fetchall=True) or []

    return render_template('shared/thread.html', order=order, other=other, msgs=msgs)


@msg_bp.route('/api/unread')
@login_required
def unread_count():
    row = query("SELECT COUNT(*) as c FROM messages WHERE receiver_id=? AND is_read=0",
                (current_user.id,), fetchone=True)
    return jsonify({'count': int(row['c'] or 0)})


@msg_bp.route('/api/order/<int:oid>/poll')
@login_required
def poll(oid):
    """Return new messages after a given id for live polling."""
    after = request.args.get('after', 0, type=int)
    order = _can_access_order(oid)
    if not order:
        return jsonify([])
    query("UPDATE messages SET is_read=1 WHERE order_id=? AND receiver_id=?",
          (oid, current_user.id), commit=True)
    msgs = query(
        "SELECT m.id, m.body, m.sender_id, m.created_at, u.full_name as sender_name "
        "FROM messages m JOIN users u ON m.sender_id=u.id "
        "WHERE m.order_id=? AND m.id>? ORDER BY m.created_at ASC",
        (oid, after), fetchall=True) or []
    return jsonify([dict(m) for m in msgs])
