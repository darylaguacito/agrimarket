import bcrypt
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from functools import wraps
from db import query, get_db
from notifs import push, send_sms

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*a, **kw):
        if current_user.role != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*a, **kw)
    return decorated

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    stats = {
        'users':    query("SELECT COUNT(*) as c FROM users WHERE role!='admin'", fetchone=True)['c'],
        'farmers':  query("SELECT COUNT(*) as c FROM users WHERE role='farmer' AND is_approved=1", fetchone=True)['c'],
        'buyers':   query("SELECT COUNT(*) as c FROM users WHERE role='buyer'", fetchone=True)['c'],
        'drivers':  query("SELECT COUNT(*) as c FROM users WHERE role='driver' AND is_approved=1", fetchone=True)['c'],
        'products': query("SELECT COUNT(*) as c FROM products WHERE status='active'", fetchone=True)['c'],
        'orders':   query("SELECT COUNT(*) as c FROM orders", fetchone=True)['c'],
        'pending_approvals': query("SELECT COUNT(*) as c FROM users WHERE is_approved=0 AND role!='buyer'", fetchone=True)['c'],
        'revenue':  query("SELECT COALESCE(SUM(total_amount),0) as r FROM orders WHERE status='delivered'", fetchone=True)['r'],
    }
    recent_orders = query(
        "SELECT o.*,b.full_name as buyer_name,f.full_name as farmer_name "
        "FROM orders o JOIN users b ON o.buyer_id=b.id JOIN users f ON o.farmer_id=f.id "
        "ORDER BY o.created_at DESC LIMIT 8", fetchall=True) or []
    pending_users = query(
        "SELECT * FROM users WHERE is_approved=0 AND role!='buyer' ORDER BY created_at DESC LIMIT 5",
        fetchall=True) or []
    return render_template('admin/dashboard.html', stats=stats,
                           recent_orders=recent_orders, pending_users=pending_users)

@admin_bp.route('/users')
@admin_required
def users():
    role   = request.args.get('role', '')
    search = request.args.get('q', '').strip()
    where, params = [], []
    if role:
        where.append("role=?"); params.append(role)
    if search:
        where.append("(full_name LIKE ? OR email LIKE ?)")
        params += [f'%{search}%', f'%{search}%']
    w = ('WHERE ' + ' AND '.join(where)) if where else ''
    users = query(f"SELECT * FROM users {w} ORDER BY created_at DESC", params, fetchall=True) or []
    return render_template('admin/users.html', users=users, role_filter=role, search=search)

