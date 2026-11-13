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

/**
 * 【code 1066 / 2.4.5 / A-2】跟手基线 / 自愈 / 启停**闸门** —— 零 Android。
 *
 * <p>从 {@code ActivityButtonHook.captureFollowBaseline} /
 * {@code healStaleBiasIfAtRest} / {@code maybeStartPageFollow} 抽出布尔裁决；
 * 写字段、读 View、Choreographer 仍在 Hook。
 */
final class FollowBaselinePolicy {

    private FollowBaselinePolicy() {
    }

    /** 门①.5：页面最近是否够安静（运动静默窗）。 */
    static boolean pageQuietEnough(long lastPageMotionMs, long nowMs, long holdMs) {
        return lastPageMotionMs != 0L && nowMs - lastPageMotionMs >= holdMs;
    }

    /** transform 通道下是否在布局静止位。 */
    static boolean atLayoutRest(boolean visualSeen, int vis, int noBaseline, int deadzonePx) {
        return visualSeen && vis != noBaseline && Math.abs(vis) < deadzonePx;
    }

    /**
     * 已有基线且 y 偏离：若未回到布局静止位则推迟标定（防拖半路覆盖基线）。
     */
    static boolean deferOffBaseline(int followBaseY, int y, int noBaseline, int deadzonePx,
            boolean atLayoutRest) {
        if (followBaseY == noBaseline) {
            return false;
        }
        if (Math.abs(y - followBaseY) <= deadzonePx) {
            return false;
        }
        return !atLayoutRest;
    }

    /** 候选 y 是否需重置（首次或漂移出死区）。 */
    static boolean candidateNeedsReset(int candY, int y, int noBaseline, int deadzonePx) {
        return candY == noBaseline || Math.abs(y - candY) > deadzonePx;
    }

    /** 候选是否已连续稳住 settleMs。 */
    static boolean settleReady(long candMs, long nowMs, long settleMs) {
        return candMs != 0L && nowMs - candMs >= settleMs;
    }

    /** 是否采纳 transform 累加为宿主静态偏置（量级闸）。 */
    static boolean shouldAdoptBias(int visualOffset, int biasMaxPx) {
        return Math.abs(visualOffset) <= biasMaxPx;
    }

    /**
     * 自愈前置：偏置已标定、当前有非零位移、但 transform 累加≈0（真在静止位）。
     * false = 清空 heal 候选后返回。
     */
    static boolean healEligible(int visualBias, int followAppliedY, int visualOffset,
            int noBaseline, int deadzonePx) {
        if (visualBias == noBaseline || followAppliedY == 0) {
            return false;
        }
        if (visualOffset == noBaseline || Math.abs(visualOffset) > deadzonePx) {
            return false;
        }
        return true;
    }

    /** 近期运动 → 应启动跟帧。 */
    static boolean shouldStartFromRecentMotion(long lastPageMotionMs, long nowMs, long holdMs) {
        return lastPageMotionMs != 0L && nowMs - lastPageMotionMs < holdMs;
    }

    /** 页面此刻被拖开且 transform 通道就绪 → 应启动跟帧。 */
    static boolean shouldStartFromDragged(boolean visualSeen, boolean biasReady, int vis,
            int noBaseline, int deadzonePx) {
        return visualSeen && biasReady && vis != noBaseline && Math.abs(vis) > deadzonePx;
    }
}
