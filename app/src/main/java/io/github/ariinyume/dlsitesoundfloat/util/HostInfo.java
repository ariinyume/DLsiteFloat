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
import android.content.SharedPreferences;
import android.content.pm.PackageInfo;

/**
 * 【code 1022 / P0-1】宿主版本感知 —— 让「宿主升级了」这件事第一次变成**可见事实**。
 *
 * <h3>为什么必须有它</h3>
 * 本模块全部锚点都建立在「宿主 2.22.0 实测有效」之上（形状锚点 / 状态 Map 键名 /
 * 播放页视图结构）。宿主每发一版都会重跑 R8，短名整体换一遍
 * （实测 2.20.2 → 2.22.0：{@code AudioPlaylist ()Map} 由 {@code y()} 变 {@code s()}、
 * {@code readWithProgress} 的响应体类由 {@code Lvk/H;} 变 {@code Lwk/H;}），
 * 而**任何一处没命中时旧版只会静默不工作** —— 用户看到的是「插件坏了」，
 * 日志里却只有一行默认关闭的 debug。
 *
 * <p>所以先把「环境」钉进日志与状态：宿主包名 / versionName / versionCode /
 * 是否在已验证白名单内 / 本次启动前是否刚被更新过。
 *
 * <h3>口径</h3>
 * <ul>
 *   <li><b>只认宿主自己的 PackageInfo</b>：本类由宿主进程调用，{@code ctx.getPackageName()}
 *       就是宿主包名；SystemUI 进程调用时会被 {@link #init} 里的包名判定挡掉。</li>
 *   <li><b>「刚更新」用 versionCode 比对</b>（不是时间戳）：宿主覆盖安装时 versionCode 必变，
 *       而 lastUpdateTime 在某些 ROM 上会被备份还原改掉。</li>
 *   <li><b>Prefs 落在宿主自己的私有目录</b>（{@code getSharedPreferences}），
 *       所以这份记录只对「同一个宿主安装」有意义 —— 清宿主数据即重置，符合直觉。</li>
 *   <li><b>绝不抛异常</b>：读包信息失败时全部字段留空，只影响日志与提示。</li>
 * </ul>
 */
public final class HostInfo {

    private static final String TAG = "[DLsiteSoundFloat:Host]";

    /**
     * 本模块**已验证**的宿主版本（最新一版）。
     *
     * 【code 1045】2.22.0 → **2.22.1**：宿主把播放页的播放进度条整体上移，
     * 播放页胶囊的落位由此改为「进度条下方」（见
     * {@code CapsuleGeometry#capsuleBottomBelowSlider}），并按本值分版本走位。
     * 2.22.0 仍在 {@link #VERIFIED_SET} 里（走原来的「进度条上方」落位），两者都算已验证。
     */
    public static final String VERIFIED_VERSION = "2.22.1";

    /**
     * 已验证白名单（精确匹配）。宿主每发一版都要重新做一次离线体检才可入列 ——
     * 白名单的意义是「这一版的宿主结构我们真的看过」，不是「尽量显得兼容」。
     */
    private static final String[] VERIFIED_SET = {"2.22.0", VERIFIED_VERSION};

    private static final String PREFS = "dlsitefloat_host";
    private static final String K_LAST_CODE = "last_version_code";
    private static final String K_LAST_NAME = "last_version_name";

    private static volatile boolean sInited = false;
    private static volatile String sVersionName = "";
    private static volatile int sVersionCode = -1;
    /** 宿主版本号是否落在已验证白名单内（当前只有一条精确匹配）。 */
    private static volatile boolean sVerified = false;
    /** 本次启动前宿主刚被更新过（versionCode 与上次记录不同）。 */
    private static volatile boolean sJustUpdated = false;

    private HostInfo() {
    }

