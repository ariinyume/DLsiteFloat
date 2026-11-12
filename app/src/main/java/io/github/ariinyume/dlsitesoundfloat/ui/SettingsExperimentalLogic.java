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
package io.github.ariinyume.dlsitesoundfloat.ui;

/**
 * 【code 1056 / 架构优化 B1 续】「实验性功能」卡的**零状态纯逻辑** —— 从
 * {@link SettingsActivity} 抽出。
 *
 * <p>只管：状态卡连点解锁 FSM、卡片显隐判据、总闸对缓存子开关的草稿影响、
 * 子控件是否可交互。View / toast / markDirty 仍在 Activity。
 */
public final class SettingsExperimentalLogic {

    /** 连续点击次数（状态卡隐藏解锁）。 */
    public static final int TAP_REQUIRED = 5;
    /** 相邻两次点击最大间隔（ms）；超过则计数清零。 */
    public static final long TAP_WINDOW_MS = 3000L;

    public enum UnlockOutcome {
        /** 草稿里实验性已开 ⇒ 提示「已打开」、不计票。 */
        ALREADY_ON,
        /** 连点进行中，未满次数。 */
        PROGRESS,
        /** 满 5 次 ⇒ Activity 把草稿 experimentalEnabled 置 true。 */
        UNLOCKED
    }

    public static final class TapState {
        public final int count;
        public final long lastMs;

        public TapState(int count, long lastMs) {
            this.count = count;
            this.lastMs = lastMs;
        }

        public static TapState zero() {
            return new TapState(0, 0L);
        }
    }

    public static final class UnlockResult {
        public final UnlockOutcome outcome;
        public final TapState next;

        public UnlockResult(UnlockOutcome outcome, TapState next) {
            this.outcome = outcome;
            this.next = next;
        }
    }

    private SettingsExperimentalLogic() {
    }

    /**
     * 状态卡连点解锁 FSM。
     *
     * <p>窗口口径：相邻间隔 {@code > TAP_WINDOW_MS} 才清零；恰好等于窗口仍累计。
     */
    public static UnlockResult onStatusTap(boolean draftExperimentalEnabled,
            TapState prev, long nowMs) {
        if (draftExperimentalEnabled) {
            return new UnlockResult(UnlockOutcome.ALREADY_ON, TapState.zero());
        }
        TapState p = prev == null ? TapState.zero() : prev;
        int count = p.count;
        if (p.lastMs > 0L && nowMs - p.lastMs > TAP_WINDOW_MS) {
            count = 0;
        }
        count++;
        if (count < TAP_REQUIRED) {
            return new UnlockResult(UnlockOutcome.PROGRESS, new TapState(count, nowMs));
        }
        return new UnlockResult(UnlockOutcome.UNLOCKED, TapState.zero());
    }

    /** 节标题 + 卡片是否显示：草稿或已保存任一侧开启即显示。 */
    public static boolean shouldShowCard(boolean draftEnabled, boolean savedEnabled) {
        return draftEnabled || savedEnabled;
    }

    /**
     * 总闸切换后缓存子开关的草稿值：
     * 关总闸 ⇒ 强制 false；开总闸 ⇒ 保留原缓存开关值。
     */
    public static boolean cacheEnabledAfterMasterToggle(boolean masterEnabled,
            boolean currentCacheEnabled) {
        return masterEnabled && currentCacheEnabled;
    }

    /** 子开关是否可交互（= 总闸开）。 */
    public static boolean childControlsEnabled(boolean masterEnabled) {
        return masterEnabled;
    }
}
