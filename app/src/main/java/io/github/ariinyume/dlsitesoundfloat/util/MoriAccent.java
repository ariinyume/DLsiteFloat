/*
 * DLsiteSound Floating Subtitle - Xposed module for DLsite Sound
 * Copyright (C) 2026 ariinyume
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * This program is free software: you can redistribute it and/or modify it under
 * the terms of the GNU General Public License as published by the Free Software
 * Foundation, either version 3 of the License, or (at your option) any later version.
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
import android.content.pm.PackageManager;
import android.os.SystemClock;

import java.lang.ref.WeakReference;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.Map;

/**
 * 【code 1045】MoriMod 强调色读取 —— 检测到用户装了 MoriMod 就用它采样出来的强调色。
 *
 * ─────────────────────────────────────────────────────────────────────
 * 为什么要读别人的颜色
 *
 * MoriMod 是同宿主（{@code jp.co.eisys.dlsitesound}）的另一枚模块，它按用户设置的
 * 背景壁纸采样出一个强调色，再把宿主界面上那一族紫色整体染成强调色
 * （它的取样入口在壁纸生效那一刻，结果只活在**宿主进程内存**里，不落盘）。
 * 本模块注入的是同一个宿主进程，播放页那两枚胶囊因此可以用同一个色，
 * 界面才会跟 MoriMod 的配色整体一致。
 *
 * ─────────────────────────────────────────────────────────────────────
 * 🔴🔴 为什么必须绕一道 ClassLoader（本项目最容易踩空的一步）
 *
 * 强调色是 MoriMod 类里的**静态字段**，而静态字段是**跟着 ClassLoader 走**的：
 * LSPosed 给每枚模块发一个独立 ClassLoader，我们用 {@code Class.forName} 在本模块
 * 的 loader 上找到的，是一套**全新、从未初始化**的类副本 —— 静态字段全是默认值，
 * 读出来永远是「功能未开」。这不是反射写错了，是找错了类。
 *
 * 所以必须拿到 **MoriMod 自己那个已加载的 ClassLoader**。本类的取法：
 *   · MoriMod 在宿主进程里注册过**动态广播接收器**（素材同步与配置应答两条通道），
 *     这些匿名内部类就挂在它的模块 ClassLoader 上；
 *   · 动态接收器统一登记在 {@code LoadedApk.mReceivers} 里 ⇒ 反射枚举它，
 *     按类名前缀认出 MoriMod 的接收器 ⇒ 取它的 {@code getClassLoader()}；
 *   · 这一步**与加载顺序无关**（MoriMod 先于/后于本模块加载都能找到），
 *     比「钩 ClassLoader.loadClass 守株待兔」稳得多。
 *
 * ⚠️ 三道闸，缺一不可（任何一道不过就回落默认配色，**绝不硬顶**）：
 *   ① 包是否安装（{@code PackageManager}，需清单 {@code <queries>} 声明）；
 *   ② 能否拿到它的 ClassLoader（模块未激活 / 作用域没勾 / 结构变了 ⇒ 拿不到）；
 *   ③ 它自己的 {@code on()} 是否为真（功能关着 / 壁纸还没采样 ⇒ 颜色无意义）。
 * 这三条是「如实报告」，取不到就返回 0，由调用方回落到原有配色 ——
 * **没有颜色可以接受，因为没颜色而闪一下不可以**（1.21.10 的老教训）。
 *
 * ─────────────────────────────────────────────────────────────────────
 * 口径
 *   · 缓存 2 秒：强调色会随壁纸变化而重采，但没必要每次重绘都去枚举一遍接收器；
 *   · 取不到时**沿用上一次成功的颜色**，不回落默认（避免短暂拿不到就闪一下）；
 *   · 白字可读性：强调色太亮时按亮度压暗到阈值以下再返回。
 */
public final class MoriAccent {

    private static final String TAG = "[DLsiteSoundFloat:Mori]";

