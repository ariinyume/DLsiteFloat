/*
 * DLsiteSound Floating Subtitle - Xposed module for DLsite Sound
 * Copyright (C) 2026 ariinyume
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you can redistribute it and/or modify it under
 * the terms of the GNU General Public License as published by the Free Software
 * Foundation, either version 3 of the License, or (at your option) any later
 * version.
 *
 * This program is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along with
 * this program. If not, see <https://www.gnu.org/licenses/>.
 */
package io.github.ariinyume.dlsitesoundfloat.config;

/**
 * 跨进程广播契约的**唯一字符串真源**。
 *
 * <p>【code 995】本模块有<b>三个进程</b>在说话（设置页 / 宿主 DLsiteSound / SystemUI），
 * 靠隐式广播串起来。改动 action 或 extra 的字符串值 = 静默断链：广播发出去没人收，
 * 且**不报错、不崩溃**，只会表现为「配置不生效」「按钮不亮」这类极难定位的症状。
 *
 * <p>此前这 20 个字面量散在 {@code ConfigBus}（8 个）与 {@code StatusBarSubtitleBridge}
 * （12 个）两处，各写一遍字符串、彼此没有交叉引用。本类把它们收拢成单点定义，
 * 两个旧类保留同名 {@code public static final} 作<b>转发壳</b> ——
 * 于是：① 两处字面量彻底合并；② 现有约 105 处 {@code ConfigBus.XXX} /
 * {@code StatusBarSubtitleBridge.XXX} 调用点<b>一行都不用改</b>；③ 老代码的可读性不变。
 *
 * <h3>🚫 铁律</h3>
 * <ul>
 *   <li><b>只许加，不许改值。</b>已发版版本（2.2.x）的 action 已固化在 App 与被注入进程里，
 *       改一个字符，旧 App 发的新广播与新 App 收的旧广播就再也对不上。
 *       确需换协议时<b>加新 action</b>（{@code PROTOCOL_VERSION} +1），别改旧的。</li>
 *   <li><b>三处包前缀必须一致。</b>全部形如
 *       {@code io.github.ariinyume.dlsitesoundfloat.action.*} —— 跟 applicationId 同源。
 *       历史上 code 950 换包名（{@code com.sena.*} → {@code io.github.ariinyume.*}）时
 *       这串前缀跟着改过一次，五条 action 全部同步，两端一致。</li>
 *   <li><b>改完必须跑 {@code tools/verify_protocol.py}</b>：它比对 dex 里的字符串常量，
 *       确认「源码声明值 == 打进包的值」—— 防的是「改了常量但没编进包」这类假绿。</li>
 * </ul>
 */
public final class Protocol {

    /**
     * 契约版本号。**只在新增/废弃 action 时 +1**，改任何其他常量不动它。
     *
     * <p>作用：握手时带上，双方版本不一致打警告 —— 跨进程链路曾经因为
     * 「一边 code 951、一边 code 950」而出现握手告警（见 CHANGELOG code 951 末尾）。
     *
     * <p>【code 1007】1 → 2：新增字幕缓存清理 / 统计三条 action（见下）。
     */
    public static final int PROTOCOL_VERSION = 2;

    /** 广播 action 的统一前缀。跟 {@code applicationId} 同源，改包名时必须同步。 */
    public static final String ACTION_PREFIX = "io.github.ariinyume.dlsitesoundfloat.action.";

    // ── 设置页 → 各被注入进程 ──────────────────────────────────────────

    /** 设置页 → 各被注入进程：配置已变更，请重载。 */
    public static final String ACTION_CONFIG_CHANGED = ACTION_PREFIX + "CONFIG_CHANGED";

    /** 设置页 → SystemUI 进程：请求重启系统界面（模块收到后自杀，系统自动拉起）。 */
    public static final String ACTION_RESTART_SYSUI = ACTION_PREFIX + "RESTART_SYSUI";

    /** 设置页 → DLsiteSound 进程：作用域探测。 */
    public static final String ACTION_HOST_PING = ACTION_PREFIX + "SCOPE_HOST_PING";

    /** DLsiteSound 进程 → 设置页：探测应答。 */
    public static final String ACTION_HOST_PONG = ACTION_PREFIX + "SCOPE_HOST_PONG";

    // ── App → SystemUI：状态栏字幕数据通道 ─────────────────────────────

    /** 当前字幕行（空串 = 清除/隐藏）+ 行时长 + 播放态 + 开关态。 */
    public static final String ACTION_LINE = ACTION_PREFIX + "STATUSBAR_SUBTITLE_LINE";

