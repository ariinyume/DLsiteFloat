#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1038 / v2.4.1】三个 bug 修复的产物层验证。

验证项
----
A 版本 / 横幅
B 设置页激活状态：旧记忆位彻底移除
C ZiptreePrefetch：bonus 子目录 + 无字幕轨防撞
D 反向锚（修代码时残留的错字段/错变量不得进包）

用法
----
    python tools/verify_1038.py [new.apk] [old.apk]
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
    ROOT, 'app', 'build', 'outputs', 'apk', 'debug', 'DLsiteFloat-2.4.1-code1038-debug.apk')
APK_OLD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    UP, 'DLsiteFloat-2.4.0-code1037-debug.apk')

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
    """整包 dexdump -d 文本。临时 dex 落 app/build/_dextmp（不删除，沿用 1037 口径）。"""
    scratch = os.path.join(ROOT, 'app', 'build', '_dextmp')
    os.makedirs(scratch, exist_ok=True)
    tag = os.path.basename(apk)
    out = []
    with zipfile.ZipFile(apk) as z:
        for n in [x for x in z.namelist() if re.match(r'classes\d*\.dex$', x)]:
            tmp = os.path.join(scratch, 'v1038_%s.%s' % (tag, n))
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
check('A1 aapt2 versionCode = 1038', code_actual == '1038', code_actual)
check('A2 aapt2 versionName = 2.4.1', name_actual == '2.4.1', name_actual)

blob_new = all_dex_blob(APK_NEW)
blob_old = all_dex_blob(APK_OLD)
BANNER = '==== BUILD 2.4.1 / code 1038'.encode()
banner_old = '==== BUILD 2.4.0 / code 1037'.encode()
check('A3 新横幅串在包内', blob_new.count(BANNER) >= 1,
      '出现 %d 次' % blob_new.count(BANNER))
check('A4 旧横幅串在履历段保留', banner_old in blob_new,
      '履历段保留 %d 次' % blob_new.count(banner_old))
check('A5 履历段串【code 1038 在包内', '【code 1038'.encode() in blob_new)
check('A6 履历段串【code 1038 不在对照包', '【code 1038'.encode() not in blob_old,
      '对照出现 %d 次' % blob_old.count('【code 1038'.encode()))

# ── B 设置页激活状态：旧记忆位移除 ───────────────────────────────────────
print()
print('=' * 74)
print('B 设置页激活状态（旧记忆位彻底移除）')
print('=' * 74)

dn = dex_dump(APK_NEW)

for token in (b'PREF_HOST_SCOPE_SEEN', b'mHostScopeSeen', b'mHostSeenOnce'):
    check('B1 %s 不在新包 dex 中' % token.decode(),
          token not in blob_new,
          '出现 %d 次' % blob_new.count(token))

cls_settings = 'Lio/github/ariinyume/dlsitesoundfloat/ui/SettingsActivity;'
seg_settings = class_seg(dn, cls_settings)
if seg_settings:
    for mname in ("name          : 'readHostScopeSeen'",
                  "name          : 'markHostScopeSeen'"):
        check('B2 SettingsActivity 方法 %s 已删除' % mname.strip(),
              mname not in seg_settings)
else:
    check('B2 SettingsActivity 类段可解析', False, '未找到类段')

# ── C ZiptreePrefetch：bonus 子目录 + 无字幕轨防撞 ───────────────────────
print()
print('=' * 74)
print('C ZiptreePrefetch（bonus 子目录 + 无字幕轨防撞）')
print('=' * 74)

prefetch_prefix = 'Lio/github/ariinyume/dlsitesoundfloat/hook/ZiptreePrefetch'
seg_track = class_seg(dn, prefetch_prefix + '$Track;')
seg_pack = class_seg(dn, prefetch_prefix + '$Pack;')
seg_no_sub = class_seg(dn, prefetch_prefix + '$NoSubtitleTrack;')
seg_prefetch = class_seg(dn, prefetch_prefix + ';')

check('C1 Track 类新增 workKey 字段',
      bool(seg_track) and "name          : 'workKey'" in seg_track)
check('C2 Pack 类新增 noSubtitleTracks 字段',
      bool(seg_pack) and "name          : 'noSubtitleTracks'" in seg_pack)
check('C3 NoSubtitleTrack 内部类已编进包', bool(seg_no_sub))
check('C4 workKeyOfAudio 辅助方法已编进包',
      bool(seg_prefetch) and "name          : 'workKeyOfAudio'" in seg_prefetch)
check('C5 无字幕轨拒绝日志串在包内',
      b' (same work has unsubtitled track with same duration)' in blob_new)
check('C6 "唯一候选"兜底串（旧逻辑）已删除',
      b'unique candidate' not in blob_new.lower())

# ── D 反向锚 ───────────────────────────────────────────────────────────
print()
print('=' * 74)
print('D 反向锚（修码时残留的错字段/错变量不得进包）')
print('=' * 74)

check('D1 noSubtitleDurations 错字段不在包内',
      b'noSubtitleDurations' not in blob_new)
check('D2 SettingsActivity 旧常量 PREF_HOST_SCOPE_SEEN 不在包内',
      b'PREF_HOST_SCOPE_SEEN' not in blob_new)

print()
print('=' * 74)
if fails:
    print('FAIL %d/%d' % (len(fails), total))
    for f in fails:
        print('  - %s' % f)
    sys.exit(1)
print('PASS %d/%d' % (total, total))
sys.exit(0)
