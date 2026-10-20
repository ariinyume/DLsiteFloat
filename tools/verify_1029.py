#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1029 / v2.3.5】设置页第三轮五项的 **产物层**（APK）验证。

一律「主验 + 上一版对照」**单进程双表**（铁律 79）：
主验 = 本轮 code 1029 包，对照 = 上一轮 code 1028 包。
每条都报「有没有区分力」，验不到的**如实标注**（铁律 79）。

验什么
------
A1–A6   版本档位（code / versionName / 对照包 / 三档 sdk）
B1–B3   新增文案（点击切换语言 三语）
C1–C3   资源增删（bg_toolbar_icon 新增 / preview_mini 消失）
D1–D4   底栏节点属性（background / backgroundTint / padding / elevation）
E1–E2   溢出键背景指向 bg_toolbar_icon
F1–F2   预存上限（ZiptreePrefetch$2.removeEldestEntry 里的 const/16）
G1–G4   保持型（预览三层 / 页签组 48dp / 常开横幅 / versionName 两包一致）
H       如实标注：本轮哪几件在产物层**没有**区分力

用法
----
    python verify_1029.py [new.apk] [old.apk]
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
UP = os.path.dirname(ROOT)                    # F:/WorkBuddyCache/DLSiteSound_Plus
APK_NEW = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    ROOT, 'app', 'build', 'outputs', 'apk', 'debug', 'DLsiteFloat-2.3.5-code1029-debug.apk')
APK_OLD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    UP, 'DLsiteFloat-2.3.5-code1028-debug.apk')

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


def res_id(apk, kind_slash_name):
    """从资源表里取 <type>/<name> 的 0x 数值（取不到返回 None）。"""
    m = re.search(r'resource (0x[0-9a-f]{8}) %s\b' % re.escape(kind_slash_name), resources(apk))
    return m.group(1) if m else None


