from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import query, get_db
from notifs import push, push_many, admins, send_sms

api_orders = Blueprint('api_orders', __name__, url_prefix='/api/orders')

def _order(r):
    return dict(r) if r else None

@api_orders.get('')
@jwt_required()
def list_orders():
    uid    = int(get_jwt_identity())
    user   = query("SELECT role FROM users WHERE id=?", (uid,), fetchone=True)
    role   = user['role']
    status = request.args.get('status', '')

    if role == 'buyer':
        where, params = "WHERE o.buyer_id=?", [uid]
    elif role == 'farmer':
        where, params = "WHERE o.farmer_id=?", [uid]
    elif role == 'driver':
        where, params = "WHERE o.driver_id=?", [uid]
    elif role == 'admin':
        where, params = "WHERE 1=1", []
    else:
        return jsonify({'error': 'Unauthorized'}), 403

    if status:
        where += " AND o.status=?"; params.append(status)

    orders = query(
        f"SELECT o.*,b.full_name as buyer_name,f.full_name as farmer_name,"
        f"d.full_name as driver_name,fp.farm_name "
        f"FROM orders o JOIN users b ON o.buyer_id=b.id JOIN users f ON o.farmer_id=f.id "
        f"LEFT JOIN users d ON o.driver_id=d.id "
        f"LEFT JOIN farmer_profiles fp ON f.id=fp.user_id "
        f"{where} ORDER BY o.created_at DESC",
        params, fetchall=True) or []
    return jsonify([dict(o) for o in orders])

@api_orders.get('/<int:oid>')
@jwt_required()
def get_order(oid):
    uid  = int(get_jwt_identity())
    user = query("SELECT role FROM users WHERE id=?", (uid,), fetchone=True)
    role = user['role']

    if role == 'admin':
        cond = "WHERE o.id=?"
        params = (oid,)
    elif role == 'buyer':
        cond = "WHERE o.id=? AND o.buyer_id=?"
        params = (oid, uid)
    elif role == 'farmer':
        cond = "WHERE o.id=? AND o.farmer_id=?"
        params = (oid, uid)
    elif role == 'driver':
        cond = "WHERE o.id=? AND o.driver_id=?"
        params = (oid, uid)
    else:
        return jsonify({'error': 'Unauthorized'}), 403

    order = query(
        f"SELECT o.*,b.full_name as buyer_name,b.phone as buyer_phone,"
        f"f.full_name as farmer_name,fp.farm_name,"
        f"d.full_name as driver_name,d.phone as driver_phone "
        f"FROM orders o JOIN users b ON o.buyer_id=b.id JOIN users f ON o.farmer_id=f.id "
        f"LEFT JOIN farmer_profiles fp ON f.id=fp.user_id "
        f"LEFT JOIN users d ON o.driver_id=d.id {cond}", params, fetchone=True)
    if not order:
        return jsonify({'error': 'Order not found'}), 404

    items    = query("SELECT oi.*,p.name,p.image_path,p.unit FROM order_items oi "
                     "JOIN products p ON oi.product_id=p.id WHERE oi.order_id=?", (oid,), fetchall=True) or []
    tracking = query("SELECT * FROM order_tracking WHERE order_id=? ORDER BY created_at ASC", (oid,), fetchall=True) or []
    return jsonify({'order': dict(order), 'items': [dict(i) for i in items],
                    'tracking': [dict(t) for t in tracking]})

