#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1032 / v2.3.5】设置页第六轮九项的 **源码层** 验证。

读的是**活的工作区** ⇒ 判结构与接线；版本号只守下界、label 只守形态（铁律 82/94）。

本轮九条（Ari 2026-10-19 17:36 的录屏）
------------------------------------------------------------------
① 「排版」里第一个选项离页签按钮，比其他卡片第一个选项离卡顶更近
② 老问题更严重：预览窗简繁中从第二行起不显示、英文所有行都不显示
③ 所有卡片控件下边距改为 4
④ 隐藏桌面图标没做小图标；且所有小图标粗细不一，需风格统一
⑤ 保存设置按钮还是太靠页面下方，再往上抬
⑥ 🔴 打开「桌面图标隐藏」后，桌面图标与 LSPosed 的「打开」一起消失（真机事故）
⑦ 「字幕 / 行态 / 排版」按钮离卡片上端太近
⑧ 保存设置按钮四个角有直角阴影，按钮下方有平切
⑨ LSPosed 简介要中英并列（上一版没把英文放上去）

验什么
------
A1–A5   页签间距 / 卡片内距（①⑦）
B1–B6   预览窗「父级压扁」修复（②）
C1–C4   控件下边距统一 4dp（③）
D1–D6   图标成套 + 隐藏图标补图（④）
E1–E6   保存栏（⑤⑧）
F1–F7   隐藏桌面图标的安全绳（⑥）
G1–G3   LSPosed 简介（⑨）
H1–H4   版本纪律
I1–I3   边界（预览三层仍在 / 语言循环 / alias 仍唯一）

用法
----
    python verify_1032_src.py [src_root]
