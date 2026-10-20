#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1031 / v2.3.5】设置页第五轮十项的 **源码层** 验证。

读的是**活的工作区** ⇒ 判结构与接线；版本号只守下界、label 只守形态（铁律 82/94）。

本轮十条（Ari 2026-10-19 16:25~16:41 的六张真机截图）
------------------------------------------------------------------
① 字幕 / 行态 / 排版三个页签里的选项间距不一致（排版特别挤）
② 迷你预览窗：简繁中不显示第三行，英文活动行都显示不全
③ 字幕外观 / 液态玻璃 / 实验性功能 / 其他 四张卡内上下距离不一致
④ 重新打开实验性功能后，清除字幕按钮下方出现巨大空白（重启页面才正常）
⑤ 英文模式下「清除预取字幕」按钮向下位移（英文说明也太长）
⑥ 页头副标题改为「…状态栏字幕模块」（英文可否缩短）
⑦ 桌面图标名改为 DLsiteFloat（删「设置」）
⑧ 「其他」卡片新增「桌面图标隐藏」开关，放在「调试日志」上面
⑨ 保存设置按钮太靠下，需上抬 + 四周阴影（看起来悬浮）
⑩ LSPosed 应用简介改为「…悬浮窗 & 状态栏字幕模块」/ 英文版

验什么
------
A1–A9   行距与卡片内距（常量 / XML 四卡 / 三种行的尾部空隙）
B1–B9   预览窗几何（裁剪下边界 / 净高 / 宽度兜底 / 真实坐标 / 折叠时序）
C1–C4   实验性卡片空白（高度守卫 / 引用 / 重钉 / 转可见重跑）
D1–D6   缓存按钮（等高 / 单行 / 英文缩写 / 说明压短）
E1–E7   文案与清单（副标题 / 桌面名 / 简介 / values-en / alias）
F1–F7   桌面图标隐藏（常量 / 位置 / 组件开关 / 落盘 / 提示）
G1–G4   保存栏（上抬 / 不裁剪 / 两档 elevation）
H1–H5   版本纪律
I1–I4   边界（预览三层 / 语言循环 / 色板热区 / 连通组）

用法
----
    python verify_1031_src.py [src_root]
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


def card_block(layout, resid, close_tag='</com.google.android.material.card.MaterialCardView>'):
    """按 id 取节点区块（卡片 / 普通容器通用，收尾标签可指定）。"""
    i = layout.find('android:id="@+id/%s"' % resid)
    if i < 0:
        return ''
    j = layout.find(close_tag, i)
    if j < 0:
        return ''
    return layout[i:j]


