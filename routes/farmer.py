import os, uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from db import query, get_db
from notifs import push

farmer_bp = Blueprint('farmer', __name__, url_prefix='/farmer')

def farmer_required(f):
    from functools import wraps
    @wraps(f)
    @login_required
    def decorated(*a, **kw):
        if current_user.role != 'farmer':
            flash('Farmer access required.', 'error')
            return redirect(url_for('auth.login'))
        if not current_user.is_approved:
            flash('Your account is pending approval.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*a, **kw)
    return decorated

@farmer_bp.route('/dashboard')
@farmer_required
def dashboard():
    fid = current_user.id
    profile = query("SELECT * FROM farmer_profiles WHERE user_id=?", (fid,), fetchone=True)
    stats = query(
        "SELECT COUNT(*) as total_products, "
        "SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) as active_products "
        "FROM products WHERE farmer_id=?", (fid,), fetchone=True) or {}
    order_stats = query(
        "SELECT COUNT(*) as total, "
        "SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending, "
        "SUM(CASE WHEN status='delivered' THEN 1 ELSE 0 END) as delivered, "
        "COALESCE(SUM(CASE WHEN status='delivered' THEN total_amount ELSE 0 END),0) as revenue "
        "FROM orders WHERE farmer_id=?", (fid,), fetchone=True) or {}
    recent_orders = query(
        "SELECT o.*,u.full_name as buyer_name FROM orders o JOIN users u ON o.buyer_id=u.id "
        "WHERE o.farmer_id=? ORDER BY o.created_at DESC LIMIT 5", (fid,), fetchall=True) or []
    top_products = query(
        "SELECT p.name,p.price,p.quantity,COALESCE(SUM(oi.quantity),0) as sold "
        "FROM products p LEFT JOIN order_items oi ON p.id=oi.product_id "
        "LEFT JOIN orders o ON oi.order_id=o.id AND o.status='delivered' "
        "WHERE p.farmer_id=? GROUP BY p.id ORDER BY sold DESC LIMIT 5", (fid,), fetchall=True) or []
    return render_template('farmer/dashboard.html', profile=profile, stats=stats,
                           order_stats=order_stats, recent_orders=recent_orders, top_products=top_products)

@farmer_bp.route('/products')
@farmer_required
def products():
    prods = query("SELECT p.*,c.name as cat_name FROM products p "
                  "LEFT JOIN categories c ON p.category_id=c.id "
                  "WHERE p.farmer_id=? ORDER BY p.created_at DESC", (current_user.id,), fetchall=True) or []
    return render_template('farmer/products.html', products=prods)

@farmer_bp.route('/products/new', methods=['GET', 'POST'])
@farmer_bp.route('/products/edit/<int:pid>', methods=['GET', 'POST'])
@farmer_required
def product_form(pid=None):
    categories = query("SELECT * FROM categories ORDER BY name", fetchall=True) or []
    product = None
    if pid:
        product = query("SELECT * FROM products WHERE id=? AND farmer_id=?", (pid, current_user.id), fetchone=True)
        if not product:
            flash('Product not found.', 'error')
            return redirect(url_for('farmer.products'))

    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        desc     = request.form.get('description', '').strip()
        price    = request.form.get('price', 0)
        qty      = request.form.get('quantity', 0)
        unit     = request.form.get('unit', 'kg')
        cat_id   = request.form.get('category_id') or None
        featured = 1 if request.form.get('is_featured') else 0
        status   = request.form.get('status', 'active')

        if not name or not price:
            flash('Name and price are required.', 'error')
            return render_template('farmer/product_form.html', product=product, categories=categories)

        img_path = product['image_path'] if product else None
        f = request.files.get('image')
        if f and f.filename:
            ext = f.filename.rsplit('.', 1)[-1].lower()
            if ext in ('jpg', 'jpeg', 'png', 'webp', 'gif'):
                fname = f"prod_{uuid.uuid4().hex}.{ext}"
                f.save(os.path.join(current_app.config['UPLOAD_FOLDER'], fname))
                img_path = f"uploads/{fname}"

        if pid:
            query("UPDATE products SET name=?,description=?,price=?,quantity=?,unit=?,"
                  "category_id=?,is_featured=?,status=?,image_path=? WHERE id=?",
                  (name, desc, price, qty, unit, cat_id, featured, status, img_path, pid), commit=True)
            flash('Product updated.', 'success')
        else:
            query("INSERT INTO products (farmer_id,name,description,price,quantity,unit,"
                  "category_id,is_featured,status,image_path) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (current_user.id, name, desc, price, qty, unit, cat_id, featured, status, img_path), commit=True)
            flash('Product added.', 'success')
        return redirect(url_for('farmer.products'))

    return render_template('farmer/product_form.html', product=product, categories=categories)

@farmer_bp.route('/products/delete/<int:pid>', methods=['POST'])
@farmer_required
def product_delete(pid):
    query("DELETE FROM products WHERE id=? AND farmer_id=?", (pid, current_user.id), commit=True)
    flash('Product deleted.', 'success')
    return redirect(url_for('farmer.products'))

@farmer_bp.route('/orders')
@farmer_required
def orders():
    status = request.args.get('status', '')
    where, params = "WHERE o.farmer_id=?", [current_user.id]
    if status:
        where += " AND o.status=?"; params.append(status)
    orders = query(
        f"SELECT o.*,u.full_name as buyer_name,d.full_name as driver_name "
        f"FROM orders o JOIN users u ON o.buyer_id=u.id LEFT JOIN users d ON o.driver_id=d.id "
        f"{where} ORDER BY o.created_at DESC", params, fetchall=True) or []
    return render_template('farmer/orders.html', orders=orders, status_filter=status)

@farmer_bp.route('/orders/<int:oid>')
@farmer_required
def order_detail(oid):
    order = query(
        "SELECT o.*,u.full_name as buyer_name,u.phone as buyer_phone,d.full_name as driver_name "
        "FROM orders o JOIN users u ON o.buyer_id=u.id LEFT JOIN users d ON o.driver_id=d.id "
        "WHERE o.id=? AND o.farmer_id=?", (oid, current_user.id), fetchone=True)
    if not order:
        flash('Order not found.', 'error')
        return redirect(url_for('farmer.orders'))
    items    = query("SELECT oi.*,p.name,p.image_path,p.unit FROM order_items oi "
                     "JOIN products p ON oi.product_id=p.id WHERE oi.order_id=?", (oid,), fetchall=True) or []
    tracking = query("SELECT * FROM order_tracking WHERE order_id=? ORDER BY created_at ASC", (oid,), fetchall=True) or []
    drivers  = query("SELECT u.id,u.full_name,dp.vehicle_type FROM users u "
                     "JOIN driver_profiles dp ON u.id=dp.user_id "
                     "WHERE u.role='driver' AND u.is_approved=1 AND dp.availability='available'", fetchall=True) or []
    return render_template('farmer/order_detail.html', order=order, items=items, tracking=tracking, drivers=drivers)

@farmer_bp.route('/orders/<int:oid>/update', methods=['POST'])
@farmer_required
def order_update(oid):
    order = query("SELECT * FROM orders WHERE id=? AND farmer_id=?", (oid, current_user.id), fetchone=True)
    if not order:
        flash('Order not found.', 'error')
        return redirect(url_for('farmer.orders'))
    new_status = request.form.get('status')
    driver_id  = request.form.get('driver_id') or None
    note       = request.form.get('note', '')
    if new_status not in ('confirmed', 'packed', 'shipped', 'cancelled'):
        flash('Invalid status.', 'error')
        return redirect(url_for('farmer.order_detail', oid=oid))
    db = get_db()
    db.execute("UPDATE orders SET status=? WHERE id=?", (new_status, oid))
    if driver_id:
        db.execute("UPDATE orders SET driver_id=? WHERE id=?", (driver_id, oid))
        db.execute("UPDATE driver_profiles SET availability='busy' WHERE user_id=?", (driver_id,))
        push(int(driver_id), '🚚 New Delivery', f"Assigned to Order #{oid}.", 'delivery', oid)
    db.execute("INSERT INTO order_tracking (order_id,status,note,updated_by) VALUES (?,?,?,?)",
               (oid, new_status, note, current_user.id))
    db.commit()
    push(order['buyer_id'], f'📦 Order #{oid}', f"Status: {new_status.upper()}", 'order', oid)
    flash('Order updated.', 'success')
    return redirect(url_for('farmer.order_detail', oid=oid))

@farmer_bp.route('/profile', methods=['GET', 'POST'])
@farmer_required
def profile():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_profile':
            phone     = request.form.get('phone', '').strip()
            farm_name = request.form.get('farm_name', '').strip()
            location  = request.form.get('farm_location', '').strip()
            lat       = request.form.get('lat') or None
            lng       = request.form.get('lng') or None
            query("UPDATE users SET phone=? WHERE id=?", (phone, current_user.id), commit=True)
            query("UPDATE farmer_profiles SET farm_name=?,farm_location=?,lat=?,lng=? WHERE user_id=?",
                  (farm_name, location, lat, lng, current_user.id), commit=True)
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
        return redirect(url_for('farmer.profile'))
    user    = query("SELECT * FROM users WHERE id=?", (current_user.id,), fetchone=True)
    profile = query("SELECT * FROM farmer_profiles WHERE user_id=?", (current_user.id,), fetchone=True)
    return render_template('farmer/profile.html', user=user, profile=profile)
