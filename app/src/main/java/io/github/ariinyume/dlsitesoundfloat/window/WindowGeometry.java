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
package io.github.ariinyume.dlsitesoundfloat.window;

/**
 * 悬浮窗几何夹取（零状态纯函数）。
 *
 * <p>【code 1067】横竖屏切换时，已挂上的 overlay 窗口不会自动改宽高；按当前屏夹宽高与位置。
 *
 * <p>【code 1069–1076】夹进物理屏；inset 由调用方传入。
 * 【code 1076】竖屏 inset 多为 0；横屏顶缘 inset 应为 0（可贴顶），
 * 高度上限「屏高 − 状态栏」由调用方在夹取后再施加。
 */
public final class WindowGeometry {

    private WindowGeometry() {
    }

    /** 夹取后的窗口矩形（像素，相对 Gravity.TOP|START）。 */
    public static final class Rect {
        public final int x;
        public final int y;
        public final int width;
        public final int height;

        public Rect(int x, int y, int width, int height) {
            this.x = x;
            this.y = y;
            this.width = width;
            this.height = height;
        }

        public boolean equalsValues(int x, int y, int w, int h) {
            return this.x == x && this.y == y && this.width == w && this.height == h;
        }
    }

    /**
     * 把窗口几何夹进屏幕安全区。
     *
     * @param x           左上角 x
     * @param y           左上角 y
     * @param w           宽
     * @param h           高
     * @param screenW     屏宽（px）
     * @param screenH     屏高（px）
     * @param minW        宽度下限（px）
     * @param minH        高度下限（px）
     * @param maxHRatio   高度上限占<strong>可用高度</strong>的百分比（如 50）
     * @param insetL      左安全边距（px）
     * @param insetT      上安全边距（px）
     * @param insetR      右安全边距（px）——满宽时右缘内收，角标不贴屏边
     * @param insetB      下安全边距（px）
     */
    public static Rect clampToScreen(int x, int y, int w, int h,
            int screenW, int screenH, int minW, int minH, int maxHRatio,
            int insetL, int insetT, int insetR, int insetB) {
        if (screenW <= 0 || screenH <= 0) {
            return new Rect(x, y, w, h);
        }
        int left = clamp(insetL, 0, screenW);
        int top = clamp(insetT, 0, screenH);
        int right = Math.max(left + 1, screenW - Math.max(0, insetR));
        int bottom = Math.max(top + 1, screenH - Math.max(0, insetB));
        int usableW = right - left;
        int usableH = bottom - top;
        int maxH = Math.max(1, usableH * Math.max(0, maxHRatio) / 100);
        int loW = Math.min(Math.max(1, minW), usableW);
        int loH = Math.min(Math.max(1, minH), maxH);
        int cw = clamp(w, loW, usableW);
        int ch = clamp(h, loH, Math.min(maxH, usableH));
        int cx = clamp(x, left, Math.max(left, right - cw));
        int cy = clamp(y, top, Math.max(top, bottom - ch));
        return new Rect(cx, cy, cw, ch);
    }

    /** 无额外 inset 时的兼容入口（测试 / 旧调用）。 */
    public static Rect clampToScreen(int x, int y, int w, int h,
            int screenW, int screenH, int minW, int minH, int maxHRatio) {
        return clampToScreen(x, y, w, h, screenW, screenH, minW, minH, maxHRatio,
                0, 0, 0, 0);
    }

    /** 仅夹位置（尺寸已合法时拖动用）；同样遵守安全区。 */
    public static Rect clampPosition(int x, int y, int w, int h,
            int screenW, int screenH, int insetL, int insetT, int insetR, int insetB) {
        if (screenW <= 0 || screenH <= 0) {
            return new Rect(x, y, w, h);
        }
        int left = clamp(insetL, 0, screenW);
        int top = clamp(insetT, 0, screenH);
        int right = Math.max(left + 1, screenW - Math.max(0, insetR));
        int bottom = Math.max(top + 1, screenH - Math.max(0, insetB));
        int usableW = right - left;
        int usableH = bottom - top;
        int cw = Math.min(Math.max(1, w), usableW);
        int ch = Math.min(Math.max(1, h), usableH);
        int cx = clamp(x, left, Math.max(left, right - cw));
        int cy = clamp(y, top, Math.max(top, bottom - ch));
        return new Rect(cx, cy, cw, ch);
    }

    public static Rect clampPosition(int x, int y, int w, int h, int screenW, int screenH) {
        return clampPosition(x, y, w, h, screenW, screenH, 0, 0, 0, 0);
    }

    private static int clamp(int v, int lo, int hi) {
        if (lo > hi) {
            return hi;
        }
        return Math.max(lo, Math.min(hi, v));
    }
}
