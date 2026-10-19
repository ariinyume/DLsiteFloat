#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1025 / v2.3.5】平台与设置页现代化（material 1.14.0 + targetSdk 36 + 签名 V1/V2/V3
+ 设计审查 P0 三项）的 **源码层**验证。
（读的是**活的工作区** ⇒ 版本号只判「本轮值」、判据只守结构与接线；见铁律 82/⑬）

本轮四件事（Ari 2026-10-18 指令）
--------------------------------
① material 1.9.0 → 1.14.0（连带 appcompat 1.7.0 / core 1.16.0，以及被依赖链逼上去的
   AGP 8.13.2 + Gradle 8.13）。
② compileSdk / targetSdk 34 → 36（Android 16），并补上 targetSdk 35+ 强制的 edge-to-edge insets。
③ 签名 V1 + V2 + V3（此前实测只有 v2）。
④ 设计审查 `DLsiteFloat_设置页_M3E设计审查.html` §06 的 P0 三项：
   行高 40→48 / 色点热区 34→48 / 色板弹性换行 / 预览窗可收起。

验什么
------
A 构建配置：SDK 档位、依赖坐标、AGP+Gradle、签名三档属性名（含「v3 没有 v3SigningEnabled」）
B edge-to-edge：insets 监听、systemBars+displayCutout、不消费 insets、系统栏明暗跟随页面底色
C P0-① 行高：ROW_MIN_H_DP=48 且旧值绝迹；CONTROL_H_DP 仍 40（证明「只改行高」）
D P0-② 色板：SWATCH_TOUCH_DP=48 / 圆点仍 22dp / 继承 ViewGroup / 自量自摆 / 换行公式
E P0-③ 预览折叠：preview_bar + chevron、scrollFlags 挂外层、持久化键、默认展开、三语文案
F 边界（**本轮不动**的东西）：页头 scroll 不 enterAlways、底栏真实占位、卡内无分隔线、
  吸顶下沿 5dp、M3E 滑块 16/4/44、语言胶囊自绘、状态卡文案三态
G 版本纪律：tag == name、code 1025、履历块口径收尾

用法
----
    python verify_1025_src.py [src_root]
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
    """读源码：先归一化行尾（铁律 58/106：工作区可能被 autocrlf 改成 CRLF）。"""
    with open(p, 'rb') as f:
        return f.read().decode('utf-8', 'replace').replace('\r\n', '\n')


def has(text, needle):
    return needle in text


def block_after(text, anchor, open_ch='{'):
    """从 anchor 起取一个花括号配平的块（源码层判据要落在**方法/类体**里，不是全文）。"""
    i = text.find(anchor)
    if i < 0:
        return ''
    j = text.find(open_ch, i)
    if j < 0:
        return ''
    depth = 0
    for k in range(j, len(text)):
        if text[k] == open_ch:
            depth += 1
        elif text[k] == '}':
            depth -= 1
            if depth == 0:
                return text[i:k + 1]
    return text[i:]


def strip_comments(text):
    """去掉 // 与 /* */ 注释。判「代码里有」用它；判「注释里有」必须读原文（铁律 87①）。"""
    out = []
    i = 0
    n = len(text)
    in_line = False
    in_block = False
    in_str = False
    quote = ''
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ''
        if in_line:
            if c == '\n':
                in_line = False
                out.append(c)
            i += 1
            continue
        if in_block:
            if c == '*' and nxt == '/':
                in_block = False
                i += 2
                continue
            if c == '\n':
                out.append(c)
            i += 1
            continue
        if in_str:
            out.append(c)
            if c == '\\':
                if i + 1 < n:
                    out.append(text[i + 1])
                i += 2
                continue
            if c == quote:
                in_str = False
            i += 1
            continue
        if c == '/' and nxt == '/':
            in_line = True
            i += 2
            continue
        if c == '/' and nxt == '*':
            in_block = True
            i += 2
            continue
        if c in ('"', "'"):
            in_str = True
            quote = c
            out.append(c)
            i += 1
            continue
        out.append(c)
        i += 1
    return ''.join(out)


