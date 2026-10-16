#!/usr/bin/env python3
"""架构体检工具（只读为主）。

把《架构审查报告-20261014》用到的测量口径固化成一个入口，避免一堆一次性脚本散在 tools/。

用法：
    python tools/audit_arch.py density     # 注释/代码/空行密度（逐文件 + 全仓）
    python tools/audit_arch.py methods     # 方法体行数分布（>=60 行清单）
    python tools/audit_arch.py dup         # 跨文件同名方法名（重复实现嫌疑）
    python tools/audit_arch.py narrative   # 注释块体量 + 叙事候选（含历史标记/日期证据）
    python tools/audit_arch.py narrative --detail data/SubtitleRepository.java
    python tools/audit_arch.py lockguard   # SubtitleRepository 实例字段的锁守卫口径
    python tools/audit_arch.py eol         # 全部 .java 行尾实测（含混合行尾告警）
    python tools/audit_arch.py eol --fix   # 把混合行尾归一（⚠️ 会写盘，默认 dry-run）

⚠️ 除 `eol --fix` 外全部只读。
⚠️ 行尾一律用 read_bytes() 判定 —— read_text() 的 universal newlines 会把 CRLF 吃成 LF。
"""
import argparse
import collections
import glob
import os
import re
import sys

SRC = 'app/src/main/java'
TEST = 'app/src/test'
PKG = 'io.github.ariinyume.dlsitesoundfloat'
PKG_PATH = PKG.replace('.', '/')

# ---------------------------------------------------------------- 公共


def java_files(include_test=False):
    pats = [SRC + '/**/*.java']
    if include_test:
        pats.append(TEST + '/**/*.java')
    out = []
    for pat in pats:
        out += glob.glob(pat, recursive=True)
    return sorted(out)


def read_text(path):
    """读文本并归一 NL。⚠️ 行尾判定必须另用 read_bytes()。"""
    raw = open(path, 'rb').read()
    return raw.decode('utf-8', errors='replace').replace('\r\n', '\n').replace('\r', '\n')


def eol_of(raw):
    crlf = raw.count(b'\r\n')
    bare = raw.count(b'\n') - crlf
    return crlf, bare


def short(p):
    return p.replace(os.sep, '/').replace(SRC + '/', '').replace(TEST + '/', 'test/')


# ---------------------------------------------------------------- density


def cmd_density(args):
    rows = []
    for p in java_files(include_test=args.with_test):
        lines = read_text(p).split('\n')
        total = len(lines)
        blank = comment = code = 0
        in_block = False
        for l in lines:
            s = l.strip()
            if in_block:
                comment += 1
                if '*/' in s:
                    in_block = False
            elif not s:
                blank += 1
            elif s.startswith('/*'):
                comment += 1
                if '*/' not in s:
                    in_block = True
            elif s.startswith('//') or s.startswith('*'):
                comment += 1
            else:
                code += 1
        rows.append((total, comment, code, blank, short(p)))

    rows.sort(reverse=True)
    print('%-32s %6s %8s %7s %7s %8s' % ('file', 'total', 'comment', 'code', 'blank', 'cmt%'))
    for total, c, code, b, f in rows[:args.top]:
        print('%-32s %6d %8d %7d %7d %7.0f%%' % (f, total, c, code, b, 100.0 * c / max(total, 1)))

    T = sum(r[0] for r in rows)
    C = sum(r[1] for r in rows)
    K = sum(r[2] for r in rows)
    B = sum(r[3] for r in rows)
    print()
    print('全仓: total=%d comment=%d (%.0f%%) code=%d (%.0f%%) blank=%d'
          % (T, C, 100.0 * C / max(T, 1), K, 100.0 * K / max(T, 1), B))
    print('注释 : 代码 = %.2f : 1' % (C / max(K, 1)))


# ---------------------------------------------------------------- methods


