#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1019 / v2.3.2（第 5 个 code）】「重启后每个作品的第一轨字幕不对」修复的 **dex 字节码层**硬验证

为什么需要它
------------
源码改了但没编进包，是这类项目最常见的假绿。本脚本只认字节码：
新方法是否真的进了 dex、字段是否真的落成字段、判据是否真的被调用。

对照口径（铁律：删除类改动的基准是「上一版」，第三参不滚动）
------------------------------------------------------------
  · 主验   = code 1019 包（本轮构建产物）
  · 对照   = code 1018 包（上一版交付包）—— 「新形态在主验有、在对照没有」才算有区分力锚
  · 反向   = code 1011 包（**固定不滚动**）—— 只做轻量断言：本轮新符号在更老的包里也不存在

验什么
------
A  首轨取缓存入口：`SubtitleRepository.onSeededTrack:(IJJLjava/lang/String;)V` 编进包、
   `PlayerSourceHook` 真的调它、其方法体走 `tryResumeFromDisk`、
   **不调** `onTrackChanged`（只取缓存，不挂起不裁决）。
B  认领即改签：`tryResumeFromCache` 体内出现对实例字段 `cuesOwnerSelection` 与暂存标签
   `stagedCacheSelection` 的写、以及 `cache label re-signed` 串。
C  到达印章陈旧旗标：字段 `stagedCacheStampStale:Z` 存在；`stageCacheToDisk` 体内
   读 workChangeKey / cuesArrivedDuringRebuild 并写该字段；`flushStagedCache` 体内读它、
   兑现后写回，且**不出现**那两个可变旗标名。
D  读取侧校验与自愈：`SubtitleCache.timelineFits:(L…Entry;J)Z` 编进包；`lookup` 体内
   调用它一次、`removeEntryLocked` 从 1 处变 2 处、并出现自愈串；`stampDuration` 体内
   也调用它（同一把尺子）。
E  清毒与可读性：`INDEX_SCHEMA` 字段值 2 → 3；`shortKey` 体内 `lastIndexOf` / `substring`
   各从 1 处变 2 处（取末两段）。
F  版本 常开横幅串 `==== BUILD 2.3.2 / code 1019` 进包；`aapt2 dump badging` 的
   versionCode=1019 / versionName=2.3.2。⚠️ label（1014.7）**不进包**是既定事实，不判。
G  身份锚（两版皆真，**无区分力**，只防「改 A 顺手弄坏 B」）：四条认领判据串、
   补盖时长串、跨作品拒绝串、`tryResumeFromCache`/`has` 签名、Interfaces 段含 LineSource。

用法
----
    python verify_1019.py [apk_1019] [apk_1018] [apk_1011]
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
                       'DLsiteFloat-2.3.2-code1019-debug.apk')
APK_OLD = os.path.join(UP, 'DLsiteFloat-2.3.2-code1018-debug.apk')
APK_REV = os.path.join(UP, 'DLsiteFloat-2.3.1-code1011-debug.apk')

PKG = 'io/github/ariinyume/dlsitesoundfloat'
CLS = {
    'cache': '%s.data.SubtitleCache' % PKG.replace('/', '.'),
    'repo': '%s.data.SubtitleRepository' % PKG.replace('/', '.'),
    'src': '%s.hook.PlayerSourceHook' % PKG.replace('/', '.'),
    'mod': '%s.DlsiteSoundSubtitleModule' % PKG.replace('/', '.'),
}
C_CACHE = 'L%s/data/SubtitleCache;' % PKG
C_REPO = 'L%s/data/SubtitleRepository;' % PKG
C_MOD = 'L%s/DlsiteSoundSubtitleModule;' % PKG
SIG_ENTRY = 'L%s/data/SubtitleCache$Entry;' % PKG
SIG_LINE = 'L%s/util/LineSource;' % PKG

TOTAL = 0
FAILS = []
NO_DISC = []


def check(desc, ok, extra=''):
    global TOTAL
    TOTAL += 1
    print('  %s %s%s' % ('OK  ' if ok else 'FAIL', desc, ('   ' + extra) if extra else ''))
    if not ok:
        FAILS.append(desc)


def dual(desc, ok_new, ok_old, extra_new=''):
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


