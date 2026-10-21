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
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along with
 * this program. If not, see <https://www.gnu.org/licenses/>.
 */
package io.github.ariinyume.dlsitesoundfloat.hook;

import android.content.Context;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.atomic.AtomicInteger;

import io.github.ariinyume.dlsitesoundfloat.data.PlaylistKey;
import io.github.ariinyume.dlsitesoundfloat.util.AppEnv;
import io.github.ariinyume.dlsitesoundfloat.util.NetState;
import io.github.ariinyume.dlsitesoundfloat.util.LogGate;
import io.github.ariinyume.dlsitesoundfloat.util.XposedCompat;

/**
 * 【code 1023 / P0-4 落地】「下载时同步缓存字幕」—— 从**作品文件树**直接预取整部作品的字幕。
 *
 * <h3>── 为什么以前做不到（1022 的取证结论，现在被证伪了）──
 * 1022 认定「字幕文件名 {@code optimized/<md5>.json} 的 md5 只能靠猜」，所以只敢做取证、
 * 不敢做预取。1023 拿到 5 份真机 ziptree（{@code _rev1022}）后直接推翻了这个前提：
 *
 * <pre>
 *   "playfile": {
 *     "e80970dcebe72a8d125315cba91818e9.wav": {         ← 音频条目
 *        "type": "audio",
 *        "audio": {
 *           "optimized": { "name": "e80970dcebe72a8d125315cba91818e9.mp3",
 *                          "duration": 278.64, ... },
 *           "vtt": "12517693b4ed97aed0aeccf78cbf63fb.vtt"   ← 这一轨的字幕文件
 *        }
 *     },
 *     "12517693b4ed97aed0aeccf78cbf63fb.vtt": {          ← 字幕条目
 *        "type": "vtt",
 *        "vtt": { "optimized": { "name": "12517693b4ed97aed0aeccf78cbf63fb.json",
 *                                "length": 7281, ... } }
 *     }
 *   }
 * </pre>
 *
 * <b>宿主的文件树自己就把「哪条音轨 → 哪个字幕文件」写出来了</b>，一个 md5 都不用算。
 * 三份包实测（RJ01728000 / RJ01735000 / RJ01353000）：
 * {@code audio.vtt} 全命中，{@code vtt.optimized.name} 全部就绪，覆盖 16/10/22 轨。
 *
 * <h3>── 为什么密钥也够用 ──
 * ziptree 请求本身就带 CloudFront 签名：
 * <pre>
 *   https://play.dl.dlsite.com/content/work/doujin/RJ01728000/RJ01727768/ziptree.json
 *       ?Key-Pair-Id=…&amp;Policy=…&amp;Signature=…
 * </pre>
 * 而 {@code Policy} 解出来是<b>作品目录级通配</b>：
 * <pre>
 *   {"Statement":[{"Resource":"https://play.dl.dlsite.com/content/work/doujin/RJ01728000/RJ01727768/*", …}]}
 * </pre>
 * ⇒ 同一份 query 原样拼到 {@code optimized/<name>} 上就是合法请求，无需再申请令牌。
 * 真机日志里那 20 条 {@code optimized/*.json} 与 ziptree 用的是同一个 {@code Key-Pair-Id}。
 *
 * <h3>── 为什么「下载时」一定抓得到 ──
 * 宿主下载/进入作品都要先取 {@code ziptree.json} 才能列出文件（它本身就是下载入口）。
 * 所以只要用户在<b>在线</b>状态打开过或下载过该作品，本类就已经把字幕全抓下来了 ——
 * 不需要等他点「下载」，也不需要额外的用户操作。
 *
 * <h3>── 缓存键怎么办（为什么不在这里直接写 SubtitleCache）──
 * {@code SubtitleCache} 的身份键是 {@code tc×10^12 + durMs×10^3 + idx}，其中
 * {@code trackCount} 是**宿主播放列表**的轨数（RJ01728000 真机 {@code tc=7}），
 * 而 ziptree 里是 20 个音频条目（含子目录/台本）—— 两者口径不同，**推不出来**。
 * 所以本类只负责「把文件抢到本地」，落缓存交给真正知道 {@code tc/idx} 的那一刻：
 * {@code SubtitleRepository#onTrackChanged} 的离线兜底按**毫秒级时长**取用
 * （ziptree 的 {@code duration} 与宿主状态 Map 的 {@code duration} 完全一致，实测
 * 278.64 → 278640ms 全中）。
 *
 * <h3>── 纪律 ──
 * <ul>
 *   <li><b>绝不拖慢主链路</b>：解析在当前（网络）线程，下载全在**单线程**后台队列。</li>
 *   <li><b>离线不发起</b>：{@link NetState#isOffline()} 为真时直接放弃（省电省流量）。</li>
 *   <li><b>有上限</b>：单作品 {@link #MAX_BYTES_PER_WORK}、最多 {@link #MAX_WORKS} 部作品。</li>
 *   <li><b>绝不抛异常</b>：任何一步失败只落一行日志，抓字幕主链路不受影响。</li>
 * </ul>
 */
public final class ZiptreePrefetch {

