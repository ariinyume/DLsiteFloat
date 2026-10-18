#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1024 / v2.3.5】预取跑通（压缩正文就地解压）+ 作品维强约束 + 离线文案收口 + P1 三项
的 **dex 字节码层**硬验证。
（读的是**死的产物** ⇒ 判据可以钉死本轮字面量；见铁律 ⑬）

主验 = 本轮包 DLsiteFloat-2.3.5-code1024-debug.apk
对照 = 上一版交付包 DLsiteFloat-2.3.5-code1023-debug.apk（**删除类改动的基准是上一版**）

验什么
------
A 版本（aapt2 badging）：versionCode=1024 / versionName=2.3.5。
B 新类**以类型描述符形态**进包（HostStyleProbe / HostLineSync）—— 对照包必须一个都没有。
C 新字符串进包（gzip 两层修法 / 作品维两条链路 / 七个 extra / 三条读数文案 / 开关文案）
  —— 每条都先 probe 对照包，**有区分力才算数**。
D 新方法名进包（pickLocked / sameWork / hasDuration / works / tracks）。
E 删除类改动：上一版两句离线专用文案在新包**消失**、在对照包存在（双向）。
F 常量层（数值改动只能在这一层验，javac 会内联）：
  HostStyleProbe 的 8f / 240f / 0.5f，SubtitleStyle 的 12sp / 30sp，HostLineSync 的 60000。
G 保持型（两版皆真，**无区分力**，只防「改 A 顺手弄坏 B」）：旧横幅、旧预取 TAG。

用法
----
    python verify_1024.py [apk_new] [apk_old]
