#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1030 / v2.3.5】设置页第四轮九项的 **源码层** 验证。

读的是**活的工作区** ⇒ 判结构与接线；版本号只守下界、label 只守形态（铁律 82/94）。

本轮九条（Ari 2026-10-19 15:01 录屏 + 15:01 日志包 + 一张折叠态截图）
------------------------------------------------------------------
① 预览窗缩小应「上下各藏一行」（现在是下面藏了两行）；英文态窗口显示不全
② 外观页签离卡片顶端太近
③ 页签高度与选中/未选配色改为与「对齐」那排一致
④ 「对齐」搬到「悬浮窗颜色」正上方
⑤ 关闭字幕缓存 / 实验性功能时**不**清除字幕缓存
⑥ 「清除所有字幕缓存」改名「清除已缓存字幕」，右侧新增「清除预取字幕」
⑦ 删掉「液态玻璃默认设置」下方那行小字
⑧ 底栏那层「底部覆盖」仍在（随滚动状态出现）⇒ 彻底去掉容器
⑨ 其他卡片下方留白过多 ⇒ 卡片贴底

验什么
------
A1–A7   预览窗（窗口下标 / clipBounds / clipTop / 宽度变化重量 / 两端清裁 / 单面裁切仍成立）
B1–B6   页签（XML 40dp / 代码按常量覆盖 / 外侧半径 / 两档配色 / 卡内上内边距）
C1–C3   排版面顺序（对齐夹在行距族与悬浮窗颜色之间）
D1–D4   关开关不清缓存（两个入口 + 全仓调用点收敛）
E1–E6   缓存清理拆分（文案 / 两枚按钮 / 预取链路 action 与方法）
F1–F2   液态玻璃删小字
G1–G5   底栏去容器 + 页面贴底
H1–H5   版本纪律
I1–I4   边界（预览三层 / 语言循环 / 色板热区 / 连通组常量）

