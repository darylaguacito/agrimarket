"""
Generates a minimal native Android WebView project (Gradle).
The app embeds the Flask server assets and loads them via WebView.
Run by GitHub Actions before building the APK.
"""
import os, shutil, textwrap

ROOT    = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..', 'android-app')
ROOT    = os.path.abspath(ROOT)
APP_DIR = os.path.join(ROOT, 'app')
SRC     = os.path.join(APP_DIR, 'src', 'main')
JAVA    = os.path.join(SRC, 'java', 'com', 'agrimarket', 'app')
RES     = os.path.join(SRC, 'res')

def mkdir(p): os.makedirs(p, exist_ok=True)
def write(path, content):
    mkdir(os.path.dirname(path))
    with open(path, 'w') as f:
        f.write(textwrap.dedent(content).lstrip())

# ── settings.gradle ──────────────────────────────────────
write(os.path.join(ROOT, 'settings.gradle'), """
    pluginManagement {
        repositories {
            google(); mavenCentral(); gradlePluginPortal()
        }
    }
    dependencyResolutionManagement {
        repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
        repositories { google(); mavenCentral() }
    }
    rootProject.name = "AgriMarket"
    include ':app'
""")

# ── build.gradle (root) ───────────────────────────────────
write(os.path.join(ROOT, 'build.gradle'), """
    plugins {
        id 'com.android.application' version '8.2.2' apply false
    }
""")

# ── gradle wrapper ────────────────────────────────────────
write(os.path.join(ROOT, 'gradle', 'wrapper', 'gradle-wrapper.properties'), """
    distributionBase=GRADLE_USER_HOME
    distributionPath=wrapper/dists
    distributionUrl=https\\://services.gradle.org/distributions/gradle-8.4-bin.zip
    zipStoreBase=GRADLE_USER_HOME
    zipStorePath=wrapper/dists
""")

