import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from sdkpath import build_tools as _build_tools
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1040 / v2.4.1（只升 code）】预取首次命中不再等满 15 秒的产物层验证。

用法
----
    python tools/verify_1040.py [new.apk] [old.apk]
退出码 0 = 全部通过
"""
import os
import re
import subprocess
import sys
import zipfile

BT = _build_tools('36.0.0')
AAPT2 = os.path.join(BT, 'aapt2.exe')
DEXDUMP = os.path.join(BT, 'dexdump.exe')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UP = os.path.dirname(ROOT)
APK_NEW = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    ROOT, 'app', 'build', 'outputs', 'apk', 'debug', 'DLsiteFloat-2.4.1-code1040-debug.apk')
APK_OLD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    UP, 'DLsiteFloat-2.4.1-code1039-debug.apk')

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
            tmp = os.path.join(scratch, 'v1040_%s.%s' % (tag, n))
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

badging = subprocess.run([AAPT2, 'dump', 'badging', APK_NEW],
                         capture_output=True, text=True, errors='replace',
                         encoding='utf-8').stdout
code_actual = (re.search(r"versionCode='(\d+)'", badging) or [''])[1]
name_actual = (re.search(r"versionName='([^']+)'", badging) or [''])[1]
check('A1 aapt2 versionCode = 1040', code_actual == '1040', code_actual)
check('A2 aapt2 versionName = 2.4.1（只升 code）', name_actual == '2.4.1', name_actual)

blob_new = all_dex_blob(APK_NEW)
blob_old = all_dex_blob(APK_OLD)
BANNER = '==== BUILD 2.4.1 / code 1040'.encode()
banner_old = '==== BUILD 2.4.1 / code 1039'.encode()
check('A3 新横幅串在包内', blob_new.count(BANNER) >= 1,
      '出现 %d 次' % blob_new.count(BANNER))
check('A4 旧横幅串在履历段保留', banner_old in blob_new,
      '履历段保留 %d 次' % blob_new.count(banner_old))
check('A5 履历段串【code 1040 在包内', '【code 1040'.encode() in blob_new)
check('A6 履历段串【code 1040 不在对照包', '【code 1040'.encode() not in blob_old,
      '对照出现 %d 次' % blob_old.count('【code 1040'.encode()))

dn = dex_dump(APK_NEW)
prefetch_prefix = 'Lio/github/ariinyume/dlsitesoundfloat/hook/ZiptreePrefetch'
seg_prefetch = class_seg(dn, prefetch_prefix + ';')
repo_sig = 'Lio/github/ariinyume/dlsitesoundfloat/data/SubtitleRepository;'
seg_repo = class_seg(dn, repo_sig)

check('B1 ZiptreePrefetch.hasCandidate 方法已编进包',
      bool(seg_prefetch) and "name          : 'hasCandidate'" in seg_prefetch)
check('B2 hasCandidate 签名为 (JLjava/lang/String;)Z',
      bool(seg_prefetch)
      and 'hasCandidate:(JLjava/lang/String;)Z' in seg_prefetch)
check('B3 SubtitleRepository 调用 hasCandidate',
      bool(seg_repo)
      and 'ZiptreePrefetch;.hasCandidate:(JLjava/lang/String;)Z' in seg_repo)
check('B4 预取命中日志串仍在包内（功能未删）',
      b'prefetch HIT on track change via ' in blob_new)
check('B5 code 1039 预取兜底日志串仍在包内',
      b'[code 1039] cloud gave no subtitle within grace' in blob_new)

print()
print('=' * 74)
if fails:
    print('FAIL %d/%d' % (len(fails), total))
    for f in fails:
        print('  - %s' % f)
    sys.exit(1)
print('PASS %d/%d' % (total, total))
sys.exit(0)
