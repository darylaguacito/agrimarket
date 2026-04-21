[app]
title = AgriMarket
package.name = agrimarket
package.domain = com.agrimarket.app
source.dir = .
source.include_exts = py,png,jpg,jpeg,gif,webp,kv,atlas,db,json,css,js,html,txt
source.include_patterns = templates/**,static/**,routes/**,*.py,*.db

version = 1.0.0

# All Python packages the app needs
requirements = python3,kivy==2.3.0,flask==3.0.3,flask_login,flask_wtf,bcrypt,werkzeug,python_dotenv,flask_cors,jinja2,itsdangerous,click,blinker,wtforms,markupsafe,requests,urllib3,certifi,charset_normalizer,idna

orientation = portrait
fullscreen = 0

# Icons
icon.filename = %(source.dir)s/static/icon.png
presplash.filename = %(source.dir)s/static/icon.png
android.presplash_color = #2E7D32

# Android config
android.minapi = 24
android.api = 34
android.ndk = 25b
android.archs = arm64-v8a

android.permissions = INTERNET, ACCESS_NETWORK_STATE, ACCESS_FINE_LOCATION, ACCESS_COARSE_LOCATION, CAMERA, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE
android.features = android.hardware.location.gps
android.allow_backup = True

# Gradle
android.gradle_dependencies = com.android.support:support-v4:28.0.0
android.enable_androidx = True

[buildozer]
log_level = 2
warn_on_root = 1
