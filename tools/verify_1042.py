#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1042 / v2.4.1（只升 code）】「离线读到别人音轨字幕」的**产物层**验证。

判据（13 项）
------------
A 版本与履历：aapt2 versionCode>=1042 / versionName=2.4.1、新横幅在包、
  【code 1042 履历串在包且不在对照包（下界口径：后续轮次用最新包当主验位）
B 缓存时长闸门进包：ZiptreePrefetch.cacheGateAllows(J)Z
C 印章锚定进包：PlaylistKey.stampForLoadedJson(JJJ)J
D 时长贯通：SubtitleRepository.loadFromJson(String,String,Z,J)V 重载
E 索引口径：SubtitleCache 静态常量 INDEX_SCHEMA = 5
F 反向锚：对照包（code 1041）里没有 B/C 这两个方法

用法
----
    python tools/verify_1042.py [new.apk] [old.apk]
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
    out = os.path.join(ROOT, 'app', 'build', 'outputs', 'apk', 'debug')
    best, best_code = None, -1
    if os.path.isdir(out):
        for n in os.listdir(out):
            m = re.match(r'DLsiteFloat-[\d.]+-code(\d+)-debug\.apk$', n)
            if m and int(m.group(1)) > best_code:
                best, best_code = os.path.join(out, n), int(m.group(1))
    return best


APK_NEW = sys.argv[1] if len(sys.argv) > 1 else _latest_apk()
APK_OLD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    UP, 'DLsiteFloat-2.4.1-code1041-debug.apk')

PKG = 'Lio/github/ariinyume/dlsitesoundfloat/'
PRE_SIG = PKG + 'hook/ZiptreePrefetch;'
PKEY_SIG = PKG + 'data/PlaylistKey;'
REPO_SIG = PKG + 'data/SubtitleRepository;'
CACHE_SIG = PKG + 'data/SubtitleCache;'

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
    scratch = os.path.join(ROOT, 'app', 'build', '_dextmp')
    os.makedirs(scratch, exist_ok=True)
    tag = os.path.basename(apk)
    out = []
    with zipfile.ZipFile(apk) as z:
        for n in [x for x in z.namelist() if re.match(r'classes\d*\.dex$', x)]:
            tmp = os.path.join(scratch, 'v1042_%s.%s' % (tag, n))
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


if not APK_NEW or not os.path.isfile(APK_NEW):
    print('缺少主验包（先 assembleDebug）: %s' % APK_NEW)
    sys.exit(2)
if not os.path.isfile(APK_OLD):
    print('缺少对照包: %s' % APK_OLD)
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
check('A1 aapt2 versionCode >= 1042', bool(code_actual) and int(code_actual) >= 1042,
      code_actual)
check('A2 aapt2 versionName 非空且形如 x.y.z', re.match(r'^\d+\.\d+\.\d+$', name_actual or '') is not None, name_actual)

blob_new = all_dex_blob(APK_NEW)
blob_old = all_dex_blob(APK_OLD)
BANNER = ('==== BUILD %s / code %s' % (name_actual, code_actual)).encode()
EV1042 = '【code 1042'.encode()
check('A3 新横幅串在包内', blob_new.count(BANNER) >= 1,
      '出现 %d 次' % blob_new.count(BANNER))
check('A4 履历段串【code 1042 在包内', EV1042 in blob_new)
check('A5 【code 1042 不在对照包', EV1042 not in blob_old,
      '对照出现 %d 次' % blob_old.count(EV1042))

# ── B~E 方法/常量进包 ───────────────────────────────────────────
print('=== B. 缓存时长闸门 ===')
dump_new = dex_dump(APK_NEW)
seg_pre = class_seg(dump_new, PRE_SIG)
check('B1 ZiptreePrefetch 类在包', seg_pre is not None)
if seg_pre:
    check("B2 cacheGateAllows 方法存在",
          "name          : 'cacheGateAllows'" in seg_pre)
    check('B3 cacheGateAllows 签名 = (J)Z',
          'cacheGateAllows:(J)Z' in seg_pre)

print('=== C. 印章时长锚定 ===')
seg_key = class_seg(dump_new, PKEY_SIG)
check('C1 PlaylistKey 类在包', seg_key is not None)
if seg_key:
    check("C2 stampForLoadedJson 方法存在",
          "name          : 'stampForLoadedJson'" in seg_key)
    check('C3 stampForLoadedJson 签名 = (JJJ)J',
          'stampForLoadedJson:(JJJ)J' in seg_key)
    check("C4 pickBestLabelMatch 方法存在（定向清理挑留哪条）",
          "name          : 'pickBestLabelMatch'" in seg_key)
    check('C5 pickBestLabelMatch 签名 = ([D[J)I',
          'pickBestLabelMatch:([D[J)I' in seg_key)

print('=== D. 时长贯通 ===')
seg_repo = class_seg(dump_new, REPO_SIG)
check('D1 SubtitleRepository 类在包', seg_repo is not None)
if seg_repo:
    check('D2 loadFromJson 四参重载在包',
          'loadFromJson:(Ljava/lang/String;Ljava/lang/String;ZJ)V' in seg_repo)
    check('D3 三参重载仍保留（云端路径零改动）',
          'loadFromJson:(Ljava/lang/String;Ljava/lang/String;Z)V' in seg_repo)
    check('D4 Repository 调 stampForLoadedJson',
          'PlaylistKey;.stampForLoadedJson:(JJJ)J' in seg_repo)
    check('D5 Repository 调 cacheGateAllows',
          'ZiptreePrefetch;.cacheGateAllows:(J)Z' in seg_repo)

print('=== E. 索引口径 ===')
seg_cache = class_seg(dump_new, CACHE_SIG)
check('E1 SubtitleCache 类在包', seg_cache is not None)
if seg_cache:
    m = re.search(r"name\s*:\s*'INDEX_SCHEMA'.{0,200}?value\s*:\s*(\d+)",
                  seg_cache, re.S)
    check('E2 INDEX_SCHEMA 常量层 = 5', bool(m) and m.group(1) == '5',
          ('实际 %s' % m.group(1)) if m else '未找到')

# ── F 反向锚 ────────────────────────────────────────────────────
print('=== F. 反向锚（对照包 code 1041）===')
dump_old = dex_dump(APK_OLD)
seg_pre_old = class_seg(dump_old, PRE_SIG)
seg_key_old = class_seg(dump_old, PKEY_SIG)
check('F1 对照包无 cacheGateAllows（证明本轮新增）',
      bool(seg_pre_old) and 'cacheGateAllows' not in seg_pre_old)
check('F2 对照包无 stampForLoadedJson（证明本轮新增）',
      bool(seg_key_old) and 'stampForLoadedJson' not in seg_key_old)
check('F3 对照包无 pickBestLabelMatch',
      bool(seg_key_old) and 'pickBestLabelMatch' not in seg_key_old)

print()
print('=' * 74)
if fails:
    print('FAIL %d/%d' % (len(fails), total))
    for f in fails:
        print('  - %s' % f)
    sys.exit(1)
print('PASS %d/%d' % (total, total))
sys.exit(0)
