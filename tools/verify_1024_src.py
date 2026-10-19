#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1024 / v2.3.5】预取跑通（压缩正文就地解压）+ 作品维强约束 + 离线文案收口 + P1 三项
的 **源码层**验证。
（读的是**活的工作区** ⇒ 版本号判下界、判据只守结构与接线，不钉字面量；见铁律 82/⑬）

本轮六件事（依据 Ari 2026-10-18 22:28 真机日志包）
--------------------------------------------------
① 预取只跑一半的根因：peek 读到的是 okhttp **先构建的压缩态正文**（4143 B），
   按文本解成替换字符 ⇒ JSON 解析必炸。修法两层：网络层认出 gzip 魔数就地解压 +
   再判「像不像文本」；预取层加结构校验，不合格静默跳过（不算故障、不进自检表）。
② 缓存字幕补「作品维」强约束（磁盘缓存）：同一身份允许多条并存，命中时必须用作品键认人，
   认不出就放弃命中。
③ 预取池补「作品维」强约束：`take(durMs, workKeyHint)`，跨作品歧义放弃。
④ 离线/弱网文案回退到「无字幕」：上一版两句离线专用文案连同文案函数一并删除。
⑤ P1-5 观测：宿主上屏文本 vs 自算行的对比计数（只统计，不改渲染）。
⑥ P1-7 样式跟随宿主 + P1-8 命中率/预取读数（跨进程多带 7 个 extra，设置页两行读数）。

验什么
------
A gzip 根因的两层修法（网络层解压 + 文本判据 + 预取层结构校验）
B 磁盘缓存的桶化与认人（byIdentity / pickLocked / sameWork / 并条）
C 预取池的作品维（take 两参 / AMBIGUOUS 放弃 / hasDuration）
D 离线文案删除（剥注释后必须一处不剩）＋ 两处 UI 接线改回「无字幕」
E P1-5 / P1-7 / P1-8 的接线（含配置键七处、7 个 extra、设置页读数行）
F 边界：本轮**不动**的部分（索引结构版本仍 4、抓取闸门、换轨判据、预取器不写缓存）
G 版本 / 横幅唯一 / 履历纪律

