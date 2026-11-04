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
package io.github.ariinyume.dlsitesoundfloat;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import io.github.ariinyume.dlsitesoundfloat.hook.TestAccessBridge;

import org.junit.Test;

/**
 * 【2026-11-04 · 拆「量 / 判」】滚动配速 / 重定目标 / 目标计算三块零状态内核的黄金向量。
 *
 * <p>为什么是这三块：11-03 的评估结论是「可测性的瓶颈不是状态散在字段里，而是计算坐在
 * {@code Paint} 上」。这一轮把 {@code ScrollGoal} 劈成「量（{@code measure}，碰 Paint）」
 * 与「判（{@code plan}，纯 int）」，再补 {@code ScrollPace} / {@code ScrollRetarget} ——
 * 于是 7 轮滚动 bug 里 **4 轮的判定逻辑**第一次有了 JVM 回归网：
 *
 * <table>
 *   <tr><th>历史 bug</th><th>钉在哪</th></tr>
 *   <tr><td>933 bug1 长字幕永不滚动</td><td>{@link #retargetAdoptsWhenNotArmed}</td></tr>
 *   <tr><td>934 bug1 滚到一半卡住（微速度）</td><td>{@link #paceSmallTargetKeepsSpeedFloor}</td></tr>
 *   <tr><td>934 bug2 右端留白 129px</td><td>{@link #retargetCancelSeatsWhenShrinkExceedsHysteresis}</td></tr>
 *   <tr><td>1.21.11 速度突然变了</td><td>{@link #retargetAdoptsWhileAnimatorRunning}</td></tr>
 *   <tr><td>969 脏 layout 宽把字幕甩飞</td><td>{@link #planRejectsDirtyLayoutWidth}</td></tr>
 *   <tr><td>971/974 就近吸附与末字裁切</td><td>{@link #planSnapPrefersUpperWhenLowerClipsTail}</td></tr>
 * </table>
 *
 * <p>⚠️ 向量里的数字都标了出处：要么是历史日志里的实测值，要么是「按当前常量算出来应该是多少」。
 * 不做「照抄一遍实现再对比」那种伪验证。
 */
public class ScrollKernelTest {

    // ── 与 StatusBarSubtitleHook 逐字一致的几何常量（改一处必须同步这里）──
    private static final int TAIL_MARGIN_PX = 3;
    private static final int COVER_MARGIN_PX = 6;
    private static final int MEASURE_TOLERANCE_PX = 128;
    private static final int MAX_TAIL_CLIP_PX = 5;
    private static final int MAX_NUDGE_PX = 6;
    private static final int TARGET_HYSTERESIS_PX = 8;

    /** 造一串等距字符边界：{@code 0, step, 2*step, …}，长度 = count + 1。 */
    private static int[] steps(int step, int count) {
        int[] b = new int[count + 1];
        for (int i = 0; i <= count; i++) {
            b[i] = i * step;
        }
        return b;
    }

    /** 常见情形：三口径一致、无脏值。 */
    private static TestAccessBridge.Plan planFits(int adv, int[] bounds, int viewW) {
        return TestAccessBridge.plan(adv, adv, adv, false, adv, bounds, viewW,
                TAIL_MARGIN_PX, COVER_MARGIN_PX, MEASURE_TOLERANCE_PX,
                MAX_TAIL_CLIP_PX, MAX_NUDGE_PX);
    }

    // ══════════════════════════════════════════════════════════════
    // ScrollPace.forLine —— 起滚定速
    // ══════════════════════════════════════════════════════════════

    /**
     * 【934 bug1】小目标必须被速度下限托住。
     *
     * <p>实测：target=10px、时长 4000ms ⇒ 原速度 2.5px/s ⇒ 244px 要滚 96 秒
     * （23:00:06 日志 96770ms）=「滚到一半卡住」。下限 70px/s 后 ⇒ 142ms 走完。
     */
    @Test
    public void paceSmallTargetKeepsSpeedFloor() {
        TestAccessBridge.Pace p = TestAccessBridge.pace(10, 4000L);
        assertEquals(0.07d, p.speedPxPerMs, 1e-9);
        assertEquals(142L, p.durMs);
    }

