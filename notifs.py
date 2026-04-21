import os
import requests
import logging
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

def send_sms(phone, message):
    """Send SMS via PhilSMS API. Phone must be in 639XXXXXXXXX format."""
    token     = os.environ.get('PHILSMS_TOKEN', '')
    sender_id = os.environ.get('PHILSMS_SENDER_ID', 'PhilSMS')
    if not token or not phone:
        return

    # Normalize phone: convert 09XXXXXXXXX → 639XXXXXXXXX
    phone = phone.strip().replace(' ', '').replace('-', '')
    if phone.startswith('0'):
        phone = '63' + phone[1:]
    elif phone.startswith('+'):
        phone = phone[1:]

    try:
        resp = requests.post(
            'https://dashboard.philsms.com/api/v3/sms/send',
            json={
                'recipient': phone,
                'sender_id': sender_id,
                'type':      'plain',
                'message':   message,
            },
            headers={
                'Authorization': f'Bearer {token}',
                'Accept':        'application/json',
                'Content-Type':  'application/json',
            },
            timeout=10
        )
        if resp.status_code != 200 or resp.json().get('status') == 'error':
            logging.warning(f"[SMS] Failed to {phone}: {resp.text}")
    except Exception as e:
        logging.warning(f"[SMS] Exception sending to {phone}: {e}")
