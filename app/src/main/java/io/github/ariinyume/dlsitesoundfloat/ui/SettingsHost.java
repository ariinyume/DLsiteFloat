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

import android.widget.LinearLayout;

/**
 * 【code 1066 / 2.4.5 / B-0】设置页宿主契约 —— Fragment 只经此面访问行工厂与壳协调。
 *
 * <p>壳（AppBar / 预览 / 保存栏 / 状态卡 / 广播）仍在 {@link SettingsActivity}；
 * 四卡 Fragment 挂到已有 {@code group_*}，不改 XML 外壳。
 */
public interface SettingsHost {

    SettingsRowRegistry rowRegistry();

    void buildMainGroup(LinearLayout parent);

    void buildInactiveGroup(LinearLayout parent);

    void buildTypoGroup(LinearLayout parent);

    void buildAppearanceTabs();

    void selectAppearancePage(int page);

    void buildLiquidGlassGroup(LinearLayout parent);

    void buildMiscGroup(LinearLayout parent);

    void buildExperimentalGroup(LinearLayout parent);

    void applyStatusbarSwitchEnabled(boolean systemUiAuthorized);

    void applyExperimentalVisibility();
}
