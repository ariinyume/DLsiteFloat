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
 * 【code 1055 / 架构优化 B1】设置页草稿态 / 保存栏的**零状态纯裁决**。
 *
 * <p>从 {@link SettingsActivity} 抽出：滑块刻度对齐、语言中立脏态、分区未保存计数、
 * 保存栏显示模型、退出是否要确认。不碰 View / Dialog / ConfigStore。
 *
 * <p>口径照搬 Activity 原实现（PRD §9.1 / §6.3 / code 1028）：
 * <ul>
 *   <li>脏态是派生值：草稿与已保存参数不同即脏；</li>
 *   <li>{@code uiLanguage} 不进脏态（切语言立即独立落盘）；</li>
 *   <li>未保存读数按**分区**计，不是按字段计。</li>
 * </ul>
 */
public final class SettingsDraftPolicy {

    /** 浮点分区比较容差（与原 dirtySectionCount 一致）。 */
    public static final float FLOAT_EPS = 0.0001f;

    private SettingsDraftPolicy() {
    }

    /** 保存栏纯 UI 模型（不含 View）。 */
    public static final class SaveBarState {
        public final boolean dirty;
        /** 干净时为 0；脏时至少为 1（即使分区统计漏字段也有兜底）。 */
        public final int sectionDisplayCount;

        public SaveBarState(boolean dirty, int sectionDisplayCount) {
            this.dirty = dirty;
            this.sectionDisplayCount = sectionDisplayCount;
        }
    }

    /** 把只由滑块表达的浮点参数对齐到滑块刻度（原地修改）。 */
    public static void quantize(SubtitleConfig c) {
        if (c == null) {
            return;
        }
        c.activeScale = Math.round(c.activeScale * 10f) / 10f;
        c.lineSpacingDp = Math.round(c.lineSpacingDp * 2f) / 2f;
        c.wrapExtraSpacingDp = Math.round(c.wrapExtraSpacingDp * 2f) / 2f;
    }

    /**
     * 语言中立脏态：比较时忽略 {@code uiLanguage}，不改动入参字段。
     *
     * <p>实现用副本对齐语言再调 {@link SubtitleConfig#sameParametersAs}，避免 Activity
     * 里「临时改字段再还原」的写法。
     */
    public static boolean isDirty(SubtitleConfig draft, SubtitleConfig saved) {
        if (draft == null || saved == null) {
            return draft != saved;
        }
        SubtitleConfig probe = draft.copy();
        probe.uiLanguage = saved.uiLanguage;
        return !probe.sameParametersAs(saved);
    }

    /** 退出页是否弹未保存确认（= {@link #isDirty}）。 */
    public static boolean shouldConfirmUnsaved(SubtitleConfig draft, SubtitleConfig saved) {
        return isDirty(draft, saved);
    }

    /**
     * 「哪几块有未保存改动」—— 五分区：字幕面 / 行态 / 排版 / 液态玻璃 / 其他。
     * 不含 {@code uiLanguage}。
     */
    public static int dirtySectionCount(SubtitleConfig draft, SubtitleConfig saved) {
        if (draft == null || saved == null) {
            return 0;
        }
        int n = 0;
        // ① 字幕面
        if (draft.subtitleColor != saved.subtitleColor
                || draft.shadowColor != saved.shadowColor
                || draft.shadowStrength != saved.shadowStrength
                || draft.shadowRadius != saved.shadowRadius
                || draft.activeHighlight != saved.activeHighlight
                || Math.abs(draft.activeScale - saved.activeScale) > FLOAT_EPS) {
            n++;
        }
        // ② 行态面
        if (draft.inactiveBlurEnabled != saved.inactiveBlurEnabled
                || draft.inactiveBlurSteps != saved.inactiveBlurSteps
                || draft.inactiveHighlight != saved.inactiveHighlight
                || draft.inactiveScaleEnabled != saved.inactiveScaleEnabled
                || draft.inactiveScalePct != saved.inactiveScalePct) {
            n++;
        }
        // ③ 排版面
        if (!eq(draft.fontWeight, saved.fontWeight)
                || !eq(draft.textAlign, saved.textAlign)
                || Math.abs(draft.lineSpacingDp - saved.lineSpacingDp) > FLOAT_EPS
                || Math.abs(draft.wrapExtraSpacingDp - saved.wrapExtraSpacingDp) > FLOAT_EPS
                || draft.floatWindowColor != saved.floatWindowColor
                || draft.subtitleFontFollowSystem != saved.subtitleFontFollowSystem
                || draft.subtitleBold != saved.subtitleBold) {
            n++;
        }
        // ④ 液态玻璃
        if (draft.liquidGlass != saved.liquidGlass
                || draft.liquidGlassBlurPct != saved.liquidGlassBlurPct
                || draft.liquidGlassPanelLum != saved.liquidGlassPanelLum
                || draft.liquidGlassTransparency != saved.liquidGlassTransparency
                || draft.liquidGlassBackdropLum != saved.liquidGlassBackdropLum) {
            n++;
        }
        // ⑤ 其他 / 实验性
        if (draft.statusbarSubtitleEnabled != saved.statusbarSubtitleEnabled
                || draft.keepScreenOn != saved.keepScreenOn
                || draft.hotReload != saved.hotReload
                || draft.debugLog != saved.debugLog
                || draft.subtitleCacheEnabled != saved.subtitleCacheEnabled
                || draft.experimentalEnabled != saved.experimentalEnabled) {
            n++;
        }
        return n;
    }

    /** 脏时 {@code max(1, sectionCount)}，干净时 0。 */
    public static int unsavedSectionDisplayCount(SubtitleConfig draft, SubtitleConfig saved) {
        if (!isDirty(draft, saved)) {
            return 0;
        }
        return Math.max(1, dirtySectionCount(draft, saved));
    }

    public static SaveBarState saveBarState(SubtitleConfig draft, SubtitleConfig saved) {
        boolean dirty = isDirty(draft, saved);
        int sections = dirty ? Math.max(1, dirtySectionCount(draft, saved)) : 0;
        return new SaveBarState(dirty, sections);
    }

    private static boolean eq(String a, String b) {
        return a == null ? b == null : a.equals(b);
    }
}
