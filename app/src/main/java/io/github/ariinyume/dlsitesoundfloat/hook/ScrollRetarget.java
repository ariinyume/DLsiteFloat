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
 * 「宽度变了，滚动该怎么办」的零状态判定内核。
 *
 * <p>从 {@link StatusBarSubtitleHook#retargetScrollForNewWidth(int)} 里剥出来的**纯判断**：
 * 吃六个 int/bool，吐一个 {@link Decision}（动作 + 采纳后的目标 + 要不要落位）。
 * 副作用（cancelScroll / setScrollX / continueScrollToLiveTarget）**全部留在调用方** ——
 * 这是本仓四次重构反复验证过的套路：判定可测，副作用可读。
 *
 * <h3>它钉住的四条历史 bug</h3>
 * <ul>
 *   <li><b>927 问题 1「先整行再半截」</b>：宽度没落地就起滚 ⇒ 本内核用 {@code armed} 表达
 *       「这一行是否已经起滚」，未起滚时只**记录**新目标、绝不重启动画（交回 startScroll 重算）。</li>
 *   <li><b>933 bug1「长字幕永不滚动」</b>：early-return 让状态永远不推进 ⇒ 这里每个出口都
 *       带明确动作，{@link Action#NONE} 只在「差异不显著」时出现。</li>
 *   <li><b>934 bug2「右端留白 129px」</b>：目标变小/已越过目标时旧逻辑 cancel 后冻结 ⇒
 *       本内核给 {@link Action#CANCEL} 挂一个 {@code seatX}，把视窗一次性回正到新目标。</li>
 *   <li><b>1.21.11 问题 1「速度突然变了」</b>：宽度变化绝不 cancel 重启动画 ⇒
 *       动画在跑时只 {@link Action#ADOPT}（改目标，让每帧比较去处理），
 *       动画跑完才 {@link Action#CONTINUE}（按原速度续滚）。</li>
 * </ul>
 */
final class ScrollRetarget {

    private ScrollRetarget() {
    }

    /** {@code seatX} 取该值表示「只取消、不落位」。 */
    static final int NO_SEAT = Integer.MIN_VALUE;

    /** 判定动作。 */
    enum Action {
        /** 差异不显著（相等，或变小但没超过迟滞）⇒ 连记录都不改，什么都不做。 */
        NONE,
        /** 采纳新目标，但**不动动画**（未起滚 / 动画在跑 / 距离还够）。 */
        ADOPT,
        /** 取消当前动画（必要时把视窗一次回正到 {@code seatX}）。 */
        CANCEL,
        /** 按原速度续滚到新目标。 */
        CONTINUE
    }

    /** 判定结果。 */
    static final class Decision {
        final Action action;
        /** 采纳后的动态目标；{@link Action#NONE} 时等于入参 {@code liveTarget}（未采纳）。 */
        final int liveTarget;
        /** 仅 {@link Action#CANCEL} 有意义：要落到的 scrollX；{@link #NO_SEAT} = 不落位。 */
        final int seatX;

        Decision(Action action, int liveTarget, int seatX) {
            this.action = action;
            this.liveTarget = liveTarget;
            this.seatX = seatX;
        }
    }

    /**
     * 决定「新目标来了怎么办」。
     *
     * @param cur          当前 scrollX
     * @param liveTarget   当前生效的动态目标 {@code sLiveTargetPx}
     * @param newTarget    重新算出来的目标（可能为 0 = 现在放得下了）
     * @param armed        这一行是否已经起滚过（false = 宽度变化交给 startScroll 重算）
     * @param hasAnimator  当前是否真有动画在跑
     * @param hysteresisPx 迟滞阈值（{@code TARGET_HYSTERESIS_PX}），只对「变小」生效
     */
    static Decision decide(int cur, int liveTarget, int newTarget, boolean armed,
                           boolean hasAnimator, int hysteresisPx) {
        final int delta = newTarget - liveTarget;
        // 迟滞**单向**：目标变大（可视区变窄 ⇒ 要滚得更远）立刻采信，
        // 压着不放的代价是「末尾那几个像素永远滚不到」= 末字被裁；
        // 只有「变小」才用迟滞挡抖动（多滚几像素只是末尾留白）。
        if (delta == 0 || (delta < 0 && -delta < hysteresisPx)) {
            return new Decision(Action.NONE, liveTarget, NO_SEAT);
        }
        if (!armed) {
            return new Decision(Action.ADOPT, newTarget, NO_SEAT);
        }
        if (newTarget <= 0 || cur >= newTarget) {
            // 【code 934 bug2 根修】变宽 → 新目标比当前位置还小：旧逻辑 cancel 后冻结，
            //   右侧留白最多达宽度差（实测 129px）直到本条字幕结束。改为一次性回正到新目标
            //   （文字尾端重新贴齐右边界；目标 0 = 放得下，回行首正常显示）。
            //   差距 ≤ 迟滞就不落位：省一次 setScrollX，也免得为了几像素抖一下。
            int seat = (newTarget >= 0 && cur - newTarget > hysteresisPx)
                    ? Math.max(newTarget, 0) : NO_SEAT;
            return new Decision(Action.CANCEL, newTarget, seat);
        }
        if (!hasAnimator) {
            return new Decision(Action.CONTINUE, newTarget, NO_SEAT);
        }
        return new Decision(Action.ADOPT, newTarget, NO_SEAT);
    }
}
