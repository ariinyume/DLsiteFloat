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

import android.content.Context;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

import io.github.ariinyume.dlsitesoundfloat.util.LogGate;
import io.github.ariinyume.dlsitesoundfloat.util.XposedCompat;

/**
 * 【2.4.0 / code 1007】字幕**磁盘缓存** —— 把在线抓到的字幕 JSON 落盘，断网时按播放身份指纹读回。
 *
 * <h3>── 为什么需要它 ──</h3>
 * 宿主 DLsite Sound 的字幕是**每次播放音轨时在线抓取**的：飞行模式（或不挂代理）下取不到
 * 字幕 JSON，宿主自己也不显示字幕。本类把「已经在线抓到过的轨」的字幕原文持久化到
 * 宿主 App 的私有目录（{@code Android/data/<宿主包名>/files/subtitle_cache/}），
 * 于是同一轨再次播放（哪怕断网）时能直接把本地那份喂回
 * {@link SubtitleRepository#loadFromJsonArrayInternal}。
 *
 * <h3>── 落盘结构 ──</h3>
 * <pre>
 *   subtitle_cache/
 *     index.json          ← 索引（原子写）：每条目一行元数据
 *     &lt;md5&gt;.json          ← 单轨字幕原文（与在线抓到的字节完全一致）
 * </pre>
 * 索引条目字段：{@code identity / selection / workKey / tc / idx / durMs / cues / bytes
 * / hash / maxEnd / file / created / used}。**内存里也留一份**（进程内查询零 I/O），
 * 磁盘只是它的持久化后背。
 *
 * <h3>── 身份口径（写 → 读 的匹配键）──</h3>
 * 主键 = 播放列表身份三元组 {@code (trackCount, durationMs, currentIndex)} 打包值
 * （与 {@code PlayerSourceHook} 的换轨判据**同一口径**，见 {@link PlaylistKey#makeIdentity}）。
 * 副键 = 选择键 {@code (trackCount, currentIndex)}（{@link PlaylistKey#makeSelection}）——
 * 字幕 JSON 往往比「带时长的权威读数」先到，落盘时先按副键挂着，等权威读数到了再补盖时长
 * （{@link #stampDuration}）。**副键只活在「补盖」这一侧；读取一律不用它**
 * 【code 1020】—— 理由见下方防护栈第 ① 条。
 *
 * <h3>── 为什么不会张冠李戴（防护栈）──</h3>
 * <ol>
 *   <li><b>只认强键</b>【code 1020】：查缓存**只认身份键**（曲目数 + 时长毫秒 + 曲目序号
 *       的三元组打包值）—— 毫秒级时长本身就是区分作品的事实。弱的「选择键」
 *       （只有曲目数 + 序号）**曾经**用作身份未知时的兜底，而真机两次兜底命中、
 *       **两次都是别的作品的台词**（2026-10-14 16:18:19 与 17:14:54）⇒ 整条兜底路径已删除；
 *       身份未知（即时长未知）时**放弃命中** —— 宁可屏幕空白，也绝不把来路不明的台词
 *       放上去；</li>
 *   <li><b>时长补盖 + 时间轴交叉校验</b>：条目里记着这份字幕的最大结束时间**和它自己的
 *       时长**，补盖时长时若最大结束时间超出 {@code durMs + 2s}、或它记的时长与身份的
 *       时长对不上 ⇒ 说明这份 JSON 其实不属于这条轨（竞态张冠李戴），拒绝补盖 ——
 *       它此后永远是「无身份的孤儿」，永不命中；</li>
 *   <li><b>内容哈希去重</b>：同一作品下两条目正文哈希相同而序号/时长不同 ⇒ 后者写入时
 *       删掉前者（被误标的那份在正确轨重播时被清掉）；</li>
 *   <li><b>作品键只作取证</b>【code 1020】：命中时若手上有「当前作品键」而它与条目里的
 *       不同，只**打一行日志**、不再拒绝。它曾是唯一的跨作品防线，但真机证明它不可靠 ——
 *       它只在抓到在线 JSON 那一刻刷新，切轨那一刻往往还停在上一个作品，而且离上次刷新
 *       不到三分钟、仍落在「新鲜窗口」内 ⇒ 会否掉**正确**的那一条
 *       （17:17:45 / 17:18:02 / 17:18:34 连续三次）；</li>
 *   <li><b>作品维强约束</b>【code 1024】：身份键只有曲目数 / 毫秒时长 / 序号三维，两部作品
 *       撞上同一个键时，旧实现后写的直接把先写的挤掉（先写的永远取不到、还占字节）。
 *       现在同一身份允许多部作品的条目并存，命中时<b>用作品键认人</b>；认不出来就
 *       <b>放弃命中</b>（宁可屏幕空白，也不放来路不明的台词）。判据见 {@link #pickLocked}。
 *       ⚠️ 与上一条不矛盾：1020 删掉的是「拿过期作品键否决**唯一**候选」（假阴性来源），
 *       本轮加的是「**多条**候选时才用它认人」；</li>
 *   <li><b>全量日志</b>：每次命中/补盖/淘汰都打一行，Ari 可事后抽验。</li>
 * </ol>
 *
 * <h3>── 铁律 ──</h3>
 * <ul>
 *   <li><b>绝不抛回宿主</b>：所有 I/O 异常一律吞掉 + 日志，降级为「本次没缓存」。</li>
 *   <li><b>只在宿主进程初始化</b>：由调用方按进程名判等守卫（设置页 / SystemUI 进程拿到的
 *       不是宿主目录，写了也读不到，见 {@code DlsiteSoundSubtitleModule}）。</li>
 *   <li><b>原子写</b>：索引与单文件都走「临时文件 + rename」（与 {@code ConfigStore.writeJsonAtomic}
 *       同口径），任何时刻读到的都是完整的旧版或新版。</li>
 * </ul>
 */
public final class SubtitleCache {

    private static final String TAG = "[DLsiteSoundFloat:SubtitleCache]";

    /** 缓存容量上限（字节）：默认 256MB（≈1600+ 轨，实测单轨 60–80KB）。 */
    public static final long LIMIT_BYTES_DEF = 256L * 1024 * 1024L;

