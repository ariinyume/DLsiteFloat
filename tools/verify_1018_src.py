#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1018 / v2.3.2（第 4 个 code）】架构审查三项的**源码层**验证

验什么（对应 `架构审查报告-20261014.md` 的 2.2 / 2.3 / 2.6）
------------------------------------------------------------
2.2 抽检测前置闸：
  · 新类 `hook/DetectGatePolicy` 存在、是三常量 + 一个零状态纯函数；
  · `detectAndLayout` 改调它，且**两道闸的旧写法在该方法体内绝迹**；
  · 副作用（写 sForceNextDetect / sLastDetectMs / sQuietScanSkips / 心跳节奏）**仍在原处**；
  · 阈值常量 `DETECT_MIN_INTERVAL_MS` / `PAGE_MOTION_HOLD_MS` 仍各只有一处定义。
2.3 断 util → data 反向依赖：
  · 新接口 `util/LineSource` 存在，`SubtitleRepository implements LineSource`；
  · 桥的五个签名改 `LineSource`，删掉的 `computeCurrentLine` / `join` **搬到数据层**；
  · 新类 `util/AppEnv` 承接宿主上下文，`NetLogFile` 不再回头找数据层要；
  · 🔴 **包级硬判据：整个 util 包不再出现 `import …data.`**。
2.6 dp 归口：
  · `Utils.dip2pxF(DisplayMetrics, float)` 存在；
  · 三个自绘视图的 `dp()` 全部转发它，旧的裸写形态绝迹；
  · 旧的两个 int 口径**保持不动**（回归锚）。
版本与横幅（**code 1019 起收回泛化**，见本节注释）：
  · `appVersionCode` 判**下界 >= 1018**、label 判 `MMDD.N` 形态、tag / name 仍 `2.3.2`；
  · 常开横幅唯一且 `>= 1018`；**履历段自报的 `【code NNNN` 必须等于横幅 code**；
    收尾句按模板判「`code (b-1) 升 b`」；
  · 履历段不点名本轮新增标识符（防空／负向探针自命中）。

⚠️ 口径纪律（本项目踩过的坑）
  · 「旧形态绝迹」类判据一律在**剥注释**的文本上做（否则注释里提到旧代码会误报）。
  · 「注释/横幅存在」类判据一律用**原始源码**（剥注释后必然搜不到）。
  · 方法体切片按**行级 `{}` 配平**，锚在声明位。

用法
----
    python verify_1018_src.py [src_root]
