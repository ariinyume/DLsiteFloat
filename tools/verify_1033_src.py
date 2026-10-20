#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1033 / v2.3.5】设置页第七轮八条的 **源码层** 验证。

对应 Ari 2026-10-19 18:51 的八条：
  ①【底部底距跳变 + 四卡不一致】→ A 节
  ②【三个页签离上端再远一点】    → B 节
  ③【删掉隐藏桌面图标下方小字】  → C 节
  ④【重启系统界面弹窗上移到按钮上方 + M3E 圆角】→ D 节
  ⑤【编辑字幕/切语言时预览窗自己弹回完整】→ E1–E5
  ⑥【连点切换时预览窗回弹】      → E6
  ⑦【版本与履历纪律】            → F 节
  ⑧【边界不许回退】              → G 节

用法
----
    python verify_1033_src.py [src_root]
退出码 0 = 全部通过
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'app', 'src', 'main')
ACT_PATH = os.path.join(SRC, 'java', 'io', 'github', 'ariinyume', 'dlsitesoundfloat',
                        'ui', 'SettingsActivity.java')
LAYOUT_PATH = os.path.join(SRC, 'res', 'layout', 'activity_settings.xml')
GRADLE_PATH = os.path.join(ROOT, 'app', 'build.gradle')
MOD_PATH = os.path.join(SRC, 'java', 'io', 'github', 'ariinyume', 'dlsitesoundfloat',
                        'DlsiteSoundSubtitleModule.java')
MANIFEST_PATH = os.path.join(SRC, 'AndroidManifest.xml')

if len(sys.argv) > 1:
    SRC = sys.argv[1]
    ACT_PATH = os.path.join(SRC, 'java', 'io', 'github', 'ariinyume', 'dlsitesoundfloat',
                            'ui', 'SettingsActivity.java')
    LAYOUT_PATH = os.path.join(SRC, 'res', 'layout', 'activity_settings.xml')
    MANIFEST_PATH = os.path.join(SRC, 'AndroidManifest.xml')

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


def skip(name, why):
    print('  SKIP  %s   %s' % (name, why))
    nodisc.append(name)


