#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1041 / v2.4.1（只升 code）】按钮「不跟随播放页消失」的**源码层**验证。

判据（18 项）
------------
A 版本号四处：appVersionCode=1041 / appVersionName=2.4.1 / appVersionTag=2.4.1 / label=1022.1
B 新常量：HOLD_SNAPSHOT_GONE_MS=500L 恰定义 1 次；长窗 HOLD_SNAPSHOT_MS=2600L 未被改坏
C 判定层：PageFollowPolicy.gate3Window 存在、面积判据 `<= 0f`、门③ 真的改调它
D hook 侧：isPageHeld 调用点把新阈值传进去了
E 双向回归：GoldenVectorTest / verify_page_follow_policy.py 各有 3 条新向量
F 反向锚：旧的「门③ 直接比 holdSnapshotMs」形态在 Policy 里绝迹
G 既有红灯清零：protocol_selfCheckPasses 钉 2（code 1019 起一直是 1 FAIL）
H 注册：run_all_verify.py 收录本脚本与 verify_1041.py

用法
----
    python tools/verify_1041_src.py
退出码 0 = 全部通过
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, 'app', 'src', 'main', 'java', 'io', 'github',
                    'ariinyume', 'dlsitesoundfloat', 'hook')
POLICY = os.path.join(HOOK, 'PageFollowPolicy.java')
BUTTON = os.path.join(HOOK, 'ActivityButtonHook.java')
GRADLE = os.path.join(ROOT, 'app', 'build.gradle')
BRIDGE = os.path.join(ROOT, 'app', 'src', 'test', 'java', 'io', 'github',
                      'ariinyume', 'dlsitesoundfloat', 'hook', 'TestAccessBridge.java')
GOLDEN = os.path.join(ROOT, 'app', 'src', 'test', 'java', 'io', 'github',
                      'ariinyume', 'dlsitesoundfloat', 'GoldenVectorTest.java')
PYVEC = os.path.join(ROOT, 'tools', 'geom', 'verify_page_follow_policy.py')
RUNALL = os.path.join(ROOT, 'tools', 'run_all_verify.py')
CHANGELOG = os.path.join(ROOT, 'CHANGELOG.md')

fails = []
total = 0


def check(name, ok, detail=''):
    global total
    total += 1
    print('  %s %s%s' % ('OK  ' if ok else 'FAIL', name,
                         ('   ' + detail) if detail else ''))
    if not ok:
        fails.append(name)


def read(p):
    with open(p, encoding='utf-8', errors='replace') as f:
        return f.read()


for p in (POLICY, BUTTON, GRADLE, BRIDGE, GOLDEN, PYVEC, RUNALL, CHANGELOG):
    if not os.path.isfile(p):
        print('缺少文件: %s' % p)
        sys.exit(2)

policy = read(POLICY)
button = read(BUTTON)
gradle = read(GRADLE)
bridge = read(BRIDGE)
golden = read(GOLDEN)
pyvec = read(PYVEC)
runall = read(RUNALL)
changelog = read(CHANGELOG)

# ── A 版本号四处 ────────────────────────────────────────────────
print('=== A. 版本号（只升 code）===')
_vc = re.search(r'^def appVersionCode\s*=\s*(\d+)\s*$', gradle, re.M)
check('A1 appVersionCode >= 1041（下界：不钉死轮次，防后续轮次假 FAIL）',
      _vc is not None and int(_vc.group(1)) >= 1041,
      ('实际 ' + _vc.group(1)) if _vc else '未找到')
_vn = re.search(r"^def appVersionName\s*=\s*'([\d.]+)'\s*$", gradle, re.M)
check('A2 appVersionName 形态 x.y.z（不钉死具体版本，防后续轮次假 FAIL）',
      _vn is not None, ('实际 ' + _vn.group(1)) if _vn else '未找到')
_vt = re.search(r"^def appVersionTag\s*=\s*'([\d.]+)'\s*$", gradle, re.M)
check('A3 appVersionTag 与 appVersionName 一致（tag 进文件名）',
      _vt is not None and _vn is not None and _vt.group(1) == _vn.group(1),
      ('tag=%s name=%s' % (_vt.group(1) if _vt else '?', _vn.group(1) if _vn else '?')))
check('A4 appVersionCodeLabel 形态为 MMDD.N（只守形态，不钉当天）',
      re.search(r"^def appVersionCodeLabel\s*=\s*'\d{4}\.\d+'\s*$", gradle, re.M) is not None)

