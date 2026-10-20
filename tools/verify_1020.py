#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1020 / v2.3.3】「关掉代理后切音轨拉不起本地字幕 + 没有缓存的音轨显示别轨字幕」修复的
**dex 字节码层**硬验证

为什么需要它
------------
源码改了但没编进包，是这类项目最常见的假绿。本脚本只认字节码：
字段是否真落成字段、方法体里到底访问了哪张表、判据串是否真进了 dex。

对照口径（铁律：删除类改动的基准是「上一版」，第三参固定不滚动）
----------------------------------------------------------------
  · 主验   = code 1020 包（本轮构建产物）
  · 对照   = code 1019 包（上一版交付包）
  · 反向   = code 1011 包（**固定不滚动**，只做轻量断言）

验什么
------
A  读取路径只认强键：`lookup` / `has` 体内**不再**访问弱键表 `bySelection`；旧的三条
   拒绝/自愈串绝迹；新的「不一致也放行」串与「身份时间轴不符」串进包；
   `lookup` 体内 `removeEntryLocked` 调用从 2 处降到 1 处。
B  前身按文件识别：新字段 `byFile:Ljava/util/Map;` 编进包；`put` 体内访问它；
   强键表索引的 Map 字段数 3 -> 4；`stampDuration` 出现「同身份让位」串。
C  时间轴校验补反向：`timelineFits` 体内读取条目自己的 `durMs:J`（旧版只读 `maxEnd:D`）。
D  清毒：静态字段 `INDEX_SCHEMA` 的值 3 -> 4。
E  版本：常开横幅串 `==== BUILD 2.3.3 / code 1020` 进包；`aapt2 dump badging` 的
   versionCode=1020 / versionName=2.3.3。⚠️ label（1014.8）**不进包**是既定事实，不判。
F  身份锚（两版皆真，**无区分力**，只防「改 A 顺手弄坏 B」）：五个对外签名、数据仓库的
   调用形态、`SubtitleCache$Entry` 的字段、`timelineFits` 签名、Interfaces 段含 LineSource。
G  反向对照（固定 1011）：本轮新符号在更老的包里也不存在。

用法
----
    python verify_1020.py [apk_1020] [apk_1019] [apk_1011]
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
                       'DLsiteFloat-2.3.3-code1020-debug.apk')
APK_OLD = os.path.join(UP, 'DLsiteFloat-2.3.2-code1019-debug.apk')
APK_REV = os.path.join(UP, 'DLsiteFloat-2.3.1-code1011-debug.apk')

PKG = 'io/github/ariinyume/dlsitesoundfloat'
CLS = {
    'cache': '%s.data.SubtitleCache' % PKG.replace('/', '.'),
    'repo': '%s.data.SubtitleRepository' % PKG.replace('/', '.'),
    'mod': '%s.DlsiteSoundSubtitleModule' % PKG.replace('/', '.'),
}
C_CACHE = 'L%s/data/SubtitleCache;' % PKG
C_REPO = 'L%s/data/SubtitleRepository;' % PKG
C_MOD = 'L%s/DlsiteSoundSubtitleModule;' % PKG
SIG_ENTRY = 'L%s/data/SubtitleCache$Entry;' % PKG
SIG_LINE = 'L%s/util/LineSource;' % PKG

LK_SIG = '(JJLjava/lang/String;)Ljava/lang/String;'
HS_SIG = '(JJ)Z'
TF_SIG = '(%sJ)Z' % SIG_ENTRY
SM_SIG = '(JJ)V'
PUT_SIG = '(Ljava/lang/String;IIJLjava/lang/String;ID)V'

BANNER_NEW = '==== BUILD 2.3.3 / code 1020'
BANNER_OLD = '==== BUILD 2.3.2 / code 1019'

