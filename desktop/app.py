"""
Vibe-Radar 桌面版 —— 全局划词鉴定
启动: backend/.venv/Scripts/python desktop/app.py
用法: 在任意地方选中文字 → 鼠标旁自动弹出按钮 → 点击鉴定
"""
import json
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path

import httpx
from pynput import mouse, keyboard as kb

API = "http://localhost:8000/api/v1"
MIN_LEN = 2
MAX_LEN = 200

# ═══════ Backend ═══════
backend_proc = None

def ensure_backend():
    global backend_proc
    try:
        r = httpx.get("http://localhost:8000/health", timeout=2)
        if r.status_code == 200:
            return True
    except Exception:
        pass
    print("[*] Starting backend...")
    backend_dir = Path(__file__).parent.parent / "backend"
    venv_py = backend_dir / ".venv" / "Scripts" / "python"
    if not venv_py.exists():
        venv_py = sys.executable
    backend_proc = subprocess.Popen(
        [str(venv_py), "-m", "uvicorn", "app.main:app", "--port", "8000"],
        cwd=str(backend_dir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        try:
            httpx.get("http://localhost:8000/health", timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False


# ═══════ Clipboard ═══════
_last_clipboard = ""

def get_clipboard():
    try:
        root = tk.Tk()
        root.withdraw()
        text = root.clipboard_get()
        root.destroy()
        return text.strip()
    except Exception:
        return ""

def simulate_copy():
    """Simulate Ctrl+C to copy current selection."""
    ctrl = kb.Controller()
    ctrl.press(kb.Key.ctrl)
    ctrl.press('c')
    ctrl.release('c')
    ctrl.release(kb.Key.ctrl)
    time.sleep(0.1)


# ═══════ Floating Icon ═══════
icon_win = None
result_win = None

def show_icon(x, y, text):
    """Show floating purple button near mouse."""
    global icon_win
    hide_icon()

    icon_win = tk.Tk()
    icon_win.overrideredirect(True)
    icon_win.attributes("-topmost", True)
    icon_win.attributes("-alpha", 0.95)
    icon_win.configure(bg="#6c5ce7")
    icon_win.geometry(f"36x36+{x+10}+{y-45}")

    btn = tk.Label(icon_win, text="✦", fg="white", bg="#6c5ce7",
                   font=("Arial", 16, "bold"), cursor="hand2")
    btn.pack(expand=True, fill="both")
    btn.bind("<Button-1>", lambda e: on_icon_click(text))

    # Rounded look
    icon_win.wm_attributes("-transparentcolor", "")

    # Auto-hide after 5s
    icon_win.after(5000, hide_icon)
    icon_win.mainloop()


def hide_icon():
    global icon_win
    if icon_win:
        try:
            icon_win.destroy()
        except Exception:
            pass
        icon_win = None


def on_icon_click(text):
    hide_icon()
    threading.Thread(target=do_analyze, args=(text,), daemon=True).start()


# ═══════ Analysis ═══════
def do_analyze(text):
    # Show loading
    show_window_loading(text)

    # Call API
    result = call_analyze(text)

    # Show result
    show_window_result(result, text)


def call_analyze(text):
    try:
        with httpx.stream("POST", f"{API}/vibe/analyze-stream",
                          json={"text": text, "domain": "movie",
                                "context": {"page_title": "", "page_url": ""},
                                "hesitation_ms": 1000},
                          timeout=60) as r:
            buf, event = "", ""
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
                            return {"error": data.get("message", "error")}
                        event = ""
    except Exception as e:
        return {"error": str(e)}
    return {"error": "no result"}


def send_action(action, result):
    try:
        httpx.post(f"{API}/vibe/action", json={
            "action": action,
            "matched_tag_ids": [t["tag_id"] for t in result.get("matched_tags", [])],
            "text_hash": result.get("text_hash", ""),
            "read_ms": 3000, "item_name": result.get("item_name", ""),
            "domain": "movie", "match_score": result.get("match_score", 0),
            "verdict": result.get("verdict", ""),
        }, timeout=5)
    except Exception:
        pass


# ═══════ Windows ═══════
_current_win = None

def _close_current():
    global _current_win
    if _current_win:
        try: _current_win.destroy()
        except: pass
        _current_win = None


def show_window_loading(text):
    global _current_win
    _close_current()

    w = tk.Tk()
    _current_win = w
    w.title("Vibe-Radar")
    w.overrideredirect(True)
    w.attributes("-topmost", True)
    w.configure(bg="#1a1233")

    x = w.winfo_pointerx() + 20
    y = w.winfo_pointery() + 20
    w.geometry(f"340x100+{x}+{y}")

    f = tk.Frame(w, bg="#1a1233", padx=20, pady=16)
    f.pack(fill="both", expand=True)
    display = text[:30] + "..." if len(text) > 30 else text
    tk.Label(f, text=f'"{display}"', fg="#c8c0ff", bg="#1a1233",
             font=("Microsoft YaHei", 11)).pack()
    tk.Label(f, text="搜索 → 识别 → 分析...", fg="#6c5ce7", bg="#1a1233",
             font=("Microsoft YaHei", 9)).pack(pady=(8, 0))
    w.bind("<Escape>", lambda e: _close_current())
    w.update()


def show_window_result(data, text):
    global _current_win
    _close_current()

    if "error" in data:
        w = tk.Tk()
        _current_win = w
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.configure(bg="#2a1e1e")
        x, y = w.winfo_pointerx() + 20, w.winfo_pointery() + 20
        w.geometry(f"300x50+{x}+{y}")
        tk.Label(w, text=data["error"], fg="#ff7675", bg="#2a1e1e",
                 font=("Microsoft YaHei", 11)).pack(expand=True)
        w.after(3000, _close_current)
        w.bind("<Escape>", lambda e: _close_current())
        w.mainloop()
        return

    w = tk.Tk()
    _current_win = w
    w.title("Vibe-Radar")
    w.overrideredirect(True)
    w.attributes("-topmost", True)
    w.configure(bg="#1a1233")

    x = w.winfo_pointerx() - 180
    y = w.winfo_pointery() + 20
    sw = w.winfo_screenwidth()
    x = max(20, min(x, sw - 400))
    w.geometry(f"380x+{x}+{y}")

    f = tk.Frame(w, bg="#1a1233", padx=20, pady=16)
    f.pack(fill="both", expand=True)

    # Top: score + verdict
    top = tk.Frame(f, bg="#1a1233")
    top.pack(fill="x")
    tk.Label(top, text=f"{data['match_score']}%", fg="#a29bfe", bg="#1a1233",
             font=("Microsoft YaHei", 32, "bold")).pack(side="left")
    v = data.get("verdict", "")
    vc = {"追": "#55efc4", "跳过": "#ff7675"}.get(v, "#ffeaa7")
    tk.Label(top, text=f"  {v}", fg=vc, bg="#1a1233",
             font=("Microsoft YaHei", 14, "bold")).pack(side="left", padx=(8, 0))

    # Item name
    if data.get("item_name"):
        tk.Label(f, text=data["item_name"], fg="#888", bg="#1a1233",
                 font=("Microsoft YaHei", 9)).pack(anchor="w", pady=(4, 0))

    # Roast
    roast = data.get("roast") or data.get("summary", "")
    tk.Label(f, text=roast, fg="#e0dced", bg="#1a1233",
             font=("Microsoft YaHei", 11), wraplength=340, justify="left"
             ).pack(anchor="w", pady=(10, 0))

    # Reasons
    for r in data.get("reasons", []):
        tk.Label(f, text=f"  {r}", fg="#8a85b0", bg="#1a1233",
                 font=("Microsoft YaHei", 9), wraplength=340, justify="left"
                 ).pack(anchor="w", pady=1)

    # Buttons
    bf = tk.Frame(f, bg="#1a1233")
    bf.pack(fill="x", pady=(12, 0))

    def do_action(action):
        threading.Thread(target=send_action, args=(action, data), daemon=True).start()
        _close_current()

    tk.Button(bf, text="👍 太准了吧", fg="#55efc4", bg="#1e2a35",
              activeforeground="#55efc4", activebackground="#253540",
              font=("Microsoft YaHei", 10, "bold"), bd=0, padx=16, pady=6,
              command=lambda: do_action("star")).pack(side="left", expand=True, fill="x", padx=(0, 4))
    tk.Button(bf, text="🤔 差点意思", fg="#ff7675", bg="#2a1e25",
              activeforeground="#ff7675", activebackground="#352530",
              font=("Microsoft YaHei", 10, "bold"), bd=0, padx=16, pady=6,
              command=lambda: do_action("bomb")).pack(side="left", expand=True, fill="x", padx=(4, 0))

    tk.Label(f, text="按 Esc 关闭", fg="#555", bg="#1a1233",
             font=("Microsoft YaHei", 8)).pack(pady=(8, 0))

    w.bind("<Escape>", lambda e: _close_current())
    w.after(30000, _close_current)
    w.mainloop()


# ═══════ Mouse Monitor ═══════
_mouse_down_pos = None
_mouse_down_time = 0

def on_mouse_down(x, y, button, pressed):
    global _mouse_down_pos, _mouse_down_time
    if pressed and button == mouse.Button.left:
        _mouse_down_pos = (x, y)
        _mouse_down_time = time.time()
    elif not pressed and button == mouse.Button.left:
        on_mouse_up(x, y)

def on_mouse_up(x, y):
    global _last_clipboard
    if _mouse_down_pos is None:
        return

    # Only trigger if mouse moved (drag select) and took >100ms
    dx = abs(x - _mouse_down_pos[0])
    dy = abs(y - _mouse_down_pos[1])
    dt = time.time() - _mouse_down_time
    if dx + dy < 5 or dt < 0.1:
        return

    # Save old clipboard, simulate Ctrl+C, check new
    old_clip = get_clipboard()
    simulate_copy()
    new_clip = get_clipboard()

    if new_clip and new_clip != old_clip and MIN_LEN <= len(new_clip) <= MAX_LEN:
        _last_clipboard = new_clip
        # Show icon in a new thread (tkinter needs main-ish thread)
        threading.Thread(target=show_icon, args=(x, y, new_clip), daemon=True).start()


# ═══════ Tray ═══════
def create_tray():
    import pystray
    from PIL import Image, ImageDraw

    img = Image.new('RGB', (64, 64), '#6c5ce7')
    draw = ImageDraw.Draw(img)
    draw.ellipse([16, 16, 48, 48], fill='#a29bfe')
    draw.ellipse([24, 24, 40, 40], fill='#fd79a8')

    def on_quit(icon, item):
        icon.stop()
        if backend_proc:
            backend_proc.terminate()
        import os
        os._exit(0)

    menu = pystray.Menu(
        pystray.MenuItem("Vibe-Radar", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("选中文字即可鉴定", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("打开 Web 版",
                         lambda icon, item: __import__('webbrowser').open("http://localhost:8000")),
        pystray.MenuItem("退出", on_quit),
    )
    return pystray.Icon("vibe-radar", img, "Vibe-Radar", menu)


# ═══════ Main ═══════
def main():
    print("=" * 45)
    print("  Vibe-Radar Desktop")
    print("=" * 45)

    if not ensure_backend():
        print("[!] Backend failed to start")
        sys.exit(1)

    print("[OK] Backend ready")
    print()
    print("Usage:")
    print("  Select text anywhere -> icon appears -> click to analyze")
    print()
    print("Tray icon running. Right-click to exit.")

    # Mouse listener
    mouse_listener = mouse.Listener(on_click=on_mouse_down)
    mouse_listener.daemon = True
    mouse_listener.start()

    # Tray (blocks)
    tray = create_tray()
    tray.run()


if __name__ == "__main__":
    main()
