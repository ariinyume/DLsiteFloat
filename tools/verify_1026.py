import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from sdkpath import build_tools as _build_tools
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1026 / v2.3.5】删「跟随宿主字幕样式」+ 三张色板去掉红与蓝 的 **产物层**验证。
（读的是**死的产物** ⇒ 判据可以钉死本轮字面量；见铁律 ⑬）

主验 = 本轮包 DLsiteFloat-2.3.5-code1026-debug.apk
对照 = 上一版交付包 DLsiteFloat-2.3.5-code1025-debug.apk
       —— **删除类改动的对照基准是上一版**（铁律 70/81）

验什么
------
A 版本档位（aapt2 badging）：versionCode=1026 / versionName=2.3.5 / minSdk=24 /
  targetSdk=36 / compileSdk=36。
B 删除项（**新包无 / 旧包有**，逐条判区分力）：宿主样式采样类、配置键、日志标签、
  悬浮窗的宿主样式版本号字段。
C 资源层：drawable/ic_ui_sync 只在上一般存在；色板的 6 项**不进产物层的判据**
  （R.color 引用被 javac 内联成整型 id，dex 里看不出「用了几种颜色」）—— 如实跳过。
D 保持型（两版皆真，**无区分力**）：本轮不该被误伤的功能锚点。
E 横幅自报（新包有 code 1026 字样、旧包没有）。

用法
----
    python verify_1026.py [apk_new] [apk_old]
退出码 0 = 全部通过
"""

import os
import re
import subprocess
import sys
import zipfile

BT = _build_tools('36.0.0')
AAPT2 = os.path.join(BT, 'aapt2.exe')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UP = os.path.dirname(ROOT)                    # 仓库的上一级（本机工作区）
APK_NEW = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    ROOT, 'app', 'build', 'outputs', 'apk', 'debug', 'DLsiteFloat-2.3.5-code1026-debug.apk')
APK_OLD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    UP, 'DLsiteFloat-2.3.5-code1025-debug.apk')

fails = []
total = 0
disc = 0
nodisc = []


def check(name, ok, detail=''):
    global total
    total += 1
    if ok:
        print('  PASS  %s' % name)
    else:
        print('  FAIL  %s   %s' % (name, detail))
        fails.append(name)


def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout.decode('utf-8', 'replace')


def badging(apk):
    return run([AAPT2, 'dump', 'badging', apk])[1]


def resources(apk):
    return run([AAPT2, 'dump', 'resources', apk])[1]


def dex_blob(apk):
    z = zipfile.ZipFile(apk)
    names = [n for n in z.namelist() if re.match(r'classes\d*\.dex$', n)]
    return b''.join(z.read(n) for n in names)


def count(blob, token):
    return blob.count(token.encode('utf-8'))


def main():
    global disc
    for p in (APK_NEW, APK_OLD):
        if not os.path.isfile(p):
            print('找不到 APK：%s' % p)
            return 2

    print('主验：%s' % os.path.basename(APK_NEW))
    print('对照：%s\n' % os.path.basename(APK_OLD))

    bn = badging(APK_NEW)
    bo = badging(APK_OLD)

    print('── A 版本档位 ──────────────────────────────────────────────')
    check('A1 versionCode = 1026', "versionCode='1026'" in bn)
    check('A2 versionName = 2.3.5', "versionName='2.3.5'" in bn)
    check('A3 对照包仍是 1025（证明这是相邻两版）', "versionCode='1025'" in bo)
    check('A4 minSdk = 24（未动）', "minSdkVersion:'24'" in bn)
    check('A5 targetSdk = 36（未动）', "targetSdkVersion:'36'" in bn)
    check('A6 compileSdk = 36（未动）', "compileSdkVersion='36'" in bn)

    print('\n── B 删除项（新包无 / 旧包有）─────────────────────────────')
    dn = dex_blob(APK_NEW)
    do = dex_blob(APK_OLD)

    def gone(name, token):
        """删除类判据：对照（上一版）必须命中，主验必须为零。"""
        global disc
        cn, co = count(dn, token), count(do, token)
        ok = cn == 0 and co > 0
        if ok:
            disc += 1
        check('%s  [new=%d old=%d]' % (name, cn, co), ok)

    gone('B1 宿主样式采样类 HostStyleProbe', 'HostStyleProbe')
    gone('B2 配置键 follow_host_style', 'follow_host_style')
    gone('B3 采样日志标签 :HostStyle', ':HostStyle')
    gone('B4 悬浮窗宿主样式版本号字段 styleHostRev', 'styleHostRev')
    # ⚠️ 别用 `offer` —— 那是常用词（新旧各 32/33 次），**没有区分力**（1026 实测）。
    gone('B5 采样入口 textSizeSp（只属于探针）', 'textSizeSp')
    gone('B6 采样入口 colorUsable（只属于探针）', 'colorUsable')

    print('\n── C 资源层 ────────────────────────────────────────────────')
    rn = resources(APK_NEW)
    ro = resources(APK_OLD)
    ok = ('drawable/ic_ui_sync' not in rn) and ('drawable/ic_ui_sync' in ro)
    if ok:
        disc += 1
    check('C1 ic_ui_sync 已从包里去掉（上一版还在）', ok)
    nodisc.append('C2 色板 6 项（R.color 内联成整型 id，产物层无区分力）')
    print('  SKIP  C2 色板项数：R.color.swatch_* 被 javac 内联成整型资源 id，dex 里看不出'
          '「用了几种颜色」 —— 不做伪造判据（验收口径 = 源码层 J13–J18 + 真机目视）')
    # 红/蓝两个色值资源本身**没有删**（自定义取色仍可用），故只守「还在」
    check('C3 swatch_red / swatch_blue 色值资源仍在（自定义取色要用，未删）',
          'swatch_red' in rn and 'swatch_blue' in rn)

    print('\n── D 保持型（两版皆真，无区分力）───────────────────────────')
    for name, token in [('D1 纯自算行 selfComputedLines', 'selfComputedLines'),
                        ('D2 设置页分段条 buildAppearanceTabs', 'buildAppearanceTabs'),
                        ('D3 行头图元 makeRowHead', 'makeRowHead'),
                        ('D4 撤销保存 undoLastSave', 'undoLastSave'),
                        ('D5 合并后的外观重置文案', '恢复字幕外观默认设置')]:
        cn, co = count(dn, token), count(do, token)
        nodisc.append(name.split()[0])
        check('%s  [new=%d old=%d]' % (name, cn, co), cn > 0 and co > 0)

    print('\n── E 横幅自报 ──────────────────────────────────────────────')
    ok = (count(dn, '==== BUILD 2.3.5 / code 1026') > 0
          and count(do, '==== BUILD 2.3.5 / code 1026') == 0)
    if ok:
        disc += 1
    check('E1 新包横幅自报 code 1026（旧包没有）', ok)

    print('\n──────────────────────────────────────────────────────────')
    print('有区分力锚：%d 条；无区分力（如实标注）：%d 条' % (disc, len(nodisc)))
    if fails:
        print('FAIL %d / %d' % (len(fails), total))
        for f in fails:
            print('  · %s' % f)
        return 1
    print('PASS %d / %d' % (total, total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
