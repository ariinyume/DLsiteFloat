package io.github.ariinyume.dlsitesoundfloat.hook;

/**
 * 【2.2.14 / code 994】页面跟随的**纯判定层**—— 把「页面是不是被拖住了 / 跟帧循环
 * 是不是已报告静止 / 位移要不要钳制」三组判据从 {@code ActivityButtonHook} 里抠出来。
 *
 * <h3>为什么只抽这三组，而不是整个状态机</h3>
 * 本轮动手前先做了取证（{@code work_diag_993/994-第2批重构-取证报告.md}），结论与
 * 「把 1,048 行状态机整体搬走」的设想相反：
 * <ul>
 *   <li>状态机区间 <b>L1573~L2620</b> 涉及 36 个 {@code s*}静态字段，
 *       其中 <b>34 个在区间外也被读写</b>（L249 / L301 / L344 / L356 / L708 / L716 /
 *       L971 / L1012 / L3653~L3677 —— 结构探针、心跳、宿主 setTranslationY 钩子都在用）。
 *       整体搬走要么造成<b>字段分裂成两份</b>（明确的回归来源），
 *       要么开几十个 getter/setter（比不抽更糟）。</li>
 *   <li>剩下的方法里，只有 {@code isPageHeld} / {@code followReportsStill} 是<b>真纯函数</b>
 *       （只读字段、返回布尔、无副作用），{@code clampFollowOffset} 的<b>钳制算术</b>也是纯的
 *       （只有屏幕高取值那一步碰 View）。</li>
 * </ul>
 * ⇒ 本类只承载<b>可离线验证的判据</b>；全部状态字段与副作用（写字段、打日志、
 * {@code setTranslationY}）一律留在 {@code ActivityButtonHook} 侧。
 *
 * <h3>这一层的价值：五道门的组合逻辑此前无法离线验证</h3>
 * {@code isPageHeld} 的五道门（会话确认 → 位移时间轴 → 快照兜底 → 视觉位移 → 锚点面积）
 * 涉及 5 个阈值常量的组合。此前只能真机试；而 v36 复盘里
 * 「<b>门③读错字段、从来没有生效过</b>」正是这类组合判据的典型事故
 * （当时门①②恰好都能通过，于是门③专门要防的场景原样发生）。
 * 现在可以喂真机实测值离线对照。
 *
 * <h3>口径约定</h3>
 * <ul>
 *   <li><b>不改任何判据的顺序与阈值</b>。原顺序（先②后③、拿不到屏幕尺寸时「宁可维持现状」
 *       返回 true）都是踩坑换来的，逐条照搬，见各方法注释。</li>
 *   <li>「无基线」哨兵统一用 {@link #NO_BASELINE}，
 *       值与 {@code ActivityButtonHook.FOLLOW_NO_BASELINE} 相同（{@code Integer.MIN_VALUE}），
 *       两侧必须一致 —— hook 侧传入的就是那个常量。</li>
 *   <li>本类<b>不持有任何状态</b>，所有状态由入参传入。
 *       这与同轮的 {@code CapsuleGeometry} 是同一个原则：看着像纯函数，抠下去全是状态。</li>
 * </ul>
 *
 * <p>类不实例化。
 */
final class PageFollowPolicy {

    private PageFollowPolicy() {}

    /** 「没有基线」哨兵。与 {@code ActivityButtonHook.FOLLOW_NO_BASELINE} 同值，两侧必须一致。 */
    static final int NO_BASELINE = Integer.MIN_VALUE;

