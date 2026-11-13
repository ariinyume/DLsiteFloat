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

import io.github.ariinyume.dlsitesoundfloat.config.SubtitleConfig;

/**
 * 【code 1063 / 架构优化 B1】外观三面「恢复默认」的零状态字段赋值。
 *
 * <p>从 {@link SettingsActivity} 的 {@code resetXxxValues} 抽出；Snack / syncWidgets
 * 仍在 Activity。
 */
public final class SettingsResetLogic {

    private SettingsResetLogic() {
    }

    /** 字幕面：颜色 / 阴影 / 活动行不透明度 / 放大倍数。 */
    public static void resetMain(SubtitleConfig d) {
        if (d == null) {
            return;
        }
        d.subtitleColor = SubtitleConfig.SUBTITLE_COLOR_DEF;
        d.shadowColor = SubtitleConfig.SHADOW_COLOR_DEF;
        d.shadowStrength = SubtitleConfig.SHADOW_STRENGTH_DEF;
        d.shadowRadius = SubtitleConfig.SHADOW_RADIUS_DEF;
        d.activeHighlight = SubtitleConfig.HIGHLIGHT_DEF;
        d.activeScale = SubtitleConfig.ACTIVE_SCALE_DEF;
    }

    /** 行态面：模糊 / 非活动不透明度 / 缩放。 */
    public static void resetInactive(SubtitleConfig d) {
        if (d == null) {
            return;
        }
        d.inactiveBlurEnabled = true;
        d.inactiveBlurSteps = SubtitleConfig.BLUR_STEPS_DEF;
        d.inactiveHighlight = SubtitleConfig.INACTIVE_HIGHLIGHT_DEF;
        d.inactiveScaleEnabled = true;
        d.inactiveScalePct = SubtitleConfig.INACTIVE_SCALE_PCT_DEF;
    }

    /** 排版面：对齐 / 行距 / 悬浮窗色 / 字体跟随 / 加粗。 */
    public static void resetTypo(SubtitleConfig d) {
        if (d == null) {
            return;
        }
        d.fontWeight = SubtitleConfig.WEIGHT_SYSTEM;
        d.textAlign = SubtitleConfig.ALIGN_CENTER;
        d.lineSpacingDp = SubtitleConfig.LINE_SPACING_DEF;
        d.wrapExtraSpacingDp = SubtitleConfig.WRAP_SPACING_DEF;
        d.floatWindowColor = SubtitleConfig.FLOAT_WINDOW_COLOR_DEF;
        d.subtitleFontFollowSystem = false;
        d.subtitleBold = false;
    }
}
