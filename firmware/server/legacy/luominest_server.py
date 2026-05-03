import asyncio
import json
import logging
import os
import io
import struct
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum

import paho.mqtt.client as mqtt
from PIL import Image, ImageDraw

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("luominest_server")


class AvatarState(str, Enum):
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


@dataclass
class FrameSequence:
    action_name: str
    frames: list[bytes] = field(default_factory=list)
    fps: int = 30
    loop: bool = True


class AvatarResourceGenerator:
    WIDTH = 128
    HEIGHT = 160

    def generate_color_frame(self, r: int, g: int, b: int) -> bytes:
        img = Image.new("RGB", (self.WIDTH, self.HEIGHT), (r, g, b))
        draw = ImageDraw.Draw(img)
        draw.text((4, 4), f"R:{r} G:{g} B:{b}", fill=(255, 255, 255))
        return self._to_rgb565(img)

    def generate_state_frames(self, state: AvatarState, frame_count: int = 30) -> FrameSequence:
        seq = FrameSequence(action_name=state.value, fps=30, loop=True)

        base_colors = {
            AvatarState.IDLE: (100, 180, 255),
            AvatarState.HAPPY: (255, 220, 50),
            AvatarState.SAD: (80, 80, 180),
            AvatarState.ANGRY: (255, 60, 60),
            AvatarState.SURPRISED: (255, 160, 0),
            AvatarState.WAVE: (100, 255, 150),
            AvatarState.NOD: (180, 100, 255),
            AvatarState.THINK: (200, 200, 100),
            AvatarState.SLEEP: (50, 50, 120),
            AvatarState.TALK: (255, 150, 200),
        }
        base_r, base_g, base_b = base_colors.get(state, (128, 128, 128))

        for i in range(frame_count):
            phase = (i / frame_count) * 2 * 3.14159
            r = int(base_r + 30 * __import__("math").sin(phase))
            g = int(base_g + 30 * __import__("math").sin(phase + 2.094))
            b = int(base_b + 30 * __import__("math").sin(phase + 4.189))
            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))

            img = Image.new("RGB", (self.WIDTH, self.HEIGHT), (r, g, b))
            draw = ImageDraw.Draw(img)

            cx, cy = self.WIDTH // 2, self.HEIGHT // 2 + 10
            face_offset_y = int(5 * __import__("math").sin(phase))

            draw.ellipse([cx - 30, cy - 35 + face_offset_y, cx + 30, cy + 25 + face_offset_y],
                         fill=(255, 220, 185), outline=(200, 170, 140))

            eye_y = cy - 12 + face_offset_y
            blink = (i % 15) < 2
            if state == AvatarState.HAPPY:
                draw.arc([cx - 18, eye_y - 4, cx - 8, eye_y + 4], 0, 180, fill=(50, 50, 50), width=2)
                draw.arc([cx + 8, eye_y - 4, cx + 18, eye_y + 4], 0, 180, fill=(50, 50, 50), width=2)
            elif state == AvatarState.SAD:
                draw.arc([cx - 18, eye_y, cx - 8, eye_y + 8], 180, 360, fill=(50, 50, 50), width=2)
                draw.arc([cx + 8, eye_y, cx + 18, eye_y + 8], 180, 360, fill=(50, 50, 50), width=2)
            elif state == AvatarState.SLEEP:
                draw.line([cx - 18, eye_y, cx - 8, eye_y], fill=(50, 50, 50), width=2)
                draw.line([cx + 8, eye_y, cx + 18, eye_y], fill=(50, 50, 50), width=2)
            elif not blink:
                draw.ellipse([cx - 16, eye_y - 4, cx - 10, eye_y + 4], fill=(50, 50, 50))
                draw.ellipse([cx + 10, eye_y - 4, cx + 16, eye_y + 4], fill=(50, 50, 50))
            else:
                draw.line([cx - 16, eye_y, cx - 10, eye_y], fill=(50, 50, 50), width=2)
                draw.line([cx + 10, eye_y, cx + 16, eye_y], fill=(50, 50, 50), width=2)

            mouth_y = cy + 10 + face_offset_y
            if state == AvatarState.HAPPY:
                draw.arc([cx - 12, mouth_y - 4, cx + 12, mouth_y + 8], 0, 180, fill=(200, 80, 80), width=2)
            elif state == AvatarState.SAD:
                draw.arc([cx - 10, mouth_y, cx + 10, mouth_y + 8], 180, 360, fill=(200, 80, 80), width=2)
            elif state == AvatarState.TALK:
                mouth_open = int(6 * abs(__import__("math").sin(phase * 3)))
                draw.ellipse([cx - 8, mouth_y - mouth_open // 2, cx + 8, mouth_y + mouth_open // 2],
                             fill=(200, 80, 80))
            elif state == AvatarState.SURPRISED:
                draw.ellipse([cx - 6, mouth_y - 5, cx + 6, mouth_y + 5], fill=(200, 80, 80))
            else:
                draw.line([cx - 8, mouth_y, cx + 8, mouth_y], fill=(200, 80, 80), width=2)

            draw.text((2, 2), state.value, fill=(255, 255, 255))

            seq.frames.append(self._to_rgb565(img))

        return seq

    def generate_jpeg_frame(self, state: AvatarState, frame_idx: int = 0) -> bytes:
        seq = self.generate_state_frames(state, 1)
        img = Image.frombytes("RGB", (self.WIDTH, self.HEIGHT),
                              self._rgb565_to_rgb(seq.frames[0]))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=60)
        return buf.getvalue()

    def _to_rgb565(self, img: Image.Image) -> bytes:
        img = img.convert("RGB")
        pixels = list(img.getdata())
        result = bytearray(len(pixels) * 2)
        for i, (r, g, b) in enumerate(pixels):
            rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            struct.pack_into(">H", result, i * 2, rgb565)
        return bytes(result)

    def _rgb565_to_rgb(self, data: bytes) -> bytes:
        pixels = []
        for i in range(0, len(data), 2):
            val = struct.unpack(">H", data[i:i + 2])[0]
            r = (val >> 8) & 0xF8
            g = (val >> 3) & 0xFC
            b = (val << 3) & 0xF8
            pixels.extend([r, g, b])
        return bytes(pixels)


