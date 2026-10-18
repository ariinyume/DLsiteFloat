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

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Arrays;
import java.util.Comparator;
import java.util.Date;
import java.util.Locale;

/**
 * 【code 1022 / P0-4 取证】把宿主的 `ziptree.json` 正文落盘，用于反推「字幕文件名」规则。
 *
 * <h3>要回答的问题</h3>
 * 宿主的下载**只下音频、不下字幕**（2.22.0 实测：`ziptree.json` 之后该作品零
 * `optimized/*.json`）。而 CloudFront 的签名 Policy 是**作品目录级通配**
 * （`.../RJ01609334/*`）⇒ 只要知道每轨字幕的文件名 `<md5>.json` 是怎么算出来的，
 * 就能在下载时顺手把整作品字幕抓下来。
 *
 * <p>本类只做一件事：把 `ziptree.json`（作品文件树）原始正文存到
 * `Android/data/<宿主包名>/files/subtitle_cache/_diag/`，供离线比对：
 * <pre>
 *   文件树里的音频相对路径  --(md5?)-->  optimized/&lt;32位hex&gt;.json
 * </pre>
 *
 * <h3>纪律（诊断文件不能变成垃圾）</h3>
 * <ul>
 *   <li><b>只在调试日志开启时工作</b>（设置页「其他 → 调试日志」）—— 普通用户零成本。</li>
 *   <li><b>最多保留 {@link #MAX_FILES} 份</b>，超了删最旧的；单份上限 {@link #MAX_BYTES}。</li>
 *   <li><b>绝不抛异常</b>：任何 IO 失败只落一行日志，不影响抓字幕主链路。</li>
 *   <li><b>不做二次加工</b>：存的就是宿主下发的原文，避免「我以为的格式」污染取证。</li>
 * </ul>
 */
public final class DiagDump {

    private static final String TAG = "[DLsiteSoundFloat:Diag]";

    /** 目录名（与字幕缓存同根，便于一次性打包）。 */
    private static final String DIR = "subtitle_cache/_diag";
    /** 最多保留几份（一个作品一份够用）。 */
    private static final int MAX_FILES = 5;
    /** 单份上限：ziptree 可能较大，给 1MB（字幕本身只有几 KB）。 */
    public static final int MAX_BYTES = 1024 * 1024;

    private static final SimpleDateFormat SDF =
            new SimpleDateFormat("MMdd-HHmmss", Locale.US);

    private DiagDump() {
    }

    /** 这个 URL 是不是要抓的取证目标（目前只有作品文件树）。 */
    public static boolean isTarget(String urlLower) {
        return urlLower != null && urlLower.contains("ziptree");
    }

    /** 调试开关关闭时，只打一行提示（每进程一次），告知用户怎么拿到取证文件。 */
    private static volatile boolean sSkipLogged = false;

    public static void logSkippedOnce() {
        if (sSkipLogged) {
            return;
        }
        sSkipLogged = true;
        XposedCompat.log(TAG + " ziptree 取证样本未保存（调试日志开关关闭）；"
                + "需要取证时请在设置页打开「调试日志」后重新下载一次作品");
    }

    /**
     * 落盘一份正文。
     *
     * @param tag  文件名前缀（如 {@code ziptree}）
     * @param url  原始 URL（只取路径最后两段做文件名，避免过长）
     * @param text 响应正文（调用方保证已经过体积闸门）
     */
    public static void save(String tag, String url, String text) {
        if (text == null || text.length() == 0) {
            return;
        }
        try {
            Context ctx = AppEnv.app();
            File base = ctx == null ? null : ctx.getExternalFilesDir(null);
            if (base == null) {
                base = ctx == null ? null : ctx.getFilesDir();
            }
            if (base == null) {
                return;
            }
            File dir = new File(base, DIR);
            if (!dir.exists() && !dir.mkdirs()) {
                XposedCompat.log(TAG + " mkdirs failed: " + dir);
                return;
            }
            byte[] bytes = text.getBytes(StandardCharsets.UTF_8);
            if (bytes.length > MAX_BYTES) {
                bytes = Arrays.copyOf(bytes, MAX_BYTES);   // 截断也要留样本
            }
            String work = workOf(url);
            String name = tag + "_" + SDF.format(new Date()) + (work.isEmpty() ? "" : "_" + work)
                    + ".json";
            File out = new File(dir, name);
            try (FileOutputStream fos = new FileOutputStream(out)) {
                fos.write(bytes);
            }
            prune(dir);
            XposedCompat.log(TAG + " saved " + out.getName() + " (" + bytes.length + " B)"
                    + " url=" + url);
            NetLogFile.log("DIAG saved " + out.getName() + " bytes=" + bytes.length
                    + " url=" + url);
        } catch (Throwable e) {
            XposedCompat.log(TAG + " save failed: " + e);
        }
    }

    /** 从 URL 里取作品号（`RJxxxxxxxx`），失败返回空串。 */
    private static String workOf(String url) {
        if (url == null) {
            return "";
        }
        java.util.regex.Matcher m =
                java.util.regex.Pattern.compile("(RJ\\d{6,10})").matcher(url.toUpperCase(Locale.US));
        return m.find() ? m.group(1) : "";
    }

    /** 只保留最新的 MAX_FILES 份。 */
    private static void prune(File dir) {
        File[] files = dir.listFiles();
        if (files == null || files.length <= MAX_FILES) {
            return;
        }
        Arrays.sort(files, new Comparator<File>() {
            @Override
            public int compare(File a, File b) {
                return Long.compare(a.lastModified(), b.lastModified());
            }
        });
        for (int i = 0; i < files.length - MAX_FILES; i++) {
            //noinspection ResultOfMethodCallIgnored
            files[i].delete();
        }
    }
}
