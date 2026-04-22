import cv2
import numpy as np
import mediapipe as mp
from collections import deque
import math
import time

print("=" * 55)
print("         AIR CANVAS ULTRA PRO  -  Starting...")
print("=" * 55)

# ─────────────────────────── CAMERA ──────────────────────────
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
if not cap.isOpened():
    cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("❌  Camera not detected! Plug in a webcam and retry.")
    exit()

cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv2.CAP_PROP_FPS, 30)
print("✅  Camera ready")

# ─────────────────────────── MEDIAPIPE ───────────────────────
mpHands = mp.solutions.hands
hands   = mpHands.Hands(
    max_num_hands          = 1,
    min_detection_confidence = 0.75,
    min_tracking_confidence  = 0.75,
)
mpDraw = mp.solutions.drawing_utils
LM_STYLE  = mpDraw.DrawingSpec(color=(0, 255, 180), thickness=2, circle_radius=4)
CON_STYLE = mpDraw.DrawingSpec(color=(0, 160, 255), thickness=2)

# ─────────────────────────── CANVAS ──────────────────────────
CANVAS_H, CANVAS_W = 720, 1280
canvas = np.zeros((CANVAS_H, CANVAS_W, 3), np.uint8)

# ─────────────────────────── SETTINGS ────────────────────────
drawColor       = (0, 255, 255)   # cyan default
brushThickness  = 8
eraserThickness = 40
activeTool      = "BRUSH"
xp, yp          = 0, 0

undoStack  = deque(maxlen=20)
redoStack  = deque(maxlen=20)

# Shapes layer (vector shapes with move / rotate)
drawn_shapes = []
drag_start   = None
shape_anchor = None

# Gesture size-control state
pinch3_active    = False   # True while three-finger pinch is held
pinch3_base_dist = None    # average spread when gesture started
pinch3_base_size = None    # brush/eraser size when gesture started

# Notifications
notif_text  = ""
notif_timer = 0.0

# FPS tracking
fps_times = deque(maxlen=30)

# ─────────────────────────── FULL COLOUR PALETTE (30) ────────
PALETTE = [
    # Row 1 – warm spectrum
    (0,0,255),(0,60,255),(0,128,255),(0,200,255),(0,255,255),
    (0,255,200),(0,255,128),(0,255,60),(0,255,0),(60,255,0),
    # Row 2 – cool spectrum
    (128,255,0),(200,255,0),(255,255,0),(255,200,0),(255,128,0),
    (255,60,0),(255,0,0),(255,0,60),(255,0,128),(255,0,200),
    # Row 3 – purples / neutrals
    (255,0,255),(200,0,255),(128,0,255),(60,0,255),(0,0,200),
    (255,255,255),(200,200,200),(128,128,128),(60,60,60),(0,0,0),
]

# ─────────────────────────── TOOLS ───────────────────────────
TOOLS = [
    "BRUSH","ERASER","LINE","RECT","CIRCLE","MOVE","ROTATE",
    "CLEAR","UNDO","REDO","SAVE",
]

# ─────────────────────────── LAYOUT CONSTANTS ────────────────
UI_H         = 165
TOOL_Y0      = 6
TOOL_H       = 62
TOOL_W       = 96
TOOL_GAP     = 6
PAL_R        = 12
PAL_GAP      = 4
PAL_COLS     = 10
PAL_ROWS     = 3
PAL_START_X  = 10
PAL_START_Y  = UI_H - PAL_ROWS * (PAL_R * 2 + PAL_GAP) - 4
BCTRL_X      = CANVAS_W - 168   # right-side brush controls

# Pre-compute tool rects
tool_rects = []
_tx = 8
for _name in TOOLS:
    tool_rects.append((_tx, TOOL_Y0, _tx + TOOL_W, TOOL_Y0 + TOOL_H, _name))
    _tx += TOOL_W + TOOL_GAP

