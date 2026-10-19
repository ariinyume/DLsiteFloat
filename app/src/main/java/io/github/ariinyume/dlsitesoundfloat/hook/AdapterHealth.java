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
package io.github.ariinyume.dlsitesoundfloat.hook;

import android.os.SystemClock;

import java.util.EnumMap;
import java.util.Map;

import io.github.ariinyume.dlsitesoundfloat.util.XposedCompat;

/**
 * 【code 1022 / P0-2】适配自检表 —— 把「某条锚点没命中」从**隐性**变成**一行常开日志**。
 *
 * <h3>要解决的问题</h3>
 * 本模块的六条链路各自 try/catch，失败时只落 {@code LogGate.debug}（**默认关闭**）。
 * 于是宿主一升级（R8 重跑短名），用户的观感是「插件突然不工作了」，
 * 而日志里干干净净 —— 这就是 2.20.2 上连废两版（964/965）的同一类问题。
 *
 * <p>本类把六条链路的「最新结论」集中到一处：状态**一旦变化**就打一行常开日志，
 * 内容是「哪一项、从什么变成什么、当前满分几项」。启动后第一屏日志就能看出
 * 是「插件没生效」还是「宿主结构变了」。
 *
 * <h3>为什么不做设置页可视化</h3>
 * 自检结果产生在**宿主进程**，而设置页在模块自己的进程（不同 uid）——
 * 共享 SharedPreferences / 静态字段都读不到，要展示必须扩 {@code ConfigBus} 协议。
 * 那是另一件事（协议升版有风险），本版先把「日志可见」做扎实；
 * 设置页只显示能自己读到的**宿主版本**（见 {@code SettingsActivity}）。
 *
 * <h3>口径</h3>
 * <ul>
 *   <li>{@link State#HIT} —— 该链路已确认可用（挂钩成功 / 首次真实命中）。</li>
 *   <li>{@link State#DEGRADED} —— 锚点在但形状/键名与预期不符，走了降级路径（功能部分可用）。</li>
 *   <li>{@link State#MISS} —— 锚点完全找不到（该能力不可用）。</li>
 *   <li>{@link State#UNKNOWN} —— 尚未有机会判定（例如用户还没进播放页）。</li>
 * </ul>
 * ⚠️ **只在状态变化时打日志**：{@code VIEW_PAGE} 这类会被高频调用的项，
 * 同状态重复上报必须零成本返回，否则会把日志刷屏（与 32 号铁律「配额型日志」同源）。
 */
public final class AdapterHealth {

    private static final String TAG = "[DLsiteSoundFloat:Health]";

    /** 七条链路。名字直接进日志，保持短且可 grep。 */
    public enum Item {
        /** 网络通道 0：{@code Response.Builder.build()} 形状锚点。 */
        NET_BUILD,
        /** 网络通道 1：{@code NetworkingModule.readWithProgress} 形状锚点。 */
        NET_RN,
        /** 播放状态：{@code AudioPlaylist/AudioPlayer} 的无参 {@code Map} 状态方法。 */
        AUDIO_STATUS,
        /** 播放页判定：主滑条 + 时间文本配对（视图树扫描）。 */
        VIEW_PAGE,
        /** 字幕文本：宿主上屏文本与 cue 列表的语义匹配。 */
        SUB_TEXT,
        /** 状态栏：SystemUI 侧注入容器。 */
        STATUSBAR,
        /**
         * 【code 1023 / P0-4】作品文件树预取（{@code ziptree} → 整部作品字幕）。
         *
         * <p>⚠️ 与上面六项**性质不同**：那六项是「宿主适配锚点」，坏了就说明插件跟不上宿主；
         * 这一项是**本模块自己的能力**，MISS/DEGRADED 只说明「离线听不了这部作品的字幕」，
         * 不影响在线字幕。放在最后，正是为了让它不和适配问题混为一谈。
         */
        PREFETCH
    }

    public enum State {
        UNKNOWN, HIT, DEGRADED, MISS
    }

    private static final Map<Item, State> STATE = new EnumMap<>(Item.class);
    private static final Map<Item, String> DETAIL = new EnumMap<>(Item.class);

    static {
        for (Item it : Item.values()) {
            STATE.put(it, State.UNKNOWN);
        }
    }

    private AdapterHealth() {
    }

    /**
     * 上报一项的结论。**只有状态真的变化时才落日志**。
     *
     * @param item   链路
     * @param state  新结论
     * @param detail 附加信息（可为 null）；命中时也建议给一句「怎么命中的」
     */
    public static synchronized void mark(Item item, State state, String detail) {
        if (item == null || state == null) {
            return;
        }
        State old = STATE.get(item);
        if (old == state) {
            // 同状态：只更新 detail，不打日志（高频项靠这条保持零噪声）
            if (detail != null) {
                DETAIL.put(item, detail);
            }
            return;
        }
        STATE.put(item, state);
        if (detail != null) {
            DETAIL.put(item, detail);
        }
        XposedCompat.log(TAG + " " + item + ": " + old + " -> " + state
                + (detail == null ? "" : " (" + detail + ")")
                + " | " + summary());
    }

    /** 兼容便捷写法：只要「成功/失败」。 */
    public static void hit(Item item, String detail) {
        mark(item, State.HIT, detail);
    }

    public static void miss(Item item, String detail) {
        mark(item, State.MISS, detail);
    }

