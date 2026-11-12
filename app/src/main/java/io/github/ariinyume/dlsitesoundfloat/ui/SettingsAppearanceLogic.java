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
 * 【code 1057 / 架构优化 B1】外观三页签的**零状态索引逻辑**。
 *
 * <p>页签顺序契约：0=字幕面 / 1=行态面 / 2=排版面（与 {@code SettingsActivity} 三组
 * LinearLayout 下标对齐）。View 显隐与配色仍在 Activity。
 */
public final class SettingsAppearanceLogic {

    /** 外观子面数量（字幕 / 行态 / 排版）。 */
    public static final int PAGE_COUNT = 3;

    public static final int PAGE_SUBTITLE = 0;
    public static final int PAGE_INACTIVE = 1;
    public static final int PAGE_TYPO = 2;

    private SettingsAppearanceLogic() {
    }

    /** 非法下标回落 0（与原 {@code selectAppearancePage} 一致）。 */
    public static int clampPage(int page) {
        if (page < 0 || page >= PAGE_COUNT) {
            return PAGE_SUBTITLE;
        }
        return page;
    }

    /** 第 {@code index} 面在选中 {@code selectedPage} 时是否应可见。 */
    public static boolean pageVisible(int index, int selectedPage) {
        int sel = clampPage(selectedPage);
        return index >= 0 && index < PAGE_COUNT && index == sel;
    }

    /** 页签按钮是否为选中态。 */
    public static boolean tabSelected(int tabIndex, int selectedPage) {
        return pageVisible(tabIndex, selectedPage);
    }
}
