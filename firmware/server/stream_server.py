import argparse
import hashlib
import io
import json
import os
import sys
import time
import threading

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import live2d_renderer as lr
from live2d_renderer import (
    Live2DRenderer,
    apply_device_profile,
    DEVICE_PROFILES,
    rgb888_to_rgb565_le,
    rgb888_to_bgr565_le,
    rgb888_to_rgb565_be,
    img_to_jpeg,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_MODEL = os.path.join(
    SCRIPT_DIR, "models", "llny", "mianfeimox", "llny.model3.json"
)
DEFAULT_EXP_MAP = os.path.join(SCRIPT_DIR, "exp_map.json")

MQTT_BROKER = os.environ.get("MQTT_BROKER", "192.168.1.222")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))

FRAME_DEDUP = True

ALL_STATES = ["idle", "happy", "sad", "angry", "surprised", "wave", "nod", "think", "sleep", "talk"]


class FrameDedup:
    def __init__(self):
        self._last_hash = None

    def should_send(self, data: bytes) -> bool:
        if not FRAME_DEDUP:
            return True
        h = hashlib.md5(data).hexdigest()
        if h == self._last_hash:
            return False
        self._last_hash = h
        return True


class AvatarStreamServer:
    def __init__(self, args):
        self._device = args.device
        self._format = args.format
        self._character = args.character
        self._model_path = args.model
        self._exp_map_path = args.exp_map
        self._broker = args.broker
        self._port = args.port
        self._fps = args.fps
        self._bgr = args.bgr
        self._flip_v = args.flip_v
        self._flip_h = args.flip_h
        self._gamma = args.gamma
        self._no_mqtt = args.no_mqtt
        self._preview = args.preview
        self._renderer = None
        self._mqtt_client = None
        self._mqtt_connected = False
        self._dedup = FrameDedup()
        self._running = False
        self._state = "idle"
        self._state_lock = threading.Lock()
        self._frame_count = 0
        self._send_count = 0
        self._actual_fps = 0.0
        self._fps_timer = time.time()
        self._fps_frame_count = 0

        self._topic_cmd = f"luominest/{self._device}/cmd"
        self._topic_stream = f"luominest/{self._device}/stream"
        self._topic_status = f"luominest/{self._device}/status"
        self._topic_chat = f"luominest/{self._device}/chat"

    def _setup_device_profile(self):
        apply_device_profile(self._device)

        if self._flip_v:
            lr.FLIP_V = True
        if self._flip_h:
            lr.FLIP_H = True
        if self._gamma != 1.0:
            lr.GAMMA = self._gamma

    def _init_renderer(self):
        w = lr.WIDTH
        h = lr.HEIGHT
        print(f"[INFO] Loading Live2D model: {self._model_path}")
        print(f"[INFO] Character: {self._character}, Device: {self._device}")
        print(f"[INFO] Output format: {self._format}, BGR: {self._bgr}")
        print(f"[INFO] Flip V: {self._flip_v}, Flip H: {self._flip_h}, Gamma: {self._gamma}")
        print(f"[INFO] Target FPS: {self._fps}")
        print(f"[INFO] Frame size: {w}x{h}")
        print(f"[INFO] MQTT topics: cmd={self._topic_cmd}, stream={self._topic_stream}")

        self._renderer = Live2DRenderer(
            model_path=self._model_path,
            exp_map_path=self._exp_map_path,
            character=self._character,
        )
        self._renderer.init_opengl()
        print("[INFO] Live2D renderer initialized")

    def _init_mqtt(self):
        if self._no_mqtt:
            print("[INFO] MQTT disabled (--no-mqtt)")
            return

        try:
            self._mqtt_client = mqtt.Client(
                callback_api_version=CallbackAPIVersion.VERSION2,
                client_id=f"luominest-server-{self._device}",
                protocol=mqtt.MQTTv311,
            )
            self._mqtt_client.on_connect = self._on_connect
            self._mqtt_client.on_message = self._on_message

            self._mqtt_client.connect_async(self._broker, self._port, keepalive=60)
            self._mqtt_client.loop_start()
            print(f"[INFO] MQTT connecting to {self._broker}:{self._port} (async)...")
            print(f"[INFO] Publish stream to: {self._topic_stream}")
            print(f"[INFO] Subscribe commands: {self._topic_cmd}")
        except Exception as e:
            print(f"[WARN] MQTT init failed: {e}, running without MQTT")
            self._mqtt_client = None

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self._mqtt_connected = True
            print("[INFO] MQTT connected successfully")
            client.subscribe(self._topic_cmd)
            print(f"[INFO] Subscribed to {self._topic_cmd}")
        else:
            print(f"[ERROR] MQTT connection failed with code {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            cmd = payload.get("cmd", "")

            if cmd == "set_state":
                state = payload.get("state", "idle")
                with self._state_lock:
                    self._state = state
                if self._renderer:
                    self._renderer.set_state(state)
                print(f"[CMD] Set state: {state}")

            elif cmd == "set_expression":
                expression = payload.get("expression", "")
                if self._renderer:
                    self._renderer.set_state(expression)
                print(f"[CMD] Set expression: {expression}")

            elif cmd == "talk_start":
                with self._state_lock:
                    self._state = "talk"
                if self._renderer:
                    self._renderer.set_state("talk")
                print("[CMD] Talk started")

            elif cmd == "talk_end":
                with self._state_lock:
                    self._state = "idle"
                if self._renderer:
                    self._renderer.set_state("idle")
                print("[CMD] Talk ended")

            elif cmd == "ping":
                resp = json.dumps({"cmd": "pong", "device": self._device})
                client.publish(self._topic_status, resp)
                print("[CMD] Ping -> Pong")

        except Exception as e:
            try:
                text = msg.payload.decode("utf-8")
                if any(s in text for s in ALL_STATES):
                    state = "idle"
                    for s in ALL_STATES:
                        if s in text:
                            state = s
                            break
                    with self._state_lock:
                        self._state = state
                    if self._renderer:
                        self._renderer.set_state(state)
                    print(f"[CMD] Plain text state: {state}")
            except Exception:
                print(f"[ERROR] Failed to process command: {e}")

    def _encode_frame(self, img: Image.Image) -> bytes:
        if self._format == "jpeg":
            profile = DEVICE_PROFILES.get(self._device, DEVICE_PROFILES["s3"])
            quality = profile.get("jpeg_quality", 75)
            return img_to_jpeg(img, quality)
        elif self._format == "rgb565":
            if self._bgr:
                return rgb888_to_bgr565_le(img)
            else:
                return rgb888_to_rgb565_le(img)
        elif self._format == "rgb565_be":
            return rgb888_to_rgb565_be(img)
        elif self._format == "rgb888":
            import numpy as np
            return np.array(img, dtype=np.uint8).tobytes()
        else:
            return img_to_jpeg(img, 75)

    def _send_frame(self, img: Image.Image):
        if self._mqtt_client is None or not self._mqtt_connected:
            return

        try:
            frame_data = self._encode_frame(img)

            if not self._dedup.should_send(frame_data):
                return

            self._mqtt_client.publish(
                self._topic_stream,
                frame_data,
                qos=0,
            )
            self._send_count += 1

        except Exception as e:
            print(f"[ERROR] Failed to send frame: {e}")

    def _update_fps_counter(self):
        self._fps_frame_count += 1
        now = time.time()
        elapsed = now - self._fps_timer
        if elapsed >= 2.0:
            self._actual_fps = self._fps_frame_count / elapsed
            self._fps_frame_count = 0
            self._fps_timer = now

    def _handle_keyboard(self):
        import msvcrt
        if not msvcrt.kbhit():
            return

        key = msvcrt.getch()
        if key == b'\xe0':
            key = msvcrt.getch()

        if key == b'q' or key == b'\x1b':
            print("\n[INFO] Quit requested")
            self._running = False
        elif key == b'+' or key == b'=' or key == b'H':
            self._fps = min(60, self._fps + 1)
            print(f"[INFO] FPS: {self._fps}")
        elif key == b'-' or key == b'P':
            self._fps = max(1, self._fps - 1)
            print(f"[INFO] FPS: {self._fps}")
        elif key == b'0':
            self._fps = 15
            print(f"[INFO] FPS reset to: {self._fps}")
        elif key == b'1':
            self._set_state("idle")
        elif key == b'2':
            self._set_state("happy")
        elif key == b'3':
            self._set_state("sad")
        elif key == b'4':
            self._set_state("angry")
        elif key == b'5':
            self._set_state("surprised")
        elif key == b'6':
            self._set_state("talk")
        elif key == b'7':
            self._set_state("think")
        elif key == b'8':
            self._set_state("sleep")
        elif key == b's':
            self._save_frame()
        elif key == b'h':
            self._print_help()

    def _set_state(self, state: str):
        with self._state_lock:
            self._state = state
        if self._renderer:
            self._renderer.set_state(state)
        print(f"[STATE] {state}")

    def _save_frame(self):
        if self._renderer and self._renderer._last_frame_image:
            ts = time.strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(SCRIPT_DIR, f"frame_{ts}.png")
            self._renderer._last_frame_image.save(filename)
            print(f"[SAVE] Frame saved to {filename}")

    def _print_help(self):
        print("\n=== Keyboard Controls ===")
        print("  +/- : Adjust FPS (current: {})".format(self._fps))
        print("  0   : Reset FPS to 15")
        print("  1-8 : Switch state (1=idle, 2=happy, 3=sad, 4=angry, 5=surprised, 6=talk, 7=think, 8=sleep)")
        print("  s   : Save current frame as PNG")
        print("  q/Esc : Quit")
        print("  h   : Show this help")
        print("=========================\n")

    def run(self):
        self._setup_device_profile()
        self._init_renderer()
        self._init_mqtt()

        self._running = True
        self._fps_timer = time.time()

        w = lr.WIDTH
        h = lr.HEIGHT

        print(f"\n[INFO] Streaming at {self._fps} FPS")
        print(f"[INFO] Frame size: {w}x{h}")
        if self._preview:
            print("[INFO] Preview mode: ON")
        if self._no_mqtt:
            print("[INFO] MQTT: DISABLED (frames rendered but not sent)")
        else:
            print(f"[INFO] MQTT: {self._broker}:{self._port}")
            print(f"[INFO] Stream topic: {self._topic_stream}")
        print("[INFO] Press 'h' for keyboard controls\n")

        try:
            while self._running:
                t0 = time.time()

                self._handle_keyboard()

                img = self._renderer.render()
                self._frame_count += 1
                self._update_fps_counter()

                self._send_frame(img)

                if self._preview and self._frame_count % max(1, self._fps // 4) == 0:
                    mqtt_status = "MQTT:ON" if self._mqtt_connected else "MQTT:OFF"
                    print(f"\r[FPS: {self._actual_fps:.1f}] [State: {self._state}] [Sent: {self._send_count}] [{mqtt_status}] [Frame: {self._frame_count}]", end="", flush=True)

                interval = 1.0 / self._fps
                elapsed = time.time() - t0
                sleep_time = max(0, interval - elapsed)
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("\n[INFO] Shutting down...")
        finally:
            self._running = False
            if self._mqtt_client:
                self._mqtt_client.loop_stop()
                self._mqtt_client.disconnect()
            if self._renderer:
                self._renderer.cleanup()
            print(f"\n[INFO] Server stopped. Total frames: {self._frame_count}, Sent: {self._send_count}")


def main():
    parser = argparse.ArgumentParser(
        description="LuomiNest Avatar Stream Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Keyboard Controls (at runtime):
  +/-     Adjust FPS
  0       Reset FPS to 15
  1-8     Switch state (1=idle, 2=happy, 3=sad, 4=angry, 5=surprised, 6=talk, 7=think, 8=sleep)
  s       Save current frame as PNG
  q/Esc   Quit
  h       Show help

MQTT Topics (auto-configured per device):
  S3: luominest/s3/cmd, luominest/s3/stream
  P4: luominest/p4/cmd, luominest/p4/stream, luominest/p4/chat

Examples:
  # Preview mode (no MQTT, just render)
  python stream_server.py --no-mqtt --preview

  # Stream to ESP32-P4
  python stream_server.py --device p4 --broker 192.168.1.222 --preview

  # Stream to ESP32-S3 at 20 FPS
  python stream_server.py --device s3 --fps 20 --broker 192.168.1.222

  # Use different model
  python stream_server.py --device p4 --character Hiyori --model models/Hiyori/Hiyori.model3.json
""")

    parser.add_argument(
        "--device", choices=["s3", "p4"], default="s3",
        help="Target device (s3=ESP32-S3, p4=ESP32-P4)"
    )
    parser.add_argument(
        "--format", choices=["jpeg", "rgb565", "rgb565_be", "rgb888"],
        default="jpeg",
        help="Frame output format (jpeg=recommended, raw bytes sent over MQTT)"
    )
    parser.add_argument(
        "--character", default="llny",
        help="Character name (must match exp_map.json key)"
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help="Path to Live2D model3.json"
    )
    parser.add_argument(
        "--exp-map", default=DEFAULT_EXP_MAP,
        help="Path to expression mapping JSON"
    )
    parser.add_argument(
        "--broker", default=MQTT_BROKER,
        help="MQTT broker address"
    )
    parser.add_argument(
        "--port", type=int, default=MQTT_PORT,
        help="MQTT broker port"
    )
    parser.add_argument(
        "--fps", type=int, default=15,
        help="Target FPS (adjustable at runtime with +/- keys)"
    )
    parser.add_argument(
        "--bgr", action="store_true",
        help="Output BGR565 instead of RGB565 (for BGR LCD panels)"
    )
    parser.add_argument(
        "--flip-v", action="store_true",
        help="Vertically flip the output frame"
    )
    parser.add_argument(
        "--flip-h", action="store_true",
        help="Horizontally flip the output frame"
    )
    parser.add_argument(
        "--gamma", type=float, default=1.0,
        help="Gamma correction (1.0=disabled, >1=brighter, <1=darker)"
    )
    parser.add_argument(
        "--no-mqtt", action="store_true",
        help="Disable MQTT (local render only, no streaming)"
    )
    parser.add_argument(
        "--preview", action="store_true",
        help="Show FPS/state info in console"
    )

    args = parser.parse_args()

    if not os.path.exists(args.model):
        print(f"[ERROR] Model file not found: {args.model}")
        print(f"[INFO] Available models in server/models/:")
        models_dir = os.path.join(SCRIPT_DIR, "models")
        if os.path.exists(models_dir):
            for char_dir in os.listdir(models_dir):
                char_path = os.path.join(models_dir, char_dir)
                if os.path.isdir(char_path):
                    print(f"  {char_dir}/")
        sys.exit(1)

    if not os.path.exists(args.exp_map):
        print(f"[ERROR] Expression map not found: {args.exp_map}")
        sys.exit(1)

    server = AvatarStreamServer(args)
    server.run()


if __name__ == "__main__":
    main()
