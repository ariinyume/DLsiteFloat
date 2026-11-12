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
 * 【code 1050 / 架构优化 A1】{@code PAGE_OTHER} 去抖后的**显隐裁决** —— 零状态纯判定。
 *
 * <p>从 {@code ActivityButtonHook.detectAndLayout} 的 {@code PAGE_OTHER} 分支抽出：
 * 「连续 N 次采样 + 证据持续 ≥T ms」才允许按底部 mini-player 隐藏按钮。
 * 调用方负责：{@code isPageHeld} 门、streak/since 字段推进、真正的 {@code hideButton}。
 *
 * <p>v26 真机铁律：单帧假阳性（过渡动画里主滑条被误判成 mini-player）绝不能把按钮打掉。
 */
final class OtherHidePolicy {

    private OtherHidePolicy() {
    }

    /**
     * 在「本趟已计入 streak、since 已初始化」之后，是否应隐藏按钮。
     *
     * @param streak       连续 OTHER 采样次数（本趟已 +1）
     * @param sinceMs      本段 OTHER 起点（uptime）；0 = 未初始化（应视为未就绪）
     * @param nowMs        当前 uptime
     * @param needStreak   {@code HIDE_ON_OTHER_STREAK}
     * @param needProofMs  {@code HIDE_ON_OTHER_PROOF_MS}
     * @return true = 采样与时间窗都够了，可以 hide
     */
    static boolean shouldHide(int streak, long sinceMs, long nowMs,
            int needStreak, long needProofMs) {
        if (sinceMs == 0L) {
            return false;
        }
        if (streak < needStreak) {
            return false;
        }
        return nowMs - sinceMs >= needProofMs;
    }
}
