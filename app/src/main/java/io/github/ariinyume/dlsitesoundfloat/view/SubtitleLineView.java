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

import android.content.Context;
import android.graphics.Canvas;
import android.widget.TextView;

/**
 * 【code 1046】字幕行专用 TextView —— **在每一帧落笔前把配置的阴影重新按住**。
 *
 * ─────────────────────────────────────────────────────────────────────
 * 解决什么问题（code 1046）
 *
 * 症状：阴影颜色 / 强度 / 半径怎么调都不生效。排查结论是**配置链路完全正常**
 * —— {@code SubtitleStyle} 算对了、{@code styleLine} 也调了 {@code setShadowLayer}，
 * 丢的是**渲染那一刻**的阴影。
 *
 * <p>原因是宿主进程里另一位「全局美化」模块会沿视图树给**每一个 TextView**
 * 重设阴影，并在 draw 路径上执行，晚于本模块 {@code styleLine} 的写入
 * ⇒ 我们刚设好的阴影被盖掉。
 *
 * <p>反制：在 {@link #onDraw(Canvas)} 里**落笔前**再写一次。两点让它稳赢：
 * <ol>
 *   <li>本模块的 TextView 在 draw 走树的**内部**执行 onDraw，晚于那层外层
 *       draw 钩子里的写入 ⇒ 同一帧内我们最后落笔；</li>
 *   <li>那类模块通常带「值没变就不重写」的记忆，且记的是**它自己设的半径**；
 *       我们把 paint 改回配置值后，它按记忆比对觉得「没变」⇒ 不会再写第二次。
 *       于是只有第一帧可能被它先占，之后一直是我们的。</li>
 * </ol>
 *
 * <p>同时它也让「跟随系统字体」那条路更稳：{@link SystemFont#clearTypeface} 走
 * {@code Paint#set(Paint)} 整份复制，会把阴影一并清掉 —— 这里每帧兜底，
 * 清完也会在落笔前补回来。
 */
public class SubtitleLineView extends TextView {

    private float shadowRadius;
    private float shadowDy;
    private int shadowColor;

    public SubtitleLineView(Context context) {
        super(context);
    }

    /**
     * 记下配置的阴影并在落笔前按住。与 {@link TextView#setShadowLayer} 的区别只有一条：
     * 这里**每帧**都会重新写入 text paint，任何第三方在帧间改写都会被覆盖回来。
     */
    public void setSubtitleShadow(float radiusPx, float dyPx, int color) {
        this.shadowRadius = radiusPx;
        this.shadowDy = dyPx;
        this.shadowColor = color;
        applyShadow();
    }

    private void applyShadow() {
        try {
            // 半径 <= 0 时 setShadowLayer 自动不画阴影（「阴影强度 0%」由此保证）
            getPaint().setShadowLayer(shadowRadius, 0f, shadowDy, shadowColor);
        } catch (Throwable ignored) {
            // 渲染路径上的异常一律吞掉
        }
    }

    @Override
    protected void onDraw(Canvas canvas) {
        applyShadow();
        super.onDraw(canvas);
    }
}
