import cv2
import mediapipe as mp
import numpy as np
import time
from collections import deque

mp_hands = mp.solutions.hands
cap = cv2.VideoCapture(0)

# تنظیم وضوح وبکم به حداکثر (اختیاری - اگر وبکم پشتیبانی کنه)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

hands = mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.7, min_tracking_confidence=0.7)

# پنجره تمام‌صفحه
cv2.namedWindow("Code_rah", cv2.WND_PROP_FULLSCREEN)
cv2.setWindowProperty("Code_rah", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

# تاریخچه موقعیت برای افکت تریل
trail_history = {0: deque(maxlen=20), 1: deque(maxlen=20)}
sparkle_particles = []


def hsv_to_rgb(h, s, v):
    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))


def get_rainbow_color(index, total, offset=0):
    hue = ((index / total) * 360 + offset) % 360
    return hsv_to_rgb(hue, 1.0, 1.0)


def darken_color(color, factor=0.5):
    return tuple(int(c * factor) for c in color)


def lighten_color(color, factor=1.3):
    return tuple(min(255, int(c * factor)) for c in color)


def draw_thick_rope(base_layer, glow_layer, p1, p2, color1, color2, thickness=16):
    """رسم طناب با نور ملایم‌تر"""
    if p1 == p2:
        return

    outer_thick = thickness
    mid_thick = int(thickness * 0.7)
    inner_thick = int(thickness * 0.35)
    core_thick = int(thickness * 0.15)

    dark_color1 = darken_color(color1, 0.4)
    dark_color2 = darken_color(color2, 0.4)
    mid_color1 = color1
    mid_color2 = color2
    light_color1 = lighten_color(color1, 1.4)
    light_color2 = lighten_color(color2, 1.4)
    core_color = (255, 255, 255)

    # لایه خارجی
    for i, t in enumerate([0, 0.5, 1]):
        color = (dark_color1 if t < 0.5 else dark_color2)
        offset = (i - 1) * 2
        p1_off = (p1[0] + offset, p1[1] + offset)
        p2_off = (p2[0] + offset, p2[1] + offset)
        cv2.line(base_layer, p1_off, p2_off, color, outer_thick, cv2.LINE_AA)

    # لایه میانی
    steps = 3
    for i in range(steps):
        t = i / (steps - 1)
        r = int(mid_color1[0] * (1 - t) + mid_color2[0] * t)
        g = int(mid_color1[1] * (1 - t) + mid_color2[1] * t)
        b = int(mid_color1[2] * (1 - t) + mid_color2[2] * t)

        for off in range(-2, 3, 2):
            alpha = 1 - abs(off) * 0.15
            final_color = (int(r * alpha), int(g * alpha), int(b * alpha))
            p1_off = (p1[0] + off, p1[1])
            p2_off = (p2[0] + off, p2[1])
            cv2.line(base_layer, p1_off, p2_off, final_color, mid_thick, cv2.LINE_AA)

    # لایه درخشان داخلی
    for i in range(steps):
        t = i / (steps - 1)
        r = int(light_color1[0] * (1 - t) + light_color2[0] * t)
        g = int(light_color1[1] * (1 - t) + light_color2[1] * t)
        b = int(light_color1[2] * (1 - t) + light_color2[2] * t)
        cv2.line(base_layer, p1, p2, (r, g, b), inner_thick, cv2.LINE_AA)

    # هسته مرکزی
    cv2.line(base_layer, p1, p2, core_color, core_thick, cv2.LINE_AA)

    # لایه glow ملایم‌تر (کمتر از قبل)
    glow_color = tuple(int(c * 0.6) for c in
                       ((color1[0] + color2[0]) // 2, (color1[1] + color2[1]) // 2, (color1[2] + color2[2]) // 2))
    cv2.line(glow_layer, p1, p2, glow_color, thickness + 8, cv2.LINE_AA)  # کاهش از 12 به 8


def draw_electric_arc(overlay, p1, p2, color, intensity=1.0):
    if p1 == p2:
        return
    points = [p1]
    segments = 5
    for i in range(1, segments):
        t = i / segments
        base_x = int(p1[0] + (p2[0] - p1[0]) * t)
        base_y = int(p1[1] + (p2[1] - p1[1]) * t)
        offset = int(15 * intensity * (1 - abs(2 * t - 1)))
        if offset > 0:
            base_x += np.random.randint(-offset, offset)
            base_y += np.random.randint(-offset, offset)
        points.append((base_x, base_y))
    points.append(p2)

    for i in range(len(points) - 1):
        thickness = max(1, int(6 * intensity * (1 - abs(2 * (i / segments) - 1))))
        cv2.line(overlay, points[i], points[i + 1], color, thickness)


def draw_neon_joint(overlay, center, color, radius=12):
    if radius <= 0:
        return
    cv2.circle(overlay, center, radius + 4, darken_color(color, 0.3), -1)
    cv2.circle(overlay, center, radius, color, -1)
    cv2.circle(overlay, (center[0] - 3, center[1] - 3), radius // 2, lighten_color(color, 1.5), -1)
    cv2.circle(overlay, center, max(2, radius // 4), (255, 255, 255), -1)


def add_sparkle(x, y, color):
    for _ in range(2):
        angle = np.random.uniform(0, 2 * np.pi)
        speed = np.random.uniform(2, 5)
        sparkle_particles.append({
            'x': float(x), 'y': float(y),
            'vx': np.cos(angle) * speed,
            'vy': np.sin(angle) * speed,
            'life': 1.0,
            'color': color,
            'size': np.random.randint(3, 6)
        })


def update_sparkles(overlay):
    global sparkle_particles
    new_particles = []
    h, w = overlay.shape[:2]

    for p in sparkle_particles:
        p['x'] += p['vx']
        p['y'] += p['vy']
        p['life'] -= 0.025

        if 0 <= int(p['x']) < w and 0 <= int(p['y']) < h and p['life'] > 0:
            size = max(1, int(p['size'] * p['life']))
            color = tuple(int(c * p['life']) for c in p['color'])
            cv2.circle(overlay, (int(p['x']), int(p['y'])), size, color, -1)
            cv2.circle(overlay, (int(p['x']), int(p['y'])), size * 2, color, 1)
            new_particles.append(p)

    sparkle_particles = new_particles


FINGER_TIPS = [4, 8, 12, 16, 20]
BRIDGE_PAIRS = [(4, 4), (8, 8), (12, 12), (16, 16), (20, 20), (0, 0)]

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)

    rope_layer = np.zeros_like(frame)
    glow_layer = np.zeros_like(frame)
    joint_layer = np.zeros_like(frame)
    particle_layer = np.zeros_like(frame)

    current_time = time.time() * 80
    color_offset = current_time % 360

    current_positions = {}

    if result.multi_hand_landmarks:
        num_hands = len(result.multi_hand_landmarks)

        for hand_idx, hand_landmarks in enumerate(result.multi_hand_landmarks):
            pos = {}
            for i, lm in enumerate(hand_landmarks.landmark):
                x, y = int(lm.x * w), int(lm.y * h)
                pos[i] = (x, y)

                if i in FINGER_TIPS and np.random.random() > 0.9:
                    color = get_rainbow_color(i, 21, color_offset + hand_idx * 180)
                    add_sparkle(x, y, color)

            current_positions[hand_idx] = pos
            trail_history[hand_idx].append(pos.copy())

        # رسم طناب‌ها
        for hand_idx, pos in current_positions.items():
            hand_color_offset = color_offset + (hand_idx * 180)

            for conn_idx, conn in enumerate(mp_hands.HAND_CONNECTIONS):
                s, e = conn
                if s in pos and e in pos:
                    unique_idx = conn_idx + (hand_idx * 100)
                    color1 = get_rainbow_color(unique_idx, 50, hand_color_offset)
                    color2 = get_rainbow_color(unique_idx + 1, 50, hand_color_offset)
                    draw_thick_rope(rope_layer, glow_layer, pos[s], pos[e], color1, color2, thickness=14)

        # رسم مفاصل
        for hand_idx, pos in current_positions.items():
            for lm_idx, point in pos.items():
                if lm_idx in FINGER_TIPS:
                    color = get_rainbow_color(lm_idx, 21, color_offset + hand_idx * 180)
                    draw_neon_joint(joint_layer, point, color, radius=12)
                else:
                    joint_color = get_rainbow_color(lm_idx + hand_idx * 50, 40, color_offset)
                    draw_neon_joint(joint_layer, point, joint_color, radius=8)

        # اتصال بین دو دست
        if len(current_positions) == 2:
            pos0, pos1 = current_positions[0], current_positions[1]

            for i, (a, b) in enumerate(BRIDGE_PAIRS):
                if a in pos0 and b in pos1:
                    bridge_color = get_rainbow_color(i, len(BRIDGE_PAIRS), color_offset * 3)
                    draw_electric_arc(glow_layer, pos0[a], pos1[b], tuple(int(c * 0.3) for c in bridge_color), 1.5)
                    draw_thick_rope(rope_layer, glow_layer, pos0[a], pos1[b], bridge_color, bridge_color, thickness=10)
                    mid = ((pos0[a][0] + pos1[b][0]) // 2, (pos0[a][1] + pos1[b][1]) // 2)
                    draw_neon_joint(joint_layer, mid, (255, 255, 255), radius=14)
                    if np.random.random() > 0.6:
                        add_sparkle(mid[0], mid[1], bridge_color)

    update_sparkles(particle_layer)

    # بلورینگ ملایم‌تر
    glow_blur_heavy = cv2.GaussianBlur(glow_layer, (51, 51), 20)  # کمتر از قبل (30->20)
    glow_blur_medium = cv2.GaussianBlur(glow_layer, (25, 25), 10)  # کمتر از قبل (15->10)
    glow_blur_light = cv2.GaussianBlur(glow_layer, (11, 11), 3)  # کمتر از قبل (5->3)

    rope_blur = cv2.GaussianBlur(rope_layer, (5, 5), 2)

    # ترکیب با شفافیت پایین‌تر (کاهش نورها)
    final = frame.copy()

    # کاهش شدت نورها (0.4,0.6,0.8 -> 0.15, 0.25, 0.4)
    final = cv2.addWeighted(final, 1.0, glow_blur_heavy, 0.15, 0)
    final = cv2.addWeighted(final, 1.0, glow_blur_medium, 0.25, 0)
    final = cv2.addWeighted(final, 1.0, glow_blur_light, 0.4, 0)

    final = cv2.addWeighted(final, 1.0, rope_blur, 0.9, 0)
    final = cv2.addWeighted(final, 1.0, rope_layer, 1.0, 0)
    final = cv2.addWeighted(final, 1.0, joint_layer, 1.0, 0)
    #final = cv2.addWeighted(final, 1.0, particle_layer, 1.0, 0)  # فعال کن اگه خواستی

    cv2.imshow("Code_rah", final)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