用法
----
    python verify_1030_src.py [src_root]
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
    layout_nodes = re.sub(r'<!--.*?-->', '', layout, flags=re.S)
    gradle = read(os.path.join(SRC, '..', '..', 'build.gradle'))
    module = read(jp('DlsiteSoundSubtitleModule.java'))
    protocol = read(jp('config', 'Protocol.java'))
    bus = read(jp('config', 'ConfigBus.java'))
    prefetch = read(jp('hook', 'ZiptreePrefetch.java'))

    print('=' * 60)
    print('verify_1030_src —— code 1030 设置页第四轮（源码层）')
    print('=' * 60)

    # ── A 预览窗 ──────────────────────────────────────────────────────
    print('\n── A 预览窗上下各藏一行 ──────────────────────────────────')
    check('A1 窗口下标 = 活动行 ±1（1..3），即上下各藏一行',
          re.search(r'WINDOW_FIRST\s*=\s*1\s*;', act) is not None
          and re.search(r'WINDOW_LAST\s*=\s*3\s*;', act) is not None
          and re.search(r'PREVIEW_ACTIVE_INDEX\s*=\s*2\s*;', act) is not None)
    # 【code 1031 有意改写】1031 给裁剪加了**下边界**（Rect 第四个参数不再是 full），
    #   但「按内容坐标裁上沿」这个意图不变 ⇒ 只判 Rect 存在 + 起点是算出来的 top。
    check('A2 折叠时按内容坐标裁上沿（否则露的是上一行的尾巴）',
          'mPreviewLines.setClipBounds(new Rect(0, top, w,' in act)
    clip = body(act, 'private void applyPreviewClip(float f)')
    check('A3 clipTop 按 f 线性收口（f=0 不裁、f=1 正好切在行边界）',
          'int top = Math.round(mPreviewClipTop * f);' in clip)
    # 【code 1031 有意改写】1031 把窗口几何重写成「第 FIRST 行顶 / LAST 行底」两个真实边界，
    #   clipTop 直接取 winTop（不再是 before + padTop 的累加式）。意图等价：裁的就是第 1 行顶边。
    check('A4 clipTop 的取值 = 第 FIRST 行顶边',
          'mPreviewClipTop = winTop;' in body(
              act, 'private void refreshPreviewMetrics()'))
    metrics = body(act, 'private void refreshPreviewMetrics()')
    # 【code 1031 有意改写】1031 的有效性判据简化为「full > 0 且 0 < 窗口净高 < full」——
    #   窗口高现在天然就是两个边界的差，不再需要额外校验 clipTop+win 越界。
    check('A5 度量有效性：窗口净高必须严格小于五行全高',
          'mPreviewMetricsValid = full > 0 && mPreviewWinH > 0 && mPreviewWinH < full;' in metrics)
    bind = body(act, 'private void bindViews(')
    check('A6 宽度一变就重量（英文换行数变了，三行窗口高度必须跟着变）',
          'mPreviewLines.addOnLayoutChangeListener' in bind
          and 'w == mPreviewMeasuredW' in bind
          and 'refreshPreviewMetrics();' in bind)
    frac = body(act, 'private void applyPreviewFraction(float f)')
    check('A7 单面裁切仍成立：位移 + 高度插值 + f<=0 清裁',
          'mPreviewLines.setTranslationY(-mPreviewWinDy * f);' in frac
          and 'Math.round(mPreviewFullH + (mPreviewWinH - mPreviewFullH) * f)' in frac
          and 'mPreviewLines.setClipBounds(null);' in frac)

    # ── B 页签与对齐统一 ──────────────────────────────────────────────
    print('\n── B 页签高度 / 配色 / 卡内上内边距 ──────────────────────')
    check('B1 布局里页签组高 40dp（= 对齐那排）',
          re.search(r'android:id="@\+id/appearance_tabs"[\s\S]{0,300}?'
                    r'android:layout_height="40dp"', layout_nodes) is not None)
    tabs = body(act, 'private void buildAppearanceTabs()')
    check('B2 代码按 dp(CONTROL_H_DP) 覆盖高度（两排不会走散）',
          'mAppearanceTabs.getLayoutParams().height = dp(CONTROL_H_DP);' in tabs)
    check('B3 页签外侧半径 = 组高一半（与对齐同一个表达式）',
          'connectedShape(i, labels.length, CONTROL_H_DP / 2f)' in tabs)
    pages = body(act, 'private void selectAppearancePage(int page)')
    check('B4 已选 = 深重点色（colorPrimary / colorOnPrimary）',
          'R.attr.colorPrimary' in pages and 'R.attr.colorOnPrimary' in pages)
    check('B5 未选 = 浅重点色（colorSecondaryContainer / onSecondaryContainer）',
          'R.attr.colorSecondaryContainer' in pages
          and 'R.attr.colorOnSecondaryContainer' in pages
          and 'colorSurfaceContainer' not in pages)
    # 【code 1031 有意改写】1031 把四张卡内距统一成 10dp（Ari：「四张卡内上下距离不一致」），
    #   1030 的 16dp 特例被推翻 —— 这里守「卡内上内边距与另外三张同值」这个意图。
    # 【code 1032 有意改写】1031 的口径是「外观卡与另外三张卡同值 10dp」；
    # 1032 起 Ari 第 7 条要求「页签离卡片上端太近」⇒ card_main 单独抬到 16dp，
    # 另外三张卡仍是 10dp。两条一起判：既守住 16，也守住「只改了这一张」。
    # 【code 1033 有意改写】16 → 24dp（Ari「三个按钮离上边距再远一点」）。
    #   判据意图不变：只抬 card_main，另三张卡仍是 10dp。
    check('B6 外观卡内上内边距 1033 起为 24dp（另三张卡仍是 10dp）',
          re.search(r'android:id="@\+id/card_main"[\s\S]{0,900}?'
                    r'android:paddingTop="24dp"', layout_nodes) is not None
          and layout_nodes.count('android:paddingTop="10dp"') == 4)

    # ── C 排版面顺序 ──────────────────────────────────────────────────
    print('\n── C 对齐搬到悬浮窗颜色上方 ──────────────────────────────')
    typo = body(act, 'private void buildTypoGroup(')
    aligns = [m.start() for m in re.finditer(r'mRowAlign = addSegmentedRow', typo)]
    check('C1 对齐行只建一次', len(aligns) == 1, 'count=%d' % len(aligns))
    i_align = typo.find('mRowAlign = addSegmentedRow')
    i_line = typo.find('Strings.LINE_SPACING')
    i_wrap = typo.find('Strings.WRAP_SPACING')
    i_panel = typo.find('Strings.FLOAT_WINDOW_COLOR')
    check('C2 顺序 = 行距 → 换行额外行距 → 对齐 → 悬浮窗颜色',
          -1 < i_line < i_wrap < i_align < i_panel,
          'line=%d wrap=%d align=%d panel=%d' % (i_line, i_wrap, i_align, i_panel))
    check('C3 三行都还在（没有顺手丢一个）',
          'Strings.ALIGN' in typo and 'Strings.LINE_SPACING' in typo
          and 'Strings.WRAP_SPACING' in typo)

    # ── D 关开关不清缓存 ──────────────────────────────────────────────
    print('\n── D 关闭开关不再清除缓存 ────────────────────────────────')
    exp = body(act, 'private void onExperimentalToggled(boolean enabled)')
    check('D1 实验性总开关关闭时不再发清理广播',
          'sendCacheClear' not in exp and 'sendPrefetchClear' not in exp)
    check('D2 子开关关闭仍只置灰（不动数据）',
          'mDraft.subtitleCacheEnabled = false;' in exp and 'markDirty();' in exp)
    sw = body(act, 'private void onSubtitleCacheToggled(boolean enabled)')
    check('D3 字幕缓存开关翻转为纯草稿改动（体内无 clear）',
          'sendCacheClear' not in sw and 'clearAll' not in sw and 'markDirty();' in sw)
    calls = re.findall(r'ConfigBus\.sendCacheClear\(this\)', act_code)
    check('D4 全仓只剩「清除已缓存字幕」按钮会发清理（旧连带路径已拆）',
          len(calls) == 1, 'count=%d' % len(calls))

    # ── E 缓存清理拆分 ────────────────────────────────────────────────
    print('\n── E 缓存清理拆成两枚按钮 ────────────────────────────────')
    # 【code 1031 有意改写】英文标签缩成 "Clear cached"（两枚按钮并排时不再换行），
    #   中文/繁中未动 —— 只守中文那两段。
    check('E1 文案改名：清除已缓存字幕',
          'CACHE_CLEAR("清除已缓存字幕", "清除已快取字幕", "Clear cached' in strings)
    # 【code 1031 有意改写】同上，英文缩成 "Clear prefetch"。
    check('E2 新增「清除预取字幕」三语文案',
          'CACHE_CLEAR_PREFETCH("清除预取字幕", "清除預取字幕", "Clear prefetch' in strings
          and 'PREFETCH_CLEAR_DONE(' in strings)
    row = body(act, 'private void buildSubtitleCacheRow(LinearLayout parent)')
    check('E3 两枚按钮并排 + 连通组外侧 = 组高一半',
          'connectedShape(0, 2, CONTROL_H_DP / 2f)' in row
          and 'connectedShape(1, 2, CONTROL_H_DP / 2f)' in row
          and 'pp.setMarginStart(dp(GROUP_GAP_DP));' in row)
    pf = body(act, 'private void onClearPrefetchClicked()')
    check('E4 预取清理有自己的确认弹窗与广播',
          'PREFETCH_CLEAR_CONFIRM_TITLE' in pf and 'ConfigBus.sendPrefetchClear(this)' in pf
          and 'mPendingPrefetchToast = true;' in pf)
    check('E5 Protocol 新增独立 action 且进 selfCheck',
          'ACTION_SUBTITLE_PREFETCH_CLEAR =\n            ACTION_PREFIX + "SUBTITLE_PREFETCH_CLEAR"'
          in protocol
          and 'ACTION_SUBTITLE_CACHE_STATS, ACTION_SUBTITLE_PREFETCH_CLEAR,' in protocol)
    check('E6 宿主链路：常量 / 注册 / 派发 / 处理 + ZiptreePrefetch.clearAll',
          'ACTION_SUBTITLE_PREFETCH_CLEAR =\n            Protocol.ACTION_SUBTITLE_PREFETCH_CLEAR;'
          in bus
          and 'f.addAction(ACTION_SUBTITLE_PREFETCH_CLEAR);' in bus
          and 'handlePrefetchClear(c, tag);' in bus
          and 'ZiptreePrefetch.clearAll();' in bus
          and 'public static void clearAll()' in prefetch)

    # ── F 液态玻璃删小字 ──────────────────────────────────────────────
    print('\n── F 删掉「液态玻璃默认设置」下方小字 ────────────────────')
    lg = body(act, 'private void buildLiquidGlassGroup(LinearLayout parent)')
    check('F1 恢复默认走 showHint=false（按钮行自己就是末行）',
          'this::resetLiquidGlassGroup, false)' in lg)
    check('F2 体内不再引用 HINT_LIQUID_GLASS',
          'HINT_LIQUID_GLASS' not in code_only(lg))

    # ── G 底栏去容器 + 页面贴底 ───────────────────────────────────────
    print('\n── G 底栏彻底去容器 / 卡片贴底 ───────────────────────────')
    bi = layout_nodes.find('android:id="@+id/bottom_bar"')
    bar_tag = layout_nodes[layout_nodes.rfind('<', 0, bi):layout_nodes.find('>', bi)] if bi > 0 else ''
    check('G1 容器已不是 FloatingToolbarLayout',
          'floatingtoolbar.FloatingToolbarLayout' not in layout_nodes)
    check('G2 bottom_bar 是普通 LinearLayout，吸底定位不变',
          bar_tag.startswith('<LinearLayout') and 'layout_gravity="bottom|end"' in bar_tag)
    check('G3 不再挂官方样式 / 二次 inset 开关 / 自身背景',
          'Widget.Material3.FloatingToolbar' not in layout_nodes
          and 'marginBottomSystemWindowInsets' not in layout_nodes
          and 'android:background' not in bar_tag)
    check('G4 滚动区底部让位 12dp（卡片贴底，只留彩蛋那行）',
          re.search(r'android:id="@\+id/settings_scroll"[\s\S]{0,500}?'
                    r'android:paddingBottom="12dp"', layout_nodes) is not None)
    check('G5 溢出键仍自带圆形底（去掉容器后靠它自己站住）',
          'android:background="@drawable/bg_toolbar_icon"' in layout_nodes)

    # ── H 版本纪律 ────────────────────────────────────────────────────
    print('\n── H 版本纪律 ────────────────────────────────────────────')
    m_code = re.search(r'def appVersionCode\s*=\s*(\d+)', gradle)
    m_name = re.search(r"def appVersionName\s*=\s*'([^']+)'", gradle)
    m_tag = re.search(r"def appVersionTag\s*=\s*'([^']+)'", gradle)
    m_label = re.search(r"def appVersionCodeLabel\s*=\s*'([^']+)'", gradle)
    check('H1 appVersionCode >= 1030（只守下界，铁律 94）',
          m_code is not None and int(m_code.group(1)) >= 1030,
          m_code.group(1) if m_code else '未匹配')
    check('H2 label 只守形态（构建当天 ≠ 发版日，禁钉当天）',
          m_label is not None and re.match(r'^\d{4}\.\d+$', m_label.group(1)) is not None)
    check('H3 versionName == versionTag',
          m_name is not None and m_tag is not None and m_name.group(1) == m_tag.group(1))
    banner = '==== BUILD %s / code %s' % (m_name.group(1), m_code.group(1))
    check('H4 常开横幅与 gradle 动态一致（不钉字面量）',
          'XposedCompat.log("[DLsiteSoundFloat] %s");' % banner in module)
    check('H5 履历段只加不删（1029 / 1028 都在）',
          'code 1029 （' in module and 'code 1028 （' in module)

    # ── I 边界 ────────────────────────────────────────────────────────
    print('\n── I 边界（本轮不该被顺手改坏）───────────────────────────')
    check('I1 完整预览仍是三层（backdrop / panel / lines）',
          all(('android:id="@+id/preview_%s"' % k) in layout_nodes
              for k in ('backdrop', 'panel', 'lines')))
    check('I2 语言胶囊仍是循环切换（没被顺手退回弹窗）',
          'mLanguageButton.setOnClickListener(v -> cycleLanguage());' in act_code
          and 'showLanguageDialog' not in act_code)
    check('I3 色板热区仍是 48dp（未回退）',
          re.search(r'SWATCH_TOUCH_DP\s*=\s*48\s*;',
                    read(jp('ui', 'ColorSwatchRow.java'))) is not None)
    check('I4 连通组常量仍在（3dp / 8dp）',
          re.search(r'GROUP_GAP_DP\s*=\s*3\s*;', act) is not None
          and re.search(r'GROUP_INNER_RADIUS_DP\s*=\s*8\s*;', act) is not None)

    print('\n' + '=' * 60)
    if fails:
        print('FAIL %d/%d' % (len(fails), total))
        for f in fails:
            print('  - %s' % f)
        return 1
    print('PASS %d/%d' % (total, total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
