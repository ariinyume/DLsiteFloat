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

import java.util.HashMap;
import java.util.Map;

/**
 * 【code 1066 / 2.4.5 / B-0】设置页行引用登记表。
 *
 * <p>语言切换会 {@code removeAllViews} 整卡重建；Fragment / Host 经本表登记
 * 最新控件，避免散落字段在重建后指到已摘除的 View。现有 {@code mRow*} 仍可并存，
 * 新路径优先 {@link #put}/{@link #get}。
 */
public final class SettingsRowRegistry {

    public static final String APPEARANCE_PAGE = "appearance_page";

    private final Map<String, Object> m = new HashMap<>();

    public void clear() {
        m.clear();
    }

    public void put(String key, Object value) {
        if (key == null) {
            return;
        }
        if (value == null) {
            m.remove(key);
        } else {
            m.put(key, value);
        }
    }

    @SuppressWarnings("unchecked")
    public <T> T get(String key) {
        return (T) m.get(key);
    }

    public boolean contains(String key) {
        return m.containsKey(key);
    }
}
