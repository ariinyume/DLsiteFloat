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
package io.github.ariinyume.dlsitesoundfloat.hook;

import android.view.View;

import io.github.ariinyume.dlsitesoundfloat.data.SubtitleRepository;

/**
 * 【code 1054 / B3】已改名 {@link PlayerPageScanner}。
 *
 * <p>本类仅作**源码兼容壳**：历史文档 / 部分 {@code tools/archive/verify_*_src.py}
 * 仍按旧文件名探测；生产调用请一律改用 {@link PlayerPageScanner}。
 *
 * @deprecated 使用 {@link PlayerPageScanner}
 */
@Deprecated
public final class SubtitleViewHook {

    /** @deprecated 使用 {@link PlayerPageScanner#PAGE_UNKNOWN} */
    @Deprecated
    public static final int PAGE_UNKNOWN = PlayerPageScanner.PAGE_UNKNOWN;
    /** @deprecated 使用 {@link PlayerPageScanner#PAGE_PLAYER} */
    @Deprecated
    public static final int PAGE_PLAYER = PlayerPageScanner.PAGE_PLAYER;
    /** @deprecated 使用 {@link PlayerPageScanner#PAGE_OTHER} */
    @Deprecated
    public static final int PAGE_OTHER = PlayerPageScanner.PAGE_OTHER;

    private SubtitleViewHook() {
    }

    /** @deprecated 使用 {@link PlayerPageScanner#hook} */
    @Deprecated
    public static void hook(ClassLoader cl, SubtitleRepository repo) {
        PlayerPageScanner.hook(cl, repo);
    }

    /** @deprecated 使用 {@link PlayerPageScanner#scan} */
    @Deprecated
    public static PlayerPageScanner.ScanResult scan(View root, SubtitleRepository repo) {
        return PlayerPageScanner.scan(root, repo);
    }

    /** @deprecated 使用 {@link PlayerPageScanner#verdictName} */
    @Deprecated
    public static String verdictName(int verdict) {
        return PlayerPageScanner.verdictName(verdict);
    }

    /** @deprecated 使用 {@link PlayerPageScanner#isEffectivelyVisible} */
    @Deprecated
    public static boolean isEffectivelyVisible(View v) {
        return PlayerPageScanner.isEffectivelyVisible(v);
    }

    /** @deprecated 使用 {@link PlayerPageScanner#visibleAreaRatio} */
    @Deprecated
    public static float visibleAreaRatio(View v, int screenW, int screenH) {
        return PlayerPageScanner.visibleAreaRatio(v, screenW, screenH);
    }
}
