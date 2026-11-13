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

    // ── ZiptreePrefetch ────────────────────────────────────────────────

    /** 【code 1049】预取 Referer 同源推导（纯函数）。 */
    public static String prefetchRefererOf(String baseUrl) {
        return ZiptreePrefetch.refererOf(baseUrl);
    }

    // ── GeomSnapshotPolicy / OtherHidePolicy（code 1050 / A1）──────────

    public static boolean acceptSliderCenter(boolean hasMain, int y, boolean stable) {
        return GeomSnapshotPolicy.acceptSliderCenter(hasMain, y, stable);
    }

    public static boolean acceptTimeLabelBottom(boolean sliderAccepted, int timeLabelBottom) {
        return GeomSnapshotPolicy.acceptTimeLabelBottom(sliderAccepted, timeLabelBottom);
    }

    public static boolean acceptSliderRight(boolean hasMain, int x, int w) {
        return GeomSnapshotPolicy.acceptSliderRight(hasMain, x, w);
    }

    public static boolean acceptDescBottom(int descBottom) {
        return GeomSnapshotPolicy.acceptDescBottom(descBottom);
    }

    public static boolean windowMoved(int decorTop, int w, int h,
            int placedTop, int lastW, int lastH) {
        return GeomSnapshotPolicy.windowMoved(decorTop, w, h, placedTop, lastW, lastH);
    }

    public static boolean geoUnchanged(int cy, int desc, int right, int time,
            int pCy, int pDesc, int pRight, int pTime, int deadzone) {
        return GeomSnapshotPolicy.geoUnchanged(cy, desc, right, time,
                pCy, pDesc, pRight, pTime, deadzone);
    }

    public static boolean otherShouldHide(int streak, long sinceMs, long nowMs,
            int needStreak, long needProofMs) {
        return OtherHidePolicy.shouldHide(streak, sinceMs, nowMs, needStreak, needProofMs);
    }

    // ── StatusBarOemHunt（code 1056 / B2）──────────────────────────────

    public static String oemFirstHitAnchor(String[] presentNames) {
        java.util.Set<String> set = new java.util.HashSet<>();
        if (presentNames != null) {
            for (String n : presentNames) {
                set.add(n);
            }
        }
        return StatusBarOemHunt.firstHitAnchorName(StatusBarOemHunt.ANCHOR_IDS, set::contains);
    }

    public static String oemDecideAnchorLabel(String firstHit, String clockDescribe) {
        return StatusBarOemHunt.decideAnchor(firstHit, clockDescribe).hitLabel;
    }

    public static String oemDescribeLabel(int viewId, String[] candidates,
            java.util.Map<String, Integer> nameToId, String className) {
        return StatusBarOemHunt.describeLabel(viewId, candidates,
                n -> nameToId.getOrDefault(n, 0), className);
    }

    public static String oemMissingCompat(String anchorHit, boolean clock, boolean notif,
            boolean seeding) {
        return StatusBarOemHunt.missingCompatCsv(anchorHit, clock, notif, seeding);
    }

    // ── StatusBarIntentRouter（code 1057 / B2）─────────────────────────

    public static String intentKind(String action) {
        return StatusBarIntentRouter.classify(action).name();
    }

    public static boolean intentShouldHideOnEnabled(boolean enabled) {
        return StatusBarIntentRouter.shouldHideOnEnabled(enabled);
    }

    public static Object[] intentParseLine(boolean enabledPresent, boolean enabledExtra,
            boolean prevEnabled, long durationMs, boolean playing, String line) {
        StatusBarIntentRouter.LinePayload p = StatusBarIntentRouter.parseLine(
                enabledPresent, enabledExtra, prevEnabled, durationMs, playing, line);
        return new Object[]{p.enabled, p.durationMs, p.playing, p.line};
    }

    // ── WidthSettlePolicy（code 1058 / B2）─────────────────────────────

    public static boolean widthSkipProbe(boolean force, int proposed, int applied, int hyst) {
        return WidthSettlePolicy.shouldSkipProbe(force, proposed, applied, hyst);
    }

    public static String widthPendingAction(int pending, int applied, int hyst) {
        return WidthSettlePolicy.pendingDecision(pending, applied, hyst).name();
    }

    public static Object[] widthResolveAvail(int left, int right, int limit, int minAvail,
            int fullSentinel) {
        WidthSettlePolicy.Avail a = WidthSettlePolicy.resolveAvail(
                left, right, limit, minAvail, fullSentinel);
        return new Object[]{a.widthPx, a.usedLimit, a.availPx};
    }

    public static int widthUnset() {
        return WidthSettlePolicy.UNSET;
    }

    // ── LineLeftGate（code 940 抽出；1058 补黄金向量）──────────────────

    public static Object[] lineLeftDecide(int real, int right, int acc, int streak, int prev,
            int anchorFallback, int tol, int relockStreak) {
        LineLeftGate.Decision d = LineLeftGate.decide(real, right, acc, streak, prev,
                anchorFallback, tol, relockStreak);
        return new Object[]{d.accepted, d.acc, d.streak, d.prev, d.log};
    }

    // ── CapsuleButtonPolicy（code 1066 / 2.4.5 / A-1）───────────────────

    public static boolean capsuleStatusOn(boolean noSub, boolean appEnabled) {
        return CapsuleButtonPolicy.statusBarButtonOn(noSub, appEnabled);
    }

    public static boolean capsuleStatusVisible(boolean noSub, boolean featureEnabled,
            boolean systemUiAuthorized) {
        return CapsuleButtonPolicy.statusBarButtonVisible(noSub, featureEnabled, systemUiAuthorized);
    }

    public static boolean capsuleFloatOn(boolean noSub, boolean floatingOpen) {
        return CapsuleButtonPolicy.floatingButtonOn(noSub, floatingOpen);
    }

    public static String capsuleVisualSig(String floatText, boolean floatOn, String statusText,
            boolean statusOn, boolean statusVisible, float alpha, boolean liquidGlass, int accent) {
        return CapsuleButtonPolicy.visualSig(floatText, floatOn, statusText, statusOn,
                statusVisible, alpha, liquidGlass, accent);
    }

    // ── FollowBaselinePolicy（code 1066 / A-2）─────────────────────────

    public static boolean followPageQuiet(long lastMs, long now, long hold) {
        return FollowBaselinePolicy.pageQuietEnough(lastMs, now, hold);
    }

    public static boolean followAtRest(boolean seen, int vis, int noBase, int dz) {
        return FollowBaselinePolicy.atLayoutRest(seen, vis, noBase, dz);
    }

    public static boolean followDeferOff(int base, int y, int noBase, int dz, boolean rest) {
        return FollowBaselinePolicy.deferOffBaseline(base, y, noBase, dz, rest);
    }

    public static boolean followCandReset(int cand, int y, int noBase, int dz) {
        return FollowBaselinePolicy.candidateNeedsReset(cand, y, noBase, dz);
    }

    public static boolean followSettle(long candMs, long now, long settle) {
        return FollowBaselinePolicy.settleReady(candMs, now, settle);
    }

    public static boolean followAdoptBias(int offset, int max) {
        return FollowBaselinePolicy.shouldAdoptBias(offset, max);
    }

    public static boolean followHealEligible(int bias, int applied, int offset, int noBase, int dz) {
        return FollowBaselinePolicy.healEligible(bias, applied, offset, noBase, dz);
    }

    public static boolean followStartMotion(long lastMs, long now, long hold) {
        return FollowBaselinePolicy.shouldStartFromRecentMotion(lastMs, now, hold);
    }

    public static boolean followStartDrag(boolean seen, boolean bias, int vis, int noBase, int dz) {
        return FollowBaselinePolicy.shouldStartFromDragged(seen, bias, vis, noBase, dz);
    }

    // ── HeldSnapshot / PlayButtonPick / FollowFrame（code 1066 / A-3）──

    public static boolean heldRenew(int held, int vis, int noBase, int dz) {
        return HeldSnapshotRenewPolicy.shouldRenew(held, vis, noBase, dz);
    }

    public static boolean playBtnSquare(int w, int h, int minPx, float slack) {
        return PlayButtonPickPolicy.isSquareCandidate(w, h, minPx, slack);
    }

    public static int playBtnScore(int locX, int w, int centerX) {
        return PlayButtonPickPolicy.centerScore(locX, w, centerX);
    }

    public static boolean playBtnBeats(int neu, int best) {
        return PlayButtonPickPolicy.beats(neu, best);
    }

    public static boolean followFrameHeld(int delta, int noBase, int dz) {
        return FollowFramePolicy.isHeld(delta, noBase, dz);
    }

    public static long followFrameCap(boolean held, long max, long maxHeld) {
        return FollowFramePolicy.durationCap(held, max, maxHeld);
    }

    public static boolean followFrameTimedOut(long start, long now, long cap) {
        return FollowFramePolicy.timedOut(start, now, cap);
    }

    public static boolean followFrameMissDone(int miss, int max) {
        return FollowFramePolicy.missExhausted(miss, max);
    }

    public static boolean followFrameStopStill(boolean held, int still, int need) {
        return FollowFramePolicy.shouldStopWhenStill(held, still, need);
    }

    // ── StatusBarScrollOrchestrator（code 1065 / B2）───────────────────

    public static String scrollStartAction(boolean hasLine, boolean widthSettled, int targetPx) {
        return StatusBarScrollOrchestrator.decideStart(hasLine, widthSettled, targetPx).name();
    }

    public static String scrollAfterWidth(boolean hasLine, boolean armed) {
        return StatusBarScrollOrchestrator.afterWidthApplied(hasLine, armed).name();
    }

    // ── ScrollFitRecheck（code 1059 / B2）──────────────────────────────

    public static boolean fitSkipPosted(boolean sameView, boolean hasAnimator,
            int liveTarget, int scrollX) {
        return ScrollFitRecheck.shouldSkipPostedFitRecheck(
                sameView, hasAnimator, liveTarget, scrollX);
    }

    public static boolean fitShouldStart(int realTarget, int hysteresisPx) {
        return ScrollFitRecheck.shouldStartAfterFitRecheck(realTarget, hysteresisPx);
    }

    public static String fitAfterEnd(int realTarget, int liveTarget, int scrollX, int slack) {
        return ScrollFitRecheck.afterAnimationEnd(realTarget, liveTarget, scrollX, slack).name();
    }

    public static int fitSettleSlack() {
        return ScrollFitRecheck.SETTLE_SLACK_PX;
    }
}