#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1031 / v2.3.5】设置页第五轮十项的 **产物层**（APK）验证。

一律「主验 + 上一版对照」**单进程双表**（铁律 79）：
主验 = 本轮 code 1031 包，对照 = 上一轮 code 1030 包。
每条都报「有没有区分力」，验不到的**如实标注**（铁律 79）。

验什么
------
A1–A4   版本档位（code / versionName / application-label / 桌面 alias 的 label 引用）
B1–B4   清单结构（activity-alias 存在 / 名字 / targetActivity / LAUNCHER 只在 alias 下）
C1–C5   文案（页头副标题三语、桌面名、简介中文 + values-en 英文）
D1–D5   本轮新增的字符串（图标开关 / UI prefs 键 / alias 全名 / 缓存短标签 / 横幅）
E1–E4   缓存按钮缩写带来的**计数变化**（Clear cached subtitles 2 → 1）
F1–F5   资源层内距（四卡 10dp / 底栏 28dp / 不裁剪 / 滚动区 12dp）
G1–G3   方法层（applyLauncherIconState / repinExperimentalLast / buildLauncherIconRow）
H       如实标注：哪几件在产物层**没有**区分力

⚠️ 判「节点自己有没有某个属性」必须只取本节点那一层（node() 按缩进切），
   不能用定长字符窗口（铁律 60）。
⚠️ xmltree 的 dp 值是 `10.000000dp` 这种六位小数形态，判据要用数值解析、不要拼字符串。

用法
----
    python verify_1031.py [new.apk] [old.apk]
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
    ROOT, 'app', 'build', 'outputs', 'apk', 'debug', 'DLsiteFloat-2.3.5-code1031-debug.apk')
APK_OLD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    UP, 'DLsiteFloat-2.3.5-code1030-debug.apk')

LAYOUT = 'res/layout/activity_settings.xml'
MANIFEST = 'AndroidManifest.xml'

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


def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout.decode('utf-8', 'replace')


def badging(apk):
    return run([AAPT2, 'dump', 'badging', apk])[1]


def resources(apk):
    return run([AAPT2, 'dump', 'resources', apk])[1]


def xml(apk, path):
    return run([AAPT2, 'dump', 'xmltree', '--file', path, apk])[1]


def _ind(s):
    return len(s) - len(s.lstrip(' '))


def _tag(s):
    """'            E: LinearLayout (line=606)' -> 'LinearLayout'（必须先 strip）。"""
    return s.strip()[3:].split(' (line=')[0].strip()


def dex_blob(apk):
    z = zipfile.ZipFile(apk)
    names = [n for n in z.namelist() if re.match(r'classes\d*\.dex$', n)]
    return b''.join(z.read(n) for n in names)


def count(blob, token):
    return blob.count(token.encode('utf-8'))


_dump_cache = {}


def dex_dump(apk):
    """整个 APK 所有 dex 的 dexdump -d 文本（判方法是否存在）。"""
    if apk in _dump_cache:
        return _dump_cache[apk]
    z = zipfile.ZipFile(apk)
    out = []
    tmpdir = os.path.dirname(os.path.abspath(__file__))
    for nm in [n for n in z.namelist() if re.match(r'classes\d*\.dex$', n)]:
        tmp = os.path.join(tmpdir, '_tmp1031_%s' % nm)
        with open(tmp, 'wb') as f:
            f.write(z.read(nm))
        out.append(run([DEXDUMP, '-d', tmp])[1])
        os.remove(tmp)
    _dump_cache[apk] = '\n'.join(out)
    return _dump_cache[apk]


def res_string(text, name):
    """从 `aapt2 dump resources` 文本里取某个 string 资源的默认值。"""
    i = text.find('string/%s' % name)
    if i < 0:
        return None
    m = re.search(r'"([^"]*)"', text[i:i + 400])
    return m.group(1) if m else None


def dp_attrs(xmltext, attr_id):
    """取出某个 dp 属性的全部数值（float）。"""
    return [float(m) for m in re.findall(re.escape(attr_id) + r'=([\d.]+)dp', xmltext)]


PAD_TOP = 'android:paddingTop(0x010100d7)'
PAD_BOTTOM = 'android:paddingBottom(0x010100d9)'
MARGIN_BOTTOM = 'android:layout_marginBottom(0x010100fa)'


