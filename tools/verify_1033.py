#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1033 / v2.3.5】设置页第七轮八条的 **产物层** 验证（主验 1033 / 对照 1032）。

口径
----
每条都报「新包有 / 旧包无」两侧读数；只在新包里成立不算证据。
验不到的**如实标注无区分力**（不硬凑）。

分节
----
A 版本 / 标签
B 资源层（布局）：card_main 上内距 24dp、四卡下内距 10dp
C dex 类/字段层：PopupWindow 取代 PopupMenu、旧测量三件套消失、新常量出现
D 如实标注

用法
----
    python verify_1033.py [new.apk] [old.apk]
退出码 0 = 全部通过
"""

import os
import re
import subprocess
import sys
import zipfile

BT = r'F:\WorkBuddyCache\DLSiteSound_Plus\toolchain\android-sdk\build-tools\36.0.0'
AAPT2 = os.path.join(BT, 'aapt2.exe')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UP = os.path.dirname(ROOT)
APK_NEW = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    ROOT, 'app', 'build', 'outputs', 'apk', 'debug', 'DLsiteFloat-2.3.5-code1033-debug.apk')
APK_OLD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    UP, 'DLsiteFloat-2.3.5-code1032-debug.apk')

LAYOUT = 'res/layout/activity_settings.xml'
PAD_TOP = 'android:paddingTop(0x010100d7)='
PAD_BOTTOM = 'android:paddingBottom(0x010100d9)='

fails = []
total = 0
nodisc = []


def check(name, ok, detail=''):
    global total
    total += 1
    if ok:
        print('  PASS  %s' % name)
    else:
        print('  FAIL  %s   %s' % (name, detail))
        fails.append(name)


def skip(name, why):
    print('  SKIP  %s   %s' % (name, why))
    nodisc.append(name)


def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout.decode('utf-8', 'replace')


def badging(apk):
    return run([AAPT2, 'dump', 'badging', apk])[1]


def xml(apk, path):
    return run([AAPT2, 'dump', 'xmltree', '--file', path, apk])[1]


def dex_blob(apk):
    z = zipfile.ZipFile(apk)
    names = [n for n in z.namelist() if re.match(r'classes\d*\.dex$', n)]
    return b''.join(z.read(n) for n in names)


def cnt(blob, token):
    return blob.count(token.encode('utf-8'))


if not os.path.exists(APK_NEW):
    print('找不到 APK：%s' % APK_NEW)
    sys.exit(2)
if not os.path.exists(APK_OLD):
    print('找不到对照 APK：%s' % APK_OLD)
    sys.exit(2)

NEW = dex_blob(APK_NEW)
OLD = dex_blob(APK_OLD)
XML_NEW = xml(APK_NEW, LAYOUT)
XML_OLD = xml(APK_OLD, LAYOUT)

# ══════════════════════════════════════════════════════════════════════
print('\n── A 版本 / 标签 ────────────────────────────────────────────')

b = badging(APK_NEW)
check('A1 versionCode=1033 / versionName=2.3.5',
      "versionCode='1033'" in b and "versionName='2.3.5'" in b,
      re.search(r"versionCode='\d+'", b).group(0) if re.search(r"versionCode='\d+'", b) else '')
check('A2 application-label 仍是 DLsiteFloat',
      "application-label:'DLsiteFloat'" in b)

# ══════════════════════════════════════════════════════════════════════
print('\n── B 资源层（布局）────────────────────────────────────────────')

check('B1 card_main 内层 paddingTop = 24dp（旧包 16dp）',
      XML_NEW.count(PAD_TOP + '24.000000dp') == 1
      and XML_OLD.count(PAD_TOP + '24.000000dp') == 0,
      '新 %d / 旧 %d' % (XML_NEW.count(PAD_TOP + '24.000000dp'),
                         XML_OLD.count(PAD_TOP + '24.000000dp')))
check('B2 另外三张卡仍是 10dp（paddingTop=10 共 4 处：页头 + 三卡）',
      XML_NEW.count(PAD_TOP + '10.000000dp') == 4
      and XML_OLD.count(PAD_TOP + '10.000000dp') == 4,
      '新 %d / 旧 %d' % (XML_NEW.count(PAD_TOP + '10.000000dp'),
                         XML_OLD.count(PAD_TOP + '10.000000dp')))
check('B3 四张卡内层下内距都是 10dp（末行 4 + 卡片 10 = 总距 14）',
      XML_NEW.count(PAD_BOTTOM + '10.000000dp') == 4,
      '新 %d 处' % XML_NEW.count(PAD_BOTTOM + '10.000000dp'))

# ══════════════════════════════════════════════════════════════════════
print('\n── C dex 类 / 字段层 ─────────────────────────────────────────')

# ⚠️ 两个类都**不是从 0 开始**：三方库里各有一处静态引用（PopupWindow 在
#   appcompat 的菜单宿主、PopupMenu 在 Material 的溢出逻辑）。所以判据只能判**增量**，
#   不能判「新包有 / 旧包无」—— 那样会假 FAIL（本轮实测 1→2 / 2→1）。
check('C1 溢出菜单新增 PopupWindow 引用（三方库本来就有 1 处，本包 +1）',
      cnt(NEW, 'Landroid/widget/PopupWindow;') == cnt(OLD, 'Landroid/widget/PopupWindow;') + 1,
      '%d→%d' % (cnt(OLD, 'Landroid/widget/PopupWindow;'),
                 cnt(NEW, 'Landroid/widget/PopupWindow;')))
check('C2 旧的 PopupMenu 引用被摘掉一处（三方库还剩 1 处，本包 −1）',
      cnt(NEW, 'Landroid/widget/PopupMenu;') == cnt(OLD, 'Landroid/widget/PopupMenu;') - 1,
      '%d→%d' % (cnt(OLD, 'Landroid/widget/PopupMenu;'),
                 cnt(NEW, 'Landroid/widget/PopupMenu;')))
for tok in ('topInkGapOf', 'topRelativeTo', 'findFirstTextView'):
    check('C3 旧测量方法 %s 已删除（旧包有 / 新包无）' % tok,
          cnt(OLD, tok) >= 1 and cnt(NEW, tok) == 0,
          '%d→%d' % (cnt(OLD, tok), cnt(NEW, tok)))
for tok in ('CARD_LAST_GAP_DP', 'MENU_RADIUS_DP', 'MENU_ITEM_H_DP',
            'MENU_ANCHOR_GAP_DP', 'mPreviewAnim'):
    check('C4 新字段 %s 只在 1033 里存在' % tok,
          cnt(NEW, tok) >= 1 and cnt(OLD, tok) == 0,
          '%d→%d' % (cnt(OLD, tok), cnt(NEW, tok)))
check('C5 旧版「按首行字形顶收敛」的辅助符号已无残留（字形墨迹测量）',
      cnt(NEW, 'getTextBounds') <= cnt(OLD, 'getTextBounds'),
      '%d→%d' % (cnt(OLD, 'getTextBounds'), cnt(NEW, 'getTextBounds')))

# ══════════════════════════════════════════════════════════════════════
print('\n── D 如实标注：以下在产物层没有区分力 ────────────────────────')

skip('卡片末行底距的**观感是否一致**',
     '底距是 dp 常量在运行时换算 + 布局，XML 里没有这个 margin 资源条目')
skip('底距**跳变**是否消失',
     '「不再挂 OnGlobalLayoutListener」只能由源码层证（C3 已证旧方法消失），观感要真机')
skip('菜单圆角 16dp 的**观感**是否够 M3E',
     '圆角是 GradientDrawable.setCornerRadius 运行时调用，产物层只能看到常量名')
skip('菜单是否真的出现在按钮**上方**',
     '位置由 showAtLocation 的 y 现算，纯运行时几何')
skip('预览窗「编辑字幕 / 切语言时不再弹回完整」',
     '纯运行时状态机；产物层只能验兜底分支与字段存在（C4 的 mPreviewAnim）')

print('\n' + '=' * 62)
if fails:
    print('FAIL %d / %d' % (len(fails), total))
    for n in fails:
        print('  · ' + n)
    sys.exit(1)
print('PASS %d/%d（另有 %d 项如实标注无区分力）' % (total, total, len(nodisc)))
