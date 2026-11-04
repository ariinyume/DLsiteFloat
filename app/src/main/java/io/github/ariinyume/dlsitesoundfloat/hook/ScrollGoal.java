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

import android.graphics.Paint;
import android.graphics.Rect;

/**
 * 「这一行该滚多远」的**纯计算内核**：三口径文本宽度测量 → 目标像素 → 就近吸附到字符边界。
 *
 * <p>从 {@link StatusBarSubtitleHook} 抽出的第二块零状态内核。它不认识 View、不认识滚动状态机，
 * 只吃 {@link Paint} + 文本 + 可视宽 + 排版宽，吐一个 {@link Goal}。所有 {@code LogGate} 日志文案
 * 也在这里拼好（{@code snapLog} / {@code nudgeLog}），调用方只负责「打不打」和加 TAG 前缀 ——
 * 这样「行为零变化」连日志文本都能逐字比对。
 *
 * <h3>为什么要三口径（adv / ink / layout）再取最大</h3>
 * <ul>
 *   <li>只取 {@code measureText}（adv）会漏掉字形外溢 —— 真机 code 968 报「末字差一点」；</li>
 *   <li>但无闸门地取最大会被**脏值**放大：真机 code 969 实测 {@code getLayout().getWidth()}
 *       在「尚未完成一次真实 layout」时返回 <b>1048576（=1024×1024）</b>，纳入 max ⇒
 *       目标 ≈105 万像素 ⇒ 字幕以 420px/s 滑出屏幕（用户报「直接飞走」）。</li>
 * </ul>
 * 所以每个口径都要先过 {@code adv + tolerance} 的合理性闸门，再取最大。
 */
final class ScrollGoal {

    private ScrollGoal() {
    }

    /** 计算结果。日志字段是**待打印的整句**，null 表示这条不该打（与原实现的「只打一次」旗标等价）。 */
    static final class Goal {
        /** 滚动终点（px）。0 = 放得下，不用滚。 */
        final int target;
        /** 三口径诊断串，原样进 {@code sLastMeasure}。 */
        final String measure;
        /** layout 宽度是否被判为脏值（调用方据此落 {@code sLayoutRejected}）。 */
        final boolean layoutRejected;
        /** 被判脏值时的原始 layout 宽与 adv，供「!! layout width abnormal」日志。 */
        final int rejectedLayoutW;
        final int rejectedAdv;
        /** 「就近吸附选了哪一侧」日志（只该打一次）；null = 不打。 */
        final String snapLog;
        /** 「末尾微调」日志（只该打一次）；null = 不打。 */
        final String nudgeLog;

        Goal(int target, String measure, boolean layoutRejected, int rejectedLayoutW,
             int rejectedAdv, String snapLog, String nudgeLog) {
            this.target = target;
            this.measure = measure;
            this.layoutRejected = layoutRejected;
            this.rejectedLayoutW = rejectedLayoutW;
            this.rejectedAdv = rejectedAdv;
            this.snapLog = snapLog;
            this.nudgeLog = nudgeLog;
        }
    }

    /**
     * 【2026-11-04 拆「量 / 判」】**测量结果** —— 唯一需要 Android 的那一段的产物。
     *
     * <p>为什么要有它：可测性的瓶颈不是「状态散在字段里」，而是「计算坐在 {@link Paint} 上」
     * （纯 JVM 测试里造不出 Paint，所以这个内核抽出来一年了仍然零测试）。
     * 把「量」（{@link #measure}，碰 Paint）与「判」（{@link #plan}，纯 int）切开之后，
     * {@code plan} 就能用「造假边界数组」的方式单测 —— 969/970/971/974 那一串
     * 「半字 / 留白 / 末字被裁」的判定终于有了回归网。
     *
     * <p>字段全部是 {@code measure} 那一刻的**快照**：{@code plan} 不再回头问 Paint，
     * 也就不会出现「同一次计算里量了两遍、中间 Paint 被改过」这种不一致。
     */
    static final class Metrics {
        /** advance 宽（{@code ceil(measureText)}）。 */
        final int adv;
        /** 字形墨迹右边界（≥ adv 时才算数，已过合理性闸门）。 */
        final int ink;
        /** 采信后的排版宽；{@code layoutWidth<=0} 或判为脏值时就等于 adv。 */
        final int layout;
        /** layout 宽是否被判为脏值（1024×1024 那类）。 */
        final boolean layoutRejected;
        /** 被判脏值时的**原始** layout 宽（供日志）。 */
        final int rawLayoutW;
        /** 字符起点数组：长度 = 字符数 + 1，末项 = 文本总宽；{@code null} = 不吸附。 */
        final int[] bounds;