def main():
    print('=' * 62)
    print('verify_1031 —— code 1031 设置页第五轮（产物层）')
    print('  new = %s' % os.path.basename(APK_NEW))
    print('  old = %s' % os.path.basename(APK_OLD))
    print('=' * 62)

    bad_n = badging(APK_NEW)
    bad_o = badging(APK_OLD)
    man_n = xml(APK_NEW, MANIFEST)
    lay_n = xml(APK_NEW, LAYOUT)
    lay_o = xml(APK_OLD, LAYOUT)
    res_n = resources(APK_NEW)
    dex_n = dex_blob(APK_NEW)
    dex_o = dex_blob(APK_OLD)

    # ── A 版本档位 ────────────────────────────────────────────────────
    print('\n── A 版本档位 ────────────────────────────────────────────')
    m = re.search(r"versionCode='(\d+)'", bad_n)
    check('A1 versionCode = 1031（new）／对照包是 1030',
          m is not None and m.group(1) == '1031'
          and "versionCode='1030'" in bad_o,
          m.group(1) if m else 'missing')
    check('A2 versionName 仍是 2.3.5',
          "versionName='2.3.5'" in bad_n)
    check('A3 application-label 已去掉「设置」二字',
          "application-label:'DLsiteFloat'" in bad_n
          and "application-label:'DLsiteFloat'" not in bad_o.replace("application-label:'DLsiteFloat'", 'X', 1))
    # 桌面名取的是 alias 的 android:label；application 的 label 是 app_name。
    # 两者可以是不同资源（settings_label / app_name），但**字符串值**都必须是 DLsiteFloat。
    alias_lbl = res_string(res_n, 'settings_label')
    app_lbl = res_string(res_n, 'app_name')
    check('A4 桌面 alias 的 label 值 = DLsiteFloat（app_name 同值）',
          alias_lbl == 'DLsiteFloat' and app_lbl == 'DLsiteFloat',
          'settings_label=%r app_name=%r' % (alias_lbl, app_lbl))

    # ── B 清单结构 ────────────────────────────────────────────────────
    print('\n── B 清单：桌面入口独立成 alias ─────────────────────────')
    check('B1 产物里确实有 E: activity-alias',
          'E: activity-alias' in man_n)
    check('B2 alias 全名 = ...ui.LauncherAlias',
          '"io.github.ariinyume.dlsitesoundfloat.ui.LauncherAlias"' in man_n)
    check('B3 alias 的 targetActivity 指向 SettingsActivity',
          ':targetActivity(0x01010202)="io.github.ariinyume.dlsitesoundfloat.ui.SettingsActivity"' in man_n)
    lm = [i for i, ln in enumerate(man_n.splitlines())
          if 'android.intent.category.LAUNCHER' in ln]
    alias_ln = next((i for i, ln in enumerate(man_n.splitlines()) if 'E: activity-alias' in ln), -1)
    check('B4 LAUNCHER 类别只有一处，且落在 alias 之内',
          len(lm) == 1 and alias_ln > 0 and lm[0] > alias_ln,
          'lines=%s alias=%s' % (lm, alias_ln))

    # ── C 文案 ────────────────────────────────────────────────────────
    print('\n── C 页头 / 桌面名 / 简介 ────────────────────────────────')
    check('C1 页头副标题（简中）= 状态栏字幕模块',
          count(dex_n, 'DLsiteSound 悬浮窗 · 状态栏字幕模块') == 1
          and count(dex_o, 'DLsiteSound 悬浮窗 · 状态栏字幕模块') == 0)
    check('C2 旧副标题（外观调整）已绝迹',
          count(dex_n, '状态栏字幕外观调整') == 0
          and count(dex_o, '状态栏字幕外观调整') == 1)
    check('C3 英文副标题缩短（新串在 / 旧串无）',
          count(dex_n, 'DLsiteSound floating window · status bar subtitles') == 1
          and count(dex_n, 'status bar subtitle appearance') == 0)
    check('C4 简介中文含「悬浮窗 & 状态栏字幕模块」',
          'DLsiteSound 悬浮窗 & 状态栏字幕模块' in res_n)
    check('C5 values-en 提供英文简介',
          'DLsiteSound Floating Window & Status Bar Subtitle Module' in res_n)

    # ── D 本轮新增的字符串 ────────────────────────────────────────────
    print('\n── D 图标开关与缓存短标签 ────────────────────────────────')
    # 简中「隐藏桌面图标」在 dex 里会命中 2 次（枚举常量 + 三语表各一份），故只守 >= 1
    check('D1 「隐藏桌面图标」三语进包',
          count(dex_n, 'Hide home screen icon') == 1
          and count(dex_n, '隐藏桌面图标') >= 1
          and count(dex_o, 'Hide home screen icon') == 0)
    check('D2 UI prefs 键 settings_hide_launcher_icon 进包',
          count(dex_n, 'settings_hide_launcher_icon') == 1
          and count(dex_o, 'settings_hide_launcher_icon') == 0)
    check('D3 alias 全名作为常量进包',
          count(dex_n, 'ui.LauncherAlias') == 1
          and count(dex_o, 'ui.LauncherAlias') == 0)
    check('D4 缓存按钮短标签：Clear cached / Clear prefetch',
          count(dex_n, 'Clear prefetch') >= 1
          and count(dex_o, 'Clear prefetch') >= 1)   # 两包都含，仅作存在性
    check('D5 缓存说明英文已压短',
          count(dex_n, 'Played tracks are cached automatically.') == 1
          and count(dex_o, 'Played tracks are cached automatically.') == 0)
    check('D6 常开横幅 = BUILD 2.3.5 / code 1031',
          count(dex_n, 'BUILD 2.3.5 / code 1031') == 2
          and count(dex_o, 'BUILD 2.3.5 / code 1031') == 0)

    # ── E 缩写带来的计数变化（有区分力的硬锚）─────────────────────────
    print('\n── E 文案缩写（计数对照）─────────────────────────────────')
    n_cc = count(dex_n, 'Clear cached subtitles')
    o_cc = count(dex_o, 'Clear cached subtitles')
    check('E1 「Clear cached subtitles」由 2 处降到 1 处（按钮改短、标题保留）  %d→%d' % (o_cc, n_cc),
          n_cc == 1 and o_cc == 2)
    n_cp = count(dex_n, 'Clear prefetched subtitles')
    o_cp = count(dex_o, 'Clear prefetched subtitles')
    check('E2 「Clear prefetched subtitles」由 2 处降到 1 处  %d→%d' % (o_cp, n_cp),
          n_cp == 1 and o_cp == 2)
    check('E3 中文按钮标签未变（仍各 1 处）',
          count(dex_n, '清除已缓存字幕') >= 1 and count(dex_n, '清除预取字幕') >= 1)

    # ── F 资源层内距 ──────────────────────────────────────────────────
    print('\n── F 资源层：四卡内距 / 底栏位置 ─────────────────────────')
    pt_n, pb_n = dp_attrs(lay_n, PAD_TOP), dp_attrs(lay_n, PAD_BOTTOM)
    pt_o, pb_o = dp_attrs(lay_o, PAD_TOP), dp_attrs(lay_o, PAD_BOTTOM)
    check('F1 卡内 paddingBottom=10dp 恰好 4 处（四张卡）  new=%d old=%d'
          % (pb_n.count(10.0), pb_o.count(10.0)),
          pb_n.count(10.0) == 4 and pb_o.count(10.0) == 0)
    check('F2 paddingTop=10dp 共 5 处（四张卡 + 页头行，上一版只有 1 处）  new=%d old=%d'
          % (pt_n.count(10.0), pt_o.count(10.0)),
          pt_n.count(10.0) == 5 and pt_o.count(10.0) == 1)
    mb_n = dp_attrs(lay_n, MARGIN_BOTTOM)
    mb_o = dp_attrs(lay_o, MARGIN_BOTTOM)
    check('F3 底栏上抬到 28dp（原来 12dp）  new=%s old=%s' % (mb_n[-1:], mb_o[-1:]),
          mb_n.count(28.0) == 1 and mb_o.count(28.0) == 0)
    check('F4 底栏容器不再裁剪子视图（clipChildren=false）',
          lay_n.count(':clipChildren(0x010100ea)=false') == 1
          and lay_o.count(':clipChildren(0x010100ea)=false') == 0)
    check('F5 滚动区底部让位仍是 12dp（未回退到 96dp）',
          lay_n.count('paddingBottom(0x010100d9)=12.000000dp') == 1
          and lay_n.count('96.000000dp') == 0)

    # ── G 方法层 ──────────────────────────────────────────────────────
    print('\n── G 方法层 ──────────────────────────────────────────────')
    d_n = dex_dump(APK_NEW)
    d_o = dex_dump(APK_OLD)
    for tag, sig in (('G1', 'SettingsActivity;.applyLauncherIconState:(Z)V'),
                     ('G2', 'SettingsActivity;.buildLauncherIconRow:(Landroid/widget/LinearLayout;)V'),
                     ('G3', 'SettingsActivity;.repinExperimentalLast:()V'),
                     ('G4', 'SettingsActivity;.onHideLauncherIconToggled:(Z)V')):
        check('%s 方法存在（new）且上一版没有  %s' % (tag, sig.split('.')[-1]),
              sig in d_n and sig not in d_o)

    # ── H 如实标注 ────────────────────────────────────────────────────
    print('\n── H 如实标注：以下在产物层**没有**区分力 ────────────────')
    nodisc.extend([
        '预览窗折叠几何（三行净高 / clipBounds）—— 纯运行时像素计算，APK 里只有常量与调用',
        '行尾空隙 ROW_LABEL_TAIL_DP / ROW_TAIL_GAP_DP —— Java 里 dp() 现算，无资源条目',
        '保存键 8dp / 溢出键 4dp 阴影 —— setElevation 在 onResume 链上执行，非 XML',
        '缓存按钮单行 + 等高 —— setSingleLine / MATCH_PARENT 均为代码调用',
        'pinCardLastBottom 的高度守卫 —— 逻辑分支，只能源码层验（见 verify_1031_src C1）',
    ])
    for s in nodisc:
        print('  SKIP  %s' % s)

    print('\n' + '=' * 62)
    if fails:
        print('FAIL %d/%d（另有 %d 项如实标注无区分力）' % (len(fails), total, len(nodisc)))
        for f in fails:
            print('  - %s' % f)
        return 1
    print('PASS %d/%d（另有 %d 项如实标注无区分力）' % (total, total, len(nodisc)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
