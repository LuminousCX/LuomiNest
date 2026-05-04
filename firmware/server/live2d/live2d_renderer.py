import math
import time
import json
import os
import random
from enum import Enum
from PIL import Image

import live2d.v3 as live2d
from PyQt5.QtWidgets import QApplication, QOpenGLWidget
from PyQt5.QtCore import Qt
from OpenGL import GL

# ============================================================
#  设备配置 — 支持多端适配
# ============================================================

DEVICE_PROFILES = {
    "s3": {
        "width": 128,
        "height": 160,
        "render_width": 512,
        "render_height": 1024,
        "crop_top": 0.0,
        "crop_bottom": 0.38,
        "saturation_boost": 1.70,
        "jpeg_quality": 70,
        "bg_color": (255, 245, 235),
    },
    "p4": {
        "width": 400,
        "height": 540,
        "render_width": 512,
        "render_height": 1024,
        "crop_top": 0.0,
        "crop_bottom": 0.55,
        "saturation_boost": 1.20,
        "jpeg_quality": 70,
        "bg_color": (255, 245, 235),
    },
}

DEFAULT_DEVICE = "s3"

# --- 输出分辨率（ESP32 屏幕） ---
WIDTH = 128
HEIGHT = 160

# --- 内部渲染分辨率 ---
RENDER_WIDTH = 512
RENDER_HEIGHT = 1024

# --- 裁剪区域（控制显示模型的哪个部位） ---
CROP_TOP_RATIO = 0.0
CROP_BOTTOM_RATIO = 0.38

# --- 背景色 ---
BG_COLOR = (255, 245, 235)

# --- 饱和度增强 ---
SATURATION_BOOST = 1.70

# --- 表情切换过渡速度 ---
TRANSITION_SPEED = 0.08

# --- 表情参数混合权重 ---
EXPRESSION_WEIGHT = 0.8


def apply_device_profile(device: str):
    global WIDTH, HEIGHT, RENDER_WIDTH, RENDER_HEIGHT
    global CROP_TOP_RATIO, CROP_BOTTOM_RATIO, SATURATION_BOOST, BG_COLOR

    profile = DEVICE_PROFILES.get(device, DEVICE_PROFILES[DEFAULT_DEVICE])
    WIDTH = profile["width"]
    HEIGHT = profile["height"]
    RENDER_WIDTH = profile["render_width"]
    RENDER_HEIGHT = profile["render_height"]
    CROP_TOP_RATIO = profile["crop_top"]
    CROP_BOTTOM_RATIO = profile["crop_bottom"]
    SATURATION_BOOST = profile["saturation_boost"]
    BG_COLOR = profile.get("bg_color", (255, 245, 235))


# ============================================================
#  缓动函数（一般不需要修改）
# ============================================================

def _sine(t):
    return -(math.cos(math.pi * t) - 1) / 2


def _cubic(t):
    if t < 0.5:
        return 4 * t * t * t
    return 1 - pow(-2 * t + 2, 3) / 2


def _lerp(a, b, t):
    return a + (b - a) * t


def _linear_scale(value, min_v1, max_v1, start_v2, end_v2):
    return start_v2 + (value - min_v1) * (end_v2 - start_v2) / (max_v1 - min_v1)


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


# ============================================================
#  眨眼控制器
#  可调参数：眨眼间隔、眨眼速度、双眨概率
# ============================================================

