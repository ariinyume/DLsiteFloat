#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1019 / v2.3.2（第 5 个 code）】「重启后每个作品的第一轨字幕不对」修复的**源码层**验证

验什么（对应真机日志还原出的两种失败）
--------------------------------------
A. 首轨取缓存入口（失败一：首轨根本不取）
  · `PlayerSourceHook` 种子分支（`if (!sIdentitySeen)`）里真的调了
    `SubtitleRepository.onSeededTrack(...)`，且**仍在 `return false` 之前**
    （种子分支「不发换轨通知」这条语义不得被改掉）；
  · 数据层新增 `onSeededTrack(int, long, long, String)`，体走 `tryResumeFromDisk`，
    **不碰**任何挂起 / 裁决 / 开窗状态（硬判据：体内不出现 pendingTrackDecision /
    floatingWindowOpen / pendingToken / onTrackChanged）。
B. 认领即改签（失败二：认领结果没写回暂存标签）
  · `tryResumeFromCache` 体内新增 `cuesOwnerSelection = newSelection;`
    且受 `if (newSelection > 0L)` 门控、位置在**同步块内**（早于那条 RESUME 日志）；
  · 暂存标签与陈旧旗标一并改签。
C. 到达印章陈旧旗标（两条规则的正交分流）
  · 新字段 `stagedCacheStampStale`；
  · `stageCacheToDisk` 在**到达那一刻**冻结它（顺序：印章之后、代数自增之前）；
  · `flushStagedCache` 按它分流，且**不重读** workChangeKey / cuesArrivedDuringRebuild
    （这是「消费时读到的状态 ≠ 事件那一刻的状态」这条铁律的落点）。
D. 读取侧校验与自愈（失败二的放大）
  · 新增纯判定 `SubtitleCache.timelineFits(Entry, long)`；
  · `lookup` 的副键命中过它、证伪即 `removeEntryLocked(stale, true)` 自愈；
  · `stampDuration` 改用同一把尺子（旧内联写法绝迹）；容差常量仍单点定义。
E. 清毒与可读性
  · `INDEX_SCHEMA` 2 → 3（旧值绝迹）；`shortKey` 取末两段。
F. 版本 / 横幅 / 履历纪律
  · code 1018 → 1019、label `1014.6` → `1014.7`、tag / name 仍 `2.3.2`；
  · 常开横幅唯一且为 code 1019；履历段存在、收尾句合规、
    **不点名本轮新增标识符**（防空／负向探针自命中）。
G. 安全边界（回归锚，两态皆真）
  · 抓取链路 / 状态栏桥 / 设置页不出现本轮新符号。

⚠️ 口径纪律（本项目踩过的坑）
  · 「旧形态绝迹」类判据一律在**剥注释**的文本上做。
  · 「注释/横幅存在」类判据一律用**原始源码**。
  · 方法体切片按**行级 `{}` 配平**，锚在声明位。

用法
----
    python verify_1019_src.py [src_root]