    private static final String TAG = "[DLsiteSoundFloat:Prefetch]";

    /** 预取根目录（与字幕缓存同根，便于一次性打包/清理）。 */
    private static final String DIR_NAME = "subtitle_cache/_prefetch";

    /**
     * 最多保留几部作品（每部约 30~300KB，16 部也才 1~5MB）。
     *
     * 【code 1029】8 → 16：Ari 2026-10-19 反馈「预存字幕上限改为 16 部作品」。
     * 16 部的代价仍然远小于宿主自己的一部作品音频（单部动辄上百 MB），
     * 换来的是「最近两周常听的十几部作品在离线时都能直接出字幕」。
     * ⚠️ 淘汰口径不变：仍是「按作品目录的最近使用时间保留 {@code MAX_WORKS} 部」（见 {@code size() > MAX_WORKS}），
     *    改数字不需要改任何淘汰逻辑。
     */
    private static final int MAX_WORKS = 16;

    /** 单作品下载上限：字幕是纯文本，正常一部 200KB 以内。 */
    private static final long MAX_BYTES_PER_WORK = 4L * 1024 * 1024;

    /** 单份字幕文件上限（防畸形/超大响应把目录塞满）。 */
    private static final int MAX_FILE_BYTES = 2 * 1024 * 1024;

    /**
     * 时长匹配容差（毫秒）。
     *
     * <p>为什么敢用「时长」当唯一键：宿主状态 Map 报的是 {@code 278.64} 秒 ⇒ {@code 278640} 毫秒，
     * 而 ziptree 里同一轨就是 {@code 278.64} —— 同一个数字的两个副本，误差恒为 0。
     * 容差只用来兜「宿主某次读到 {@code 278.639}」这类浮点抖动，不承担「模糊匹配」职责。
     */
    private static final long DUR_TOLERANCE_MS = 250L;

    /** 一次 {@link #offer} 最多触发几条下载（防某个畸形包卡死队列）。 */
    private static final int MAX_TRACKS_PER_WORK = 256;

    private static final ExecutorService EXEC = Executors.newSingleThreadExecutor(
            new ThreadFactory() {
                private final AtomicInteger seq = new AtomicInteger();

                @Override
                public Thread newThread(Runnable r) {
                    Thread t = new Thread(r, "DLSiteFloat-prefetch-" + seq.incrementAndGet());
                    t.setDaemon(true);
                    return t;
                }
            });

    /** workno → 包（accessOrder=true ⇒ 最近用过的排最后，便于 LRU 淘汰）。 */
    private static final Map<String, Pack> PACKS =
            new LinkedHashMap<String, Pack>(8, 0.75f, true) {
                @Override
                protected boolean removeEldestEntry(Map.Entry<String, Pack> eldest) {
                    return size() > MAX_WORKS;
                }
            };
    private static final Object LOCK = new Object();
    private static volatile boolean sIndexLoaded = false;
    private static volatile boolean sDisabled = false;
    /** 【code 1024】「正文不是完整文件树」只提示一次（否则每次压缩态都刷一行）。 */
    private static boolean sBadBodyLogged = false;

    private ZiptreePrefetch() {
    }

    /** 一条「音轨 → 字幕文件」的映射。 */
    static final class Track {
        final long durMs;
        /** 相对于 {@code optimized/} 的字幕路径（可能含子目录，如 {@code 04_omake/xxx.json}）。 */
        final String jsonName;
        /** 本轨的作品键（{@link PlaylistKey#workKeyOf} 口径，含子目录）。 */
        final String workKey;

        Track(long durMs, String jsonName, String workKey) {
            this.durMs = durMs;
            this.jsonName = jsonName;
            this.workKey = workKey;
        }
    }

    /** 一部作品中「等长但无字幕」的轨，用于防撞。 */
    static final class NoSubtitleTrack {
        final long durMs;
        final String workKey;

        NoSubtitleTrack(long durMs, String workKey) {
            this.durMs = durMs;
            this.workKey = workKey;
        }
    }

    /** 一部作品的预取包。 */
    static final class Pack {
        final String workno;
        /** 目录前缀，**以 / 结尾**，如 {@code https://play.dl.dlsite.com/.../RJ01727768/}。 */
        final String baseUrl;
        /** 原样的 {@code ?Key-Pair-Id=…&Policy=…&Signature=…}（空串 = 没有签名，放弃）。 */
        final String query;
        final File dir;
        final List<Track> tracks = new ArrayList<>();
        /**
         * 【code 1038】本作品中**明确没有字幕**的轨（按作品键分槽）。
         *
         * <p>用途：无字幕轨的时长若与另一条有字幕轨撞车，按作品键命中仍可能张冠李戴。
         * 记下这些轨后，命中前检查「同一作品键下是否同时存在有字幕和无字幕的等长轨」，
         * 有则拒绝，宁可空白也不放错台词。
         */
        final List<NoSubtitleTrack> noSubtitleTracks = new ArrayList<>();

        Pack(String workno, String baseUrl, String query, File dir) {
            this.workno = workno;
            this.baseUrl = baseUrl;
            this.query = query;
            this.dir = dir;
        }

