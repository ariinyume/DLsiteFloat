#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_layer —— verify 通用层：共享原语 + 清单驱动 runner。

【为什么收拢】（2026-11-03 实账）
    65 个 verify_*.py 各自复制一套 dexdump / aapt2 / 横幅履历样板，合计 2 万行；
    「本轮判据」钉死当轮值（appVersionCode = 1044、①~⑨ 九段模板、schema 仍是 4 …），
    而工作区是**滚动的** ⇒ 版本一前进 / 合法重构一发生，整批脚本集体假红
    （11-03 实测 10/61 红，追根全是这一类）。已知红被容忍 ⇒ 真回归被噪音盖住。

【收拢成两层】
  1. **原语层**（本文件的函数）：dex 串池 / 静态常量 / aapt2 / pathdata / 横幅履历 /
     版本纪律。判据只许四种**恒成立口径**（铁律 82 推广）：
        · 下界   —— 版本号、code 之类每轮必涨的值只判 `>= 本轮`
        · 自洽   —— 横幅自报 == 构建配置；收尾句 code 与本条目编号对上
        · 形态   —— label 只守 MMDD.N；版本动作只有「升 / 不变」
        · 历史条目 —— 模板判据锚**本轮自己的历史条目**（履历追加式不覆盖 ⇒
                     历史被改写才红；最新条目的写法随轮次演进，钉最新必假红）
  2. **清单层**（manifest JSON）：每轮只维护一小份断言清单（manifests/*.json），
     不再新建 verify_10XX.py。结构性强断言仍可写小脚本，但公共层 import 本模块。

用法
----
    # 当库用（历史脚本迁移 / 新手写小脚本）：
    from verify_layer import banner_history_checks, dex_text, aapt2_badging

    # 跑清单（新轮次的标准姿势）：
    python tools/verify_layer.py tools/manifests/example_round.json \\
        --apk DLsiteFloat-2.4.3-code1048-debug.apk [--old <对照包>]

退出码：0 全绿 / 1 有 FAIL / 2 用法或缺包（run_all 判 SKIP）。
"""
import json
import os
import re
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sdkpath import build_tools as _build_tools  # noqa: E402

BT = _build_tools('36.0.0')
DEXDUMP = os.environ.get('DEXDUMP', os.path.join(BT, 'dexdump.exe'))
AAPT2 = os.environ.get('AAPT2', os.path.join(BT, 'aapt2.exe'))


# ────────────────────────── 源码层原语 ──────────────────────────

def read(path):
    return open(path, encoding='utf-8', errors='replace').read()


def norm(src):
    return src.replace('\r\n', '\n')


def strip_comments(src):
    """剥 // 与 /* */ 注释（单遍、字符串感知）。"""
    out, i, n = [], 0, len(src)
    in_str = in_chr = in_line = in_block = False
    while i < n:
        c = src[i]
        if in_line:
            if c == '\n':
                in_line = False
                out.append(c)
            i += 1
            continue
        if in_block:
            if c == '*' and i + 1 < n and src[i + 1] == '/':
                in_block = False
                i += 2
                continue
            i += 1
            continue
        if in_str:
            out.append(c)
            if c == '\\' and i + 1 < n:
                out.append(src[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if in_chr:
            out.append(c)
            if c == '\\' and i + 1 < n:
                out.append(src[i + 1])
                i += 2
                continue
            if c == "'":
                in_chr = False
            i += 1
            continue
        if c == '/' and i + 1 < n and src[i + 1] == '/':
            in_line = True
            i += 2
            continue
        if c == '/' and i + 1 < n and src[i + 1] == '*':
            in_block = True
            i += 2
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "'":
            in_chr = True
            out.append(c)
            i += 1
            continue
        out.append(c)
        i += 1
    return ''.join(out)


def gradle_versions(gradle_text):
    """读 build.gradle 的版本四处 → dict（守形态；label 只当字符串）。"""
    def g(pat):
        m = re.search(pat, gradle_text, re.M)
        return m.group(1) if m else None
    return {
        'tag': g(r"^def appVersionTag = '([^']+)'"),
        'name': g(r"^def appVersionName = '([^']+)'"),
        'code': g(r'^def appVersionCode = (\d+)'),
        'label': g(r"^def appVersionCodeLabel = '([^']+)'"),
    }


def ver_tuple(v):
    try:
        return tuple(int(x) for x in v.split('.'))
    except (ValueError, AttributeError):
        return (0,)


# ────────────────────────── 横幅履历恒成立判据 ──────────────────────────

_ENTRY_RE = r'LogGate\.debug\("\[DLsiteSoundFloat\] ==== BUILD ([\d.]+) / code (\d+) （(.*?)"\);'


def banner_entries(mod_raw):
    """所有履历条目 → [(ver, code, text)]，源码顺序（新在前）。"""
    return re.findall(_ENTRY_RE, mod_raw, re.S)


def banner_history_checks(check, mod_raw, *, own_code, own_ver=None,
                          sections=None, tail_own=False, forbidden=()):
    """横幅 + 履历段的恒成立判据块（替代各脚本手抄的那 20 行）。

    check        调用方的 check(desc, ok, detail=None) 回调
    own_code     本脚本守护的轮次号（历史条目锚）
    own_ver      该轮历史条目的 versionName（如 '2.3.1'）；None 则只按 code 搜
    sections     本条目要求的编号分段元组，如 ('①','②','③','④')；None 则不判
    tail_own     True ⇒ 追判收尾句模板（版本号 A 升/不变 [B]、code C 升 own_code。）
    forbidden    最新条目里不许出现的标识符（防负向探针自命中）
    """
    # 1) 常开横幅唯一且自报 == 构建配置（下界交给调用方各自的版本块）
    b = re.findall(r'XposedCompat\.log\("\[DLsiteSoundFloat\] ==== BUILD ([\d.]+) / code (\d+)"\);',
                   mod_raw)
    check('常开横幅唯一', len(b) == 1, '实际 %r' % (b,))
    entries = banner_entries(mod_raw)
    check('履历段可切出（至少一条）', bool(entries))
    if not entries:
        return
    v_latest, c_latest, t_latest = entries[0]
    self_code = re.findall(r'【code (\d+)', t_latest)
    check('最新履历自报 code == 横幅 code（只升横幅、抄上一轮会被抓）',
          bool(self_code) and self_code[0] == c_latest,
          '自报 %r 横幅 %s' % (self_code[:1], c_latest))
    # 2) 历史条目锚（履历追加式不覆盖 ⇒ 被改写就红）
    own = [t for v, c, t in entries if c == str(own_code)]
    if own_ver is not None:
        own = [t for v, c, t in entries
               if c == str(own_code) and v == own_ver] or own
    hist = own[0] if own else ''
    check('code %s 历史条目可切出（履历追加式不覆盖）' % own_code, bool(hist))
    if sections:
        check('历史条目分段齐全（%s）' % ''.join(sections),
              all(s in hist for s in sections))
    if tail_own:
        m_tail = re.findall(
            r'版本号 (\d+\.\d+\.\d+) (升|不变)(?: (\d+\.\d+\.\d+))?、code (\d+) (升|不变) (\d+)。', hist)
        check('历史条目收尾句合模板（版本号 A 升/不变 [B]、code C 升 D。）',
              bool(m_tail), repr(m_tail[-1:]))
        if m_tail:
            c_before, _, c_after = m_tail[-1][3], None, m_tail[-1][5]
            check('收尾句口径自洽（code-after == 本条目 %s）' % own_code,
                  c_after == str(own_code), 'C=%s D=%s' % (c_before, c_after))
    if forbidden:
        hit = [w for w in forbidden if w in t_latest]
        check('最新条目不点名探针标识符（防空/负向自命中）', not hit, '命中: %s' % (hit or '无'))


# ────────────────────────── 产物层原语 ──────────────────────────

def dex_blobs(apk):
    out = []
    with zipfile.ZipFile(apk) as z:
        for n in z.namelist():
            m = re.match(r'classes(\d*)\.dex$', n)
            if m:
                out.append((int(m.group(1) or 0), n, z.read(n)))
    out.sort(key=lambda x: x[0])
    return out


def dex_text(apk):
    """dex 原始字节（字符串串池扫描用）。"""
    return b'\n'.join(b for _, _, b in dex_blobs(apk))


def dexdump(apk, cache_dir=None):
    """dexdump -d 全文（静态常量层用）。cache_dir 给了就落盘复用。"""
    if cache_dir:
        stamp = os.path.join(cache_dir, '.stamp')
        merged = os.path.join(cache_dir, 'all.txt')
        if (os.path.isfile(stamp) and os.path.isfile(merged)
                and os.path.getmtime(stamp) >= os.path.getmtime(apk)):
            return open(merged, encoding='utf-8', errors='replace').read()
        os.makedirs(cache_dir, exist_ok=True)
    chunks = []
    for _, name, blob in dex_blobs(apk):
        tmp = os.path.join(cache_dir or '.', name + '.dx')
        with open(tmp, 'wb') as f:
            f.write(blob)
        p = subprocess.run([DEXDUMP, '-d', tmp], stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL)
        chunks.append(p.stdout.decode('utf-8', 'replace'))
        if cache_dir:
            os.remove(tmp)
    text = '\n'.join(chunks)
    if cache_dir:
        with open(os.path.join(cache_dir, 'all.txt'), 'w', encoding='utf-8') as f:
            f.write(text)
        with open(os.path.join(cache_dir, '.stamp'), 'w') as f:
            f.write('')
    return text


def static_field_value(dump_text, class_desc, field_name):
    """dexdump 静态字段常量层：`value : …`（javac 内联，串池查不到值 ⇒ 必须走这层）。

    返回 ('int', 500) / ('float', '0.22') / ('str', 'x') / None（无值或找不到）。
    """
    m = re.search(re.escape(class_desc) + r'.*?'
                  + re.escape(field_name) + r'.*?value\s*:\s*([^\n]+)',
                  dump_text, re.S)
    if not m:
        return None
    raw = m.group(1).strip()
    if re.match(r'^-?\d+$', raw):
        return ('int', int(raw))
    if re.match(r'^-?\d*\.\d+(?:[eE][-+]?\d+)?$', raw) or raw.startswith('0x'):
        return ('float', raw)
    return ('str', raw)


def aapt2_badging(apk):
    p = subprocess.run([AAPT2, 'dump', 'badging', apk], stdout=subprocess.PIPE,
                       stderr=subprocess.DEVNULL)
    txt = p.stdout.decode('utf-8', 'replace')
    m = re.search(r"package: name='([^']+)' versionCode='(\d+)' versionName='([^']+)'", txt)
    return {
        'package': m.group(1) if m else None,
        'versionCode': m.group(2) if m else None,
        'versionName': m.group(3) if m else None,
        'raw': txt,
    }


def check_pathdata(check, res_dir):
    """矢量图 pathData 语法层（无编译期校验 ⇒ 写错照样编译绿灯）。"""
    from verify_pathdata import check_one as _one, PATH_RE, VIEWPORT_RE
    bad, total = [], 0
    for root, _, files in os.walk(res_dir):
        for f in files:
            if not f.endswith('.xml'):
                continue
            src = open(os.path.join(root, f), encoding='utf-8', errors='replace').read()
            vp = VIEWPORT_RE.search(src)
            viewport = float(vp.group(1)) if vp else 24.0
            for m in PATH_RE.finditer(src):
                total += 1
                errs = _one(m.group(1), viewport)
                if errs:
                    bad.append('%s: %s' % (f, '; '.join(errs)))
    check('pathData 语法全过（%d 条）' % total, not bad, '; '.join(bad[:5]) or None)


# ────────────────────────── 清单驱动 runner ──────────────────────────

class Ctx:
    """manifest 断言的求值上下文。"""
    def __init__(self, repo, apk=None, old_apk=None):
        self.repo = repo
        self.apk = apk
        self.old_apk = old_apk
        self._src = {}
        self._dump = None

    def src(self, rel):
        if rel not in self._src:
            self._src[rel] = norm(read(os.path.join(self.repo, rel)))
        return self._src[rel]

    def dump(self):
        if self._dump is None:
            if not self.apk:
                raise RuntimeError('dex_constant 需要 --apk')
            self._dump = dexdump(self.apk, os.path.join(self.repo, 'build', '_verify_layer'))
        return self._dump


def run_assertion(ctx, a):
    """单条断言 → (desc, ok, detail)。type 分发见 manifests/example_round.json。"""
    t = a['type']
    d = a.get('desc', t)
    if t == 'src_contains':
        return d, a['pat'] in ctx.src(a['file']), None
    if t == 'src_absent':
        return d, a['pat'] not in ctx.src(a['file']), None
    if t == 'src_regex':
        return d, re.search(a['pat'], ctx.src(a['file'])) is not None, None
    if t == 'src_regex_absent':
        return d, re.search(a['pat'], ctx.src(a['file'])) is None, None
    if t == 'version_lower_bound':
        v = gradle_versions(ctx.src('app/build.gradle'))
        ok = (v['code'] and int(v['code']) >= int(a['code'])
              and ver_tuple(v['name']) >= ver_tuple(a.get('name_min', '0.0.0')))
        return d, bool(ok), 'code=%s name=%s' % (v['code'], v['name'])
    if t == 'version_label_form':
        v = gradle_versions(ctx.src('app/build.gradle'))
        return d, bool(re.match(r'^\d{4}\.\d+$', v['label'] or '')), repr(v['label'])
    if t == 'banner_self_report':
        v = gradle_versions(ctx.src('app/build.gradle'))
        m = re.search(r'XposedCompat\.log\("\[DLsiteSoundFloat\] ==== BUILD ([\d.]+) / code (\d+)"\);',
                      ctx.src(a.get('file', 'app/src/main/java/io/github/ariinyume/dlsitesoundfloat/'
                                          'DlsiteSoundSubtitleModule.java')))
        ok = bool(m) and m.group(1) == v['name'] and m.group(2) == v['code']
        return d, ok, '横幅 %r 配置 %s/%s' % (m.groups() if m else None, v['name'], v['code'])
    if t == 'banner_history':
        mod = ctx.src(a.get('file', 'app/src/main/java/io/github/ariinyume/dlsitesoundfloat/'
                                    'DlsiteSoundSubtitleModule.java'))
        got = []
        def _check(desc, ok, detail=None):
            got.append((desc, ok, detail))
        banner_history_checks(_check, mod, own_code=a['own_code'],
                              own_ver=a.get('own_ver'),
                              sections=tuple(a['sections']) if a.get('sections') else None,
                              tail_own=a.get('tail_own', False),
                              forbidden=tuple(a.get('forbidden', ())))
        return d + '（%d 子项）' % len(got), all(g[1] for g in got), \
            '; '.join('%s=%s' % (g[0], g[1]) for g in got if not g[1]) or None
    if t == 'dex_string':
        if not ctx.apk:
            return d, False, '缺 --apk'
        blob = dex_text(ctx.apk)
        ok = (a['pat'].encode('utf-8') in blob) if a.get('expect', True) else \
             (a['pat'].encode('utf-8') not in blob)
        return d, ok, None
    if t == 'dex_constant':
        got = static_field_value(ctx.dump(), a['class'], a['field'])
        ok = got is not None and str(got[1]) == str(a['value'])
        return d, ok, '实际 %r' % (got,)
    if t == 'aapt2_version':
        info = aapt2_badging(ctx.apk)
        ok = (int(info['versionCode'] or 0) >= int(a['code_min'])
              and info['versionName'] == a.get('name', info['versionName']))
        return d, ok, 'code=%s name=%s' % (info['versionCode'], info['versionName'])
    if t == 'pathdata':
        ok, detail = True, None
        def _c(desc, o, det=None):
            nonlocal ok, detail
            ok = ok and o
            detail = det
        check_pathdata(_c, os.path.join(ctx.repo, a.get('dir', 'app/src/main/res')))
        return d, ok, detail
    return d, False, '未知断言类型 %r' % t


def run_manifest(path, apk=None, old_apk=None):
    man = json.load(open(path, encoding='utf-8'))
    repo = os.path.dirname(HERE)
    ctx = Ctx(repo, apk, old_apk)
    print('清单：%s（round=%s）' % (os.path.basename(path), man.get('round', '?')))
    fails = 0
    for a in man.get('checks', []):
        try:
            d, ok, detail = run_assertion(ctx, a)
        except Exception as e:                       # noqa: BLE001
            d, ok, detail = a.get('desc', a.get('type', '?')), False, '%s: %s' % (type(e).__name__, e)
        print('  %s  %s%s' % ('OK  ' if ok else 'FAIL', d,
                              ('   %s' % detail) if detail else ''))
        if not ok:
            fails += 1
    total = len(man.get('checks', []))
    print('%s %d/%d' % ('PASS' if not fails else 'HAS FAIL', total - fails, total))
    return 1 if fails else 0


def main(argv):
    if len(argv) < 1:
        print('usage: verify_layer.py <manifest.json> [--apk NEW.apk] [--old OLD.apk]')
        return 2
    man_path = argv[0]
    if not os.path.isfile(man_path):
        print('usage: verify_layer.py <manifest.json> [--apk NEW.apk] [--old OLD.apk]')
        print('manifest not found: ' + man_path)
        return 2
    apk = old = None
    if '--apk' in argv:
        apk = argv[argv.index('--apk') + 1]
    if '--old' in argv:
        old = argv[argv.index('--old') + 1]
    return run_manifest(man_path, apk, old)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
