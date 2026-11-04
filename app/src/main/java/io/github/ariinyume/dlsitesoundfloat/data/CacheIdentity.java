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
package io.github.ariinyume.dlsitesoundfloat.data;

import java.util.Map;
import java.util.Set;

/**
 * 【code 1048】离线兜底「这份预取字幕属于哪部作品」的**零状态纯判定层**。
 *
 * <h3>── 要解决的问题（Ari 2026-11-04 10:07 报的 bug）──
 * 「缓存到本地的音轨，还是会偶尔挂错缓存到本地的字幕」。
 *
 * <p>真机日志 {@code LSPosed_20261104_100911} 把那条路径完整写下来了：
 * <pre>
 *   10:04:59  seeded playlist identity tc=5 dur=176231ms idx=0
 *   10:05:0x  [code 1042] disk cache SKIPPED: dur=176231ms is not uniquely identifiable
 *   10:07:57  [code 1023] prefetch HIT … dur=1909823ms -> 4ae314….json
 *                       (work=https://play.dl.dlsite.com/…/RJ01552416/optimized)
 *   10:08:5x  Ari 截图：屏上放的是**另一部作品**的台词
 * </pre>
 *
 * <p>根因不是 1042 的闸门坏了，而是<b>两条兜底路径的证据强度不一样，而弱的那条更宽松</b>：
 * <ul>
 *   <li><b>磁盘缓存</b>用强身份键 {@code tc×10^12 + durMs×10^3 + idx}（还记着写入时的作品键）——
 *       但它头上压着 {@code cacheGateAllows} 的「时长歧义」闸门，歧义时被拒；</li>
 *   <li><b>预取池</b>只有毫秒时长这一维（预取时拿不到 {@code tc/idx}）—— 它却还留着
 *       【code 1039】的「受限推断」：<b>只要全池里同一个时长只对应一个作品键，就直接采信</b>。</li>
 * </ul>
 * 于是「磁盘拒绝 → 预取放行」成了必然顺序，而预取的「唯一候选」只是
 * <b>「这个池子里唯一」</b>，不是「用户库里唯一」——池子按 LRU 只留 16 部，
 * 正在听的那部一旦被淘汰，同长的<b>别人家</b>就成了唯一候选。1042 修的正是这条链的前半段，
 * 本轮补后半段。
 *
 * <h3>── 判据：把「唯一」从「池内唯一」升级为「所有本地证据都同意」──</h3>
 * 推断（没有作品键正证据）时，除「候选唯一」外再加两道闸：
 * <ol>
 *   <li><b>磁盘交叉证据</b>：磁盘缓存里同一条时长如果属于<b>别的</b>作品键 ⇒ 说明这个时长
 *       在用户库里确实跨作品重复 ⇒ 拒。磁盘条目是「当初带着 URL 的作品键写下的」，
 *       它对「这个时长有没有别人」这件事，比预取池更接近事实；</li>
 *   <li><b>播放列表指纹</b>：同一个播放列表里，前面已经听过的轨（{@code idx→时长}）是
 *       可以累积的事实。候选包如果对这些时长<b>一个都对不上</b>，那它根本不是这个列表
 *       —— 拒。这一条专治「本作品的包被淘汰、陌生人同长上位」：
 *       本例里 idx=0 的 176231ms 早就记下了，陌生人的包不可能同时握着它。</li>
 * </ol>
 *
 * <p>反过来说：<b>没有正证据、也没有反证据</b>（池里就一个候选、磁盘没别的作品、指纹还没攒到
 * 第二轨）时仍然放行 —— 那正是 1039 要治的「新下载的作品离线播放永远没字幕」，
 * 本轮不动它。
 *
 * <h3>── 纪律 ──</h3>
 * 本类<b>不持有任何状态、不碰文件、不碰 Android</b>（入参全是幂等快照），
 * 判据可进 {@code GoldenVectorTest} 逐条钉死。副作用（读预取池 / 读磁盘索引 / 落日志）
 * 全部留在调用方 {@link SubtitleRepository#tryResumeFromPrefetch}。
 */
