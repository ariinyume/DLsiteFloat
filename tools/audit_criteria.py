#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
判据画像：把 tools/ 与 tools/archive/ 下的 verify_*.py 里每条判据按「保质期来源」归类。

用法：
    python tools/audit_criteria.py            # 打印画像
    python tools/audit_criteria.py --detail   # 附带每条脆弱判据的明细

--------------------------------------------------------------------------
⚠️ 定位：给的是**构成画像**，不是定罪结论
    判据到底会不会假红，`_diag_audit_1103/mutate.py` 那套变异测试才是硬证据
    （造一个假下一轮：code+1 / 版本号+1 / 履历追加，看谁红）。
    画像的价值是解释「为什么不会红」，并指出结构上还剩哪些软肋。
--------------------------------------------------------------------------
分档（按「被钉的值因什么而变化」—— 这才是保质期的真实来源，铁律 109）：

  A 轮次耦合  每轮必变的值（versionCode / versionName / 履历段位置）
              ⇒ 每轮假红，必须改。铁律 109 点名的病灶。
  B 形态耦合  只要重构就变（方法体切片 count == N、集合长度）
              ⇒ 与「历史锚」同源，是可接受成本，但重构时要记得同步。
  C 规格锚    产品决策才变（默认值 / 常量 / 映射端点 / 浮点容差）
              ⇒ 合法。改设计时同步改脚本是应有成本。
  D 恒成立    下界 / 自洽 / 形态正则 / 存在性 / 负向锚 / 源码位置顺序
              ⇒ 不会假红。
  U 未分类    本工具规则没覆盖（人工确认后多半是形态/规格）

对象口径（决定 A 档是否成立）：
  · 源码层脚本读的是**滚动工作区** ⇒ 版本号会变 ⇒ A 档成立。
  · dex 脚本通过 run_all 的 NEEDS_APK 绑定**固定 code 的凝固包** ⇒ `== 1040`
    对那个包恒成立 ⇒ 不构成 A 档。
  · 唯一例外 verify_998 用 latest 语义（主验位是滚动的最新包），但脚本头部
    已明确写下契约「改这几个常量就该 FAIL，那是真信号」⇒ 有意识的滚动锚，不算隐患。

已知盲区（本工具覆盖不到，需人工看）：
  verify_1044.py / verify_1044_src.py 用 `rows = [(id, desc, ok)]` 三元组而非 check()；
  verify_pathdata.py 是 pathData 语法校验，与轮次无关。