    /**
     * 判定：页面是不是正被用户拖住（因而应当压制 {@code hide}）。
     *
     * <p>五道门（顺序与阈值逐条照搬 {@code ActivityButtonHook.isPageHeld}）：
     * <ol>
     *   <li><b>⓪ 会话闸</b>：本次前台会话还没确认过播放页 → 一律不放行。
     *       意义是「别在用户拖播放页时把按钮藏了」，前提是播放页确实在眼前；
     *       切后台再回前台时屏幕上可能是首页/ 书架，播放页容器只是停靠在屏外
     *       （实测 translateY=2772px），此时按「拖开」处理会让 {@code hide} 被<b>永久压制</b>
     *       —— 按钮就挂在非播放页上不走了（{@code pageVisualOffset()} 的 v43 复盘）。</li>
     *   <li><b>门② 位移时间轴</b>：{@code lastPageMotionMs} 非零且距今不足
     *       {@code pageMotionHoldMs} → 刚动过，放行。</li>
     *   <li><b>门③ 快照兜底</b>：先于门④判断 —— 门④在「拖到极限」时必然失效，
     *       门③正是为那一刻准备的：距 {@code heldOffsetMs} 不足有效期
     *       且 {@code |heldOffset| >= pageHoldPx} 且探测锚点仍挂着。
     *       <p><b>【code 1041】有效期分两档</b>（见 {@link #gate3Window}）：
     *       锚点还有任何可见面积 → {@code holdSnapshotMs}（长窗，保护「手指按住极限位静止」）；
     *       锚点<b>完全不可见</b>（{@code anchorAreaRatio <= 0}）→ {@code holdSnapshotGoneMs}
     *       （短窗）。理由是「关闭动画同样把位移推到满屏且 ref 仍 attached」，
     *       长窗会让按钮在列表页上多挂 2.6 秒。</li>
     *   <li><b>门④ 视觉位移</b>：{@code pageVisualOffset()} 返回哨兵 → 放行；
     *       {@code |held|} 不足 {@code pageHoldPx} → 放行。</li>
     *   <li><b>门⑤ 锚点面积</b>：拿不到屏幕尺寸 → <b>返回 true（宁可维持现状）</b>；
     *       否则按 {@code anchorAreaRatio(screenW, screenH) >= pageHoldMinArea}。</li>
     * </ol>
     *
     * @param playerConfirmedInSession 本次前台会话是否已确认过播放页（门⓪）
     * @param lastPageMotionMs         最近一次「页面在动」的时刻，0 = 从未动过
     * @param heldOffsetMs             最近一次「页面被拖住」的位移快照时刻，0 = 无快照
     * @param heldOffset               该快照的位移量（px）
     * @param holdProbeStillAttached   快照探测的锚点此刻是否仍挂在窗口上（门③）
     * @param pageVisualOffset         无基线通道算出的位移（px），{@link #NO_BASELINE} = 无
     * @param screenW / screenH        屏幕尺寸，&lt;= 0 表示取不到
     * @param anchorAreaRatio          锚点面积占屏比例（门⑤）
     * @param pageMotionHoldMs         门② 阈值 {@code PAGE_MOTION_HOLD_MS}
     * @param holdSnapshotMs           门③ 阈值 {@code HOLD_SNAPSHOT_MS}（锚点仍有可见面积时）
     * @param holdSnapshotGoneMs       门③ 阈值 {@code HOLD_SNAPSHOT_GONE_MS}（锚点完全不可见时）
     * @param pageHoldPx               门③④ 阈值 {@code PAGE_HOLD_PX}
     * @param pageHoldMinArea          门⑤ 阈值 {@code PAGE_HOLD_MIN_AREA}
     * @return true = 页面正被拖住，调用方应压制 {@code hide}
     */
    static boolean isPageHeld(boolean playerConfirmedInSession,
            long lastPageMotionMs, long now,
            long heldOffsetMs, int heldOffset, boolean holdProbeStillAttached,
            int pageVisualOffset,
            int screenW, int screenH, float anchorAreaRatio,
            long pageMotionHoldMs, long holdSnapshotMs,
            long holdSnapshotGoneMs,
            int pageHoldPx, float pageHoldMinArea) {
        // 门⓪：还没确认过播放页 → 一律放行。
        if (!playerConfirmedInSession) {
            return false;
        }
        // 门②：刚动过。
        if (lastPageMotionMs != 0L && now - lastPageMotionMs < pageMotionHoldMs) {
            return true;
        }
        // 门③：快照兜底（**先于门④**，门④在拖到极限时必然失效）。
        if (heldOffsetMs != 0L && now - heldOffsetMs < gate3Window(anchorAreaRatio,
                holdSnapshotMs, holdSnapshotGoneMs)
                && Math.abs(heldOffset) >= pageHoldPx
                && holdProbeStillAttached) {
            return true;
        }
        // 门④：视觉位移。
        if (pageVisualOffset == NO_BASELINE) {
            return false;
        }
        if (Math.abs(pageVisualOffset) < pageHoldPx) {
            return false;
        }
        // 门⑤：锚点面积。拿不到屏幕尺寸 → 宁可维持现状（放行 = 判定为「被拖住」）。
        if (screenW <= 0 || screenH <= 0) {
            return true;
        }
        return anchorAreaRatio >= pageHoldMinArea;
    }

