"""
AgriMarket Android App
Pure Python - Kivy WebView wrapping the Flask backend
"""
import threading
import os
import sys

# ── Ensure the app directory is in path ───────────────────
APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

# ── Start Flask server in background thread ────────────────
def start_flask():
    from app import create_app
    flask_app = create_app()
    flask_app.run(host='127.0.0.1', port=5001, debug=False, use_reloader=False)

flask_thread = threading.Thread(target=start_flask, daemon=True)
flask_thread.start()

# ── Kivy WebView App ───────────────────────────────────────
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.utils import platform

# Android WebView
if platform == 'android':
    from android.runnable import run_on_ui_thread
    from jnius import autoclass

    WebView        = autoclass('android.webkit.WebView')
    WebViewClient  = autoclass('android.webkit.WebViewClient')
    WebSettings    = autoclass('android.webkit.WebSettings')
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    LayoutParams   = autoclass('android.view.ViewGroup$LayoutParams')

    class AndroidWebView(BoxLayout):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            Clock.schedule_once(self.create_webview, 2)  # wait for Flask to start

        @run_on_ui_thread
        def create_webview(self, dt):
            activity = PythonActivity.mActivity
            webview  = WebView(activity)

            settings = webview.getSettings()
            settings.setJavaScriptEnabled(True)
            settings.setDomStorageEnabled(True)
            settings.setGeolocationEnabled(True)
            settings.setAllowFileAccess(True)
            settings.setMediaPlaybackRequiresUserGesture(False)
            settings.setUserAgentString(
                'AgriMarket/1.0 Android Mobile')

            webview.setWebViewClient(WebViewClient())
            webview.loadUrl('http://127.0.0.1:5001')

            layout = activity.getWindow().getDecorView()
            layout.addView(webview, LayoutParams(
                LayoutParams.MATCH_PARENT,
                LayoutParams.MATCH_PARENT
            ))

    class AgriMarketApp(App):
        def build(self):
            return AndroidWebView()

# Desktop fallback (for testing on PC)
else:
    from kivy.uix.label import Label

    class AgriMarketApp(App):
        def build(self):
            layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
            layout.add_widget(Label(
                text='🌾 AgriMarket\n\nOpen http://127.0.0.1:5001\nin your browser',
                font_size='18sp', halign='center', markup=True
            ))
            return layout

if __name__ == '__main__':
    AgriMarketApp().run()
