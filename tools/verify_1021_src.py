#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1021 / v2.3.3】「等官方字幕的窗口 3 秒 → 1 秒」的**源码层**验证
（读的是**活的工作区** ⇒ 版本号判下界、履历段判自报值，见铁律 82）

Ari 指令（2026-10-15）：
    「现在是检测到官方没有返回字幕等3秒才调用本地字幕，
      改为没收到官方字幕1秒后就尝试调用本地字幕。」

验什么
------
A. 常量层：`NO_SUBTITLE_GRACE_MS` = 1000L 是**本轮值**；同名的 3000L 绝迹；
   与它并列的另外三个时限常量（PRELOAD 3500 / CACHED 15000 / EARLY_CLOSE 5000）
   **一个都不许被动过**（本轮只该动一个数）。
B. 结构不动：窗口分级那一行原样；`hasDiskCacheFor` / `diskFallbackReady` 仍在；
   裁决兜底读盘的触发条件（`noSubtitles && !spurious` + 目标键优先）仍在；
   离线直读仍在；提前收窗取 `min(EARLY_CLOSE, grace)` 仍在。
C. 联动约束（**数值比较**，不是抄注释）：钩子侧上报静默窗 `INDEX_SUPPRESS_MS`
   必须**严格大于**本窗口 —— 这是 974「上报→作废→上报」死循环的根治条件。
D. 文档口径：本轮改了的三处交叉引用是**新形态**，旧形态绝迹；
   而带真机日志引用的**历史段原样保留**（本项目纪律：不改写历史）。
   另证两个无关的 3000L 常量没被误伤。
E. 改动范围：`【code 1021` 只出现在预期的四个 java 文件里。
F. 零调用点改动（本轮刻意保证的边界）：数据仓库对缓存类的四处调用一字未改。
G. 版本 / 横幅 / 履历纪律：code >= 1021、tag == name、label 形态 `MMDD.NN`（日期段随构建当天，只守形态）、
   横幅唯一且 >= 1021、履历段自报 `【code NNNN` == 横幅 code、九段齐全、收尾句合模板、
   且履历段**不点名**本轮新标识符（防空/负向探针自命中）。

用法
----
    python verify_1021_src.py [src_root]
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
    'repo': os.path.join('data', 'SubtitleRepository.java'),
    'src': os.path.join('hook', 'PlayerSourceHook.java'),
    'btn': os.path.join('hook', 'ActivityButtonHook.java'),
    'cache': os.path.join('data', 'SubtitleCache.java'),
    'mod': 'DlsiteSoundSubtitleModule.java',
}
GRADLE_REL = os.path.join('app', 'build.gradle')

# 本轮新标识符 —— 履历段里出现就等于「负向探针自己命中自己」
BANNER_FORBIDDEN = ['NO_SUBTITLE_GRACE_MS', 'NO_SUBTITLE_GRACE_MS_CACHED',
                    'provisionalEarlyClose', 'resolvePendingTrack',
                    'tryResumeFromDisk', 'hasDiskCacheFor', 'onTrackChanged']

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


