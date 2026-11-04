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
 * 滚动**配速**的零状态内核：这一行该走多久、续滚还差多少毫秒。
 *
 * <p>从 {@link StatusBarSubtitleHook} 抽出的第三块纯计算层。它只吃 int/long/double，
 * 不认识 View、不认识动画、不读任何字段 —— 因此可以在纯 JVM 测试里跑黄金向量。
 *
 * <h3>它钉住的两条历史 bug</h3>
 * <ul>
 *   <li><b>934 bug1「滚到一半卡住」</b>：小目标（10px）配长时长会算出 2.5px/s 的
 *       <b>微速度</b>，而后续 retarget 沿用这个速度 ⇒ 244px 要滚 96 秒（日志 96770ms）。
 *       ⇒ {@link #forLine} 给速度设**下限** = 兜底速度的一半（70px/s）。</li>
 *   <li><b>934 bug2「右端留白 129px」/ 续滚失控</b>：剩余时间没有上界时会排出一个
 *       离谱的时长。⇒ {@link #remainMs} 夹到 {@link #MAX_MS}（12s）双保险。</li>
 * </ul>
 *
 * <h3>为什么速度必须「一次性定死」</h3>
 * 1.21.11 问题 1（「速度突然变了」）的根因是：每变一次宽度就 cancel + 按「剩余距离 ÷ 剩余时间」
 * 重启动画，而被夹过的剩余时间已经不等于原速度了 —— 反推出的速度比原来大，
 * 于是每 retarget 一次就快一截。⇒ 本内核把「定速」和「按已有速度算剩余时间」拆成两个
 * 方法：{@link #forLine} 只在起滚时调一次，之后只用 {@link #remainMs} 读速度、绝不反推。
 */
final class ScrollPace {

    private ScrollPace() {
    }

    /** 单程滚动时长下限（太快的整行扫过看不清）。 */
    static final long MIN_MS = 1500L;
    /** 单程滚动时长上限：再长用户已经换句了。 */
    static final long MAX_MS = 12000L;
    /** 拿不到该行播放时长时的兜底时长。 */
    static final long FALLBACK_MS = 4000L;
    /** 速度上限（px/s）：超过这个速度人眼读不完，宁可拉长时长。 */
    static final float MAX_SPEED_PX_PER_S = 420f;
    /** 兜底速度（px/s）：一般在「拿不到时长」时兜底用。 */
    static final float FALLBACK_SPEED_PX_PER_S = 140f;
    /** 单段动画的最短时长：短于此值 Animator 会「瞬移」，看起来是跳一下。 */
    static final long MIN_SEGMENT_MS = 60L;
    /** 剩余距离 ≤ 该值视为「已到位」，不再起动画（起一个 0px 的动画只会多一次回调）。 */
    static final int REMAIN_EPS_PX = 2;

    /** 配速结果：本段时长 + 定死的速度（px/ms）。 */
    static final class Pace {
        /** 本段动画时长（ms）；0 表示「不用滚」。 */
        final long durMs;
        /** 本行**定死**的速度（px/ms）；后续续滚只能读它，绝不重算。 */
        final double speedPxPerMs;

        Pace(long durMs, double speedPxPerMs) {
            this.durMs = durMs;
            this.speedPxPerMs = speedPxPerMs;
        }
    }

    /**
     * 【起滚时调一次】按「该行播放时长」定速，并算出本段时长。
     *
     * <p>顺序与旧实现逐字一致（这里改一个符号就会让真机手感变，别凭直觉重排）：
     * <ol>
     *   <li>时长先夹 [{@link #MIN_MS}, {@link #MAX_MS}]；</li>
     *   <li>再按 {@link #MAX_SPEED_PX_PER_S} 补一个**时长下限**（目标太大时不许一帧闪过）；</li>
     *   <li>由「目标 ÷ 时长」得到速度，再抬到下限（{@link #FALLBACK_SPEED_PX_PER_S} 的一半）；</li>
     *   <li>最后用**定死的速度**反算时长 —— 所以速度下限生效时，时长会被拉长，
     *       而不是速度被悄悄抬高（后者会让 retarget 沿用一个不可解释的速度）。</li>
     * </ol>
     *
     * @param target     滚动目标（px）；&lt;=0 表示放得下、不用滚
     * @param lineDurMs  该行字幕自身的播放时长；&lt;=0 表示拿不到
     */
    static Pace forLine(int target, long lineDurMs) {
        if (target <= 0) {
            return new Pace(0L, 0d);
        }
        long dur = lineDurMs > 0 ? lineDurMs : FALLBACK_MS;
        dur = Math.max(MIN_MS, Math.min(MAX_MS, dur));
        long minDurBySpeed = (long) (target * 1000f / MAX_SPEED_PX_PER_S);
        if (dur < minDurBySpeed) {
            dur = minDurBySpeed;
        }
        double spd = (double) target / (double) dur;
        // 【code 934 bug1 卡住根修】速度下限 = 半倍兜底速度(70px/s)
        double speed = Math.max(spd, FALLBACK_SPEED_PX_PER_S * 0.5 / 1000d);
        long seg = Math.max(MIN_SEGMENT_MS, (long) (target / speed));
        return new Pace(seg, speed);
    }

    /**
     * 解析「实际使用的速度」：还没起过滚（{@code <=0}）时用兜底速度。
     *
     * <p>抽成单独方法是为了让**日志**与**计算**用的是同一个解析结果 ——
     * 以前调用方各自写一遍三元表达式，改一处忘另一处就会打出误导人的日志。
     */
    static double speedOrFallback(double speedPxPerMs) {
        return speedPxPerMs > 0 ? speedPxPerMs : FALLBACK_SPEED_PX_PER_S / 1000d;
    }

    /**
     * 【续滚时调】按**已定死的速度**算剩余时间；速度只读，绝不从剩余距离反推。
     *
     * @param cur           当前 scrollX
     * @param target        当前动态目标 {@code sLiveTargetPx}
     * @param speedPxPerMs  {@link #forLine} 定下的速度；&lt;=0（还没起过滚）时用兜底速度
     * @return 剩余时长（ms）；**0 = 已到位，不该起动画**
     */
    static long remainMs(int cur, int target, double speedPxPerMs) {
        int dist = target - cur;
        if (dist <= REMAIN_EPS_PX) {
            return 0L;
        }
        double speed = speedOrFallback(speedPxPerMs);
        long remain = (long) (dist / speed);
        if (remain < MIN_SEGMENT_MS) {
            remain = MIN_SEGMENT_MS;
        }
        // 【code 934 bug1】上限钳制：速度异常时剩余滚动也绝不超过 12s（双保险）
        if (remain > MAX_MS) {
            remain = MAX_MS;
        }
        return remain;
    }
}
