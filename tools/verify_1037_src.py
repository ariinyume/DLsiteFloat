#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1037 / v2.4.0】日常日志降噪 ＋ 验证链两处根治的 **源码层** 验证。

分节
----
A 日志降噪（缓存层双写绝迹 / 告警点分流 / 三组高频行归调试）
B 验证链（dump 完整性哨兵 / 临时 dex 不删 / 998 现状复验 / ENVBLOCK 说明仍在）
C 版本号 / 横幅 / 履历段
D 边界（本轮不动资源与功能路径）

口径
----
· 一律「剥注释后判」：注释里写着 `XposedCompat.log` 不算调用点。
· 本脚本守的是**本轮意图**，不钉死「将来不许再变」：将来真要再加常开日志，
  改这里的上界即可，别绕过。
用法
----
    python verify_1037_src.py
退出码 0 = 全部通过
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
JAVA = os.path.join(ROOT, 'app', 'src', 'main', 'java', 'io', 'github', 'ariinyume',
                    'dlsitesoundfloat')

fails = []
total = 0
note = []


def check(name, ok, detail=''):
    global total
    total += 1
    if ok:
        print('  OK   %s%s' % (name, ('   ' + detail) if detail else ''))
    else:
        print('  FAIL %s   %s' % (name, detail))
        fails.append(name)


def rd(rel, base=None):
    p = os.path.join(base or JAVA, rel)
    with io.open(p, 'r', encoding='utf-8', errors='replace', newline='') as f:
        return f.read().replace('\r\n', '\n')


def strip_comments(s):
    """剥 // 行注释与 /* */ 块注释（**保留字符串字面量里的 //**，如 URL）。

    做法：逐字符走，遇到 " 就整段吞到配对的 " 为止；遇到 // 或 /* 才起注释态。
    """
    out = []
    i = 0
    n = len(s)
    state = None          # None / 'line' / 'block' / 'str'
    while i < n:
        c = s[i]
        if state is None:
            if c == '"':
                state = 'str'
                out.append(c)
            elif c == '/' and i + 1 < n and s[i + 1] == '/':
                state = 'line'
                i += 1
            elif c == '/' and i + 1 < n and s[i + 1] == '*':
                state = 'block'
                i += 1
            else:
                out.append(c)
        elif state == 'str':
            out.append(c)
            if c == '\\' and i + 1 < n:
                out.append(s[i + 1])
                i += 1
            elif c == '"':
                state = None
        elif state == 'line':
            if c == '\n':
                state = None
                out.append(c)
        elif state == 'block':
            if c == '*' and i + 1 < n and s[i + 1] == '/':
                state = None
                i += 1
        i += 1
    return ''.join(out)


def body_of(code, sig):
    """按「方法签名 → 花括号配对」抽方法体（sig 是方法声明里的唯一片段）。"""
    i = code.find(sig)
    if i < 0:
        return None
    j = code.find('{', i)
    if j < 0:
        return None
    depth = 0
    k = j
    while k < len(code):
        if code[k] == '{':
            depth += 1
        elif code[k] == '}':
            depth -= 1
            if depth == 0:
                return code[j:k + 1]
        k += 1
    return None


CACHE = strip_comments(rd('data/SubtitleCache.java'))
ABTN = strip_comments(rd('hook/ActivityButtonHook.java'))
ZPF = strip_comments(rd('hook/ZiptreePrefetch.java'))
SVH = strip_comments(rd('hook/SubtitleViewHook.java'))
PPH = strip_comments(rd('hook/PlayerPositionHook.java'))
MOD = strip_comments(rd('DlsiteSoundSubtitleModule.java'))
GRADLE = rd(os.path.join(ROOT, 'app', 'build.gradle'), base=ROOT)
RUNALL = rd('run_all_verify.py', base=HERE)
V998 = rd('verify_998.py', base=HERE)

print('=' * 74)
print('A 日志降噪')
print('=' * 74)

# A1：log() 体内**不得**再有常开出口（这就是「双写」的病根）
b = body_of(CACHE, 'private static void log(String msg)')
check('A1 SubtitleCache.log() 已无双写（体内无 XposedCompat.log）',
      bool(b) and 'XposedCompat.log' not in b and 'LogGate.debug' in b,
      '体长 %d' % (len(b) if b else -1))

