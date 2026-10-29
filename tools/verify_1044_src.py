#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
code 1044 / 2.4.3 —— 源码层验证（「字幕字体跟随系统设定」）。

对应用户需求的三条，逐条落到源码判据：
  ① 排版卡片里多一个开关、默认关 ⇒ SettingsActivity 建行 + Strings 三语 + 默认 false；
  ② 开 = 悬浮窗字幕用手机系统字体 ⇒ SubtitleStyle 走 null typeface + SystemFont 清字体；
  ③ 关 = 跟随宿主 App 字体（**上一版行为不变**）⇒ 原有 setTypeface 分支原样保留；
  ④ 播放页三枚按钮不受影响 ⇒ ActivityButtonHook / StatusBarSubtitleHook 本轮零改动。

用法：python tools/verify_1044_src.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

F_CONFIG = 'app/src/main/java/io/github/ariinyume/dlsitesoundfloat/config/SubtitleConfig.java'
F_STYLE = 'app/src/main/java/io/github/ariinyume/dlsitesoundfloat/view/SubtitleStyle.java'
F_SYSFONT = 'app/src/main/java/io/github/ariinyume/dlsitesoundfloat/view/SystemFont.java'
F_VIEW = 'app/src/main/java/io/github/ariinyume/dlsitesoundfloat/view/FloatingSubtitleView.java'
F_SETTINGS = 'app/src/main/java/io/github/ariinyume/dlsitesoundfloat/ui/SettingsActivity.java'
F_STRINGS = 'app/src/main/java/io/github/ariinyume/dlsitesoundfloat/ui/Strings.java'
F_MODULE = 'app/src/main/java/io/github/ariinyume/dlsitesoundfloat/DlsiteSoundSubtitleModule.java'
F_GRADLE = 'app/build.gradle'
F_CHANGELOG = 'CHANGELOG.md'
F_ICON = 'app/src/main/res/drawable/ic_ui_font.xml'


def read(rel):
    """读文本；新文件缺失时返回空串（判据自然 FAIL，不抛）。"""
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        return ''
    return open(p, 'rb').read().decode('utf-8', 'replace').replace('\r\n', '\n')


def code_only(text):
    """剥注释：负向判据必须先剥，否则自己写的解释性注释会骗过断言。"""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'//[^\n]*', '', text)


def body_of(text, sig):
    """从 `sig` 起截到下一个同级方法（用下一处 '    private ' / '    public ' 兜底）。"""
    i = text.find(sig)
    if i < 0:
        return ''
    m = re.search(r'\n    (?:private|public|protected|static)[^\n]*\(',
                  text[i + len(sig):])
    return text[i:i + len(sig) + (m.start() if m else 4000)]


