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
 * 「整棵树扫成空」的补检推迟门（从 {@code ActivityButtonHook.deferHideOnEmptyScan}
 * 抽出，2026-11-03 零状态内核拆分起）。
 *
 * <p>─────────────────────────────────────────────────────────────────────
 * 为什么要抽这一块
 *
 * 【code 953】真机取证（Ari 2026-09-26）：播放页完好铺在屏幕上，中间却夹着
 * 「滑条 0 + 时间文本 0 + 锚点 none」的**单趟退化测量**，8 秒闪了 6 次
 * （948/949 的「面积归零 ⇒ need=0/1 次采样」让这种退化测量当场收起按钮）。
 * 修法是命中「全空」时<b>本轮不收起</b>、补一趟 60ms 快检。
 *
 * <p>四道门的组合判据（全空的定义、证据新鲜度、每回合只补检一次）是纯布尔算术，
 * 但它原先和 {@code uiHandler.postDelayed} / 日志 / 两个静态字段写搅在一起 ——
 * 「全空到底怎么判的」只能真机试。抽出来后判据可单测钉死。
 *
 * <p>─────────────────────────────────────────────────────────────────────
 * ⚠️ 铁律（抽取时的取证结论，改本类前必读）
 *
 * 1. <b>本类必须保持无状态、可单测。</b>不碰 {@code sHideRecheckMs} /
 *    {@code sForceNextDetect} / {@code sLastPlayerSeenMs} / {@code sLastDecision}
 *    —— 全部由调用方读出传入。
 *
 * 2. <b>不碰日志、不碰副作用。</b>{@code [code 953] empty scan ...} 那条日志与
 *    {@code postDelayed(detectRunnable)} 留在 hook 侧 —— 补检调度是副作用，
 *    与「该不该推迟」的判定无关（同 {@link AnchorDeadPolicy} 铁律 4 的口径）。
 *
 * 3. <b>四道门的顺序与短路语义一字不改</b>（见 {@link #shouldDefer}）。
 *    特别是「本回合已补检过」必须<b>最后</b>判：它管的是「真离开时绝不赖着不走」，
 *    不能被提到前面把别的门挤掉。
 * ─────────────────────────────────────────────────────────────────────
 */
final class EmptyScanPolicy {

    private EmptyScanPolicy() {
    }

    /**
     * 这一趟是不是**退化测量**（七路证据全部缺席）。
     *
     * <p>判据原文（code 953 真机取证的结论）：「滑条 0 条 + 时间文本 0 个 +
     * 连锚点都找不到」= 这趟<b>什么都没测到</b>。真离开播放页时不可能全空 ——
     * 首页/列表页至少有文字（{@code descCandidateCount}），列表页还有底部
     * mini-player 滑条；只有「整棵子树被瞬时重排成不可测」（窗口重排 /
     * RN 换实例那一帧）才会全空。
     *
     * <p>注意 {@code anchorRef != null} 的语义是「锚点<b>在场</b>（哪怕面积为 0）」——
     * 在场就不算全空，那是 948/949 归零档该管的事，与本门无关。
     *
     * @param hasMainSlider      主滑条在场
     * @param hasBottomSlider    底部 mini-player 滑条在场
     * @param hasAnchor          锚点引用在场（{@code scan.anchorRef != null}）
     * @param wideSliderCount    宽滑条数
     * @param timeTextCount      时间文本数
     * @param descCandidateCount 简介候选行数
     * @param hasLiveLines       实时字幕行非空
     * @return true = 七路证据全空（退化测量）
     */
    static boolean isDegenerate(boolean hasMainSlider, boolean hasBottomSlider,
                                boolean hasAnchor, int wideSliderCount,
                                int timeTextCount, int descCandidateCount,
                                boolean hasLiveLines) {
        return !hasMainSlider && !hasBottomSlider && !hasAnchor
                && wideSliderCount <= 0 && timeTextCount <= 0
                && descCandidateCount <= 0 && !hasLiveLines;
    }

    /**
     * 【code 953】这一趟要不要**推迟收起**（四道门，短路顺序与原实现一致）。
     *
     * <ol>
     *   <li>按钮本来就没显示 / 扫描结果缺失 → 收无可收，不推迟；</li>
     *   <li>扫到了任何证据 → 那是<b>真的</b>离开播放页，照常收起，不推迟；</li>
     *   <li>早就没有播放页证据了（{@code lastPlayerSeenMs == 0} 或超时）→
     *       不该再犹豫，不推迟；</li>
     *   <li>本回合已补检过一次（{@code alreadyArmed}）→ 还是全空 ⇒ 真的走了，不推迟。</li>
     * </ol>
     *
     * <p>命中（四门全过）时调用方才写 {@code sHideRecheckMs}、置
     * {@code sForceNextDetect} 并 {@code postDelayed} 补检。
     *
     * @param scanPresent     扫描结果非 null
     * @param buttonShown     按钮正显示（{@code Boolean.TRUE.equals(sLastDecision)}）
     * @param degenerate      {@link #isDegenerate} 的结果
     * @param lastPlayerSeenMs 最近一次见到播放页证据的时刻（ms）；{@code 0} = 从没见过
     * @param now             当前时刻（ms）
     * @param evidenceTtlMs   {@code HIDE_RECHECK_EVIDENCE_MS}
     * @param alreadyArmed    本回合是否已补检过（{@code sHideRecheckMs != 0}）
     * @return true = 本轮推迟收起（调用方直接 return，维持现状）
     */
    static boolean shouldDefer(boolean scanPresent, boolean buttonShown, boolean degenerate,
                               long lastPlayerSeenMs, long now, long evidenceTtlMs,
                               boolean alreadyArmed) {
        if (!scanPresent || !buttonShown) {
            return false;
        }
        if (!degenerate) {
            return false;
        }
        if (lastPlayerSeenMs == 0L || now - lastPlayerSeenMs > evidenceTtlMs) {
            return false;
        }
        return !alreadyArmed;
    }
}
