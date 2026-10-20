#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1037 / v2.4.0】日常日志降噪 ＋ 验证链的 **产物层** 验证（主验 1037 / 对照 1036）。

口径
----
· 每条都报「新包 / 旧包」两侧读数，只在新包成立不算证据；
· 数的是 **dex 指令层的调用点**（`invoke-*` 行），不是字符串出现次数 ——
  `XposedCompat.log` 这个**名字**在方法引用与字符串里都会出现，只有调用行才是真调用；
· 验不到的**如实标注无区分力**，不硬凑。

分节
----
A 版本 / 横幅（aapt2 + dex 字符串）
B 日志出口迁移（dex 指令层计数）
C 反向锚（本轮 tools 改动不得漏进 APK）

用法
----
    python verify_1037.py [new.apk] [old.apk]
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
    ROOT, 'app', 'build', 'outputs', 'apk', 'debug', 'DLsiteFloat-2.4.0-code1037-debug.apk')
APK_OLD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    UP, 'DLsiteFloat-2.3.5-code1036-debug.apk')

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


def nodisc(name, why):
    print('  --   %s   （如实标注无区分力：%s）' % (name, why))


def all_dex_blob(apk):
    with zipfile.ZipFile(apk) as z:
        names = [n for n in z.namelist() if re.match(r'classes\d*\.dex$', n)]
        return b'\n'.join(z.read(n) for n in names)


def dex_dump(apk):
    """整包 dexdump -d 文本。临时 dex 落 app/build/_dextmp（**不删除**，见 code 1037）。"""
    scratch = os.path.join(ROOT, 'app', 'build', '_dextmp')
    os.makedirs(scratch, exist_ok=True)
    tag = os.path.basename(apk)
    out = []
    with zipfile.ZipFile(apk) as z:
        for n in [x for x in z.namelist() if re.match(r'classes\d*\.dex$', x)]:
            tmp = os.path.join(scratch, 'v1037_%s.%s' % (tag, n))
            with open(tmp, 'wb') as f:
                f.write(z.read(n))
            r = subprocess.run([DEXDUMP, '-d', tmp], capture_output=True, text=True,
                               errors='replace', encoding='utf-8')
            out.append(r.stdout)
    return '\n'.join(out)


def count_calls(dump, sig):
    """数 `invoke-*` 行里的目标方法（sig 形如 `LXposedCompat;.log:(`）。

    ⚠️ dexdump 的行格式是 `0006e4: 71 00 ... invoke-static {...}, L...;.log:(...)V` —
    操作码前面还有**字节码列**，所以不能写 `^[0-9a-f]{6}:\s+invoke`（实测全 0，本轮踩过）。
    """
    n = 0
    for line in dump.split('\n'):
        if 'invoke' in line and sig in line:
            n += 1
    return n


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
check('A1 aapt2 versionCode = 1037',
      "versionCode='1037'" in badging,
      (re.search(r"versionCode='(\d+)'", badging) or [''])[1])
check('A2 aapt2 versionName = 2.4.0',
      "versionName='2.4.0'" in badging,
      (re.search(r"versionName='([^']+)'", badging) or [''])[1])

blob_new = all_dex_blob(APK_NEW)
blob_old = all_dex_blob(APK_OLD)
BANNER = '==== BUILD 2.4.0 / code 1037'.encode()
banner_old = '==== BUILD 2.3.5 / code 1036'.encode()
check('A3 新横幅串在包内', blob_new.count(BANNER) >= 1, '出现 %d 次' % blob_new.count(BANNER))
check('A4 旧横幅串只在履历段残留（不再是常开那行）',
      banner_old in blob_new, '履历段保留 %d 次' % blob_new.count(banner_old))
check('A5 履历段串【code 1037 在包内',
      '【code 1037'.encode() in blob_new)
check('A6 履历段串在对照包里不存在（有区分力）',
      '【code 1037'.encode() not in blob_old,
      '对照出现 %d 次' % blob_old.count('【code 1037'.encode()))

# ── B 日志出口迁移 ─────────────────────────────────────────────────────
print()
print('=' * 74)
print('B 日志出口迁移（dex 指令层调用点计数）')
print('=' * 74)

dn = dex_dump(APK_NEW)
do = dex_dump(APK_OLD)
open_calls_new = count_calls(dn, 'XposedCompat;.log:')
open_calls_old = count_calls(do, 'XposedCompat;.log:')
dbg_calls_new = count_calls(dn, 'LogGate;.debug:')
dbg_calls_old = count_calls(do, 'LogGate;.debug:')
print('  常开出口 XposedCompat.log 调用点：新 %d / 旧 %d' % (open_calls_new, open_calls_old))
print('  调试出口 LogGate.debug 调用点：新 %d / 旧 %d' % (dbg_calls_new, dbg_calls_old))

check('B1 常开出口调用点减少 ≥ 6（本轮 8 处迁移）',
      open_calls_new <= open_calls_old - 6,
      '差 %d' % (open_calls_old - open_calls_new))
check('B2 调试出口调用点增加 ≥ 6',
      dbg_calls_new >= dbg_calls_old + 6,
      '差 %d' % (dbg_calls_new - dbg_calls_old))
check('B3 两个出口此消彼长（不是两边都涨）',
      open_calls_new < open_calls_old and dbg_calls_new > dbg_calls_old)

# logWarn 是本轮新增的私有方法：编译后名字保留（未被 R8 重命名）── 但 debug 包不混淆，
# 所以这条**不是**区分力锚，只作形态回归。
# ⚠️ 不能直接 grep 字节串 `logWarn` —— ConfigBus 里早就有同名方法（实测旧包也有）。
#   必须切到 SubtitleCache 类体里判「这个方法名是否出现在该类中」。
CLS_CACHE = 'Lio/github/ariinyume/dlsitesoundfloat/data/SubtitleCache;'


def class_seg(dump, sig):
    i = dump.find("Class descriptor  : '%s'" % sig)
    if i < 0:
        return None, None
    j = dump.find('Class descriptor  :', i + 10)
    return dump[i:j if j > 0 else len(dump)], True


seg_n, _ = class_seg(dn, CLS_CACHE)
seg_o, _ = class_seg(do, CLS_CACHE)
has_warn_n = bool(seg_n) and "name          : 'logWarn'" in seg_n
has_warn_o = bool(seg_o) and "name          : 'logWarn'" in seg_o
check('B4 SubtitleCache 新增 logWarn 方法（对照包该类里没有）',
      has_warn_n and not has_warn_o,
      '新 %s / 旧 %s' % (has_warn_n, has_warn_o))

# ── C 反向锚 ───────────────────────────────────────────────────────────
print()
print('=' * 74)
print('C 反向锚（tools 的改动不得漏进 APK）')
print('=' * 74)

for token in (b'DUMPCOMPLETE', b'_dextmp', b'dexdump_994.txt'):
    check('C %s 不在包内' % token.decode(), token not in blob_new)
nodisc('verify_998 的 latest 语义', '只在工具侧，不进包 —— 无产物层证据')

print()
print('=' * 74)
if fails:
    print('FAIL %d/%d' % (len(fails), total))
    for f in fails:
        print('  - %s' % f)
    sys.exit(1)
print('PASS %d/%d' % (total, total))
sys.exit(0)
