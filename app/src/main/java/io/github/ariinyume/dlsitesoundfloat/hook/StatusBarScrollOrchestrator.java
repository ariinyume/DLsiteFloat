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
 * 【code 1065 / 架构优化 B2】状态栏字幕**起滚 / 宽度落地后补起滚 / retarget** 零状态闸门。
 *
 * <p>从 {@link StatusBarSubtitleHook} 的 {@code startScroll} / {@code applyPendingWidth}
 * 补起滚路径抽出。ValueAnimator / setScrollX / View.post 仍在 Hook。
 *
 * <p>钉住口径（code 927 / 933）：宽度未 settle 不许起滚；落地后未 armed 则补起滚，
 * 已 armed 则 retarget。
 */
final class StatusBarScrollOrchestrator {

    enum StartAction {
        /** 无行视图。 */
        ABORT,
        /** 宽度未落地：等 applyPendingWidth 补起滚。 */
        WAIT_WIDTH,
        /** 放得下：静态显示，并安排 fit recheck。 */
        SHOW_STATIC,
        /** 起滚动画。 */
        ANIMATE
    }

    enum AfterWidthSettleAction {
        /** 无行 / 无事。 */
        NONE,
        /** 尚未起滚 ⇒ 调 startScroll。 */
        ARM_START,
        /** 已起滚 ⇒ retargetScrollForNewWidth。 */
        RETARGET
    }

    private StatusBarScrollOrchestrator() {
    }

    /**
     * {@code startScroll} 入口闸。
     *
     * @param targetPx {@code computeScrollTarget()}；≤0 表示放得下
     */
    static StartAction decideStart(boolean hasLineView, boolean widthSettled, int targetPx) {
        if (!hasLineView) {
            return StartAction.ABORT;
        }
        if (!widthSettled) {
            return StartAction.WAIT_WIDTH;
        }
        if (targetPx <= 0) {
            return StartAction.SHOW_STATIC;
        }
        return StartAction.ANIMATE;
    }

    /**
     * 宽度真正写入 LayoutParams 之后：未起滚则补起滚，已起滚则 retarget。
     */
    static AfterWidthSettleAction afterWidthApplied(boolean hasLineView, boolean scrollArmed) {
        if (!hasLineView) {
            return AfterWidthSettleAction.NONE;
        }
        return scrollArmed ? AfterWidthSettleAction.RETARGET : AfterWidthSettleAction.ARM_START;
    }

    /**
     * pending 宽被迟滞吞掉、仍须 settle 时：与「真正改宽」后同一套补起滚/retarget。
     */
    static AfterWidthSettleAction afterHysteresisSettle(boolean hasLineView, boolean scrollArmed) {
        return afterWidthApplied(hasLineView, scrollArmed);
    }
}