def read(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def body(src, sig):
    """从方法签名取到方法体结束（首个 4 空格缩进的 `}`）。"""
    i = src.find(sig)
    if i < 0:
        return ''
    j = src.find('\n    }', i)
    return src[i:j + 6] if j > 0 else ''


ACT = read(ACT_PATH)
LAYOUT = read(LAYOUT_PATH)
GRADLE = read(GRADLE_PATH)
MOD = read(MOD_PATH)
MANIFEST = read(MANIFEST_PATH)

# ══════════════════════════════════════════════════════════════════════
print('\n── A 卡片末行底距：纯常量、四卡一致、不再跳变（第 1 / 2 条）─────')

check('A1 CARD_LAST_GAP_DP 与 ROW_TAIL_GAP_DP 是**同一个值**（不写第二份 4）',
      re.search(r'CARD_LAST_GAP_DP\s*=\s*ROW_TAIL_GAP_DP\s*;', ACT) is not None)

pin = body(ACT, 'private void pinCardLastBottom(')
# 【code 1034 有意改写】pinCardLastBottom 增加「墨迹补偿」重载，常量消费变成
#   dp(CARD_LAST_GAP_DP + extraInkDp)（补偿量只对按钮条收尾的两卡生效）。
check('A2 末行底距取常量 CARD_LAST_GAP_DP（1034 起带墨迹补偿重载）',
      'dp(CARD_LAST_GAP_DP + extraInkDp)' in ACT)
check('A3 函数里**不再有任何测量**（这是「跳变」的根：多个 OnGlobalLayout 回调打架）',
      'OnGlobalLayoutListener' not in pin and 'getHeight()' not in pin)
check('A4 旧测量三件套已删除（topInkGapOf / topRelativeTo / findFirstTextView）',
      'topInkGapOf' not in ACT and 'topRelativeTo' not in ACT
      and 'findFirstTextView' not in ACT)
check('A5 四张卡的内层容器下内边距都是 10dp（末行 4 + 卡片 10 = 总距 14）',
      LAYOUT.count('android:paddingBottom="10dp"') == 4,
      '实际 %d 处' % LAYOUT.count('android:paddingBottom="10dp"'))
check('A6 三个外观面仍各自 pin 一次末行（切面后底距不靠测量也不会掉）',
      'pinAppearanceBottom(pages[page]);' in ACT
      and body(ACT, 'private void pinAppearanceBottom(').count('pinCardLastBottom') == 1)

# ══════════════════════════════════════════════════════════════════════
print('\n── B 三个页签离卡片上端再远一点（第 3 条）─────────────────────')

card_main = LAYOUT[LAYOUT.find('@+id/card_main'):]
card_main = card_main[:card_main.find('</com.google.android.material.card.MaterialCardView>')]
check('B1 card_main 内层 paddingTop = 24dp',
      'android:paddingTop="24dp"' in card_main)
check('B2 另外三张卡仍是 10dp（只抬了这一张）',
      LAYOUT.count('android:paddingTop="10dp"') == 4,
      '实际 %d 处' % LAYOUT.count('android:paddingTop="10dp"'))
check('B3 页签 → 首个选项的间距仍取 CARD_PAD_TOP_DP（没被顺手改掉）',
      'android:layout_marginBottom="10dp"' in card_main
      and 'dp(CARD_PAD_TOP_DP)' in body(ACT, 'private void buildAppearanceTabs('))

# ══════════════════════════════════════════════════════════════════════
print('\n── C 删掉「隐藏桌面图标」下方小字（第 4 条）───────────────────')

launcher_row = body(ACT, 'private void buildLauncherIconRow(')
check('C1 该行不再引用说明小字文案', 'HIDE_LAUNCHER_ICON_HINT' not in launcher_row)
check('C2 该行仍是「开关 + 安全绳」两件事（功能没被顺手删掉）',
      'addSwitchRow' in launcher_row and 'applyLauncherIconState(true)' in launcher_row)
check('C3 安全绳被拒时的提示仍在（小字删了，用户仍要知道发生了什么）',
      'HIDE_ICON_UNSUPPORTED' in ACT
      and 'HIDE_ICON_UNSUPPORTED(' in read(os.path.join(SRC, 'java', 'io', 'github',
                                                        'ariinyume', 'dlsitesoundfloat',
                                                        'ui', 'Strings.java')))

# ══════════════════════════════════════════════════════════════════════
print('\n── D 「重启系统界面」弹窗上移到按钮上方 + M3E 圆角（第 5 条）────')

menu = body(ACT, 'private void showOverflowMenu(')
check('D1 已换成自绘 PopupWindow（系统 PopupMenu 的方向与圆角都改不动）',
      'new PopupWindow(' in menu and 'new PopupMenu(' not in ACT)
check('D2 容器圆角 = MENU_RADIUS_DP(16dp)',
      re.search(r'MENU_RADIUS_DP\s*=\s*16\s*;', ACT) is not None
      and 'setCornerRadius(dp(MENU_RADIUS_DP))' in menu)
check('D3 圆角真的裁住子 View（否则水波纹会在四角画成直角块）',
      'setClipToOutline(true)' in menu)
check('D4 位置 = 按钮**上方**（y = 按钮顶 - 菜单高 - 间隙）',
      'loc[1] - h - dp(MENU_ANCHOR_GAP_DP)' in menu)
check('D5 上方放不下时才退回下方（不画到屏幕外）',
      'loc[1] + mOverflowButton.getHeight() + dp(MENU_ANCHOR_GAP_DP)' in menu
      and 'if (y < 0)' in menu)
check('D6 点外部可关闭 + 点条目进确认流程',
      'setOutsideTouchable(true)' in menu and 'setBackgroundDrawable' in menu
      and 'confirmRestartSystemUi()' in menu)

# ══════════════════════════════════════════════════════════════════════
print('\n── E 预览窗不再自己弹回完整 / 连点不回弹（第 6 / 7 / 8 条）─────')

refresh = body(ACT, 'private void refreshPreviewMetrics()')
check('E1 测量前 forceLayout（View.measure 自带缓存，不强制会拿到旧尺寸）',
      'forceLayout()' in refresh)
check('E2 旧的「容器高度 >= 自然全高 ⇒ 坐标可信」判据已删除',
      'if (mPreviewLines.getHeight() >= full' not in ACT)
check('E3 两个边界改为**逐行累加**（与是否 layout 过无关）',
      'i == WINDOW_FIRST' in refresh and 'i == WINDOW_LAST' in refresh
      and 'getMeasuredHeight()' in refresh)

frac = body(ACT, 'private void applyPreviewFraction(float f)')
check('E4 量不出来时，折叠态沿用上次实测窗口高（不再无条件 WRAP_CONTENT）',
      'if (mPreviewCollapsed && mPreviewWinH > 0 && mPreviewFullH > 0)' in frac
      and 'lp.height = mPreviewWinH;' in frac)
check('E5 兜底分支里 pin 早于改卡高（顺序反了会被父级压扁）',
      frac.find('pinPreviewContentHeight();') < frac.find('lp.height = mPreviewWinH;'))
check('E6 连点切换先 cancel 上一条动画（两个 animator 抢写同一个进度 = 回弹）',
      'private ValueAnimator mPreviewAnim;' in ACT
      and 'mPreviewAnim.cancel()' in body(ACT, 'private void applyPreviewCollapsed('))
check('E7 展开态仍交回 wrap_content（两端必须落回确定值）',
      'lp.height = ViewGroup.LayoutParams.WRAP_CONTENT;' in frac)
check('E8 行重建后仍按当前折叠态重贴（updatePreview 尾部三条都在）',
      all(k in body(ACT, 'private void updatePreview()')
          for k in ('mPreviewMetricsValid = false;', 'refreshPreviewMetrics();',
                    'applyPreviewFraction(1f)')))

# ══════════════════════════════════════════════════════════════════════
print('\n── F 版本与履历纪律 ──────────────────────────────────────────')

# 【code 1034 泛化】原钉 1033 / 1019.9 —— 铁律 82：本轮判据随轮次前进会假 FAIL，
#   改为下界 + label 只守形态（与 verify_1007 L2 / 1021 口径一致）。
# 【code 1037 泛化】原钉死 2.3.5 —— 1037 是**第一次真正升语义版本号**（2.3.5 → 2.4.0），
#   这类「本轮当时的不变量」在源码层脚本里必须收成形态（铁律 82）：守
#   「name 成型 + tag == name（tag 进 APK 文件名）」这两条真正的不变式，不钉具体值。
check('F1 versionCode >= 1033 / label 形态 MMDD.N / name 成型且 == tag',
      re.search(r'appVersionCode\s*=\s*(\d+)', GRADLE) is not None
      and int(re.search(r'appVersionCode\s*=\s*(\d+)', GRADLE).group(1)) >= 1033
      and re.search(r"appVersionCodeLabel\s*=\s*'\d{4}\.\d+'", GRADLE) is not None
      and re.search(r"appVersionName\s*=\s*'(\d+\.\d+\.\d+)'", GRADLE) is not None
      and re.search(r"appVersionTag\s*=\s*'%s'"
                    % re.escape(re.search(r"appVersionName\s*=\s*'(\d+\.\d+\.\d+)'",
                                          GRADLE).group(1)), GRADLE) is not None)
check('F2 常开横幅自报 code 1033',
      '==== BUILD 2.3.5 / code 1033' in MOD)
check('F3 履历段写明「code 1032 升 1033」', 'code 1032 升 1033' in MOD)
check('F4 debug 履历里没有 ASCII 引号 / 反斜杠 / 反引号（日志行会被截断）',
      '\\' not in MOD[MOD.find('code 1033 （'):MOD.find('code 1033 （') + 1200]
      and '`' not in MOD[MOD.find('code 1033 （'):MOD.find('code 1033 （') + 1200])
check('F5 履历覆盖六件事（①②③④⑤⑥ 各一条）',
      all(k in MOD for k in ('①卡片末行底距', '②三个页签', '③删掉隐藏桌面图标',
                             '④重启系统界面', '⑤编辑字幕或切语言', '⑥连点切换')))

# ══════════════════════════════════════════════════════════════════════
print('\n── G 边界：本轮不许回退的东西 ────────────────────────────────')

check('G1 预览三层结构仍在（backdrop / panel / lines）',
      all(k in LAYOUT for k in ('@+id/preview_backdrop', '@+id/preview_panel',
                                '@+id/preview_lines')))
check('G2 语言切换仍是三语循环（不是弹窗）',
      body(ACT, 'private void cycleLanguage(').count('next = UiLang.') == 3)
clip = LAYOUT.count('android:clipChildren="false"')
# 【code 1034 有意改写】settings_coord 恢复 clipChildren=true（Ari 第 1 条：吸顶时
#   状态卡漏进状态栏 ⇒ 滚出顶界的内容必须在 coord 顶界被切住）。保存键投影链
#   （内容容器 → bottom_bar → settings_root）不经 coord，三层不裁剪不受影响。
check('G3 保存键投影链三层不裁剪没有回退 + coord 已恢复裁剪（1034 起）',
      clip == 3 and LAYOUT.count('android:clipChildren="true"') >= 1,
      '实际 %d 处' % clip)
check('G4 清单里 LAUNCHER 仍唯一、MAIN+INFO 安全绳仍在',
      MANIFEST.count('android.intent.category.LAUNCHER') == 1
      and MANIFEST.count('android.intent.category.INFO') == 1)
check('G5 末行底距不再出现「负 margin 下沉」的老写法（floor 与 want<floor 都已删）',
      'Math.max(dp(CARD_PAD_BOTTOM_DP)' not in ACT and 'want <' not in pin)

skip('底距 14dp 的**观感**与「跳变消失」', '纯运行时像素，源码层只能验「不再测量」')
skip('菜单圆角 16dp 的**观感**是否够 M3E', '矢量/主题属性，产物层也只能验出常量')
skip('预览窗「编辑字幕时不再展开」', '纯运行时状态机，源码层只能验兜底分支存在')

print('\n' + '=' * 62)
if fails:
    print('FAIL %d / %d' % (len(fails), total))
    for n in fails:
        print('  · ' + n)
    sys.exit(1)
print('PASS %d/%d（另有 %d 项如实标注无区分力）' % (total, total, len(nodisc)))