# A2：新增 logWarn 走常开
bw = body_of(CACHE, 'private static void logWarn(String msg)')
check('A2 SubtitleCache.logWarn() 存在且走常开出口',
      bool(bw) and 'XposedCompat.log' in bw)

# A3：常开出口只剩 logWarn 这一处
n_keep = CACHE.count('XposedCompat.log(')
check('A3 SubtitleCache 常开出口只剩 1 处（logWarn 内）', n_keep == 1, '实际 %d 处' % n_keep)

# A4：12 个告警点确实改走 logWarn
n_warn_call = len(re.findall(r'\blogWarn\(', CACHE)) - 1   # 减掉定义本身
check('A4 告警 / 里程碑调用点 ≥ 12 个走 logWarn', n_warn_call >= 12, '实际 %d 个' % n_warn_call)

# A5：ActivityButtonHook 生命周期两行 → 调试
check('A5a 生命周期两行改走 LogGate.debug',
      'LogGate.debug(TAG, " activity onResume -> ensureButton")' in ABTN
      and 'LogGate.debug(TAG, " activity onPause -> removeButton")' in ABTN)
check('A5b 生命周期行不再有常开出口',
      'XposedCompat.log(TAG + " activity on' not in ABTN)

# A6：ZiptreePrefetch 命中判定四行 → 调试，告警仍常开
# 【11-03 追认】1039 把 AMBIGUOUS 一行拆成 REFUSE/INFER 两条（受限推断），计数钉随现形：
#   HIT=1（take）/ MISS=2（take+find）/ REFUSE=2（全局负证据 + 歧义放弃）/ INFER=1（唯一键推断）。
check('A6a HIT/MISS/REFUSE/INFER 全走 LogGate.debug（1039 起 AMBIGUOUS 拆成 REFUSE/INFER）',
      ZPF.count('LogGate.debug(TAG, " HIT') == 1
      and ZPF.count('LogGate.debug(TAG, " MISS') == 2
      and ZPF.count('LogGate.debug(TAG, " REFUSE') == 2
      and ZPF.count('LogGate.debug(TAG, " INFER') == 1,
      'HIT=%d MISS=%d REFUSE=%d INFER=%d' % (ZPF.count('LogGate.debug(TAG, " HIT'),
                                              ZPF.count('LogGate.debug(TAG, " MISS'),
                                              ZPF.count('LogGate.debug(TAG, " REFUSE'),
                                              ZPF.count('LogGate.debug(TAG, " INFER')))
# ⚠️ 「dl fail」在剥注释后有 3 处（http / empty / 前缀共用），旧写法要求 >=3 时
#   把 `TAG + " dl fail http="` 与 `" dl fail empty "` 两条串按出现次数算错 —— 这里数
#   **声明位置**：只要它们还挂在 XposedCompat.log 那一侧即可。
check('A6b 下载失败告警仍在常开侧',
      len(re.findall(r'XposedCompat\.log\(TAG \+ " dl fail', ZPF)) >= 2
      and 'XposedCompat.log(TAG + " dl error' in ZPF)

# A7：tag dump → 调试
check('A7 SubtitleViewHook tag dump 改走 LogGate.debug',
      'LogGate.debug(TAG, " [code 1010] tag dump' in SVH
      and 'XposedCompat.log(TAG + " [code 1010] tag dump' not in SVH)

# A8：poll tick 写法统一（行为不变）
check('A8 PlayerPositionHook poll tick 统一走 LogGate.debug',
      'LogGate.debug(TAG, " poll tick #' in PPH
      and 'XposedCompat.log(TAG + " poll tick #' not in PPH)

