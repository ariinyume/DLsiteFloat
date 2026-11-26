/*
 * DLsiteSound Floating Subtitle - Xposed module for DLsite Sound
 * Copyright (C) 2026 ariinyume
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package io.github.ariinyume.dlsitesoundfloat.view;

import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Color;
import android.graphics.RenderEffect;
import android.graphics.Typeface;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.DisplayMetrics;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.view.animation.DecelerateInterpolator;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.util.Collections;
import java.util.List;

import io.github.ariinyume.dlsitesoundfloat.config.RemoteConfig;
import io.github.ariinyume.dlsitesoundfloat.config.SubtitleConfig;
import io.github.ariinyume.dlsitesoundfloat.data.SubtitleCue;
import io.github.ariinyume.dlsitesoundfloat.data.SubtitleRepository;
import io.github.ariinyume.dlsitesoundfloat.ui.Strings;
import io.github.ariinyume.dlsitesoundfloat.ui.UiLang;
import io.github.ariinyume.dlsitesoundfloat.util.Utils;

/**
 * 全屏字幕壳（挂在宿主 decor）：氛围背景 + 左上角 Spicy 霜面返回 +
 * 右下角「跟随字幕」（仅手滑出现）+ 换行位移动画；左右边缘放行走势返回。
 */
public class FullscreenSubtitleView extends FrameLayout {

    /** SpicyEX 风：只做 scrollY 平滑下移，不用 translationY 叠滚（叠滚会整页抖）。 */
    private static final long TRAVEL_ANIM_MS = 380L;
    private static final long FOLLOW_CHIP_ANIM_MS = 220L;
    private static final float SECONDARY_SIZE_FACTOR = 0.82f;
    private static final float SECONDARY_ALPHA_FACTOR = 0.75f;
    private static final int BTN_DP = 44;
    private static final int EDGE_DP = 16;
    private static final int BELOW_BACK_GAP_DP = 20;
    /** 无 WindowInsets 时左右手势留白兜底（≈系统边缘返回区）。 */
    private static final int GESTURE_EDGE_FALLBACK_DP = 28;
    /** 顶边硬裁切改成渐隐时，额外向下延伸的柔边（dp）。 */
    private static final int TOP_FADE_EXTRA_DP = 36;

    private final AmbientCoverBackdrop backdrop;
    private final ScrollView scroll;
    private final LinearLayout lines;
    private final View backBtn;
    private final TextView followChip;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final Runnable fadePass = this::applyTopFadeAlphas;

    private boolean followEnabled = true;
    private int lastCueIndex = -1;
    private String lastWorkKey = "";
    private int[] cueTops = new int[0];
    private int[] cueHeights = new int[0];
    private int lastCueSig = Integer.MIN_VALUE;
    private int lastStyleSig = Integer.MIN_VALUE;
    private ValueAnimator travelAnim;
    private int contentTopPadPx;
    private int gestureEdgePx;
    private boolean followChipVisible = false;
    private float touchDownX = -1f;
    private float touchDownY = -1f;
    private boolean fingerDown = false;

    public FullscreenSubtitleView(Context context) {
        super(context);
        // 根不抢点击：边缘触摸放行走势返回；只让滚动区与钮消费。
        setClickable(false);
        setFocusable(false);
        setWillNotDraw(false);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            setSystemGestureExclusionRects(Collections.emptyList());
        }

        gestureEdgePx = Utils.dip2px(context, GESTURE_EDGE_FALLBACK_DP);

