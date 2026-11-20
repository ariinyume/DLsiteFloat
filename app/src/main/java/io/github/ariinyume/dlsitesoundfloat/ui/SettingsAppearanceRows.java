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
package io.github.ariinyume.dlsitesoundfloat.ui;

import android.widget.LinearLayout;

/**
 * 【优化 P1-5】外观卡三面行编排 —— 由 {@link SettingsAppearanceFragment} 拥有调用顺序；
 * 具体行仍经 {@link Ops} 回 Host（颜色/滑条/开关工厂尚未整块搬出 Activity）。
 */
public final class SettingsAppearanceRows {

    private SettingsAppearanceRows() {
    }

    public interface Ops {
        void buildMain(LinearLayout parent);

        void buildInactive(LinearLayout parent);

        void buildTypo(LinearLayout parent);

        void buildTabs();

        void selectPage(int page);

        void rememberPage(int page);
    }

    public static void rebuild(LinearLayout main, LinearLayout inactive, LinearLayout typo,
            int page, Ops ops) {
        if (ops == null || main == null || inactive == null || typo == null) {
            return;
        }
        main.removeAllViews();
        ops.buildMain(main);
        inactive.removeAllViews();
        ops.buildInactive(inactive);
        typo.removeAllViews();
        ops.buildTypo(typo);
        ops.buildTabs();
        ops.selectPage(page);
        ops.rememberPage(page);
    }
}
