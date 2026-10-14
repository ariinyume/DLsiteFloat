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

package io.github.ariinyume.dlsitesoundfloat.util;

import android.content.Context;

/**
 * 【code 1018 / 架构审查 2.3】宿主 Application 上下文的**唯一注入点**。
 *
 * <h3>为什么需要它</h3>
 * {@code util/NetLogFile} 原先在拿不到 {@code Context} 时回读
 * {@code SubtitleRepository.getInstance().getAppContext()} —— 那是又一条
 * {@code util → data} 的反向依赖。{@code util} 按约定是叶子包，不该认识数据层。
 * 本类把「宿主上下文」这件事收到 util 自己手里：由 Application#attach 的钩子注入一次，
 * 谁要用谁读。
 *
 * <h3>口径</h3>
 * <ul>
 *   <li>只保存<b>宿主 Application 上下文</b>（不是 Activity，也不是 system 上下文）。</li>
 *   <li>{@code install(null)} 被忽略 —— 不允许用 null 把已装好的上下文擦掉。</li>
 *   <li>未注入时 {@link #app()} 返回 {@code null}，调用方必须自行兜底
 *       （{@code NetLogFile} 的做法是「拿不到就不写日志，等下一次」）。</li>
 * </ul>
 *
 * <p>类不实例化。字段 {@code volatile}：写入发生在 Application#attach 钩子里，
 * 读取可能发生在任意写日志的线程。
 */
public final class AppEnv {

    private AppEnv() {}

    private static volatile Context sAppContext;

    /** 注入宿主 Application 上下文（由 {@code DlsiteSoundSubtitleModule} 在 attach 钩子里调用）。 */
    public static void install(Context ctx) {
        if (ctx != null) {
            sAppContext = ctx;
        }
    }

    /** 宿主 Application 上下文；尚未注入时返回 {@code null}。 */
    public static Context app() {
        return sAppContext;
    }
}