    /** 缓存目录名（宿主 {@code getExternalFilesDir(null)} 下）。 */
    private static final String DIR_NAME = "subtitle_cache";
    /** 索引文件名。 */
    private static final String INDEX_NAME = "index.json";
    /**
     * 索引 schema（日后结构变更时用它做迁移/丢弃）。
     *
     * <p>⚠️【code 1017】本值一旦推进，旧索引会被**整批丢弃，且盘上那些单轨文件一并清掉**
     * （见 {@link #discardIndexAndSweepLocked()}）—— 加这个版本号等于宣布旧条目的标签
     * 已不可信，别为了「顺手升一版」而改它。
     *
     * <p>【code 1012】1 → 2：code 1007 的落盘轨标签取自「加载 JSON 那一刻」的选择键，
     * 而宿主取字幕的时机早于 {@code currentIndex} 更新 ⇒ 盘上条目的 idx 与 duration 整体错位
     * （真机实证），离线读回就是**别的音轨**的字幕。标签口径已在 {@code SubtitleRepository}
     * 修正，这里把索引版本加一，让已被标错的旧条目整批作废、按正确标签重新积累。
     *
     * <p>【code 1019】2 → 3：code 1013~1018 期间写下的条目里混进了一批**标签张冠李戴**的
     * 副键条目 —— 认领成功时没把目标键写回暂存标签（见 {@code SubtitleRepository} 的
     * {@code tryResumeFromCache}）。真机实证：同一份 13086 字节的字幕被写到
     * {@code tc=4 idx=0} / {@code tc=9 idx=0} / {@code tc=6 idx=0} 三个槽位，
     * 而「按选择键回退命中」会把它当成 {@code tc=9 idx=0} 那一轨的字幕放行（16:18:19 实测）；
     * 补盖时长时被时间轴校验拒绝（{@code maxEnd=383.733s > 208.08s + 2.0s}，一场 416 次）
     * 却**仍然留在副键表里可被命中**，放出来就是别的作品的台词。
     * 写入侧已修（认领即改签）、读取侧已补校验（副键命中同样过时间轴并自愈删除），
     * 这里把已经写歪的旧条目整批作废，让缓存目录从干净状态重新积累。
     *
     * <p>【code 1020】3 → 4：读取路径**不再认副键**（选择键兜底已整条删除，见
     * {@link #bySelection}），于是「什么样的条目才算能命中」的口径整个变了。盘上按旧口径
     * 写下的条目里仍混着跨作品错标的历史脏数据（code 1013~1019 写入侧竞态留痕），
     * 本轮把索引版本加一，让它们整批作废、按新口径重新积累。
     *
     * <p>【code 1024】**刻意维持在 4**：本轮给缓存补上「作品维强约束」（同一身份允许多部
     * 作品的条目并存，命中时用作品键认人），但**条目形态一个字段都没变** ——
     * 索引 JSON 还是那几个键，旧文件照旧能读、照旧能命中。加版本号等于宣布旧条目不可信，
     * 会连带把用户攒下来的整部作品缓存清空一次；本轮没有任何一条理由值这个代价。
     */
    private static final int INDEX_SCHEMA = 4;
    /** 时间轴交叉校验的容差：字幕最大结束时间允许超出时长这么多秒。 */
    private static final double TIMELINE_TOLERANCE_SEC = 2.0;

    private static volatile SubtitleCache sInstance;

    /** 一条缓存轨的元数据。字段名同时是 index.json 的键名。 */
    public static final class Entry {
        /** 身份键（{@link PlaylistKey#makeIdentity}；0 = 时长还没补盖 ⇒ 孤儿，永不命中）。 */
        public long identity;
        /** 选择键（{@link PlaylistKey#makeSelection}）。 */
        public long selection;
        /** 作品键（{@link PlaylistKey#workKeyOf}；null = 这条通道拿不到 URL）。 */
        public String workKey;
        public int tc;
        public int idx;
        public long durMs;
        public int cues;
        public long bytes;
        /** 正文哈希（去重 + 取证）。 */
        public String hash;
        /** 字幕最大结束时间（秒）—— 时长补盖时的时间轴交叉校验用。 */
        public double maxEnd;
        /** 单轨文件名（相对缓存目录）。 */
        public String file;
        public long created;
        /** 最近一次命中时刻（LRU 依据）。 */
        public long used;
    }

    private final Object lock = new Object();
    private Context appCtx;
    private boolean ready;

    /**
     * 【code 1020】强键索引：身份键（{@link PlaylistKey#makeIdentity}，**含毫秒级时长**）
     * → 条目。**刻意不按作品分槽** —— 时长本身就是区分作品的事实，而「作品键」只能在抓到
     * 在线 JSON 时得到：切轨那一刻它要么为空、要么是**上一部作品的陈旧快照**（详见
     * {@link #lookup} 里那段说明）。
     *
     * <p>【code 1024】值从「单条目」改成「条目列表」—— <b>作品维强约束</b>。
     * 身份键只有 (曲目数, 毫秒时长, 序号) 三维：两部作品若同曲目数、同时长、同序号就完全同键。
     * 1023 之前后写的直接 {@code put} 覆盖，先写的那条仍在条目表里占字节、却<b>永远取不到</b>
     * （静默泄漏 + 命中全凭写入顺序）。现在同键允许多条并存，命中时用作品键认人；
     * 认不出来就放弃命中（见 {@link #lookup}）。
     */
    private final Map<Long, List<Entry>> byIdentity = new HashMap<>();
    /**
     * 【code 1020】弱键索引：选择键 → **尚未补盖时长的孤儿**（{@code identity == 0}）。
     *
     * <p>⚠️ 它**不参与读取**：{@link #lookup} 只认身份键。选择键只由
     * {@code (trackCount, idx)} 组成，任何两部作品的同序号音轨都会撞在同一个槽位上 ——
     * 真机实证（2026-10-14 16:18:19 与 17:14:54）两次「按选择键兜底命中」，
     * **两次都是别人的台词**，一次都没对。它现在只承担一件事：给
     * {@link #stampDuration} 找到那条等着补盖时长的条目。
     */
    private final Map<Long, Entry> bySelection = new HashMap<>();
    /**
     * 【code 1020】文件名 → 条目。同一个 {@code (作品, tc, idx)} 必然落到同一个文件名
     * （见 {@link #fileNameFor}），覆盖写之后旧条目必须让位 —— 否则两条目共用一份文件，
     * 删掉其中一条会把另一条也弄成「文件读不出来」。
     *
     * <p>为什么不用选择键找前身：选择键跨作品共用 ⇒ 一部作品写自己的一条轨，会顺手把
     * **另一部作品**那条已经能被强键命中的条目一起摘掉（真机 17:16:55 摘掉之后，
     * 17:17:16 那次换轨的主键查询直接落空）。
     */
    private final Map<String, Entry> byFile = new HashMap<>();
    /** 全部条目（LRU / 统计 / 索引持久化）。 */
    private final List<Entry> entries = new ArrayList<>();
    /** 内容哈希 → 条目（同一作品内的去重）。 */
    private final Map<String, Entry> byHash = new HashMap<>();

    private long limitBytes = LIMIT_BYTES_DEF;
    private long totalBytes;

