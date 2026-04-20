import os
from flask import Flask
from dotenv import load_dotenv
from extensions import login_manager
from db import close_db

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv('SECRET_KEY', 'dev-secret')
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to continue.'
    login_manager.login_message_category = 'warning'

    # ── SQLite returns dates as strings — add strftime filter ──
    from datetime import datetime

    def parse_dt(value, fmt='%b %d, %Y %I:%M %p'):
        if not value:
            return ''
        if hasattr(value, 'strftime'):
            return value.strftime(fmt)
        for pattern in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d'):
            try:
                return datetime.strptime(str(value), pattern).strftime(fmt)
            except ValueError:
                continue
        return str(value)

    app.jinja_env.filters['dt'] = parse_dt

    from routes.auth          import auth_bp
    from routes.buyer         import buyer_bp
    from routes.farmer        import farmer_bp
    from routes.driver        import driver_bp
    from routes.admin         import admin_bp
    from routes.notifications import notif_bp

    for bp in (auth_bp, buyer_bp, farmer_bp, driver_bp, admin_bp, notif_bp):
        app.register_blueprint(bp)

    # ── /connect — QR code page for phone access ──
    import socket
    from flask import render_template as rt
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        _ip = s.getsockname()[0]
        s.close()
    except Exception:
        _ip = '127.0.0.1'

    @app.route('/connect')
    def connect_page():
        return rt('connect.html', url=f'http://{_ip}:5001')

    app.teardown_appcontext(close_db)
    return app

if __name__ == '__main__':
    import socket, qrcode, os

    # Get local IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = '127.0.0.1'

    port = 5001
    url  = f'http://{local_ip}:{port}'

    # Generate QR code image
    qr_path = os.path.join(os.path.dirname(__file__), 'static', 'qr.png')
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='#2E7D32', back_color='white')
    img.save(qr_path)

    print("\n" + "="*50)
    print("  🌾 AgriMarket is running!")
    print(f"  Local:   http://127.0.0.1:{port}")
    print(f"  Network: {url}")
    print(f"  QR Code: {qr_path}")
    print("  Scan the QR code to open on your phone")
    print("="*50 + "\n")

    app = create_app()
    # host='0.0.0.0' makes it accessible on all network interfaces
    app.run(debug=True, host='0.0.0.0', port=port)
