"""
Pushes AgriMarket to GitHub and triggers APK build.
Run: python push_to_github.py
"""
import os, sys, subprocess, webbrowser

print("""
╔══════════════════════════════════════════╗
║   🌾 AgriMarket APK Builder              ║
║   Builds a real Android APK via GitHub   ║
╚══════════════════════════════════════════╝

STEPS:
1. Create a FREE GitHub account at https://github.com
2. Create a NEW repository named: agrimarket
3. Come back here and enter your GitHub username

""")

username = input("Enter your GitHub username: ").strip()
if not username:
    print("Username required."); sys.exit(1)

repo_url = f"https://github.com/{username}/agrimarket"
print(f"\nRepository will be: {repo_url}")

# Initialize git if needed
project_dir = os.path.dirname(os.path.abspath(__file__))
git_dir = os.path.join(project_dir, '.git')

if not os.path.exists(git_dir):
    print("\nInitializing git repository...")
    subprocess.run(['git', 'init'], cwd=project_dir, check=True)
    subprocess.run(['git', 'branch', '-M', 'main'], cwd=project_dir)

# Create .gitignore
gitignore = os.path.join(project_dir, '.gitignore')
with open(gitignore, 'w') as f:
    f.write("""__pycache__/
*.pyc
*.pyo
.env
agrimarket.db
static/uploads/*.jpg
static/uploads/*.png
static/uploads/*.gif
static/uploads/*.webp
static/qr.png
.buildozer/
bin/
""")

print("Adding files...")
subprocess.run(['git', 'add', '.'], cwd=project_dir, check=True)

try:
    subprocess.run(['git', 'commit', '-m', 'AgriMarket app - initial commit'],
                   cwd=project_dir, check=True)
except:
    pass  # already committed

print(f"\nSetting remote to {repo_url}...")
subprocess.run(['git', 'remote', 'remove', 'origin'], cwd=project_dir, capture_output=True)
subprocess.run(['git', 'remote', 'add', 'origin',
                f'https://github.com/{username}/agrimarket.git'],
               cwd=project_dir, check=True)

print("\nPushing to GitHub...")
print("(A browser window will open for GitHub login if needed)\n")
result = subprocess.run(['git', 'push', '-u', 'origin', 'main', '--force'],
                        cwd=project_dir)

if result.returncode == 0:
    actions_url = f"https://github.com/{username}/agrimarket/actions"
    print(f"""
✅ Code pushed successfully!

NOW:
1. Go to: {actions_url}
2. Click "Build AgriMarket APK"
3. Click "Run workflow" → "Run workflow"
4. Wait ~20 minutes
5. Download the APK from "Artifacts"
6. Send APK to your phone and install

Opening GitHub Actions page...
""")
    webbrowser.open(actions_url)
else:
    print(f"""
❌ Push failed. Do this manually:

1. Go to https://github.com/{username}/agrimarket
2. Click "uploading an existing file"
3. Drag the entire agrimarket folder
4. Commit changes
5. Go to Actions tab → Run workflow
""")
    webbrowser.open(f"https://github.com/{username}/agrimarket")
