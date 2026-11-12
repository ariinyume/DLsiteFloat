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

import java.util.List;

/**
 * 【code 1053 / 架构优化 A2】悬浮窗 / 状态栏 / 按钮的**只读显隐口径** —— 从
 * {@link SubtitleRepository} 抽出的零状态纯函数。
 *
 * <p>按钮、悬浮窗、状态栏必须走同一套闸（1.21.16 / 2.1.3 / 973），本类把那几条
 * if 钉死，Repository 只负责把字段快照喂进来。不持锁、不读单例。
 *
 * <p>{@link io.github.ariinyume.dlsitesoundfloat.util.LineSource} 仍是跨包接口；
 * 本类是数据层内部的判定内核，避免 util↔data 再长边。
 */
public final class DisplayContract {

    private DisplayContract() {
    }

    /**
     * 当前是否应当按「无字幕」显示 —— 按钮底色 / 状态栏开关 / 悬浮窗占位的**唯一口径**。
     *
     * <ul>
     *   <li>手上无 cues 或软裁决已下 ⇒ true；</li>
     *   <li>硬挂起（待确认且非软挂起）⇒ true；</li>
     *   <li>软挂起（有 cues、JSON 在路上）⇒ false，维持正常显示不降级。</li>
     * </ul>
     */
    public static boolean shouldShowNoSubtitles(boolean cuesEmpty, boolean softNoSubtitles,
            boolean pendingTrackDecision, boolean pendingSoftSuspend) {
        if (cuesEmpty || softNoSubtitles) {
            return true;
        }
        return pendingTrackDecision && !pendingSoftSuspend;
    }

    /**
     * {@code getCurrentSubtitles()} 是否应返回空列表（屏上镜像被掐）。
     *
     * <p>含 973：上一轨 cue 隔离期也按空返回。
     */
    public static boolean hideCurrentSubtitles(boolean softNoSubtitles,
            boolean previousTrackCuesHidden, boolean pendingTrackDecision,
            boolean pendingSoftSuspend) {
        return softNoSubtitles || previousTrackCuesHidden
                || (pendingTrackDecision && !pendingSoftSuspend);
    }

    /**
     * {@code getCues()} 是否应返回空列表（数据保留但不参与渲染）。
     *
     * <p>注意：与 {@link #hideCurrentSubtitles} 略不同 —— 待确认期间**不论软硬**
     * 都隐藏 cues 列表（原实现：{@code pendingTrackDecision || softNoSubtitles || previous…}）。
     */
    public static boolean hideCues(boolean pendingTrackDecision, boolean softNoSubtitles,
            boolean previousTrackCuesHidden) {
        return pendingTrackDecision || softNoSubtitles || previousTrackCuesHidden;
    }

    /**
     * {@code selfComputedLines()} 是否应返回空（纯自算观测被掐）。
     */
    public static boolean hideSelfComputed(boolean pendingTrackDecision,
            boolean previousTrackCuesHidden, boolean cuesEmpty) {
        return pendingTrackDecision || previousTrackCuesHidden || cuesEmpty;
    }

    /** 把一条 cue 的多行用空格拼成状态栏单行。 */
    public static String joinCue(SubtitleCue cue) {
        if (cue == null || cue.subtitles == null) {
            return "";
        }
        return joinLines(cue.subtitles);
    }

    /** 多行 → 单行（空格连接）。 */
    public static String joinLines(List<String> lines) {
        if (lines == null || lines.isEmpty()) {
            return "";
        }
        StringBuilder sb = new StringBuilder();
        for (String s : lines) {
            if (sb.length() > 0) {
                sb.append(' ');
            }
            sb.append(s);
        }
        return sb.toString();
    }

    /**
     * 状态栏最终文案：优先当前 cue 拼行；否则用屏上镜像；都没有 → 空串
     * （桥据此隐藏 SystemUI 字幕）。
     */
    public static String statusBarLine(String joinedCueLine, List<String> mirrorLines) {
        if (joinedCueLine != null && !joinedCueLine.isEmpty()) {
            return joinedCueLine;
        }
        String mirror = joinLines(mirrorLines);
        return mirror == null ? "" : mirror;
    }
}
