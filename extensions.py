from flask_login import LoginManager
from db import query

login_manager = LoginManager()

class User:
    def __init__(self, d):
        self.id           = d['id']
        self.full_name    = d['full_name']
        self.email        = d['email']
        self.role         = d['role']
        self.is_approved  = d.get('is_approved', 0)
        self._is_active   = d.get('is_active', 1)

    @property
    def is_authenticated(self): return True
    @property
    def is_active(self): return bool(self._is_active)
    @property
    def is_anonymous(self): return False
    def get_id(self): return str(self.id)

@login_manager.user_loader
def load_user(uid):
    row = query('SELECT * FROM users WHERE id=%s', (uid,), fetchone=True)
    return User(row) if row else None
    