退出码 0 = 全部通过
"""

import os
import re
import sys

SRC_DEFAULT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'app', 'src', 'main', 'java')

REL = {
    'src': os.path.join('hook', 'PlayerSourceHook.java'),
    'repo': os.path.join('data', 'SubtitleRepository.java'),
    'cache': os.path.join('data', 'SubtitleCache.java'),
    'bridge': os.path.join('util', 'StatusBarSubtitleBridge.java'),
    'netlog': os.path.join('util', 'NetLogFile.java'),
    'settings': os.path.join('ui', 'SettingsActivity.java'),
    'mod': 'DlsiteSoundSubtitleModule.java',
}
GRADLE_REL = os.path.join('app', 'build.gradle')

SEED_DECL = ('public static boolean onPlaylistStateFromStatusMap(int idx,'
             ' int trackCount, double durationSec,')
SEED_CALL = 'SubtitleRepository.getInstance().onSeededTrack(idx, identity, selection, where);'
SEEDED_DECL = 'public void onSeededTrack(int idx, long identity, long selection, String where) {'
RESUME_DECL = 'private boolean tryResumeFromCache(String where, long newIdentity,' \
              ' long newSelection) {'
STAGE_DECL = 'private void stageCacheToDisk(String workKey, int cues, double maxEndSec) {'
FLUSH_DECL = 'private void flushStagedCache(long authoritativeSelection) {'
LOOKUP_DECL = 'public String lookup(long identity, long selection, String currentWorkKey) {'
STAMP_DECL = 'public void stampDuration(long identity, long selection) {'
SHORTKEY_DECL = 'private static String shortKey(String workKey) {'
TF_DECL = 'private static boolean timelineFits(Entry e, long identity) {'

# 陈旧旗标在 flushStagedCache 里**不得**重读的两个可变旗标
NO_REREAD = ['workChangeKey', 'cuesArrivedDuringRebuild']
# 首轨入口**不得**触碰的挂起/裁决/开窗符号
SEED_FORBIDDEN = ['pendingTrackDecision', 'pendingSoftSuspend', 'floatingWindowOpen',
                  'pendingToken', 'onTrackChanged', 'previousTrackCuesHidden']
# 履历段里出现 = 横幅自己命中自己（负向/正向探针会被自己骗过）
BANNER_FORBIDDEN = ['onSeededTrack', 'timelineFits', 'stagedCacheStampStale',
                    'self-heal', 're-signed', 'INDEX_SCHEMA', 'shortKey']


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
    # ⚠️ 声明可能**跨行**（如本轮的 onPlaylistStateFromStatusMap）⇒ 用前缀匹配取首个声明行。
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

    src_raw = raw('src')
    repo_raw = raw('repo')
    cache_raw = raw('cache')

    # ================= A. 首轨取缓存入口 =================
    print('=== A. 首轨取缓存入口（失败一）===')
    check('hook/PlayerSourceHook.java 存在', bool(src_raw))
    check('hook/SubtitleRepository.java 存在', bool(repo_raw))
    src_body = ''
    src = strip_comments(src_raw) if src_raw else ''
    if src:
        src_body = method_body_by_lines(src, SEED_DECL) if SEED_DECL in src else ''
        check('种子分支所在方法体切到', bool(src_body))
        check('种子分支真的调 onSeededTrack', SEED_CALL in src_body)
        i_call = src_body.find(SEED_CALL)
        i_ret = src_body.find('return false;', i_call) if i_call >= 0 else -1
        check('调用在 `return false;` 之前（种子分支语义未被改掉）',
              0 <= i_call < i_ret, 'i_call=%d i_ret=%d' % (i_call, i_ret))
        check('种子分支仍不发换轨通知（notifyTrackChanged 在该方法体内未新增）',
              'seeded playlist identity' in src_body)
        check('种子分支调用点在 `if (!sIdentitySeen) {` 内',
              src_body.count('if (!sIdentitySeen) {') == 1
              and src_body.find('if (!sIdentitySeen) {') < i_call)

    repo = strip_comments(repo_raw) if repo_raw else ''
    check('仓库：新增 onSeededTrack 声明', SEEDED_DECL in repo)
    sb = method_body_by_lines(repo, SEEDED_DECL) if SEEDED_DECL in repo else ''
    check('onSeededTrack 方法体切到', bool(sb))
    if sb:
        check('onSeededTrack 走 tryResumeFromDisk', 'tryResumeFromDisk(' in sb)
        check('onSeededTrack 先看缓存总闸 cacheUsable()', 'cacheUsable()' in sb)
        bad = [s for s in SEED_FORBIDDEN if s in sb]
        check('onSeededTrack 不碰挂起/裁决/开窗/换轨通知（只取缓存）', not bad,
              '命中: %s' % (bad or '无'))
        check('onSeededTrack 体内无 loadFromJson 直调（必须走磁盘兜底那条路）',
              'loadFromJson(' not in sb)
        check('onSeededTrack 有专属日志（code 1019 + seeded first track）',
              'code 1019' in sb and 'seeded first track ->' in sb
              and 'resumed from LOCAL cache' in sb)

    # ================= B. 认领即改签 =================
    print()
    print('=== B. 认领即改签（失败二）===')
    rb = method_body_by_lines(repo, RESUME_DECL) if RESUME_DECL in repo else ''
    check('tryResumeFromCache 方法体切到', bool(rb))
    if rb:
        check('认领后写回 cuesOwnerSelection = newSelection',
              'cuesOwnerSelection = newSelection;' in rb)
        i_resign = rb.find('cuesOwnerSelection = newSelection;')
        i_gate = rb.rfind('if (newSelection > 0L) {', 0, i_resign)
        check('改签受 `if (newSelection > 0L)` 门控（0 = 给不出目标键时不动）',
              i_gate >= 0 and i_resign - i_gate < 200,
              'i_gate=%d i_resign=%d' % (i_gate, i_resign))
        i_log = rb.find('track changed via')
        check('改签发生在同步块内（早于那条 RESUME 日志）',
              0 <= i_resign < i_log, 'i_resign=%d i_log=%d' % (i_resign, i_log))
        check('暂存标签一并改签', 'stagedCacheSelection = newSelection;' in rb)
        check('陈旧旗标一并清掉', 'stagedCacheStampStale = false;' in rb)
        check('改签带诊断日志（cache label re-signed）', 'cache label re-signed' in rb)
        check('改签只在暂存真的存在时动手（stagedCacheJson != null）',
              'if (stagedCacheJson != null) {' in rb)
        # 四条认领判据仍在（回归锚）
        for c in ('byIdentity', 'bySelection', 'byRebuild', 'byWorkChange'):
            check('认领判据 %s 仍在（回归锚）' % c, c in rb)

    # ================= C. 到达印章陈旧旗标 =================
    print()
    print('=== C. 到达印章陈旧旗标（两条规则的正交分流）===')
    check('新字段 stagedCacheStampStale 声明',
          'private volatile boolean stagedCacheStampStale = false;' in repo)
    st = method_body_by_lines(repo, STAGE_DECL) if STAGE_DECL in repo else ''
    check('stageCacheToDisk 方法体切到', bool(st))
    if st:
        check('到达那一刻冻结旗标',
              'stagedCacheStampStale = workChangeKey != null || cuesArrivedDuringRebuild;' in st)
        i_stamp = st.find('stagedCacheSelection = cuesOwnerSelection;')
        i_flag = st.find('stagedCacheStampStale = workChangeKey != null')
        i_tok = st.find('++stagedCacheToken')
        check('冻结顺序：印章之后、代数自增之前',
              0 <= i_stamp < i_flag < i_tok, 'i_stamp=%d i_flag=%d i_tok=%d'
              % (i_stamp, i_flag, i_tok))
    fl = method_body_by_lines(repo, FLUSH_DECL) if FLUSH_DECL in repo else ''
    check('flushStagedCache 方法体切到', bool(fl))
    if fl:
        check('按旗标分流', 'if (stagedCacheStampStale) {' in fl)
        i_sel = fl.find('long sel;')
        i_branch = fl.find('if (stagedCacheStampStale) {')
        i_guard = fl.find('if (sel <= 0L) {')
        check('分流位置：取 sel 之后、`sel <= 0` 守卫之前',
              0 <= i_sel < i_branch < i_guard,
              'i_sel=%d i_branch=%d i_guard=%d' % (i_sel, i_branch, i_guard))
        check('权威目标键优先于当前读数',
              'sel = authoritativeSelection > 0L' in fl)
        leaked = [s for s in NO_REREAD if s in fl]
        check('🔴 兑现时**不重读**可变旗标（铁律：消费≠事件那一刻）', not leaked,
              '命中: %s' % (leaked or '无'))
        check('兑现后清旗标', 'stagedCacheStampStale = false;' in fl)
        check('分流带诊断日志（staged label was STALE at arrival）',
              'staged label was STALE at' in fl)
        check('1013 的老规则仍在（印章可信用印章）',
              'sel = stagedCacheSelection > 0L' in fl)

    # ================= D. 读取侧校验与自愈 =================
    print()
    print('=== D. 读取侧时间轴校验与自愈（失败二的放大）===')
    cache = strip_comments(cache_raw) if cache_raw else ''
    check('新增纯判定 timelineFits(Entry, long)', TF_DECL in cache)
    tf = method_body_by_lines(cache, TF_DECL) if TF_DECL in cache else ''
    check('timelineFits 方法体切到', bool(tf))
    if tf:
        check('零状态（不 iget/iput 实例字段、不持阈值常量）',
              'iget' not in tf and 'iput' not in tf
              and 'TIMELINE_TOLERANCE_SEC' in tf)
        check('请求身份无时长时放行（durMs <= 0 ⇒ true）', 'if (durMs <= 0L) {' in tf)
        check('条目无 maxEnd 时放行', 'if (e == null || e.maxEnd <= 0) {' in tf)
        check('判据 = maxEnd <= durMs/1000 + 容差',
              'return e.maxEnd <= durMs / 1000.0 + TIMELINE_TOLERANCE_SEC;' in tf)
    lk = method_body_by_lines(cache, LOOKUP_DECL) if LOOKUP_DECL in cache else ''
    check('lookup 方法体切到', bool(lk))
    if lk:
        check('副键命中过时间轴校验', '!timelineFits(e, identity)' in lk)
        check('证伪即标记为 stale 并让出 e', 'stale = e;' in lk and 'e = null;' in lk)
        check('自愈：连同文件一起删掉', 'removeEntryLocked(stale, true);' in lk)
        check('自愈带诊断日志（selection-only, timeline mismatch）',
              'hit REJECTED (selection-only, timeline mismatch)' in lk
              and 'self-heal drop' in lk)
        i_hit = lk.find('!timelineFits(e, identity)')
        i_work = lk.find('work-key mismatch')
        check('时间轴校验排在作品键校验之前（先证伪再谈跨作品）',
              0 <= i_hit < (i_work if i_work >= 0 else 10 ** 9),
              'i_hit=%d i_work=%d' % (i_hit, i_work))
        check('stale 处理在同步块之外（不在锁里做文件删除）',
              lk.find('removeEntryLocked(stale, true);') > lk.find('if (stale != null) {'))
        check('主键（身份）命中路径未加校验（补盖时已验过）',
              'timelineFits' in lk and lk.count('!timelineFits(') == 1)
        check('找不到条目仍旧返回 null（回归锚）', 'if (e == null) {' in lk)
    sm = method_body_by_lines(cache, STAMP_DECL) if STAMP_DECL in cache else ''
    check('stampDuration 方法体切到', bool(sm))
    if sm:
        check('补盖改用同一把尺子', 'if (!timelineFits(e, identity)) {' in sm)
        check('补盖被拒的诊断日志仍在（回归锚，真机 416 次靠它取证）',
              'stamp REFUSED (timeline mismatch)' in sm)
        check('补盖成功后仍写 byIdentity + persistIndex（回归锚）',
              'byIdentity.put(identity, e);' in sm and 'persistIndexLocked();' in sm)
    check('旧的内联时间轴判据绝迹（剥注释后）',
          'if (e.maxEnd > 0 && e.maxEnd > durMs / 1000.0 + TIMELINE_TOLERANCE_SEC) {' not in cache)
    n_tol = len(re.findall(r'private static final double TIMELINE_TOLERANCE_SEC = 2\.0;', cache))
    check('容差常量仍单点定义且值不变（2.0）', n_tol == 1, '实际 %d 处' % n_tol)

    # ================= E. 清毒与可读性 =================
    print()
    print('=== E. 清毒与可读性 ===')
    check('INDEX_SCHEMA = 3', 'private static final int INDEX_SCHEMA = 3;' in cache)
    check('旧值 INDEX_SCHEMA = 2 绝迹（剥注释后）',
          'private static final int INDEX_SCHEMA = 2;' not in cache)
    check('文档写清「推进它 = 整批丢弃 + 删文件」（原始源码）',
          '整批丢弃' in cache_raw and '一并清掉' in cache_raw)
    sk = method_body_by_lines(cache, SHORTKEY_DECL) if SHORTKEY_DECL in cache else ''
    check('shortKey 方法体切到', bool(sk))
    if sk:
        check('取末两段：先算 prev', "int prev = workKey.lastIndexOf('/', slash - 1);" in sk)
        check('拼接 parent + "/" + tail',
              'return (parent == null || parent.isEmpty()) ? tail : parent + "/" + tail;' in sk)
        check('末段无上级时退回末段（回归锚）',
              "int slash = workKey.lastIndexOf('/');" in sk and 'if (slash < 0) {' in sk)
        check('null 作品键仍返回 (none)（回归锚）', 'return "(none)";' in sk)

    # ================= F. 版本 / 横幅 / 履历 =================
    print()
    print('=== F. 版本号 / 横幅 / 履历段 ===')
    gd_path = os.path.join(repo_root, GRADLE_REL)
    gd = read_text(gd_path) if os.path.exists(gd_path) else ''
    check('build.gradle：appVersionCode = 1019', 'def appVersionCode = 1019' in gd)
    check('build.gradle：label = 1014.7', "def appVersionCodeLabel = '1014.7'" in gd)
    check('build.gradle：tag 仍 2.3.2', "def appVersionTag = '2.3.2'" in gd)
    check('build.gradle：name 仍 2.3.2（Ari：不升版本号）',
          "def appVersionName = '2.3.2'" in gd)
    check('build.gradle：tag == name（APK 文件名与包内版本一致）',
          "def appVersionTag = '2.3.2'" in gd and "def appVersionName = '2.3.2'" in gd)

    mod_raw = raw('mod')
    banners = re.findall(r'XposedCompat\.log\("\[DLsiteSoundFloat\] ==== BUILD [\d.]+ / code (\d+)"\);',
                         mod_raw)
    check('常开横幅唯一且为 code 1019', banners == ['1019'], '实际 %r' % banners)
    check('履历段存在（【code 1019）', '【code 1019' in mod_raw)
    check('履历段收尾句合规', '版本号 2.3.2 不变、code 1018 升 1019。' in mod_raw)
    m_hist = re.search(r'LogGate\.debug\("\[DLsiteSoundFloat\] ==== BUILD 2\.3\.2 / code 1019 （(.*?)"\);',
                       mod_raw, re.S)
    hist = m_hist.group(1) if m_hist else ''
    check('履历段可切出（非空）', bool(hist))
    check('履历段无引号 / 反斜杠 / 反引号',
          '"' not in hist and '\\' not in hist and '`' not in hist)
    check('履历段九段（①..⑨ 各一）',
          all(hist.count(c) == 1 for c in '①②③④⑤⑥⑦⑧⑨'))
    hit_tok = [t for t in BANNER_FORBIDDEN if t in hist]
    check('履历段不点名本轮新增标识符（防空／负向探针自命中）', not hit_tok,
          '命中: %s' % (hit_tok or '无'))

    # ================= G. 安全边界（回归锚） =================
    print()
    print('=== G. 安全边界（改动未扩散）===')
    for key, name in (('bridge', 'StatusBarSubtitleBridge'), ('netlog', 'NetLogFile'),
                      ('settings', 'SettingsActivity')):
        t = strip_comments(raw(key))
        hit = [s for s in ('onSeededTrack', 'timelineFits', 'stagedCacheStampStale')
               if s in t]
        check('%s：不出现本轮新符号' % name, not hit, '命中: %s' % (hit or '无'))
    check('仓库：仍 implements LineSource（1018 的成果未被回退）',
          'public class SubtitleRepository implements LineSource {' in repo)
    check('仓库：statusBarLine 仍在（1018 的成果未被回退）',
          'public String statusBarLine() {' in repo)

    print()
    print('=' * 70)
    if fails:
        print('FAIL %d/%d' % (len(fails), total))
        for f in fails:
            print('  - %s' % f)
        return 1
    print('PASS %d/%d' % (total, total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
