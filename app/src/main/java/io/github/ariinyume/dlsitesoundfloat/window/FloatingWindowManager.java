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
package io.github.ariinyume.dlsitesoundfloat.window;

import android.content.ComponentCallbacks;
import android.content.Context;
import android.content.Intent;
import android.content.res.Configuration;
import android.graphics.PixelFormat;
import android.graphics.Rect;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.provider.Settings;
import android.util.DisplayMetrics;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.view.WindowMetrics;

import io.github.ariinyume.dlsitesoundfloat.data.SubtitleRepository;
import io.github.ariinyume.dlsitesoundfloat.view.FloatingSubtitleView;
import io.github.ariinyume.dlsitesoundfloat.view.GripIndicatorView;

import io.github.ariinyume.dlsitesoundfloat.util.XposedCompat;
import io.github.ariinyume.dlsitesoundfloat.util.LogGate;
import io.github.ariinyume.dlsitesoundfloat.util.Utils;

/**
 * 进程内悬浮窗管理器（单例）。
 *
 * 关键设计：本管理器与目标 App（DLsiteSound）运行在【同一个进程】中，
 * 因此与各个 Hook 共享同一个 SubtitleRepository 实例，字幕数据天然互通。
 *
 * 悬浮窗的权限归属（重要）：窗口是在 DLsiteSound 的进程里、用它的 Context 挂的，
 * 所以类型 2038 (TYPE_APPLICATION_OVERLAY) 首先需要【DLsiteSound 自己】的
 * SYSTEM_ALERT_WINDOW（显示在其他应用上层 / 悬浮窗）权限 —— 这是必需项。
 * ⚠️ 实测（ColorOS）**模块 App 侧也建议一并授予**该权限：系统会在模块侧再拦一道，
 * 两者都开最稳妥。详见 docs/build.md 的「运行环境」。
 *
 * 交互（v5）：
 *   - 面板任意处按住拖动 → 移动窗口
 *   - 右下角手柄区按住拖动 → 缩放窗口（宽高）
 *
 * v12：系统级「背后实时模糊」默认关闭（{@link #ENABLE_SYSTEM_BLUR_BEHIND}）。
 *   原因见该常量注释 —— ColorOS 上 FLAG_BLUR_BEHIND 会糊掉整个屏幕，且 App 侧无法限制模糊区域。
 */
