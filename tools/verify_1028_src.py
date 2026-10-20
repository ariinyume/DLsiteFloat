#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1028 / v2.3.5】设置页第二轮审查七项（其中第 6、7 条合并）的 **源码层**验证。

读的是**活的工作区** ⇒ 判结构与接线；版本号只判本轮值，label 只守形态（铁律 82/⑬/94）。

本轮七条（Ari 2026-10-19 12:25）
--------------------------------
① 页签改名 字幕 / 行态 / 排版（悬浮窗颜色留在排版面）
② 三个不到 48dp 的可点元素补热区
③ 恢复默认挂 Snackbar 撤销（与保存同一套）
④ 字阶：页头 28sp / 节标题 16sp·onSurfaceVariant·600 / 读数 onSurface
⑤ 底栏 → FloatingToolbarLayout（脏态圆点 + 溢出）
⑥⑦ 折叠态迷你预览（三行，与完整预览同源）—— 两条指令同一件事，合并实现

验什么
------
A1–A3   页签文案与「悬浮窗颜色」位置
B1–B4   三处热区（语言胶囊 / 恢复默认 / 页签组）
C1–C4   恢复默认撤销（四个入口 + 只回滚草稿）
D1–D6   字阶（页头 / 节标题样式 / 600 / 读数 / 重置标签）
E1–E9   浮动工具条（结构 / 脏态 / 溢出 / 让位 / 不再刷底色）
F1–F6   迷你预览（结构 / 三行下标 / 同源 / 高度参与动画）
G1–G6   版本纪律
H1–H3   边界（预览三层 / 色板未回退 / 三条重置仍独立）

用法
----
    python verify_1028_src.py [src_root]
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
    """读源码：先归一化行尾（铁律 58/106）。"""
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


