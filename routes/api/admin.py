from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import query, get_db
from notifs import push

api_admin = Blueprint('api_admin', __name__, url_prefix='/api/admin')

def _admin_check(uid):
    user = query("SELECT role FROM users WHERE id=?", (uid,), fetchone=True)
    return user and user['role'] == 'admin'

@api_admin.get('/dashboard')
@jwt_required()
def dashboard():
    uid = int(get_jwt_identity())
    if not _admin_check(uid): return jsonify({'error': 'Unauthorized'}), 403
    stats = {
        'users':    query("SELECT COUNT(*) as c FROM users WHERE role!='admin'", fetchone=True)['c'],
        'farmers':  query("SELECT COUNT(*) as c FROM users WHERE role='farmer' AND is_approved=1", fetchone=True)['c'],
        'buyers':   query("SELECT COUNT(*) as c FROM users WHERE role='buyer'", fetchone=True)['c'],
        'drivers':  query("SELECT COUNT(*) as c FROM users WHERE role='driver' AND is_approved=1", fetchone=True)['c'],
        'products': query("SELECT COUNT(*) as c FROM products WHERE status='active'", fetchone=True)['c'],
        'orders':   query("SELECT COUNT(*) as c FROM orders", fetchone=True)['c'],
        'pending':  query("SELECT COUNT(*) as c FROM users WHERE is_approved=0 AND role!='buyer'", fetchone=True)['c'],
        'revenue':  query("SELECT COALESCE(SUM(total_amount),0) as r FROM orders WHERE status='delivered'", fetchone=True)['r'],
    }
    recent = query(
        "SELECT o.*,b.full_name as buyer_name,f.full_name as farmer_name "
        "FROM orders o JOIN users b ON o.buyer_id=b.id JOIN users f ON o.farmer_id=f.id "
        "ORDER BY o.created_at DESC LIMIT 8", fetchall=True) or []
    pending_users = query(
        "SELECT * FROM users WHERE is_approved=0 AND role!='buyer' ORDER BY created_at DESC",
        fetchall=True) or []
    return jsonify({'stats': stats, 'recent_orders': [dict(o) for o in recent],
                    'pending_users': [dict(u) for u in pending_users]})

@api_admin.get('/users')
@jwt_required()
def users():
    uid = int(get_jwt_identity())
    if not _admin_check(uid): return jsonify({'error': 'Unauthorized'}), 403
    role   = request.args.get('role', '')
    search = request.args.get('q', '').strip()
    where, params = [], []
    if role:   where.append("role=?");                    params.append(role)
    if search: where.append("(full_name LIKE ? OR email LIKE ?)"); params += [f'%{search}%', f'%{search}%']
    w = ('WHERE ' + ' AND '.join(where)) if where else ''
    rows = query(f"SELECT * FROM users {w} ORDER BY created_at DESC", params, fetchall=True) or []
    # Don't expose password hashes
    safe = [{k: v for k, v in dict(r).items() if k != 'password_hash'} for r in rows]
    return jsonify(safe)

@api_admin.post('/users/<int:target_uid>/approve')
@jwt_required()
def approve_user(target_uid):
    uid = int(get_jwt_identity())
    if not _admin_check(uid): return jsonify({'error': 'Unauthorized'}), 403
    query("UPDATE users SET is_approved=1 WHERE id=?", (target_uid,), commit=True)
    push(target_uid, '✅ Account Approved', 'Your account has been approved!', 'info')
    return jsonify({'message': 'User approved'})

@api_admin.post('/users/<int:target_uid>/toggle')
@jwt_required()
def toggle_user(target_uid):
    uid = int(get_jwt_identity())
    if not _admin_check(uid): return jsonify({'error': 'Unauthorized'}), 403
    if target_uid == uid: return jsonify({'error': 'Cannot deactivate yourself'}), 400
    user = query("SELECT is_active FROM users WHERE id=?", (target_uid,), fetchone=True)
    query("UPDATE users SET is_active=? WHERE id=?", (0 if user['is_active'] else 1, target_uid), commit=True)
    return jsonify({'message': 'User status updated'})

@api_admin.delete('/users/<int:target_uid>')
@jwt_required()
def delete_user(target_uid):
    uid = int(get_jwt_identity())
    if not _admin_check(uid): return jsonify({'error': 'Unauthorized'}), 403
    if target_uid == uid: return jsonify({'error': 'Cannot delete yourself'}), 400
    query("DELETE FROM users WHERE id=?", (target_uid,), commit=True)
    return jsonify({'message': 'User deleted'})

@api_admin.post('/orders/<int:oid>/assign-driver')
@jwt_required()
def assign_driver(oid):
    uid = int(get_jwt_identity())
    if not _admin_check(uid): return jsonify({'error': 'Unauthorized'}), 403
    driver_id = (request.get_json() or {}).get('driver_id')
    if not driver_id: return jsonify({'error': 'driver_id required'}), 400
    db = get_db()
    db.execute("UPDATE orders SET driver_id=?,status='shipped' WHERE id=?", (driver_id, oid))
    db.execute("UPDATE driver_profiles SET availability='busy' WHERE user_id=?", (driver_id,))
    db.execute("INSERT INTO order_tracking (order_id,status,note,updated_by) VALUES (?,'shipped','Driver assigned',?)",
               (oid, uid))
    db.commit()
    order = query("SELECT buyer_id FROM orders WHERE id=?", (oid,), fetchone=True)
    push(int(driver_id), '🚚 New Delivery Assigned', f"Order #{oid} assigned.", 'delivery', oid)
    push(order['buyer_id'], f'📦 Order #{oid} Shipped', 'A driver has been assigned.', 'order', oid)
    return jsonify({'message': 'Driver assigned'})

@api_admin.get('/analytics')
@jwt_required()
def analytics():
    uid = int(get_jwt_identity())
    if not _admin_check(uid): return jsonify({'error': 'Unauthorized'}), 403
    monthly = query(
        "SELECT strftime('%b %Y',created_at) as month,strftime('%Y-%m',created_at) as key_,"
        "COUNT(*) as orders,COALESCE(SUM(total_amount),0) as revenue "
        "FROM orders WHERE status='delivered' AND created_at>=datetime('now','-6 months') "
        "GROUP BY key_,month ORDER BY key_ ASC", fetchall=True) or []
    top_products = query(
        "SELECT p.name,COALESCE(SUM(oi.quantity),0) as sold,"
        "COALESCE(SUM(oi.quantity*oi.price),0) as revenue "
        "FROM products p LEFT JOIN order_items oi ON p.id=oi.product_id "
        "LEFT JOIN orders o ON oi.order_id=o.id AND o.status='delivered' "
        "GROUP BY p.id ORDER BY sold DESC LIMIT 8", fetchall=True) or []
    return jsonify({'monthly': [dict(m) for m in monthly],
                    'top_products': [dict(p) for p in top_products]})
