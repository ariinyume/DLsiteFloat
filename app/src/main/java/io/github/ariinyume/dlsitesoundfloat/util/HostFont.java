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
import java.io.FileInputStream;
import java.io.InputStream;

/**
 * 【code 1046】宿主侧「字幕**真正**在用的字体」解析器。
 *
 * ─────────────────────────────────────────────────────────────────────
 * 解决什么问题（code 1046）
 *
 * 预览窗在**模块自己的进程**里跑，悬浮窗在**宿主进程**里跑。宿主里若装了
 * 「全局改字体」类模块，悬浮窗那行字幕的字体是它 hook {@code Paint#setTypeface}
 * 换出来的；而预览进程没有这个钩子，只能画出 ROM 默认字体
 * ⇒ 用户看到的是「预览的字体 ≠ 悬浮窗真正的字体」，调参完全失去参照。
 *
 * 解法：宿主进程把它**真正解析出来的那份字体**读出来递给设置页。
 *
 * <p>「全局改字体」模块的取字优先级通常是：
 * <ol>
 *   <li>字体文件 —— 若是 {@code /system/fonts/*} 则本进程直接可读；否则是用户导入的
 *       字体，字节缓存在<b>宿主 filesDir</b> 的 {@code morimod_assets/} 里；</li>
 *   <li>系统字体族名 —— {@code Typeface.create(family, …)}。</li>
 * </ol>
 *
 * <p>字体文件在宿主私有目录里，**只有宿主 uid 读得到** —— 所以字节必须由
 * 宿主进程（也就是本模块被注入的那个进程）用广播分片递给设置页，
 * 见 {@code ConfigBus#answerHostFont}。本类只负责「找到并读出来」。
 *
 * <p>⚠️ 全部反射都套 {@code try/catch(Throwable)}：MoriMod 不在场 / 内部结构改名 /
 * 没开 F4，一律返回「没有」，设置页回落到原预览行为 —— **绝不硬顶**。
 */
public final class HostFont {

    private static final String TAG = "[DLsiteSoundFloat:HostFont]";

    /** MoriMod 的配置类（public 字段 {@code f4Enabled / f4FontFile / f4FontFamily}）。 */
    private static final String MORI_CONFIG_CLASS = "io.github.ariinyume.morimod.config.RemoteConfig";
    /** MoriMod 的素材缓存目录名（其 {@code AssetSync.DIR}）。 */
    private static final String MORI_ASSET_DIR = "morimod_assets";

    /** 单文件上限，与 MoriMod 侧 {@code AssetSync.MAX_BYTES} 对齐。 */
    public static final int MAX_BYTES = 32 * 1024 * 1024;
    /** 单片字节数（Binder 单事务上限 ~1MB，留足余量；32MB 字体 = 160 片）。 */
    public static final int CHUNK = 200 * 1024;

    private HostFont() {
    }

    /**
     * 悬浮窗字幕**真正**会用到的字体描述。
     *
     * @return {@code file:<绝对路径>} / {@code family:<族名>} / {@code user:<相对名>}；
     *         空串 = 没有全局字体替换（或拿不到）—— 预览维持原行为
     */
    public static String describe(Context ctx) {
        try {
            Object cfg = moriConfig(ctx);
            if (cfg == null) {
                return "";
            }
            Boolean enabled = boolOf(cfg, "f4Enabled");
            if (enabled == null || !enabled.booleanValue()) {
                return "";
            }
            String file = strOf(cfg, "f4FontFile");
            if (file != null && !file.isEmpty()) {
                if (file.startsWith("/") && new File(file).isFile()) {
                    // 系统字体文件（/system/fonts/*）：设置页同路径直接可读，零搬运。
                    return "file:" + file;
                }
                // 用户导入的字体：字节在 MoriMod 的宿主侧缓存里，要走分片。
                String rel = relativeName(file);
                return rel == null ? "" : "user:" + rel;
            }
            String fam = strOf(cfg, "f4FontFamily");
            if (fam != null && !fam.isEmpty()) {
                return "family:" + fam;
            }
            return "";
        } catch (Throwable t) {
            LogGate.debug(TAG + " describe failed: " + t);
            return "";
        }
    }

    /** {@link #describe(Context)} 给出的 {@code user:<rel>} → 建议落地文件名（含扩展名）。 */
    public static String baseNameOf(String desc) {
        if (desc == null) {
            return "";
        }
        String v = desc.startsWith("user:") ? desc.substring(5)
                : desc.startsWith("file:") ? desc.substring(5) : desc;
        int s = Math.max(v.lastIndexOf('/'), v.lastIndexOf('\\'));
        String name = s >= 0 ? v.substring(s + 1) : v;
        return name.isEmpty() ? "host_font.ttf" : name;
    }