    public static void degraded(Item item, String detail) {
        mark(item, State.DEGRADED, detail);
    }

    public static State get(Item item) {
        return STATE.get(item) == null ? State.UNKNOWN : STATE.get(item);
    }

    /**
     * 一行摘要：{@code 5/6 [VIEW_PAGE=DEGRADED]}。
     *
     * <p>「满分」＝ HIT 的项数；分母固定为 6（未知项也算没拿到分，因为对用户而言
     * 就是「还不能确定能用」）。
     */
    public static synchronized String summary() {
        int hit = 0;
        StringBuilder bad = new StringBuilder();
        for (Item it : Item.values()) {
            State st = STATE.get(it);
            if (st == State.HIT) {
                hit++;
            } else {
                if (bad.length() > 0) {
                    bad.append(' ');
                }
                bad.append(it).append('=').append(st);
            }
        }
        return hit + "/" + Item.values().length
                + (bad.length() > 0 ? " [" + bad + "]" : " [all clear]");
    }

    /** 首次进入播放页 / 启动完成时打一行清单，便于用户直接复制进 Issue。 */
    public static synchronized void logTable(String why) {
        StringBuilder sb = new StringBuilder();
        for (Item it : Item.values()) {
            if (sb.length() > 0) {
                sb.append(' ');
            }
            sb.append(it).append('=').append(STATE.get(it));
            String d = DETAIL.get(it);
            if (d != null && d.length() > 0) {
                sb.append('(').append(d).append(')');
            }
        }
        XposedCompat.log(TAG + " table(" + why + "): " + sb + " -> " + summary());
    }

    private static boolean sTableLogged = false;

    /** 【code 1027】播放页首次判成立的时刻（uptime 毫秒）；{@code 0} = 还没进过播放页。 */
    private static long sPlayerPageAtMs = 0L;

    /** 【code 1027】通道静默只报一次 —— 每进程一行，不刷屏。 */
    private static boolean sSilentLogged = false;

    /**
     * 【code 1027】进了播放页多久还一条响应都没读到，就认定「通道疑似静默」。
     *
     * <p>20 秒是**给正常路径留的余量**：切轨后宿主发字幕 JSON 通常在 1 秒内到，
     * 20 秒还没见过任何响应，基本只剩三种解释 —— 宿主的网络栈换了（钩子挂上但永不触发）、
     * 全程离线、或者整部作品的字幕全在本地缓存里根本没有请求。
     */
    private static final long SILENT_GRACE_MS = 20_000L;

    /**
     * 只打一次的表 —— 挂在「首次判出播放页」那一刻。
     *
     * <p>那一刻六项里至少「网络 / 状态 Map / 视图」三条已经有结论，
     * 是用户与维护者最想看到的一张快照；再往后打就是噪声。
     */
    public static synchronized void logTableOnce(String why) {
        if (sTableLogged) {
            return;
        }
        sTableLogged = true;
        logTable(why);
    }

    /**
     * 【code 1027】通道静默自检 —— 补上「钩子挂上但从不触发」这个盲区。
     *
     * <h3>为什么需要</h3>
     * {@link #mark} 只在**状态变化**时落日志，所以「钩子装好了、但宿主一次都没调用」
     * 这种故障在日志里只剩一句 {@code NET_BUILD: UNKNOWN -> DEGRADED (hooked, waiting first tap)}，
     * 之后再无下文 —— 用户看到的却是「字幕一直不出来」。964/965 两版就是这么废掉的
     * （见铁律：钩子挂上 ≠ 钩子会触发）。
     *
     * <h3>判据</h3>
     * 播放页已成立 ≥ {@link #SILENT_GRACE_MS}、两条网络通道仍停在 {@code DEGRADED}
     * （= 挂上了但没命中过）、且**一条响应都没被 peek 到** ⇒ 怀疑通道失效。
     * 三项缺一不可：把「没进播放页」「已经 MISS（自己会报）」「peek 到了（活的）」全都排除掉。
     *
     * <h3>口径</h3>
     * <b>只落一行日志、不改任何状态</b>：离线播放、整部命中本地缓存时同样满足前三项，
     * 那是正常的 —— 所以措辞写「疑似」，不冒充结论，更不去动 {@link State}。
     *
     * @param peekedResponses {@code NetworkHook#peekedCount()}（真正 peek 过的响应条数）
     */
    public static synchronized void tickChannelSilence(int peekedResponses) {
        if (sSilentLogged || get(Item.VIEW_PAGE) != State.HIT) {
            return;
        }
        long now = SystemClock.uptimeMillis();
        if (sPlayerPageAtMs == 0L) {
            sPlayerPageAtMs = now;
            return;
        }
        long held = now - sPlayerPageAtMs;
        if (held < SILENT_GRACE_MS) {
            return;
        }
        boolean pending = get(Item.NET_BUILD) == State.DEGRADED
                || get(Item.NET_RN) == State.DEGRADED;
        if (!pending || peekedResponses > 0) {
            return;
        }
        sSilentLogged = true;
        XposedCompat.log(TAG + " NET_SILENT: 播放页已 " + (held / 1000L)
                + "s，两条网络通道仍 DEGRADED、0 条响应被读到 —— 疑似通道失效"
                + "（宿主换网络栈 / 全程离线 / 整部命中本地缓存都会这样）"
                + "；仅提示，不改判据。table: " + summary());
    }
}
