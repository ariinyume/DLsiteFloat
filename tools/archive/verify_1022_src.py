#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1022 / v2.3.4】P0 适配体检四项 + ziptree 取证的**源码层**验证。
（读的是**活的工作区** ⇒ 版本号判下界、判据只守结构与接线，不钉字面量；见铁律 82/⑬）

本轮四件事（依据宿主 2.22.0 实包离线体检，见 ../_review_2220/）
--------------------------------------------------------------
P0-1 宿主版本感知  util/HostInfo
P0-2 适配自检表    hook/AdapterHealth（六项三态）
P0-3 状态映射键体检 hook/PlayerPositionHook（六键 + 降级）
P0-4 离线播放文案  util/NetState + util/I18n + 两处 UI 接线
取证  ziptree 落盘 util/DiagDump + NetworkHook 闸门放宽

验什么
------
A 新文件：四个类都存在，且各自的关键结构齐全（不是空壳）。
B 接线：八处调用点都真的接上了（写了类没人调 = 白做）。
C 文案：离线两句话三语齐全，且旧「无字幕」文案仍在（不许替换掉）。
D 边界：本轮**不动**的三处（抓取闸门口径 / 换轨判据 / 缓存键空间）关键行仍在。
E 版本 / 横幅 / 履历纪律：tag == name、code >= 1022、label 形态 `MMDD.N`、
  横幅唯一且自报 code == gradle code、履历段收尾句合模板、且履历段不点名新标识符。

用法
----
    python verify_1022_src.py [src_root]
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


