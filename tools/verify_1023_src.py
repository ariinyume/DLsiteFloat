#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1023 / v2.3.5】真机回归三修 + P0-4 落地的**源码层**验证。
（读的是**活的工作区** ⇒ 版本号判下界、判据只守结构与接线，不钉字面量；见铁律 82/⑬）

本轮五件事（依据 Ari 2026-10-18 21:21 真机日志包 + 五份 ziptree + 设置页截图）
--------------------------------------------------------------------------
① P0-1 修：宿主版本不显示（读错进程 + 清单漏包可见性），并搬进状态卡
② P0-3 修：键体检必然误报（六键合并表套在两种 Map 形状上）
③ P0-2 复核：六条链路均在跑（本轮只补一项预取自检）
④ P0-4 结论：可行 —— 作品文件树自带字幕文件名、签名是目录级通配
⑤ P0-4 落地：ZiptreePrefetch 预取 + 离线换轨时长兜底

验什么
------
A 新文件：ZiptreePrefetch 的解析/下载/索引/取值四条骨架齐全（不是空壳）。
B 接线：清单 queries、NetworkHook 触发、Repository 两处兜底、状态卡第二行。
C 修复点：宿主版本走「本进程读」入口；旧卡片行已删；键体检只认列表形状。
D 文案/自检：预取自检项存在；离线文案仍在（不许回退掉）。
E 边界：本轮**不动**的三处（抓取闸门形状 / 换轨判据 / 缓存索引结构版本）。
F 版本 / 横幅 / 履历纪律。

用法
----
    python verify_1023_src.py [src_root]
退出码 0 = 全部通过
"""

import os
import re
import sys

SRC = None
fails = []
total = 0


def check(name, ok, detail=''):
    global total
    total += 1
    if ok:
        print('  PASS  %s' % name)
    else:
        print('  FAIL  %s   %s' % (name, detail))
        fails.append(name)


def read(p):
    """读源码：先归一化行尾（铁律 58/106：工作区可能被 autocrlf 改成 CRLF）。"""
    with open(p, 'rb') as f:
        return f.read().decode('utf-8', 'replace').replace('\r\n', '\n')


def has(text, needle):
    return needle in text


def strip_comments(text):
    """去掉 // 与 /* */ 注释。判「代码里有」时用它；判「注释里有」必须读原文（铁律 87①）。"""
    out = []
    i = 0
    n = len(text)
    in_line = False
    in_block = False
    in_str = False
    quote = ''
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ''
        if in_line:
            if c == '\n':
                in_line = False
                out.append(c)
            i += 1
            continue
        if in_block:
            if c == '*' and nxt == '/':
                in_block = False
                i += 2
                continue
            if c == '\n':
                out.append(c)
            i += 1
            continue
        if in_str:
            out.append(c)
            if c == '\\':
                if i + 1 < n:
                    out.append(text[i + 1])
                i += 2
                continue
            if c == quote:
                in_str = False
            i += 1
            continue
        if c == '/' and nxt == '/':
            in_line = True
            i += 2
            continue
        if c == '/' and nxt == '*':
            in_block = True
            i += 2
            continue
        if c in ('"', "'"):
            in_str = True
            quote = c
            out.append(c)
            i += 1
            continue
        out.append(c)
        i += 1
    return ''.join(out)


