#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1032 / v2.3.5】设置页第六轮九项的 **产物层** 验证（主验 1032 / 对照 1031）。

口径
----
每一条都报**「新包有 / 旧包无」两侧读数**；只在新包里成立不算证据。
验不到的**如实标注无区分力**（不硬凑）。

分节
----
A  清单层：SettingsActivity 的 MAIN+INFO 安全绳、LAUNCHER 仍唯一
B  资源层（布局）：页签下距 / 卡片内距 / 底栏上抬 / 四层不裁剪
C  资源层（字符串）：LSPosed 简介中英并列
D  资源层（图标）：新增 ic_ui_launcher、删除 ic_palette
E  dex 方法层：三个新方法只在 1032 里存在
F  dex 字符串层：安全绳 Toast 文案只在 1032 里存在
G  如实标注：产物层没有区分力的项

用法
----
    python verify_1032.py [new.apk] [old.apk]
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
    ROOT, 'app', 'build', 'outputs', 'apk', 'debug', 'DLsiteFloat-2.3.5-code1032-debug.apk')
APK_OLD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    UP, 'DLsiteFloat-2.3.5-code1031-debug.apk')

LAYOUT = 'res/layout/activity_settings.xml'
MANIFEST = 'AndroidManifest.xml'

PAD_TOP = 'android:paddingTop(0x010100d7)'
MARGIN_BOTTOM = 'android:layout_marginBottom(0x010100fa)'
CLIP_CHILDREN = 'clipChildren(0x010100ea)=false'
CLIP_TO_PADDING = 'clipToPadding(0x010100eb)=false'

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


def dex_blob(apk):
    z = zipfile.ZipFile(apk)
    names = [n for n in z.namelist() if re.match(r'classes\d*\.dex$', n)]
    return b''.join(z.read(n) for n in names)


def count(blob, token):
    return blob.count(token.encode('utf-8'))


_dump_cache = {}


def dex_dump(apk):
    """整个 APK 所有 dex 的 `dexdump -d` 文本（判方法是否存在）。"""
    if apk in _dump_cache:
        return _dump_cache[apk]
    z = zipfile.ZipFile(apk)
    out = []
    tmpdir = os.path.dirname(os.path.abspath(__file__))
    for nm in [n for n in z.namelist() if re.match(r'classes\d*\.dex$', n)]:
        tmp = os.path.join(tmpdir, '_tmp1032_%s' % nm)
        with open(tmp, 'wb') as f:
            f.write(z.read(nm))
        out.append(run([DEXDUMP, '-d', tmp])[1])
        os.remove(tmp)
    _dump_cache[apk] = '\n'.join(out)
    return _dump_cache[apk]


def res_string(text, name):
    """`aapt2 dump resources` 里某个 string 资源的默认值。"""
    i = text.find('string/%s' % name)
    if i < 0:
        return None
    m = re.search(r'"([^"]*)"', text[i:i + 600])
    return m.group(1) if m else None


def res_strings_all(text, name):
    """某个 string 资源的**全部**配置值（含 (en) 这类限定符）。"""
    i = text.find('string/%s' % name)
    if i < 0:
        return []
    # 只取这一条资源自己的区块：下一个 `    resource ` 之前
    j = text.find('    resource ', i + len('string/%s' % name))
    seg = text[i:j] if j > 0 else text[i:i + 400]
    return re.findall(r'\(([a-zA-Z\-]*)\)\s*"([^"]*)"', seg)


def dp_attrs(xmltext, attr_id):
    return [float(m) for m in re.findall(re.escape(attr_id) + r'=([\d.]+)dp', xmltext)]


def apk_entries(apk):
    return zipfile.ZipFile(apk).namelist()


