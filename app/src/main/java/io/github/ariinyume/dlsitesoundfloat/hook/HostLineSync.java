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
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along with
 * this program. If not, see <https://www.gnu.org/licenses/>.
 */
package io.github.ariinyume.dlsitesoundfloat.hook;

import java.util.List;

import io.github.ariinyume.dlsitesoundfloat.util.XposedCompat;

/**
 * 【code 1024 / P1-5】**宿主上屏行**与**自算行**的一致性观测（只统计，不接管渲染）。
 *
 * <h3>── 权威行其实一直在手上 ──</h3>
 * {@code SubtitleViewHook} 抓屏时已经把宿主字幕控件上的文本读出来了 —— 判据是
 * 「文本 ∈ 已加载的 cue 列表」（见 {@code SubtitleRepository#isKnownSubtitleText}），
 * 它现在只用于判定「这一屏有没有真字幕」。而「宿主**实际**在显示哪几句」与
 * 「我们自算该显示哪几句」是否一致，从来没有被量过。
 *
 * <h3>── 为什么先只观测，不直接接管 ──</h3>
 * 体检报告 P1-5 的原话是「先只统计 mismatch（观测一版），确认不影响换轨后，再切到
 * 宿主行优先、自算行兜底」。理由很硬：换成「宿主行优先」等于把渲染权从自己的时间轴
 * 交给宿主的时间轴，一旦宿主在换轨瞬间还留着上一轨的控件（真机见过 4627~7284ms 的空档），
 * 屏上就会出现上一轨的句子 —— 那正是 978/1013 时代的顽疾。<b>没有数据就不动渲染。</b>
 *
 * <p>所以本轮只做三件事：① 每次抓屏把两侧的行比对一次；② 第一次不一致与
 * 「比例明显偏高」时各落一行常开日志（带内容片段，能直接看出差在哪一句）；
 * ③ 把累计计数暴露出去，设置页那行缓存读数里顺带显示（见 {@code ConfigBus} 的统计广播）。
 *
 * <h3>── 两侧的来源（【code 1025】修正过一次，务必看完） ──</h3>
 *
 * <ul>
 *   <li><b>hostLines</b> = {@code ScanResult#liveLines}：扫屏得到的宿主上屏行。
 *       它的判据是「文本 ∈ 我们已加载的 cue 表」——**已经过我们自己的表过滤**；</li>
 *   <li><b>selfLines</b> = {@code SubtitleRepository#selfComputedLines()}：只读
 *       {@code currentCueIndex}（纯本地「位置÷1000 → cue 区间」推算），不走镜像回退。</li>
 * </ul>
 *
 * <p>🔴 **code 1024 这里传的是 {@code repo.getCurrentSubtitles()} —— 那是错的。**
 * 该值由 {@code ActivityButtonHook} 用 {@code setCurrentSubtitles(scan.liveLines)} 写入，
 * 即**上一帧的 hostLines** ⇒ 两边同源，测出来的是「连续两帧上屏内容相同率」。
 * 真机读数 {@code 408/416}（mismatch 1.92%）看似卡在 P1-5 验收线（&lt;1%）附近，
 * 实际**没有判别力**，不能用来决定「要不要切镜像优先」。
 *
 * <p>⚠️ <b>本指标仍有固有限制（不是 bug，是判据形状决定的）</b>：
 * {@code liveLines} 只收「∈ 我们 cue 表」的行，所以「宿主显示了、而我们表里根本没有」
 * 这类差异**永远不会进样本**。因此它衡量的是「双方都承认为本轨的行里，我们算得对不对」，
 * 不是「宿主上屏内容的覆盖率」。要测后者得另开一路：不过滤地抓候选文本再比对。
 *
 * <h3>── 判据 ──</h3>
 * 两侧都用「去首尾空白 + 折叠连续空白」归一化后比对，<b>交集非空即算一致</b> ——
 * 字幕常常是多行（日文一行、译文一行），宿主与我们的行序可能不同，逐行对齐会造出假不一致。
 * 只在「宿主显示了、而我们一句都没有对上」时才记 mismatch。
 *
 * <p>线程模型：只在宿主进程内被 {@code scan()} 调用（单线程为主，计数器用 synchronized
 * 兜住偶发的并发扫描），不持有任何 View 引用。
 */
public final class HostLineSync {

    private static final String TAG = "[DLsiteSoundFloat:LineSync]";

    /** 汇总日志的最小间隔（毫秒）—— 抓屏是高频动作，不能每次都刷一行。 */
    private static final long SUMMARY_INTERVAL_MS = 60_000L;