        /** 指定作品键下有没有「等长但无字幕」的轨。 */
        boolean hasNoSubtitle(String workKey, long durMs) {
            for (NoSubtitleTrack n : noSubtitleTracks) {
                if (workKey.equals(n.workKey) && Math.abs(n.durMs - durMs) <= DUR_TOLERANCE_MS) {
                    return true;
                }
            }
            return false;
        }
    }

    /** 一次命中的结果。 */
    public static final class Hit {
        public final String text;
        public final String workKey;
        public final long durMs;
        public final String name;

        Hit(String text, String workKey, long durMs, String name) {
            this.text = text;
            this.workKey = workKey;
            this.durMs = durMs;
            this.name = name;
        }
    }

    // ==================================================================
    // 入口：拦到 ziptree 响应时调用
    // ==================================================================

    /**
     * 拿到一份 {@code ziptree.json} 正文后调用：解析出全轨字幕名并排队下载。
     *
     * <p>必须由<b>已经确认是 ziptree</b> 的响应调用（{@link #isZiptree(String)}），
     * 解析失败时只落下一条日志。
     *
     * @param url  该响应的**完整 URL**（含签名 query）
     * @param text 响应正文
     */
    public static void offer(String url, String text) {
        if (sDisabled || url == null || text == null || text.length() == 0) {
            return;
        }
        try {
            // 【code 1024】正文结构校验：不是「{…"playfile"…}」就不是完整文件树。
            //
            // 🔴 真机实证（1023 的日志）：同一份 ziptree 被读到 4 次，前 3 次是 4143 字节的
            //    **压缩正文**（按文本解出来是一串替换字符），每次都在这里抛 JSONException
            //    并记一条 DEGRADED —— 整部作品能不能预取到，全看「第几次恰好读到解压的那份」。
            //    压缩正文的解压已在网络层补上（见 NetworkHook#maybeGunzip）；这里再加一道
            //    结构校验兜底：**不合格就静默跳过**，不算故障、不进自检表 ——
            //    「还没读到完整的那一份」不是「预取坏了」。
            String body = text.trim();
            if (!body.startsWith("{") || !body.contains("\"playfile\"")) {
                if (!sBadBodyLogged) {
                    sBadBodyLogged = true;
                    XposedCompat.log(TAG + " skip (not a complete ziptree: len=" + body.length()
                            + ", startsWithBrace=" + body.startsWith("{")
                            + ") -> waiting for the inflated copy");
                }
                return;
            }
            if (NetState.isOffline()) {
                // 离线时宿主多半是从它自己的缓存里读的 ziptree，下载必然失败 —— 直接跳过
                XposedCompat.log(TAG + " skip (offline) url=" + url);
                return;
            }
            int q = url.indexOf('?');
            String path = q >= 0 ? url.substring(0, q) : url;
            if (!path.endsWith("/ziptree.json")) {
                return;
            }
            String baseUrl = path.substring(0, path.length() - "ziptree.json".length());
            String query = q >= 0 ? url.substring(q) : "";
            if (query.isEmpty()) {
                XposedCompat.log(TAG + " skip (ziptree has no signature query) path=" + path);
                return;
            }
            String workno = lastSeg(baseUrl);
            if (workno == null) {
                return;
            }

            File dir = new File(baseDir(), workno);
            if (!dir.exists() && !dir.mkdirs()) {
                XposedCompat.log(TAG + " mkdirs failed: " + dir);
                AdapterHealth.degraded(AdapterHealth.Item.PREFETCH, "mkdirs failed");
                return;
            }
            Pack pack = new Pack(workno, baseUrl, query, dir);
            parseTracks(text, pack);
            if (pack.tracks.isEmpty()) {
                // 正常现象：这部作品本来就没有字幕（真机 RJ01654099 就只有 1 条音频、0 条 vtt）
                //
                // 【code 1039】仍然要把这个包留下来：它没有 T 行，但 N 行记着「哪些时长明确无字幕」。
                // 离线取字幕时，这段负证据用来阻止「当前作品无字幕，却命中另一部作品等长轨」。
                writeIndex(pack);
                synchronized (LOCK) {
                    PACKS.put(workno, pack);
                }
                XposedCompat.log(TAG + " " + workno + ": ziptree has no vtt entry (作品无字幕)"
                        + " noSub=" + pack.noSubtitleTracks.size() + " (negative pack kept)");
                // 对用户而言这是「已知事实」而不是故障 ⇒ 记 HIT，别让自检表报红（1023 口径）
                AdapterHealth.hit(AdapterHealth.Item.PREFETCH,
                        workno + ": no vtt in work (作品本来无字幕)");
                return;
            }
            int queued = 0;
            int already = 0;
            long budget = MAX_BYTES_PER_WORK;
            for (Track t : pack.tracks) {
                File f = new File(dir, t.jsonName);
                if (f.exists() && f.length() > 0) {
                    already++;
                    budget -= f.length();
                    continue;
                }
                queued++;
                download(pack, t);
            }
            writeIndex(pack);

            synchronized (LOCK) {
                PACKS.put(workno, pack);
            }
            XposedCompat.log(TAG + " " + workno + ": tracks=" + pack.tracks.size()
                    + " already=" + already + " queued=" + queued
                    + (budget < MAX_BYTES_PER_WORK ? " budget_left=" + budget : "")
                    + " -> " + pack.baseUrl + "optimized");
            AdapterHealth.hit(AdapterHealth.Item.PREFETCH,
                    workno + ": " + pack.tracks.size() + " tracks"
                            + (queued > 0 ? " (+" + queued + " dl)" : " (all cached)"));
        } catch (Throwable e) {
            XposedCompat.log(TAG + " offer failed (ignored): " + e);
            AdapterHealth.degraded(AdapterHealth.Item.PREFETCH, "parse failed: " + e);
        }
    }