    /** 状态栏字幕开关状态（由悬浮窗按钮长按 1s 翻转）。 */
    public static final String ACTION_ENABLED = ACTION_PREFIX + "STATUSBAR_SUBTITLE_ENABLED";

    /** 反向通道 **SystemUI → App**：请求关闭状态栏字幕（双击状态栏字幕位置）。 */
    public static final String ACTION_DISMISS_REQUEST =
            ACTION_PREFIX + "STATUSBAR_SUBTITLE_DISMISS_REQUEST";

    // ── 作用域探测（App ↔ SystemUI）────────────────────────────────────

    /** 作用域探测 **App → SystemUI**。 */
    public static final String ACTION_SCOPE_PING = ACTION_PREFIX + "STATUSBAR_SCOPE_PING";

    /** 作用域探测应答 **SystemUI → App**。 */
    public static final String ACTION_SCOPE_PONG = ACTION_PREFIX + "STATUSBAR_SCOPE_PONG";

    // ── 【code 1007】字幕缓存（设置页 ↔ DLsiteSound 进程）────────────────
    //
    // 为什么必须走广播：缓存落在**宿主 App 的私有目录**
    // （Android/data/<宿主包名>/files/subtitle_cache/），设置页进程受 SELinux 限制读不到
    // 那个目录，SystemUI 同理。所以「清空缓存」与「查缓存占用」都只能由宿主进程执行。

    /** 设置页 → DLsiteSound 进程：清空**已缓存**的字幕正文（{@code subtitle_cache/}）。 */
    public static final String ACTION_SUBTITLE_CACHE_CLEAR = ACTION_PREFIX + "SUBTITLE_CACHE_CLEAR";

    /**
     * 【code 1030】设置页 → DLsiteSound 进程：清空**预取**的字幕（作品文件树 + 抓下来的 json）。
     *
     * <p>与 {@link #ACTION_SUBTITLE_CACHE_CLEAR} 是**两个独立动作**（Ari 要求拆开）：
     * 前者删的是「播放过的音轨正文」，后者删的是「为了换轨不卡而提前抓的作品文件树」。
     * 两者落在同一个父目录下的不同子项，删一个不会连带另一个。
     */
    public static final String ACTION_SUBTITLE_PREFETCH_CLEAR =
            ACTION_PREFIX + "SUBTITLE_PREFETCH_CLEAR";

    /** 设置页 → DLsiteSound 进程：查询字幕缓存占用。 */
    public static final String ACTION_SUBTITLE_CACHE_STATS_REQ =
            ACTION_PREFIX + "SUBTITLE_CACHE_STATS_REQ";

    /** DLsiteSound 进程 → 设置页：字幕缓存占用应答（{@link #EXTRA_CACHE_COUNT}/{@link #EXTRA_CACHE_BYTES}）。 */
    public static final String ACTION_SUBTITLE_CACHE_STATS = ACTION_PREFIX + "SUBTITLE_CACHE_STATS";

    // ── 【code 1046】宿主字体描述（设置页 ↔ DLsiteSound 进程）─────────────
    //
    // 为什么要有这条：预览窗跑在**模块自己的进程**里，悬浮窗跑在**宿主进程**里。
    // 宿主里若装了「全局改字体」类模块（MoriMod F4 就是），悬浮窗那行字幕的字体
    // 是它 hook {@code Paint#setTypeface} 换出来的 —— 而预览进程没有这个钩子，
    // 只能画出 ROM 默认字体 ⇒「预览的字体 ≠ 悬浮窗真正的字体」。
    //
    // 解法：宿主进程把它**真正解析出来的那份字体**读出来，用广播递给设置页。
    // 字体文件只有宿主 uid 读得到（ MoriMod 缓存在宿主 filesDir 下），所以
    // 「描述」走一条广播，「字节」分片走 N 条广播（Binder 单事务 ~1MB 上限）。

    /** 【code 1046】设置页 → DLsiteSound 进程：请把「悬浮窗真正用的字体」报上来。 */
    public static final String ACTION_HOST_FONT_REQ = ACTION_PREFIX + "HOST_FONT_REQ";

