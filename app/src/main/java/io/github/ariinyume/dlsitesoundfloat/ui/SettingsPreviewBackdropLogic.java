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
 * 【code 1061 / 架构优化 B1】设置页预览**面板渐变 alpha + 背景模糊**零状态数学。
 *
 * <p>从 {@link SettingsActivity#applyPreviewPanel} /
 * {@link SettingsActivity#previewBackdropFor} 抽出。Bitmap / Canvas / 缓存字段仍在
 * Activity。
 *
 * <p>模糊口径：对 n×n ARGB 做两遍可分离盒式模糊；半径的小数部分在 r0 与 r0+1
 * 两档结果间 {@link #lerpArgb}（{@code Math.round(255*f)} 定权）。
 */
public final class SettingsPreviewBackdropLogic {

    /** 色板 / 非液态预览顶部 alpha（≈57%，与渲染端增益口径对齐）。 */
    public static final int PANEL_PREVIEW_TOP_ALPHA = 0x92;
    /** 底部相对顶部的不透明比例分子（分母同 {@link #PANEL_PREVIEW_TOP_ALPHA}）。 */
    public static final int PANEL_PREVIEW_BOTTOM_ALPHA = 0x5B;

    public static final float BLUR_RADIUS_MAX_PX = 9f;
    public static final float LERP_FRAC_EPSILON = 0.005f;

    private SettingsPreviewBackdropLogic() {
    }

    public static int clampBlurPct(int pct) {
        return Math.max(0, Math.min(100, pct));
    }

    public static float blurRadiusPx(int pct) {
        return clampBlurPct(pct) / 100f * BLUR_RADIUS_MAX_PX;
    }

    /** floor + frac；{@code out[0]=r0}，{@code out[1]} 未用，frac 单独返回。 */
    public static float blurRadiusFrac(float rad, int[] floorOut) {
        int r0 = (int) Math.floor(rad);
        if (floorOut != null && floorOut.length > 0) {
            floorOut[0] = r0;
        }
        return rad - r0;
    }

    public static boolean shouldInterpolateBlur(float frac) {
        return frac > LERP_FRAC_EPSILON;
    }

    public static int panelPreviewBottomAlpha(int topAlpha) {
        return Math.max(0, Math.round(topAlpha * (PANEL_PREVIEW_BOTTOM_ALPHA
                / (float) PANEL_PREVIEW_TOP_ALPHA)));
    }

    /** 非液态预览垂直渐变两色（基色 RGB + 顶部/底部 alpha）。 */
    public static int[] panelPreviewGradientColors(int baseRgb) {
        int topA = PANEL_PREVIEW_TOP_ALPHA;
        int botA = panelPreviewBottomAlpha(topA);
        return new int[]{withAlpha(baseRgb, topA / 255f), withAlpha(baseRgb, botA / 255f)};
    }

    public static int withAlpha(int color, float alpha) {
        int a = Math.round(255 * SubtitleConfig.clampFloat(alpha, 0f, 1f));
        return (a << 24) | (color & 0x00FFFFFF);
    }

    public static int backdropSeed(int a, int b, int c, int d) {
        return a ^ (b * 31) ^ (c * 131) ^ (d * 3571);
    }

    /** 均值亮度 0..1（BT.601 近似权重，与原 ensurePreviewBackdropTile 一致）。 */
    public static float backdropLumFromArgb(int[] px) {
        if (px == null || px.length == 0) {
            return 0f;
        }
        long sum = 0;
        for (int v : px) {
            sum += (77 * ((v >> 16) & 0xFF) + 150 * ((v >> 8) & 0xFF) + 29 * (v & 0xFF)) >> 8;
        }
        return (sum / (float) px.length) / 255f;
    }

    public static int clampIndex(int v, int n) {
        return v < 0 ? 0 : (v >= n ? n - 1 : v);
    }

    public static int lerpArgb(int a, int b, float f) {
        final int g = Math.round(255 * f);
        final int ia = 255 - g;
        return ((((a >>> 24) * ia + (b >>> 24) * g) / 255) << 24)
                | (((((a >> 16) & 0xFF) * ia + ((b >> 16) & 0xFF) * g) / 255) << 16)
                | (((((a >> 8) & 0xFF) * ia + ((b >> 8) & 0xFF) * g) / 255) << 8)
                | (((a & 0xFF) * ia + (b & 0xFF) * g) / 255);
    }

    /** 两遍可分离盒式模糊；radius≤0 返回 clone。 */
    public static int[] blurTile(int[] src, int n, int radius) {
        int[] a = src.clone();
        if (radius <= 0) {
            return a;
        }
        int[] t = new int[a.length];
        for (int pass = 0; pass < 2; pass++) {
            blurTileH(a, t, n, radius);
            blurTileV(t, a, n, radius);
        }
        return a;
    }

    /**
     * 连续半径：在 floor(rad) 与 floor+1 两档间插值（与原 previewBackdropFor 一致）。
     */
    public static int[] blurTileInterpolated(int[] src, int n, float radiusPx) {
        int[] floorOut = new int[1];
        float frac = blurRadiusFrac(radiusPx, floorOut);
        int r0 = floorOut[0];
        int[] b0 = blurTile(src, n, r0);
        int[] out = blurTile(src, n, r0 + 1);
        if (shouldInterpolateBlur(frac)) {
            for (int i = 0; i < out.length; i++) {
                out[i] = lerpArgb(b0[i], out[i], frac);
            }
        } else {
            System.arraycopy(b0, 0, out, 0, out.length);
        }
        return out;
    }

    private static void blurTileH(int[] in, int[] out, int n, int r) {
        final int div = 2 * r + 1;
        for (int y = 0; y < n; y++) {
            final int row = y * n;
            int sa = 0, sr = 0, sg = 0, sb = 0;
            for (int i = -r; i <= r; i++) {
                int p = in[row + clampIndex(i, n)];
                sa += p >>> 24;
                sr += (p >> 16) & 0xFF;
                sg += (p >> 8) & 0xFF;
                sb += p & 0xFF;
            }
            for (int x = 0; x < n; x++) {
                out[row + x] = ((sa / div) << 24) | ((sr / div) << 16)
                        | ((sg / div) << 8) | (sb / div);
                int add = in[row + clampIndex(x + r + 1, n)];
                int sub = in[row + clampIndex(x - r, n)];
                sa += (add >>> 24) - (sub >>> 24);
                sr += ((add >> 16) & 0xFF) - ((sub >> 16) & 0xFF);
                sg += ((add >> 8) & 0xFF) - ((sub >> 8) & 0xFF);
                sb += (add & 0xFF) - (sub & 0xFF);
            }
        }
    }

    private static void blurTileV(int[] in, int[] out, int n, int r) {
        final int div = 2 * r + 1;
        for (int x = 0; x < n; x++) {
            int sa = 0, sr = 0, sg = 0, sb = 0;
            for (int i = -r; i <= r; i++) {
                int p = in[clampIndex(i, n) * n + x];
                sa += p >>> 24;
                sr += (p >> 16) & 0xFF;
                sg += (p >> 8) & 0xFF;
                sb += p & 0xFF;
            }
            for (int y = 0; y < n; y++) {
                out[y * n + x] = ((sa / div) << 24) | ((sr / div) << 16)
                        | ((sg / div) << 8) | (sb / div);
                int add = in[clampIndex(y + r + 1, n) * n + x];
                int sub = in[clampIndex(y - r, n) * n + x];
                sa += (add >>> 24) - (sub >>> 24);
                sr += ((add >> 16) & 0xFF) - ((sub >> 16) & 0xFF);
                sg += ((add >> 8) & 0xFF) - ((sub >> 8) & 0xFF);
                sb += (add & 0xFF) - (sub & 0xFF);
            }
        }
    }
}