class BlinkController:
    def __init__(self):
        self._timer = time.time()
        # --- 眨眼间隔（秒） ---
        # uniform(2.0, 5.0) = 每 2~5 秒眨一次，改大=眨得更少
        self._interval = random.uniform(2.0, 5.0)
        self._phase = 0
        # --- 眨眼速度（秒） ---
        # 0.15 = 闭眼 0.15 秒 + 睁眼 0.15 秒，改小=眨得更快
        self._duration = 0.15
        self._start_l = 1.0
        self._start_r = 1.0
        self._k = 1.0
        # --- 双眨概率 ---
        # random() > 0.6 = 40% 概率双眨，改 0.6 越大双眨越少
        self._double = False

    def update(self, model):
        t = (time.time() - self._timer) / self._duration

        if self._phase == 0:
            if time.time() - self._timer > self._interval:
                self._phase = 1
                self._timer = time.time()
                self._start_l = 1.0
                self._start_r = 1.0
                # --- 眨眼力度 ---
                # uniform(0.7, 1.3) = 闭眼程度 70%~130%，>1.0 会用力闭
                self._k = min(1.0, random.uniform(0.7, 1.3))
                self._double = random.random() > 0.6
        elif self._phase == 1:
            if t <= 1.0:
                eased = _sine(t)
                val_l = _lerp(self._start_l, 0, eased)
                val_r = _lerp(self._start_r, 0, eased)
                model.SetParameterValue("ParamEyeLOpen", round(val_l, 2), 1)
                model.SetParameterValue("ParamEyeROpen", round(val_r, 2), 1)
            else:
                if self._double:
                    self._phase = 2
                    self._timer = time.time()
                    self._start_l = 0
                    self._start_r = 0
                else:
                    self._phase = 3
                    self._timer = time.time()
                    self._start_l = 0
                    self._start_r = 0
        elif self._phase == 2:
            if t <= 1.0:
                eased = _sine(t)
                val_l = _lerp(self._start_l, self._k, eased)
                val_r = _lerp(self._start_r, self._k, eased)
                model.SetParameterValue("ParamEyeLOpen", round(val_l, 2), 1)
                model.SetParameterValue("ParamEyeROpen", round(val_r, 2), 1)
            else:
                self._phase = 3
                self._timer = time.time()
                self._start_l = self._k
                self._start_r = self._k
        elif self._phase == 3:
            if t <= 1.0:
                eased = _sine(t)
                val_l = _lerp(self._start_l, 1.0, eased)
                val_r = _lerp(self._start_r, 1.0, eased)
                model.SetParameterValue("ParamEyeLOpen", round(val_l, 2), 1)
                model.SetParameterValue("ParamEyeROpen", round(val_r, 2), 1)
            else:
                self._phase = 0
                self._timer = time.time()
                self._interval = random.uniform(2.0, 5.0)


# ============================================================
#  呼吸控制器
#  可调参数：呼吸速度
# ============================================================

class BreathController:
    def __init__(self):
        self._phase = 0.0
        # --- 呼吸速度 ---
        # 0.03 = 慢呼吸，0.05 = 快呼吸，0.01 = 极慢
        self._speed = 0.03

    def update(self, model):
        self._phase += self._speed
        if self._phase > math.pi * 2:
            self._phase -= math.pi * 2
        val = (math.sin(self._phase) + 1.0) / 2.0
        try:
            model.SetParameterValue("ParamBreath", val, 0.5)
        except Exception:
            pass


# ============================================================
#  嘴巴控制器（说话时张合）
#  可调参数：张嘴速度、最大张嘴幅度
# ============================================================

class MouthController:
    def __init__(self):
        self._phase = 0.0
        self._is_talking = False

    def update(self, model, is_talking):
        self._is_talking = is_talking
        if self._is_talking:
            # --- 张嘴动画速度 ---
            # 0.4 = 正常语速，0.6 = 快语速，0.2 = 慢语速
            self._phase += 0.4
        else:
            self._phase *= 0.9

        if self._is_talking:
            # --- 最大张嘴幅度 ---
            # 0.8 * sin + 0.1 = 张嘴范围 0.1~0.9，改小=嘴张得更小
            openness = abs(math.sin(self._phase)) * 0.8 + 0.1
        else:
            openness = max(0.0, abs(math.sin(self._phase)) * 0.05)

        model.SetParameterValue("ParamMouthOpenY", round(openness, 2), 1)


# ============================================================
#  眼球控制器
#  可调参数：注视时长、移动速度、漂移幅度、微颤频率
# ============================================================

