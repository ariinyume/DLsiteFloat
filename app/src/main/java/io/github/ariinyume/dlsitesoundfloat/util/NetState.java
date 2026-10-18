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
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;

/**
 * 【code 1022 / P0-4】联网状态判定 —— 只服务于「无字幕」的**文案细分**。
 *
 * <h3>为什么需要它</h3>
 * 宿主 2.22.0 的下载是「只下音频、不下字幕」（实测：`ziptree.json` 之后该作品零
 * `optimized/*.json`）。于是「下载了作品 + 飞行模式播放」这个**官方鼓励的场景**
 * 在插件侧只会显示笼统的「无字幕」，与「本音轨本来就没字幕」无法区分。
 *
 * <p>本类只回答一个问题：<b>现在这台设备有没有可用的互联网</b>。
 * 有网 ⇒ 用原文案；无网 ⇒ 用「离线 · 无缓存」并给出下一步（联网播放一次即可缓存）。
 *
 * <h3>口径与降级</h3>
 * <ul>
 *   <li>优先 {@link NetworkCapabilities}：必须同时具备 {@code NET_CAPABILITY_INTERNET}
 *       与 {@code NET_CAPABILITY_VALIDATED}（后者才代表「真的能出网」，
 *       连着 WiFi 但没登录门户时不算在线）。</li>
 *   <li>拿不到 capabilities（极老系统 / 权限缺失）⇒ 退 {@code getActiveNetworkInfo()}；
 *       再拿不到就**按「在线」处理** —— 宁可保持旧文案，也不要误报「离线」误导用户。</li>
 *   <li>结果缓存 {@link #TTL_MS}：胶囊每秒会重算多次状态，不能每次都查系统服务。</li>
 *   <li>⚠️ 不申请任何新权限：宿主自带 {@code ACCESS_NETWORK_STATE}（RN 网络栈需要）。
 *       万一没有，{@link SecurityException} 会被吞掉并视为在线。</li>
 * </ul>
 */
public final class NetState {

    /** 结果缓存时长：3 秒足够跟手，又不至于把系统服务打爆。 */
    private static final long TTL_MS = 3000L;

    private static volatile long sLastCheckMs = 0L;
    private static volatile boolean sOffline = false;

    private NetState() {
    }

    /** 当前是否「没有可用互联网」。读不到状态时一律返回 false（视为在线）。 */
    public static boolean isOffline() {
        long now = android.os.SystemClock.uptimeMillis();
        if (now - sLastCheckMs < TTL_MS) {
            return sOffline;
        }
        boolean offline;
        try {
            Context ctx = AppEnv.app();
            ConnectivityManager cm = ctx == null ? null
                    : (ConnectivityManager) ctx.getSystemService(Context.CONNECTIVITY_SERVICE);
            if (cm == null) {
                offline = false;
            } else {
                Network n = cm.getActiveNetwork();
                if (n == null) {
                    offline = true;              // 没有任何活动网络
                } else {
                    NetworkCapabilities cap = cm.getNetworkCapabilities(n);
                    if (cap != null) {
                        offline = !(cap.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                                && cap.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED));
                    } else {
                        // 退化路径：老系统拿不到 capabilities
                        android.net.NetworkInfo ni = cm.getActiveNetworkInfo();
                        offline = ni == null || !ni.isConnected();
                    }
                }
            }
        } catch (Throwable e) {
            offline = false;                     // 权限/服务异常 ⇒ 不误报
        }
        sOffline = offline;
        sLastCheckMs = now;
        return offline;
    }

    /** 便于诊断日志引用（不做 IO，不改变缓存）。 */
    public static String label() {
        return isOffline() ? "offline" : "online";
    }
}
