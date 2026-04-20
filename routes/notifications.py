from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from db import query

notif_bp = Blueprint('notif', __name__, url_prefix='/notifications')

@notif_bp.route('/')
@login_required
def index():
    notifs = query(
        "SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 50",
        (current_user.id,), fetchall=True) or []
    query("UPDATE notifications SET is_read=1 WHERE user_id=? AND is_read=0",
          (current_user.id,), commit=True)
    return render_template('shared/notifications.html', notifications=notifs)

@notif_bp.route('/count')
@login_required
def count():
    row = query("SELECT COUNT(*) as c FROM notifications WHERE user_id=? AND is_read=0",
                (current_user.id,), fetchone=True)
    return jsonify({'count': int(row['c'] or 0) if row else 0})

@notif_bp.route('/mark-all', methods=['POST'])
@login_required
def mark_all():
    query("UPDATE notifications SET is_read=1 WHERE user_id=? AND is_read=0",
          (current_user.id,), commit=True)
    return jsonify({'ok': True})