    /** {@code user:<rel>} 的相对名部分；其余形态返回 null。 */
    public static String userRelOf(String desc) {
        if (desc == null || !desc.startsWith("user:")) {
            return null;
        }
        String rel = desc.substring(5).trim();
        if (rel.isEmpty() || rel.length() > 200 || rel.indexOf("..") >= 0) {
            return null;
        }
        return rel;
    }

    /**
     * MoriMod 的 {@code ModuleAssets.relativeName} 口径复刻：
     * 绝对路径 → {@code <目录名>/<文件名>}（只认 {@code fonts/}、{@code media/} 两层；
     * 其它一律只取文件名）。
     *
     * <p>⚠️ 这里**不**调 MoriMod 自己的方法 —— 那要在它 ClassLoader 上再起一路反射，
     * 而这个字符串口径极稳定（{@code AssetQueryReceiver.isSafe} 只认这两个目录）。
     */
    private static String relativeName(String path) {
        if (path == null) {
            return null;
        }
        String p = path.replace('\\', '/');
        while (p.startsWith("/")) {
            p = p.substring(1);
        }
        if (p.isEmpty()) {
            return null;
        }
        int slash = p.lastIndexOf('/');
        if (slash <= 0) {
            return p;
        }
        String parent = p.substring(0, slash);
        int ps = parent.lastIndexOf('/');
        String dir = ps >= 0 ? parent.substring(ps + 1) : parent;
        String name = p.substring(slash + 1);
        if (name.isEmpty()) {
            return null;
        }
        if ("fonts".equals(dir) || "media".equals(dir)) {
            return dir + "/" + name;
        }
        return name;
    }

    /**
     * 读 MoriMod 缓存在**宿主 filesDir** 里的用户字体字节。
     *
     * @return 字节；拿不到 / 超限 / 路径不安全一律 {@code null}
     */
    public static byte[] readUserFont(Context ctx, String rel) {
        if (ctx == null || rel == null) {
            return null;
        }
        try {
            Context app = ctx.getApplicationContext() != null ? ctx.getApplicationContext() : ctx;
            File dir = new File(app.getFilesDir(), MORI_ASSET_DIR);
            // MoriMod 的 AssetSync.cachedFile 把 '/' 整个换成 '_'（拍平成单层目录）
            File f = new File(dir, rel.replace('/', '_'));
            if (!f.isFile() || f.length() <= 0 || f.length() > MAX_BYTES) {
                LogGate.debug(TAG + " font not readable: " + f.getPath()
                        + " len=" + (f.isFile() ? f.length() : -1));
                return null;
            }
            try (InputStream in = new FileInputStream(f)) {
                java.io.ByteArrayOutputStream bos =
                        new java.io.ByteArrayOutputStream(256 * 1024);
                byte[] buf = new byte[32 * 1024];
                int r;
                long total = 0;
                while ((r = in.read(buf)) > 0) {
                    total += r;
                    if (total > MAX_BYTES) {
                        return null;
                    }
                    bos.write(buf, 0, r);
                }
                byte[] all = bos.toByteArray();
                LogGate.debug(TAG + " font read ok: " + rel + " bytes=" + all.length);
                return all.length == 0 ? null : all;
            }
        } catch (Throwable t) {
            LogGate.debug(TAG + " readUserFont failed: " + t);
            return null;
        }
    }

    // ── MoriMod 配置反射 ─────────────────────────────────────────────

    /**
     * MoriMod 当前的 {@code MoriConfig} 实例。
     *
     * <p>强调色那条路（{@link MoriAccent}）已经解决了「静态字段跟着 ClassLoader 走」
     * 的坑 —— 这里复用同一个 ClassLoader，否则拿到的是一套从未初始化的类副本，
     * 读出来永远是默认值（code 1045 的教训）。
     */
    private static Object moriConfig(Context ctx) throws Throwable {
        ClassLoader cl = MoriAccent.moriClassLoader(ctx);
        if (cl == null) {
            return null;
        }
        Class<?> c = Class.forName(MORI_CONFIG_CLASS, true, cl);
        return c.getMethod("get").invoke(null);
    }

    private static Boolean boolOf(Object cfg, String name) {
        try {
            Object v = cfg.getClass().getField(name).get(cfg);
            return v instanceof Boolean ? (Boolean) v : null;
        } catch (Throwable t) {
            return null;
        }
    }

    private static String strOf(Object cfg, String name) {
        try {
            Object v = cfg.getClass().getField(name).get(cfg);
            return v instanceof String ? (String) v : null;
        } catch (Throwable t) {
            return null;
        }
    }
}
