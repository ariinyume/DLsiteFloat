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
package io.github.ariinyume.dlsitesoundfloat.hook;


/**
 * 【code 995】测试访问桥：把 {@code hook} 包的 package-private 判定层暴露给测试。
 *
 * ─────────────────────────────────────────────────────────────────────
 * 为什么需要它
 *
 * {@code PageFollowPolicy} / {@code CapsuleGeometry} / {@code AnchorDeadPolicy}
 * 刻意声明为 package-private —— 它们是 {@code ActivityButtonHook} 的**内部实现**，
 * 不该成为模块对外 API 的一部分（对外暴露的只有 {@code ConfigBus} 等广播面）。
 *
 * 但测试类放在根包 {@code io.github.ariinyume.dlsitesoundfloat}（JUnit 的惯例位置），
 * 就跨包访问不到了。三种解法：
 * <ol>
 *   <li>把三个内核改成 public —— ❌ 扩大了对外 API 表面，破坏原设计意图；</li>
 *   <li>把测试塞进 {@code hook} 包 —— 可行，但会让测试跟着实现搬家，且与
 *       {@code Protocol} 等其他被测类的包结构割裂；</li>
 *   <li><b>本桥类</b> —— 唯一入口、零透传逻辑、只转发调用。✅</li>
 * </ol>
 *
 *⚠️ 铁律：<b>本类只许加方法，不许写任何逻辑。</b>
 *   一旦在这里写了 if/switch，三个内核就重新长出了状态，等于白抽。
 *   每个方法体都应当是单行 return。
 */
public final class TestAccessBridge {

    private TestAccessBridge() {
    }

    // ── PageFollowPolicy ───────────────────────────────────────────────

    public static boolean isPageHeld(boolean playerConfirmedInSession,
            long lastPageMotionMs, long now,
            long heldOffsetMs, int heldOffset, boolean holdProbeStillAttached,
            int pageVisualOffset,
            int screenW, int screenH, float anchorAreaRatio,
            long pageMotionHoldMs, long holdSnapshotMs,
            long holdSnapshotGoneMs,
            int pageHoldPx, float pageHoldMinArea) {
        return PageFollowPolicy.isPageHeld(playerConfirmedInSession, lastPageMotionMs, now,
                heldOffsetMs, heldOffset, holdProbeStillAttached, pageVisualOffset,
                screenW, screenH, anchorAreaRatio, pageMotionHoldMs, holdSnapshotMs,
                holdSnapshotGoneMs, pageHoldPx, pageHoldMinArea);
    }

    /** 【code 1041】门③ 有效窗分档（纯函数）。 */
    public static long gate3Window(float anchorAreaRatio, long holdSnapshotMs,
            long holdSnapshotGoneMs) {
        return PageFollowPolicy.gate3Window(anchorAreaRatio, holdSnapshotMs, holdSnapshotGoneMs);
    }

    public static boolean reportsStill(boolean following, int followStill, int followStillFrames) {
        return PageFollowPolicy.reportsStill(following, followStill, followStillFrames);
    }

    public static int clampOffset(int delta, int screenH, float sanityRatio) {
        return PageFollowPolicy.clampOffset(delta, screenH, sanityRatio);
    }

    // ── CapsuleGeometry ────────────────────────────────────────────────

    public static int clampRight(int wantRight, int screenW, int btnW, int edgePadPx) {
        return CapsuleGeometry.clampRight(wantRight, screenW, btnW, edgePadPx);
    }

    public static int clampBottom(int wantBottom, int screenH, int btnH, int edgePadPx) {
        return CapsuleGeometry.clampBottom(wantBottom, screenH, btnH, edgePadPx);
    }

    /**
     * 【code 1045】「进度条下方」落位（纯函数，宿主 2.22.1 起）。
     *
     * @return bottomMargin（px）；{@code -1} = 输入不可用（内核返回 null）
     */
    public static int belowBottom(int screenH, int sliderCy, int sliderH, int timeLabelBottom,
            int gapPx, int capsuleHPx, int fallbackSeekHalfPx, int edgePadPx) {
        CapsuleGeometry.BottomResult r = CapsuleGeometry.capsuleBottomBelowSlider(
                screenH, sliderCy, sliderH, timeLabelBottom, gapPx, capsuleHPx,
                fallbackSeekHalfPx, edgePadPx);
        return r == null ? -1 : r.bottomMargin;
    }