    /** 这个 URL 是不是作品文件树（网络层用它决定要不要把正文交给本类）。 */
    public static boolean isZiptree(String urlLower) {
        return urlLower != null && urlLower.contains("ziptree.json");
    }

    // ==================================================================
    // 出口：离线换轨时按毫秒级时长取一份
    // ==================================================================

    /**
     * 按**时长 + 作品键**取一份已预取的字幕。
     *
     * <h3>── 为什么必须加作品维（Ari 的要求：预防「多作品时长撞车」）──</h3>
     * 预取时拿不到宿主的 {@code trackCount}，本类只能用<b>毫秒级时长</b>当键。
     * 1023 的取法是「逆序遍历所有作品，谁先撞上就用谁」—— 手上同时攒了两部以上作品时，
     * 只要它们的某条轨时长相同，就会**随便挑一部**：挑中的正好是本作品是运气，
     * 挑中就别的作品就是「放着别人家的台词」。同一部作品内时长相同的那几条是同一轨的
     * 不同语言版本（取哪份都对），跨作品相同则完全没有这层保证。
     *
     * <p>【code 1038】判据收紧为：
     * <ol>
     *   <li><b>作品键 + 时长双重认人</b>：只有某条轨的 {@link Track#workKey} 与
     *       {@code workKeyHint} 相等、且时长在容差内，才算命中；</li>
     *   <li><b>无字幕轨防撞</b>：同一作品里若存在「等长但无字幕」的轨，说明当前时长
     *       不能唯一确定一条有字幕轨 ⇒ 放弃命中。</li>
     * </ol>
     *
     * <p>【code 1039】没有作品键时允许一次**受限推断**（真机日志：新下载作品已预取，
     * 但本进程还没在线加载过任何字幕 JSON ⇒ {@code freshWorkKey()} 为空 ⇒ 直接 REFUSE，
     * 离线播放永远无字幕）。推断规则：
     * <ul>
     *   <li>所有预取包里，同一时长只对应**一个**作品键 ⇒ 采用它；</li>
     *   <li>只要任一预取包里存在「等长但明确无字幕」的轨 ⇒ 放弃 —— 宁可空白，不放错台词；</li>
     *   <li>推断出的作品键仍要过下面的严格匹配，不会跳过作品维。</li>
     * </ul>
     * 这比 1023 的「任意唯一候选」强一档：1023 在同一时长有多条轨时会随便挑一条；
     * 这里要求**作品键唯一**，且全局无字幕负证据一票否决。
     *
     * @param durMs       目标音轨时长（毫秒，来自身份键）
     * @param workKeyHint 手上的当前作品键（{@link PlaylistKey#workKeyOf} 口径；
     *                    {@code null}/空 = 没有正证据 ⇒ 走受限推断）
     * @return 命中返回正文；没有（或歧义放弃）返回 {@code null}
     */
    public static Hit take(long durMs, String workKeyHint) {
        if (sDisabled || durMs <= 0L) {
            return null;
        }
        try {
            Match m = find(durMs, workKeyHint);
            if (m == null) {
                return null;
            }
            File f = new File(m.pack.dir, m.track.jsonName);
            if (!f.exists() || f.length() <= 0) {
                LogGate.debug(TAG, " MISS dur=" + durMs + "ms work=" + shortKey(m.track.workKey)
                        + " (file not downloaded yet: " + m.track.jsonName + ")");
                return null;
            }
            String txt = readText(f);
            if (txt == null || txt.length() == 0) {
                return null;
            }
            LogGate.debug(TAG, " HIT dur=" + durMs + "ms -> "
                    + m.pack.workno + "/" + m.track.jsonName + " (" + f.length() + " B)"
                    + " work=" + shortKey(m.track.workKey));
            return new Hit(txt, m.track.workKey, m.track.durMs, m.track.jsonName);
        } catch (Throwable e) {
            XposedCompat.log(TAG + " take failed (ignored): " + e);
            return null;
        }
    }

