#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1042 / v2.4.1（只升 code）】「离线读到别人音轨字幕」的**源码层**验证。

两个口子：① 磁盘缓存绕过时长歧义判定；② 印章时长取自会漂移的活值。
判据（24 项）见下面 A~H 各组。

用法
----
    python tools/verify_1042_src.py
退出码 0 = 全部通过
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'app', 'src', 'main', 'java', 'io', 'github',
                   'ariinyume', 'dlsitesoundfloat')
REPO = os.path.join(SRC, 'data', 'SubtitleRepository.java')
CACHE = os.path.join(SRC, 'data', 'SubtitleCache.java')
PKEY = os.path.join(SRC, 'data', 'PlaylistKey.java')
PRE = os.path.join(SRC, 'hook', 'ZiptreePrefetch.java')
MODULE = os.path.join(SRC, 'DlsiteSoundSubtitleModule.java')
GRADLE = os.path.join(ROOT, 'app', 'build.gradle')
GOLDEN = os.path.join(ROOT, 'app', 'src', 'test', 'java', 'io', 'github',
                      'ariinyume', 'dlsitesoundfloat', 'GoldenVectorTest.java')
RUNALL = os.path.join(ROOT, 'tools', 'run_all_verify.py')
CHANGELOG = os.path.join(ROOT, 'CHANGELOG.md')

fails = []
total = 0


def check(name, ok, detail=''):
    global total
    total += 1
    print('  %s %s%s' % ('OK  ' if ok else 'FAIL', name,
                         ('   ' + detail) if detail else ''))
    if not ok:
        fails.append(name)


def read(p):
    with open(p, encoding='utf-8', errors='replace') as f:
        return f.read()


for p in (REPO, CACHE, PKEY, PRE, MODULE, GRADLE, GOLDEN, RUNALL, CHANGELOG):
    if not os.path.isfile(p):
        print('缺少文件: %s' % p)
        sys.exit(2)

repo, cache, pkey = read(REPO), read(CACHE), read(PKEY)
pre, module = read(PRE), read(MODULE)
gradle, golden = read(GRADLE), read(GOLDEN)
runall, changelog = read(RUNALL), read(CHANGELOG)

# ── A 版本号 ────────────────────────────────────────────────────
print('=== A. 版本号（只升 code）===')
_m = re.search(r'^def appVersionCode\s*=\s*(\d+)\s*$', gradle, re.M)
check('A1 appVersionCode >= 1042（下界口径）',
      _m is not None and int(_m.group(1)) >= 1042,
      ('实际 ' + _m.group(1)) if _m else '未找到')
_vn = re.search(r"^def appVersionName\s*=\s*'([\d.]+)'\s*$", gradle, re.M)
check('A2 appVersionName 形态 x.y.z（不钉死具体版本）',
      _vn is not None, ('实际 ' + _vn.group(1)) if _vn else '未找到')
_vt = re.search(r"^def appVersionTag\s*=\s*'([\d.]+)'\s*$", gradle, re.M)
check('A3 appVersionTag 与 appVersionName 一致（tag 进文件名）',
      _vt is not None and _vn is not None and _vt.group(1) == _vn.group(1),
      ('tag=%s name=%s' % (_vt.group(1) if _vt else '?', _vn.group(1) if _vn else '?')))
check('A4 label 形态 MMDD.N（只守形态）',
      re.search(r"^def appVersionCodeLabel\s*=\s*'\d{4}\.\d+'\s*$", gradle, re.M) is not None)

# ── B 缓存时长闸门 ──────────────────────────────────────────────
print('=== B. 磁盘缓存时长闸门（与预取池同尺子）===')
check('B1 ZiptreePrefetch.cacheGateAllows 存在',
      re.search(r'static boolean cacheGateAllows\s*\(\s*long durMs\s*\)', pre) is not None)
check('B2 闸门里有「等长无字幕轨」负证据',
      'hasAnyNoSubtitle(snapshot, durMs)' in
      pre.split('cacheGateAllows', 1)[-1].split('public static int works', 1)[0])
check('B3 闸门里有「跨 ≥2 作品」歧义判定',
      'keys.size() >= 2' in pre)
check('B4 池子为空时放行（不能反向封死缓存）',
      'snapshot.isEmpty()' in pre and 'return true;' in pre)
check('B5 tryResumeFromDisk 调用闸门',
      'cacheGateAllows(durMs)' in repo)
check('B6 hasDiskCacheFor 同口径（grace 分级一致）',
      'cacheGateAllows(PlaylistKey.identityDurationMs(identity))' in repo)
check('B7 本地缓存可用性读数同口径（状态卡不撒谎）',
      'cacheGateAllows(PlaylistKey.identityDurationMs(identity))' in
      repo.split('refreshLocalCacheAvailability', 1)[-1])

# ── C 印章时长锚定 ──────────────────────────────────────────────
print('=== C. 印章时长锚定 ===')
check('C1 PlaylistKey.stampForLoadedJson 存在（纯函数）',
      re.search(r'public static long stampForLoadedJson\s*\(', pkey) is not None)
check('C2 时长超容差 ⇒ 返回 0（作废印章）',
      'return 0L;' in pkey.split('stampForLoadedJson', 1)[-1].split('public static long makeIdentity', 1)[0])
check('C3 Repository 印章赋值走锚定函数',
      'cuesOwnerIdentity = stampIdentityForLoadedJson(observedPlaylistIdentity, durMsHint)'
      in repo)
check('C4 不再直接 `cuesOwnerIdentity = observedPlaylistIdentity`',
      'cuesOwnerIdentity = observedPlaylistIdentity;' not in repo)