def const_of(text, name):
    """取 `... <name> = <digits>L?;` 的数值（源码层真源）。"""
    m = re.search(r'\b%s\s*=\s*(\d+)L?\s*;' % re.escape(name), text)
    return int(m.group(1)) if m else None


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

    repo_raw = raw('repo')
    src_raw = raw('src')
    btn_raw = raw('btn')
    cache_raw = raw('cache')
    mod_raw = raw('mod')
    gradle_raw = read_text(gradle) if gradle and os.path.exists(gradle) else ''

    repo = strip_comments(repo_raw)

    # ================= A. 常量层【本轮核心】=================
    print('=== A. 常量层：只动一个数【本轮核心】===')
    check('data/SubtitleRepository.java 存在', bool(repo_raw))
    g = const_of(repo, 'NO_SUBTITLE_GRACE_MS')
    check('NO_SUBTITLE_GRACE_MS == 1000（本轮值）【本轮新增】',
          g == 1000, '实际 %r' % g)
    check('NO_SUBTITLE_GRACE_MS 旧值 3000L 绝迹【本轮删除】',
          'NO_SUBTITLE_GRACE_MS = 3000L;' not in repo)
    for nm, want in (('PRELOAD_TOLERANCE_MS', 3500),
                     ('NO_SUBTITLE_GRACE_MS_CACHED', 15000),
                     ('NO_SUBTITLE_EARLY_CLOSE_MS', 5000)):
        v = const_of(repo, nm)
        check('%s 保持 %d（本轮不该动）' % (nm, want), v == want, '实际 %r' % v)

    # ================= B. 结构不动 =================
    print('=== B. 分级 / 兜底 / 提前收窗：一行都不动 ===')
    check('窗口分级那一行原样（有本地垫背才走标准窗）',
          bool(re.search(r'grace\s*=\s*\(cueCount\s*>\s*0\s*&&\s*!diskFallbackReady\)\s*\n'
                         r'\s*\?\s*NO_SUBTITLE_GRACE_MS_CACHED\s*:\s*NO_SUBTITLE_GRACE_MS;', repo)))
    check('hasDiskCacheFor 定义仍在（纯内存索引查询）',
          'private boolean hasDiskCacheFor(long identity, long selection) {' in repo)
    check('diskFallbackReady 仍取自 hasDiskCacheFor',
          'boolean diskFallbackReady = hasDiskCacheFor(newIdentity, newSelection);' in repo)
    check('裁决兜底读盘仍在（noSubtitles && !spurious 才读）',
          'if (noSubtitles && !spurious' in repo
          and 'tryResumeFromDisk("no json in grace -> local fallback"' in repo)
    check('兜底仍优先用**本次换轨的目标键**',
          'pendingTrackIdentity != 0L ? pendingTrackIdentity' in repo
          and 'pendingTrackSelection != 0L ? pendingTrackSelection' in repo)
    check('已确认离线直读本地仍在',
          'isOffline() && tryResumeFromDisk(where, newIdentity, newSelection)' in repo)
    check('提前收窗仍取 min(NO_SUBTITLE_EARLY_CLOSE_MS, grace)',
          'Math.min(NO_SUBTITLE_EARLY_CLOSE_MS, grace)' in repo)
    check('提前收窗有「已裁决即 no-op」的卫语句',
          'token != pendingToken || !pendingTrackDecision || !floatingWindowOpen' in repo)

    # ================= C. 联动约束（数值比较）=================
    print('=== C. 联动约束：静默窗必须严格大于本窗口（数值比较）===')
    sup = const_of(strip_comments(src_raw), 'INDEX_SUPPRESS_MS')
    check('PlayerSourceHook.INDEX_SUPPRESS_MS 存在', sup is not None, '实际 %r' % sup)
    check('INDEX_SUPPRESS_MS > NO_SUBTITLE_GRACE_MS（974 死循环的根治条件）',
          sup is not None and g is not None and sup > g,
          '静默窗 %r ms > 窗口 %r ms' % (sup, g))
    check('静默窗对窗口的余量 >= 10 倍（够宽，不靠边）',
          sup is not None and g is not None and sup >= 10 * g,
          '%.1fx' % (sup / float(g)) if (sup and g) else '-')

    # ================= D. 文档口径 =================
    print('=== D. 文档口径：新形态在、旧形态绝迹、历史段不改写 ===')
    check('仓库 javadoc 记了本轮的 3000 → 1000 与理由',
          '【code 1021】3000 → 1000' in repo_raw
          and '把白等的 2 秒还给用户' in repo_raw)
    check('仓库 javadoc 复核了两处联动约束',
          'INDEX_SUPPRESS_MS' in repo_raw and 'provisionalEarlyClose' in repo_raw)
    check('裁决点「这 1 秒里」已改（旧「这 3 秒里」绝迹）',
          '这 1 秒里播放位置若一直在往前走' in repo_raw
          and '这 3 秒里播放位置若一直在往前走' not in repo_raw)

    check('钩子侧旧交叉引用绝迹：`（NO_SUBTITLE_GRACE_MS = 3000ms）`',
          '（NO_SUBTITLE_GRACE_MS = 3000ms）' not in src_raw)
    check('钩子侧旧交叉引用绝迹：`{@code NO_SUBTITLE_GRACE_MS = 3000ms}`',
          '{@code NO_SUBTITLE_GRACE_MS = 3000ms}' not in src_raw)
    check('钩子侧新口径在：静默窗两套口径下都远大于它',
          '静默窗 20000ms 在两套口径下都远大于它' in src_raw
          and '【code 1021】起 1000ms' in src_raw)
    check('钩子侧**真机日志引用**原样保留（`wait 3000ms` —— 不改写历史）',
          'wait 3000ms' in src_raw)

    check('按钮侧旧交叉引用绝迹：`数据侧那 3000ms 裁决窗一个字没动`',
          '数据侧那 3000ms 裁决窗一个字没动' not in btn_raw)
    check('按钮侧旧交叉引用绝迹：`` `NO_SUBTITLE_GRACE_MS` = 3000ms）：字幕先挂起 ``',
          '`NO_SUBTITLE_GRACE_MS` = 3000ms）：字幕先挂起' not in btn_raw)
    check('按钮侧新口径在（两处）',
          '【code 1021】起 1000ms）：字幕先挂起不显示' in btn_raw
          and '数据侧那个裁决窗（【code 1021】起 1000ms）一个字没动' in btn_raw)
    check('按钮侧**v53/v54 历史叙述**原样（带真机日志引用，不改写历史）',
          '{@code NO_SUBTITLE_GRACE_MS}(3000ms) 裁决完' in btn_raw
          and '照旧等 3000ms 数据裁决' in btn_raw)
    check('按钮侧两个**无关**的 3000L 常量未被误伤',
          'ANCHOR_HARD_TIMEOUT_MS = 3000L' in btn_raw
          and 'PLAY_BTN_RESCAN_MS = 3000L' in btn_raw)

    # ================= E. 改动范围 =================
    print('=== E. 改动范围：本轮标记只落在预期文件 ===')
    others = [rel for rel, ap in files.items()
              if '【code 1021' in read_text(ap)]

    # ⚠️ files 的键是**相对源码根**的路径（io/github/…），而 REL 是**包内短路径**（data/…）
    #   ⇒ 只能按后缀匹配（踩过：拿两组路径直接比集合会假 FAIL）。
    def _is(rel, key):
        return os.path.normpath(rel).endswith(os.path.normpath(REL[key]))

    check('含 `【code 1021` 的 java 文件恰为 预期的四个',
          len(others) == 4 and all(
              any(_is(o, k) for k in ('repo', 'src', 'btn', 'mod')) for o in others),
          '实际：%r' % sorted(others))
    check('SubtitleCache.java **不含**本轮标记（缓存类一行未动）',
          '【code 1021' not in cache_raw)
    check('build.gradle 含本轮标记（版本块注释）',
          '【code 1021】' in gradle_raw)

    # ================= F. 零调用点改动 =================
    print('=== F. 零调用点改动【本轮刻意保证的边界】===')
    for c in REPO_CALLS:
        check('数据仓库调用原样：%s' % c[:46], c in repo_raw)

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

    check('appVersionCode 存在且 >= 1021', code >= 1021, '实际 %s' % code)
    check('appVersionName >= 2.3.3（本轮**不动**语义版本号）',
          ver(name) >= (2, 3, 3), '实际 %s' % name)
    check('appVersionTag == appVersionName（决定 APK 文件名，最易漏）',
          tag == name and bool(tag), 'tag=%s name=%s' % (tag, name))
    # ⚠️ 铁律 82：源码层脚本读的是**滚动的工作区**，「本轮判据」必须泛化 ⇒
    #   label 的日期段**只守形态、不钉死当天**（构建日 != 发版日是常态；
    #   既有 verify_1004_src / verify_1007_src 同样只守 `MMDD.NN` 形态）。
    check('label 形态为 MMDD.NN（日期段随构建当天，不钉死）',
          bool(re.match(r'^\d{4}\.\d+$', lbl)),
          '实际 %r' % lbl)

    banners = re.findall(r'==== BUILD [\d.]+ / code (\d+)', mod_raw)
    check('常开横幅唯一（且 >= 1021）',
          len(banners) >= 1 and int(banners[0]) >= 1021, '横幅 code=%r' % banners[:1])

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
    # 第二个版本号**可选**：版本号「不变」时按项目惯例省略它
    # （`版本号 2.3.3 不变、code 1020 升 1021。` —— 1012~1017 各轮都这么写）。
    m_tail = re.findall(r'版本号 (\d+\.\d+\.\d+) (升|不变)(?: (\d+\.\d+\.\d+))?、code (\d+) (升|不变) (\d+)。', hist)
    check('履历段收尾句合规（版本号 A 升/不变 [B]、code C 升 D。）', bool(m_tail), repr(m_tail[-1:]))
    if m_tail:
        a, _, b, c, _, d = m_tail[-1]
        b_eff = b if b else a          # 「不变」⇒ 被省略的第二个版本号就是第一个
        check('收尾句口径自洽（版本号 == 当前 name、code-after == 横幅 code）',
              b_eff == name and d == hcode,
              'B=%s name=%s D=%s 横幅=%s' % (b_eff, name, d, hcode))
    check('履历段写明本轮「不动语义版本号」',
          '版本号 2.3.3 不变' in hist)
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
    print('verify_1021_src: ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