    /** 正常一行：时长在区间内、速度低于上限 ⇒ 时长原样保留。 */
    @Test
    public void paceNormalLineKeepsLineDuration() {
        TestAccessBridge.Pace p = TestAccessBridge.pace(508, 3200L);
        assertEquals(0.15875d, p.speedPxPerMs, 1e-9);
        assertEquals(3200L, p.durMs);
    }

    /** 行很长而时长很短 ⇒ 按 420px/s 抬时长下限，别一帧闪过。 */
    @Test
    public void paceLongLineClampedBySpeedCap() {
        TestAccessBridge.Pace p = TestAccessBridge.pace(1000, 100L);
        assertEquals(2380L, p.durMs);
        assertTrue("速度不得超过上限太多", p.speedPxPerMs < 0.421d);
    }

    /** 时长超上限 ⇒ 夹到 12s，再被速度下限改写成「按 70px/s 走完」。 */
    @Test
    public void paceLongDurationClampedToMax() {
        TestAccessBridge.Pace p = TestAccessBridge.pace(200, 99999L);
        assertEquals(0.07d, p.speedPxPerMs, 1e-9);
        assertEquals(2857L, p.durMs);
    }

    /** 放得下（目标 0）⇒ 不配速。 */
    @Test
    public void paceZeroTargetIsNoop() {
        TestAccessBridge.Pace p = TestAccessBridge.pace(0, 3000L);
        assertEquals(0L, p.durMs);
        assertEquals(0d, p.speedPxPerMs, 0d);
    }

    // ══════════════════════════════════════════════════════════════
    // ScrollPace.remainMs —— 续滚算时间（速度只读）
    // ══════════════════════════════════════════════════════════════

    /** 【934 bug1】速度异常时，剩余时间也必须夹在 12s 以内。 */
    @Test
    public void remainClampsToMaxMs() {
        assertEquals(12000L, TestAccessBridge.remainMs(100, 2000, 0.01d));
    }

    /** 剩余距离很短 ⇒ 时长抬到 60ms 下限（否则 Animator 会「瞬移」）。 */
    @Test
    public void remainFloorsAtSegmentMin() {
        assertEquals(60L, TestAccessBridge.remainMs(100, 103, 0.5d));
    }

    /** 剩余 ≤ 2px ⇒ 视为已到位，返回 0（调用方据此不起动画）。 */
    @Test
    public void remainIsZeroWhenArrived() {
        assertEquals(0L, TestAccessBridge.remainMs(100, 102, 0.5d));
        assertEquals(0L, TestAccessBridge.remainMs(100, 100, 0.5d));
        assertEquals(0L, TestAccessBridge.remainMs(120, 100, 0.5d));
    }

    /** 还没起过滚（速度 0）⇒ 用兜底速度 140px/s。 */
    @Test
    public void remainUsesFallbackSpeed() {
        // 1400 / 0.14 在 double 下是 9999.999999999998，截断成 9999 —— 与旧实现逐位一致
        // （差 1ms 无感，但「照抄旧行为」比「取整到好看的数字」更重要）。
        assertEquals(9999L, TestAccessBridge.remainMs(0, 1400, 0d));
        assertEquals(9999L, TestAccessBridge.remainMs(0, 1400, -1d));
    }

    /** 日志与计算必须用同一个解析结果（以前两处各写一遍三元表达式）。 */
    @Test
    public void speedOrFallbackIsShared() {
        assertEquals(0.14d, TestAccessBridge.speedOrFallback(0d), 1e-9);
        assertEquals(0.2d, TestAccessBridge.speedOrFallback(0.2d), 1e-9);
    }

    // ══════════════════════════════════════════════════════════════
    // ScrollRetarget.decide —— 宽度变了怎么办
    // ══════════════════════════════════════════════════════════════

    /** 【934 bug2】真机向量（23:00:22 日志 cur=517 target=388）：变宽后必须一次性回正，不许冻结。 */
    @Test
    public void retargetCancelSeatsWhenShrinkExceedsHysteresis() {
        TestAccessBridge.Retarget d = TestAccessBridge.retarget(
                517, 400, 388, true, true, TARGET_HYSTERESIS_PX);
        assertEquals("CANCEL", d.action);
        assertEquals(388, d.liveTarget);
        assertEquals(388, d.seatX);
    }