@admin_bp.route('/users/approve/<int:uid>', methods=['POST'])
@admin_required
def approve_user(uid):
    query("UPDATE users SET is_approved=1 WHERE id=?", (uid,), commit=True)
    user = query("SELECT full_name,role FROM users WHERE id=?", (uid,), fetchone=True)
    push(uid, '✅ Account Approved', 'Your account has been approved!', 'info')
    flash(f"{user['full_name']} approved.", 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/toggle/<int:uid>', methods=['POST'])
@admin_required
def toggle_user(uid):
    if uid == current_user.id:
        flash("Cannot deactivate yourself.", 'error')
        return redirect(url_for('admin.users'))
    user = query("SELECT is_active FROM users WHERE id=?", (uid,), fetchone=True)
    query("UPDATE users SET is_active=? WHERE id=?", (0 if user['is_active'] else 1, uid), commit=True)
    flash('User status updated.', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/delete/<int:uid>', methods=['POST'])
@admin_required
def delete_user(uid):
    if uid == current_user.id:
        flash("Cannot delete yourself.", 'error')
        return redirect(url_for('admin.users'))
    query("DELETE FROM users WHERE id=?", (uid,), commit=True)
    flash('User deleted.', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/products')
@admin_required
def products():
    products = query(
        "SELECT p.*,u.full_name as farmer_name,c.name as cat_name "
        "FROM products p JOIN users u ON p.farmer_id=u.id "
        "LEFT JOIN categories c ON p.category_id=c.id ORDER BY p.created_at DESC", fetchall=True) or []
    return render_template('admin/products.html', products=products)

@admin_bp.route('/products/toggle/<int:pid>', methods=['POST'])
@admin_required
def toggle_product(pid):
    p = query("SELECT status FROM products WHERE id=?", (pid,), fetchone=True)
    query("UPDATE products SET status=? WHERE id=?",
          ('inactive' if p['status'] == 'active' else 'active', pid), commit=True)
    flash('Product status updated.', 'success')
    return redirect(url_for('admin.products'))

@admin_bp.route('/products/feature/<int:pid>', methods=['POST'])
@admin_required
def feature_product(pid):
    p = query("SELECT is_featured FROM products WHERE id=?", (pid,), fetchone=True)
    query("UPDATE products SET is_featured=? WHERE id=?", (0 if p['is_featured'] else 1, pid), commit=True)
    flash('Featured status updated.', 'success')
    return redirect(url_for('admin.products'))

@admin_bp.route('/orders')
@admin_required
def orders():
    status = request.args.get('status', '')
    where, params = [], []
    if status:
        where.append("o.status=?"); params.append(status)
    w = ('WHERE ' + ' AND '.join(where)) if where else ''
    orders = query(
        f"SELECT o.*,b.full_name as buyer_name,f.full_name as farmer_name,d.full_name as driver_name "
        f"FROM orders o JOIN users b ON o.buyer_id=b.id JOIN users f ON o.farmer_id=f.id "
        f"LEFT JOIN users d ON o.driver_id=d.id {w} ORDER BY o.created_at DESC",
        params, fetchall=True) or []
    drivers = query(
        "SELECT u.id,u.full_name,dp.vehicle_type FROM users u "
        "JOIN driver_profiles dp ON u.id=dp.user_id "
        "WHERE u.role='driver' AND u.is_approved=1 AND dp.availability='available'",
        fetchall=True) or []
    return render_template('admin/orders.html', orders=orders, status_filter=status, drivers=drivers)

@admin_bp.route('/orders/<int:oid>/assign-driver', methods=['POST'])
@admin_required
def assign_driver(oid):
    driver_id = request.form.get('driver_id')
    if not driver_id:
        flash('Select a driver.', 'error')
        return redirect(url_for('admin.orders'))
    db = get_db()
    db.execute("UPDATE orders SET driver_id=?,status='shipped' WHERE id=?", (driver_id, oid))
    db.execute("UPDATE driver_profiles SET availability='busy' WHERE user_id=?", (driver_id,))
    db.execute("INSERT INTO order_tracking (order_id,status,note,updated_by) VALUES (?,'shipped','Driver assigned',?)",
               (oid, current_user.id))
    db.commit()
    order = query("SELECT buyer_id,farmer_id FROM orders WHERE id=?", (oid,), fetchone=True)
    push(int(driver_id), '🚚 New Delivery Assigned', f"Order #{oid} assigned.", 'delivery', oid)
    push(order['buyer_id'], f'📦 Order #{oid} Shipped', 'A driver has been assigned.', 'order', oid)
    buyer = query("SELECT phone, full_name FROM users WHERE id=?", (order['buyer_id'],), fetchone=True)
    if buyer and buyer.get('phone'):
        send_sms(buyer['phone'],
                 f"Hi {buyer['full_name']}, your AgriMarket Order #{oid} is now ON THE WAY! "
                 f"A driver has been assigned to deliver your order.")
    flash('Driver assigned.', 'success')
    return redirect(url_for('admin.orders'))

@admin_bp.route('/analytics')
@admin_required
def analytics():
    monthly = query(
        "SELECT strftime('%b %Y', created_at) as month, "
        "strftime('%Y-%m', created_at) as key_, "
        "COUNT(*) as orders, COALESCE(SUM(total_amount),0) as revenue "
        "FROM orders WHERE status='delivered' "
        "AND created_at >= datetime('now','-6 months') "
        "GROUP BY key_, month ORDER BY key_ ASC", fetchall=True) or []
    top_products = query(
        "SELECT p.name, COALESCE(SUM(oi.quantity),0) as sold, "
        "COALESCE(SUM(oi.quantity*oi.price),0) as revenue "
        "FROM products p LEFT JOIN order_items oi ON p.id=oi.product_id "
        "LEFT JOIN orders o ON oi.order_id=o.id AND o.status='delivered' "
        "GROUP BY p.id ORDER BY sold DESC LIMIT 8", fetchall=True) or []
    top_farmers = query(
        "SELECT u.full_name, fp.farm_name, fp.rating, "
        "COALESCE(SUM(o.total_amount),0) as revenue, COUNT(o.id) as orders "
        "FROM users u JOIN farmer_profiles fp ON u.id=fp.user_id "
        "LEFT JOIN orders o ON u.id=o.farmer_id AND o.status='delivered' "
        "GROUP BY u.id ORDER BY revenue DESC LIMIT 5", fetchall=True) or []
    cat_stats = query(
        "SELECT c.name, COUNT(p.id) as products, COALESCE(SUM(oi.quantity),0) as sold "
        "FROM categories c LEFT JOIN products p ON c.id=p.category_id "
        "LEFT JOIN order_items oi ON p.id=oi.product_id "
        "GROUP BY c.id ORDER BY sold DESC", fetchall=True) or []
    return render_template('admin/analytics.html', monthly=monthly, top_products=top_products,
                           top_farmers=top_farmers, cat_stats=cat_stats)
