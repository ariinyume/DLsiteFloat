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
 * density 锁定/重锁判定内核（从 {@code ActivityButtonHook.stableDensity} 抽出，
 * 2026-11-03 零状态内核拆分起）。
 *
 * <p>─────────────────────────────────────────────────────────────────────
 * 为什么要抽这一块
 *
 * 【code 939 bug2】「打开播放页转场瞬间」会读到<b>伪 density</b>，直接采信会让
 * 按钮大小跟着抖。修法是一个带迟滞的重锁状态机：读数与锁定值不一致且<b>像素
 * 尺寸没变</b>时一律沿用锁定值；只有「持续不一致」（时长 + 采样数双门槛）或
 * 「屏幕真的变了」（宽高像素键不同）才重锁。这套算术夹在 try/catch、三处
 * 静态字段与三条日志之间，边界差一个采样就退回 939 的老毛病 —— 抽出来钉死。
 *
 * <p>─────────────────────────────────────────────────────────────────────
 * ⚠️ 铁律（抽取时的取证结论，改本类前必读）
 *
 * 1. <b>本类必须保持无状态、可单测。</b>四个记忆位（锁定密度 / 像素键 /
 *    差异起算时刻 / 差异计数）由调用方读出来传入、拿 {@link Result} 回去落账。
 *
 * 2. <b>本类只管 {@code d > 0} 的主状态机</b>；读数异常、{@code d <= 0} 的
 *    兜底（{@code 锁定值 > 0 ? 锁定值 : 3f}）留在 hook 侧 —— 那是 IO 失败路径，
 *    不是判定。
 *
 * 3. <b>判据顺序与阈值语义一字不改</b>（顺序敏感处见 {@link #step} 注释）：
 *    · 首次锁定 / 像素键变化 → <b>无条件重锁</b>（屏幕真的变了，转场伪值不成立）；
 *    · 读数与锁定值一致（容差 0.0001）→ 清差异计数、沿用锁定值；
 *    · 读数漂移但像素键没变 → 累计差异，双门槛（{@code relockMs} 且
 *      {@code relockSamples}）<b>同时</b>满足才重锁，否则沿用锁定值。
 *
 * 4. <b>不碰日志。</b>三条日志（screen changed / sustained diff / spike ignored）
 *    全部留在 hook 侧按 {@link Result#event} 打 —— 可观测性口径与算术无关
 *    （同 {@link AnchorDeadPolicy} 铁律 4 的口径）。
 * ─────────────────────────────────────────────────────────────────────
 */
final class DensityPolicy {

    /** 事件：无日志。 */
    static final int EVENT_NONE = 0;
    /** 事件：屏幕像素键变化（或首次锁定后有差异）→ 打 {@code density re-locked (screen changed)}。 */
    static final int EVENT_RELOCK_SCREEN = 1;
    /** 事件：持续差异过双门槛 → 打 {@code density re-locked (sustained diff)}。 */
    static final int EVENT_RELOCK_SUSTAINED = 2;
    /** 事件：差异计数恰好第 1 次 → 打 {@code density spike ignored}。 */
    static final int EVENT_SPIKE = 3;

    private DensityPolicy() {
    }

    /**
     * 一步状态机的结果 = 返回值 + 四个记忆位的新值 + 该打哪条日志。
     */
    static final class Result {
        /** 本趟应当采用的 density（返回给调用方）。 */
        final float use;
        /** {@code sLockedDensity} 新值。 */
        final float lockedDensity;
        /** {@code sLockedPxKey} 新值。 */
        final int lockedPxKey;
        /** {@code sDensityDiffSinceMs} 新值。 */
        final long diffSinceMs;
        /** {@code sDensityDiffCount} 新值。 */
        final int diffCount;
        /** 该打哪条日志（{@code EVENT_*}）；{@link #EVENT_NONE} = 不打。 */
        final int event;
        /** 判定时的差异采样数（已含本步 +1；仅供「sustained」日志用）。 */
        final int samples;

        Result(float use, float lockedDensity, int lockedPxKey,
               long diffSinceMs, int diffCount, int event, int samples) {
            this.use = use;
            this.lockedDensity = lockedDensity;
            this.lockedPxKey = lockedPxKey;
            this.diffSinceMs = diffSinceMs;
            this.diffCount = diffCount;
            this.event = event;
            this.samples = samples;
        }
    }

    /**
     * 走一步重锁状态机（仅 {@code d > 0} 的主路径；兜底见类注释铁律 2）。
     *
     * <p>顺序敏感（与原实现逐行一致，改前先读类注释铁律 3）：
     * <ol>
     *   <li><b>首次锁定 / 像素键变化</b>：无条件重锁并清差异计数。
     *       带 {@code EVENT_RELOCK_SCREEN} 的条件是「<b>既有</b>锁定值存在且与
     *       新值有差异」（首次锁定静默、重锁到同值也静默 —— 与原实现的
     *       {@code if (sLockedDensity > 0f && |d - sLockedDensity| > 0.0001f)} 一致）；</li>
     *   <li><b>读数一致</b>（容差 {@code 0.0001f}）：清差异计数、沿用锁定值；</li>
     *   <li><b>读数漂移</b>：本步先累计（{@code diffSinceMs == 0} 则以 {@code now}
     *       起算、计数 +1），再判双门槛
     *       {@code now - diffSinceMs >= relockMs && samples >= relockSamples}：
     *       满足 → 重锁（像素键<b>不动</b>，与原实现一致）；
     *       不满足 → 沿用锁定值，计数恰为 1 时给 {@code EVENT_SPIKE}。</li>
     * </ol>
     *
     * @param lockedDensity {@code sLockedDensity}；{@code <= 0} 表示首次锁定
     * @param lockedPxKey   {@code sLockedPxKey}
     * @param diffSinceMs   {@code sDensityDiffSinceMs}；{@code 0} = 差异尚未起算
     * @param diffCount     {@code sDensityDiffCount}
     * @param d             本趟读到的 density（调用方保证 {@code > 0}）
     * @param pxKey         本趟像素键（{@code widthPixels * 31 + heightPixels}）
     * @param now           当前时刻（{@code SystemClock.uptimeMillis()}）
     * @param relockMs      {@code DENSITY_RELOCK_MS}
     * @param relockSamples {@code DENSITY_RELOCK_SAMPLES}
     * @return 返回值 + 记忆位新值 + 日志事件
     */
    static Result step(float lockedDensity, int lockedPxKey, long diffSinceMs, int diffCount,
                       float d, int pxKey, long now,
                       long relockMs, int relockSamples) {
        // ① 首次锁定 / 像素屏幕尺寸真的变了（旋转、分屏、换屏）→ 无条件重锁。
        if (lockedDensity <= 0f || pxKey != lockedPxKey) {
            boolean logScreen = lockedDensity > 0f
                    && Math.abs(d - lockedDensity) > 0.0001f;
            return new Result(d, d, pxKey, 0L, 0,
                    logScreen ? EVENT_RELOCK_SCREEN : EVENT_NONE, 0);
        }

        // ② 读数与锁定值一致 → 清差异计数、沿用锁定值。
        if (Math.abs(d - lockedDensity) <= 0.0001f) {
            return new Result(lockedDensity, lockedDensity, lockedPxKey, 0L, 0,
                    EVENT_NONE, 0);
        }

        // ③ 像素尺寸没变但 density 变了 —— 真机实证这是「打开播放页转场瞬间」的伪值。
        //    先累计差异，再判双门槛。
        long since = diffSinceMs == 0L ? now : diffSinceMs;
        int samples = diffCount + 1;
        if (now - since >= relockMs && samples >= relockSamples) {
            // 持续不一致过双门槛 → 真的换了显示大小，重锁。
            return new Result(d, d, lockedPxKey, 0L, 0,
                    EVENT_RELOCK_SUSTAINED, samples);
        }
        // 门槛没到 → 沿用锁定值；首个差异样本打一条 spike 日志。
        return new Result(lockedDensity, lockedDensity, lockedPxKey, since, samples,
                samples == 1 ? EVENT_SPIKE : EVENT_NONE, samples);
    }
}
