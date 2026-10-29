import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from sdkpath import build_tools as _build_tools
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1022 / v2.3.4】P0 适配体检四项 + ziptree 取证的 **dex 字节码层**硬验证。
（读的是**死的产物** ⇒ 判据可以钉死本轮字面量；见铁律 ⑬）

主验 = 本轮包 DLsiteFloat-2.3.4-code1022-debug.apk
对照 = 上一版交付包 DLsiteFloat-2.3.3-code1021-debug.apk（**删除类改动的基准是上一版**）

验什么
------
A 版本（aapt2 badging）：versionCode=1022 / versionName=2.3.4；
  常开横幅串进包，且对照包里没有。
B 四个新类**以类型描述符形态**进包（`L.../HostInfo;` 等）—— 对照包必须一个都没有。
C 新字符串进包：三个新日志 TAG + 两条离线文案 + 取证关键字；对照包必须一个都没有。
D 新方法名进包：各新类/新出口的独有名字；对照包必须没有。
E 保持型（两版皆真，**无区分力**，只防「改 A 顺手弄坏 B」）：旧 TAG 与旧横幅仍在。

用法
----
    python verify_1022.py [apk_new] [apk_old]
退出码 0 = 全部通过
"""

import os
import re
import subprocess
import sys
import zipfile

BT = _build_tools('34.0.0')
AAPT2 = os.path.join(BT, 'aapt2.exe')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UP = os.path.dirname(ROOT)                    # 仓库的上一级（本机工作区）
APK_NEW = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    ROOT, 'app', 'build', 'outputs', 'apk', 'debug', 'DLsiteFloat-2.3.4-code1022-debug.apk')
APK_OLD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    UP, 'DLsiteFloat-2.3.3-code1021-debug.apk')

PKG = 'Lio/github/ariinyume/dlsitesoundfloat'

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


def dex_bytes(apk):
    """把所有 classes*.dex 的字节拼起来（字符串池与类型描述符都在其中，做存在性判定足够）。"""
    out = []
    with zipfile.ZipFile(apk) as z:
        for n in sorted(z.namelist()):
            if re.match(r'classes\d*\.dex$', n):
                out.append(z.read(n))
    return b'\x00'.join(out)


def has(dex, s):
    if isinstance(s, str):
        s = s.encode('utf-8')
    return s in dex


def badging(apk):
    try:
        r = subprocess.run([AAPT2, 'dump', 'badging', apk],
                           capture_output=True, timeout=120)
        return r.stdout.decode('utf-8', 'replace')
    except Exception as e:                     # noqa: BLE001
        return 'ERR:%s' % e


def main():
    for p in (APK_NEW, APK_OLD):
        if not os.path.exists(p):
            print('缺少 APK：%s' % p)
            return 2
    new, old = dex_bytes(APK_NEW), dex_bytes(APK_OLD)
    print('new=%s (%d B dex)\nold=%s (%d B dex)\n'
          % (os.path.basename(APK_NEW), len(new), os.path.basename(APK_OLD), len(old)))

    print('A 版本与横幅')
    bg = badging(APK_NEW)
    m_code = re.search(r"versionCode='(\d+)'", bg)
    m_name = re.search(r"versionName='([^']+)'", bg)
    check('aapt2 versionCode == 1022', bool(m_code) and m_code.group(1) == '1022',
          bg[:160])
    check('aapt2 versionName == 2.3.4', bool(m_name) and m_name.group(1) == '2.3.4',
          bg[:160])
    check('常开横幅串进包', has(new, '==== BUILD 2.3.4 / code 1022'))
    check('对照包没有本轮横幅（区分力）', not has(old, '==== BUILD 2.3.4 / code 1022'))

    print('B 新类（类型描述符）')
    new_classes = [
        ('util/HostInfo', PKG + '/util/HostInfo;'),
        ('hook/AdapterHealth', PKG + '/hook/AdapterHealth;'),
        ('util/NetState', PKG + '/util/NetState;'),
        ('util/DiagDump', PKG + '/util/DiagDump;'),
        ('hook/AdapterHealth$Item', PKG + '/hook/AdapterHealth$Item;'),
        ('hook/AdapterHealth$State', PKG + '/hook/AdapterHealth$State;'),
    ]
    for label, desc in new_classes:
        check('新包有 %s' % label, has(new, desc))
        check('对照包无 %s（区分力）' % label, not has(old, desc))

    print('C 新字符串')
    new_strs = [
        '[DLsiteSoundFloat:Host]',
        '[DLsiteSoundFloat:Health]',
        '[DLsiteSoundFloat:Diag]',
        '离线 · 无缓存',
        '离线 · 无字幕缓存（联网播放一次即可缓存）',
        'ziptree',
        'subtitle_cache/_diag',
    ]
    for s in new_strs:
        check('新包有串 %r' % s, has(new, s))
        check('对照包无串 %r（区分力）' % s, not has(old, s))

    print('D 新方法 / 新出口')
    new_names = ['offlineNoCache', 'offlineNoCacheHint', 'logTableOnce',
                 'buildHostVersionRow', 'logSkippedOnce', 'VERIFIED_VERSION']
    for s in new_names:
        # 方法名/字段名在 dex 的字符串池里（不一定是类型描述符），做存在性判定
        check('新包有名字 %r' % s, has(new, s))
        check('对照包无名字 %r（区分力）' % s, not has(old, s))

    print('E 保持型（两版皆真，无区分力）')
    keep = ['[DLsiteSoundFloat:Network]', '[DLsiteSoundFloat:Pos]', '[DLsiteSoundFloat:View]',
            '==== BUILD 2.3.3 / code 1021', 'status-map method = ']
    for s in keep:
        check('两版都有 %r' % s, has(new, s) and has(old, s))

    print()
    print('总计 %d 条，通过 %d 条，失败 %d 条' % (total, total - len(fails), len(fails)))
    if fails:
        print('失败项：')
        for x in fails:
            print('  - %s' % x)
        return 1
    print('verify_1022: ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
