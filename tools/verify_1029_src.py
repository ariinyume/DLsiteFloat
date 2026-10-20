#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1029 / v2.3.5】设置页第三轮五项的 **源码层**验证。

读的是**活的工作区** ⇒ 判结构与接线；版本号只判本轮值，label 只守形态（铁律 82/⑬/94）。

本轮五条（Ari 2026-10-19 13:52 录屏 + 14:12 日志包）
------------------------------------------------------
① 预览收起改单面裁切（旧版「百叶窗」）；顺带让底色与展开态同源
② 三处横向按钮组改 M3E 连通组（3dp 间距 / 内侧 8dp / 外侧保持圆角）
③ 底栏去掉容器层，按钮真正悬空
④ 语言胶囊点一下循环切换（删弹窗）
⑤ 预存字幕上限 8 → 16 部作品

验什么
------
A1–A7   预览单面裁切（视图合一 / 逐帧插值 / 内容位移 / 实测口径 / 双向动画）
B1–B7   连通按钮组（两个常量 / 逐角模型 / 三处接线 / 组圆角不再整角同值）
C1–C6   底栏悬空（背景·阴影·内边距三清 / 溢出键自有圆底 / 不刷底色）
D1–D7   语言循环（顺序 / SYSTEM 先解析 / 弹窗已删 / 无障碍文案）
E1–E2   预存上限
F1–F5   版本纪律
G1–G3   边界（预览三层 / 液态玻璃 / 色板）

用法
----
    python verify_1029_src.py [src_root]
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