public class FloatingWindowManager {
    private static final String TAG = "[DLsiteSoundFloat:Window]";
    private static final long MIN_RETRY_INTERVAL_MS = 800L;
    private static final int MIN_W_DP = 140;
    private static final int MIN_H_DP = 72;
    private static final int DEFAULT_W_RATIO = 85; // 屏宽百分比
    private static final int DEFAULT_H_DP = 200;
    /**
     * v20：竖屏窗口纵向**最长** = 屏幕高度的该百分比（50 = 一半）。
     * Ari 要求"上下拉长长度不得超过屏幕的一半"，缩放 clamp 的上限即取自本值。
     * 【code 1074 / 2.4.6】横屏不限制高度（见 {@link #maxHRatioFor}），可拉到纵向满屏。
     */
    private static final int MAX_H_SCREEN_RATIO = 50;
    /** 【code 1074】横屏高度上限 = 可用高度 100%（纵向满屏）。 */
    private static final int MAX_H_LANDSCAPE_RATIO = 100;
    /**
     * 【code 1072–1073】横屏右缘 keep 下限（dp）= 角标 INSET+LEG。
     * 【code 1073】横屏右缘优先取本机<strong>状态栏高度</strong>（机型相关），
     * 再与本下限取 max，避免状态栏偏矮时角标又贴进圆角。
     * 竖屏不加（仍可贴齐右边）。
     */
    private static final float LANDSCAPE_RIGHT_KEEP_FLOOR_DP =
            GripIndicatorView.INSET_DP + GripIndicatorView.LEG_DP;
    /** 面板背后实时模糊半径（dp）。仅 Android 12+ 且系统开启跨窗模糊时生效，否则自动降级。 */
    private static final int BLUR_RADIUS_DP = 26;
    /**
     * 是否启用系统级「背后实时模糊」（FLAG_BLUR_BEHIND + setBlurBehindRadius）。
     *
     * ⚠️ 默认 false —— 实测在 OPPO/ColorOS 上，TYPE_APPLICATION_OVERLAY 窗口一旦置上
     * FLAG_BLUR_BEHIND，模糊会铺满【整个屏幕】而不是只模糊面板身后那一小块区域：
     * 只开一个 85%×200dp 的小窗，结果整个桌面/页面全糊（Ari 机器实测已复现）。
     *
     * 原因：模糊区域由系统合成器（SurfaceFlinger 的 blur region）决定，对 overlay 窗口
     * 就是整屏；App 侧没有任何公开 API 能把它裁到窗口范围内。于是只能整体关闭，
     * 面板的质感改由 GlassPanelDrawable 的**半透明渐变底 + 提高底色不透明度**实现
     * （v13 起已移除顶部高光/外辉光/轮廓边缘光等装饰层）。
     *
     * 若要重新试错（例如换到 AOSP 机型）：把这里改成 true 即可，其余逻辑无需改动。
     *
     * ⚠️ 【2.2.12】**本常量永远是 false，不是待办项** —— 真·背后模糊已经用另一条路做成了：
     *    不走窗口标志，而是由 {@code util/BackdropBlur} 直接把模糊设到**我们自己的图层**上
     *    （真机已验收：面板背后有真实模糊、可调、可全局、零权限、零额外功耗）。
     *    窗口标志这条路之所以保留为"永久关闭"，是因为真机取证确认它在本机型上**只有整屏效果**，
     *    且 App 侧无法收窄（详见 {@code ColorOS17_液态玻璃_悬浮窗可行性分析.md} §7）。
     */
    private static final boolean ENABLE_SYSTEM_BLUR_BEHIND = false;

    private static FloatingWindowManager sInstance;

    // ---- v29：窗口几何记忆（同一进程内生效）----
    /**
     * 最近一次的窗口尺寸 / 位置。0 或 {@link Integer#MIN_VALUE} 表示「还没设定过」。
     *
     * 背景：换轨时会「自动关窗（判无字幕后）→ 字幕到达再开窗」，窗口被整个重建；
     * 旧实现每次重建都套用默认尺寸（85% 屏宽 × 200dp）与默认位置，
     * 于是 Ari 拖好的大小/位置会被重置回默认 —— 这就是「短时间换轨后悬浮窗变回默认尺寸」。
     * 这里把几何记在静态字段里，重建时优先恢复（并按当前屏幕重新夹取，防旋转/分辨率变化后跑出屏外）。
     */
    private static int sLastW = 0;
    private static int sLastH = 0;
    private static int sLastX = Integer.MIN_VALUE;
    private static int sLastY = Integer.MIN_VALUE;

    private Context appContext;
    /** 注册 ComponentCallbacks 用的 Application Context（避免 Activity 销毁后丢监听）。 */
    private Context callbackContext;
    private WindowManager wm;
    private FloatingSubtitleView view;
    private WindowManager.LayoutParams params;
    private boolean showing = false;
    private boolean permissionPromptPending = false; // 守卫：失败只自动提示一次权限页
    private boolean configCallbacksRegistered = false;
    /**
     * 上一次「挂载失败」的时刻。
     * v17：只在失败时记录 —— 原先无论成败都记录，导致「隐藏后立刻再显示」（例如切音轨时
     * 自动关窗又被字幕到达重新打开）会被这条节流挡掉，窗口迟迟不出现。
     */
    private long lastFailMs = 0L;
    private final Object lock = new Object();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    /**
     * 【code 1067】旋转 / 分屏改屏后，把已显示窗口的宽高位置重新夹进新屏幕。
     * show() 里才夹一次不够 —— overlay 在旋转时不会重建。
     */
    private final ComponentCallbacks configCallbacks = new ComponentCallbacks() {
        @Override
        public void onConfigurationChanged(Configuration newConfig) {
            // DisplayMetrics 偶发滞后一帧，立刻夹一次 + 再 post 一次兜底。
            fitGeometryToScreen("config");
            mainHandler.post(() -> fitGeometryToScreen("config-post"));
        }

        @Override
        public void onLowMemory() {
        }
    };