# 本轮删掉的串（必须在主验绝迹、在对照存在）
GONE = [
    'hit REJECTED (work-key mismatch)',
    'hit REJECTED (selection-only, timeline mismatch) -> self-heal drop:',
    ' (selection-only)',
]
# 本轮新增的串（必须在主验存在、在对照不存在）
NEW_STR = [
    'hit ACCEPTED despite work-key mismatch',
    'hit REJECTED (identity, timeline mismatch)',
    'stamp: identity already held by another entry',
]

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


def method_body(dump, cls, name, mtype):
    """
    按 dexdump 的方法头行切方法体：
      `] io.…SubtitleCache.lookup:(JJLjava/lang/String;)Ljava/lang/String;`
    ⚠️ 头行可能带偏移前缀、也可能不带 ⇒ 用 `] <cls>.<name>:<type>` 这个后缀找。
      指令行里的调用形态是 `L…;.name:(…)`，中间多一个 `;`，与本锚不冲突。
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


def has_method(seg, name, mtype):
    if not seg:
        return False
    return re.search(r"name\s*:\s*'%s'\s*\n\s*type\s*:\s*'%s'"
                     % (re.escape(name), re.escape(mtype)), seg) is not None


def has_field(seg, name, ftype, value=None):
    """
    value=None  ⇒ 只断言「字段存在、类型正确」，**不要求 value 行**
       （非编译期常量字段 dexdump 只打 name/type/access）。
    value='4' ⇒ 必须是编译期常量且取该值。
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


def raw_has(apk, s):
    """轻量：直接在 dex 字节里搜字符串（不 dump）。"""
    b = s.encode('utf-8')
    with zipfile.ZipFile(apk) as z:
        for n in z.namelist():
            if n.endswith('.dex') and b in z.read(n):
                return True
    return False


