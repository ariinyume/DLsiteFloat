import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from sdkpath import build_tools as _build_tools
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1025 / v2.3.5】material 1.14.0 + targetSdk 36 + 签名 V1/V2/V3 + 设计审查 P0 三项
的 **产物层（aapt2 / apksigner / dex）** 硬验证。
（读的是**死的产物** ⇒ 判据可以钉死本轮字面量；见铁律 ⑬）

主验 = 本轮包 DLsiteFloat-2.3.5-code1025-debug.apk
对照 = 上一版交付包 DLsiteFloat-2.3.5-code1024-debug.apk（**删除/新增类判据的基准是上一版**）

验什么
------
A 版本档位（aapt2 badging）：versionCode=1025 / versionName=2.3.5 /
  minSdk=24 / **targetSdk=36** / compileSdk=36。
B 签名三档（apksigner）：v1 + v2 + v3 **全部 true**；
  🔴 必须带 `--min-sdk-version 23` —— 不带时 apksigner 按清单 minSdk=24 判定
  「v1 用不上」，**跳过校验并打印 v1:false**（假阴性）。反向对照：code 1024 在这个
  参数下直接 `DOES NOT VERIFY / Missing META-INF/MANIFEST.MF` ⇒ 证明旧包确实没有 v1。
C dex 新符号（主验有 / 对照无，逐条判区分力）：三处 insets/折叠方法名、折叠持久化键、
  六条三语文案、三枚 M3E 库版本指纹类。
D 资源层（aapt2 dump resources）：id/preview_bar、id/preview_chevron、
  drawable/ic_chevron_down 只在新包。
E 保持型（两版皆真、**无区分力**）：旧版就有的文案与类，防「改 A 顺手弄坏 B」。
F 常量层：**本轮不适用** —— 改的是 40→48 / 34→48 这类 UI 数值，在 dex 里没有区分力
  （48 是常量池里的常客）。这里如实打印说明，不伪造判据。

用法
----
    python verify_1025.py [apk_new] [apk_old]