    /** MoriMod 的包名（它的 {@code applicationId}，见其 build.gradle）。 */
    public static final String MORI_PKG = "io.github.ariinyume.morimod";

    /** MoriMod 侧强调色类的全名（public final class，{@code on()} / {@code remap(int)} 均 public static）。 */
    private static final String ACCENT_CLASS = MORI_PKG + ".hook.AccentColor";
    private static final String METHOD_ON = "on";
    private static final String METHOD_REMAP = "remap";

    /**
     * MoriMod 侧「宿主基准紫」常量的拷贝（{@code AccentColor.HOST_PURPLE}）。
     *
     * 拿强调色的正解是把它自己染的那支紫丢进 {@code remap}：强调色在它内部是以
     * 色相/彩度持有的，只有 {@code remap} 出来的才是**它真正渲染到界面上的**那个 ARGB。
     * 硬编码这一支紫是必要的 —— 它是它那侧的常量，本模块读不到。
     */
    private static final int HOST_PURPLE = 0xFFC387E8;

    /** 强调色的缓存有效期（ms）。壁纸换了会重采，2s 足够跟上又不至于每次重绘都枚举。 */
    private static final long REFRESH_MS = 2000L;
    /** 关态相对开态的压暗系数（两态同色系，靠亮度区分开/关）。 */
    public static final float OFF_DIM = 0.565f;
    /**
     * 底色亮度上限（加权亮度 / 255）：超过它就压暗，保证胶囊上的白字仍然可读。
     *
     * 【code 1047】0.42 → **0.75**。
     *
     * 0.42 是「底色**完全不透明**」年代标定的（那时底色亮度 = 合成亮度）。
     * 现在底色只盖 {@link #BODY_ALPHA} = 40%（见下），合成亮度 ≈ {@code 0.4 × 原色亮度}
     * —— 还拿 0.42 卡原色，等于把按钮压得比宿主播放控件暗一大截。
     * 上限改卡**合成后** ≤ 0.30 ⇒ 原色上限 = {@code 0.30 / 0.4 = 0.75}。
     * 白字对比度反而是**变好**的：合成 0.298 ⇒ 相对亮度 ≈ 0.073 ⇒ 对比 ≈ 8.5:1。
     */
    private static final float MAX_LUMA = 0.75f;

    // ── 【code 1047】胶囊底色**统一口径**（液态玻璃 / GradientDrawable 两条路径共用）──
    //
    // 需求原话：「调整字幕开关按钮的**明亮度和通透度**，想要和宿主播放控件看起来一致」——
    // **颜色仍然跟 MoriMod 强调色走**，这里只动「透多少」和「压多暗」两件事。
    //
    // 目标口径（按「与宿主播放控件的观感一致」标定）：
    //   宿主播放控件用的就是**强调色原色 + 约 40% 不透明度** —— 与我们要用的颜色同源，
    //   差别只在「压不压暗」和「透多少」。所以口径收敛成一句话：
    //   **强调色原色 + alpha 40%**，不再额外压暗、不再额外提亮。
    // 之前是「强调色压暗到 0.42 亮度 + alpha 91%~100%」⇒ 又暗又实，这就是差距的全部来源。
    //
    // ⚠️ 这个 alpha 是**两条路径唯一的事实来源** —— {@code LiquidGlassDrawable} 的四档
    //    底色 alpha 与这里保持一致，{@code ActivityButtonHook#capsuleColor} 直接调
    //    {@link #capsuleBody}。谁都不许再私设一份，否则两种主题又会各长各样。
    //
    // ⚠️ 开/关**同一 alpha**，靠 RGB 亮度（{@link #OFF_DIM}）区分 —— 与宿主「同一个材质、
    //    靠内容区分」的做法一致；如果改成「关态更透」，两态就不是一个材质的观感了。
    /** 胶囊底色 alpha：40%（与宿主播放控件同一档，原 0xE8 / 0xFF）。 */
    public static final int BODY_ALPHA = 0x66;

