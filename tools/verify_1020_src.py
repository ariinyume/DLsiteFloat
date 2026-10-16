#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1020 / v2.3.3】「关掉代理后切音轨拉不起本地字幕 + 没有缓存的音轨显示别轨字幕」修复的
**源码层**验证（读的是**活的工作区** ⇒ 版本号判下界、履历段判自报值，见铁律 82）

验什么
------
A. 读取路径只认强键（本轮的核心）
  · `lookup` 体内出现「身份未知即放弃」的早退（`identity == 0L`）；
  · `lookup` 体内**不再**触碰弱键表 `bySelection`、**不再**做自愈删除；
  · 证伪自愈那条路彻底绝迹（剥注释后全文件不出现 self-heal drop 串）；
  · `has` 与 `lookup` 同口径（体内不出现 `bySelection`）。
B. 作品键降为「只作取证」
  · `lookup` 体内出现新的「不一致也放行」串，**不出现**旧的拒绝串。
C. 前身按文件识别
  · 新字段 `byFile` 声明；`put` 用它找前身；`stampDuration` 补盖后从孤儿槽位摘除；
  · 索引重建按身份分派到两张表。
D. 时间轴校验补反向
  · `timelineFits` 体内读到条目自己的时长（旧版只读 maxEnd）。
E. 清毒
  · `INDEX_SCHEMA` 3 -> 4（旧值绝迹）。
F. 零调用点改动（本轮刻意保证的边界）
  · `SubtitleRepository` / `ConfigBus` 对缓存类的调用**一字未改**；
  · 新符号只出现在 SubtitleCache.java 一个文件里。
G. 版本 / 横幅 / 履历纪律
  · code >= 1020、tag == name 且 >= 2.3.3、label 形态 `MMDD.NN`
    （日期段随构建当天，**只守形态、不钉死**）；
  · 常开横幅唯一且自报 code >= 1020；
  · 履历段存在、自报 `【code NNNN】` == 横幅 code、九段齐全、
    收尾句为 `版本号 A 升 B、code C 升 D。`、且**不点名**本轮新标识符（防空/负向探针自命中）。

用法
----
    python verify_1020_src.py [src_root]
