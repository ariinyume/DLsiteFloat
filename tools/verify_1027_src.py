#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1027 / v2.3.5】只加诊断、不发版 的 **源码层**验证。
（读的是**活的工作区** ⇒ 判结构与接线，版本号只判「本轮值」+ label 只守形态；见铁律 82/⑬/94）

本轮两件事（Ari 2026-10-19：先改代码，不用发版）
------------------------------------------------
① 上屏行一致观测加「连续次数」（streak）—— 原来只记总量，读不出失配是
   「采样相位差」（自己会消失，不该追）还是「索引停在别处」（才需要镜像优先定位）。
② 网络通道静默自检 —— 补齐「钩子挂上但从不触发」这个盲区。

验什么
------
L1–L5   行同步观测：明细上限 / 成串门槛 / streak 归零 / 明细带 streak / 汇总三段
L6–L7   渲染未被接管（MISMATCH 分支不许出现 setCurrentSubtitles / currentCueIndex 赋值）
M1–M6   通道静默：阈值 20s / peekedCount / 调用点 / 三项判据齐 / 只报一次 / 不改 State
N1–N4   版本纪律：code 1027、name 不变、label 形态、横幅自报 + 禁字符
K1–K3   边界（本轮**不动**）：selfComputedLines 仍在用 / 网络两通道仍在 / 设置页无新增开关

用法
----
    python verify_1027_src.py [src_root]
