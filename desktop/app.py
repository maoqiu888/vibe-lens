"""
Vibe-Radar 桌面版 —— 全局划词鉴定
启动: python desktop/app.py
用法: 选中任意文字 → 按 Ctrl+Shift+Space → 弹出鉴定结果
"""
import json
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path

import httpx
from pynput import keyboard

API = "http://localhost:8000/api/v1"

# ═══════ Backend Management ═══════
backend_proc = None

def ensure_backend():
    global backend_proc
    try:
        r = httpx.get("http://localhost:8000/health", timeout=2)
        if r.status_code == 200:
            return True
    except Exception:
        pass

    print("🚀 启动后端...")
    backend_dir = Path(__file__).parent.parent / "backend"
    venv_py = backend_dir / ".venv" / "Scripts" / "python"
    if not venv_py.exists():
        venv_py = sys.executable
    backend_proc = subprocess.Popen(
        [str(venv_py), "-m", "uvicorn", "app.main:app", "--port", "8000"],
        cwd=str(backend_dir),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        try:
            httpx.get("http://localhost:8000/health", timeout=1)
            print("✓ 后端已启动")
            return True
        except Exception:
            time.sleep(0.5)
    return False


# ═══════ Clipboard ═══════
def get_clipboard():
    """Get clipboard text cross-platform."""
    root = tk.Tk()
    root.withdraw()
    try:
        text = root.clipboard_get()
    except tk.TclError:
        text = ""
    root.destroy()
    return text.strip()


def copy_selection():
    """Simulate Ctrl+C to copy selection, then read clipboard."""
    from pynput.keyboard import Controller, Key
    kb = Controller()
    kb.press(Key.ctrl)
    kb.press('c')
    kb.release('c')
    kb.release(Key.ctrl)
    time.sleep(0.15)
    return get_clipboard()


# ═══════ API Calls ═══════
def analyze_text(text):
    """Call analyze-stream SSE and collect result."""
    try:
        with httpx.stream("POST", f"{API}/vibe/analyze-stream",
                          json={"text": text, "domain": "movie",
                                "context": {"page_title": "", "page_url": ""},
                                "hesitation_ms": 1000},
                          timeout=60) as r:
            buf = ""
            event = ""
            for chunk in r.iter_text():
                buf += chunk
                lines = buf.split("\n")
                buf = lines.pop()
                for line in lines:
                    if line.startswith("event: "):
                        event = line[7:].strip()
                    elif line.startswith("data: ") and event:
                        data = json.loads(line[6:])
                        if event == "done":
                            return data
                        elif event == "error":
                            return {"error": data.get("message", "分析失败")}
                        event = ""
    except Exception as e:
        return {"error": f"后端连接失败: {e}"}
    return {"error": "未收到结果"}


def send_action(action, result):
    try:
        httpx.post(f"{API}/vibe/action", json={
            "action": action,
            "matched_tag_ids": [t["tag_id"] for t in result.get("matched_tags", [])],
            "text_hash": result.get("text_hash", ""),
            "read_ms": 3000,
            "item_name": result.get("item_name", ""),
            "domain": "movie",
            "match_score": result.get("match_score", 0),
            "verdict": result.get("verdict", ""),
        }, timeout=5)
    except Exception:
        pass


# ═══════ Result Window ═══════
class ResultWindow:
    def __init__(self):
        self.root = None
        self.result = None

    def show_loading(self, text):
        self._close()
        self.root = tk.Tk()
        self.root.title("Vibe-Radar")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#1a1233")

        # Position near mouse
        x, y = self.root.winfo_pointerx() + 20, self.root.winfo_pointery() + 20
        self.root.geometry(f"360x120+{x}+{y}")

        frame = tk.Frame(self.root, bg="#1a1233", padx=20, pady=16)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text=f'正在鉴定: "{text[:20]}..."',
                 fg="#a29bfe", bg="#1a1233", font=("Microsoft YaHei", 11)).pack()
        tk.Label(frame, text="✦ 搜索 → 识别 → 分析",
                 fg="#6c5ce7", bg="#1a1233", font=("Microsoft YaHei", 9)).pack(pady=(8, 0))

        # Escape to close
        self.root.bind("<Escape>", lambda e: self._close())
        self.root.update()

    def show_result(self, data):
        self._close()
        if "error" in data:
            self._show_error(data["error"])
            return

        self.result = data
        self.root = tk.Tk()
        self.root.title("Vibe-Radar")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#1a1233")

        x, y = self.root.winfo_pointerx() - 180, self.root.winfo_pointery() + 20
        screen_w = self.root.winfo_screenwidth()
        if x + 380 > screen_w:
            x = screen_w - 400
        if x < 0:
            x = 20
        self.root.geometry(f"380x+{x}+{y}")

        frame = tk.Frame(self.root, bg="#1a1233", padx=20, pady=16)
        frame.pack(fill="both", expand=True)

        # Score + Verdict
        top = tk.Frame(frame, bg="#1a1233")
        top.pack(fill="x")
        tk.Label(top, text=f"{data['match_score']}%",
                 fg="#a29bfe", bg="#1a1233", font=("Microsoft YaHei", 32, "bold")).pack(side="left")
        v = data.get("verdict", "看心情")
        vc = {"追": "#55efc4", "跳过": "#ff7675"}.get(v, "#ffeaa7")
        tk.Label(top, text=f"  {v}", fg=vc, bg="#1a1233",
                 font=("Microsoft YaHei", 14, "bold")).pack(side="left", padx=(8, 0))

        # Item name
        if data.get("item_name"):
            tk.Label(frame, text=data["item_name"], fg="#888",
                     bg="#1a1233", font=("Microsoft YaHei", 9)).pack(anchor="w", pady=(4, 0))

        # Roast
        roast = data.get("roast") or data.get("summary", "")
        roast_label = tk.Label(frame, text=roast, fg="#e0dced", bg="#1a1233",
                               font=("Microsoft YaHei", 11), wraplength=340, justify="left")
        roast_label.pack(anchor="w", pady=(10, 0))

        # Reasons
        for r in data.get("reasons", []):
            tk.Label(frame, text=f"· {r}", fg="#8a85b0", bg="#1a1233",
                     font=("Microsoft YaHei", 9), wraplength=340, justify="left").pack(anchor="w", pady=1)

        # Action buttons
        btn_frame = tk.Frame(frame, bg="#1a1233")
        btn_frame.pack(fill="x", pady=(12, 0))

        star_btn = tk.Button(btn_frame, text="👍 太准了吧", fg="#55efc4", bg="#1e2a35",
                             activeforeground="#55efc4", activebackground="#253540",
                             font=("Microsoft YaHei", 10, "bold"), bd=0, padx=16, pady=6,
                             command=lambda: self._action("star"))
        star_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))

        bomb_btn = tk.Button(btn_frame, text="🤔 差点意思", fg="#ff7675", bg="#2a1e25",
                             activeforeground="#ff7675", activebackground="#352530",
                             font=("Microsoft YaHei", 10, "bold"), bd=0, padx=16, pady=6,
                             command=lambda: self._action("bomb"))
        bomb_btn.pack(side="left", expand=True, fill="x", padx=(4, 0))

        # Close hint
        tk.Label(frame, text="按 Esc 关闭", fg="#555", bg="#1a1233",
                 font=("Microsoft YaHei", 8)).pack(pady=(8, 0))

        self.root.bind("<Escape>", lambda e: self._close())
        # Auto-close after 30s
        self.root.after(30000, self._close)
        self.root.update()
        self.root.mainloop()

    def _action(self, action):
        if self.result:
            threading.Thread(target=send_action, args=(action, self.result), daemon=True).start()
        self._close()

    def _show_error(self, msg):
        self.root = tk.Tk()
        self.root.title("Vibe-Radar")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2a1e1e")
        x, y = self.root.winfo_pointerx() + 20, self.root.winfo_pointery() + 20
        self.root.geometry(f"300x60+{x}+{y}")
        tk.Label(self.root, text=msg, fg="#ff7675", bg="#2a1e1e",
                 font=("Microsoft YaHei", 11)).pack(expand=True)
        self.root.after(3000, self._close)
        self.root.bind("<Escape>", lambda e: self._close())
        self.root.mainloop()

    def _close(self):
        if self.root:
            try:
                self.root.destroy()
            except Exception:
                pass
            self.root = None