    /**
     * 【code 1040】只判「这一轨现在有没有可用的预取文件」，**不读正文**。
     *
     * <p>用途：换轨时决定「云端优先等多久」。原来只要手上有上一轨 cues 就无条件等
     * {@code NO_SUBTITLE_GRACE_MS_CACHED=15000ms}；预取池明明已经有本轨 JSON 也要等满
     * 15 秒才回退（真机日志：11:46:55.153 换轨 → 11:47:10.155 才 prefetch HIT，差 15.002s）。
     * 本方法只做内存索引 + 文件存在性检查，供仓库把长窗降为标准窗（1s）。
     */
    public static boolean hasCandidate(long durMs, String workKeyHint) {
        if (sDisabled || durMs <= 0L) {
            return false;
        }
        try {
            Match m = find(durMs, workKeyHint);
            if (m == null) {
                return false;
            }
            File f = new File(m.pack.dir, m.track.jsonName);
            return f.exists() && f.length() > 0;
        } catch (Throwable e) {
            return false;
        }
    }

    private static final class Match {
        final Pack pack;
        final Track track;

        Match(Pack pack, Track track) {
            this.pack = pack;
            this.track = track;
        }
    }

    /** 纯匹配层：作品键/时长/负证据都过一遍，不碰文件 IO。 */
    private static Match find(long durMs, String workKeyHint) {
        ensureIndexLoaded();
        List<Pack> snapshot;
        synchronized (LOCK) {
            snapshot = new ArrayList<>(PACKS.values());
        }
        // 【code 1039】全局负证据：任一预取包里存在「等长但明确无字幕」的轨 ⇒
        //   当前时长无法唯一认人。**有作品键也要查**：freshWorkKey 可能是上一部作品的
        //   陈旧值（切到无字幕作品时宿主不会发新 JSON），只查当前作品键会放过跨作品误配。
        if (hasAnyNoSubtitle(snapshot, durMs)) {
            LogGate.debug(TAG, " REFUSE dur=" + durMs + "ms (some prefetched work has"
                    + " unsubtitled track with same duration)");
            return null;
        }
        String hint = workKeyHint;
        if (hint == null || hint.isEmpty()) {
            // 【code 1039】没有作品键：只接受「同一时长在全池里只对应一个作品键」。
            LinkedHashSet<String> keys = new LinkedHashSet<>();
            for (Pack p : snapshot) {
                for (Track t : p.tracks) {
                    if (Math.abs(t.durMs - durMs) <= DUR_TOLERANCE_MS) {
                        keys.add(t.workKey);
                    }
                }
            }
            if (keys.size() != 1) {
                LogGate.debug(TAG, " REFUSE dur=" + durMs + "ms (ambiguous work key: "
                        + keys.size() + " candidates)");
                return null;
            }
            hint = keys.iterator().next();
            LogGate.debug(TAG, " INFER dur=" + durMs + "ms work=" + shortKey(hint)
                    + " (unique work key across " + snapshot.size() + " packs)");
        }
        // 逆序 = 最近 offer/命中的作品优先（accessOrder 的末尾是最新的）
        for (int i = snapshot.size() - 1; i >= 0; i--) {
            Pack p = snapshot.get(i);
            for (Track t : p.tracks) {
                if (!hint.equals(t.workKey)) {
                    continue;
                }
                if (Math.abs(t.durMs - durMs) > DUR_TOLERANCE_MS) {
                    continue;
                }
                return new Match(p, t);
            }
        }
        LogGate.debug(TAG, " MISS dur=" + durMs + "ms work=" + shortKey(hint)
                + " (packs=" + snapshot.size() + ")");
        return null;
    }

    /** 【code 1039】全池负证据：任一作品的「等长但明确无字幕」轨。 */
    private static boolean hasAnyNoSubtitle(List<Pack> packs, long durMs) {
        for (Pack p : packs) {
            for (NoSubtitleTrack n : p.noSubtitleTracks) {
                if (Math.abs(n.durMs - durMs) <= DUR_TOLERANCE_MS) {
                    return true;
                }
            }
        }
        return false;
    }

    /** 【code 1024 / P1-8】已预取几部作品（设置页读数用）。 */
    public static int works() {
        try {
            ensureIndexLoaded();
            synchronized (LOCK) {
                return PACKS.size();
            }
        } catch (Throwable e) {
            return 0;
        }
    }

    /** 【code 1024 / P1-8】已预取多少条轨（设置页读数用）。 */
    public static int tracks() {
        try {
            ensureIndexLoaded();
            int n = 0;
            synchronized (LOCK) {
                for (Pack p : PACKS.values()) {
                    n += p.tracks.size();
                }
            }
            return n;
        } catch (Throwable e) {
            return 0;
        }
    }

    /** 诊断用：现在手上有几部作品、共多少条轨。 */
    public static String summary() {
        try {
            return works() + " works / " + tracks() + " tracks";
        } catch (Throwable e) {
            return "?";
        }
    }

