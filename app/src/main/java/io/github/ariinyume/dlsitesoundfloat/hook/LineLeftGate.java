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
 * 「字幕行左界的实测值能不能采信」——**零状态纯判定层**。
 *
 * <p>从 {@link StatusBarSubtitleHook} 抽出的第三块内核，形态照抄
 * {@link AnchorDeadPolicy} / {@code DensityPolicy}：<b>状态留在调用方</b>，
 * 内核只吃「当前状态快照 + 本次观测」，吐「下一份状态 + 结论」。
 *
 * <h3>它解决的问题（code 940 bug1 根修）</h3>
 * 采信门必须拿**常量**当锚，不能拿「上次采信值」自己当锚。旧口径
 * {@code acc <= 0 || |real - acc| <= 20dp} ⇒ 初值 -1 让**首次采样无条件过门**；
 * 而 {@code showLine()} 在「隐藏系统图标」之后 1ms 就调 {@code applyFluidBoundary(true)}，
 * 那次 hide 的 relayout 还没跑，{@code screenX(sLineView)} 仍是旧值 251 ⇒ 被锁存；
 * 之后真值 ~110 因 |110-251| = 141 &gt; 60 **永久拒收**，直到 SystemUI 重启。
 *
 * <p>本内核保留「连续 N 拍稳定停在新位置才认作容器真的搬家」的重锁机制 ——
 * 单帧跳变会因下一拍回到真值而被清空。
 */
final class LineLeftGate {

    private LineLeftGate() {
    }

    /** 判定结果：新状态 + 是否采信 + 待打印日志（null = 不该打）。 */
    static final class Decision {
        /** 是否采用本次实测值（true 时调用方用 {@link #acc} 当左界）。 */
        final boolean accepted;
        /** 下一份 {@code sLineLeftAcc}。 */
        final int acc;
        /** 下一份 {@code sLineLeftRejectStreak}。 */
        final int streak;
        /** 下一份 {@code sLineLeftRejectPrev}。 */
        final int prev;
        /** 日志正文（不含 TAG）；null = 本条不打印。 */
        final String log;

        Decision(boolean accepted, int acc, int streak, int prev, String log) {
            this.accepted = accepted;
            this.acc = acc;
            this.streak = streak;
            this.prev = prev;
            this.log = log;
        }
    }

    /**
     * @param real         本次实测的行左界（相对基准 x）
     * @param right        可用区间右界（左界必须落在它左边）
     * @param acc          当前采信值；&lt;=0 表示还没有采信过
     * @param streak        当前「连续偏离」计数
     * @param prev          上一次被拒的实测值；&lt;=0 表示没有
     * @param anchorFallback 还没采信过时的锚（常量 dp(38)）
     * @param tol          容差（dp(20)）
     * @param relockStreak 连续多少拍稳定停在新位置才重锁
     */
    static Decision decide(int real, int right, int acc, int streak, int prev,
                           int anchorFallback, int tol, int relockStreak) {
        if (real <= 0 || real >= right) {
            return new Decision(false, acc, streak, prev, null);
        }
        int anchor = (acc > 0) ? acc : anchorFallback;
        if (Math.abs(real - anchor) <= tol) {
            // 落在容差内 —— 正常采信（含徽标让位带来的 ±15dp 级平移）
            return new Decision(true, real, 0, -1, null);
        }
        int newStreak;
        if (prev > 0 && Math.abs(real - prev) <= tol) {
            newStreak = streak + 1;
        } else {
            newStreak = 1;
        }
        if (newStreak >= relockStreak) {
            String log = " line left relocked -> " + real + "px (sustained offset from anchor)";
            return new Decision(true, real, 0, -1, log);
        }
        String log = null;
        if (newStreak == 1) {
            log = " line left rejected -> " + real + "px (anchor=" + anchor + ", tol=" + tol + ")";
        }
        return new Decision(false, acc, newStreak, real, log);
    }
}