    /**
     * 【code 1024 / P1-8】本进程启动以来的命中 / 未命中次数。
     *
     * <p>用途只有一个：设置页那行缓存读数里加一段「命中 18/24 轨」，让「缓存到底有没有用」
     * 从猜测变成可读的数字（体检报告 P1-8）。计数走的是 {@link #lookup} 的两个出口，
     * 与 {@code tryResumeFromDisk} 的返回值口径一致；跨进程由既有的缓存统计广播带出去。
     */
    private int hitCount;
    private int missCount;

    private SubtitleCache() {
    }

    public static SubtitleCache get() {
        SubtitleCache s = sInstance;
        if (s == null) {
            synchronized (SubtitleCache.class) {
                s = sInstance;
                if (s == null) {
                    s = new SubtitleCache();
                    sInstance = s;
                }
            }
        }
        return s;
    }

    /**
     * 初始化（幂等）。**只在宿主进程调用** —— 设置页 / SystemUI 进程拿到的文件目录不是宿主的，
     * 写了也读不到，所以调用方必须先按进程名判等（见 {@code DlsiteSoundSubtitleModule}）。
     */
    public void init(Context ctx) {
        if (ready || ctx == null) {
            return;
        }
        synchronized (lock) {
            if (ready) {
                return;
            }
            this.appCtx = ctx.getApplicationContext() != null ? ctx.getApplicationContext() : ctx;
            try {
                File dir = cacheDir();
                if (dir != null && !dir.exists()) {
                    //noinspection ResultOfMethodCallIgnored
                    dir.mkdirs();
                }
                loadIndexLocked();
                // 【code 1017】开机顺手扫一次孤儿：回收历史遗留（例如 code 1012 把
                //   INDEX_SCHEMA 1→2 那一次作废、文件却没删）以及「写完文件、落索引之前
                //   崩溃」留下的半成品。索引正常时白名单覆盖全部条目 ⇒ 一个都不会误删。
                sweepOrphansLocked();
            } catch (Throwable t) {
                log("init failed (degraded to no cache): " + t);
            }
            ready = true;
            log("ready: entries=" + entries.size() + " bytes=" + totalBytes
                    + "/" + limitBytes + " dir=" + dirPath());
        }
    }

    public boolean isReady() {
        return ready;
    }

    /** 当前缓存条目数。 */
    public int count() {
        synchronized (lock) {
            return entries.size();
        }
    }

    /** 当前占用字节数。 */
    public long bytes() {
        synchronized (lock) {
            return totalBytes;
        }
    }

    /** 容量上限（字节）。 */
    public long limitBytes() {
        synchronized (lock) {
            return limitBytes;
        }
    }

    /** 【code 1024 / P1-8】本进程启动以来按强键命中的次数。 */
    public int hitCount() {
        synchronized (lock) {
            return hitCount;
        }
    }

    /** 【code 1024 / P1-8】本进程启动以来没命中的次数（含「有歧义主动放弃」）。 */
    public int missCount() {
        synchronized (lock) {
            return missCount;
        }
    }

    // ==================================================================
    // 写入
    // ==================================================================

    /**
     * 把一份**已经在线抓到的**字幕 JSON 落盘。由 {@code SubtitleRepository} 在
     * {@code loadFromJsonArrayInternal} 成功后调用（异步线程）。
     *
     * @param workKey   这份 JSON 的作品键（{@link PlaylistKey#workKeyOf}；null = 这条加载路径拿不到 URL）
     * @param tc        写入那一刻的 {@code trackCount}（-1 = 未知）
     * @param idx       写入那一刻的 {@code currentIndex}（-1 = 未知）
     * @param durMs     写入那一刻已知的时长（0 = 还没就绪 ⇒ 先当孤儿，等 {@link #stampDuration} 补盖）
     * @param json      字幕 JSON 原文
     * @param cues      解析出的 cue 条数（0 = 未知，仅用于日志/统计）
     * @param maxEndSec 字幕最大结束时间（秒；用于时长补盖的时间轴交叉校验）
     */
    public void put(String workKey, int tc, int idx, long durMs, String json,
                    int cues, double maxEndSec) {
        if (!ready || json == null || json.isEmpty()) {
            return;
        }
        try {
            synchronized (lock) {
                if (tc < 0 || idx < 0) {
                    // 连「哪条轨」都不知道 ⇒ 没有可用的匹配键，不落盘（免得日后误命中）
                    return;
                }
                long selection = PlaylistKey.makeSelection(tc, idx);
                String hash = md5(json);
                String fileName = fileNameFor(workKey, tc, idx);
                byte[] data = json.getBytes(StandardCharsets.UTF_8);
                if (!writeFileAtomic(fileName, data)) {
                    return;
                }

                // 【code 1020】前身按**文件**找，不再按选择键（见 byFile 的注释）。
                Entry prev = byFile.get(fileName);
                long prevBytes = prev != null ? prev.bytes : 0L;
                if (prev != null) {
                    removeEntryLocked(prev, false);   // 同轨重写（自愈：字幕被更新时也覆盖）
                }
                // ③ 内容哈希去重：同一作品下「同样的内容」只留一条 —— 竞态张冠李戴的那份
                //    会在正确轨重播时被这里清掉。
                if (workKey != null) {
                    Entry same = byHash.get(hashKey(workKey, hash));
                    if (same != null && same != prev
                            && (same.idx != idx || same.durMs != durMs)) {
                        log("dedupe: same content under work, removing stale entry "
                                + "(idx=" + same.idx + " dur=" + same.durMs + " -> new idx=" + idx
                                + " dur=" + durMs + ")");
                        removeEntryLocked(same, true);
                    }
                }

                Entry e = new Entry();
                e.workKey = workKey;
                e.tc = tc;
                e.idx = idx;
                e.durMs = durMs > 0 ? durMs : 0L;
                e.cues = cues;
                e.bytes = data.length;
                e.hash = hash;
                e.maxEnd = maxEndSec;
                e.file = fileName;
                e.created = System.currentTimeMillis();
                e.used = e.created;
                e.selection = selection;
                e.identity = e.durMs > 0 ? PlaylistKey.makeIdentity(tc, e.durMs / 1000.0, idx) : 0L;

                // 【code 1020】孤儿槽位一条轨只留一个：被顶掉的那条永远等不到补盖时长
                //   （它已经不在索引里了），留着只是白占字节 —— 一并回收。
                Entry orphanPrev = bySelection.get(selection);
                if (orphanPrev != null && orphanPrev != prev) {
                    removeEntryLocked(orphanPrev, true);
                }
                entries.add(e);
                byFile.put(fileName, e);
                if (e.identity != 0L) {
                    // 【code 1024】同一身份允许多部作品并存（作品维强约束）：
                    //   只摘掉**同作品同身份**的旧条目（那是同一条轨重写），
                    //   别的作品占着同一个身份时让它继续留在桶里，由 lookup 用作品键认人。
                    List<Entry> bucket = byIdentity.get(e.identity);
                    if (bucket == null) {
                        bucket = new ArrayList<>(2);
                        byIdentity.put(e.identity, bucket);
                    } else {
                        for (int i = bucket.size() - 1; i >= 0; i--) {
                            Entry old = bucket.get(i);
                            if (old != prev && sameWork(old, e)) {
                                log("identity SAME WORK collision: replacing old entry"
                                        + " (idx=" + old.idx + " dur=" + old.durMs
                                        + " work=" + shortKey(old.workKey) + ")");
                                removeEntryLocked(old, true);
                            }
                        }
                        bucket = byIdentity.get(e.identity);
                        if (bucket == null) {
                            bucket = new ArrayList<>(2);
                            byIdentity.put(e.identity, bucket);
                        }
                    }
                    bucket.add(e);
                    if (bucket.size() > 1) {
                        log("identity shared by " + bucket.size() + " works ->"
                                + " hits must be disambiguated by work key (identity="
                                + e.identity + ")");
                    }
                } else {
                    bySelection.put(selection, e);   // 只是个待补盖的孤儿，读侧不用它
                }
                if (workKey != null) {
                    byHash.put(hashKey(workKey, hash), e);
                }
                totalBytes += e.bytes - prevBytes;
                enforceLimitLocked();
                persistIndexLocked();
                log("put work=" + shortKey(workKey) + " tc=" + tc + " idx=" + idx
                        + " dur=" + e.durMs + " cues=" + cues + " bytes=" + e.bytes
                        + (e.identity == 0L ? " (stamped later)" : " identity=" + e.identity)
                        + " total=" + totalBytes + "/" + limitBytes);
            }
        } catch (Throwable t) {
            log("put failed (ignored): " + t);
        }
    }