def cmd_methods(args):
    res = []
    for p in java_files():
        lines = read_text(p).split('\n')
        n = len(lines)
        i = 0
        while i < n:
            l = lines[i]
            if re.match(r'^    [\w@][\w<>\[\],\. ]*\s+\w+\s*\(.*\)\s*(\{|\s*throws.*\{)?\s*$', l) and '{' in l:
                start, d, j = i, 0, i
                while j < n:
                    d += lines[j].count('{') - lines[j].count('}')
                    if d <= 0 and j > start:
                        break
                    j += 1
                if j - start + 1 >= args.min:
                    res.append((j - start + 1, start + 1, short(p), l.strip()[:78]))
                i = j + 1
            else:
                i += 1

    res.sort(reverse=True)
    print('=== 方法体 >= %d 行（top %d）===' % (args.min, args.top))
    for ln, at, f, sig in res[:args.top]:
        print('%5d  L%-6d %-30s %s' % (ln, at, f, sig))
    print()
    print('>=%d 行: %d 个 · >=150 行: %d 个'
          % (args.min, len(res), sum(1 for r in res if r[0] >= 150)))
    agg, cnt = collections.Counter(), collections.Counter()
    for ln, at, f, sig in res:
        agg[f] += ln
        cnt[f] += 1
    print()
    print('=== 按文件汇总 ===')
    for f, tot in agg.most_common(12):
        print('%-30s %2d 个 / 累计 %5d 行' % (f, cnt[f], tot))


# ---------------------------------------------------------------- dup


def cmd_dup(args):
    names = collections.defaultdict(set)
    # 方法声明：4 空格缩进 + 修饰符 + 返回类型 + 名字 + `(`。
    # ⚠️ 两个坑都踩过：
    #   1) 不要用 `(?:kw|kw|...)*` 那种带惰性通配的循环 —— 实测会漏掉
    #      `private static int dp(Context…)`（FloatingWindowManager 被漏报）。显式列修饰符白名单。
    #   2) 🔴 **编译后的 pattern 方法不接受 flags**：`p.finditer(s, re.M)` 里的 `re.M`
    #      会被当成 `pos=8`（起始偏移），**flags 静默失效** ⇒ 匹配数 0 而毫无报错。
    #      flags 必须写进 `re.compile(...)`。
    decl = re.compile(
        r'^    ((?:@\w+\s+)*'
        r'(?:public |private |protected |static |final |synchronized |abstract |native )*)'
        r'[\w<>\[\],\.\?]+\s+(\w+)\s*\(',
        re.M)
    for p in java_files():
        f = short(p)
        for m in decl.finditer(read_text(p)):
            names[m.group(2)].add(f)

    # ⚠️ 注意：不要把 'dp' 放进忽略集 —— 「8 个文件各养一个 dp()」正是本工具要暴露的信号。
    # 'setAlpha' 已核为假阳性：GlassPanelDrawable / LiquidGlassDrawable 是 `Drawable.setAlpha(int)`
    #    的 API 覆写（必须实现、签名相同但语义独立），SubtitleStyle 是同名不同签名的颜色助手
    #    `setAlpha(int argb, int alpha)` ⇒ 三者非重复实现，故列入忽略集。
    skip = {'init', 'toString', 'equals', 'hashCode', 'run', 'get', 'put', 'reset', 'apply',
            'log', 'show', 'close', 'open', 'update', 'refresh', 'clear', 'start', 'stop',
            'install', 'dismiss', 'if', 'for', 'while', 'return', 'switch', 'super', 'hook',
            'setAlpha', 'invalidate', 'synchronized', 'try', 'getResources'}
    print('=== 跨 >= %d 个文件的同名方法（已滤通用名）===' % args.min)
    for n, fs in sorted(names.items(), key=lambda kv: -len(kv[1])):
        if len(fs) >= args.min and n not in skip and not n.startswith('on'):
            print('%2d  %-34s %s' % (len(fs), n, ' | '.join(sorted(fs))))


# ---------------------------------------------------------------- narrative

HIST = re.compile(r'【(code \d+|v\d+|\d+\.\d+\.\d+)')
DATE = re.compile(r'\d{1,2}:\d{2}:\d{2}|\d{4}-\d{2}-\d{2}|录屏|实测|日志实证')
INV = re.compile(r'必须|否则|绝不能|不得|严禁|不要混|这条|根因|铁律|红线')


