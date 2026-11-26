/*
 * DLsiteSound Floating Subtitle - Xposed module for DLsite Sound
 * Copyright (C) 2026 ariinyume
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package io.github.ariinyume.dlsitesoundfloat.util;

/**
 * 全屏字幕封面取色 / 兜底色的零状态纯逻辑（可单测）。
 */
public final class CoverAmbientLogic {

    /** 无封面且无 MoriAccent 时的深色渐变顶色。 */
    public static final int FALLBACK_TOP = 0xFF1A1028;
    /** 无封面且无 MoriAccent 时的深色渐变底色。 */
    public static final int FALLBACK_BOTTOM = 0xFF0A0C14;

    private CoverAmbientLogic() {
    }

    /**
     * 从 ARGB 像素提 2 个主色（顶/底渐变用）：按亮度分桶取均值，暗色优先作底。
     *
     * @return length-2：{@code [top, bottom]}，失败返回 null
     */
    public static int[] dominantPair(int[] pixels) {
        if (pixels == null || pixels.length == 0) {
            return null;
        }
        long sumR = 0, sumG = 0, sumB = 0;
        long darkR = 0, darkG = 0, darkB = 0;
        int n = 0, darkN = 0;
        for (int v : pixels) {
            int a = (v >>> 24) & 0xFF;
            if (a < 16) {
                continue;
            }
            int r = (v >> 16) & 0xFF;
            int g = (v >> 8) & 0xFF;
            int b = v & 0xFF;
            sumR += r;
            sumG += g;
            sumB += b;
            n++;
            int luma = (77 * r + 150 * g + 29 * b) >> 8;
            if (luma < 140) {
                darkR += r;
                darkG += g;
                darkB += b;
                darkN++;
            }
        }
        if (n == 0) {
            return null;
        }
        int avg = 0xFF000000
                | ((int) (sumR / n) << 16)
                | ((int) (sumG / n) << 8)
                | (int) (sumB / n);
        int dark;
        if (darkN > 0) {
            dark = 0xFF000000
                    | ((int) (darkR / darkN) << 16)
                    | ((int) (darkG / darkN) << 8)
                    | (int) (darkB / darkN);
        } else {
            dark = darken(avg, 0.45f);
        }
        int top = darken(avg, 0.72f);
        int bottom = darken(dark, 0.55f);
        return new int[]{top, bottom};
    }

    /** MoriAccent 有值时用其压暗渐变；否则固定深色兜底。 */
    public static int[] fallbackPair(int accentArgb) {
        if (accentArgb != 0) {
            int rgb = accentArgb | 0xFF000000;
            return new int[]{darken(rgb, 0.55f), darken(rgb, 0.28f)};
        }
        return new int[]{FALLBACK_TOP, FALLBACK_BOTTOM};
    }

    public static int darken(int argb, float factor) {
        float f = factor < 0f ? 0f : (factor > 1f ? 1f : factor);
        int r = Math.round(((argb >> 16) & 0xFF) * f);
        int g = Math.round(((argb >> 8) & 0xFF) * f);
        int b = Math.round((argb & 0xFF) * f);
        return 0xFF000000 | (r << 16) | (g << 8) | b;
    }
}