    /**
     * 【时长补盖】权威身份读数到达时（{@code PlayerSourceHook.onPlaylistStateFromStatusMap} →
     * {@code SubtitleRepository.noteObservedPlaylistIdentity}）调用。
     *
     * <p>字幕 JSON 常比「带时长的权威读数」先到（真机实测提前量 165ms~7s），所以落盘时
     * 时长还取不到、条目只能是孤儿；这里把等待中的那条补上身份，它才可能被命中。
     *
     * <p>⚠️ 补盖前做**时间轴交叉校验**：条目里记的字幕最大结束时间若超出
     * {@code durMs + 2s}，说明这份 JSON 其实不属于这条轨（写入时的标签竞态）⇒ 拒绝补盖，
     * 让它永远当孤儿（{@link #put} 的防护栈第 ① 条）。
     */
    public void stampDuration(long identity, long selection) {
        if (!ready || identity == 0L || selection == 0L) {
            return;
        }
        try {
            synchronized (lock) {
                Entry e = bySelection.get(selection);
                if (e == null || e.identity != 0L) {
                    return;
                }
                long durMs = PlaylistKey.identityDurationMs(identity);
                if (durMs <= 0) {
                    return;
                }
                if (!timelineFits(e, identity)) {   // 【code 1019】与 lookup 共用同一把尺子
                    log("stamp REFUSED (timeline mismatch): idx=" + e.idx
                            + " maxEnd=" + e.maxEnd + "s > dur=" + (durMs / 1000.0)
                            + "s + " + TIMELINE_TOLERANCE_SEC + "s -> stays orphan (never matches)");
                    return;
                }
                // 【code 1020】补盖成功 ⇒ 它不再是孤儿：从孤儿槽位摘掉，改挂强键表。
                e.durMs = durMs;
                e.identity = identity;
                bySelection.remove(selection);
                // 【code 1024】作品维强约束：只有**同作品同身份**的旧条目才让位；
                //   别的作品占着同一个身份时让它留在桶里，由 lookup 用作品键认人。
                List<Entry> bucket = byIdentity.get(identity);
                if (bucket != null) {
                    for (int i = bucket.size() - 1; i >= 0; i--) {
                        Entry dup = bucket.get(i);
                        if (dup != e && sameWork(dup, e)) {
                            // 同一身份被**本作品**的另一条占着（只可能来自被改坏的索引）
                            log("stamp: same-work entry already holds identity -> replacing"
                                    + " (idx=" + dup.idx + " dur=" + dup.durMs
                                    + " bytes=" + dup.bytes + ")");
                            removeEntryLocked(dup, false);
                        }
                    }
                    bucket = byIdentity.get(identity);
                }
                if (bucket == null) {
                    bucket = new ArrayList<>(2);
                    byIdentity.put(identity, bucket);
                }
                bucket.add(e);
                persistIndexLocked();
                log("stamp duration: tc=" + e.tc + " idx=" + e.idx + " dur=" + durMs
                        + "ms -> identity=" + identity + " (now matchable)");
            }
        } catch (Throwable t) {
            log("stampDuration failed (ignored): " + t);
        }
    }

    // ==================================================================
    // 读取
    // ==================================================================