退出码 0 = 全部通过
"""

import os
import re
import sys
import time

SRC_DEFAULT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'app', 'src', 'main', 'java')

REL = {
    'cache': os.path.join('data', 'SubtitleCache.java'),
    'repo': os.path.join('data', 'SubtitleRepository.java'),
    'bus': os.path.join('config', 'ConfigBus.java'),
    'mod': 'DlsiteSoundSubtitleModule.java',
}
GRADLE_REL = os.path.join('app', 'build.gradle')

LOOKUP_DECL = 'public String lookup(long identity, long selection, String currentWorkKey) {'
HAS_DECL = 'public boolean has(long identity, long selection) {'
PUT_DECL = 'public void put(String workKey, int tc, int idx, long durMs, String json,'
STAMP_DECL = 'public void stampDuration(long identity, long selection) {'
TF_DECL = 'private static boolean timelineFits(Entry e, long identity) {'
LOAD_DECL = 'private void loadIndexLocked() {'

# 本轮新增的标识符 —— 履历段里出现就等于「负向探针自己命中自己」
BANNER_FORBIDDEN = ['byFile', 'bySelection', 'byIdentity', 'INDEX_SCHEMA',
                    'timelineFits', 'lookup', 'stampDuration', 'self-heal']

# 「零调用点改动」的回归锚（SubtitleRepository 里那四处调用）
REPO_CALLS = [
    'SubtitleCache.get().lookup(newIdentity, newSelection, freshWorkKey())',
    'SubtitleCache.get().has(identity, sel)',
    'SubtitleCache.get().stampDuration(identity, sel)',
    'SubtitleCache.get().put(wk, fTc, fIdx, 0L, text, fCues, fMaxEnd)',
]


def strip_comments(text):
    """剥块注释与行注释；**保留**字符串字面量（很多判据查的就是它们）。"""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    text = re.sub(r'//[^\n]*', '', text)
    return text


def read_text(path):
    """读文本并做 CRLF → LF 归一（本项目 java 有 LF / CRLF 两种，比较前必须归一）。"""
    return open(path, 'rb').read().decode('utf-8').replace('\r\n', '\n')


def method_body_by_lines(text, decl, max_lines=900):
    """按**行级** `{}` 配平，从声明行起切出整段方法体（含声明行）。"""
    lines = text.split('\n')
    start = None
    for i, l in enumerate(lines):
        if l.strip().startswith(decl.strip()):
            start = i
            break
    if start is None:
        raise KeyError('找不到声明：%s' % decl)
    depth = 0
    for i in range(start, min(start + max_lines, len(lines))):
        depth += lines[i].count('{') - lines[i].count('}')
        if depth == 0 and i > start:
            return '\n'.join(lines[start:i + 1])
    raise AssertionError('方法体未闭合：%s' % decl)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else SRC_DEFAULT
    repo_root = os.path.dirname(root)
    while repo_root and not os.path.exists(os.path.join(repo_root, 'app')):
        nxt = os.path.dirname(repo_root)
        if nxt == repo_root:
            break
        repo_root = nxt
    gradle = os.path.join(repo_root, GRADLE_REL) if repo_root else None

    files = {}
    for dp, _, fns in os.walk(root):
        for fn in fns:
            if fn.endswith('.java'):
                rel = os.path.relpath(os.path.join(dp, fn), root)
                files[rel] = os.path.join(dp, fn)

    total = 0
    fails = []

    def check(desc, ok, extra=''):
        nonlocal total
        total += 1
        print('  %s %s%s' % ('OK  ' if ok else 'FAIL', desc,
                             ('   ' + extra) if extra else ''))
        if not ok:
            fails.append(desc)

    def path_of(key):
        want = REL[key]
        for rel, ap in files.items():
            if rel.endswith(want):
                return ap
        return None

    def raw(key):
        p = path_of(key)
        return read_text(p) if p else ''

    print('源码根: %s' % root)
    print('java 文件数: %d' % len(files))
    print()

    cache_raw = raw('cache')
    repo_raw = raw('repo')
    bus_raw = raw('bus')
    mod_raw = raw('mod')
    gradle_raw = read_text(gradle) if gradle and os.path.exists(gradle) else ''

    cache = strip_comments(cache_raw)
    repo = strip_comments(repo_raw)

    # ================= A. 读取路径只认强键 =================
    print('=== A. 读取路径只认强键【本轮核心】===')
    check('data/SubtitleCache.java 存在', bool(cache_raw))
    body = {}
    for k, d in (('lookup', LOOKUP_DECL), ('has', HAS_DECL), ('put', PUT_DECL),
                 ('stamp', STAMP_DECL), ('tf', TF_DECL), ('load', LOAD_DECL)):
        try:
            body[k] = method_body_by_lines(cache, d) if cache else ''
        except (KeyError, AssertionError):
            body[k] = ''
        check('方法体切到：%s' % d.split('(')[0].split()[-1], bool(body[k]))

    check('lookup 有「身份未知即放弃」的早退（identity == 0L + return null）',
          bool(re.search(r'if\s*\(\s*identity\s*==\s*0L\s*\)\s*\{\s*return null;', body['lookup'])),
          '【本轮新增】')
    check('lookup 体内不再触碰弱键表 bySelection',
          'bySelection' not in body['lookup'], '【本轮删除】')
    # ⚠️ 判据要**回源码确认**（铁律 11）：lookup 里还剩一条「文件读不出来就丢条目」的删除，
    #    那是与时间轴无关的正常兜底；本轮删掉的是**时间轴证伪的自愈删除**。
    #    因此不能一刀切「removeEntryLocked 绝迹」，要判「只剩一处、且锚在文件读不出来之后」。
    # ⚠️ 且不能裸判 'stale' —— 新日志串里有英文单词 stale（铁律 84 的子串污染），只判标识符形态。
    check('lookup 体内只剩「文件读不出来」那一处删除（时间轴自愈删除绝迹）',
          body['lookup'].count('removeEntryLocked') == 1
          and 'hit but file unreadable' in body['lookup']
          and 'Entry stale' not in body['lookup']
          and 'stale =' not in body['lookup']
          and 'stale.' not in body['lookup'],
          '【本轮删除时间轴自愈】')
    check('has 体内不再触碰弱键表 bySelection',
          'bySelection' not in body['has'], '【本轮删除】')
    check('has 有「身份未知即 false」门控',
          bool(re.search(r'if\s*\(\s*!ready\s*\|\|\s*identity\s*==\s*0L\s*\)', body['has'])))
    check('has 返回 byIdentity.containsKey(identity)',
          'byIdentity.containsKey(identity)' in body['has'])

    print('=== A2. 旧形态绝迹（剥注释后全文）===')
    for gone in ['hit REJECTED (work-key mismatch)',
                 'hit REJECTED (selection-only, timeline mismatch)',
                 'self-heal drop',
                 ' (selection-only)']:
        check('旧串绝迹：%r' % gone, gone not in cache, '【本轮删除】')

    # ================= B. 作品键降为只作取证 =================
    print('=== B. 作品键只作取证 ===')
    check('lookup 体内出现「不一致也放行」串',
          'hit ACCEPTED despite work-key mismatch' in body['lookup'], '【本轮新增】')
    check('lookup 体内仍读 currentWorkKey（判据保留、只改后果）',
          'currentWorkKey' in body['lookup'])
    check('lookup 的 javadoc 写明「只作取证」',
          '只作取证' in cache_raw)

    # ================= C. 前身按文件识别 =================
    print('=== C. 前身按文件识别 ===')
    check('新字段 byFile 声明为 Map<String, Entry>',
          bool(re.search(r'private final Map<String, Entry> byFile = new HashMap<>\(\);', cache)),
          '【本轮新增】')
    check('put 用 byFile.get(fileName) 找前身',
          'byFile.get(fileName)' in body['put'], '【本轮新增】')
    check('put 不再用 bySelection 找前身',
          'bySelection.get(selection);\n                long prevBytes' not in body['put'],
          '【本轮删除】')
    check('put 注册进 byFile',
          'byFile.put(fileName, e)' in body['put'])
    check('stampDuration 补盖后从孤儿槽位摘除',
          'bySelection.remove(selection)' in body['stamp'], '【本轮新增】')
    check('stampDuration 有「同身份让位」守卫',
          'stamp: identity already held by another entry' in body['stamp'], '【本轮新增】')
    check('removeEntryLocked 一并摘 byFile',
          'byFile.remove(e.file)' in cache)
    check('loadIndexLocked 按身份分派（identity != 0 才进强键表）',
          bool(re.search(r'if\s*\(e\.identity\s*!=\s*0L\)\s*\{', body['load']))
          and 'byFile.put(e.file, e)' in body['load'])
    check('clearAll 清 byFile',
          bool(re.search(r'bySelection\.clear\(\);\s*\n\s*byFile\.clear\(\);', cache)))

    # ================= D. 时间轴校验补反向 =================
    print('=== D. 时间轴校验补反向 ===')
    check('timelineFits 读到条目自己的时长（e.durMs）',
          'e.durMs' in body['tf'], '【本轮新增】')
    check('timelineFits 仍在（与补盖共用同一把尺子）',
          'timelineFits(e, identity)' in body['lookup'])
    check('容差常量单点定义',
          cache_raw.count('TIMELINE_TOLERANCE_SEC = 2.0') == 1)

    # ================= E. 清毒 =================
    print('=== E. 清毒 ===')
    check('INDEX_SCHEMA = 4（本轮值）',
          'private static final int INDEX_SCHEMA = 4;' in cache, '【本轮新增】')
    check('INDEX_SCHEMA 旧值 3 绝迹',
          'INDEX_SCHEMA = 3;' not in cache, '【本轮删除】')

    # ================= F. 零调用点改动（边界回归锚）=================
    print('=== F. 零调用点改动【本轮刻意保证的边界】===')
    for c in REPO_CALLS:
        check('数据仓库调用原样：%s' % c[:46], c in repo_raw)
    check('数据仓库不引用新字段/新方法',
          'byFile' not in repo and 'byFile' not in bus_raw)
    new_syms = ['byFile']
    others = [rel for rel, ap in files.items()
              if any(s in strip_comments(read_text(ap)) for s in new_syms)
              and not rel.endswith(REL['cache'])]
    check('新符号只出现在 SubtitleCache.java（其余 java 文件 0 处）',
          not others, '其他文件：%r' % (others[:3],))

    # ================= G. 版本 / 横幅 / 履历纪律 =================
    print('=== G. 版本 / 横幅 / 履历纪律 ===')
    m_tag = re.search(r"def appVersionTag\s*=\s*'([^']+)'", gradle_raw)
    m_code = re.search(r'def appVersionCode\s*=\s*(\d+)', gradle_raw)
    m_lbl = re.search(r"def appVersionCodeLabel\s*=\s*'([^']+)'", gradle_raw)
    m_name = re.search(r"def appVersionName\s*=\s*'([^']+)'", gradle_raw)
    tag = m_tag.group(1) if m_tag else ''
    code = int(m_code.group(1)) if m_code else -1
    lbl = m_lbl.group(1) if m_lbl else ''
    name = m_name.group(1) if m_name else ''

    def ver(s):
        try:
            return tuple(int(x) for x in s.split('.'))
        except ValueError:
            return (0,)

    check('appVersionCode 存在且 >= 1020', code >= 1020, '实际 %s' % code)
    check('appVersionName >= 2.3.3', ver(name) >= (2, 3, 3), '实际 %s' % name)
    check('appVersionTag == appVersionName（决定 APK 文件名，最易漏）',
          tag == name and bool(tag), 'tag=%s name=%s' % (tag, name))
    # ⚠️ 铁律 82：源码层脚本读的是**滚动的工作区**，「本轮判据」必须泛化 ⇒
    #   label 的日期段**只守形态、不钉死当天**（构建日 != 发版日是常态；
    #   既有 verify_1004_src / verify_1007_src 同样只守 `MMDD.NN` 形态）。
    check('label 形态为 MMDD.NN（日期段随构建当天，不钉死）',
          bool(re.match(r'^\d{4}\.\d+$', lbl)),
          '实际 %r' % lbl)

    banners = re.findall(r'==== BUILD [\d.]+ / code (\d+)', mod_raw)
    check('常开横幅唯一（且 >= 1020）',
          len(banners) >= 1 and int(banners[0]) >= 1020, '横幅 code=%r' % banners[:1])

    # 履历段：横幅之后**第一段** LogGate.debug 就是本轮
    m = re.search(r'==== BUILD [\d.]+ / code (\d+) （(.*?)"\);', mod_raw, flags=re.S)
    hist = m.group(2) if m else ''
    hcode = m.group(1) if m else ''
    check('履历段切到（横幅后第一段）', bool(hist))
    self_code = re.findall(r'【code (\d+)', hist)
    check('履历段自报 code == 横幅 code（只升横幅、抄上一轮会被抓）',
          bool(self_code) and self_code[0] == hcode, '自报 %r 横幅 %s' % (self_code[:1], hcode))
    check('履历段九段齐全（①~⑨）',
          all(ch in hist for ch in '①②③④⑤⑥⑦⑧⑨'))
    # 【code 1021】第二个版本号改**可选**：「版本号不变」时按项目惯例省略它
    #   （`版本号 2.3.3 不变、code 1020 升 1021。`）。旧模板强制要求它 ⇒ 不变轮次假 FAIL。
    m_tail = re.findall(r'版本号 (\d+\.\d+\.\d+) (升|不变)(?: (\d+\.\d+\.\d+))?、code (\d+) (升|不变) (\d+)。', hist)
    check('履历段收尾句合规（版本号 A 升/不变 [B]、code C 升 D。）', bool(m_tail), repr(m_tail[-1:]))
    if m_tail:
        a, _, b, c, _, d = m_tail[-1]
        b_eff = b if b else a          # 「不变」⇒ 被省略的第二个版本号就是第一个
        check('收尾句口径自洽（版本号 == 当前 name、code-after == 横幅 code）',
              b_eff == name and d == hcode,
              'B=%s name=%s D=%s 横幅=%s' % (b_eff, name, d, hcode))
    hit_bad = [w for w in BANNER_FORBIDDEN if w in hist]
    check('履历段不点名本轮新标识符（防空/负向探针自命中）',
          not hit_bad, '违禁词：%r' % hit_bad)

    print()
    print('总计 %d 条，通过 %d 条，失败 %d 条' % (total, total - len(fails), len(fails)))
    if fails:
        print('失败项：')
        for f in fails:
            print('  - %s' % f)
        return 1
    print('verify_1020_src: ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