def node_block(apk, resid, span=16):
    """按 android:id 的数值找到节点属性块（含 id 行往后 span 行）。"""
    if resid is None:
        return ''
    x = xmltree(apk)
    i = x.find('android:id(0x010100d0)=@%s' % resid)
    if i < 0:
        return ''
    return x[i:i + span * 220]


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
    check('A1 versionCode = 1029', "versionCode='1029'" in bn)
    check('A2 versionName = 2.3.5', "versionName='2.3.5'" in bn)
    check('A3 对照包仍是 1028（证明这是相邻两版）', "versionCode='1028'" in bo)
    check('A4 minSdk = 24（未动）', "minSdkVersion:'24'" in bn)
    check('A5 targetSdk = 36（未动）', "targetSdkVersion:'36'" in bn)
    check('A6 compileSdk = 36（未动）', "compileSdkVersion='36'" in bn)

    dn = dex_blob(APK_NEW)
    do = dex_blob(APK_OLD)

    print('\n── B 新增文案（新包有 / 旧包无）─────────────────────────────')

    def added(name, token):
        global disc
        n = count(dn, token)
        o = count(do, token)
        ok = n > 0 and o == 0
        if ok:
            disc += 1
        check('%s  (new=%d / old=%d)' % (name, n, o), ok)
        return ok

    added('B1 「点击切换语言」', '点击切换语言')
    added('B2 「點擊切換語言」', '點擊切換語言')
    added('B3 「Tap to switch language」', 'Tap to switch language')

    print('\n── C 资源增删 ──────────────────────────────────────────────')
    bg_new = res_id(APK_NEW, 'drawable/bg_toolbar_icon')
    bg_old = res_id(APK_OLD, 'drawable/bg_toolbar_icon')
    check('C1 drawable/bg_toolbar_icon 已进包（新 %s / 旧 %s）'
          % (bg_new or '无', bg_old or '无'),
          bg_new is not None and bg_old is None)
    if bg_new is not None and bg_old is None:
        disc += 1
    check('C2 preview_mini 的四个 id 已全部消失（折叠不再有第二个视图）',
          all(r is None for r in (res_id(APK_NEW, 'id/preview_mini'),
                                  res_id(APK_NEW, 'id/preview_mini_lines'),
                                  res_id(APK_NEW, 'id/preview_mini_backdrop'),
                                  res_id(APK_NEW, 'id/preview_mini_panel'))))
    old_has_mini = res_id(APK_OLD, 'id/preview_mini') is not None
    check('C3 对照包确实有 id/preview_mini（证明 C2 有区分力）', old_has_mini)
    if old_has_mini:
        disc += 1

    print('\n── D 底栏节点属性（新包有 / 旧包无）─────────────────────────')
    bb_new = node_block(APK_NEW, res_id(APK_NEW, 'id/bottom_bar'))
    bb_old = node_block(APK_OLD, res_id(APK_OLD, 'id/bottom_bar'))

    def attr_added(name, token):
        global disc
        ok = token in bb_new and token not in bb_old
        if ok:
            disc += 1
        check('%s  (new=%s / old=%s)' % (name, '有' if token in bb_new else '无',
                                         '有' if token in bb_old else '无'), ok)

    attr_added('D1 background = transparent（0x0106000d 是系统 transparent）',
               'android:background(0x010100d4)=@0x0106000d')
    attr_added('D2 backgroundTint = transparent（样式里的色调会重新上色）',
               'backgroundTint(0x7f030051)=@0x0106000d')
    attr_added('D3 padding = 0dp（容器不在了，不留容器内缩）',
               'android:padding(0x010100d5)=0.000000dp')
    attr_added('D4 elevation = 0dp（没有背景就没有阴影可画）',
               'elevation(0x7f0301c2)=0.000000dp')

    print('\n── E 溢出键自有圆底 ────────────────────────────────────────')
    ov_new = node_block(APK_NEW, res_id(APK_NEW, 'id/overflow_button'), span=8)
    ov_old = node_block(APK_OLD, res_id(APK_OLD, 'id/overflow_button'), span=8)
    check('E1 溢出键 background 指向 bg_toolbar_icon（旧包是 attr 选择器）',
          bg_new is not None and ('android:background(0x010100d4)=@%s' % bg_new) in ov_new)
    check('E2 对照包溢出键没有这枚 drawable（判据有区分力）',
          bg_new is None or ('@%s' % bg_new) not in ov_old)
    if bg_new is not None and ('@%s' % bg_new) not in ov_old:
        disc += 1

    print('\n── F 预存字幕上限 ──────────────────────────────────────────')

    def evict_const(apk):
        """取 ZiptreePrefetch$2.removeEldestEntry 里紧跟在 size() 后面的常量。"""
        z = zipfile.ZipFile(apk)
        for nm in [n for n in z.namelist() if re.match(r'classes\d*\.dex$', n)]:
            # code 1037：临时 dex 落 app/build/_dextmp/ 覆盖写、**不删除**
            # （删 9 次/脚本会撞环境批量删除保护 ⇒ 进程被掐断 ⇒ 误报 ENVBLOCK）。
            scratch = os.path.join(ROOT, 'app', 'build', '_dextmp')
            os.makedirs(scratch, exist_ok=True)
            tmp = os.path.join(scratch, '_v1029_%s' % nm)
            with open(tmp, 'wb') as f:
                f.write(z.read(nm))
            rc, out = run([DEXDUMP, '-d', tmp])
            i = out.find('ZiptreePrefetch$2.removeEldestEntry')
            if i > 0:
                seg = out[i:i + 1400]
                m = re.search(r'const/16 v\d+, #int (\d+)', seg)
                return int(m.group(1)) if m else None
        return None

    cn = evict_const(APK_NEW)
    co = evict_const(APK_OLD)
    check('F1 淘汰阈值常量 = 16  (new=%s / old=%s)' % (cn, co), cn == 16)
    check('F2 对照包仍是 8（证明 F1 有区分力）', co == 8)
    if cn == 16 and co == 8:
        disc += 1

    print('\n── G 保持型（本轮不该被顺手改坏）──────────────────────────')
    check('G1 完整预览三层 id 仍在',
          all(res_id(APK_NEW, 'id/preview_%s' % k) is not None
              for k in ('backdrop', 'panel', 'lines')))
    tabs = node_block(APK_NEW, res_id(APK_NEW, 'id/appearance_tabs'), span=8)
    check('G2 外观页签组仍是 48dp',
          'layout_height(0x010100f5)=48.000000dp' in tabs)
    check('G3 常开横幅自报 1029',
          count(dn, '==== BUILD 2.3.5 / code 1029') > 0)
    check('G4 两包 versionName 一致（只升 code）',
          "versionName='2.3.5'" in bn and "versionName='2.3.5'" in bo)

    print('\n── H 如实标注（本轮这几件在产物层**没有**区分力）─────────────')
    for s in ('连通组内侧 8dp / 3dp 间距：运行时 ShapeAppearanceModel 逐角构造，'
              '无对应资源，只能源码层判（verify_1029_src B1–B8）',
              '语言循环与「删弹窗」：属代码结构；LANG_DIALOG_TITLE 字符串仍随 Strings 枚举进包，'
              '不能拿它的存在与否下结论',
              '预览收起方向（向上抬 / 向下落）：纯运行时行为，产物层不可见'):
        nodisc.append(s)
        print('  N/A   ' + s)

    print('\n' + '=' * 60)
    print('有区分力的锚：%d 条' % disc)
    if fails:
        print('FAIL %d/%d' % (len(fails), total))
        for f in fails:
            print('  - ' + f)
        return 1
    print('PASS %d/%d' % (total, total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
