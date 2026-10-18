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
package io.github.ariinyume.dlsitesoundfloat.util;

import android.util.DisplayMetrics;
import android.widget.TextView;

/**
 * 【code 1024 / P1-7】宿主字幕控件「长什么样」—— 字号与文字色的**只读采样点**。
 *
 * <h3>── 为什么需要它（体检报告 P1-7）──</h3>
 * 宿主的字幕样式来自它自己的 bundle 常量（字号 / 行数 / 字号倍率上限都在里面），
 * 而本模块有一套自己的样式参数（字号基准 17sp、颜色、字重、阴影……）。两套参数各调一遍，
 * 用户要重复调参；更常见的是「宿主字号比插件大，一眼能看出这不是一个东西」。
 *
 * <h3>── 数据从哪来（不是猜的）──</h3>
 * {@code SubtitleViewHook} 的抓屏本来就会拿到宿主字幕控件上的**文本**（判据是
 * 「文本 ∈ 已加载 cue 列表」）。既然那个控件就在手上，顺手读它的
 * {@link TextView#getTextSize()}（px）与 {@link TextView#getCurrentTextColor()} 即可 ——
 * 这是宿主**真正上屏的那一份**样式，比解 bundle 常量可靠。
 *
 * <h3>── 怎么用（默认不影响任何人）──</h3>
 * 只有设置页打开「跟随宿主字幕样式」时，{@code FloatingSubtitleView} 才会来读这里的值；
 * 读不到（宿主还没渲染过字幕）就静默退回用户自己的配置。默认**关** ——
 * 既有用户的观感不会因为升级而被动变化。
 *
 * <h3>── 为什么存 px、不直接存 sp ──</h3>
 * {@code getTextSize()} 返回的是**已经乘过 scaledDensity（density × fontScale）**的 px。
 * 想还原成「喂给 {@code setTextSize(SP, x)} 之后能画出同样大小」的数值，必须再除一次
 * scaledDensity —— 用 {@link #textSizeSp(DisplayMetrics)}，不要自己除 density，
 * 否则用户把系统字体调大时会被重复放大（真机上一眼就能看出来）。
 *
 * <p>线程模型：只在宿主进程内使用（写入方与读取方同进程）；字段 volatile，
 * 读侧永远拿到某个完整快照，不做加锁。
 */
public final class HostStyleProbe {

    private static final String TAG = "[DLsiteSoundFloat:HostStyle]";

    /** 判「换了一次样子」的容差（px）：小于它认为没变，避免每帧都刷 revision。 */
    private static final float SIZE_EPSILON_PX = 0.5f;

    /**
     * 合理的字号区间（px）。超出这个范围的一律不采信 ——
     * 抓屏是按「文本命中 cue 列表」认字幕的，万一某个别的大字号控件里恰好也有同样文案
     * （标题 / 歌词页），采信它会让悬浮窗的字号突然翻几倍。
     */
    private static final float MIN_PX = 8f;
    private static final float MAX_PX = 240f;

    /** 宿主字幕控件的字号（px）；{@code 0} = 还没采到。 */
    private static volatile float sTextSizePx = 0f;
    /** 宿主字幕控件的当前文字色（ARGB）；{@code 0} = 还没采到。 */
    private static volatile int sTextColor = 0;
    /** 采样版本号：字号或颜色真的变了才 +1（渲染端靠它决定要不要重算样式）。 */
    private static volatile int sRevision = 0;

    private static int sSamples = 0;

    private HostStyleProbe() {
    }

    /**
     * 采样一个「已确认是字幕」的控件。
     *
     * <p>调用点必须已经确认过「这个 View 上的文本就是宿主正在显示的字幕行」——
     * 本方法不做任何文本判定，只负责把样子记下来。
     */
    public static void offer(TextView tv) {
        if (tv == null) {
            return;
        }
        try {
            float px = tv.getTextSize();
            if (px < MIN_PX || px > MAX_PX) {
                return;                         // 不像字幕字号 ⇒ 不采信
            }
            int color = tv.getCurrentTextColor();
            boolean changed = Math.abs(px - sTextSizePx) > SIZE_EPSILON_PX || color != sTextColor;
            sTextSizePx = px;
            sTextColor = color;
            if (changed) {
                sRevision = sRevision + 1;      // 只有「样子真的变了」才配一次重算
            }
            if (sSamples++ == 0 || changed) {
                XposedCompat.log(TAG + " host subtitle style: size=" + px + "px color=#"
                        + String.format(java.util.Locale.US, "%08X", color)
                        + (sSamples > 1 ? " (changed)" : " (first)"));
            }
        } catch (Throwable ignored) {
            // 采样失败绝不影响抓屏主链路
        }
    }

    /** 有没有采到过宿主样式。 */
    public static boolean known() {
        return sTextSizePx > 0f;
    }

    /** 采样版本号（渲染端用它判断「要不要重算样式」）。 */
    public static int revision() {
        return sRevision;
    }

    /** 宿主字幕字号（px）；{@code 0} = 未知。 */
    public static float textSizePx() {
        return sTextSizePx;
    }

    /**
     * 宿主字幕字号换算成「喂给 {@code setTextSize(SP, x)} 能画出同样大小」的 sp。
     *
     * @return {@code 0} = 未知（调用方应退回自己的配置）
     */
    public static float textSizeSp(DisplayMetrics dm) {
        float px = sTextSizePx;
        if (px <= 0f) {
            return 0f;
        }
        float scaled = (dm == null || dm.scaledDensity <= 0f) ? 1f : dm.scaledDensity;
        return px / scaled;
    }

    /** 宿主字幕文字色（ARGB）；{@code 0} = 未知。 */
    public static int textColor() {
        return sTextColor;
    }

    /** 宿主字幕文字色是否可用（不透明度过低时用它会看不见，调用方应退回配置色）。 */
    public static boolean colorUsable() {
        int alpha = (sTextColor >>> 24) & 0xFF;
        return sTextSizePx > 0f && alpha >= 0x80;
    }

    /** 一行日志摘要（排查「跟随宿主到底跟到了什么」时看它）。 */
    public static String summary() {
        if (!known()) {
            return "unknown";
        }
        return String.format(java.util.Locale.US, "size=%.1fpx color=#%08X rev=%d",
                sTextSizePx, sTextColor, sRevision);
    }
}
