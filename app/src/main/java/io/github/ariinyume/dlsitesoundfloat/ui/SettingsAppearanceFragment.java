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

import androidx.fragment.app.Fragment;

/**
 * 【code 1066 / 2.4.5 / B-1】外观卡 Fragment —— 持有页签下标；三面行经 {@link SettingsHost}。
 */
public final class SettingsAppearanceFragment extends Fragment {

    public static final String TAG = "settings_appearance";

    private LinearLayout mMain;
    private LinearLayout mInactive;
    private LinearLayout mTypo;
    private int mPage;

    public void bindContainers(LinearLayout main, LinearLayout inactive, LinearLayout typo) {
        mMain = main;
        mInactive = inactive;
        mTypo = typo;
    }

    public int page() {
        return mPage;
    }

    public void setPage(int page) {
        mPage = SettingsAppearanceLogic.clampPage(page);
    }

    public void rebuild(SettingsHost host) {
        if (host == null || mMain == null || mInactive == null || mTypo == null) {
            return;
        }
        mMain.removeAllViews();
        host.buildMainGroup(mMain);
        mInactive.removeAllViews();
        host.buildInactiveGroup(mInactive);
        mTypo.removeAllViews();
        host.buildTypoGroup(mTypo);
        host.buildAppearanceTabs();
        host.selectAppearancePage(mPage);
        host.rowRegistry().put(SettingsRowRegistry.APPEARANCE_PAGE, Integer.valueOf(mPage));
    }
}
