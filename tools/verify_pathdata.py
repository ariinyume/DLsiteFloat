#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""矢量图 pathData 语法校验（铁律：pathData 没有编译期校验，写错要等真机崩）。

为什么需要它
------------
`aapt2` 只把 `<path android:pathData="...">` 当字符串抄进资源表，**不解析**。
真正的解析发生在运行时 `VectorDrawableCompat.create()`；语法一错就是
`XmlPullParserException` / `IllegalArgumentException` —— 表现为「编译绿灯、
设置页打不开」。曾经踩过（见 MEM_rules 第 7 条）。

本脚本做三件事
--------------
1. 白名单命令字母（Mm Ll Hh Vv Cc Ss Qq Tt Aa Zz）；
2. 按 SVG 规范逐个命令核对**参数个数**（可重复、可省略后续命令字母）；
3. 数字可解析性 + 坐标落在视口附近的粗检（防「24 写成 2400」这类手误）。

⚠️ 它不能证明图形好看，只能证明**不会因为语法把页面搞崩**。

用法
----
    python tools/verify_pathdata.py [目录...]
    默认扫 app/src/main/res/drawable 与 drawable-* 全部 .xml
"""

import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DIRS = [os.path.join(ROOT, 'app', 'src', 'main', 'res')]

# 每个命令的参数个数（Z 为 0）
ARITY = {
    'M': 2, 'L': 2, 'T': 2,
    'H': 1, 'V': 1,
    'C': 6, 'S': 4, 'Q': 4,
    'A': 7,
    'Z': 0,
}
LETTERS = set('MmLlHhVvCcSsQqTtAaZz')
TOKEN = re.compile(r'[MmLlHhVvCcSsQqTtAaZz]|-?\d*\.?\d+(?:[eE][-+]?\d+)?')

PATH_RE = re.compile(r'android:pathData\s*=\s*"([^"]*)"')
VIEWPORT_RE = re.compile(r'android:viewportWidth\s*=\s*"([\d.]+)"')


def check_one(path_data, viewport=24.0):
    """返回问题列表（空 = 通过）。"""
    errs = []
    toks = TOKEN.findall(path_data)
    # 残留字符 = 有 token 之外的东西（逗号空格除外）
    residual = TOKEN.sub('', path_data)
    residual = residual.replace(',', '').replace(' ', '').replace('\n', '').replace('\t', '')
    residual = residual.replace('\r', '')
    if residual:
        errs.append('含非法字符: %r' % residual[:40])
    if not toks:
        return ['pathData 为空']

    i = 0
    cur = None
    while i < len(toks):
        tk = toks[i]
        if tk in LETTERS:
            cur = tk
            i += 1
            if cur.upper() == 'Z':
                continue
            # 命令后可能紧跟参数，也可能紧跟另一命令（表示沿用）
            if i >= len(toks) or toks[i] in LETTERS:
                if cur.upper() == 'Z':
                    continue
                # 允许「M 后面没有参数」？不允许
                errs.append('命令 %s 后缺少参数' % cur)
                continue
        if cur is None:
            errs.append('pathData 未以命令字母开头')
            break
        need = ARITY[cur.upper()]
        if need == 0:
            i += 1
            continue
        # 收参数：直到凑够 need 个或被命令打断
        got = 0
        while got < need and i < len(toks) and toks[i] not in LETTERS:
            v = toks[i]
            try:
                f = float(v)
            except ValueError:
                errs.append('参数无法解析: %r' % v)
                return errs
            if abs(f) > max(viewport * 12, 64):
                errs.append('坐标量级异常: %s（视口 %.0f）' % (v, viewport))
            got += 1
            i += 1
        if got < need:
            errs.append('命令 %s 需要 %d 个参数，只给了 %d 个' % (cur, need, got))
            if got == 0:
                break
        # 隐式重复：同一命令可连续给多组参数，主循环继续处理
        if cur.upper() == 'M':
            # 后续隐式参数按 L 处理（SVG 规范），这里不改变 cur 也能通过校验
            pass
    return errs


def main():
    dirs = sys.argv[1:] or DEFAULT_DIRS
    files = []
    for d in dirs:
        files.extend(glob.glob(os.path.join(d, 'drawable*', '*.xml')))
    files = sorted(set(files))
    if not files:
        print('没有找到 drawable xml')
        return 1

    total = 0
    bad = 0
    for f in files:
        try:
            txt = open(f, 'r', encoding='utf-8').read()
        except Exception as e:
            print('SKIP %s (%s)' % (os.path.basename(f), e))
            continue
        datas = PATH_RE.findall(txt)
        if not datas:
            continue
        m = VIEWPORT_RE.search(txt)
        vp = float(m.group(1)) if m else 24.0
        for pd in datas:
            total += 1
            errs = check_one(pd, vp)
            if errs:
                bad += 1
                print('FAIL %s' % os.path.relpath(f, ROOT))
                for e in errs[:4]:
                    print('     - %s' % e)
                print('     pathData: %s' % (pd[:120] + ('...' if len(pd) > 120 else '')))
    print('\npathData 共 %d 条，失败 %d 条，文件 %d 个' % (total, bad, len(files)))
    return 0 if bad == 0 else 2


if __name__ == '__main__':
    sys.exit(main())