class EyeBallController:
    def __init__(self):
        self._x = 0.0
        self._y = 0.0
        self._target_x = 0.0
        self._target_y = 0.0
        self._start_x = 0.0
        self._start_y = 0.0
        self._phase = 0
        self._timer = time.time()
        self._move_duration = 0.15
        # --- 注视停留时长（秒） ---
        # uniform(1.5, 4.0) = 注视 1.5~4 秒后移动，改大=眼球动得更少
        self._fixation_time = random.uniform(1.5, 4.0)
        self._drift_x = 0.0
        self._drift_y = 0.0
        self._micro_timer = time.time()
        self._micro_interval = random.uniform(0.2, 0.6)

    def _generate_target(self):
        angle = random.uniform(0, 2 * math.pi)
        # --- 眼球水平/垂直移动范围 ---
        # h_range 0.3~1.0 = 水平幅度，v_range 0.2~0.6 = 垂直幅度
        h_range = random.uniform(0.3, 1.0)
        v_range = random.uniform(0.2, 0.6)
        self._target_x = max(-1, min(1, h_range * math.cos(angle) + random.uniform(-0.1, 0.1)))
        self._target_y = max(-0.5, min(0.5, v_range * math.sin(angle) + random.uniform(-0.05, 0.05)))

    def _micro_movement(self):
        now = time.time()
        if now - self._micro_timer > self._micro_interval:
            self._micro_timer = now
            self._micro_interval = random.uniform(0.2, 0.6)
            # --- 漂移幅度 ---
            # ±0.02 = 每次漂移量，±0.05 = 最大累积漂移
            self._drift_x += random.uniform(-0.02, 0.02)
            self._drift_y += random.uniform(-0.01, 0.01)
            self._drift_x = max(-0.05, min(0.05, self._drift_x))
            self._drift_y = max(-0.05, min(0.05, self._drift_y))
        # --- 微颤频率和幅度 ---
        # 30/25 = 高频抖动频率(Hz)，0.005/0.003 = 抖动幅度
        tremor_x = math.sin(now * 30) * 0.005
        tremor_y = math.cos(now * 25) * 0.003
        return tremor_x + self._drift_x, tremor_y + self._drift_y

    def update(self, model):
        now = time.time()
        elapsed = now - self._timer

        if self._phase == 0:
            if elapsed > self._fixation_time:
                self._phase = 1
                self._timer = now
                self._start_x = self._x
                self._start_y = self._y
                self._generate_target()
                dist = math.sqrt((self._target_x - self._start_x) ** 2 + (self._target_y - self._start_y) ** 2)
                # --- 眼球移动速度 ---
                # 0.1 + dist*0.1 = 距离越远移动越慢，改 0.1 越小移动越快
                self._move_duration = 0.1 + dist * 0.1
        elif self._phase == 1:
            t = elapsed / self._move_duration
            if t <= 1.0:
                eased = _cubic(t)
                self._x = _lerp(self._start_x, self._target_x, eased)
                self._y = _lerp(self._start_y, self._target_y, eased)
            else:
                self._x = self._target_x
                self._y = self._target_y
                self._phase = 0
                self._timer = now
                self._fixation_time = random.uniform(1.0, 3.5)

        micro_x, micro_y = self._micro_movement()
        model.SetParameterValue("ParamEyeBallX", round(self._x + micro_x, 3), 1)
        model.SetParameterValue("ParamEyeBallY", round(self._y + micro_y, 3), 1)


# ============================================================
#  身体晃动控制器
#  可调参数：晃动幅度、晃动速度、等待间隔
# ============================================================

class BodySwayController:
    def __init__(self):
        self._axis = random.choice(['x', 'y', 'z'])
        # --- 晃动幅度系数 ---
        # uniform(-0.6, 0.6) = 晃动方向和力度，改大=晃得更猛
        self._k = random.uniform(-0.6, 0.6)
        self._timer = time.time()
        # --- 晃动速度（秒/次） ---
        # uniform(0.8, 2.0) = 0.8~2 秒完成一次晃动，改小=晃得更快
        self._interval = random.uniform(0.8, 2.0)
        # --- 等待间隔（秒） ---
        # uniform(1.0, 4.0) = 晃完后等 1~4 秒再晃，改大=晃得更少
        self._wait = random.uniform(1.0, 4.0)
        self._phase = 0
        self._start_body = 0.0
        self._start_head = 0.0
        self._start_eye_y = 0.0

    def update(self, model):
        now = time.time()
        elapsed = now - self._timer

        if self._phase == 0:
            if elapsed > self._wait:
                self._phase = 1
                self._timer = now
                self._interval = random.uniform(0.8, 2.0)
                self._axis = random.choice(['x', 'y', 'z'])
                self._k = random.uniform(-0.6, 0.6)
                self._start_body = 0.0
                self._start_head = 0.0
        elif self._phase == 1:
            t = elapsed / self._interval
            if t <= 1.0:
                eased = _sine(t)
                self._apply_sway(model, eased, 0, 1)
            elif 1.0 < t <= 2.0:
                t -= 1.0
                eased = _sine(t)
                self._apply_sway(model, eased, 1, 0)
            else:
                self._phase = 0
                self._timer = now
                self._wait = random.uniform(1.0, 4.0)

    def _apply_sway(self, model, eased, from_phase, to_phase):
        k_from = self._k * from_phase
        k_to = self._k * to_phase
        # --- 身体/头部晃动倍率 ---
        # 8 = 身体最大偏移角度，25 = 头部最大偏移角度
        body_val = _lerp(k_from * 8, k_to * 8, eased)
        head_val = _lerp(k_from * 25, k_to * 25, eased)

        if self._axis == 'x':
            model.SetParameterValue("ParamBodyAngleX", round(body_val, 2), 1)
            model.SetParameterValue("ParamAngleX", round(head_val, 2), 1)
        elif self._axis == 'y':
            model.SetParameterValue("ParamBodyAngleY", round(body_val, 2), 1)
            model.SetParameterValue("ParamAngleY", round(head_val, 2), 1)
            model.SetParameterValue("ParamEyeBallY", round(-k_to * 0.5, 2), 0.5)
        elif self._axis == 'z':
            model.SetParameterValue("ParamBodyAngleZ", round(body_val, 2), 1)
            model.SetParameterValue("ParamAngleZ", round(head_val, 2), 1)


