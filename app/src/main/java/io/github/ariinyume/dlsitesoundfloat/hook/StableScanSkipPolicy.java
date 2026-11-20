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
 * 【优化 P0-2】播放页稳态时跳过全 decor 树扫描的纯判定。
 *
 * <p>跟手跳过见 {@link DetectGatePolicy#SKIP_FOLLOWING}；本类覆盖的是另一档：
 * 结论已是 {@code PAGE_PLAYER}、streak 已满、按钮可见、锚点仍活、且本趟未被
 * 强制复检时 —— 心跳只需锚点探针（{@code anchorWatch}）与结构事件唤醒，
 * 不必再跑 {@link PlayerPageScanner#scan}。
 *
 * <p>铁律：零状态；阈值（含 {@code settleStreak} / {@code pagePlayerVerdict}）由调用方传入。
 */
final class StableScanSkipPolicy {

    private StableScanSkipPolicy() {
    }

    /**
     * @param forceNext          结构事件 / 过渡态复检等强制全扫开关
     * @param lastVerdict        上趟扫描结论
     * @param pagePlayerVerdict  {@link PlayerPageScanner#PAGE_PLAYER}
     * @param stableStreak       连续同结论次数
     * @param settleStreak       认为「已稳态」的门槛（{@code SETTLE_STREAK}）
     * @param buttonVisible      胶囊组当前是否可见
     * @param anchorAlive        播放页锚点是否仍有效可见
     */
    static boolean shouldSkip(boolean forceNext, int lastVerdict, int pagePlayerVerdict,
            int stableStreak, int settleStreak,
            boolean buttonVisible, boolean anchorAlive) {
        if (forceNext) {
            return false;
        }
        if (lastVerdict != pagePlayerVerdict) {
            return false;
        }
        if (stableStreak < settleStreak) {
            return false;
        }
        if (!buttonVisible || !anchorAlive) {
            return false;
        }
        return true;
    }
}
