import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from sdkpath import build_tools as _build_tools
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1021 / v2.3.3】「等官方字幕的窗口 3000ms → 1000ms」的 **dex 字节码层**硬验证。

为什么需要它
------------
本轮**只改了一个数值**。源码里把 3000L 改成 1000L 是编译期常量 ⇒ 它会被
**内联进指令的立即数**（`const-wide/16 vX, #1000`），字符串层与指令层都**看不到**
「哪个字段是多少」这个对应关系。唯一能验的地方是 dexdump 的**字段定义**
（`name / type / access / value`）—— 所以本脚本的 A 段读的就是它。

对照口径（铁律：删除类改动的基准是「上一版」，第三参固定不滚动）
----------------------------------------------------------------
  · 主验 = code 1021 包（本轮构建产物）
  · 对照 = code 1020 包（**上一版交付包**）
  · 反向 = code 1011 包（**固定不滚动**，只做轻量断言）

验什么
------
A  常量层【本轮核心】：
   ① 全包静态常量表逐项 diff —— **恰好只有一项**发生变化，且那一项正是本轮的改动
      （`SubtitleRepository.NO_SUBTITLE_GRACE_MS`：3000 → 1000）。这一条比逐个断言更硬：
      它能同时抓住「改漏了」与「手滑多改了别的常量」。
   ② 逐个复核：本轮值 1000、旧值 3000 在反转包（1011）里仍是 3000；
      与它并列的三个时限常量（PRELOAD 3500 / CACHED 15000 / EARLY_CLOSE 5000）
      与钩子侧静默窗（INDEX_SUPPRESS_MS 20000）**一个都没动**。
B  结构不动：`hasDiskCacheFor`(JJ)Z 仍在；缓存类五个对外签名仍在；缓存类仍被数据仓库调用；
   `INDEX_SCHEMA` 的值仍为 4（本轮**没碰**缓存层）。
C  版本：常开横幅串 `==== BUILD 2.3.3 / code 1021` 进包；`aapt2 dump badging` 的
   versionCode=1021 / versionName=2.3.3。⚠️ label（1015.1）**不进包**是既定事实，不判。
D  反向对照（固定 1011）：本轮新值/新横幅在更老的包里都不存在，且那里仍是 3000。
E  保持型（两版皆真，**无区分力**，只防「改 A 顺手弄坏 B」）：本轮没加任何新日志串，
   旧的取数/兜底串必须原样还在。

用法
----
    python verify_1021.py [apk_1021] [apk_1020] [apk_1011]