# ============================================================
#  头部歪斜控制器
#  可调参数：歪斜幅度、歪斜速度、等待间隔
# ============================================================

class HeadTiltController:
    def __init__(self):
        self._timer = time.time()
        # --- 等待间隔（秒） ---
        # uniform(3.0, 8.0) = 每 3~8 秒歪一次头，改大=歪得更少
        self._wait = random.uniform(3.0, 8.0)
        # --- 歪斜幅度系数 ---
        # uniform(-0.5, 0.5) = 歪斜方向和力度
        self._k = random.uniform(-0.5, 0.5)
        # --- 歪斜速度（秒/段） ---
        # uniform(1.0, 2.0) = 每段 1~2 秒，共 4 段
        self._interval = random.uniform(1.0, 2.0)
        self._phase = 0

    def update(self, model):
        now = time.time()
        elapsed = now - self._timer

        if self._phase == 0:
            if elapsed > self._wait:
                self._phase = 1
                self._timer = now
                self._k = random.uniform(-0.5, 0.5)
                self._interval = random.uniform(1.0, 2.0)
        elif self._phase == 1:
            t = elapsed / self._interval
            # --- 歪斜最大角度 ---
            # 15 * self._k = 最大歪 15°，改 15 越大歪得越狠
            if t <= 1.0:
                eased = _cubic(t)
                val = _lerp(0, 15 * self._k, eased)
                model.SetParameterValue("ParamAngleZ", round(val, 2), 0.6)
            elif 1.0 < t <= 3.0:
                t = (t - 1.0) / 2.0
                eased = _cubic(t)
                # 0.5 = 回弹幅度比例，回弹到 -50% 方向
                val = _lerp(15 * self._k, -15 * self._k * 0.5, eased)
                model.SetParameterValue("ParamAngleZ", round(val, 2), 0.6)
            elif 3.0 < t <= 4.0:
                t -= 3.0
                eased = _cubic(t)
                val = _lerp(-15 * self._k * 0.5, 0, eased)
                model.SetParameterValue("ParamAngleZ", round(val, 2), 0.6)
            else:
                self._phase = 0
                self._timer = now
                self._wait = random.uniform(3.0, 8.0)


# ============================================================
#  Live2D 渲染器主类
# ============================================================