    /**
     * 【code 1030】清空**全部预取**（设置页「清除预取字幕」）。
     *
     * <p>删的是「为换轨提前抓好的作品文件树」：{@code baseDir()} 下每部一个子目录
     * （{@code RJxxxxxx/}）加一份索引（{@code RJxxxxxx.idx}）。**不碰**正文缓存
     * （{@code data.SubtitleCache}）—— 那是另一条链路，Ari 明确要求两者分开清。
     *
     * <p>只删 {@code baseDir()} 的**直接子项**，不递归父目录：预取目录与正文缓存目录
     * 是兄弟关系，越界删除的代价不可逆。
     *
     * <p>删完把 {@code sIndexLoaded} 置回 false：下次 {@link #works()} 会重新扫一遍
     * （此时扫到的是空目录），不必在这里自己维护计数。
     */
    public static void clearAll() {
        try {
            synchronized (LOCK) {
                PACKS.clear();
            }
            File d = baseDir();
            if (d != null && d.isDirectory()) {
                File[] kids = d.listFiles();
                if (kids != null) {
                    for (File f : kids) {
                        deleteRecursively(f);
                    }
                }
            }
            sIndexLoaded = false;
            XposedCompat.log(TAG + " prefetch cleared by settings page");
        } catch (Throwable t) {
            XposedCompat.log(TAG + " clearAll failed: " + t);
        }
    }

    private static void deleteRecursively(File f) {
        if (f == null) {
            return;
        }
        try {
            if (f.isDirectory()) {
                File[] kids = f.listFiles();
                if (kids != null) {
                    for (File k : kids) {
                        deleteRecursively(k);
                    }
                }
            }
            if (!f.delete()) {
                XposedCompat.log(TAG + " delete failed: " + f);
            }
        } catch (Throwable ignored) {
            // 单个文件删不掉不该让整次清理中断
        }
    }

    // ==================================================================
    // 解析
    // ==================================================================

    /**
     * 从 ziptree 里抽出 `[时长, 字幕相对路径, 作品键]`，并记录无字幕轨的时长。
     *
     * <p>只认 {@code type == "audio"} 的条目：
     * <ul>
     *   <li>有 {@code audio.vtt} 且能解析出字幕文件 ⇒ 生成一条 {@link Track}；</li>
     *   <li>没有 vtt 的轨（台本、无字幕轨）⇒ 把时长记入 {@link Pack#noSubtitleDurations}
     *       用于后续防撞。</li>
     * </ul>
     *
     * <p>【code 1038】字幕路径不再直接用 {@code vtt.optimized.name}，而是按宿主自己的算法
     * {@code optimized/ + vttPath.replaceFirst("vtt", "json")} 推导。bonus 轨道常放在子目录
     * （如 {@code 04_omake/xxx.vtt}），{@code vtt.optimized.name} 在部分作品里只给文件名，
     * 按它拼接会得到 {@code optimized/xxx.json} 从而 404。
     */
    private static void parseTracks(String text, Pack pack) throws Exception {
        JSONObject root = new JSONObject(text);
        JSONObject pf = root.optJSONObject("playfile");
        if (pf == null) {
            return;
        }
        Iterator<String> it = pf.keys();
        while (it.hasNext() && pack.tracks.size() < MAX_TRACKS_PER_WORK) {
            String key = it.next();
            JSONObject entry = pf.optJSONObject(key);
            if (entry == null || !"audio".equals(entry.optString("type"))) {
                continue;
            }
            JSONObject audio = entry.optJSONObject("audio");
            if (audio == null) {
                continue;
            }
            JSONObject audioOpt = audio.optJSONObject("optimized");
            double durSec = audioOpt == null ? 0.0 : audioOpt.optDouble("duration", 0.0);
            long durMs = Math.round(durSec * 1000.0);
            if (durMs <= 0L) {
                continue;
            }
            String vttPath = audio.optString("vtt", "");
            if (vttPath.length() == 0) {
                pack.noSubtitleTracks.add(new NoSubtitleTrack(durMs, workKeyOfAudio(pack.baseUrl, key)));
                continue;
            }
            JSONObject vttEntry = pf.optJSONObject(vttPath);
            if (vttEntry == null) {
                pack.noSubtitleTracks.add(new NoSubtitleTrack(durMs, workKeyOfAudio(pack.baseUrl, key)));
                continue;
            }
            JSONObject vtt = vttEntry.optJSONObject("vtt");
            if (vtt == null) {
                pack.noSubtitleTracks.add(new NoSubtitleTrack(durMs, workKeyOfAudio(pack.baseUrl, key)));
                continue;
            }
            // 与宿主行为一致：String.replace 字符串时只替换第一处 "vtt" 为 "json"。
            String jsonName = vttPath.replaceFirst("vtt", "json");
            if (jsonName.length() == 0 || jsonName.equals(vttPath)) {
                pack.noSubtitleTracks.add(new NoSubtitleTrack(durMs, workKeyOfAudio(pack.baseUrl, key)));
                continue;
            }
            String workKey = PlaylistKey.workKeyOf(pack.baseUrl + "optimized/" + jsonName);
            if (workKey == null) {
                workKey = pack.baseUrl + "optimized";
            }
            pack.tracks.add(new Track(durMs, jsonName, workKey));
        }
    }

    // ==================================================================
    // 下载
    // ==================================================================

