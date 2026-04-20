"""
Vibe-Lens 一键启动
运行: python start.py
效果: 启动后端 + 自动打开浏览器（带划词功能）
"""
import os
import platform
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent
BACKEND = ROOT / "backend"
EXTENSION = ROOT / "extension"
BUILD = EXTENSION / "build"

def find_chrome():
    """Find Chrome/Edge executable."""
    system = platform.system()
    candidates = []
    if system == "Windows":
        for base in [os.environ.get("PROGRAMFILES", ""), os.environ.get("PROGRAMFILES(X86)", ""), os.environ.get("LOCALAPPDATA", "")]:
            if not base:
                continue
            candidates += [
                Path(base) / "Google/Chrome/Application/chrome.exe",
                Path(base) / "Microsoft/Edge/Application/msedge.exe",
            ]
    elif system == "Darwin":
        candidates = [
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
        ]
    else:
        for name in ["google-chrome", "google-chrome-stable", "chromium", "microsoft-edge"]:
            p = shutil.which(name)
            if p:
                return p

    for c in candidates:
        if c.exists():
            return str(c)
    return None


def build_extension():
    """Build extension if needed."""
    if not (BUILD / "content.js").exists():
        print("📦 构建扩展...")
        subprocess.run(["npm", "run", "build"], cwd=str(EXTENSION), shell=True, check=True)
    else:
        print("✓ 扩展已构建")


def start_backend():
    """Start uvicorn in background."""
    venv_python = BACKEND / ".venv" / ("Scripts" if platform.system() == "Windows" else "bin") / "python"
    if not venv_python.exists():
        venv_python = sys.executable

    print("🚀 启动后端 (localhost:8000)...")
    proc = subprocess.Popen(
        [str(venv_python), "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=str(BACKEND),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Wait for backend to be ready
    import urllib.request
    for i in range(30):
        try:
            urllib.request.urlopen("http://localhost:8000/health", timeout=1)
            print("✓ 后端已启动")
            return proc
        except Exception:
            time.sleep(0.5)
    print("⚠ 后端启动超时，继续...")
    return proc


def open_browser_with_extension():
    """Open Chrome with extension auto-loaded."""
    chrome = find_chrome()
    ext_path = str(BUILD.resolve())

    if chrome:
        print(f"🌐 打开浏览器 (自动加载扩展)...")
        # Create a temporary user data dir to avoid conflicts with existing Chrome
        user_data = ROOT / ".chrome-vibe"
        user_data.mkdir(exist_ok=True)
        subprocess.Popen([
            chrome,
            f"--load-extension={ext_path}",
            f"--user-data-dir={user_data.resolve()}",
            "--no-first-run",
            "--no-default-browser-check",
            "http://localhost:8000",
        ])
    else:
        print("⚠ 未找到 Chrome/Edge，请手动打开浏览器")
        print(f"  方式1: 打开 http://localhost:8000 使用 Web 版")
        print(f"  方式2: 在 chrome://extensions 加载 {ext_path}")
        webbrowser.open("http://localhost:8000")


def main():
    print("=" * 50)
    print("  ✦ Vibe-Lens · 审美雷达")
    print("=" * 50)
    print()

    # Seed database if needed
    os.chdir(str(BACKEND))
    sys.path.insert(0, str(BACKEND))
    try:
        from app.services.seed import seed_all
        seed_all()
        print("✓ 数据库就绪")
    except Exception as e:
        print(f"⚠ 数据库初始化: {e}")

    # Build extension
    build_extension()

    # Start backend
    proc = start_backend()

    # Open browser
    open_browser_with_extension()

    print()
    print("✦ Vibe-Lens 已启动！")
    print("  • Web 版: http://localhost:8000")
    print("  • 划词: 在任意网页选中文字 → 点击紫色图标")
    print("  • 按 Ctrl+C 停止")
    print()

    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\n正在停止...")
        proc.terminate()
        print("✦ 已停止")


if __name__ == "__main__":
    main()
