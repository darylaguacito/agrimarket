[app]
title = AgriMarket
package.name = agrimarket
package.domain = com.agrimarket.app
source.dir = .
source.include_exts = py,png,jpg,jpeg,gif,webp,kv,atlas,db,sql,json,css,js,html,txt
source.include_patterns = templates/**,static/**,routes/**,*.py,*.db

version = 1.0.0
requirements = python3,kivy,flask,flask-login,flask-wtf,bcrypt,werkzeug,python-dotenv,flask-cors,jinja2,itsdangerous,click,blinker,wtforms,markupsafe

orientation = portrait
fullscreen = 0
android.minapi = 21
android.api = 33
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a

android.permissions = INTERNET, ACCESS_NETWORK_STATE, ACCESS_FINE_LOCATION, ACCESS_COARSE_LOCATION, CAMERA, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE

android.features = android.hardware.location.gps

# App icon and presplash
#icon.filename = %(source.dir)s/static/icon.png
#presplash.filename = %(source.dir)s/static/splash.png

android.presplash_color = #2E7D32
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