    private static void download(final Pack pack, final Track t) {
        EXEC.execute(new Runnable() {
            @Override
            public void run() {
                File out = new File(pack.dir, t.jsonName);
                if (out.exists() && out.length() > 0) {
                    return;
                }
                File parent = out.getParentFile();
                if (parent != null && !parent.exists() && !parent.mkdirs()) {
                    XposedCompat.log(TAG + " dl mkdirs failed " + parent);
                    return;
                }
                HttpURLConnection conn = null;
                try {
                    URL u = new URL(pack.baseUrl + "optimized/" + t.jsonName + pack.query);
                    conn = (HttpURLConnection) u.openConnection();
                    conn.setConnectTimeout(10000);
                    conn.setReadTimeout(15000);
                    conn.setRequestProperty("Referer", "https://play.dl.dlsite.com/");
                    int code = conn.getResponseCode();
                    if (code != HttpURLConnection.HTTP_OK) {
                        XposedCompat.log(TAG + " dl fail http=" + code + " " + t.jsonName
                                + " (" + pack.workno + ")");
                        return;
                    }
                    byte[] data = readAll(conn.getInputStream(), MAX_FILE_BYTES);
                    if (data == null || data.length == 0) {
                        XposedCompat.log(TAG + " dl fail empty " + t.jsonName);
                        return;
                    }
                    if (!writeFile(out, data)) {
                        XposedCompat.log(TAG + " dl write failed " + out);
                    }
                } catch (Throwable e) {
                    XposedCompat.log(TAG + " dl error " + t.jsonName + ": " + e);
                } finally {
                    if (conn != null) {
                        conn.disconnect();
                    }
                }
            }
        });
    }

    private static byte[] readAll(InputStream in, int limit) {
        if (in == null) {
            return null;
        }
        try {
            ByteArrayOutputStream bos = new ByteArrayOutputStream(8192);
            byte[] buf = new byte[8192];
            int total = 0;
            int n;
            while ((n = in.read(buf)) > 0) {
                total += n;
                if (total > limit) {
                    return null;   // 超限直接放弃（字幕不可能这么大）
                }
                bos.write(buf, 0, n);
            }
            return bos.toByteArray();
        } catch (Throwable e) {
            return null;
        } finally {
            try {
                in.close();
            } catch (Throwable ignored) {
            }
        }
    }

    // ==================================================================
    // 索引（重启后仍能命中）
    // ==================================================================

    private static File baseDir() {
        Context ctx = AppEnv.app();
        File base = ctx == null ? null : ctx.getExternalFilesDir(null);
        if (base == null && ctx != null) {
            base = ctx.getFilesDir();
        }
        return base == null ? null : new File(base, DIR_NAME);
    }

    private static File indexFile(String workno) {
        File d = baseDir();
        return d == null ? null : new File(d, workno + ".idx");
    }

    /**
     * 索引格式（纯文本，一行一条）：
     * <pre>
     *   Q&lt;TAB&gt;?Key-Pair-Id=…&amp;Policy=…&amp;Signature=…
     *   B&lt;TAB&gt;&lt;baseUrl 以 / 结尾&gt;
     *   N&lt;TAB&gt;&lt;durMs&gt;&lt;TAB&gt;&lt;workKey&gt;  ← 无字幕轨（code 1038 新增）
     *   T&lt;TAB&gt;&lt;durMs&gt;&lt;TAB&gt;&lt;jsonName&gt;&lt;TAB&gt;&lt;workKey&gt;
     * </pre>
     * 不用 JSON：这里只有四种行，文本更好排查，也不受宿主 JSON 实现差异影响。
     *
     * <p>【code 1038】旧索引只有 3 列 T 行（无 workKey），读回时从 baseUrl + jsonName
     * 重新推导 workKey；新索引写 4 列，保证 bonus 子目录场景下作品键正确。
     */
    private static void writeIndex(Pack pack) {
        File f = indexFile(pack.workno);
        if (f == null) {
            return;
        }
        StringBuilder sb = new StringBuilder(256);
        sb.append("Q\t").append(pack.query).append('\n');
        sb.append("B\t").append(pack.baseUrl).append('\n');
        for (NoSubtitleTrack n : pack.noSubtitleTracks) {
            sb.append("N\t").append(n.durMs).append('\t').append(n.workKey).append('\n');
        }
        for (Track t : pack.tracks) {
            sb.append("T\t").append(t.durMs).append('\t')
                    .append(t.jsonName).append('\t')
                    .append(t.workKey).append('\n');
        }
        writeFile(f, sb.toString().getBytes(StandardCharsets.UTF_8));
    }

    private static void ensureIndexLoaded() {
        if (sIndexLoaded) {
            return;
        }
        synchronized (LOCK) {
            if (sIndexLoaded) {
                return;
            }
            sIndexLoaded = true;
            try {
                File d = baseDir();
                if (d == null) {
                    return;
                }
                File[] idx = d.listFiles();
                if (idx == null) {
                    return;
                }
                Arrays.sort(idx, new Comparator<File>() {
                    @Override
                    public int compare(File a, File b) {
                        return Long.compare(a.lastModified(), b.lastModified());
                    }
                });
                for (File f : idx) {
                    if (!f.isFile() || !f.getName().endsWith(".idx")) {
                        continue;
                    }
                    Pack p = readIndex(f);
                    // 【code 1039】无字幕作品也要读回：它没有 tracks，但 N 行是离线取字幕时的
                    //   负证据（阻止「无字幕轨命中另一部作品的等长轨」）。
                    if (p != null && (!p.tracks.isEmpty() || !p.noSubtitleTracks.isEmpty())) {
                        PACKS.put(p.workno, p);
                    }
                }
                XposedCompat.log(TAG + " index loaded: " + PACKS.size() + " works"
                        + " dir=" + d);
            } catch (Throwable e) {
                XposedCompat.log(TAG + " index load failed (ignored): " + e);
            }
        }
    }