    /** 回正量不到迟滞就不落位（省一次 setScrollX，也免得为几像素抖一下）。 */
    @Test
    public void retargetCancelWithoutSeatWithinHysteresis() {
        TestAccessBridge.Retarget d = TestAccessBridge.retarget(
                395, 400, 390, true, false, TARGET_HYSTERESIS_PX);
        assertEquals("CANCEL", d.action);
        assertEquals(TestAccessBridge.noSeat(), d.seatX);
    }

    /** 变小但差距 < 迟滞 ⇒ 连记录都不改（迟滞治抖）。 */
    @Test
    public void retargetIgnoresSmallShrink() {
        TestAccessBridge.Retarget d = TestAccessBridge.retarget(
                200, 300, 295, true, true, TARGET_HYSTERESIS_PX);
        assertEquals("NONE", d.action);
        assertEquals("未采纳时目标必须原样返回", 300, d.liveTarget);
    }

    /** 【933 bug1】未起滚 ⇒ 只采纳目标、绝不重启动画（交回 startScroll 用新宽度重算）。 */
    @Test
    public void retargetAdoptsWhenNotArmed() {
        TestAccessBridge.Retarget d = TestAccessBridge.retarget(
                0, 0, 300, false, false, TARGET_HYSTERESIS_PX);
        assertEquals("ADOPT", d.action);
        assertEquals(300, d.liveTarget);
    }

    /** 【1.21.11】动画在跑 ⇒ 只改目标，绝不 cancel 重启（否则速度会一次比一次快）。 */
    @Test
    public void retargetAdoptsWhileAnimatorRunning() {
        TestAccessBridge.Retarget d = TestAccessBridge.retarget(
                200, 300, 500, true, true, TARGET_HYSTERESIS_PX);
        assertEquals("ADOPT", d.action);
        assertEquals(500, d.liveTarget);
    }

    /** 动画已跑完 ⇒ 按原速度续滚（CONTINUE 由调用方执行，速度不重算）。 */
    @Test
    public void retargetContinuesWhenAnimatorGone() {
        TestAccessBridge.Retarget d = TestAccessBridge.retarget(
                200, 300, 500, true, false, TARGET_HYSTERESIS_PX);
        assertEquals("CONTINUE", d.action);
        assertEquals(500, d.liveTarget);
    }

    /** 迟滞**单向**：目标变大 2px 也必须立刻采信（压着 = 末尾几像素永远滚不到）。 */
    @Test
    public void retargetGrowsAreNeverHysteresisBlocked() {
        TestAccessBridge.Retarget d = TestAccessBridge.retarget(
                100, 300, 302, true, true, TARGET_HYSTERESIS_PX);
        assertEquals("ADOPT", d.action);
        assertEquals(302, d.liveTarget);
    }

    /** 又变回放得下（目标 0）且已经在行首 ⇒ 取消动画但不落位。 */
    @Test
    public void retargetCancelWhenFitsAgain() {
        TestAccessBridge.Retarget d = TestAccessBridge.retarget(
                0, 300, 0, true, false, TARGET_HYSTERESIS_PX);
        assertEquals("CANCEL", d.action);
        assertEquals(0, d.liveTarget);
        assertEquals(TestAccessBridge.noSeat(), d.seatX);
    }

    // ══════════════════════════════════════════════════════════════
    // ScrollGoal.plan —— 纯 int 的「该滚多远」
    // ══════════════════════════════════════════════════════════════

    /** 放得下 ⇒ 目标 0、不做吸附。 */
    @Test
    public void planFitsMeansNoScroll() {
        TestAccessBridge.Plan g = planFits(500, steps(50, 10), 508);
        assertEquals(0, g.target);
        assertNull(g.snapLog);
        assertNull(g.nudgeLog);
    }

