from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from db import query, get_db
from notifs import push, push_many, admins

buyer_bp = Blueprint('buyer', __name__, url_prefix='/buyer')

def buyer_required(f):
    from functools import wraps
    @wraps(f)
    @login_required
    def decorated(*a, **kw):
        if current_user.role not in ('buyer', 'farmer'):
            flash('Access denied.', 'error')
            return redirect(url_for('auth.login'))
        return f(*a, **kw)
    return decorated

@buyer_bp.route('/home')
@login_required
def home():
    search = request.args.get('q', '').strip()
    cat_id = request.args.get('cat', '')
    featured = query(
        "SELECT p.*,u.full_name as seller_name,c.name as cat_name FROM products p "
        "JOIN users u ON p.farmer_id=u.id LEFT JOIN categories c ON p.category_id=c.id "
        "WHERE p.is_featured=1 AND p.status='active' AND p.quantity>0 LIMIT 6", fetchall=True) or []
    categories = query("SELECT * FROM categories ORDER BY name", fetchall=True) or []

    where, params = ["p.status='active'", "p.quantity>0"], []
    if search:
        where.append("(p.name LIKE ? OR p.description LIKE ?)")
        params += [f'%{search}%', f'%{search}%']
    if cat_id:
        where.append("p.category_id=?"); params.append(cat_id)

    products = query(
        f"SELECT p.*,u.full_name as seller_name,fp.farm_name,c.name as cat_name "
        f"FROM products p JOIN users u ON p.farmer_id=u.id "
        f"LEFT JOIN farmer_profiles fp ON u.id=fp.user_id "
        f"LEFT JOIN categories c ON p.category_id=c.id "
        f"WHERE {' AND '.join(where)} ORDER BY p.created_at DESC",
        params, fetchall=True) or []

    cart_count = 0
    if current_user.is_authenticated:
        row = query("SELECT SUM(quantity) as c FROM cart_items WHERE user_id=?", (current_user.id,), fetchone=True)
        cart_count = int(row['c'] or 0) if row else 0

    return render_template('buyer/home.html', featured=featured, products=products,
                           categories=categories, search=search, cat_id=cat_id, cart_count=cart_count)

@buyer_bp.route('/product/<int:pid>')
@login_required
def product_detail(pid):
    product = query(
        "SELECT p.*,u.full_name as seller_name,u.id as seller_id,fp.farm_name,fp.farm_location,"
        "fp.rating as seller_rating,fp.rating_count,c.name as cat_name "
        "FROM products p JOIN users u ON p.farmer_id=u.id "
        "LEFT JOIN farmer_profiles fp ON u.id=fp.user_id "
        "LEFT JOIN categories c ON p.category_id=c.id WHERE p.id=?", (pid,), fetchone=True)
    if not product:
        flash('Product not found.', 'error')
        return redirect(url_for('buyer.home'))
    reviews = query(
        "SELECT r.*,u.full_name FROM reviews r JOIN users u ON r.buyer_id=u.id "
        "WHERE r.farmer_id=? ORDER BY r.created_at DESC LIMIT 5",
        (product['seller_id'],), fetchall=True) or []
    return render_template('buyer/product_detail.html', product=product, reviews=reviews)

@buyer_bp.route('/cart')
@buyer_required
def cart():
    items = query(
        "SELECT ci.*,p.name,p.price,p.image_path,p.unit,p.quantity as stock,u.full_name as seller "
        "FROM cart_items ci JOIN products p ON ci.product_id=p.id JOIN users u ON p.farmer_id=u.id "
        "WHERE ci.user_id=?", (current_user.id,), fetchall=True) or []
    total = sum(float(i['price']) * i['quantity'] for i in items)
    return render_template('buyer/cart.html', items=items, total=total)

@buyer_bp.route('/cart/add', methods=['POST'])
@buyer_required
def cart_add():
    pid = request.form.get('product_id')
    qty = max(1, int(request.form.get('quantity', 1)))
    product = query("SELECT * FROM products WHERE id=? AND status='active'", (pid,), fetchone=True)
    if not product or product['farmer_id'] == current_user.id:
        flash("Cannot add this product.", 'error')
        return redirect(url_for('buyer.home'))
    existing = query("SELECT id,quantity FROM cart_items WHERE user_id=? AND product_id=?",
                     (current_user.id, pid), fetchone=True)
    if existing:
        new_qty = min(existing['quantity'] + qty, product['quantity'])
        query("UPDATE cart_items SET quantity=? WHERE id=?", (new_qty, existing['id']), commit=True)
    else:
        query("INSERT INTO cart_items (user_id,product_id,quantity) VALUES (?,?,?)",
              (current_user.id, pid, min(qty, product['quantity'])), commit=True)
    flash('Added to cart!', 'success')
    return redirect(request.referrer or url_for('buyer.cart'))

