#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_1007_src.py —— code 1007 的**源码层**验证。

code 1007 是**新功能**：**字幕离线缓存**（飞行模式 / 不挂代理时也能显示已经在线
抓到过的字幕）。Ari 2026-10-13 需求原文六条：

  1. 飞行模式下宿主 App 不显示自带字幕（字幕是每次播放音轨时**在线抓取**的）；
  2. 缓存范围默认「全部在线播过的轨」自动 LRU；
  3. 设置页「其它」里加「字幕缓存功能」开关 + 「清除所有字幕缓存」按钮；
  4. 播放页右上角加一个按键提示（官方字幕开关按钮的左边），**默认关**；点开才显示
     本地缓存字幕，关着时照旧抓在线字幕、抓不到就显示无字幕；
  5. 上限 **256MB**（Ari 明确纠正了分析文档里的 128MB），满了从**最早缓存**的开始删；
  6. 身份口径认 `(trackCount, durationMs, currentIndex)` 指纹，并投入
     标题 / 媒体源 URI 确认通道把它做得更稳。

追问确认的两条口径：
  · 落位 —— 「如果官方 CC 按钮显示就挂在 CC 按钮的左边，如果 CC 按钮不显示就挂在
    CC 按钮的位置上」；
  · 状态 —— **会话级、默认关**。

本脚本验的是**源码层**（dex 层见 verify_1007.py）：看得见「值写对没、门控对不对、
两处口径是否互补、有没有回写刚读出来的东西」这类字节码证不了的事。

⚠️ 每一条都只在**剥掉注释**后的源码上匹配（铁律 53），且第一步先把行尾归一成 LF
   （铁律 58：`core.autocrlf=true` 会让工作区 .java 变成 CRLF，而本仓库里
   有 LF 也有 CRLF 的文件，不归一会假 FAIL）。

用法：
    python tools/verify_1007_src.py          （在仓库根执行，不接参数）
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = 'app/src/main/java/io/github/ariinyume/dlsitesoundfloat/'
CACHE = os.path.join(ROOT, J, 'data/SubtitleCache.java')
KEY = os.path.join(ROOT, J, 'data/PlaylistKey.java')
REPO = os.path.join(ROOT, J, 'data/SubtitleRepository.java')
CFG = os.path.join(ROOT, J, 'config/SubtitleConfig.java')
RCFG = os.path.join(ROOT, J, 'config/RemoteConfig.java')
PROTO = os.path.join(ROOT, J, 'config/Protocol.java')
BUS = os.path.join(ROOT, J, 'config/ConfigBus.java')
MOD = os.path.join(ROOT, J, 'DlsiteSoundSubtitleModule.java')
SET = os.path.join(ROOT, J, 'ui/SettingsActivity.java')
STR = os.path.join(ROOT, J, 'ui/Strings.java')
ABH = os.path.join(ROOT, J, 'hook/ActivityButtonHook.java')
SVH = os.path.join(ROOT, J, 'hook/SubtitleViewHook.java')
I18N = os.path.join(ROOT, J, 'util/I18n.java')
GRADLE = os.path.join(ROOT, 'app/build.gradle')
LAYOUT = os.path.join(ROOT, 'app/src/main/res/layout/activity_settings.xml')

rows = []
fails = 0


def check(label, ok, detail=''):
    global fails
    rows.append((label, bool(ok), detail))
    if not ok:
        fails += 1


def read(p):
    """读源码并**把行尾统一成 LF**（铁律 53/58）。"""
    return io.open(p, encoding='utf-8', newline='').read().replace('\r\n', '\n')


def strip_comments(src):
    """剥掉块注释与行注释 —— 判据必须在「只有代码」的文本上匹配（铁律 53）。"""
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    src = re.sub(r'//[^\n]*', '', src)
    return src


def norm(src):
    """折空白：判据的「字符级形态」不能被换行/缩进变化左右（铁律 53）。"""
    return re.sub(r'\s+', ' ', src)


# 声明位前缀（铁律新增）：行首缩进 + 可选注解 + 可选修饰符 + 返回类型。
#   作用：让「按名字裸匹配」的判据只落在**方法定义**上，不落进调用点。
#   例：`handleCacheClear\(` 若裸匹配，会先命中 onReceive 里的 `handleCacheClear(c, tag);`
#   ⇒ 切出来的是调用点之后的一坨无关代码（E9 假 FAIL 的根因）。
_DECL_ANNO = r'(?:@\w+(?:\([^)]*\))?\s+)*'
_DECL_MODS = (r'(?:(?:public|private|protected|static|final|synchronized'
              r'|abstract|native|default|transient|volatile)\s+)*')
_DECL_TYPE = r'(?!return\b|new\b|throw\b|else\b|case\b)[\w\.\$]+(?:\s*<[^<>]*>)?(?:\s*\[\s*\])*'


def method_body(src, sig_regex):
    """按方法签名正则切出一段方法体（切到下一个同缩进的方法头）。

    只在**声明位置**匹配：要求签名之前是「行首缩进 +（可选注解/修饰符）+ 返回类型」，
    这样纯缩进的调用点（`            foo(x);`）不可能命中。
    若严格匹配不到（调用方已把修饰符/返回类型写进 sig_regex，如
    `protected void onResume\(`），退回裸匹配以保持兼容。
    """
    decl = (r'(?m)^[ \t]+' + _DECL_ANNO + _DECL_MODS + _DECL_TYPE + r'\s+'
            + sig_regex)
    m = re.search(decl, src)
    if not m:
        m = re.search(sig_regex, src)
    if not m:
        return ''
    nxt = re.search(r'\n    (?:/\*\*|@|private |public |protected |static |final )',
                    src[m.end():])
    return src[m.start():m.end() + (nxt.start() if nxt else len(src))]


