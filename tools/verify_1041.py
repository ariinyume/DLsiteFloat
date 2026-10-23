#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1041 / v2.4.1（只升 code）】按钮「不跟随播放页消失」的**产物层**验证。

判据（12 项）
------------
A 版本与履历：aapt2 versionCode=1041 / versionName=2.4.1、新横幅在包、
  旧横幅（1040）保留在履历段、【code 1041 履历串在包且不在对照包
B 判定层进包：PageFollowPolicy.gate3Window 存在且签名 (FJJ)J、
  isPageHeld 新签名收第 13 参（J holdSnapshotGoneMs）、门③ 里 invoke-static 它
C 常量层：ActivityButtonHook.HOLD_SNAPSHOT_GONE_MS 静态常量 = 500（dexdump 的 value 行）
D 反向锚：对照包（code 1040）里没有 gate3Window / 没有 500 这个新常量

用法
----
    python tools/verify_1041.py [new.apk] [old.apk]
退出码 0 = 全部通过
"""
import os
import re
import subprocess
import sys
import zipfile

BT = r'F:\WorkBuddyCache\DLSiteSound_Plus\toolchain\android-sdk\build-tools\36.0.0'
AAPT2 = os.path.join(BT, 'aapt2.exe')
DEXDUMP = os.path.join(BT, 'dexdump.exe')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UP = os.path.dirname(ROOT)


def _latest_apk():
    """当前最新 debug 包（**下界口径**：1041 之后每一轮都用它当主验位）。"""
    out = os.path.join(ROOT, 'app', 'build', 'outputs', 'apk', 'debug')
    best, best_code = None, -1
    if os.path.isdir(out):
        for n in os.listdir(out):
            m = re.match(r'DLsiteFloat-[\d.]+-code(\d+)-debug\.apk$', n)
            if m and int(m.group(1)) > best_code:
                best, best_code = os.path.join(out, n), int(m.group(1))
    return best or os.path.join(out, 'DLsiteFloat-2.4.1-code1041-debug.apk')


APK_NEW = sys.argv[1] if len(sys.argv) > 1 else _latest_apk()
APK_OLD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    UP, 'DLsiteFloat-2.4.1-code1040-debug.apk')

PKG = 'Lio/github/ariinyume/dlsitesoundfloat/hook/'
POLICY_SIG = PKG + 'PageFollowPolicy;'
HOOK_SIG = PKG + 'ActivityButtonHook;'

fails = []
total = 0


def check(name, ok, detail=''):
    global total
    total += 1
    print('  %s %s%s' % ('OK  ' if ok else 'FAIL', name,
                         ('   ' + detail) if detail else ''))
    if not ok:
        fails.append(name)


def all_dex_blob(apk):
    with zipfile.ZipFile(apk) as z:
        names = [n for n in z.namelist() if re.match(r'classes\d*\.dex$', n)]
        return b'\n'.join(z.read(n) for n in names)


def dex_dump(apk):
    """把每个 classesN.dex 抽到 _dextmp 再 dexdump -d（不污染包目录）。"""
    scratch = os.path.join(ROOT, 'app', 'build', '_dextmp')
    os.makedirs(scratch, exist_ok=True)
    tag = os.path.basename(apk)
    out = []
    with zipfile.ZipFile(apk) as z:
        for n in [x for x in z.namelist() if re.match(r'classes\d*\.dex$', x)]:
            tmp = os.path.join(scratch, 'v1041_%s.%s' % (tag, n))
            with open(tmp, 'wb') as f:
                f.write(z.read(n))
            r = subprocess.run([DEXDUMP, '-d', tmp], capture_output=True,
                               text=True, errors='replace', encoding='utf-8')
            out.append(r.stdout)
    return '\n'.join(out)


def class_seg(dump, sig):
    i = dump.find("Class descriptor  : '%s'" % sig)
    if i < 0:
        return None
    j = dump.find('Class descriptor  :', i + 10)
    return dump[i:j if j > 0 else len(dump)]


for p in (APK_NEW, APK_OLD):
    if not os.path.isfile(p):
        print('缺少包: %s' % p)
        sys.exit(2)

print('主验 = %s (%d B)' % (os.path.basename(APK_NEW), os.path.getsize(APK_NEW)))
print('对照 = %s (%d B)' % (os.path.basename(APK_OLD), os.path.getsize(APK_OLD)))
print()

# ── A 版本与履历 ────────────────────────────────────────────────
print('=== A. 版本与履历 ===')
badging = subprocess.run([AAPT2, 'dump', 'badging', APK_NEW],
                         capture_output=True, text=True, errors='replace',
                         encoding='utf-8').stdout
code_actual = (re.search(r"versionCode='(\d+)'", badging) or ['', ''])[1]
name_actual = (re.search(r"versionName='([^']+)'", badging) or ['', ''])[1]
check('A1 aapt2 versionCode >= 1041（下界：1041 之后每轮都用最新包当主验位）',
      bool(code_actual) and int(code_actual) >= 1041, code_actual)
check('A2 aapt2 versionName 非空且形如 x.y.z',
      re.match(r'^\d+\.\d+\.\d+$', name_actual or '') is not None, name_actual)

blob_new = all_dex_blob(APK_NEW)
blob_old = all_dex_blob(APK_OLD)
BANNER = ('==== BUILD %s / code %s' % (name_actual, code_actual)).encode()
banner_old = '==== BUILD 2.4.1 / code 1040'.encode()
EV1041 = '【code 1041'.encode()
check('A3 新横幅串在包内', blob_new.count(BANNER) >= 1,
      '出现 %d 次' % blob_new.count(BANNER))
check('A4 旧横幅串（1040）在履历段保留', banner_old in blob_new,
      '保留 %d 次' % blob_new.count(banner_old))
check('A5 履历段串【code 1041 在包内', EV1041 in blob_new)
check('A6 【code 1041 不在对照包', EV1041 not in blob_old,
      '对照出现 %d 次' % blob_old.count(EV1041))

# ── B 判定层进包 ────────────────────────────────────────────────
print('=== B. 判定层进包 ===')
dump_new = dex_dump(APK_NEW)
seg_policy = class_seg(dump_new, POLICY_SIG)
check('B1 PageFollowPolicy 类在包', seg_policy is not None)
if seg_policy:
    check("B2 gate3Window 方法存在",
          "name          : 'gate3Window'" in seg_policy)
    check('B3 gate3Window 签名 = (FJJ)J',
          'gate3Window:(FJJ)J' in seg_policy)
    check('B4 isPageHeld 签名收第 13 参（J holdSnapshotGoneMs）= (ZJJJIZIIIFJJJIF)Z',
          'isPageHeld:(ZJJJIZIIIFJJJIF)Z' in seg_policy,
          '实际签名 %s' % (re.search(r'isPageHeld:\([^)]*\)[A-Z]', seg_policy)
                          or ['未找到'])[0])
    check('B5 门③ 确实 invoke-static gate3Window',
          'PageFollowPolicy;.gate3Window:(FJJ)J' in seg_policy)

# ── C 常量层 ────────────────────────────────────────────────────
print('=== C. 常量层（dexdump value）===')
seg_hook = class_seg(dump_new, HOOK_SIG)
check('C1 ActivityButtonHook 类在包', seg_hook is not None)
if seg_hook:
    m = re.search(r"name\s*:\s*'HOLD_SNAPSHOT_GONE_MS'.{0,200}?value\s*:\s*(\d+)",
                  seg_hook, re.S)
    check('C2 HOLD_SNAPSHOT_GONE_MS 静态常量存在', m is not None)
    check('C3 常量值 = 500', bool(m) and m.group(1) == '500',
          ('实际 %s' % m.group(1)) if m else '未找到')
    m2 = re.search(r"name\s*:\s*'HOLD_SNAPSHOT_MS'.{0,200}?value\s*:\s*(\d+)",
                   seg_hook, re.S)
    check('C4 长窗 HOLD_SNAPSHOT_MS 仍 = 2600', bool(m2) and m2.group(1) == '2600',
          ('实际 %s' % m2.group(1)) if m2 else '未找到')

# ── D 反向锚 ────────────────────────────────────────────────────
print('=== D. 反向锚（对照包）===')
dump_old = dex_dump(APK_OLD)
seg_old = class_seg(dump_old, POLICY_SIG)
check('D1 对照包里没有 gate3Window（证明本轮新增）',
      bool(seg_old) and 'gate3Window' not in seg_old)
seg_hook_old = class_seg(dump_old, HOOK_SIG)
check('D2 对照包里没有 HOLD_SNAPSHOT_GONE_MS',
      bool(seg_hook_old) and 'HOLD_SNAPSHOT_GONE_MS' not in seg_hook_old)
check('D3 对照包 isPageHeld 旧签名（12 参）仍在',
      bool(seg_old) and 'isPageHeld:(ZJJJIZIIIFJJIF)Z' in seg_old)

print()
print('=' * 74)
if fails:
    print('FAIL %d/%d' % (len(fails), total))
    for f in fails:
        print('  - %s' % f)
    sys.exit(1)
print('PASS %d/%d' % (total, total))
sys.exit(0)
