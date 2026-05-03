import math
import time
from enum import Enum
from PIL import Image, ImageDraw

WIDTH = 128
HEIGHT = 160

FACE_CX = 64
FACE_CY = 82
FACE_R = 46

EYE_Y = 70
EYE_R = 7
L_EYE_X = 46
R_EYE_X = 82

MOUTH_Y = 102
BLUSH_Y = 90
BLUSH_R = 6
L_BLUSH_X = 36
R_BLUSH_X = 92

BROW_Y = 58

SKIN = (255, 218, 185)
SKIN_SHADOW = (245, 200, 170)
EYE_COL = (50, 40, 40)
EYE_HIGHLIGHT = (255, 255, 255)
MOUTH_COL = (220, 100, 100)
MOUTH_DARK = (180, 70, 70)
BLUSH_COL = (255, 180, 190)
TEAR_COL = (150, 210, 255)
HAIR_COL = (70, 50, 40)
HAIR_HIGHLIGHT = (110, 80, 60)
BROW_COL = (60, 45, 35)
NOSE_COL = (240, 190, 160)


class AvatarState(Enum):
    IDLE = "idle"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    SURPRISED = "surprised"
    WAVE = "wave"
    NOD = "nod"
    THINK = "think"
    SLEEP = "sleep"
    TALK = "talk"


BG_COLORS = {
    AvatarState.IDLE: (135, 206, 235),
    AvatarState.HAPPY: (255, 230, 200),
    AvatarState.SAD: (176, 196, 222),
    AvatarState.ANGRY: (255, 200, 200),
    AvatarState.SURPRISED: (255, 255, 200),
    AvatarState.WAVE: (200, 240, 220),
    AvatarState.NOD: (220, 220, 255),
    AvatarState.THINK: (230, 220, 250),
    AvatarState.SLEEP: (40, 40, 80),
    AvatarState.TALK: (200, 235, 255),
}