    /**
     * 按身份键查缓存，命中返回**字幕 JSON 全文**（未命中返回 {@code null}）。
     *
     * @param identity       本次换轨目标的身份键（0 = 未知）—— 【code 1020】**唯一主判据**；
     *                       为 0（等价于时长未知）时直接放弃命中
     * @param selection      本次换轨目标的选择键（0 = 未知）—— 【code 1020】只进日志，不参与判据
     * @param currentWorkKey 【Phase 3 / URI 通道】手上「当前作品键」（null = 没有）。
     *                       【code 1020】它**不否决单条命中** —— 它只在抓到在线 JSON 那一刻刷新，
     *                       切轨那一刻往往还停在**上一部作品**，而它仍在三分钟新鲜窗口内 ⇒
     *                       拿它否决会否掉正确的那一条（真机连续三次）。
     *                       <p>【code 1024】但它从此有了**一项新职责**：同一身份有多条候选时
     *                       （= 多部作品撞了同一个身份键），它是唯一能认人的证据 ——
     *                       见 {@link #pickLocked}。认不出来就放弃命中。
     */
    public String lookup(long identity, long selection, String currentWorkKey) {
        if (!ready) {
            return null;
        }
        try {
            // 【code 1020】只认强键（身份键，**含毫秒级时长**）。
            //   弱键（选择键）兜底已整条删除 —— 理由见 {@link #bySelection} 的注释
            //   （真机两次副键兜底命中，两次都是别人的台词）。
            //   身份未知（== 0L，等价于「时长未知」）⇒ 按 Ari 定的政策**放弃命中**：
            //   宁可屏幕空白，也绝不把来路不明的台词放上去。
            if (identity == 0L) {
                synchronized (lock) {
                    missCount++;
                }
                return null;
            }
            Entry e;
            synchronized (lock) {
                // 【code 1024】作品维强约束：同一身份可能有多部作品的条目并存。
                List<Entry> bucket = byIdentity.get(identity);
                e = pickLocked(bucket, currentWorkKey, identity, selection);
                if (e != null && !timelineFits(e, identity)) {
                    // 护栏：强键条目在补盖时已经过同一把尺子，正常走不到这里；
                    //   只有索引被外力改坏（手改 index.json / 半截写盘）才可能。
                    log("hit REJECTED (identity, timeline mismatch): idx=" + e.idx
                            + " dur=" + e.durMs + "ms maxEnd=" + e.maxEnd + "s"
                            + " requested dur="
                            + (PlaylistKey.identityDurationMs(identity) / 1000.0) + "s");
                    e = null;
                }
                if (e != null) {
                    e.used = System.currentTimeMillis();
                    hitCount++;
                } else {
                    missCount++;
                }
            }
            if (e == null) {
                return null;
            }
            if (currentWorkKey != null && e.workKey != null
                    && !currentWorkKey.equals(e.workKey)) {
                // 【code 1020】作品键从此**只作取证、不再作否决**。真机 17:17:45 /
                //   17:18:02 / 17:18:34 三次都拿它当否决依据，而被它否掉的恰恰是**正确**
                //   的那一条：切轨那一刻手上那个键还停在上一个作品（这一部作品的字幕 JSON
                //   还没到），可它离上次刷新不到三分钟、仍在「新鲜窗口」内 ⇒ 被判成正证据。
                //   同场的反证在 17:16:03：强键命中后 6ms 到达的 JSON 与条目同属一个作品
                //   ⇒ 含毫秒级时长的身份键本身足以定归属，作品键只是个会过期的快照。
                log("hit ACCEPTED despite work-key mismatch (current work key is a stale"
                        + " snapshot, NOT evidence): entry work=" + shortKey(e.workKey)
                        + " current work=" + shortKey(currentWorkKey)
                        + " identity=" + identity + " selection=" + selection);
            }
            String text = readFile(e.file);
            if (text == null || text.isEmpty()) {
                log("hit but file unreadable -> drop entry file=" + e.file);
                synchronized (lock) {
                    removeEntryLocked(e, true);
                    persistIndexLocked();
                }
                return null;
            }
            log("HIT (identity): tc=" + e.tc + " idx=" + e.idx + " dur=" + e.durMs
                    + "ms cues=" + e.cues + " work=" + shortKey(e.workKey)
                    + " bytes=" + e.bytes + " selection=" + selection);
            synchronized (lock) {
                persistIndexLocked();   // 记下 lastUsed（LRU）
            }
            return text;
        } catch (Throwable t) {
            log("lookup failed (ignored): " + t);
            return null;
        }
    }

    /**
     * 【code 1024】作品维强约束下的**取人逻辑** —— 从「同一身份的所有候选」里挑出唯一那条。
     *
     * <h3>── 为什么同一个身份会有多条候选 ──</h3>
     * 身份键 = {@code (曲目数, 毫秒时长, 序号)}。两部作品只要同曲目数、同时长、同序号，
     * 就是**同一个键** —— 这不是理论风险：系列作、分前后篇的作品、同一作品的不同章节
     * 都极容易出现「三轨、每轨 5 分钟、序号 0」这种撞车。1023 之前后写的直接覆盖，
     * 先写的那条从此永远取不到（还占着字节）；更糟的是「取到的是哪一部」纯看写入顺序。
     *
     * <h3>── 判据（越往下越弱，弱到有歧义就放弃）──</h3>
     * <ol>
     *   <li><b>一条候选</b> ⇒ 就是它（没有歧义，1020 以来的老行为，一个字节都没变）；</li>
     *   <li><b>多条候选 + 作品键能认人</b> ⇒ 取作品键相等的那条（最强证据：宿主自己写在
     *       字幕 JSON 的 URL 里的作品路径）；</li>
     *   <li><b>多条候选 + 作品键认不出来</b>（为 null / 停在上一部作品 / 都对不上）⇒
     *       <b>放弃命中</b>。按 Ari 定的政策：宁可屏幕空白，也绝不把来路不明的台词放上去。</li>
     * </ol>
     *
     * <p>⚠️ 与 1020 的关系：1020 删掉的是「拿**过期**的作品键去否决唯一候选」，
     * 本轮加的是「**多条候选时**用作品键认人、认不出就放弃」。前者是假阴性来源、
     * 后者只在真有歧义时生效 —— 两者不冲突。
     *
     * <p>调用方必须持有 {@link #lock}。
     */
    private Entry pickLocked(List<Entry> bucket, String currentWorkKey,
                             long identity, long selection) {
        if (bucket == null || bucket.isEmpty()) {
            return null;
        }
        if (bucket.size() == 1) {
            return bucket.get(0);
        }
        if (currentWorkKey != null && !currentWorkKey.isEmpty()) {
            for (int i = bucket.size() - 1; i >= 0; i--) {
                Entry e = bucket.get(i);
                if (currentWorkKey.equals(e.workKey)) {
                    log("identity shared by " + bucket.size() + " works -> picked by work key: "
                            + shortKey(e.workKey) + " identity=" + identity
                            + " selection=" + selection);
                    return e;
                }
            }
        }
        // 【code 1024】候选有多条、但**全属同一部作品**（或全都没有作品键）⇒ 不是跨作品撞车，
        //   只是历史写入留下的同槽重复（见 loadIndexLocked 的并条逻辑）。取最近用过的那条，
        //   不要让「自己不干净的历史」变成假 MISS。
        Entry first = bucket.get(0);
        boolean oneWork = true;
        for (Entry e : bucket) {
            if (!sameWork(first, e)) {
                oneWork = false;
                break;
            }
        }
        if (oneWork) {
            Entry best = first;
            for (Entry e : bucket) {
                if (e.used > best.used) {
                    best = e;
                }
            }
            log("identity shared by " + bucket.size() + " entries of the SAME work ->"
                    + " picked most recently used (idx=" + best.idx + " used=" + best.used + ")");
            return best;
        }
        log("hit REFUSED (ambiguous across works): identity=" + identity
                + " has " + bucket.size() + " candidates, work key "
                + (currentWorkKey == null || currentWorkKey.isEmpty()
                        ? "missing" : "mismatched (" + shortKey(currentWorkKey) + ")")
                + " -> blank rather than a wrong line");
        return null;
    }