def badging(apk):
    r = subprocess.run([AAPT2, 'dump', 'badging', apk], capture_output=True, text=True,
                       errors='replace', encoding='utf-8')
    return r.stdout


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
    nd = open(dexdump_all(apk_new, dump_path(apk_new)), encoding='utf-8',
              errors='replace').read()
    od = open(dexdump_all(apk_old, dump_path(apk_old)), encoding='utf-8',
              errors='replace').read()
    print('  dump 完成（主验 %d / 对照 %d 字符）' % (len(nd), len(od)))
    print()

    cn, co = slice_class(nd, C_CACHE), slice_class(od, C_CACHE)
    rn, ro = slice_class(nd, C_REPO), slice_class(od, C_REPO)
    mn, mo = slice_class(nd, C_MOD), slice_class(od, C_MOD)
    en, eo = slice_class(nd, SIG_ENTRY), slice_class(od, SIG_ENTRY)
    check('目标类都切到（主验）',
          all(x is not None for x in (cn, rn, mn, en)),
          'cache=%s repo=%s mod=%s entry=%s'
          % (cn is not None, rn is not None, mn is not None, en is not None))
    if cn is None or rn is None:
        print('类切片失败 —— 后续判据无意义，直接 FAIL')
        print('FAIL')
        return 1

    lk_n = method_body(nd, CLS['cache'], 'lookup', LK_SIG)
    lk_o = method_body(od, CLS['cache'], 'lookup', LK_SIG)
    hs_n = method_body(nd, CLS['cache'], 'has', HS_SIG)
    hs_o = method_body(od, CLS['cache'], 'has', HS_SIG)
    tf_n = method_body(nd, CLS['cache'], 'timelineFits', TF_SIG)
    tf_o = method_body(od, CLS['cache'], 'timelineFits', TF_SIG)
    sm_n = method_body(nd, CLS['cache'], 'stampDuration', SM_SIG)
    sm_o = method_body(od, CLS['cache'], 'stampDuration', SM_SIG)
    pt_n = method_body(nd, CLS['cache'], 'put', PUT_SIG)
    pt_o = method_body(od, CLS['cache'], 'put', PUT_SIG)

    # ================= A. 读取路径只认强键 =================
    print('=== A. 读取路径只认强键【本轮核心】===')
    check('lookup / has / put / stampDuration / timelineFits 方法体都切到',
          all(bool(x) for x in (lk_n, lk_o, hs_n, hs_o, tf_n, tf_o, sm_n, sm_o, pt_n, pt_o)),
          'lookup=%d has=%d tf=%d sm=%d put=%d' % (len(lk_n), len(hs_n), len(tf_n),
                                                   len(sm_n), len(pt_n)))
    dual('lookup 体内**不再**访问弱键表 bySelection',
         '.bySelection:' not in lk_n, '.bySelection:' not in lk_o)
    dual('has 体内**不再**访问弱键表 bySelection',
         '.bySelection:' not in hs_n, '.bySelection:' not in hs_o)
    n_rm_n = lk_n.count('.removeEntryLocked:')
    n_rm_o = lk_o.count('.removeEntryLocked:')
    dual('lookup 体内 removeEntryLocked 调用 2 处 -> 1 处（只剩「文件读不出来」那条）',
         n_rm_n == 1, n_rm_o == 1,
         '主验 %d 处 / 对照 %d 处' % (n_rm_n, n_rm_o))
    check('lookup 体内仍访问强键表 byIdentity（判据保留）',
          '.byIdentity:' in lk_n and '.byIdentity:' in lk_o)
    check('lookup 体内仍调用 timelineFits（护栏保留）', '.timelineFits:' in lk_n)

    print('=== A2. 旧串绝迹 / 新串进包（字符串池）===')
    for s in GONE:
        dual('旧串绝迹：%r' % s[:52], not raw_has(apk_new, s), not raw_has(apk_old, s))
    for s in NEW_STR:
        dual('新串进包：%r' % s[:52], raw_has(apk_new, s), raw_has(apk_old, s))

    # ================= B. 前身按文件识别 =================
    print('=== B. 前身按文件识别 ===')
    dual('新字段 byFile:Ljava/util/Map; 编进包',
         has_field(cn, 'byFile', 'Ljava/util/Map;', None),
         has_field(co, 'byFile', 'Ljava/util/Map;', None))
    dual('put 体内访问 byFile（前身改按文件找）',
         '.byFile:' in pt_n, '.byFile:' in pt_o)
    map_fields_n = len(re.findall(r"type\s*:\s*'Ljava/util/Map;'", cn))
    map_fields_o = len(re.findall(r"type\s*:\s*'Ljava/util/Map;'", co))
    dual('索引用的 Map 字段数 3 -> 4（多出 byFile）',
         map_fields_n == 4, map_fields_o == 4,
         '主验 %d / 对照 %d' % (map_fields_n, map_fields_o))
    check('put 体内仍把条目挂进强键表（byIdentity）', '.byIdentity:' in pt_n)
    check('put 体内仍用 bySelection 挂孤儿（读侧不用它）', '.bySelection:' in pt_n)
    check('stampDuration 补盖后从孤儿槽位摘除',
          '.bySelection:' in sm_n and '.remove:' in sm_n)
    check('stampDuration 体内仍写强键表', '.byIdentity:' in sm_n)
    check('loadIndexLocked 切到', bool(method_body(nd, CLS['cache'], 'loadIndexLocked', '()V')))

    # ================= C. 时间轴校验补反向 =================
    print('=== C. 时间轴校验补反向 ===')
    dual('timelineFits 体内读取条目自己的 durMs:J（旧版只读 maxEnd:D）',
         '.durMs:J' in tf_n, '.durMs:J' in tf_o)
    check('timelineFits 体内仍读 maxEnd:D（旧尺子保留）',
          '.maxEnd:D' in tf_n and '.maxEnd:D' in tf_o)

    # ================= D. 清毒 =================
    print('=== D. 清毒 ===')
    dual('静态字段 INDEX_SCHEMA 的值 3 -> 4',
         has_field(cn, 'INDEX_SCHEMA', 'I', '4'),
         has_field(co, 'INDEX_SCHEMA', 'I', '4'))
    check('对照包 INDEX_SCHEMA 确为 3（口径自证）',
          has_field(co, 'INDEX_SCHEMA', 'I', '3'))

    # ================= E. 版本 =================
    print('=== E. 版本 ===')
    dual('常开横幅串进包：%s' % BANNER_NEW,
         raw_has(apk_new, BANNER_NEW), raw_has(apk_old, BANNER_NEW))
    check('上一轮横幅串仍是历史段（回归锚）', raw_has(apk_new, BANNER_OLD))
    bg = badging(apk_new)
    check('badging versionCode=1020', "versionCode='1020'" in bg or 'versionCode="1020"' in bg,
          re.search(r"versionCode='\d+'", bg).group(0) if re.search(r"versionCode='\d+'", bg) else '')
    check('badging versionName=2.3.3', 'versionName=\'2.3.3\'' in bg,
          re.search(r"versionName='[^']*'", bg).group(0) if re.search(r"versionName='[^']*'", bg) else '')
    check('label 不进包（1020 的 1014.8 在 dex 里查不到 —— 既定事实）',
          not raw_has(apk_new, '1014.8'))

    # ================= F. 身份锚（无区分力，防回归）=================
    print('=== F. 身份锚（两版皆真，只防「改 A 弄坏 B」）===')
    for nm, sig, seg in (('lookup', LK_SIG, cn), ('has', HS_SIG, cn),
                         ('stampDuration', SM_SIG, cn), ('put', PUT_SIG, cn),
                         ('timelineFits', TF_SIG, cn)):
        check('SubtitleCache.%s%s 仍在' % (nm, sig), has_method(seg, nm, sig))
    check('数据仓库仍调 lookup（签名未变）',
          'SubtitleCache;.lookup:%s' % LK_SIG in rn)
    check('数据仓库仍调 has（签名未变）',
          'SubtitleCache;.has:%s' % HS_SIG in rn)
    check('数据仓库仍调 stampDuration（签名未变）',
          'SubtitleCache;.stampDuration:%s' % SM_SIG in rn)
    check('数据仓库仍调 put（签名未变）',
          'SubtitleCache;.put:%s' % PUT_SIG in rn)
    for f in ('identity', 'selection', 'workKey', 'durMs', 'maxEnd', 'hash'):
        check("SubtitleCache$Entry 字段 %s 仍在" % f,
              re.search(r"name\s*:\s*'%s'\s*\n" % f, en or '') is not None)
    check('SubtitleRepository 实现 LineSource（Interfaces 段）',
          SIG_LINE in ifaces(rn) and SIG_LINE in ifaces(ro))

    # ================= G. 反向对照（固定 1011）=================
    print('=== G. 反向对照（固定 1011，不滚动）===')
    rd = open(dexdump_all(apk_rev, dump_path(apk_rev)), encoding='utf-8',
              errors='replace').read()
    cr = slice_class(rd, C_CACHE)
    check('1011 包里没有 byFile 字段',
          bool(cr) and not has_field(cr, 'byFile', 'Ljava/util/Map;', None))
    check('1011 包里没有 1020 横幅串', not raw_has(apk_rev, BANNER_NEW))
    check('1011 包里备尺子只有单向（无 durMs 反向读取）',
          '.durMs:J' not in method_body(rd, CLS['cache'], 'timelineFits', TF_SIG))
    check('1011 包里 INDEX_SCHEMA 还不是 4',
          not has_field(cr, 'INDEX_SCHEMA', 'I', '4'))

    print()
    print('总计 %d 条，通过 %d 条，失败 %d 条'
          % (TOTAL, TOTAL - len(FAILS), len(FAILS)))
    print('有区分力锚 %d 条；无区分力（同一性）%d 条' % (TOTAL - len(FAILS) - len(NO_DISC),
                                                len(NO_DISC)))
    if FAILS:
        print('失败项：')
        for f in FAILS:
            print('  - %s' % f)
        print('FAIL')
        return 1
    print('verify_1020: ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