        Metrics(int adv, int ink, int layout, boolean layoutRejected, int rawLayoutW,
                int[] bounds) {
            this.adv = adv;
            this.ink = ink;
            this.layout = layout;
            this.layoutRejected = layoutRejected;
            this.rawLayoutW = rawLayoutW;
            this.bounds = bounds;
        }
    }

    /**
     * 【量】**唯一碰 {@link Paint} 的一步**：三口径宽度 + 字符边界。
     *
     * @param paint       字幕行的 Paint（字体/字号已经同步过，度量结果就是屏上所见）
     * @param text        当前行的文本
     * @param layoutWidth 排版宽；&lt;=0 表示「还没 layout 过 / 拿不到」，按 adv 处理
     * @param tolerance   合理性闸门容差（{@code MEASURE_TOLERANCE_PX}）
     */
    static Metrics measure(Paint paint, CharSequence cs, int layoutWidth, int tolerance) {
        String text = cs == null ? "" : cs.toString();
        int adv = (int) Math.ceil(paint.measureText(text));

        int ink = adv;
        try {
            Rect inkRect = new Rect();
            paint.getTextBounds(text, 0, text.length(), inkRect);
            int right = inkRect.right;
            if (right > 0 && right <= adv + tolerance) {
                ink = Math.max(ink, right);
            }
        } catch (Throwable ignored) {
            // 拿不到轮廓边界就退回 advance，不抛错
        }

        boolean rejected = false;
        int lay = adv;
        if (layoutWidth > 0) {
            if (layoutWidth <= adv + tolerance) {
                lay = Math.max(lay, layoutWidth);
            } else {
                // 脏值：只报一次，绝不采用（旗标由调用方落）
                rejected = true;
            }
        }
        return new Metrics(adv, ink, lay, rejected, layoutWidth,
                charBoundaries(paint, text));
    }

    /**
     * 【判】用 {@link Metrics} 算「这一行需要滚多远」——**纯 int，可单测**。
     *
     * @param m             {@link #measure} 的快照
     * @param viewW         可视宽（已扣掉左右 padding）
     * @param tailMargin    末尾保留的富余像素（{@code TAIL_MARGIN_PX}）
     * @param coverMargin   「期望被覆盖到」的额外富余（{@code COVER_MARGIN_PX}）
     * @param tolerance     合理性闸门容差（{@code MEASURE_TOLERANCE_PX}）
     * @param maxTailClip   向下吸附时允许裁掉末字的最大像素（{@code MAX_TAIL_CLIP_PX}）
     * @param maxNudge      末尾微调的最大挪动量（{@code MAX_NUDGE_PX}）
     */
    static Goal plan(Metrics m, int viewW, int tailMargin, int coverMargin, int tolerance,
                     int maxTailClip, int maxNudge) {
        String measure = "adv=" + m.adv + " ink=" + m.ink + " layout=" + m.layout
                + (m.layoutRejected ? "[rejected]" : "")
                + " calcW=" + viewW;

        int base = Math.max(Math.max(m.adv, m.ink), m.layout);
        // 终极保底：任何「比 advance 大出一个字宽以上」的度量都不可信
        if (base > m.adv + tolerance) {
            base = m.adv + tolerance;
        }
        if (base <= viewW) {
            // 放得下 -> 不滚（保持旧判据）；此时**不做**吸附与微调（与原实现一致）
            return new Goal(0, measure, m.layoutRejected, m.rawLayoutW, m.adv, null, null);
        }
        int raw = base + tailMargin - viewW;
        // 出口保底：滚动量绝不该超过文本总宽（超过就是滚到文本之外 = 满屏空白）
        if (raw > m.adv) {
            raw = m.adv;
        }
        Snap snap = snap(raw, m.bounds, viewW, base + coverMargin,
                coverMargin, maxTailClip, maxNudge);
        return new Goal(snap.value, measure, m.layoutRejected, m.rawLayoutW, m.adv,
                snap.sideLog, snap.nudgeLog);
    }

