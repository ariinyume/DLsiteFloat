/*
 * DLsiteSound Floating Subtitle - Xposed module for DLsite Sound
 * Copyright (C) 2026 ariinyume
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package io.github.ariinyume.dlsitesoundfloat.view;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.RenderEffect;
import android.graphics.drawable.BitmapDrawable;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.AttributeSet;
import android.view.View;
import android.widget.FrameLayout;
import android.widget.ImageView;

import io.github.ariinyume.dlsitesoundfloat.ui.SettingsPreviewBackdropLogic;
import io.github.ariinyume.dlsitesoundfloat.util.CoverAmbientLogic;
import io.github.ariinyume.dlsitesoundfloat.util.CoverArtSampler;
import io.github.ariinyume.dlsitesoundfloat.util.MoriAccent;
import io.github.ariinyume.dlsitesoundfloat.util.XposedCompat;

/**
 * 全屏字幕背景：封面下采样模糊 + 取色渐变；无封面时 MoriAccent / 深色兜底。
 */
public class AmbientCoverBackdrop extends FrameLayout {

    private static final String TAG = "[DLsiteSoundFloat:Ambient]";
    private static final int SAMPLE_SIZE = 64;
    private static final int BLUR_RADIUS = 12;

    private final ImageView artView;
    private final View washView;
    private final Handler main = new Handler(Looper.getMainLooper());
    private Bitmap lastArt;
    private int gen;

    public AmbientCoverBackdrop(Context context) {
        this(context, null);
    }

    public AmbientCoverBackdrop(Context context, AttributeSet attrs) {
        super(context, attrs);
        setWillNotDraw(false);
        artView = new ImageView(context);
        artView.setScaleType(ImageView.ScaleType.CENTER_CROP);
        addView(artView, new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT));
        washView = new View(context);
        addView(washView, new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT));
        applyFallback(context);
    }

    /**
     * 同步采封面（须在主线程、且最好在全屏壳挂上 decor 之前调用）。
     */
    public void refreshSync() {
        final int g = ++gen;
        Bitmap raw = null;
        try {
            raw = CoverArtSampler.sampleFromPlayerPage();
        } catch (Throwable t) {
            XposedCompat.log(TAG + " sync sample: " + t.getMessage());
        }
        Prepared prep = prepare(raw, getContext());
        if (g == gen) {
            applyPrepared(prep, getContext());
        } else if (prep != null && prep.blurred != null) {
            try {
                prep.blurred.recycle();
            } catch (Throwable ignored) {
            }
        }
    }

    /** 异步采封面并刷新；可重复调用（换轨）。 */
    public void refreshAsync() {
        final int g = ++gen;
        final Context ctx = getContext();
        new Thread(() -> {
            Bitmap raw = null;
            try {
                raw = CoverArtSampler.sampleFromPlayerPage();
            } catch (Throwable t) {
                XposedCompat.log(TAG + " sample: " + t.getMessage());
            }
            final Bitmap src = raw;
            final Prepared prep = prepare(src, ctx);
            main.post(() -> {
                if (g != gen) {
                    if (prep != null && prep.blurred != null) {
                        try {
                            prep.blurred.recycle();
                        } catch (Throwable ignored) {
                        }
                    }
                    return;
                }
                applyPrepared(prep, ctx);
            });
        }, "fs-cover").start();
    }

    private void applyFallback(Context ctx) {
        int accent = 0;
        try {
            accent = MoriAccent.accentOr(ctx, 0);
        } catch (Throwable ignored) {
        }
        int[] pair = CoverAmbientLogic.fallbackPair(accent);
        setWash(pair[0], pair[1]);
        artView.setImageDrawable(null);
        artView.setBackgroundColor(pair[1]);
    }

    private void applyPrepared(Prepared prep, Context ctx) {
        if (prep == null || prep.blurred == null) {
            applyFallback(ctx);
            return;
        }
        recycleLast();
        lastArt = prep.blurred;
        artView.setImageDrawable(new BitmapDrawable(getResources(), lastArt));
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            try {
                artView.setRenderEffect(RenderEffect.createBlurEffect(
                        28f, 28f, android.graphics.Shader.TileMode.CLAMP));
            } catch (Throwable ignored) {
            }
        }
        setWash(prep.top, prep.bottom);
    }

    private void setWash(int top, int bottom) {
        washView.setBackground(new android.graphics.drawable.GradientDrawable(
                android.graphics.drawable.GradientDrawable.Orientation.TOP_BOTTOM,
                new int[]{
                        (top & 0x00FFFFFF) | 0x99000000,
                        (bottom & 0x00FFFFFF) | 0xCC000000
                }));
    }

    private void recycleLast() {
        if (lastArt != null) {
            try {
                lastArt.recycle();
            } catch (Throwable ignored) {
            }
            lastArt = null;
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            try {
                artView.setRenderEffect(null);
            } catch (Throwable ignored) {
            }
        }
    }

    @Override
    protected void onDetachedFromWindow() {
        super.onDetachedFromWindow();
        gen++;
        recycleLast();
    }

    private static Prepared prepare(Bitmap src, Context ctx) {
        if (src == null || src.isRecycled()) {
            return null;
        }
        try {
            Bitmap small = Bitmap.createScaledBitmap(src, SAMPLE_SIZE, SAMPLE_SIZE, true);
            if (src != small) {
                // src 来自 sampler 的独立拷贝，可回收
                try {
                    src.recycle();
                } catch (Throwable ignored) {
                }
            }
            int[] px = new int[SAMPLE_SIZE * SAMPLE_SIZE];
            small.getPixels(px, 0, SAMPLE_SIZE, 0, 0, SAMPLE_SIZE, SAMPLE_SIZE);
            int[] blurred = SettingsPreviewBackdropLogic.blurTile(px, SAMPLE_SIZE, BLUR_RADIUS);
            int[] pair = CoverAmbientLogic.dominantPair(blurred);
            if (pair == null) {
                int accent = 0;
                try {
                    accent = MoriAccent.accentOr(ctx, 0);
                } catch (Throwable ignored) {
                }
                pair = CoverAmbientLogic.fallbackPair(accent);
            }
            Bitmap out = Bitmap.createBitmap(SAMPLE_SIZE, SAMPLE_SIZE, Bitmap.Config.ARGB_8888);
            out.setPixels(blurred, 0, SAMPLE_SIZE, 0, 0, SAMPLE_SIZE, SAMPLE_SIZE);
            try {
                small.recycle();
            } catch (Throwable ignored) {
            }
            Prepared p = new Prepared();
            p.blurred = out;
            p.top = pair[0];
            p.bottom = pair[1];
            return p;
        } catch (Throwable t) {
            XposedCompat.log(TAG + " prepare: " + t.getMessage());
            return null;
        }
    }

    private static final class Prepared {
        Bitmap blurred;
        int top;
        int bottom;
    }
}
