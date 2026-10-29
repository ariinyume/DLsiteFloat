# -*- coding: utf-8 -*-
"""Android SDK / build-tools 定位。

入库脱敏说明
------------
早期的一次性验证脚本把 Android SDK 的**绝对路径写死**在源码里（某台机器的盘符 + 目录名），
既会泄露开发机的目录结构，也让别人 clone 下来根本跑不起来。
现在统一走本模块：**先环境变量，再 local.properties，最后才回落「仓库同级的离线工具链」**。

用法
----
    from sdkpath import build_tools
    BT = build_tools('36.0.0')          # → <sdk>/build-tools/36.0.0
    BT = build_tools()                  # → 已安装的最高版本
"""
import os

# 本机离线工具链的相对布局：<工作区>/toolchain/android-sdk，仓库是 <工作区>/<repo>
_OFFLINE_TAIL = ("toolchain", "android-sdk")


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _from_local_properties():
    """读仓库根 local.properties 的 sdk.dir（Java properties 转义：'\\:'、'\\\\'）。"""
    p = os.path.join(_repo_root(), "local.properties")
    try:
        with open(p, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                s = line.strip()
                if not s.startswith("sdk.dir="):
                    continue
                v = s.split("=", 1)[1].strip()
                v = v.replace("\\:", ":").replace("\\\\", "\\")
                return v if os.path.isdir(v) else None
    except OSError:
        pass
    return None


def sdk_root():
    """Android SDK 根目录。取不到也返回一个路径，由调用方在使用时报错。"""
    for key in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        v = os.environ.get(key)
        if v and os.path.isdir(v):
            return v
    v = _from_local_properties()
    if v:
        return v
    return os.path.join(os.path.dirname(_repo_root()), *_OFFLINE_TAIL)


def build_tools(version=None):
    """build-tools 目录。指定 version 且存在就用它，否则返回已安装的最高版本。"""
    base = os.path.join(sdk_root(), "build-tools")
    if version:
        cand = os.path.join(base, version)
        if os.path.isdir(cand):
            return cand
    try:
        names = sorted(n for n in os.listdir(base)
                       if os.path.isdir(os.path.join(base, n)))
    except OSError:
        return base
    return os.path.join(base, names[-1]) if names else base