class Live2DRenderer:
    def __init__(self, model_path: str, exp_map_path: str, character: str = "llny"):
        self.state = AvatarState.IDLE
        self.prev_state = AvatarState.IDLE
        self.transition_progress = 1.0
        self.frame_count = 0

        self.blink_ctrl = BlinkController()
        self.breath_ctrl = BreathController()
        self.mouth_ctrl = MouthController()
        self.eyeball_ctrl = EyeBallController()
        self.body_sway_ctrl = BodySwayController()
        self.head_tilt_ctrl = HeadTiltController()

        self._character = character
        self._model_path = os.path.abspath(model_path)
        self._exp_map = self._load_exp_map(exp_map_path, character)
        self._current_expression = None
        self._target_params = {}
        self._current_params = {}

        self._app = None
        self._canvas = None
        self._model = None
        self._initialized = False
        self._last_frame_image = None

    def _load_exp_map(self, exp_map_path: str, character: str):
        with open(exp_map_path, 'r', encoding='utf-8') as f:
            all_maps = json.load(f)
        char_map = all_maps.get(character, {})
        return {
            "expressions": char_map.get("expressions", {}),
            "params": char_map.get("params", {})
        }

    def init_opengl(self):
        live2d.init()

        self._app = QApplication([])
        self._canvas = _Live2DCanvas(self._model_path, RENDER_WIDTH, RENDER_HEIGHT)
        # 注意：不能用 hide()，否则 paintGL 不会被调用（黑屏）
        self._canvas.move(-10000, -10000)
        self._canvas.show()

        for _ in range(20):
            self._app.processEvents()

        self._model = self._canvas.model
        if self._model:
            self._model.SetAutoBlinkEnable(False)
            self._model.SetAutoBreathEnable(False)

        self._initialized = True

    def set_state(self, state_name: str):
        try:
            new_state = AvatarState(state_name.lower())
            if new_state != self.state:
                self.prev_state = self.state
                self.state = new_state
                self.transition_progress = 0.0
                self._apply_expression(new_state)
        except ValueError:
            pass

    def _apply_expression(self, state: AvatarState):
        state_key = state.value
        exp_name = self._exp_map["expressions"].get(state_key)

        if exp_name is not None:
            self._current_expression = exp_name
        else:
            self._current_expression = None

        self._target_params = self._exp_map["params"].get(state_key, {})
        self._current_params = {}

    def render(self) -> Image.Image:
        if not self._initialized or self._model is None:
            return Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)

        self._update_animation()
        # repaint() 强制立即重绘，不能用 update()（延迟调度）
        self._canvas.repaint()
        self._app.processEvents()

        img = self._canvas.grab_frame()
        if img is not None:
            img = self._crop_and_resize(img)
            self._last_frame_image = img

        return self._last_frame_image or Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)

    def _crop_and_resize(self, img: Image.Image) -> Image.Image:
        w, h = img.size

        crop_top = int(h * CROP_TOP_RATIO)
        crop_bottom = int(h * CROP_BOTTOM_RATIO)
        cropped = img.crop((0, crop_top, w, crop_bottom))

        target_ratio = WIDTH / HEIGHT
        crop_w, crop_h = cropped.size
        current_ratio = crop_w / crop_h

        if current_ratio > target_ratio:
            new_w = int(crop_h * target_ratio)
            left = (crop_w - new_w) // 2
            cropped = cropped.crop((left, 0, left + new_w, crop_h))
        elif current_ratio < target_ratio:
            new_h = int(crop_w / target_ratio)
            top = (crop_h - new_h) // 2
            cropped = cropped.crop((0, top, crop_w, top + new_h))

        return self._boost_saturation(cropped.resize((WIDTH, HEIGHT), Image.LANCZOS))

    @staticmethod
    def _boost_saturation(img: Image.Image) -> Image.Image:
        """HSV 饱和度增强：RGB → HSV → S×SATURATION_BOOST → RGB"""
        import numpy as np
        hsv = img.convert("HSV")
        arr = np.array(hsv, dtype=np.uint8)
        s = arr[:, :, 1].astype(np.float32)
        s = np.clip(s * SATURATION_BOOST, 0, 255)
        arr[:, :, 1] = s.astype(np.uint8)
        return Image.fromarray(arr, "HSV").convert("RGB")

    def _update_animation(self):
        model = self._model
        if model is None:
            return

        if self.state == AvatarState.SLEEP:
            model.SetParameterValue("ParamEyeLOpen", 0.0, 1)
            model.SetParameterValue("ParamEyeROpen", 0.0, 1)
        else:
            self.blink_ctrl.update(model)

        self.breath_ctrl.update(model)
        self.mouth_ctrl.update(model, self.state == AvatarState.TALK)
        self.eyeball_ctrl.update(model)
        self.body_sway_ctrl.update(model)
        self.head_tilt_ctrl.update(model)

        if self.transition_progress < 1.0:
            self.transition_progress = min(1.0, self.transition_progress + TRANSITION_SPEED)

        t = self.transition_progress
        for param_id, target_val in self._target_params.items():
            current_val = self._current_params.get(param_id, 0.0)
            blended = _lerp(current_val, target_val, t)
            self._current_params[param_id] = blended
            try:
                model.SetParameterValue(param_id, round(blended, 2), EXPRESSION_WEIGHT)
            except Exception:
                pass

        self._apply_state_params(model)

        self.frame_count += 1

    # ============================================================
    #  表情参数 — 修改这里的数值来调整每种表情的效果
    #  SetParameterValue(参数名, 值, 权重)
    #  值范围: -1.0 ~ 1.0  权重: 0.0 ~ 1.0
    # ============================================================

    def _apply_state_params(self, model):
        if self.state == AvatarState.HAPPY or self.state == AvatarState.WAVE:
            try:
                model.SetParameterValue("ParamEyeLSmile", 1.0, EXPRESSION_WEIGHT)
                model.SetParameterValue("ParamEyeRSmile", 1.0, EXPRESSION_WEIGHT)
                model.SetParameterValue("ParamMouthForm", 0.8, EXPRESSION_WEIGHT)
            except Exception:
                pass

        elif self.state == AvatarState.SAD:
            try:
                model.SetParameterValue("ParamBrowLY", -0.8, EXPRESSION_WEIGHT)
                model.SetParameterValue("ParamBrowRY", -0.8, EXPRESSION_WEIGHT)
                model.SetParameterValue("ParamBrowLAngle", -0.8, EXPRESSION_WEIGHT)
                model.SetParameterValue("ParamBrowRAngle", -0.8, EXPRESSION_WEIGHT)
                model.SetParameterValue("ParamMouthForm", -0.8, EXPRESSION_WEIGHT)
            except Exception:
                pass

        elif self.state == AvatarState.ANGRY:
            try:
                model.SetParameterValue("ParamBrowLY", 0.8, EXPRESSION_WEIGHT)
                model.SetParameterValue("ParamBrowRY", 0.8, EXPRESSION_WEIGHT)
                model.SetParameterValue("ParamBrowLAngle", -0.8, EXPRESSION_WEIGHT)
                model.SetParameterValue("ParamBrowRAngle", -0.8, EXPRESSION_WEIGHT)
                model.SetParameterValue("ParamMouthForm", -0.6, EXPRESSION_WEIGHT)
            except Exception:
                pass

        elif self.state == AvatarState.SURPRISED:
            try:
                model.SetParameterValue("ParamBrowLY", 1.0, EXPRESSION_WEIGHT)
                model.SetParameterValue("ParamBrowRY", 1.0, EXPRESSION_WEIGHT)
                model.SetParameterValue("ParamMouthOpenY", 0.8, EXPRESSION_WEIGHT)
            except Exception:
                pass

        elif self.state == AvatarState.THINK:
            try:
                model.SetParameterValue("ParamEyeBallX", -0.8, EXPRESSION_WEIGHT)
                model.SetParameterValue("ParamMouthForm", -0.5, EXPRESSION_WEIGHT)
            except Exception:
                pass

        elif self.state == AvatarState.SLEEP:
            try:
                model.SetParameterValue("ParamBrowLY", -0.3, EXPRESSION_WEIGHT)
                model.SetParameterValue("ParamBrowRY", -0.3, EXPRESSION_WEIGHT)
            except Exception:
                pass

    def cleanup(self):
        if self._app is not None:
            self._app.quit()