def main():
    global SRC
    SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'src', 'main')
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    java = os.path.join(SRC, 'java', 'io', 'github', 'ariinyume', 'dlsitesoundfloat')

    def jp(rel):
        return os.path.join(java, rel)

    print('源根：%s\n' % SRC)

    gradle = read(os.path.join(repo, 'app', 'build.gradle'))
    root_gradle = read(os.path.join(repo, 'build.gradle'))
    props = read(os.path.join(repo, 'gradle.properties'))
    wrapper = read(os.path.join(repo, 'gradle', 'wrapper', 'gradle-wrapper.properties'))
    activity = read(jp('ui/SettingsActivity.java'))
    swatch = read(jp('ui/ColorSwatchRow.java'))
    strings = read(jp('ui/Strings.java'))
    store = read(jp('config/ConfigStore.java'))
    config = read(jp('config/SubtitleConfig.java'))
    layout = read(os.path.join(SRC, 'res', 'layout', 'activity_settings.xml'))
    chevron = read(os.path.join(SRC, 'res', 'drawable', 'ic_chevron_down.xml'))

    # 判「代码里有」用剥注释版；判「注释里有」用原文
    swatch_code = strip_comments(swatch)
    activity_code = strip_comments(activity)
    gradle_code = strip_comments(gradle)

    print('── A 构建配置 ──────────────────────────────────────────────')
    check('A1 compileSdk = 36', has(gradle_code, 'compileSdk 36'))
    check('A2 targetSdk = 36', has(gradle_code, 'targetSdk 36'))
    check('A3 buildToolsVersion = 36.0.0', has(gradle_code, "buildToolsVersion '36.0.0'"))
    check('A4 material 1.14.0', has(gradle_code, 'material:1.14.0'))
    check('A5 appcompat 1.7.0（显式钉）', has(gradle_code, 'appcompat:1.7.0'))
    check('A6 core 1.16.0（显式钉）', has(gradle_code, 'core:1.16.0'))
    check('A7 AGP 8.13.2', has(root_gradle, "version '8.13.2'"))
    check('A8 wrapper = gradle-8.13', has(wrapper, 'gradle-8.13-bin.zip'))
    check('A9 旧 material 1.9.0 绝迹', not has(gradle_code, 'material:1.9.0'))
    check('A10 旧 core 1.9.0 绝迹', not has(gradle_code, 'core:1.9.0'))
    check('A11 compileSdk 36 的 suppress 兜底在（toolchain 回退时不硬失败）',
          has(props, 'android.suppressUnsupportedCompileSdk=36'))

    print('\n── B 签名 V1 + V2 + V3 ──────────────────────────────────────')
    check('B1 v1SigningEnabled true（老属性名，生效的那个）',
          has(gradle_code, 'v1SigningEnabled true'))
    check('B2 v2SigningEnabled true', has(gradle_code, 'v2SigningEnabled true'))
    check('B3 enableV3Signing true（v3 只有新属性名）',
          has(gradle_code, 'enableV3Signing true'))
    check('B4 不写 v3SigningEnabled（AGP 8.13 无此方法，写了会配置期失败）',
          not has(gradle_code, 'v3SigningEnabled'))
    check('B5 buildType 显式绑定 signingConfigs.debug',
          has(gradle_code, 'signingConfig signingConfigs.debug'))

    print('\n── C edge-to-edge（targetSdk 36 的强制项）───────────────────')
    check('C1 setDecorFitsSystemWindows(false)',
          has(activity_code, 'setDecorFitsSystemWindows(getWindow(), false)'))
    check('C2 挂上 insets 监听', has(activity_code, 'setOnApplyWindowInsetsListener'))
    check('C3 覆盖 systemBars()', has(activity_code, 'WindowInsetsCompat.Type.systemBars()'))
    check('C4 覆盖 displayCutout()（横屏刘海不被切）',
          has(activity_code, 'WindowInsetsCompat.Type.displayCutout()'))
    check('C5 **不消费** insets（吞掉会破坏吸顶/滚动计算）',
          not has(activity_code, 'consumeSystemWindowInsets'))
    check('C6 applyEdgeToEdgeInsets() 在 setContentView 之后调用',
          activity.find('setContentView(R.layout.activity_settings)')
          < activity.find('applyEdgeToEdgeInsets();')
          and activity.find('applyEdgeToEdgeInsets();') > 0)
    check('C7 系统栏图标明暗按页面底色算（浅色底→深图标）',
          has(activity_code, 'setAppearanceLightStatusBars(light)')
          and has(activity_code, 'setAppearanceLightNavigationBars(light)'))
    bg = block_after(activity_code, 'private void applyPageBackground()')
    check('C8 applyPageBackground 里调了 applySystemBarAppearance()',
          has(bg, 'applySystemBarAppearance();'))

    print('\n── D P0-① 行高 40 → 48 ─────────────────────────────────────')
    check('D1 ROW_MIN_H_DP = 48', has(activity_code, 'ROW_MIN_H_DP = 48;'))
    check('D2 旧值 40 在代码层绝迹', not has(activity_code, 'ROW_MIN_H_DP = 40;'))
    check('D3 CONTROL_H_DP 仍 40（只改行高，不改控件自身高度）',
          has(activity_code, 'CONTROL_H_DP = 40;'))
    label = block_after(activity_code, 'private TextView makeRowLabel(')
    check('D4 行标签的最小高度仍以 ROW_MIN_H_DP 为唯一来源',
          has(label, 'setMinHeight(dp(ROW_MIN_H_DP))'))

    print('\n── E P0-② 色板弹性换行 ─────────────────────────────────────')
    check('E1 SWATCH_TOUCH_DP = 48', has(swatch_code, 'SWATCH_TOUCH_DP = 48;'))
    check('E2 旧值 34 在代码层绝迹', not has(swatch_code, 'SWATCH_TOUCH_DP = 34;'))
    check('E3 色点圆直径仍 22dp（格子变大、圆不变）',
          has(swatch_code, 'SWATCH_DOT_DP = 22;'))
    check('E4 格子有上限 56dp（宽屏不摊成一条线）',
          has(swatch_code, 'SWATCH_MAX_CELL_DP = 56;'))
    check('E5 不再继承 LinearLayout', not has(swatch_code, 'extends LinearLayout'))
    check('E6 改成自己量自己摆的 ViewGroup',
          has(swatch_code, 'class ColorSwatchRow extends ViewGroup'))
    check('E7 有 onMeasure', has(swatch_code, 'protected void onMeasure('))
    check('E8 有 onLayout', has(swatch_code, 'protected void onLayout('))
    check('E9 换行行数公式在位', has(swatch_code, '(count + perRow - 1) / perRow'))
    check('E10 最后一行居中对齐', has(swatch_code, '(avail - rowWidth) / 2'))
    # ⚠️ addColorRow 有**两个重载**（6 参转发壳 / 9 参真实现），按 6 参那个切块会切到转发体
    #    ⇒ 判据直接落在「构造 ColorSwatchRow 之后紧跟的 LayoutParams」这一处。
    i_row = activity_code.find('new ColorSwatchRow(this)')
    addc = activity_code[i_row:i_row + 600] if i_row >= 0 else ''
    check('E11 色板在 body 里是 MATCH_PARENT（否则换行位置会抖）',
          i_row > 0 and has(addc, 'ViewGroup.LayoutParams.MATCH_PARENT'))

    print('\n── F P0-③ 预览窗可收起 ─────────────────────────────────────')
    check('F1 布局里有 preview_bar', has(layout, 'android:id="@+id/preview_bar"'))
    check('F2 布局里有 preview_chevron', has(layout, 'android:id="@+id/preview_chevron"'))
    check('F3 预览条点击热区 ≥ 48dp', has(layout, 'android:minHeight="48dp"'))
    i_bar = layout.find('android:id="@+id/preview_bar"')
    seg = layout[i_bar:i_bar + 2200] if i_bar >= 0 else ''
    check('F4 scrollFlags(nonScroll) 挂在**外层**条上', has(seg, 'layout_scrollFlags="noScroll"'))
    i_title = layout.find('android:id="@+id/title_preview"')
    tseg = layout[i_title:i_title + 400] if i_title >= 0 else ''
    check('F5 title_preview 自身不再带 scrollFlags（挂里面会被无视）',
          i_title > 0 and not has(tseg, 'layout_scrollFlags'))
    check('F6 新图标文件存在', has(chevron, '<vector'))
    check('F7 pathData 是标准 expand_more（无非法字符）',
          has(chevron, 'M7.41,8.59L12,13.17l4.59,-4.58L18,10l-6,6 -6,-6z')
          and set(re.findall(r'[^MmLlHhVvCcSsQqTtAaZz0-9.,\-\s]',
                            ''.join(re.findall(r'pathData="([^"]*)"', chevron)))) <= set())
    check('F8 折叠方法在位', has(activity_code, 'private void applyPreviewCollapsed('))
    check('F9 展开/收起都会转箭头', has(activity_code, 'rotation(collapsed ? 180f : 0f)'))
    check('F10 收起走高度动画（下面内容不跳）', has(activity_code, 'ValueAnimator.ofInt(from, 0)'))
    check('F11 点条即落盘', has(activity_code, 'mStore.savePreviewCollapsed(mPreviewCollapsed)'))
    check('F12 进页面恢复上次状态', has(activity_code, 'mStore.readPreviewCollapsed()'))
    check('F13 ConfigStore 有读方法', has(store, 'public boolean readPreviewCollapsed()'))
    check('F14 ConfigStore 有写方法', has(store, 'public void savePreviewCollapsed(boolean collapsed)'))
    check('F15 缺省 = 展开（不给证据就不替用户收起）',
          has(store, 'getBoolean(K_PREVIEW_COLLAPSED, false)'))
    check('F16 折叠状态**不进** SubtitleConfig（配置 schema 不变）',
          not has(config, 'preview_collapsed') and not has(config, 'PREVIEW_COLLAPSED'))
    check('F17 三语文案齐（收起/展开各三语）',
          len(re.findall(r'PREVIEW_COLLAPSE\("[^"]*", "[^"]*", "[^"]*"\)', strings)) == 1
          and len(re.findall(r'PREVIEW_EXPAND\("[^"]*", "[^"]*", "[^"]*"\)', strings)) == 1)
    check('F18 读屏动作名随语言重刷', has(activity_code, 'updatePreviewBarDescription();'))

    print('\n── G 边界（本轮**不动**的东西）─────────────────────────────')
    # ⚠️ 判据只认**属性值形态**：文件头注释里大段讨论过 `scroll|enterAlways`，
    #    裸判 `'enterAlways' not in layout` 会被自己的注释判死（铁律 87① 的反面用法）。
    check('G1 页头仍 scroll（不是 scroll|enterAlways，975/976 的成果）',
          has(layout, 'app:layout_scrollFlags="scroll"')
          and not has(layout, 'layout_scrollFlags="scroll|enterAlways"'))
    check('G2 底栏仍是**真实占位**的兄弟节点（2.1.4 的成果）',
          layout.rfind('android:id="@+id/bottom_bar"')
          > layout.rfind('</androidx.coordinatorlayout.widget.CoordinatorLayout>'))
    check('G3 卡内仍无分隔线', not has(activity_code, 'setDividerDrawable')
          and not has(activity_code, 'DividerItemDecoration'))
    check('G4 吸顶下沿仍留 5dp', has(layout, 'android:paddingBottom="5dp"'))
    check('G5 M3E 滑块度量未动（16 / 4 / 44）',
          has(activity_code, 'SLIDER_TRACK_H_DP = 16;')
          and has(activity_code, 'SLIDER_THUMB_W_DP = 4;')
          and has(activity_code, 'SLIDER_THUMB_H_DP = 44;'))
    check('G6 语言胶囊仍是自绘两兄弟 View（1.1）',
          has(layout, 'android:id="@+id/language_icon"')
          and has(layout, 'android:id="@+id/language_text"'))
    check('G7 状态卡三态文案仍在', has(strings, 'MODULE_ON(')
          and has(strings, 'MODULE_OFF(') and has(strings, 'PROBING('))

    print('\n── H 版本纪律 ──────────────────────────────────────────────')
    tag = re.search(r"def appVersionTag = '([^']+)'", gradle)
    code = re.search(r'def appVersionCode = (\d+)', gradle)
    name = re.search(r"def appVersionName = '([^']+)'", gradle)
    label = re.search(r"def appVersionCodeLabel = '([^']+)'", gradle)
    check('H1 tag == name（L12：tag 决定 APK 文件名，最易漏）',
          tag and name and tag.group(1) == name.group(1),
          '%s vs %s' % (tag and tag.group(1), name and name.group(1)))
    check('H2 versionCode = 1025', code and code.group(1) == '1025')
    check('H3 label 形态 = 月日.当日第几版', label and re.fullmatch(r'\d{4}\.\d+', label.group(1)))
    # 🔴 铁律 94：label 的日期段跟「构建当天」（MMDD.当日第几版），跨日就会变
    #   ⇒ 只守**形态**，绝不钉具体字面值（1025 轮跨了 10-18 / 10-19 两天，实踩）
    check('H4 履历块按「版本号不变 / code 升」口径收尾',
          has(gradle, 'versionName 保持 2.3.5') and has(gradle, '1025、label 推到 ')
          and re.search(r"appVersionCodeLabel = '10\d\d\.\d'", gradle) is not None)
    check('H5 上一轮 code 1024 在履历里可追溯', has(gradle, '1024'))

    print('\n── I 设置页 P1/P2（设计审查 §06）────────────────────────────')
    # I1 三卡合一：只剩一张 card_main；卡内多出 appearance_tabs 与第三面
    check('I1 三卡合一：card_inactive / card_typo 两个 id 已消失',
          not has(layout, '@+id/card_inactive') and not has(layout, '@+id/card_typo')
          and not has(layout, '@+id/title_inactive') and not has(layout, '@+id/title_typo'))
    check('I1b 卡内有 tab 条 + 三个面 + 唯一重置容器',
          has(layout, '@+id/appearance_tabs') and has(layout, '@+id/group_main')
          and has(layout, '@+id/group_inactive') and has(layout, '@+id/group_typo')
          and has(layout, '@+id/group_appearance_reset'))
    check('I1c tab 三段由代码建（buildAppearanceTabs + selectAppearancePage）',
          has(activity_code, 'private void buildAppearanceTabs()')
          and has(activity_code, 'private void selectAppearancePage(int page)')
          and has(activity_code, 'mAppearanceTabButtons[i] = b'))
    check('I1d 三段文案齐（颜色 / 行态 / 排版）',
          has(strings, 'TAB_COLOR(') and has(strings, 'TAB_LINE_STATE(')
          and has(strings, 'TAB_TYPE(') and has(strings, 'GROUP_APPEARANCE('))
    check('I1e 切面**零重建**（只改可见性，不调 buildRows）',
          'buildRows()' not in block_after(activity_code, 'private void selectAppearancePage'))

    # I2 P2-2：重置只关联单卡片（三组共用一条，且只弹一次提示）
    # ⚠️ 只判「三张卡各自的那三条」消失；**液态玻璃卡的重置必须保留**
    #    （它也是「重置只作用于本卡」，正是 P2-2 要的形态）。
    check('I2 三张卡各自的重置行已移除（字面 RESET_MAIN/INACTIVE/TYPO 不再上屏）',
          not has(activity_code, 'Strings.RESET_MAIN,')
          and not has(activity_code, 'Strings.RESET_INACTIVE,')
          and not has(activity_code, 'Strings.RESET_TYPO,')
          and has(activity_code, 'addResetRow(mGroupAppearanceReset'))
    check('I2b 重置三组共用一条，且 sync/提示只做一次',
          has(activity_code, 'private void resetAppearanceGroup()')
          and has(activity_code, 'resetMainValues();')
          and has(activity_code, 'resetInactiveValues();')
          and has(activity_code, 'resetTypoValues();'))
    check('I2c 不做预设 chips（本轮 Ari 明确排除）',
          not has(strings, 'PRESET_') and not has(layout, 'chip'))

    # I3 P1-2：行头（icon + supporting）
    check('I3 行头原语存在且被 5 个行构建器共用',
          has(activity_code, 'private RowHead makeRowHead(Strings label)')
          and activity_code.count('makeRowHead(label)') >= 5)
    check('I3b 图标按行查表（不是逐调用点传参）',
          has(activity_code, 'private int iconForRow(Strings label)')
          and has(activity_code, 'private Strings supportingForRow(Strings label)'))
    icon_dir = os.path.join(SRC, 'res', 'drawable')
    icons = [n for n in os.listdir(icon_dir) if n.startswith('ic_ui_') and n.endswith('.xml')]
    check('I3c 新增 14 枚行图标全部存在', len(icons) == 14, '实际 %d' % len(icons))
    bad_v = []
    for n in icons:
        txt = read(os.path.join(icon_dir, n))
        if 'android:pathData=' not in txt or '<vector' not in txt:
            bad_v.append(n)
    check('I3d 每枚图标都有 vector + pathData', not bad_v, ','.join(bad_v))
    check('I3e 副标题只给需要区分的行（5 条）',
          has(strings, 'SUP_SHADOW_STRENGTH(') and has(strings, 'SUP_SHADOW_RADIUS(')
          and has(strings, 'SUP_LINE_SPACING(') and has(strings, 'SUP_WRAP_SPACING(')
          and has(strings, 'SUP_BLUR_RADIUS('))

    # I4 P1-3：状态卡降噪
    status_body = block_after(activity_code, 'private void renderStatusCard()')
    check('I4 状态卡不再用四色整卡（primary/surfaceVariant 两枝已收掉）',
          'colorPrimaryContainer' not in status_body
          and 'colorSurfaceVariant, 0xFFE7E0EC' not in status_body)
    check('I4b 错误态仍是唯一整卡着色（errorContainer 保留）',
          'colorErrorContainer' in status_body)
    check('I4c 已激活/探测中走中性底 + 有色状态点',
          'cardBgColor()' in status_body and 'mStatusIcon.setColorFilter(accent)' in status_body)

    # I5 P2-1：Snackbar + 可撤销
    toast_body = block_after(activity_code, 'private void toast(String msg)')
    snack_body = block_after(activity_code, 'private void snack(String msg')
    check('I5 回执统一出口是 Snackbar（Toast 只作极端兜底）',
          'snack(msg, null, null)' in toast_body and 'Snackbar.make' in snack_body)
    check('I5b 保存成功带「撤销」动作',
          has(activity_code, 'private void undoLastSave(SubtitleConfig before)')
          and has(activity_code, 'Strings.UNDO.get(mLang)'))
    check('I5c Snackbar 补了导航栏内边距（targetSdk 36 edge-to-edge）',
          'navigationBars()).bottom' in snack_body)

    # I6 P2-3：联动显隐动效
    check('I6 联动显隐走统一动效入口',
          has(activity_code, 'private void animateRowVisibility(')
          and has(activity_code, 'private static AutoTransition rowTransition()'))
    # ⚠️ 只在**开关回调**里要求走动效；syncWidgets 回灌草稿值时仍直接 setVisibility
    #    （那里每次都同步，走动效反而会在进页面时闪一下）。
    inactive_body = block_after(activity_code, 'private void buildInactiveGroup(')
    check('I6b 口子仍是 GONE（不是置灰），两处开关联动都已改调用',
          'animateRowVisibility(parent, mRowBlurRadius.root, v)' in inactive_body
          and 'animateRowVisibility(parent, mRowInactiveScalePct.root, v)' in inactive_body
          and 'mRowBlurRadius.root.setVisibility(' not in inactive_body
          and 'mRowInactiveScalePct.root.setVisibility(' not in inactive_body)
    check('I6c syncWidgets 回灌仍直设（不产生入场动画）',
          'mRowBlurRadius.root.setVisibility(' in activity_code)

    # I7 P1-5 判据修正（本轮同时修）
    check('I7 P1-5 观测改用纯自算行（不再是屏上镜像）',
          has(activity_code, 'HostLineSync.observe(r.liveLines, repo.selfComputedLines())')
          or has(read(os.path.join(SRC, 'java', 'io', 'github', 'ariinyume',
                                   'dlsitesoundfloat', 'hook', 'SubtitleViewHook.java')),
                 'repo.selfComputedLines()'))
    # I8 横幅自报本轮三项 —— 横幅是普通字符串字面量、整段进 dex 串池，
    #    内容不全会造成「发了版，日志里却读不出这版改了什么」。
    module = read(os.path.join(SRC, 'java', 'io', 'github', 'ariinyume',
                               'dlsitesoundfloat', 'DlsiteSoundSubtitleModule.java'))
    banner_line = ''
    for ln in module.split('\n'):
        if '==== BUILD' in ln and 'LogGate' in ln:
            banner_line = ln
            break
    check('I8 常开横幅自报设置页 P1/P2 与观测判据修正',
          banner_line != ''
          and '⑫设置页 P1 三项' in banner_line
          and '⑬设置页 P2 三项' in banner_line
          and '⑭上屏行观测判据修正' in banner_line)
    # 禁字符：正文里出现引号 / 反斜杠 / 反引号都会把整条字符串截断或转义
    banner_body = (banner_line[banner_line.index('"') + 1:banner_line.rindex('"')]
                   if banner_line else '')
    check('I8b 横幅正文无禁用字符（引号 / 反斜杠 / 反引号）',
          banner_body != '' and '"' not in banner_body
          and '\\' not in banner_body and '`' not in banner_body)

    print('\n──────────────────────────────────────────────────────────')
    if fails:
        print('FAIL %d / %d' % (len(fails), total))
        for f in fails:
            print('  · %s' % f)
        return 1
    print('PASS %d / %d' % (total, total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