def main():
    global SRC
    SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'src', 'main')
    java = os.path.join(SRC, 'java', 'io', 'github', 'ariinyume', 'dlsitesoundfloat')

    def jp(rel):
        return os.path.join(java, rel)

    print('源根：%s\n' % SRC)

    prefetch = read(jp('hook/ZiptreePrefetch.java'))
    hostinfo = read(jp('util/HostInfo.java'))
    network = read(jp('hook/NetworkHook.java'))
    repo = read(jp('data/SubtitleRepository.java'))
    settings = read(jp('ui/SettingsActivity.java'))
    position = read(jp('hook/PlayerPositionHook.java'))
    health = read(jp('hook/AdapterHealth.java'))
    strings = read(jp('ui/Strings.java'))
    manifest = read(os.path.join(SRC, 'AndroidManifest.xml'))
    gradle = read(os.path.join(os.path.dirname(SRC), '..', 'build.gradle'))
    module = read(jp('DlsiteSoundSubtitleModule.java'))

    # ---------- A 新文件骨架 ----------
    print('A 预取器骨架（ZiptreePrefetch）')
    check('类存在且为 final', re.search(r'public final class ZiptreePrefetch', prefetch) is not None)
    check('入口 offer()', re.search(r'public static void offer\(String url, String text\)',
                                     prefetch) is not None)
    check('出口 take(long)', re.search(r'public static Hit take\(long durMs\)', prefetch) is not None)
    check('解析 parseTracks()', re.search(r'private static List<Track> parseTracks', prefetch) is not None)
    check('下载 download(Pack, Track)', re.search(r'private static void download\(final Pack', prefetch) is not None)
    check('索引 writeIndex(Pack)', re.search(r'private static void writeIndex\(Pack', prefetch) is not None)
    check('索引回读 readIndex(File)', re.search(r'private static Pack readIndex\(File', prefetch) is not None)
    check('启动时加载索引 ensureIndexLoaded()',
          re.search(r'private static void ensureIndexLoaded\(\)', prefetch) is not None)
    check('结果载体 Hit 三字段（正文/作品键/时长）',
          all(re.search(r'public final %s' % t, prefetch) for t in ('String text', 'String workKey', 'long durMs')))
    check('离线不发起（NetState）', has(prefetch, 'NetState.isOffline()'))
    check('单线程后台队列（不拖主链路）', has(prefetch, 'newSingleThreadExecutor'))
    check('有作品数上限常量', re.search(r'MAX_WORKS\s*=\s*\d+', prefetch) is not None)
    check('有单作品字节上限常量', re.search(r'MAX_BYTES_PER_WORK\s*=', prefetch) is not None)

    print('A2 解析口径（必须读 audio.vtt 而不是猜哈希）')
    check('读 audio 子对象', has(prefetch, 'entry.optJSONObject("audio")'))
    check('读 audio.vtt 字段', has(prefetch, 'audio.optString("vtt", "")'))
    check('读 vtt.optimized.name', has(prefetch, 'optimized.optString("name", "")'))
    check('读 audio.optimized.duration', has(prefetch, 'audioOpt.optDouble("duration"'))
    check('不出现「算 md5」的投机写法（无 MessageDigest）', not has(prefetch, 'MessageDigest'))
    check('无活动网络时直接放弃（省流量）', re.search(r'if \(NetState\.isOffline\(\)\)', prefetch) is not None)

    # ---------- B 接线 ----------
    print('B 接线')
    check('清单有 <queries>', '<queries>' in manifest)
    check('清单声明宿主包可见', 'android:name="jp.co.eisys.dlsitesound"' in manifest)
    # ⚠️ 只判**真的声明**，不判注释里出现过这个词（本轮清单注释正在解释「不要用它」）
    check('清单没有 QUERY_ALL_PACKAGES 宽口子',
          'android.permission.QUERY_ALL_PACKAGES' not in strip_comments(manifest))
    check('NetworkHook 触发预取', 'ZiptreePrefetch.offer(url, text)' in network)
    check('NetworkHook 用 isZiptree 判定（不是模糊 contains）',
          'ZiptreePrefetch.isZiptree(urlLc)' in network)
    check('Repository 换轨离线兜底接上',
          re.search(r'tryResumeFromDisk\(where, newIdentity, newSelection\)\s*\n\s*\|\|\s*tryResumeFromPrefetch', repo) is not None)
    check('Repository 首轨冷启动兜底接上',
          re.search(r'tryResumeFromDisk\(where \+ " \[seeded idx=".*?tryResumeFromPrefetch', repo, re.S) is not None)
    check('兜底方法本体存在', re.search(r'private boolean tryResumeFromPrefetch', repo) is not None)
    check('兜底走正常加载路径（会自己落盘）',
          'loadFromJson(hit.text, hit.workKey, false)' in repo)
    check('状态卡第二行接了宿主版本', 'hostLineText()' in settings)

    # ---------- C 修复点 ----------
    print('C P0-1 / P0-3 修复点')
    check('HostInfo 有「本进程读」入口',
          re.search(r'public static Info readInCurrentProcess\(Context ctx, String hostPkg\)', hostinfo) is not None)
    check('HostInfo 有不可变快照类型 Info', re.search(r'public static final class Info', hostinfo) is not None)
    check('Info 有 known() 判定（读不到不许显示成数字）',
          re.search(r'public boolean known\(\)', hostinfo) is not None)
    check('设置页不再有旧的卡片行方法', 'private void buildHostVersionRow' not in settings)
    check('设置页不再调用 buildHostVersionRow',
          re.search(r'^\s*buildHostVersionRow\(', settings, re.M) is None)
    check('状态卡副标题是两行（模块版本 + 宿主版本）',
          re.search(r'BuildConfig\.VERSION_CODE, sysUiText\)\s*\n\s*\+ "\\n" \+ hostLineText\(\)', settings) is not None)
    check('三语新增 HOST_LINE 文案', re.search(r'HOST_LINE\(', strings) is not None)
    check('文案表仍是三语三元组（HOST_LINE 那行有三个参数）',
          re.search(r'HOST_LINE\("[^"]*%1\$s[^"]*",\s*"[^"]*",\s*"[^"]*"\)', strings) is not None)

    check('键体检只认列表形状（带 trackCount）',
          re.search(r'!sKeysChecked && m\.get\("trackCount"\) instanceof Number', position) is not None)
    m_keys = re.search(r'private static final String\[\] WANT_KEYS = \{(.*?)\};', position, re.S)
    check('必备键表存在', m_keys is not None)
    if m_keys:
        body = m_keys.group(1)
        check('必备键含 trackCount', '"trackCount"' in body)
        check('必备键含 currentIndex', '"currentIndex"' in body)
        check('必备键不再含单播放器独有的 playing（1022 误报源）',
              '"playing"' not in body)
    check('体检注释点名了两种形状（可追溯根因）', 'AudioPlayer' in position and 'AudioPlaylist' in position)

    # ---------- D 自检项与文案 ----------
    print('D 自检项与离线文案')
    check('AdapterHealth 有预取项 PREFETCH', re.search(r'^\s*PREFETCH\b', health, re.M) is not None)
    check('预取器会上报自检态', 'AdapterHealth.Item.PREFETCH' in prefetch)
    check('摘要分母是动态的（不写死 6）',
          re.search(r'Item\.values\(\)\.length', health) is not None)
    i18n = read(jp('util/I18n.java'))
    check('离线无缓存文案仍在（不许回退掉）', 'offlineNoCache' in i18n or 'offlineNoCache' in prefetch)
    check('离线占位文案仍在（悬浮窗那句）', 'offlineNoCacheHint' in i18n)

    # ---------- E 边界 ----------
    print('E 本轮不动的边界')
    cache = read(jp('data/SubtitleCache.java'))
    check('缓存索引结构版本仍是 4（本轮不清毒）',
          re.search(r'INDEX_SCHEMA = 4;', cache) is not None)
    check('抓取闸门的三层判据没被改（体积/媒体类型/媒体后缀）',
          all(has(network, k) for k in ('MEDIA_CT_HINTS', 'MEDIA_EXT_HINTS', 'peekLimit')))
    check('换轨判据仍用三元组身份（makeIdentity 仍在）',
          'PlaylistKey.makeIdentity' in cache or 'makeIdentity' in repo)
    # ⚠️ 必须先剥注释：类头正在解释「为什么不在这里写 SubtitleCache」（铁律 87①）
    check('预取器不写缓存（只交原文，落盘交给数据层）',
          'SubtitleCache' not in strip_comments(prefetch))

    # ---------- F 版本 / 横幅 / 履历 ----------
    print('F 版本 / 横幅 / 履历纪律')
    m_name = re.search(r"def appVersionName = '([0-9.]+)'", gradle)
    m_tag = re.search(r"def appVersionTag = '([0-9.]+)'", gradle)
    m_code = re.search(r'def appVersionCode = (\d+)', gradle)
    m_label = re.search(r"def appVersionCodeLabel = '(\d{4}\.\d+)'", gradle)
    check('versionName 存在', m_name is not None)
    check('versionCode >= 1023（本轮判据放下界，防后面轮次假 FAIL）',
          m_code is not None and int(m_code.group(1)) >= 1023,
          m_code.group(1) if m_code else 'missing')
    check('tag == name（APK 文件名由 tag 决定，最易漏）',
          bool(m_name and m_tag) and m_name.group(1) == m_tag.group(1),
          '%s vs %s' % (m_tag.group(1) if m_tag else '?', m_name.group(1) if m_name else '?'))
    check('label 形态 MMDD.N（构建当天，不钉日期）', m_label is not None)

    # ⚠️ 只数**常开行**：每轮有两条同版本串（常开里程碑 + debug 详细段），
    #    数所有会恒定得 2（上一轮踩过，见 1022 脚本注释）。
    banners = re.findall(
        r'XposedCompat\.log\("\[DLsiteSoundFloat\] ==== BUILD ([0-9.]+) / code (\d+)"\)',
        module)
    check('横幅至少一条', bool(banners))
    if banners:
        check('横幅首条 == gradle（name / code）',
              banners[0][0] == m_name.group(1) and int(banners[0][1]) == int(m_code.group(1)),
              'banner=%s/%s gradle=%s/%s' % (banners[0][0], banners[0][1],
                                             m_name.group(1), m_code.group(1)))
        check('本轮 code 在**常开行**里恰好一条',
              banners.count((m_name.group(1), m_code.group(1))) == 1,
              'occurrences=%d' % banners.count((m_name.group(1), m_code.group(1))))
        prev_name = next((n for n, _ in banners if n != m_name.group(1)), None)
        check('履历段收尾句合模板（版本号 X 升 Y、code A 升 B）',
              prev_name is not None and re.search(
                  r'版本号 %s 升 %s、code \d+ 升 \d+。' % (
                      re.escape(prev_name), re.escape(m_name.group(1))), module) is not None,
              'prev=%s' % prev_name)

    print()
    print('总计 %d 条，通过 %d 条，失败 %d 条' % (total, total - len(fails), len(fails)))
    if fails:
        print('失败项：')
        for x in fails:
            print('  - %s' % x)
        return 1
    print('verify_1023_src: ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
