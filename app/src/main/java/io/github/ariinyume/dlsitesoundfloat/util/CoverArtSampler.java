/*
 * DLsiteSound Floating Subtitle - Xposed module for DLsite Sound
 * Copyright (C) 2026 ariinyume
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package io.github.ariinyume.dlsitesoundfloat.util;

import android.app.Activity;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.drawable.BitmapDrawable;
import android.graphics.drawable.Drawable;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageView;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

import io.github.ariinyume.dlsitesoundfloat.hook.ActivityButtonHook;

/**
 * 从播放页封面抠 Bitmap。宿主用 Expo Image，{@code getDrawable} 常为空，
 * 因此优先按 tag 找 {@code player-thumbnail*}，再对 View 直接 {@code draw}。
 */
public final class CoverArtSampler {

    private static final String TAG = "[DLsiteSoundFloat:Cover]";
    private static final String THUMB_HINT = "PLAYER_THUMBNAIL";
    private static final int MAX_WALK = 1200;
    private static final int MIN_SIDE_PX = 64;
    private static final Handler MAIN = new Handler(Looper.getMainLooper());

    private CoverArtSampler() {
    }

    /**
     * 同步采封面（可在任意线程调用；内部切主线程 draw）。
     * @return 软件 Bitmap 拷贝，失败 null
     */
    public static Bitmap sampleFromPlayerPage() {
        if (Looper.myLooper() == Looper.getMainLooper()) {
            return sampleOnMain();
        }
        final AtomicReference<Bitmap> out = new AtomicReference<>();
        final CountDownLatch latch = new CountDownLatch(1);
        MAIN.post(() -> {
            try {
                out.set(sampleOnMain());
            } finally {
                latch.countDown();
            }
        });
        try {
            if (!latch.await(1200, TimeUnit.MILLISECONDS)) {
                XposedCompat.log(TAG + " sample timed out on main");
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        return out.get();
    }

    private static Bitmap sampleOnMain() {
        Activity a = ActivityButtonHook.currentPlayerActivity();
        if (a == null || a.isFinishing()) {
            XposedCompat.log(TAG + " no player activity");
            return null;
        }
        try {
            View root = a.getWindow() != null ? a.getWindow().getDecorView() : null;
            if (root == null) {
                return null;
            }
            Holder best = new Holder();
            walk(root, best, 0, new int[]{0});
            if (best.bmp != null && !best.bmp.isRecycled()) {
                XposedCompat.log(TAG + " HIT score=" + best.score
                        + " " + best.bmp.getWidth() + "x" + best.bmp.getHeight()
                        + " thumb=" + best.thumbHit);
                return best.bmp;
            }
            XposedCompat.log(TAG + " MISS (walked views, no bitmap)");
        } catch (Throwable t) {
            XposedCompat.log(TAG + " sample failed: " + t.getMessage());
        }
        return null;
    }

    private static void walk(View v, Holder best, int depth, int[] count) {
        if (v == null || depth > 56 || count[0] >= MAX_WALK) {
            return;
        }
        // 跳过我们自己的全屏壳，避免采到氛围层
        try {
            String cn = v.getClass().getName();
            if (cn.contains("FullscreenSubtitle") || cn.contains("AmbientCover")) {
                return;
            }
        } catch (Throwable ignored) {
        }
        count[0]++;
        try {
            if (v.getVisibility() == View.VISIBLE) {
                String tag = tagOf(v);
                boolean thumb = isThumbTag(tag);
                boolean imageLike = isImageLike(v);
                if (thumb || imageLike) {
                    Bitmap b = captureView(v);
                    if (b != null) {
                        considerBitmap(b, thumb, v.getWidth(), v.getHeight(), best);
                    }
                }
            }
        } catch (Throwable ignored) {
        }
        if (v instanceof ViewGroup) {
            ViewGroup g = (ViewGroup) v;
            int n = g.getChildCount();
            for (int i = 0; i < n; i++) {
                walk(g.getChildAt(i), best, depth + 1, count);
            }
        }
    }

    private static boolean isThumbTag(String tag) {
        if (tag == null || tag.isEmpty()) {
            return false;
        }
        String key = tag.toUpperCase().replace('-', '_');
        return key.contains(THUMB_HINT);
    }

    private static boolean isImageLike(View v) {
        if (v instanceof ImageView) {
            return true;
        }
        try {
            String cn = v.getClass().getName();
            return cn.contains("ExpoImage")
                    || cn.contains("ReactImage")
                    || cn.contains("Drawee")
                    || cn.contains("Fresco");
        } catch (Throwable ignored) {
            return false;
        }
    }

    private static Bitmap captureView(View v) {
        // 1) ImageView / getDrawable
        if (v instanceof ImageView) {
            try {
                Drawable d = ((ImageView) v).getDrawable();
                Bitmap b = drawableBitmap(d);
                if (b != null) {
                    return b;
                }
            } catch (Throwable ignored) {
            }
        }
        Bitmap b = reflectDrawableBitmap(v);
        if (b != null) {
            return b;
        }
        b = drawableBitmap(v.getBackground());
        if (b != null) {
            return b;
        }
        // 2) Expo：直接把 View 画到 Bitmap（必须主线程）
        int w = v.getWidth();
        int h = v.getHeight();
        if (w < MIN_SIDE_PX || h < MIN_SIDE_PX) {
            return null;
        }
        // 限宽，避免巨大位图
        int max = 512;
        float scale = 1f;
        if (w > max || h > max) {
            scale = Math.min(max / (float) w, max / (float) h);
        }
        int bw = Math.max(1, Math.round(w * scale));
        int bh = Math.max(1, Math.round(h * scale));
        try {
            Bitmap out = Bitmap.createBitmap(bw, bh, Bitmap.Config.ARGB_8888);
            Canvas c = new Canvas(out);
            if (scale != 1f) {
                c.scale(scale, scale);
            }
            v.draw(c);
            return out;
        } catch (Throwable t) {
            return null;
        }
    }

    private static void considerBitmap(Bitmap src, boolean thumbHint, int w, int h, Holder best) {
        if (src == null || src.isRecycled()) {
            return;
        }
        int side = Math.max(src.getWidth(), src.getHeight());
        if (side < MIN_SIDE_PX && Math.max(w, h) < MIN_SIDE_PX) {
            return;
        }
        // 近似正方形的大图加分（封面）
        float aspect = src.getWidth() / (float) Math.max(1, src.getHeight());
        int score = side;
        if (thumbHint) {
            score += 200_000;
        }
        if (aspect > 0.7f && aspect < 1.4f) {
            score += 5_000;
        }
        score += Math.max(w, h);
        if (score <= best.score) {
            try {
                if (src != best.bmp) {
                    src.recycle();
                }
            } catch (Throwable ignored) {
            }
            return;
        }
        Bitmap copy = safeCopy(src);
        if (src != copy) {
            try {
                src.recycle();
            } catch (Throwable ignored) {
            }
        }
        if (copy == null) {
            return;
        }
        if (best.bmp != null) {
            try {
                best.bmp.recycle();
            } catch (Throwable ignored) {
            }
        }
        best.bmp = copy;
        best.score = score;
        best.thumbHit = thumbHint;
    }

    private static Bitmap safeCopy(Bitmap src) {
        try {
            Bitmap.Config cfg = src.getConfig();
            if (cfg == null || cfg == Bitmap.Config.HARDWARE) {
                cfg = Bitmap.Config.ARGB_8888;
            }
            return src.copy(cfg, false);
        } catch (Throwable t) {
            try {
                return src.copy(Bitmap.Config.ARGB_8888, false);
            } catch (Throwable ignored) {
                return null;
            }
        }
    }

    private static Bitmap drawableBitmap(Drawable d) {
        if (d == null) {
            return null;
        }
        if (d instanceof BitmapDrawable) {
            Bitmap bm = ((BitmapDrawable) d).getBitmap();
            return bm != null ? safeCopy(bm) : null;
        }
        try {
            int w = d.getIntrinsicWidth();
            int h = d.getIntrinsicHeight();
            if (w <= 0 || h <= 0) {
                return null;
            }
            w = Math.min(w, 512);
            h = Math.min(h, 512);
            Bitmap b = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
            Canvas c = new Canvas(b);
            d.setBounds(0, 0, w, h);
            d.draw(c);
            return b;
        } catch (Throwable ignored) {
            return null;
        }
    }

    private static Bitmap reflectDrawableBitmap(View v) {
        try {
            java.lang.reflect.Method m = v.getClass().getMethod("getDrawable");
            Object o = m.invoke(v);
            if (o instanceof Drawable) {
                return drawableBitmap((Drawable) o);
            }
        } catch (Throwable ignored) {
        }
        return null;
    }

    private static String tagOf(View v) {
        try {
            Object raw = v.getTag();
            if (raw instanceof String && ((String) raw).length() > 0) {
                return (String) raw;
            }
        } catch (Throwable ignored) {
        }
        try {
            int rid = v.getResources().getIdentifier(
                    "react_test_id", "id", v.getContext().getPackageName());
            if (rid != 0) {
                Object alt = v.getTag(rid);
                if (alt instanceof String && ((String) alt).length() > 0) {
                    return (String) alt;
                }
            }
        } catch (Throwable ignored) {
        }
        return null;
    }

    private static final class Holder {
        Bitmap bmp;
        int score = -1;
        boolean thumbHit;
    }
}
