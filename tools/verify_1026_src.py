#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1026 / v2.3.5】删「跟随宿主字幕样式」+ 三张色板去掉红与蓝 的 **源码层**验证。
（读的是**活的工作区** ⇒ 只判结构与接线，版本号只判「本轮值」；见铁律 82/⑬）

本轮两件事（Ari 2026-10-19 指令）
--------------------------------
① 删除「跟随宿主字幕样式」（code 1024 的 P1-7）—— 从配置键到设置页开关、从抓屏采样
   到绘制参数分支，整条链路摘掉，不留半截。
② 主字幕 / 阴影 / 悬浮窗三张色板各删「红」与「蓝」：8 → 6。
   旧配置里存着红/蓝**不迁移** —— 色板行末的自定义色环会接住它们。

验什么
------
J1–J12  删除完整性（文件 / 类名 / 键 / 字段 / 读取口 / 采样 / 重载 / 常量 / 开关行 / 图标）
J13–J17 色板：两张表各 6 项、红蓝绝迹、顺序不变、自定义色环仍在
J18–J22 版本纪律：code 1026、label 形态、履历块收尾、横幅自报、横幅禁字符
K1–K4   边界（本轮**不动**的东西）：三卡合一 / 行头原语 / 纯自算行 / 液态玻璃自带重置

用法
----
    python verify_1026_src.py [src_root]
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


def _one_call(src, handler, resetter):
    """判 handler 方法体里只调用了指定的 resetter（不越界到别的面）。"""
    i = src.find('private void %s()' % handler)
    if i < 0:
        return False
    j = src.find('    }\n', i)
    body = src[i:j if j > 0 else i + 400]
    others = [r for r in ('resetMainValues', 'resetInactiveValues', 'resetTypoValues')
              if r != resetter and r + '();' in body]
    return resetter + '();' in body and not others


def jp(rel):
    return os.path.join(SRC, 'java', 'io', 'github', 'ariinyume', 'dlsitesoundfloat',
                        rel.replace('/', os.sep))


def method_body(text, signature, end='\n    }'):
    """按方法签名切片（**锚在声明位**：签名后必须紧跟 `{`，避免先命中调用点）。"""
    i = text.find(signature + ' {')
    if i < 0:
        return ''
    j = text.find(end, i)
    return '' if j < 0 else text[i:j]


def palette_items(body):
    return re.findall(r'color\(R\.color\.(swatch_[a-z_]+)\)', body)


