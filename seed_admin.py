"""Run once to set admin password. Usage: python seed_admin.py"""
import bcrypt, os, mysql.connector
from dotenv import load_dotenv
load_dotenv()

pw = bcrypt.hashpw(b'admin123', bcrypt.gensalt()).decode()
db = mysql.connector.connect(
    host=os.getenv('DB_HOST','localhost'), user=os.getenv('DB_USER','root'),
    password=os.getenv('DB_PASS',''), database=os.getenv('DB_NAME','agrimarket'))
cur = db.cursor()
cur.execute("UPDATE users SET password_hash=%s WHERE email='admin@agrimarket.com'", (pw,))
db.commit()
print(f"Admin password set to: admin123")
cur.close(); db.close()
