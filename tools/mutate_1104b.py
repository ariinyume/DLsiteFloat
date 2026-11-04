# -*- coding: utf-8 -*-
"""round_1104b 变异测试：逐条回退源码，确认清单判据有区分力（变红）。

用法：python tools/mutate_1104b.py

★ 这是**模板 + 本轮记录**：MUTANTS 里的十个变异是本轮（1048）专用的。
  换轮次时复制本文件成 mutate_<轮次>.py，只改 MUTANTS，驱动器部分原样复用。

铁律（本轮踩出来的，别省）：
  · baseline 必须存**原始字节**，还原一律写回原始字节 —— 否则 CRLF 文件会被
    二次转行尾成 \r\r\n（本轮真踩：三个文件 4693/1161/1376 行全被写脏）。
  · 每个变异跑完 `finally` 里立刻还原，最后再逐字节校验一遍。
  · 判据文字含糊（只钉一句话的存在、不钉控制流）就会被变异骗过 ——
    本轮 M5/M6 首跑 MISSED，就是判据只断言了 `return refuse("…")` 存在、
    没断言它挂在哪个 guard 底下。变异测试的价值恰恰是逼出这种弱判据。
"""
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MAN = os.path.join(HERE, 'manifests', 'round_1104b.json')

S = 'app/src/main/java/io/github/ariinyume/dlsitesoundfloat/'
GEOM = S + 'hook/CapsuleGeometry.java'
IDENT = S + 'data/CacheIdentity.java'
POOL = S + 'hook/ZiptreePrefetch.java'
CACHE = S + 'data/SubtitleCache.java'
ABH = S + 'hook/ActivityButtonHook.java'

# (名字, 文件, [(old, new), ...], 预期变红的 desc 关键词)
MUTANTS = [
    ('M1 上方分支不减窗口原点', GEOM,
     [('int bottomMargin = screenH - (centerY - decorTopPx + capsuleHPx / 2);\n'
       '        // 安全钳制：别把按钮推到屏幕外',
       'int bottomMargin = screenH - (centerY + capsuleHPx / 2);\n'
       '        // 安全钳制：别把按钮推到屏幕外')],
     ['上方分支']),
    ('M2 下方分支不减窗口原点', GEOM,
     [('（见「上方」分支同一段注释）。\n        int bottomMargin = screenH - (centerY - decorTopPx + capsuleHPx / 2);',
       '（见「上方」分支同一段注释）。\n        int bottomMargin = screenH - (centerY + capsuleHPx / 2);')],
     ['下方分支']),
    ('M3 歧义闸失效（>=2 改成 >=99）', IDENT,
     [('if (candidates.size() >= 2) {', 'if (candidates.size() >= 99) {')],
     ['歧义']),
    ('M4 磁盘反证据失效', IDENT,
     [('!k.equals(only)', 'false')],
     ['磁盘反证据']),
    ('M5 指纹闸失效', IDENT,
     [('if (!any) {', 'if (!any && false) {')],
     ['指纹']),
    ('M6 强证据退回时长猜', IDENT,
     [('return refuse("作品键不在预取池里");',
       'return new Decision(workKeyHint, false, "作品键不在预取池里");')],
     ['强证据']),
    ('M7 候选漏掉无字幕轨', POOL,
     [('                for (NoSubtitleTrack n : p.noSubtitleTracks) {\n',
       '                for (NoSubtitleTrack n : java.util.Collections.<NoSubtitleTrack>emptyList()) {\n')],
     ['noSubtitleTracks']),
    ('M8 磁盘证据吃空作品键', CACHE,
     [('if (e.workKey == null || e.workKey.isEmpty() || e.durMs <= 0L) {',
       'if (e.durMs <= 0L) {')],
     ['空作品键']),
    ('M9 窗口形态变化判据失效', ABH,
     [('boolean windowMoved = decorTop != sPlacedDecorTop\n'
       '                    || screenW != sLastScreenW || screenH != sLastScreenH;',
       'boolean windowMoved = false;')],
     ['形态变化']),
    ('M10 showButton 漏传 decorTop', ABH,
     [('showButton(activity, repo, screenW, screenH, sDecorTopScreen);',
       'showButton(activity, repo, screenW, screenH, 0);')],
     ['showButton']),
]


def read_raw(path):
    with io.open(path, 'rb') as f:
        return f.read()


def write_raw(path, raw):
    with io.open(path, 'wb') as f:
        f.write(raw)


def run_manifest():
    """返回 {desc: ok}。"""
    p = subprocess.run([sys.executable, os.path.join(HERE, 'verify_layer.py'), MAN],
                       cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    txt = p.stdout.decode('utf-8', 'replace')
    fails = {}
    nfail = 0
    for line in txt.splitlines():
        t = line.strip()
        if t.startswith('FAIL'):
            nfail += 1
            body = t[4:].strip()
            key = body.split('   ')[0]
            fails[key] = body
    return nfail, fails, txt


def main():
    # baseline 存**原始字节**：还原一律写回原始字节，绝不二次转行尾（11-04 踩过 \r\r\n）
    baseline = {}
    for rel in {GEOM, IDENT, POOL, CACHE, ABH}:
        baseline[rel] = read_raw(os.path.join(REPO, rel))

    nfail, _, txt = run_manifest()
    if nfail:
        print('!! 基线不是全绿，先修基线：')
        print(txt)
        return 1
    print('基线 PASS 37/37\n')

    caught = 0
    for name, rel, subs, expect in MUTANTS:
        if expect is None:
            print('--  %s（跳过：占位）' % name)
            continue
        raw = baseline[rel]
        crlf = b'\r\n' in raw
        body = raw.decode('utf-8').replace('\r\n', '\n')
        ok = True
        for old, new in subs:
            if old not in body:
                print('!! %s：模板没匹配上 %r' % (name, old[:60]))
                ok = False
                break
            body = body.replace(old, new)
        if not ok:
            continue
        out_bytes = body.replace('\n', '\r\n') if crlf else body
        write_raw(os.path.join(REPO, rel), out_bytes.encode('utf-8'))
        try:
            nf, fails, out = run_manifest()
        finally:
            write_raw(os.path.join(REPO, rel), raw)
        hit = [k for k in expect if any(k in d for d in fails)]
        mark = 'CAUGHT ' if (nf > 0 and hit) else ('MISSED ' if nf == 0 else 'PARTIAL')
        if nf > 0 and hit:
            caught += 1
        print('%s %-28s 红 %d 条  命中预期=%s' % (mark, name, nf, hit or '—'))
        if nf and not hit:
            for d in fails.values():
                print('        · ' + d[:100])

    print('\n变异捕获 %d/%d' % (caught, len([m for m in MUTANTS if m[3]])))

    # 还原校验：逐字节比对原始字节
    bad = [rel for rel, raw in baseline.items()
           if read_raw(os.path.join(REPO, rel)) != raw]
    print('还原校验：%s' % ('全部逐字节一致' if not bad else '不一致 %r' % bad))
    return 0 if not bad else 2


if __name__ == '__main__':
    sys.exit(main())
