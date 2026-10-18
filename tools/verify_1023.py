#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1023 / v2.3.5】真机回归三修 + P0-4 落地的 **dex 字节码层**硬验证。
（读的是**死的产物** ⇒ 判据可以钉死本轮字面量；见铁律 ⑬）

主验 = 本轮包 DLsiteFloat-2.3.5-code1023-debug.apk
对照 = 上一版交付包 DLsiteFloat-2.3.4-code1022-debug.apk（**删除类改动的基准是上一版**）

验什么
------
A 版本（aapt2 badging）：versionCode=1023 / versionName=2.3.5；常开横幅串进包且对照包没有。
B 新类**以类型描述符形态**进包（`L.../ZiptreePrefetch;` 等）—— 对照包必须一个都没有。
C 新字符串进包：新 TAG、预取目录、自检项名、字幕路径片段；对照包必须一个都没有。
D 新方法名进包：预取器与两个新出口的独有名字；对照包必须没有。
E 删除类改动：旧卡片行的构造方法在新包**消失**、在对照包存在。
F 保持型（两版皆真，**无区分力**，只防「改 A 顺手弄坏 B」）：旧 TAG 与旧横幅仍在。

用法
----
    python verify_1023.py [apk_new] [apk_old]
退出码 0 = 全部通过
"""

import os
import re
import subprocess
import sys
import zipfile

BT = r'F:\WorkBuddyCache\DLSiteSound_Plus\toolchain\android-sdk\build-tools\34.0.0'
AAPT2 = os.path.join(BT, 'aapt2.exe')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UP = os.path.dirname(ROOT)                    # F:/WorkBuddyCache/DLSiteSound_Plus
APK_NEW = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    ROOT, 'app', 'build', 'outputs', 'apk', 'debug', 'DLsiteFloat-2.3.5-code1023-debug.apk')
APK_OLD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    UP, 'DLsiteFloat-2.3.4-code1022-debug.apk')

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


def manifest_xml(apk):
    """aapt2 dump xmltree —— 用来验 <queries>（badging 不打印它）。"""
    try:
        r = subprocess.run([AAPT2, 'dump', 'xmltree', apk, '--file', 'AndroidManifest.xml'],
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
    check('aapt2 versionCode == 1023', bool(m_code) and m_code.group(1) == '1023', bg[:160])
    check('aapt2 versionName == 2.3.5', bool(m_name) and m_name.group(1) == '2.3.5', bg[:160])
    check('常开横幅串进包', has(new, '==== BUILD 2.3.5 / code 1023'))
    check('对照包没有本轮横幅（区分力）', not has(old, '==== BUILD 2.3.5 / code 1023'))

    print('A2 清单：包可见性声明真的进了安装包')
    mx = manifest_xml(APK_NEW)
    check('aapt2 能读出清单', not mx.startswith('ERR:'))
    # <queries> 在 xmltree 里表现为 E: queries 节点；包名以 A: http://...android:name 的字符串出现
    check('清单含 queries 节点', re.search(r'E:\s*queries', mx) is not None)
    check('清单含宿主包名', 'jp.co.eisys.dlsitesound' in mx)
    check('清单没有 QUERY_ALL_PACKAGES 权限',
          'QUERY_ALL_PACKAGES' not in mx)

    print('B 新类（类型描述符）')
    new_classes = [
        ('hook/ZiptreePrefetch', PKG + '/hook/ZiptreePrefetch;'),
        ('hook/ZiptreePrefetch$Track', PKG + '/hook/ZiptreePrefetch$Track;'),
        ('hook/ZiptreePrefetch$Pack', PKG + '/hook/ZiptreePrefetch$Pack;'),
        ('hook/ZiptreePrefetch$Hit', PKG + '/hook/ZiptreePrefetch$Hit;'),
        ('util/HostInfo$Info', PKG + '/util/HostInfo$Info;'),
    ]
    for label, desc in new_classes:
        check('新包有 %s' % label, has(new, desc))
        check('对照包无 %s（区分力）' % label, not has(old, desc))

    print('C 新字符串')
    new_strs = [
        '[DLsiteSoundFloat:Prefetch]',
        'subtitle_cache/_prefetch',
        'skip (ziptree has no signature query)',
        'dl fail http=',
        'ziptree has no vtt entry',
    ]
    for s in new_strs:
        check('新包有串 %r' % s, has(new, s))
        check('对照包无串 %r（区分力）' % s, not has(old, s))

    print('C2 新名字（枚举项 / JSON 键 / 路径片段）')
    # ⚠️ PREFETCH 在本包**无区分力**：旧包里 `TRACE_NESTED_PREFETCH_TAG` /
    #    `TRACE_PREFETCH_TAG` 是 RecyclerView 的常量，子串必然命中（实测 2 次）。
    #    ⇒ 只做存在性检查；真正的区分力来自 `AdapterHealth$Item;` 描述符与下面的新方法名。
    check('新包有 %r（无区分力：旧包 RecyclerView 常量含同名子串）' % 'PREFETCH',
          has(new, 'PREFETCH'))
    # `optimized/` 有区分力：旧包从不拼这个路径
    check('新包有 %r' % 'optimized/', has(new, 'optimized/'))
    check('对照包无 %r（区分力）' % 'optimized/', not has(old, 'optimized/'))
    for s in ('audio', 'duration'):
        check('新包仍有 %r（保持型）' % s, has(new, s))

    print('D 新方法 / 新出口')
    # ⚠️ 刻意不判 `writeIndex` / `readIndex`：旧包里 Parcel 的
    #    `writeIndex/readIndex` 是同名方法（子串必然命中，零区分力）⇒ 换成日志串。
    new_names = ['tryResumeFromPrefetch', 'readInCurrentProcess', 'hostLineText',
                 'parseTracks', 'ensureIndexLoaded', 'isZiptree']
    for s in new_names:
        check('新包有名字 %r' % s, has(new, s))
        check('对照包无名字 %r（区分力）' % s, not has(old, s))

    # ⚠️ `index loaded: ` 旧包亦有（依赖库同名日志）⇒ 不入判据；` index loaded: ` 带前导空格
    new_logs = [' index loaded: ', 'HIT dur=', 'MISS dur=', 'skip (offline) url=']
    for s in new_logs:
        check('新包有日志串 %r' % s, has(new, s))
        check('对照包无日志串 %r（区分力）' % s, not has(old, s))

    print('E 删除类改动（旧卡片行必须真的消失）')
    check('新包没有 buildHostVersionRow（已删）', not has(new, 'buildHostVersionRow'))
    check('对照包有 buildHostVersionRow（反向对照成立）', has(old, 'buildHostVersionRow'))

    print('F 保持型（两版皆真，无区分力）')
    keep = ['[DLsiteSoundFloat:Network]', '[DLsiteSoundFloat:Pos]', '[DLsiteSoundFloat:View]',
            '[DLsiteSoundFloat:Health]', '[DLsiteSoundFloat:Host]',
            '==== BUILD 2.3.4 / code 1022',
            '离线 · 无缓存']
    for s in keep:
        check('两版都有 %r' % s, has(new, s) and has(old, s))

    print()
    print('总计 %d 条，通过 %d 条，失败 %d 条' % (total, total - len(fails), len(fails)))
    if fails:
        print('失败项：')
        for x in fails:
            print('  - %s' % x)
        return 1
    print('verify_1023: ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