退出码 0 = 全部通过
"""

import os
import re
import subprocess
import sys
import zipfile

BT = _build_tools('36.0.0')
AAPT2 = os.path.join(BT, 'aapt2.exe')
APKSIGNER = os.path.join(BT, 'apksigner.bat')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UP = os.path.dirname(ROOT)                    # 仓库的上一级（本机工作区）
APK_NEW = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    ROOT, 'app', 'build', 'outputs', 'apk', 'debug', 'DLsiteFloat-2.3.5-code1025-debug.apk')
APK_OLD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    UP, 'DLsiteFloat-2.3.5-code1024-debug.apk')

fails = []
total = 0
disc = 0            # 有区分力的条数（主验有 / 对照无）
nodisc = []         # 无区分力条目名


def check(name, ok, detail=''):
    global total
    total += 1
    if ok:
        print('  PASS  %s' % name)
    else:
        print('  FAIL  %s   %s' % (name, detail))
        fails.append(name)


def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout.decode('utf-8', 'replace')


def badging(apk):
    _, out = run([AAPT2, 'dump', 'badging', apk])
    return out


def resources(apk):
    _, out = run([AAPT2, 'dump', 'resources', apk])
    return out


def dex_blob(apk):
    z = zipfile.ZipFile(apk)
    names = [n for n in z.namelist() if re.match(r'classes\d*\.dex$', n)]
    return b''.join(z.read(n) for n in names)


def count(blob, token):
    return blob.count(token.encode('utf-8'))


def main():
    for p in (APK_NEW, APK_OLD):
        if not os.path.isfile(p):
            print('找不到 APK：%s' % p)
            return 2

    print('主验：%s' % os.path.basename(APK_NEW))
    print('对照：%s\n' % os.path.basename(APK_OLD))

    bn = badging(APK_NEW)
    bo = badging(APK_OLD)

    print('── A 版本档位 ──────────────────────────────────────────────')
    check('A1 versionCode = 1025', "versionCode='1025'" in bn)
    check('A2 versionName = 2.3.5', "versionName='2.3.5'" in bn)
    check('A3 minSdk = 24（未动，向下兼容仍到 Android 7）', "minSdkVersion:'24'" in bn)
    check('A4 **targetSdk = 36**（Android 16）', "targetSdkVersion:'36'" in bn)
    check('A5 compileSdk = 36', "compileSdkVersion='36'" in bn)
    check('A6 对照包仍是 targetSdk 34（证明这是一步真改动）',
          "targetSdkVersion:'34'" in bo)

    print('\n── B 签名 V1 + V2 + V3 ──────────────────────────────────────')
    rc_new, out_new = run([APKSIGNER, 'verify', '-v', '--min-sdk-version', '23', APK_NEW])
    check('B0 主验包整体可验（Verifies）', rc_new == 0 and 'Verifies' in out_new, out_new[:160])
    check('B1 v1（JAR signing）= true',
          'Verified using v1 scheme (JAR signing): true' in out_new)
    check('B2 v2 = true', 'Verified using v2 scheme (APK Signature Scheme v2): true' in out_new)
    check('B3 v3 = true', 'Verified using v3 scheme (APK Signature Scheme v3): true' in out_new)
    z = zipfile.ZipFile(APK_NEW)
    names = z.namelist()
    check('B4 APK 内确有 JAR 签名三件套（不只看 apksigner 的口径）',
          any(n.startswith('META-INF/') and n.endswith('.SF') for n in names)
          and any(n.startswith('META-INF/') and n.endswith('.RSA') for n in names)
          and 'META-INF/MANIFEST.MF' in names)
    # 反向对照：旧包在同一参数下必须「验不过」——这才证明 v1 不是假阳性
    rc_old, out_old = run([APKSIGNER, 'verify', '-v', '--min-sdk-version', '23', APK_OLD])
    check('B5 对照包(1024) 在 --min-sdk-version 23 下缺 MANIFEST.MF（双向判据）',
          rc_old != 0 and 'Missing META-INF/MANIFEST.MF' in out_old, out_old[:160])
    check('B6 签名者仍是同一个 debug 证书（不影响覆盖安装）',
          'CN=Android Debug' in run([APKSIGNER, 'verify', '--print-certs', APK_NEW])[1])

    print('\n── C dex 新符号（主验有 / 对照无）──────────────────────────')
    dn = dex_blob(APK_NEW)
    do = dex_blob(APK_OLD)
    global disc

    def pair(name, token, expect_old=0):
        """主验必须命中、对照必须 expect_old 次 —— 命中即记一条「有区分力」。"""
        global disc
        cn = count(dn, token)
        co = count(do, token)
        ok = cn > 0 and co == expect_old
        if ok and expect_old == 0:
            disc += 1
        check('%s  [new=%d old=%d]' % (name, cn, co), ok)

    pair('C1 insets 入口方法', 'applyEdgeToEdgeInsets')
    pair('C2 系统栏明暗方法', 'applySystemBarAppearance')
    pair('C3 折叠动作方法', 'applyPreviewCollapsed')
    pair('C4 折叠状态读取', 'readPreviewCollapsed')
    pair('C5 折叠状态落盘', 'savePreviewCollapsed')
    pair('C6 折叠持久化键（不进配置 JSON）', 'settings_preview_collapsed')
    pair('C7 文案 · 简中 收起', '收起预览窗')
    pair('C8 文案 · 繁中 收起', '收合預覽窗')
    pair('C9 文案 · 英文 收起', 'Collapse preview')
    pair('C10 文案 · 简中 展开', '展开预览窗')
    pair('C11 文案 · 繁中 展开', '展開預覽窗')
    pair('C12 文案 · 英文 展开', 'Expand preview')
    # 库版本指纹：以下几类在 material 1.13+ 才有；debug 不裁剪 ⇒ 进包即可判版本。
    # ⚠️ 别用 `SchemeExpressive`（实测 1.9.0 里就有同名工具类，new=2 / old=2，无区分力）。
    pair('C13 库指纹 · LoadingIndicator（1.13+）',
         'com/google/android/material/loadingindicator/LoadingIndicator')
    pair('C14 库指纹 · MaterialButtonGroup（1.13+）',
         'com/google/android/material/button/MaterialButtonGroup')
    pair('C15 库指纹 · FloatingToolbarLayout（1.13+）',
         'com/google/android/material/floatingtoolbar/FloatingToolbarLayout')

    print('\n── D 资源层 ────────────────────────────────────────────────')
    rn = resources(APK_NEW)
    ro = resources(APK_OLD)
    for rid, label in [('id/preview_bar', 'D1 预览条容器'),
                       ('id/preview_chevron', 'D2 折叠箭头'),
                       ('drawable/ic_chevron_down', 'D3 箭头矢量图')]:
        ok = rid in rn and rid not in ro
        if ok:
            disc += 1
        check('%s (%s)' % (label, rid), ok)
    nodisc.append('D4 id/preview_card（两版都有，保持型）')
    check('D4 旧预览卡仍在（没被折叠改造弄丢）', 'id/preview_card' in rn and 'id/preview_card' in ro)

    print('\n── E 保持型（两版皆真，无区分力）───────────────────────────')
    for name, token in [('E1 节标题「调整预览窗」', '调整预览窗'),
                        ('E2 底栏「保存设置」', '保存设置'),
                        ('E3 「液态玻璃」分组', '液态玻璃'),
                        ('E4 WindowCompat（旧版就有，本轮才真正使用）',
                         'androidx/core/view/WindowCompat')]:
        cn, co = count(dn, token), count(do, token)
        nodisc.append(name.split()[0])
        check('%s  [new=%d old=%d]' % (name, cn, co), cn > 0 and co > 0)

    print('\n── F 常量层：本轮**不适用** ────────────────────────────────')
    print('  SKIP  行高 40→48 / 色点热区 34→48 是 UI 整型常量，javac 会内联成立即数；')
    print('        48 这类值在常量池里到处都是，**没有区分力** —— 不做伪造判据。')
    print('        这两条的验收口径是：源码层（verify_1025_src.py D1/D2/E1/E2）+ 真机目视。')

    print('\n── G 设置页 P1/P2 + P1-5 判据修正（本轮新增）───────────────')
    # P1-1 三卡合一：分段文案 + 建段/切面方法
    pair('G1 分段 · 简中「行态」', '行态')
    pair('G2 分段 · 繁中「行態」', '行態')
    pair('G3 方法 · 建分段条（零重建入口）', 'buildAppearanceTabs')
    pair('G4 方法 · 切面', 'selectAppearancePage')
    # P2-2 重置收敛：三组共用一条文案
    pair('G5 合并后的外观重置文案', '恢复字幕外观默认设置')
    pair('G6 外观组副标题（说明影响范围）', '颜色 · 行态 · 排版一并回到默认')
    pair('G7 方法 · 三组重置合并', 'resetAppearanceGroup')
    # P1-2 行头原语
    pair('G8 方法 · 行头查表原语', 'makeRowHead')
    pair('G9 类 · 行头描述（图标 + 副标题）', 'RowHead')
    # P2-1 Snackbar + 撤销
    pair('G10 撤销提示', '已撤销上一次保存')
    pair('G11 方法 · 撤销保存', 'undoLastSave')
    # P2-3 联动动效
    pair('G12 方法 · 联动显隐动效', 'animateRowVisibility')
    # P1-5 判据修正：纯自算行
    pair('G13 方法 · 纯自算行（只读游标、不回退镜像）', 'selfComputedLines')
    nodisc.append('G14 「排版」「snack」两词旧版即有，命中数不可比 ⇒ 不作判据')

    # P1-1 布局层：卡顶分段条 + 唯一重置容器 —— 这两个 id 旧版确实没有
    for rid, label in [('id/appearance_tabs', 'G15 卡顶分段条'),
                       ('id/group_appearance_reset', 'G16 唯一重置容器')]:
        ok = rid in rn and rid not in ro
        if ok:
            disc += 1
        check('%s (%s)' % (label, rid), ok)
    # ⚠️ 下面三个容器 id **两版都有**（旧版每张卡内也各有一个同名容器）⇒ 无区分力，
    #    只守「还在」（别被三卡合一改丢了）。真正证明「三张卡收成一张」的是
    #    G20/G21 的反向判据（旧卡 id 已消失）。
    for rid, label in [('id/group_main', 'G17 外观面 · 颜色容器仍在'),
                       ('id/group_inactive', 'G18 外观面 · 行态容器仍在'),
                       ('id/group_typo', 'G19 外观面 · 排版容器仍在')]:
        nodisc.append(label.split()[0])
        check('%s (%s)' % (label, rid), rid in rn and rid in ro)
    # 🔴 删除类改动：对照基准是**上一版**（old 有、new 没有）
    for rid, label in [('id/card_inactive', 'G20 旧「未激活」卡已删'),
                       ('id/card_typo', 'G21 旧「字体排版」卡已删')]:
        ok = rid not in rn and rid in ro
        if ok:
            disc += 1
        check('%s (%s)' % (label, rid), ok)
    # P1-2 十四枚行图标全进包（少一枚就会出现「无图标的行」）
    icons = ['opacity', 'radius', 'highlight', 'scale', 'blur', 'align',
             'line_spacing', 'wrap', 'sync', 'panel', 'statusbar', 'log',
             'cache', 'flask']
    miss = [i for i in icons if ('drawable/ic_ui_' + i) not in rn]
    if not miss:
        disc += 1
    check('G22 十四枚行图标全部进包（缺 %d 枚）' % len(miss), not miss)

    print('\n──────────────────────────────────────────────────────────')
    print('有区分力锚：%d 条；无区分力（如实标注）：%d 条' % (disc, len(nodisc)))
    if fails:
        print('FAIL %d / %d' % (len(fails), total))
        for f in fails:
            print('  · %s' % f)
        return 1
    print('PASS %d / %d' % (total, total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