def main():
    global SRC
    SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'src', 'main')

    act = read(jp('ui', 'SettingsActivity.java'))
    act_code = code_only(act)
    strings = read(jp('ui', 'Strings.java'))
    layout = read(os.path.join(SRC, 'res', 'layout', 'activity_settings.xml'))
    gradle = read(os.path.join(SRC, '..', '..', 'build.gradle'))
    module = read(jp('DlsiteSoundSubtitleModule.java'))
    prefetch = read(jp('hook', 'ZiptreePrefetch.java'))
    icon_bg = read(os.path.join(SRC, 'res', 'drawable', 'bg_toolbar_icon.xml'))

    # ── A 预览单面裁切 ────────────────────────────────────────────────
    print('\n── A 预览收起改单面裁切 ──────────────────────────────────')
    # 注释里会写「1028 的 preview_mini 已删除」，所以判据必须先剥掉 XML 注释再看节点
    layout_nodes = re.sub(r'<!--.*?-->', '', layout, flags=re.S)
    check('A1 布局里已无 preview_mini（折叠不再有第二个视图）',
          'preview_mini' not in layout_nodes)
    check('A2 代码里已无 mPreviewMini / updateMiniPreview',
          'mPreviewMini' not in act_code and 'updateMiniPreview' not in act_code)
    frac = body(act, 'private void applyPreviewFraction(float f)')
    check('A3 applyPreviewFraction 按 0→1 插值高度（不是两态硬切换）',
          'mPreviewFullH' in frac and 'mPreviewWinH' in frac
          and re.search(r'Math\.round\(mPreviewFullH \+ \(mPreviewWinH - mPreviewFullH\) \* f\)', frac) is not None)
    check('A4 折叠时把 1..3 行对齐窗口顶部（translationY）',
          'mPreviewLines.setTranslationY(-mPreviewWinDy * f)' in frac)
    metrics = body(act, 'private void refreshPreviewMetrics()')
    check('A5 用 UNSPECIFIED 量五行自然高（避开父级 AT_MOST 夹值）',
          'MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED)' in metrics)
    # 【code 1031 有意改写】1031 把窗口几何从「逐行累加」换成「第 FIRST 行顶 / 第 LAST 行底」
    #   两个真实边界（卡高 = 两者之差）。意图完全等价：窗口里只有 FIRST..LAST 这三行。
    # 【code 1033 有意改写】接受第三种形态：从 paddingTop 起逐行累加，用下标
    #   WINDOW_FIRST / WINDOW_LAST 夹出区间（不再直接读 getChildAt(WINDOW_LAST)）。
    #   判据意图不变：窗口里只有 FIRST..LAST 这三行。
    check('A6 折叠窗口只取 WINDOW_FIRST..WINDOW_LAST 三行',
          ('i >= WINDOW_FIRST && i <= WINDOW_LAST' in metrics
           or ('getChildAt(WINDOW_FIRST)' in metrics and 'getChildAt(WINDOW_LAST)' in metrics)
           or ('i == WINDOW_FIRST' in metrics and 'i == WINDOW_LAST' in metrics))
          and 'WINDOW_FIRST = 1' in act)
    coll = body(act, 'private void applyPreviewCollapsed(boolean collapsed, boolean animate)')
    check('A7 收起与展开**双向**都走同一条 ofFloat 动画',
          'ValueAnimator.ofFloat(mPreviewFraction, target)' in coll
          and 'applyPreviewFraction(target)' in coll)
    upd = body(act, 'private void updatePreview()')
    check('A8 行被重建后按当前折叠态重贴高度（否则字号变大会停在旧高度）',
          'mPreviewMetricsValid = false;' in upd and 'refreshPreviewMetrics();' in upd
          and 'applyPreviewFraction(1f)' in upd)

    # ── B 连通按钮组 ──────────────────────────────────────────────────
    print('\n── B M3E 连通按钮组 ──────────────────────────────────────')
    check('B1 相邻间距常量 = 3dp',
          re.search(r'GROUP_GAP_DP\s*=\s*3\s*;', act) is not None)
    check('B2 内侧圆角常量 = 8dp',
          re.search(r'GROUP_INNER_RADIUS_DP\s*=\s*8\s*;', act) is not None)
    shape = body(act, 'private ShapeAppearanceModel connectedShape(')
    check('B3 逐角设置四个 CornerSize（整角同值会把外侧也削平）',
          all(k in shape for k in ('setTopLeftCornerSize(', 'setBottomLeftCornerSize(',
                                   'setTopRightCornerSize(', 'setBottomRightCornerSize(')))
    check('B4 内侧只给「有邻居」的那一侧',
          'index > 0 ? inner : outer' in shape and 'index < count - 1 ? inner : outer' in shape)
    tabs = body(act, 'private void buildAppearanceTabs()')
    seg = body(act, 'private SegmentedRow addSegmentedRow(')
    # 【code 1030】**有意改写**：页签组高 48 → CONTROL_H_DP(40)，外侧半径
    #   跟着从写死的 24f 改成「组高一半」—— 与对齐那排同一个表达式，两排才不会走散。
    check('B5 外观页签组接上连通模型（外侧 = 组高一半）',
          'connectedShape(i, labels.length, CONTROL_H_DP / 2f)' in tabs)
    check('B6 对齐/分段行接上连通模型（外侧 = 组高一半）',
          'connectedShape(i, options.length, CONTROL_H_DP / 2f)' in seg)
    check('B7 导出/导入两段接上连通模型且间距 3dp',
          'connectedShape(0, 2, CONTROL_H_DP / 2f)' in act
          and 'connectedShape(1, 2, CONTROL_H_DP / 2f)' in act
          and 'ip.setMarginStart(dp(GROUP_GAP_DP))' in act)
    # ⚠️ 只判**按钮**：分段行里 trackBg.setCornerRadius(组高一半) 是轨道的裁切轮廓，
    #    不是按钮圆角，它必须留着（否则外侧胶囊的裁切就没了）。
    check('B8 按钮圆角不再用 setCornerRadius 设（那是四角同值）',
          'b.setCornerRadius(' not in tabs and 'b.setCornerRadius(' not in seg)

    # ── C 底栏真悬空 ──────────────────────────────────────────────────
    print('\n── C 底栏去掉容器层 ──────────────────────────────────────')
    # 🔴【code 1030】**本段判据有意改写**（判的是同一件事的更彻底实现）。
    #   1029 的做法是「留着 FloatingToolbarLayout，把 background / backgroundTint /
    #   elevation / padding 四样清成透明」。真机复测（Ari 第 8 条，连续两轮）那层
    #   「底部覆盖」还在，而且**随滚动状态出现 / 消失** ⇒ 它不是 XML 里那四样，
    #   是该控件在自身状态变化时重新装回来的一层形状绘制，清属性管不住。
    #   1030 直接把容器换成普通 LinearLayout ⇒ 判据从「四个属性是透明」改成
    #   「容器不存在 + 底栏自身零背景」。
    bar_nodes = re.sub(r'<!--.*?-->', '', layout, flags=re.S)
    bi = bar_nodes.find('android:id="@+id/bottom_bar"')
    bar_tag = bar_nodes[bar_nodes.rfind('<', 0, bi):bar_nodes.find('>', bi)] if bi > 0 else ''
    check('C1 容器已不是 FloatingToolbarLayout（清属性管不住被重装的形状绘制）',
          'floatingtoolbar.FloatingToolbarLayout' not in bar_nodes)
    check('C2 bottom_bar 变成普通 LinearLayout，id 与吸底定位不变',
          bar_tag.startswith('<LinearLayout') and 'layout_gravity="bottom|end"' in bar_tag)
    check('C3 不再挂官方样式 / 二次 inset 开关',
          'Widget.Material3.FloatingToolbar' not in bar_nodes
          and 'marginBottomSystemWindowInsets' not in bar_nodes)
    check('C4 底栏自身零背景、零阴影（要的是按钮悬空，不是一条浮起的板子）',
          bar_tag != '' and 'android:background' not in bar_tag
          and 'app:elevation' not in bar_tag and 'app:backgroundTint' not in bar_tag)
    check('C5 溢出键有自己的圆形 tonal 底',
          'android:background="@drawable/bg_toolbar_icon"' in layout)
    check('C6 bg_toolbar_icon = 4dp inset + oval + colorSurfaceContainerHigh'
          '（视觉 40dp、命中区仍 48dp）',
          '<inset' in icon_bg and 'android:inset="4dp"' in icon_bg
          and 'android:shape="oval"' in icon_bg
          and '?attr/colorSurfaceContainerHigh' in icon_bg)
    page = body(act, 'private void applyPageBackground(')
    check('C7 页面底色仍不刷 bottom_bar（刷了会把工具条刷成一块板）',
          '\n        setBg(mBottomBar' not in page)

    # ── D 语言循环 ────────────────────────────────────────────────────
    print('\n── D 语言胶囊点一下换一种 ────────────────────────────────')
    cyc = body(act, 'private void cycleLanguage()')
    check('D1 cycleLanguage 存在且先 resolve 再取下一个',
          'UiLang resolved = current.resolve();' in cyc)
    check('D2 循环顺序 简中 → 繁中 → EN → 简中',
          re.search(r'case ZH_CN:\s*\n\s*next = UiLang\.ZH_TW;', cyc) is not None
          and re.search(r'case ZH_TW:\s*\n\s*next = UiLang\.EN;', cyc) is not None
          and re.search(r'default:\s*\n\s*next = UiLang\.ZH_CN;', cyc) is not None)
    check('D3 语言选择弹窗已删',
          'showLanguageDialog' not in act_code)
    check('D4 点击走循环',
          'mLanguageButton.setOnClickListener(v -> cycleLanguage());' in act_code)
    check('D5 无障碍文案含「点击切换语言」',
          'Strings.LANGUAGE_CYCLE_HINT.get(mLang)' in act_code)
    check('D6 LANGUAGE_CYCLE_HINT 三语齐备',
          re.search(r'LANGUAGE_CYCLE_HINT\("点击切换语言",\s*"點擊切換語言",\s*"Tap to switch language"\)',
                    strings) is not None)
    check('D7 SYSTEM 的短名仍走 resolve()（初始显示跟随系统）',
          'switch (resolve())' in read(jp('ui', 'UiLang.java')))

    # ── E 预存上限 ────────────────────────────────────────────────────
    print('\n── E 预存字幕上限 ────────────────────────────────────────')
    check('E1 MAX_WORKS = 16', re.search(r'MAX_WORKS\s*=\s*16\s*;', prefetch) is not None)
    check('E2 淘汰判据仍挂在 MAX_WORKS 上（只改数字，不改逻辑）',
          'size() > MAX_WORKS' in prefetch)

    # ── F 版本纪律 ────────────────────────────────────────────────────
    print('\n── F 版本纪律 ────────────────────────────────────────────')
    m_code = re.search(r'def appVersionCode\s*=\s*(\d+)', gradle)
    m_name = re.search(r"def appVersionName\s*=\s*'([^']+)'", gradle)
    m_tag = re.search(r"def appVersionTag\s*=\s*'([^']+)'", gradle)
    m_label = re.search(r"def appVersionCodeLabel\s*=\s*'([^']+)'", gradle)
    # 【code 1030】**有意改写**：源码层读的是**活的工作区**，钉死本轮值会让每一次
    #   版本推进都把旧脚本判成 FAIL（1027/1028 两轮实踩，铁律 82/94）⇒ 只守下界。
    check('F1 appVersionCode >= 1029（本轮及以后）',
          m_code is not None and int(m_code.group(1)) >= 1029,
          m_code.group(1) if m_code else '未匹配')
    check('F2 label 只守形态（构建当天 ≠ 发版日，禁钉当天）',
          m_label is not None and re.match(r'^\d{4}\.\d+$', m_label.group(1)) is not None)
    check('F3 versionName == versionTag（同一轮里两处必须相等）',
          m_name is not None and m_tag is not None and m_name.group(1) == m_tag.group(1))
    banner = '==== BUILD %s / code %s' % (m_name.group(1), m_code.group(1))
    check('F4 常开横幅与 gradle 的 versionName + code 一致（动态拼，不钉字面量）',
          'XposedCompat.log("[DLsiteSoundFloat] %s");' % banner in module)
    check('F5 历史履历段仍保留 1028（只加不删）',
          'code 1028 （' in module)

    # ── G 边界 ────────────────────────────────────────────────────────
    print('\n── G 边界（本轮不该被顺手改坏）──────────────────────────')
    check('G1 完整预览仍是三层（backdrop / panel / lines）',
          all(('android:id="@+id/preview_%s"' % k) in layout
              for k in ('backdrop', 'panel', 'lines')))
    check('G2 液态玻璃预览材质未被动过',
          'mPreviewGlass.setPreviewBackdrop(' in act_code
          and 'new LiquidGlassDrawable(radius, density)' in act_code)
    check('G3 色板热区仍是 48dp（未回退）',
          re.search(r'SWATCH_TOUCH_DP\s*=\s*48\s*;',
                    read(jp('ui', 'ColorSwatchRow.java'))) is not None)

    print('\n' + '=' * 60)
    if fails:
        print('FAIL %d/%d' % (len(fails), total))
        for f in fails:
            print('  - ' + f)
        return 1
    print('PASS %d/%d' % (total, total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
