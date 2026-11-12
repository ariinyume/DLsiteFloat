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

/**
 * 【code 1057 / 架构优化 B1】液态玻璃卡的**零状态门控**。
 *
 * <p>总开关以下子行显隐、悬浮窗颜色行置灰系数与是否可点。不改
 * {@code floatWindowColor} 键值（与 PRD §FR-07 同口径）。
 */
public final class SettingsLiquidGlassLogic {

    /** 液态玻璃开启时「悬浮窗颜色」行的置灰 alpha。 */
    public static final float PANEL_COLOR_LOCKED_ALPHA = 0.38f;
    public static final float PANEL_COLOR_OPEN_ALPHA = 1f;

    private SettingsLiquidGlassLogic() {
    }

    /** 总开关以下子行是否可见（= 液态玻璃开）。 */
    public static boolean childrenVisible(boolean liquidGlassOn) {
        return liquidGlassOn;
    }

    /** 悬浮窗颜色是否被锁（液态玻璃开 ⇒ 不可调）。 */
    public static boolean panelColorLocked(boolean liquidGlassOn) {
        return liquidGlassOn;
    }

    public static float panelColorAlpha(boolean liquidGlassOn) {
        return panelColorLocked(liquidGlassOn)
                ? PANEL_COLOR_LOCKED_ALPHA : PANEL_COLOR_OPEN_ALPHA;
    }

    /** 色板是否可交互（= 未锁定）。 */
    public static boolean panelColorInteractive(boolean liquidGlassOn) {
        return !panelColorLocked(liquidGlassOn);
    }
}