def main():
    global SRC
    SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'src', 'main')

    act = read(jp('ui', 'SettingsActivity.java'))
    strings = read(jp('ui', 'Strings.java'))
    layout = read(os.path.join(SRC, 'res', 'layout', 'activity_settings.xml'))
    themes = read(os.path.join(SRC, 'res', 'values', 'themes.xml'))
    gradle = read(os.path.join(SRC, '..', '..', 'build.gradle'))
    module = read(jp('DlsiteSoundSubtitleModule.java'))

    # ── A 页签语义 ────────────────────────────────────────────────────
    print('\n── A 页签改名 ────────────────────────────────────────────')
    check('A1 TAB_COLOR 三语改「字幕 / 字幕 / Subtitles」',
          'TAB_COLOR("字幕", "字幕", "Subtitles")' in strings)
    check('A2 行态 / 排版两段文案未动',
          'TAB_LINE_STATE("行态", "行態", "Lines")' in strings
          and 'TAB_TYPE("排版", "排版", "Layout")' in strings)
    main_g = body(act, 'private void buildMainGroup(')
    typo_g = body(act, 'private void buildTypoGroup(')
    check('A3 悬浮窗颜色**仍留在排版面**（Ari 明确不搬）',
          'FLOAT_WINDOW_COLOR' in typo_g and 'FLOAT_WINDOW_COLOR' not in main_g)

    # ── B 热区 ────────────────────────────────────────────────────────
    print('\n── B 三个不到 48dp 的可点元素补热区 ──────────────────────')
    i = layout.find('android:id="@+id/language_button"')
    around = layout[max(0, i - 700):i]
    check('B1 语言胶囊外包 48dp 容器（胶囊本体仍是 32dp）',
          'android:layout_height="48dp"' in around
          and 'android:id="@+id/language_button"' in layout
          and layout[layout.find('android:id="@+id/language_button"'):
                     layout.find('android:id="@+id/language_button"') + 260].find(
              'android:layout_height="32dp"') > 0)
    # 【code 1030】**有意改写**：Ari 要求页签高度与「对齐」那排一致（40dp），
    #   48dp 这一版被明确推翻 ⇒ 本条判据跟着改成 40dp（真值仍由代码按 CONTROL_H_DP 覆盖）。
    check('B2 外观页签组 = 对齐那排的高度（1030 起为 40dp）',
          re.search(r'android:id="@\+id/appearance_tabs"[\s\S]{0,300}?'
                    r'android:layout_height="40dp"', layout) is not None)
    reset_m = body(act, 'boolean showHint) {')
    check('B3 恢复默认胶囊挂上 attachExpandedTouchTarget',
          'attachExpandedTouchTarget(root, reset);' in reset_m)
    touch_m = body(act, 'private void attachExpandedTouchTarget(')
    check('B4 真用 TouchDelegate 且四向各扩 8dp（32 → 48）',
          'new TouchDelegate(r, target)' in touch_m
          and 'int grow = dp(8);' in touch_m
          and 'r.left - grow' in touch_m and 'r.bottom + grow' in touch_m)

    # ── C 撤销 ────────────────────────────────────────────────────────
    print('\n── C 恢复默认挂撤销 ──────────────────────────────────────')
    check('C1 三条重置各自先留一眼快照',
          all('final SubtitleConfig before = mDraft.copy();' in body(act, h)
              for h in ('private void onResetMain(', 'private void onResetInactive(',
                        'private void onResetTypo(')))
    check('C2 液态玻璃重置同样留快照（第四处入口不漏）',
          'final SubtitleConfig before = mDraft.copy();' in body(
              act, 'private void resetLiquidGlassGroup('))
    snack_m = body(act, 'private void snackResetUndo(')
    check('C3 回执走同一套 snack(msg, UNDO, action)',
          'snack(Strings.RESET_DONE.get(mLang), Strings.UNDO.get(mLang)' in snack_m)
    undo_m = body(act, 'private void undoReset(')
    check('C4 撤销只回滚草稿（不写 store）+ 回灌控件',
          'mDraft = before.copy();' in undo_m and 'syncWidgets();' in undo_m
          and 'mStore.save' not in undo_m)

    # ── D 字阶 ────────────────────────────────────────────────────────
    print('\n── D 字阶与配色 ──────────────────────────────────────────')
    check('D1 页头 26 → 28sp',
          re.search(r'android:id="@\+id/header_title"[\s\S]{0,300}?'
                    r'android:textSize="28sp"', layout) is not None)
    msec = re.search(r'<style name="TextAppearance\.DLsiteFloat\.SectionTitle"[^>]*>(.*?)</style>',
                     themes, re.S)
    sec = msec.group(1) if msec else ''
    check('D2 节标题样式 16sp / onSurfaceVariant / 非 bold',
          '16sp' in sec and '?attr/colorOnSurfaceVariant' in sec
          and '<item name="android:textStyle">normal</item>' in sec)
    check('D3 五个节标题全部改用该样式',
          layout.count('@style/TextAppearance.DLsiteFloat.SectionTitle') >= 5,
          'count=%d' % layout.count('@style/TextAppearance.DLsiteFloat.SectionTitle'))
    tf = body(act, 'private void applySectionTitleTypeface(')
    check('D4 600 字重落地（API 28+ Typeface.create(…,600,…) / 旧版 sans-serif-medium）',
          'Typeface.create(tv.getTypeface(), 600, false)' in tf
          and 'sans-serif-medium' in tf)
    slider = body(act, 'private SliderRow addSliderRow(')
    check('D5 滑块读数 primary → onSurface',
          'R.attr.colorOnSurface' in slider and 'R.attr.colorPrimary' not in slider)
    check('D6 重置标签 primary → onSurfaceVariant',
          'colorOnSurfaceVariant' in reset_m and 'colorPrimary' not in reset_m)

    # ── E 浮动工具条 ──────────────────────────────────────────────────
    print('\n── E 底栏 → FloatingToolbarLayout ────────────────────────')
    # 【code 1030】**有意改写**：底栏容器已换成普通 LinearLayout（那条「底部覆盖」
    #   在真机上随滚动状态复现，清属性管不住，见 verify_1029_src 的 C 段说明）。
    #   本条只守「浮起、不占高度、id 不变」这三件当年就定下来的事。
    check('E1 底栏仍是浮起容器（不占高度）且 id 仍是 bottom_bar',
          'android:id="@+id/bottom_bar"' in layout
          and 'layout_gravity="bottom|end"' in layout)
    # 【code 1030】**有意改写**：不再有官方样式，也就没有「二次 inset」要关；
    #   insets 统一由根布局处理。本条改守「底栏自身无样式 / 无背景」。
    # 注释里正好在解释「为什么不用 FloatingToolbarLayout」⇒ 必须剥掉注释再判，
    # 否则判据会被自己的说明文字打死（1029 B 段同一坑）。
    layout_nodes = re.sub(r'<!--.*?-->', '', layout, flags=re.S)
    bi = layout_nodes.find('android:id="@+id/bottom_bar"')
    seg = layout_nodes[max(0, bi - 400):bi + 600]
    check('E2 底栏不再挂 FloatingToolbar 样式、自身无背景',
          'Widget.Material3.FloatingToolbar' not in seg
          and 'marginBottomSystemWindowInsets' not in seg
          and 'android:background=' not in seg)
    check('E3 工具条四件：脏点 / 读数 / 溢出 / 保存',
          all(('android:id="@+id/%s"' % k) in layout
              for k in ('dirty_dot', 'dirty_label', 'overflow_button', 'save_button')))
    check('E4 旧的 restart_button 已从布局与代码里消失',
          'restart_button' not in layout and 'mRestartButton' not in act)
    # 【code 1030】**有意改写**：底栏不再占高度 ⇒ 96dp 的让位变成纯空白（Ari 第 9 条
    #   「其他卡片下方留白过多」），收到 12dp，只给彩蛋那一行留位置。
    check('E5 滚动区底部让位 = 12dp（1030 起；卡片贴底）',
          re.search(r'android:id="@\+id/settings_scroll"[\s\S]{0,400}?'
                    r'android:paddingBottom="12dp"', layout) is not None)
    savebar = body(act, 'private void updateSaveBar(')
    check('E6 updateSaveBar 驱动圆点与读数（脏时才显示）',
          'mDirtyDot.setVisibility' in savebar and 'mDirtyLabel.setText' in savebar
          and 'UNSAVED_COUNT' in savebar)
    dcnt = body(act, 'private int dirtySectionCount(')
    check('E7 分区统计覆盖五组（字幕/行态/排版/液态玻璃/其他）',
          dcnt.count('n++;') >= 5
          and 'floatWindowColor' in dcnt and 'liquidGlassBackdropLum' in dcnt
          and 'experimentalEnabled' in dcnt)
    mark = body(act, 'private void markDirty(')
    check('E8 markDirty 与 doSave 都刷新工具条',
          'updateSaveBar();' in mark and 'updateSaveBar();' in body(act, 'private void doSave('))
    ov = body(act, 'private void showOverflowMenu(')
    # 【code 1033 有意改写】系统 PopupMenu 换成自绘 PopupWindow：Ari 第 5 条要求
    #   「弹窗往按钮上面走 + M3E 圆角」，而 PopupMenu 的方向与圆角都由 framework 决定。
    #   判据意图不变：溢出菜单里承载「重启系统界面」，点了要能进确认流程。
    check('E9 溢出菜单承载「重启系统界面」',
          'new PopupWindow(' in ov and 'RESTART_SYSUI' in ov
          and 'confirmRestartSystemUi()' in ov)
    page = body(act, 'private void applyPageBackground(')
    check('E10 不再给工具条刷页面底色（否则圆角背景被整块覆盖）',
          '\n        setBg(mBottomBar' not in page)

    # ── F 折叠态（**1029 口径**：单面裁切，不再有第二个视图）──────────
    # 🔴 本节判据**有意改写**：1028 的 preview_mini 已被 1029 删除 ——
    #    Ari 反馈「收起是百叶窗效果」（两张几乎一样的画面逐帧交叉淡入）。
    #    折叠态现在 = 同一张 preview_card 收到三行实测高，所以 F1–F6 判的是新事实，
    #    不是把旧判据放宽（旧事实已不存在，放宽等于永远绿）。
    print('\n── F 折叠态单面裁切（1029 口径）────────────────────────────')
    nodes = re.sub(r'<!--.*?-->', '', layout, flags=re.S)
    check('F1 布局里已无 preview_mini（折叠不再有第二个视图）',
          'preview_mini' not in nodes)
    check('F2 折叠窗口下标 1..3（非活动 / 活动 / 非活动）',
          re.search(r'WINDOW_FIRST\s*=\s*1\s*;', act) is not None
          and re.search(r'WINDOW_LAST\s*=\s*3\s*;', act) is not None)
    upd = body(act, 'private void updatePreview(')
    check('F3 行被重建后按当前折叠态重贴高度（字号变化不会停在旧高度）',
          'mPreviewMetricsValid = false;' in upd and 'applyPreviewFraction(' in upd)
    check('F4 折叠态与完整预览同源（仍是同一批 stylePreviewLine 画的行）',
          'stylePreviewLine(tv, st, sizeSp, color, alpha, active);' in upd)
    coll = body(act, 'private void applyPreviewCollapsed(')
    check('F5 收起与展开双向走同一条高度动画（不再有第二张画面参与）',
          'ValueAnimator.ofFloat(mPreviewFraction, target)' in coll)
    check('F6 量的是真实高度（不写死 88/90）',
          'View.MeasureSpec.UNSPECIFIED' in body(act, 'private void refreshPreviewMetrics('))

    # ── G 版本纪律 ────────────────────────────────────────────────────
    print('\n── G 版本纪律 ───────────────────────────────────────────')
    # 【铁律 82/⑬】源码层读的是**活的工作区** ⇒ 版本号只守下界，不钉本轮具体值
    m_code = re.search(r'def appVersionCode\s*=\s*(\d+)', gradle)
    check('G1 versionCode ≥ 1028（本轮基线）',
          m_code is not None and int(m_code.group(1)) >= 1028)
