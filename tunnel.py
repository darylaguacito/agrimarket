"""
AgriMarket Public Tunnel
Opens a public HTTPS URL so your phone can access the app
from anywhere — no firewall config, no signup needed.
"""
import subprocess, threading, time, re, sys, os
import qrcode

def start_tunnel():
    print("\n🌾 AgriMarket Tunnel")
    print("="*45)
    print("Starting tunnel... please wait 5 seconds")
    print("="*45)

    # Use localhost.run — free, no signup, works via SSH
    cmd = ['ssh', '-o', 'StrictHostKeyChecking=no',
           '-o', 'ServerAliveInterval=30',
           '-R', '80:localhost:5001',
           'nokey@localhost.run']

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    url = None
    for line in proc.stdout:
        line = line.strip()
        if line:
            print(" ", line)
        # Extract the public URL
        match = re.search(r'https://[a-zA-Z0-9\-]+\.lhr\.life', line)
        if not match:
            match = re.search(r'https://[a-zA-Z0-9\-]+\.localhost\.run', line)
        if match and not url:
            url = match.group(0)
            print("\n" + "="*45)
            print(f"  ✅ PUBLIC URL READY!")
            print(f"  {url}")
            print("="*45)
            print("  Open this URL on your phone browser")
            print("  Or scan the QR code below:\n")

            # Print QR in terminal
            qr = qrcode.QRCode(border=1)
            qr.add_data(url)
            qr.make(fit=True)
            qr.print_ascii(invert=True)

            # Save QR image
            img = qr.make_image(fill_color='#2E7D32', back_color='white')
            qr_path = os.path.join(os.path.dirname(__file__), 'static', 'qr.png')
            img.save(qr_path)
            print(f"\n  QR also saved to: {qr_path}")
            print("  Open http://127.0.0.1:5001/connect to see it")
            print("\n  Press Ctrl+C to stop\n")

    proc.wait()

if __name__ == '__main__':
    # Make sure Flask is running first
    import socket
    try:
        s = socket.create_connection(('127.0.0.1', 5001), timeout=2)
        s.close()
    except Exception:
        print("❌ Flask is not running! Start it first:")
        print("   python app.py")
        sys.exit(1)

    start_tunnel()
