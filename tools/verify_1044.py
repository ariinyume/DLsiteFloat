import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from sdkpath import build_tools as _build_tools, sdk_root as _sdk_root
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
code 1044 / 2.4.3 —— dex 字节码层 + 资源层验证（「字幕字体跟随系统设定」）。

验什么
------
① APK 身份：versionCode=1044、versionName=2.4.3（aapt2 badging 是权威口径）；
② 配置键：subtitle_font_follow_system 进包，且四通道（JSON 读/写、Prefs 读/写）都在；
③ 新类 SystemFont：存在、clearTypeface/applyBold 两个签名、**体内走 Paint#set(Paint)**、
   **绝不调 setTypeface**（那正是被宿主改字体模块接管的入口）；
④ 调用点：真窗（FloatingSubtitleView）与设置页预览（SettingsActivity）都调了这两个方法；
⑤ 样式层：SubtitleStyle 新增 fontFollowSystem / activeFakeBold / inactiveFakeBold 三个字段；
⑥ UI：Strings 新增 FONT_FOLLOW_SYSTEM / SUP_FONT_FOLLOW_SYSTEM 三语枚举，中文文案进包；
⑦ 横幅：BUILD 2.4.3 / code 1044 进包，旧的 2.4.2 / code 1043 **短横幅**必须彻底消失
   （历史段是长串、不带收尾引号，用带引号的形态才只命中短横幅）；
⑧ 资源层：drawable/ic_ui_font 进包，pathData 与源码一致，且过 verify_pathdata 的命令元数校验。

用法
----
    python tools/verify_1044.py                 # 主验（本版包）
    python tools/verify_1044.py --control PKG   # 反向对照（上一版包）