@api_orders.post('/checkout')
@jwt_required()
def checkout():
    uid  = int(get_jwt_identity())
    user = query("SELECT * FROM users WHERE id=?", (uid,), fetchone=True)
    d    = request.get_json() or {}

    address = d.get('shipping_address', '').strip()
    contact = d.get('contact_number', '').strip()
    payment = d.get('payment_method', 'cod')
    notes   = d.get('notes', '')

    if not address or not contact:
        return jsonify({'error': 'Address and contact are required'}), 400

    items = query(
        "SELECT ci.*,p.name,p.price,p.unit,p.quantity as stock,p.farmer_id "
        "FROM cart_items ci JOIN products p ON ci.product_id=p.id WHERE ci.user_id=?",
        (uid,), fetchall=True) or []
    if not items:
        return jsonify({'error': 'Cart is empty'}), 400

    db = get_db()
    order_ids = []
    try:
        by_farmer = {}
        for i in items:
            by_farmer.setdefault(i['farmer_id'], []).append(i)

        for fid, fitems in by_farmer.items():
            total = sum(float(i['price']) * i['quantity'] for i in fitems)
            cur = db.execute(
                "INSERT INTO orders (buyer_id,farmer_id,total_amount,payment_method,"
                "shipping_address,contact_number,notes,buyer_lat,buyer_lng) VALUES (?,?,?,?,?,?,?,?,?)",
                (uid, fid, total, payment, address, contact, notes,
                 d.get('lat'), d.get('lng')))
            oid = cur.lastrowid
            order_ids.append(oid)
            for i in fitems:
                db.execute("INSERT INTO order_items (order_id,product_id,quantity,price) VALUES (?,?,?,?)",
                           (oid, i['product_id'], i['quantity'], i['price']))
                db.execute("UPDATE products SET quantity=quantity-? WHERE id=?",
                           (i['quantity'], i['product_id']))
                new_stock = db.execute("SELECT quantity,name,unit,farmer_id FROM products WHERE id=?",
                                       (i['product_id'],)).fetchone()
                if new_stock and new_stock[0] <= 10:
                    push(new_stock[3], '⚠️ Low Stock Alert',
                         f"{new_stock[1]} has only {new_stock[0]} {new_stock[2]} left!", 'info')
            db.execute("INSERT INTO order_tracking (order_id,status,note,updated_by) VALUES (?,'pending','Order placed',?)",
                       (oid, uid))
            db.commit()
            push(fid, '🛒 New Order!', f"New order #{oid} for ₱{total:,.2f}.", 'order', oid)
            push(uid, '✅ Order Placed', f"Order #{oid} confirmed!", 'order', oid)
            push_many(admins(), '📦 New Order', f"Order #{oid} placed.", 'order', oid)

        db.execute("DELETE FROM cart_items WHERE user_id=?", (uid,))
        db.commit()
        return jsonify({'message': 'Order placed', 'order_ids': order_ids}), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500

@api_orders.put('/<int:oid>/status')
@jwt_required()
def update_status(oid):
    uid  = int(get_jwt_identity())
    user = query("SELECT role FROM users WHERE id=?", (uid,), fetchone=True)
    role = user['role']
    d    = request.get_json() or {}
    new_status = d.get('status')
    note       = d.get('note', '')
    driver_id  = d.get('driver_id')

    if role == 'farmer':
        order = query("SELECT * FROM orders WHERE id=? AND farmer_id=?", (oid, uid), fetchone=True)
        allowed = ('confirmed', 'packed', 'shipped', 'cancelled')
    elif role == 'admin':
        order = query("SELECT * FROM orders WHERE id=?", (oid,), fetchone=True)
        allowed = ('confirmed', 'packed', 'shipped', 'delivered', 'cancelled')
    else:
        return jsonify({'error': 'Unauthorized'}), 403

    if not order:
        return jsonify({'error': 'Order not found'}), 404
    if new_status not in allowed:
        return jsonify({'error': f'Invalid status. Allowed: {allowed}'}), 400

    db = get_db()
    db.execute("UPDATE orders SET status=? WHERE id=?", (new_status, oid))
    if driver_id:
        db.execute("UPDATE orders SET driver_id=? WHERE id=?", (driver_id, oid))
        db.execute("UPDATE driver_profiles SET availability='busy' WHERE user_id=?", (driver_id,))
        push(int(driver_id), '🚚 New Delivery', f"Assigned to Order #{oid}.", 'delivery', oid)
    db.execute("INSERT INTO order_tracking (order_id,status,note,updated_by) VALUES (?,?,?,?)",
               (oid, new_status, note, uid))
    db.commit()

    push(order['buyer_id'], f'📦 Order #{oid}', f"Status: {new_status.upper()}", 'order', oid)

    buyer = query("SELECT phone,full_name FROM users WHERE id=?", (order['buyer_id'],), fetchone=True)
    sms_map = {
        'confirmed': f"Hi {buyer['full_name']}, Order #{oid} CONFIRMED. Total: ₱{order['total_amount']:,.2f}.",
        'packed':    f"Hi {buyer['full_name']}, Order #{oid} is PACKED and ready for pickup.",
        'cancelled': f"Hi {buyer['full_name']}, Order #{oid} has been CANCELLED by the seller.",
    }
    if new_status in sms_map and buyer and buyer.get('phone'):
        send_sms(buyer['phone'], sms_map[new_status])

    return jsonify({'message': 'Order updated'})