public final class CacheIdentity {

    /** 判定结果：取哪个作品键的那份字幕，或不取。 */
    public static final class Decision {
        /** 命中的作品键；{@code null} = 拒（不许取用）。 */
        public final String workKey;
        /** 是否靠「推断」得到（{@code true} = 没有正证据，只靠时长+辅助证据）。 */
        public final boolean inferred;
        /** 给人读的理由（进日志，说明「为什么取 / 为什么拒」）。 */
        public final String reason;

        Decision(String workKey, boolean inferred, String reason) {
            this.workKey = workKey;
            this.inferred = inferred;
            this.reason = reason;
        }

        public boolean hit() {
            return workKey != null;
        }

        @Override
        public String toString() {
            return (workKey == null ? "REFUSE" : (inferred ? "INFER" : "HIT"))
                    + "(" + reason + (workKey == null ? "" : " work=" + workKey) + ")";
        }
    }

    private CacheIdentity() {
    }

    private static Decision refuse(String reason) {
        return new Decision(null, false, reason);
    }

    /**
     * 决定「这一轨的预取字幕能不能取、取哪部作品的」。
     *
     * @param durMs            目标轨时长（毫秒，来自身份键）；{@code <= 0} 直接拒
     * @param workKeyHint      手上的当前作品键（{@code PlaylistKey#workKeyOf} 口径）；
     *                         {@code null}/空 = 没有正证据 ⇒ 走推断
     * @param candidates       预取池里「时长在容差内」的候选：
     *                         {@code 作品键 → 该作品已知的全部轨时长}（含有字幕与明确无字幕的轨）
     * @param diskWorkKeys     磁盘缓存里**同一时长**的条目所属的作品键（可空）
     * @param otherObservedDurs 同一播放列表里**其它**轨已观测到的时长（可空；
     *                         第一轨时为空数组 ⇒ 指纹闸不生效）
     * @return 判定；{@link Decision#hit()} 为假时一律「宁可空白」
     */
    public static Decision decide(long durMs,
                                  String workKeyHint,
                                  Map<String, long[]> candidates,
                                  Set<String> diskWorkKeys,
                                  long[] otherObservedDurs) {
        if (durMs <= 0L) {
            return refuse("时长未知");
        }
        if (candidates == null || candidates.isEmpty()) {
            return refuse("预取池里没有这个时长");
        }
        // ── 有正证据：作品键说话，命中与否都只看它 ──
        if (workKeyHint != null && !workKeyHint.isEmpty()) {
            if (candidates.containsKey(workKeyHint)) {
                return new Decision(workKeyHint, false, "作品键命中");
            }
            return refuse("作品键不在预取池里");
        }
        // ── 没有正证据：只允许「唯一候选 + 无反证据」 ──
        if (candidates.size() >= 2) {
            return refuse("跨作品歧义：" + candidates.size() + " 个候选");
        }
        String only = candidates.keySet().iterator().next();
        if (diskWorkKeys != null) {
            for (String k : diskWorkKeys) {
                if (k != null && !k.isEmpty() && !k.equals(only)) {
                    return refuse("磁盘缓存里同时长属于别的作品：" + k);
                }
            }
        }
        long[] packDurs = candidates.get(only);
        if (otherObservedDurs != null && otherObservedDurs.length > 0) {
            boolean any = false;
            for (long d : otherObservedDurs) {
                if (d <= 0L || packDurs == null) {
                    continue;
                }
                for (long pd : packDurs) {
                    if (Math.abs(pd - d) <= 250L) {
                        any = true;
                        break;
                    }
                }
                if (any) {
                    break;
                }
            }
            if (!any) {
                return refuse("播放列表指纹不吻合（候选包含不下本列表其它轨的时长）");
            }
        }
        return new Decision(only, true, "唯一候选且无反证据");
    }
}
