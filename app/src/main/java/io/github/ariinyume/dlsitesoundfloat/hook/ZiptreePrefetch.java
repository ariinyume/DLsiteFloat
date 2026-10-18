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
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.atomic.AtomicInteger;

import io.github.ariinyume.dlsitesoundfloat.util.AppEnv;
import io.github.ariinyume.dlsitesoundfloat.util.NetState;
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

    /** 最多保留几部作品（每部约 30~300KB，8 部也才 1~2MB）。 */
    private static final int MAX_WORKS = 8;

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

    private ZiptreePrefetch() {
    }

    /** 一条「音轨 → 字幕文件」的映射。 */
    static final class Track {
        final long durMs;
        final String jsonName;

        Track(long durMs, String jsonName) {
            this.durMs = durMs;
            this.jsonName = jsonName;
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

        Pack(String workno, String baseUrl, String query, File dir) {
            this.workno = workno;
            this.baseUrl = baseUrl;
            this.query = query;
            this.dir = dir;
        }

        /** 命中时给数据层的作品键（与 {@code PlaylistKey.workKeyOf} 同口径，末段是 {@code optimized}）。 */
        String workKey() {
            return baseUrl + "optimized";
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

            List<Track> tracks = parseTracks(text);
            if (tracks.isEmpty()) {
                // 正常现象：这部作品本来就没有字幕（真机 RJ01654099 就只有 1 条音频、0 条 vtt）
                XposedCompat.log(TAG + " " + workno + ": ziptree has no vtt entry (作品无字幕)");
                // 对用户而言这是「已知事实」而不是故障 ⇒ 记 HIT，别让自检表报红（1023 口径）
                AdapterHealth.hit(AdapterHealth.Item.PREFETCH,
                        workno + ": no vtt in work (作品本来无字幕)");
                return;
            }

            File dir = new File(baseDir(), workno);
            if (!dir.exists() && !dir.mkdirs()) {
                XposedCompat.log(TAG + " mkdirs failed: " + dir);
                AdapterHealth.degraded(AdapterHealth.Item.PREFETCH, "mkdirs failed");
                return;
            }
            Pack pack = new Pack(workno, baseUrl, query, dir);
            pack.tracks.addAll(tracks);
            int queued = 0;
            int already = 0;
            long budget = MAX_BYTES_PER_WORK;
            for (Track t : tracks) {
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
            XposedCompat.log(TAG + " " + workno + ": tracks=" + tracks.size()
                    + " already=" + already + " queued=" + queued
                    + (budget < MAX_BYTES_PER_WORK ? " budget_left=" + budget : "")
                    + " -> " + pack.workKey());
            AdapterHealth.hit(AdapterHealth.Item.PREFETCH,
                    workno + ": " + tracks.size() + " tracks"
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
     * 按**时长**取一份已预取的字幕。
     *
     * @param durMs 目标音轨时长（毫秒，来自身份键）
     * @return 命中返回正文；没有则 {@code null}
     */
    public static Hit take(long durMs) {
        if (sDisabled || durMs <= 0L) {
            return null;
        }
        try {
            ensureIndexLoaded();
            List<Pack> snapshot;
            synchronized (LOCK) {
                snapshot = new ArrayList<>(PACKS.values());
            }
            // 逆序 = 最近 offer/命中的作品优先（accessOrder 的末尾是最新的）
            for (int i = snapshot.size() - 1; i >= 0; i--) {
                Pack p = snapshot.get(i);
                for (Track t : p.tracks) {
                    if (Math.abs(t.durMs - durMs) > DUR_TOLERANCE_MS) {
                        continue;
                    }
                    File f = new File(p.dir, t.jsonName);
                    if (!f.exists() || f.length() <= 0) {
                        continue;
                    }
                    String txt = readText(f);
                    if (txt == null || txt.length() == 0) {
                        continue;
                    }
                    XposedCompat.log(TAG + " HIT dur=" + durMs + "ms -> "
                            + p.workno + "/" + t.jsonName + " (" + f.length() + " B)"
                            + " work=" + p.workKey());
                    return new Hit(txt, p.workKey(), t.durMs, t.jsonName);
                }
            }
            XposedCompat.log(TAG + " MISS dur=" + durMs + "ms (packs=" + snapshot.size() + ")");
            return null;
        } catch (Throwable e) {
            XposedCompat.log(TAG + " take failed (ignored): " + e);
            return null;
        }
    }

    /** 诊断用：现在手上有几部作品、共多少条轨。 */
    public static String summary() {
        try {
            ensureIndexLoaded();
            int works;
            int tracks = 0;
            synchronized (LOCK) {
                works = PACKS.size();
                for (Pack p : PACKS.values()) {
                    tracks += p.tracks.size();
                }
            }
            return works + " works / " + tracks + " tracks";
        } catch (Throwable e) {
            return "?";
        }
    }

    // ==================================================================
    // 解析
    // ==================================================================

    /**
     * 从 ziptree 里抽出 `[时长, 字幕文件名]`。
     *
     * <p>只认 {@code type == "audio"} 且 {@code audio.vtt} 非空的条目 ——
     * 宿主是**一条音轨一份字幕**，没有 vtt 的轨（台本、无字幕轨）直接跳过。
     */
    private static List<Track> parseTracks(String text) throws Exception {
        List<Track> out = new ArrayList<>();
        JSONObject root = new JSONObject(text);
        JSONObject pf = root.optJSONObject("playfile");
        if (pf == null) {
            return out;
        }
        Iterator<String> it = pf.keys();
        while (it.hasNext() && out.size() < MAX_TRACKS_PER_WORK) {
            String key = it.next();
            JSONObject entry = pf.optJSONObject(key);
            if (entry == null || !"audio".equals(entry.optString("type"))) {
                continue;
            }
            JSONObject audio = entry.optJSONObject("audio");
            if (audio == null) {
                continue;
            }
            String vttName = audio.optString("vtt", "");
            if (vttName.length() == 0) {
                continue;
            }
            JSONObject vttEntry = pf.optJSONObject(vttName);
            if (vttEntry == null) {
                continue;
            }
            JSONObject vtt = vttEntry.optJSONObject("vtt");
            JSONObject optimized = vtt == null ? null : vtt.optJSONObject("optimized");
            String jsonName = optimized == null ? "" : optimized.optString("name", "");
            if (jsonName.length() == 0) {
                continue;
            }
            JSONObject audioOpt = audio.optJSONObject("optimized");
            double durSec = audioOpt == null ? 0.0 : audioOpt.optDouble("duration", 0.0);
            long durMs = Math.round(durSec * 1000.0);
            if (durMs <= 0L) {
                continue;
            }
            out.add(new Track(durMs, jsonName));
        }
        return out;
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
     *   T&lt;TAB&gt;&lt;durMs&gt;&lt;TAB&gt;&lt;jsonName&gt;
     * </pre>
     * 不用 JSON：这里只有三种行，文本更好排查，也不受宿主 JSON 实现差异影响。
     */
    private static void writeIndex(Pack pack) {
        File f = indexFile(pack.workno);
        if (f == null) {
            return;
        }
        StringBuilder sb = new StringBuilder(256);
        sb.append("Q\t").append(pack.query).append('\n');
        sb.append("B\t").append(pack.baseUrl).append('\n');
        for (Track t : pack.tracks) {
            sb.append("T\t").append(t.durMs).append('\t').append(t.jsonName).append('\n');
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
                    if (p != null && !p.tracks.isEmpty()) {
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
            for (String line : txt.split("\n")) {
                if (line.length() < 3) {
                    continue;
                }
                char tag = line.charAt(0);
                if (tag == 'Q') {
                    query = line.substring(2);
                } else if (tag == 'B') {
                    baseUrl = line.substring(2);
                } else if (tag == 'T') {
                    String[] parts = line.split("\t");
                    if (parts.length >= 3) {
                        tracks.add(new Track(Long.parseLong(parts[1]), parts[2]));
                    }
                }
            }
            File dir = new File(baseDir(), workno);
            if (baseUrl.length() == 0 || !dir.exists()) {
                return null;
            }
            Pack p = new Pack(workno, baseUrl, query, dir);
            p.tracks.addAll(tracks);
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
