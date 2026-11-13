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
 * 【code 1066 / 2.4.5 / A-3】播放键候选评分 —— 零 Android。
 *
 * <p>DFS / View 遍历仍在 Hook；本类只裁决「方正尺寸」与 centerX 距离分。
 */
final class PlayButtonPickPolicy {

    private PlayButtonPickPolicy() {
    }

    /**
     * 是否像方正播放键（最小边长 + 宽高比）。
     *
     * @param aspectSlack 相对 max(w,h) 的宽高差比例上限（Hook 用 0.4f）
     */
    static boolean isSquareCandidate(int w, int h, int minPx, float aspectSlack) {
        if (w < minPx || h < minPx) {
            return false;
        }
        return Math.abs(w - h) <= Math.max(w, h) * aspectSlack;
    }

    /** 候选中心到屏中心的水平距离（越小越好）。 */
    static int centerScore(int locX, int width, int screenCenterX) {
        return Math.abs(locX + width / 2 - screenCenterX);
    }

    /** 新候选是否优于当前最佳（严格更小分）。 */
    static boolean beats(int newScore, int bestScore) {
        return newScore < bestScore;
    }
}