@buyer_bp.route('/cart/remove/<int:cid>', methods=['POST'])
@buyer_required
def cart_remove(cid):
    query("DELETE FROM cart_items WHERE id=? AND user_id=?", (cid, current_user.id), commit=True)
    return redirect(url_for('buyer.cart'))

@buyer_bp.route('/cart/update', methods=['POST'])
@buyer_required
def cart_update():
    cid = request.form.get('cart_id')
    qty = max(1, int(request.form.get('quantity', 1)))
    item = query("SELECT ci.id,p.quantity as stock FROM cart_items ci "
                 "JOIN products p ON ci.product_id=p.id WHERE ci.id=? AND ci.user_id=?",
                 (cid, current_user.id), fetchone=True)
    if item:
        query("UPDATE cart_items SET quantity=? WHERE id=?", (min(qty, item['stock']), cid), commit=True)
    return redirect(url_for('buyer.cart'))

@buyer_bp.route('/checkout', methods=['GET', 'POST'])
@buyer_required
def checkout():
    user  = query("SELECT * FROM users WHERE id=?", (current_user.id,), fetchone=True)
    items = query(
        "SELECT ci.*,p.name,p.price,p.unit,p.quantity as stock,p.farmer_id "
        "FROM cart_items ci JOIN products p ON ci.product_id=p.id WHERE ci.user_id=?",
        (current_user.id,), fetchall=True) or []
    if not items:
        flash('Your cart is empty.', 'error')
        return redirect(url_for('buyer.cart'))

    if request.method == 'POST':
        address = request.form.get('shipping_address', '').strip()
        contact = request.form.get('contact_number', '').strip()
        payment = request.form.get('payment_method', 'cod')
        notes   = request.form.get('notes', '').strip()
        if not address or not contact:
            flash('Address and contact are required.', 'error')
            return render_template('buyer/checkout.html', items=items, user=user,
                                   total=sum(float(i['price'])*i['quantity'] for i in items))
        db = get_db()
        try:
            by_farmer = {}
            for i in items:
                by_farmer.setdefault(i['farmer_id'], []).append(i)

            for fid, fitems in by_farmer.items():
                total = sum(float(i['price']) * i['quantity'] for i in fitems)
                cur = db.execute(
                    "INSERT INTO orders (buyer_id,farmer_id,total_amount,payment_method,"
                    "shipping_address,contact_number,notes,buyer_lat,buyer_lng) VALUES (?,?,?,?,?,?,?,?,?)",
                    (current_user.id, fid, total, payment, address, contact, notes,
                     user.get('lat'), user.get('lng')))
                oid = cur.lastrowid
                for i in fitems:
                    db.execute("INSERT INTO order_items (order_id,product_id,quantity,price) VALUES (?,?,?,?)",
                               (oid, i['product_id'], i['quantity'], i['price']))
                    db.execute("UPDATE products SET quantity=quantity-? WHERE id=?",
                               (i['quantity'], i['product_id']))
                db.execute("INSERT INTO order_tracking (order_id,status,note,updated_by) VALUES (?,'pending','Order placed',?)",
                           (oid, current_user.id))
                db.commit()
                push(fid, '🛒 New Order!', f"New order #{oid} for ₱{total:,.2f}.", 'order', oid)
                push(current_user.id, '✅ Order Placed', f"Order #{oid} confirmed!", 'order', oid)
                push_many(admins(), '📦 New Order', f"Order #{oid} by {current_user.full_name}.", 'order', oid)

            db.execute("DELETE FROM cart_items WHERE user_id=?", (current_user.id,))
            db.commit()
            flash('Order placed successfully!', 'success')
            return redirect(url_for('buyer.orders'))
        except Exception as e:
            db.rollback()
            flash(f'Order failed: {e}', 'error')

    total = sum(float(i['price']) * i['quantity'] for i in items)
    return render_template('buyer/checkout.html', items=items, user=user, total=total)