# 【code 1037 泛化】原钉死 2.3.5 —— 1037 是**第一次真正升语义版本号**（2.3.5 → 2.4.0），
#   这类「本轮当时的不变量」在源码层脚本里必须收成形态（铁律 82）：守
#   「name 成型 + tag == name（tag 进 APK 文件名）」这两条真正的不变式，不钉具体值。
    check('G2 versionName 成型且 == tag',
          re.search(r"def appVersionName\s*=\s*'(\d+\.\d+\.\d+)'", gradle) is not None
          and re.search(r"def appVersionTag\s*=\s*'%s'"
                        % re.escape(re.search(r"def appVersionName\s*=\s*'(\d+\.\d+\.\d+)'",
                                              gradle).group(1)), gradle) is not None)
    check('G3 label 形态合规（MMDD.N，N ≥ 1）',
          re.search(r"def appVersionCodeLabel\s*=\s*'(\d{4})\.([1-9]\d*)'", gradle) is not None,
          repr(re.findall(r"appVersionCodeLabel\s*=\s*'([^']*)'", gradle)))
    m = re.search(r'// 【code 1028】[^\n]*\n((?://[^\n]*\n)+)', gradle)
    hist = m.group(1) if m else ''
    check('G4 履历段自报【code 1028】并以「版本号不变 / code 升」收尾',
          bool(hist) and '2.3.5 不变' in hist and 'code 1027 升 1028' in hist,
          '履历段长度 %d' % len(hist))
    # 【铁律 82/94】横幅动态拼，不钉死某一轮的 code（否则每升一轮就假红一次）
    m_name = re.search(r"def appVersionName\s*=\s*'([^']+)'", gradle)
    want = '==== BUILD %s / code %s' % (m_name.group(1) if m_name else '?',
                                        m_code.group(1) if m_code else '?')
    banner = ''
    for ln in module.split('\n'):
        if 'XposedCompat.log' in ln and want in ln:
            banner = ln
            break
    check('G5 常开横幅与 gradle 的 versionName + code 一致（%s）' % want, bool(banner))
    check('G6 1027 的历史履历段仍在（LogGate 逐条保留，不删旧账）',
          any('==== BUILD' in ln and 'LogGate' in ln and 'code 1027' in ln
              for ln in module.split('\n')))

    # ── H 边界 ────────────────────────────────────────────────────────
    print('\n── H 边界（本轮不该被顺手改坏）──────────────────────────')
    check('H1 完整预览仍是三层（backdrop / panel / lines）',
          'android:id="@+id/preview_backdrop"' in layout
          and 'android:id="@+id/preview_panel"' in layout
          and 'android:id="@+id/preview_lines"' in layout)
    check('H2 色板热区仍是 1025 的 48dp（未回退到 34）',
          re.search(r'SWATCH_TOUCH_DP\s*=\s*48\s*;', read(jp('ui', 'ColorSwatchRow.java'))) is not None)
    check('H3 三条重置仍各管一面（没有被合并成一条）',
          all(h in act for h in ('private void resetMainValues(', 'private void resetInactiveValues(',
                                 'private void resetTypoValues(')))

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
