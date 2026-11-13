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

/**
 * 【code 1066 / 2.4.5 / A-1】胶囊按钮**显隐与开态**纯判 —— 零 Android / 零 View。
 *
 * <p>从 {@code ActivityButtonHook} 抽出：状态栏钮 on/visible、悬浮窗钮 on，以及
 * {@code applyButtonText} 的视觉签名拼装。调用方负责读桥接开关与仓库状态并传入。
 *
 * <p>历史坑（必须同口径喂两条路径）：1.21.12 / 1.21.16 文字与底色各算一套
 * → 「字变了色没变」/「底色比事实早」。{@code applyButtonText} 与
 * {@code updateButtonDrawable} 必须都走本类。
 */
final class CapsuleButtonPolicy {

    private CapsuleButtonPolicy() {
    }

    /**
     * 状态栏钮是否呈「开」底色。无字幕时不算开（签名稳定；钮本身也不显示）。
     */
    static boolean statusBarButtonOn(boolean noSub, boolean appEnabled) {
        return !noSub && appEnabled;
    }

    /**
     * 状态栏钮是否显示：有字幕 + L1 功能闸 + SystemUI 作用域已授权。
     * 与 {@link #statusBarButtonOn} 是两件事（颜色 vs 在不在）。
     */
    static boolean statusBarButtonVisible(boolean noSub, boolean featureEnabled,
            boolean systemUiAuthorized) {
        return !noSub && featureEnabled && systemUiAuthorized;
    }

    /**
     * 悬浮窗钮是否呈「开」态。无字幕时文字是「无字幕」、底色按关。
     */
    static boolean floatingButtonOn(boolean noSub, boolean floatingOpen) {
        return !noSub && floatingOpen;
    }

    /**
     * 两钮全部视觉输入的合成签名。漏任何一项都会留下「文字变了底色没变」。
     */
    static String visualSig(String floatText, boolean floatOn, String statusText,
            boolean statusOn, boolean statusVisible, float alpha, boolean liquidGlass,
            int accent) {
        return floatText + '\u0000' + floatOn + '\u0000'
                + statusText + '\u0000' + statusOn + '\u0000' + statusVisible
                + '\u0000' + alpha + '\u0000' + liquidGlass
                + '\u0000' + accent;
    }
}