退出码 0 = 全部通过
"""

import hashlib
import os
import re
import subprocess
import sys
import zipfile

BT = _build_tools('34.0.0')
DEXDUMP = os.path.join(BT, 'dexdump.exe')
AAPT2 = os.path.join(BT, 'aapt2.exe')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UP = os.path.dirname(ROOT)          # 仓库的上一级（本机工作区）
APK_NEW = os.path.join(ROOT, 'app', 'build', 'outputs', 'apk', 'debug',
                       'DLsiteFloat-2.3.3-code1021-debug.apk')
APK_OLD = os.path.join(UP, 'DLsiteFloat-2.3.3-code1020-debug.apk')
APK_REV = os.path.join(UP, 'DLsiteFloat-2.3.1-code1011-debug.apk')

PKG = 'io/github/ariinyume/dlsitesoundfloat'
C_REPO = 'L%s/data/SubtitleRepository;' % PKG
C_SRC = 'L%s/hook/PlayerSourceHook;' % PKG
C_BTN = 'L%s/hook/ActivityButtonHook;' % PKG
C_CACHE = 'L%s/data/SubtitleCache;' % PKG

# 本轮唯一改变的常量（⚠️ 必须与 C_REPO 逐字相同 —— 多写一个 '/' 就查不到，踩过）
TARGET_CLS = C_REPO
TARGET_FLD = 'NO_SUBTITLE_GRACE_MS'

BANNER_NEW = '==== BUILD 2.3.3 / code 1021'
BANNER_OLD = '==== BUILD 2.3.3 / code 1020'

# 本轮**不许**被动过的常量（所在类, 字段名, 期望值）
UNTOUCHED = [
    (C_REPO, 'PRELOAD_TOLERANCE_MS', 3500),
    (C_REPO, 'NO_SUBTITLE_GRACE_MS_CACHED', 15000),
    (C_REPO, 'NO_SUBTITLE_EARLY_CLOSE_MS', 5000),
    (C_SRC, 'INDEX_SUPPRESS_MS', 20000),
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


CLASS_SPLIT = re.compile(r"Class descriptor\s*:\s*'([^']+)'")
# name / type / access 三行紧挨，value 行**可选且必须紧接其后** —— 这样不会跨字段串位
FIELD_RE = re.compile(
    r"name\s*:\s*'([^']+)'\s*\n\s*type\s*:\s*'([^']*)'\s*\n"
    r"\s*access\s*:[^\n]*\n(?:\s*value\s*:\s*(\S+)\n)?")


def const_map_all(dump):
    """全包（PKG 下）**所有带 value 行的字段** → {'<类>.<字段>': '值'}。

    这是本轮最硬的一条判据：把两个包的常量表逐项 diff，
    既抓「改漏」，也抓「手滑多改了别的常量」。
    """
    out = {}
    parts = list(CLASS_SPLIT.finditer(dump))
    for i, m in enumerate(parts):
        cls = m.group(1)
        if not cls.startswith('L%s/' % PKG):
            continue
        end = parts[i + 1].start() if i + 1 < len(parts) else len(dump)
        seg = dump[m.start():end]
        for fm in FIELD_RE.finditer(seg):
            if fm.group(3) is None:
                continue
            out['%s.%s' % (cls, fm.group(1))] = fm.group(3)
    return out


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
    a = sys.argv[1:]
    apk_new = a[0] if len(a) > 0 else APK_NEW
    apk_old = a[1] if len(a) > 1 else APK_OLD
    apk_rev = a[2] if len(a) > 2 else APK_REV
    for p in (apk_new, apk_old, apk_rev):
        if not os.path.exists(p):
            print('缺 APK：%s' % p)
            return 2
    print('主验: %s (%d B)' % (os.path.basename(apk_new), os.path.getsize(apk_new)))
    print('对照: %s (%d B)' % (os.path.basename(apk_old), os.path.getsize(apk_old)))
    print('反向: %s (%d B)' % (os.path.basename(apk_rev), os.path.getsize(apk_rev)))
    print()
    print('正在反汇编…')
    d_new = open(dexdump_all(apk_new, dump_path(apk_new)), encoding='utf-8', errors='replace').read()
    d_old = open(dexdump_all(apk_old, dump_path(apk_old)), encoding='utf-8', errors='replace').read()
    print('  dump 完成（主验 %d / 对照 %d 字符）' % (len(d_new), len(d_old)))
    print()

    seg = {k: slice_class(d_new, v) for k, v in
           (('repo', C_REPO), ('src', C_SRC), ('btn', C_BTN), ('cache', C_CACHE))}
    check('目标类都切到（主验）',
          all(bool(v) for v in seg.values()),
          ' '.join('%s=%s' % (k, bool(v)) for k, v in seg.items()))

    # ================= A. 常量层【本轮核心】=================
    print('=== A. 常量层：全包常量表只该有一项变动【本轮核心】===')
    cm_new = const_map_all(d_new)
    cm_old = const_map_all(d_old)
    check('常量表抽到（主验）', len(cm_new) > 20, '主验 %d 项 / 对照 %d 项' % (len(cm_new), len(cm_old)))
    keys = set(cm_new) | set(cm_old)
    diff = sorted('%s: %s -> %s' % (k, cm_old.get(k), cm_new.get(k))
                  for k in keys if cm_new.get(k) != cm_old.get(k))
    only = ('%s.%s: 3000 -> 1000' % (TARGET_CLS, TARGET_FLD))
    # 允许且**只允许**额外出现 BuildConfig.VERSION_CODE（versionCode 本来就该变，
    #   它由 aapt2 badging 单独验）。这样这条判据能同时抓「改漏」与「手滑多改别的常量」。
    non_bc = [x for x in diff if '.VERSION_CODE:' not in x]
    check('除 BuildConfig.VERSION_CODE 外，全包静态常量**只有一项**变化，且正是本轮改动',
          len(diff) == 2 and non_bc == [only],
          '差异 %d 项：%r' % (len(diff), diff[:4]))

    v_new = cm_new.get('%s.%s' % (TARGET_CLS, TARGET_FLD))
    v_old = cm_old.get('%s.%s' % (TARGET_CLS, TARGET_FLD))
    dual('NO_SUBTITLE_GRACE_MS 的值 3000 -> 1000', v_new == '1000', v_old == '1000',
         '主验 %s / 对照 %s' % (v_new, v_old))
    check('对照包该常量确为 3000（口径自证）', v_old == '3000', '实际 %s' % v_old)

    for cls, fld, want in UNTOUCHED:
        check('%s 仍是 %d（本轮不该动）' % (fld, want),
              cm_new.get('%s.%s' % (cls, fld)) == str(want),
              '实际 %s' % cm_new.get('%s.%s' % (cls, fld)))
    sup = cm_new.get('%s.%s' % (C_SRC, 'INDEX_SUPPRESS_MS'))
    g_new = int(v_new) if (v_new or '').isdigit() else None
    check('钩子侧静默窗 > 本窗口（974 死循环的根治条件，按**字节码真值**比）',
          sup is not None and g_new is not None and int(sup) > g_new,
          '静默窗 %s ms > 窗口 %s ms' % (sup, g_new))

    # ================= B. 结构不动 =================
    print('=== B. 结构不动：本轮不该碰的地方一个字没动 ===')
    check('SubtitleRepository.hasDiskCacheFor(JJ)Z 仍在',
          has_method(seg['repo'], 'hasDiskCacheFor', '(JJ)Z'))
    check('SubtitleCache 五个对外签名仍在（数据层接口未变）',
          has_method(seg['cache'], 'lookup', '(JJLjava/lang/String;)Ljava/lang/String;')
          and has_method(seg['cache'], 'has', '(JJ)Z')
          and has_method(seg['cache'], 'stampDuration', '(JJ)V')
          and has_method(seg['cache'], 'put',
                         '(Ljava/lang/String;IIJLjava/lang/String;ID)V')
          and has_method(seg['cache'], 'timelineFits',
                         '(L%s/data/SubtitleCache$Entry;J)Z' % PKG))
    check('数据仓库仍真的调用缓存类（invoke 形态）',
          ('%s.lookup:(JJLjava/lang/String;)Ljava/lang/String;' % C_CACHE) in seg['repo']
          and ('%s.has:(JJ)Z' % C_CACHE) in seg['repo'])
    check('缓存类 INDEX_SCHEMA 仍是 4（本轮**没碰**缓存层）',
          has_field(seg['cache'], 'INDEX_SCHEMA', 'I', value='4'),
          '实际 %s' % cm_new.get('%s.INDEX_SCHEMA' % C_CACHE))
    check('SubtitleCache$Entry 的六个字段仍在',
          all(has_field(slice_class(d_new, 'L%s/data/SubtitleCache$Entry;' % PKG), f, t)
              for f, t in (('identity', 'J'), ('selection', 'J'), ('workKey',
                          'Ljava/lang/String;'), ('durMs', 'J'), ('maxEnd', 'D'),
                          ('hash', 'Ljava/lang/String;'))))

    # ================= C. 版本 =================
    print('=== C. 版本 ===')
    dual('常开横幅串进包：%s' % BANNER_NEW,
         raw_has(apk_new, BANNER_NEW), raw_has(apk_old, BANNER_NEW))
    check('上一轮横幅串仍是历史段（回归锚）', raw_has(apk_new, BANNER_OLD))
    bg = badging(apk_new)
    m = re.search(r"versionCode='(\d+)'", bg)
    vcode = m.group(1) if m else None
    m = re.search(r"versionName='([^']+)'", bg)
    vname = m.group(1) if m else None
    # ⚠️ 对照侧要**真测**（照抄一个 False 只是把「有区分力」做成装饰）
    bg_old = badging(apk_old)
    m_old = re.search(r"versionCode='(\d+)'", bg_old)
    vcode_old = m_old.group(1) if m_old else None
    dual('badging versionCode=1021', vcode == '1021', vcode_old == '1021',
         '主验 %r / 对照 %r' % (vcode, vcode_old))
    check('对照包 versionCode 确为 1020（口径自证）', vcode_old == '1020',
          '实际 %r' % vcode_old)
    check('badging versionName=2.3.3', vname == '2.3.3', 'versionName=%r' % vname)
    check('label 不进包（1021 的 1015.1 在 dex 里查不到 —— 既定事实）',
          not raw_has(apk_new, '1015.1'))

    # ================= D. 反向对照（固定 1011）=================
    print('=== D. 反向对照（固定 1011，不滚动）===')
    d_rev = open(dexdump_all(apk_rev, dump_path(apk_rev)), encoding='utf-8',
                 errors='replace').read()
    r_repo = slice_class(d_rev, C_REPO)
    check('1011 包里 NO_SUBTITLE_GRACE_MS 还是旧值 3000',
          has_field(r_repo, 'NO_SUBTITLE_GRACE_MS', 'J', value='3000'))
    check('1011 包里没有 1021 横幅串', not raw_has(apk_rev, BANNER_NEW))
    check('1011 包里没有 1020 横幅串',
          not raw_has(apk_rev, '==== BUILD 2.3.3 / code 1020'))

    # ================= E. 保持型（无区分力）=================
    print('=== E. 保持型（两版皆真，只防「改 A 弄坏 B」）===')
    for s in ['cloud gave no subtitle within grace',
              'resumed from LOCAL disk cache (cloud-first, local fallback)',
              'disk cache HIT on track change via ',
              'local cache availability -> ']:
        check('取数/兜底日志串仍在：%r' % s[:40], raw_has(apk_new, s))

    print()
    print('总计 %d 条，通过 %d 条，失败 %d 条' % (TOTAL, TOTAL - len(FAILS), len(FAILS)))
    print('有区分力锚 %d 条；无区分力（同一性）%d 条' % (TOTAL - len(FAILS) - len(NO_DISC),
                                                    len(NO_DISC)))
    if FAILS:
        print('失败项：')
        for f in FAILS:
            print('  - %s' % f)
        return 1
    print('verify_1021: ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
