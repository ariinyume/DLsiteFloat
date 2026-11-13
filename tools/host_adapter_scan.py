#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1050 / 架构优化 A3】宿主离线适配体检 —— 新宿主发版的固定入口。

用法
----
    # 已解包目录（含 dex/classes*.dex 与 bundle/index.android.bundle，或 assets/）
    python tools/host_adapter_scan.py path/to/_host231

    # 或直接喂 base.apk（会解到 <out>/_host_scan_tmp/）
    python tools/host_adapter_scan.py path/to/base.apk --out path/to/host231_scan

退出码：0 = 静态闸门全过；1 = 有必过锚点 MISS；2 = 用法/路径错误。

流水线
------
解包 → 本脚本串池锚点 →（可选）真机 AdapterHealth → 改 HostInfo.VERIFIED_SET
  → 写 ADAPTER_CHECK_*.md
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))


def load_blobs(root: str) -> tuple[bytes, bytes]:
    """Return (dex_blob, bundle_blob)."""
    dex_parts: list[bytes] = []
    bundle = b""

    # Layout A: <root>/dex/classes*.dex + <root>/bundle/index.android.bundle
    dex_dir = os.path.join(root, "dex")
    if os.path.isdir(dex_dir):
        for name in sorted(os.listdir(dex_dir)):
            if name.endswith(".dex"):
                dex_parts.append(open(os.path.join(dex_dir, name), "rb").read())
        bpath = os.path.join(root, "bundle", "index.android.bundle")
        if not os.path.isfile(bpath):
            bpath = os.path.join(dex_dir, "assets", "index.android.bundle")
        if os.path.isfile(bpath):
            bundle = open(bpath, "rb").read()

    # Layout B: apktool-ish decoded tree or flat extracted apk
    if not dex_parts:
        for dirpath, _, files in os.walk(root):
            for name in sorted(files):
                path = os.path.join(dirpath, name)
                if name.endswith(".dex"):
                    dex_parts.append(open(path, "rb").read())
                elif name == "index.android.bundle" and not bundle:
                    bundle = open(path, "rb").read()

    if not dex_parts:
        raise FileNotFoundException("no classes*.dex under " + root)
    return b"\x00".join(dex_parts), bundle


class FileNotFoundException(RuntimeError):
    pass


def has(blob: bytes, s: str) -> bool:
    return s.encode("utf-8") in blob


def check(section: str, items: list[tuple[str, bytes]]) -> int:
    print(f"\n=== {section} ===")
    hit = miss = 0
    for name, blob in items:
        ok = has(blob, name)
        print(("HIT " if ok else "MISS"), name)
        hit += int(ok)
        miss += int(not ok)
    print(f"-- {hit} hit / {miss} miss / {hit + miss} total")
    return miss


def unpack_apk(apk: str, out: str) -> str:
    os.makedirs(out, exist_ok=True)
    dex_out = os.path.join(out, "dex")
    bun_out = os.path.join(out, "bundle")
    os.makedirs(dex_out, exist_ok=True)
    os.makedirs(bun_out, exist_ok=True)
    with zipfile.ZipFile(apk) as z:
        for n in z.namelist():
            base = os.path.basename(n)
            if base.startswith("classes") and base.endswith(".dex"):
                target = os.path.join(dex_out, base)
                with z.open(n) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                print("extracted", base, os.path.getsize(target))
            elif base == "index.android.bundle":
                target = os.path.join(bun_out, base)
                with z.open(n) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                print("extracted", base, os.path.getsize(target))
            elif n == "assets/app.config":
                target = os.path.join(dex_out, "assets", "app.config")
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with z.open(n) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    return out


