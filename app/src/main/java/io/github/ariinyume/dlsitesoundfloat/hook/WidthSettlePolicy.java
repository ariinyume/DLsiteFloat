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
 * 【code 1058 / 架构优化 B2】状态栏字幕行**宽度 settle 零状态裁决**。
 *
 * <p>从 {@link StatusBarSubtitleHook#applyFluidBoundary} /
 * {@link StatusBarSubtitleHook#applyPendingWidth} 抽出：迟滞跳过探测、pending
 * 落地分支、可用宽度收紧。View / Handler / setLayoutParams / startScroll 副作用
 * 仍在 Hook。
 *
 * <p>钉住的历史口径：
 * <ul>
 *   <li>934：seeding 子视图在 448~454 间抖 6px，&lt;24px 不重排；</li>
 *   <li>933：迟滞丢弃 pending 时仍须视为已 settle，否则长句永不滚。</li>
 * </ul>
 */
final class WidthSettlePolicy {

    /** 与 Hook 的 {@code sAppliedLineWidth} 初值一致：尚未落地。 */
    static final int UNSET = Integer.MIN_VALUE;

    /** 无侧栏收紧时的 limit 哨兵（与 {@code Integer.MAX_VALUE} 同口径）。 */
    static final int NO_LIMIT = Integer.MAX_VALUE;

    enum PendingAction {
        /** 差值落在迟滞内：不改 LayoutParams，但必须 settle + 补起滚/retarget。 */
        NO_CHANGE_SETTLE,
        /** 需要真正改宽。 */
        APPLY_NEW
    }

    /** {@link #resolveAvail} 结果。 */
    static final class Avail {
        /** 建议宽度（可能是 fullWidthSentinel）。 */
        final int widthPx;
        /** 本次是否用 limit 收紧了右界。 */
        final boolean usedLimit;
        /** right-left（收紧后）；供日志。 */
        final int availPx;

        Avail(int widthPx, boolean usedLimit, int availPx) {
            this.widthPx = widthPx;
            this.usedLimit = usedLimit;
            this.availPx = availPx;
        }
    }

    private WidthSettlePolicy() {
    }

    /** |proposed - applied| &lt; hysteresis，且已有生效宽。 */
    static boolean withinHysteresis(int proposedPx, int appliedPx, int hysteresisPx) {
        return appliedPx != UNSET
                && Math.abs(proposedPx - appliedPx) < hysteresisPx;
    }

    /**
     * 非 force 且落在迟滞内 ⇒ 整段 probe 早退（不复位 settled、不排队 WIDTH_TASK）。
     */
    static boolean shouldSkipProbe(boolean force, int proposedPx, int appliedPx,
            int hysteresisPx) {
        return !force && withinHysteresis(proposedPx, appliedPx, hysteresisPx);
    }

    /**
     * pending 落地分支。首次（applied=UNSET）永远 {@link PendingAction#APPLY_NEW}。
     */
    static PendingAction pendingDecision(int pendingPx, int appliedPx, int hysteresisPx) {
        if (withinHysteresis(pendingPx, appliedPx, hysteresisPx)) {
            return PendingAction.NO_CHANGE_SETTLE;
        }
        return PendingAction.APPLY_NEW;
    }

    /**
     * 左/右/limit → 建议宽度。
     *
     * @param fullWidthSentinel 放不下最小可用宽时回落（Hook 传 {@code MATCH_PARENT}）
     */
    static Avail resolveAvail(int left, int right, int limit, int minAvailPx,
            int fullWidthSentinel) {
        int r = right;
        boolean usedLimit = false;
        if (limit != NO_LIMIT && limit > left && limit < right) {
            r = limit;
            usedLimit = true;
        }
        int avail = r - left;
        if (avail >= minAvailPx) {
            return new Avail(avail, usedLimit, avail);
        }
        return new Avail(fullWidthSentinel, false, avail);
    }
}