    /**
     * 入口 —— 由 {@code DlsiteSoundSubtitleModule} 在宿主进程就绪后调用一次。
     *
     * @param ctx       宿主 Context（SystemUI 进程调用时会被包名判定拒绝）
     * @param hostPkg   宿主包名（{@code Protocol.HOST_PKG}）
     */
    public static synchronized void init(Context ctx, String hostPkg) {
        if (sInited || ctx == null) {
            return;
        }
        try {
            if (!hostPkg.equals(ctx.getPackageName())) {
                return; // SystemUI / 其它被注入进程：不记录
            }
            PackageInfo pi = ctx.getPackageManager().getPackageInfo(hostPkg, 0);
            sVersionName = pi.versionName == null ? "" : pi.versionName;
            sVersionCode = pi.versionCode;

            SharedPreferences sp = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
            int lastCode = sp.getInt(K_LAST_CODE, -1);
            String lastName = sp.getString(K_LAST_NAME, "");
            // lastCode == -1 ⇒ 首次运行（或宿主清过数据），不算「刚更新」
            sJustUpdated = lastCode > 0 && lastCode != sVersionCode;
            sVerified = inVerifiedSet(sVersionName);
            if (lastCode != sVersionCode) {
                sp.edit().putInt(K_LAST_CODE, sVersionCode)
                        .putString(K_LAST_NAME, sVersionName).apply();
            }
            sInited = true;

            // 常开一行（每次启动一条，不刷屏）：这是排障的**第一手环境证据**。
            XposedCompat.log(TAG + " host=" + hostPkg
                    + " versionName=" + sVersionName
                    + " (code " + sVersionCode + ")"
                    + " verified=" + (sVerified ? "yes" : "NO(verified=" + VERIFIED_VERSION + ")")
                    + " justUpdated=" + sJustUpdated
                    + (lastName.length() > 0 && sJustUpdated ? " from=" + lastName : ""));
        } catch (Throwable e) {
            XposedCompat.log(TAG + " init failed: " + e);
        }
    }

    public static String versionName() {
        return sVersionName;
    }

    public static int versionCode() {
        return sVersionCode;
    }

    /** 是否等于本模块已验证的宿主版本。 */
    public static boolean verified() {
        return sVerified;
    }

    /** 本次启动前宿主是否刚被更新（用于给一次性的提示）。 */
    public static boolean justUpdated() {
        return sJustUpdated;
    }

    /**
     * 【code 1045】宿主版本是否 **≥** 指定的三段版本号（如 {@code 2, 22, 1}）。
     *
     * ── 为什么必须是「≥」而不是「等于」──
     * 播放页的**布局排布**会随宿主发版变化（2.22.1 把播放进度条整体上移就是一例，
     * 胶囊落位因此要从「进度条上方」改到「进度条下方」）。凡是依赖具体布局的口径，
     * 宿主再往后的 2.22.2 / 2.23.0 **大概率沿用新排布**，用精确等于会在那之后
     * 静默退回旧口径 —— 正是「宿主一升级就坏、且坏得没声音」的典型形态。
     *
     * ⚠️ 读不到版本号（SystemUI 进程 / 包信息失败 / 版本串不规范）时**一律返回 false**
     *    ⇒ 走旧落位。与 {@link #verified()} 那套「宁可保守」的取舍保持一致。
     *
     * @return true = 宿主版本不低于指定版本
     */
    public static boolean hostAtLeast(int a, int b, int c) {
        return versionAtLeast(sVersionName, a, b, c);
    }

    /**
     * 纯函数版：把「某个版本串是否 ≥ 指定三段版本号」单独暴露出来（可单测）。
     *
     * <p>宿主版本串来自 {@code PackageInfo.versionName}，在 JVM 单测里造不出来
     * （{@link #init} 要 Android 的 {@code Context}），所以判定本身必须是独立的纯函数。
     */
    public static boolean versionAtLeast(String name, int a, int b, int c) {
        int[] v = parseVersion(name);
        if (v == null) {
            return false;
        }
        int[] want = {a, b, c};
        for (int i = 0; i < 3; i++) {
            if (v[i] != want[i]) {
                return v[i] > want[i];
            }
        }
        return true; // 三段全等
    }

    /** 版本号是否在已验证白名单内。 */
    private static boolean inVerifiedSet(String name) {
        if (name == null || name.length() == 0) {
            return false;
        }
        for (String v : VERIFIED_SET) {
            if (v.equals(name)) {
                return true;
            }
        }
        return false;
    }

