import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import live2d_renderer as lr
from live2d_renderer import (
    Live2DRenderer,
    apply_device_profile,
    DEVICE_PROFILES,
    img_to_jpeg,
    rgb888_to_rgb565_be,
    rgb888_to_bgr565_le,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_MODEL = os.path.join(
    SCRIPT_DIR, "models", "llny", "mianfeimox", "llny.model3.json"
)
DEFAULT_EXP_MAP = os.path.join(SCRIPT_DIR, "exp_map.json")

ALL_STATES = ["idle", "happy", "sad", "angry", "surprised", "think", "neutral", "talk", "sleep"]

LOCAL_STATES = ["idle", "neutral", "sleep"]

DEFAULT_FPS = 30
DEFAULT_DURATION = 4.0
DEFAULT_QUALITY = 80

DEVICE_DEFAULTS = {
    "s3": {"fps": 15, "format": "raw"},
    "p4": {"fps": 30, "format": "bgr565"},
}


def prerender_sequences(args):
    apply_device_profile(args.device)

    output_dir = args.output
    os.makedirs(output_dir, exist_ok=True)

    fmt = args.format

    print(f"[INFO] Loading Live2D model: {args.model}")
    print(f"[INFO] Character: {args.character}")
    print(f"[INFO] Output: {output_dir}")
    print(f"[INFO] Frame size: {lr.WIDTH}x{lr.HEIGHT}")
    print(f"[INFO] Format: {fmt}")
    print(f"[INFO] FPS: {args.fps}, Duration: {args.duration}s, Quality: {args.quality}")

    renderer = Live2DRenderer(
        model_path=args.model,
        exp_map_path=args.exp_map,
        character=args.character,
    )
    renderer.init_opengl()

    states = args.states.split(",") if args.states else ALL_STATES
    manifest = {"sequences": []}

    ext = "raw" if fmt in ("raw", "bgr565") else "jpg"
    total_frames = 0

    for state_name in states:
        state_name = state_name.strip().lower()
        if state_name not in ALL_STATES:
            print(f"[WARN] Unknown state: {state_name}, skipping")
            continue

        seq_dir = os.path.join(output_dir, state_name)
        os.makedirs(seq_dir, exist_ok=True)

        renderer.set_state(state_name)
        time.sleep(0.5)

        fps = args.fps
        duration = args.duration
        frame_count = int(fps * duration)
        is_local = state_name in LOCAL_STATES

        print(f"\n[RENDER] State: {state_name}")
        print(f"  Frames: {frame_count}, FPS: {fps}, Duration: {duration}s")
        print(f"  Format: {fmt.upper()}")
        print(f"  Category: {'LOCAL (offline)' if is_local else 'STREAM (online)'}")

        for i in range(frame_count):
            img = renderer.render()

            filename = f"{i+1:04d}.{ext}"
            filepath = os.path.join(seq_dir, filename)

            if fmt == "bgr565":
                frame_data = rgb888_to_bgr565_le(img)
            elif fmt == "raw":
                frame_data = rgb888_to_rgb565_be(img)
            else:
                frame_data = img_to_jpeg(img, args.quality)

            with open(filepath, "wb") as f:
                f.write(frame_data)

            if (i + 1) % fps == 0 or i == 0:
                print(f"  [{i+1}/{frame_count}] {filename} ({len(frame_data)} bytes)")

            interval = 1.0 / fps
            time.sleep(max(0, interval * 0.1))

        manifest["sequences"].append({
            "name": state_name,
            "path": f"/sdcard/frames/{state_name}",
            "frame_count": frame_count,
            "fps": fps,
            "format": fmt,
            "loop": True,
        })

        total_frames += frame_count
        print(f"  Done: {frame_count} frames written to {seq_dir}")

    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"\n[INFO] Manifest written to {manifest_path}")
    print(f"[INFO] Total: {total_frames} frames across {len(manifest['sequences'])} states")

    total_size = 0
    for state_name in states:
        state_name = state_name.strip().lower()
        seq_dir = os.path.join(output_dir, state_name)
        if os.path.isdir(seq_dir):
            for fn in os.listdir(seq_dir):
                fp = os.path.join(seq_dir, fn)
                if os.path.isfile(fp):
                    total_size += os.path.getsize(fp)
    print(f"[INFO] Total size: {total_size / 1024 / 1024:.1f} MB")
    print(f"\n[NEXT] Copy the '{output_dir}' folder to your SD card's /frames/ directory:")
    print(f"  SD card path: /sdcard/frames/")
    print(f"  So the structure should be:")
    print(f"    /sdcard/frames/manifest.json")
    for seq in manifest["sequences"]:
        print(f"    /sdcard/frames/{seq['name']}/0001.{ext} ... {seq['frame_count']:04d}.{ext}")

    renderer.cleanup()


def main():
    parser = argparse.ArgumentParser(
        description="LuomiNest Prerender Server - Generate frame sequences for ESP32",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Prerender all states for P4 in BGR565 format (recommended for P4, no decode needed)
  python prerender_server.py --device p4 --format bgr565

  # Prerender for P4 in JPEG format (smaller files, needs JPEG decode on device)
  python prerender_server.py --device p4 --format jpg

  # Prerender for S3 in RAW format (RGB565 big-endian)
  python prerender_server.py --device s3 --format raw

  # Prerender only local states
  python prerender_server.py --device p4 --format bgr565 --states idle,neutral,sleep

  # Prerender at 30 FPS for P4
  python prerender_server.py --device p4 --format bgr565 --fps 30
""")
    parser.add_argument(
        "--device", choices=["s3", "p4"], default="p4",
        help="Target device (s3=ESP32-S3 320x480, p4=ESP32-P4 400x540)"
    )
    parser.add_argument(
        "--format", choices=["raw", "bgr565", "jpg"], default=None,
        help="Output format: bgr565=BGR565 LE for P4 (no decode, fastest), raw=RGB565 BE for S3, jpg=JPEG (smaller, needs decode)"
    )
    parser.add_argument(
        "--output", default=os.path.join(SCRIPT_DIR, "frames"),
        help="Output directory for frame sequences (default: server/frames/)"
    )
    parser.add_argument(
        "--states", default=",".join(ALL_STATES),
        help="Comma-separated list of states to prerender (default: all)"
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
        "--fps", type=int, default=None,
        help="Frames per second (default: 30 for P4, 15 for S3)"
    )
    parser.add_argument(
        "--duration", type=float, default=DEFAULT_DURATION,
        help="Duration in seconds per state (default: 4.0)"
    )
    parser.add_argument(
        "--quality", type=int, default=DEFAULT_QUALITY,
        help="JPEG quality 1-100 (default: 80, only used with --format jpg)"
    )

    args = parser.parse_args()

    dev_defaults = DEVICE_DEFAULTS.get(args.device, DEVICE_DEFAULTS["p4"])
    if args.format is None:
        args.format = dev_defaults["format"]
    if args.fps is None:
        args.fps = dev_defaults["fps"]

    if not os.path.exists(args.model):
        print(f"[ERROR] Model file not found: {args.model}")
        sys.exit(1)

    if not os.path.exists(args.exp_map):
        print(f"[ERROR] Expression map not found: {args.exp_map}")
        sys.exit(1)

    prerender_sequences(args)


if __name__ == "__main__":
    main()