退出码 0 = 全部通过
"""

import os
import re
import sys

SRC = None
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


def read(p):
    """读源码：先归一化行尾（铁律 58）。"""
    with open(p, 'rb') as f:
        return f.read().decode('utf-8', 'replace').replace('\r\n', '\n')


def jp(*parts):
    return os.path.join(SRC, 'java', 'io', 'github', 'ariinyume', 'dlsitesoundfloat', *parts)


def body(src, header):
    """取一个方法/内部类的花括号体（从 header 起、配对到收口）。"""
    i = src.find(header)
    if i < 0:
        return ''
    j = src.find('{', i)
    if j < 0:
        return ''
    depth = 0
    for k in range(j, len(src)):
        c = src[k]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return src[j:k + 1]
    return ''


def code_only(src):
    """去掉行注释（判「代码里有没有」时用，避免被注释里的历史说明误判）。"""
    out = []
    for ln in src.split('\n'):
        s = ln.strip()
        if s.startswith('//') or s.startswith('*') or s.startswith('/*'):
            continue
        out.append(ln)
    return '\n'.join(out)


def strip_comments(xml):
    return re.sub(r'<!--.*?-->', '', xml, flags=re.S)


def node_block(xml, resid, close_tag='>'):
    """按 id 取节点区块（自闭合标签与成对标签都能取到）。"""
    i = xml.find('android:id="@+id/%s"' % resid)
    if i < 0:
        return ''
    start = xml.rfind('<', 0, i)
    if close_tag == '>':
        j = xml.find('>', i)
        return xml[start:j + 1] if j > 0 else ''
    j = xml.find(close_tag, i)
    return xml[start:j + len(close_tag)] if j > 0 else ''


def grep_const(src, name):
    m = re.search(r'\b%s\s*=\s*(\d+)\s*;' % re.escape(name), src)
    return int(m.group(1)) if m else None


def main():
    global SRC
    SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'src', 'main')

    act = read(jp('ui', 'SettingsActivity.java'))
    act_code = code_only(act)
    strings_java = read(jp('ui', 'Strings.java'))
    layout = read(os.path.join(SRC, 'res', 'layout', 'activity_settings.xml'))
    layout_nc = strip_comments(layout)
    manifest = read(os.path.join(SRC, 'AndroidManifest.xml'))
    manifest_nc = strip_comments(manifest)
    res_zh = read(os.path.join(SRC, 'res', 'values', 'strings.xml'))
    res_en = read(os.path.join(SRC, 'res', 'values-en', 'strings.xml'))
    gradle = read(os.path.join(SRC, '..', '..', 'build.gradle'))
    drawable_dir = os.path.join(SRC, 'res', 'drawable')

    print('=' * 62)
    print('code 1032 源码层验证  （src=%s）' % os.path.normpath(SRC))
    print('=' * 62)

    # ── A 页签间距 / 卡片内距 ────────────────────────────────────────
    print('\n── A 页签间距与卡片内距（①⑦）────────────────────────────')
    card_pad_top = grep_const(act, 'CARD_PAD_TOP_DP')
    check('A1 CARD_PAD_TOP_DP 仍是 10（页签下距以它为准）  %s' % card_pad_top,
          card_pad_top == 10)

    tabs_xml = node_block(layout_nc, 'appearance_tabs')
    m = re.search(r'layout_marginBottom="([\d.]+)dp"', tabs_xml)
    check('A2 XML 页签 marginBottom = 10dp（原 6dp）  %s'
          % (m.group(1) if m else '未取到'),
          bool(m) and abs(float(m.group(1)) - 10.0) < 1e-6)

    tabs_java = body(act_code, 'private void buildAppearanceTabs()')
    check('A3 代码里页签 bottomMargin 取同一个常量',
          'bottomMargin' in tabs_java and 'dp(CARD_PAD_TOP_DP)' in tabs_java)

    card_main = node_block(layout_nc, 'card_main',
                           '</com.google.android.material.card.MaterialCardView>')
    m = re.search(r'android:paddingTop="([\d.]+)dp"', card_main)
    # 【code 1033 有意改写】16 → 24dp：Ari「字幕 / 行态 / 排版 三个按钮离上边距再远一点」。
    #   判据意图不变（只抬这一张卡，另三张仍由下面的 others 判 10dp）。
    check('A4 字幕外观卡内层 paddingTop = 24dp（1032 起 16、1033 起 24）  %s'
          % (m.group(1) if m else '未取到'),
          bool(m) and abs(float(m.group(1)) - 24.0) < 1e-6)

    others = []
    for rid in ('group_liquidglass', 'group_experimental', 'group_misc'):
        blk = node_block(layout_nc, rid)
        mm = re.search(r'android:paddingTop="([\d.]+)dp"', blk)
        others.append(float(mm.group(1)) if mm else -1.0)
    check('A5 另外三张卡 paddingTop 仍是 10dp（未被顺手改）  %s' % others,
          others == [10.0, 10.0, 10.0])

    # ── B 预览窗「父级压扁」修复 ────────────────────────────────────
    print('\n── B 预览窗压扁修复（②）────────────────────────────────')
    pin = body(act_code, 'private void pinPreviewContentHeight()')
    check('B1 pinPreviewContentHeight() 存在', pin != '')
    check('B2 折叠态把内容高度钉成自然全高 mPreviewFullH',
          'p.height = mPreviewFullH;' in pin)

    rel = body(act_code, 'private void releasePreviewContentHeight()')
    check('B3 releasePreviewContentHeight() 写回 WRAP_CONTENT',
          'p.height = ViewGroup.LayoutParams.WRAP_CONTENT;' in rel)

    frac = body(act_code, 'private void applyPreviewFraction(float f)')
    i_pin = frac.find('pinPreviewContentHeight();')
    i_card = frac.find('lp.height = mPreviewWinH;')
    check('B4 顺序：先钉内容高度、后改卡片高度  pin=%d card=%d' % (i_pin, i_card),
          0 <= i_pin < i_card)

    check('B5 量不出来时也要释放（否则停在固定高度上）',
          'releasePreviewContentHeight();' in frac)

    check('B6 钉高度时只按「与目标不同」写（避免每帧 setLayoutParams）',
          'p.height == mPreviewFullH' in pin)

    # ── C 控件下边距统一 4dp ────────────────────────────────────────
    print('\n── C 控件下边距统一（③）────────────────────────────────')
    tail_gap = grep_const(act, 'ROW_TAIL_GAP_DP')
    check('C1 ROW_TAIL_GAP_DP = 4（原 6）  %s' % tail_gap, tail_gap == 4)

    seg = body(act_code, 'private SegmentedRow addSegmentedRow(')
    check('C2 分段行 trackLp.bottomMargin = dp(ROW_TAIL_GAP_DP)',
          'trackLp.bottomMargin = dp(ROW_TAIL_GAP_DP);' in seg)

    sl = body(act_code, 'private SliderRow addSliderRow(')
    check('C3 滑块行 rowLp.bottomMargin = dp(ROW_TAIL_GAP_DP)',
          'rowLp.bottomMargin = dp(ROW_TAIL_GAP_DP);' in sl)

    colors = body(act_code, 'int previewAlpha, boolean showChecker)')
    check('C4 色板行 bodyLp.bottomMargin = dp(ROW_TAIL_GAP_DP)',
          'bodyLp.bottomMargin = dp(ROW_TAIL_GAP_DP);' in colors)

    # ── D 图标成套 ─────────────────────────────────────────────────
    print('\n── D 图标成套 + 隐藏图标补图（④）──────────────────────')
    EXPECT = ['ic_ui_palette', 'ic_ui_opacity', 'ic_ui_radius', 'ic_ui_highlight',
              'ic_ui_scale', 'ic_ui_blur', 'ic_ui_align', 'ic_ui_line_spacing',
              'ic_ui_wrap', 'ic_ui_panel', 'ic_ui_statusbar', 'ic_ui_log',
              'ic_ui_cache', 'ic_ui_flask', 'ic_ui_launcher']
    missing = [n for n in EXPECT if not os.path.exists(os.path.join(drawable_dir, n + '.xml'))]
    check('D1 15 枚图标全部存在（含新增 ic_ui_launcher）  缺=%s' % (missing or '无'),
          not missing)

    bad = []
    for n in EXPECT:
        p = os.path.join(drawable_dir, n + '.xml')
        if not os.path.exists(p):
            continue
        t = read(p)
        if 'android:strokeWidth="2"' not in t:
            bad.append(n + ':strokeWidth')
        if 'android:strokeLineCap="round"' not in t:
            bad.append(n + ':cap')
        if 'android:width="24dp"' not in t:
            bad.append(n + ':size')
    check('D2 全套统一 24dp / 描边 2dp / 圆头  异常=%s' % (bad or '无'), not bad)

    icon_body = body(act_code, 'private int iconForRow(Strings label)')
    check('D3 iconForRow 把 HIDE_LAUNCHER_ICON 映射到 ic_ui_launcher',
          'Strings.HIDE_LAUNCHER_ICON' in icon_body
          and 'R.drawable.ic_ui_launcher' in icon_body)

    check('D4 色板行改用 ic_ui_palette，旧的 ic_palette 已删除',
          'R.drawable.ic_ui_palette' in icon_body
          and 'R.drawable.ic_palette' not in act_code
          and not os.path.exists(os.path.join(drawable_dir, 'ic_palette.xml')))

    check('D5 不再有实心填充的行头图标（fillColor 只允许 #00000000）',
          all('android:fillColor="#FF' not in read(os.path.join(drawable_dir, n + '.xml'))
              or n == 'ic_ui_palette'
              for n in EXPECT if os.path.exists(os.path.join(drawable_dir, n + '.xml'))))

    # 【code 1033 有意改写】原判据要求「图标生成器脚本留档」。1033 起工具脚本一律
    #   用完即删（避免 tools/ 堆积一次性脚本），所以改为**反向**守：临时脚本不许残留。
    #   图标成套这件事由 D1–D5 直接判资源本体验证，不依赖生成器是否存在。
    check('D6 一次性生成脚本已清理（1033 起：tools/_gen_icons_*.py 不许残留）',
          not [n for n in os.listdir(os.path.dirname(os.path.abspath(__file__)))
               if n.startswith('_gen_icons_')])

    # ── E 保存栏 ───────────────────────────────────────────────────
    print('\n── E 保存栏上抬与投影不被裁（⑤⑧）──────────────────────')
    bar = node_block(layout_nc, 'bottom_bar', '</LinearLayout>')
    m = re.search(r'layout_marginBottom="([\d.]+)dp"', bar)
    check('E1 bottom_bar marginBottom = 48dp（原 28dp）  %s'
          % (m.group(1) if m else '未取到'),
          bool(m) and abs(float(m.group(1)) - 48.0) < 1e-6)

    root = node_block(layout_nc, 'settings_root', '</LinearLayout>')
    check('E2 settings_root clipChildren=false（祖先链最外层）',
          'android:clipChildren="false"' in root)

    coord = node_block(layout_nc, 'settings_coord', '</androidx.coordinatorlayout.widget.CoordinatorLayout>')
    check('E3 settings_coord clipChildren=false（第二层）',
          'android:clipChildren="false"' in coord)

    check('E4 bottom_bar clipChildren=false（第三层，1031 已有）',
          'android:clipChildren="false"' in bar)

    # 内层 wrap_content 容器：取 bottom_bar 里第一个 <LinearLayout ...> 属性串
    inner = bar[bar.find('<LinearLayout'):]
    inner = inner[:inner.find('>') + 1] if inner else ''
    check('E5 内层 wrap_content 容器 clipChildren=false（第四层，1031 漏的）',
          'android:clipChildren="false"' in inner)

    style = body(act_code, 'private void styleBottomBar()')
    check('E6 保存键恒定 elevation + 关掉 stateListAnimator',
          'setStateListAnimator(null)' in style and 'setElevation(dp(8))' in style)

    # ── F 隐藏桌面图标安全绳 ────────────────────────────────────────
    print('\n── F 隐藏桌面图标的安全绳（⑥ 真机事故）────────────────')
    sa = node_block(manifest_nc, '@+id/__none__')  # 占位，避免误用
    i_act = manifest_nc.find('ui.SettingsActivity"')
    seg_m = manifest_nc[i_act:i_act + 900] if i_act >= 0 else ''
    check('F1 SettingsActivity 挂着常驻 MAIN + CATEGORY_INFO',
          'android.intent.action.MAIN' in seg_m
          and 'android.intent.category.INFO' in seg_m
          and 'android.intent.category.LAUNCHER' not in seg_m)

    i_alias = manifest_nc.find('<activity-alias')
    alias_m = manifest_nc[i_alias:i_alias + 900] if i_alias >= 0 else ''
    check('F2 LauncherAlias 仍独占 MAIN + LAUNCHER',
          'android.intent.category.LAUNCHER' in alias_m)

    fb = body(act_code, 'private boolean hasFallbackEntry()')
    check('F3 hasFallbackEntry() 用 getLaunchIntentForPackage 判兜底入口',
          'getLaunchIntentForPackage' in fb and 'LAUNCHER_ALIAS' in fb)

    ap = body(act_code, 'private boolean applyLauncherIconState(boolean hide)')
    check('F4 隐藏前必须过安全绳，否则拒绝', 'hasFallbackEntry()' in ap)
    check('F5 拒绝时把 alias 强制回 ENABLED（不留半隐藏）',
          ap.count('COMPONENT_ENABLED_STATE_ENABLED') >= 2)

    tog = body(act_code, 'private void onHideLauncherIconToggled(boolean hide)')
    check('F6 被拒时开关弹回 + Toast + 落盘纠正',
          'if (!applyLauncherIconState(hide))' in tog
          and 'setChecked(!hide)' in tog
          and 'HIDE_ICON_UNSUPPORTED' in tog
          and 'saveHideLauncherIcon(!hide)' in tog)

    build_row = body(act_code, 'private void buildLauncherIconRow(')
    check('F7 进页面回填时也过一遍安全绳并纠正落盘',
          'applyLauncherIconState(true)' in build_row
          and 'saveHideLauncherIcon(false)' in build_row)

    # ── G LSPosed 简介 ─────────────────────────────────────────────
    print('\n── G LSPosed 简介中英并列（⑨）──────────────────────────')
    mz = re.search(r'<string name="app_description">(.*?)</string>', res_zh, re.S)
    me = re.search(r'<string name="app_description">(.*?)</string>', res_en, re.S)
    vz = mz.group(1) if mz else ''
    ve = me.group(1) if me else ''
    check('G1 默认值同时含中文与英文',
          '状态栏字幕模块' in vz and 'Status Bar Subtitle Module' in vz)
    check('G2 values-en 与默认值逐字相同（两处必须同步）', vz != '' and vz == ve)
    check('G3 简介用 &amp; 转义（不是裸 &）',
          '&amp;' in vz and ' & ' not in vz)

    # ── H 版本纪律 ─────────────────────────────────────────────────
    print('\n── H 版本纪律 ───────────────────────────────────────────')
    code = re.search(r'def appVersionCode = (\d+)', gradle)
    name = re.search(r"def appVersionName = '([\d.]+)'", gradle)
    label = re.search(r"def appVersionCodeLabel = '([^']*)'", gradle)
    check('H1 源码 versionCode ≥ 1032  %s' % (code.group(1) if code else '未取到'),
          bool(code) and int(code.group(1)) >= 1032)
# 【code 1037 泛化】原钉死 2.3.5 —— 1037 是**第一次真正升语义版本号**（2.3.5 → 2.4.0），
#   这类「本轮当时的不变量」在源码层脚本里必须收成形态（铁律 82）：守
#   「name 成型 + tag == name（tag 进 APK 文件名）」这两条真正的不变式，不钉具体值。
    check('H2 versionName 成型且 == tag（1037 起会真的升语义版本号）  %s'
          % (name.group(1) if name else '未取到'),
          bool(name) and re.fullmatch(r'\d+\.\d+\.\d+', name.group(1)) is not None
          and re.search(r"def appVersionTag\s*=\s*'%s'" % re.escape(name.group(1)),
                        gradle) is not None)
    check('H3 label 形态合法（四位+点+序号，不钉当天）  %s'
          % (label.group(1) if label else '未取到'),
          bool(label) and re.fullmatch(r'\d{4}\.\d+', label.group(1)) is not None)
    check('H4 履历里有【code 1032】段落', '【code 1032】' in gradle)

    # ── I 边界 ────────────────────────────────────────────────────
    print('\n── I 边界（不许顺手改坏）──────────────────────────────')
    check('I1 预览仍是「壁纸 + 面板 + 字幕」三层',
          all(layout_nc.count('android:id="@+id/%s"' % n) == 1
              for n in ('preview_backdrop', 'preview_panel', 'preview_lines')))
    check('I2 语言胶囊仍是循环切换（没退回弹窗）',
          'ic_language' in layout_nc and 'language_button' in layout_nc)
    check('I3 全清单只一处 LAUNCHER 分类（桌面不会出现两个图标）',
          manifest_nc.count('android.intent.category.LAUNCHER') == 1)

    print('\n' + '=' * 62)
    if fails:
        print('FAIL %d/%d' % (len(fails), total))
        for f in fails:
            print('  - %s' % f)
        return 1
    print('PASS %d/%d' % (total, total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