退出码 0 = 全部通过
"""

import os
import re
import sys

SRC = None
fails = []
total = 0


def check(name, ok, detail=''):
    global total
    total += 1
    if ok:
        print('  PASS  %s' % name)
    else:
        print('  FAIL  %s   %s' % (name, detail))
        fails.append(name)


def read(p):
    """读源码：先归一化行尾（铁律 58/106）。"""
    with open(p, 'rb') as f:
        return f.read().decode('utf-8', 'replace').replace('\r\n', '\n')


def jp(*parts):
    return os.path.join(SRC, 'java', 'io', 'github', 'ariinyume', 'dlsitesoundfloat', *parts)


def body(src, header):
    """取一个方法/内部类的花括号体（从 header 起、配对到收口）。"""
    i = src.find(header)
    if i < 0:
        return ''
    j = src.find('{', i)
    if j < 0:
        return ''
    depth = 0
    for k in range(j, len(src)):
        c = src[k]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return src[j:k + 1]
    return ''


def main():
    global SRC
    SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'src', 'main')

    sync = read(jp('hook', 'HostLineSync.java'))
    health = read(jp('hook', 'AdapterHealth.java'))
    net = read(jp('hook', 'NetworkHook.java'))
    viewhook = read(jp('hook', 'SubtitleViewHook.java'))
    # SRC = app/src/main ⇒ app/build.gradle 在两级之上
    gradle = read(os.path.join(SRC, '..', '..', 'build.gradle'))
    module = read(jp('DlsiteSoundSubtitleModule.java'))

    print('\n── L 行同步观测（streak）──────────────────────────────────')

    check('L1 明细上限 DETAIL_MAX = 8',
          re.search(r'DETAIL_MAX\s*=\s*8\s*;', sync) is not None)

    check('L2 成串门槛 PERSISTENT_STREAK = 3',
          re.search(r'PERSISTENT_STREAK\s*=\s*3\s*;', sync) is not None)

    observe = body(sync, 'public static void observe(')
    check('L3 对上就归零 streak、失配就自增',
          'sMissStreak = 0;' in observe and 'sMissStreak++;' in observe)

    check('L4 失配走统一出口 logMismatchLocked（带 hostLines 条数）',
          'logMismatchLocked(firstHost, hostLines.size(), selfLines);' in observe)

    detail = body(sync, 'private static void logMismatchLocked(')
    check('L5 明细带 streak / episodes，且明写不改渲染',
          'streak=' in detail and 'episodes=' in detail
          and 'rendering NOT changed' in detail)

    summ = body(sync, 'public static synchronized String summary()')
    check('L6 汇总行给三段：mismatch / persistent / streak',
          'mismatch ' in summ and 'persistent ' in summ and ', streak ' in summ)

    check('L7 观测不接管渲染（失配分支里不写镜像、不写索引）',
          'setCurrentSubtitles' not in observe
          and 'currentCueIndex' not in observe
          and 'notifyObservers' not in observe)

    print('\n── M 网络通道静默自检 ────────────────────────────────────')

    check('M1 静默阈值 SILENT_GRACE_MS = 20_000L',
          re.search(r'SILENT_GRACE_MS\s*=\s*20_000L\s*;', health) is not None)

    check('M2 NetworkHook 暴露 peekedCount() 且返回 sPeeked',
          re.search(r'public static int peekedCount\(\)\s*\{\s*return sPeeked;\s*\}', net) is not None)

    check('M3 scan() 里接上自检（scan 是播放页内唯一确定会周期跑到的点）',
          'AdapterHealth.tickChannelSilence(NetworkHook.peekedCount());' in viewhook)

    tick = body(health, 'public static synchronized void tickChannelSilence(')
    check('M4 三项判据齐（播放页 HIT / 两通道 DEGRADED / peeked == 0）',
          'get(Item.VIEW_PAGE) != State.HIT' in tick
          and 'State.DEGRADED' in tick
          and 'peekedResponses > 0' in tick)

    check('M5 只报一次（sSilentLogged 先判后置）',
          'sSilentLogged ||' in tick and 'sSilentLogged = true;' in tick)

    check('M6 不改任何 State（不调 mark/hit/miss/degraded、不写 STATE）',
          'STATE.put' not in tick and 'mark(' not in tick
          and 'AdapterHealth.hit(' not in tick and 'AdapterHealth.miss(' not in tick)

    print('\n── N 版本纪律 ───────────────────────────────────────────')

    check('N1 versionCode = 1027', re.search(r'def appVersionCode\s*=\s*1027\b', gradle) is not None)
    check('N2 versionName 保持 2.3.5',
          re.search(r"def appVersionName\s*=\s*'2\.3\.5'", gradle) is not None)
    # label 只守形态：日期段跟构建当天，不许钉具体值（铁律 94）
    check('N3 label 形态合规（MMDD.N，N ≥ 1）',
          re.search(r"def appVersionCodeLabel\s*=\s*'(\d{4})\.([1-9]\d*)'", gradle) is not None,
          repr(re.findall(r"appVersionCodeLabel\s*=\s*'([^']*)'", gradle)))

    hist = ''
    m = re.search(r'// 【code 1027】[^\n]*\n((?://[^\n]*\n)+)', gradle)
    if m:
        hist = m.group(1)
    check('N4 履历段自报【code 1027】并以「版本号不变 / code 升」收尾',
          bool(hist) and '2.3.5 不变' in hist and 'code 1026 升 1027' in hist,
          '履历段长度 %d' % len(hist))

    banner = ''
    for ln in module.split('\n'):
        if '==== BUILD' in ln and 'LogGate' in ln and 'code 1027' in ln:
            banner = ln
            break
    body_txt = banner[banner.index('"') + 1:banner.rindex('"')] if banner else ''
    check('N5 调试横幅自报本轮两件事（streak / NET_SILENT）',
          'streak' in body_txt and 'NET_SILENT' in body_txt and '只加诊断' in body_txt)
    check('N6 横幅正文无禁用字符（ASCII 引号 / 反斜杠 / 反引号）',
          body_txt != '' and '"' not in body_txt
          and '\\' not in body_txt and '`' not in body_txt)
    check('N7 常开横幅已进 1027',
          'XposedCompat.log("[DLsiteSoundFloat] ==== BUILD 2.3.5 / code 1027");' in module)

    print('\n── K 边界（本轮不动）─────────────────────────────────────')

    check('K1 观测入参仍是纯自算 selfComputedLines()',
          'HostLineSync.observe(r.liveLines, repo.selfComputedLines());' in viewhook)
    check('K2 两条网络通道仍在（NET_BUILD / NET_RN 都有上报）',
          'Item.NET_BUILD' in net and 'Item.NET_RN' in net)
    check('K3 设置页没有为本轮诊断新增任何开关行',
          'Silent' not in read(jp('ui', 'SettingsActivity.java'))
          and 'SILENT' not in read(jp('ui', 'Strings.java')))

    print('\n' + '=' * 60)
    if fails:
        print('FAIL %d/%d' % (len(fails), total))
        for f in fails:
            print('  - ' + f)
        return 1
    print('PASS %d/%d' % (total, total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