def _comment_blocks(path, minlen):
    lines = read_text(path).split('\n')
    out = []
    i, n = 0, len(lines)
    while i < n:
        s = lines[i].strip()
        if s.startswith('/**') or s.startswith('/*') or s.startswith('//'):
            j = i
            if s.startswith('/*'):
                while j < n and '*/' not in lines[j]:
                    j += 1
                j += 1
            else:
                while j + 1 < n and lines[j + 1].strip().startswith('//'):
                    j += 1
                j += 1
            if j - i >= minlen:
                out.append((i + 1, lines[i:j]))
            i = j
        else:
            i += 1
    return out


def cmd_narrative(args):
    if args.detail:
        target = args.detail
        if not target.startswith(('app/', os.sep)):
            target = SRC + '/' + PKG_PATH + '/' + target
        for at, blk in _comment_blocks(target, 8):
            txt = '\n'.join(blk)
            if not (HIST.search(txt) and DATE.search(txt)):
                continue
            print('─── L%-6d %3d 行  [%s] ───' % (at, len(blk), 'INV' if INV.search(txt) else '---'))
            for l in blk[:3]:
                print('   | ' + l.strip()[:96])
            if len(blk) > 5:
                print('   | ... (%d 行) ...' % (len(blk) - 4))
                print('   | ' + blk[-1].strip()[:96])
            print()
        return

    print('%-34s %8s %10s %12s %8s' % ('file', '块>=8', '块行数', '含历史标记', '含历史+日期'))
    for p in java_files():
        blocks = _comment_blocks(p, 8)
        hist = [b for b in blocks if HIST.search('\n'.join(b[1]))]
        hd = [b for b in hist if DATE.search('\n'.join(b[1]))]
        if len(blocks) < 5:
            continue
        print('%-34s %8d %10d %12d %8d'
              % (short(p), len(blocks), sum(len(b[1]) for b in blocks), len(hist), len(hd)))

    ts = tot = 0
    for p in java_files():
        for l in read_text(p).split('\n'):
            s = l.strip()
            if s.startswith('//') or s.startswith('*'):
                tot += 1
                if re.search(r'\d{1,2}:\d{2}:\d{2}', s):
                    ts += 1
    print()
    print('注释行 %d，其中含时间戳 %d (%.1f%%)  <-- 真正的「运行时证据」，搬迁候选'
          % (tot, ts, 100.0 * ts / max(tot, 1)))


# ---------------------------------------------------------------- lockguard


def cmd_lockguard(args):
    p = SRC + '/' + PKG_PATH + '/data/SubtitleRepository.java'
    lines = read_text(p).split('\n')

    lock_ranges = []
    i = 0
    while i < len(lines):
        if re.search(r'synchronized\s*\(\s*lock\s*\)', lines[i]):
            d, j, started = 0, i, False
            while j < len(lines):
                d += lines[j].count('{') - lines[j].count('}')
                if '{' in lines[j]:
                    started = True
                if started and d <= 0:
                    break
                j += 1
            lock_ranges.append((i, j))
            i = j + 1
        else:
            i += 1

    def in_lock(idx):
        return any(a <= idx <= b for a, b in lock_ranges)

    DECL = re.compile(r'^private\s+((?:final|volatile|transient)\s+)*(?!static)[\w\.<>\[\],\s]+?\s+(\w+)\s*(=|;)')
    fields = []
    for idx, l in enumerate(lines):
        s = l
        if s.startswith('    private ') and 'static ' not in s:
            m = DECL.match(s.strip())
            if m and '(' not in s.split('=')[0]:
                mods = sorted(set(re.findall(r'\b(final|volatile|transient)\b', s)))
                fields.append((m.group(2), idx + 1, ''.join(mods)))

    IDENT = re.compile(r'\b([a-z][A-Za-z0-9_]*)\b')
    KW = {'if', 'for', 'while', 'return', 'new', 'int', 'long', 'boolean', 'void', 'null',
          'true', 'false', 'this', 'else', 'synchronized', 'lock', 'final', 'private',
          'public', 'static', 'volatile', 'throw', 'instanceof', 'try', 'catch', 'switch',
          'case', 'break', 'double', 'class', 'default'}
    in_set, out_set = set(), set()
    for idx, l in enumerate(lines):
        s = l.strip()
        if s.startswith('//') or s.startswith('*') or s.startswith('/*'):
            continue
        for c in IDENT.findall(s):
            if c not in KW:
                (in_set if in_lock(idx) else out_set).add(c)

    def verdict(n):
        a, b = n in in_set, n in out_set
        return '内外都有' if a and b else ('仅锁内' if a else ('仅锁外' if b else '未检出'))

    groups = collections.defaultdict(list)
    for name, ln, mods in sorted(fields, key=lambda f: f[1]):
        key = '裸字段(无修饰)' if not mods else ('volatile' if 'volatile' in mods else 'final')
        groups[key].append((name, ln, verdict(name)))

    print('锁区块 %d 个，覆盖行数约 %d' % (len(lock_ranges), sum(b - a + 1 for a, b in lock_ranges)))
    print('实例字段总数: %d' % len(fields))
    print()
    for g, items in groups.items():
        print('### %s（%d 个）' % (g, len(items)))
        for name, ln, v in items:
            print('    %-28s L%-5d %s' % (name, ln, v))
        print()
    print('判定汇总:', dict(collections.Counter(verdict(f[0]) for f in fields)))


