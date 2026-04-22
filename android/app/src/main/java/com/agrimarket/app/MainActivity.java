package com.agrimarket.app;

import android.annotation.SuppressLint;
import android.os.Bundle;
import android.view.KeyEvent;
import android.webkit.GeolocationPermissions;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import androidx.appcompat.app.AppCompatActivity;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

public class MainActivity extends AppCompatActivity {

    private WebView webView;
    private SwipeRefreshLayout swipeRefresh;
    private static final String PREFS   = "agrimarket";
    private static final String KEY_URL = "server_url";

    @SuppressLint({"SetJavaScriptEnabled", "JavascriptInterface"})
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        swipeRefresh = findViewById(R.id.swipeRefresh);
        webView      = findViewById(R.id.webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setGeolocationEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setDatabaseEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setUserAgentString("AgriMarket/1.0 Android");

        // JS bridge so setup.html can save the server URL
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
                runOnUiThread(() -> webView.loadUrl("file:///android_asset/setup.html"));
            }
        }, "Android");

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                swipeRefresh.setRefreshing(false);
            }
            @Override
            public void onReceivedError(WebView view, WebResourceRequest request,
                                        WebResourceError error) {
                if (request.isForMainFrame()) {
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
