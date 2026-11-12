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
 * 【code 1059 / 架构优化 B2】滚动**放得下 / 跑完后**复核的零状态裁决。
 *
 * <p>从 {@link StatusBarSubtitleHook#recheckFitAfterLayout} 与
 * {@code animateScrollTo} 的 {@code onAnimationEnd} 抽出。View.post /
 * computeScrollTarget / continueScroll 副作用仍在 Hook。
 *
 * <p>钉住的口径（2.2.0 半字根修）：
 * <ul>
 *   <li>layout 落地后 real 目标大于迟滞 ⇒ 原先「放得下」是错的，要补起滚；</li>
 *   <li>动画自然跑完后 real 比 live 大超过 slack ⇒ 目标算小了，按原速续滚；</li>
 *   <li>scrollX 仍落后 live 超过 slack ⇒ 目标变大后的剩余段续滚。</li>
 * </ul>
 */
final class ScrollFitRecheck {

    /** onAnimationEnd 用的像素松弛（历史硬编码 2）。 */
    static final int SETTLE_SLACK_PX = 2;

    enum AfterEndAction {
        /** 无事可做。 */
        NONE,
        /** 采纳更大 real 目标并 {@code continueScrollToLiveTarget}。 */
        RETARGET_CONTINUE,
        /** live 未变，但 scrollX 落后 ⇒ 续滚剩余。 */
        CONTINUE_REMAINING
    }

    private ScrollFitRecheck() {
    }

    /**
     * fit recheck 的 Runnable 入口闸：视图换代 / 已有动画 / 已安排滚动 ⇒ 跳过。
     */
    static boolean shouldSkipPostedFitRecheck(boolean sameView, boolean hasAnimator,
            int liveTargetPx, int scrollX) {
        if (!sameView || hasAnimator) {
            return true;
        }
        return liveTargetPx > 0 || scrollX != 0;
    }

    /** layout 落地后：real 超过迟滞 ⇒ 应补起滚。 */
    static boolean shouldStartAfterFitRecheck(int realTargetPx, int hysteresisPx) {
        return realTargetPx > hysteresisPx;
    }

    /**
     * 动画自然跑完后的裁决。
     *
     * @param slackPx 通常 {@link #SETTLE_SLACK_PX}
     */
    static AfterEndAction afterAnimationEnd(int realTargetPx, int liveTargetPx,
            int scrollX, int slackPx) {
        if (realTargetPx > liveTargetPx + slackPx) {
            return AfterEndAction.RETARGET_CONTINUE;
        }
        if (scrollX < liveTargetPx - slackPx) {
            return AfterEndAction.CONTINUE_REMAINING;
        }
        return AfterEndAction.NONE;
    }
}