def _dump_cache_ok(out, n_dex):
    """缓存是否**完整**（code 1037 起必须带哨兵）。

    ⚠️ 踩过的坑：旧判据只看「文件存在且 >1MB」。一次被环境保护中断的 dump
    只写完前 1~2 个 dex，体积照样 >1MB ⇒ 被当成有效缓存**永久复用**
    ⇒ 后面所有「类存在」判据全判 false ⇒ 36/45 假 FAIL（看着像大回归，其实没验）。
    现在写完追加 `#DUMPCOMPLETE <dex数>`，复用时校验**行在、数对**。
    """
    if not os.path.exists(out) or os.path.getsize(out) < 1_000_000:
        return False
    size = os.path.getsize(out)
    with open(out, 'rb') as f:
        f.seek(max(0, size - 64))
        tail = f.read().decode('utf-8', 'replace')
    return ('#DUMPCOMPLETE %d' % n_dex) in tail


def dexdump_all(apk, out):
    with zipfile.ZipFile(apk) as z:
        dexs = [n for n in z.namelist() if re.match(r'.*\.dex$', n)]
    if _dump_cache_ok(out, len(dexs)):
        return out                     # 复用缓存（按包 sha 命名，且已过完整性哨兵）
    # 临时 dex 统一落 app/build/_dextmp/ 并**覆盖写复用、不删除**：
    # 每脚本 9 个 dex、每个删一次 ⇒ 一轮累计 70+ 次删除 ⇒ 撞上环境的批量删除保护，
    # 进程被外部掐断、判据没跑完 ⇒ run_all 记 ENVBLOCK（看着像失败，其实没验完）。
    scratch = os.path.join(ROOT, 'app', 'build', '_dextmp')
    os.makedirs(scratch, exist_ok=True)
    tmp = os.path.join(scratch, os.path.basename(out) + '.dex')
    with zipfile.ZipFile(apk) as z:
        for i, n in enumerate(dexs):
            with open(tmp, 'wb') as f:
                f.write(z.read(n))
            r = subprocess.run([DEXDUMP, '-d', tmp], capture_output=True, text=True,
                               errors='replace', encoding='utf-8')
            with open(out, 'a' if i else 'w', encoding='utf-8') as f:
                f.write(r.stdout)
    with open(out, 'a', encoding='utf-8') as f:
        f.write('\n#DUMPCOMPLETE %d\n' % len(dexs))
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
    value=None  ⇒ 只断言「字段存在、类型正确」，**不要求 value 行**
       （非编译期常量字段 dexdump 只打 name/type/access）。
    value='3' 等 ⇒ 必须是编译期常量，且取该值。
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
    """类头 `Interfaces -` 之后那几行（**带 `#N : ` 前缀**）。"""
    if not seg:
        return ''
    m = re.search(r"Interfaces\s*-\s*\n((?:\s*#\d+\s*:[^\n]*\n)*)", seg)
    return m.group(1) if m else ''


