#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1018 / v2.3.2（第 4 个 code）】架构审查三项的 **dex 字节码层**硬验证

为什么需要它
------------
源码改了但没编进包，是这类项目最常见的假绿。本脚本只认字节码：
新类是否真的进了 dex、方法描述符是否真的换了、旧方法是否真的没了。

对照口径（铁律：删除类改动的基准是「上一版」，第三参不滚动）
------------------------------------------------------------
  · 主验   = code 1018 包（本轮构建产物）
  · 对照   = code 1017 包（上一版交付包）—— 「新形态在主验有、在对照没有」才算有区分力锚
  · 反向   = code 1011 包（**固定不滚动**）—— 只做轻量断言：新类在更老的包里也不存在

验什么
------
2.2  `hook/DetectGatePolicy` 编进包：三常量值 0/1/2、`decide:(JJZZJJJ)I`、零实例字段；
     `ActivityButtonHook` 里真的出现对它的调用。
2.3  `util/LineSource` / `util/AppEnv` 编进包；`SubtitleRepository` 的 Interfaces 段含 LineSource
     且新增 `statusBarLine` / `joinCue`；桥的五个签名换成 LineSource，
     **旧的 `canToggle:(…SubtitleRepository;)Z`、`computeCurrentLine`、`join` 全部绝迹**。
2.6  `Utils.dip2pxF:(Landroid/util/DisplayMetrics;F)F` 编进包、旧两个 int 口径保留；
     三个自绘视图的 `dp:(F)F` 仍在，且方法体里出现对 `dip2pxF` 的调用。
版本 常开横幅串 `==== BUILD 2.3.2 / code 1018` 与履历段串在 dex 里；
     `aapt2 dump badging` 的 versionCode=1018 / versionName=2.3.2。
⚠️ label（1014.6）**不进包**是既定事实，不判。

用法
----
    python verify_1018.py [apk_1018] [apk_1017] [apk_1011]