class AvatarRenderer:
    def __init__(self):
        self.state = AvatarState.IDLE
        self.prev_state = AvatarState.IDLE
        self.frame_count = 0
        self.blink_timer = 0
        self.is_blinking = False
        self.mouth_phase = 0.0
        self.transition_progress = 1.0

    def set_state(self, state_name: str):
        try:
            new_state = AvatarState(state_name.lower())
            if new_state != self.state:
                self.prev_state = self.state
                self.state = new_state
                self.transition_progress = 0.0
        except ValueError:
            pass

    def render(self) -> Image.Image:
        self._update_animation()
        img = Image.new("RGB", (WIDTH, HEIGHT), self._bg_color())
        draw = ImageDraw.Draw(img)
        self._draw_bg_stars(draw)
        self._draw_hair_back(draw)
        self._draw_face(draw)
        self._draw_ears(draw)
        self._draw_eyes(draw)
        self._draw_nose(draw)
        self._draw_mouth(draw)
        self._draw_blush(draw)
        self._draw_eyebrows(draw)
        self._draw_hair_front(draw)
        self._draw_extras(draw)
        self.frame_count += 1
        return img

    def _update_animation(self):
        self.blink_timer += 1
        blink_interval = 100
        if self.state == AvatarState.SLEEP:
            self.is_blinking = True
        elif self.blink_timer >= blink_interval:
            self.is_blinking = True
            if self.blink_timer >= blink_interval + 5:
                self.is_blinking = False
                self.blink_timer = 0
        else:
            self.is_blinking = False

        if self.state == AvatarState.TALK:
            self.mouth_phase += 0.4
        else:
            self.mouth_phase *= 0.9

        if self.transition_progress < 1.0:
            self.transition_progress = min(1.0, self.transition_progress + 0.1)

    def _bg_color(self):
        cur = BG_COLORS.get(self.state, BG_COLORS[AvatarState.IDLE])
        if self.transition_progress < 1.0:
            prev = BG_COLORS.get(self.prev_state, BG_COLORS[AvatarState.IDLE])
            t = self.transition_progress
            return tuple(int(prev[i] + (cur[i] - prev[i]) * t) for i in range(3))
        return cur

    def _draw_bg_stars(self, draw: ImageDraw.Draw):
        if self.state == AvatarState.SLEEP:
            import random
            rng = random.Random(42)
            for _ in range(15):
                x = rng.randint(5, WIDTH - 5)
                y = rng.randint(5, 50)
                r = rng.randint(1, 2)
                brightness = 150 + int(50 * math.sin(self.frame_count * 0.05 + x))
                draw.ellipse([x - r, y - r, x + r, y + r],
                             fill=(brightness, brightness, brightness + 50))
            draw.arc([20, 10, 50, 40], 200, 340, fill=(220, 220, 180), width=2)

    def _draw_hair_back(self, draw: ImageDraw.Draw):
        draw.ellipse([FACE_CX - FACE_R - 4, FACE_CY - FACE_R - 12,
                       FACE_CX + FACE_R + 4, FACE_CY + 10],
                      fill=HAIR_COL)

    def _draw_face(self, draw: ImageDraw.Draw):
        draw.ellipse([FACE_CX - FACE_R, FACE_CY - FACE_R,
                       FACE_CX + FACE_R, FACE_CY + FACE_R],
                      fill=SKIN)
        draw.ellipse([FACE_CX - FACE_R + 5, FACE_CY - FACE_R + 8,
                       FACE_CX + FACE_R - 5, FACE_CY + FACE_R - 2],
                      fill=SKIN)

    def _draw_ears(self, draw: ImageDraw.Draw):
        draw.ellipse([FACE_CX - FACE_R - 5, FACE_CY - 8,
                       FACE_CX - FACE_R + 5, FACE_CY + 8],
                      fill=SKIN)
        draw.ellipse([FACE_CX + FACE_R - 5, FACE_CY - 8,
                       FACE_CX + FACE_R + 5, FACE_CY + 8],
                      fill=SKIN)

    def _draw_eyes(self, draw: ImageDraw.Draw):
        if self.is_blinking and self.state != AvatarState.HAPPY:
            self._draw_eyes_closed(draw)
        elif self.state == AvatarState.HAPPY:
            self._draw_eyes_happy(draw)
        elif self.state == AvatarState.SURPRISED:
            self._draw_eyes_big(draw)
        elif self.state == AvatarState.THINK:
            self._draw_eyes_wink_left(draw)
        elif self.state == AvatarState.SLEEP:
            self._draw_eyes_closed(draw)
        else:
            self._draw_eyes_normal(draw)

    def _draw_eyes_normal(self, draw: ImageDraw.Draw):
        for ex in (L_EYE_X, R_EYE_X):
            draw.ellipse([ex - EYE_R, EYE_Y - EYE_R, ex + EYE_R, EYE_Y + EYE_R],
                          fill=(255, 255, 255))
            draw.ellipse([ex - EYE_R + 1, EYE_Y - EYE_R + 1,
                           ex + EYE_R - 1, EYE_Y + EYE_R - 1],
                          fill=EYE_COL)
            draw.ellipse([ex + 1, EYE_Y - 4, ex + 4, EYE_Y - 1],
                          fill=EYE_HIGHLIGHT)
            draw.ellipse([ex - 2, EYE_Y + 1, ex + 1, EYE_Y + 3],
                          fill=(255, 255, 255, 180))

    def _draw_eyes_happy(self, draw: ImageDraw.Draw):
        for ex in (L_EYE_X, R_EYE_X):
            draw.arc([ex - 8, EYE_Y - 5, ex + 8, EYE_Y + 5],
                      0, 180, fill=EYE_COL, width=3)

    def _draw_eyes_closed(self, draw: ImageDraw.Draw):
        for ex in (L_EYE_X, R_EYE_X):
            draw.line([ex - 7, EYE_Y, ex + 7, EYE_Y], fill=EYE_COL, width=2)
            if self.state == AvatarState.SLEEP:
                draw.text((ex - 4, EYE_Y - 10), "z", fill=(200, 200, 255))

    def _draw_eyes_big(self, draw: ImageDraw.Draw):
        r = EYE_R + 3
        for ex in (L_EYE_X, R_EYE_X):
            draw.ellipse([ex - r, EYE_Y - r, ex + r, EYE_Y + r],
                          fill=(255, 255, 255))
            draw.ellipse([ex - r + 2, EYE_Y - r + 2, ex + r - 2, EYE_Y + r - 2],
                          fill=EYE_COL)
            draw.ellipse([ex - 2, EYE_Y - 5, ex + 3, EYE_Y - 1],
                          fill=EYE_HIGHLIGHT)
            draw.ellipse([ex + 2, EYE_Y + 1, ex + 5, EYE_Y + 4],
                          fill=(230, 230, 255))

    def _draw_eyes_wink_left(self, draw: ImageDraw.Draw):
        draw.line([L_EYE_X - 7, EYE_Y, L_EYE_X + 7, EYE_Y], fill=EYE_COL, width=2)
        draw.ellipse([R_EYE_X - EYE_R, EYE_Y - EYE_R,
                       R_EYE_X + EYE_R, EYE_Y + EYE_R],
                      fill=(255, 255, 255))
        draw.ellipse([R_EYE_X - EYE_R + 1, EYE_Y - EYE_R + 1,
                       R_EYE_X + EYE_R - 1, EYE_Y + EYE_R - 1],
                      fill=EYE_COL)
        draw.ellipse([R_EYE_X + 1, EYE_Y - 4, R_EYE_X + 4, EYE_Y - 1],
                      fill=EYE_HIGHLIGHT)

    def _draw_nose(self, draw: ImageDraw.Draw):
        draw.ellipse([FACE_CX - 2, FACE_CY + 2, FACE_CX + 2, FACE_CY + 5],
                      fill=NOSE_COL)

    def _draw_mouth(self, draw: ImageDraw.Draw):
        if self.state == AvatarState.HAPPY or self.state == AvatarState.WAVE:
            self._draw_mouth_smile(draw)
        elif self.state == AvatarState.SAD:
            self._draw_mouth_frown(draw)
        elif self.state == AvatarState.ANGRY:
            self._draw_mouth_frown(draw)
        elif self.state == AvatarState.SURPRISED:
            self._draw_mouth_open(draw, 8)
        elif self.state == AvatarState.TALK:
            openness = int(abs(math.sin(self.mouth_phase)) * 8) + 2
            self._draw_mouth_open(draw, openness)
        elif self.state == AvatarState.THINK:
            self._draw_mouth_small(draw)
        elif self.state == AvatarState.SLEEP:
            draw.line([FACE_CX - 5, MOUTH_Y, FACE_CX + 5, MOUTH_Y],
                      fill=MOUTH_DARK, width=1)
        else:
            draw.line([FACE_CX - 8, MOUTH_Y, FACE_CX + 8, MOUTH_Y],
                      fill=MOUTH_DARK, width=2)

    def _draw_mouth_smile(self, draw: ImageDraw.Draw):
        draw.arc([FACE_CX - 12, MOUTH_Y - 8, FACE_CX + 12, MOUTH_Y + 8],
                  10, 170, fill=MOUTH_COL, width=2)

    def _draw_mouth_frown(self, draw: ImageDraw.Draw):
        draw.arc([FACE_CX - 10, MOUTH_Y - 4, FACE_CX + 10, MOUTH_Y + 10],
                  190, 350, fill=MOUTH_COL, width=2)

    def _draw_mouth_open(self, draw: ImageDraw.Draw, r: int):
        draw.ellipse([FACE_CX - r, MOUTH_Y - r + 2, FACE_CX + r, MOUTH_Y + r + 2],
                      fill=MOUTH_COL)
        draw.ellipse([FACE_CX - r + 2, MOUTH_Y - r + 4, FACE_CX + r - 2, MOUTH_Y + 2],
                      fill=MOUTH_DARK)

    def _draw_mouth_small(self, draw: ImageDraw.Draw):
        draw.ellipse([FACE_CX - 3, MOUTH_Y - 2, FACE_CX + 3, MOUTH_Y + 2],
                      fill=MOUTH_COL)

    def _draw_blush(self, draw: ImageDraw.Draw):
        if self.state in (AvatarState.HAPPY, AvatarState.WAVE, AvatarState.THINK):
            draw.ellipse([L_BLUSH_X - BLUSH_R, BLUSH_Y - BLUSH_R + 2,
                           L_BLUSH_X + BLUSH_R, BLUSH_Y + BLUSH_R + 2],
                          fill=BLUSH_COL)
            draw.ellipse([R_BLUSH_X - BLUSH_R, BLUSH_Y - BLUSH_R + 2,
                           R_BLUSH_X + BLUSH_R, BLUSH_Y + BLUSH_R + 2],
                          fill=BLUSH_COL)

    def _draw_eyebrows(self, draw: ImageDraw.Draw):
        if self.state == AvatarState.ANGRY:
            draw.line([L_EYE_X - 8, BROW_Y + 2, L_EYE_X + 8, BROW_Y - 3],
                      fill=BROW_COL, width=2)
            draw.line([R_EYE_X - 8, BROW_Y - 3, R_EYE_X + 8, BROW_Y + 2],
                      fill=BROW_COL, width=2)
        elif self.state == AvatarState.SURPRISED:
            draw.line([L_EYE_X - 8, BROW_Y - 5, L_EYE_X + 8, BROW_Y - 5],
                      fill=BROW_COL, width=2)
            draw.line([R_EYE_X - 8, BROW_Y - 5, R_EYE_X + 8, BROW_Y - 5],
                      fill=BROW_COL, width=2)
        elif self.state == AvatarState.SAD:
            draw.line([L_EYE_X - 8, BROW_Y - 3, L_EYE_X + 4, BROW_Y + 1],
                      fill=BROW_COL, width=2)
            draw.line([R_EYE_X - 4, BROW_Y + 1, R_EYE_X + 8, BROW_Y - 3],
                      fill=BROW_COL, width=2)
        elif self.state == AvatarState.THINK:
            draw.line([L_EYE_X - 8, BROW_Y - 4, L_EYE_X + 8, BROW_Y - 4],
                      fill=BROW_COL, width=2)

    def _draw_hair_front(self, draw: ImageDraw.Draw):
        draw.polygon([
            (FACE_CX - FACE_R - 2, FACE_CY - FACE_R + 10),
            (FACE_CX - 20, FACE_CY - FACE_R - 10),
            (FACE_CX - 5, FACE_CY - FACE_R + 8),
            (FACE_CX + 5, FACE_CY - FACE_R - 5),
            (FACE_CX + 20, FACE_CY - FACE_R + 5),
            (FACE_CX + FACE_R + 2, FACE_CY - FACE_R + 10),
        ], fill=HAIR_COL)
        draw.polygon([
            (FACE_CX - 15, FACE_CY - FACE_R - 5),
            (FACE_CX, FACE_CY - FACE_R + 12),
            (FACE_CX + 15, FACE_CY - FACE_R - 2),
        ], fill=HAIR_HIGHLIGHT)

    def _draw_extras(self, draw: ImageDraw.Draw):
        if self.state == AvatarState.SAD:
            draw.ellipse([R_EYE_X + 3, EYE_Y + 8, R_EYE_X + 7, EYE_Y + 18],
                          fill=TEAR_COL)
            draw.ellipse([R_EYE_X + 2, EYE_Y + 15, R_EYE_X + 8, EYE_Y + 22],
                          fill=TEAR_COL)
        if self.state == AvatarState.WAVE:
            hand_x = FACE_CX + FACE_R + 8
            hand_y = FACE_CY - 15
            draw.ellipse([hand_x - 6, hand_y - 6, hand_x + 6, hand_y + 6],
                          fill=SKIN)
            for i, dy in enumerate([-12, -4, 4, 12]):
                draw.line([hand_x + 4, hand_y + dy, hand_x + 10, hand_y + dy - 3],
                          fill=SKIN_SHADOW, width=2)
        if self.state == AvatarState.THINK:
            draw.text((FACE_CX + 25, FACE_CY - 25), "...", fill=(100, 100, 150))


def rgb888_to_rgb565_le(img: Image.Image) -> bytes:
    import numpy as np
    arr = np.array(img, dtype=np.uint8)
    r = (arr[:, :, 0].astype(np.uint16) >> 3) << 11
    g = (arr[:, :, 1].astype(np.uint16) >> 2) << 5
    b = arr[:, :, 2].astype(np.uint16) >> 3
    rgb565 = r | g | b
    return rgb565.astype(np.dtype("<u2")).tobytes()


def img_to_jpeg(img: Image.Image, quality: int = 75) -> bytes:
    import io
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()
