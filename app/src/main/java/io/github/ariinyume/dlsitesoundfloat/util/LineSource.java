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

package io.github.ariinyume.dlsitesoundfloat.util;

/**
 * 【code 1018 / 架构审查 2.3】状态栏字幕桥的**数据源接口**。
 *
 * <h3>为什么需要它</h3>
 * {@code StatusBarSubtitleBridge} 原先直接 {@code import data.SubtitleRepository}
 * 与 {@code data.SubtitleCue} —— 那是 {@code util → data} 的**反向依赖**。
 * {@code util} 是 13 个文件的公共底座，按约定应当是叶子包（谁都能依赖它、它不依赖任何人），
 * 这条边让包级依赖图成环 ⇒「改 util 要考虑会不会影响数据层」。
 *
 * <p>现在桥只依赖本接口；实现由数据层提供
 * （{@code SubtitleRepository implements LineSource}）——
 * 因此调用点传进去的**还是同一个仓库对象**，一个字都不用改。
 *
 * <h3>口径（逐条搬自桥里的原实现，未改语义）</h3>
 * <ul>
 *   <li>{@link #isPlayingOrUnknown()} —— 三态：hook 全挂时返回 true（宁可多显示，
 *       也不要把字幕弄没）；桥还额外套一层 try/catch 兜底。</li>
 *   <li>{@link #statusBarLine()} —— 取不到任何内容时返回<b>空串</b>（不是 null）；
 *       桥据此让 SystemUI 隐藏字幕。</li>
 *   <li>{@link #getCurrentCueDurationMs()} —— 0 = 未知，状态栏退回默认滚动时长。</li>
 *   <li>{@link #shouldShowNoSubtitles()} —— 桥的 {@code canToggle} 用它禁掉「无字幕」时的开启操作。</li>
 * </ul>
 *
 * <p>⚠️ 接口只暴露**算好的结果**，不暴露 {@code SubtitleCue} 之类的数据层类型 ——
 * 否则 {@code util → data} 会换个形式长回来。
 */
public interface LineSource {

    /** 是否处于「播放中」（三态：hook 全挂时返回 true）。 */
    boolean isPlayingOrUnknown();

    /** 当前该显示的字幕行（单行）；无内容 = 空串。 */
    String statusBarLine();

    /** 当前字幕行的播放时长（毫秒）；0 = 未知。 */
    long getCurrentCueDurationMs();

    /** 是否处于「本音轨无字幕」态（用于禁掉状态栏字幕开关）。 */
    boolean shouldShowNoSubtitles();
}