def main():
    global SRC
    SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'src', 'main')

    act = read(jp('ui', 'SettingsActivity.java'))
    act_code = code_only(act)
    strings = read(jp('ui', 'Strings.java'))
    store = read(jp('config', 'ConfigStore.java'))
    layout = read(os.path.join(SRC, 'res', 'layout', 'activity_settings.xml'))
    layout_nodes = re.sub(r'<!--.*?-->', '', layout, flags=re.S)
    manifest = read(os.path.join(SRC, 'AndroidManifest.xml'))
    gradle = read(os.path.join(SRC, '..', '..', 'build.gradle'))
    module = read(jp('DlsiteSoundSubtitleModule.java'))
    res_values = read(os.path.join(SRC, 'res', 'values', 'strings.xml'))
    en_path = os.path.join(SRC, 'res', 'values-en', 'strings.xml')
    res_en = read(en_path) if os.path.exists(en_path) else ''

    print('=' * 60)
    print('verify_1031_src —— code 1031 设置页第五轮（源码层）')
    print('=' * 60)

    # ── A 行距 / 卡内距 ────────────────────────────────────────────────
    print('\n── A 行距与四卡内距统一 ──────────────────────────────────')
    check('A1 卡片上内距常量 = 10dp',
          re.search(r'CARD_PAD_TOP_DP\s*=\s*10\s*;', act) is not None)
    check('A2 卡片下内距常量 = 10dp',
          re.search(r'CARD_PAD_BOTTOM_DP\s*=\s*10\s*;', act) is not None)
    check('A3 行间留白 9 → 12dp',
          re.search(r'ROW_SPACER_DP\s*=\s*12\s*;', act) is not None)
    # 【code 1032 有意改写】控件下空隙 6 → 4（Ari「所有卡片控件下边距改为 4」）；
    # 标签下仍是 6。两个数分开判，避免「一个改了两个一起绿」。
    check('A4 行内两个常量（标签下 6 / 控件下 4，1032 起）',
          re.search(r'ROW_LABEL_TAIL_DP\s*=\s*6\s*;', act) is not None
          and re.search(r'ROW_TAIL_GAP_DP\s*=\s*4\s*;', act) is not None)

    # 【code 1032 有意改写】card_main 的上内距 10 → 16dp：Ari 第 7 条「页签离卡片上端太近」。
    # 另外三张卡不动（它们的首项是文字，10dp 已是合适读数）。
    # 【code 1033 有意改写】16 → 24dp：Ari「三个按钮离上边距再远一点」。仍只动这一张卡。
    for resid, label, top in (('card_main', '字幕外观', 24),
                              ('card_liquidglass', '液态玻璃', 10),
                              ('card_experimental', '实验性功能', 10),
                              ('card_misc', '其他', 10)):
        seg = card_block(layout_nodes, resid)
        check('A5 卡 %s（%s）上内距 %ddp / 下内距 10dp' % (resid, label, top),
              ('android:paddingTop="%ddp"' % top) in seg
              and 'android:paddingBottom="10dp"' in seg,
              'seg len=%d' % len(seg))

    seg_row = body(act, 'private SegmentedRow addSegmentedRow(')
    check('A6 分段行：标签下走常量、轨道补 ROW_TAIL_GAP_DP',
          'dp(ROW_LABEL_TAIL_DP)' in seg_row and 'bottomMargin = dp(ROW_TAIL_GAP_DP)' in seg_row)
    seg_slider = body(act, 'private SliderRow addSliderRow(')
    check('A7 滑块行：header 之后补同一个空隙',
          'headerGap' in seg_slider and 'dp(ROW_LABEL_TAIL_DP)' in seg_slider)
    seg_color = body(act, 'int previewAlpha, boolean showChecker)')
    check('A8 色板行：标签下同常量（不再是裸 6dp）',
          'dp(ROW_LABEL_TAIL_DP)' in seg_color)
    check('A9 旧的 2dp 标签下间距已绝迹',
          'labelView.setPadding(0, 0, 0, dp(2));' not in act)

    # ── B 预览窗几何 ──────────────────────────────────────────────────
    print('\n── B 预览窗折叠几何 ──────────────────────────────────────')
    check('B1 窗口下标仍是活动行 ±1（1..3）',
          re.search(r'WINDOW_FIRST\s*=\s*1\s*;', act) is not None
          and re.search(r'WINDOW_LAST\s*=\s*3\s*;', act) is not None)
    check('B2 新增裁剪下边界字段 mPreviewClipBottom',
          'private int mPreviewClipBottom;' in act)
    m_refresh = body(act, 'private void refreshPreviewMetrics()')
    # 【code 1033 有意改写】边界来源从「getTop()/getBottom() 真实坐标」换成
    #   「从 paddingTop 起逐行累加 measuredHeight」。意图不变（仍是 FIRST 顶 / LAST 底
    #   两个边界），但累加不依赖「是否已经 layout 过」—— 真实坐标在行刚重建时全是 0，
    #   正是 Ari 第 6/8 条「预览窗自己弹回完整」的真因。
    check('B3 折叠窗口取「第 FIRST 行顶 / 第 LAST 行底」两个边界（1033 起改用累加）',
          'int winTop' in m_refresh and 'int winBottom' in m_refresh
          and 'getMeasuredHeight()' in m_refresh)
    check('B4 卡高 = 三行净高（不含容器 padding）',
          'mPreviewWinH = winBottom - winTop;' in m_refresh)
    check('B5 clip 上边界与位移同源',
          'mPreviewClipTop = winTop;' in m_refresh
          and 'mPreviewWinDy = winTop;' in m_refresh)
    check('B6 宽度兜底扣掉了 preview_lines 自己的左右 padding',
          'getPaddingLeft()' in m_refresh and 'getPaddingRight()' in m_refresh)
    # 【code 1033 有意改写】**反向**守：这个判据必须不存在。
    #   它默认「容器高度对得上 ⇒ 布局也是按这批子 View 做的」，而重建行的瞬间
    #   getHeight() 还是上一次的值、新子 View 的坐标却全是 0 ⇒ 判据为真但坐标是 (0,0)
    #   ⇒ 提前 return ⇒ 调用方把窗口弹成完整。现在改为「forceLayout + 一律累加」。
    check('B7 不再用容器高度推断排版一致性（1033 起改累加，旧判据必须消失）',
          'if (mPreviewLines.getHeight() >= full' not in m_refresh
          and 'forceLayout()' in m_refresh)
    seg_clip = body(act, 'private void applyPreviewClip(float f)')
    check('B8 裁剪下边界线性收口（不再固定 full）',
          'mPreviewClipBottom - mPreviewFullH' in seg_clip)
    check('B9 折叠动作延后到布局完成（bindViews 不再提前收）',
          'if (!mPreviewCollapsed) {\n            applyPreviewCollapsed(false, false);\n        }' in act
          and 'applyPreviewCollapsed(true, false);' in act)

    # ── C 实验性卡片空白 ──────────────────────────────────────────────
    print('\n── C 重新开启实验性功能后的大空白 ────────────────────────')
    m_pin = body(act, 'private void pinCardLastBottom(')
    # 【code 1033 有意改写】底距不再「实测后收敛」，所以也就没有「高度为 0 就放弃」
    #   这条保护了 —— 改守新事实：末行底距是**纯常量**、函数里不含任何测量。
    # 【code 1034 有意改写】pinCardLastBottom 拆成「委托 + 实现」两段（新增墨迹补偿
    #   重载），body() 只切到委托段 ⇒ 判据改为从首个声明切到常量消费点。
    _i0 = act.index('private void pinCardLastBottom(')
    _i1 = act.index('dp(CARD_LAST_GAP_DP + extraInkDp)', _i0)
    # 🔴 从**实现段**的声明起切（rindex）—— 两段之间还夹着历史 javadoc，
    #    里面有「OnGlobalLayoutListener」字样，会把纯代码判据污染成假 FAIL。
    #    常量消费由上面 index() 命中即证（切片终点就是消费点本身）。
    _i0 = act.rindex('private void pinCardLastBottom(', _i0, _i1)
    m_pin_full = act[_i0:_i1]
    check('C1 末行底距改为纯常量（1034 起含墨迹补偿重载；函数内不允许出现测量）',
          'getHeight()' not in m_pin_full and 'OnGlobalLayoutListener' not in m_pin_full)
    check('C2 新增末行引用 mExpLastRow',
          'private View mExpLastRow;' in act)
    m_repin = body(act, 'private void repinExperimentalLast()')
    check('C3 重钉前先把上一次的 bottomMargin 归零',
          'bottomMargin = 0;' in m_repin and 'pinCardLastBottom' in m_repin)
    m_vis = body(act, 'private void applyExperimentalVisibility()')
    check('C4 由 GONE 转 VISIBLE 之后 post 一次重钉',
          'wasHidden' in m_vis and 'post(this::repinExperimentalLast)' in m_vis)
    check('C5 buildExperimentalGroup 仍钉最后一行（引用已留存）',
          'mExpLastRow = parent.getChildAt(' in act)

    # ── D 缓存按钮 ────────────────────────────────────────────────────
    print('\n── D 清除缓存两枚按钮 ────────────────────────────────────')
    m_cache = body(act, 'private void buildSubtitleCacheRow(')
    check('D1 整排钉 CONTROL_H_DP（两枚等高）',
          'ViewGroup.LayoutParams.MATCH_PARENT, dp(CONTROL_H_DP))' in m_cache)
    check('D2 两枚按钮都吃满整排高度',
          m_cache.count('ViewGroup.LayoutParams.MATCH_PARENT, 1f)') == 2)
    check('D3 两枚都强制单行 + 省略号',
          m_cache.count('setSingleLine(true)') == 2
          and m_cache.count('TruncateAt.END') == 2)
    check('D4 英文标签缩成 Clear cached / Clear prefetch',
          'CACHE_CLEAR("清除已缓存字幕", "清除已快取字幕", "Clear cached")' in strings
          and 'CACHE_CLEAR_PREFETCH("清除预取字幕", "清除預取字幕", "Clear prefetch")' in strings)
    check('D5 缓存说明英文压短（Played tracks …）',
          'Played tracks are cached automatically.' in strings)
    check('D6 中文标签未被顺手改掉',
          '清除已缓存字幕' in strings and '清除预取字幕' in strings)

    # ── E 文案与清单 ──────────────────────────────────────────────────
    print('\n── E 页头 / 桌面名 / 简介 / 清单 ─────────────────────────')
    check('E1 页头副标题 = 状态栏字幕模块',
          'DLsiteSound 悬浮窗 · 状态栏字幕模块' in strings)
    check('E2 英文副标题已缩短（不再含 appearance）',
          'DLsiteSound floating window · status bar subtitles' in strings
          and 'status bar subtitle appearance' not in strings)
    check('E3 桌面图标名去掉「设置」',
          '<string name="settings_label">DLsiteFloat</string>' in res_values)
    check('E4 中文简介 = 悬浮窗 & 状态栏字幕模块',
          'DLsiteSound 悬浮窗 &amp; 状态栏字幕模块' in res_values)
    check('E5 新增 values-en 并提供英文简介',
          'DLsiteSound Floating Window &amp; Status Bar Subtitle Module' in res_en)
    check('E6 清单新增 activity-alias 指向 SettingsActivity',
          'android:name="io.github.ariinyume.dlsitesoundfloat.ui.LauncherAlias"' in manifest
          and 'android:targetActivity="io.github.ariinyume.dlsitesoundfloat.ui.SettingsActivity"' in manifest)
    # SettingsActivity 现在是自闭合 <activity ... />，所以不能靠 </activity> 取段；
    # 改成「alias 声明之前不许出现 LAUNCHER 类别」—— 那正是「两个桌面图标」的判据。
    alias_at = manifest.find('<activity-alias')
    before_alias = manifest[:alias_at] if alias_at > 0 else manifest
    check('E7 alias 之前没有 LAUNCHER 类别（否则桌面两个图标）',
          alias_at > 0 and 'android.intent.category.LAUNCHER' not in before_alias
          and manifest.count('android.intent.category.LAUNCHER') == 1)

    # ── F 桌面图标隐藏 ────────────────────────────────────────────────
    print('\n── F 桌面图标隐藏开关 ────────────────────────────────────')
    check('F1 常量 LAUNCHER_ALIAS 与清单一致',
          'io.github.ariinyume.dlsitesoundfloat.ui.LauncherAlias' in act)
    m_misc = body(act, 'private void buildMiscGroup(')
    check('F2 开关插在「调试日志」之上',
          m_misc.find('buildLauncherIconRow(parent)') > 0
          and m_misc.find('buildLauncherIconRow(parent)') < m_misc.find('buildDebugLogRow(parent)'))
    # 【code 1032 有意改写】签名由 void 改成 boolean —— 真机事故后它必须能「拒绝执行」，
    # 调用方据此把开关弹回去。
    m_hide = body(act, 'private boolean applyLauncherIconState(boolean hide)')
    check('F3 走 setComponentEnabledSetting + DONT_KILL_APP',
          'setComponentEnabledSetting' in m_hide and 'DONT_KILL_APP' in m_hide)
    check('F4 只启停 alias（不碰 SettingsActivity）',
          'new ComponentName(this, LAUNCHER_ALIAS)' in m_hide
          and 'SettingsActivity.class' not in m_hide)
    check('F5 状态相同就不写（避免图标闪一下）',
          'getComponentEnabledSetting(alias) != want' in m_hide)
    check('F6 ConfigStore 有读 / 写两个入口',
          'public boolean readHideLauncherIcon()' in store
          and 'public void saveHideLauncherIcon(boolean hide)' in store
          and 'settings_hide_launcher_icon' in store)
    check('F7 小字说明了之后从 LSPosed 进',
          'HIDE_LAUNCHER_ICON_HINT' in strings and 'LSPosed' in strings)

    # ── G 保存栏 ──────────────────────────────────────────────────────
    print('\n── G 保存按钮上抬 + 悬浮阴影 ─────────────────────────────')
    m_bar = card_block(layout_nodes, 'bottom_bar', '</LinearLayout>')
    # 【code 1032 有意改写】28 → 48dp：Ari 第 5 条「还是太靠页面下方，再往上抬一些」。
    check('G1 底栏下外边距 1032 起为 48dp',
          'android:layout_marginBottom="48dp"' in m_bar)
    check('G2 容器不再裁剪子视图（阴影才出得来）',
          'android:clipChildren="false"' in m_bar and 'android:clipToPadding="false"' in m_bar)
    m_style = body(act, 'private void styleBottomBar()')
    check('G3 保存键关掉按压动画 + 恒定 8dp 阴影',
          'mSaveButton.setStateListAnimator(null)' in m_style
          and 'mSaveButton.setElevation(dp(8))' in m_style)
    check('G4 溢出键 4dp 阴影（两枚层次不同）',
          'mOverflowButton.setElevation(dp(4))' in m_style)

    # ── H 版本 ────────────────────────────────────────────────────────
    print('\n── H 版本纪律 ────────────────────────────────────────────')
    m_code = re.search(r'def appVersionCode = (\d+)', gradle)
    m_label = re.search(r"def appVersionCodeLabel = '([^']+)'", gradle)
    m_name = re.search(r"def appVersionName = '([^']+)'", gradle)
    check('H1 versionCode >= 1031（只守下界，铁律 82）',
          m_code is not None and int(m_code.group(1)) >= 1031,
          m_code.group(1) if m_code else 'missing')
    check('H2 label 形态 ^\\d{4}\\.\\d+$（不钉当天，铁律 94）',
          m_label is not None and re.fullmatch(r'\d{4}\.\d+', m_label.group(1)) is not None,
          m_label.group(1) if m_label else 'missing')
    # 【code 1037 泛化】原钉死 2.3.5；1037 真的升到 2.4.0 ⇒ 改守「成型 + tag == name」。
    check('H3 versionName 成型且 == tag',
          m_name is not None
          and re.fullmatch(r'\d+\.\d+\.\d+', m_name.group(1)) is not None
          and re.search(r"def appVersionTag\s*=\s*'%s'" % re.escape(m_name.group(1)),
                        gradle) is not None)
    check('H4 build.gradle 有 code 1031 履历段',
          '【code 1031】' in gradle)
    check('H5 常开横幅 = BUILD 2.3.5 / code 1031',
          'BUILD 2.3.5 / code 1031' in module
          and 'BUILD 2.3.5 / code 1030' not in module)

    # ── I 边界 ────────────────────────────────────────────────────────
    print('\n── I 边界（不该被顺手改掉的）──────────────────────────────')
    check('I1 完整预览仍是三层（backdrop / panel / lines）',
          all(('android:id="@+id/preview_%s"' % k) in layout_nodes
              for k in ('backdrop', 'panel', 'lines')))
    check('I2 语言胶囊仍是循环切换（没退回弹窗）',
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