    public static synchronized FloatingWindowManager getInstance() {
        if (sInstance == null) {
            sInstance = new FloatingWindowManager();
        }
        return sInstance;
    }

    /**
     * 由 SubtitleRepository 的观察者驱动：根据 repo 的开关状态与实际显示状态对齐窗口。
     */
    public void sync(Context ctx) {
        if (ctx != null) {
            this.appContext = ctx;
        }
        SubtitleRepository repo = SubtitleRepository.getInstance();
        // 全屏字幕打开时暂隐悬浮窗（会话态仍保留 floatingWindowOpen，退出全屏后自动恢复）。
        boolean wantOpen = repo.isFloatingWindowOpen() && !repo.isFullscreenOpen();
        synchronized (lock) {
            if (wantOpen && !showing) {
                show();
            } else if (!wantOpen && showing) {
                hide();
            }
            if (showing && view != null) {
                view.updateFromRepository();
            }
        }
    }

    private void show() {
        Context ctx = appContext;
        if (ctx == null) {
            return;
        }
        // 节流：只在「上一次真的失败」时才限制重试频率（成功不节流，
        // 否则 hide→show 的快速切换会被挡掉）。
        long now = SystemClock.uptimeMillis();
        if (now - lastFailMs < MIN_RETRY_INTERVAL_MS) {
            return;
        }

        // 不用 Settings.canDrawOverlays() 做前置门控（OPPO 上会误报 false），
        // 直接尝试 addView，用真实结果判断权限是否生效。
        try {
            wm = (WindowManager) ctx.getSystemService(Context.WINDOW_SERVICE);
            if (wm == null) {
                return;
            }
            view = new FloatingSubtitleView(ctx);
            view.setOnTouchListener(new GestureListener());

            ScreenSafe safe = screenSafe(ctx);
            int screenW = safe.screenW;
            int screenH = safe.screenH;
            // 【2.2.13 / 987】窗口 = 玻璃 + 四周阴影环：默认值与下限都按"玻璃口径"补上环宽，
            //   保证玻璃部分的默认大小 / 最小值与旧版一致。
            //   ⚠️ 987 起环宽为 0（那一圈已整体删除，见 FloatingSubtitleView
            //   #GLASS_SHADOW_INSET_DP）⇒ frame2 恒为 0，本行等价于旧算式。
            final int frame2 = 2 * view.getFrameInsetPx();
            int minW = dp(ctx, MIN_W_DP) + frame2;
            int minH = dp(ctx, MIN_H_DP) + frame2;

            // v29：优先恢复上次的尺寸 / 位置；从未设定过才用默认值。
            // 恢复值一律按当前屏幕重新夹取（旋转、分辨率变化、字体缩放后仍保证窗口可见）。
            int defW = Math.max(minW, screenW * DEFAULT_W_RATIO / 100 + frame2);
            int defH = dp(ctx, DEFAULT_H_DP) + frame2;
            int rawW = sLastW > 0 ? sLastW : defW;
            int rawH = sLastH > 0 ? sLastH : defH;
            int rawX = sLastX != Integer.MIN_VALUE ? sLastX : (int) (screenW * 0.075);
            int rawY = sLastY != Integer.MIN_VALUE ? sLastY : (int) (screenH * 0.32);
            WindowGeometry.Rect geo = clampGeo(
                    rawX, rawY, rawW, rawH, safe, minW, minH);
            boolean restored = sLastW > 0 || sLastX != Integer.MIN_VALUE;

            params = new WindowManager.LayoutParams(
                    geo.width, geo.height,
                    Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                            ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                            : WindowManager.LayoutParams.TYPE_PHONE,
                    WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                            | WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON,
                    PixelFormat.TRANSLUCENT);
            params.gravity = Gravity.TOP | Gravity.START;
            params.x = geo.x;
            params.y = geo.y;

            boolean blurOn = applyBlurBehind(ctx);
            wm.addView(view, params);
            showing = true;
            permissionPromptPending = false; // 成功挂载即重置提示守卫
            registerConfigCallbacks(ctx);
            view.setBlurBehindActive(blurOn); // 玻璃底按模糊是否生效自适应通透度
            view.updateFromRepository();
            XposedCompat.log(TAG + " floating window shown (pkg=" + ctx.getPackageName()
                    + ", " + params.width + "x" + params.height
                    + " at " + params.x + "," + params.y
                    + (restored ? " [geometry restored]" : " [default geometry]") + ")");
        } catch (Throwable e) {
            lastFailMs = SystemClock.uptimeMillis(); // 只有失败才参与节流
            boolean canDraw = Build.VERSION.SDK_INT < Build.VERSION_CODES.M
                    || Settings.canDrawOverlays(ctx);
            XposedCompat.log(TAG + " addView FAILED: " + e.getMessage()
                    + " | canDrawOverlays=" + canDraw
                    + " | windowOwnerPkg=" + ctx.getPackageName()
                    + " (需给该 App 打开「显示在其他应用上层/悬浮窗」)");
            showing = false;
            view = null;
            // 真正没权限：回退开关，让按钮显示「悬浮关」，并只自动提示一次权限页。
            SubtitleRepository.getInstance().setFloatingWindowOpen(false);
            if (!permissionPromptPending) {
                permissionPromptPending = true;
                promptOverlayPermission(ctx);
            }
        }
    }