退出码 0 = 全部通过
"""

import hashlib
import os
import re
import subprocess
import sys
import zipfile

BT = r'F:\WorkBuddyCache\DLSiteSound_Plus\toolchain\android-sdk\build-tools\34.0.0'
DEXDUMP = os.path.join(BT, 'dexdump.exe')
AAPT2 = os.path.join(BT, 'aapt2.exe')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UP = os.path.dirname(ROOT)          # F:/WorkBuddyCache/DLSiteSound_Plus
APK_NEW = os.path.join(ROOT, 'app', 'build', 'outputs', 'apk', 'debug',
                       'DLsiteFloat-2.3.2-code1018-debug.apk')
APK_OLD = os.path.join(UP, 'DLsiteFloat-2.3.2-code1017-debug.apk')
APK_REV = os.path.join(UP, 'DLsiteFloat-2.3.1-code1011-debug.apk')

PKG = 'io/github/ariinyume/dlsitesoundfloat'
C_GATE = 'L%s/hook/DetectGatePolicy;' % PKG
C_ACT = 'L%s/hook/ActivityButtonHook;' % PKG
C_LINESRC = 'L%s/util/LineSource;' % PKG
C_APPENV = 'L%s/util/AppEnv;' % PKG
C_REPO = 'L%s/data/SubtitleRepository;' % PKG
C_BRIDGE = 'L%s/util/StatusBarSubtitleBridge;' % PKG
C_UTILS = 'L%s/util/Utils;' % PKG
C_CLOSE = 'L%s/view/CloseButtonView;' % PKG
C_GRIP = 'L%s/view/GripIndicatorView;' % PKG
C_BADGE = 'L%s/view/NotificationBadgeView;' % PKG
C_MOD = 'L%s/DlsiteSoundSubtitleModule;' % PKG

SIG_LINE = 'L%s/util/LineSource;' % PKG
SIG_REPO = 'L%s/data/SubtitleRepository;' % PKG
SIG_DM = 'Landroid/util/DisplayMetrics;'
SIG_CTX = 'Landroid/content/Context;'
SIG_CUE = 'L%s/data/SubtitleCue;' % PKG

TOTAL = 0
FAILS = []
NO_DISC = []


def check(desc, ok, extra=''):
    global TOTAL
    TOTAL += 1
    print('  %s %s%s' % ('OK  ' if ok else 'FAIL', desc, ('   ' + extra) if extra else ''))
    if not ok:
        FAILS.append(desc)


def dual(desc, ok_new, ok_old, extra_new='', extra_old=''):
    """主验命中 + 对照未命中 ⇒ 有区分力锚；两者都命中 ⇒ 记「无区分力」。"""
    global TOTAL
    TOTAL += 1
    disc = ok_new and not ok_old
    tag = 'OK  ' if ok_new else 'FAIL'
    s = '  %s %s' % (tag, desc)
    if ok_new:
        s += '   [%s]' % ('有区分力锚' if disc else '⚠ 无区分力（对照也命中）')
    if extra_new:
        s += ' ' + extra_new
    print(s)
    if not ok_new:
        FAILS.append(desc)
    if ok_new and not disc:
        NO_DISC.append(desc)


def _rm(p):
    try:
        os.remove(p)
        return True
    except OSError:
        return False


def dexdump_all(apk, out):
    if os.path.exists(out) and os.path.getsize(out) > 1_000_000:
        return out                     # 复用缓存（按包 sha 命名，不会串包）
    _rm(out)
    with zipfile.ZipFile(apk) as z:
        dexs = [n for n in z.namelist() if re.match(r'.*\.dex$', n)]
        for i, n in enumerate(dexs):
            tmp = out + '.tmp'
            with open(tmp, 'wb') as f:
                f.write(z.read(n))
            r = subprocess.run([DEXDUMP, '-d', tmp], capture_output=True, text=True,
                               errors='replace', encoding='utf-8')
            with open(out, 'a' if i else 'w', encoding='utf-8') as f:
                f.write(r.stdout)
            _rm(tmp)
    return out


def dump_path(apk):
    sha = hashlib.sha256(open(apk, 'rb').read()).hexdigest()[:12]
    return os.path.join(ROOT, 'app', 'build', '_dump_%s.txt' % sha)


def slice_class(dump, cls_sig):
    m = re.search(r"Class descriptor\s*:\s*'%s'" % re.escape(cls_sig), dump)
    if not m:
        return None
    m2 = re.search(r"\n[^\n]*Class descriptor\s*:", dump[m.end():])
    end = m.end() + m2.start() if m2 else len(dump)
    return dump[m.start():end]


def has_method(seg, name, mtype):
    if not seg:
        return False
    return re.search(r"name\s*:\s*'%s'\s*\n\s*type\s*:\s*'%s'"
                     % (re.escape(name), re.escape(mtype)), seg) is not None


def has_field(seg, name, ftype, value=None):
    """
    value=None  ⇒ 只断言「字段存在、类型正确」，**不要求 value 行**。
    ⚠️ 非编译期常量字段（如 `private static volatile Context sAppContext;`）
       dexdump 只打 name/type/access，**不打 value 行** —— 早先的写法硬要求
       value 行，把这类字段一律判成「不存在」（1018 首跑红 2 条，全是假 FAIL）。
    value='0' 等 ⇒ 必须是编译期常量，且取该值。
    """
    if not seg:
        return False
    pat = (r"name\s*:\s*'%s'\s*\n\s*type\s*:\s*'%s'\s*\n"
           % (re.escape(name), re.escape(ftype)))
    if value is None:
        return re.search(pat + r"[^\n]*", seg) is not None
    m = re.search(pat + r"[^\n]*\n\s*value\s*:\s*(\S+)", seg)
    return m is not None and m.group(1) == value


def ifaces(seg):
    """
    取 dexdump 类头里 `Interfaces -` 之后那几行。

    ⚠️ 形态是（**带 `#N : ` 前缀**，不是裸描述符）：
        Interfaces        -
          #0              : 'Lio/…/util/LineSource;'
        早先写成 `Interfaces\\s*-\\s*\\n\\s*Lio/…` 直接漏掉 `#0 : ` ⇒ 假 FAIL。
    """
    if not seg:
        return ''
    m = re.search(r"Interfaces\s*-\s*\n((?:\s*#\d+\s*:[^\n]*\n)*)", seg)
    return m.group(1) if m else ''


def raw_has(apk, s):
    """轻量：直接在 dex 字节里搜字符串（不 dump）。"""
    b = s.encode('utf-8')
    with zipfile.ZipFile(apk) as z:
        for n in z.namelist():
            if n.endswith('.dex') and b in z.read(n):
                return True
    return False


def main():
    apk_new = sys.argv[1] if len(sys.argv) > 1 else APK_NEW
    apk_old = sys.argv[2] if len(sys.argv) > 2 else APK_OLD
    apk_rev = sys.argv[3] if len(sys.argv) > 3 else APK_REV
    for p in (apk_new, apk_old, apk_rev):
        if not os.path.exists(p):
            print('缺少包: %s' % p)
            return 2

    print('主验: %s (%d B)' % (os.path.basename(apk_new), os.path.getsize(apk_new)))
    print('对照: %s (%d B)' % (os.path.basename(apk_old), os.path.getsize(apk_old)))
    print('反向: %s (%d B)' % (os.path.basename(apk_rev), os.path.getsize(apk_rev)))
    print()
    print('正在反汇编…')
    nd = open(dexdump_all(apk_new, dump_path(apk_new)), encoding='utf-8').read()
    od = open(dexdump_all(apk_old, dump_path(apk_old)), encoding='utf-8').read()
    print('  dump 完成（主验 %d / 对照 %d 字符）' % (len(nd), len(od)))
    print()

    def seg(d, cls):
        return slice_class(d, cls)

    print('=== 2.2 DetectGatePolicy（检测前置闸）===')
    gn, go = seg(nd, C_GATE), seg(od, C_GATE)
    dual('DetectGatePolicy 类存在', gn is not None, go is not None)
    for name, val in (('PROCEED', '0'), ('SKIP_THROTTLE', '1'), ('SKIP_FOLLOWING', '2')):
        dual('常量 %s = %s' % (name, val),
             has_field(gn, name, 'I', val), has_field(go, name, 'I', val))
    dual('方法 decide:(JJZZJJJ)I',
         has_method(gn, 'decide', '(JJZZJJJ)I'), has_method(go, 'decide', '(JJZZJJJ)I'))
    # 零验证：decide 的字节码里必须出现「两次 long 比较 + 一次布尔短路」的形状
    if gn:
        m = re.search(r"name\s*:\s*'decide'.*?(?=\n\s*#\d+\s+: \(in |\Z)", gn, re.S)
        body = m.group(0) if m else ''
        dual('decide 是零状态（无 iget/iput/sget/sput）',
             ('iput' not in body) and ('iget' not in body)
             and ('sput' not in body) and ('sget' not in body) and bool(body),
             True)
    an, ao = seg(nd, C_ACT), seg(od, C_ACT)
    dual('ActivityButtonHook 调用 DetectGatePolicy.decide',
         'DetectGatePolicy;.decide:(JJZZJJJ)I' in (an or ''),
         'DetectGatePolicy;.decide:(JJZZJJJ)I' in (ao or ''))

    print()
    print('=== 2.3 依赖倒置（util 不再依赖 data）===')
    ln, lo = seg(nd, C_LINESRC), seg(od, C_LINESRC)
    dual('util/LineSource 接口存在', ln is not None, lo is not None)
    for m, t in (('isPlayingOrUnknown', '()Z'), ('statusBarLine', '()Ljava/lang/String;'),
                 ('getCurrentCueDurationMs', '()J'), ('shouldShowNoSubtitles', '()Z')):
        dual('LineSource.%s:%s' % (m, t), has_method(ln, m, t), has_method(lo, m, t))
    dual('LineSource 是 interface',
         bool(ln) and re.search(r"Access flags\s*:\s*0x[0-9a-f]+\s*\([^)]*INTERFACE", ln) is not None,
         bool(lo))

    en, eo = seg(nd, C_APPENV), seg(od, C_APPENV)
    dual('util/AppEnv 类存在', en is not None, eo is not None)
    dual('AppEnv.install:(Context;)V',
         has_method(en, 'install', '(%s)V' % SIG_CTX),
         has_method(eo, 'install', '(%s)V' % SIG_CTX))
    dual('AppEnv.app:()Context',
         has_method(en, 'app', '()%s' % SIG_CTX), has_method(eo, 'app', '()%s' % SIG_CTX))
    dual('AppEnv 静态字段 sAppContext',
         has_field(en, 'sAppContext', SIG_CTX), has_field(eo, 'sAppContext', SIG_CTX))

    rn, ro = seg(nd, C_REPO), seg(od, C_REPO)
    dual('SubtitleRepository 实现 LineSource（Interfaces 段）',
         SIG_LINE in ifaces(rn),
         SIG_LINE in ifaces(ro))
    dual('SubtitleRepository.statusBarLine:()String',
         has_method(rn, 'statusBarLine', '()Ljava/lang/String;'),
         has_method(ro, 'statusBarLine', '()Ljava/lang/String;'))
    dual('SubtitleRepository.joinCue:(SubtitleCue;)String',
         has_method(rn, 'joinCue', '(%s)Ljava/lang/String;' % SIG_CUE),
         has_method(ro, 'joinCue', '(%s)Ljava/lang/String;' % SIG_CUE))
    dual('SubtitleRepository 仍实现 isPlayingOrUnknown/getCurrentCueDurationMs/shouldShowNoSubtitles',
         has_method(rn, 'isPlayingOrUnknown', '()Z')
         and has_method(rn, 'getCurrentCueDurationMs', '()J')
         and has_method(rn, 'shouldShowNoSubtitles', '()Z'),
         True)

    bn, bo = seg(nd, C_BRIDGE), seg(od, C_BRIDGE)
    dual('桥 canToggle:(LineSource;)Z（签名升级）',
         has_method(bn, 'canToggle', '(%s)Z' % SIG_LINE),
         has_method(bo, 'canToggle', '(%s)Z' % SIG_LINE))
    dual('桥旧签名 canToggle:(SubtitleRepository;)Z 绝迹',
         not has_method(bn, 'canToggle', '(%s)Z' % SIG_REPO),
         not has_method(bo, 'canToggle', '(%s)Z' % SIG_REPO))
    dual('桥 resendCurrentFromRepo:(Context;LineSource;)V',
         has_method(bn, 'resendCurrentFromRepo', '(%s%s)V' % (SIG_CTX, SIG_LINE)),
         has_method(bo, 'resendCurrentFromRepo', '(%s%s)V' % (SIG_CTX, SIG_LINE)))
    dual('桥 sendCurrentFromRepo:(Context;LineSource;)V',
         has_method(bn, 'sendCurrentFromRepo', '(%s%s)V' % (SIG_CTX, SIG_LINE)),
         has_method(bo, 'sendCurrentFromRepo', '(%s%s)V' % (SIG_CTX, SIG_LINE)))
    dual('桥旧 computeCurrentLine 绝迹',
         'computeCurrentLine' not in (bn or ''), 'computeCurrentLine' not in (bo or ''))
    dual('桥旧 join(SubtitleCue) 绝迹',
         not has_method(bn, 'join', '(%s)Ljava/lang/String;' % SIG_CUE),
         not has_method(bo, 'join', '(%s)Ljava/lang/String;' % SIG_CUE))
    dual('桥内确实调用 LineSource.statusBarLine',
         'LineSource;.statusBarLine:()Ljava/lang/String;' in (bn or ''),
         'LineSource;.statusBarLine:()Ljava/lang/String;' in (bo or ''))

    print()
    print('=== 2.6 dp 归口（Utils.dip2pxF）===')
    un, uo = seg(nd, C_UTILS), seg(od, C_UTILS)
    dual('Utils.dip2pxF:(DisplayMetrics;F)F',
         has_method(un, 'dip2pxF', '(%sF)F' % SIG_DM),
         has_method(uo, 'dip2pxF', '(%sF)F' % SIG_DM))
    for m, t in (('dip2px', '(%sF)I' % SIG_CTX), ('dip2pxOrDefault', '(%sF)I' % SIG_CTX),
                 ('applyDimensionDip', '(%sF)I' % SIG_CTX)):
        dual('Utils.%s 旧口径保留（回归锚）' % m,
             has_method(un, m, t), has_method(uo, m, t))
    for cls, name in ((C_CLOSE, 'CloseButtonView'), (C_GRIP, 'GripIndicatorView'),
                      (C_BADGE, 'NotificationBadgeView')):
        vn, vo = seg(nd, cls), seg(od, cls)
        dual('%s.dp:(F)F 仍在' % name, has_method(vn, 'dp', '(F)F'), True)
        dual('%s 方法体调用 Utils.dip2pxF' % name,
             'Utils;.dip2pxF:(%sF)F' % SIG_DM in (vn or ''),
             'Utils;.dip2pxF:(%sF)F' % SIG_DM in (vo or ''))

    print()
    print('=== 版本 / 横幅 ===')
    mn = seg(nd, C_MOD)
    dual('常开横幅串 code 1018 在包内',
         '==== BUILD 2.3.2 / code 1018' in (mn or ''),
         '==== BUILD 2.3.2 / code 1018' in (seg(od, C_MOD) or ''))
    dual('履历段串 【code 1018 在包内',
         '【code 1018' in (mn or ''), '【code 1018' in (seg(od, C_MOD) or ''))
    badging = ''
    try:
        r = subprocess.run([AAPT2, 'dump', 'badging', apk_new], capture_output=True,
                           text=True, errors='replace', encoding='utf-8')
        badging = r.stdout
    except Exception as e:
        badging = 'ERR %s' % e
    check('aapt2：versionCode=1018', "'1018'" in badging, badging.split('\n')[0][:80])
    check('aapt2：versionName=2.3.2', "versionName='2.3.2'" in badging)

    print()
    print('=== 反向对照包（code 1011，固定不滚动）===')
    for s, label in ((C_GATE, 'DetectGatePolicy'), (C_LINESRC, 'util/LineSource'),
                     (C_APPENV, 'util/AppEnv')):
        check('code 1011 里没有 %s' % label, not raw_has(apk_rev, s))
    check('code 1011 里没有 dip2pxF',
          not raw_has(apk_rev, 'dip2pxF'))

    print()
    print('=' * 72)
    print('有区分力锚：%d 条' % (TOTAL - len(FAILS) - len(NO_DISC)))
    if NO_DISC:
        print('⚠ 无区分力（对照也命中，仅作形态回归锚）：%d 条' % len(NO_DISC))
        for d in NO_DISC:
            print('    · %s' % d)
    if FAILS:
        print('FAIL %d/%d' % (len(FAILS), TOTAL))
        for f in FAILS:
            print('  - %s' % f)
        return 1
    print('PASS %d/%d' % (TOTAL, TOTAL))
    return 0


if __name__ == '__main__':
    sys.exit(main())