class _Live2DCanvas(QOpenGLWidget):
    def __init__(self, model_path: str, width: int, height: int):
        super().__init__()
        self._model_path = model_path
        self._w = width
        self._h = height
        self.resize(width, height)
        self.model: live2d.LAppModel | None = None

    def initializeGL(self):
        # 背景色必须设为 BG_COLOR，否则模型边缘抗锯齿会与黑色混合变暗
        r, g, b = [c / 255.0 for c in BG_COLOR]
        GL.glClearColor(r, g, b, 1.0)

        live2d.glInit()
        self.model = live2d.LAppModel()
        self.model.LoadModelJson(self._model_path)
        self.model.Resize(self._w, self._h)
        self.model.SetAutoBlinkEnable(False)
        self.model.SetAutoBreathEnable(False)

    def paintGL(self):
        if self.model is None:
            return
        live2d.clearBuffer()
        self.model.Update()
        self.model.Draw()

    def grab_frame(self) -> Image.Image | None:
        try:
            qimg = self.grabFramebuffer()
            if qimg.isNull():
                print("[WARN] grabFramebuffer returned null image")
                return None
            buf = qimg.bits()
            buf.setsize(qimg.size().width() * qimg.size().height() * 4)
            import numpy as np
            arr = np.frombuffer(buf, dtype=np.uint8).reshape(
                (qimg.height(), qimg.width(), 4)
            )
            return Image.fromarray(arr[:, :, :3], "RGB")
        except Exception as e:
            print(f"[ERROR] grab_frame failed: {e}")
            return None


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