        backdrop = new AmbientCoverBackdrop(context);
        backdrop.setClickable(false);
        addView(backdrop, new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT));

        scroll = new ScrollView(context) {
            @Override
            public boolean onInterceptTouchEvent(MotionEvent ev) {
                if (isInGestureEdge(ev.getX())) {
                    return false;
                }
                return super.onInterceptTouchEvent(ev);
            }

            @Override
            public boolean onTouchEvent(MotionEvent ev) {
                int a = ev.getActionMasked();
                if (a == MotionEvent.ACTION_DOWN) {
                    touchDownX = ev.getX();
                    touchDownY = ev.getY();
                    fingerDown = true;
                    if (isInGestureEdge(touchDownX)) {
                        fingerDown = false;
                        return false;
                    }
                } else if (a == MotionEvent.ACTION_MOVE) {
                    if (fingerDown && touchDownY >= 0f
                            && Math.abs(ev.getY() - touchDownY) > Utils.dip2px(getContext(), 6)) {
                        pauseFollowFromUserScroll();
                    }
                } else if (a == MotionEvent.ACTION_UP || a == MotionEvent.ACTION_CANCEL) {
                    touchDownX = -1f;
                    touchDownY = -1f;
                    fingerDown = false;
                }
                return super.onTouchEvent(ev);
            }

            @Override
            protected void onScrollChanged(int l, int t, int oldl, int oldt) {
                super.onScrollChanged(l, t, oldl, oldt);
                // 手指在拖：任何纵向滚动量都暂停跟随并弹出 chip（程序滚动不走这里的 fingerDown）
                if (fingerDown && Math.abs(t - oldt) > 1) {
                    pauseFollowFromUserScroll();
                }
                applyTopFadeAlphas();
            }
        };
        scroll.setFillViewport(true);
        scroll.setOverScrollMode(OVER_SCROLL_NEVER);
        // 硬裁切到返回钮下方：字幕不得画进按钮背后；柔边只在裁切线以下做 alpha 渐隐
        scroll.setClipToPadding(true);
        scroll.setClipChildren(true);
        scroll.setClickable(true);
        scroll.setVerticalScrollBarEnabled(false);
        scroll.setHorizontalScrollBarEnabled(false);
        scroll.setScrollBarFadeDuration(0);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            scroll.setVerticalScrollbarThumbDrawable(null);
            scroll.setVerticalScrollbarTrackDrawable(null);
        }
        contentTopPadPx = Utils.dip2px(context, 96);
        scroll.setPadding(0, contentTopPadPx, 0, 0);
        lines = new LinearLayout(context);
        lines.setOrientation(LinearLayout.VERTICAL);
        int padH = Utils.dip2px(context, 28);
        lines.setPadding(padH, 0, padH, Utils.dip2px(context, 120));
        scroll.addView(lines, new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        addView(scroll, new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT));

        // 左上角返回（Spicy 透明霜面）
        backBtn = buildFrostCircleButton(context, "←");
        LayoutParams blp = new LayoutParams(Utils.dip2px(context, BTN_DP), Utils.dip2px(context, BTN_DP));
        blp.gravity = Gravity.TOP | Gravity.START;
        blp.leftMargin = Utils.dip2px(context, EDGE_DP);
        blp.topMargin = statusBarTopFallback(context) + Utils.dip2px(context, 8);
        addView(backBtn, blp);
        backBtn.setOnClickListener(v ->
                SubtitleRepository.getInstance().setFullscreenOpen(false));
        backBtn.setContentDescription("Back");
        backBtn.addOnLayoutChangeListener((v, l, t, r, b, ol, ot, or, ob) -> {
            if (b != ob) {
                relayoutContentTop();
            }
        });

        // 右下角跟随字幕：默认隐藏，仅手滑后出现
        followChip = buildFrostPill(context);
        LayoutParams flp = new LayoutParams(LayoutParams.WRAP_CONTENT, Utils.dip2px(context, 40));
        flp.gravity = Gravity.BOTTOM | Gravity.END;
        flp.rightMargin = Utils.dip2px(context, EDGE_DP);
        flp.bottomMargin = Utils.dip2px(context, 36);
        addView(followChip, flp);
        followChip.setVisibility(GONE);
        followChip.setAlpha(0f);
        followChip.setTranslationY(Utils.dip2px(context, 14));
        followChip.setOnClickListener(v -> onFollowChipClicked());
        refreshFollowChipLabel();

        backBtn.post(this::relayoutContentTop);
        setOnApplyWindowInsetsListener((v, insets) -> {
            applyGestureInsets(insets);
            applyStatusBarToBack(insets);
            relayoutContentTop();
            return insets;
        });
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            requestApplyInsets();
        }
    }

    private static int statusBarTopFallback(Context ctx) {
        int resId = ctx.getResources().getIdentifier("status_bar_height", "dimen", "android");
        if (resId > 0) {
            try {
                return ctx.getResources().getDimensionPixelSize(resId);
            } catch (Throwable ignored) {
            }
        }
        return Utils.dip2px(ctx, 28);
    }

    private void applyStatusBarToBack(WindowInsets insets) {
        if (backBtn == null || insets == null) {
            return;
        }
        int top = 0;
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                android.graphics.Insets si = insets.getInsets(WindowInsets.Type.statusBars());
                top = si.top;
            } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                top = insets.getSystemWindowInsetTop();
            }
        } catch (Throwable ignored) {
        }
        if (top <= 0) {
            top = statusBarTopFallback(getContext());
        }
        LayoutParams lp = (LayoutParams) backBtn.getLayoutParams();
        if (lp == null) {
            return;
        }
        int want = top + Utils.dip2px(getContext(), 8);
        if (lp.topMargin != want) {
            lp.topMargin = want;
            backBtn.setLayoutParams(lp);
        }
    }

    /** 在 addView 进 decor 之前同步采封面（避免采到自己）。 */
    public void prepareCoverBeforeAttach() {
        backdrop.refreshSync();
    }

    /** 确保位于 decor 最上层（胶囊组可能被结构扫描再次 addView）。 */
    public void bringShellToFront() {
        try {
            bringToFront();
        } catch (Throwable ignored) {
        }
    }

    private void applyGestureInsets(WindowInsets insets) {
        if (insets == null) {
            return;
        }
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                android.graphics.Insets gi = insets.getSystemGestureInsets();
                int edge = Math.max(gi.left, gi.right);
                if (edge > 0) {
                    gestureEdgePx = edge;
                }
            }
        } catch (Throwable ignored) {
        }
    }

    private boolean isInGestureEdge(float x) {
        int w = getWidth();
        if (w <= 0) {
            w = scroll.getWidth();
        }
        return x <= gestureEdgePx || (w > 0 && x >= w - gestureEdgePx);
    }

    @Override
    public boolean dispatchTouchEvent(MotionEvent ev) {
        // 左右系统手势区：本壳不消费，交给系统 / Decor 处理返回。
        if (ev != null && isInGestureEdge(ev.getX())) {
            int a = ev.getActionMasked();
            if (a == MotionEvent.ACTION_DOWN
                    || a == MotionEvent.ACTION_MOVE
                    || a == MotionEvent.ACTION_UP
                    || a == MotionEvent.ACTION_CANCEL) {
                return false;
            }
        }
        return super.dispatchTouchEvent(ev);
    }

    private int topSoftFadeBandPx() {
        return Utils.dip2px(getContext(), TOP_FADE_EXTRA_DP);
    }

    /**
     * 显示区起点 = paddingTop（返回钮底+20dp，clipToPadding 硬裁切）。
     * 完全落在显示区内的行保持不透明（避免首行发灰）；
     * 仅当行顶已被裁进死区（top &lt; pad）时，按残留可见比例渐隐。
     */
    private void applyTopFadeAlphas() {
        if (scroll == null || lines == null || lines.getChildCount() == 0) {
            return;
        }
        int pad = scroll.getPaddingTop();
        if (pad <= 0) {
            return;
        }
        float fadeStart = pad;
        int scrollY = scroll.getScrollY();
        for (int i = 0; i < lines.getChildCount(); i++) {
            View block = lines.getChildAt(i);
            float h = Math.max(1, block.getHeight());
            float top = block.getTop() - scrollY + pad;
            float bottom = top + h;
            float a;
            if (bottom <= fadeStart) {
                a = 0f;
            } else if (top >= fadeStart) {
                // 整行在返回钮下方显示区内 → 不压灰
                a = 1f;
            } else {
                // 行顶已滚进裁切区：按仍露出的高度比例柔隐
                a = (bottom - fadeStart) / h;
                if (a < 0f) {
                    a = 0f;
                } else if (a > 1f) {
                    a = 1f;
                }
                a = a * a * (3f - 2f * a);
            }
            if (Math.abs(block.getAlpha() - a) > 0.02f) {
                block.setAlpha(a);
            }
        }
    }

    private void scheduleTopFadePass() {
        main.removeCallbacks(fadePass);
        main.post(fadePass);
    }

    private void relayoutContentTop() {
        if (backBtn == null || scroll == null) {
            return;
        }
        int backBottom = backBtn.getBottom();
        if (backBottom <= 0) {
            LayoutParams lp = (LayoutParams) backBtn.getLayoutParams();
            int topM = lp != null ? lp.topMargin : statusBarTopFallback(getContext());
            backBottom = topM + Utils.dip2px(getContext(), BTN_DP);
        }
        // 顶边距：返回钮底 + 20dp；硬裁切保证不进按钮背后，柔边在裁切线以下
        int want = backBottom + Utils.dip2px(getContext(), BELOW_BACK_GAP_DP);
        if (want == contentTopPadPx && scroll.getPaddingTop() == want) {
            scheduleTopFadePass();
            return;
        }
        contentTopPadPx = want;
        scroll.setPadding(0, contentTopPadPx, 0, 0);
        scroll.setClipToPadding(true);
        int padH = Utils.dip2px(getContext(), 28);
        lines.setPadding(padH, 0, padH, Utils.dip2px(getContext(), 120));
        io.github.ariinyume.dlsitesoundfloat.util.XposedCompat.log(
                "[DLsiteSoundFloat:Fullscreen] contentTopPad=" + contentTopPadPx
                        + "px backBottom=" + backBottom + " softFade=" + topSoftFadeBandPx());
        refreshCueTops();
        scheduleTopFadePass();
    }

    private View buildFrostCircleButton(Context ctx, String glyph) {
        FrameLayout wrap = new FrameLayout(ctx);
        float dens = ctx.getResources().getDisplayMetrics().density;
        float r = Utils.dip2px(ctx, BTN_DP) / 2f;
        wrap.setBackground(LiquidGlassDrawable.frostChip(r, dens));
        TextView tv = new TextView(ctx);
        tv.setText(glyph);
        tv.setTextColor(Color.WHITE);
        tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 20);
        tv.setGravity(Gravity.CENTER);
        wrap.addView(tv, new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT));
        wrap.setClickable(true);
        return wrap;
    }

    private TextView buildFrostPill(Context ctx) {
        TextView tv = new TextView(ctx);
        float dens = ctx.getResources().getDisplayMetrics().density;
        float r = Utils.dip2px(ctx, 20);
        tv.setBackground(LiquidGlassDrawable.frostChip(r, dens));
        tv.setTextColor(Color.WHITE);
        tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13);
        tv.setGravity(Gravity.CENTER);
        int ph = Utils.dip2px(ctx, 16);
        tv.setPadding(ph, 0, ph, 0);
        tv.setMinWidth(Utils.dip2px(ctx, 108));
        return tv;
    }

    private void pauseFollowFromUserScroll() {
        if (followEnabled) {
            followEnabled = false;
        }
        showFollowChip();
    }

    private void onFollowChipClicked() {
        followEnabled = true;
        hideFollowChip();
        int idx = SubtitleRepository.getInstance().findCurrentCueIndex();
        if (idx >= 0) {
            scrollToCue(idx, true);
        }
    }

    private void showFollowChip() {
        if (followChip == null) {
            return;
        }
        refreshFollowChipLabel();
        if (followChipVisible && followChip.getVisibility() == VISIBLE) {
            return;
        }
        followChipVisible = true;
        followChip.setVisibility(VISIBLE);
        followChip.animate().cancel();
        followChip.animate()
                .alpha(1f)
                .translationY(0f)
                .setDuration(FOLLOW_CHIP_ANIM_MS)
                .setInterpolator(new DecelerateInterpolator())
                .start();
    }

    private void hideFollowChip() {
        if (followChip == null || !followChipVisible) {
            followChipVisible = false;
            if (followChip != null) {
                followChip.setVisibility(GONE);
                followChip.setAlpha(0f);
            }
            return;
        }
        followChipVisible = false;
        followChip.animate().cancel();
        final float dy = Utils.dip2px(getContext(), 14);
        followChip.animate()
                .alpha(0f)
                .translationY(dy)
                .setDuration(FOLLOW_CHIP_ANIM_MS - 40)
                .setInterpolator(new DecelerateInterpolator())
                .withEndAction(() -> {
                    followChip.setVisibility(GONE);
                    followChip.setTranslationY(dy);
                })
                .start();
    }

    private void refreshFollowChipLabel() {
        if (followChip == null) {
            return;
        }
        UiLang lang;
        try {
            lang = UiLang.fromConfigValue(RemoteConfig.get().uiLanguage);
        } catch (Throwable t) {
            lang = UiLang.ZH_CN;
        }
        followChip.setText(Strings.FOLLOW_SUBTITLES.get(lang));
    }

    public void updateFromRepository() {
        SubtitleRepository repo = SubtitleRepository.getInstance();
        if (repo.shouldShowNoSubtitles()) {
            main.post(() -> SubtitleRepository.getInstance().setFullscreenOpen(false));
            return;
        }
        String wk = "";
        try {
            wk = repo.getCuesWorkKey() != null ? repo.getCuesWorkKey() : "";
        } catch (Throwable ignored) {
        }
        if (!wk.equals(lastWorkKey)) {
            lastWorkKey = wk;
            backdrop.refreshAsync();
        }

        List<SubtitleCue> cues = repo.getCues();
        int idx = repo.findCurrentCueIndex();
        SubtitleConfig cfg = RemoteConfig.get().copy();
        cfg.textAlign = cfg.fullscreenTextAlign;
        DisplayMetrics dm = getResources().getDisplayMetrics();
        SubtitleStyle st = SubtitleStyle.of(cfg, dm);
        int styleSig = styleSignature(cfg);

        int sig = cueListSignature(cues);
        boolean rebuild = sig != lastCueSig || lines.getChildCount() == 0;
        boolean cueMoved = idx != lastCueIndex;
        boolean styleChanged = styleSig != lastStyleSig;
        int prevCue = lastCueIndex;
        lastCueSig = sig;
        lastStyleSig = styleSig;
        if (rebuild) {
            rebuildLines(cues, idx, st);
        } else if (cueMoved || styleChanged) {
            if (styleChanged) {
                restyleAll(st, idx);
            } else {
                restyleCueBlock(prevCue, false, st);
                restyleCueBlock(idx, true, st);
            }
            // 等字号重排完成后再滚，避免「改高 → 瞬滚 → translationY」连环抖
            if (followEnabled && idx >= 0 && cueMoved) {
                final int go = idx;
                lines.post(() -> scrollToCue(go, true));
            }
        }
        lastCueIndex = idx;
    }

    private void rebuildLines(List<SubtitleCue> cues, int currentIdx, SubtitleStyle st) {
        cancelTravelAnim();
        lines.removeAllViews();
        if (cues == null || cues.isEmpty()) {
            cueTops = new int[0];
            cueHeights = new int[0];
            return;
        }
        cueTops = new int[cues.size()];
        cueHeights = new int[cues.size()];
        for (int i = 0; i < cues.size(); i++) {
            SubtitleCue cue = cues.get(i);
            boolean active = i == currentIdx;
            LinearLayout block = new LinearLayout(getContext());
            block.setOrientation(LinearLayout.VERTICAL);
            block.setTag(i);
            List<String> subs = cue.subtitles;
            if (subs == null || subs.isEmpty()) {
                continue;
            }
            for (int li = 0; li < subs.size(); li++) {
                String text = subs.get(li);
                if (text == null || text.trim().isEmpty()) {
                    continue;
                }
                TextView tv = new TextView(getContext());
                tv.setText(text.trim());
                styleLine(tv, st, active, li == 0);
                block.addView(tv, new LinearLayout.LayoutParams(
                        LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT));
            }
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                    LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT);
            lp.bottomMargin = Utils.dip2px(getContext(), 18);
            lines.addView(block, lp);
        }
        lines.post(() -> {
            refreshCueTops();
            if (followEnabled && currentIdx >= 0) {
                scrollToCue(currentIdx, false);
            }
            applyTopFadeAlphas();
        });
    }

    private void refreshCueTops() {
        for (int i = 0; i < lines.getChildCount(); i++) {
            View child = lines.getChildAt(i);
            Object tag = child.getTag();
            if (tag instanceof Integer) {
                int ci = (Integer) tag;
                if (ci >= 0 && ci < cueTops.length) {
                    cueTops[ci] = child.getTop();
                    cueHeights[ci] = child.getHeight();
                }
            }
        }
    }

    private void restyleAll(SubtitleStyle st, int currentIdx) {
        for (int i = 0; i < lines.getChildCount(); i++) {
            View child = lines.getChildAt(i);
            if (!(child instanceof LinearLayout)) {
                continue;
            }
            Object tag = child.getTag();
            if (!(tag instanceof Integer)) {
                continue;
            }
            restyleBlock((LinearLayout) child, ((Integer) tag) == currentIdx, st);
        }
    }

    private void restyleCueBlock(int cueIdx, boolean active, SubtitleStyle st) {
        if (cueIdx < 0) {
            return;
        }
        for (int i = 0; i < lines.getChildCount(); i++) {
            View child = lines.getChildAt(i);
            if (!(child instanceof LinearLayout)) {
                continue;
            }
            Object tag = child.getTag();
            if (tag instanceof Integer && ((Integer) tag) == cueIdx) {
                restyleBlock((LinearLayout) child, active, st);
                return;
            }
        }
    }

    private void restyleBlock(LinearLayout block, boolean active, SubtitleStyle st) {
        for (int j = 0; j < block.getChildCount(); j++) {
            View row = block.getChildAt(j);
            if (row instanceof TextView) {
                styleLine((TextView) row, st, active, j == 0);
            }
        }
    }

    private void styleLine(TextView tv, SubtitleStyle st, boolean active, boolean primary) {
        float sizeSp = active
                ? (primary ? st.activeSizeSp : st.activeSizeSp * SECONDARY_SIZE_FACTOR)
                : (primary ? st.inactiveSizeSp : st.inactiveSizeSp * SECONDARY_SIZE_FACTOR);
        float alpha = active
                ? (primary ? st.activeAlpha : st.activeAlpha * SECONDARY_ALPHA_FACTOR)
                : (primary ? st.inactiveAlpha : st.inactiveAlpha * SECONDARY_ALPHA_FACTOR);
        int color = active ? st.activeColor : st.inactiveColor;
        tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, sizeSp);
        tv.setTextColor(color);
        tv.setAlpha(alpha);
        tv.setGravity(st.gravity);
        tv.setPadding(Utils.dip2px(getContext(), st.linePadH),
                Utils.dip2px(getContext(), st.linePadV),
                Utils.dip2px(getContext(), st.linePadH),
                Utils.dip2px(getContext(), Math.max(2, st.linePadV / 2)));
        if (st.fontFollowSystem) {
            SystemFont.clearTypeface(tv.getPaint());
            SystemFont.applyBold(tv.getPaint(), active ? st.activeFakeBold : st.inactiveFakeBold);
            tv.setTypeface(Typeface.DEFAULT);
        } else {
            tv.setTypeface(active ? st.activeTypeface : st.inactiveTypeface);
        }
        if (st.shadowRadiusPx > 0f) {
            tv.setShadowLayer(st.shadowRadiusPx, 0f, st.shadowDyPx, st.shadowColor);
        } else {
            tv.setShadowLayer(0f, 0f, 0f, 0);
        }
        if (!active && st.inactiveBlurEnabled && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            try {
                float r = Math.max(1f, st.blurRadiusPx);
                tv.setRenderEffect(RenderEffect.createBlurEffect(
                        r, r, android.graphics.Shader.TileMode.CLAMP));
            } catch (Throwable ignored) {
            }
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            try {
                tv.setRenderEffect(null);
            } catch (Throwable ignored) {
            }
        }
    }

    private static int styleSignature(SubtitleConfig cfg) {
        if (cfg == null) {
            return 0;
        }
        int h = cfg.fullscreenTextAlign == null ? 0 : cfg.fullscreenTextAlign.hashCode();
        h = 31 * h + Float.floatToIntBits(cfg.activeScale);
        h = 31 * h + cfg.activeHighlight;
        h = 31 * h + cfg.inactiveHighlight;
        h = 31 * h + cfg.inactiveScalePct;
        h = 31 * h + (cfg.inactiveBlurEnabled ? 1 : 0);
        h = 31 * h + cfg.inactiveBlurSteps;
        h = 31 * h + cfg.subtitleColor;
        h = 31 * h + cfg.shadowStrength;
        h = 31 * h + (cfg.subtitleBold ? 1 : 0);
        h = 31 * h + Float.floatToIntBits(cfg.lineSpacingDp);
        return h;
    }

    private static int cueListSignature(List<SubtitleCue> cues) {
        if (cues == null || cues.isEmpty()) {
            return 0;
        }
        int n = cues.size();
        SubtitleCue a = cues.get(0);
        SubtitleCue b = cues.get(n - 1);
        int h = n * 31;
        if (a != null) {
            h = h * 17 + (int) (a.startTime * 1000);
        }
        if (b != null) {
            h = h * 13 + (int) (b.endTime * 1000);
        }
        return h;
    }

    /**
     * 滚到活动行（视口约 1/3 处）。换行动画只平滑改 scrollY，
     * 让下一行自然进入焦点，不做 translationY 补偿（那套在全量列表上会整页抖）。
     */
    private void scrollToCue(int cueIdx, boolean animate) {
        if (cueIdx < 0 || cueIdx >= cueTops.length) {
            return;
        }
        Runnable go = () -> {
            refreshCueTops();
            if (cueIdx >= cueTops.length) {
                return;
            }
            int vh = scroll.getHeight() - scroll.getPaddingTop() - scroll.getPaddingBottom();
            if (vh <= 0) {
                return;
            }
            int top = cueTops[cueIdx];
            int h = cueIdx < cueHeights.length ? cueHeights[cueIdx] : 0;
            int maxScroll = Math.max(0, lines.getHeight() - vh);
            int targetY = Math.max(0, Math.min(maxScroll, top - vh / 3 + h / 4));
            int fromY = scroll.getScrollY();
            cancelTravelAnim();
            if (lines.getTranslationY() != 0f) {
                lines.setTranslationY(0f);
            }
            if (!animate || Math.abs(targetY - fromY) < 2) {
                scroll.scrollTo(0, targetY);
                applyTopFadeAlphas();
                return;
            }
            ValueAnimator anim = ValueAnimator.ofInt(fromY, targetY);
            anim.setDuration(TRAVEL_ANIM_MS);
            anim.setInterpolator(new DecelerateInterpolator(1.6f));
            anim.addUpdateListener(a -> {
                if (scroll != null) {
                    scroll.scrollTo(0, (Integer) a.getAnimatedValue());
                    applyTopFadeAlphas();
                }
            });
            travelAnim = anim;
            anim.start();
        };
        // 布局未完成时 top 为 0，再等一帧
        if (lines.getHeight() <= 0 || cueTops[cueIdx] == 0 && cueIdx > 0) {
            lines.post(go);
        } else {
            go.run();
        }
    }

    private void cancelTravelAnim() {
        if (travelAnim != null) {
            travelAnim.cancel();
            travelAnim = null;
        }
        if (lines != null && lines.getTranslationY() != 0f) {
            lines.setTranslationY(0f);
        }
    }

    @Override
    protected void onDetachedFromWindow() {
        super.onDetachedFromWindow();
        main.removeCallbacks(fadePass);
        cancelTravelAnim();
        if (followChip != null) {
            followChip.animate().cancel();
        }
    }
}