    /**
     * 【code 1046】DLsiteSound 进程 → 设置页：字体**描述**应答（不带字节）。
     *
     * <p>{@link #EXTRA_FONT_DESC} 形如：
     * <ul>
     *   <li>{@code file:/system/fonts/xxx.ttf} —— 系统字体文件，设置页直接读；</li>
     *   <li>{@code family:sans-serif} —— 系统字体族，设置页 {@code Typeface.create}；</li>
     *   <li>{@code user:fonts/xxx.ttf} —— 用户导入的字体，字节随后分片送到；</li>
     *   <li>空串 —— 宿主侧没有全局字体替换（或拿不到），预览维持现状。</li>
     * </ul>
     */
    public static final String ACTION_HOST_FONT_INFO = ACTION_PREFIX + "HOST_FONT_INFO";

    /** 【code 1046】DLsiteSound 进程 → 设置页：字体文件**分片**（{@code user:*} 时才有）。 */
    public static final String ACTION_HOST_FONT_CHUNK = ACTION_PREFIX + "HOST_FONT_CHUNK";

    /** 【code 1046】字体描述串（见 {@link #ACTION_HOST_FONT_INFO}）。 */
    public static final String EXTRA_FONT_DESC = "font_desc";

    /** 【code 1046】字体文件的建议文件名（设置页落地用，含扩展名）。 */
    public static final String EXTRA_FONT_NAME = "font_name";

    /** 【code 1046】本次传输的请求号（设置页用它丢弃上一轮残片）。 */
    public static final String EXTRA_FONT_RID = "font_rid";

    /** 【code 1046】分片序号（0 起）。 */
    public static final String EXTRA_FONT_SEQ = "font_seq";

    /** 【code 1046】分片总数（0 = 否定应答，别等了）。 */
    public static final String EXTRA_FONT_N = "font_n";

    /** 【code 1046】分片字节。 */
    public static final String EXTRA_FONT_DATA = "font_data";

    // ── EXTRA key ───────────────────────────────────────────────────────

    /** PONG 携带的模块构建号（与 {@code BuildConfig.VERSION_CODE} 同源）。 */
    public static final String EXTRA_BUILD = "build";

    /** PONG 携带的进程标识，取值 {@link #TAG_HOST} / {@link #TAG_SYSTEMUI}。 */
    public static final String EXTRA_TAG = "tag";

    /** 宿主 PONG 携带的「DLsiteSound 当前真的在用」标志（boolean）。 */
    public static final String EXTRA_HOST_ALIVE = "host_alive";

    /** {@link #ACTION_CONFIG_CHANGED} 携带的完整配置 JSON。 */
    public static final String EXTRA_CONFIG_JSON = "config_json";

    /** 关闭原因（仅用于日志/取证）。 */
    public static final String EXTRA_DISMISS_REASON = "reason";

    /** 当前字幕行文本。 */
    public static final String EXTRA_LINE = "line";

    /** 开关状态（boolean）。 */
    public static final String EXTRA_ENABLED = "enabled";

    /** 当前字幕行的播放时长（毫秒）。0 = 未知，状态栏侧退回默认时长。 */
    public static final String EXTRA_DURATION_MS = "duration_ms";

    /** 当前是否在播放（boolean）。false 时 line 一定是空串。 */
    public static final String EXTRA_PLAYING = "playing";

    /** PONG 携带的 SystemUI 侧构建号（见 {@link #ACTION_SCOPE_PONG}）。 */
    public static final String EXTRA_PONG_BUILD = "pong_build";

    /** 【code 1007】字幕缓存条目数（{@link #ACTION_SUBTITLE_CACHE_STATS} 携带，int）。 */
    public static final String EXTRA_CACHE_COUNT = "cache_count";

    /** 【code 1007】字幕缓存占用字节数（{@link #ACTION_SUBTITLE_CACHE_STATS} 携带，long）。 */
    public static final String EXTRA_CACHE_BYTES = "cache_bytes";

    /**
     * 【code 1024 / P1-8】本进程启动以来**按强键命中**的次数（{@link #ACTION_SUBTITLE_CACHE_STATS} 携带，int）。
     *
     * <p>与 {@link #EXTRA_CACHE_MISSES} 一起构成设置页那行「命中 18/24 轨」。
     * 两个都**含歧义放弃**（作品维强约束下主动放弃也算一次未命中），
     * 所以「命中/总请求」能真实反映离线可播的比例。
     */
    public static final String EXTRA_CACHE_HITS = "cache_hits";

    /** 【code 1024 / P1-8】本进程启动以来没命中的次数（同上，int）。 */
    public static final String EXTRA_CACHE_MISSES = "cache_misses";