    /**
     * 【code 1024】两条条目是不是**同一部作品**（决定「同身份覆盖」还是「同身份并存」）。
     *
     * <p>两边都有作品键 ⇒ 比键；<b>都</b>没有作品键（这条通道拿不到 URL，例如数组入口）
     * ⇒ 退回「同轨标签」判等 —— 那种情况下它们只可能是同一条轨的两次写入，覆盖是对的；
     * 一边有一边没有 ⇒ 判「不同作品」（宁可让两条并存，也不能悄悄删掉可能正确的那条）。
     */
    private static boolean sameWork(Entry a, Entry b) {
        if (a == null || b == null) {
            return false;
        }
        boolean an = a.workKey == null || a.workKey.isEmpty();
        boolean bn = b.workKey == null || b.workKey.isEmpty();
        if (an && bn) {
            return a.tc == b.tc && a.idx == b.idx;
        }
        if (an || bn) {
            return false;
        }
        return a.workKey.equals(b.workKey);
    }

    /**
     * 【code 1019】时间轴交叉校验 —— **补盖与读取同一把尺子**（{@link #TIMELINE_TOLERANCE_SEC}）。
     *
     * <p>判据两条：① 条目自己记的时长与本次请求的时长**必须一致**（容差
     * {@link #TIMELINE_TOLERANCE_SEC}）—— 这是真正有区分力的一条【code 1020 新增】；
     * ② 条目的字幕最大结束时间不得超过 {@code durMs + 容差}（code 1019 的尺子）。
     * 第二条在条目没记最大结束时间、或请求没带时长时一律放行 —— 读路径已经不认
     * 「时长未知」的请求（见 {@link #lookup}），这里的宽松只会少一次本该命中的机会，
     * 不会放进错误的条目。
     *
     * <p>纯判定、零状态：不读实例字段、不改任何东西，因此 {@link #stampDuration} 与
     * {@link #lookup} 可以共用同一条判据，不会出现「补盖严、命中松」的裂缝。
     */
    private static boolean timelineFits(Entry e, long identity) {
        if (e == null) {
            return true;
        }
        long durMs = identity != 0L ? PlaylistKey.identityDurationMs(identity) : 0L;
        // 【code 1020】补上真正有区分力的那**反向**：条目自己记的时长与本请求的时长必须
        //   对得上。旧的单向判据只看「字幕最大结束时间 ≤ 时长 + 容差」，天生偏向放行 ——
        //   真机 17:14:54 的伪命中就是「条目 470.136s、请求 975.504s」：
        //   950.677s ≤ 977.5s ⇒ 放行，于是屏上放的是另一条轨的台词。
        if (e.durMs > 0L && durMs > 0L) {
            long tolMs = (long) (TIMELINE_TOLERANCE_SEC * 1000.0);
            if (e.durMs > durMs + tolMs || durMs > e.durMs + tolMs) {
                return false;
            }
        }
        if (e.maxEnd <= 0 || durMs <= 0L) {
            return true;
        }
        return e.maxEnd <= durMs / 1000.0 + TIMELINE_TOLERANCE_SEC;
    }

    /**
     * 这份身份是否**有**可命中的缓存（不读文件、只查内存索引）。
     *
     * <p>【code 1020】口径与 {@link #lookup} 完全一致：**只认身份键**。副键兜底已经删除，
     * 这里再留一条「选择键命中就算有」的分支，就会出现「页面亮着有缓存、真去取却取不到」
     * 的自相矛盾（{@code hasDiskCacheFor} 还拿它决定云端要等多久）。
     * {@code selection} 只为调用点签名稳定而保留。
     *
     * <p>⚠️【code 1024】唯一的例外是**歧义**：同一身份装着多部作品的条目、而作品键又认不出人时，
     * {@link #lookup} 会放弃命中，这里仍返回 true。方向是保守的 —— 这里的 true 只影响
     * 「云端优先等多久」（有本地垫背就只等标准窗），不会让错误的台词上屏。
     */
    public boolean has(long identity, long selection) {
        if (!ready || identity == 0L) {
            return false;
        }
        synchronized (lock) {
            return byIdentity.containsKey(identity);
        }
    }

    /** 清空整个缓存（设置页「清除所有字幕缓存」）。 */
    public void clearAll() {
        synchronized (lock) {
            int n = entries.size();
            long b = totalBytes;
            for (Entry e : new ArrayList<>(entries)) {
                deleteFile(e.file);
            }
            entries.clear();
            byIdentity.clear();
            bySelection.clear();
            byFile.clear();
            byHash.clear();
            totalBytes = 0L;
            persistIndexLocked();
            log("cleared: removed " + n + " entries (" + b + " bytes)");
        }
    }

    // ==================================================================
    // 内部：索引 / LRU / 文件
    // ==================================================================

    private File cacheDir() {
        File base = null;
        try {
            if (appCtx != null) {
                base = appCtx.getExternalFilesDir(null);
            }
        } catch (Throwable ignored) {
        }
        if (base == null) {
            try {
                base = appCtx == null ? null : appCtx.getFilesDir();
            } catch (Throwable ignored) {
            }
        }
        if (base == null) {
            return null;
        }
        File dir = new File(base, DIR_NAME);
        if (!dir.exists()) {
            //noinspection ResultOfMethodCallIgnored
            dir.mkdirs();
        }
        return dir;
    }

    private String dirPath() {
        try {
            File d = cacheDir();
            return d == null ? "(null)" : d.getAbsolutePath();
        } catch (Throwable t) {
            return "(err)";
        }
    }

    /** LRU 淘汰：超过上限就按 {@code used} 由旧到新删，直到降回上限以下。 */
    private void enforceLimitLocked() {
        if (totalBytes <= limitBytes) {
            return;
        }
        List<Entry> sorted = new ArrayList<>(entries);
        Collections.sort(sorted, new Comparator<Entry>() {
            @Override
            public int compare(Entry a, Entry b) {
                return Long.compare(a.used, b.used);
            }
        });
        int evicted = 0;
        for (Entry e : sorted) {
            if (totalBytes <= limitBytes) {
                break;
            }
            evicted++;
            removeEntryLocked(e, true);
        }
        if (evicted > 0) {
            log("LRU evicted " + evicted + " entr(ies) -> now " + totalBytes + "/" + limitBytes
                    + " bytes, entries=" + entries.size());
        }
    }

