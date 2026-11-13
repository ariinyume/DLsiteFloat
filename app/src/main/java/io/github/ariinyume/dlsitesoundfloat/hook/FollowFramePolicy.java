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
 * 【code 1066 / 2.4.5 / A-3】跟帧循环闸门 —— 零 Android。
 *
 * <p>held 判定、时长帽、miss 预算、静止停帧；写 translationY / 再 post 帧留 Hook。
 */
final class FollowFramePolicy {

    private FollowFramePolicy() {
    }

    static boolean isHeld(int delta, int noBaseline, int deadzonePx) {
        return delta != noBaseline && Math.abs(delta) > deadzonePx;
    }

    static long durationCap(boolean held, long maxMs, long maxHeldMs) {
        return held ? maxHeldMs : maxMs;
    }

    static boolean timedOut(long startMs, long nowMs, long capMs) {
        return nowMs - startMs > capMs;
    }

    /** miss 帧 +1 后是否应放弃循环。 */
    static boolean missExhausted(int missAfterInc, int missMax) {
        return missAfterInc >= missMax;
    }

    /**
     * 静止位附近是否应停帧（held 时永不因 still 停 —— v39）。
     */
    static boolean shouldStopWhenStill(boolean held, int followStill, int stillFrames) {
        return !held && followStill >= stillFrames;
    }
}
