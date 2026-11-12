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
package io.github.ariinyume.dlsitesoundfloat.data;

/**
 * 【code 1051–1052 / 架构优化 A2】换轨待确认窗的**零状态纯裁决** —— 从
 * {@link SubtitleRepository} 的 {@code onTrackChanged} / {@code resolvePendingTrack} 抽出。
 *
 * <p>只管算术：进不进挂起、等多久、窗到点是「假换轨 / 无字幕 / JSON 已到」。
 * 不持有状态、不碰 Handler / 磁盘 / 预取 / UI。常量值仍由 Repository 传入。
 *
 * <p>认领 / 归属（选择键、重建窗、作品键）已在 {@link PlaylistKey}。
 * CueStore / DisplayContract 未在本轮动。
 */
public final class TrackDecision {

    /** 待确认窗到点后的三岔口（副作用仍由 Repository 执行）。 */
    public enum PendingVerdict {
        /** 宽限内已有新 JSON → 保留 cues。 */
        JSON_ARRIVED,
        /** 老信号路径上的假换轨 → 撤销挂起、保留旧 cues。 */
        SPURIOUS,
        /** 真换轨且等到点仍无 JSON → 软/硬「无字幕」分支。 */
        NO_SUBTITLES
    }

    private TrackDecision() {
    }

    /**
     * 刚加载过字幕 JSON（距今 ≤ 预加载容差）⇒ 大概率就是新音轨的，保留 cues，不进挂起。
     *
     * <p>{@code agoMs} 取 {@code Long.MAX_VALUE} 表示从未加载过。
     */
    public static boolean keepRecentJson(long agoMs, long preloadToleranceMs) {
        return agoMs <= preloadToleranceMs;
    }

    /**
     * 手上已有 cues ⇒ 软挂起（清显示、保留数据）；否则硬挂起。
     */
    public static boolean softSuspend(boolean hadCues) {
        return hadCues;
    }

    /**
     * 挂起后等多久再做「无字幕」裁决。
     *
     * <p>分级口径（code 1014 / 1040）：
     * <ul>
     *   <li>手上有上一轨 cues，且本轨磁盘与预取都还没垫背 ⇒ 长窗（等慢云端）；</li>
     *   <li>否则标准短窗（本地兜底就绪时不必苦等）。</li>
     * </ul>
     */
    public static long graceMs(boolean hadCues, boolean diskFallbackReady,
            boolean prefetchFallbackReady, long standardMs, long cachedMs) {
        if (hadCues && !diskFallbackReady && !prefetchFallbackReady) {
            return cachedMs;
        }
        return standardMs;
    }

    /**
     * 提前收窗延时 = {@code min(earlyCloseCapMs, graceMs)}。
     * 短窗 1000ms 时收窗与裁决同刻；长窗 15000ms 时仍按 5s 先关空窗。
     */
    public static long earlyCloseDelayMs(long earlyCloseCapMs, long graceMs) {
        return Math.min(earlyCloseCapMs, graceMs);
    }

    /**
     * 宽限内是否等到了比挂起基线更新的字幕 JSON。
     *
     * <p>{@code lastLoadJsonMs <= pendingBaselineLoadMs} ⇒ 没等到。
     */
    public static boolean jsonArrivedDuringGrace(long lastLoadJsonMs,
            long pendingBaselineLoadMs) {
        return lastLoadJsonMs > pendingBaselineLoadMs;
    }

    /**
     * 【code 1052】待确认窗到点：假换轨 / 无字幕 / JSON 已到。
     *
     * <p>口径照搬 {@code resolvePendingTrack}（v28 + code 973）：
     * <ul>
     *   <li>权威序号门（{@code indexVerified}）⇒ <b>不做</b>假换轨兜底；</li>
     *   <li>假换轨只认「观察到位置大幅回退」或「基线明显 &gt;0 且位置只增不减」；</li>
     *   <li>其余 ⇒ {@link PendingVerdict#NO_SUBTITLES}（软硬副作用由调用方按 hadCues 分支）。</li>
     * </ul>
     *
     * <p>入参必须是挂起期间采到的样本副本（不要传已清零的字段）。
     */
    public static PendingVerdict resolvePending(boolean jsonArrived, boolean indexVerified,
            boolean sawPositionReset, int posSamples, long startPosMs, long curPosMs,
            long positionResetToleranceMs) {
        if (jsonArrived) {
            return PendingVerdict.JSON_ARRIVED;
        }
        if (isSpuriousChange(indexVerified, sawPositionReset, posSamples,
                startPosMs, curPosMs, positionResetToleranceMs)) {
            return PendingVerdict.SPURIOUS;
        }
        return PendingVerdict.NO_SUBTITLES;
    }

    /**
     * 老信号路径上的假换轨判据（权威序号门一律 false）。
     *
     * <p>v28：不能再用「位置从未回退」—— 真换轨瞬间 pos 常被清到 0，窗内只涨不跌，
     * 会把真换轨全判成假换轨。现在要求看到大幅回退，或「基线远大于 0 且仍在往前走」。
     */
    public static boolean isSpuriousChange(boolean indexVerified, boolean sawPositionReset,
            int posSamples, long startPosMs, long curPosMs, long positionResetToleranceMs) {
        if (indexVerified) {
            return false;
        }
        if (sawPositionReset) {
            return true;
        }
        return posSamples > 0
                && startPosMs > positionResetToleranceMs
                && curPosMs >= 0
                && curPosMs > startPosMs;
    }

    /**
     * 「无字幕」软裁决：手上仍有 cues ⇒ 只清显示、不销毁数据。
     */
    public static boolean softNoSubtitleVerdict(boolean hadCues) {
        return hadCues;
    }
}