# ── B 新常量 ────────────────────────────────────────────────────
print('=== B. 阈值常量 ===')
n_gone = len(re.findall(r'HOLD_SNAPSHOT_GONE_MS\s*=\s*500L\s*;', button))
check('B1 HOLD_SNAPSHOT_GONE_MS = 500L 定义恰 1 处', n_gone == 1,
      '实际 %d 处' % n_gone)
check('B2 长窗 HOLD_SNAPSHOT_MS = 2600L 未被改坏',
      re.search(r'HOLD_SNAPSHOT_MS\s*=\s*2600L\s*;', button) is not None)
check('B3 判定层不重复持有阈值（无第二个赋值点）',
      re.search(r'HOLD_SNAPSHOT_GONE_MS\s*=', policy) is None)

# ── C 判定层 ────────────────────────────────────────────────────
print('=== C. PageFollowPolicy 分档判据 ===')
check('C1 gate3Window 方法存在',
      re.search(r'static long gate3Window\s*\(', policy) is not None)
check('C2 面积判据是 `<= 0f`（0% = 真的看不见了）',
      re.search(r'anchorAreaRatio\s*<=\s*0f\s*\?\s*holdSnapshotGoneMs\s*:\s*'
                r'holdSnapshotMs', policy) is not None)
check('C3 isPageHeld 签名收 holdSnapshotGoneMs',
      re.search(r'long holdSnapshotMs,\s*\n\s*long holdSnapshotGoneMs,', policy)
      is not None)
check('C4 门③ 真的改调 gate3Window（不再直接比 holdSnapshotMs）',
      'now - heldOffsetMs < gate3Window(anchorAreaRatio,' in policy)

# ── D hook 侧传参 ───────────────────────────────────────────────
print('=== D. hook 侧调用点 ===')
check('D1 isPageHeld 调用点传入新阈值',
      'PAGE_MOTION_HOLD_MS, HOLD_SNAPSHOT_MS, HOLD_SNAPSHOT_GONE_MS,' in button)

# ── E 双向回归 ──────────────────────────────────────────────────
print('=== E. 双向回归（JVM + 离线脚本）===')
for m in ('gate3_goneAnchor_usesShortWindow', 'gate3_visibleAnchor_keepsLongWindow'):
    check('E1 GoldenVectorTest.%s 存在' % m, m in golden)
check('E2 GoldenVectorTest 里有短窗常量 500L',
      re.search(r'HOLD_SNAPSHOT_GONE_MS\s*=\s*500L\s*;', golden) is not None)
check('E3 verify_page_follow_policy.py 有 HOLD_SNAPSHOT_GONE_MS = 500',
      re.search(r'HOLD_SNAPSHOT_GONE_MS\s*=\s*500\b', pyvec) is not None)
check('E4 脚本有 gate3_window 且门③ 调它',
      'def gate3_window(' in pyvec and
      'gate3_window(' in pyvec.split('def is_page_held', 1)[-1])
n_vec = pyvec.count('【1041】')
check('E5 脚本新增 3 条【1041】向量', n_vec == 3, '实际 %d 条' % n_vec)

# ── F 反向锚 ────────────────────────────────────────────────────
print('=== F. 反向锚（旧形态绝迹）===')
check('F1 旧「now - heldOffsetMs < holdSnapshotMs」在 Policy 里绝迹',
      'now - heldOffsetMs < holdSnapshotMs' not in policy)
check('F2 hook 侧不再自己算门③（判据只在 Policy 一份）',
      'now - heldOffsetMs <' not in button)

# ── G 既有红灯清零 ──────────────────────────────────────────────
print('=== G. 既有红灯 ===')
check('G1 protocol_selfCheckPasses 已对齐 PROTOCOL_VERSION = 2',
      'assertEquals(2, Protocol.PROTOCOL_VERSION)' in golden)
check('G2 不再钉 1',
      'assertEquals(1, Protocol.PROTOCOL_VERSION)' not in golden)

# ── H 注册与履历 ────────────────────────────────────────────────
print('=== H. 注册与履历 ===')
check("H1 run_all_verify.py 收录 verify_1041.py",
      "'verify_1041.py'" in runall)
check("H2 run_all_verify.py 收录 verify_1041_src.py",
      "'verify_1041_src.py'" in runall)
check('H3 run_all_verify.py 里 1041 排在 1040 之前（最新在上）',
      runall.find("'verify_1041.py'") >= 0
      and runall.find("'verify_1041.py'") < runall.find("'verify_1040.py'"))
check('H4 CHANGELOG 有 1041 条目',
      'code 1040 → 1041' in changelog)

print()
print('=' * 74)
if fails:
    print('FAIL %d/%d' % (len(fails), total))
    for f in fails:
        print('  - %s' % f)
    sys.exit(1)
print('PASS %d/%d' % (total, total))
sys.exit(0)