    /**
     * 把 {@code 2.22.1} 解析成三段整数；缺段补 0，含非数字段返回 null。
     *
     * ⚠️ 宿主偶尔会带后缀（{@code 2.22.1-rc1}）—— 那种串按 null 处理（走保守口径），
     *    不要为了「认出来」去做模糊匹配：认错的代价比认不出大得多。
     */
    private static int[] parseVersion(String name) {
        if (name == null || name.length() == 0) {
            return null;
        }
        String[] parts = name.split("\\.");
        int[] out = new int[3];
        for (int i = 0; i < 3; i++) {
            if (i >= parts.length) {
                out[i] = 0;
                continue;
            }
            try {
                out[i] = Integer.parseInt(parts[i]);
            } catch (NumberFormatException e) {
                return null;
            }
        }
        return out;
    }

    /** 日志/诊断用的一行摘要。 */
    public static String summary() {
        return "host " + (sVersionName.length() > 0 ? sVersionName : "?")
                + " (code " + sVersionCode + ")"
                + (sVerified ? " verified" : " unverified");
    }

    // ==================================================================
    // 【code 1023 / P0-1 修复】设置页读取通道
    // ==================================================================

    /**
     * 设置页专用：在**当前进程**直接读宿主包信息。
     *
     * <h3>为什么不能复用上面的静态字段（1022 真机的 bug）</h3>
     * 上面那套 {@code sVersionName / sVersionCode / sVerified} 只在<b>宿主进程</b>里被
     * {@link #init} 写过一次；设置页跑在<b>模块自己的进程</b>（{@code io.github...dlsitesoundfloat}），
     * 那是另一份静态字段，永远是初始值 ⇒ 界面显示 {@code 宿主版本 ? · 未验证}。
     * 而同期宿主日志里明明写着 {@code versionName=2.22.0 (code 612) verified=yes}——
     * 一次「跨进程读静态变量」的低级错误。
     *
     * <p>真机日志还纠了一个假设：宿主 {@code versionCode} 是 <b>612</b>，不是 {@code 2220}。
     * ⇒ 任何「用 versionName 推 versionCode」的写法都是错的，只能分开读。
     *
     * <h3>包可见性</h3>
     * Android 11+ 读别的包需要清单里 {@code <queries>} 声明（见 AndroidManifest），
     * 否则抛 {@code NameNotFoundException} —— 1022 那一版就是栽在这里：代码写了、
     * 清单没写，于是静默落到 {@code "?"}。
     *
     * @param ctx     任意 Context（设置页的即可）
     * @param hostPkg 宿主包名
     * @return 读不到时返回 {@link Info#UNKNOWN}
     */
    public static Info readInCurrentProcess(Context ctx, String hostPkg) {
        if (ctx == null || hostPkg == null) {
            return Info.UNKNOWN;
        }
        try {
            PackageInfo pi = ctx.getPackageManager().getPackageInfo(hostPkg, 0);
            String name = pi.versionName == null ? "" : pi.versionName;
            return new Info(name, pi.versionCode, inVerifiedSet(name));
        } catch (Throwable e) {
            // 宿主未安装 / 包可见性未声明 / ROM 限制：一律降级成「未知」，绝不抛给 UI
            XposedCompat.log(TAG + " readInCurrentProcess failed (" + hostPkg + "): " + e);
            return Info.UNKNOWN;
        }
    }

    /** 一次「读到的宿主版本」快照（不可变）。 */
    public static final class Info {
        public static final Info UNKNOWN = new Info("", -1, false);

        public final String versionName;
        public final int versionCode;
        public final boolean verified;

        Info(String versionName, int versionCode, boolean verified) {
            this.versionName = versionName;
            this.versionCode = versionCode;
            this.verified = verified;
        }

        /** 读到了版本号没有（决定 UI 显示数字还是问号）。 */
        public boolean known() {
            return versionName != null && versionName.length() > 0;
        }
    }
}
