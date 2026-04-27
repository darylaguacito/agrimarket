import os, uuid
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import query, get_db
from notifs import push

api_products = Blueprint('api_products', __name__, url_prefix='/api/products')

def _row(r):
    return dict(r) if r else None

@api_products.get('')
@jwt_required()
def list_products():
    search = request.args.get('q', '').strip()
    cat_id = request.args.get('cat', '')
    featured_only = request.args.get('featured', '')

    where, params = ["p.status='active'", "p.quantity>0"], []
    if search:
        where.append("(p.name LIKE ? OR p.description LIKE ?)")
        params += [f'%{search}%', f'%{search}%']
    if cat_id:
        where.append("p.category_id=?"); params.append(cat_id)
    if featured_only:
        where.append("p.is_featured=1")

    products = query(
        f"SELECT p.*,u.full_name as seller_name,fp.farm_name,c.name as cat_name,c.icon as cat_icon "
        f"FROM products p JOIN users u ON p.farmer_id=u.id "
        f"LEFT JOIN farmer_profiles fp ON u.id=fp.user_id "
        f"LEFT JOIN categories c ON p.category_id=c.id "
        f"WHERE {' AND '.join(where)} ORDER BY p.created_at DESC",
        params, fetchall=True) or []
    return jsonify([dict(p) for p in products])

@api_products.get('/<int:pid>')
@jwt_required()
def get_product(pid):
    product = query(
        "SELECT p.*,u.full_name as seller_name,u.id as seller_id,fp.farm_name,"
        "fp.farm_location,fp.rating as seller_rating,fp.rating_count,c.name as cat_name "
        "FROM products p JOIN users u ON p.farmer_id=u.id "
        "LEFT JOIN farmer_profiles fp ON u.id=fp.user_id "
        "LEFT JOIN categories c ON p.category_id=c.id WHERE p.id=?", (pid,), fetchone=True)
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    reviews = query(
        "SELECT r.*,u.full_name FROM reviews r JOIN users u ON r.buyer_id=u.id "
        "WHERE r.farmer_id=? ORDER BY r.created_at DESC LIMIT 5",
        (product['seller_id'],), fetchall=True) or []
    return jsonify({'product': dict(product), 'reviews': [dict(r) for r in reviews]})

@api_products.get('/categories')
@jwt_required()
def categories():
    cats = query("SELECT * FROM categories ORDER BY name", fetchall=True) or []
    return jsonify([dict(c) for c in cats])

# ── Farmer product management ─────────────────────────────

@api_products.get('/mine')
@jwt_required()
def my_products():
    uid = int(get_jwt_identity())
    prods = query(
        "SELECT p.*,c.name as cat_name FROM products p "
        "LEFT JOIN categories c ON p.category_id=c.id "
        "WHERE p.farmer_id=? ORDER BY p.created_at DESC", (uid,), fetchall=True) or []
    return jsonify([dict(p) for p in prods])

@api_products.post('')
@jwt_required()
def create_product():
    uid  = int(get_jwt_identity())
    user = query("SELECT role FROM users WHERE id=?", (uid,), fetchone=True)
    if user['role'] != 'farmer':
        return jsonify({'error': 'Farmers only'}), 403
    d = request.get_json() or {}
    name  = d.get('name', '').strip()
    price = d.get('price', 0)
    if not name or not price:
        return jsonify({'error': 'Name and price required'}), 400
    query("INSERT INTO products (farmer_id,name,description,price,quantity,unit,category_id,is_featured,status) "
          "VALUES (?,?,?,?,?,?,?,?,?)",
          (uid, name, d.get('description',''), price, d.get('quantity',0),
           d.get('unit','kg'), d.get('category_id'), d.get('is_featured',0),
           d.get('status','active')), commit=True)
    qty = int(d.get('quantity', 0))
    if qty <= 10:
        push(uid, '⚠️ Low Stock', f"{name} added with only {qty} units.", 'info')
    return jsonify({'message': 'Product created'}), 201

@api_products.put('/<int:pid>')
@jwt_required()
def update_product(pid):
    uid = int(get_jwt_identity())
    p   = query("SELECT * FROM products WHERE id=? AND farmer_id=?", (pid, uid), fetchone=True)
    if not p:
        return jsonify({'error': 'Not found'}), 404
    d = request.get_json() or {}
    query("UPDATE products SET name=?,description=?,price=?,quantity=?,unit=?,"
          "category_id=?,is_featured=?,status=? WHERE id=?",
          (d.get('name', p['name']), d.get('description', p['description']),
           d.get('price', p['price']), d.get('quantity', p['quantity']),
           d.get('unit', p['unit']), d.get('category_id', p['category_id']),
           d.get('is_featured', p['is_featured']), d.get('status', p['status']), pid), commit=True)
    qty = int(d.get('quantity', p['quantity']))
    if qty <= 10:
        push(uid, '⚠️ Low Stock Alert', f"{d.get('name', p['name'])} has only {qty} left!", 'info')
    return jsonify({'message': 'Product updated'})

@api_products.delete('/<int:pid>')
@jwt_required()
def delete_product(pid):
    uid = int(get_jwt_identity())
    query("DELETE FROM products WHERE id=? AND farmer_id=?", (pid, uid), commit=True)
    return jsonify({'message': 'Product deleted'})

@api_products.post('/<int:pid>/image')
@jwt_required()
def upload_image(pid):
    uid = int(get_jwt_identity())
    p   = query("SELECT id FROM products WHERE id=? AND farmer_id=?", (pid, uid), fetchone=True)
    if not p:
        return jsonify({'error': 'Not found'}), 404
    f = request.files.get('image')
    if not f or not f.filename:
        return jsonify({'error': 'No image provided'}), 400
    ext = f.filename.rsplit('.', 1)[-1].lower()
    if ext not in ('jpg', 'jpeg', 'png', 'webp'):
        return jsonify({'error': 'Invalid image type'}), 400
    fname = f"prod_{uuid.uuid4().hex}.{ext}"
    f.save(os.path.join(current_app.config['UPLOAD_FOLDER'], fname))
    img_path = f"uploads/{fname}"
    query("UPDATE products SET image_path=? WHERE id=?", (img_path, pid), commit=True)
    return jsonify({'image_path': img_path})