退出码 0 = 全部通过
"""

import os
import re
import subprocess
import sys
import tempfile
import zipfile

BT = r'F:\WorkBuddyCache\DLSiteSound_Plus\toolchain\android-sdk\build-tools\34.0.0'
AAPT2 = os.path.join(BT, 'aapt2.exe')
DEXDUMP = os.path.join(BT, 'dexdump.exe')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UP = os.path.dirname(ROOT)                    # F:/WorkBuddyCache/DLSiteSound_Plus
APK_NEW = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    ROOT, 'app', 'build', 'outputs', 'apk', 'debug', 'DLsiteFloat-2.3.5-code1024-debug.apk')
APK_OLD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    UP, 'DLsiteFloat-2.3.5-code1023-debug.apk')

PKG = 'Lio/github/ariinyume/dlsitesoundfloat'

fails = []
total = 0
disc = 0          # 有区分力的判定条数（PASS 里「新包有 / 对照包无」那些）
nodisc = []       # 无区分力的条目名（两版皆真）


def check(name, ok, detail=''):
    global total
    total += 1
    if ok:
        print('  PASS  %s' % name)
    else:
        print('  FAIL  %s   %s' % (name, detail))
        fails.append(name)


def dex_bytes(apk):
    """把所有 classes*.dex 的字节拼起来（字符串池与类型描述符都在其中，做存在性判定足够）。"""
    out = []
    with zipfile.ZipFile(apk) as z:
        for n in sorted(z.namelist()):
            if re.match(r'classes\d*\.dex$', n):
                out.append(z.read(n))
    return b'\x00'.join(out)


def has(dex, s):
    if isinstance(s, str):
        s = s.encode('utf-8')
    return s in dex


def badging(apk):
    try:
        r = subprocess.run([AAPT2, 'dump', 'badging', apk],
                           capture_output=True, timeout=120)
        return r.stdout.decode('utf-8', 'replace')
    except Exception as e:                     # noqa: BLE001
        return 'ERR:%s' % e


def class_sections(apk, wanted):
    """
    只对**含目标类的那些 dex** 跑 dexdump -d，再按类头切成「描述符 → 段落」。
    （classes.dex 有 9 MB、全量 dump 出 118 MB，没必要全跑。）
    """
    tmp = tempfile.mkdtemp(prefix='v1024_')
    names = []
    with zipfile.ZipFile(apk) as z:
        for n in sorted(z.namelist()):
            if not re.match(r'classes\d*\.dex$', n):
                continue
            b = z.read(n)
            if any(w.encode('utf-8') in b for w in wanted):
                z.extract(n, tmp)
                names.append(n)
    sections = {}
    for n in names:
        r = subprocess.run([DEXDUMP, '-d', os.path.join(tmp, n)],
                           capture_output=True, timeout=600)
        txt = r.stdout.decode('utf-8', 'replace')
        for sec in re.split(r'(?m)^Class #\d+\s+-', txt)[1:]:
            m = re.search(r"Class descriptor  : '([^']+)'", sec)
            if m:
                sections[m.group(1)] = sec
    return sections


def main():
    global disc
    print('主验包：%s' % APK_NEW)
    print('对照包：%s\n' % APK_OLD)
    if not os.path.exists(APK_NEW):
        print('主验包不存在')
        return 2
    if not os.path.exists(APK_OLD):
        print('对照包不存在（删除类改动没有基准 ⇒ 无法判定）')
        return 2

    new = dex_bytes(APK_NEW)
    old = dex_bytes(APK_OLD)

    def pair(name, needle):
        """新包必须**有**、对照包必须**没有**（有区分力）。"""
        global disc
        hn = has(new, needle)
        ho = has(old, needle)
        ok = hn and not ho
        if ok:
            disc += 1
        check(name, ok, 'new=%s old=%s' % (hn, ho))

    def gone(name, needle):
        """新包必须**没有**、对照包必须**有**（删除类改动，有区分力）。"""
        global disc
        hn = has(new, needle)
        ho = has(old, needle)
        ok = (not hn) and ho
        if ok:
            disc += 1
        check(name, ok, 'new=%s old=%s' % (hn, ho))

    def keep(name, needle):
        """两版皆真 —— 无区分力，只防回归。"""
        hn = has(new, needle)
        ho = has(old, needle)
        if hn and ho:
            nodisc.append(name)
        check(name + '（无区分力：两版皆真）', hn and ho, 'new=%s old=%s' % (hn, ho))

    # ---------- A 版本 ----------
    print('A 版本（aapt2 badging）')
    bg = badging(APK_NEW)
    check('versionCode 1024', re.search(r"versionCode='1024'", bg) is not None,
          (re.search(r"versionCode='\d+'", bg) or ['?'])[0] if bg else 'ERR')
    check('versionName 2.3.5', re.search(r"versionName='2\.3\.5'", bg) is not None)
    check('包名未变', re.search(r"package: name='io\.github\.ariinyume\.dlsitesoundfloat'", bg) is not None)
    banner = '[DLsiteSoundFloat] ==== BUILD 2.3.5 / code 1024'
    pair('常开横幅串进包（2.3.5 / 1024）', banner)

    # ---------- B 新类型 ----------
    print('\nB 新类型以类型描述符形态进包')
    sections = class_sections(APK_NEW,
                              ['HostStyleProbe', 'HostLineSync', 'SubtitleStyle',
                               'SubtitleCache', 'ZiptreePrefetch'])
    for cls in ('util/HostStyleProbe', 'hook/HostLineSync'):
        d = PKG + '/' + cls + ';'
        pair('类型描述符进包：%s' % cls.split('/')[-1],
             d)
        check('  该类的类体真的在 dex 里（不是只留个字符串）', d in sections,
              'sections=%d' % len(sections))

    # ---------- C 新字符串 ----------
    print('\nC 新字符串（逐条 probe 对照包）')
    print(' C1 gzip 两层修法')
    pair('解压里程碑日志', 'peek: gzip body inflated ')
    pair('解压超限日志', 'gunzip dropped (inflated > limit=')
    pair('二进制丢弃日志', 'peek dropped: body looks binary (')
    pair('预取层结构校验日志', 'skip (not a complete ziptree: ')
    pair('结构校验的说明（等解压那一份）', 'waiting for the inflated copy')
    pair('GZIPInputStream 真的被引用（类型描述符）', 'Ljava/util/zip/GZIPInputStream;')
    keep('ByteArrayInputStream 描述符在包内', 'Ljava/io/ByteArrayInputStream;')

    print(' C2 作品维强约束')
    pair('缓存歧义放弃日志', 'hit REFUSED (ambiguous across works)')
    pair('跨作品并存日志', 'identity shared by ')
    pair('同作品同槽取最近使用日志', 'entries of the SAME work ->')
    pair('预取池歧义放弃日志', 'AMBIGUOUS dur=')
    pair('预取池放弃说明', 'refuse hit')
    pair('预取命中标注：作品键认人', '[work-scoped]')
    pair('预取命中标注：唯一候选', '[sole candidate]')

    print(' C3 P1-8 七个 extra 与读数文案')
    for e in ('cache_hits', 'cache_misses', 'prefetch_works',
              'prefetch_tracks', 'line_matched', 'line_mismatched', 'line_samples'):
        pair('extra 串：%s' % e, e)
    pair('读数文案：命中', '命中 %1$d/%2$d 次')
    pair('读数文案：预取', '预取 %1$d 部 / %2$d 轨')
    pair('读数文案：上屏行', '上屏行一致 %1$d/%2$d')

    print(' C4 P1-7 样式跟随')
    pair('配置键串', 'follow_host_style')
    pair('开关文案', '跟随宿主字幕样式')
    pair('宿主样式采样日志', 'host subtitle style: size=')

    print(' C5 P1-5 观测')
    pair('上屏行不一致日志', 'MISMATCH (first): host=')
    pair('观测汇总类 TAG（自报口径）', 'host-line')

    # ---------- D 新方法名 ----------
    print('\nD 新方法名进包')
    for m in ('pickLocked', 'sameWork', 'hasDuration'):
        pair('方法名：%s' % m, m)
    # ⚠️ works / tracks 是**极短且通用**的名字，裸名 probe 两版皆真（1023 的 summary
    #    串里就有 " works / "），只能走「方法头 + 描述符」判，且必须回对照包对照。
    sec_new = sections.get(PKG + '/hook/ZiptreePrefetch;', '')
    sec_old = class_sections(APK_OLD, ['ZiptreePrefetch']).get(
        PKG + '/hook/ZiptreePrefetch;', '')
    check('两端类体都拿到（ZiptreePrefetch）', bool(sec_new) and bool(sec_old),
          'new=%s old=%s' % (bool(sec_new), bool(sec_old)))
    for m in ('works', 'tracks'):
        pat = r"name\s*:\s*'%s'\s*\n\s*type\s*:\s*'\(\)I'" % m
        hn = bool(sec_new) and re.search(pat, sec_new) is not None
        ho = bool(sec_old) and re.search(pat, sec_old) is not None
        ok = hn and not ho
        if ok:
            disc += 1
        check('方法头：%s(): int（新包有，对照包无）' % m, ok, 'new=%s old=%s' % (hn, ho))

    # ---------- E 删除类改动 ----------
    print('\nE 删除类改动（基准 = 上一版）')
    gone('旧文案「离线 · 无缓存」已消失', '离线 · 无缓存')
    gone('旧文案「离线 · 无字幕缓存（联网播放一次即可缓存）」已消失',
         '离线 · 无字幕缓存')
    gone('旧文案函数名 offlineNoCache 已消失', 'offlineNoCache')
    gone('旧文案函数名 offlineNoCacheHint 已消失', 'offlineNoCacheHint')

    # ---------- F 常量层 ----------
    print('\nF 常量层（数值改动只能在这一层验）')
    probe = sections.get(PKG + '/util/HostStyleProbe;', '')
    check('HostStyleProbe 类体拿到', bool(probe))
    if probe:
        check('采样下限 8f 以立即数形态在包内', '// #4100' in probe, '8f=0x41000000')
        check('采样上限 240f 以立即数形态在包内', '// #4370' in probe, '240f=0x43700000')
        check('抖动阈值 0.5f 以立即数形态在包内', '// #3f00' in probe, '0.5f=0x3f000000')
    style = sections.get(PKG + '/view/SubtitleStyle;', '')
    check('SubtitleStyle 类体拿到', bool(style))
    if style:
        check('宿主字号下限 12sp 在包内', '// #4140' in style, '12f=0x41400000')
        check('宿主字号上限 30sp 在包内', '// #41f0' in style, '30f=0x41f00000')
    sync = sections.get(PKG + '/hook/HostLineSync;', '')
    check('HostLineSync 类体拿到', bool(sync))
    if sync:
        check('汇总节流 60000ms 落在字段常量上（long 保留 value 行）',
              re.search(r"name\s*:\s*'SUMMARY_INTERVAL_MS'.*?value\s*:\s*60000", sync, re.S) is not None,
              'value 行缺失' if 'SUMMARY_INTERVAL_MS' in sync else '字段缺失')

    # ---------- G 保持型 ----------
    print('\nG 保持型（无区分力，只防回归）')
    keep('上一版横幅仍在（降为 debug 但没删）', '[DLsiteSoundFloat] ==== BUILD 2.3.5 / code 1023')
    keep('预取器 TAG 仍在', 'ZiptreePrefetch')
    keep('缓存 TAG 仍在', 'SubtitleCache')

    print()
    print('总计 %d 条，通过 %d 条，失败 %d 条' % (total, total - len(fails), len(fails)))
    print('有区分力锚数：%d（「新包有 / 对照包无」或反向）；无区分力条目：%d'
          % (disc, len(nodisc)))
    if nodisc:
        print('  无区分力项（如实标注，不当作本轮证据）：')
        for x in nodisc:
            print('    - %s' % x)
    if fails:
        print('失败项：')
        for x in fails:
            print('  - %s' % x)
        return 1
    print('verify_1024: ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