    /**
     * 算「这一行需要滚多远」（原入口，保留为**一行薄封装**，调用方零改动）。
     *
     * @param paint        字幕行的 Paint（字体/字号已经同步过，度量结果就是屏上所见）
     * @param text         当前行的文本
     * @param viewW        可视宽（已扣掉左右 padding）
     * @param layoutWidth  排版宽；&lt;=0 表示「还没 layout 过 / 拿不到」，按 adv 处理
     * @param tailMargin   末尾保留的富余像素（{@code TAIL_MARGIN_PX}）
     * @param coverMargin  「期望被覆盖到」的额外富余（{@code COVER_MARGIN_PX}）
     * @param tolerance    合理性闸门容差（{@code MEASURE_TOLERANCE_PX}）
     * @param maxTailClip  向下吸附时允许裁掉末字的最大像素（{@code MAX_TAIL_CLIP_PX}）
     * @param maxNudge     末尾微调的最大挪动量（{@code MAX_NUDGE_PX}）
     */
    static Goal compute(Paint paint, CharSequence cs, int viewW, int layoutWidth,
                        int tailMargin, int coverMargin, int tolerance,
                        int maxTailClip, int maxNudge) {
        return plan(measure(paint, cs, layoutWidth, tolerance),
                viewW, tailMargin, coverMargin, tolerance, maxTailClip, maxNudge);
    }

    /** 吸附结果：终点 + 两条日志（哪一侧 / 有没有微调）。 */
    private static final class Snap {
        final int value;
        final String sideLog;
        final String nudgeLog;

        Snap(int value, String sideLog, String nudgeLog) {
            this.value = value;
            this.sideLog = sideLog;
            this.nudgeLog = nudgeLog;
        }
    }

    /**
     * 文本里每个**字符起点的 x 坐标**（相对文本起点），末项 = 文本总宽。
     *
     * <p>用 {@link Paint#getTextWidths} 逐字累加 —— 它给的是每个字的**步进宽度**，
     * 和 {@code measureText}（整体宽度）同源，所以边界值与文本总宽自洽。
     *
     * @return 长度 = 字符数 + 1；任何异常（字体度量拿不到）都返回 {@code null} 表示「不吸附」
     */
    static int[] charBoundaries(Paint p, String text) {
        if (p == null || text == null || text.isEmpty()) {
            return null;
        }
        int n = text.length();
        float[] adv = new float[n];
        try {
            if (p.getTextWidths(text, adv) < n) {
                return null;
            }
        } catch (Throwable t) {
            return null;
        }
        int[] b = new int[n + 1];
        float acc = 0f;
        for (int i = 0; i < n; i++) {
            if (adv[i] <= 0f) {
                return null;   // 度量异常 -> 宁可不吸附，也不要算出坏值把滚动带偏
            }
            b[i] = (int) Math.round(acc);
            acc += adv[i];
        }
        b[n] = (int) Math.ceil(acc);
        return b;
    }

