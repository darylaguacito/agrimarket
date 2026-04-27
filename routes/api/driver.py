import os, uuid
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import query, get_db
from notifs import push, send_sms

api_driver = Blueprint('api_driver', __name__, url_prefix='/api/driver')

def _driver_check(uid):
    user = query("SELECT role,is_approved FROM users WHERE id=?", (uid,), fetchone=True)
    if not user or user['role'] != 'driver' or not user['is_approved']:
        return False
    return True

@api_driver.get('/dashboard')
@jwt_required()
def dashboard():
    uid = int(get_jwt_identity())
    if not _driver_check(uid): return jsonify({'error': 'Unauthorized'}), 403
    profile = query("SELECT * FROM driver_profiles WHERE user_id=?", (uid,), fetchone=True)
    active  = query(
        "SELECT o.*,u.full_name as buyer_name,u.phone as buyer_phone,f.full_name as farmer_name "
        "FROM orders o JOIN users u ON o.buyer_id=u.id JOIN users f ON o.farmer_id=f.id "
        "WHERE o.driver_id=? AND o.status='shipped' ORDER BY o.created_at DESC", (uid,), fetchall=True) or []
    stats = query(
        "SELECT COUNT(*) as total,"
        "SUM(CASE WHEN status='delivered' THEN 1 ELSE 0 END) as delivered,"
        "SUM(CASE WHEN status='shipped' THEN 1 ELSE 0 END) as active "
        "FROM orders WHERE driver_id=?", (uid,), fetchone=True) or {}
    return jsonify({'profile': dict(profile) if profile else {}, 'active': [dict(o) for o in active],
                    'stats': dict(stats)})

@api_driver.get('/stops')
@jwt_required()
def stops():
    uid = int(get_jwt_identity())
    if not _driver_check(uid): return jsonify({'error': 'Unauthorized'}), 403
    rows = query(
        "SELECT o.id,o.shipping_address,o.contact_number,o.total_amount,o.status,"
        "o.payment_method,o.buyer_lat,o.buyer_lng,"
        "u.full_name as buyer_name,u.phone as buyer_phone,u.lat as user_lat,u.lng as user_lng "
        "FROM orders o JOIN users u ON o.buyer_id=u.id "
        "WHERE o.driver_id=? AND o.status IN ('shipped','delivered') ORDER BY o.created_at ASC",
        (uid,), fetchall=True) or []
    return jsonify([dict(r) for r in rows])

@api_driver.post('/location')
@jwt_required()
def update_location():
    uid = int(get_jwt_identity())
    if not _driver_check(uid): return jsonify({'error': 'Unauthorized'}), 403
    d = request.get_json() or {}
    lat, lng = d.get('lat'), d.get('lng')
    if lat and lng:
        query("UPDATE driver_profiles SET current_location=? WHERE user_id=?",
              (f"{lat},{lng}", uid), commit=True)
    return jsonify({'ok': True})

@api_driver.post('/deliver/<int:oid>')
@jwt_required()
def deliver(oid):
    uid   = int(get_jwt_identity())
    if not _driver_check(uid): return jsonify({'error': 'Unauthorized'}), 403
    order = query("SELECT * FROM orders WHERE id=? AND driver_id=? AND status='shipped'",
                  (oid, uid), fetchone=True)
    if not order:
        return jsonify({'error': 'Order not found'}), 404

    proof_path = None
    f = request.files.get('proof_photo')
    if f and f.filename:
        ext = f.filename.rsplit('.', 1)[-1].lower()
        if ext in ('jpg', 'jpeg', 'png', 'webp'):
            fname = f"proof_{uuid.uuid4().hex}.{ext}"
            f.save(os.path.join(current_app.config['UPLOAD_FOLDER'], fname))
            proof_path = f"uploads/{fname}"

    note = request.form.get('note', 'Delivered')
    db   = get_db()
    db.execute("UPDATE orders SET status='delivered',delivery_proof=? WHERE id=?", (proof_path, oid))
    db.execute("INSERT INTO order_tracking (order_id,status,note,updated_by) VALUES (?,'delivered',?,?)",
               (oid, note, uid))
    remaining = db.execute(
        "SELECT COUNT(*) FROM orders WHERE driver_id=? AND status='shipped'",
        (uid,)).fetchone()[0]
    if remaining == 0:
        db.execute("UPDATE driver_profiles SET availability='available' WHERE user_id=?", (uid,))
    db.commit()

    push(order['buyer_id'],  f'✅ Order #{oid} Delivered', 'Your order has been delivered!', 'delivery', oid)
    push(order['farmer_id'], f'✅ Order #{oid} Delivered', 'Driver completed delivery.', 'delivery', oid)
    buyer = query("SELECT phone,full_name FROM users WHERE id=?", (order['buyer_id'],), fetchone=True)
    if buyer and buyer.get('phone'):
        send_sms(buyer['phone'],
                 f"Hi {buyer['full_name']}, Order #{oid} has been DELIVERED. Thank you!")
    return jsonify({'ok': True})

@api_driver.post('/availability')
@jwt_required()
def set_availability():
    uid    = int(get_jwt_identity())
    if not _driver_check(uid): return jsonify({'error': 'Unauthorized'}), 403
    status = (request.get_json() or {}).get('availability', 'available')
    if status in ('available', 'busy', 'offline'):
        query("UPDATE driver_profiles SET availability=? WHERE user_id=?", (status, uid), commit=True)
    return jsonify({'ok': True})