    /** MoriMod 的模块 ClassLoader（弱引用：它自己由动态接收器强引用着，不会真被回收）。 */
    private static volatile WeakReference<ClassLoader> sLoaderRef;
    /** 最近一次成功取到的强调色；0 = 一次都没取到。 */
    private static volatile int sAccent = 0;
    private static volatile long sStampMs = 0L;
    /** 安装判定缓存：只在「已装」时钉死，未装时每次都重查（装了之后能立刻生效）。 */
    private static volatile boolean sInstalled = false;
    /** 常开日志只打一次（采纳 / 拿不到 各一条），避免每次重绘刷屏。 */
    private static volatile boolean sLoggedAdopt = false;
    private static volatile boolean sLoggedMiss = false;

    private MoriAccent() {
    }

    /**
     * 取强调色；取不到返回 {@code fallback}。
     *
     * @param ctx 宿主进程里的 Context（用于查包可见性 + 定位 LoadedApk）；可为 null
     */
    public static int accentOr(Context ctx, int fallback) {
        int c = accent(ctx);
        return c != 0 ? c : fallback;
    }

    /** 关态底色：同一强调色压暗一档（开态直接用 {@link #accentOr} 的原色）。 */
    public static int offState(int accent) {
        return dim(accent, OFF_DIM);
    }

    /**
     * 【code 1047】字幕开关胶囊的**最终底色** —— 液态玻璃 / GradientDrawable 两条路径
     * 都从这里拿，保证两种主题下的按钮观感不会各长各样。
     *
     * <p>口径（见类头「统一口径」那段）：**RGB 直接用强调色原色**（关态按 {@link #OFF_DIM}
     * 压暗一档做区分），**alpha 一律 {@link #BODY_ALPHA}** —— 与宿主播放控件同材质同色，
     * 不再额外压暗、也不再额外提亮。
     *
     * @param ctx         宿主进程里的 Context；可为 null（取不到强调色就走设计稿原色）
     * @param on          true = 开态
     * @param fallbackOn  取不到强调色时的开态底色（设计稿 #584179）
     * @param fallbackOff 取不到强调色时的关态底色（设计稿 #212042）
     */
    public static int capsuleBody(Context ctx, boolean on, int fallbackOn, int fallbackOff) {
        int accent = accentOr(ctx, 0);
        int rgb = on ? (accent != 0 ? accent : fallbackOn)
                : (accent != 0 ? offState(accent) : fallbackOff);
        return withAlpha(rgb, BODY_ALPHA);
    }

    /** 只改 alpha，RGB 不动。 */
    private static int withAlpha(int argb, int a) {
        return (a << 24) | (argb & 0x00FFFFFF);
    }

    /**
     * 取强调色；取不到返回 0（**沿用上一次成功值**已经包含在这里 —— 一次都没取到才返回 0）。
     */
    public static int accent(Context ctx) {
        long now = SystemClock.uptimeMillis();
        if (sAccent != 0 && now - sStampMs < REFRESH_MS) {
            return sAccent;
        }
        int v = 0;
        try {
            v = probe(ctx);
        } catch (Throwable t) {
            LogGate.debug(TAG + " probe failed: " + t);
        }
        sStampMs = now;
        if (v != 0) {
            sAccent = v;
        }
        return v != 0 ? v : sAccent;
    }

    // ==================================================================
    // 三道闸
    // ==================================================================

    /**
     * MoriMod 在**宿主进程**里已加载的模块 ClassLoader（{@code null} = 它此刻不在本进程）。
     *
     * <p>【code 1046】开放给 {@code HostFont} 复用 —— 读它的 F4 字体配置与取强调色
     * 是同一个「必须用它自己的 loader」的道理。
     */
    public static ClassLoader moriClassLoader(Context ctx) {
        return moriLoader(ctx);
    }