退出码 0 = 全部通过
"""

import os
import re
import sys

SRC_DEFAULT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'app', 'src', 'main', 'java')

PKG = 'io.github.ariinyume.dlsitesoundfloat'
REL = {
    'act': os.path.join('hook', 'ActivityButtonHook.java'),
    'gate': os.path.join('hook', 'DetectGatePolicy.java'),
    'bridge': os.path.join('util', 'StatusBarSubtitleBridge.java'),
    'linesrc': os.path.join('util', 'LineSource.java'),
    'appenv': os.path.join('util', 'AppEnv.java'),
    'netlog': os.path.join('util', 'NetLogFile.java'),
    'utils': os.path.join('util', 'Utils.java'),
    'repo': os.path.join('data', 'SubtitleRepository.java'),
    'close': os.path.join('view', 'CloseButtonView.java'),
    'grip': os.path.join('view', 'GripIndicatorView.java'),
    'badge': os.path.join('view', 'NotificationBadgeView.java'),
    'mod': 'DlsiteSoundSubtitleModule.java',
}
GRADLE_REL = os.path.join('app', 'build.gradle')

# ── 2.2 ────────────────────────────────────────────────────────────
GATE_DECL = 'private static void detectAndLayout(Activity activity, SubtitleRepository repo) {'
GATE_OLD_THROTTLE = 'if (!sForceNextDetect && now - sLastDetectMs < DETECT_MIN_INTERVAL_MS) {'
GATE_OLD_FOLLOW = 'if (sFollowing && sLastPageMotionMs != 0L'
# ── 2.3 ────────────────────────────────────────────────────────────
BRIDGE_SIGS = [
    'public static boolean canToggle(LineSource src) {',
    'public static void resendCurrentFromRepo(Context ctx, LineSource src) {',
    'public static void sendCurrentFromRepo(Context ctx, LineSource src) {',
    'private static boolean isPlaying(LineSource src) {',
    'private static long computeCurrentDurationMs(LineSource src) {',
]
# ── 2.6 ────────────────────────────────────────────────────────────
DPI_FWD = 'Utils.dip2pxF(getResources().getDisplayMetrics(), v)'
# ── 本轮新增标识符（履历段里出现 = 横幅自己命中自己）──────────────
BANNER_FORBIDDEN = ['DetectGatePolicy', 'LineSource', 'AppEnv',
                    'statusBarLine', 'joinCue', 'dip2pxF']


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
        if l.strip() == decl.strip():
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
    repo_root = os.path.dirname(root)          # …/DLsiteSound_FloatSubtitle
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

    # ================= 2.2 抽检测前置闸 =================
    print('=== 2.2 检测前置闸（DetectGatePolicy）===')
    gate_raw = raw('gate')
    check('hook/DetectGatePolicy.java 存在', gate_raw is not None)
    gate = strip_comments(gate_raw) if gate_raw else ''
    if gate:
        check('类声明为 package-private final class',
              'final class DetectGatePolicy {' in gate)
        check('私有构造（类不实例化）', 'private DetectGatePolicy() {}' in gate)
        for c, v in (('PROCEED', '0'), ('SKIP_THROTTLE', '1'), ('SKIP_FOLLOWING', '2')):
            check('常量 %s = %s' % (c, v),
                  ('static final int %s = %s;' % (c, v)) in gate)
        check('decide(...) 七参纯函数签名',
              'static int decide(long now, long lastDetectMs, boolean forceNext,' in gate
              and 'long minIntervalMs, long pageMotionHoldMs) {' in gate)
        check('① 节流闸判据形态', 'if (!forceNext && now - lastDetectMs < minIntervalMs) {'
              in gate and 'return SKIP_THROTTLE;' in gate)
        check('② 跟手闸判据形态',
              'if (following && lastPageMotionMs != 0L' in gate
              and '&& now - lastPageMotionMs < pageMotionHoldMs) {' in gate
              and 'return SKIP_FOLLOWING;' in gate)
        # 零状态：不得出现 hook 侧的字段名 / 阈值常量
        leaked = [s for s in ('sForceNextDetect', 'sLastDetectMs', 'sQuietScanSkips',
                              'sNextHeartbeatMs', 'DETECT_MIN_INTERVAL_MS',
                              'PAGE_MOTION_HOLD_MS', 'FOLLOW_QUIET_HEARTBEAT_MS')
                  if s in gate]
        check('零状态：不读 hook 侧字段 / 不持阈值常量', not leaked,
              '泄漏: %s' % (leaked or '无'))

    act_raw = raw('act')
    act = strip_comments(act_raw) if act_raw else ''
    body = method_body_by_lines(act, GATE_DECL) if act else ''
    body_lines = body.count('\n') + 1 if body else 0
    check('detectAndLayout 方法体切到（300~500 行）', 300 <= body_lines <= 500,
          '实际 %d 行' % body_lines)
    if body:
        check('改调 DetectGatePolicy.decide(...)',
              'DetectGatePolicy.decide(now, sLastDetectMs, sForceNextDetect,' in body
              and 'sFollowing, sLastPageMotionMs,' in body)
        check('节流分支按返回值走', 'if (gate == DetectGatePolicy.SKIP_THROTTLE) {' in body)
        check('跟手分支按返回值走', 'if (gate == DetectGatePolicy.SKIP_FOLLOWING) {' in body)
        check('旧节流写法已绝迹', GATE_OLD_THROTTLE not in body)
        check('旧跟手写法已绝迹', GATE_OLD_FOLLOW not in body)
        # 副作用必须留在原处
        for s, d in (('sForceNextDetect = false;', '清 force 标志'),
                     ('sLastDetectMs = now;', '记检测时刻'),
                     ('sQuietScanSkips++;', '跳过计数自增'),
                     ('sNextHeartbeatMs = FOLLOW_QUIET_HEARTBEAT_MS;', '跳过期心跳节奏')):
            check('副作用仍在原处：%s' % d, s in body)
        # 顺序：清 force / 记时刻 必须早于跟手分支
        i_reset = body.find('sForceNextDetect = false;')
        i_follow = body.find('if (gate == DetectGatePolicy.SKIP_FOLLOWING) {')
        check('顺序与原实现一致（推进状态先于跟手分支）',
              0 <= i_reset < i_follow, 'i_reset=%d i_follow=%d' % (i_reset, i_follow))
    for c, v in (('DETECT_MIN_INTERVAL_MS', '150L'), ('PAGE_MOTION_HOLD_MS', '200L')):
        n = len(re.findall(r'private static final long %s = %s;' % (c, v), act))
        check('阈值常量 %s 仍单点定义（且值不变）' % c, n == 1, '实际 %d 处' % n)

    # ================= 2.3 断 util → data =================
    print()
    print('=== 2.3 依赖倒置（util 不再依赖 data）===')
    ls_raw = raw('linesrc')
    check('util/LineSource.java 存在', ls_raw is not None)
    if ls_raw:
        check('LineSource 是 public interface', 'public interface LineSource {' in ls_raw)
        for sig in ('boolean isPlayingOrUnknown();', 'String statusBarLine();',
                    'long getCurrentCueDurationMs();', 'boolean shouldShowNoSubtitles();'):
            check('接口声明 %s' % sig, sig in strip_comments(ls_raw))
        check('接口不暴露数据层类型（无 SubtitleCue / SubtitleRepository）',
              'SubtitleCue' not in strip_comments(ls_raw)
              and 'SubtitleRepository' not in strip_comments(ls_raw))

    br_raw = raw('bridge')
    br = strip_comments(br_raw) if br_raw else ''
    check('桥：不再 import data 包',
          'import io.github.ariinyume.dlsitesoundfloat.data.' not in br_raw)
    check('桥：不再 import android.text.TextUtils',
          'import android.text.TextUtils;' not in br_raw)
    check('桥：不再 import java.util.List', 'import java.util.List;' not in br_raw)
    check('桥：剥注释后不出现 SubtitleRepository', 'SubtitleRepository' not in br)
    check('桥：剥注释后不出现 SubtitleCue', 'SubtitleCue' not in br)
    for sig in BRIDGE_SIGS:
        check('桥签名：%s' % sig.split('(')[0].split()[-1] + '(LineSource src)', sig in br)
    check('桥：statusBarLine() 在两条推送上各调一次',
          br.count('src.statusBarLine()') == 2, '实际 %d 次' % br.count('src.statusBarLine()'))
    for c in ('src.isPlayingOrUnknown()', 'src.getCurrentCueDurationMs()',
              'src.shouldShowNoSubtitles()'):
        check('桥：仍调用 %s' % c, c in br)
    check('桥：旧的 computeCurrentLine 已绝迹', 'computeCurrentLine' not in br)
    check('桥：旧的 join(SubtitleCue) 已绝迹',
          'private static String join(SubtitleCue cue)' not in br)
    # 老脚本的回归锚（verify_995 / verify_protocol_src 会独立再判一次）
    check('桥：LogGate.debug 仍在（verify_995 的判据）', 'LogGate.debug' in br)
    check('桥：Protocol 常量转发壳仍在（≥6）',
          len(re.findall(r'=\s*Protocol\.[A-Z_]+', br)) >= 6)

    rp_raw = raw('repo')
    rp = strip_comments(rp_raw) if rp_raw else ''
    check('仓库：implements LineSource', 'public class SubtitleRepository implements LineSource {'
          in rp)
    check('仓库：import util.LineSource',
          'import io.github.ariinyume.dlsitesoundfloat.util.LineSource;' in rp_raw)
    check('仓库：import android.text.TextUtils',
          'import android.text.TextUtils;' in rp_raw)
    for m in ('isPlayingOrUnknown', 'getCurrentCueDurationMs',
              'shouldShowNoSubtitles', 'statusBarLine'):
        check('仓库：%s 带 @Override' % m,
              re.search(r'@Override\s+public [\w<>\[\], .]+ %s\(\)' % m, rp) is not None)
    check('仓库：新增 joinCue(SubtitleCue)',
          'private static String joinCue(SubtitleCue cue) {' in rp)
    sbl = method_body_by_lines(rp, 'public String statusBarLine() {') if rp else ''
    check('仓库：statusBarLine 方法体切到', bool(sbl))
    if sbl:
        for c in ('getCues()', 'findCurrentCueIndex()', 'getCurrentSubtitles()',
                  'joinCue(cues.get(idx))', 'TextUtils.join(" ", cur)'):
            check('statusBarLine 体含 %s' % c, c in sbl)
        check('statusBarLine **自身不加锁**（锁粒度与原来一致）',
              'synchronized' not in sbl)

    nl_raw = raw('netlog')
    nl = strip_comments(nl_raw) if nl_raw else ''
    check('NetLogFile：不再 import data 包',
          'import io.github.ariinyume.dlsitesoundfloat.data.' not in nl_raw)
    check('NetLogFile：剥注释后不出现 SubtitleRepository', 'SubtitleRepository' not in nl)
    check('NetLogFile：改读 AppEnv.app()', 'ctx = AppEnv.app();' in nl)

    ae_raw = raw('appenv')
    check('util/AppEnv.java 存在', ae_raw is not None)
    if ae_raw:
        ae = strip_comments(ae_raw)
        check('AppEnv 是 public final class', 'public final class AppEnv {' in ae)
        check('AppEnv：volatile 静态字段',
              'private static volatile Context sAppContext;' in ae)
        check('AppEnv：install 忽略 null',
              'public static void install(Context ctx) {' in ae and 'if (ctx != null) {' in ae)
        check('AppEnv：app() 读取入口', 'public static Context app() {' in ae)

    mod_raw = raw('mod')
    mod = strip_comments(mod_raw) if mod_raw else ''
    check('Module：登记宿主上下文', 'AppEnv.install(appCtx);' in mod)

    # 🔴 包级硬判据
    util_dir = os.path.join(root, 'io', 'github', 'ariinyume', 'dlsitesoundfloat', 'util')
    bad = []
    for rel, ap in sorted(files.items()):
        if os.path.dirname(rel).replace('\\', '/').endswith('dlsitesoundfloat/util'):
            if 'import io.github.ariinyume.dlsitesoundfloat.data.' in read_text(ap):
                bad.append(rel)
    check('🔴 包级判据：整个 util 包不再 import data 包', not bad,
          '残留: %s' % (bad or '无'))

    # ================= 2.6 dp 归口 =================
    print()
    print('=== 2.6 dp 归口（Utils.dip2pxF）===')
    ut_raw = raw('utils')
    ut = strip_comments(ut_raw) if ut_raw else ''
    check('Utils：import DisplayMetrics', 'import android.util.DisplayMetrics;' in ut_raw)
    check('Utils：新增 dip2pxF(DisplayMetrics, float)',
          'public static float dip2pxF(DisplayMetrics dm, float dp) {' in ut)
    check('Utils：dip2pxF 走 applyDimension（与原来同源）',
          'return TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, dp, dm);' in ut)
    for s in ('public static int dip2px(Context ctx, float dp) {',
              'public static int dip2pxOrDefault(Context ctx, float dp) {',
              'public static int applyDimensionDip(Context ctx, float dp) {'):
        check('Utils：旧口径保留（回归锚）%s' % s.split(' ')[-2], s in ut)

    for key, name in (('close', 'CloseButtonView'), ('grip', 'GripIndicatorView'),
                      ('badge', 'NotificationBadgeView')):
        v_raw = raw(key)
        v = strip_comments(v_raw) if v_raw else ''
        check('%s：dp() 转发 Utils.dip2pxF' % name, DPI_FWD in v)
        check('%s：旧的裸写形态绝迹' % name,
              'TypedValue.applyDimension' not in v
              and 'v * getResources().getDisplayMetrics().density' not in v)
        check('%s：import util.Utils' % name,
              'import io.github.ariinyume.dlsitesoundfloat.util.Utils;' in v_raw)
        check('%s：不在用 TypedValue' % name,
              'import android.util.TypedValue;' not in v_raw)

    # ================= 版本号 / 横幅 / 履历 =================
    print()
    print('=== 版本号 / 横幅 / 履历段 ===')
    gd_path = os.path.join(repo_root, GRADLE_REL)
    gd = read_text(gd_path) if os.path.exists(gd_path) else ''
    # 🔴 【铁律 82 / code 1019 收回泛化】源码层脚本读的是**会往前滚的工作区**：
    #   本节原先钉死 1018 / 1014.6 / 1017 升 1018 ⇒ 工作区一升版就必出假 FAIL。
    #   现改为「版本号判下界」+「履历段自报 code 必须等于横幅 code」+「收尾句按模板判」。
    m_code = re.search(r'def appVersionCode = (\d+)', gd)
    code_now = int(m_code.group(1)) if m_code else 0
    check('build.gradle：appVersionCode >= 1018（下界，不再钉死）', code_now >= 1018,
          '实际 %s' % (m_code.group(1) if m_code else '缺失'))
    check('build.gradle：label 存在且为 MMDD.N 形态',
          re.search(r"def appVersionCodeLabel = '\d{4}\.\d+'", gd) is not None)
    # 【code 1020】这一组原来钉死在 2.3.2（属 code 1018 那轮的**本轮判据**）；
    #   1020 按 Ari 指令升到 2.3.3。按铁律 82 收回泛化：只守那条**不变式** ——
    #   tag == name（tag 决定 APK 文件名，与包内版本必须一致）。
    _mt = re.search(r"def appVersionTag\s*=\s*'([^']+)'", gd)
    _mn = re.search(r"def appVersionName\s*=\s*'([^']+)'", gd)
    _tag = _mt.group(1) if _mt else ''
    _nam = _mn.group(1) if _mn else ''
    check('build.gradle：tag 与 name 都成型且相等（APK 文件名与包内版本一致）',
          bool(_tag) and _tag == _nam
          and re.match(r'^\d+\.\d+\.\d+$', _tag) is not None,
          'tag=%s name=%s' % (_tag, _nam))

    banners = re.findall(r'XposedCompat\.log\("\[DLsiteSoundFloat\] ==== BUILD [\d.]+ / code (\d+)"\);',
                         mod_raw)
    check('常开横幅唯一且 >= code 1018', len(banners) == 1 and int(banners[0]) >= 1018,
          '实际 %r' % banners)
    bcode = banners[0] if banners else ''
    check('履历段存在（自报 code == 横幅 code）',
          bool(bcode) and ('【code %s' % bcode) in mod_raw)
    check('履历段收尾句合规（code (b-1) 升 b）',
          bool(bcode) and ('、code %d 升 %s。' % (int(bcode) - 1, bcode)) in mod_raw)
    m_hist = re.search(r'LogGate\.debug\("\[DLsiteSoundFloat\] ==== BUILD [\d.]+ / code %s （(.*?)"\);'
                       % re.escape(bcode),
                       mod_raw, re.S)
    hist = m_hist.group(1) if m_hist else ''
    check('履历段可切出（非空）', bool(hist))
    check('履历段无引号 / 反斜杠 / 反引号',
          '"' not in hist and '\\' not in hist and '`' not in hist)
    hit_tok = [t for t in BANNER_FORBIDDEN if t in hist]
    check('履历段不点名本轮新增标识符（防空／负向探针自命中）', not hit_tok,
          '命中: %s' % (hit_tok or '无'))

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