def main():
    cache = read(CACHE)
    key = read(KEY)
    repo = read(REPO)
    cfg = read(CFG)
    rcfg = read(RCFG)
    proto = read(PROTO)
    bus = read(BUS)
    mod = read(MOD)
    sett = read(SET)
    strs = read(STR)
    abh = read(ABH)
    svh = read(SVH)
    i18n = read(I18N)
    gra = read(GRADLE)
    xml = read(LAYOUT)

    cc = norm(strip_comments(cache))
    kc = norm(strip_comments(key))
    rc = norm(strip_comments(repo))
    fc = norm(strip_comments(cfg))
    rcc = norm(strip_comments(rcfg))
    pc = norm(strip_comments(proto))
    bc = norm(strip_comments(bus))
    mc = norm(strip_comments(mod))
    sc = norm(strip_comments(sett))
    ssc = norm(strip_comments(strs))
    ac = norm(strip_comments(abh))
    vc = norm(strip_comments(svh))
    ic = norm(strip_comments(i18n))
    xc = norm(strip_comments(xml))

    # ══════════════ A. 数据层 SubtitleCache ══════════════
    check('A1 新增数据层文件 data/SubtitleCache.java 存在且包名正确',
          os.path.exists(CACHE)
          and 'package io.github.ariinyume.dlsitesoundfloat.data;' in cache)
    check('A2 容量常量是 **256MB**（Ari 明确口径，分析文档里的 128MB 不算）',
          'LIMIT_BYTES_DEF = 256L * 1024 * 1024L' in cc,
          'find: LIMIT_BYTES_DEF = 256L * 1024 * 1024L')
    check('A3 缓存目录名是 subtitle_cache（落盘位置唯一真源）',
          '"subtitle_cache"' in cc)
    check('A4 索引文件名 index.json + 条目文件名后缀 .json',
          '"index.json"' in cc and '".json"' in cc)
    check('A5 原子写：先写临时文件再 renameTo（与 ConfigStore.writeJsonAtomic 同口径）',
          'renameTo' in cc and 'tmp' in cc.lower())
    check('A6 LRU：按最后使用时间由旧到新排序后再删（used / lastUsed 参与排序）',
          re.search(r'sort|Comparator', cc) is not None
          and re.search(r'\bused\b', cc) is not None)
    check('A7 清空能力 clearAll() 删除索引与全部条目文件',
          'void clearAll()' in cc and re.search(r'delete\(\)', cc) is not None)
    check('A8 公开查询 API lookup / has 都在',
          'lookup(' in cc and re.search(r'boolean has\(', cc) is not None)
    check('A9 落盘入口 put(...) 带完整指纹与内容哈希参数',
          re.search(r'void put\(|Entry put\(', cc) is not None and 'hash' in cc)
    check('A10 时长补盖 stampDuration 单独成口（标签竞态：JSON 常比权威读数先到）',
          'stampDuration(' in cc)
    check('A11 put() 里校验 tc/idx 合法才落盘（防脏标签误命中）',
          re.search(r'tc >= 0 && idx >= 0', cc) is not None
          or re.search(r'tc < 0 \|\| idx < 0', cc) is not None)
    check('A12 时间轴交叉校验容差常量为 2.0 秒',
          'TIMELINE_TOLERANCE_SEC = 2.0' in cc)
    check('A13 stampDuration 拒绝「时长明显短于内容」的补盖（校验不是摆设）',
          'TIMELINE_TOLERANCE_SEC' in method_body(cache, r'void stampDuration\('))
    check('A14 同轨重写用选择键覆盖旧条目（不留双份）',
          'bySelection' in cc and 'remove' in cc)

    # ══════════════ B. 身份 / 选择键 ══════════════
    check('B1 PlaylistKey 新增 identityDurationMs（从指纹里取回时长毫秒）',
          'identityDurationMs(' in kc)
    check('B2 PlaylistKey 公开 makeIdentity（口径收拢，防两处各算一套）',
          re.search(r'makeIdentity\(', kc) is not None)
    check('B3 identityDurationMs 的算式是「模 TC 尺度再整除 IDX 尺度」',
          'IDENTITY_TC_SCALE' in kc and 'IDENTITY_IDX_SCALE' in kc
          and re.search(r'% IDENTITY_TC_SCALE', kc) is not None)
    check('B4 PlayerSourceHook 的 makeIdentity 改成转发壳（不再自己算）',
          'PlaylistKey.makeIdentity(' in norm(strip_comments(
              read(os.path.join(ROOT, J, 'hook/PlayerSourceHook.java')))))

    # ══════════════ C. 仓库接线 / 门控 ══════════════
    # 【code 1012】本地缓存改为**全自动**（云端优先、本地兜底）：会话级手动开关整批移除。
    check('C1 会话级手动开关字段已删（不再有 localCacheMode）',
          'localCacheMode' not in rc)
    check('C2 门控 cacheUsable 只看配置总闸（不再叠会话级开关）',
          re.search(r'cacheUsable\(\) \{ try \{ return RemoteConfig\.get\(\)\.subtitleCacheEnabled;',
                    rc) is not None)
    check('C3 换轨路径上调用了 tryResumeFromDisk（读盘恢复接入换轨判定）',
          re.search(r'tryResumeFromDisk\(', rc) is not None)
    check('C4 落盘只走「非磁盘来源」那条路，且改为**先暂存**（stageCacheToDisk）',
          'stageCacheToDisk(' in rc
          and 'if (!fromDisk)' in rc)
    check('C5 落盘一律在**缓存 IO 线程**上做，不在主线程写盘',
          'cacheIo' in rc and 'newSingleThreadExecutor' in rc)
    check('C6 时长补盖挂在「带时长的权威读数」路径上（noteObservedPlaylistIdentity）',
          'stampDuration(' in rc
          and 'stampDuration(' in method_body(repo, r'void noteObservedPlaylistIdentity\('))
    check('C7 【落盘标签修正】换轨入口先按权威选择键兑现暂存（flushStagedCache）',
          'flushStagedCache(newSelection)' in rc and 'private void flushStagedCache(' in rc)
    check('C8 可用性刷新只在真的翻转时通知观察者（不把高频读数变成抖动源）',
          'avail != localCacheAvailable' in rc)
    check('C9 字幕原文单独留存（lastCacheableJson），断网读回的字节与在线一致',
          'lastCacheableJson' in rc)
    check('C10 离线判定失败一律按「有网」处理（宁可信有网，不比改动前更差）',
          'private boolean isOffline()' in rc
          and 'return false;' in method_body(repo, r'private boolean isOffline\(')
          and 'NET_CAPABILITY_INTERNET' in rc)

    # ══════════════ D. 配置键（七处同步）══════════════
    check('D1 配置键常量 subtitle_cache_enabled 存在',
          'K_SUBTITLE_CACHE_ENABLED = "subtitle_cache_enabled"' in fc)
    check('D2 字段默认**开**（true）',
          'boolean subtitleCacheEnabled = true' in fc)
    n_cfg = len(re.findall(r'subtitleCacheEnabled', fc))
    check('D3 字段在 copy / sameParametersAs / toJson / fromJson / writeTo / fromPrefs / '
          'summary 里都出现（出现次数 ≥ 8，漏一处就是「改了值不落盘」）',
          n_cfg >= 8, 'count=%d' % n_cfg)
    check('D4 RemoteConfig 暴露只读访问器 subtitleCacheEnabled()',
          'static boolean subtitleCacheEnabled()' in rcc)
    check('D5 该访问器读不到时**回落 true**（不因为异常把功能关掉）',
          'return true;' in method_body(rcfg, r'static boolean subtitleCacheEnabled\(\)'))

    # ══════════════ E. 跨进程协议 ══════════════
    check('E1 PROTOCOL_VERSION 升到 2（只加不改值）',
          'PROTOCOL_VERSION = 2' in pc)
    for a in ('ACTION_SUBTITLE_CACHE_CLEAR', 'ACTION_SUBTITLE_CACHE_STATS_REQ',
              'ACTION_SUBTITLE_CACHE_STATS'):
        check('E2 action 常量 %s 存在且带 ACTION_PREFIX' % a,
              re.search(r'%s = ACTION_PREFIX \+' % a, pc) is not None)
    for x in ('EXTRA_CACHE_COUNT', 'EXTRA_CACHE_BYTES'):
        check('E3 extra 常量 %s 存在' % x, re.search(r'%s = "' % x, pc) is not None)
    check('E4 selfCheck 的 action 数组收进了三条新 action（自检才算完整）',
          all(('%s,' % a) in pc or ('%s)' % a) in pc for a in
              ('ACTION_SUBTITLE_CACHE_CLEAR', 'ACTION_SUBTITLE_CACHE_STATS_REQ',
               'ACTION_SUBTITLE_CACHE_STATS')))
    check('E5 selfCheck 的 extra 数组收进了两个新 extra',
          re.search(r'EXTRA_CACHE_COUNT, EXTRA_CACHE_BYTES', pc) is not None)
    check('E6 ConfigBus 转发三条 action + 两个 extra（各 1 行 = 5 处）',
          len(re.findall(r'Protocol\.(ACTION_SUBTITLE_CACHE_\w+|EXTRA_CACHE_\w+)', bus)) >= 5)
    check('E7 清理/统计只在 tag=="host" 的应答器上注册（设置页 / SystemUI 注册了也办不到）',
          re.search(r'if \("host"\.equals\(tag\)\) \{ f\.addAction\(ACTION_SUBTITLE_CACHE_CLEAR\)',
                    bc) is not None)
    check('E8 清理请求走**显式广播**（setPackage(HOST_PKG)，宿主在后台也收得到）',
          'i.setPackage(HOST_PKG)' in method_body(bus, r'sendCacheClear\(')
          and 'i.setPackage(HOST_PKG)' in method_body(bus, r'sendCacheStatsRequest\('))
    check('E9 宿主侧清完/查完都回一条统计（0 条也要回，设置页那行才能归零）',
          'sendCacheStats(' in method_body(bus, r'handleCacheClear\(')
          and 'sendCacheStats(' in method_body(bus, r'answerCacheStats\('))

    # ══════════════ F. 宿主进程初始化守卫 ══════════════
    check('F1 模块里真的初始化了 SubtitleCache',
          'SubtitleCache.get().init(' in mc)
    check('F2 该初始化落在 hookApplicationAttach 里（Application 拿到 Context 的第一时刻）',
          'SubtitleCache.get().init(' in method_body(mod, r'void hookApplicationAttach\('))
    check('F3 hookApplicationAttach 只在**宿主包**分支被调用（不是 SystemUI 进程也初始化）',
          re.search(r'if \(!TARGET_PKG\.equals\(pkg\)\) \{ return; \} try \{ '
                    r'hookApplicationAttach\(', mc) is not None)

    # ══════════════ G. 设置页 ══════════════
    check('G1 【code 1015 改锚】字幕缓存整组仍在，但已从「其他」卡搬进「实验性功能」卡',
          'buildSubtitleCacheRow(' in sc
          and 'buildSubtitleCacheRow(parent);'
              in method_body(sett, r'void buildExperimentalGroup\(')
          and 'buildSubtitleCacheRow(parent);' not in method_body(sett, r'void buildMiscGroup\('))
    # 【code 1034 改写】末行收敛增加「墨迹补偿」重载：按钮条收尾的两卡（其他=备份按钮条 /
    #   实验=清除按钮条）改为传入 CARD_LAST_BTN_INSET_DP，实验卡末行仍是「最后一个孩子」。
    #   补偿只为拉平四卡可见底距，收敛语义未变。
    check('G2 【code 1015 改锚】两卡的底部收敛各自钉在自己的最后一行（其他=备份按钮 / 实验=清除按钮；1034 起带墨迹补偿）',
          'pinCardLastBottom(parent, bar, CARD_LAST_BTN_INSET_DP);' in method_body(sett, r'void buildMiscGroup\(')
          and 'pinCardLastBottom(parent, mExpLastRow, CARD_LAST_BTN_INSET_DP);'
              in method_body(sett, r'void buildExperimentalGroup\('))
    check('G3 开关行用的是 addSwitchRow + 新的 SUBTITLE_CACHE 文案',
          'addSwitchRow(root, Strings.SUBTITLE_CACHE' in sett)
    check('G4 开关回灌进 syncWidgets（否则打开设置页不显示真实状态）',
          'setSwitch(mRowSubtitleCache, mDraft.subtitleCacheEnabled)' in sc)
    check('G5 清除按钮有二次确认（删的是用户攒下来的离线字幕，不可逆）',
          'CACHE_CLEAR_CONFIRM_TITLE' in sc and 'CACHE_CLEAR_CONFIRM_MSG' in sc
          and 'MaterialAlertDialogBuilder' in method_body(sett, r'void onClearCacheClicked\('))
    check('G6 「已清除」提示由**宿主回执**触发，不是点下按钮就报成功',
          'mPendingClearToast' in method_body(sett, r'void onClearCacheClicked\(')
          and 'mPendingClearToast' in method_body(sett, r'void applyCacheStats\('))
    check('G7 统计接收器在 onCreate 注册、onDestroy 注销（成对，不漏）',
          'registerCacheStatsReceiver();' in sett
          and 'unregisterReceiver(mCacheStatsReceiver)' in sett
          and 'protected void onDestroy()' in sett)
    check('G8 Android 13+ 动态注册声明 RECEIVER_EXPORTED（宿主是别的 UID）',
          'Context.RECEIVER_EXPORTED' in method_body(sett, r'void registerCacheStatsReceiver\('))
    check('G9 占用读数有「读不到」态，不用 0 冒充（0 会被读成「缓存是空的」）',
          'CACHE_USAGE_OFF' in sc and 'CACHE_USAGE_LOADING' in sc)
    check('G10 回本页（onResume）会重问一次占用',
          'ConfigBus.sendCacheStatsRequest(this)' in method_body(sett, r'protected void onResume\('))
    check('G11 整页禁用（模块未激活）覆盖得到这一组：它在 mGroupMisc 里',
          'buildSubtitleCacheRow(mGroupMisc)' not in sett  # 由 buildMiscGroup(mGroupMisc) 传入
          and 'buildMiscGroup(mGroupMisc);' in sc
          and 'setGroupEnabled(mGroupMisc, enabled);' in sc)

    # ══════════════ H. 文案（三语齐全）══════════════
    for name in ('SUBTITLE_CACHE', 'SUBTITLE_CACHE_HINT', 'CACHE_USAGE',
                 'CACHE_USAGE_LOADING', 'CACHE_USAGE_OFF', 'CACHE_CLEAR',
                 'CACHE_CLEAR_CONFIRM_TITLE', 'CACHE_CLEAR_CONFIRM_MSG',
                 'CACHE_CLEAR_DONE'):
        m = re.search(r'\b%s\((.*?)\),\n' % re.escape(name), strs, flags=re.S)
        check('H1 文案 %s 三语齐全（三个字符串字面量）' % name,
              m is not None and len(re.findall(r'"[^"]*"', m.group(1))) >= 3)

    # ══════════════ I. 【code 1012】播放页「字幕缓存」胶囊已整批移除 ══════════════
    # 真机截图（2026-10-13 20:30）：胶囊落在结构推断档，纵向中线取自更靠下的容器，
    # 被推到屏幕左下角；而它存在的唯一目的（手动开本地缓存）已由自动策略取代。
    check('I1 胶囊 id 常量已删（不再占用 0x7F999004）',
          'CACHE_BUTTON_ID' not in ac)
    check('I2 胶囊本体与懒创建已删（ensureCacheButton / sCacheButton 不在）',
          'ensureCacheButton' not in ac and 'sCacheButton' not in ac)
    check('I3 点击回调与会话级开关调用已删（不再 setLocalCacheMode / isLocalCacheMode）',
          'setLocalCacheMode' not in ac and 'isLocalCacheMode' not in ac)
    check('I4 胶囊显隐门已删（hasLocalCacheForCurrentTrack / cacheButtonWanted 不在按钮层）',
          'hasLocalCacheForCurrentTrack' not in ac and 'cacheButtonWanted' not in ac)
    check('I5 落位阶梯与三档锚点调用已删（layoutCacheButton / targetRight 不存在）',
          'layoutCacheButton' not in ac and 'targetRight' not in ac)
    check('I6 锚点记忆位与死区常量已删',
          'sLastCcRect' not in ac and 'sHasLastCcRect' not in ac
          and 'CACHE_PLACE_DEADZONE_PX' not in ac and 'sCachePlacedAt' not in ac)
    check('I7 隐藏分支与第四档兜底调用已删',
          'hideCacheButton' not in ac and 'symmetricCcRect' not in ac)
    check('I8 跟手位移通道里的缓存胶囊分支已删（applyFollowOffset 只剩按钮组）',
          'sCacheButton' not in method_body(abh, r'void applyFollowOffset\('))
    check('I9 切后台摘除胶囊的代码已删（removeButton 里不再 findViewById(CACHE_BUTTON_ID)）',
          'CACHE_BUTTON_ID' not in method_body(abh, r'void removeButton\('))
    check('I10 观察者里不再刷新胶囊文字/底色（applyCacheButtonState 已删）',
          'applyCacheButtonState' not in ac)
    check('I11 负向：另外两枚胶囊（状态栏 / 悬浮窗）与共享视觉件一字未动',
          'createCapsule(ctx, CAPSULE_ID_STATUSBAR)' in ac
          and 'createCapsule(ctx, CAPSULE_ID_FLOATING)' in ac
          and 'private static Drawable createCapsuleDrawable(' in ac)

    check('J1 CC 按钮的判定标签是 SUBTITLE_BUTTON',
          'CC_BUTTON_TAG = "SUBTITLE_BUTTON"' in vc)
    check('J2 顶栏收起键的判定标签是 FULL_PLAYER_CLOSE_BUTTON',
          'CLOSE_BUTTON_TAG = "FULL_PLAYER_CLOSE_BUTTON"' in vc)
    check('J3 取 testID：普通 tag 优先，R.id 槽**只作兜底**（按名字查 —— 编译期拿不到对方 R）',
          'raw = v.getTag();' in vc
          and 'v.getTag(rid)' in vc
          and 'getIdentifier("react_test_id", "id"' in vc)
    check('J4 【code 1009】判定前先归一化，再用**后缀匹配**比对常量'
          '（宿主 testID 实值是短横线；后缀匹配容忍前缀、排除同前缀图标名）',
          'String key = normalizeTag(tag);' in vc
          and 'key.endsWith(CC_BUTTON_TAG)' in vc
          and 'key.endsWith(CLOSE_BUTTON_TAG)' in vc)
    check('J5 探测挂在既有的一次性遍历里（不另起一趟整树扫描）',
          'probeOfficialToolbar(v, r);' in norm(svh)
          and svh.count('probeOfficialToolbar') >= 2)
    check('J6 两个控件都认到（且普查做完）后短路返回（每 View 只做一次 tag 判定的开销）',
          'if (r.ccFound && r.closeFound && sTagCensusDone) { return; }' in vc)
    check('J7 探测包在 try 里，绝不因它把整趟扫描带崩',
          'catch (Throwable ignored)' in method_body(svh, r'void probeOfficialToolbar\('))
    check('J8 结构下潜有层数上限 + 宽度量级收口（拿不到就返回 null，不猜）',
          'CLUSTER_MAX_DEPTH' in vc and 'CLUSTER_W_RATIO' in vc
          and 'return null;' in method_body(svh, r'int\[\] trailingToolbarClusterRect\('))
    check('J9 结构下潜只在「CC 缺席但收起键在场」时才算（有 CC 的轨一次都不进）',
          'if (!r.ccFound && r.closeFound)' in vc)

    # ══════════════ K. 胶囊文案（三语 + 参与量宽）══════════════
    check('K1 I18n 新增 cacheOn / cacheOff',
          'String cacheOn()' in ic and 'String cacheOff()' in ic)
    check('K2 cacheOn/cacheOff 都是三语（简 / 繁 / 英）',
          len(re.findall(r'"', method_body(i18n, r'String cacheOn\('))) >= 6
          and len(re.findall(r'"', method_body(i18n, r'String cacheOff\('))) >= 6)
    check('K3 新文案进了 capsuleTextPx 的量宽样本（否则可能被撑出省略号）',
          'I18n.cacheOn(), I18n.cacheOff()' in ac)

    # ══════════════ L. 版本号自洽（**不钉死具体值** —— 口径同 1004/1005/1006）══════════════
    m_code = re.search(r"def appVersionCode = (\d+)", gra)
    m_lab = re.search(r"def appVersionCodeLabel = '([\d.]+)'", gra)
    m_name = re.search(r"def appVersionName = '([\d.]+)'", gra)
    vname = m_name.group(1) if m_name else None
    vcode = m_code.group(1) if m_code else None
    check('L1 appVersionCode >= 1007（本轮 1009）',
          vcode is not None and vcode.isdigit() and int(vcode) >= 1007, 'code=%s' % vcode)
    # 【code 1017 / label 规则修订】日期段跟着构建当天走 ⇒ 形如 `1014.5`，不再钉 1008。
    check('L2 appVersionCodeLabel 形如 MMDD.NN（日期段随构建当天）',
          m_lab is not None and re.match(r'^\d{4}\.\d+$', m_lab.group(1)) is not None,
          'label=%s' % (m_lab.group(1) if m_lab else '?'))
    # 【code 1020】2.3.2 是 code 1019 那轮的钉死值（属**本轮判据**）；1020 按 Ari 指令
    #   升到 2.3.3。按铁律 82 收回泛化：只要求语义版本号成型且**不低于 2.3.2**
    #   （防倒退、不设过期日）。「包内 code 与构建配置一致」由 L4 的横幅判据守。
    def _vtL3(s):
        try:
            return tuple(int(x) for x in str(s).split('.'))
        except Exception:
            return (0,)
    check('L3 appVersionName 成型且 >= 2.3.2（code 1020 起改为下界）',
          vname is not None and _vtL3(vname) >= (2, 3, 2), 'versionName=%s' % vname)
    keep = 'XposedCompat.log("[DLsiteSoundFloat] ==== BUILD %s / code %s");' % (vname, vcode)
    check('L4 常开横幅那一行是本轮 code、且 versionName 与 build.gradle 一致（装机前核这行）',
          keep in mod, 'expected: %s' % keep)
    check('L5 常开横幅只有一行（上一轮的常开行已被替换，不是两行并存）',
          not re.search(r'XposedCompat\.log\("\[DLsiteSoundFloat\] '
                        r'==== BUILD [\d.]+ / code (?!%s)\d+"\);'
                        % re.escape(vcode or 'x'), mod))
    # 【code 1015】补一条：「版本号四处」里的第一处 —— appVersionTag 决定 APK 文件名，
    #   本轮就因为漏改它而产出过一个叫 2.3.1 却装着 2.3.2 的包。
    m_tag = re.search(r"def appVersionTag = '([\d.]+)'", gra)
    check('L12 appVersionTag 与 appVersionName 一致（版本号四处之一，决定 APK 文件名）',
          m_tag is not None and vname is not None and m_tag.group(1) == vname,
          'tag=%s name=%s' % (m_tag.group(1) if m_tag else '?', vname))

    seg = re.search(r'==== BUILD %s / code %s （([\s\S]*?)"\);'
                    % (re.escape(vname or ''), re.escape(vcode or 'x')), mod)
    check('L6 调试段里的本轮履历含六段（①②③④⑤⑥）',
          seg is not None and all(k in seg.group(1) for k in
                                  ('①', '②', '③', '④', '⑤', '⑥')))
    check('L7 1007 的履历段仍在（履历追加式，不覆盖）',
          '==== BUILD 2.3.1 / code 1007 （' in mod)
    # ⚠️ 历史段的 versionName 是**当年的** 2.3.1，不随轮次滚动（本轮的 vname 已是 2.3.2）
    seg7 = re.search(r'==== BUILD 2\.3\.1 / code 1007 （([\s\S]*?)"\);', mod)
    check('L8 1007 履历点明用户口径的关键数字与落位口径（256MB / CC 左边 / 会话级默认关）',
          seg7 is not None and all(k in seg7.group(1)
                                   for k in ('256MB', 'CC', '会话级', '默认关')))
    check('L9 code 1006 的历史段仍在（履历追加式，不覆盖）',
          '==== BUILD 2.3.1 / code 1006 （' in mod)
    # 【code 1018】原判据 =「本轮履历点明孤儿 / 清扫 / 作废」——那是**上一轮的**要点词，
    #   属**本轮判据**（铁律 82）：源码层脚本读的是会往前滚的工作区，钉死必假 FAIL。
    #   改为**不钉轮次**的自洽形态：履历段自报的【code NNNN】必须等于横幅 code
    #   ⇒ 「只升了横幅、履历段抄上一轮」照样被抓，且今后不用再改。
    check('L10 本轮履历段自报的【code】与横幅 code 一致（防履历段抄上一轮）',
          seg is not None and ('【code %s' % (vcode or 'x')) in seg.group(1))
    check('L11 履历尾部写明「版本号」变化（与本仓「每段收尾都要交代版本号」的约定一致）',
          seg is not None and '版本号' in seg.group(1))

    # ══════════════ N. 【code 1008】取证件（诊断 + testID 兜底通道）══════════════
    svh8 = norm(svh)
    abh8 = norm(abh)
    repo8 = norm(repo)
    check('N1 视图层：testID 普查件齐（样本表 / 完成位 / 日志上限 / 计数）',
          all(k in svh8 for k in ('sTagSamples', 'sTagCensusDone', 'TAG_CENSUS_MAX',
                                 'TAG_CENSUS_LOG_MAX', 'censusTag(')))
    check('N2 视图层：按名字查宿主 react_test_id（编译期拿不到对方 R）',
          'getIdentifier("react_test_id", "id"' in svh8
          and 'sReactTestIdRes' in svh and 'reactTestIdRes(' in svh)
    check('N3 视图层：普通 tag 优先、R.id 槽兜底（不是只认一条路）',
          'v.getTag()' in svh and 'v.getTag(rid)' in svh)
    check('N4 视图层：认到两个控件各打一条 FOUND（含 tag 原值与矩形）',
          'logFoundOnce' in svh and 'button FOUND tag=' in svh
          and '"CC"' in svh and '"CLOSE"' in svh and 'fmtRect(rect)' in svh)
    check('N5 【code 1012】胶囊门控快照已随按钮移除（无 sLastCacheGateDiag / gateWanted）',
          'sLastCacheGateDiag' not in abh and 'gateWanted' not in abh)
    check('N6 【code 1012】胶囊锚点记忆位（sLastCcRect / sHasLastCcRect）已随按钮移除',
          'sLastCcRect' not in abh and 'sHasLastCcRect' not in abh)
    check('N7 仓库层：本轨缓存可用性翻转时留一行（含 identity）',
          'local cache availability -> ' in repo8 and 'avail != localCacheAvailable' in repo)
    check('N8 【code 1012】按钮层的隐藏早退已删（无 gateWanted / hideCacheButton 分支）',
          'if (!gateWanted) {' not in abh and 'hideCacheButton(' not in abh
          and 'dumpTagSamples(' not in abh)

    # ══════════════ O. 【code 1009】真机根因修复（testID 归一化）══════════════
    check('O1 归一化助手 normalizeTag 在（整体大写 + 短横线/空格折下划线）',
          'private static String normalizeTag(' in svh
          and "sb.append('_');" in svh and 'Character.toUpperCase(c)' in svh)
    check('O2 【根因】两个控件的比对都走「归一化 + 后缀匹配」，不再拿属性名 contains 短横线实值',
          'String key = normalizeTag(tag);' in vc
          and 'key.endsWith(CC_BUTTON_TAG)' in vc
          and 'key.endsWith(CLOSE_BUTTON_TAG)' in vc
          and 'tag.contains(CC_BUTTON_TAG)' not in vc
          and 'tag.contains(CLOSE_BUTTON_TAG)' not in vc)
    check('O3 注释里写下 testID 的**真值**（短横线形态），防下一轮又照属性名写',
          'subtitle-button' in svh and 'full-player-close-button' in svh)
    check('O4 「像顶栏」的 tag 有独立小预算日志（不吃普查名额，普查停了它还在跑）',
          'logToolbarIshTag(tag);' in svh and 'TAG_KEYWORD_LOG_MAX' in svh
          and 'sTagKeywordLogs' in svh)
    check('O5 普查样本上限已抬高（首页/作品页吃不完，进播放页还抄得到）',
          'TAG_CENSUS_MAX = 48' in svh and 'TAG_CENSUS_LOG_MAX = 14' in svh)

    # ══════════════ P. 【code 1010】普查早停（「胶囊仍不出现」的第二个根因）══════════════
    # 真机取证：census 在进播放页**之前**就停了（18:53:01 停 / 18:53:47 才进播放页）。
    # 读源码发现 censusTag 把「日志条数打满」误当成「普查结束」——日志只是打印上限。
    check('P1 【根因】sTagCensusDone 只在**样本收满或时间窗到期**时置真，不再「日志一满就停」',
          'if (full || expired) {' in svh
          and 'sTagCensusLogs >= TAG_CENSUS_LOG_MAX) {' not in svh)
    check('P2 解耦处留下注释（防下一轮又把「打印上限」当「普查终止」）',
          'code 1010 修' in svh)
    check('P3 新增 dumpTagSamples（public static：全量倒样本 + done / logs 位）',
          'public static void dumpTagSamples(String why)' in svh
          and 'tag dump (' in svh
          and 'sTagSamples.size()' in svh)
    check('P4 「像顶栏」关键词放宽到 CLOSE / HEADER，上限升到 12',
          'key.contains("CLOSE")' in svh and 'key.contains("HEADER")' in svh
          and 'TAG_KEYWORD_LOG_MAX = 12' in svh)
    check('P5 【code 1012】dumpTagSamples 的按钮层调用点随胶囊移除（View 层能力保留）',
          'SubtitleViewHook.dumpTagSamples(' not in abh
          and 'public static void dumpTagSamples(String why)' in svh)


    # ══════════════ Q. 【code 1011】簇推断根修 + 对称几何兜底 + 日志精简 ══════════════
    # 真机 20:03（首次跑上 1010）读数：wanted/avail/cfg 三开关全过、close=true（81 次认到）、
    # 而 cluster=false —— 即第三档锚点恒空。静态追因：播放页顶栏之后挂着全屏手势层
    # （tag=player-gesture-area，自 x=0 起），它恰好是旧判据要找的「最后一个可见子」，
    # 于是「最后一个可见子在收起键右侧」永不成立。另：FOUND 那条日志单次会话自重打 81 遍。
    check('Q1 【根因】上溯判据改为「存在可见子整体位于收起键右侧」；旧的 lastVisibleChild 整方法已删',
          'hasVisibleChildRightOf(g, node, closeRect)' in svh
          and 'private static View lastVisibleChild' not in svh)
    check('Q2 右侧按钮簇改由「右侧可见子的外接矩形」给出，太宽才下潜收窄',
          'unionChildrenRightOf' in svh and 'leftmostChildRightOf' in svh
          and 'w = uni[2] - uni[0]' in svh and 'w <= limit' in svh)
    check('Q3 上溯层数上限由写死的 4 放宽到 CLUSTER_ASCEND_MAX（RN 包裹层数不稳定）',
          'CLUSTER_ASCEND_MAX = ' in svh
          and 'for (int i = 0; i < CLUSTER_ASCEND_MAX; i++)' in svh)
    check('Q4 新增第四档「对称几何」兜底（public static，供按钮层调用）',
          'public static int[] symmetricCcRect(ScanResult r, int screenW)' in svh
          and 'int right = screenW - pad;' in svh and 'right - w' in svh)
    check('Q5 兜底依据（收起键左边距与主滑条右边距实测对称）写进注释',
          '左边距' in svh and '右边距' in svh and '对称' in svh)
    check('Q6 【code 1012】第四档调用点随胶囊移除；对称几何能力仍留在 View 层（可复用）',
          'symmetricCcRect(scan, screenW)' not in abh
          and 'public static int[] symmetricCcRect(ScanResult r, int screenW)' in svh)
    check('Q7 【日志精简】FOUND 加整进程去重（首次常开里程碑、之后降诊断级）',
          'logFoundOnce' in svh and 'sCcFoundLogged' in svh and 'sCloseFoundLogged' in svh
          and 'LogGate.debug(TAG, " " + msg)' in svh)
    check('Q8 【日志精简】普查与顶栏 tag 抄写降为诊断级（不再占常开通道）',
          'LogGate.debug(TAG, " [code 1008] tag census' in svh
          and 'LogGate.debug(TAG, " [code 1009] toolbar-ish tag' in svh
          and 'XposedCompat.log(TAG + " [code 1008] tag census' not in svh
          and 'XposedCompat.log(TAG + " [code 1009] toolbar-ish tag' not in svh)
    check('Q9 【日志精简】普查补 60s 时间窗收口（原来「样本满才停」在真机上等于永不停）',
          'TAG_CENSUS_WINDOW_MS = 60000L' in svh and 'sTagCensusStartMs' in svh
          and 'now - sTagCensusStartMs > TAG_CENSUS_WINDOW_MS' in svh)
    check('Q10 负向：本轮不动数据层（缓存口径与仓库层一字未改）',
          'symmetricCcRect' not in repo8 and 'TAG_CENSUS_WINDOW_MS' not in repo8)

    # ══════════════ R. 【code 1012】删手动开关 + 云端优先/本地兜底 + 落盘标签修正 ══════════════
    # 真机两份硬证据：①截图里胶囊跑到左下角；②宿主自己的时长读数按序号是
    # [1252560, 353256, 1252560, 1103664, 658536]ms，而盘上条目按序号记的是
    # [658536, 1103664, 1252560, 1698768]ms —— 整体错位，说明写盘时贴的轨标签不是这一轨的。
    # 根因：宿主取字幕的时机是「用户点击那一刻」，比 currentIndex 更新更早，
    # 而旧口径直接拿「加载那一刻的选择键」当缓存键。
    check('R1 【需求】胶囊整套 UI 已删（常量 / 字段 / 门控 / 落位 / 重绘全清）',
          all(k not in ac for k in ('CACHE_BUTTON_ID', 'ensureCacheButton', 'sCacheButton',
                                    'layoutCacheButton', 'hideCacheButton', 'cacheButtonWanted',
                                    'applyCacheButtonState', 'CACHE_PLACE_DEADZONE_PX')))
    check('R2 仓库层不再有会话级手动开关三件套与即时落盘入口',
          'localCacheMode' not in rc and 'isLocalCacheMode' not in rc
          and 'setLocalCacheMode' not in rc and 'maybeCacheToDisk' not in rc
          and 'tryResumeFromDiskNow' not in rc and 'hasLocalCacheForCurrentTrack' not in rc)
    check('R3 【需求】门控只看配置总闸（不再叠会话级开关）',
          re.search(r'cacheUsable\(\) \{ try \{ return RemoteConfig\.get\(\)\.subtitleCacheEnabled;',
                    rc) is not None)
    check('R4 【需求】新增离线判定（无活动网络 → 直接读盘，不干等裁决窗）',
          'private boolean isOffline()' in rc and 'ConnectivityManager' in rc
          and 'NET_CAPABILITY_INTERNET' in rc)
    # 【code 1034 改写】code 1023 给离线兜底加了「预取池」并列分支 ⇒ 原串多一层括号，
    #   直读语义未变，判据跟新形态（同 verify_1021 的同款改写）。
    check('R5 【需求】换轨入口：在线**不**主动读本地，只有已确认离线才直接读盘',
          'isOffline() && (tryResumeFromDisk(where, newIdentity, newSelection)' in rc)
    check('R6 【需求】云端一直没给字幕 → 回退本地磁盘缓存（锁外，语义等同 JSON 晚到）',
          'no json in grace -> local fallback' in rc
          and re.search(r'if \(noSubtitles && !spurious && tryResumeFromDisk\(', rc) is not None)
    check('R7 【根因】落盘改为「先暂存、等权威轨标签」（不再用加载时刻的选择键）',
          'private void stageCacheToDisk(' in rc and 'private void flushStagedCache(' in rc
          and 'stagedCacheToken' in rc and 'CACHE_FLUSH_FALLBACK_MS = 2500L' in rc)
    check('R8 负向：加载路径的旧落盘标签已消失（cacheTc / cacheIdx / cacheSelection 全无）',
          'cacheTc' not in rc and 'cacheIdx' not in rc and 'cacheSelection' not in rc)
    # 【code 1019】原为 `'INDEX_SCHEMA = 2' in cc` —— 那是我**本轮判据**（1019 的 schema 3
    #   属下一轮判据）。按铁律 82 收回泛化为**下界**：只守「有 schema 版本号、且清毒机制
    #   （>= 2 引入）还在」，防倒退、不设过期日。「当前值恰为几」由 verify_1019_src.py 守。
    _m_schema = re.search(r'INDEX_SCHEMA = (\d+)', cc)
    check('R9 【清毒】缓存索引带 schema 版本且不低于 2（作废已被标错的旧条目）',
          _m_schema is not None and int(_m_schema.group(1)) >= 2,
          '实际 %s' % (_m_schema.group(1) if _m_schema else '缺失'))
    check('R10 【履历锚】1012 的历史段仍在（履历追加式，不覆盖）',
          '==== BUILD 2.3.1 / code 1012 （' in mod)


    # ══════════════ S. 【code 1013】暂存落盘的轨标签改用「JSON 到达那刻的印章」══════════════
    # 真机（2026-10-14 挂代理场）暴露的时序缝隙：
    #   落盘是「先暂存、等权威轨标签」，而兑现时取的是**当时**的当前选择键；
    #   暂存后 2.5s 内若又换到别的轨，兜底兑现就会把 A 轨字幕标成 B 轨 ⇒ 离线读回错字幕。
    # 判据：onTrackChanged 的说明与真机实测都写明「切轨时序号立刻翻、新轨 JSON 约 165ms
    #   后才到」⇒ JSON 到达那刻盖的 cuesOwnerSelection 才是权威轨标签。
    check('S1 【根因】新增字段：暂存那份 JSON 自己的轨标签（volatile long）',
          'private volatile long stagedCacheSelection = 0L;' in rc)
    check('S2 暂存时记下到达那刻的印章（cuesOwnerSelection）',
          'stagedCacheSelection = cuesOwnerSelection;' in rc)
    # 【code 1019】原锚要求声明与三元式连写（`long sel = …`）。1019 把兑现逻辑改成
    #   「先判到达时刻冻结的陈旧旗标 stagedCacheStampStale」，`long sel;` 提前声明，
    #   三元式降级成 else 分支里的 `sel = …` ⇒ 只放宽**声明前缀**为可选，表达式不动。
    check('S3 【核心】兑现时优先用印章，只有它未知才退回当前读数',
          re.search(r'(?:\w+ )?sel = stagedCacheSelection > 0L\s*\?\s*stagedCacheSelection\s*:'
                    r'\s*\(authoritativeSelection > 0L\s*\?\s*authoritativeSelection'
                    r'\s*:\s*observedPlaylistSelection\);', rc) is not None)
    check('S4 兑现后与其余四件一起清掉印章（幂等）',
          'stagedCacheSelection = 0L;' in rc)
    check('S5 【少丢一条】宿主复用自己 JSON 的早退分支也先兑现再返回',
          'boolean resumedFromCache = tryResumeFromCache(' in rc
          and re.search(r'if \(resumedFromCache\) \{\s*return;\s*\}', rc) is not None)
    check('S6 负向：兑现处不再有无条件用 authoritativeSelection 的旧形态',
          re.search(r'long sel = authoritativeSelection > 0L', rc) is None)
    check('S7 【历史锚】1012 的落盘机制仍在（stageCacheToDisk + flushStagedCache + 2500ms 兜底）',
          'private void stageCacheToDisk(' in rc and 'private void flushStagedCache(' in rc
          and 'CACHE_FLUSH_FALLBACK_MS = 2500L' in rc)
    check('S8 【历史锚】1013 的常开横幅段仍在（履历追加式，不覆盖）',
          '==== BUILD 2.3.1 / code 1013 （' in mod)
    # ══════════════ T. 【code 1014】云端优先的窗口分级 + 兜底钥匙 ══════════════
    # 真机（2026-10-14 10:24:32 关代理后重开宿主，RJ01609334 五音轨）：
    #   10:25:07 序号零→一，lastJson=never、cues=0 ⇒ 窗 3000ms ⇒ 10:25:10 磁盘命中 ✅
    #   10:25:22 序号一→二、10:25:25 序号二→三，手上握着上一轨的 148 条 cues
    #     ⇒ 走 15000ms 长窗 ⇒ 盘上明明有本轨缓存却干等满 15s（日志 10:25:30 导出，
    #       裁决点 10:25:37 尚未到）⇒ Ari 体感「本地字幕用不了」。
    # 两个破口：① 窗口分级漏了「盘上有无本轨缓存」这一档；
    #           ② 兜底读盘用的是全局观测键（重建列表/快切时会指到别的轨）。
    check('T1 【根因·破口一】窗口分级：手上有 cues **且**盘上无本轨缓存，才用 15s 长窗',
          re.search(r'grace = \(cueCount > 0 && !diskFallbackReady\)\s*\n?\s*'
                    r'\?\s*NO_SUBTITLE_GRACE_MS_CACHED\s*:\s*NO_SUBTITLE_GRACE_MS;', rc)
          is not None)
    check('T2 【新增】hasDiskCacheFor：纯内存索引查询（无磁盘 IO）',
          re.search(r'private boolean hasDiskCacheFor\(long identity, long selection\) \{',
                    rc) is not None
          and 'SubtitleCache.get().has(identity, sel)' in rc
          and 'readFile' not in rc[rc.index('private boolean hasDiskCacheFor('):
                                      rc.index('private boolean hasDiskCacheFor(') + 600])
    check('T3 换轨入口在挂起之前探一次盘（决定等多久）',
          'final boolean diskFallbackReady = hasDiskCacheFor(newIdentity, newSelection);' in rc)
    check('T4 【根因·破口二】新增两个字段：本次换轨的目标键（identity + selection）',
          'private volatile long pendingTrackIdentity = 0L;' in rc
          and 'private volatile long pendingTrackSelection = 0L;' in rc)
    check('T5 换轨入口记下目标键（与 pendingToken 同处赋值）',
          'pendingTrackIdentity = newIdentity;' in rc
          and 'pendingTrackSelection = newSelection;' in rc)
    check('T6 【核心】兜底读盘优先用目标键，全局观测键只作退路',
          re.search(r'pendingTrackIdentity != 0L \? pendingTrackIdentity\s*\n?\s*'
                    r': observedPlaylistIdentity,', rc) is not None
          and re.search(r'pendingTrackSelection != 0L \? pendingTrackSelection\s*\n?\s*'
                        r': observedPlaylistSelection\)\)', rc) is not None)
    check('T7 负向：兜底处不再有无条件传观测键的旧形态',
          re.search(r'tryResumeFromDisk\("no json in grace -> local fallback",\s*\n?\s*'
                    r'observedPlaylistIdentity, observedPlaylistSelection\)', rc) is None)
    # 【code 1019】同 R9：原为 `'INDEX_SCHEMA = 2' in cc`。T8 当年的「维持 2」是
    #   1014 那一轮的**对比口径**（1014 只改标签来源与等待时长），钉在工作区上必假 FAIL。
    #   收回泛化为下界 `>= 2`（1019 起 schema 升至 3，结构作废历史错标条目）。
    _m_schema2 = re.search(r'INDEX_SCHEMA = (\d+)', cc)
    check('T8 索引 schema 声明存在且不低于 2（1019 起升至 3，不再钉死）',
          _m_schema2 is not None and int(_m_schema2.group(1)) >= 2,
          '实际 %s' % (_m_schema2.group(1) if _m_schema2 else '缺失'))
    # 【code 1034 改写】同 R5：1023 起离线直读带预取并列括号。
    check('T9 云端优先不变：换轨入口仍**没有**无条件读盘（只在已确认离线时直接读）',
          re.search(r'if \(isOffline\(\) && \(tryResumeFromDisk\(where, newIdentity, newSelection\)',
                    rc) is not None)
    check('T10 【历史锚】1014 的常开横幅段仍在（履历追加式，不覆盖）',
          '==== BUILD 2.3.1 / code 1014 （' in mod)

    # ══════════════ U. 【code 1015 / 2.3.2】「实验性功能」卡片 ══════════════
    #    Ari 五项需求：卡片默认关 + 连点状态卡五次解锁 + 版本升级后保持 + 摆在
    #    「液态玻璃效果调整」与「其他」之间 + 字幕缓存搬入并改名 + 总开关关闭时
    #    下属功能全关 / 开关置灰 / 相关缓存清除。
    check('U1 【配置键】新增 K_EXPERIMENTAL_ENABLED = "experimental_enabled"',
          'public static final String K_EXPERIMENTAL_ENABLED = "experimental_enabled";' in fc)
    check('U2 【字段】experimentalEnabled 默认 **false**（「默认关闭」是需求第一句）',
          'public boolean experimentalEnabled = false;' in fc)
    check('U3 【不变式】clamp 里「总闸关 ⇒ 卡内子功能一律关」（任何读配置路径都遵守）',
          re.search(r'if \(!experimentalEnabled\) \{\s*subtitleCacheEnabled = false;\s*\}', fc)
          is not None)
    check('U4 配置键七处同步齐全（copy / sameAs / toJson / fromJson / writePrefs / readPrefs / toString）',
          all(k in fc for k in (
              'c.experimentalEnabled = experimentalEnabled;',
              '&& experimentalEnabled == o.experimentalEnabled',
              'o.put(K_EXPERIMENTAL_ENABLED, experimentalEnabled);',
              'c.experimentalEnabled = o.optBoolean(K_EXPERIMENTAL_ENABLED,',
              'e.putBoolean(K_EXPERIMENTAL_ENABLED, experimentalEnabled);',
              'c.experimentalEnabled = p.getBoolean(K_EXPERIMENTAL_ENABLED,',
              '+ " experimental=" + experimentalEnabled;')))
    check('U5 【布局】新增 title / card / group 三个实验性功能视图 id',
          all(k in xc for k in ('@+id/title_experimental', '@+id/card_experimental',
                                '@+id/group_experimental')))
    check('U6 【落点】buildRows 顺序 = 液态玻璃 → 实验性功能 → 其他（需求第二条）',
          re.search(r'buildLiquidGlassGroup\(mGroupLiquidGlass\);\s*\}'
                    r'[\s\S]{0,400}?buildExperimentalGroup\(mGroupExperimental\);'
                    r'[\s\S]{0,400}?buildMiscGroup\(mGroupMisc\);', sc) is not None)
    check('U7 【搬运】「其他」卡片里已无字幕缓存整组（buildMiscGroup 内该调用为 0）',
          method_body(sett, r'private void buildMiscGroup\(').count('buildSubtitleCacheRow') == 0)
    check('U8 【搬运】字幕缓存整组改由实验卡调用（buildExperimentalGroup 内确实调了）',
          'buildSubtitleCacheRow(parent);'
          in method_body(sett, r'private void buildExperimentalGroup\('))
    check('U9 【解锁】连点五次：常量 5 次 + 3 秒窗 + 状态卡挂上点击入口',
          'STATUS_TAP_REQUIRED = 5' in sc and 'STATUS_TAP_WINDOW_MS = 3000L' in sc
          and 'mStatusCard.setOnClickListener(v -> onStatusCardClicked());' in sc)
    check('U10 【解锁】超窗即清零重数（免得把偶然点击累计成解锁）',
          re.search(r'now - mStatusTapLastMs > STATUS_TAP_WINDOW_MS\) \{\s*'
                    r'mStatusTapCount = 0;', sc) is not None)
    check('U11 【需求4①】关闭总闸 ⇒ 卡内子功能关掉（草稿当场置假）',
          re.search(r'if \(!enabled\) \{[\s\S]{0,240}?mDraft.subtitleCacheEnabled = false;',
                    sc) is not None)
    check('U12 【需求4②】子开关置灰（setEnabled + 整行 alpha）',
          'mRowSubtitleCache.sw.setEnabled(enabled);' in sc
          and re.search(r'mRowSubtitleCache.root.setAlpha\(enabled \? 1f : 0\.45f\);',
                        sc) is not None)
    check('U13 【需求4③】关闭总闸 ⇒ 清除相关缓存（走既有显式广播 + 待弹提示）',
          'ConfigBus.sendCacheClear(this);' in sc and 'mPendingClearToast = true;' in sc)
    check('U14 【需求2/4】显隐判据 = draft || saved（草稿解锁立刻可见、保存后按配置收敛）',
          'boolean show = mDraft.experimentalEnabled || mSaved.experimentalEnabled;' in sc)
    check('U15 【需求3】「字幕缓存功能」改名「字幕缓存」（简中 + 繁中都改了）',
          'SUBTITLE_CACHE("字幕缓存", "字幕快取", "Subtitle cache")' in strs)
    check('U16 【文案】实验性功能三语齐全（标题 / 总开关 / 解锁提示 / 已开启提示）',
          all(k in strs for k in ('GROUP_EXPERIMENTAL("实验性功能", "實驗性功能", "Experimental")',
                                  'EXPERIMENTAL_MASTER("启用实验性功能"',
                                  'EXPERIMENTAL_UNLOCKED(',
                                  'EXPERIMENTAL_ALREADY_ON(')))
    check('U17 【code 1016 / 需求 2】总开关下方的说明小字已**整段删除**'
          '（连带文案枚举一起摘掉，不留死代码）',
          'EXPERIMENTAL_MASTER_HINT' not in strs
          and 'EXPERIMENTAL_MASTER_HINT' not in sc)
    # 【code 1018】原为「appVersionCode = 1017」的钉死值 —— 本轮判据，每轮必假 FAIL。
    #   按铁律 82 收回泛化为**下界**（口径同 L1 的 `>= 1007`）：防倒退、不设过期日。
    #   「包内 code 与构建配置一致」由 L4 的横幅判据守，这里只兜住版本号口径。
    # 【code 1020】同 L3：versionName 的钉死值也随轮次前进（1020 起是 2.3.3）⇒
    #   这里只守 code 的**下界**，versionName 交给 L3 判（避免两处重复钉同一个值）。
    check('U18 【版本】appVersionCode 不低于本轮（下界 1020）',
          bool(vname) and vcode is not None and vcode.isdigit() and int(vcode) >= 1020)
    check('U19 负向：1014 的那行常开横幅已消失（常量池里不再有 2.3.1 / code 1014 的常开行）',
          'XposedCompat.log("[DLsiteSoundFloat] ==== BUILD 2.3.1 / code 1014");' not in mod)

    # ══════════════ V. 【code 1016】设置页五条（底色 / 小字 / 提示 / 激活口径）══════════════
    #    Ari 五条：①实验卡底色与其他卡片一致；②总开关下方小字全删；
    #    ③缓存说明改口径；④已开启再点状态卡给提示；⑤授权即视为模块已激活。
    check('V1 【需求1】实验卡进入卡片底色白名单（refreshCardTints 逐个 tint 的那份名单）',
          'tintCard(findViewById(R.id.card_experimental), cardBg);'
          in method_body(sett, r'private void refreshCardTints\('))
    check('V2 【需求2】总开关之后**直接**接卡内子功能（方法体里不再出现任何 TextView）',
          re.search(r'addSwitchRow\(parent, Strings.EXPERIMENTAL_MASTER,[\s\S]{0,600}?'
                    r'buildSubtitleCacheRow\(parent\);',
                    method_body(sett, r'private void buildExperimentalGroup\(')) is not None
          and 'TextView' not in method_body(sett, r'private void buildExperimentalGroup\('))
    # 【code 1034 改写】英文句被 code 1031 合法压缩（三行压一行半，Ari 反馈太长）；
    #   简 / 繁两语未动。英文锚跟 1031 形态。
    check('V3 【需求3】缓存说明改成新口径（三语齐全：简 / 繁 / 英）',
          'SUBTITLE_CACHE_HINT("播放过的音轨字幕会自动缓存，超出储存上限后按最早缓存顺序自动清除"' in strs
          and re.search(r'SUBTITLE_CACHE_HINT\([\s\S]{0,600}?播放過的音軌字幕會自動快取', strs) is not None
          and re.search(r'SUBTITLE_CACHE_HINT\([\s\S]{0,600}?oldest entries are removed first', strs) is not None)
    check('V4 【需求3 负向】旧口径（「断网 / 飞行模式下也能显示」+ 写死的 256MB）已从文案里去掉',
          '断网 / 飞行模式下也能显示' not in strs
          and '上限 256MB' not in strs)
    check('V5 【需求4】已打开实验性功能时再点状态卡 ⇒ 直接弹提示（不再静默 return）',
          re.search(r'if \(mDraft.experimentalEnabled\) \{[\s\S]{0,240}?'
                    r'toast\(Strings.EXPERIMENTAL_ALREADY_ON.get\(mLang\)\);\s*\n\s*return;',
                    method_body(sett, r'private void onStatusCardClicked\(')) is not None
          and 'mStatusTapCount = 0;'
              in method_body(sett, r'private void onStatusCardClicked\('))
    check('V6 【需求4】提示文案三语齐全',
          'EXPERIMENTAL_ALREADY_ON("你已经打开实验性功能，无需进行此操作"' in strs
          and re.search(r'EXPERIMENTAL_ALREADY_ON\([\s\S]{0,400}?你已經開啟實驗性功能', strs) is not None
          and re.search(r'EXPERIMENTAL_ALREADY_ON\([\s\S]{0,400}?already on', strs) is not None)
    check('V7 【需求5】激活判定 = **只看授权位**（active = hostAuthorized）',
          re.search(r'boolean active = hostAuthorized;',
                    method_body(sett, r'private void renderStatusCard\(')) is not None)
    check('V8 【需求5】授权判定纳入持久化镜像 mHostScopeSeen（跨页面重开 / 跨进程重启都认）',
          re.search(r'boolean hostAuthorized = !probing\s*\n?\s*'
                    r'&& \(mProbe.hostAuthorized \|\| mHostSeenOnce \|\| mHostScopeSeen\);',
                    sc) is not None)
    check('V9 【需求5】「曾确认授权」三个环节齐全：常量键 + 进页面读 + 探到就落盘',
          'PREF_HOST_SCOPE_SEEN = "host_scope_seen"' in sc
          and 'mHostScopeSeen = readHostScopeSeen();' in sc
          and 'private boolean readHostScopeSeen()' in sc
          and 'private void markHostScopeSeen()' in sc
          and 'markHostScopeSeen();' in method_body(sett, r'private void startProbe\('))
    check('V10 【需求5 负向】原「DLsiteSound 未运行」中间态分支已整条删除',
          'hostNotRunning' not in sc)

    # ══════════════ W. 【code 1017】缓存孤儿清扫（索引作废即回收）══════════════
    #    Ari 报「更新后 26 轨缓存没了」，真机日志证明与升级无关（是设置页的清空入口被
    #    显式触发，且发生在 code 1014 上）；顺手挖出的真问题是：索引作废那条分支
    #    只丢索引、不删文件 ⇒ 孤儿永久占空间（totalBytes 从 0 重算，LRU 永远选不中）。
    check('W1 【code 1017】schema 不匹配分支不再空手返回：改走 discardIndexAndSweepLocked',
          'discardIndexAndSweepLocked();' in cc
          and 'index schema mismatch -> rebuild as empty' not in cc
          and re.search(r'!= INDEX_SCHEMA\) \{[\s\S]{0,900}?discardIndexAndSweepLocked\(\);',
                        cc) is not None)
    check('W2 【code 1017】新增 discardIndexAndSweepLocked：先清扫、再重写空索引（作废即收口）',
          'private void discardIndexAndSweepLocked()' in cc
          and 'sweepOrphansLocked();' in method_body(cc, r'private void discardIndexAndSweepLocked\(')
          and 'persistIndexLocked();' in method_body(cc, r'private void discardIndexAndSweepLocked\('))
    check('W3 【code 1017】新增 sweepOrphansLocked：列目录 + 只删 .json + 白名单保底 index.json',
          'private int sweepOrphansLocked()' in cc
          and 'dir.listFiles()' in cc
          and 'name.endsWith(".json")' in cc
          and 'keep.add(INDEX_NAME);' in cc)
    check('W4 【code 1017】白名单逐条收索引引用的文件名（不可能删到可命中的缓存）',
          'keep.add(e.file);' in cc)
    check('W5 【code 1017】init 读完索引后补一次孤儿清扫（开机顺手回收历史遗留与半成品）',
          'sweepOrphansLocked();' in method_body(cc, r'public void init\('))
    check('W6 【code 1017 负向】清扫绝不递归删目录（只删文件，不动别的）',
          'deleteRecursively' not in cc and 'rmtree' not in cc)
    # ⚠️ 这条查的是**注释**：必须用「未剥注释的原始源码」`cache`，
    #    用 `cc`（= norm(strip_comments(cache))）永远假 FAIL。
    check('W7 【code 1017】索引常量的告警注释在位（推进版本号 = 整批丢弃 + 删文件）',
          re.search(r'本值一旦推进[\s\S]{0,200}?整批丢弃', cache) is not None)
    check('W8 【code 1017】导入齐备：HashSet 与 Set（清扫白名单用）',
          'import java.util.HashSet;' in cc and 'import java.util.Set;' in cc)
    # 【code 1018】同 U18：钉死值 1017 属本轮判据，收回泛化为下界。
    # 【code 1020】同 L3：versionName 的钉死值也随轮次前进（1020 起是 2.3.3）⇒
    #   这里只守 code 的**下界**，versionName 交给 L3 判（避免两处重复钉同一个值）。
    check('W9 【版本】appVersionCode 不低于本轮（下界 1020）',
          bool(vname) and vcode is not None and vcode.isdigit() and int(vcode) >= 1020)
    # 【code 1018】同 L10：上一轮的要点词不再复用，改判「履历段自报 code == 横幅 code」。
    check('W10 本轮履历段自报的【code】与横幅 code 一致（同 L10，两处各守一半）',
          seg is not None and ('【code %s' % (vcode or 'x')) in seg.group(1))

    # ══════════════ M. 负向锚（横幅纪律 + 不越界）══════════════
    check('M1 常开横幅里不写具体文件名 / 被删标识符（横幅纪律，防负向锚自伤）',
          all(ch not in keep for ch in
              ('SubtitleCache', 'ConfigBus', 'ActivityButtonHook', 'hasLocalCacheForCurrentTrack')))
    if seg is not None:
        body = seg.group(1)
        check('M2 本轮履历段里不出现引号/反斜杠（横幅校验对象是纯文本段）',
              '"' not in body and '\\' not in body and '`' not in body)
    else:
        check('M2 本轮履历段里不出现引号/反斜杠（横幅校验对象是纯文本段）', False,
              '未取到履历段')
    check('M3 没有把「清缓存」写成删整个缓存目录（只删条目，不动别的文件）',
          'deleteRecursively' not in cc and 'rmtree' not in cc)

    # ══════════════ 报告 ══════════════
    print()
    print('=' * 96)
    print('code 1007~1018 —— 源码层验证（字幕离线缓存 + 取证件 + 根因修复 + 自动来源 + 落盘标签 + 兜底窗口 + 实验性功能 + 设置页细化 + 孤儿清扫 + 架构三项）')
    print('=' * 96)
    for label, ok, detail in rows:
        print('  %s %s%s' % ('✓' if ok else '✗', label, ('   → ' + detail) if detail else ''))
    print()
    print('  断言 %d 项' % len(rows))
    if fails:
        print('FAIL %d/%d' % (fails, len(rows)))
        return 1
    print('PASS %d/%d' % (len(rows), len(rows)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
