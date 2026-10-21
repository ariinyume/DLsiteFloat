#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1039 / v2.4.1（只升 code）】「新下载作品已预取，关代理后仍无字幕」的产物层验证。

分节
----
A 版本 / 横幅
B 预取池受限推断 + 无字幕负证据
C 裁决窗到点后的预取兜底
D 反向锚（旧「no work key hint 直接拒绝」不得回包）

用法
----
    python tools/verify_1039.py [new.apk] [old.apk]
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
APK_NEW = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    ROOT, 'app', 'build', 'outputs', 'apk', 'debug', 'DLsiteFloat-2.4.1-code1039-debug.apk')
APK_OLD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    UP, 'DLsiteFloat-2.4.1-code1038-debug.apk')

fails = []
total = 0


def check(name, ok, detail=''):
    global total
    total += 1
    if ok:
        print('  OK   %s%s' % (name, ('   ' + detail) if detail else ''))
    else:
        print('  FAIL %s   %s' % (name, detail))
        fails.append(name)


def all_dex_blob(apk):
    with zipfile.ZipFile(apk) as z:
        names = [n for n in z.namelist() if re.match(r'classes\d*\.dex$', n)]
        return b'\n'.join(z.read(n) for n in names)


def dex_dump(apk):
    scratch = os.path.join(ROOT, 'app', 'build', '_dextmp')
    os.makedirs(scratch, exist_ok=True)
    tag = os.path.basename(apk)
    out = []
    with zipfile.ZipFile(apk) as z:
        for n in [x for x in z.namelist() if re.match(r'classes\d*\.dex$', x)]:
            tmp = os.path.join(scratch, 'v1039_%s.%s' % (tag, n))
            with open(tmp, 'wb') as f:
                f.write(z.read(n))
            r = subprocess.run([DEXDUMP, '-d', tmp], capture_output=True, text=True,
                               errors='replace', encoding='utf-8')
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

# ── A 版本 / 横幅 ───────────────────────────────────────────────────────
print()
print('=' * 74)
print('A 版本 / 横幅')
print('=' * 74)

badging = subprocess.run([AAPT2, 'dump', 'badging', APK_NEW],
                         capture_output=True, text=True, errors='replace',
                         encoding='utf-8').stdout
code_actual = (re.search(r"versionCode='(\d+)'", badging) or [''])[1]
name_actual = (re.search(r"versionName='([^']+)'", badging) or [''])[1]
check('A1 aapt2 versionCode = 1039', code_actual == '1039', code_actual)
check('A2 aapt2 versionName = 2.4.1', name_actual == '2.4.1', name_actual)

blob_new = all_dex_blob(APK_NEW)
blob_old = all_dex_blob(APK_OLD)
BANNER = '==== BUILD 2.4.1 / code 1039'.encode()
banner_old = '==== BUILD 2.4.1 / code 1038'.encode()
check('A3 新横幅串在包内', blob_new.count(BANNER) >= 1,
      '出现 %d 次' % blob_new.count(BANNER))
check('A4 旧横幅串在履历段保留', banner_old in blob_new,
      '履历段保留 %d 次' % blob_new.count(banner_old))
check('A5 履历段串【code 1039 在包内', '【code 1039'.encode() in blob_new)
check('A6 履历段串【code 1039 不在对照包', '【code 1039'.encode() not in blob_old,
      '对照出现 %d 次' % blob_old.count('【code 1039'.encode()))

# ── B 预取池受限推断 + 负证据 ───────────────────────────────────────────
print()
print('=' * 74)
print('B 预取池受限推断 + 无字幕负证据')
print('=' * 74)

check('B1 受限推断串 ambiguous work key 在包内',
      b'(ambiguous work key: ' in blob_new)
check('B2 全局负证据串在包内',
      b'(some prefetched work has' in blob_new)
check('B3 唯一作品键推断串在包内',
      b'(unique work key across ' in blob_new)
check('B4 无字幕作品负包日志串在包内',
      b'negative pack kept' in blob_new)
check('B5 无字幕作品索引行（N 行）读取条件仍在',
      b'noSubtitleTracks' in blob_new)

# ── C 裁决窗到点后的预取兜底 ─────────────────────────────────────────────
print()
print('=' * 74)
print('C 裁决窗到点后的预取兜底')
print('=' * 74)

check('C1 code 1039 预取兜底日志串在包内',
      b'[code 1039] cloud gave no subtitle within grace' in blob_new)
check('C2 prefetch fallback 串在包内',
      b'prefetch fallback' in blob_new)
check('C3 旧 code 1012 磁盘兜底串仍在（未误删）',
      b'resumed from LOCAL disk cache (cloud-first, local fallback)' in blob_new)

# ── D 反向锚 ───────────────────────────────────────────────────────────
print()
print('=' * 74)
print('D 反向锚（旧「直接拒绝」不得回包）')
print('=' * 74)

dn = dex_dump(APK_NEW)
seg_prefetch = class_seg(
    dn, 'Lio/github/ariinyume/dlsitesoundfloat/hook/ZiptreePrefetch;')
check('D1 旧 REFUSE no work key hint 串不在 ZiptreePrefetch 类体',
      bool(seg_prefetch) and '(no work key hint)' not in seg_prefetch)
check('D2 错字段 noSubtitleDurations 不在包内',
      b'noSubtitleDurations' not in blob_new)

print()
print('=' * 74)
if fails:
    print('FAIL %d/%d' % (len(fails), total))
    for f in fails:
        print('  - %s' % f)
    sys.exit(1)
print('PASS %d/%d' % (total, total))
sys.exit(0)