    /**
     * 【2.2.0 半字根修·第二处】把滚动终点**就近吸附到字符边界**上。
     *
     * <h3>为什么</h3>
     * 终点是一个**像素值**，几乎必然落在某个字的中间。滚到底停下时，可视区
     * **左边缘**就正好切在那个字中间 ⇒ 状态栏最左边永久挂着「半个字」。
     *
     * <h3>怎么吸（code 971 起 =「就近」）</h3>
     * 取「**离 target 最近的字符边界**」，而不是旧版的「≥ target 的最小边界」。
     * 旧版只向右取，终点最多被推远**一个整字宽**（真机 13:34 日志统计：25/25 条
     * 起滚记录过冲全为正，中位 32px、最大 40px ≈ 一个字）—— 这就是用户报的
     * 「每句后面多了一大块空白」。改成就近后，过冲最多半个字，空白直接砍半。
     *
     * <p>⚠️ 但「向下取」有一个前提：取到 {@code target} 左边的边界后，可视区必须
     * **仍能盖住末尾**（{@code lower + viewW >= coverNeed}）—— 否则末字会被重新裁掉，
     * 那正是 969/970 花大力气修掉的问题。不满足就退回右边界的 {@code upper}。
     * 换句话说：就近是「能就近就就近，不能就近就保住末字完整」。
     *
     * <p>⚠️ 上界保护：吸附值不会超过「**最后一个字的起点**」—— 否则可视区会整段
     * 滑到文本之外（全空白）。正常机型的可视宽（真机 508px）远大于一个字宽，
     * 该保护不会生效；它只防「可视宽 &lt; 一个字宽」这种退化情形。
     */
    private static Snap snap(int target, int[] bounds, int viewW, int coverNeed,
                             int coverMargin, int maxTailClip, int maxNudge) {
        if (target <= 0) {
            return new Snap(0, null, null);
        }
        int[] b = bounds;
        if (b == null || b.length < 2) {
            return new Snap(target, null, null);   // 拿不到边界就不吸（保守：维持原行为）
        }
        final int maxSnap = b[b.length - 2];   // 最后一个字的起点
        // 找 target 两侧最近的边界：lower = ≤target 的最大边界，upper = ≥target 的最小边界
        int lower = -1;
        int upper = -1;
        for (int v : b) {
            if (v <= target) {
                lower = v;
            }
            if (upper < 0 && v >= target) {
                upper = Math.min(v, maxSnap);
            }
        }
        if (upper < 0) {
            // target 比整段文本还长（说明上游输入异常，正常路径不可能走到）⇒
            // 保底回落到「最后一个字的起点」：至少能看到末尾，而不是把视窗整段滑到文本之外。
            return new Snap(Math.min(target, maxSnap), null, null);
        }
        // 【code 971 就近吸附】取离 target 最近的字符边界（左或右），把过冲从
        //   「最多一个字宽」压到「最多半个字宽」。
        //
        //   ⚠️ 「向下取」会裁掉末尾一点 —— 这是「留白」与「切末字」的此消彼长：
        //   可视宽不是字宽的整数倍时，右对齐点（adv - viewW）几乎总落在字中间，
        //   向左取边界 = 末字被裁，向右取边界 = 句尾留白。真机 13:34 实测过冲 +32px
        //   （「金枪鱼」句：adv=882/viewW=371，theory=514 落在边界 504 与 546 之间，
        //   向右取 546 留白 32px）。
        //
        //   ⇒ 折中：向下取时**允许末字被裁 ≤ maxTailClip**
        //   （code 974 起 = 6px ≈ 1/7 字宽，句尾多为标点/语气词，肉眼几乎不可见；
        //    比 969 修掉的 5px 硬切更轻，且只发生在「恰好卡在边界」的少数句子上）。
        //   裁切超限就退回右边界，保住末字完整。这样过冲最多半个字、多数句子直接压到 0。
        int chosen = upper;
        String sideLog = null;
        if (lower >= 0) {
            int tailBase = coverNeed - coverMargin;   // = base（文本真实宽）
            int clip = tailBase - (lower + viewW);    // 向下取会裁掉末字的量（>0 表示裁）
            boolean lowerAcceptable = viewW <= 0 || clip <= maxTailClip;
            int toUpper = upper - target;
            int toLower = target - lower;
            if (lowerAcceptable && toLower < toUpper) {
                chosen = lower;
            }
            sideLog = " snap: target=" + target + " lower=" + lower
                    + " upper=" + upper + " -> " + chosen
                    + (chosen == lower ? " [nearer-lower]" : " [upper]")
                    + (lowerAcceptable ? "" : " (lower clips tail " + clip + "px)");
        }
        // 微调：选中边界仍包不住 coverNeed 时，往右挪「差的那一点点」（限 maxNudge）
        if (viewW > 0 && chosen + viewW < coverNeed) {
            int ideal = coverNeed - viewW;
            int nudge = ideal - chosen;
            if (nudge > 0 && nudge <= maxNudge && ideal <= maxSnap) {
                String nudgeLog = " tail nudge: " + chosen + " -> " + ideal
                        + "px (+" + nudge + "px, coverNeed=" + coverNeed
                        + ", viewW=" + viewW + ") [keeps tail fully visible]";
                return new Snap(ideal, sideLog, nudgeLog);
            }
        }
        return new Snap(chosen, sideLog, null);
    }
}