# Pre-compute palette circles
pal_circles = []
for _ri in range(PAL_ROWS):
    for _ci in range(PAL_COLS):
        _idx = _ri * PAL_COLS + _ci
        if _idx < len(PALETTE):
            _cx = PAL_START_X + _ci * (PAL_R * 2 + PAL_GAP) + PAL_R
            _cy = PAL_START_Y + _ri * (PAL_R * 2 + PAL_GAP) + PAL_R
            pal_circles.append((_cx, _cy, PALETTE[_idx]))

# Brush +/- buttons (in header)
BINC_RECT = (BCTRL_X,      10, BCTRL_X + 54,  54)
BDEC_RECT = (BCTRL_X + 62, 10, BCTRL_X + 116, 54)

# ─────────────────────────── HELPERS ─────────────────────────
def rounded_rect(img, pt1, pt2, color, r=10, thick=-1):
    x1, y1 = pt1;  x2, y2 = pt2
    cv2.rectangle(img, (x1 + r, y1), (x2 - r, y2), color, thick)
    cv2.rectangle(img, (x1, y1 + r), (x2, y2 - r), color, thick)
    for cx, cy in [(x1+r,y1+r),(x2-r,y1+r),(x1+r,y2-r),(x2-r,y2-r)]:
        cv2.circle(img, (cx, cy), r, color, thick)

def glow_text(img, text, pos, font, scale, color, thick=1, gr=2):
    dim = tuple(max(0, int(c * 0.25)) for c in color)
    for dx in (-gr, 0, gr):
        for dy in (-gr, 0, gr):
            if dx or dy:
                cv2.putText(img, text, (pos[0]+dx, pos[1]+dy), font, scale, dim, thick+1)
    cv2.putText(img, text, pos, font, scale, color, thick)

def find_dist(p1, p2):
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])

def in_rect(px, py, rect):
    x1, y1, x2, y2 = rect
    return x1 <= px <= x2 and y1 <= py <= y2

def fingers_up(lm):
    """Return [thumb, index, middle, ring, pinky] up-state as 0/1."""
    f = []
    f.append(1 if lm[4][1] < lm[3][1] else 0)          # thumb (x-axis)
    for tip in [8, 12, 16, 20]:                          # others (y-axis)
        f.append(1 if lm[tip][2] < lm[tip - 2][2] else 0)
    return f

def rotate_pts(pts, center, angle_deg):
    cx, cy = center
    a = math.radians(angle_deg)
    cos_a, sin_a = math.cos(a), math.sin(a)
    out = []
    for (x, y) in pts:
        dx, dy = x - cx, y - cy
        out.append((int(dx*cos_a - dy*sin_a + cx),
                    int(dx*sin_a + dy*cos_a + cy)))
    return out

# ─────────────────────────── DRAW SHAPES ─────────────────────
def draw_shapes_on(target):
    for sh in drawn_shapes:
        t    = sh["type"]
        col  = sh["color"]
        thk  = sh["thick"]
        ang  = sh.get("angle", 0)
        pts  = sh["pts"]
        cen  = sh["center"]

        if t == "LINE":
            p0, p1 = rotate_pts(pts, cen, ang)
            cv2.line(target, p0, p1, col, thk)

        elif t == "RECT":
            corners = rotate_pts(pts, cen, ang)
            cv2.polylines(target, [np.array(corners, np.int32)], True, col, thk)

        elif t == "CIRCLE":
            cv2.circle(target, cen, sh["radius"], col, thk)

# ─────────────────────────── NOTIFICATIONS ───────────────────
def set_notif(text):
    global notif_text, notif_timer
    notif_text  = text
    notif_timer = time.time()

