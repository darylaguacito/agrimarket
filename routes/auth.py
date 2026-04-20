import bcrypt
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from db import query, get_db
from extensions import User
from notifs import push, push_many, admins

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def index():
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(_home(current_user.role)))
    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        row = query('SELECT * FROM users WHERE email=? AND is_active=1', (email,), fetchone=True)
        if row and bcrypt.checkpw(password.encode(), row['password_hash'].encode()):
            if not row['is_approved'] and row['role'] != 'buyer':
                flash('Your account is pending admin approval.', 'warning')
                return render_template('auth/login.html')
            login_user(User(row))
            return redirect(url_for(_home(row['role'])))
        flash('Invalid email or password.', 'error')
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        role     = request.form.get('role', 'buyer')
        name     = request.form.get('full_name', '').strip()
        email    = request.form.get('email', '').strip()
        phone    = request.form.get('phone', '').strip()
        password = request.form.get('password', '').strip()

        if not name or not email or not password:
            flash('All fields are required.', 'error')
            return render_template('auth/register.html')
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('auth/register.html')
        if query('SELECT id FROM users WHERE email=?', (email,), fetchone=True):
            flash('Email already registered.', 'error')
            return render_template('auth/register.html')

        pw       = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        approved = 1 if role == 'buyer' else 0
        uid = query(
            'INSERT INTO users (full_name,email,password_hash,role,phone,is_approved) VALUES (?,?,?,?,?,?)',
            (name, email, pw, role, phone, approved), commit=True)

        db = get_db()
        if role == 'farmer':
            farm_name = request.form.get('farm_name', name + "'s Farm")
            location  = request.form.get('farm_location', '')
            prod_type = request.form.get('product_type', '')
            db.execute('INSERT INTO farmer_profiles (user_id,farm_name,farm_location,product_type) VALUES (?,?,?,?)',
                       (uid, farm_name, location, prod_type))
        elif role == 'driver':
            vtype   = request.form.get('vehicle_type', '')
            license = request.form.get('license_number', '')
            db.execute('INSERT INTO driver_profiles (user_id,vehicle_type,license_number) VALUES (?,?,?)',
                       (uid, vtype, license))
        db.commit()

        push_many(admins(), '👤 New Registration',
                  f"{name} registered as {role}.{'Needs approval.' if role != 'buyer' else ''}", 'info')

        flash('Registration successful! Please log in.' if role == 'buyer'
              else 'Registration submitted. Await admin approval.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

def _home(role=None):
    return {'admin': 'admin.dashboard', 'farmer': 'farmer.dashboard',
            'driver': 'driver.dashboard', 'buyer': 'buyer.home'}.get(role, 'buyer.home')