    private static Pack readIndex(File f) {
        try {
            String txt = readText(f);
            if (txt == null) {
                return null;
            }
            String workno = f.getName().substring(0, f.getName().length() - 4);
            String query = "";
            String baseUrl = "";
            List<Track> tracks = new ArrayList<>();
            List<NoSubtitleTrack> noSubs = new ArrayList<>();
            for (String line : txt.split("\n")) {
                if (line.length() < 3) {
                    continue;
                }
                char tag = line.charAt(0);
                if (tag == 'Q') {
                    query = line.substring(2);
                } else if (tag == 'B') {
                    baseUrl = line.substring(2);
                } else if (tag == 'N') {
                    String[] parts = line.split("\t");
                    if (parts.length >= 3) {
                        try {
                            noSubs.add(new NoSubtitleTrack(Long.parseLong(parts[1]), parts[2]));
                        } catch (NumberFormatException ignored) {
                        }
                    }
                } else if (tag == 'T') {
                    String[] parts = line.split("\t");
                    if (parts.length >= 3) {
                        long durMs = Long.parseLong(parts[1]);
                        String jsonName = parts[2];
                        String workKey = parts.length >= 4 ? parts[3]
                                : PlaylistKey.workKeyOf(baseUrl + "optimized/" + jsonName);
                        if (workKey == null) {
                            workKey = baseUrl + "optimized";
                        }
                        tracks.add(new Track(durMs, jsonName, workKey));
                    }
                }
            }
            File dir = new File(baseDir(), workno);
            if (baseUrl.length() == 0 || !dir.exists()) {
                return null;
            }
            Pack p = new Pack(workno, baseUrl, query, dir);
            p.tracks.addAll(tracks);
            p.noSubtitleTracks.addAll(noSubs);
            return p;
        } catch (Throwable e) {
            return null;
        }
    }

    // ==================================================================
    // IO 小工具
    // ==================================================================

    private static String readText(File f) {
        FileInputStream in = null;
        try {
            in = new FileInputStream(f);
            ByteArrayOutputStream bos = new ByteArrayOutputStream((int) Math.max(64, f.length()));
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) {
                bos.write(buf, 0, n);
            }
            return new String(bos.toByteArray(), StandardCharsets.UTF_8);
        } catch (Throwable e) {
            return null;
        } finally {
            if (in != null) {
                try {
                    in.close();
                } catch (Throwable ignored) {
                }
            }
        }
    }

    private static boolean writeFile(File f, byte[] data) {
        FileOutputStream out = null;
        try {
            out = new FileOutputStream(f);
            out.write(data);
            return true;
        } catch (Throwable e) {
            return false;
        } finally {
            if (out != null) {
                try {
                    out.close();
                } catch (Throwable ignored) {
                }
            }
        }
    }

    /** 作品键日志简写：取末两段，避免满屏 URL。 */
    private static String shortKey(String workKey) {
        if (workKey == null) {
            return "(none)";
        }
        int slash = workKey.lastIndexOf('/');
        if (slash < 0) {
            return workKey;
        }
        int prev = workKey.lastIndexOf('/', slash - 1);
        String tail = workKey.substring(slash + 1);
        String parent = prev >= 0 ? workKey.substring(prev + 1, slash) : null;
        return (parent == null || parent.isEmpty()) ? tail : parent + "/" + tail;
    }

    /**
     * 由音频文件在 playfile 里的 key 推断「如果这条轨有字幕，它的作品键会是什么」。
     *
     * <p>宿主请求字幕的算法是 {@code optimized/ + vttPath.replaceFirst("vtt","json")}，
     * 而 vtt 文件通常与音频文件在同一子目录。{@code audioKey} 形如 {@code 04_omake/track.wav}
     * 或 {@code track.wav}，这里取它的目录部分拼到 {@code optimized/} 下，再算出作品键。
     */
    private static String workKeyOfAudio(String baseUrl, String audioKey) {
        if (audioKey == null) {
            audioKey = "";
        }
        String dir = "";
        int slash = audioKey.lastIndexOf('/');
        if (slash >= 0) {
            dir = audioKey.substring(0, slash);
        }
        String dummy = baseUrl + "optimized" + (dir.isEmpty() ? "" : "/" + dir) + "/x.json";
        String k = PlaylistKey.workKeyOf(dummy);
        return k != null ? k : baseUrl + "optimized";
    }

    /** URL 路径的最后一段（去掉尾部 {@code /}）。 */
    private static String lastSeg(String path) {
        if (path == null) {
            return null;
        }
        String s = path.endsWith("/") ? path.substring(0, path.length() - 1) : path;
        int i = s.lastIndexOf('/');
        if (i < 0 || i == s.length() - 1) {
            return null;
        }
        return s.substring(i + 1);
    }
}