    private static int probe(Context ctx) throws Throwable {
        // ── 【code 1046 真机根修】不再拿 PackageManager 当「装没装」的闸 ──
        //
        // code 1045 在本模块清单里加了 <queries><package morimod/>，真机上取色仍静默失败
        // （LSPosed 全程没有一条 [DLsiteSoundFloat:Mori] 日志）。原因：包可见性判定看的是
        // **调用方**的清单，而这里的 ctx 是**宿主 Activity**的 Context —— 调用方是宿主 App，
        // 它的清单我们改不了 ⇒ getPackageInfo(morimod) 在宿主进程里**永远**
        // NameNotFoundException。这与 code 1023 的结论完全对称：那次是「宿主进程读得到、
        // 模块进程读不到」，这次反过来 —— 声明只对**声明它的那个 uid**生效。
        //
        // 所以这条闸换成更强的证据：**能拿到它的 ClassLoader** 本身就证明了
        // 「装了 + 激活了 + 勾了作用域」—— 接收器是 MoriMod 自己在本进程注册的，
        // 不在本进程注册就不可能被枚举到。PackageManager 的读数只留作日志诊断，
        // 不再拦截。
        boolean pmSees = installed(ctx);
        ClassLoader cl = moriLoader(ctx);
        if (cl == null) {
            miss("no morimod receiver/classloader in host process (pmSees=" + pmSees + ")");
            return 0;
        }
        Class<?> c = Class.forName(ACCENT_CLASS, true, cl);
        Method on = c.getMethod(METHOD_ON);
        Object onv = on.invoke(null);
        if (!(onv instanceof Boolean) || !((Boolean) onv)) {
            if (!sLoggedMiss) {
                sLoggedMiss = true;
                XposedCompat.log(TAG + " morimod accent off (feature disabled or wallpaper "
                        + "not sampled yet) -> keep default capsule color");
            }
            return 0; // 它的强调色功能关着 / 壁纸还没采样 —— 没有颜色可给
        }
        Method remap = c.getMethod(METHOD_REMAP, int.class);
        Object v = remap.invoke(null, HOST_PURPLE);
        if (!(v instanceof Integer)) {
            return 0;
        }
        int argb = contrastSafe((Integer) v);
        if (!sLoggedAdopt) {
            sLoggedAdopt = true;
            XposedCompat.log(TAG + " morimod accent adopted: #"
                    + Integer.toHexString(argb).toUpperCase());
        }
        return argb;
    }

    /** ① 包是否安装。 */
    private static boolean installed(Context ctx) {
        if (sInstalled) {
            return true;
        }
        if (ctx == null) {
            return false;
        }
        try {
            ctx.getPackageManager().getPackageInfo(MORI_PKG, 0);
            sInstalled = true;
            return true;
        } catch (PackageManager.NameNotFoundException e) {
            return false; // 没装 / 包可见性没声明 —— 都是「没有」
        } catch (Throwable t) {
            LogGate.debug(TAG + " package probe failed: " + t);
            return false;
        }
    }

