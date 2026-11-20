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

import android.view.View;
import android.widget.LinearLayout;

/**
 * 【优化 P1-5】液态玻璃卡行工厂编排 —— 从 {@link SettingsActivity} 下沉，
 * 由 {@link SettingsLiquidGlassFragment} 调用；具体控件创建仍经 {@link Ops} 回 Host。
 *
 * <p>顺序与原 {@code buildLiquidGlassGroup} 一字对齐：总开关 → 四滑条 → 恢复默认 →
 * 钉底距 → 子行显隐。Host 负责草稿字段与 {@code addSwitchRow}/{@code addSliderRow}。
 */
public final class SettingsLiquidGlassRows {

    private SettingsLiquidGlassRows() {
    }

    /**
     * Host 侧能力：创建行控件、落草稿、钉底距、按总开关显隐子行。
     * 实现留在 Activity（行控件类型仍是其私有嵌套类）。
     */
    public interface Ops {
        void addMasterSwitch(LinearLayout parent);

        void addBackdropLum(LinearLayout parent);

        void addTransparency(LinearLayout parent);

        void addPanelLum(LinearLayout parent);

        void addBlur(LinearLayout parent);

        void addReset(LinearLayout parent);

        void pinCardLastBottom(LinearLayout parent, View lastChild);

        void applyChildrenVisibility();
    }

    public static void build(LinearLayout parent, Ops ops) {
        if (parent == null || ops == null) {
            return;
        }
        ops.addMasterSwitch(parent);
        ops.addBackdropLum(parent);
        ops.addTransparency(parent);
        ops.addPanelLum(parent);
        ops.addBlur(parent);
        ops.addReset(parent);
        if (parent.getChildCount() > 0) {
            ops.pinCardLastBottom(parent, parent.getChildAt(parent.getChildCount() - 1));
        }
        ops.applyChildrenVisibility();
    }
}