check('C5 作废时打日志（可取证）',
      'stamp VOIDED' in repo)

# ── D 时长贯通 ──────────────────────────────────────────────────
print('=== D. 「这份 JSON 自己的时长」贯通两条兜底路径 ===')
check('D1 loadFromJson 四参重载存在（带 durMsHint）',
      'loadFromJson(String json, String workKey, boolean fromDisk, long durMsHint)'
      in repo)
check('D2 三参重载仍保留（云端/字节流路径零改动）',
      'loadFromJson(String json, String workKey, boolean fromDisk) {' in repo)
check('D3 loadFromJsonArrayInternal 收 durMsHint',
      'loadFromJsonArrayInternal(JSONArray webvtt, String workKey, boolean fromDisk,'
      in repo and 'long durMsHint)' in repo)
check('D4 磁盘命中路径传 durMs',
      'loadFromJson(text, null, true, durMs)' in repo)
check('D5 预取命中路径传 durMs',
      'loadFromJson(hit.text, hit.workKey, false, durMs)' in repo)

# ── E 索引 ──────────────────────────────────────────────────────
print('=== E. 索引口径（定向清理，不清空缓存）===')
check('E1 INDEX_SCHEMA = 5',
      re.search(r'INDEX_SCHEMA\s*=\s*5\s*;', cache) is not None)
check('E2 4→5 走迁移分支（不整批丢弃）',
      'migrateFrom4 = true' in cache
      and re.search(r'foundSchema == 4 && INDEX_SCHEMA == 5', cache) is not None)
check('E3 整批丢弃只剩一个调用点（4→5 不再走它）',
      cache.count('discardIndexAndSweepLocked();') == 1)
check('E4 purgeMislabelledLocked 存在（只清错标条目）',
      'private int purgeMislabelledLocked()' in cache)
check('E5 迁移后落盘（schema 写成 5，下次不再迁移）',
      re.search(r'if \(migrateFrom4\) \{[\s\S]{0,400}?persistIndexLocked\(\);', cache)
      is not None)
check('E6 「判不了就一条不动」的保守分支在位',
      'purge skipped: same content under work but labels not judgeable' in cache)
check('E7 挑留哪条的算式在 PlaylistKey（纯函数、进单测）',
      re.search(r'public static int pickBestLabelMatch\s*\(', pkey) is not None)
check('E8 SubtitleCache 委托它（不写第二份实现）',
      'PlaylistKey.pickBestLabelMatch(maxEnds, durs)' in cache)

# ── F 单元测试 ──────────────────────────────────────────────────
print('=== F. 单元测试 ===')
check('F1 GoldenVectorTest 有 stampForLoadedJson 向量',
      'stampForLoadedJson_anchorsOnJsonOwnDuration' in golden)
check('F2 向量里覆盖「对不上 ⇒ 0」',
      '时长对不上 ⇒ 印章必须作废' in golden)
check('F3 定向清理挑留哪条也有向量',
      'pickBestLabelMatch_keepsTheMatchingSlot' in golden)

# ── G 横幅与履历 ────────────────────────────────────────────────
print('=== G. 横幅 / 履历纪律 ===')
_bn = re.search(r'XposedCompat\.log\("\[DLsiteSoundFloat\] ==== BUILD ([\d.]+) / code (\d+)"\)',
                module)
check('G1 常开横幅 code >= 1042 且版本名与 build.gradle 一致',
      _bn is not None and int(_bn.group(2)) >= 1042
      and _vn is not None and _bn.group(1) == _vn.group(1),
      ('banner=%s code=%s' % (_bn.group(1), _bn.group(2))) if _bn else '未找到')
_h = module.split('code 1042 （', 1)
check('G2 1042 履历段存在', len(_h) == 2)
if len(_h) == 2:
    seg = _h[1].split('");', 1)[0]
    check('G3 履历九段齐全（①~⑨）',
          all(('①②③④⑤⑥⑦⑧⑨'[i] in seg) for i in range(9)))
    check('G4 收尾句落在段末（版本号 X 升/不变 [Y]、code A 升 B。）',
          re.search(r'版本号 \d+\.\d+\.\d+ (?:升|不变)(?: \d+\.\d+\.\d+)?'
                    r'、code \d+ 升 \d+。\s*$', seg) is not None,
          seg[-40:])
    check('G5 履历不点名内部标识符（防空锚自伤）',
          not any(w in seg for w in ('NO_SUBTITLE_GRACE_MS', 'provisionalEarlyClose',
                                     'resolvePendingTrack', 'tryResumeFromDisk',
                                     'hasDiskCacheFor', 'stampForLoadedJson')))

# ── H 注册与履历 ────────────────────────────────────────────────
print('=== H. 注册与 CHANGELOG ===')
check("H1 run_all 收录 verify_1042.py", "'verify_1042.py'" in runall)
check("H2 run_all 收录 verify_1042_src.py", "'verify_1042_src.py'" in runall)
check('H3 1042 排在 1041 之前（最新在上）',
      runall.find("'verify_1042.py'") >= 0
      and runall.find("'verify_1042.py'") < runall.find("'verify_1041.py'"))
check('H4 CHANGELOG 有 1042 条目', 'code 1041 → 1042' in changelog)

print()
print('=' * 74)
if fails:
    print('FAIL %d/%d' % (len(fails), total))
    for f in fails:
        print('  - %s' % f)
    sys.exit(1)
print('PASS %d/%d' % (total, total))
sys.exit(0)
