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
 * 【code 1018 / 架构审查 2.2】{@code detectAndLayout} 的**两道前置闸** —— 零状态纯判定层。
 *
 * <h3>为什么抽它</h3>
 * {@code detectAndLayout} 是一个 404 行、要碰 6 组静态字段的方法，头两段却是**纯前置闸**：
 * 输入只有 {@code now} / {@code lastDetectMs} / {@code forceNext} / {@code following} /
 * {@code lastPageMotionMs}，输出只有「过 / 不过」。以前这类判据只能连着整棵类一起真机试；
 * 抠成静态纯函数后可以喂真实采样节奏离线对照 —— 而这道判据决定的正是**主线程掉不掉帧**。
 *
 * <p>与同包的 {@link CapsuleGeometry} / {@link PageFollowPolicy} / {@link AnchorDeadPolicy}
 * 是同一个原则：只承载<b>可离线验证的判据</b>，全部状态与副作用（写字段、改心跳节奏、
 * 跳过计数）一律留在 {@code ActivityButtonHook} 侧。
 *
 * <h3>口径约定</h3>
 * <ul>
 *   <li><b>不改判据顺序与阈值</b>：两道闸的先后、每一道的比较符，逐条照搬原实现。
 *       阈值一律由调用方以参数传入（本类不持有常量，避免与 hook 侧出现第二份口径）。</li>
 *   <li>本类<b>不持有任何状态</b>，也不读任何静态字段。</li>
 * </ul>
 *
 * <p>类不实例化。
 */
final class DetectGatePolicy {

    private DetectGatePolicy() {}

    /** 两道闸都放行 —— 调用方应继续整树扫描。 */
    static final int PROCEED = 0;

    /** 被节流闸拦下（距上次检测不足最小间隔，且本次未被要求强制复检）。 */
    static final int SKIP_THROTTLE = 1;

    /** 被跟手闸拦下（跟帧循环正在跟，且页面刚动过）。 */
    static final int SKIP_FOLLOWING = 2;

    /**
     * 判定这一趟检测该不该继续（纯函数，无副作用）。
     *
     * <p>判定顺序与 {@code ActivityButtonHook.detectAndLayout} 原实现逐行一致：
     * <ol>
     *   <li><b>① 节流闸</b>：{@code forceNext} 为假、且距上次检测不足 {@code minIntervalMs}
     *       → {@link #SKIP_THROTTLE}。{@code forceNext} 是「切页动画 / 结构事件期间必须
     *       立刻复检」的绕行开关（全局布局回调极其频繁，不限频会拖死主线程）。</li>
     *   <li><b>② 跟手闸</b>：跟帧循环正在跟（{@code following}）且页面刚动过
     *       （{@code lastPageMotionMs} 非零、距今不足 {@code pageMotionHoldMs}）
     *       → {@link #SKIP_FOLLOWING}。</li>
     *   <li>否则 {@link #PROCEED}。</li>
     * </ol>
     *
     * <p><b>②的完整论证</b>（v44 原文，另见调用点注释）：
     * 拖动播放页时宿主每帧 {@code setTranslationY} → 结构事件被合并成 ~50ms 一趟，
     * 每趟一次整树扫描（实测单次 6~8ms）+ 2 行长日志，而跟帧回调与它**抢同一个主线程** ——
     * 实测代价是「写下 202px 后，下一帧等了 110ms」。拖动期间扫描**没有决策价值**：
     * 结论不可能是「离开播放页」（页面就在手指底下，真离开时锚点会 detach，走
     * {@code removeView} / attach 监听那条路）；{@code hide} 本来就被 {@code isPageHeld()}
     * 的「页面被拖住」判据压着；基线采集要求「页面静止」，拖动中本来就采不到。
     * 所以直接跳过，只把心跳按 {@code FOLLOW_QUIET_HEARTBEAT_MS}（120ms）续上；
     * 页面一停本条件立刻不成立，完整扫描自动恢复（含「页面被卸载」的判定）。
     *
     * <p>⚠️ <b>调用方必须知道的顺序敏感性</b>：原实现在①放行之后、②之前就写了
     * {@code sForceNextDetect = false} 与 {@code sLastDetectMs = now} ——
     * 也就是说**②跳过时那两个状态已经被推进**。调用方按原顺序写即可；本类只回答
     * 「过 / 不过」，不替调用方改任何状态。
     *
     * @param now              本次检测时刻（{@code SystemClock.uptimeMillis()}）
     * @param lastDetectMs     上次检测时刻，0 = 从未检测过
     * @param forceNext        本次是否强制绕过节流（结构事件 / 切页复检）
     * @param following        跟帧循环是否正在跟
     * @param lastPageMotionMs 页面最后运动时刻，0 = 从未动过
     * @param minIntervalMs    ①的阈值 {@code DETECT_MIN_INTERVAL_MS}
     * @param pageMotionHoldMs ②的阈值 {@code PAGE_MOTION_HOLD_MS}
     * @return {@link #PROCEED} / {@link #SKIP_THROTTLE} / {@link #SKIP_FOLLOWING}
     */
    static int decide(long now, long lastDetectMs, boolean forceNext,
            boolean following, long lastPageMotionMs,
            long minIntervalMs, long pageMotionHoldMs) {
        // ① 节流闸：全局布局回调非常频繁，限制检测频率，避免主线程被拖死。
        if (!forceNext && now - lastDetectMs < minIntervalMs) {
            return SKIP_THROTTLE;
        }
        // ② 跟手闸。
        if (following && lastPageMotionMs != 0L
                && now - lastPageMotionMs < pageMotionHoldMs) {
            return SKIP_FOLLOWING;
        }
        return PROCEED;
    }
}