def main():
    global SRC
    SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'src', 'main', 'java')
    base = os.path.join(SRC, 'io', 'github', 'ariinyume', 'dlsitesoundfloat')

    def f(rel):
        p = os.path.join(base, rel)
        return read(p) if os.path.exists(p) else ''

    host = f('util/HostInfo.java')
    health = f('hook/AdapterHealth.java')
    net = f('util/NetState.java')
    diag = f('util/DiagDump.java')
    module = f('DlsiteSoundSubtitleModule.java')
    netHook = f('hook/NetworkHook.java')
    posHook = f('hook/PlayerPositionHook.java')
    viewHook = f('hook/SubtitleViewHook.java')
    btnHook = f('hook/ActivityButtonHook.java')
    floatView = f('view/FloatingSubtitleView.java')
    i18n = f('util/I18n.java')
    settings = f('ui/SettingsActivity.java')
    strings = f('ui/Strings.java')
    gradle = read(os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(SRC))), 'build.gradle'))

    print('A 新文件与内部结构')
    check('util/HostInfo.java 存在', bool(host), 'missing')
    check('HostInfo 有已验证版本常量 + 读包信息',
          has(host, 'VERIFIED_VERSION') and 'getPackageInfo' in host and 'versionCode' in host)
    check('HostInfo 有「刚更新」判定（版本号比对，不用时间戳）',
          has(host, 'justUpdated') and 'last_version_code' in host)
    check('hook/AdapterHealth.java 存在', bool(health), 'missing')
    items = ['NET_BUILD', 'NET_RN', 'AUDIO_STATUS', 'VIEW_PAGE', 'SUB_TEXT', 'STATUSBAR']
    check('AdapterHealth 六项齐全', all(i in health for i in items),
          '缺：%r' % [i for i in items if i not in health])
    check('AdapterHealth 三态 + 只在状态变化时落日志',
          all(s in health for s in ['UNKNOWN', 'HIT', 'DEGRADED', 'MISS'])
          and 'old == state' in health)
    check('util/NetState.java 存在', bool(net), 'missing')
    check('NetState 用「已验证」能力位，读不到按在线',
          'NET_CAPABILITY_VALIDATED' in net and 'offline = false' in net)
    check('util/DiagDump.java 存在', bool(diag), 'missing')
    check('DiagDump 只认 ziptree + 限份数限体积',
          'ziptree' in diag and 'MAX_FILES' in diag and 'MAX_BYTES' in diag)

    print('B 接线（写了没人调 = 白做）')
    check('模块入口初始化 HostInfo（宿主 Application 上下文）',
          'HostInfo.init(appCtx' in module)
    check('NetworkHook 上报网络两通道 + 首 tap 判 HIT',
          'AdapterHealth.Item.NET_BUILD' in netHook and 'AdapterHealth.Item.NET_RN' in netHook
          and 'sBuildCalls == 1' in netHook)
    check('NetworkHook 取证目标单独放宽体积上限',
          'diagTarget' in netHook and 'DiagDump.MAX_BYTES' in netHook)
    check('NetworkHook 取证受调试开关控制 + 关闭时提示一次',
          'DiagDump.save(' in netHook and 'DiagDump.logSkippedOnce()' in netHook)
    check('PlayerPositionHook 上报状态映射 + 六键体检',
          'AdapterHealth.Item.AUDIO_STATUS' in posHook and 'WANT_KEYS' in posHook
          and 'sKeysChecked' in posHook)
    check('SubtitleViewHook 上报播放页 / 字幕文本 + 首表',
          'AdapterHealth.Item.VIEW_PAGE' in viewHook and 'AdapterHealth.Item.SUB_TEXT' in viewHook
          and 'logTableOnce' in viewHook)
    check('StatusBarSubtitleHook 上报状态栏项',
          'AdapterHealth.Item.STATUSBAR' in f('hook/StatusBarSubtitleHook.java'))
    check('胶囊文案按联网状态分流', 'NetState.isOffline()' in btnHook
          and 'I18n.offlineNoCache()' in btnHook)
    check('悬浮窗占位按联网状态分流', 'NetState.isOffline()' in floatView
          and 'I18n.offlineNoCacheHint()' in floatView)
    check('设置页有宿主版本只读行（读 PackageInfo + 已验证比对）',
          'buildHostVersionRow' in settings and 'getPackageInfo' in settings
          and 'HostInfo.VERIFIED_VERSION' in settings)

    print('C 文案')
    check('I18n 新增两条离线文案', 'offlineNoCache()' in i18n and 'offlineNoCacheHint()' in i18n)
    check('离线文案三语齐全（简 / 繁 / 英）',
          i18n.count('Offline') >= 2 and '離線' in i18n and '离线' in i18n)
    check('原「无字幕」两条文案未被替换掉',
          'public static String noSub()' in i18n and 'public static String noSubtitles()' in i18n)
    check('Strings 新增宿主版本三项（三语）',
          'HOST_VERSION' in strings and 'HOST_VERIFIED' in strings and 'HOST_UNVERIFIED' in strings)

    print('D 边界（本轮明确不动的东西）')
    check('抓取闸门三档仍在（大体积 / 媒体类型 / 媒体扩展名）',
          'MEDIA_CT_HINTS' in netHook and 'MEDIA_EXT_HINTS' in netHook and 'peekLimit' in netHook)
    check('去重表只在「准备 peek」时登记（不在闸门前登记）',
          'sSeenBodies.add(body)' in netHook)
    check('换轨判据三元组仍在（trackCount / duration / currentIndex）',
          'onPlaylistStateFromStatusMap(curIdx, trackCount, durSec' in posHook)
    check('缓存身份口径未被改动（PlaylistKey.makeIdentity 仍在）',
          'PlaylistKey' in f('data/SubtitleCache.java') or 'makeIdentity' in f('data/PlaylistKey.java'))

    print('E 版本 / 横幅 / 履历')
    m_tag = re.search(r"def appVersionTag = '([^']+)'", gradle)
    m_code = re.search(r'def appVersionCode = (\d+)', gradle)
    m_name = re.search(r"def appVersionName = '([^']+)'", gradle)
    m_lab = re.search(r"def appVersionCodeLabel = '([^']+)'", gradle)
    tag = m_tag.group(1) if m_tag else ''
    code = int(m_code.group(1)) if m_code else -1
    name = m_name.group(1) if m_name else ''
    label = m_lab.group(1) if m_lab else ''
    check('gradle 四处都能解析', bool(tag and name and code > 0 and label),
          'tag=%r name=%r code=%s label=%r' % (tag, name, code, label))
    check('tag == name（APK 文件名只吃 tag，最易漏）', tag == name, 'tag=%s name=%s' % (tag, name))
    check('code >= 1022（上界不设：留给后续轮）', code >= 1022, 'code=%s' % code)
    check('label 形态 MMDD.N（日期段随构建当天，不钉具体日期）',
          bool(re.match(r'^\d{4}\.\d+$', label)), 'label=%r' % label)

    # 只认**常开**那一行（项目形态：常开一行 + debug 详细一段，两行都含同一句 BUILD 抬头）
    banners = re.findall(
        r'XposedCompat\.log\("\[DLsiteSoundFloat\] ==== BUILD ([0-9.]+) / code (\d+)"\)', module)
    check('常开横幅至少有一条', bool(banners), 'none')
    if banners:
        top_name, top_code = banners[0]
        check('常开横幅首条 == gradle（versionName / code）',
              top_name == name and int(top_code) == code,
              'banner=%s/%s gradle=%s/%s' % (top_name, top_code, name, code))
        # ⚠️ 历史上有「同版本号第二次打包」⇒ 老 code 在横幅里可能重复出现；
        #    只守**本轮 code** 恰好一条，不去管历史重复。
        check('本轮 code 在常开横幅里恰好一条',
              banners.count((name, str(code))) == 1,
              'occurrences=%d total=%d' % (banners.count((name, str(code))), len(banners)))

    # 履历段：取与当前 code 对应的那条 debug 横幅（形如 BUILD x / code N （…））
    m_hist = re.search(r'==== BUILD [0-9.]+ / code %d （(.*?)"\);' % code, module, re.S)
    hist = m_hist.group(1) if m_hist else ''
    check('本轮履历段存在（与横幅 code 同号）', bool(hist), 'not found')
    if hist:
        segs = re.findall(r'[①②③④⑤⑥⑦⑧⑨]', hist)
        check('履历段分段 >= 6 且不重复', len(segs) >= 6 and len(set(segs)) == len(segs),
              'segs=%r' % segs)
        m_tail = re.search(r'版本号 (\d+\.\d+\.\d+) 升 (\d+\.\d+\.\d+)、code (\d+) 升 (\d+)。', hist)
        check('履历段收尾句合模板（版本号 A 升 B、code C 升 D。）', bool(m_tail),
              repr(hist[-80:]))
        if m_tail:
            check('收尾句口径自洽（B == name、D == 横幅 code）',
                  m_tail.group(2) == name and int(m_tail.group(4)) == code,
                  'tail=%r name=%s code=%s' % (m_tail.group(0), name, code))
        forbidden = ['AdapterHealth', 'HostInfo', 'NetState', 'DiagDump', 'ziptree',
                     '"', '\\', '\n']
        bad = [w for w in forbidden if w in hist]
        check('履历段不点名新标识符 / 无引号反斜杠换行（防空探针自命中）',
              not bad, '违禁词：%r' % bad)

    print()
    print('总计 %d 条，通过 %d 条，失败 %d 条' % (total, total - len(fails), len(fails)))
    if fails:
        print('失败项：')
        for x in fails:
            print('  - %s' % x)
        return 1
    print('verify_1022_src: ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
