import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from sdkpath import build_tools as _build_tools
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1028 / v2.3.5】设置页第二轮审查七项（6/7 合并）的 **产物层**验证。
（读的是**死的产物** ⇒ 判据可以钉死本轮字面量；见铁律 ⑬）

主验 = 本轮包 DLsiteFloat-2.3.5-code1028-debug.apk
对照 = 上一版交付包 DLsiteFloat-2.3.5-code1027-debug.apk

验什么
------
A 版本档位（aapt2 badging）
B 新增文案（新包有 / 旧包无）：未保存读数、撤销恢复默认、更多操作、Subtitles
C 资源层新增：7 个 id + 2 个 drawable
D 布局结构：bottom_bar 的类换成 FloatingToolbarLayout
E 删除项：restart_button 资源名已消失（上一版还在）
F 保持型（两版皆真，无区分力）
G 横幅自报 code 1028

⚠️ 不做伪造判据的项（如实跳过）：
   · 48dp 热区（语言胶囊容器 / 页签组 / TouchDelegate 的 dp(8)）—— 全是布局与整型常量，
     javac 会把 dp(8) 内联成立即数，`48` 在常量池里到处都是 ⇒ 产物层无法区分；
   · 16sp / 28sp 字号、colorPrimary→onSurfaceVariant 的色槽切换 —— 同上，都是编译期常量/资源 id；
   · 600 字重（Typeface.create 的第三个参数在 dex 里是 const/4，无法归属到某个调用点）。
   以上验收口径 = 源码层 verify_1028_src.py + 真机目视。

用法
----
    python verify_1028.py [apk_new] [apk_old]
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
    ROOT, 'app', 'build', 'outputs', 'apk', 'debug', 'DLsiteFloat-2.3.5-code1028-debug.apk')
APK_OLD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    UP, 'DLsiteFloat-2.3.5-code1027-debug.apk')

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