# ═══════ Global Hotkey ═══════
win = ResultWindow()


def handle_hotkey():
    text = copy_selection()
    if not text or len(text) < 2 or len(text) > 200:
        return

    # Show loading in main thread
    def show():
        win.show_loading(text)
    threading.Thread(target=show, daemon=True).start()
    time.sleep(0.3)

    # Analyze
    result = analyze_text(text)

    # Show result
    win.show_result(result)


# ═══════ System Tray ═══════
def create_tray():
    import pystray
    from PIL import Image, ImageDraw

    # Create a simple icon
    img = Image.new('RGB', (64, 64), '#6c5ce7')
    draw = ImageDraw.Draw(img)
    draw.ellipse([16, 16, 48, 48], fill='#a29bfe')
    draw.ellipse([24, 24, 40, 40], fill='#fd79a8')

    def on_quit(icon, item):
        icon.stop()
        if backend_proc:
            backend_proc.terminate()
        sys.exit(0)

    menu = pystray.Menu(
        pystray.MenuItem("Vibe-Radar · 审美雷达", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("快捷键: Ctrl+Shift+Space", None, enabled=False),
        pystray.MenuItem("选中文字后按快捷键即可鉴定", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("打开 Web 版", lambda: __import__('webbrowser').open("http://localhost:8000")),
        pystray.MenuItem("退出", on_quit),
    )

    icon = pystray.Icon("vibe-radar", img, "Vibe-Radar", menu)
    return icon


# ═══════ Main ═══════
def main():
    print("=" * 50)
    print("  ✦ Vibe-Radar 桌面版")
    print("=" * 50)
    print()

    # Ensure backend
    if not ensure_backend():
        print("❌ 后端启动失败")
        sys.exit(1)

    print()
    print("✦ 使用方法:")
    print("  1. 在任意地方选中文字（浏览器、微信、PDF...）")
    print("  2. 按 Ctrl+Shift+Space")
    print("  3. 弹出鉴定结果")
    print()
    print("系统托盘图标已运行，右键可退出")
    print()

    # Start hotkey listener (Ctrl+Shift+Space)
    def on_hotkey():
        threading.Thread(target=handle_hotkey, daemon=True).start()

    hotkey = keyboard.GlobalHotKeys({"<ctrl>+<shift>+<space>": on_hotkey})
    hotkey.daemon = True
    hotkey.start()
    print("✓ 快捷键监听已启动 (Ctrl+Shift+Space)")

    # Start tray icon (blocks)
    tray = create_tray()
    tray.run()


if __name__ == "__main__":
    main()
