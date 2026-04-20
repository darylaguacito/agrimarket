import os, uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from db import query, get_db
from notifs import push

driver_bp = Blueprint('driver', __name__, url_prefix='/driver')

def driver_required(f):
    from functools import wraps
    @wraps(f)
    @login_required
    def decorated(*a, **kw):
        if current_user.role != 'driver':
            flash('Driver access required.', 'error')
            return redirect(url_for('auth.login'))
        if not current_user.is_approved:
            flash('Your account is pending approval.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*a, **kw)
    return decorated

@driver_bp.route('/route')
@driver_required
def route_map():
    stops = query(
        "SELECT o.id, o.shipping_address, o.contact_number, o.total_amount, o.status, "
        "o.payment_method, o.buyer_lat, o.buyer_lng, "
        "u.full_name as buyer_name, u.phone as buyer_phone, u.lat as user_lat, u.lng as user_lng "
        "FROM orders o JOIN users u ON o.buyer_id=u.id "
        "WHERE o.driver_id=? AND o.status='shipped' ORDER BY o.created_at ASC",
        (current_user.id,), fetchall=True) or []
    return render_template('driver/route_map.html', stops=stops)

@driver_bp.route('/api/stops')
@driver_required
def api_stops():
    stops = query(
        "SELECT o.id, o.shipping_address, o.contact_number, o.total_amount, o.status, "
        "o.payment_method, o.buyer_lat, o.buyer_lng, "
        "u.full_name as buyer_name, u.phone as buyer_phone, u.lat as user_lat, u.lng as user_lng "
        "FROM orders o JOIN users u ON o.buyer_id=u.id "
        "WHERE o.driver_id=? AND o.status IN ('shipped','delivered') ORDER BY o.created_at ASC",
        (current_user.id,), fetchall=True) or []
    return jsonify([dict(s) for s in stops])

@driver_bp.route('/api/location', methods=['POST'])
@driver_required
def api_location():
    data = request.get_json() or {}
    lat, lng = data.get('lat'), data.get('lng')
    if lat and lng:
        query("UPDATE driver_profiles SET current_location=? WHERE user_id=?",
              (f"{lat},{lng}", current_user.id), commit=True)
    return jsonify({'ok': True})

@driver_bp.route('/api/stops/<int:oid>/deliver', methods=['POST'])
@driver_required
def api_deliver(oid):
    order = query("SELECT * FROM orders WHERE id=? AND driver_id=? AND status='shipped'",
                  (oid, current_user.id), fetchone=True)
    if not order:
        return jsonify({'error': 'Not found'}), 404
    note = (request.get_json(silent=True) or {}).get('note', 'Delivered')
    db = get_db()
    db.execute("UPDATE orders SET status='delivered' WHERE id=?", (oid,))
    db.execute("INSERT INTO order_tracking (order_id,status,note,updated_by) VALUES (?,'delivered',?,?)",
               (oid, note, current_user.id))
    remaining = db.execute(
        "SELECT COUNT(*) FROM orders WHERE driver_id=? AND status='shipped'",
        (current_user.id,)).fetchone()[0]
    if remaining == 0:
        db.execute("UPDATE driver_profiles SET availability='available' WHERE user_id=?", (current_user.id,))
    db.commit()
    push(order['buyer_id'],  f'✅ Order #{oid} Delivered', 'Your order has been delivered!', 'delivery', oid)
    push(order['farmer_id'], f'✅ Order #{oid} Delivered', 'Driver completed delivery.', 'delivery', oid)
    return jsonify({'ok': True})

@driver_bp.route('/dashboard')
@driver_required
def dashboard():
    did = current_user.id
    profile = query("SELECT * FROM driver_profiles WHERE user_id=?", (did,), fetchone=True)
    active = query(
        "SELECT o.*,u.full_name as buyer_name,u.phone as buyer_phone,f.full_name as farmer_name "
        "FROM orders o JOIN users u ON o.buyer_id=u.id JOIN users f ON o.farmer_id=f.id "
        "WHERE o.driver_id=? AND o.status='shipped' ORDER BY o.created_at DESC",
        (did,), fetchall=True) or []
    stats = query(
        "SELECT COUNT(*) as total, "
        "SUM(CASE WHEN status='delivered' THEN 1 ELSE 0 END) as delivered, "
        "SUM(CASE WHEN status='shipped' THEN 1 ELSE 0 END) as active "
        "FROM orders WHERE driver_id=?", (did,), fetchone=True) or {}
    return render_template('driver/dashboard.html', profile=profile, active=active, stats=stats)

@driver_bp.route('/deliveries')
@driver_required
def deliveries():
    status = request.args.get('status', '')
    where, params = "WHERE o.driver_id=?", [current_user.id]
    if status:
        where += " AND o.status=?"; params.append(status)
    orders = query(
        f"SELECT o.*,u.full_name as buyer_name,u.phone as buyer_phone "
        f"FROM orders o JOIN users u ON o.buyer_id=u.id {where} ORDER BY o.created_at DESC",
        params, fetchall=True) or []
    return render_template('driver/deliveries.html', orders=orders, status_filter=status)

@driver_bp.route('/deliveries/<int:oid>/navigate')
@driver_required
def navigate(oid):
    order = query(
        "SELECT o.*, u.full_name as buyer_name, u.phone as buyer_phone, "
        "o.buyer_lat, o.buyer_lng, u.lat as user_lat, u.lng as user_lng "
        "FROM orders o JOIN users u ON o.buyer_id=u.id "
        "WHERE o.id=? AND o.driver_id=?", (oid, current_user.id), fetchone=True)
    if not order:
        flash('Delivery not found.', 'error')
        return redirect(url_for('driver.deliveries'))
    dest_lat = order.get('buyer_lat') or order.get('user_lat')
    dest_lng = order.get('buyer_lng') or order.get('user_lng')
    return render_template('driver/navigate.html', order=order, dest_lat=dest_lat, dest_lng=dest_lng)

@driver_bp.route('/deliveries/<int:oid>')
@driver_required
def delivery_detail(oid):
    order = query(
        "SELECT o.*,u.full_name as buyer_name,u.phone as buyer_phone,f.full_name as farmer_name "
        "FROM orders o JOIN users u ON o.buyer_id=u.id JOIN users f ON o.farmer_id=f.id "
        "WHERE o.id=? AND o.driver_id=?", (oid, current_user.id), fetchone=True)
    if not order:
        flash('Delivery not found.', 'error')
        return redirect(url_for('driver.deliveries'))
    items    = query("SELECT oi.*,p.name FROM order_items oi "
                     "JOIN products p ON oi.product_id=p.id WHERE oi.order_id=?", (oid,), fetchall=True) or []
    tracking = query("SELECT * FROM order_tracking WHERE order_id=? ORDER BY created_at ASC", (oid,), fetchall=True) or []
    return render_template('driver/delivery_detail.html', order=order, items=items, tracking=tracking)

@driver_bp.route('/deliveries/<int:oid>/update', methods=['POST'])
@driver_required
def update_delivery(oid):
    order = query("SELECT * FROM orders WHERE id=? AND driver_id=?", (oid, current_user.id), fetchone=True)
    if not order:
        flash('Not found.', 'error')
        return redirect(url_for('driver.deliveries'))
    new_status = request.form.get('status')
    if new_status not in ('shipped', 'delivered'):
        flash('Invalid status.', 'error')
        return redirect(url_for('driver.delivery_detail', oid=oid))
    db = get_db()
    db.execute("UPDATE orders SET status=? WHERE id=?", (new_status, oid))
    db.execute("INSERT INTO order_tracking (order_id,status,note,updated_by) VALUES (?,?,?,?)",
               (oid, new_status, request.form.get('note', ''), current_user.id))
    if new_status == 'delivered':
        db.execute("UPDATE driver_profiles SET availability='available' WHERE user_id=?", (current_user.id,))
    db.commit()
    push(order['buyer_id'],  f'🚚 Order #{oid}', f"Status: {new_status.upper()}", 'delivery', oid)
    push(order['farmer_id'], f'📦 Order #{oid}', f"Driver updated: {new_status.upper()}", 'delivery', oid)
    flash('Delivery updated.', 'success')
    return redirect(url_for('driver.delivery_detail', oid=oid))

@driver_bp.route('/availability', methods=['POST'])
@driver_required
def set_availability():
    status = request.form.get('availability', 'available')
    if status in ('available', 'busy', 'offline'):
        query("UPDATE driver_profiles SET availability=? WHERE user_id=?", (status, current_user.id), commit=True)
    return redirect(url_for('driver.dashboard'))

@driver_bp.route('/profile', methods=['GET', 'POST'])
@driver_required
def profile():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_profile':
            phone = request.form.get('phone', '').strip()
            avail = request.form.get('availability', 'available')
            query("UPDATE users SET phone=? WHERE id=?", (phone, current_user.id), commit=True)
            query("UPDATE driver_profiles SET availability=? WHERE user_id=?", (avail, current_user.id), commit=True)
            flash('Profile updated.', 'success')
        elif action == 'change_password':
            import bcrypt
            cur_pw   = request.form.get('current_password', '')
            new_pw   = request.form.get('new_password', '')
            user_row = query("SELECT password_hash FROM users WHERE id=?", (current_user.id,), fetchone=True)
            if not bcrypt.checkpw(cur_pw.encode(), user_row['password_hash'].encode()):
                flash('Current password incorrect.', 'error')
            elif len(new_pw) < 6:
                flash('New password must be at least 6 characters.', 'error')
            else:
                hashed = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
                query("UPDATE users SET password_hash=? WHERE id=?", (hashed, current_user.id), commit=True)
                flash('Password changed.', 'success')
        return redirect(url_for('driver.profile'))
    user    = query("SELECT * FROM users WHERE id=?", (current_user.id,), fetchone=True)
    profile = query("SELECT * FROM driver_profiles WHERE user_id=?", (current_user.id,), fetchone=True)
    return render_template('driver/profile.html', user=user, profile=profile)
