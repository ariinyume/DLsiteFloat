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
package io.github.ariinyume.dlsitesoundfloat;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import io.github.ariinyume.dlsitesoundfloat.data.CacheIdentity;

import org.junit.Test;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;

/**
 * 【code 1048】离线兜底「这份预取字幕归谁」的判据表。
 *
 * <p>每条用例都对应 {@code CacheIdentity#decide} 的一条出口 —— 判据一旦被谁「顺手放宽」，
 * 这里立刻红。特别是最后两条：<b>唯一候选且无反证据时**仍然要放行**</b>
 * （那是 1039 治过的「新下载的作品离线永远没字幕」，不能为了保守把它掐回来）。
 */
public class CacheIdentityTest {

    /** 【真机向量】RJ01552416 的 1909823ms 轨（Ari 2026-11-04 10:07:57 那次误配）。 */
    private static final long DUR = 1909823L;
    /** 同一播放列表第 1 轨（真机 10:04:59 seeded identity 里的时长）。 */
    private static final long OTHER_IDX0 = 176231L;

    private static Map<String, long[]> one(String key, long... durs) {
        Map<String, long[]> m = new LinkedHashMap<>();
        m.put(key, durs);
        return m;
    }

    private static Set<String> keys(String... ks) {
        Set<String> s = new LinkedHashSet<>();
        Collections.addAll(s, ks);
        return s;
    }

    private static Set<String> none() {
        return Collections.emptySet();
    }

    @Test
    public void workKeyHintWinsWithoutInference() {
        CacheIdentity.Decision d = CacheIdentity.decide(
                DUR, "w:rj01552416", one("w:rj01552416", DUR), none(), new long[0]);
        assertTrue(d.hit());
        assertFalse("有作品键正证据时不算推断", d.inferred);
        assertEquals("w:rj01552416", d.workKey);
    }

    @Test
    public void hintAbsentFromPoolIsRefused() {
        CacheIdentity.Decision d = CacheIdentity.decide(
                DUR, "w:rj09999999", one("w:rj01552416", DUR), none(), new long[0]);
        assertFalse(d.hit());
        assertNull(d.workKey);
    }

    @Test
    public void unknownDurationIsRefused() {
        assertFalse(CacheIdentity.decide(0L, null, one("a", DUR), none(), new long[0]).hit());
        assertFalse(CacheIdentity.decide(-1L, null, one("a", DUR), none(), new long[0]).hit());
    }

    @Test
    public void emptyPoolIsRefused() {
        assertFalse(CacheIdentity.decide(DUR, null, Collections.emptyMap(), none(),
                new long[0]).hit());
    }

    /** 池里两部同长作品 ⇒ 推断不出人 ⇒ 拒（1042 那条闸门的池内版）。 */
    @Test
    public void twoCandidatesAreRefused() {
        Map<String, long[]> m = new LinkedHashMap<>();
        m.put("w:a", new long[]{DUR});
        m.put("w:b", new long[]{DUR});
        assertFalse(CacheIdentity.decide(DUR, null, m, none(), new long[0]).hit());
    }

    /** ★ 本轮根修：磁盘缓存里同一条时长属于**别的**作品 ⇒ 这个时长跨作品重复 ⇒ 拒。 */
    @Test
    public void diskCollisionWithAnotherWorkIsRefused() {
        CacheIdentity.Decision d = CacheIdentity.decide(
                DUR, null, one("w:stranger", DUR),
                keys("w:stranger", "w:mine"), new long[0]);
        assertFalse(d.hit());
        assertTrue(d.reason.contains("磁盘"));
    }

    /** 磁盘里同到时长的作品键与候选一致 ⇒ 不是反证据，放行。 */
    @Test
    public void diskAgreementStillHits() {
        CacheIdentity.Decision d = CacheIdentity.decide(
                DUR, null, one("w:mine", DUR), keys("w:mine"), new long[0]);
        assertTrue(d.hit());
        assertTrue("没有正证据 ⇒ 标成推断", d.inferred);
    }

    /** 磁盘里作品键为空的条目不算证据（它们是上次推断写下的，拿它当证据会自我循环）。 */
    @Test
    public void blankWorkKeyInDiskIsNotEvidence() {
        CacheIdentity.Decision d = CacheIdentity.decide(
                DUR, null, one("w:mine", DUR), keys(""), new long[0]);
        assertTrue(d.hit());
    }

    /** ★ 本轮根修：播放列表指纹对不上 ⇒ 候选包根本不属于这个列表 ⇒ 拒。 */
    @Test
    public void fingerprintMismatchIsRefused() {
        CacheIdentity.Decision d = CacheIdentity.decide(
                DUR, null, one("w:stranger", DUR, 300000L), none(), new long[]{OTHER_IDX0});
        assertFalse(d.hit());
        assertTrue(d.reason.contains("指纹"));
    }

    /** 指纹对得上（包里握有本列表第 1 轨的 176231ms）⇒ 放行。 */
    @Test
    public void fingerprintMatchHits() {
        CacheIdentity.Decision d = CacheIdentity.decide(
                DUR, null, one("w:mine", DUR, OTHER_IDX0), none(), new long[]{OTHER_IDX0});
        assertTrue(d.hit());
        assertEquals("w:mine", d.workKey);
        assertTrue(d.inferred);
    }

    /** 指纹比对的容差与预取池同一把尺子（250ms）。 */
    @Test
    public void fingerprintToleranceIsSameRulerAsPool() {
        assertTrue(CacheIdentity.decide(DUR, null, one("w:mine", DUR, OTHER_IDX0 + 240L),
                none(), new long[]{OTHER_IDX0}).hit());
        assertFalse(CacheIdentity.decide(DUR, null, one("w:mine", DUR, OTHER_IDX0 + 260L),
                none(), new long[]{OTHER_IDX0}).hit());
    }

    /**
     * ★ 不能把 1039 治过的病治回来：第一轨、池里唯一候选、无任何反证据 ⇒ 必须放行。
     * （「新下载的作品离线播放永远没字幕」= 上一版的 P0。）
     */
    @Test
    public void singleCandidateWithoutContraryEvidenceStillHits() {
        CacheIdentity.Decision d = CacheIdentity.decide(
                DUR, null, one("w:only", DUR), none(), new long[0]);
        assertTrue(d.hit());
        assertTrue(d.inferred);
    }
}
