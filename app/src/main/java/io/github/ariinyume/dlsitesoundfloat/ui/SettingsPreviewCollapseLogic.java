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
 * 【code 1062 / 架构优化 B1】设置页预览卡**折叠几何**零状态数学。
 *
 * <p>从 {@link SettingsActivity#applyPreviewFraction} /
 * {@link SettingsActivity#applyPreviewClip} /
 * {@link SettingsActivity#refreshPreviewMetrics} 抽出。View.measure /
 * ValueAnimator / clipBounds 副作用仍在 Activity。
 *
 * <p>窗口行口径：{@link #WINDOW_FIRST}..{@link #WINDOW_LAST} = 非活动 / 活动 / 非活动
 * （与 {@code PREVIEW_ACTIVE_INDEX=2} 同套下标）。
 */
public final class SettingsPreviewCollapseLogic {

    public static final int WINDOW_FIRST = 1;
    public static final int WINDOW_LAST = 3;

    /** 与 {@code ViewGroup.LayoutParams.WRAP_CONTENT} 同值（-2）。 */
    public static final int HEIGHT_WRAP = -2;

    /** 裁剪上下界（内容坐标）；Activity 再包成 {@code Rect(0,top,w,bottom)}。 */
    public static final class ClipBounds {
        public final int top;
        public final int bottom;

        public ClipBounds(int top, int bottom) {
            this.top = top;
            this.bottom = bottom;
        }
    }

    /** 折叠尺寸缓存（对应 Activity 的 mPreview* 字段）。 */
    public static final class CollapsedMetrics {
        public final int fullH;
        public final int winH;
        public final int winDy;
        public final int clipTop;
        public final int clipBottom;
        public final boolean valid;

        public CollapsedMetrics(int fullH, int winH, int winDy, int clipTop, int clipBottom,
                boolean valid) {
            this.fullH = fullH;
            this.winH = winH;
            this.winDy = winDy;
            this.clipTop = clipTop;
            this.clipBottom = clipBottom;
            this.valid = valid;
        }
    }

    private SettingsPreviewCollapseLogic() {
    }

    /**
     * 卡片目标高度。{@code f<=0} → {@link #HEIGHT_WRAP}；{@code f>=1} → winH；
     * 中间线性插值。
     */
    public static int cardHeightPx(int fullH, int winH, float f) {
        if (f <= 0f) {
            return HEIGHT_WRAP;
        }
        if (f >= 1f) {
            return winH;
        }
        return Math.round(fullH + (winH - fullH) * f);
    }

    public static float contentTranslationY(int winDy, float f) {
        return -winDy * f;
    }

    /**
     * f≤0 或几何非法 → null（调用方 {@code setClipBounds(null)}）。
     * 底部保证 {@code bottom > top}。
     */
    public static ClipBounds clipBoundsOrNull(float f, int clipTop, int clipBottom,
            int fullH, int contentWidth) {
        if (f <= 0f || clipTop <= 0 || clipBottom <= clipTop
                || contentWidth <= 0 || fullH <= 0) {
            return null;
        }
        int top = Math.round(clipTop * f);
        int bottom = Math.round(fullH + (clipBottom - fullH) * f);
        if (bottom <= top) {
            bottom = top + 1;
        }
        return new ClipBounds(top, bottom);
    }

    /**
     * 按子行实测高度累加窗口。窗口行非法 → {@code null}（Activity 早退不更新缓存）。
     *
     * @param measuredFullH {@code preview_lines} 的 measuredHeight（不是子高之和）
     */
    public static CollapsedMetrics fromChildHeights(int paddingTop, int[] childHeights,
            int first, int last, int measuredFullH) {
        if (childHeights == null || childHeights.length <= last) {
            return null;
        }
        int y = paddingTop;
        int winTop = -1;
        int winBottom = -1;
        for (int i = 0; i < childHeights.length; i++) {
            if (i == first) {
                winTop = y;
            }
            y += childHeights[i];
            if (i == last) {
                winBottom = y;
            }
        }
        if (winTop < 0 || winBottom <= winTop) {
            return null;
        }
        int winH = winBottom - winTop;
        boolean valid = measuredFullH > 0 && winH > 0 && winH < measuredFullH;
        return new CollapsedMetrics(measuredFullH, winH, winTop, winTop, winBottom, valid);
    }

    /** 首次未排版时推可用宽：优先 parentW，否则 screen − margin − pads。 */
    public static int inferContentWidth(int parentW, int screenW, int cardMarginPx,
            int padL, int padR) {
        if (parentW > 0) {
            return parentW;
        }
        return screenW - cardMarginPx - padL - padR;
    }
}
