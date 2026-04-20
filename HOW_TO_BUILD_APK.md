# How to Build AgriMarket APK

## Option 1 — GitHub Actions (Easiest, Free)

1. Create a free account at https://github.com
2. Create a new repository
3. Upload the entire `agrimarket/` folder to the repo
4. Go to **Actions** tab → **Build AgriMarket APK** → **Run workflow**
5. Wait ~20 minutes for the build
6. Download the `.apk` from the **Artifacts** section
7. Transfer to phone and install

## Option 2 — WSL on Windows (Local Build)

1. Install WSL: open PowerShell as Admin and run:
   ```
   wsl --install
   ```
2. Open WSL terminal, navigate to the project:
   ```
   cd /mnt/c/xampp/htdocs/Agripy/agrimarket
   bash build_apk_wsl.sh
   ```
3. APK will be in `bin/agrimarket-1.0.0-arm64-v8a-debug.apk`

## Option 3 — Install via Browser (No APK needed)

1. Run `python app.py`
2. Open `http://172.20.10.5:5001` on your phone (same WiFi)
3. Chrome menu → **Add to Home Screen**
4. Works like a native app!

## Installing the APK on Android

1. Transfer `.apk` to phone (USB, Google Drive, WhatsApp)
2. On phone: Settings → Security → **Allow unknown sources**
3. Open the `.apk` file and tap **Install**
4. Open **AgriMarket** from home screen

## Notes
- First build takes 15-30 minutes (downloads Android SDK/NDK)
- Subsequent builds take ~5 minutes
- APK size: ~30-50 MB
- Requires Android 5.0+ (API 21)