# A9：常开侧的关键锚一个没丢
anchors = [
    # ⚠️ `>>> track changed` 在 **PlayerSourceHook**（本轮第一版锚点写错文件 ⇒ 假 FAIL）
    ('PlayerSourceHook', 'hook/PlayerSourceHook.java', '>>> track changed'),
    ('SubtitleRepository', 'data/SubtitleRepository.java', 'track decision:'),
    ('ActivityButtonHook', 'hook/ActivityButtonHook.java', 'button shown (player page)'),
    ('ActivityButtonHook', 'hook/ActivityButtonHook.java', 'capsule group hidden'),
    ('HostLineSync', 'hook/HostLineSync.java', 'MISMATCH'),
]
lost = []
for label, rel, token in anchors:
    src = strip_comments(rd(rel))
    # 只要求「该 token 仍出现在某个常开调用里」
    hit = False
    for m in re.finditer(r'XposedCompat\.log\((.*?)\);', src, re.S):
        if token in m.group(1):
            hit = True
            break
    if not hit:
        lost.append('%s/%s' % (label, token))
check('A9 常开侧取证锚全部仍在（换轨 / 裁决 / 显隐 / 行一致）', not lost, '丢失: %s' % (lost or '无'))

print()
print('=' * 74)
print('B 验证链')
print('=' * 74)

CACHE_FILES = ['verify_1018.py', 'verify_1019.py', 'verify_1020.py', 'verify_1021.py']
DEXTMP_FILES = ['verify_994.py', 'verify_995.py', 'verify_1018.py', 'verify_1019.py',
                'verify_1020.py', 'verify_1021.py', 'verify_1029.py', 'verify_1030.py']

miss_sent = [f for f in CACHE_FILES
             if '#DUMPCOMPLETE' not in rd(f, base=HERE) or '_dump_cache_ok' not in rd(f, base=HERE)]
check('B1 四个落盘缓存脚本都有完整性哨兵', not miss_sent, '缺: %s' % (miss_sent or '无'))

miss_tmp = [f for f in DEXTMP_FILES if '_dextmp' not in rd(f, base=HERE)]
check('B2 八个脚本的临时 dex 都改落 app/build/_dextmp', not miss_tmp, '缺: %s' % (miss_tmp or '无'))

leftover = []
for f in ('verify_1018.py', 'verify_1019.py', 'verify_1020.py', 'verify_1021.py',
          'verify_994.py', 'verify_995.py'):
    src = rd(f, base=HERE)
    if re.search(r'_rm\(tmp\)', src) or re.search(r'os\.remove\(tmp\)', src):
        leftover.append(f)
check('B3 旧「逐个删临时 dex」的删除点已绝迹', not leftover, '残留: %s' % (leftover or '无'))

check('B4 run_all 支持 latest（主验位取最大 code）',
      "'latest'" in RUNALL and 'max(cands)' in RUNALL)
check('B5 run_all 的 ENVBLOCK 说明仍在（没把环境问题伪装成通过）',
      'ENV_BLOCK_MARKER' in RUNALL and 'ENVBLOCK' in RUNALL)
check('B6 verify_998 已注明「998 包归档不可得」的口径',
      '998 包已归档不可得' in V998)

print()
print('=' * 74)
print('C 版本号 / 横幅 / 履历段')
print('=' * 74)

m_code = re.search(r'def appVersionCode = (\d+)', GRADLE)
# 【11-03 泛化】原钉 `== '1037'` —— 版本每轮必涨 ⇒ 每轮假 FAIL（铁律 82）。改**下界**。
check('C1 appVersionCode >= 1037（下界，不再钉死当轮值）',
      bool(m_code) and int(m_code.group(1)) >= 1037,
      '实际 %s' % (m_code.group(1) if m_code else '缺失'))
m_tag = re.search(r"def appVersionTag\s*=\s*'([^']+)'", GRADLE)
m_nam = re.search(r"def appVersionName\s*=\s*'([^']+)'", GRADLE)
# 【11-03 泛化】原钉 `== '2.4.0'` —— 同上。保留两条恒成立不变量：
#   ① tag == name（APK 文件名与包内版本一致，最易漏）；② name 不低于本轮 2.4.0。
def _ver_ge(v, ref):
    try:
        return tuple(int(x) for x in v.split('.')) >= ref
    except ValueError:
        return False
check('C2 tag == name 且 versionName >= 2.4.0（APK 文件名与包内版本一致，下界）',
      bool(m_tag) and bool(m_nam) and m_tag.group(1) == m_nam.group(1)
      and _ver_ge(m_nam.group(1), (2, 4, 0)),
      'tag=%s name=%s' % (m_tag.group(1) if m_tag else '?', m_nam.group(1) if m_nam else '?'))
