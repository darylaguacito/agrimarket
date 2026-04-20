from db import query

def push(user_id, title, message, ntype='info', order_id=None):
    query("INSERT INTO notifications (user_id,title,message,type,related_order_id) VALUES (?,?,?,?,?)",
          (user_id, title, message, ntype, order_id), commit=True)

def push_many(user_ids, title, message, ntype='info', order_id=None):
    for uid in user_ids:
        push(uid, title, message, ntype, order_id)

def admins():
    rows = query("SELECT id FROM users WHERE role='admin'", fetchall=True) or []
    return [r['id'] for r in rows]
