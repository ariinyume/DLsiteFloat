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

import android.content.Context;
import android.graphics.Typeface;

import java.io.File;
import java.io.FileOutputStream;

import io.github.ariinyume.dlsitesoundfloat.config.ConfigBus;
import io.github.ariinyume.dlsitesoundfloat.util.LogGate;

/**
 * 【code 1046】设置页进程侧：把「悬浮窗字幕**真正**在用的字体」落到本地并供预览使用。
 *
 * <p>预览窗跑在模块自己的进程里，宿主进程里被全局字体模块（MoriMod F4）换掉的字体
 * 这里画不出来。宿主通过 {@code ConfigBus} 把字体**描述**与**字节**递过来，
 * 本类负责接收拼装、落盘、解析成 {@link Typeface}，并在解析成功后回调一次刷新预览。
 *
 * <p>三种描述形态对应三种落地方式：
 * <ul>
 *   <li>{@code file:/system/fonts/x.ttf} —— 系统字体文件，本进程同路径直接可读；</li>
 *   <li>{@code family:sans-serif} —— 系统字体族，{@code Typeface.create(family, …)}；</li>
 *   <li>{@code user:fonts/x.ttf} —— 用户导入的字体，字节分片到齐后写进本模块 cacheDir。</li>
 * </ul>
 *
 * <p>任何一步失败都只是「预览回落到原行为」，**绝不抛** —— 这只是预览的锦上添花，
 * 不该因为它把设置页搞挂。
 */
public final class PreviewHostFont {

    private static final String TAG = "[DLsiteSoundFloat:PreviewFont]";

    /** 解析成功的字体；null = 还没拿到（或宿主没有全局字体替换）。 */
    private static volatile Typeface sTypeface;
    /** 宿主最近一次报的描述串（"" = 未知 / 没有）。 */
    private static volatile String sDesc = "";
    /** 分片拼装状态（只在主线程读写；分片广播本身也是主线程回调）。 */
    private static long sRid;
    private static byte[][] sParts;
    private static int sGot;
    private static String sFileName;

    private static volatile Listener sListener;

    /** 预览的刷新回调（拼装完成后由设置页设置；在主线程回调）。 */
    public interface Listener {
        void onHostFontReady();
    }

    private PreviewHostFont() {
    }

    public static void setListener(Listener l) {
        sListener = l;
    }

    /** 预览可用的宿主字体；null = 没有（预览回落原行为）。 */
    public static Typeface get() {
        return sTypeface;
    }

    /** 宿主是否已经明说「没有全局字体替换」（此时预览不必再等）。 */
    public static boolean knownAbsent() {
        return sDesc.isEmpty();
    }

    /** 每次进设置页 / 保存配置后清一次，并重新向宿主要一份。 */
    public static void refresh(Context ctx) {
        sTypeface = null;
        sDesc = "";
        sParts = null;
        sGot = 0;
        sRid = ConfigBus.sendHostFontReq(ctx);
    }

    /** 宿主的描述应答。返回 true = 需要继续等分片。 */
    public static boolean onInfo(Context ctx, String desc, String name) {
        sDesc = desc == null ? "" : desc;
        if (sDesc.isEmpty()) {
            notifyReady();
            return false;
        }
        try {
            if (sDesc.startsWith("file:")) {
                String path = sDesc.substring(5);
                File f = new File(path);
                sTypeface = (f.isFile() && f.canRead())
                        ? safeFromFile(f) : null;
                notifyReady();
                return false;
            }
            if (sDesc.startsWith("family:")) {
                String fam = sDesc.substring(7).trim();
                sTypeface = fam.isEmpty() ? null : safeCreate(fam);
                notifyReady();
                return false;
            }
            // user:* —— 等分片
            sFileName = (name == null || name.isEmpty()) ? "host_font.ttf" : name;
            if (!sFileName.endsWith(".ttf") && !sFileName.endsWith(".otf")) {
                sFileName = sFileName + ".ttf";
            }
            return true;
        } catch (Throwable t) {
            LogGate.debug(TAG + " onInfo failed: " + t);
            notifyReady();
            return false;
        }
    }

    /** 收一片。返回 true = 拼装完成（或本轮作废）。 */
    public static boolean onChunk(Context ctx, long rid, int seq, int n, byte[] data) {
        try {
            if (rid != sRid || n <= 0) {
                return true; // 上一轮的残片 / 否定应答 → 不再等
            }
            if (sParts == null || sParts.length != n) {
                sParts = new byte[n][];
                sGot = 0;
            }
            if (data != null && seq >= 0 && seq < n && sParts[seq] == null) {
                sParts[seq] = data;
                sGot++;
            }
            if (sGot < n) {
                return false;
            }
            int total = 0;
            for (byte[] p : sParts) {
                total += p == null ? 0 : p.length;
            }
            if (total <= 0) {
                return true;
            }
            byte[] all = new byte[total];
            int off = 0;
            for (byte[] p : sParts) {
                if (p != null) {
                    System.arraycopy(p, 0, all, off, p.length);
                    off += p.length;
                }
            }
            sTypeface = materialize(ctx, all);
            LogGate.debug(TAG + " host font materialized: bytes=" + total
                    + " ok=" + (sTypeface != null));
            notifyReady();
            return true;
        } catch (Throwable t) {
            LogGate.debug(TAG + " onChunk failed: " + t);
            notifyReady();
            return true;
        }
    }

    /** 把字节写进本模块 cacheDir 再解析（{@code Typeface.createFromFile} 只认路径）。 */
    private static Typeface materialize(Context ctx, byte[] all) {
        if (ctx == null || all == null || all.length == 0) {
            return null;
        }
        try {
            File dir = ctx.getCacheDir();
            if (dir == null) {
                return null;
            }
            File f = new File(dir, "preview_" + sFileName);
            try (FileOutputStream out = new FileOutputStream(f)) {
                out.write(all);
                out.flush();
            }
            return safeFromFile(f);
        } catch (Throwable t) {
            LogGate.debug(TAG + " materialize failed: " + t);
            return null;
        }
    }

    /** 残缺字体文件会让 {@code createFromFile} 返回「无字形」的对象，这里多验一道。 */
    private static Typeface safeFromFile(File f) {
        try {
            Typeface tf = Typeface.createFromFile(f);
            if (tf == null) {
                return null;
            }
            // 无字形字体 measureText 恒为 0 —— 用它把「假成功」筛掉
            android.graphics.Paint probe = new android.graphics.Paint();
            probe.setTextSize(40f);
            probe.setTypeface(tf);
            return probe.measureText("你A") > 0f ? tf : null;
        } catch (Throwable t) {
            return null;
        }
    }

    private static Typeface safeCreate(String family) {
        try {
            return Typeface.create(family, Typeface.NORMAL);
        } catch (Throwable t) {
            return null;
        }
    }

    private static void notifyReady() {
        Listener l = sListener;
        if (l != null) {
            try {
                l.onHostFontReady();
            } catch (Throwable ignored) {
            }
        }
    }
}
