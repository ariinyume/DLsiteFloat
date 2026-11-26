/*
 * DLsiteSound Floating Subtitle - Xposed module for DLsite Sound
 * Copyright (C) 2026 ariinyume
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */
package io.github.ariinyume.dlsitesoundfloat.window;

import android.app.Activity;
import android.content.Context;
import android.os.SystemClock;
import android.view.ViewGroup;
import android.widget.FrameLayout;

import io.github.ariinyume.dlsitesoundfloat.config.RemoteConfig;
import io.github.ariinyume.dlsitesoundfloat.data.SubtitleRepository;
import io.github.ariinyume.dlsitesoundfloat.hook.ActivityButtonHook;
import io.github.ariinyume.dlsitesoundfloat.util.XposedCompat;
import io.github.ariinyume.dlsitesoundfloat.view.FullscreenSubtitleView;

/**
 * 全屏字幕：挂进宿主 Activity decor（非系统 overlay），
 * 以便系统返回/上划桌面/最近任务与宿主同窗缩放。
 */
public class FullscreenSubtitleManager {

    private static final String TAG = "[DLsiteSoundFloat:Fullscreen]";
    private static final long MIN_RETRY_INTERVAL_MS = 400L;

    private static FullscreenSubtitleManager sInstance;

    private Context appContext;
    private FullscreenSubtitleView view;
    private ViewGroup hostDecor;
    private boolean showing = false;
    private long lastFailMs = 0L;
    private final Object lock = new Object();

    public static synchronized FullscreenSubtitleManager getInstance() {
        if (sInstance == null) {
            sInstance = new FullscreenSubtitleManager();
        }
        return sInstance;
    }

    public void sync(Context ctx) {
        if (ctx != null) {
            this.appContext = ctx.getApplicationContext() != null
                    ? ctx.getApplicationContext() : ctx;
        }
        SubtitleRepository repo = SubtitleRepository.getInstance();
        boolean featureOn = false;
        try {
            featureOn = RemoteConfig.get().experimentalEnabled
                    && RemoteConfig.get().fullscreenSubtitleEnabled;
        } catch (Throwable ignored) {
        }
        boolean wantOpen = featureOn && repo.isFullscreenOpen();
        if (wantOpen && repo.shouldShowNoSubtitles()) {
            repo.setFullscreenOpen(false);
            wantOpen = false;
        }
        if (!featureOn && repo.isFullscreenOpen()) {
            repo.setFullscreenOpen(false);
            wantOpen = false;
        }
        // 宿主 Activity 已销毁 ⇒ 强制关
        Activity a = ActivityButtonHook.currentPlayerActivity();
        if (wantOpen && (a == null || a.isFinishing())) {
            repo.setFullscreenOpen(false);
            wantOpen = false;
        }
        final boolean open = wantOpen;
        synchronized (lock) {
            if (open && !showing) {
                show();
            } else if (!open && showing) {
                hide();
            }
            if (showing && view != null) {
                ActivityButtonHook.hideCapsulesForFullscreen();
                view.bringShellToFront();
                view.updateFromRepository();
            }
        }
    }

    private void show() {
        Activity a = ActivityButtonHook.currentPlayerActivity();
        if (a == null || a.isFinishing()) {
            XposedCompat.log(TAG + " show aborted: no activity");
            SubtitleRepository.getInstance().setFullscreenOpen(false);
            return;
        }
        long now = SystemClock.uptimeMillis();
        if (now - lastFailMs < MIN_RETRY_INTERVAL_MS) {
            return;
        }
        try {
            ViewGroup decor = (ViewGroup) a.getWindow().getDecorView();
            // 先采封面再盖层，避免采到自己的氛围 View
            ActivityButtonHook.hideCapsulesForFullscreen();
            view = new FullscreenSubtitleView(a);
            view.prepareCoverBeforeAttach();
            FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.MATCH_PARENT);
            decor.addView(view, lp);
            hostDecor = decor;
            showing = true;
            view.bringShellToFront();
            view.updateFromRepository();
            XposedCompat.log(TAG + " fullscreen shown (decor inject)");
        } catch (Throwable e) {
            lastFailMs = SystemClock.uptimeMillis();
            XposedCompat.log(TAG + " decor addView FAILED: " + e.getMessage());
            showing = false;
            view = null;
            hostDecor = null;
            SubtitleRepository.getInstance().setFullscreenOpen(false);
        }
    }

    private void hide() {
        try {
            if (hostDecor != null && view != null) {
                hostDecor.removeView(view);
            }
        } catch (Throwable ignored) {
        }
        view = null;
        hostDecor = null;
        showing = false;
        XposedCompat.log(TAG + " fullscreen hidden");
    }

    public boolean isShowing() {
        synchronized (lock) {
            return showing;
        }
    }
}