    /**
     * 【code 1048】「进度条下方」落位 + 窗口原点（decorTop）。
     *
     * @return bottomMargin（px）；{@code -1} = 输入不可用（内核返回 null）
     */
    public static int belowBottomAt(int screenH, int decorTop, int sliderCy, int sliderH,
            int timeLabelBottom, int gapPx, int capsuleHPx, int fallbackSeekHalfPx,
            int edgePadPx) {
        CapsuleGeometry.BottomResult r = CapsuleGeometry.capsuleBottomBelowSlider(
                screenH, decorTop, sliderCy, sliderH, timeLabelBottom, gapPx, capsuleHPx,
                fallbackSeekHalfPx, edgePadPx);
        return r == null ? -1 : r.bottomMargin;
    }

    /** 【code 1048】「滑条上方」落位 + 窗口原点（decorTop）。 */
    public static int aboveBottomAt(int screenH, int decorTop, int sliderCy, int sliderH,
            int descBottomY, int prevDescStable, int gapPx, int capsuleHPx,
            int aboveSliderTopPx, int minClearPx, int descHysteresisPx,
            int fallbackSeekHalfPx, int edgePadPx) {
        CapsuleGeometry.BottomResult r = CapsuleGeometry.capsuleBottomForSlider(
                screenH, decorTop, sliderCy, sliderH, descBottomY, prevDescStable, gapPx,
                capsuleHPx, aboveSliderTopPx, minClearPx, descHysteresisPx,
                fallbackSeekHalfPx, edgePadPx);
        return r == null ? -1 : r.bottomMargin;
    }

    // ── AnchorDeadPolicy ───────────────────────────────────────────────

    public static boolean confirmWindow(
            boolean anchorGone,
            long pageStillMs,
            long goneStillThresholdMs,
            boolean hasFreshEvidence,
            long withEvidenceMs,
            long goneMs,
            long minMs,
            long deadSinceMs,
            long lastOtherSeenMs,
            long lastPageMotionMs) {
        return AnchorDeadPolicy.confirmWindow(anchorGone, pageStillMs, goneStillThresholdMs,
                hasFreshEvidence, withEvidenceMs, goneMs, minMs,
                deadSinceMs, lastOtherSeenMs, lastPageMotionMs) != null;
    }

    public static boolean confirmWindowRaw(
            boolean anchorGone,
            long pageStillMs,
            long goneStillThresholdMs,
            boolean hasFreshEvidence,
            long withEvidenceMs,
            long goneMs,
            long minMs,
            long deadSinceMs,
            long lastOtherSeenMs,
            long lastPageMotionMs) {
        return AnchorDeadPolicy.confirmWindow(anchorGone, pageStillMs, goneStillThresholdMs,
                hasFreshEvidence, withEvidenceMs, goneMs, minMs,
                deadSinceMs, lastOtherSeenMs, lastPageMotionMs) != null;
    }

    /**
     * 把package-private 的 {@code AnchorDeadPolicy.Window} 摊平成可断言的四个字段。
     *
     * <p>本桥同样只做搬运，不做任何换算 —— 避免测试读到的是「桥算出来的值」，
     * 而不是内核真正吐出的值。
     */
    public static final class Win {
        public final long needMs;
        public final long sinceMs;
        public final boolean goneStill;
        public final boolean hasEvidence;

public Win(long needMs, long sinceMs, boolean goneStill, boolean hasEvidence) {
            this.needMs = needMs;
            this.sinceMs = sinceMs;
            this.goneStill = goneStill;
            this.hasEvidence = hasEvidence;
        }
    }

    public static Win window(
            boolean anchorGone,
            long pageStillMs,
            long goneStillThresholdMs,
            boolean hasFreshEvidence,
            long withEvidenceMs,
            long goneMs,
            long minMs,
            long deadSinceMs,
            long lastOtherSeenMs,
            long lastPageMotionMs) {
        AnchorDeadPolicy.Window w = AnchorDeadPolicy.confirmWindow(anchorGone, pageStillMs,
                goneStillThresholdMs, hasFreshEvidence, withEvidenceMs, goneMs, minMs,
                deadSinceMs, lastOtherSeenMs, lastPageMotionMs);
        return w == null ? null : new Win(w.needMs, w.sinceMs, w.goneStill, w.hasEvidence);
    }

    public static boolean shouldHide(long deadFor, long need, int samples,
                              boolean goneStill, int minSamples) {
        return AnchorDeadPolicy.shouldHide(deadFor, need, samples, goneStill, minSamples);
    }