m_lab = re.search(r"def appVersionCodeLabel = '(\d{4}\.\d+)'", GRADLE)
check('C3 label 形态 MMDD.N（只守形态，不钉当天）', bool(m_lab),
      '实际 %s' % (m_lab.group(1) if m_lab else '缺失'))

banners = re.findall(
    r'XposedCompat\.log\("\[DLsiteSoundFloat\] ==== BUILD ([\d.]+) / code (\d+)"\);', MOD)
# 【11-03 泛化】原钉 `== ('2.4.0', '1037')` —— 每轮必假 FAIL。改两条恒成立不变量：
#   ① 横幅自报 == 构建配置（versionName / versionCode 同源）；② code 下界 1037。
check('C4 常开横幅唯一且自报 == 构建配置、code >= 1037',
      len(banners) == 1 and bool(m_code) and bool(m_nam)
      and banners[0] == (m_nam.group(1), m_code.group(1))
      and int(m_code.group(1)) >= 1037,
      '实际 %r 配置 %s/%s' % (banners, m_nam.group(1) if m_nam else '?',
                          m_code.group(1) if m_code else '?'))

hist_m = re.search(r'LogGate\.debug\("\[DLsiteSoundFloat\] ==== BUILD 2\.4\.0 / code 1037 '
                   r'（(.*?)"\);', MOD, re.S)
hist = hist_m.group(1) if hist_m else ''
check('C5 履历段存在且自报 code 1037', bool(hist) and '【code 1037' in hist)
check('C6 履历段收尾句合规（版本号 + code 双升模板）',
      '版本号 2.3.5 升 2.4.0、code 1036 升 1037。' in hist)
check('C7 履历段无引号 / 反斜杠 / 反引号（防空 / 负向探针自命中）',
      not any(c in hist for c in '"\\`'))
check('C8 本轮三条主线都在履历段里（验证链 / 日志降噪）',
      'dump' in hist and '日志' in hist)

print()
print('=' * 74)
print('D 边界')
print('=' * 74)

LAYOUT = rd(os.path.join(ROOT, 'app', 'src', 'main', 'res', 'layout',
                         'activity_settings.xml'), base=ROOT)
check('D1 设置页布局未动（页签容器仍在 → 本轮零资源改动）',
      'appearance_tabs' in LAYOUT)
check('D2 LogGate 的口径注释仍在（判据写在代码旁边，不只在提交信息里）',
      '里程碑 / 告警' in rd('util/LogGate.java'))
check('D3 ZiptreePrefetch 已 import LogGate（否则编译不过——这里守的是「别删了 import」）',
      'import io.github.ariinyume.dlsitesoundfloat.util.LogGate;' in rd('hook/ZiptreePrefetch.java'))
check('D4 SubtitleCache 仍 import LogGate 与 XposedCompat（两条路都要）',
      'import io.github.ariinyume.dlsitesoundfloat.util.LogGate;' in rd('data/SubtitleCache.java')
      and 'XposedCompat' in rd('data/SubtitleCache.java'))
# 常开调用点总量上界：本轮降噪后应低于 1036 轮（实测 1036 = 202）
import glob
n_open = 0
for p in glob.glob(os.path.join(JAVA, '**', '*.java'), recursive=True):
    src = strip_comments(io.open(p, 'r', encoding='utf-8', errors='replace',
                                 newline='').read().replace('\r\n', '\n'))
    n_open += src.count('XposedCompat.log(')
# 【11-03 追认】1036→1037 降噪把 202 压到 197，此后 1038~1047 又合法涨回 201。
#   阈值随实测挪（总量受控的回归网，不是死数）：钉 ≤ 201，再涨必须由当轮自觉改这里。
check('D5 常开调用点总量 ≤ 201（1037 降噪后 197，1047 实测 201；再涨须当轮追认）',
      n_open <= 201, '实际 %d 处' % n_open)

print()
print('=' * 74)
if fails:
    print('FAIL %d/%d' % (len(fails), total))
    for f in fails:
        print('  - %s' % f)
    sys.exit(1)
print('PASS %d/%d' % (total, total))
sys.exit(0)