@buyer_bp.route('/orders')
@buyer_required
def orders():
    orders = query(
        "SELECT o.*,u.full_name as farmer_name,fp.farm_name,d.full_name as driver_name "
        "FROM orders o JOIN users u ON o.farmer_id=u.id "
        "LEFT JOIN farmer_profiles fp ON u.id=fp.user_id "
        "LEFT JOIN users d ON o.driver_id=d.id "
        "WHERE o.buyer_id=? ORDER BY o.created_at DESC",
        (current_user.id,), fetchall=True) or []
    return render_template('buyer/orders.html', orders=orders)

@buyer_bp.route('/orders/<int:oid>')
@buyer_required
def order_detail(oid):
    order = query(
        "SELECT o.*,u.full_name as farmer_name,fp.farm_name,d.full_name as driver_name,d.phone as driver_phone "
        "FROM orders o JOIN users u ON o.farmer_id=u.id "
        "LEFT JOIN farmer_profiles fp ON u.id=fp.user_id "
        "LEFT JOIN users d ON o.driver_id=d.id "
        "WHERE o.id=? AND o.buyer_id=?", (oid, current_user.id), fetchone=True)
    if not order:
        flash('Order not found.', 'error')
        return redirect(url_for('buyer.orders'))
    items    = query("SELECT oi.*,p.name,p.image_path,p.unit FROM order_items oi "
                     "JOIN products p ON oi.product_id=p.id WHERE oi.order_id=?", (oid,), fetchall=True) or []
    tracking = query("SELECT * FROM order_tracking WHERE order_id=? ORDER BY created_at ASC", (oid,), fetchall=True) or []
    has_review = query("SELECT id FROM reviews WHERE order_id=? AND buyer_id=?", (oid, current_user.id), fetchone=True)
    return render_template('buyer/order_detail.html', order=order, items=items,
                           tracking=tracking, has_review=has_review)

@buyer_bp.route('/orders/<int:oid>/review', methods=['POST'])
@buyer_required
def submit_review(oid):
    order = query("SELECT * FROM orders WHERE id=? AND buyer_id=? AND status='delivered'",
                  (oid, current_user.id), fetchone=True)
    if not order:
        flash('Cannot review this order.', 'error')
        return redirect(url_for('buyer.orders'))
    if query("SELECT id FROM reviews WHERE order_id=? AND buyer_id=?", (oid, current_user.id), fetchone=True):
        flash('Already reviewed.', 'error')
        return redirect(url_for('buyer.order_detail', oid=oid))
    rating  = int(request.form.get('rating', 5))
    comment = request.form.get('comment', '').strip()
    db = get_db()
    db.execute("INSERT INTO reviews (order_id,buyer_id,farmer_id,rating,comment) VALUES (?,?,?,?,?)",
               (oid, current_user.id, order['farmer_id'], rating, comment))
    db.execute("UPDATE farmer_profiles SET "
               "rating=(SELECT AVG(rating) FROM reviews WHERE farmer_id=?),"
               "rating_count=(SELECT COUNT(*) FROM reviews WHERE farmer_id=?) WHERE user_id=?",
               (order['farmer_id'], order['farmer_id'], order['farmer_id']))
    db.commit()
    flash('Review submitted!', 'success')
    return redirect(url_for('buyer.order_detail', oid=oid))

@buyer_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        phone   = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        lat     = request.form.get('lat') or None
        lng     = request.form.get('lng') or None
        query("UPDATE users SET phone=?,address=?,lat=?,lng=? WHERE id=?",
              (phone, address, lat, lng, current_user.id), commit=True)
        flash('Profile updated.', 'success')
        return redirect(url_for('buyer.profile'))
    user = query("SELECT * FROM users WHERE id=?", (current_user.id,), fetchone=True)
    return render_template('buyer/profile.html', user=user)

@buyer_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    import bcrypt
    cur_pw = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    user   = query("SELECT password_hash FROM users WHERE id=?", (current_user.id,), fetchone=True)
    if not bcrypt.checkpw(cur_pw.encode(), user['password_hash'].encode()):
        flash('Current password is incorrect.', 'error')
    elif len(new_pw) < 6:
        flash('New password must be at least 6 characters.', 'error')
    else:
        hashed = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
        query("UPDATE users SET password_hash=? WHERE id=?", (hashed, current_user.id), commit=True)
        flash('Password changed successfully.', 'success')
    return redirect(url_for('buyer.profile'))

@buyer_bp.route('/api/notif-count')
@login_required
def notif_count():
    row = query("SELECT COUNT(*) as c FROM notifications WHERE user_id=? AND is_read=0",
                (current_user.id,), fetchone=True)
    return jsonify({'count': int(row['c'] or 0)})