@api_orders.post('/<int:oid>/cancel')
@jwt_required()
def cancel_order(oid):
    uid   = int(get_jwt_identity())
    order = query("SELECT o.*,u.phone as farmer_phone,u.full_name as farmer_name "
                  "FROM orders o JOIN users u ON o.farmer_id=u.id "
                  "WHERE o.id=? AND o.buyer_id=?", (oid, uid), fetchone=True)
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    if order['status'] not in ('pending', 'confirmed'):
        return jsonify({'error': 'Cannot cancel this order'}), 400

    reason = (request.get_json() or {}).get('reason', 'Cancelled by buyer')
    db = get_db()
    db.execute("UPDATE orders SET status='cancelled',cancelled_reason=? WHERE id=?", (reason, oid))
    db.execute("INSERT INTO order_tracking (order_id,status,note,updated_by) VALUES (?,'cancelled',?,?)",
               (oid, f'Cancelled by buyer: {reason}', uid))
    items = db.execute("SELECT product_id,quantity FROM order_items WHERE order_id=?", (oid,)).fetchall()
    for item in items:
        db.execute("UPDATE products SET quantity=quantity+? WHERE id=?", (item[1], item[0]))
    db.commit()

    push(order['farmer_id'], f'❌ Order #{oid} Cancelled', f"Reason: {reason}", 'order', oid)
    if order.get('farmer_phone'):
        send_sms(order['farmer_phone'],
                 f"Hi {order['farmer_name']}, Order #{oid} CANCELLED by buyer. Reason: {reason}.")
    return jsonify({'message': 'Order cancelled'})

@api_orders.post('/<int:oid>/review')
@jwt_required()
def submit_review(oid):
    uid   = int(get_jwt_identity())
    order = query("SELECT * FROM orders WHERE id=? AND buyer_id=? AND status='delivered'",
                  (oid, uid), fetchone=True)
    if not order:
        return jsonify({'error': 'Cannot review this order'}), 400
    if query("SELECT id FROM reviews WHERE order_id=? AND buyer_id=?", (oid, uid), fetchone=True):
        return jsonify({'error': 'Already reviewed'}), 409

    d      = request.get_json() or {}
    rating = int(d.get('rating', 5))
    comment = d.get('comment', '').strip()
    db = get_db()
    db.execute("INSERT INTO reviews (order_id,buyer_id,farmer_id,rating,comment) VALUES (?,?,?,?,?)",
               (oid, uid, order['farmer_id'], rating, comment))
    db.execute("UPDATE farmer_profiles SET "
               "rating=(SELECT AVG(rating) FROM reviews WHERE farmer_id=?),"
               "rating_count=(SELECT COUNT(*) FROM reviews WHERE farmer_id=?) WHERE user_id=?",
               (order['farmer_id'], order['farmer_id'], order['farmer_id']))
    db.commit()
    return jsonify({'message': 'Review submitted'})