⚠️ 对照模式只对「本轮专属锚」断言 0：它们必须自然取反；身份锚（两版都该有）只打印不判。
"""
import os
import re
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from verify_pathdata import check_one as pathdata_check  # noqa: E402

APK = os.path.join(ROOT, 'app/build/outputs/apk/debug/DLsiteFloat-2.4.3-code1044-debug.apk')
CACHE = os.path.join(ROOT, 'build/_v1044/decm')

SDK = os.environ.get('ANDROID_HOME') or _sdk_root()
BUILD_TOOLS = os.path.join(SDK, 'build-tools', '36.0.0')
AAPT2 = os.path.join(BUILD_TOOLS, 'aapt2.exe')
DEXDUMP = os.path.join(BUILD_TOOLS, 'dexdump.exe')


def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return p.stdout.decode('utf-8', 'replace')


def load_dex(apk):
    """把 APK 里所有 dex 反汇编进缓存目录（APK 更新才重跑）。"""
    if not os.path.isfile(apk):
        raise SystemExit('APK not found: ' + apk)
    stamp = os.path.join(CACHE, '.stamp')
    if os.path.isfile(stamp) and os.path.getmtime(stamp) >= os.path.getmtime(apk):
        texts = [open(os.path.join(CACHE, f), encoding='utf-8', errors='replace').read()
                 for f in sorted(os.listdir(CACHE)) if f.endswith('.txt')]
        if texts:
            return texts
    os.makedirs(CACHE, exist_ok=True)
    texts = []
    with zipfile.ZipFile(apk) as z:
        names = [n for n in z.namelist() if n.endswith('.dex')]
        for n in names:
            dx = os.path.join(CACHE, n)
            with open(dx, 'wb') as f:
                f.write(z.read(n))
            out = run([DEXDUMP, '-d', dx])
            txt = os.path.join(CACHE, n.replace('.dex', '.txt'))
            with open(txt, 'w', encoding='utf-8') as f:
                f.write(out)
            texts.append(out)
    open(stamp, 'w').write('ok')
    return texts


def count(texts, pat):
    rx = re.compile(pat)
    return sum(len(rx.findall(t)) for t in texts)


def class_body(text, desc):
    """按 'Class descriptor  : <desc>' 切出一整个类的文本（到下一个类描述为止）。"""
    key = "Class descriptor  : '%s'" % desc
    i = text.find(key)
    if i < 0:
        return ''
    j = text.find('Class descriptor  :', i + len(key))
    return text[i:] if j < 0 else text[i:j]


def method_body(cls_text, sig):
    """按 '[xxxx] <类名>.<方法名>:(proto)' 切出方法体（到下一个 '#NN' 元信息块为止）。"""
    key = '.' + sig
    i = cls_text.find(key)
    if i < 0:
        return ''
    j = cls_text.find('\n    #', i)
    return cls_text[i:] if j < 0 else cls_text[i:j]


# (标签, 说明, 正则, 主验期望, 对照期望 or None=身份锚)
CHECKS = [
    ('D1', '配置键串进包（JSON/Prefs 四通道 + 常量）',
     r'subtitle_font_follow_system', 5, 0),
    ('D2', 'summary 里的 fontFollowSystem= 读数',
     r'fontFollowSystem=', 1, 0),
    ('D3', '新类 SystemFont 的 class descriptor',
     r"Class descriptor  : 'Lio/github/ariinyume/dlsitesoundfloat/view/SystemFont;'", 1, 0),
    ('D4', 'clearTypeface 调用点（真窗两处 + 预览一处）',
     r'SystemFont;\.clearTypeface:\(Landroid/graphics/Paint;\)Z', 3, 0),
    ('D5', 'applyBold 调用点（真窗两处 + 预览一处）',
     r'SystemFont;\.applyBold:\(Landroid/graphics/Paint;Z\)V', 3, 0),
    ('D6', 'SubtitleStyle 新字段 fontFollowSystem 的引用点（声明 + 读写）',
     r'Lio/github/ariinyume/dlsitesoundfloat/view/SubtitleStyle;\.fontFollowSystem:Z', 9, 0),
    ('D7', 'SubtitleStyle 新字段 activeFakeBold / inactiveFakeBold 的引用点',
     r'SubtitleStyle;\.(?:activeFakeBold|inactiveFakeBold):Z', 13, 0),
    ('D9', 'SettingsActivity 引用 Strings.FONT_FOLLOW_SYSTEM（图标/副标题/开关行三处）',
     r'Strings;\.FONT_FOLLOW_SYSTEM', 5, 0),
    ('D10', 'SettingsActivity 引用 Strings.SUP_FONT_FOLLOW_SYSTEM',
     r'Strings;\.SUP_FONT_FOLLOW_SYSTEM', 3, 0),
    ('D11', '简中标题进常量池（Strings 枚举 + 本轮横幅自述）',
     r'字幕字体跟随系统设定', 2, 0),
    ('D12', '简中副标题（开＝系统 / 关＝宿主）进常量池',
     r'开 ＝ 用手机系统字体；关 ＝ 用宿主 App 的字体', 1, 0),
    ('D13', '新横幅 BUILD 2.4.3 / code 1044（常开一行 + 调试段）',
     r'BUILD 2\.4\.3 / code 1044', 2, 0),
    ('D14', '旧短横幅 BUILD 2.4.2 / code 1043 收尾引号形态必须绝迹（负向）',
     r'BUILD 2\.4\.2 / code 1043"', 0, 1),
    ('D15', '身份锚：2.4.2 / code 1043 历史段仍在（长串形态）',
     r'BUILD 2\.4\.2 / code 1043 （', 1, 1),
    ('D16', '身份锚：播放页按钮字体的旧口径未被改动（Typeface.DEFAULT_BOLD 仍在按钮侧）',
     r'Landroid/graphics/Typeface;\.DEFAULT_BOLD:Landroid/graphics/Typeface;', 4, None),
]


def main():
    control = None
    if '--control' in sys.argv:
        control = sys.argv[sys.argv.index('--control') + 1]

    if not os.path.isfile(APK):
        print('FAIL 找不到本版 APK：%s（先 assembleDebug）' % APK)
        return 1

    target = control or APK
    if control and not os.path.isfile(control):
        print('FAIL 对照包不存在：%s' % control)
        return 1
    if control:
        # 对照包用独立缓存目录，别和主验的 dex 文本混在一起
        global CACHE
        CACHE = os.path.join(ROOT, 'build/_v1044/decm_ctrl')

    print('APK : %s' % os.path.basename(target))
    print('大小: %d 字节\n' % os.path.getsize(target))

    # ① 身份
    badging = run([AAPT2, 'dump', 'badging', target])
    vc = re.search(r"versionCode='(\d+)'", badging)
    vn = re.search(r"versionName='([^']+)'", badging)
    pkg = re.search(r"package: name='([^']+)'", badging)
    print('aapt2: package=%s versionCode=%s versionName=%s'
          % (pkg.group(1) if pkg else '?', vc.group(1) if vc else '?',
             vn.group(1) if vn else '?'))
    want_vc, want_vn = ('1043', '2.4.2') if control else ('1044', '2.4.3')
    ident_ok = (pkg and pkg.group(1) == 'io.github.ariinyume.dlsitesoundfloat'
                and vc and vc.group(1) == want_vc and vn and vn.group(1) == want_vn)

    texts = load_dex(target)
    print('dex : %d 个文件已反汇编\n' % len(texts))

    # ② SystemFont 的体内判据（方法级）
    cls = class_body('\n'.join(texts), 'Lio/github/ariinyume/dlsitesoundfloat/view/SystemFont;')
    body_clear = method_body(cls, 'clearTypeface:(Landroid/graphics/Paint;)Z')
    inner_set = body_clear.count('Landroid/graphics/Paint;.set:(Landroid/graphics/Paint;)V')
    inner_settf = cls.count('Landroid/graphics/Paint;.setTypeface')
    inner_blank = body_clear.count('SystemFont;.BLANK')

    # ③ 资源层
    res = run([AAPT2, 'dump', 'resources', target])
    has_icon = len(re.findall(r'\bic_ui_font\b', res))
    tree = run([AAPT2, 'dump', 'xmltree', target, '--file', 'res/drawable/ic_ui_font.xml'])
    m = re.search(r'android:pathData\(0x[0-9a-f]+\)="([^"]*)"', tree)
    path_data = m.group(1) if m else ''
    path_errs = pathdata_check(path_data) if path_data else ['pathData 缺失']

    rows = []
    for tag, desc, pat, want, ctrl in CHECKS:
        got = count(texts, pat)
        if control is None:
            ok = got == want
        else:
            ok = (got == ctrl) if ctrl is not None else True
        rows.append((tag, desc, got, want, ctrl, ok))

    # 方法级与资源级锚点（同样进表，口径一致）
    rows.append(('M1', 'clearTypeface 体内调 Paint#set(Paint) 的次数', inner_set, 1, 0,
                 inner_set == (1 if control is None else 0)))
    rows.append(('M2', 'clearTypeface 体内引用 BLANK 模板', inner_blank, 1, 0,
                 inner_blank == (1 if control is None else 0)))
    rows.append(('M3', 'SystemFont 类内 setTypeface 调用次数（必须 0：勾子就在那）',
                 inner_settf, 0, 0, inner_settf == 0))
    # 资源层锚点：对照包（1043）压根没有这个 drawable ⇒ 三者天然取反，
    # 「对照侧期望值」写死成「没有」的形态，正好证明判据有区分力。
    R1_MAIN = has_icon >= 1
    rows.append(('R1', '资源表出现 ic_ui_font（id + drawable 两条）', has_icon, 2, 0,
                 R1_MAIN if control is None else has_icon == 0))
    rows.append(('R2', 'APK 内 pathData 与源码一致', path_data,
                 'M5,19L12,5L19,19M8,14.5H16', '<absent>',
                 (path_data == 'M5,19L12,5L19,19M8,14.5H16') if control is None
                 else path_data == ''))
    rows.append(('R3', 'pathData 命令元数/量级校验（verify_pathdata）', len(path_errs), 0,
                 '<missing>',
                 (not path_errs) if control is None else bool(path_errs)))

    print('%-4s %-58s %8s %8s %8s %s' % ('tag', 'desc', 'got', 'want', 'ctrl', 'verdict'))
    print('-' * 104)
    bad = 0
    for tag, desc, got, want, ctrl, ok in rows:
        if not ok:
            bad += 1
        print('%-4s %-58s %8s %8s %8s %s'
              % (tag, desc[:58], str(got)[:8], str(want), str(ctrl), 'PASS' if ok else 'FAIL'))

    if path_errs:
        print('\npathData 问题：' + '; '.join(path_errs))

    print('\n身份：%s（versionCode %s / versionName %s / 包名一致）'
          % ('PASS' if ident_ok else 'FAIL', want_vc, want_vn))
    total = len(rows) + 1
    print('%s：%d 项 / FAIL %d 项%s'
          % ('ALL PASS' if (bad == 0 and ident_ok) else 'HAS FAIL', total,
             bad + (0 if ident_ok else 1), '（主验）' if control is None else '（对照）'))
    return 0 if (bad == 0 and ident_ok) else 1


if __name__ == '__main__':
    sys.exit(main())
