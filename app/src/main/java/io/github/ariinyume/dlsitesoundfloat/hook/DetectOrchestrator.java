/*
 * DLsiteSound Floating Subtitle - Xposed module for DLsite Sound
 * Copyright (C) 2026 ariinyume
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you can redistribute it and/or modify it under
 * the terms of the GNU General Public License as published by the Free Software
 * Foundation, either version 3 of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
 * PARTICULAR PURPOSE. See the GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along with
 * this program. If not, see <https://www.gnu.org/licenses/>.
 */
package io.github.ariinyume.dlsitesoundfloat.hook;

/**
 * 【优化 P1-4 / P0-2】{@code detectAndLayout} 入口编排的薄判定层。
 *
 * <p>把「节流闸 → 跟手闸 → 稳态跳过全树」三道前置路径合成一次 {@link #decide}，
 * hook 侧只按返回值推进状态 / 跑全扫。不持有状态；阈值全部由调用方传入。
 *
 * <p>{@link #SKIP_THROTTLE} / {@link #SKIP_FOLLOWING} 与 {@link DetectGatePolicy}
 * 同值，便于调用方与既有测试向量对齐。
 */
final class DetectOrchestrator {

    private DetectOrchestrator() {
    }

    /** 继续整树扫描。 */
    static final int FULL_SCAN = DetectGatePolicy.PROCEED;

    /** 节流闸：本趟直接 return，不推进 {@code lastDetectMs}。 */
    static final int SKIP_THROTTLE = DetectGatePolicy.SKIP_THROTTLE;

    /** 跟手闸：推进检测时刻后 return，心跳走 quiet 档。 */
    static final int SKIP_FOLLOWING = DetectGatePolicy.SKIP_FOLLOWING;

    /** 稳态跳过：推进检测时刻后 return，不做 {@link PlayerPageScanner#scan}。 */
    static final int SKIP_STABLE = 3;

    /**
     * @param forceNext          本趟是否强制绕过节流 / 禁止稳态跳过
     * @param pagePlayerVerdict  {@link PlayerPageScanner#PAGE_PLAYER}
     * @see DetectGatePolicy#decide
     * @see StableScanSkipPolicy#shouldSkip
     */
    static int decide(long now, long lastDetectMs, boolean forceNext,
            boolean following, long lastPageMotionMs,
            long minIntervalMs, long pageMotionHoldMs,
            int lastVerdict, int pagePlayerVerdict,
            int stableStreak, int settleStreak,
            boolean buttonVisible, boolean anchorAlive) {
        int gate = DetectGatePolicy.decide(now, lastDetectMs, forceNext,
                following, lastPageMotionMs, minIntervalMs, pageMotionHoldMs);
        if (gate != DetectGatePolicy.PROCEED) {
            return gate;
        }
        if (StableScanSkipPolicy.shouldSkip(forceNext, lastVerdict, pagePlayerVerdict,
                stableStreak, settleStreak, buttonVisible, anchorAlive)) {
            return SKIP_STABLE;
        }
        return FULL_SCAN;
    }
}