    /** 【code 1024 / P1-8】已预取几部作品（作品文件树抓到过、字幕已落本地；int）。 */
    public static final String EXTRA_PREFETCH_WORKS = "prefetch_works";

    /** 【code 1024 / P1-8】已预取多少条轨（同上，int）。 */
    public static final String EXTRA_PREFETCH_TRACKS = "prefetch_tracks";

    /**
     * 【code 1024 / P1-5】宿主上屏行与自算行「对得上」的样本数（int）。
     *
     * <p>口径见 {@code hook.HostLineSync}：两侧都非空才算一次样本，交集非空算对上。
     * 这三个数只用于观测（本站不做「宿主行优先」），攒够数据再决定要不要接管渲染。
     */
    public static final String EXTRA_LINE_MATCHED = "line_matched";

    /** 【code 1024 / P1-5】两侧都非空、却一句都没对上的样本数（int）。 */
    public static final String EXTRA_LINE_MISMATCHED = "line_mismatched";

    /** 【code 1024 / P1-5】总共比对了多少次（int）。 */
    public static final String EXTRA_LINE_SAMPLES = "line_samples";

    // ── 标识与包名 ──────────────────────────────────────────────────────

    /** {@link #EXTRA_TAG} 的宿主取值。 */
    public static final String TAG_HOST = "host";

    /** {@link #EXTRA_TAG} 的 SystemUI 取值。 */
    public static final String TAG_SYSTEMUI = "systemui";

    /** 宿主包名（LSPosed 作用域声明之一）。 */
    public static final String HOST_PKG = "jp.co.eisys.dlsitesound";

    /** SystemUI 包名（LSPosed 作用域声明之一）。 */
    public static final String SYSTEMUI_PKG = "com.android.systemui";

    private Protocol() {
    }

    /**
     * 契约自检：确认所有 action 都带统一前缀、8 个 action 互不重复。
     *
     * <p>供构建期/启动期调用。返回值 null 表示通过，否则是首个问题的描述。
     * 写成纯函数（不依赖 {@code android.*}）⇒ 可以在 JUnit 里直接跑，见 {@code ProtocolTest}。
     */
    public static String selfCheck() {
        String[] actions = {
                ACTION_CONFIG_CHANGED, ACTION_RESTART_SYSUI,
                ACTION_HOST_PING, ACTION_HOST_PONG,
                ACTION_LINE, ACTION_ENABLED, ACTION_DISMISS_REQUEST,
                ACTION_SCOPE_PING, ACTION_SCOPE_PONG,
                ACTION_SUBTITLE_CACHE_CLEAR, ACTION_SUBTITLE_CACHE_STATS_REQ,
                ACTION_SUBTITLE_CACHE_STATS, ACTION_SUBTITLE_PREFETCH_CLEAR,
                ACTION_HOST_FONT_REQ, ACTION_HOST_FONT_INFO, ACTION_HOST_FONT_CHUNK,
        };
        java.util.Set<String> seen = new java.util.HashSet<>();
        for (String a : actions) {
            if (a == null || !a.startsWith(ACTION_PREFIX)) {
                return "action 缺统一前缀: " + a;
            }
            if (!seen.add(a)) {
                return "action 重复: " + a;
            }
        }
        // extra key 重复检查（重复会让两个语义不同的负载互相覆盖）
        String[] extras = {
                EXTRA_BUILD, EXTRA_TAG, EXTRA_HOST_ALIVE, EXTRA_CONFIG_JSON,
                EXTRA_DISMISS_REASON, EXTRA_LINE, EXTRA_ENABLED,
                EXTRA_DURATION_MS, EXTRA_PLAYING, EXTRA_PONG_BUILD,
                EXTRA_CACHE_COUNT, EXTRA_CACHE_BYTES,
                EXTRA_CACHE_HITS, EXTRA_CACHE_MISSES,
                EXTRA_PREFETCH_WORKS, EXTRA_PREFETCH_TRACKS,
                EXTRA_LINE_MATCHED, EXTRA_LINE_MISMATCHED, EXTRA_LINE_SAMPLES,
                EXTRA_FONT_DESC, EXTRA_FONT_NAME, EXTRA_FONT_RID,
                EXTRA_FONT_SEQ, EXTRA_FONT_N, EXTRA_FONT_DATA,
        };
        seen.clear();
        for (String e : extras) {
            if (e == null || e.isEmpty()) {
                return "extra key 为空";
            }
            if (!seen.add(e)) {
                return "extra key 重复: " + e;
            }
        }
        return null;
    }
}