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
 * 心跳节奏判定内核（从 {@code ActivityButtonHook.decideHeartbeat} 抽出，
 * 2026-11-03 零状态内核拆分起）。
 *
 * <p>─────────────────────────────────────────────────────────────────────
 * 为什么要抽这一块
 *
 * {@code decideHeartbeat} 是 v24「响应提速」的核心状态机：给定本趟扫描的结论
 * （verdict / 过渡态）与三个记忆位（连续稳定次数、上次结论、过渡态复检计数），
 * 决定下一次心跳该多快，并顺手更新这三个记忆位。全部是**纯算术**，
 * 但它藏在 4600 行的 hook 里，四个常量档位（{@code AMBIGUOUS_RECHECK_MS} /
 * {@code HEARTBEAT_FAST_MS} / {@code HEARTBEAT_MS} / {@code SETTLE_STREAK}）
 * 的取值与边界「差一次采样」这种事只能真机试。
 *
 * <p>─────────────────────────────────────────────────────────────────────
 * ⚠️ 铁律（抽取时的取证结论，改本类前必读）
 *
 * 1. <b>本类必须保持无状态、可单测。</b>原逻辑里的 4 处静态字段读写
 *    （{@code sAmbiguousRechecks} / {@code sForceNextDetect} / {@code sLastVerdict} /
 *    {@code sStableStreak}）由调用方读出来传入、拿 {@link Beat} 回去落账 ——
 *    本类一行状态都不持有。
 *
 * 2. <b>档位常量全部由调用方以入参传入</b>（同 {@link AnchorDeadPolicy} 的口径），
 *    避免「改了 hook 的常量却忘了纯内核」这类双份真值。
 *
 * 3. <b>分支顺序一字不改</b>，三条 early-return 的优先级 =
 *    <b>过渡态复检 &gt; 结论与现状不符 &gt; 稳定 streak</b>：
 *    · 过渡态且复检配额没用完 → 固定 {@code ambiguousRecheckMs}，并置
 *      {@code forceNextDetect}（复检要绕过节流）；
 *      <b>此时不动 verdict / streak 记忆位</b>（原实现提前 return，两字段原样）；
 *    · 「是不是播放页」与「按钮在不在」不符 → 快速收敛
 *      （离开播放页后的隐藏就走这条）；同样不动记忆位；
 *    · 其余才做 streak 记账：结论变了归零，没变 +1；
 *      streak 未满 {@code settleStreak} 走快档，满了走常规档。
 *
 * 4. {@code forceNextDetect} 是<b>只置真不清假</b>的写法（原实现只写 true、
 *    从不在本路径清零）—— 调用方落账时必须 {@code if (b.forceNextDetect)} 才写。
 * ─────────────────────────────────────────────────────────────────────
 */
final class HeartbeatPolicy {

    private HeartbeatPolicy() {
    }

    /**
     * 一趟心跳判定的结果 = 下次间隔 + 三个记忆位的新值。
     *
     * <p>记忆位在「过渡态」「不符」两条 early-return 路径上原样带回
     * （等价于原实现的不写）；调用方无条件落账即可，值不变的写是无操作。
     */
    static final class Beat {
        /** 下一次心跳间隔（ms）。 */
        final long nextMs;
        /** {@code sAmbiguousRechecks} 新值（过渡态档 +1）。 */
        final int ambiguousRechecks;
        /** 是否要置 {@code sForceNextDetect}（只在过渡态档为 true）。 */
        final boolean forceNextDetect;
        /** {@code sLastVerdict} 新值（仅 streak 档可能更新）。 */
        final int lastVerdict;
        /** {@code sStableStreak} 新值（仅 streak 档可能更新）。 */
        final int stableStreak;

        Beat(long nextMs, int ambiguousRechecks, boolean forceNextDetect,
             int lastVerdict, int stableStreak) {
            this.nextMs = nextMs;
            this.ambiguousRechecks = ambiguousRechecks;
            this.forceNextDetect = forceNextDetect;
            this.lastVerdict = lastVerdict;
            this.stableStreak = stableStreak;
        }
    }

    /**
     * 决定下一次心跳间隔（v24 响应提速的核心）。
     *
     * <p>原则：<b>只在「需要尽快收敛」的时候快，其余时间省电。</b>
     * <ol>
     *   <li>过渡态（主滑条 + mini-player 滑条同时在）→ 快速复检（配额内）；</li>
     *   <li>结论与按钮<b>现状不一致</b>（例：还显示着按钮但判定已不确定）→ 快速跟踪；</li>
     *   <li>结论刚刚变化 → 快速跟踪一段（{@code settleStreak} 次）后转常规。</li>
     * </ol>
     *
     * @param verdict             本趟扫描结论（{@code PlayerPageScanner} 的 verdict 常量）
     * @param ambiguous           本趟是否为过渡态
     * @param ambiguousRechecks   已用掉的过渡态复检次数（{@code sAmbiguousRechecks}）
     * @param maxAmbiguousRechecks {@code MAX_AMBIGUOUS_RECHECKS}
     * @param verdictIsPlayer     调用方算好的 {@code verdict == PAGE_PLAYER}
     * @param buttonVisible       调用方算好的「按钮当前可见」
     * @param lastVerdict         上趟结论（{@code sLastVerdict}）
     * @param stableStreak        连续同结论次数（{@code sStableStreak}）
     * @param ambiguousRecheckMs  {@code AMBIGUOUS_RECHECK_MS}
     * @param fastMs              {@code HEARTBEAT_FAST_MS}
     * @param normalMs            {@code HEARTBEAT_MS}
     * @param settleStreak        {@code SETTLE_STREAK}
     * @return 下次间隔 + 记忆位新值
     */
    static Beat decide(int verdict, boolean ambiguous,
                       int ambiguousRechecks, int maxAmbiguousRechecks,
                       boolean verdictIsPlayer, boolean buttonVisible,
                       int lastVerdict, int stableStreak,
                       long ambiguousRecheckMs, long fastMs, long normalMs,
                       int settleStreak) {
        // ① 过渡态复检：配额内固定快档，并要求下一趟绕过节流。
        //    两处记忆位（verdict / streak）原样带回 —— 原实现在这里提前 return。
        if (ambiguous && ambiguousRechecks < maxAmbiguousRechecks) {
            return new Beat(ambiguousRecheckMs, ambiguousRechecks + 1, true,
                    lastVerdict, stableStreak);
        }

        // ② 结论与现状不符 → 尽快收敛（离开播放页后的隐藏就走这条）。不动记忆位。
        if (verdictIsPlayer != buttonVisible) {
            return new Beat(fastMs, ambiguousRechecks, false, lastVerdict, stableStreak);
        }

        // ③ streak 记账：结论变了归零，没变 +1；未满 settleStreak 走快档。
        if (verdict != lastVerdict) {
            return new Beat(settleStreak > 0 ? fastMs : normalMs,
                    ambiguousRechecks, false, verdict, 0);
        }
        int streak = stableStreak + 1;
        return new Beat(streak < settleStreak ? fastMs : normalMs,
                ambiguousRechecks, false, lastVerdict, streak);
    }
}