    /** 从内存索引 + 磁盘移除一条（{@code deleteFile} 决定要不要真删文件）。 */
    private void removeEntryLocked(Entry e, boolean deleteFile) {
        if (e == null) {
            return;
        }
        entries.remove(e);
        if (e.identity != 0L) {
            // 【code 1024】桶里可能还有别的作品的条目 ⇒ 只摘掉这一条，桶空了才删键。
            List<Entry> bucket = byIdentity.get(e.identity);
            if (bucket != null) {
                bucket.remove(e);
                if (bucket.isEmpty()) {
                    byIdentity.remove(e.identity);
                }
            }
        }
        if (bySelection.get(e.selection) == e) {
            bySelection.remove(e.selection);
        }
        if (e.workKey != null && e.hash != null
                && byHash.get(hashKey(e.workKey, e.hash)) == e) {
            byHash.remove(hashKey(e.workKey, e.hash));
        }
        if (e.file != null && byFile.get(e.file) == e) {
            byFile.remove(e.file);
        }
        totalBytes -= e.bytes;
        if (totalBytes < 0) {
            totalBytes = 0;
        }
        if (deleteFile) {
            deleteFile(e.file);
        }
    }

    private void loadIndexLocked() {
        File dir = cacheDir();
        if (dir == null) {
            return;
        }
        File idx = new File(dir, INDEX_NAME);
        if (!idx.exists()) {
            return;
        }
        try {
            String text = readText(new FileInputStream(idx));
            JSONObject root = new JSONObject(text);
            if (root.optInt("schema", 0) != INDEX_SCHEMA) {
                // 【code 1017】旧索引不被认，盘上单轨文件也就**全部失去引用** ——
                //   以前这里只 return，于是那些 .json 成了永久孤儿：占用字节数从 0
                //   重算，而淘汰只按内存里的总数挑人 ⇒ 它们永远选不中，只有「同作品
                //   同轨重新缓存」覆盖写同名文件才会回收，缓存目录只增不减。
                //   现在作废即清扫（1012 把 INDEX_SCHEMA 1→2 那批遗留就是这个形状）。
                log("index schema mismatch (found " + root.optInt("schema", 0)
                        + ", want " + INDEX_SCHEMA + ") -> discard index + sweep orphans");
                discardIndexAndSweepLocked();
                return;
            }
            JSONArray arr = root.optJSONArray("entries");
            if (arr == null) {
                return;
            }
            for (int i = 0; i < arr.length(); i++) {
                JSONObject o = arr.optJSONObject(i);
                if (o == null) {
                    continue;
                }
                Entry e = new Entry();
                e.identity = o.optLong("identity", 0L);
                e.selection = o.optLong("selection", 0L);
                e.workKey = o.optString("workKey", null);
                e.tc = o.optInt("tc", -1);
                e.idx = o.optInt("idx", -1);
                e.durMs = o.optLong("durMs", 0L);
                e.cues = o.optInt("cues", 0);
                e.bytes = o.optLong("bytes", 0L);
                e.hash = o.optString("hash", null);
                e.maxEnd = o.optDouble("maxEnd", 0d);
                e.file = o.optString("file", null);
                e.created = o.optLong("created", 0L);
                e.used = o.optLong("used", e.created);
                if (e.file == null || e.tc < 0 || e.idx < 0) {
                    continue;
                }
                File f = new File(dir, e.file);
                if (!f.exists()) {
                    continue;               // 单文件损坏/丢失 ⇒ 丢条目（按未命中处理）
                }
                if (e.bytes <= 0) {
                    e.bytes = f.length();
                }
                entries.add(e);
                totalBytes += e.bytes;
                if (e.selection == 0L) {
                    e.selection = PlaylistKey.makeSelection(e.tc, e.idx);
                }
                // 【code 1020】按身份分派：有身份的进强键表，没身份的（孤儿）进孤儿槽位。
                if (e.file != null && !byFile.containsKey(e.file)) {
                    byFile.put(e.file, e);
                }
                if (e.identity != 0L) {
                    // 【code 1024】同一身份可能装着多部作品的条目 ⇒ 一律进桶（读侧再认人）。
                    //   但**同作品同身份**的重复条目必须先并掉：1023 及更早的写入侧会按
                    //   byIdentity 直接覆盖（桶里只留最后一条），而 entries 里两条都在 ——
                    //   读回来若不并，桶里就有两条同作品的候选，命中也变成「有歧义」而放弃，
                    //   等于把老用户已经攒下的缓存全部变成假 MISS。
                    //   并的规则：同作品同身份 ⇒ 保留最近用过的（used 大的），另一条丢条目。
                    List<Entry> bucket = byIdentity.get(e.identity);
                    if (bucket == null) {
                        bucket = new ArrayList<>(2);
                        byIdentity.put(e.identity, bucket);
                    } else {
                        Entry dup = null;
                        for (Entry old : bucket) {
                            if (sameWork(old, e)) {
                                dup = old;
                                break;
                            }
                        }
                        if (dup != null) {
                            if (dup.used >= e.used) {
                                log("index: same-work duplicate identity -> keep older-loaded"
                                        + " entry (dropped idx=" + e.idx + " used=" + e.used + ")");
                                entries.remove(e);
                                totalBytes -= e.bytes;
                                continue;
                            }
                            log("index: same-work duplicate identity -> keep newer entry"
                                    + " (dropped idx=" + dup.idx + " used=" + dup.used + ")");
                            entries.remove(dup);
                            totalBytes -= dup.bytes;
                            bucket.remove(dup);
                        }
                    }
                    bucket.add(e);
                } else if (bySelection.get(e.selection) == null) {
                    bySelection.put(e.selection, e);
                }
                if (e.workKey != null && e.hash != null) {
                    byHash.put(hashKey(e.workKey, e.hash), e);
                }
            }
            log("index loaded: " + entries.size() + " entr(ies), " + totalBytes + " bytes");
        } catch (Throwable t) {
            // 索引损坏 ⇒ 重建为空（PRD 口径：读取失败整体回退，不半套生效）
            log("index corrupted -> rebuild as empty: " + t);
            entries.clear();
            byIdentity.clear();
            bySelection.clear();
            byFile.clear();
            byHash.clear();
            totalBytes = 0L;
        }
    }

    /**
     * 【code 1017】索引不可用（结构版本不匹配）时的收尾：清扫孤儿 + 重写一份空索引。
     *
     * <p>顺序与 {@link #clearAll()} 一致（先删文件、再落索引）：万一中途崩溃，残局是
     * 「索引引用着已不存在的文件」，而 {@link #loadIndexLocked()} 对「单文件不存在」
     * 本来就是丢条目不报错 —— 两个中断点都能自愈。
     */
    private void discardIndexAndSweepLocked() {
        int n = sweepOrphansLocked();
        persistIndexLocked();
        log("stale index discarded: swept " + n + " orphan file(s), index reset to schema "
                + INDEX_SCHEMA);
    }

