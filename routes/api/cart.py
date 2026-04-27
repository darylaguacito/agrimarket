from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import query

api_cart = Blueprint('api_cart', __name__, url_prefix='/api/cart')

@api_cart.get('')
@jwt_required()
def get_cart():
    uid   = int(get_jwt_identity())
    items = query(
        "SELECT ci.*,p.name,p.price,p.image_path,p.unit,p.quantity as stock,u.full_name as seller "
        "FROM cart_items ci JOIN products p ON ci.product_id=p.id JOIN users u ON p.farmer_id=u.id "
        "WHERE ci.user_id=?", (uid,), fetchall=True) or []
    total = sum(float(i['price']) * i['quantity'] for i in items)
    return jsonify({'items': [dict(i) for i in items], 'total': total,
                    'count': sum(i['quantity'] for i in items)})

@api_cart.post('/add')
@jwt_required()
def add():
    uid = int(get_jwt_identity())
    d   = request.get_json() or {}
    pid = d.get('product_id')
    qty = max(1, int(d.get('quantity', 1)))

    product = query("SELECT * FROM products WHERE id=? AND status='active'", (pid,), fetchone=True)
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    if product['farmer_id'] == uid:
        return jsonify({'error': 'Cannot add your own product'}), 400

    existing = query("SELECT id,quantity FROM cart_items WHERE user_id=? AND product_id=?",
                     (uid, pid), fetchone=True)
    if existing:
        new_qty = min(existing['quantity'] + qty, product['quantity'])
        query("UPDATE cart_items SET quantity=? WHERE id=?", (new_qty, existing['id']), commit=True)
    else:
        query("INSERT INTO cart_items (user_id,product_id,quantity) VALUES (?,?,?)",
              (uid, pid, min(qty, product['quantity'])), commit=True)
    return jsonify({'message': 'Added to cart'})

@api_cart.put('/<int:cid>')
@jwt_required()
def update(cid):
    uid = int(get_jwt_identity())
    qty = max(1, int((request.get_json() or {}).get('quantity', 1)))
    item = query("SELECT ci.id,p.quantity as stock FROM cart_items ci "
                 "JOIN products p ON ci.product_id=p.id WHERE ci.id=? AND ci.user_id=?",
                 (cid, uid), fetchone=True)
    if not item:
        return jsonify({'error': 'Cart item not found'}), 404
    query("UPDATE cart_items SET quantity=? WHERE id=?", (min(qty, item['stock']), cid), commit=True)
    return jsonify({'message': 'Cart updated'})

@api_cart.delete('/<int:cid>')
@jwt_required()
def remove(cid):
    uid = int(get_jwt_identity())
    query("DELETE FROM cart_items WHERE id=? AND user_id=?", (cid, uid), commit=True)
    return jsonify({'message': 'Removed from cart'})

@api_cart.delete('')
@jwt_required()
def clear():
    uid = int(get_jwt_identity())
    query("DELETE FROM cart_items WHERE user_id=?", (uid,), commit=True)
    return jsonify({'message': 'Cart cleared'})