def main():
    global SRC
    SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'src', 'main')

    print('源码根：%s\n' % SRC)

    pkg = os.path.join(SRC, 'java', 'io', 'github', 'ariinyume', 'dlsitesoundfloat')
    # 全量 java 原文（含注释）—— 判「删除」必须连注释一起干净，残留注释会误导后来人
    all_java = {}
    for root, _dirs, files in os.walk(pkg):
        for fn in files:
            if fn.endswith('.java'):
                p = os.path.join(root, fn)
                all_java[os.path.relpath(p, pkg).replace(os.sep, '/')] = read(p)
    joined = '\n'.join(all_java.values())

    print('── J 删除完整性 ────────────────────────────────────────────')
    check('J1 util/HostStyleProbe.java 已删除',
          'util/HostStyleProbe.java' not in all_java,
          '仍存在：%s' % list(all_java)[:3])
    check('J2 全仓 Java 无 HostStyleProbe 字样（含注释）',
          'HostStyleProbe' not in joined)
    check('J3 全仓 Java 无 followHostStyle 字样', 'followHostStyle' not in joined)
    check('J4 全仓 Java 无 K_FOLLOW_HOST_STYLE 常量', 'K_FOLLOW_HOST_STYLE' not in joined)

    strings = all_java.get('ui/Strings.java', '')
    check('J5 三语文案「跟随宿主」全部摘除',
          'FOLLOW_HOST_STYLE' not in strings
          and '跟随宿主' not in strings and '跟隨宿主' not in strings
          and 'Follow host' not in strings)

    cfg = all_java.get('config/SubtitleConfig.java', '')
    check('J6 配置键 follow_host_style 已删（键名与字段都不在）',
          'follow_host_style' not in cfg and 'followHostStyle' not in cfg)

    style = all_java.get('view/SubtitleStyle.java', '')
    ctors = re.findall(r'private SubtitleStyle\(', style)
    check('J7 SubtitleStyle 只剩一个构造函数（宿主样式重载已删）', len(ctors) == 1,
          '构造函数 %d 个' % len(ctors))
    check('J8 SubtitleStyle 无宿主字号夹取常量（HOST_SIZE_*）',
          'HOST_SIZE_MIN_SP' not in style and 'HOST_SIZE_MAX_SP' not in style)

    fview = all_java.get('view/FloatingSubtitleView.java', '')
    check('J9 悬浮窗无 styleHostRev，buildStyle 只剩一条路',
          'styleHostRev' not in fview
          and 'private SubtitleStyle buildStyle()' in fview
          and 'SubtitleStyle.of(cfg, dm, ' not in fview
          and 'return SubtitleStyle.of(' in fview)

    view = all_java.get('hook/SubtitleViewHook.java', '')
    check('J10 抓屏侧不再采样宿主样式（无 offer 调用）',
          'HostStyleProbe' not in view and '.offer(' not in view)

    act = all_java.get('ui/SettingsActivity.java', '')
    check('J11 设置页开关行与其回调已删',
          'mRowFollowHost' not in act and 'onFollowHostStyleToggled' not in act)
    check('J12 只为它画的 ic_ui_sync 已删且无引用',
          not os.path.isfile(os.path.join(SRC, 'res', 'drawable', 'ic_ui_sync.xml'))
          and 'ic_ui_sync' not in act)

    print('\n── J 色板（三行各删红蓝）──────────────────────────────────')
    common = method_body(act, 'private int[] commonPalette()')
    common_names = method_body(act, 'private String[] commonPaletteNames()')
    panel = method_body(act, 'private int[] panelPalette()')
    panel_names = method_body(act, 'private String[] panelPaletteNames()')

    ci = palette_items(common)
    pi = palette_items(panel)
    check('J13 主字幕 / 阴影色板 = 6 项（原 8）', len(ci) == 6, '实际 %d：%s' % (len(ci), ci))
    check('J14 该表无 swatch_red / swatch_blue',
          'swatch_red' not in ci and 'swatch_blue' not in ci, str(ci))
    check('J15 顺序仍为 白/黑/绿/橙/青/紫',
          ci == ['swatch_white', 'swatch_black', 'swatch_green',
                 'swatch_orange', 'swatch_cyan', 'swatch_purple'], str(ci))
    check('J16 名称表与色值表一一对应（6 项）',
          len(re.findall(r'Strings\.COLOR_[A-Z_]+\.get\(mLang\)', common_names)) == 6)
    check('J17 悬浮窗色板 = 6 项、首项仍是深蓝黑、无红蓝',
          len(pi) == 6 and pi[0] == 'swatch_deep_blue_black'
          and 'swatch_red' not in pi and 'swatch_blue' not in pi, str(pi))
    check('J18 悬浮窗名称表 6 项',
          len(re.findall(r'Strings\.COLOR_[A-Z_]+\.get\(mLang\)', panel_names)) == 6)
    # 旧配置兜底：值不在预设表里 ⇒ 点亮行末的自定义色环（不是「无选中」）
    check('J19 自定义色环兜底仍在（setCustomEntry + setCustomSelected(!containsColor)）',
          'row.setCustomEntry(' in act
          and re.search(r'row\.setCustomSelected\(!containsColor\(colors, initial\)\)', act) is not None)

    print('\n── M 恢复默认拆回三条（同日补改）──────────────────────────')
    check('M1 三条文案齐（颜色 / 行态 / 排版）',
          'RESET_MAIN("恢复字幕颜色默认设置"' in strings
          and 'RESET_INACTIVE("恢复行态默认设置"' in strings
          and 'RESET_TYPO("恢复字幕排版默认设置"' in strings)
    check('M2 合并入口与统一容器都已删除',
          'resetAppearanceGroup' not in act and 'mGroupAppearanceReset' not in act
          and 'group_appearance_reset' not in act)
    layout = read(os.path.join(SRC, 'res', 'layout', 'activity_settings.xml'))
    check('M3 布局里不再有统一重置容器',
          'group_appearance_reset' not in layout
          and '@+id/group_main' in layout and '@+id/group_typo' in layout)
    check('M4 三条重置各自只调自己那一组（互不越界）',
          _one_call(act, 'onResetMain', 'resetMainValues')
          and _one_call(act, 'onResetInactive', 'resetInactiveValues')
          and _one_call(act, 'onResetTypo', 'resetTypoValues'))
    check('M5 三条都走「无小字」档（showHint = false）',
          act.count('this::onResetMain, false') == 1
          and act.count('this::onResetInactive, false') == 1
          and act.count('this::onResetTypo, false') == 1)
    check('M6 解释小字（HINT_MAIN / HINT_INACTIVE / HINT_TYPO / HINT_APPEARANCE）已删',
          'HINT_MAIN' not in strings and 'HINT_INACTIVE' not in strings
          and 'HINT_TYPO' not in strings and 'HINT_APPEARANCE' not in strings)
    check('M7 末行底距在切面时补（可见面才量）',
          'pinAppearanceBottom(pages[page])' in act)

    print('\n── K 版本纪律 ──────────────────────────────────────────────')
    gradle = read(os.path.join(SRC, '..', '..', 'build.gradle'))
    check('K1 versionCode = 1026', re.search(r'^def appVersionCode = 1026$', gradle, re.M) is not None)
    check('K2 versionName / tag 仍是 2.3.5（未发版不动语义版本号）',
          re.search(r"^def appVersionName = '2\.3\.5'$", gradle, re.M) is not None
          and re.search(r"^def appVersionTag = '2\.3\.5'$", gradle, re.M) is not None,
          'tag == name 必须成立（tag 进 APK 文件名）')
    # 铁律 94：label 只守形态（构建当天 MMDD.N），绝不钉死字面值
    label = re.search(r"^def appVersionCodeLabel = '(\d{4}\.\d+)'$", gradle, re.M)
    check('K3 label 形态合规（MMDD.N，不钉当天）', label is not None,
          label.group(1) if label else '未匹配')
    check('K4 履历块有【code 1026】且按「版本号不变 / code 升」收尾',
          '// 【code 1026】' in gradle and 'code 1025 升 1026' in gradle)

    module = all_java.get('DlsiteSoundSubtitleModule.java', '')
    banner = ''
    for ln in module.split('\n'):
        if '==== BUILD' in ln and 'LogGate' in ln:
            banner = ln
            break
    check('K5 常开标题行已到 code 1026',
          'XposedCompat.log("[DLsiteSoundFloat] ==== BUILD 2.3.5 / code 1026");' in module)
    check('K6 调试横幅自报本轮两项 + 未发版',
          banner != '' and '跟随宿主字幕样式' in banner
          and '色板' in banner and '未提交、未打 tag、未发版' in banner)
    body = banner[banner.index('"') + 1:banner.rindex('"')] if banner else ''
    check('K7 横幅正文无禁用字符（引号 / 反斜杠 / 反引号）',
          body != '' and '"' not in body and '\\' not in body and '`' not in body)

    print('\n── L 边界（本轮不动的东西仍完好）──────────────────────────')
    check('L1 三卡合一仍在（分段条 + 切面入口）',
          'buildAppearanceTabs' in act and 'selectAppearancePage' in act)
    check('L2 行头图元仍在（makeRowHead）', 'makeRowHead' in act)
    check('L3 纯自算行仍在（selfComputedLines 且抓屏侧接线）',
          'selfComputedLines' in all_java.get('data/SubtitleRepository.java', '')
          and 'repo.selfComputedLines()' in view)
    check('L4 液态玻璃卡自己的重置行保留',
          'addResetRow(parent, Strings.RESET_LIQUID_GLASS,' in act)

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
