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

import io.github.ariinyume.dlsitesoundfloat.config.Protocol;

/**
 * 【code 1057 / 架构优化 B2】状态栏字幕广播的**意图分类 + LINE 载荷解析**。
 *
 * <p>从 {@link StatusBarSubtitleHook#registerReceiver} 抽出：不碰 Context /
 * registerReceiver / showLine 副作用。action 字符串以 {@link Protocol} 为真源。
 */
final class StatusBarIntentRouter {

    enum Kind {
        IGNORE,
        SCOPE_PING,
        ENABLED,
        LINE
    }

    /** LINE 广播解析结果（字段已拍平，便于单测）。 */
    static final class LinePayload {
        final boolean enabled;
        final long durationMs;
        final boolean playing;
        final String line;

        LinePayload(boolean enabled, long durationMs, boolean playing, String line) {
            this.enabled = enabled;
            this.durationMs = durationMs;
            this.playing = playing;
            this.line = line == null ? "" : line;
        }
    }

    private StatusBarIntentRouter() {
    }

    static Kind classify(String action) {
        if (action == null || action.isEmpty()) {
            return Kind.IGNORE;
        }
        if (Protocol.ACTION_SCOPE_PING.equals(action)) {
            return Kind.SCOPE_PING;
        }
        if (Protocol.ACTION_ENABLED.equals(action)) {
            return Kind.ENABLED;
        }
        if (Protocol.ACTION_LINE.equals(action)) {
            return Kind.LINE;
        }
        return Kind.IGNORE;
    }

    /**
     * 解析 LINE 载荷。{@code enabledPresent=false} 时沿用 {@code prevEnabled}
     * （与 Intent 缺省 extra 行为一致）。
     */
    static LinePayload parseLine(boolean enabledPresent, boolean enabledExtra,
            boolean prevEnabled, long durationMs, boolean playing, String line) {
        boolean enabled = enabledPresent ? enabledExtra : prevEnabled;
        return new LinePayload(enabled, durationMs, playing, line);
    }

    /** ENABLED 广播：新开关为 false 时调用方应 hide。 */
    static boolean shouldHideOnEnabled(boolean enabled) {
        return !enabled;
    }
}
