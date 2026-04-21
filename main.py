"""
AgriMarket Android App
Kivy WebView wrapping the Flask backend running locally on the device.
"""
import threading, os, sys, time

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

# ── Start Flask in background ─────────────────────────────
def start_flask():
    from app import create_app
    flask_app = create_app()
    flask_app.run(host='127.0.0.1', port=5001, debug=False, use_reloader=False)

threading.Thread(target=start_flask, daemon=True).start()

# ── Kivy App ──────────────────────────────────────────────
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.utils import platform

PORT = 5001
URL  = f'http://127.0.0.1:{PORT}'

if platform == 'android':
    from android.runnable import run_on_ui_thread
    from jnius import autoclass

    WebView        = autoclass('android.webkit.WebView')
    WebViewClient  = autoclass('android.webkit.WebViewClient')
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    LayoutParams   = autoclass('android.view.ViewGroup$LayoutParams')

    class AgriWebView(BoxLayout):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            # Wait for Flask to be ready before loading
            Clock.schedule_interval(self._wait_for_flask, 0.5)

        def _wait_for_flask(self, dt):
            import socket
            try:
                s = socket.create_connection(('127.0.0.1', PORT), timeout=1)
                s.close()
                Clock.unschedule(self._wait_for_flask)
                self._launch_webview(0)
            except Exception:
                pass  # still starting, keep waiting

        @run_on_ui_thread
        def _launch_webview(self, dt):
            activity = PythonActivity.mActivity
            wv = WebView(activity)
            s  = wv.getSettings()
            s.setJavaScriptEnabled(True)
            s.setDomStorageEnabled(True)
            s.setGeolocationEnabled(True)
            s.setAllowFileAccess(True)
            s.setDatabaseEnabled(True)
            s.setMediaPlaybackRequiresUserGesture(False)
            s.setUserAgentString('AgriMarket/1.0 Android')
            wv.setWebViewClient(WebViewClient())
            wv.loadUrl(URL)
            activity.getWindow().getDecorView().addView(
                wv, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT))

    class AgriMarketApp(App):
        def build(self):
            return AgriWebView()

else:
    # Desktop fallback
    class AgriMarketApp(App):
        def build(self):
            box = BoxLayout(orientation='vertical', padding=30, spacing=10)
            box.add_widget(Label(
                text=f'[b]🌾 AgriMarket[/b]\n\nOpen [color=2E7D32]{URL}[/color]\nin your browser',
                font_size='18sp', halign='center', markup=True))
            return box

if __name__ == '__main__':
    AgriMarketApp().run()