    /**
     * 【code 1017】孤儿清扫：删掉缓存目录里**没有被索引引用**的单轨文件。
     *
     * <p>为什么需要：任何让索引整体作废的情形（结构版本推进、索引损坏后重建）都会把
     * 盘上全部单轨文件变成无主孤儿，而淘汰只按 {@link #totalBytes} 挑人 —— 索引里没有
     * 条目，它一辈子都选不中这些文件，于是缓存目录**只增不减**。
     *
     * <p>安全性：只删扩展名为 {@code .json} 的普通文件，白名单是「当前内存索引引用的
     * 每条 file」加索引文件本身；正在写入的 {@code .tmp} 一律不碰
     * （{@link #writeFileAtomic} 自己收尾）。因此不可能删掉任何可命中的缓存，
     * 最坏情况是把一份孤儿留到下次再删。
     */
    private int sweepOrphansLocked() {
        File dir = cacheDir();
        if (dir == null) {
            return 0;
        }
        File[] list = dir.listFiles();
        if (list == null) {
            return 0;
        }
        Set<String> keep = new HashSet<>();
        keep.add(INDEX_NAME);
        for (Entry e : entries) {
            if (e.file != null) {
                keep.add(e.file);
            }
        }
        int n = 0;
        long freed = 0L;
        for (File f : list) {
            if (f == null || !f.isFile()) {
                continue;
            }
            String name = f.getName();
            if (!name.endsWith(".json") || keep.contains(name)) {
                continue;
            }
            long len = f.length();
            if (f.delete()) {
                n++;
                freed += len;
            }
        }
        if (n > 0) {
            log("orphan sweep: removed " + n + " stale file(s), " + freed + " bytes");
        }
        return n;
    }

    private void persistIndexLocked() {
        try {
            File dir = cacheDir();
            if (dir == null) {
                return;
            }
            JSONObject root = new JSONObject();
            root.put("schema", INDEX_SCHEMA);
            root.put("saved_at", System.currentTimeMillis());
            JSONArray arr = new JSONArray();
            for (Entry e : entries) {
                JSONObject o = new JSONObject();
                o.put("identity", e.identity);
                o.put("selection", e.selection);
                if (e.workKey != null) {
                    o.put("workKey", e.workKey);
                }
                o.put("tc", e.tc);
                o.put("idx", e.idx);
                o.put("durMs", e.durMs);
                o.put("cues", e.cues);
                o.put("bytes", e.bytes);
                if (e.hash != null) {
                    o.put("hash", e.hash);
                }
                o.put("maxEnd", e.maxEnd);
                o.put("file", e.file);
                o.put("created", e.created);
                o.put("used", e.used);
                arr.put(o);
            }
            root.put("entries", arr);
            byte[] data = root.toString().getBytes(StandardCharsets.UTF_8);
            writeFileAtomic(INDEX_NAME, data);
        } catch (Throwable t) {
            log("persistIndex failed (ignored): " + t);
        }
    }

    /** 临时文件 + rename（与 {@code ConfigStore.writeJsonAtomic} 同口径）。 */
    private boolean writeFileAtomic(String name, byte[] data) {
        File dir = cacheDir();
        if (dir == null) {
            return false;
        }
        File target = new File(dir, name);
        File tmp = new File(dir, name + ".tmp");
        try {
            try (FileOutputStream fos = new FileOutputStream(tmp)) {
                fos.write(data);
                fos.flush();
                try {
                    fos.getFD().sync();
                } catch (Throwable ignored) {
                    // 某些 ROM 的 FUSE 上 fsync 会抛；不影响 rename 的原子性
                }
            }
            if (!tmp.renameTo(target)) {
                if (!target.delete() || !tmp.renameTo(target)) {
                    //noinspection ResultOfMethodCallIgnored
                    tmp.delete();
                    return false;
                }
            }
            return true;
        } catch (Throwable t) {
            try {
                //noinspection ResultOfMethodCallIgnored
                tmp.delete();
            } catch (Throwable ignored) {
            }
            return false;
        }
    }

    private String readFile(String name) {
        try {
            File dir = cacheDir();
            if (dir == null || name == null) {
                return null;
            }
            File f = new File(dir, name);
            if (!f.exists()) {
                return null;
            }
            return readText(new FileInputStream(f));
        } catch (Throwable t) {
            return null;
        }
    }

    private void deleteFile(String name) {
        try {
            File dir = cacheDir();
            if (dir == null || name == null) {
                return;
            }
            //noinspection ResultOfMethodCallIgnored
            new File(dir, name).delete();
        } catch (Throwable ignored) {
        }
    }

    private static String readText(InputStream in) throws Exception {
        try (InputStream is = in) {
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = is.read(buf)) > 0) {
                bos.write(buf, 0, n);
            }
            return new String(bos.toByteArray(), StandardCharsets.UTF_8);
        }
    }

    /** 单轨文件名：作品键 + 轨标签的 md5（同作品同轨 ⇒ 同名 ⇒ 覆盖重写即自愈）。 */
    private static String fileNameFor(String workKey, int tc, int idx) {
        String seed = (workKey == null ? "nw" : workKey) + "|" + tc + "|" + idx;
        return md5(seed) + ".json";
    }

    /** 去重键：作品键 + 正文哈希。 */
    private static String hashKey(String workKey, String hash) {
        return workKey + "#" + hash;
    }

    private static String shortKey(String workKey) {
        if (workKey == null) {
            return "(none)";
        }
        // 【code 1019】原先只取**最后一段**，而作品键的末段恒为频道名
        //   （真机 URL 形如 …/work/doujin/RJ01353000/RJ01352276/optimized ⇒ 末段 optimized）
        //   ⇒ 所有作品在日志里都打成同一个词，跨作品对照**根本读不出来**。
        //   改取末两段：optimized 那种形态显出 RJ 号（RJ01352276/optimized），
        //   没有频道段时（ziptree.json 那条路）显出上一级（RJ01353000/RJ01352276）。
        int slash = workKey.lastIndexOf('/');
        if (slash < 0) {
            return workKey;
        }
        int prev = workKey.lastIndexOf('/', slash - 1);
        String tail = workKey.substring(slash + 1);
        String parent = prev >= 0 ? workKey.substring(prev + 1, slash) : null;
        return (parent == null || parent.isEmpty()) ? tail : parent + "/" + tail;
    }

    static String md5(String s) {
        try {
            MessageDigest md = MessageDigest.getInstance("MD5");
            byte[] d = md.digest(s.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(d.length * 2);
            for (byte b : d) {
                sb.append(String.format(Locale.US, "%02x", b));
            }
            return sb.toString();
        } catch (Throwable t) {
            return "x" + Integer.toHexString(s.hashCode());
        }
    }

    private static void log(String msg) {
        XposedCompat.log(TAG + " " + msg);
        LogGate.debug(TAG, msg);
    }
}