class LuomiNestServer:
    TOPIC_CMD = "luominest/s3/cmd"
    TOPIC_STATUS = "luominest/s3/status"
    TOPIC_STREAM = "luominest/s3/stream"

    def __init__(self, broker_host: str = "localhost", broker_port: int = 1883):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="luominest_server")
        self.generator = AvatarResourceGenerator()
        self.current_state = AvatarState.IDLE
        self.streaming = False

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        logger.info(f"Connected to MQTT broker (code={reason_code})")
        client.subscribe(self.TOPIC_STATUS)

    def _on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            logger.info(f"Device status: {data}")
        except Exception:
            pass

    def start(self):
        self.client.connect(self.broker_host, self.broker_port, 60)
        self.client.loop_start()
        logger.info("Server started")

    def stop(self):
        self.streaming = False
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("Server stopped")

    def send_command(self, state: AvatarState):
        cmd = json.dumps({"action": state.value, "timestamp": __import__("time").time()})
        self.client.publish(self.TOPIC_CMD, cmd, qos=1)
        self.current_state = state
        logger.info(f"Sent command: {state.value}")

    def send_mouth_command(self, openness: int):
        cmd = json.dumps({"mouth": openness, "timestamp": __import__("time").time()})
        self.client.publish(self.TOPIC_CMD, cmd, qos=1)

    def start_streaming(self, state: AvatarState = AvatarState.IDLE, fps: int = 10):
        import threading
        self.streaming = True

        def _stream():
            import time
            frame_idx = 0
            while self.streaming:
                jpeg = self.generator.generate_jpeg_frame(state, frame_idx)
                self.client.publish(self.TOPIC_STREAM, jpeg, qos=0)
                frame_idx += 1
                time.sleep(1.0 / fps)

        t = threading.Thread(target=_stream, daemon=True)
        t.start()
        logger.info(f"Started streaming at {fps} fps")

    def stop_streaming(self):
        self.streaming = False
        logger.info("Stopped streaming")

    def interactive(self):
        print("\n=== LuomiNest ESP32-S3 Controller ===")
        print("Commands:")
        print("  happy, sad, angry, surprised, wave, nod, think, sleep, talk, idle")
        print("  stream [state]  - start JPEG streaming")
        print("  stop            - stop streaming/animation")
        print("  quit            - exit")
        print()

        while True:
            try:
                cmd = input("> ").strip().lower()
                if not cmd:
                    continue

                if cmd == "quit":
                    break
                elif cmd == "stop":
                    self.stop_streaming()
                    self.send_command(AvatarState.IDLE)
                elif cmd.startswith("stream"):
                    parts = cmd.split()
                    state = AvatarState(parts[1]) if len(parts) > 1 else AvatarState.IDLE
                    self.start_streaming(state, fps=10)
                elif cmd in [s.value for s in AvatarState]:
                    self.stop_streaming()
                    self.send_command(AvatarState(cmd))
                else:
                    print(f"Unknown command: {cmd}")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")

        self.stop()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="LuomiNest ESP32-S3 Server")
    parser.add_argument("--host", default="localhost", help="MQTT broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    args = parser.parse_args()

    server = LuomiNestServer(args.host, args.port)
    server.start()
    server.interactive()
    server.stop()


if __name__ == "__main__":
    main()
