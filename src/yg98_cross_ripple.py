import ctypes
import ctypes.wintypes as wt
import hid
import time
import threading
import tkinter as tk
from tkinter import colorchooser, simpledialog, messagebox
import json
import os
import sys
import winreg
import struct
from pathlib import Path

def resource_path(relative_path):
    """Return asset path for source mode and PyInstaller one-file mode."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        # src/yg98_cross_ripple.py -> repo root
        base = Path(__file__).resolve().parent.parent
    return str(base / relative_path)

ICON_PATH = resource_path(Path("assets") / "YG98CrossRipple.ico")

VID = 0x05AC
PID = 0x024F

MATRIX_LEN = 126
ROWS = 6
COLS = 21

BASE = bytearray(520)
BASE[0] = 0x07
BASE[1] = 0x07

FPS = 30.0
DT = 1.0 / FPS

# GUI 可即時調整
settings_lock = threading.Lock()
settings = {
    "press_color": (255, 70, 170),   # 粉紅
    "outer_color": (145, 55, 255),   # 紫
    "speed": 8.5,
    "life": 1.05,
    "gradient_strength": 0.72,
}

running = True
ripples = []
lock = threading.Lock()

# ------------------------------------------------------------
# YG98 真實 6 x 21 LED matrix
# 這次不再用 pynput 的 Key.left / Key.enter 去猜，
# 而是直接用 Windows low-level keyboard hook 的 scan code
# + extended flag 區分：
#   主鍵盤 Enter vs NumPad Enter
#   方向鍵 vs NumPad 2/4/6/8
#   NumLock ON/OFF
#   左/右 Shift
# ------------------------------------------------------------

# key = (scanCode, extendedFlag)
SCAN_TO_LED = {
    # Row 0 : 0~20
    (0x01, 0): 0,   # Esc
    (0x3B, 0): 1,   # F1
    (0x3C, 0): 2,
    (0x3D, 0): 3,
    (0x3E, 0): 4,
    (0x3F, 0): 5,
    (0x40, 0): 6,
    (0x41, 0): 7,
    (0x42, 0): 8,
    (0x43, 0): 9,
    (0x44, 0): 10,
    (0x57, 0): 11,
    (0x58, 0): 12,
    (0x53, 1): 13,  # Delete
    (0x47, 1): 14,  # Home
    (0x52, 1): 15,  # Insert
    (0x49, 1): 16,  # PageUp
    (0x51, 1): 17,  # PageDown

    # Row 1 : 21~41
    (0x29, 0): 21,  # `
    (0x02, 0): 22,  # 1
    (0x03, 0): 23,
    (0x04, 0): 24,
    (0x05, 0): 25,
    (0x06, 0): 26,
    (0x07, 0): 27,
    (0x08, 0): 28,
    (0x09, 0): 29,
    (0x0A, 0): 30,
    (0x0B, 0): 31,
    (0x0C, 0): 32,  # -
    (0x0D, 0): 33,  # =
    (0x0E, 0): 34,  # Backspace
    (0x45, 0): 35,  # NumLock
    (0x35, 1): 36,  # NumPad /
    (0x37, 0): 37,  # NumPad *
    (0x4A, 0): 38,  # NumPad -

    # Row 2 : 42~62
    (0x0F, 0): 42,  # Tab
    (0x10, 0): 43,  # Q
    (0x11, 0): 44,
    (0x12, 0): 45,
    (0x13, 0): 46,
    (0x14, 0): 47,
    (0x15, 0): 48,
    (0x16, 0): 49,
    (0x17, 0): 50,
    (0x18, 0): 51,
    (0x19, 0): 52,
    (0x1A, 0): 53,  # [
    (0x1B, 0): 54,  # ]
    (0x2B, 0): 55,  # \
    (0x47, 0): 56,  # NumPad 7
    (0x48, 0): 57,  # NumPad 8
    (0x49, 0): 58,  # NumPad 9
    (0x4E, 0): 59,  # NumPad +

    # Row 3 : 63~83
    (0x3A, 0): 63,  # CapsLock
    (0x1E, 0): 64,  # A
    (0x1F, 0): 65,
    (0x20, 0): 66,
    (0x21, 0): 67,
    (0x22, 0): 68,
    (0x23, 0): 69,
    (0x24, 0): 70,
    (0x25, 0): 71,
    (0x26, 0): 72,
    (0x27, 0): 73,  # ;
    (0x28, 0): 74,  # '
    (0x1C, 0): 76,  # Main Enter
    (0x4B, 0): 77,  # NumPad 4
    (0x4C, 0): 78,  # NumPad 5
    (0x4D, 0): 79,  # NumPad 6

    # Row 4 : 84~104
    (0x2A, 0): 84,  # Left Shift
    (0x2C, 0): 86,  # Z
    (0x2D, 0): 87,
    (0x2E, 0): 88,
    (0x2F, 0): 89,
    (0x30, 0): 90,
    (0x31, 0): 91,
    (0x32, 0): 92,
    (0x33, 0): 93,  # ,
    (0x34, 0): 94,  # .
    (0x35, 0): 95,  # /
    (0x36, 0): 96,  # Right Shift  <-- 修正
    (0x48, 1): 97,  # Arrow Up
    (0x4F, 0): 98,  # NumPad 1
    (0x50, 0): 99,  # NumPad 2
    (0x51, 0): 100, # NumPad 3
    (0x1C, 1): 101, # NumPad Enter <-- 修正

    # Row 5 : 105~125
    (0x1D, 0): 105, # Left Ctrl
    (0x5B, 1): 106, # Left Win
    (0x38, 0): 107, # Left Alt
    (0x39, 0): 110, # Space
    (0x38, 1): 113, # Right Alt / AltGr
    # 114 = Fn：Windows 不會上報，無法直接觸發
    (0x1D, 1): 115, # Right Ctrl
    (0x4B, 1): 117, # Arrow Left  <-- 修正
    (0x50, 1): 118, # Arrow Down  <-- 修正
    (0x4D, 1): 119, # Arrow Right <-- 修正
    (0x52, 0): 120, # NumPad 0
    (0x53, 0): 121, # NumPad .
}

# 只保留實際有鍵的位置；Fn 114 雖不能當觸發源，但漣漪可經過它
ACTIVE_LEDS = set(SCAN_TO_LED.values()) | {114}

# 回到原本的 6 x 21 matrix 座標。
# 不再對整個鍵盤套 row stagger，避免所有往上軌跡一起變成右上。
POS = {idx: (idx // COLS, idx % COLS) for idx in ACTIVE_LEDS}


APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "YG98CrossRipple")
CONFIG_FILE = os.path.join(APP_DIR, "settings.json")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "YG98CrossRipple"

DEFAULT_PROFILES = {
    "粉紅 + 紫": {
        "press_color": [255, 70, 170],
        "outer_color": [145, 55, 255],
        "speed": 8.5,
        "life": 1.05,
        "gradient_strength": 0.72,
    },
    "藍 + 綠": {
        "press_color": [45, 130, 255],
        "outer_color": [40, 230, 130],
        "speed": 8.5,
        "life": 1.05,
        "gradient_strength": 0.72,
    },
    "紅 + 橘": {
        "press_color": [255, 45, 55],
        "outer_color": [255, 145, 25],
        "speed": 8.5,
        "life": 1.05,
        "gradient_strength": 0.72,
    },
}

profiles = {}
current_profile = "粉紅 + 紫"
startup_enabled = True


def profile_from_settings():
    with settings_lock:
        return {
            "press_color": list(settings["press_color"]),
            "outer_color": list(settings["outer_color"]),
            "speed": float(settings["speed"]),
            "life": float(settings["life"]),
            "gradient_strength": float(settings["gradient_strength"]),
        }


def apply_profile_data(data):
    with settings_lock:
        settings["press_color"] = tuple(data.get("press_color", [255, 70, 170]))
        settings["outer_color"] = tuple(data.get("outer_color", [145, 55, 255]))
        settings["speed"] = float(data.get("speed", 8.5))
        settings["life"] = float(data.get("life", 1.05))
        settings["gradient_strength"] = float(data.get("gradient_strength", 0.72))


def save_config():
    os.makedirs(APP_DIR, exist_ok=True)
    payload = {
        "current_profile": current_profile,
        "profiles": profiles,
        "startup_enabled": startup_enabled,
    }
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_FILE)


def load_config():
    global profiles, current_profile, startup_enabled
    profiles = json.loads(json.dumps(DEFAULT_PROFILES))
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data.get("profiles"), dict):
            profiles.update(data["profiles"])
        current_profile = data.get("current_profile", current_profile)
        # 舊版設定沒有這個欄位時，預設開啟 Windows 自動啟動。
        startup_enabled = bool(data.get("startup_enabled", True))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    if current_profile not in profiles:
        current_profile = next(iter(profiles))
    apply_profile_data(profiles[current_profile])


def startup_command():
    # PyInstaller EXE：直接啟動自己。
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --startup'

    exe = sys.executable
    # Python 腳本：用 pythonw.exe，避免登入時跳 console。
    if exe.lower().endswith("python.exe"):
        pyw = exe[:-10] + "pythonw.exe"
        if os.path.exists(pyw):
            exe = pyw
    script = os.path.abspath(sys.argv[0])
    return f'"{exe}" "{script}" --startup'


def is_startup_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, RUN_NAME)
        return bool(value)
    except OSError:
        return False


def set_startup(enabled):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, RUN_NAME)
            except FileNotFoundError:
                pass


def candidate_devices():
    """列出可能能接受 07 07 Feature Report 的有線/2.4G/藍牙 HID。"""
    found = []
    seen = set()

    # 第一優先：已知有線 VID/PID。
    for d in hid.enumerate(VID, PID):
        path = d.get("path")
        if path not in seen:
            found.append(d)
            seen.add(path)

    # 第二優先：三模切換後 VID/PID 可能改變。
    # 只納入產品/廠商名稱吻合的裝置，避免亂送到其他 HID。
    for d in hid.enumerate():
        product = (d.get("product_string") or "").lower()
        maker = (d.get("manufacturer_string") or "").lower()
        if ("yg99" in product or "yg98" in product or "sino wealth" in maker):
            path = d.get("path")
            if path not in seen:
                found.append(d)
                seen.add(path)

    def score(d):
        s = 0
        if d.get("interface_number") == 1: s += 20
        if d.get("usage_page") == 0xFF01: s += 30
        if d.get("usage") == 0x01: s += 20
        if d.get("vendor_id") == VID and d.get("product_id") == PID: s += 10
        return -s

    return sorted(found, key=score)


def open_dev():
    errors = []
    for info in candidate_devices():
        # 優先/限制在 vendor-defined RGB/control collection。
        if info.get("usage_page") not in (0xFF01, None):
            continue
        try:
            d = hid.device()
            d.open_path(info["path"])
            # 用全黑 07 07 當能力探測；成功才接受這個介面。
            probe = bytearray(BASE)
            d.send_feature_report(bytes(probe))
            return d, info
        except Exception as e:
            errors.append(str(e))
            try:
                d.close()
            except Exception:
                pass
    raise RuntimeError("目前找不到可控制 RGB 的 YG98/YG99 HID")

def send_rgb(dev, colors):
    """07 07 planar RGB: R[126] + G[126] + B[126], data starts at byte 8."""
    b = bytearray(BASE)
    for idx, rgb in colors.items():
        if not (0 <= idx < MATRIX_LEN):
            continue
        r, g, bl = rgb
        b[8 + idx] = max(0, min(255, int(r)))
        b[8 + MATRIX_LEN + idx] = max(0, min(255, int(g)))
        b[8 + 2 * MATRIX_LEN + idx] = max(0, min(255, int(bl)))
    dev.send_feature_report(bytes(b))

def distances(center):
    if center not in POS:
        return {}
    r0, c0 = POS[center]
    out = {center: 0.0}

    # 橫向
    for idx, (r, c) in POS.items():
        if r == r0:
            out[idx] = abs(c - c0)

    # 直向
    for r in range(ROWS):
        if r == r0:
            continue
        candidates = [idx for idx, (rr, cc) in POS.items() if rr == r]
        if not candidates:
            continue
        idx = min(candidates, key=lambda i: abs(POS[i][1] - c0))
        rr, cc = POS[idx]
        out[idx] = abs(rr - r0) + 0.10 * abs(cc - c0)

    return out

DIST = {idx: distances(idx) for idx in POS}

# 特殊底排垂直路徑：只覆寫 Right Alt / Right Ctrl，
# 其他所有鍵仍沿用原本的 6x21 matrix 十字軌跡。
#
# Right Alt 指定順序：
#   Right Alt -> <, -> K -> I -> * -> F7
#
# Right Ctrl 指定順序：
#   Right Ctrl -> ?/ -> ' -> ] -> = -> F9
#
# 這裡保留各自底排的橫向擴散，只替換「往上」那條線。

def apply_special_vertical(center, chain):
    if center not in DIST:
        return
    base = {
        idx: d for idx, d in DIST[center].items()
        if POS[idx][0] == POS[center][0]
    }
    out = {center: 0.0, **base}
    for step, idx in enumerate(chain, start=1):
        out[idx] = float(step)
    DIST[center] = out

# LED index:
# 93 = <,
# 71 = K
# 50 = I
# 37 = NumPad *
# 7  = F7
# Z ~ ? 這一排相對上面幾排本來就有半格錯位。
# 原本用相同 matrix column，會造成例如 Z -> S -> W -> 2 -> F2。
# 改成實際鍵帽的垂直方向：
# Z -> A -> Q -> 1 -> Esc
# X -> S -> W -> 2 -> F1
# C -> D -> E -> 3 -> F2
# V -> F -> R -> 4 -> F3
# B -> G -> T -> 5 -> F4
# N -> H -> Y -> 6 -> F5
# M -> J -> U -> 7 -> F6
# < -> K -> I -> 8/* -> F7
# > -> L -> O -> 9/( -> F8
# ? -> ;/: -> P -> 0/) -> F9
BOTTOM_ROW_VERTICAL = {
    86: [64, 43, 22, 0],
    87: [65, 44, 23, 1],
    88: [66, 45, 24, 2],
    89: [67, 46, 25, 3],
    90: [68, 47, 26, 4],
    91: [69, 48, 27, 5],
    92: [70, 49, 28, 6],
    93: [71, 50, 29, 7],
    94: [72, 51, 30, 8],
    95: [73, 52, 31, 9],
}
for center, chain in BOTTOM_ROW_VERTICAL.items():
    apply_special_vertical(center, chain)

# ASDFGHJKL;' 這一排往上的最頂端也整體右偏一格。
# 只修「往上最後一顆」：
# A -> ... -> Esc
# S -> ... -> F1
# D -> ... -> F2
# F -> ... -> F3
# G -> ... -> F4
# H -> ... -> F5
# J -> ... -> F6
# K -> ... -> F7
# L -> ... -> F8
# ; -> ... -> F9
# ' -> ... -> F10
#
# 保留原本中間路徑，只把最上方 F-row 改成正確位置。
AS_ROW_TOP_FIX = {
    64: 0,   # A -> Esc
    65: 1,   # S -> F1
    66: 2,   # D -> F2
    67: 3,   # F -> F3
    68: 4,   # G -> F4
    69: 5,   # H -> F5
    70: 6,   # J -> F6
    71: 7,   # K -> F7
    72: 8,   # L -> F8
    73: 9,   # ; -> F9
    74: 10,  # ' -> F10
}

for center, top_led in AS_ROW_TOP_FIX.items():
    if center not in DIST:
        continue

    # 找出這顆鍵目前往上的所有節點，取最遠距離當成頂端距離。
    upper = [
        (idx, d) for idx, d in DIST[center].items()
        if idx != center and POS[idx][0] < POS[center][0]
    ]
    if not upper:
        continue

    max_d = max(d for _, d in upper)

    # 移除目前位於 F-row、且距離最遠的錯誤頂端。
    fixed = {}
    for idx, d in DIST[center].items():
        is_wrong_top = (POS[idx][0] == 0 and abs(d - max_d) < 1e-9)
        if not is_wrong_top:
            fixed[idx] = d

    # 補上正確的最上方 LED。
    fixed[top_led] = max_d
    DIST[center] = fixed

# ASDFGHJKL;'" 這一排「往下」依實際鍵帽位置校正。
# 只覆寫下方分支，橫向與往上分支保留。
#
# A -> Z -> Left Alt
# S -> X
# D -> C
# F -> V -> Space
# G -> B -> Space
# H -> N
# J -> M
# K -> < -> Right Alt
# L -> > -> Fn
# ;/: -> ? -> Right Ctrl
# '/" -> Right Shift -> Left Arrow
#
# 同一距離可以同時亮兩顆（例如 F/G 都可延伸到 Space）。

AS_ROW_DOWN_FIX = {
    64: [[86], [107]],       # A -> Z -> Left Alt
    65: [[87]],              # S -> X
    66: [[88]],              # D -> C
    67: [[89], [110]],       # F -> V -> Space
    68: [[90], [110]],       # G -> B -> Space
    69: [[91]],              # H -> N
    70: [[92]],              # J -> M
    71: [[93], [113]],       # K -> < -> Right Alt
    72: [[94], [114]],       # L -> > -> Fn
    73: [[95], [115]],       # ;/: -> ? -> Right Ctrl
    74: [[96], [117]],       # '/" -> Right Shift -> Left Arrow
}

for center, levels in AS_ROW_DOWN_FIX.items():
    if center not in DIST:
        continue

    # 保留中心、同排橫向、以及所有往上的節點；刪掉原本自動算出的下方節點。
    fixed = {
        idx: d for idx, d in DIST[center].items()
        if POS[idx][0] <= POS[center][0]
    }

    # 指定新的下方垂直鏈，每層距離 +1。
    for step, leds in enumerate(levels, start=1):
        for idx in leds:
            fixed[idx] = float(step)

    DIST[center] = fixed

# F1 ~ F10 往下的尾端依指定路徑修正。
# 只修改 F1..F10 作為中心時的「往下」路徑；其他鍵完全不動。
#
# F1  -> 2 -> W -> S -> X 
# F2  -> 3 -> E -> D -> C
# F3  -> 4 -> R -> F -> V -> Space
# F4  -> 5 -> T -> G -> B -> Space
# F5  -> 6 -> Y -> H -> N
# F6  -> 7 -> U -> J -> M
# F7  -> 8 -> I -> K -> < -> Right Alt
# F8  -> 9 -> O -> L -> > -> Fn
# F9  -> 0 -> P -> ;/: -> ? -> Right Ctrl
# F10 -> - -> [ -> '/" -> ? -> Right Ctrl
#
# 注意：只覆寫 row0 中 LED 1..10 的下方分支。
FROW_DOWN_FIX = {
    1:  [23, 44, 65, 87],       # F1
    2:  [24, 45, 66, 88],            # F2
    3:  [25, 46, 67, 89, 110],            # F3
    4:  [26, 47, 68, 90, 110],       # F4
    5:  [27, 48, 69, 91],       # F5
    6:  [28, 49, 70, 92],            # F6
    7:  [29, 50, 71, 93, 113],            # F7
    8:  [30, 51, 72, 94, 114],       # F8
    9:  [31, 52, 73, 95, 115],       # F9
    10: [32, 53, 74, 95, 115],       # F10
}

for center, chain in FROW_DOWN_FIX.items():
    if center not in DIST:
        continue

    # F-row 沒有「往上」，保留中心與同一排的橫向十字，
    # 移除原本自動算出的所有下方節點，再套指定鏈。
    fixed = {
        idx: d for idx, d in DIST[center].items()
        if POS[idx][0] == POS[center][0]
    }
    fixed[center] = 0.0

    for step, idx in enumerate(chain, start=1):
        fixed[idx] = float(step)

    DIST[center] = fixed

# Left Alt 指定：Left Alt -> Z -> A -> Q -> !/1 -> Esc
apply_special_vertical(107, [86, 64, 43, 22, 0])

apply_special_vertical(113, [93, 71, 50, 37, 7])

# 95 = ?/
# 73 = : ;
# 52 = P
# 31 = ) 0
# 9  = F9
apply_special_vertical(115, [95, 73, 52, 31, 9])

def brightness(d, radius, age, life):
    delta = radius - d
    if delta < -0.8:
        return 0
    if -0.8 <= delta <= 0.8:
        shape = 1.0 - 0.28 * abs(delta) / 0.8
    elif 0.8 < delta <= 2.2:
        shape = max(0.0, 1.0 - (delta - 0.8) / 1.4) * 0.68
    else:
        shape = 0.0

    fade_start = min(0.72, life * 0.68)
    fade = 1.0
    if age > fade_start:
        denom = max(0.001, life - fade_start)
        fade = max(0.0, (life - age) / denom)
    return int(255 * shape * fade)


def mix_color(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def ripple_rgb(press_color, outer_color, distance, max_distance, strength):
    """
    空間漸變：按鍵中心保持 press_color，距離越遠越接近 outer_color。
    strength < 1 時，前幾格仍保留較多中心色，過渡更柔和。
    """
    if max_distance <= 0:
        return press_color
    x = max(0.0, min(1.0, distance / max_distance))
    # smoothstep，避免線性漸變看起來像一格一格換色
    x = x * x * (3.0 - 2.0 * x)
    x = x ** max(0.25, strength)
    return mix_color(press_color, outer_color, x)

def renderer(dev):
    global running
    nxt = time.perf_counter()

    while running:
        now = time.perf_counter()

        with settings_lock:
            press_color = settings["press_color"]
            outer_color = settings["outer_color"]
            speed = settings["speed"]
            life = settings["life"]
            strength = settings["gradient_strength"]

        with lock:
            ripples[:] = [r for r in ripples if now - r[1] < life]
            active = list(ripples)

        # 每顆 LED 保存目前最強 ripple 的亮度與 RGB。
        # 多個 ripple 相遇時採「亮度最大者」，避免顏色相加變白。
        colors = {}
        powers = {}

        for center, t0 in active:
            age = now - t0
            radius = age * speed
            dist_map = DIST.get(center, {})
            max_distance = max(dist_map.values(), default=1.0)

            for idx, d in dist_map.items():
                v = brightness(d, radius, age, life)
                if v <= 0:
                    continue

                base_rgb = ripple_rgb(
                    press_color, outer_color, d, max_distance, strength
                )
                rgb = tuple(int(ch * v / 255.0) for ch in base_rgb)

                if v > powers.get(idx, -1):
                    powers[idx] = v
                    colors[idx] = rgb

            # 剛按下的中心鍵固定使用「按下顏色」
            if age < 0.24:
                colors[center] = press_color
                powers[center] = 255

        send_rgb(dev, colors)

        nxt += DT
        delay = nxt - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
        else:
            nxt = time.perf_counter()

# ---------------- Windows low-level keyboard hook ----------------

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
LLKHF_EXTENDED = 0x01

ULONG_PTR = wt.WPARAM
LRESULT = ctypes.c_ssize_t
HHOOK = wt.HANDLE
HINSTANCE = wt.HANDLE

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wt.DWORD),
        ("scanCode", wt.DWORD),
        ("flags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]

LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
    LRESULT, ctypes.c_int, wt.WPARAM, wt.LPARAM
)

# 64-bit Windows 必須明確宣告 HANDLE 回傳型別。
# 否則 ctypes 預設把 GetModuleHandleW 的 64-bit handle 截成 32-bit，
# SetWindowsHookExW 就可能報 WinError 126。
kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
kernel32.GetModuleHandleW.restype = HINSTANCE

user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    LowLevelKeyboardProc,
    HINSTANCE,
    wt.DWORD,
]
user32.SetWindowsHookExW.restype = HHOOK

user32.UnhookWindowsHookEx.argtypes = [HHOOK]
user32.UnhookWindowsHookEx.restype = wt.BOOL

user32.CallNextHookEx.argtypes = [
    HHOOK,
    ctypes.c_int,
    wt.WPARAM,
    wt.LPARAM,
]
user32.CallNextHookEx.restype = LRESULT

user32.GetMessageW.argtypes = [
    ctypes.POINTER(wt.MSG),
    wt.HWND,
    wt.UINT,
    wt.UINT,
]
user32.GetMessageW.restype = wt.BOOL

user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
user32.TranslateMessage.restype = wt.BOOL

user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
user32.DispatchMessageW.restype = LRESULT

user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostQuitMessage.restype = None

user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short

ctrl_down = False

def hook_proc(nCode, wParam, lParam):
    global running, ctrl_down

    if nCode >= 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
        info = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        scan = int(info.scanCode)
        ext = 1 if (info.flags & LLKHF_EXTENDED) else 0
        vk = int(info.vkCode)

        # Ctrl + F12 = 結束；F12 單按仍然可以觸發漣漪
        if scan == 0x58 and (user32.GetAsyncKeyState(0x11) & 0x8000):
            running = False
            user32.PostQuitMessage(0)
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        # 某些鍵盤/Windows 組合對右側修飾鍵的 scan/ext 回報不一致，
        # 所以右 Shift / 右 Alt 再用 vkCode 做一層強制辨識。
        if vk == 0xA1:          # VK_RSHIFT
            idx = 96
        elif vk == 0xA5:        # VK_RMENU / Right Alt (AltGr)
            idx = 113
        else:
            idx = SCAN_TO_LED.get((scan, ext))

        if idx is not None:
            with lock:
                ripples.append((idx, time.perf_counter()))
                if len(ripples) > 24:
                    del ripples[:-24]

    return user32.CallNextHookEx(None, nCode, wParam, lParam)

HOOK_CALLBACK = LowLevelKeyboardProc(hook_proc)

def keyboard_hook_loop():
    hmod = kernel32.GetModuleHandleW(None)
    ctypes.set_last_error(0)
    hook = user32.SetWindowsHookExW(
        WH_KEYBOARD_LL,
        HOOK_CALLBACK,
        hmod,
        0
    )
    if not hook:
        err = ctypes.get_last_error()
        raise OSError(err, f"SetWindowsHookExW 失敗 (WinError {err})")

    msg = wt.MSG()
    try:
        while running and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    finally:
        user32.UnhookWindowsHookEx(hook)

def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)




# ---------------- Single-instance / reopen existing GUI ----------------
ERROR_ALREADY_EXISTS = 183
WAIT_OBJECT_0 = 0x00000000
EVENT_MODIFY_STATE = 0x0002

MUTEX_NAME = r"Local\YG98CrossRipple.SingleInstance.v1"
SHOW_EVENT_NAME = r"Local\YG98CrossRipple.ShowWindow.v1"

kernel32.CreateMutexW.argtypes = [wt.LPVOID, wt.BOOL, wt.LPCWSTR]
kernel32.CreateMutexW.restype = wt.HANDLE
kernel32.CreateEventW.argtypes = [wt.LPVOID, wt.BOOL, wt.BOOL, wt.LPCWSTR]
kernel32.CreateEventW.restype = wt.HANDLE
kernel32.OpenEventW.argtypes = [wt.DWORD, wt.BOOL, wt.LPCWSTR]
kernel32.OpenEventW.restype = wt.HANDLE
kernel32.SetEvent.argtypes = [wt.HANDLE]
kernel32.SetEvent.restype = wt.BOOL
kernel32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
kernel32.WaitForSingleObject.restype = wt.DWORD
kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.CloseHandle.restype = wt.BOOL

def acquire_single_instance():
    """Return (is_primary, mutex_handle, show_event_handle)."""
    ctypes.set_last_error(0)
    mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not mutex:
        return True, None, None

    already_running = (ctypes.get_last_error() == ERROR_ALREADY_EXISTS)
    if already_running:
        evt = kernel32.OpenEventW(EVENT_MODIFY_STATE, False, SHOW_EVENT_NAME)
        if evt:
            kernel32.SetEvent(evt)
            kernel32.CloseHandle(evt)
        kernel32.CloseHandle(mutex)
        return False, None, None

    show_event = kernel32.CreateEventW(None, False, False, SHOW_EVENT_NAME)
    return True, mutex, show_event


# ---------------- Windows notification-area / system-tray icon ----------------
# 使用原生 Shell_NotifyIconW，不需要額外安裝 pystray。
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

WM_USER = 0x0400
WM_TRAYICON = WM_USER + 20
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_COMMAND = 0x0111
WM_DESTROY = 0x0002
MF_STRING = 0x0000
TPM_RIGHTBUTTON = 0x0002
NIM_ADD = 0x00000000
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
IDI_APPLICATION = 32512
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040
SW_SHOWNORMAL = 1

class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("hWnd", wt.HWND),
        ("uID", wt.UINT),
        ("uFlags", wt.UINT),
        ("uCallbackMessage", wt.UINT),
        ("hIcon", wt.HANDLE),
        ("szTip", wt.WCHAR * 128),
        ("dwState", wt.DWORD),
        ("dwStateMask", wt.DWORD),
        ("szInfo", wt.WCHAR * 256),
        ("uTimeoutOrVersion", wt.UINT),
        ("szInfoTitle", wt.WCHAR * 64),
        ("dwInfoFlags", wt.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wt.HANDLE),
    ]

TrayWndProc = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)


HCURSOR = wt.HANDLE
HBRUSH = wt.HANDLE
HICON = wt.HANDLE
HMENU = wt.HANDLE

class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wt.UINT),
        ("lpfnWndProc", TrayWndProc),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", HINSTANCE),
        ("hIcon", HICON),
        ("hCursor", HCURSOR),
        ("hbrBackground", HBRUSH),
        ("lpszMenuName", wt.LPCWSTR),
        ("lpszClassName", wt.LPCWSTR),
    ]

# Tray-related Win32 signatures.
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.RegisterClassW.restype = wt.ATOM

user32.CreateWindowExW.argtypes = [
    wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.HWND, HMENU, HINSTANCE, wt.LPVOID,
]
user32.CreateWindowExW.restype = wt.HWND

user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = LRESULT

user32.LoadIconW.argtypes = [HINSTANCE, wt.LPCWSTR]
user32.LoadIconW.restype = HICON

user32.LoadImageW.argtypes = [
    HINSTANCE, wt.LPCWSTR, wt.UINT,
    ctypes.c_int, ctypes.c_int, wt.UINT
]
user32.LoadImageW.restype = wt.HANDLE

user32.CreatePopupMenu.argtypes = []
user32.CreatePopupMenu.restype = HMENU

user32.AppendMenuW.argtypes = [HMENU, wt.UINT, wt.WPARAM, wt.LPCWSTR]
user32.AppendMenuW.restype = wt.BOOL

user32.DestroyMenu.argtypes = [HMENU]
user32.DestroyMenu.restype = wt.BOOL

user32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
user32.GetCursorPos.restype = wt.BOOL

user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.SetForegroundWindow.restype = wt.BOOL

user32.TrackPopupMenu.argtypes = [
    HMENU, wt.UINT, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, wt.HWND, wt.LPVOID,
]
user32.TrackPopupMenu.restype = wt.BOOL

shell32.Shell_NotifyIconW.argtypes = [wt.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.Shell_NotifyIconW.restype = wt.BOOL


class NativeTray:
    CMD_OPEN = 1001
    CMD_EXIT = 1002

    def __init__(self, root):
        self.root = root
        self.hwnd = None
        self.thread = None
        self.ready = threading.Event()
        self._wndproc = TrayWndProc(self._proc)

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self.ready.wait(timeout=2.0)

    def show_window(self):
        try:
            self.root.after(0, self._show_tk)
        except Exception:
            pass

    def _show_tk(self):
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        self.root.focus_force()

    def _exit_app(self):
        global running
        running = False
        try:
            save_config()
        except Exception:
            pass
        try:
            self.root.after(0, self.root.destroy)
        except Exception:
            pass
        user32.PostQuitMessage(0)

    def _proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAYICON:
            event = int(lparam)
            if event == WM_LBUTTONDBLCLK:
                self.show_window()
                return 0
            if event == WM_RBUTTONUP:
                menu = user32.CreatePopupMenu()
                user32.AppendMenuW(menu, MF_STRING, self.CMD_OPEN, "開啟 YG98 十字漣漪")
                user32.AppendMenuW(menu, MF_STRING, self.CMD_EXIT, "完全結束")
                pt = wt.POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                user32.SetForegroundWindow(hwnd)
                user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON, pt.x, pt.y, 0, hwnd, None)
                user32.DestroyMenu(menu)
                return 0
        elif msg == WM_COMMAND:
            cmd = int(wparam) & 0xFFFF
            if cmd == self.CMD_OPEN:
                self.show_window()
            elif cmd == self.CMD_EXIT:
                self._exit_app()
            return 0
        elif msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _run(self):
        hinst = kernel32.GetModuleHandleW(None)
        class_name = f"YG98CrossRippleTrayWindow_{os.getpid()}"

        wc = WNDCLASSW()
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.lpszClassName = class_name

        atom = user32.RegisterClassW(ctypes.byref(wc))
        # 已註冊時 RegisterClassW 可能失敗，但 CreateWindowExW 仍可使用 class。
        self.hwnd = user32.CreateWindowExW(
            0, class_name, "YG98 Cross Ripple Tray", 0,
            0, 0, 0, 0, None, None, hinst, None
        )
        if not self.hwnd:
            self.ready.set()
            return

        icon = None
        if os.path.exists(ICON_PATH):
            icon = user32.LoadImageW(
                None, ICON_PATH, IMAGE_ICON, 0, 0,
                LR_LOADFROMFILE | LR_DEFAULTSIZE
            )
        if not icon:
            icon = user32.LoadIconW(
                None,
                ctypes.cast(ctypes.c_void_p(IDI_APPLICATION), wt.LPCWSTR)
            )
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAYICON
        nid.hIcon = icon
        nid.szTip = "YG98 十字漣漪"
        if not shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
            err = ctypes.get_last_error()
            print(f"[Tray] Shell_NotifyIconW failed: {err}")
            self.ready.set()
            return
        self.ready.set()

        msg = wt.MSG()
        try:
            while running and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))


def make_gui(device_info=None):
    global current_profile, startup_enabled

    root = tk.Tk()
    try:
        if os.path.exists(ICON_PATH):
            root.iconbitmap(default=ICON_PATH)
    except Exception:
        pass
    root.title("YG98 燈效控制器 v3.3")
    root.geometry("470x610")
    root.resizable(False, False)

    title = tk.Label(root, text="YG98 十字漣漪", font=("Microsoft JhengHei UI", 18, "bold"))
    title.pack(pady=(16, 3))

    mode_text = "RGB HID 已連線"
    if device_info:
        product = device_info.get("product_string") or "YG98/YG99"
        mode_text = f"{product}｜RGB HID 已連線"
    tk.Label(root, text=mode_text, font=("Microsoft JhengHei UI", 9)).pack(pady=(0, 10))

    profile_box = tk.LabelFrame(root, text="顏色組合", font=("Microsoft JhengHei UI", 10, "bold"))
    profile_box.pack(fill="x", padx=24, pady=(0, 10))

    profile_var = tk.StringVar(value=current_profile)
    profile_menu = tk.OptionMenu(profile_box, profile_var, *profiles.keys())
    profile_menu.config(width=24)
    profile_menu.pack(side="left", padx=8, pady=10)

    color_frame = tk.Frame(root)
    color_frame.pack(fill="x", padx=28)

    previews = {}
    sliders = {}

    def refresh_controls():
        with settings_lock:
            pc = settings["press_color"]
            oc = settings["outer_color"]
            vals = {k: settings[k] for k in ("speed", "life", "gradient_strength")}
        previews["press_color"].config(bg=rgb_to_hex(pc))
        previews["outer_color"].config(bg=rgb_to_hex(oc))
        for k, v in vals.items():
            sliders[k].set(v)

    def select_profile(*_):
        global current_profile
        name = profile_var.get()
        if name not in profiles:
            return
        current_profile = name
        apply_profile_data(profiles[name])
        refresh_controls()
        save_config()

    profile_var.trace_add("write", select_profile)

    def choose_color(which, preview):
        with settings_lock:
            current = settings[which]
        chosen = colorchooser.askcolor(color=rgb_to_hex(current), parent=root)
        if chosen and chosen[0]:
            rgb = tuple(int(round(v)) for v in chosen[0])
            with settings_lock:
                settings[which] = rgb
            preview.config(bg=rgb_to_hex(rgb))
            # 任何修改都立即寫回目前組合，因此下次開機就是最後狀態。
            profiles[current_profile] = profile_from_settings()
            save_config()

    def color_row(label_text, which):
        row = tk.Frame(color_frame)
        row.pack(fill="x", pady=6)
        tk.Label(row, text=label_text, width=12, anchor="w",
                 font=("Microsoft JhengHei UI", 11)).pack(side="left")
        with settings_lock:
            initial = settings[which]
        preview = tk.Label(row, width=8, height=2, bg=rgb_to_hex(initial),
                           relief="solid", bd=1)
        preview.pack(side="left", padx=8)
        previews[which] = preview
        tk.Button(row, text="選擇顏色", command=lambda: choose_color(which, preview),
                  width=12).pack(side="right")

    color_row("按下顏色", "press_color")
    color_row("外圈顏色", "outer_color")

    control = tk.Frame(root)
    control.pack(fill="x", padx=28, pady=(8, 0))

    def add_slider(label, key, lo, hi, resolution):
        row = tk.Frame(control)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, width=12, anchor="w",
                 font=("Microsoft JhengHei UI", 10)).pack(side="left")
        with settings_lock:
            initial = settings[key]
        var = tk.DoubleVar(value=initial)
        scale = tk.Scale(row, from_=lo, to=hi, resolution=resolution,
                         orient="horizontal", variable=var, showvalue=True,
                         length=255)
        scale.pack(side="right")
        sliders[key] = var

        def update(_=None):
            with settings_lock:
                settings[key] = float(var.get())
            profiles[current_profile] = profile_from_settings()
            save_config()
        scale.configure(command=update)

    add_slider("擴散速度", "speed", 4.0, 14.0, 0.5)
    add_slider("殘影時間", "life", 0.6, 1.8, 0.05)
    add_slider("漸變曲線", "gradient_strength", 0.35, 1.4, 0.05)

    def rebuild_menu():
        menu = profile_menu["menu"]
        menu.delete(0, "end")
        for name in profiles:
            menu.add_command(label=name, command=lambda n=name: profile_var.set(n))

    def add_profile():
        global current_profile
        name = simpledialog.askstring("新增組合", "輸入組合名稱：", parent=root)
        if not name:
            return
        name = name.strip()
        if not name:
            return
        if name in profiles and not messagebox.askyesno("覆蓋？", f"「{name}」已存在，要覆蓋嗎？", parent=root):
            return
        profiles[name] = profile_from_settings()
        current_profile = name
        rebuild_menu()
        profile_var.set(name)
        save_config()

    def delete_profile():
        global current_profile
        if len(profiles) <= 1:
            messagebox.showinfo("無法刪除", "至少要保留一組設定。", parent=root)
            return
        name = profile_var.get()
        if not messagebox.askyesno("刪除組合", f"刪除「{name}」？", parent=root):
            return
        profiles.pop(name, None)
        current_profile = next(iter(profiles))
        rebuild_menu()
        profile_var.set(current_profile)
        save_config()

    buttons = tk.Frame(profile_box)
    buttons.pack(side="right", padx=7)
    tk.Button(buttons, text="＋ 新增", width=8, command=add_profile).pack(side="left", padx=2)
    tk.Button(buttons, text="刪除", width=7, command=delete_profile).pack(side="left", padx=2)

    startup_frame = tk.LabelFrame(root, text="自動啟動", font=("Microsoft JhengHei UI", 10, "bold"))
    startup_frame.pack(fill="x", padx=24, pady=(14, 8))

    startup_var = tk.BooleanVar(value=startup_enabled and is_startup_enabled())

    def toggle_startup():
        global startup_enabled
        try:
            startup_enabled = bool(startup_var.get())
            set_startup(startup_enabled)
            save_config()
        except OSError as e:
            startup_var.set(is_startup_enabled())
            startup_enabled = bool(startup_var.get())
            save_config()
            messagebox.showerror("設定失敗", str(e), parent=root)

    tk.Checkbutton(
        startup_frame,
        text="Windows 登入後自動啟動十字漣漪",
        variable=startup_var,
        command=toggle_startup,
        font=("Microsoft JhengHei UI", 10)
    ).pack(anchor="w", padx=10, pady=8)

    tk.Label(
        startup_frame,
        text="自動啟動時會用 pythonw 背景執行，不需要開 PowerShell。",
        font=("Microsoft JhengHei UI", 9)
    ).pack(anchor="w", padx=12, pady=(0, 8))

    tk.Label(
        root,
        text="所有修改會自動儲存；下次啟動直接載入最後使用的組合。",
        font=("Microsoft JhengHei UI", 9)
    ).pack(pady=(6, 2))

    tk.Label(
        root,
        text="關閉視窗只會縮到右下角工具列｜雙擊圖示可再次開啟｜Ctrl + F12 完全結束",
        font=("Microsoft JhengHei UI", 9)
    ).pack()

    def close_app():
        # 右上角 X 只隱藏 GUI；十字漣漪繼續在背景執行。
        save_config()
        root.withdraw()

    root.protocol("WM_DELETE_WINDOW", close_app)
    refresh_controls()
    return root
def main():
    global running

    is_primary, mutex_handle, show_event = acquire_single_instance()
    if not is_primary:
        # 已經有一份程式在背景執行：通知原本那份把 GUI 打開，自己立刻結束。
        return

    try:
        load_config()

        # 每次啟動都依照設定同步 Registry。
        # 舊版沒有 startup_enabled 設定時預設為 True，所以升級後會自動補上開機自啟。
        try:
            set_startup(startup_enabled)
        except OSError:
            pass

        dev = None
        device_info = None

        # Windows 登入時 HID 常比程式晚幾秒出現。
        # 舊版只試一次，找不到就直接退出，這就是重開機後效果沒啟動的主要原因。
        if "--startup" in sys.argv:
            deadline = time.monotonic() + 90.0
            while running and time.monotonic() < deadline:
                try:
                    dev, device_info = open_dev()
                    break
                except Exception:
                    time.sleep(2.0)
        else:
            try:
                dev, device_info = open_dev()
            except Exception as e:
                root = tk.Tk()
                try:
                    if os.path.exists(ICON_PATH):
                        root.iconbitmap(default=ICON_PATH)
                except Exception:
                    pass
                root.withdraw()
                messagebox.showerror(
                    "YG98 十字漣漪",
                    "目前找不到可控制 RGB 的 YG98/YG99 HID。\n\n"
                    "如果你現在是 2.4G 或藍牙模式，先切換模式後再試一次。\n\n"
                    f"{e}"
                )
                root.destroy()
                return

        # 開機 90 秒內仍找不到鍵盤就安靜結束；下次手動開啟仍可使用。
        if dev is None:
            return

        send_rgb(dev, {})

        render_thread = threading.Thread(target=renderer, args=(dev,), daemon=True)
        render_thread.start()

        hook_thread = threading.Thread(target=keyboard_hook_loop, daemon=True)
        hook_thread.start()

        root = make_gui(device_info)

        tray = NativeTray(root)
        tray.start()

        if "--startup" in sys.argv:
            root.after(100, root.withdraw)

        def show_existing_if_requested():
            if show_event and kernel32.WaitForSingleObject(show_event, 0) == WAIT_OBJECT_0:
                try:
                    root.deiconify()
                    root.state("normal")
                    root.lift()
                    root.focus_force()
                except Exception:
                    pass
            if running:
                root.after(150, show_existing_if_requested)

        def poll_running():
            if not running:
                try:
                    root.destroy()
                except Exception:
                    pass
                return
            root.after(100, poll_running)

        root.after(150, show_existing_if_requested)
        root.after(100, poll_running)

        try:
            root.mainloop()
        finally:
            running = False
            save_config()
            render_thread.join(timeout=1.0)
            hook_thread.join(timeout=0.5)
            try:
                send_rgb(dev, {})
            except Exception:
                pass
            dev.close()

    finally:
        if show_event:
            kernel32.CloseHandle(show_event)
        if mutex_handle:
            kernel32.CloseHandle(mutex_handle)

if __name__ == "__main__":
    main()
