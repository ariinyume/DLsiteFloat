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
 * 【code 1066 / 2.4.5 / A-3】held 快照是否应续期 —— 零 Android。
 *
 * <p>v43：位移变化 ≥ 死区才续期；无条件续期会让 HOLD 窗永不失效（首页挂按钮）。
 */
final class HeldSnapshotRenewPolicy {

    private HeldSnapshotRenewPolicy() {
    }

    /**
     * @param heldOffset 当前快照位移；{@code noBaseline} = 尚未采过
     * @param vis        本帧视觉位移
     */
    static boolean shouldRenew(int heldOffset, int vis, int noBaseline, int deadzonePx) {
        return heldOffset == noBaseline || Math.abs(vis - heldOffset) >= deadzonePx;
    }
}