# ---------------------------------------------------------------- eol


def cmd_eol(args):
    mixed, crlf, lf = [], [], []
    for p in java_files(include_test=True):
        raw = open(p, 'rb').read()
        c, b = eol_of(raw)
        if c and b:
            mixed.append((p, c, b))
        elif c:
            crlf.append(p)
        else:
            lf.append(p)

    print('CRLF: %d   LF: %d   混合: %d' % (len(crlf), len(lf), len(mixed)))
    for p, c, b in mixed:
        print('   MIX  %-60s CRLF=%d 裸LF=%d' % (short(p), c, b))

    if not args.fix:
        if mixed:
            print()
            print('（dry-run）加 --fix 可把混合行尾归一为 CRLF')
        return

    if not mixed:
        print('无混合行尾，无需修正')
        return

    for p, _, _ in mixed:
        before = open(p, 'rb').read()
        n_before = before.count(b'\n')
        bl_before = eol_of(before)[1]
        fixed = before.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        assert fixed.count(b'\n') == n_before, '%s: 行数变了' % p
        assert eol_of(fixed)[1] == 0, '%s: 归一后仍有裸 LF' % p
        assert fixed != before, '%s: 字节未变（判为未落盘）' % p
        open(p, 'wb').write(fixed)
        back = open(p, 'rb').read()
        assert back == fixed, '%s: 回读不一致' % p
        print('FIXED %-58s 裸LF %d -> 0 · 字节 %d -> %d'
              % (short(p), bl_before, len(before), len(back)))


# ---------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser(description='DLsiteFloat 架构体检（除 eol --fix 外全部只读）')
    sub = ap.add_subparsers(dest='cmd', required=True)

    d = sub.add_parser('density', help='注释/代码密度')
    d.add_argument('--top', type=int, default=16)
    d.add_argument('--with-test', action='store_true',
                   help='一并统计 app/src/test（默认只统计 main，与审查报告口径一致）')
    d.set_defaults(func=cmd_density)

    m = sub.add_parser('methods', help='方法体行数分布')
    m.add_argument('--min', type=int, default=60)
    m.add_argument('--top', type=int, default=40)
    m.set_defaults(func=cmd_methods)

    u = sub.add_parser('dup', help='跨文件同名方法名')
    u.add_argument('--min', type=int, default=3)
    u.set_defaults(func=cmd_dup)

    n = sub.add_parser('narrative', help='注释块体量 / 叙事候选')
    n.add_argument('--detail', metavar='FILE', help='逐块打印某文件的候选块')
    n.set_defaults(func=cmd_narrative)

    lk = sub.add_parser('lockguard', help='SubtitleRepository 字段锁守卫口径')
    lk.set_defaults(func=cmd_lockguard)

    e = sub.add_parser('eol', help='行尾实测（--fix 归一混合行尾）')
    e.add_argument('--fix', action='store_true', help='⚠️ 写盘：把混合行尾归一为 CRLF')
    e.set_defaults(func=cmd_eol)

    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    sys.exit(main())
