import argparse
import hashlib
import threading
import time
import sys
import signal

import paho.mqtt.client as mqtt

from avatar_renderer import AvatarRenderer, img_to_jpeg, rgb888_to_rgb565_le, WIDTH, HEIGHT

TOPIC_CMD = "luominest/s3/cmd"
TOPIC_STREAM = "luominest/s3/stream"
TOPIC_MODE = "luominest/s3/mode"

MODE_JPEG = "jpeg"
MODE_RGB565 = "rgb565"

FRAME_SIZE_RGB565 = WIDTH * HEIGHT * 2


class FrameDedup:
    def __init__(self, sample_bytes=512):
        self._sample_bytes = sample_bytes
        self._last_hash = None
        self._last_size = 0
        self.frames_skipped = 0
        self.frames_sent = 0

    def should_send(self, data: bytes) -> bool:
        if self._last_hash is None:
            self._last_hash = self._hash(data)
            self._last_size = len(data)
            self.frames_sent += 1
            return True

        if len(data) != self._last_size:
            self._last_hash = self._hash(data)
            self._last_size = len(data)
            self.frames_sent += 1
            return True

        current_hash = self._hash(data)
        if current_hash == self._last_hash:
            self.frames_skipped += 1
            return False

        self._last_hash = current_hash
        self.frames_sent += 1
        return True

    def _hash(self, data: bytes) -> str:
        sample = data[:self._sample_bytes] + data[-self._sample_bytes:]
        return hashlib.md5(sample).hexdigest()

    def reset(self):
        self._last_hash = None
        self._last_size = 0


class StreamServer:
    def __init__(self, broker: str, port: int, fps: int, mode: str, quality: int,
                 dedup: bool = True):
        self.renderer = AvatarRenderer()
        self.fps = fps
        self.mode = mode
        self.quality = quality
        self.running = False
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.actual_fps = 0.0
        self.connected = threading.Event()
        self.dedup = dedup

        if self.dedup:
            self.frame_dedup = FrameDedup()
        else:
            self.frame_dedup = None

        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="luominest_pc_renderer",
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
        client.subscribe(TOPIC_CMD, qos=1)
        client.subscribe(TOPIC_MODE, qos=1)
        print(f"[StreamServer] Subscribed to {TOPIC_CMD}, {TOPIC_MODE}")
        self.connected.set()
        if self.frame_dedup:
            self.frame_dedup.reset()

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        print(f"[StreamServer] Disconnected (rc={rc}), will auto-reconnect...")
        self.connected.clear()

    def _on_message(self, client, userdata, msg):
        payload = msg.payload.decode("utf-8", errors="replace").strip()
        topic = msg.topic

        if topic == TOPIC_CMD:
            print(f"[CMD] {payload}")
            self.renderer.set_state(payload)
            if self.frame_dedup:
                self.frame_dedup.reset()
        elif topic == TOPIC_MODE:
            if payload in (MODE_JPEG, MODE_RGB565):
                self.mode = payload
                print(f"[MODE] Switched to {self.mode}")
                if self.frame_dedup:
                    self.frame_dedup.reset()

    def run(self):
        self.running = True
        frame_interval = 1.0 / self.fps

        print(f"[StreamServer] Streaming at {self.fps} FPS, mode={self.mode}")
        print(f"[StreamServer] Dedup={'ON' if self.dedup else 'OFF'}")
        print(f"[StreamServer] Commands: happy, sad, angry, surprised, wave, nod, think, sleep, talk, idle")
        print(f"[StreamServer] Mode switch: mosquitto_pub -h <broker> -t \"{TOPIC_MODE}\" -m \"jpeg|rgb565\"")
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

            if self.dedup and self.frame_dedup:
                if not self.frame_dedup.should_send(data):
                    self.frame_count += 1
                    now = time.time()
                    if now - self.last_fps_time >= 2.0:
                        self.actual_fps = self.frame_count / (now - self.last_fps_time)
                        dedup_pct = (self.frame_dedup.frames_skipped /
                                     max(1, self.frame_dedup.frames_skipped + self.frame_dedup.frames_sent) * 100)
                        print(f"[STATS] {self.actual_fps:.1f} FPS | "
                              f"{self.mode} | dedup saved {dedup_pct:.0f}% | "
                              f"state={self.renderer.state.value}")
                        self.frame_count = 0
                        self.last_fps_time = now

                    elapsed = time.time() - t_start
                    sleep_time = frame_interval - elapsed
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    continue

            result = self.client.publish(TOPIC_STREAM, data, qos=0)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                print(f"[WARN] Publish failed: rc={result.rc}")

            self.frame_count += 1
            now = time.time()
            if now - self.last_fps_time >= 2.0:
                self.actual_fps = self.frame_count / (now - self.last_fps_time)
                size_kb = len(data) / 1024
                dedup_info = ""
                if self.frame_dedup:
                    dedup_pct = (self.frame_dedup.frames_skipped /
                                 max(1, self.frame_dedup.frames_skipped + self.frame_dedup.frames_sent) * 100)
                    dedup_info = f" | dedup saved {dedup_pct:.0f}%"
                print(f"[STATS] {self.actual_fps:.1f} FPS | "
                      f"{self.mode} {size_kb:.1f}KB/frame{dedup_info} | "
                      f"state={self.renderer.state.value}")
                self.frame_count = 0
                self.last_fps_time = now

            elapsed = time.time() - t_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def stop(self):
        self.running = False
        self.client.loop_stop()
        self.client.disconnect()
        print("[StreamServer] Stopped")


def main():
    parser = argparse.ArgumentParser(description="LuomiNest PC Avatar Renderer & Streamer")
    parser.add_argument("--broker", default="192.168.1.222", help="MQTT broker address")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--fps", type=int, default=15, help="Target FPS (default: 15)")
    parser.add_argument("--mode", default=MODE_JPEG, choices=[MODE_JPEG, MODE_RGB565],
                        help="Stream mode: jpeg (compressed) or rgb565 (raw)")
    parser.add_argument("--quality", type=int, default=60, help="JPEG quality 1-100 (default: 60)")
    parser.add_argument("--no-dedup", action="store_true", help="Disable frame deduplication")
    args = parser.parse_args()

    server = StreamServer(args.broker, args.port, args.fps, args.mode, args.quality,
                          dedup=not args.no_dedup)

    def signal_handler(sig, frame):
        print("\n[StreamServer] Interrupt received, stopping...")
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        server.run()
    except Exception as e:
        print(f"[ERROR] {e}")
        server.stop()


if __name__ == "__main__":
    main()
