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
package io.github.ariinyume.dlsitesoundfloat.ui;

import java.util.Locale;

/**
 * 【code 1063 / 架构优化 B1】设置页滑块读数的零状态格式化。
 *
 * <p>从 {@link SettingsActivity} 抽出 {@code fmtScale}/{@code fmtDp}/{@code fmtOneDecimal}。
 * View / Strings 拼接仍在 Activity。
 */
public final class SettingsDisplayFormatLogic {

    private SettingsDisplayFormatLogic() {
    }

    /** 滑块刻度（×10）→ 倍数文本，如 {@code 8 → "0.8"}。 */
    public static String fmtScale(int tick) {
        return String.format(Locale.ROOT, "%.1f", tick / 10f);
    }

    /** dp 值：整数省略小数，否则一位小数。 */
    public static String fmtDp(float v) {
        if (Math.abs(v - Math.round(v)) < 0.01f) {
            return String.valueOf(Math.round(v));
        }
        return String.format(Locale.ROOT, "%.1f", v);
    }

    /** 模糊半径等：始终一位小数。 */
    public static String fmtOneDecimal(float v) {
        return String.format(Locale.ROOT, "%.1f", v);
    }

    /**
     * {@code inactive_scale_pct}（50–180）↔ 滑块 ×10 刻度（5–18）。
     * 与活动行放大倍数滑块同一套刻度语义。
     */
    public static int inactiveScalePctToTick(int pct) {
        return Math.round(pct / 10f);
    }

    public static int inactiveScaleTickToPct(int tick) {
        return tick * 10;
    }
}