    // ── PokeThrottle（code 997 第 5 批重构）──────────────────────────────

    /** 把 package-private 的 {@code PokeThrottle.Decision} 摊平供断言（同样只搬运、不换算）。 */
    public static final class Poke {
        public final boolean passedMerge;
        public final boolean allow;
        public final long burstStartMs;
        public final long lastEventMs;
        public final long lastPokeMs;
        public final long windowStartMs;
        public final int windowCount;
        public final boolean quietBypass;

        public Poke(boolean passedMerge, boolean allow, long burstStartMs, long lastEventMs,
                    long lastPokeMs, long windowStartMs, int windowCount, boolean quietBypass) {
            this.passedMerge = passedMerge;
            this.allow = allow;
            this.burstStartMs = burstStartMs;
            this.lastEventMs = lastEventMs;
            this.lastPokeMs = lastPokeMs;
            this.windowStartMs = windowStartMs;
            this.windowCount = windowCount;
            this.quietBypass = quietBypass;
        }
    }

    public static Poke poke(long now,
                            long lastEventMs, long burstStartMs, long lastPokeMs,
                            long windowStartMs, int windowCount,
                            long burstGapMs, long quietBypassMs, long minIntervalMs,
                            long windowMs, int maxPerSec) {
        PokeThrottle.Decision d = PokeThrottle.decide(now, lastEventMs, burstStartMs, lastPokeMs,
                windowStartMs, windowCount, burstGapMs, quietBypassMs, minIntervalMs,
                windowMs, maxPerSec);
        return new Poke(d.passedMerge, d.allow, d.burstStartMs, d.lastEventMs,
                d.lastPokeMs, d.windowStartMs, d.windowCount, d.quietBypass);
    }

    // ── HeartbeatPolicy（2026-11-03 零状态内核拆分）──────────────────────

    /** 把 package-private 的 {@code HeartbeatPolicy.Beat} 摊平供断言（只搬运、不换算）。 */
    public static final class Beat {
        public final long nextMs;
        public final int ambiguousRechecks;
        public final boolean forceNextDetect;
        public final int lastVerdict;
        public final int stableStreak;

        public Beat(long nextMs, int ambiguousRechecks, boolean forceNextDetect,
                    int lastVerdict, int stableStreak) {
            this.nextMs = nextMs;
            this.ambiguousRechecks = ambiguousRechecks;
            this.forceNextDetect = forceNextDetect;
            this.lastVerdict = lastVerdict;
            this.stableStreak = stableStreak;
        }
    }

    public static Beat beat(int verdict, boolean ambiguous,
                            int ambiguousRechecks, int maxAmbiguousRechecks,
                            boolean verdictIsPlayer, boolean buttonVisible,
                            int lastVerdict, int stableStreak,
                            long ambiguousRecheckMs, long fastMs, long normalMs,
                            int settleStreak) {
        HeartbeatPolicy.Beat b = HeartbeatPolicy.decide(verdict, ambiguous,
                ambiguousRechecks, maxAmbiguousRechecks,
                verdictIsPlayer, buttonVisible, lastVerdict, stableStreak,
                ambiguousRecheckMs, fastMs, normalMs, settleStreak);
        return new Beat(b.nextMs, b.ambiguousRechecks, b.forceNextDetect,
                b.lastVerdict, b.stableStreak);
    }

    // ── EmptyScanPolicy（2026-11-03 零状态内核拆分）───────────────────────

    public static boolean scanDegenerate(boolean hasMainSlider, boolean hasBottomSlider,
                                         boolean hasAnchor, int wideSliderCount,
                                         int timeTextCount, int descCandidateCount,
                                         boolean hasLiveLines) {
        return EmptyScanPolicy.isDegenerate(hasMainSlider, hasBottomSlider, hasAnchor,
                wideSliderCount, timeTextCount, descCandidateCount, hasLiveLines);
    }

    public static boolean shouldDefer(boolean scanPresent, boolean buttonShown,
                                      boolean degenerate, long lastPlayerSeenMs,
                                      long now, long evidenceTtlMs, boolean alreadyArmed) {
        return EmptyScanPolicy.shouldDefer(scanPresent, buttonShown, degenerate,
                lastPlayerSeenMs, now, evidenceTtlMs, alreadyArmed);
    }

    // ── DensityPolicy（2026-11-03 零状态内核拆分）────────────────────────