def draw_notif(img):
    if not notif_text:
        return
    elapsed = time.time() - notif_timer
    if elapsed > 2.5:
        return
    fade = min(1.0, (2.5 - elapsed) / 0.4)
    overlay = img.copy()
    cv2.rectangle(overlay,
                  (CANVAS_W//2 - 220, CANVAS_H - 82),
                  (CANVAS_W//2 + 220, CANVAS_H - 32),
                  (12, 12, 30), -1)
    cv2.addWeighted(overlay, 0.72, img, 0.28, 0, img)
    col = tuple(int(c * fade) for c in (0, 255, 180))
    glow_text(img, notif_text,
              (CANVAS_W//2 - 210, CANVAS_H - 47),
              cv2.FONT_HERSHEY_SIMPLEX, 0.65, col, 2, gr=1)

# ─────────────────────────── UI HEADER ───────────────────────
header = np.zeros((UI_H, CANVAS_W, 3), np.uint8)

def draw_ui():
    """Rebuild header each frame (cheap: 165 rows only)."""
    header[:] = (16, 16, 26)

    # subtle top-to-bottom dim
    for y in range(UI_H):
        alpha = 1.0 - y / UI_H * 0.35
        header[y] = np.clip(header[y] * alpha, 0, 255).astype(np.uint8)

    font = cv2.FONT_HERSHEY_SIMPLEX

    # ── Tool buttons ──────────────────────────────────────────
    for (x1, y1, x2, y2, name) in tool_rects:
        active = (name == activeTool)
        border = (0, 210, 255) if active else (50, 50, 72)
        fill   = (0, 80, 120)  if active else (32, 32, 48)
        rounded_rect(header, (x1, y1), (x2, y2), border, r=8)
        rounded_rect(header, (x1+2, y1+2), (x2-2, y2-2), fill, r=6)
        col = (0, 255, 210) if active else (140, 140, 185)
        glow_text(header, name[:6],
                  (x1 + 5, y1 + TOOL_H//2 + 7),
                  font, 0.44, col, 1, gr=1)

    # ── Palette circles ───────────────────────────────────────
    for (cx, cy, col) in pal_circles:
        cv2.circle(header, (cx, cy), PAL_R + 2, (70, 70, 92), -1)
        cv2.circle(header, (cx, cy), PAL_R, col, -1)
        if col == drawColor:
            cv2.circle(header, (cx, cy), PAL_R + 4, (0, 255, 210), 2)

    # active-colour swatch
    sw_x = PAL_START_X + PAL_COLS * (PAL_R * 2 + PAL_GAP) + 10
    sw_y1, sw_y2 = PAL_START_Y - 4, PAL_START_Y + PAL_ROWS * (PAL_R*2+PAL_GAP) + 4
    cv2.rectangle(header, (sw_x, sw_y1), (sw_x + 42, sw_y2), (70,70,92), -1)
    cv2.rectangle(header, (sw_x+2, sw_y1+2), (sw_x+40, sw_y2-2), drawColor, -1)

    # ── Brush +/- buttons ─────────────────────────────────────
    bx1, by1, bx2, by2 = BINC_RECT
    rounded_rect(header, (bx1, by1), (bx2, by2), (0, 160, 70), r=7)
    glow_text(header, "+", (bx1+14, by2-10), font, 1.0, (255,255,255), 2)

    bx1, by1, bx2, by2 = BDEC_RECT
    rounded_rect(header, (bx1, by1), (bx2, by2), (180, 40, 40), r=7)
    glow_text(header, "-", (bx1+18, by2-10), font, 1.15, (255,255,255), 2)

    # size / tool readouts
    glow_text(header, f"BRUSH: {brushThickness}px",
              (BCTRL_X, 74), font, 0.48, (170, 215, 255), 1)
    glow_text(header, f"ERASE: {eraserThickness}px",
              (BCTRL_X, 94), font, 0.45, (195, 170, 255), 1)
    glow_text(header, f"TOOL : {activeTool}",
              (BCTRL_X, 116), font, 0.48, (0, 255, 195), 1, gr=1)

    # gesture hint bar
    hint = "GESTURE: 3-finger pinch = resize | 2-finger select | 1-finger draw"
    glow_text(header, hint, (CANVAS_W//2 - 330, UI_H - 6),
              font, 0.38, (90, 90, 140), 1, gr=0)

    # title
    glow_text(header, "AIR CANVAS ULTRA PRO",
              (CANVAS_W//2 - 150, UI_H - 20),
              font, 0.58, (0, 195, 255), 1, gr=2)

# ─────────────────────────── PINCH SIZE HUD ──────────────────
def draw_pinch_hud(img, lmList):
    """Draw a live pinch indicator when three-finger pinch is active."""
    if not pinch3_active:
        return
    tx, ty = lmList[4][1], lmList[4][2]
    ix, iy = lmList[8][1], lmList[8][2]
    mx, my = lmList[12][1], lmList[12][2]
    cx = (tx + ix + mx) // 3
    cy = (ty + iy + my) // 3

    size = eraserThickness if activeTool == "ERASER" else brushThickness
    col  = (160, 160, 160) if activeTool == "ERASER" else drawColor

    # centroid dot
    cv2.circle(img, (cx, cy), 6, col, -1)
    # size preview ring
    cv2.circle(img, (cx, cy), max(2, size), col, 2)
    # connecting lines to fingertips
    for (fx, fy) in [(tx,ty),(ix,iy),(mx,my)]:
        cv2.line(img, (cx,cy), (fx,fy), col, 1)
        cv2.circle(img, (fx,fy), 5, col, -1)

    # text label
    label = f"{'ERASER' if activeTool=='ERASER' else 'BRUSH'} SIZE: {size}"
    cv2.putText(img, label, (cx - 60, cy - size - 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 1)

# ─────────────────────────── MAIN LOOP ───────────────────────
print("\nGesture guide:")
print("  ☝  1 finger  → Draw / Erase / Shape drag")
print("  ✌  2 fingers → Select tool / colour / UI")
print("  🤌  3-finger pinch (thumb+index+middle) → Resize brush / eraser")
print("  ↩  U  / ↪  R  = Undo / Redo")
print("  +  / -  keys  = Brush size")
print("  S  = Save   |  C  = Clear   |  ESC = Quit\n")

while True:
    ok, img = cap.read()
    if not ok:
        print("❌  Frame read failed – retrying…")
        continue

    img = cv2.flip(img, 1)

    # ── FPS ───────────────────────────────────────────────────
    fps_times.append(time.time())
    if len(fps_times) > 1:
        fps = len(fps_times) / (fps_times[-1] - fps_times[0])
    else:
        fps = 0.0

    # ── Hand detection ────────────────────────────────────────
    imgRGB  = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = hands.process(imgRGB)

    lmList = []
    if results.multi_hand_landmarks:
        hand = results.multi_hand_landmarks[0]
        for _id, _lm in enumerate(hand.landmark):
            h, w, _ = img.shape
            lmList.append([_id, int(_lm.x * w), int(_lm.y * h)])
        mpDraw.draw_landmarks(img, hand, mpHands.HAND_CONNECTIONS,
                              LM_STYLE, CON_STYLE)

    if lmList:
        # fingertip positions
        ix1, iy1 = lmList[8][1],  lmList[8][2]    # index tip
        tx2, ty2 = lmList[4][1],  lmList[4][2]    # thumb tip
        mx3, my3 = lmList[12][1], lmList[12][2]   # middle tip

        fingers = fingers_up(lmList)
        # unpack for readability
        f_thumb, f_idx, f_mid, f_ring, f_pinky = fingers

        # ── THREE-FINGER PINCH  (thumb + index + middle up, ring + pinky down)
        #    → resize brush or eraser
        if f_thumb and f_idx and f_mid and not f_ring and not f_pinky:
            d1 = find_dist((tx2,ty2), (ix1,iy1))
            d2 = find_dist((tx2,ty2), (mx3,my3))
            d3 = find_dist((ix1,iy1), (mx3,my3))
            avg_spread = (d1 + d2 + d3) / 3.0

            if not pinch3_active:
                # Gesture just started – record baseline
                pinch3_active    = True
                pinch3_base_dist = avg_spread
                pinch3_base_size = (eraserThickness if activeTool == "ERASER"
                                    else brushThickness)

            # Scale size proportionally from baseline
            ratio    = avg_spread / max(pinch3_base_dist, 1)
            new_size = int(pinch3_base_size * ratio)

            if activeTool == "ERASER":
                eraserThickness = int(np.clip(new_size, 5, 80))
            else:
                brushThickness  = int(np.clip(new_size, 2, 60))

            # Reset draw anchor so brush doesn't jump after pinch
            xp, yp = 0, 0
            draw_pinch_hud(img, lmList)

        # ── SELECTION MODE  (index + middle up, others down)
        elif f_idx and f_mid and not f_thumb and not f_ring and not f_pinky:
            pinch3_active    = False
            pinch3_base_dist = None
            xp, yp           = 0, 0

            # cursor dot
            cv2.circle(img, (ix1, iy1), 12, (0, 255, 190), 2)
            cv2.circle(img, (ix1, iy1),  4, (0, 255, 190), -1)

            if iy1 < UI_H:
                # ── Tool buttons ────────────────────────────
                for (tx1, ty1, tx2_, ty2_, tname) in tool_rects:
                    if tx1 <= ix1 <= tx2_ and ty1 <= iy1 <= ty2_:
                        if tname == "CLEAR":
                            undoStack.append(canvas.copy())
                            canvas[:] = 0
                            drawn_shapes.clear()
                            set_notif("Canvas cleared")
                        elif tname == "SAVE":
                            merged = canvas.copy()
                            draw_shapes_on(merged)
                            fname = f"AirCanvas_{int(time.time())}.png"
                            cv2.imwrite(fname, merged)
                            set_notif(f"Saved  {fname}")
                        elif tname == "UNDO":
                            if undoStack:
                                item = undoStack.pop()
                                if isinstance(item, tuple) and item[0] == "shapes":
                                    redoStack.append(("shapes", [s.copy() for s in drawn_shapes]))
                                    drawn_shapes.clear()
                                    drawn_shapes.extend(item[1])
                                else:
                                    redoStack.append(canvas.copy())
                                    canvas[:] = item
                            set_notif("Undo")
                        elif tname == "REDO":
                            if redoStack:
                                item = redoStack.pop()
                                if isinstance(item, tuple) and item[0] == "shapes":
                                    undoStack.append(("shapes", [s.copy() for s in drawn_shapes]))
                                    drawn_shapes.clear()
                                    drawn_shapes.extend(item[1])
                                else:
                                    undoStack.append(canvas.copy())
                                    canvas[:] = item
                            set_notif("Redo")
                        else:
                            activeTool = tname
                            set_notif(f"Tool: {tname}")

                # ── Palette ──────────────────────────────────
                for (pcx, pcy, pcol) in pal_circles:
                    if find_dist((ix1, iy1), (pcx, pcy)) < PAL_R + 7:
                        drawColor = pcol

                # ── Brush +/- buttons ────────────────────────
                if in_rect(ix1, iy1, BINC_RECT):
                    brushThickness = min(60, brushThickness + 2)
                if in_rect(ix1, iy1, BDEC_RECT):
                    brushThickness = max(2, brushThickness - 2)

        # ── DRAW MODE  (only index finger up)
        elif f_idx and not f_mid and not f_thumb:
            pinch3_active    = False
            pinch3_base_dist = None

            eff_y = max(iy1, UI_H + 2)

            # live cursor
            cv2.circle(img, (ix1, iy1),
                       max(3, brushThickness // 2), drawColor, -1)

            # ── BRUSH ────────────────────────────────────────
            if activeTool == "BRUSH":
                if xp == 0 and yp == 0:
                    xp, yp = ix1, eff_y
                    undoStack.append(canvas.copy())
                cv2.line(canvas, (xp, yp), (ix1, eff_y),
                         drawColor, brushThickness)
                xp, yp = ix1, eff_y

            # ── ERASER ───────────────────────────────────────
            elif activeTool == "ERASER":
                cv2.circle(canvas, (ix1, eff_y), eraserThickness, (0,0,0), -1)
                cv2.circle(img,    (ix1, eff_y), eraserThickness, (90,90,90), 2)
                xp, yp = ix1, eff_y

            # ── SHAPE TOOLS (drag preview) ────────────────────
            elif activeTool in ("LINE", "RECT", "CIRCLE"):
                if xp == 0 and yp == 0:
                    drag_start = (ix1, eff_y)
                    xp, yp     = ix1, eff_y
                if drag_start:
                    prev = img.copy()
                    if activeTool == "LINE":
                        cv2.line(prev, drag_start, (ix1, eff_y),
                                 drawColor, brushThickness)
                    elif activeTool == "RECT":
                        cv2.rectangle(prev, drag_start, (ix1, eff_y),
                                      drawColor, brushThickness)
                    elif activeTool == "CIRCLE":
                        r = int(find_dist(drag_start, (ix1, eff_y)))
                        cv2.circle(prev, drag_start, r, drawColor, brushThickness)
                    img[:] = prev

            # ── MOVE (last shape) ─────────────────────────────
            elif activeTool == "MOVE":
                if drawn_shapes:
                    if shape_anchor is None:
                        shape_anchor = (ix1, eff_y)
                    else:
                        dx = ix1 - shape_anchor[0]
                        dy = eff_y - shape_anchor[1]
                        sh = drawn_shapes[-1]
                        sh["pts"]    = [(p[0]+dx, p[1]+dy) for p in sh["pts"]]
                        sh["center"] = (sh["center"][0]+dx, sh["center"][1]+dy)
                        shape_anchor = (ix1, eff_y)
                xp, yp = ix1, eff_y

            # ── ROTATE (last shape) ───────────────────────────
            elif activeTool == "ROTATE":
                if drawn_shapes:
                    if shape_anchor is None:
                        shape_anchor = (ix1, eff_y)
                    else:
                        dx = ix1 - shape_anchor[0]
                        drawn_shapes[-1]["angle"] = (
                            drawn_shapes[-1].get("angle", 0) + dx * 0.6
                        )
                        shape_anchor = (ix1, eff_y)
                xp, yp = ix1, eff_y

        # ── ALL OTHER FINGER COMBOS → commit / idle ────────────
        else:
            pinch3_active    = False
            pinch3_base_dist = None

            # Commit shape if drag was in progress
            if activeTool in ("LINE", "RECT", "CIRCLE") and drag_start:
                eff_y = max(iy1, UI_H + 2)
                cx_s  = (drag_start[0] + ix1) // 2
                cy_s  = (drag_start[1] + eff_y) // 2

                if activeTool == "LINE":
                    sh = {"type":"LINE",
                          "pts":[drag_start, (ix1, eff_y)],
                          "center":(cx_s, cy_s),
                          "color":drawColor, "thick":brushThickness, "angle":0}

                elif activeTool == "RECT":
                    corners = [drag_start,
                               (ix1, drag_start[1]),
                               (ix1, eff_y),
                               (drag_start[0], eff_y)]
                    sh = {"type":"RECT", "pts":corners,
                          "center":(cx_s, cy_s),
                          "color":drawColor, "thick":brushThickness, "angle":0}

                elif activeTool == "CIRCLE":
                    r = int(find_dist(drag_start, (ix1, eff_y)))
                    sh = {"type":"CIRCLE",
                          "pts":[drag_start, (ix1, eff_y)],
                          "center":drag_start, "radius":r,
                          "color":drawColor, "thick":brushThickness, "angle":0}

                undoStack.append(("shapes", [s.copy() for s in drawn_shapes]))
                drawn_shapes.append(sh)
                drag_start = None

            if activeTool in ("MOVE", "ROTATE"):
                shape_anchor = None

            xp, yp = 0, 0

    else:
        # No hand detected
        pinch3_active    = False
        pinch3_base_dist = None
        xp, yp           = 0, 0
        drag_start       = None
        shape_anchor     = None

    # ─────────── COMPOSE FRAME ───────────────────────────────
    combined = canvas.copy()
    draw_shapes_on(combined)

    # Merge drawing onto camera feed (black = transparent)
    gray = cv2.cvtColor(combined, cv2.COLOR_BGR2GRAY)
    _, inv_mask = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY_INV)
    inv_mask = cv2.cvtColor(inv_mask, cv2.COLOR_GRAY2BGR)
    img = cv2.bitwise_and(img, inv_mask)
    img = cv2.bitwise_or(img, combined)

    # Draw UI header
    draw_ui()
    img[0:UI_H, :] = header

    # ─── Brush / Eraser live preview (bottom-left) ───────────
    px, py = 55, CANVAS_H - 55
    if activeTool == "ERASER":
        cv2.circle(img, (px, py), eraserThickness, (130,130,130), 2)
        cv2.putText(img, f"ERASER {eraserThickness}px",
                    (10, CANVAS_H - 15), cv2.FONT_HERSHEY_SIMPLEX,
                    0.45, (160,160,160), 1)
    else:
        cv2.circle(img, (px, py), max(2, brushThickness), drawColor, -1)
        cv2.putText(img, f"BRUSH {brushThickness}px",
                    (10, CANVAS_H - 15), cv2.FONT_HERSHEY_SIMPLEX,
                    0.45, (170, 215, 255), 1)

    # ─── Notification ────────────────────────────────────────
    draw_notif(img)

    # ─── FPS ─────────────────────────────────────────────────
    cv2.putText(img, f"FPS {fps:.0f}",
                (CANVAS_W - 90, CANVAS_H - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (60, 60, 100), 1)

    cv2.imshow("Air Canvas ULTRA PRO", img)

    # ─────────── KEYBOARD SHORTCUTS ──────────────────────────
    key = cv2.waitKey(1) & 0xFF

    if key == 27:          # ESC – quit
        print("👋  Goodbye!")
        break

    elif key == ord('u'):  # Undo
        if undoStack:
            item = undoStack.pop()
            if isinstance(item, tuple) and item[0] == "shapes":
                redoStack.append(("shapes", [s.copy() for s in drawn_shapes]))
                drawn_shapes.clear(); drawn_shapes.extend(item[1])
            else:
                redoStack.append(canvas.copy()); canvas[:] = item
        set_notif("Undo")

    elif key == ord('r'):  # Redo
        if redoStack:
            item = redoStack.pop()
            if isinstance(item, tuple) and item[0] == "shapes":
                undoStack.append(("shapes", [s.copy() for s in drawn_shapes]))
                drawn_shapes.clear(); drawn_shapes.extend(item[1])
            else:
                undoStack.append(canvas.copy()); canvas[:] = item
        set_notif("Redo")

    elif key in (ord('+'), ord('=')):
        brushThickness = min(60, brushThickness + 2)
        set_notif(f"Brush size: {brushThickness}")

    elif key == ord('-'):
        brushThickness = max(2, brushThickness - 2)
        set_notif(f"Brush size: {brushThickness}")

    elif key == ord('s'):  # Save
        merged = canvas.copy(); draw_shapes_on(merged)
        fname  = f"AirCanvas_{int(time.time())}.png"
        cv2.imwrite(fname, merged)
        set_notif(f"Saved: {fname}")

    elif key == ord('c'):  # Clear
        undoStack.append(canvas.copy())
        canvas[:] = 0; drawn_shapes.clear()
        set_notif("Canvas cleared")

    elif key == ord('e'):  # Toggle eraser quickly
        activeTool = "ERASER" if activeTool != "ERASER" else "BRUSH"
        set_notif(f"Tool: {activeTool}")

# ─────────────────────────── CLEANUP ─────────────────────────
cap.release()
cv2.destroyAllWindows()
print("Session ended. Goodbye!")