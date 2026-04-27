import bcrypt
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from db import query, get_db
from notifs import push, push_many, admins

api_auth = Blueprint('api_auth', __name__, url_prefix='/api/auth')

def _make_user(row):
    return {
        'id': row['id'], 'full_name': row['full_name'],
        'email': row['email'], 'role': row['role'],
        'phone': row['phone'], 'address': row['address'],
        'lat': row['lat'], 'lng': row['lng'],
        'is_approved': bool(row['is_approved']),
        'profile_photo': row['profile_photo'],
    }

@api_auth.post('/login')
def login():
    d = request.get_json() or {}
    email    = d.get('email', '').strip()
    password = d.get('password', '').strip()
    row = query('SELECT * FROM users WHERE email=? AND is_active=1', (email,), fetchone=True)
    if not row or not bcrypt.checkpw(password.encode(), row['password_hash'].encode()):
        return jsonify({'error': 'Invalid email or password'}), 401
    if not row['is_approved'] and row['role'] != 'buyer':
        return jsonify({'error': 'Account pending admin approval'}), 403
    token = create_access_token(identity=str(row['id']))
    return jsonify({'token': token, 'user': _make_user(row)})

@api_auth.post('/register')
def register():
    d    = request.get_json() or {}
    role = d.get('role', 'buyer')
    name = d.get('full_name', '').strip()
    email    = d.get('email', '').strip()
    phone    = d.get('phone', '').strip()
    password = d.get('password', '').strip()

    if not name or not email or not password:
        return jsonify({'error': 'All fields are required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    if query('SELECT id FROM users WHERE email=?', (email,), fetchone=True):
        return jsonify({'error': 'Email already registered'}), 409

    pw       = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    approved = 1 if role == 'buyer' else 0
    uid = query(
        'INSERT INTO users (full_name,email,password_hash,role,phone,is_approved) VALUES (?,?,?,?,?,?)',
        (name, email, pw, role, phone, approved), commit=True)

    db = get_db()
    if role == 'farmer':
        db.execute('INSERT INTO farmer_profiles (user_id,farm_name,farm_location,product_type) VALUES (?,?,?,?)',
                   (uid, d.get('farm_name', name+"'s Farm"), d.get('farm_location',''), d.get('product_type','')))
    elif role == 'driver':
        db.execute('INSERT INTO driver_profiles (user_id,vehicle_type,license_number) VALUES (?,?,?)',
                   (uid, d.get('vehicle_type',''), d.get('license_number','')))
    db.commit()

    push_many(admins(), '👤 New Registration',
              f"{name} registered as {role}.", 'info')

    msg = 'Registration successful' if role == 'buyer' else 'Registration submitted. Await admin approval.'
    return jsonify({'message': msg, 'approved': bool(approved)}), 201

@api_auth.get('/me')
@jwt_required()
def me():
    uid = int(get_jwt_identity())
    row = query('SELECT * FROM users WHERE id=?', (uid,), fetchone=True)
    if not row:
        return jsonify({'error': 'User not found'}), 404
    extra = {}
    if row['role'] == 'farmer':
        fp = query('SELECT * FROM farmer_profiles WHERE user_id=?', (uid,), fetchone=True)
        extra['farmer_profile'] = dict(fp) if fp else {}
    elif row['role'] == 'driver':
        dp = query('SELECT * FROM driver_profiles WHERE user_id=?', (uid,), fetchone=True)
        extra['driver_profile'] = dict(dp) if dp else {}
    return jsonify({**_make_user(row), **extra})

@api_auth.put('/profile')
@jwt_required()
def update_profile():
    uid = int(get_jwt_identity())
    d   = request.get_json() or {}
    query("UPDATE users SET phone=?,address=?,lat=?,lng=? WHERE id=?",
          (d.get('phone'), d.get('address'), d.get('lat'), d.get('lng'), uid), commit=True)
    if d.get('farm_name'):
        query("UPDATE farmer_profiles SET farm_name=?,farm_location=?,lat=?,lng=? WHERE user_id=?",
              (d['farm_name'], d.get('farm_location'), d.get('lat'), d.get('lng'), uid), commit=True)
    return jsonify({'message': 'Profile updated'})

@api_auth.put('/password')
@jwt_required()
def change_password():
    uid = int(get_jwt_identity())
    d   = request.get_json() or {}
    cur = d.get('current_password', '')
    new = d.get('new_password', '')
    row = query('SELECT password_hash FROM users WHERE id=?', (uid,), fetchone=True)
    if not bcrypt.checkpw(cur.encode(), row['password_hash'].encode()):
        return jsonify({'error': 'Current password incorrect'}), 400
    if len(new) < 6:
        return jsonify({'error': 'New password must be at least 6 characters'}), 400
    hashed = bcrypt.hashpw(new.encode(), bcrypt.gensalt()).decode()
    query('UPDATE users SET password_hash=? WHERE id=?', (hashed, uid), commit=True)
    return jsonify({'message': 'Password changed'})