"""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEX_CALLS = {'add', 'add_negative', 'add_keep', 'add_diff'}
VER_KW = ('version', 'Version', '版本', '编号')
SPEC_KW = ('默认', '阈值', '常量', '历史', '端点', '映射', 'DEFAULT', 'def_', 'target',
           'TARGET', 'alpha', 'Alpha', 'lum', 'LUM', 'thr', '基准', '观感', '容差', '限制')


def call_name(node):
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def const_str(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def classify(name, cond, src_layer):
    """返回 (档, 说明)。顺序即优先级：先认最强的恒成立口径，再逐级放宽。"""
    n, c = name or '', cond or ''
    spec = any(k in (n + c) for k in SPEC_KW)

    # ---- D：恒成立（先判）----
    # 只要出现 `>= 数字` 就算下界：常见形态是 `len(banners) == 1 and int(banners[0]) >= 1019`，
    # 前半段是**已断言长度后的安全下标**，不是钉死。
    if re.search(r'>=\s*\d', c) or '下界' in n:
        return 'D', '下界'
    if '形态' in n or '形如' in n or 're.match' in c or 're.fullmatch' in c:
        return 'D', '形态（正则）'
    if '自洽' in n:
        return 'D', '自洽'
    if c.strip() == 'm is not None':
        return 'D', '形态（可解析性）'
    if 'is not None' in c and 're.' in c:
        return 'D', '形态（正则存在性）'
    if 'find(' in c and '<' in c and not re.search(r'<\s*\d', c):
        return 'D', '形态（源码位置顺序）'
    if re.search(r'==\s*[\{\[]', c):
        return 'D', '形态（集合/序列等值）'
    if re.match(r'^\s*not\s+\w+', c):
        return 'D', '自洽（不变量）'
    if 'not in' in c:
        return 'D', '负向锚（绝迹）'
    if re.search(r'\bin\b', c):
        return 'D', '存在性'

    # ---- A：轮次耦合 —— 只有源码层（滚动对象）才成立 ----
    if src_layer:
        if re.search(r"==\s*[\'\"](2\.\d+\.\d+|\d{3,4})[\'\"]", c) and any(k in (n + c) for k in VER_KW):
            return 'A', 'A1 版本号精确等值（滚动源码）'
        if re.search(r'appVersionCode\s*==\s*\d', c) or re.search(r'appVersionName\s*==\s*[\'"]', c):
            if not spec:
                return 'A', 'A1 版本号精确等值（滚动源码）'
        # 唯一性规格（「常开横幅只有一行」「LAUNCHER 只一处」）是**设计约束**，
        # 不是轮次耦合：追加履历不会让它红，改设计才该红 ⇒ 归 C。
        uniq = any(k in n for k in ('唯一', '只有一行', '只有一处', '恰为', '恰好一条'))
        if re.search(r'banners\s*\[\s*\d', c) and not re.search(r'>=\s*\d', c):
            if uniq:
                return 'C', 'C3 横幅唯一性规格（设计约束）'
            return 'A', 'A2 履历段按下标定位且无下界保护'
        if re.search(r'len\(banners\)\s*==\s*\d', c) and not re.search(r'>=\s*\d', c):
            if uniq:
                return 'C', 'C3 横幅唯一性规格（设计约束）'
            return 'A', 'A2 履历条数精确等值'

    # ---- B：形态耦合（重构即变）----
    if re.search(r'\.count\([^)]*\)\s*(==|>=)\s*\d', c):
        return 'B', 'B1 方法体内符号计数（重构即变）'
    if re.search(r'len\([^)]*\)\s*==\s*\d', c):
        return 'B', 'B2 集合长度精确等值'

    # ---- C：规格锚 ----
    if re.search(r'abs\([^)]*\)\s*<', c):
        return 'C', 'C1 数值规格（浮点容差）'
    if re.search(r'==\s*-?\d+(\.\d+)?\b', c):
        return 'C', 'C2 数值等值（规格锚）'
    return 'U', '未分类'


def audit_file(path, src_layer):
    src = open(path, encoding='utf-8', errors='replace').read()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [dict(line=e.lineno or 0, kind='U', why='SYNTAX ' + str(e), name='', cond='')], 0
    rows, total = [], 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and call_name(node) == 'check':
            total += 1
            nm = const_str(node.args[0]) if node.args else ''
            cond = ast.unparse(node.args[1]) if len(node.args) > 1 else ''
            k, why = classify(nm, cond, src_layer)
            rows.append(dict(line=node.lineno, kind=k, why=why,
                             name=(nm or '')[:70], cond=cond[:130]))
    return rows, total


def main(argv):
    detail = '--detail' in argv
    sys.path.insert(0, HERE)
    import run_all_verify as rav
    cat = {n: c for n, c, _ in rav.SCRIPTS}

    src_rows, dex_total, other = [], 0, []
    for f in sorted(cat):
        # 2026-11-03 目录整理：判据脚本已归档到 tools/archive/，
        #   统一走 run_all_verify.locate()（先顶层、后 archive）拿物理路径。
        p = rav.locate(f)
        if p is None:
            other.append((f, '文件不存在（顶层与 archive/ 均未找到）'))
            continue
        src_layer = cat[f] == '源码层'
        rows, total = audit_file(p, src_layer)
        if total:
            src_rows.extend((f, r) for r in rows)
        else:
            body = open(p, encoding='utf-8', errors='replace').read()
            kinds = {}
            for node in ast.walk(ast.parse(body)):
                if isinstance(node, ast.Call) and call_name(node) in DEX_CALLS:
                    k = call_name(node)
                    kinds[k] = kinds.get(k, 0) + 1
            if kinds:
                dex_total += sum(kinds.values())
            else:
                other.append((f, '判据结构非 check/add（rows 三元组等）—— 本工具不覆盖'))

    agg = {}
    for _, r in src_rows:
        agg[r['kind']] = agg.get(r['kind'], 0) + 1
    lbl = {'A': 'A 轮次耦合（每轮必假红，必修）', 'B': 'B 形态耦合（重构即变，需登记）',
           'C': 'C 规格锚（改设计才变，合法）', 'D': 'D 恒成立（不假红）',
           'U': 'U 未分类（规则未覆盖）'}

    print('=' * 70)
    print('判据画像 —— 登记脚本 %d 个' % len(cat))
    print('=' * 70)
    print('check() 型判据 %d 条：' % len(src_rows))
    for k in 'ABCDU':
        v = agg.get(k, 0)
        bar = '#' * int(round(v * 40.0 / max(1, len(src_rows))))
        print('  %-28s %5d %5.1f%%  %s' % (lbl[k], v, v * 100.0 / max(1, len(src_rows)), bar))
    print('dex add 型判据 %d 条（双包对照，对象是凝固包 ⇒ 天然免疫轮次演进）' % dex_total)
    if other:
        print('\n未覆盖（需人工看）：')
        for f, why in other:
            print('  %-24s %s' % (f, why))

    a = [(f, r) for f, r in src_rows if r['kind'] == 'A']
    print('\nA 档残留：%s' % ('无' if not a else '%d 条' % len(a)))
    for f, r in a:
        print('  %-22s:%-5d %s | %s' % (f, r['line'], r['why'], r['name'][:46]))

    if detail:
        for k in 'BA':
            rows = [(f, r) for f, r in src_rows if r['kind'] == k]
            if not rows:
                continue
            print('\n%s 档明细：' % k)
            for f, r in rows:
                print('  %-22s:%-5d %s' % (f, r['line'], r['name'][:56]))
                print('        %s' % r['cond'][:100])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
