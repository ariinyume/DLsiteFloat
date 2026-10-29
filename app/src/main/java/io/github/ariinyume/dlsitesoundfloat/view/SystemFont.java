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
package io.github.ariinyume.dlsitesoundfloat.view;

import android.graphics.Paint;

/**
 * 【code 1044 / 2.4.3】「字幕字体跟随系统设定」的**渲染侧唯一落点**。
 *
 * ─────────────────────────────────────────────────────────────────────
 * 为什么不能直接 {@code setTypeface(null)}
 *
 * 「系统字体」在 Android 里的准确表达是「**不指定** typeface」—— paint 的 typeface 为
 * null 时，Skia 用平台默认字体渲染（即手机系统设置里那套字体，含中文回退链）。
 *
 * 可是宿主 App 若装了「全局改字体」类模块（本模块作者的 Mori Mod 即属此类），它 hook 的正是
 * {@code Paint#setTypeface}：任何一次 setTypeface —— **包括 setTypeface(null)** —— 都会被
 * 换成它的字体。于是「把 typeface 设为 null」这条路在宿主进程里根本走不通。
 *
 * 绕法：{@code Paint#set(Paint)} 是**整份复制**（native {@code nSetPaint}），不经过被 hook 的
 * setTypeface；复制源是一个全新 Paint（typeface = null）⇒ 目标 paint 的 typeface 归 null。
 * 代价是字号 / 颜色 / 阴影 / flags 也会被一并清回默认，所以调用点必须**先清后写**
 * （见 {@link FloatingSubtitleView#styleLine}）。
 *
 * 粗细：平台默认字体没有可选的粗体变体 ⇒ 用 {@code setFakeBoldText} 合成加粗
 * （与宿主字体模块处理单字重字体时用的是同一手段）。
 * ─────────────────────────────────────────────────────────────────────
 */
public final class SystemFont {

    /** 复制源模板：全新 Paint 的 typeface 为 null（= 平台默认字体）。只读，可跨线程共享。 */
    private static final Paint BLANK = new Paint();

    private SystemFont() {
    }

    /**
     * 把 paint 上的 typeface 清成「未指定」（= 平台默认字体）。
     *
     * <p>⚠️ 会顺带把字号 / 颜色 / 阴影 / flags 清回默认 ⇒ 调用方必须**先调它、再写其余属性**。
     *
     * @return true = 该 paint 现在不带 typeface（本来就是 null 时直接返回 true，不做任何事）
     */
    public static boolean clearTypeface(Paint paint) {
        if (paint == null) {
            return false;
        }
        if (paint.getTypeface() == null) {
            return true;
        }
        try {
            int flags = paint.getFlags();
            paint.set(BLANK);
            paint.setFlags(flags);
            return paint.getTypeface() == null;
        } catch (Throwable t) {
            // 万一某个 ROM 的 Paint#set 行为不同：保持原样，绝不把异常抛给渲染线程
            return false;
        }
    }

    /** 合成加粗（只在跟随系统时使用；值没变就不下发，省掉每帧一次 native 调用）。 */
    public static void applyBold(Paint paint, boolean bold) {
        if (paint == null) {
            return;
        }
        try {
            if (paint.isFakeBoldText() != bold) {
                paint.setFakeBoldText(bold);
            }
        } catch (Throwable ignored) {
            // 同上：渲染路径上的异常一律吞掉
        }
    }
}