    /** 把 package-private 的 {@code DensityPolicy.Result} 摊平供断言（只搬运、不换算）。 */
    public static final class Dens {
        public final float use;
        public final float lockedDensity;
        public final int lockedPxKey;
        public final long diffSinceMs;
        public final int diffCount;
        public final int event;
        public final int samples;

        public Dens(float use, float lockedDensity, int lockedPxKey,
                    long diffSinceMs, int diffCount, int event, int samples) {
            this.use = use;
            this.lockedDensity = lockedDensity;
            this.lockedPxKey = lockedPxKey;
            this.diffSinceMs = diffSinceMs;
            this.diffCount = diffCount;
            this.event = event;
            this.samples = samples;
        }
    }

    public static Dens densityStep(float lockedDensity, int lockedPxKey,
                                   long diffSinceMs, int diffCount,
                                   float d, int pxKey, long now,
                                   long relockMs, int relockSamples) {
        DensityPolicy.Result r = DensityPolicy.step(lockedDensity, lockedPxKey,
                diffSinceMs, diffCount, d, pxKey, now, relockMs, relockSamples);
        return new Dens(r.use, r.lockedDensity, r.lockedPxKey,
                r.diffSinceMs, r.diffCount, r.event, r.samples);
    }

    // ── ScrollPace / ScrollRetarget / ScrollGoal.plan（2026-11-04 拆「量 / 判」）──

    /** 把 package-private 的 {@code ScrollPace.Pace} 摊平供断言。 */
    public static final class Pace {
        public final long durMs;
        public final double speedPxPerMs;

        public Pace(long durMs, double speedPxPerMs) {
            this.durMs = durMs;
            this.speedPxPerMs = speedPxPerMs;
        }
    }

    public static Pace pace(int target, long lineDurMs) {
        ScrollPace.Pace p = ScrollPace.forLine(target, lineDurMs);
        return new Pace(p.durMs, p.speedPxPerMs);
    }

    public static long remainMs(int cur, int target, double speedPxPerMs) {
        return ScrollPace.remainMs(cur, target, speedPxPerMs);
    }

    public static double speedOrFallback(double speedPxPerMs) {
        return ScrollPace.speedOrFallback(speedPxPerMs);
    }

    /** 把 package-private 的 {@code ScrollRetarget.Decision} 摊平供断言；action 用枚举名，避免测试钉序号。 */
    public static final class Retarget {
        public final String action;
        public final int liveTarget;
        public final int seatX;

        public Retarget(String action, int liveTarget, int seatX) {
            this.action = action;
            this.liveTarget = liveTarget;
            this.seatX = seatX;
        }
    }

    public static Retarget retarget(int cur, int liveTarget, int newTarget, boolean armed,
                                    boolean hasAnimator, int hysteresisPx) {
        ScrollRetarget.Decision d = ScrollRetarget.decide(cur, liveTarget, newTarget, armed,
                hasAnimator, hysteresisPx);
        return new Retarget(d.action.name(), d.liveTarget, d.seatX);
    }

    public static int noSeat() {
        return ScrollRetarget.NO_SEAT;
    }

    /** 把 package-private 的 {@code ScrollGoal.Goal} 摊平供断言（只搬运、不换算）。 */
    public static final class Plan {
        public final int target;
        public final boolean layoutRejected;
        public final String measure;
        public final String snapLog;
        public final String nudgeLog;

        public Plan(int target, boolean layoutRejected, String measure,
                    String snapLog, String nudgeLog) {
            this.target = target;
            this.layoutRejected = layoutRejected;
            this.measure = measure;
            this.snapLog = snapLog;
            this.nudgeLog = nudgeLog;
        }
    }

    /**
     * 用「造出来的 Metrics」跑 {@code ScrollGoal.plan} —— 这一步就是拆「量 / 判」的全部意义：
     * 测试不需要 {@code Paint}，只要给一串假的字符边界。
     */
    public static Plan plan(int adv, int ink, int layout, boolean rejected, int rawLayoutW,
                            int[] bounds, int viewW, int tailMargin, int coverMargin,
                            int tolerance, int maxTailClip, int maxNudge) {
        ScrollGoal.Metrics m = new ScrollGoal.Metrics(adv, ink, layout, rejected, rawLayoutW, bounds);
        ScrollGoal.Goal g = ScrollGoal.plan(m, viewW, tailMargin, coverMargin, tolerance,
                maxTailClip, maxNudge);
        return new Plan(g.target, g.layoutRejected, g.measure, g.snapLog, g.nudgeLog);
    }
}