    /**
     * 【971 真机向量】「金枪鱼」那句：adv=882 / viewW=371 ⇒ 理论 514，落在边界 504 与 546 之间。
     *
     * <p>向下取 504 会裁掉末字 7px（> 允许的 5px）⇒ 必须退回上边界 546，
     * 宁可多留白也不切字。这条同时证明「就近吸附」不是无条件往下取。
     */
    @Test
    public void planSnapPrefersUpperWhenLowerClipsTail() {
        TestAccessBridge.Plan g = planFits(882, steps(42, 21), 371);
        assertEquals(546, g.target);
        assertNotNull(g.snapLog);
        assertTrue(g.snapLog.contains("[upper]"));
        assertNull(g.nudgeLog);
    }

    /** 向下取不裁字（clip=0）⇒ 就近取 lower，过冲从半个字压到 3px。 */
    @Test
    public void planSnapTakesLowerWhenTailSurvives() {
        TestAccessBridge.Plan g = TestAccessBridge.plan(600, 600, 600, false, 600,
                steps(40, 15), 560, TAIL_MARGIN_PX, 0, MEASURE_TOLERANCE_PX,
                MAX_TAIL_CLIP_PX, MAX_NUDGE_PX);
        assertEquals(40, g.target);
        assertTrue(g.snapLog.contains("[nearer-lower]"));
        assertNull(g.nudgeLog);
    }

    /** 选中边界仍包不住末尾 ⇒ 往右微调到「刚好覆盖」，但不超过 MAX_NUDGE_PX。 */
    @Test
    public void planNudgesToCoverTailWithinLimit() {
        TestAccessBridge.Plan g = planFits(300, steps(50, 6), 200);
        assertEquals(106, g.target);
        assertNotNull(g.nudgeLog);
        assertTrue(g.nudgeLog.contains("tail nudge"));
    }

    /**
     * 【969 真机事故】{@code getLayout().getWidth()} 返回 1048576（1024×1024 占位值）时，
     * 绝不许纳入「取最大」 —— 否则目标 ≈105 万像素、字幕以 420px/s 滑出屏幕（「直接飞走」）。
     */
    @Test
    public void planRejectsDirtyLayoutWidth() {
        TestAccessBridge.Plan g = TestAccessBridge.plan(300, 300, 300, true, 1048576,
                steps(50, 6), 200, TAIL_MARGIN_PX, COVER_MARGIN_PX, MEASURE_TOLERANCE_PX,
                MAX_TAIL_CLIP_PX, MAX_NUDGE_PX);
        assertTrue(g.layoutRejected);
        assertTrue(g.measure.contains("[rejected]"));
        assertTrue("目标必须仍在一行的量级", g.target > 0 && g.target < 200);
    }

    /** 【968】字形墨迹比 advance 宽时，目标要跟着变大（否则末字差一点）。 */
    @Test
    public void planInkWidensTarget() {
        // adv=100 时放得下（viewW=105 ⇒ 目标 0）
        assertEquals(0, planFits(100, steps(10, 10), 105).target);
        // 墨迹右边界到 118 ⇒ 必须滚 20px 才能露出末尾
        TestAccessBridge.Plan g = TestAccessBridge.plan(100, 118, 100, false, 100,
                steps(10, 10), 105, TAIL_MARGIN_PX, COVER_MARGIN_PX,
                MEASURE_TOLERANCE_PX, MAX_TAIL_CLIP_PX, MAX_NUDGE_PX);
        assertEquals(20, g.target);
    }

    /** 拿不到字符边界（设备字体没度量出来）⇒ 不吸附，直接返回理论值。 */
    @Test
    public void planWithoutBoundsReturnsRawTarget() {
        TestAccessBridge.Plan g = planFits(882, null, 371);
        assertEquals(514, g.target);
        assertNull(g.snapLog);
    }

    /** 诊断串形态固定（日志里有人肉对照表，改格式会让排障对不上）。 */
    @Test
    public void planMeasureStringShape() {
        TestAccessBridge.Plan g = planFits(882, steps(42, 21), 371);
        assertEquals("adv=882 ink=882 layout=882 calcW=371", g.measure);
        assertFalse(g.layoutRejected);
    }
}