用法
----
    python verify_1024_src.py [src_root]
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

    network = read(jp('hook/NetworkHook.java'))
    prefetch = read(jp('hook/ZiptreePrefetch.java'))
    cache = read(jp('data/SubtitleCache.java'))
    repo = read(jp('data/SubtitleRepository.java'))
    i18n = read(jp('util/I18n.java'))
    fview = read(jp('view/FloatingSubtitleView.java'))
    style = read(jp('view/SubtitleStyle.java'))
    abtn = read(jp('hook/ActivityButtonHook.java'))
    sync = read(jp('hook/HostLineSync.java'))
    viewhook = read(jp('hook/SubtitleViewHook.java'))
    config = read(jp('config/SubtitleConfig.java'))
    remote = read(jp('config/RemoteConfig.java'))
    protocol = read(jp('config/Protocol.java'))
    bus = read(jp('config/ConfigBus.java'))
    strings = read(jp('ui/Strings.java'))
    settings = read(jp('ui/SettingsActivity.java'))
    module = read(jp('DlsiteSoundSubtitleModule.java'))
    gradle = read(os.path.join(os.path.dirname(SRC), '..', 'build.gradle'))

    # ---------- A gzip 根因的两层修法 ----------
    print('A 预取只跑一半的根因（压缩正文）')
    check('引入了 GZIPInputStream', 'import java.util.zip.GZIPInputStream;' in network)
    check('引入了 ByteArrayInputStream', 'import java.io.ByteArrayInputStream;' in network)
    check('maybeGunzip 存在且返回 byte[]',
          re.search(r'private static byte\[\] maybeGunzip\(byte\[\] data, long limit\)', network) is not None)
    check('按 gzip 魔数识别（不是看响应头）',
          re.search(r'data\[0\] & 0xFF\) != 0x1F', network) is not None
          and re.search(r'data\[1\] & 0xFF\) != 0x8B', network) is not None)
    check('解压超限即放弃（防解压炸弹）',
          re.search(r'total > limit', network) is not None
          and 'gunzip dropped (inflated > limit=' in network)
    check('解压有常开里程碑日志（只打第一次）',
          'peek: gzip body inflated ' in network and 'sGunzipCount++ == 0' in network)
    check('半截 member 不抛给上层（catch 后返回 null）',
          re.search(r'catch \(Throwable e\) \{\s*\n\s*// 半截 gzip member', network) is not None)
    check('looksTextual 存在',
          re.search(r'private static boolean looksTextual\(byte\[\] data\)', network) is not None)
    check('文本判据只扫前 4KB（不做无谓全扫）',
          re.search(r'Math\.min\(data\.length, 4096\)', network) is not None)
    check('合法 UTF-8 首/续字节放行（0xF5..0xFF 才算坏）',
          re.search(r'if \(b <= 0xF4\)', network) is not None)
    check('二进制丢弃有一次性日志',
          'peek dropped: body looks binary (' in network and 'sNonTextDrops++ == 0' in network)
    check('peekText 走「先解压 → 再判文本 → 再解码」三步',
          re.search(r'byte\[\] plain = maybeGunzip\(data, limit\);.*?'
                    r'if \(!looksTextual\(plain\)\).*?'
                    r'return decodeUtf8\(plain, 0, plain\.length\);', network, re.S) is not None)
    check('peekText 里的局部变量没再叫 body（重名会编译失败）',
          re.search(r'byte\[\] body = maybeGunzip', network) is None)

    print('A2 预取层的结构校验（不合格静默跳过）')
    check('offer 开头有正文结构校验',
          re.search(r'String body = text\.trim\(\);\s*\n\s*'
                    r'if \(!body\.startsWith\("\{"\) \|\| !body\.contains\("\\"playfile\\""\)\)',
                    prefetch) is not None)
    check('结构校验**先于**离线判断（离线也不是「失败」）',
          prefetch.index('body.startsWith("{")') < prefetch.index('if (NetState.isOffline())'))
    check('结构校验只落一行日志、不记故障',
          'skip (not a complete ziptree: ' in prefetch and 'sBadBodyLogged' in prefetch)
    check('日志里点名了「等解压后的那一份」',
          'waiting for the inflated copy' in prefetch)

    # ---------- B 磁盘缓存的桶化与认人 ----------
    print('B 磁盘缓存的作品维强约束')
    check('byIdentity 改为「一身份多条目」',
          re.search(r'Map<Long, List<Entry>> byIdentity = new HashMap<>\(\);', cache) is not None)
    check('pickLocked 存在（认人逻辑收在一处）',
          re.search(r'private Entry pickLocked\(List<Entry> bucket, String currentWorkKey', cache) is not None)
    check('单条直取（不必认人）',
          re.search(r'if \(bucket\.size\(\) == 1\)', cache) is not None)
    check('按作品键认人', re.search(r'if \(currentWorkKey\.equals\(e\.workKey\)\)', cache) is not None)
    check('歧义时放弃命中并落日志',
          'hit REFUSED (ambiguous across works)' in cache)
    check('sameWork 存在（覆盖 / 并存的判据）',
          re.search(r'private static boolean sameWork\(Entry a, Entry b\)', cache) is not None)
    check('「都无作品键」退回同轨标签判等（数组入口没有 URL）',
          re.search(r'if \(an && bn\) \{\s*\n\s*return a\.tc == b\.tc && a\.idx == b\.idx;', cache) is not None)
    check('「一边有一边无」判不同作品（不悄悄删可能对的那条）',
          re.search(r'if \(an \|\| bn\) \{\s*\n\s*return false;', cache) is not None)
    check('全同作品时取最近使用（自己历史留下的同槽不算撞车）',
          'entries of the SAME work ->' in cache)
    check('写入时只摘同作品同身份的旧条目',
          cache.count('sameWork(') >= 4)
    check('跨作品并存有日志留证', 'identity shared by ' in cache)
    check('读索引时合并「同作品同身份」重复条目（防老缓存变假 MISS）',
          re.search(r'if \(dup != e && sameWork\(dup, e\)\)', cache) is not None)
    check('removeEntryLocked 从桶里摘（桶空才删键）',
          re.search(r'bucket\.remove\(e\)', cache) is not None)
    check('歧义时 has() 仍返回 true（保守方向写在注释里，口径不反）',
          re.search(r'public boolean has\(long identity, long selection\)', cache) is not None
          and re.search(r'【code 1024】[^\n]*例外', cache) is not None)

    # ---------- C 预取池的作品维 ----------
    print('C 预取池的作品维强约束')
    check('take 改为两参（时长 + 作品键提示）',
          re.search(r'public static Hit take\(long durMs, String workKeyHint\)', prefetch) is not None)
    check('旧的单参 take 已不存在',
          re.search(r'public static Hit take\(long durMs\)', prefetch) is None)
    check('先收集全部时长命中的作品', 'List<Pack> matched = new ArrayList<>(2);' in prefetch)
    check('作品键认人优先', re.search(r'if \(hinted != null\) \{\s*\n\s*pick = hinted;', prefetch) is not None)
    check('唯一候选可直接用', re.search(r'else if \(matched\.size\(\) == 1\)', prefetch) is not None)
    check('跨作品歧义 ⇒ 放弃命中并落日志',
          'AMBIGUOUS dur=' in prefetch and 'refuse hit' in prefetch)
    check('hasDuration 只看索引不碰磁盘',
          re.search(r'private static boolean hasDuration\(Pack p, long durMs\)', prefetch) is not None)
    check('命中日志标明是靠什么认到的（work-scoped / sole candidate）',
          '[work-scoped]' in prefetch and '[sole candidate]' in prefetch)
    check('works() / tracks() 读数出口存在',
          re.search(r'public static int works\(\)', prefetch) is not None
          and re.search(r'public static int tracks\(\)', prefetch) is not None)
    check('summary() 复用两个出口（不各算一遍）',
          'return works() + " works / " + tracks() + " tracks";' in prefetch)
    check('Repository 兜底把作品键传进去',
          re.search(r'ZiptreePrefetch\.take\(\s*\n?\s*durMs, freshWorkKey\(\)\)', prefetch + repo) is not None)

    # ---------- D 离线文案删除 ----------
    print('D 离线文案回退到「无字幕」')
    i18n_code = strip_comments(i18n)
    check('文案函数 offlineNoCache 已删干净（剥注释后 0 处）',
          'offlineNoCache' not in i18n_code)
    check('文案函数 offlineNoCacheHint 已删干净（剥注释后 0 处）',
          'offlineNoCacheHint' not in i18n_code)
    check('I18n 仍以 noSubtitles() 收尾（回退目标还在）',
          re.search(r'public static String noSubtitles\(\)', i18n) is not None)
    check('悬浮窗占位改回「无字幕」',
          'hint.setText(I18n.noSubtitles());' in fview)
    check('胶囊文字改回「无字幕」',
          re.search(r'floatText = I18n\.noSub\(\);', abtn) is not None)
    check('悬浮窗不再引用离线判定（无用 import 已摘）',
          'NetState' not in fview)
    check('胶囊不再引用离线判定（无用 import 已摘）',
          'NetState' not in abtn)

    # ---------- E P1 三项 ----------
    print('E P1-5 宿主上屏行观测（只统计不改渲染）')
    check('HostLineSync.observe 存在且是两参（宿主行 / 自算行）',
          re.search(r'public static void observe\(List<String> hostLines, List<String> selfLines\)',
                    sync) is not None)
    check('两侧都非空才算样本（不拿空窗充数）',
          re.search(r'hostLines == null \|\| hostLines\.isEmpty\(\)', sync) is not None
          and re.search(r'selfLines == null \|\| selfLines\.isEmpty\(\)', sync) is not None)
    # 【code 1027 泛化】code 1027 把「只记第一次」改成「前 N 次逐条 + 成串单记」，
    #   文案由 MISMATCH (first) 变为 MISMATCH #n / MISMATCH PERSISTENT。
    #   这里守语义不守字面：要有 MISMATCH 留证，且必须写明不接管渲染。
    check('有不一致留证日志（且写明不改渲染）',
          'MISMATCH' in sync and 'rendering NOT changed' in sync)
    check('有汇总节流（不是每帧一行）',
          re.search(r'SUMMARY_INTERVAL_MS = \d+_000L', sync) is not None)
    check('三个读数出口（样本 / 对得上 / 对不上）',
          all(re.search(r'public static synchronized int %s\(\)' % n, sync) is not None
              for n in ('samples', 'matched', 'mismatched')))
    sync_code = strip_comments(sync)
    check('只观测不接管：类里没有 setText / addView / submit 一类写操作',
          not any(k in sync_code for k in ('setText(', 'addView(', 'invalidate()')))
    # ⚠️ 1024 当时写的是 `repo.getCurrentSubtitles()` —— 那是**循环判据**
    #    （它正是本模块上一帧写进去的镜像），code 1025 已改成纯自算 `repo.selfComputedLines()`。
    #    本条只守「scan 收尾把两路数据接进观测」这条**接线**，不钉具体取值方法
    #    （取值来源会随判据改进而变，钉死它等于每改一次判据就得回来改历史脚本）。
    check('SubtitleViewHook 的 scan 收尾接上观测',
          re.search(r'HostLineSync\.observe\(r\.liveLines,\s*repo\.\w+\(\)\);',
                    viewhook) is not None)

    print('E2 P1-7 样式跟随宿主（code 1026 已整体删除）')
    # 【code 1026 / Ari 指令】这一项从配置键一路删到渲染分支，历史判据随之**反转**：
    #   只要代码里再冒出探针类 / 跟随键 / 宿主字号夹取常量，就说明删除被回退了。
    check('P1-7 已整体删除（采样、重载、读口、开关行全无）',
          'HostStyleProbe' not in viewhook and 'HostStyleProbe' not in fview
          and 'HOST_SIZE_MIN_SP' not in style and 'hostSizeSp' not in style
          and 'followHostStyle' not in config and 'followHostStyle' not in remote
          and 'mRowFollowHost' not in settings)

    print('E3 P1-8 命中率与预取读数')
    check('缓存有命中/未命中计数',
          re.search(r'public int hitCount\(\)', cache) is not None
          and re.search(r'public int missCount\(\)', cache) is not None)
    check('身份为 0 也计未命中（不虚高命中率）',
          re.search(r'identity == 0L', cache) is not None or 'missCount++' in cache)
    extras = ['EXTRA_CACHE_HITS', 'EXTRA_CACHE_MISSES', 'EXTRA_PREFETCH_WORKS',
              'EXTRA_PREFETCH_TRACKS', 'EXTRA_LINE_MATCHED', 'EXTRA_LINE_MISMATCHED',
              'EXTRA_LINE_SAMPLES']
    check('Protocol 七个 extra 齐全', all(re.search(r'String %s = "' % e, protocol) for e in extras))
    m_tbl = re.search(r'String\[\] extras = \{(.*?)\};', protocol, re.S)
    check('七个 extra 都进了 selfCheck 的去重表',
          m_tbl is not None and all(('%s,' % e) in m_tbl.group(1) for e in extras),
          'table=%s' % (m_tbl.group(1).strip() if m_tbl else 'missing'))
    check('ConfigBus 七个转发壳齐全（漏一层 = 编译失败）',
          all(re.search(r'String %s = Protocol\.%s;' % (e, e), bus) for e in extras))
    check('ConfigBus 真正把三组读数塞进广播',
          'cache.hitCount()' in bus and 'ZiptreePrefetch.works()' in bus
          and 'HostLineSync.samples()' in bus)
    check('三条读数文案是三语三元组',
          all(re.search(r'%s\("[^"]*%%1\$[ds][^"]*",\s*\n?\s*"[^"]*",\s*\n?\s*"[^"]*"\)' % k, strings)
              for k in ('CACHE_HIT_LINE', 'PREFETCH_LINE', 'LINE_SYNC_LINE')))
    check('设置页接九参统计入口',
          re.search(r'private void applyCacheStats\(int count, long bytes,\s*\n\s*'
                    r'int hits, int misses,\s*\n\s*'
                    r'int prefetchWorks, int prefetchTracks,\s*\n\s*'
                    r'int lineSamples, int lineMatched, int lineMismatched\)', settings) is not None)
    check('设置页有第二行读数拼装器',
          re.search(r'private String cacheStatsExtraLine\(\)', settings) is not None)
    check('接收器按七个 extra 取值',
          all(('ConfigBus.' + e) in settings for e in extras))

    # ---------- F 边界 ----------
    print('F 本轮不动的边界')
    check('缓存索引结构版本仍是 4（条目形态未变，不清毒）',
          re.search(r'INDEX_SCHEMA = 4;', cache) is not None)
    check('抓取闸门三层判据没被改（体积/媒体类型/媒体后缀）',
          all(has(network, k) for k in ('MEDIA_CT_HINTS', 'MEDIA_EXT_HINTS', 'peekLimit')))
    check('换轨判据仍用三元组身份（makeIdentity 仍在）',
          'makeIdentity' in cache or 'makeIdentity' in repo)
    # ⚠️ 必须先剥注释：预取器类头正在解释「为什么不在这里写缓存」（铁律 87①）
    check('预取器仍不写缓存（只交原文，落盘交给数据层）',
          'SubtitleCache' not in strip_comments(prefetch))

    # ---------- G 版本 / 横幅 / 履历 ----------
    print('G 版本 / 横幅唯一 / 履历纪律')
    m_name = re.search(r"def appVersionName = '([0-9.]+)'", gradle)
    m_tag = re.search(r"def appVersionTag = '([0-9.]+)'", gradle)
    m_code = re.search(r'def appVersionCode = (\d+)', gradle)
    m_label = re.search(r"def appVersionCodeLabel = '(\d{4}\.\d+)'", gradle)
    check('versionName 存在', m_name is not None)
    check('versionCode >= 1024（本轮判据放下界，防后面轮次假 FAIL）',
          m_code is not None and int(m_code.group(1)) >= 1024,
          m_code.group(1) if m_code else 'missing')
    check('tag == name（APK 文件名由 tag 决定，最易漏）',
          bool(m_name and m_tag) and m_name.group(1) == m_tag.group(1),
          '%s vs %s' % (m_tag.group(1) if m_tag else '?', m_name.group(1) if m_name else '?'))
    check('label 形态 MMDD.N（构建当天，不钉日期）', m_label is not None)

    # ⚠️ 只数**常开行**（XposedCompat.log）。
    #    本轮顺带把 1022 漏降级的那条降为 LogGate.debug ⇒ 全文件常开横幅应**恰好一条**。
    live = re.findall(
        r'XposedCompat\.log\("\[DLsiteSoundFloat\] ==== BUILD ([0-9.]+) / code (\d+)"\)',
        module)
    check('常开横幅恰好一条（启动时只留一条，不再叠两版）',
          len(live) == 1, 'count=%d -> %s' % (len(live), live))
    if live:
        check('常开横幅 == gradle（name / code）',
              live[0][0] == m_name.group(1) and int(live[0][1]) == int(m_code.group(1)),
              'banner=%s/%s gradle=%s/%s' % (live[0][0], live[0][1],
                                             m_name.group(1), m_code.group(1)))
    check('上一版（1022）的横幅已降为调试行（还在，但不再常开）',
          re.search(r'LogGate\.debug\("\[DLsiteSoundFloat\] ==== BUILD 2\.3\.4 / code 1022"\)',
                    module) is not None)
    check('上一版（1023）的横幅也已是调试行',
          re.search(r'LogGate\.debug\("\[DLsiteSoundFloat\] ==== BUILD [0-9.]+ / code 1023"\)',
                    module) is not None)
    check('本轮履历段存在且自报 code 与 gradle 一致',
          re.search(r'【code %s ——' % re.escape(m_code.group(1)), module) is not None)
    check('履历段收尾句合模板（版本号 X 不变、code A 升 B）',
          re.search(r'版本号 [0-9.]+ (?:不变|升 [0-9.]+)、code \d+ 升 \d+。', module) is not None)

    print()
    print('总计 %d 条，通过 %d 条，失败 %d 条' % (total, total - len(fails), len(fails)))
    if fails:
        print('失败项：')
        for x in fails:
            print('  - %s' % x)
        return 1
    print('verify_1024_src: ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