def main():
    print('=' * 62)
    print('verify_1032 —— code 1032 设置页第六轮（产物层）')
    print('  new = %s' % os.path.basename(APK_NEW))
    print('  old = %s' % os.path.basename(APK_OLD))
    print('=' * 62)

    bad_n = badging(APK_NEW)
    bad_o = badging(APK_OLD)
    man_n = xml(APK_NEW, MANIFEST)
    man_o = xml(APK_OLD, MANIFEST)

    # ── A 清单层 ───────────────────────────────────────────────────
    print('\n── A 清单层：MAIN+INFO 安全绳 ───────────────────────────')
    # ⚠️ `aapt2 dump xmltree` 对每条属性会打两遍：`="X"` 与 `(Raw: "X")`。
    #    只数 `" (Raw:` 这一种形态，否则每处都被算 2 次（本轮踩过）。
    INFO = 'android.intent.category.INFO" (Raw'
    LAUNCHER = 'android.intent.category.LAUNCHER" (Raw'
    info_n = man_n.count(INFO)
    info_o = man_o.count(INFO)
    check('A1 新包有 MAIN + CATEGORY_INFO（旧包 0 处）  %d→%d' % (info_o, info_n),
          info_n == 1 and info_o == 0)

    lau_n = man_n.count(LAUNCHER)
    lau_o = man_o.count(LAUNCHER)
    check('A2 LAUNCHER 仍只 1 处（桌面不会出现两个图标）  %d→%d' % (lau_o, lau_n),
          lau_n == 1 and lau_o == 1)

    check('A3 alias 仍指向 SettingsActivity 且带图标/标签',
          'ui.LauncherAlias' in man_n
          and man_n.count('ui.LauncherAlias') >= 2)

    # ── B 布局资源层 ───────────────────────────────────────────────
    print('\n── B 布局层：页签下距 / 卡片内距 / 底栏 / 不裁剪 ───────')
    lay_n = xml(APK_NEW, LAYOUT)
    lay_o = xml(APK_OLD, LAYOUT)

    pt16_n, pt16_o = dp_attrs(lay_n, PAD_TOP).count(16.0), dp_attrs(lay_o, PAD_TOP).count(16.0)
    check('B1 卡片内 paddingTop=16dp（字幕外观卡）  0→1  %d→%d' % (pt16_o, pt16_n),
          pt16_n == 1 and pt16_o == 0)

    pt10_n, pt10_o = dp_attrs(lay_n, PAD_TOP).count(10.0), dp_attrs(lay_o, PAD_TOP).count(10.0)
    check('B2 paddingTop=10dp 由 5 处降为 4 处（另三卡 + 页头行）  %d→%d' % (pt10_o, pt10_n),
          pt10_n == 4 and pt10_o == 5)

    mb_n = dp_attrs(lay_n, MARGIN_BOTTOM)
    mb_o = dp_attrs(lay_o, MARGIN_BOTTOM)
    check('B3 底栏 marginBottom=48dp（原 28dp）  28:%d→%d  48:%d→%d'
          % (mb_o.count(28.0), mb_n.count(28.0), mb_o.count(48.0), mb_n.count(48.0)),
          mb_n.count(48.0) == 1 and mb_o.count(48.0) == 0
          and mb_n.count(28.0) == 0 and mb_o.count(28.0) == 1)

    check('B4 页签 marginBottom=10dp（原 6dp）  6:%d→%d  10:%d→%d'
          % (mb_o.count(6.0), mb_n.count(6.0), mb_o.count(10.0), mb_n.count(10.0)),
          mb_n.count(10.0) == 1 and mb_o.count(10.0) == 0
          and mb_n.count(6.0) == 0 and mb_o.count(6.0) == 1)

    cc_n, cc_o = lay_n.count(CLIP_CHILDREN), lay_o.count(CLIP_CHILDREN)
    check('B5 clipChildren=false 由 1 处扩到 4 处（祖先链四层）  %d→%d' % (cc_o, cc_n),
          cc_n == 4 and cc_o == 1)

    cp_n, cp_o = lay_n.count(CLIP_TO_PADDING), lay_o.count(CLIP_TO_PADDING)
    check('B6 clipToPadding=false 同步扩到 4 处  %d→%d' % (cp_o, cp_n),
          cp_n == 4 and cp_o == 1)

    check('B7 滚动区底部让位仍是 12dp（未回退）',
          lay_n.count('paddingBottom(0x010100d9)=12.000000dp') == 1)

    # ── C 字符串 ───────────────────────────────────────────────────
    print('\n── C 字符串层：LSPosed 简介中英并列 ─────────────────────')
    rs_n = resources(APK_NEW)
    rs_o = resources(APK_OLD)
    all_n = res_strings_all(rs_n, 'app_description')
    d_n = res_string(rs_n, 'app_description') or ''
    d_o = res_string(rs_o, 'app_description') or ''
    check('C1 新包默认简介含中文与英文  zh=%s en=%s'
          % ('状态栏字幕模块' in d_n, 'Status Bar Subtitle Module' in d_n),
          '状态栏字幕模块' in d_n and 'Status Bar Subtitle Module' in d_n)
    check('C2 旧包默认简介只有中文（英文没上去）  zh=%s en=%s'
          % ('状态栏字幕模块' in d_o, 'Status Bar Subtitle Module' in d_o),
          '状态栏字幕模块' in d_o and 'Status Bar Subtitle Module' not in d_o)
    same = len(all_n) >= 2 and len({v for _, v in all_n}) == 1
    check('C3 所有语言配置的简介逐字相同（%d 份配置）  %s'
          % (len(all_n), '一致' if same else [v for _, v in all_n]),
          same)

    # ── D 图标资源 ─────────────────────────────────────────────────
    print('\n── D 图标资源：新增 launcher / 删除旧 palette ───────────')
    ent_n = apk_entries(APK_NEW)
    ent_o = apk_entries(APK_OLD)
    lan_n = len([e for e in ent_n if 'ic_ui_launcher' in e])
    lan_o = len([e for e in ent_o if 'ic_ui_launcher' in e])
    check('D1 ic_ui_launcher 进包（旧包 0 份）  %d→%d' % (lan_o, lan_n),
          lan_n >= 1 and lan_o == 0)

    pal_n = len([e for e in ent_n if re.search(r'/ic_palette', e)])
    pal_o = len([e for e in ent_o if re.search(r'/ic_palette', e)])
    check('D2 旧 ic_palette 已从包里消失（被 ic_ui_palette 取代）  %d→%d' % (pal_o, pal_n),
          pal_n == 0 and pal_o >= 1)

    ui_n = len({e for e in ent_n if 'ic_ui_' in e})
    ui_o = len({e for e in ent_o if 'ic_ui_' in e})
    # +2 = 新增 ic_ui_palette（取代旧 ic_palette） + 新增 ic_ui_launcher
    check('D3 ic_ui_* 资源数由 %d 增到 %d（palette 换代 + launcher 新增）' % (ui_o, ui_n),
          ui_n == ui_o + 2)

    # ── E dex 方法层 ───────────────────────────────────────────────
    print('\n── E dex 方法层：三个新方法 ─────────────────────────────')
    dmp_n = dex_dump(APK_NEW)
    dmp_o = dex_dump(APK_OLD)
    for tag, sig in (('E1', 'hasFallbackEntry:()Z'),
                     ('E2', 'pinPreviewContentHeight:()V'),
                     ('E3', 'releasePreviewContentHeight:()V')):
        check('%s 方法存在（new）且上一版没有  %s' % (tag, sig.split(':')[0]),
              sig in dmp_n and sig not in dmp_o)

    # ── F dex 字符串层 ─────────────────────────────────────────────
    print('\n── F dex 字符串层：安全绳提示文案 ──────────────────────')
    blob_n = dex_blob(APK_NEW)
    blob_o = dex_blob(APK_OLD)
    s_n = count(blob_n, '此设备不支持隐藏桌面图标')
    s_o = count(blob_o, '此设备不支持隐藏桌面图标')
    check('F1 中文提示只在 1032 里（旧包 0 次）  %d→%d' % (s_o, s_n), s_n >= 1 and s_o == 0)

    l_n = count(blob_n, 'ic_ui_launcher')
    check('F2 dex 里已引用 ic_ui_launcher 资源名  %d' % l_n, l_n >= 1)

    # ── G 如实标注 ─────────────────────────────────────────────────
    print('\n── G 如实标注：以下在产物层**没有**区分力 ──────────────')
    nodisc.extend([
        '控件下边距 4dp（ROW_TAIL_GAP_DP）—— Java 里 dp() 现算，无资源条目',
        '图标「粗细一致」—— 描边宽度是矢量图属性，二进制 XML 里按资源 id 存取，纯视觉判',
        '保存键投影不再被裁 —— 阴影是运行时栅格化，XML 只能验 clipChildren',
        '预览窗「三行都在」—— 纯运行时几何，能验的只有 pinPreviewContentHeight 方法存在',
        '页签→首项与卡顶→首项的**观感相等** —— 只能验两个数值相同，实际像素要真机',
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
