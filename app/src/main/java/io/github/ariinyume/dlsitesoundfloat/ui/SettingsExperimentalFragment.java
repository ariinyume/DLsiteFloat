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
 * 【code 1066 / 2.4.5 / B-2】实验卡 Fragment。
 * title/card 显隐仍由 Host {@link SettingsHost#applyExperimentalVisibility()} 协调。
 */
public final class SettingsExperimentalFragment extends Fragment {

    public static final String TAG = "settings_experimental";

    private LinearLayout mGroup;

    public void bindContainer(LinearLayout group) {
        mGroup = group;
    }

    public void rebuild(SettingsHost host) {
        if (host == null || mGroup == null) {
            return;
        }
        mGroup.removeAllViews();
        host.buildExperimentalGroup(mGroup);
    }
}