    /**
     * 门③ 快照的**有效窗**：锚点还有任何可见面积 → 长窗；完全不可见 → 短窗。
     *
     * <p>【code 1041】为什么要分档 —— 2026-10-22 真机日志（Ari 11:05:53~11:06:33，
     * 2.4.1 / code 1040）四次关闭播放页，按钮**全部滞后 ≈2.7s 才消失**：
     * <pre>
     *   54.892 verdict=OTHER bottom=y=2661   → 57.668 hide（snap=2771px/2615ms）
     *   00.209 verdict=OTHER bottom=y=2668   → 03.072 hide（snap=2771px/2654ms）
     *   23.067 verdict=OTHER bottom=y=2372   → 25.914 hide（snap=2771px/2633ms）
     *   30.121 全部证据 gone=true            → 32.789 hide（snap=2771px/2679ms）
     * </pre>
     * 四条 hide 的 {@code snap 距现在}都恰好顶在 {@code HOLD_SNAPSHOT_MS=2600} 上，
     * 期间每次都先打一行 {@code hide suppressed: page held}。
     *
     * <p>机制：<b>关闭动画本身</b>（页面 translateY 0→2772）就在往
     * {@code pageVisualOffset()} 写快照 —— 位移每帧变化 ≥ 死区 ⇒ 续期，动画末帧把
     * {@code heldOffset=2771} 钉在「拖到极限」。之后页面静止、不再续期，但 2600ms
     * 的窗要等满；而宿主把栈内播放页**停靠在屏外不 detach**（四次全是
     * {@code attached=true}），所以「ref detach ⇒ 自然放行」这条退路根本不存在。
     *
     * <p>为什么不能直接全局下调 2600：那个值是为「手指按住页面停在极限位**静止**」
     * 留的（注释称实测最长 2.1s 空窗）。这类真实拖动场景下锚点<b>仍有可见面积</b>
     * （实测 30~45%，见 {@code PAGE_HOLD_MIN_AREA}），而关闭完成后是 <b>0%</b>
     * （{@code anchorAreaRatio} 按占屏面积算）—— 两者可以分开，所以只在 0 时缩窗。
     *
     * @param anchorAreaRatio 锚点占屏面积比（&lt;= 0 = 完全不可见）
     * @param holdSnapshotMs  长窗阈值（{@code HOLD_SNAPSHOT_MS}）
     * @param holdSnapshotGoneMs 短窗阈值（{@code HOLD_SNAPSHOT_GONE_MS}）
     */
    static long gate3Window(float anchorAreaRatio, long holdSnapshotMs,
            long holdSnapshotGoneMs) {
        return anchorAreaRatio <= 0f ? holdSnapshotGoneMs : holdSnapshotMs;
    }

    /**
     * 跟帧循环是否<b>报告页面已静止</b>（{@code captureFollowBaseline} 的门①）。
     *
     * <p>v44 以前这道门直接读 {@code !sFollowing}，而循环现在会在页面停手后再
     * <b>热待机 {@code followStillFrames} 帧（≈1s，见那条常量的注释）</b>才注销 ——
     * 若还按「没在跑」判断，基线 / 偏置采集会被推迟 1 秒，跟手反而更晚就绪。
     *
     * <p>语义：循环没在跑 → 当作静止（与老行为一致）；在跑但已连续
     * {@code followStillFrames} 帧读到同一个位移 → 同样是静止。
     * <b>「位移为 0」由调用方另行把关</b>，所以这里只回答「页面还在不在动」。
     */
    static boolean reportsStill(boolean following, int followStill, int followStillFrames) {
        return !following || followStill >= followStillFrames;
    }

    /**
     * 位移安全钳制：把位移限制在屏幕高的 {@code sanityRatio} 倍以内。
     *
     * <p>纯算术。屏幕高<b>取不到（&lt;= 0）时原样放行</b> —— 取不到屏幕尺寸就
     * 不钳制，与 {@code isPageHeld} 门⑤「宁可维持现状」是同一个保守取向。
     *
     * @param delta      待施加的位移（px，可负）
     * @param screenH    屏幕高（px），&lt;= 0 表示取不到
     * @param sanityRatio 比例阈值 {@code FOLLOW_SANITY_RATIO}
     * @return 钳制后的位移
     */
    static int clampOffset(int delta, int screenH, float sanityRatio) {
        if (screenH <= 0) {
            return delta;
        }
        int lim = (int) (screenH * sanityRatio);
        if (delta > lim) {
            return lim;
        }
        if (delta < -lim) {
            return -lim;
        }
        return delta;
    }
}