def run(root: str) -> int:
    dex, bundle = load_blobs(root)
    allb = dex + b"\x00" + bundle
    print("root=", root)
    print("dex_bytes=", len(dex), "bundle_bytes=", len(bundle))

    fails = 0
    fails += check(
        "DEX class anchors (must survive R8 keep)",
        [
            ("Lcom/reactnativecommunity/slider/ReactSlider;", dex),
            ("Landroidx/appcompat/widget/AppCompatSeekBar;", dex),
            ("Lexpo/modules/audio/AudioPlaylist;", dex),
            ("Lexpo/modules/audio/AudioPlayer;", dex),
            ("Lexpo/modules/audio/BaseAudioPlayer;", dex),
            ("Lcom/facebook/react/modules/network/NetworkingModule;", dex),
            ("Lexpo/modules/fetch/NativeResponse;", dex),
            ("readWithProgress", dex),
        ],
    )
    fails += check(
        "DEX status Map keys",
        [
            ("currentTime", dex),
            ("playbackState", dex),
            ("trackCount", dex),
            ("currentIndex", dex),
            ("playing", dex),
            ("duration", dex),
        ],
    )
    fails += check(
        "BUNDLE RN testIDs / ziptree",
        [
            ("SUBTITLE_BUTTON", bundle if bundle else allb),
            ("FULL_PLAYER_CLOSE_BUTTON", bundle if bundle else allb),
            ("ziptree.json", bundle if bundle else allb),
            ("webvtt", allb),
            ("subtitles", allb),
        ],
    )
    fails += check(
        "Host anti-tamper (expect MISS)",
        [
            ("PlayIntegrity", allb),
            ("SafetyNet", allb),
            ("XposedBridge", allb),
            ("de.robv.android.xposed", allb),
            ("lsposed", allb),
            ("RootBeer", allb),
        ],
    )

    print("\n=== WHITELIST GATE (static must-HIT) ===")
    must = [
        ("ReactSlider", has(dex, "Lcom/reactnativecommunity/slider/ReactSlider;")),
        ("AudioPlaylist", has(dex, "Lexpo/modules/audio/AudioPlaylist;")),
        ("AudioPlayer", has(dex, "Lexpo/modules/audio/AudioPlayer;")),
        ("NetworkingModule", has(dex, "Lcom/facebook/react/modules/network/NetworkingModule;")),
        ("readWithProgress", has(dex, "readWithProgress")),
        (
            "status keys",
            all(has(dex, k) for k in ("currentTime", "trackCount", "playbackState")),
        ),
        ("SUBTITLE_BUTTON", has(bundle if bundle else allb, "SUBTITLE_BUTTON")),
        ("FULL_PLAYER_CLOSE_BUTTON", has(bundle if bundle else allb, "FULL_PLAYER_CLOSE_BUTTON")),
        ("ziptree.json", has(bundle if bundle else allb, "ziptree.json")),
    ]
    gate_fail = 0
    for name, ok in must:
        print(("PASS" if ok else "FAIL"), name)
        gate_fail += int(not ok)

    print(
        "STATIC_ADAPTER_OK"
        if gate_fail == 0
        else "STATIC_ADAPTER_FAIL"
    )
    print(
        "note: okhttp3 class names may be R8-renamed; Float uses Shape discovery — "
        "runtime AdapterHealth still required before HostInfo.VERIFIED_SET."
    )
    # anti-tamper hits are informational (Frida Friday false-positives possible);
    # gate only cares about must-HIT list.
    return 0 if gate_fail == 0 else 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="DLsiteSound host offline adapter scan")
    ap.add_argument("path", help="unpacked host dir, or base.apk / .apks")
    ap.add_argument(
        "--out",
        default="",
        help="when path is an apk/apks, extract here (default: <path>_scan)",
    )
    args = ap.parse_args(argv)
    path = os.path.abspath(args.path)
    if not os.path.exists(path):
        print("path not found:", path, file=sys.stderr)
        return 2

    root = path
    if os.path.isfile(path) and path.lower().endswith((".apk", ".apks")):
        out = args.out or (path + "_scan")
        if path.lower().endswith(".apks"):
            # extract base.apk first
            tmp = out + "_apks"
            os.makedirs(tmp, exist_ok=True)
            with zipfile.ZipFile(path) as z:
                z.extractall(tmp)
            base = os.path.join(tmp, "base.apk")
            if not os.path.isfile(base):
                # largest apk
                apks = [
                    os.path.join(tmp, n)
                    for n in os.listdir(tmp)
                    if n.endswith(".apk")
                ]
                if not apks:
                    print("no apk inside .apks", file=sys.stderr)
                    return 2
                base = max(apks, key=os.path.getsize)
            root = unpack_apk(base, out)
        else:
            root = unpack_apk(path, out)

    try:
        return run(root)
    except FileNotFoundException as e:
        print(e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