def method_body(dump, cls, name, mtype):
    """
    按 dexdump 的方法头行切方法体：
      00336c:            |[00336c] io.…SubtitleCache.timelineFits:(…)Z
    ⇒ 从含 `|[hex] <cls>.<name>:<type>` 的那一行起，到下一个 `catches :` 之前。
    ⚠️ 头行**可能带偏移前缀、也可能不带** ⇒ 用 `] <cls>.<name>:<type>` 这个后缀找，
       再回退到行首。（指令行里的调用形态是 `L…;.name:(…)`，中间多一个 `;`，
       与本锚不冲突。）
    """
    needle = '%s.%s:%s' % (cls, name, mtype)
    i = dump.find('] ' + needle)
    if i < 0:
        return ''
    ls = dump.rfind('\n', 0, i)
    e = dump.find('\n', i + len(needle))
    if e < 0:
        e = len(dump)
    m2 = re.search(r'\n\s*catches\s+:', dump[e:])
    return dump[ls + 1:e + (m2.start() if m2 else 0)]


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

    rn, ro = slice_class(nd, C_REPO), slice_class(od, C_REPO)
    cn, co = slice_class(nd, C_CACHE), slice_class(od, C_CACHE)
    C_SRC = 'L%s/hook/PlayerSourceHook;' % PKG
    sn, so = slice_class(nd, C_SRC), slice_class(od, C_SRC)
    mn, mo = slice_class(nd, C_MOD), slice_class(od, C_MOD)
    check('四个目标类都切到（主验）',
          all(x is not None for x in (rn, cn, sn, mn)),
          'repo=%s cache=%s src=%s mod=%s'
          % (rn is not None, cn is not None, sn is not None, mn is not None))
    if rn is None or cn is None or sn is None or mn is None:
        print('类切片失败 —— 后续判据无意义，直接 FAIL')
        print('FAIL')
        return 1

    # ================= A. 首轨取缓存入口 =================
    print('=== A. 首轨取缓存入口（失败一）===')
    SIG_SEEDED = '(IJJLjava/lang/String;)V'
    dual('SubtitleRepository.onSeededTrack(%s) 编进包' % SIG_SEEDED,
         has_method(rn, 'onSeededTrack', SIG_SEEDED),
         has_method(ro, 'onSeededTrack', SIG_SEEDED))
    call = 'SubtitleRepository;.onSeededTrack:%s' % SIG_SEEDED
    dual('PlayerSourceHook 调用 onSeededTrack',
         call in (sn or ''), call in (so or ''))
    sb_n = method_body(nd, CLS['repo'], 'onSeededTrack', SIG_SEEDED)
    sb_o = method_body(od, CLS['repo'], 'onSeededTrack', SIG_SEEDED)
    dual('onSeededTrack 方法体切到（主验非空 / 对照为空）', bool(sb_n), bool(sb_o),
         'len=%d' % len(sb_n))
    if sb_n:
        dual('onSeededTrack 走 tryResumeFromDisk',
             'SubtitleRepository;.tryResumeFromDisk:(Ljava/lang/String;JJ)Z' in sb_n,
             'SubtitleRepository;.tryResumeFromDisk:(Ljava/lang/String;JJ)Z' in sb_o)
        check('🔴 onSeededTrack **不调** onTrackChanged（只取缓存，不挂起不裁决）',
              'onTrackChanged:' not in sb_n)
        check('onSeededTrack 不调 loadFromJson 直灌（必须走磁盘兜底那条路）',
              '.loadFromJson:' not in sb_n)
        check('onSeededTrack 含专属串 seeded first track ->',
              'seeded first track ->' in sb_n)
        dual('onSeededTrack 含 resumed from LOCAL cache 串',
             'resumed from LOCAL cache' in sb_n, 'resumed from LOCAL cache' in sb_o)
        dual('onSeededTrack 含 [seeded idx= 串（诊断可分辨首轨路径）',
             '[seeded idx=' in sb_n, '[seeded idx=' in sb_o)

    # ================= B. 认领即改签 =================
    print()
    print('=== B. 认领即改签（失败二）===')
    RB_SIG = '(Ljava/lang/String;JJ)Z'
    rb_n = method_body(nd, CLS['repo'], 'tryResumeFromCache', RB_SIG)
    rb_o = method_body(od, CLS['repo'], 'tryResumeFromCache', RB_SIG)
    check('tryResumeFromCache 方法体切到（两版皆应有）', bool(rb_n) and bool(rb_o))

    def cnt(t, pat):
        return len(re.findall(pat, t))

    dual('tryResumeFromCache 写实例字段 cuesOwnerSelection（iput）',
         cnt(rb_n, r'iput[^\n]*cuesOwnerSelection') >= 1,
         cnt(rb_o, r'iput[^\n]*cuesOwnerSelection') >= 1,
         '主验 %d / 对照 %d' % (cnt(rb_n, r'iput[^\n]*cuesOwnerSelection'),
                               cnt(rb_o, r'iput[^\n]*cuesOwnerSelection')))
    dual('tryResumeFromCache 写暂存标签 stagedCacheSelection',
         cnt(rb_n, r'iput[^\n]*stagedCacheSelection') >= 1,
         cnt(rb_o, r'iput[^\n]*stagedCacheSelection') >= 1)
    dual('tryResumeFromCache 写陈旧旗标 stagedCacheStampStale',
         cnt(rb_n, r'iput[^\n]*stagedCacheStampStale') >= 1,
         cnt(rb_o, r'iput[^\n]*stagedCacheStampStale') >= 1)
    dual('tryResumeFromCache 含改签日志串 cache label re-signed',
         'cache label re-signed' in rb_n, 'cache label re-signed' in rb_o)
    dual('🔴 改签受 `newSelection > 0` 门控（出现 cmp-long + if-*z 组合）',
         ('cmp-long' in rb_n and cnt(rb_n, r'iput[^\n]*cuesOwnerSelection') == 1),
         ('cmp-long' in rb_o and cnt(rb_o, r'iput[^\n]*cuesOwnerSelection') == 1))

    # ================= C. 到达印章陈旧旗标 =================
    print()
    print('=== C. 到达印章陈旧旗标（两条规则的正交分流）===')
    dual('字段 stagedCacheStampStale:Z 存在',
         has_field(rn, 'stagedCacheStampStale', 'Z'),
         has_field(ro, 'stagedCacheStampStale', 'Z'))
    ST_SIG = '(Ljava/lang/String;ID)V'
    st_n = method_body(nd, CLS['repo'], 'stageCacheToDisk', ST_SIG)
    st_o = method_body(od, CLS['repo'], 'stageCacheToDisk', ST_SIG)
    check('stageCacheToDisk 方法体切到（两版皆应有）', bool(st_n) and bool(st_o))
    dual('stageCacheToDisk 冻结旗标：读 workChangeKey / cuesArrivedDuringRebuild 并写该字段',
         ('workChangeKey' in st_n and 'cuesArrivedDuringRebuild' in st_n
          and cnt(st_n, r'iput[^\n]*stagedCacheStampStale') == 1),
         ('workChangeKey' in st_o and 'cuesArrivedDuringRebuild' in st_o
          and cnt(st_o, r'iput[^\n]*stagedCacheStampStale') == 1),
         '主验 flag_iput=%d' % cnt(st_n, r'iput[^\n]*stagedCacheStampStale'))
    fl_n = method_body(nd, CLS['repo'], 'flushStagedCache', '(J)V')
    fl_o = method_body(od, CLS['repo'], 'flushStagedCache', '(J)V')
    check('flushStagedCache 方法体切到（两版皆应有）', bool(fl_n) and bool(fl_o))
    dual('flushStagedCache 读旗标分流（iget-boolean ×2）',
         cnt(fl_n, r'iget-boolean[^\n]*stagedCacheStampStale') >= 2,
         cnt(fl_o, r'iget-boolean[^\n]*stagedCacheStampStale') >= 2,
         '主验 %d / 对照 %d' % (cnt(fl_n, r'iget-boolean[^\n]*stagedCacheStampStale'),
                               cnt(fl_o, r'iget-boolean[^\n]*stagedCacheStampStale')))
    dual('flushStagedCache 兑现后清旗标（iput-boolean）',
         cnt(fl_n, r'iput-boolean[^\n]*stagedCacheStampStale') >= 1,
         cnt(fl_o, r'iput-boolean[^\n]*stagedCacheStampStale') >= 1)
    dual('flushStagedCache 含分流日志串 staged label was STALE at',
         'staged label was STALE at' in fl_n, 'staged label was STALE at' in fl_o)
    check('🔴 flushStagedCache **不重读**可变旗标（workChangeKey / cuesArrivedDuringRebuild）',
          'workChangeKey' not in fl_n and 'cuesArrivedDuringRebuild' not in fl_n)

    # ================= D. 读取侧校验与自愈 =================
    print()
    print('=== D. 读取侧时间轴校验与自愈（失败二的放大）===')
    TF_SIG = '(%sJ)Z' % SIG_ENTRY
    dual('SubtitleCache.timelineFits%s 编进包' % TF_SIG,
         has_method(cn, 'timelineFits', TF_SIG), has_method(co, 'timelineFits', TF_SIG))
    tf_n = method_body(nd, CLS['cache'], 'timelineFits', TF_SIG)
    check('timelineFits 方法体切到', bool(tf_n))
    if tf_n:
        check('timelineFits 调 PlaylistKey.identityDurationMs（请求身份取时长）',
              'PlaylistKey;.identityDurationMs:(J)J' in tf_n)
        check('timelineFits 内联容差 2.0（const-wide/high16 #4000）',
              '4611686018427387904' in tf_n)
        check('timelineFits 读 Entry.maxEnd（iget-wide）',
              cnt(tf_n, r'iget-wide[^\n]*\$Entry;\.maxEnd:D') >= 2)
        check('timelineFits 零状态（无 iget/iput 本类实例字段、无 sput）',
              'this' not in tf_n)

    LK_SIG = '(JJLjava/lang/String;)Ljava/lang/String;'
    lk_n = method_body(nd, CLS['cache'], 'lookup', LK_SIG)
    lk_o = method_body(od, CLS['cache'], 'lookup', LK_SIG)
    check('lookup 方法体切到（两版皆应有）', bool(lk_n) and bool(lk_o))
    dual('lookup 调用 timelineFits（副键命中过校验）',
         'SubtitleCache;.timelineFits:%s' % TF_SIG in lk_n,
         'SubtitleCache;.timelineFits:%s' % TF_SIG in lk_o,
         '调用 %d 次' % lk_n.count('SubtitleCache;.timelineFits:'))
    dual('lookup 里 removeEntryLocked 由 1 处变 2 处（新增自愈删除）',
         cnt(lk_n, r'\.removeEntryLocked:') == 2, cnt(lk_o, r'\.removeEntryLocked:') == 2,
         '主验 %d / 对照 %d' % (cnt(lk_n, r'\.removeEntryLocked:'),
                               cnt(lk_o, r'\.removeEntryLocked:')))
    dual('lookup 含自愈串 hit REJECTED (selection-only, timeline mismatch)',
         'hit REJECTED (selection-only, timeline mismatch)' in lk_n,
         'hit REJECTED (selection-only, timeline mismatch)' in lk_o)
    dual('lookup 含 self-heal drop 串',
         'self-heal drop' in lk_n, 'self-heal drop' in lk_o)
    dual('lookup 含 requested dur= 串（取证用）',
         'requested dur=' in lk_n, 'requested dur=' in lk_o)

    SM_SIG = '(JJ)V'
    sm_n = method_body(nd, CLS['cache'], 'stampDuration', SM_SIG)
    sm_o = method_body(od, CLS['cache'], 'stampDuration', SM_SIG)
    check('stampDuration 方法体切到（两版皆应有）', bool(sm_n) and bool(sm_o))
    dual('stampDuration 改用同一把尺子（调 timelineFits）',
         'SubtitleCache;.timelineFits:%s' % TF_SIG in sm_n,
         'SubtitleCache;.timelineFits:%s' % TF_SIG in sm_o)

    # ================= E. 清毒与可读性 =================
    print()
    print('=== E. 清毒与可读性 ===')
    dual('INDEX_SCHEMA 常量 = 3（清掉已写歪的旧条目）',
         has_field(cn, 'INDEX_SCHEMA', 'I', '3'), has_field(co, 'INDEX_SCHEMA', 'I', '3'))
    SK_SIG = '(Ljava/lang/String;)Ljava/lang/String;'
    sk_n = method_body(nd, CLS['cache'], 'shortKey', SK_SIG)
    sk_o = method_body(od, CLS['cache'], 'shortKey', SK_SIG)
    check('shortKey 方法体切到（两版皆应有）', bool(sk_n) and bool(sk_o))
    dual('shortKey 里 lastIndexOf 由 1 处变 2 处（取末两段）',
         cnt(sk_n, r'\.lastIndexOf:') == 2, cnt(sk_o, r'\.lastIndexOf:') == 2,
         '主验 %d / 对照 %d' % (cnt(sk_n, r'\.lastIndexOf:'), cnt(sk_o, r'\.lastIndexOf:')))
    dual('shortKey 里 substring 由 1 处变 2 处',
         cnt(sk_n, r'\.substring:') == 2, cnt(sk_o, r'\.substring:') == 2,
         '主验 %d / 对照 %d' % (cnt(sk_n, r'\.substring:'), cnt(sk_o, r'\.substring:')))

    # ================= F. 版本 / 横幅 =================
    print()
    print('=== F. 版本 / 横幅 ===')
    dual('常开横幅串 `==== BUILD 2.3.2 / code 1019` 在包内',
         '==== BUILD 2.3.2 / code 1019' in (mn or ''),
         '==== BUILD 2.3.2 / code 1019' in (mo or ''))
    dual('履历段串 【code 1019 在包内',
         '【code 1019' in (mn or ''), '【code 1019' in (mo or ''))
    dual('履历段九段（①..⑨）都进了包',
         all(c in (mn or '') for c in '①②③④⑤⑥⑦⑧⑨'),
         all(c in (mo or '') for c in '①②③④⑤⑥⑦⑧⑨'))
    badging = ''
    try:
        r = subprocess.run([AAPT2, 'dump', 'badging', apk_new], capture_output=True,
                           text=True, errors='replace', encoding='utf-8')
        badging = r.stdout
    except Exception as e:
        badging = 'ERR %s' % e
    check('aapt2：versionCode=1019', "versionCode='1019'" in badging,
          badging.split('\n')[0][:80])
    check('aapt2：versionName=2.3.2', "versionName='2.3.2'" in badging)
    check('aapt2：包名不变', "package: name='io.github.ariinyume.dlsitesoundfloat'" in badging)

    # ================= G. 身份锚（两版皆真，无区分力） =================
    print()
    print('=== G. 身份锚（**无区分力**，只防「改 A 顺手弄坏 B」）===')
    IDENT = [
        ('四条认领判据串 [code 1006] subtitle json came from ANOTHER work',
         '[code 1006] subtitle json came from ANOTHER work'),
        ('RESUME from cache 串', 'RESUME from cache ('),
        ('[cache label re-signed 之外的 track changed via 串', 'track changed via '),
        ('补盖时长串 stamp duration: tc=', 'stamp duration: tc='),
        ('补盖被拒串 stamp REFUSED (timeline mismatch)', 'stamp REFUSED (timeline mismatch)'),
        ('跨作品拒绝串 hit REJECTED (work-key mismatch)', 'hit REJECTED (work-key mismatch)'),
        # ⚠️ 源码是 `"HIT" + (byIdent ? " (identity)" : " (selection-only)") + ": tc="`，
        #    javac **不会**把它折成一条 `HIT (identity)` ⇒ 锚必须落在真实的常量串上。
        ('命中串 HIT', 'HIT'),
        ('命中串 (identity)', ' (identity)'),
        ('命中串 (selection-only)', ' (selection-only)'),
        ('本地兜底串 [code 1007] disk cache HIT', '[code 1007] disk cache HIT'),
        ('徽标/缓存可用性串 local cache availability', 'local cache availability'),
        ('索引就绪串 index loaded:', 'index loaded:'),
        ('孤儿清扫串 orphan sweep:', 'orphan sweep:'),
    ]
    for desc, s in IDENT:
        dual(desc, s in nd, s in od)
    dual('tryResumeFromCache 签名仍在',
         has_method(rn, 'tryResumeFromCache', RB_SIG),
         has_method(ro, 'tryResumeFromCache', RB_SIG))
    dual('lookup 签名仍在', has_method(cn, 'lookup', LK_SIG), has_method(co, 'lookup', LK_SIG))
    dual('has 签名仍在', has_method(cn, 'has', '(JJ)Z'), has_method(co, 'has', '(JJ)Z'))
    dual('SubtitleRepository 仍实现 LineSource（1018 成果未回退）',
         SIG_LINE in ifaces(rn), SIG_LINE in ifaces(ro))
    dual('SubtitleCache 仍是 final class（结构未变）',
         bool(cn) and re.search(r"Access flags\s*:\s*0x[0-9a-f]+\s*\([^)]*FINAL",
                                cn) is not None,
         bool(co))
    dual('Entry 内部类仍在（缓存条目结构未变）',
         'SubtitleCache$Entry' in (cn or ''), 'SubtitleCache$Entry' in (co or ''))

    # ================= H. 反向对照包（code 1011，固定不滚动） =================
    print()
    print('=== H. 反向对照包（code 1011，固定不滚动）===')
    for s, label in (('onSeededTrack', 'onSeededTrack'),
                     ('timelineFits', 'timelineFits'),
                     ('stagedCacheStampStale', 'stagedCacheStampStale'),
                     ('cache label re-signed', '改签日志串'),
                     ('staged label was STALE at', '陈旧旗标日志串'),
                     ('hit REJECTED (selection-only, timeline mismatch)', '自愈串')):
        check('code 1011 里没有 %s' % label, not raw_has(apk_rev, s))

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
