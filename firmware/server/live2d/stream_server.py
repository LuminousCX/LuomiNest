import argparse
import threading
import time
import sys
import signal
import os

import paho.mqtt.client as mqtt

from live2d_renderer import (
    Live2DRenderer, img_to_jpeg, rgb888_to_rgb565_le,
    WIDTH, HEIGHT, DEVICE_PROFILES, apply_device_profile,
)

DEVICE_TOPICS = {
    "s3": {
        "cmd": "luominest/s3/cmd",
        "stream": "luominest/s3/stream",
        "mode": "luominest/s3/mode",
    },
    "p4": {
        "cmd": "luominest/p4/cmd",
        "stream": "luominest/p4/stream",
        "mode": "luominest/p4/mode",
    },
}

MODE_JPEG = "jpeg"
MODE_RGB565 = "rgb565"

DEFAULT_MODEL = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "Demo", "Demo_Live2D", "Live2D-Virtual-Girlfriend",
    "Character", "llny", "mianfeimox", "llny.model3.json"
)
DEFAULT_EXP_MAP = os.path.join(os.path.dirname(__file__), "exp_map.json")


class StreamServer:
    def __init__(self, broker: str, port: int, fps: int, mode: str, quality: int,
                 model_path: str, exp_map_path: str, character: str, device: str):
        self.device = device
        self.topics = DEVICE_TOPICS.get(device, DEVICE_TOPICS["s3"])
        self.fps = fps
        self.mode = mode
        self.quality = quality
        self.running = False
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.actual_fps = 0.0
        self.connected = threading.Event()

        apply_device_profile(device)
        profile = DEVICE_PROFILES[device]
        self.quality = profile.get("jpeg_quality", quality)

        print(f"[Live2D] Target device: {device} ({profile['width']}x{profile['height']})")
        print(f"[Live2D] Initializing renderer with model: {model_path}")
        print(f"[Live2D] Character: {character}")
        self.renderer = Live2DRenderer(model_path, exp_map_path, character)
        self.renderer.init_opengl()
        print("[Live2D] Renderer initialized successfully")

        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"luominest_live2d_{device}",
            clean_session=True,
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.max_inflight_messages_set(200)
        self.client.reconnect_delay_set(min_delay=1, max_delay=5)

        print(f"[StreamServer] Connecting to {broker}:{port} ...")
        self.client.connect(broker, port, 60)
        self.client.loop_start()

        print("[StreamServer] Waiting for connection...")
        if not self.connected.wait(timeout=10):
            print("[StreamServer] WARNING: Connection timeout, will retry in loop")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        print(f"[StreamServer] Connected (rc={rc})")
        client.subscribe(self.topics["cmd"], qos=1)
        client.subscribe(self.topics["mode"], qos=1)
        print(f"[StreamServer] Subscribed to {self.topics['cmd']}, {self.topics['mode']}")
        self.connected.set()

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        print(f"[StreamServer] Disconnected (rc={rc}), will auto-reconnect...")
        self.connected.clear()

    def _on_message(self, client, userdata, msg):
        payload = msg.payload.decode("utf-8", errors="replace").strip()
        topic = msg.topic

        if topic == self.topics["cmd"]:
            print(f"[CMD] {payload}")
            self.renderer.set_state(payload)
        elif topic == self.topics["mode"]:
            if payload in (MODE_JPEG, MODE_RGB565):
                self.mode = payload
                print(f"[MODE] Switched to {self.mode}")

    def run(self):
        self.running = True
        frame_interval = 1.0 / self.fps

        from live2d_renderer import WIDTH, HEIGHT

        print(f"[StreamServer] Streaming at {self.fps} FPS, mode={self.mode}, device={self.device}")
        print(f"[StreamServer] Resolution: {WIDTH}x{HEIGHT}")
        print(f"[StreamServer] Commands: happy, sad, angry, surprised, wave, nod, think, sleep, talk, idle")
        print(f"[StreamServer] Mode switch: mosquitto_pub -h <broker> -t \"{self.topics['mode']}\" -m \"jpeg|rgb565\"")
        print(f"[StreamServer] Press Ctrl+C to stop")

        while self.running:
            t_start = time.time()

            if not self.connected.is_set():
                time.sleep(0.1)
                continue

            img = self.renderer.render()

            if self.mode == MODE_JPEG:
                data = img_to_jpeg(img, self.quality)
            else:
                data = rgb888_to_rgb565_le(img)

            result = self.client.publish(self.topics["stream"], data, qos=0)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                print(f"[WARN] Publish failed: rc={result.rc}")

            self.frame_count += 1
            now = time.time()
            if now - self.last_fps_time >= 2.0:
                self.actual_fps = self.frame_count / (now - self.last_fps_time)
                size_kb = len(data) / 1024
                print(f"[STATS] {self.actual_fps:.1f} FPS | "
                      f"{self.mode} {size_kb:.1f}KB/frame | "
                      f"device={self.device} | "
                      f"state={self.renderer.state.value}")
                self.frame_count = 0
                self.last_fps_time = now

            elapsed = time.time() - t_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def stop(self):
        self.running = False
        self.renderer.cleanup()
        self.client.loop_stop()
        self.client.disconnect()
        print("[StreamServer] Stopped")


def main():
    parser = argparse.ArgumentParser(description="LuomiNest Live2D Renderer & Streamer")
    parser.add_argument("--broker", default="192.168.1.222", help="MQTT broker address")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--fps", type=int, default=15, help="Target FPS (default: 15)")
    parser.add_argument("--mode", default=MODE_JPEG, choices=[MODE_JPEG, MODE_RGB565],
                        help="Stream mode: jpeg (compressed) or rgb565 (raw)")
    parser.add_argument("--quality", type=int, default=None, help="JPEG quality 1-100 (default: device profile)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Path to Live2D model3.json")
    parser.add_argument("--exp-map", default=DEFAULT_EXP_MAP, help="Path to expression mapping JSON")
    parser.add_argument("--character", default="llny", choices=["llny", "cat"],
                        help="Character name for expression mapping (default: llny)")
    parser.add_argument("--device", default="s3", choices=["s3", "p4"],
                        help="Target device: s3 (128x160) or p4 (1024x600) (default: s3)")
    args = parser.parse_args()

    model_path = os.path.abspath(args.model)
    exp_map_path = os.path.abspath(args.exp_map)

    if not os.path.exists(model_path):
        print(f"[ERROR] Model file not found: {model_path}")
        print(f"[HINT]  Use --model to specify the path to the .model3.json file")
        sys.exit(1)

    if not os.path.exists(exp_map_path):
        print(f"[ERROR] Expression map not found: {exp_map_path}")
        sys.exit(1)

    quality = args.quality if args.quality is not None else DEVICE_PROFILES[args.device].get("jpeg_quality", 60)

    server = StreamServer(
        broker=args.broker,
        port=args.port,
        fps=args.fps,
        mode=args.mode,
        quality=quality,
        model_path=model_path,
        exp_map_path=exp_map_path,
        character=args.character,
        device=args.device,
    )

    def signal_handler(sig, frame):
        print("\n[StreamServer] Interrupt received, stopping...")
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        server.run()
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        server.stop()


if __name__ == "__main__":
    main()