    /**
     * 为悬浮窗开启「背后实时模糊」——即让面板像磨砂玻璃一样把身后画面真正模糊掉。
     *
     * 依赖 Android 12+ 的跨窗模糊能力：给 LayoutParams 设置模糊半径并置 FLAG_BLUR_BEHIND。
     * 该能力受系统/厂商开关控制（部分机器默认关闭跨窗模糊），因此：
     *   - 先探测 {@link WindowManager#isCrossWindowBlurEnabled()}；
     *   - 全程 try/catch，任何异常都不影响窗口正常显示。
     * 返回是否真正开启，供视图层据此调整玻璃底的通透度（无模糊时更不透明以保证可读性）。
     *
     * 必须在 addView 之前调用（模糊是窗口创建时的属性）。
     */
    private boolean applyBlurBehind(Context ctx) {
        if (!ENABLE_SYSTEM_BLUR_BEHIND) {
            // ColorOS 上会糊掉整个屏幕，已全局关闭（详见常量注释）。
            XposedCompat.log(TAG + " blurBehind: DISABLED by config (would blur whole screen on ColorOS)");
            return false;
        }
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S || params == null) {
            XposedCompat.log(TAG + " blurBehind skipped: SDK_INT=" + Build.VERSION.SDK_INT);
            return false;
        }
        try {
            boolean enabled = true;
            if (wm != null) {
                try {
                    enabled = wm.isCrossWindowBlurEnabled();
                } catch (Throwable ignored) {
                }
            }
            if (enabled) {
                params.setBlurBehindRadius(dp(ctx, BLUR_RADIUS_DP));
                params.flags |= WindowManager.LayoutParams.FLAG_BLUR_BEHIND;
            }
            XposedCompat.log(TAG + " blurBehind: crossWindowBlurEnabled=" + enabled
                    + ", radiusDp=" + BLUR_RADIUS_DP);
            return enabled;
        } catch (Throwable e) {
            XposedCompat.log(TAG + " blurBehind unavailable: " + e.getMessage());
            return false;
        }
    }

    private void promptOverlayPermission(Context ctx) {
        if (ctx == null) {
            return;
        }
        try {
            Intent intent = new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:" + ctx.getPackageName()));
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            ctx.startActivity(intent);
            XposedCompat.log(TAG + " prompted overlay permission for " + ctx.getPackageName());
        } catch (Throwable e) {
            XposedCompat.log(TAG + " promptOverlayPermission failed: " + e.getMessage());
        }
    }

    private void hide() {
        saveGeometry(); // v29：关窗前固化几何，下次开窗直接恢复
        unregisterConfigCallbacks();
        try {
            if (wm != null && view != null) {
                wm.removeView(view);
            }
        } catch (Throwable ignored) {
        }
        view = null;
        showing = false;
        XposedCompat.log(TAG + " floating window hidden");
    }

    private void registerConfigCallbacks(Context ctx) {
        if (configCallbacksRegistered || ctx == null) {
            return;
        }
        try {
            Context app = ctx.getApplicationContext();
            callbackContext = app != null ? app : ctx;
            callbackContext.registerComponentCallbacks(configCallbacks);
            configCallbacksRegistered = true;
        } catch (Throwable t) {
            XposedCompat.log(TAG + " registerComponentCallbacks failed: " + t.getMessage());
        }
    }

    private void unregisterConfigCallbacks() {
        if (!configCallbacksRegistered || callbackContext == null) {
            configCallbacksRegistered = false;
            return;
        }
        try {
            callbackContext.unregisterComponentCallbacks(configCallbacks);
        } catch (Throwable ignored) {
        }
        configCallbacksRegistered = false;
        callbackContext = null;
    }

    /**
     * 【code 1067】按当前屏幕重新夹取已显示窗口的宽高与位置，并写回 WindowManager。
     * 横屏宽窗 → 竖屏、竖屏高窗 → 横屏时，把越界部分收回屏内。
     */
    private void fitGeometryToScreen(String reason) {
        synchronized (lock) {
            if (!showing || params == null || view == null || wm == null) {
                return;
            }
            Context ctx = appContext != null ? appContext : view.getContext();
            if (ctx == null) {
                return;
            }
            ScreenSafe safe = screenSafe(ctx);
            if (safe.screenW <= 0 || safe.screenH <= 0) {
                return;
            }
            final int frame2 = 2 * view.getFrameInsetPx();
            int minW = dp(ctx, MIN_W_DP) + frame2;
            int minH = dp(ctx, MIN_H_DP) + frame2;
            // 动态下限优先（字幕行完整显示），但不允许把夹取推回屏外。
            int dynMinW = view.getMinWidthPx();
            int dynMinH = view.getMinHeightPx();
            if (dynMinW > 0) {
                minW = Math.max(minW, dynMinW + frame2);
            }
            if (dynMinH > 0) {
                minH = Math.max(minH, dynMinH + frame2);
            }
            WindowGeometry.Rect geo = clampGeo(
                    params.x, params.y, params.width, params.height, safe, minW, minH);
            if (geo.equalsValues(params.x, params.y, params.width, params.height)) {
                return;
            }
            int oldW = params.width;
            int oldH = params.height;
            params.x = geo.x;
            params.y = geo.y;
            params.width = geo.width;
            params.height = geo.height;
            try {
                wm.updateViewLayout(view, params);
                if (oldW != params.width || oldH != params.height) {
                    view.recenterCurrent();
                }
                saveGeometry();
                XposedCompat.log(TAG + " fitGeometry (" + reason + "): "
                        + oldW + "x" + oldH + " -> " + params.width + "x" + params.height
                        + " at " + params.x + "," + params.y
                        + " screen=" + safe.screenW + "x" + safe.screenH
                        + " insets=[" + safe.insetL + "," + safe.insetT
                        + "," + safe.insetR + "," + safe.insetB + "]"
                        + " statusH=" + safe.statusBarH);
            } catch (Throwable t) {
                XposedCompat.log(TAG + " fitGeometry updateViewLayout failed: " + t.getMessage());
            }
        }
    }

    /** 全屏尺寸 + 安全边距（角标/手势/刘海）。 */
    private static final class ScreenSafe {
        final int screenW;
        final int screenH;
        final int insetL;
        final int insetT;
        final int insetR;
        final int insetB;
        /** 本机状态栏高度；横屏用来限制最大高度，不占用顶缘 inset。 */
        final int statusBarH;

        ScreenSafe(int screenW, int screenH, int insetL, int insetT, int insetR, int insetB,
                int statusBarH) {
            this.screenW = screenW;
            this.screenH = screenH;
            this.insetL = insetL;
            this.insetT = insetT;
            this.insetR = insetR;
            this.insetB = insetB;
            this.statusBarH = statusBarH;
        }
    }

    /**
     * 【code 1074】竖屏高度上限仍为 {@link #MAX_H_SCREEN_RATIO}（半屏）；
     * 横屏改为 {@link #MAX_H_LANDSCAPE_RATIO}（相对可用高度 100%）。
     * 【code 1075/1076】横屏最大高度 = 屏高 − 状态栏（见 {@link #applyLandscapeMaxHeight}），
     * 但顶缘 inset=0，仍可移动到顶部。
     */
    private static int maxHRatioFor(ScreenSafe safe) {
        return (safe.screenW > safe.screenH) ? MAX_H_LANDSCAPE_RATIO : MAX_H_SCREEN_RATIO;
    }

    /** 开窗 / 旋转 / 缩放共用：先按屏夹取，再施加横屏高度上限。 */
    private static WindowGeometry.Rect clampGeo(int x, int y, int w, int h,
            ScreenSafe safe, int minW, int minH) {
        WindowGeometry.Rect geo = WindowGeometry.clampToScreen(
                x, y, w, h, safe.screenW, safe.screenH, minW, minH, maxHRatioFor(safe),
                safe.insetL, safe.insetT, safe.insetR, safe.insetB);
        return applyLandscapeMaxHeight(geo, safe, minH);
    }

    /**
     * 【code 1076】横屏只限高度、不挡顶缘：maxH = 屏高 − 状态栏；
     * y 仍可为 0（真机 175439：1075 的 insetT=141 导致状态栏下空一截）。
     */
    private static WindowGeometry.Rect applyLandscapeMaxHeight(
            WindowGeometry.Rect geo, ScreenSafe safe, int minH) {
        if (safe.screenW <= safe.screenH || safe.statusBarH <= 0) {
            return geo;
        }
        int maxH = Math.max(Math.max(1, minH), safe.screenH - safe.statusBarH);
        if (geo.height <= maxH) {
            return geo;
        }
        int y = geo.y;
        if (y + maxH > safe.screenH) {
            y = Math.max(0, safe.screenH - maxH);
        }
        return new WindowGeometry.Rect(geo.x, y, geo.width, maxH);
    }

    /**
     * 【code 1069–1076】读<strong>物理显示</strong>大小（{@link WindowManager#getMaximumWindowMetrics()}），
     * 不要用宿主 {@link DisplayMetrics}：DLsiteSound 竖屏锁定时 widthPixels 仍是竖屏短边。
     *
     * <p>【code 1076】竖屏四边 inset=0。横屏：insetT=0（可贴顶）；
     * 右缘 insetR = max(状态栏高度, {@link #LANDSCAPE_RIGHT_KEEP_FLOOR_DP})；
     * 高度上限另用 {@link #statusBarH}（屏高 − 状态栏），不靠顶缘 inset。
     */
    private ScreenSafe screenSafe(Context ctx) {
        int screenW = 0;
        int screenH = 0;
        WindowManager useWm = wm;
        try {
            if (useWm == null && ctx != null) {
                useWm = (WindowManager) ctx.getSystemService(Context.WINDOW_SERVICE);
            }
            if (useWm != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                WindowMetrics metrics;
                try {
                    metrics = useWm.getMaximumWindowMetrics();
                } catch (Throwable t) {
                    metrics = useWm.getCurrentWindowMetrics();
                }
                Rect bounds = metrics.getBounds();
                screenW = bounds.width();
                screenH = bounds.height();
            } else if (useWm != null) {
                android.view.Display display = useWm.getDefaultDisplay();
                android.graphics.Point p = new android.graphics.Point();
                display.getRealSize(p);
                screenW = p.x;
                screenH = p.y;
            }
        } catch (Throwable ignored) {
        }
        if (screenW <= 0 || screenH <= 0) {
            DisplayMetrics dm = ctx.getResources().getDisplayMetrics();
            screenW = dm.widthPixels;
            screenH = dm.heightPixels;
        }
        // 横屏：顶缘 0（可移到顶）；右缘护角标；高度上限用 statusBarH。竖屏全 0。
        int insetR = 0;
        int statusH = 0;
        if (screenW > screenH) {
            statusH = statusBarHeightPx(ctx, useWm);
            int floor = dp(ctx, LANDSCAPE_RIGHT_KEEP_FLOOR_DP);
            insetR = Math.max(statusH, floor);
        }
        return new ScreenSafe(screenW, screenH, 0, 0, insetR, 0, statusH);
    }

    /**
     * 本机状态栏高度（px）。优先 {@link WindowInsets.Type#statusBars()}，
     * 回退 {@code android:status_bar_height}；都读不到则 0（由调用方用 floor）。
     */
    private static int statusBarHeightPx(Context ctx, WindowManager useWm) {
        try {
            if (useWm != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                // Current 带真实 insets；Maximum 的 insets 常为 0。
                WindowInsets wi = useWm.getCurrentWindowMetrics().getWindowInsets();
                android.graphics.Insets bars = wi.getInsets(WindowInsets.Type.statusBars());
                int h = Math.max(bars.top, bars.bottom);
                if (h <= 0) {
                    h = Math.max(bars.left, bars.right);
                }
                if (h > 0) {
                    return h;
                }
            }
        } catch (Throwable ignored) {
        }
        try {
            int resId = ctx.getResources().getIdentifier("status_bar_height", "dimen", "android");
            if (resId > 0) {
                int h = ctx.getResources().getDimensionPixelSize(resId);
                if (h > 0) {
                    return h;
                }
            }
        } catch (Throwable ignored) {
        }
        return 0;
    }

    public boolean isShowing() {
        return showing;
    }

    private static int dp(Context ctx, float v) {
        // 【code 995】dp→px 口径收敛到 {@link Utils#applyDimensionDip}。
        // ⚠️ 本类走的是**截断**口径（TypedValue.applyDimension 官方实现，无 +0.5f），
        // 与 Utils.dip2px 的四舍五入口径最多差 1px —— 这里**只搬不改**，
        // 换口径属像素级行为变更，不能混在同一次重构里（见 Utils 类头注释）。
        return Utils.applyDimensionDip(ctx, v);
    }

    /** v29：把当前窗口几何写进静态记忆（尺寸 + 位置）。 */
    private void saveGeometry() {
        WindowManager.LayoutParams p = params;
        if (p == null) {
            return;
        }
        sLastW = p.width;
        sLastH = p.height;
        sLastX = p.x;
        sLastY = p.y;
    }

    /**
     * 移动 + 缩放（右下角手柄）。窗口根的 OnTouchListener 先于子 View 的 onTouchEvent 生效，
     * 且内部 ScrollView 已被改成不拦截触摸，所以这里能稳定拿到全部事件。
     */
    private class GestureListener implements View.OnTouchListener {
        private boolean resizing;
        private boolean moved;
        private float downRawX;
        private float downRawY;
        private int startW;
        private int startH;
        private int startX;
        private int startY;

        @Override
        public boolean onTouch(View v, MotionEvent event) {
            synchronized (lock) {
                if (params == null || view == null || wm == null) {
                    return false;
                }
                switch (event.getActionMasked()) {
                    case MotionEvent.ACTION_DOWN: {
                        downRawX = event.getRawX();
                        downRawY = event.getRawY();
                        startW = params.width;
                        startH = params.height;
                        startX = params.x;
                        startY = params.y;
                        moved = false;
                        // 缩放热区：以右下角**三角形自身为中心**、边长 GRIP_HIT_DP(30dp) 的正方形
                        // （v16 之前是「距窗口右下角 44dp 见方」—— 既过大，又与三角形错位）。
                        resizing = view.hitResizeArea(event.getX(), event.getY());
                        // 诊断：确认触摸是否真的送达悬浮窗视图（若「点了没反应」，先看有没有这行）
                        LogGate.debug(TAG, " touch DOWN x=" + (int) event.getX()
                                + " y=" + (int) event.getY()
                                + " viewW=" + view.getWidth() + " viewH=" + view.getHeight()
                                + " resizing=" + resizing);
                        return true;
                    }
                    case MotionEvent.ACTION_MOVE: {
                        float rawDx = event.getRawX() - downRawX;
                        float rawDy = event.getRawY() - downRawY;
                        float slop = 8f * view.getContext().getResources().getDisplayMetrics().density;
                        // 超过阈值才判定为拖动，轻触不移动 → 视为「点击」。
                        if (!moved && (Math.abs(rawDx) > slop || Math.abs(rawDy) > slop)) {
                            moved = true;
                        }
                        if (!moved) {
                            return true;
                        }
                        int dx = (int) rawDx;
                        int dy = (int) rawDy;
                        ScreenSafe safe = screenSafe(view.getContext());
                        if (resizing) {
                            // 缩放下界：当前字幕行完整显示所需的最小尺寸（动态）。
                            // 【2.2.13 / 987】上面都是**玻璃**内容的最小值；窗口包着的一圈
                            //   阴影环（987 起宽度为 0）要补进去，否则玻璃会被压得比字幕还小。
                            final int frame2 = 2 * view.getFrameInsetPx();
                            int dynMinW = view.getMinWidthPx();
                            int dynMinH = view.getMinHeightPx();
                            int loW = (dynMinW > 0 ? dynMinW : dp(view.getContext(), MIN_W_DP))
                                    + frame2;
                            int loH = (dynMinH > 0 ? dynMinH : dp(view.getContext(), MIN_H_DP))
                                    + frame2;
                            WindowGeometry.Rect geo = clampGeo(
                                    startX, startY, startW + dx, startH + dy, safe, loW, loH);
                            params.width = geo.width;
                            params.height = geo.height;
                            // 缩放只改右下角，位置保持按下时的左上角（再夹一次防越界）。
                            params.x = geo.x;
                            params.y = geo.y;
                            view.recenterCurrent(); // 缩放时保持当前字幕行垂直居中
                        } else {
                            // 横屏 insetT=0，可拖到顶；高度已在缩放/旋转路径按 statusBar 限过。
                            WindowGeometry.Rect geo = WindowGeometry.clampPosition(
                                    startX + dx, startY + dy,
                                    params.width, params.height,
                                    safe.screenW, safe.screenH,
                                    safe.insetL, safe.insetT, safe.insetR, safe.insetB);
                            params.x = geo.x;
                            params.y = geo.y;
                        }
                        try {
                            wm.updateViewLayout(view, params);
                        } catch (Throwable ignored) {
                        }
                        saveGeometry(); // v29：随时记住尺寸/位置，供「关窗 → 重开」时恢复
                        return true;
                    }
                    case MotionEvent.ACTION_UP: {
                        // 未拖动、且不是按在右下角缩放手柄上 → 视为「点击面板任意处」：
                        // 显示右上角关闭按钮（✕）；【code 944】之后 5s 内没人点它，
                        // 视图侧会自动把它藏回去。
                        if (!moved && !resizing) {
                            view.onPanelTapped();
                        } else {
                            LogGate.debug(TAG, " touch UP moved=" + moved
                                    + " resizing=" + resizing + " -> no tap toggle");
                        }
                        saveGeometry(); // v29：抬手时再固化一次
                        resizing = false;
                        moved = false;
                        return true;
                    }
                    case MotionEvent.ACTION_CANCEL:
                        // 【2.1.4】诊断：手势被系统打断时留一行。2.1.3 实测「16 次 DOWN 只有 15 次 UP」，补上这条日志后下次取证能一眼看清手势从哪个口出去（本条只记日志，不改行为）。
                        LogGate.debug(TAG, " touch CANCEL moved=" + moved
                                + " resizing=" + resizing + " -> gesture aborted by system");
                        resizing = false;
                        moved = false;
                        return true;
                    default:
                        return false;
                }
            }
        }

    }
}