    /**
     * ② 找 MoriMod 的模块 ClassLoader —— 从动态注册的广播接收器反推。
     *
     * @return 找到的 ClassLoader；null = 它此刻不在宿主进程里（未激活 / 作用域没勾 / 结构变了）
     */
    private static ClassLoader moriLoader(Context ctx) {
        WeakReference<ClassLoader> ref = sLoaderRef;
        ClassLoader cached = ref == null ? null : ref.get();
        if (cached != null) {
            return cached;
        }
        ClassLoader found = null;
        try {
            Object loadedApk = loadedApk(ctx);
            Field f = loadedApk == null ? null : field(loadedApk.getClass(), "mReceivers");
            if (f != null) {
                Object outer = f.get(loadedApk);
                if (outer instanceof Map) {
                    for (Object inner : ((Map<?, ?>) outer).values()) {
                        if (!(inner instanceof Map)) {
                            continue;
                        }
                        for (Object dispatcher : ((Map<?, ?>) inner).values()) {
                            Object recv = fieldOf(dispatcher, "mReceiver");
                            if (recv == null) {
                                continue;
                            }
                            Class<?> rc = recv.getClass();
                            if (rc.getName().startsWith(MORI_PKG + ".")) {
                                found = rc.getClassLoader();
                                break;
                            }
                        }
                        if (found != null) {
                            break;
                        }
                    }
                }
            }
        } catch (Throwable t) {
            LogGate.debug(TAG + " receiver scan failed: " + t);
        }
        if (found != null) {
            // 自检：这个 loader 真能解析出强调色类（拿到别的东西时不算数）
            try {
                Class.forName(ACCENT_CLASS, false, found);
            } catch (Throwable t) {
                found = null;
            }
        }
        if (found != null) {
            sLoaderRef = new WeakReference<>(found);
        }
        return found;
    }

    /**
     * 从任意 Context 拿到它所属的 {@code LoadedApk}（动态接收器登记表在它身上）。
     *
     * {@code ContextWrapper} 链上是 {@code mBase} → {@code ContextImpl}，
     * {@code ContextImpl} 上才是 {@code mPackageInfo}；两者不在同一条继承链上，
     * 所以必须先解一层 {@code mBase}。
     */
    private static Object loadedApk(Context ctx) {
        if (ctx == null) {
            return null;
        }
        Object base = ctx;
        for (int i = 0; i < 4; i++) {
            Object next = fieldOf(base, "mBase");
            if (next == null) {
                break;
            }
            base = next;
        }
        return base == null ? null : fieldOf(base, "mPackageInfo");
    }

    private static Object fieldOf(Object o, String name) {
        if (o == null) {
            return null;
        }
        try {
            Field f = field(o.getClass(), name);
            return f == null ? null : f.get(o);
        } catch (Throwable t) {
            return null;
        }
    }

    /** 沿继承链找字段（含私有、含隐藏字段）。 */
    private static Field field(Class<?> c, String name) {
        for (Class<?> k = c; k != null; k = k.getSuperclass()) {
            try {
                Field f = k.getDeclaredField(name);
                f.setAccessible(true);
                return f;
            } catch (Throwable ignored) {
                // 本层没有，继续往父类找
            }
        }
        return null;
    }

    private static void miss(String why) {
        if (sLoggedMiss) {
            return;
        }
        sLoggedMiss = true;
        XposedCompat.log(TAG + " morimod installed but accent unavailable (" + why
                + ") -> keep default capsule color");
    }

    // ==================================================================
    // 颜色口径
    // ==================================================================

    /** 太亮就压暗，保证胶囊上的白字仍然可读（开态与关态共用这道闸）。 */
    static int contrastSafe(int argb) {
        float luma = luma(argb);
        float k = 1f;
        while (luma * k > MAX_LUMA && k > 0.25f) {
            k -= 0.1f;
        }
        return k >= 1f ? argb : dim(argb, k);
    }

    static int dim(int argb, float k) {
        int a = argb >>> 24;
        int r = (int) (((argb >> 16) & 0xff) * k);
        int g = (int) (((argb >> 8) & 0xff) * k);
        int b = (int) ((argb & 0xff) * k);
        return (a << 24) | (clamp255(r) << 16) | (clamp255(g) << 8) | clamp255(b);
    }

    /** 近似相对亮度（不做 sRGB 线性化 —— 这里只需要一个稳定的同序量）。 */
    static float luma(int argb) {
        int r = (argb >> 16) & 0xff;
        int g = (argb >> 8) & 0xff;
        int b = argb & 0xff;
        return (0.2126f * r + 0.7152f * g + 0.0722f * b) / 255f;
    }

    private static int clamp255(int v) {
        return v < 0 ? 0 : (v > 255 ? 255 : v);
    }
}