def xmltree(apk):
    return run([AAPT2, 'dump', 'xmltree', '--file',
                'res/layout/activity_settings.xml', apk])[1]


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
    check('A1 versionCode = 1028', "versionCode='1028'" in bn)
    check('A2 versionName = 2.3.5', "versionName='2.3.5'" in bn)
    check('A3 对照包仍是 1027（证明这是相邻两版）', "versionCode='1027'" in bo)
    check('A4 minSdk = 24（未动）', "minSdkVersion:'24'" in bn)
    check('A5 targetSdk = 36（未动）', "targetSdkVersion:'36'" in bn)
    check('A6 compileSdk = 36（未动）', "compileSdkVersion='36'" in bn)

    dn = dex_blob(APK_NEW)
    do = dex_blob(APK_OLD)

    print('\n── B 新增文案（新包有 / 旧包无）─────────────────────────────')

    def added(name, token):
        """新增类判据：主验必须命中，对照必须为零。"""
        global disc
        cn, co = count(dn, token), count(do, token)
        ok = cn > 0 and co == 0
        if ok:
            disc += 1
        check('%s  [new=%d old=%d]' % (name, cn, co), ok)

    added('B1 工具条未保存读数「有 %1$d 处未保存」', '有 %1$d 处未保存')
    added('B2 撤销恢复默认的回执「已撤销本次恢复默认」', '已撤销本次恢复默认')
    added('B3 溢出菜单读屏名「更多操作」', '更多操作')
    # ⚠️ 不要用 `Subtitles` 当判据：1027 包里 SUBTITLE_CACHE_HINT 的英文正文
    #    （"Subtitles of tracks you have played…"）已经含着它，实测 new=24 / old=23
    #    ⇒ **没有区分力**（本脚本第一版就踩了这个假锚）。
    nodisc.append('B4 页签英文名 Subtitles（旧包正文里已有该词，无区分力）')

    print('\n── C 资源层新增 ────────────────────────────────────────────')
    rn = resources(APK_NEW)
    ro = resources(APK_OLD)
    for name, token in [('C1 id/preview_mini', 'id/preview_mini'),
                        ('C2 id/preview_mini_backdrop', 'id/preview_mini_backdrop'),
                        ('C3 id/preview_mini_panel', 'id/preview_mini_panel'),
                        ('C4 id/preview_mini_lines', 'id/preview_mini_lines'),
                        ('C5 id/dirty_dot', 'id/dirty_dot'),
                        ('C6 id/dirty_label', 'id/dirty_label'),
                        ('C8 drawable/bg_dirty_dot', 'drawable/bg_dirty_dot'),
                        ('C9 drawable/ic_more_horiz', 'drawable/ic_more_horiz')]:
        ok = token in rn and token not in ro
        if ok:
            disc += 1
        check('%s  [new=%s old=%s]' % (name, token in rn, token in ro), ok)

    # material 1.14.0 自带 id/overflow_button（m3_button_group_overflow_button 等）
    # ⇒ 它不是本轮新增，产物层无区分力；如实标注，不做假锚。
    nodisc.append('C10 id/overflow_button（material 库自带，旧包也有）')

    print('\n── D 布局结构：底栏换成官方浮动工具条 ─────────────────────')
    xn = xmltree(APK_NEW)
    xo = xmltree(APK_OLD)
    # xmltree 的 E: 行给标签名；FloatingToolbarLayout 只在 1028 的布局里出现
    cn = len(re.findall(r'floatingtoolbar\.FloatingToolbarLayout', xn))
    co = len(re.findall(r'floatingtoolbar\.FloatingToolbarLayout', xo))
    ok = cn >= 1 and co == 0
    if ok:
        disc += 1
    check('D1 activity_settings.xml 里出现 FloatingToolbarLayout  [new=%d old=%d]' % (cn, co), ok)

    def group_height(apk, res):
        m = re.search(r'resource (0x[0-9a-f]+) id/appearance_tabs', res)
        if not m:
            return None
        x = xmltree(apk)
        i = x.find('=@' + m.group(1))
        if i < 0:
            return None
        seg = x[i:i + 500]
        h = re.search(r'layout_height\(0x010100f5\)=([0-9.]+)dp', seg)
        return float(h.group(1)) if h else None

    hn, ho = group_height(APK_NEW, rn), group_height(APK_OLD, ro)
    ok = hn == 48.0 and ho == 40.0
    if ok:
        disc += 1
    check('D2 外观页签组高 48dp（上一版 40dp）  [new=%s old=%s]' % (hn, ho), ok)

    print('\n── E 删除项（新包无 / 旧包有）─────────────────────────────')
    ok = ('id/restart_button' not in rn) and ('id/restart_button' in ro)
    if ok:
        disc += 1
    check('E1 id/restart_button 已从资源表消失（移进溢出菜单）', ok)

    print('\n── F 保持型（两版皆真，无区分力）───────────────────────────')
    for name, token in [('F1 外观分段条 buildAppearanceTabs', 'buildAppearanceTabs'),
                        ('F2 保存撤销 undoLastSave', 'undoLastSave'),
                        ('F3 预览折叠 applyPreviewCollapsed', 'applyPreviewCollapsed'),
                        ('F4 三条重置 onResetMain', 'onResetMain'),
                        ('F5 色板自量 ColorSwatchRow', 'ColorSwatchRow')]:
        cn, co = count(dn, token), count(do, token)
        nodisc.append(name.split()[0])
        check('%s  [new=%d old=%d]' % (name, cn, co), cn > 0 and co > 0)

    print('\n── G 横幅自报 ──────────────────────────────────────────────')
    ok = (count(dn, '==== BUILD 2.3.5 / code 1028') > 0
          and count(do, '==== BUILD 2.3.5 / code 1028') == 0)
    if ok:
        disc += 1
    check('G1 新包常开横幅自报 code 1028（旧包没有）', ok)

    print('\n── H 如实跳过（产物层无区分力）─────────────────────────────')
    for line in ['H1 48dp 热区（语言胶囊容器 / 页签组 / TouchDelegate 的 8dp 扩展）',
                 'H2 字号 28sp / 16sp 与 600 字重',
                 'H3 colorPrimary → colorOnSurfaceVariant / onSurface 的色槽切换']:
        nodisc.append(line.split()[0])
        print('  SKIP  %s：编译期常量或整型资源 id，dex 里无法归属到具体调用点'
              '（验收 = 源码层 + 真机目视）' % line)

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