# Download gradlew
import urllib.request, stat
gw_url = 'https://raw.githubusercontent.com/gradle/gradle/v8.4.0/gradlew'
gw_path = os.path.join(ROOT, 'gradlew')
try:
    urllib.request.urlretrieve(gw_url, gw_path)
    os.chmod(gw_path, os.stat(gw_path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
except Exception as e:
    print(f"Warning: could not download gradlew: {e}")
    # Write a minimal gradlew shell script
    with open(gw_path, 'w') as f:
        f.write('#!/bin/sh\nexec gradle "$@"\n')
    os.chmod(gw_path, 0o755)

# ── app/build.gradle ─────────────────────────────────────
write(os.path.join(APP_DIR, 'build.gradle'), """
    plugins {
        id 'com.android.application'
    }
    android {
        namespace 'com.agrimarket.app'
        compileSdk 34
        defaultConfig {
            applicationId 'com.agrimarket.app'
            minSdk 24
            targetSdk 34
            versionCode 1
            versionName '1.0.0'
        }
        buildTypes {
            debug { minifyEnabled false }
            release {
                minifyEnabled false
                proguardFiles getDefaultProguardFile('proguard-android-optimize.txt')
            }
        }
        compileOptions {
            sourceCompatibility JavaVersion.VERSION_17
            targetCompatibility JavaVersion.VERSION_17
        }
    }
    dependencies {
        implementation 'androidx.appcompat:appcompat:1.6.1'
        implementation 'androidx.swiperefreshlayout:swiperefreshlayout:1.1.0'
    }
""")

# ── AndroidManifest.xml ───────────────────────────────────
write(os.path.join(SRC, 'AndroidManifest.xml'), """
    <?xml version="1.0" encoding="utf-8"?>
    <manifest xmlns:android="http://schemas.android.com/apk/res/android">
        <uses-permission android:name="android.permission.INTERNET"/>
        <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>
        <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>
        <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION"/>
        <uses-permission android:name="android.permission.CAMERA"/>
        <application
            android:allowBackup="true"
            android:icon="@mipmap/ic_launcher"
            android:label="AgriMarket"
            android:theme="@style/Theme.AppCompat.NoActionBar"
            android:usesCleartextTraffic="true">
            <activity
                android:name=".MainActivity"
                android:exported="true"
                android:configChanges="orientation|screenSize|keyboardHidden"
                android:windowSoftInputMode="adjustResize">
                <intent-filter>
                    <action android:name="android.intent.action.MAIN"/>
                    <category android:name="android.intent.category.LAUNCHER"/>
                </intent-filter>
            </activity>
        </application>
    </manifest>
""")

# ── MainActivity.java ─────────────────────────────────────
write(os.path.join(JAVA, 'MainActivity.java'), """
    package com.agrimarket.app;

    import android.annotation.SuppressLint;
    import android.content.SharedPreferences;
    import android.os.Bundle;
    import android.view.KeyEvent;
    import android.webkit.*;
    import androidx.appcompat.app.AppCompatActivity;
    import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

    public class MainActivity extends AppCompatActivity {

        private WebView webView;
        private SwipeRefreshLayout swipeRefresh;
        private static final String PREFS = "agrimarket";
        private static final String KEY_URL = "server_url";

        @SuppressLint({"SetJavaScriptEnabled","JavascriptInterface"})
        @Override
        protected void onCreate(Bundle savedInstanceState) {
            super.onCreate(savedInstanceState);
            setContentView(R.layout.activity_main);

            swipeRefresh = findViewById(R.id.swipeRefresh);
            webView      = findViewById(R.id.webView);

            WebSettings s = webView.getSettings();
            s.setJavaScriptEnabled(true);
            s.setDomStorageEnabled(true);
            s.setGeolocationEnabled(true);
            s.setAllowFileAccess(true);
            s.setDatabaseEnabled(true);
            s.setMediaPlaybackRequiresUserGesture(false);
            s.setCacheMode(WebSettings.LOAD_DEFAULT);
            s.setUserAgentString("AgriMarket/1.0 Android");

            // Bridge so setup.html can call Android.saveUrl(url)
            webView.addJavascriptInterface(new Object() {
                @JavascriptInterface
                public void saveUrl(String url) {
                    getSharedPreferences(PREFS, MODE_PRIVATE)
                        .edit().putString(KEY_URL, url).apply();
                    runOnUiThread(() -> webView.loadUrl(url));
                }
                @JavascriptInterface
                public String getSavedUrl() {
                    return getSharedPreferences(PREFS, MODE_PRIVATE)
                        .getString(KEY_URL, "");
                }
                @JavascriptInterface
                public void clearUrl() {
                    getSharedPreferences(PREFS, MODE_PRIVATE)
                        .edit().remove(KEY_URL).apply();
                }
            }, "Android");

            webView.setWebViewClient(new WebViewClient() {
                @Override
                public void onPageFinished(WebView view, String url) {
                    swipeRefresh.setRefreshing(false);
                }
                @Override
                public void onReceivedError(WebView view, WebResourceRequest req,
                                            WebResourceError err) {
                    if (req.isForMainFrame()) {
                        view.loadUrl("file:///android_asset/offline.html");
                    }
                }
            });

            webView.setWebChromeClient(new WebChromeClient() {
                @Override
                public void onGeolocationPermissionsShowPrompt(String origin,
                        GeolocationPermissions.Callback callback) {
                    callback.invoke(origin, true, false);
                }
            });

            swipeRefresh.setColorSchemeColors(0xFF2E7D32);
            swipeRefresh.setOnRefreshListener(() -> webView.reload());

            String savedUrl = getSharedPreferences(PREFS, MODE_PRIVATE)
                    .getString(KEY_URL, null);
            if (savedUrl != null && !savedUrl.isEmpty()) {
                webView.loadUrl(savedUrl);
            } else {
                webView.loadUrl("file:///android_asset/setup.html");
            }
        }

        @Override
        public boolean onKeyDown(int keyCode, KeyEvent event) {
            if (keyCode == KeyEvent.KEYCODE_BACK && webView.canGoBack()) {
                webView.goBack();
                return true;
            }
            return super.onKeyDown(keyCode, event);
        }
    }
""")

# ── activity_main.xml ─────────────────────────────────────
write(os.path.join(RES, 'layout', 'activity_main.xml'), """
    <?xml version="1.0" encoding="utf-8"?>
    <androidx.swiperefreshlayout.widget.SwipeRefreshLayout
        xmlns:android="http://schemas.android.com/apk/res/android"
        android:id="@+id/swipeRefresh"
        android:layout_width="match_parent"
        android:layout_height="match_parent">
        <WebView
            android:id="@+id/webView"
            android:layout_width="match_parent"
            android:layout_height="match_parent"/>
    </androidx.swiperefreshlayout.widget.SwipeRefreshLayout>
""")

# ── colors.xml ────────────────────────────────────────────
write(os.path.join(RES, 'values', 'colors.xml'), """
    <?xml version="1.0" encoding="utf-8"?>
    <resources>
        <color name="green">#2E7D32</color>
        <color name="white">#FFFFFF</color>
    </resources>
""")

# ── Setup HTML (first-launch IP entry) ───────────────────
assets = os.path.join(SRC, 'assets')
mkdir(assets)
write(os.path.join(assets, 'setup.html'), """
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>AgriMarket Setup</title>
    <style>
      body{font-family:system-ui,sans-serif;background:#F9FBF9;display:flex;
           align-items:center;justify-content:center;min-height:100vh;margin:0}
      .card{background:white;border-radius:16px;padding:2rem;max-width:340px;
            width:90%;box-shadow:0 4px 20px rgba(0,0,0,.1);text-align:center}
      h1{color:#2E7D32;margin-bottom:.5rem}
      p{color:#6b7280;font-size:.9rem;margin-bottom:1.5rem}
      input{width:100%;padding:.75rem;border:1px solid #E8F5E9;border-radius:8px;
            font-size:1rem;margin-bottom:1rem;box-sizing:border-box;outline:none}
      input:focus{border-color:#2E7D32}
      button{background:#2E7D32;color:white;border:none;padding:.75rem 2rem;
             border-radius:999px;font-size:1rem;cursor:pointer;width:100%}
      .hint{font-size:.78rem;color:#9ca3af;margin-top:1rem}
    </style>
    </head>
    <body>
    <div class="card">
      <div style="font-size:3rem">🌾</div>
      <h1>AgriMarket</h1>
      <p>Enter the IP address of the computer running the AgriMarket server.</p>
      <input type="text" id="ip" placeholder="e.g. 192.168.1.5" inputmode="decimal">
      <input type="number" id="port" value="5001" placeholder="Port (default 5001)">
      <button onclick="connect()">Connect</button>
      <p class="hint">Make sure your phone and the server are on the same WiFi network. Run <b>ipconfig</b> on the server PC to find the IP.</p>
    </div>
    <script>
    // Pre-fill saved URL if any
    window.onload = function(){
      if(window.Android){
        var saved = Android.getSavedUrl();
        if(saved){
          var parts = saved.replace('http://','').split(':');
          document.getElementById('ip').value   = parts[0] || '';
          document.getElementById('port').value = parts[1] || '5001';
        }
      }
    };
    function connect(){
      var ip   = document.getElementById('ip').value.trim();
      var port = document.getElementById('port').value.trim() || '5001';
      if(!ip){ alert('Please enter the server IP address'); return; }
      var url = 'http://' + ip + ':' + port;
      if(window.Android){
        Android.saveUrl(url);  // saves and navigates via Java
      } else {
        window.location.href = url;
      }
    }
    </script>
    </body>
    </html>
""")

# ── Offline HTML ──────────────────────────────────────────
write(os.path.join(assets, 'offline.html'), """
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Offline</title>
    <style>
      body{font-family:system-ui,sans-serif;background:#F9FBF9;display:flex;
           align-items:center;justify-content:center;min-height:100vh;margin:0;text-align:center}
      h1{color:#2E7D32} p{color:#6b7280}
      button{background:#2E7D32;color:white;border:none;padding:.75rem 2rem;
             border-radius:999px;font-size:1rem;cursor:pointer;margin-top:1rem}
    </style>
    </head>
    <body>
    <div>
      <div style="font-size:4rem">🌾</div>
      <h1>Cannot connect</h1>
      <p>Make sure the server is running<br>and you're on the same WiFi.</p>
      <button onclick="history.back()">Go Back</button>
      <button onclick="location.reload()">Retry</button>
    </div>
    </body>
    </html>
""")

# ── App icon (copy from static) ───────────────────────────
icon_src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'static', 'icon-192.png')
for density, size in [('mdpi',48),('hdpi',72),('xhdpi',96),('xxhdpi',144),('xxxhdpi',192)]:
    dest = os.path.join(RES, f'mipmap-{density}', 'ic_launcher.png')
    mkdir(os.path.dirname(dest))
    if os.path.exists(icon_src):
        shutil.copy(icon_src, dest)

print(f"✅ Android project generated at: {ROOT}")