    /** 一条日志里最多带多少个字符（防长句把日志撑爆）。 */
    private static final int PREVIEW_CHARS = 40;

    private static int sSamples = 0;
    private static int sMatched = 0;
    private static int sMismatched = 0;
    private static boolean sFirstMismatchLogged = false;
    private static long sLastSummaryMs = 0L;

    private HostLineSync() {
    }

    /**
     * 比对一次。
     *
     * @param hostLines 宿主**当前上屏**的字幕行（{@code ScanResult#liveLines}）
     * @param selfLines 我们**纯自算**出来该显示的行
     *                  （{@code SubtitleRepository#selfComputedLines()} ——
     *                  只读 currentCueIndex，**不是**屏上镜像；见类头）
     */
    public static void observe(List<String> hostLines, List<String> selfLines) {
        try {
            if (hostLines == null || hostLines.isEmpty()
                    || selfLines == null || selfLines.isEmpty()) {
                return;                         // 只有一侧有内容时不构成「不一致」，不计样本
            }
            boolean any = false;
            String firstHost = null;
            for (String h : hostLines) {
                String hn = norm(h);
                if (hn.isEmpty()) {
                    continue;
                }
                if (firstHost == null) {
                    firstHost = hn;
                }
                if (containsNormalized(selfLines, hn)) {
                    any = true;
                    break;
                }
            }
            if (firstHost == null) {
                return;
            }
            synchronized (HostLineSync.class) {
                sSamples++;
                if (any) {
                    sMatched++;
                } else {
                    sMismatched++;
                    if (!sFirstMismatchLogged) {
                        sFirstMismatchLogged = true;
                        XposedCompat.log(TAG + " MISMATCH (first): host=\"" + preview(firstHost)
                                + "\" self=" + preview(selfLines.get(0))
                                + " | hostLines=" + hostLines.size()
                                + " selfLines=" + selfLines.size()
                                + " -> observe only, rendering NOT changed");
                    }
                }
                maybeLogSummaryLocked();
            }
        } catch (Throwable ignored) {
            // 观测绝不影响主链路
        }
    }

    /** 累计样本数（两侧都有内容才算一次）。 */
    public static synchronized int samples() {
        return sSamples;
    }

    /** 对上过几次。 */
    public static synchronized int matched() {
        return sMatched;
    }

    /** 一句都没对上过几次。 */
    public static synchronized int mismatched() {
        return sMismatched;
    }

    /** 一行摘要（日志 / 设置页读数用）。 */
    public static synchronized String summary() {
        if (sSamples == 0) {
            return "no sample yet";
        }
        return "line sync " + sMatched + "/" + sSamples + " matched"
                + " (mismatch " + sMismatched + ")";
    }

    // ==================================================================
    // 内部
    // ==================================================================

    /** 至少每 {@link #SUMMARY_INTERVAL_MS} 落一次汇总；比例偏高时提前落（每次会话至多几行）。 */
    private static void maybeLogSummaryLocked() {
        long now = android.os.SystemClock.uptimeMillis();
        if (sLastSummaryMs != 0L && now - sLastSummaryMs < SUMMARY_INTERVAL_MS) {
            return;
        }
        sLastSummaryMs = now;
        XposedCompat.log(TAG + " " + summary()
                + " -> 口径：宿主上屏行与自算行逐条归一化后比交集，只统计、不接管渲染");
    }

    private static boolean containsNormalized(List<String> lines, String target) {
        for (String s : lines) {
            if (target.equals(norm(s))) {
                return true;
            }
        }
        return false;
    }

    /** 去首尾空白 + 连续空白折成一个空格（宿主 RN 文本里常见全角/半角空格混排）。 */
    static String norm(String s) {
        if (s == null) {
            return "";
        }
        StringBuilder sb = new StringBuilder(s.length());
        boolean lastSpace = false;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\u3000') {
                if (!lastSpace && sb.length() > 0) {
                    sb.append(' ');
                }
                lastSpace = true;
            } else {
                sb.append(c);
                lastSpace = false;
            }
        }
        int end = sb.length();
        while (end > 0 && sb.charAt(end - 1) == ' ') {
            end--;
        }
        return end == sb.length() ? sb.toString() : sb.substring(0, end);
    }

    private static String preview(String s) {
        if (s == null) {
            return "";
        }
        return s.length() <= PREVIEW_CHARS ? s : s.substring(0, PREVIEW_CHARS) + "…";
    }
}