def main():
    cfg = read(F_CONFIG)
    style = read(F_STYLE)
    sysf = read(F_SYSFONT)
    sysf_code = code_only(sysf)
    view = read(F_VIEW)
    setj = read(F_SETTINGS)
    strings = read(F_STRINGS)
    module = read(F_MODULE)
    gradle = read(F_GRADLE)
    changelog = read(F_CHANGELOG)
    icon = read(F_ICON)

    style_line = body_of(view, 'private void styleLine(TextView tv,')
    measure = body_of(view, 'private void measureCurrentCue(')
    preview = body_of(setj, 'private void stylePreviewLine(TextView tv,')
    typo = body_of(setj, 'private void buildTypoGroup(')

    def has(t, s):
        return s in t

    def count(t, s):
        return t.count(s)

    def order(t, a, b):
        """a 出现在 b 之前（且两者都在）。"""
        ia, ib = t.find(a), t.find(b)
        return ia >= 0 and ib >= 0 and ia < ib

    rows = [
        # ── 版本号四处 ────────────────────────────────────────────
        ('V1', 'build.gradle appVersionTag = 2.4.3',
         has(gradle, "def appVersionTag = '2.4.3'")),
        ('V2', 'build.gradle appVersionCode = 1044',
         re.search(r'^def appVersionCode = 1044\s*$', gradle, re.M) is not None),
        ('V3', 'build.gradle appVersionName = 2.4.3',
         has(gradle, "def appVersionName = '2.4.3'")),
        ('V4', 'build.gradle appVersionCodeLabel = 1023.1（构建当天）',
         has(gradle, "def appVersionCodeLabel = '1023.1'")),
        ('V5', '横幅常开行升到 2.4.3 / code 1044',
         has(module, '[DLsiteSoundFloat] ==== BUILD 2.4.3 / code 1044"')),
        ('V6', '本轮履历段【code 1044 已追加，且排在上一条之上',
         count(module, '【code 1044') >= 1
         and module.find('==== BUILD 2.4.3 / code 1044 （【code 1044')
         < module.find('==== BUILD 2.4.2 / code 1043 （【code 1043')),
        ('V7', 'CHANGELOG 追加 1023.1 条目',
         has(changelog, '### 1023.1 code 1043 → 1044')),

        # ── 配置层：键 + 字段 + 两个存储通道 ───────────────────────
        ('C1', 'SubtitleConfig 新增 K_SUBTITLE_FONT_FOLLOW_SYSTEM 常量',
         has(cfg, 'public static final String K_SUBTITLE_FONT_FOLLOW_SYSTEM'
                  ' = "subtitle_font_follow_system";')),
        ('C2', '字段 subtitleFontFollowSystem 默认 false',
         has(cfg, 'public boolean subtitleFontFollowSystem = false;')),
        ('C3', 'copy() 带上新字段',
         has(cfg, 'c.subtitleFontFollowSystem = subtitleFontFollowSystem;')),
        ('C4', 'sameParametersAs 纳入新字段（保存判定能感知开关）',
         has(cfg, '&& subtitleFontFollowSystem == o.subtitleFontFollowSystem')),
        ('C5', 'JSON 两通道（toJson / fromJson）都写了新键',
         has(cfg, 'o.put(K_SUBTITLE_FONT_FOLLOW_SYSTEM, subtitleFontFollowSystem);')
         and has(cfg, 'c.subtitleFontFollowSystem = o.optBoolean'
                      '(K_SUBTITLE_FONT_FOLLOW_SYSTEM,')),
        ('C6', 'SharedPreferences 两通道（writeTo / fromPrefs）都写了新键',
         has(cfg, 'e.putBoolean(K_SUBTITLE_FONT_FOLLOW_SYSTEM, subtitleFontFollowSystem);')
         and has(cfg, 'c.subtitleFontFollowSystem = p.getBoolean'
                      '(K_SUBTITLE_FONT_FOLLOW_SYSTEM,')),
        ('C7', 'summary() 带 fontFollowSystem 读数，且插在 experimental **之前**'
                '（那条历史锚带行尾分号，追加只能接在它前面）',
         has(cfg, '+ " fontFollowSystem=" + subtitleFontFollowSystem')
         and has(cfg, '+ " experimental=" + experimentalEnabled;')),

        # ── 渲染层：SubtitleStyle ────────────────────────────────
        ('S1', 'SubtitleStyle 新增 fontFollowSystem / activeFakeBold / inactiveFakeBold',
         all(has(style, d) for d in (
             'public final boolean fontFollowSystem;',
             'public final boolean activeFakeBold;',
             'public final boolean inactiveFakeBold;'))),
        ('S2', '跟随系统时 typeface 归 null（语义 = 平台默认字体）',
         has(style, 'this.activeTypeface = null;')
         and has(style, 'this.inactiveTypeface = null;')),
        ('S3', '粗细口径：默认档活动行粗、非活动行常规（与跟随时等价）',
         has(style, 'this.activeFakeBold = explicit ? explicitBold : true;')
         and has(style, 'this.inactiveFakeBold = explicitBold;')),
        ('S4', '跟随宿主分支的 setTypeface 老逻辑原样保留（关 = 上一版行为）',
         has(style, 'this.activeTypeface = TF_BOLD;')
         and has(style, 'this.inactiveTypeface = TF_NORMAL;')),
        ('S5', 'sameAs 纳入新字段（开关一拨就重画）',
         has(style, '&& fontFollowSystem == o.fontFollowSystem')),
        ('S6', 'tfName(null) 打成 system（日志别把 null 说成 normal）',
         has(style, 'return "system";')),

        # ── 新增 SystemFont：绕开被 hook 的 setTypeface ───────────
        ('F1', 'SystemFont.java 存在且带 GPL 头',
         'SPDX-License-Identifier: GPL-3.0-or-later' in sysf),
        ('F2', '走 Paint#set(Paint) 整份复制（不经过 setTypeface）',
         has(sysf_code, 'paint.set(BLANK);')),
        ('F3', '🔴 SystemFont 内绝不出现 setTypeface（否则被宿主改字体钩子接走）',
         'setTypeface' not in sysf_code),
        ('F4', '复制后补回 flags（抗锯齿等绘制质量不能丢）',
         has(sysf_code, 'int flags = paint.getFlags();')
         and has(sysf_code, 'paint.setFlags(flags);')),
        ('F5', '已经是「未指定字体」时空操作（每行只真清一次）',
         has(sysf_code, 'if (paint.getTypeface() == null) {')),
        ('F6', '合成加粗按需下发（值没变不调 native）',
         has(sysf_code, 'if (paint.isFakeBoldText() != bold)')),

        # ── 真窗 + 预览的落地顺序 ─────────────────────────────────
        ('W1', 'styleLine 里「先清字体、后写字号」（清空会连带清字号）',
         order(style_line, 'SystemFont.clearTypeface(tv.getPaint())', 'tv.setTextSize(')),
        ('W2', 'styleLine 跟随系统时不调 setTypeface，改下发合成加粗',
         has(style_line, 'SystemFont.applyBold(tv.getPaint(),'
                         ' active ? st.activeFakeBold : st.inactiveFakeBold);')
         and count(style_line, 'tv.setTypeface(') == 1),
        ('W3', '测量 Paint 与渲染同字体（否则换行行数算错）',
         has(measure, 'SystemFont.clearTypeface(paint);')
         and order(measure, 'SystemFont.clearTypeface(paint);',
                   'SystemFont.applyBold(paint, st.activeFakeBold);')),
        ('W4', '预览行与真窗同序（设置页看到的就是浮窗看到的）',
         has(preview, 'SystemFont.clearTypeface(tv.getPaint());')
         and order(preview, 'SystemFont.clearTypeface(tv.getPaint())', 'tv.setTextSize(')),

        # ── 设置页 ────────────────────────────────────────────────
        ('U1', '排版面新增开关行（addSwitchRow + 写草稿 + markDirty）',
         has(typo, 'addSwitchRow(parent, Strings.FONT_FOLLOW_SYSTEM, v -> {')
         and has(typo, 'mDraft.subtitleFontFollowSystem = v;')
         and has(typo, 'markDirty();')),
        ('U2', '开关行字段 mRowFontFollowSystem 已声明',
         has(setj, 'private SwitchRow mRowFontFollowSystem;')),
        ('U3', 'syncWidgets 回灌草稿值（语言切换 / 撤销后不错位）',
         has(setj, 'setSwitch(mRowFontFollowSystem, mDraft.subtitleFontFollowSystem);')),
        ('U4', '排版面「恢复默认」把开关关回去',
         has(setj, 'mDraft.subtitleFontFollowSystem = false;')),
        ('U5', '脏标记计数把它算进排版面',
         has(setj, '|| mDraft.subtitleFontFollowSystem != mSaved.subtitleFontFollowSystem')),
        ('U6', '行图标 / 副标题都登记了（不许出现左边空一格的孤儿行）',
         has(setj, 'if (label == Strings.FONT_FOLLOW_SYSTEM) {\n            return R.drawable.ic_ui_font;')
         and has(setj, 'return Strings.SUP_FONT_FOLLOW_SYSTEM;')),
        ('U7', 'import SystemFont',
         has(setj, 'import io.github.ariinyume.dlsitesoundfloat.view.SystemFont;')),

        # ── 文案三语 ──────────────────────────────────────────────
        ('T1', 'Strings 三语标题（简 / 繁 / 英）',
         has(strings, 'FONT_FOLLOW_SYSTEM("字幕字体跟随系统设定", "字幕字型跟隨系統設定",')
         and has(strings, '"Subtitle font follows system"),')),
        ('T2', 'Strings 三语副标题',
         has(strings, 'SUP_FONT_FOLLOW_SYSTEM("开 ＝ 用手机系统字体；关 ＝ 用宿主 App 的字体",')
         and has(strings, '"On = phone system font; off = host app font"),')),

        # ── 图标资源 ──────────────────────────────────────────────
        ('I1', 'ic_ui_font.xml 24x24 视口',
         has(icon, 'android:viewportWidth="24"')
         and has(icon, 'android:viewportHeight="24"')),
        ('I2', 'ic_ui_font pathData 只含 M/L/H（元数可静态判定）',
         has(icon, 'android:pathData="M5,19L12,5L19,19M8,14.5H16"')),
        ('I3', '与 1032 那批同规格：2dp 描边 + 圆头',
         has(icon, 'android:strokeWidth="2"')
         and has(icon, 'android:strokeLineCap="round"')),
    ]

    print('%-4s %-62s %s' % ('tag', 'desc', 'verdict'))
    print('-' * 92)
    bad = 0
    for tag, desc, ok in rows:
        if not ok:
            bad += 1
        print('%-4s %-62s %s' % (tag, desc[:62], 'PASS' if ok else 'FAIL'))
    print('\n%s：%d 项 / FAIL %d 项'
          % ('ALL PASS' if bad == 0 else 'HAS FAIL', len(rows), bad))
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
