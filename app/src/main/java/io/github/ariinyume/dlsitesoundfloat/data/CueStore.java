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

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * 【code 1053 / 架构优化 A2】字幕摄入的**零状态纯解析层** —— 从 {@link SubtitleRepository}
 * 的 {@code loadFromJsonArrayInternal} / 行匹配辅助抽出。
 *
 * <p>只做：时间串 → 秒、行归一化、cue 装配、精确匹配集。不持锁、不碰印章 / 挂起 /
 * 磁盘 / UI。JSON 遍历与状态写入仍在 Repository。
 */
public final class CueStore {

    private CueStore() {
    }

    /**
     * {@code HH:mm:ss.SSS}（或 {@code HH:mm:ss}）→ 当天秒数。
     * 口径对齐原 {@code SimpleDateFormat("HH:mm:ss.SSS", UTC)}：失败返回 0。
     */
    public static double parseTime(String t) {
        if (t == null || t.isEmpty()) {
            return 0d;
        }
        try {
            String[] parts = t.trim().split(":");
            if (parts.length != 3) {
                return 0d;
            }
            int h = Integer.parseInt(parts[0]);
            int m = Integer.parseInt(parts[1]);
            double s = Double.parseDouble(parts[2]);
            // 与旧 SDF 失败回落一致：非法分量 → 0（避免 99:99:99 被算进时间轴）
            if (h < 0 || m < 0 || m >= 60 || s < 0d || s >= 60d) {
                return 0d;
            }
            return h * 3600d + m * 60d + s;
        } catch (Throwable e) {
            return 0d;
        }
    }

    /** 抓屏 / 匹配用：trim + 连续空白压成单空格；null → ""。 */
    public static String normalizeLine(String s) {
        return s == null ? "" : s.trim().replaceAll("\\s+", " ");
    }

    /**
     * 装配一条 cue。{@code lines} 为 null 时按空列表处理（与 optJSONArray 缺省一致）。
     */
    public static SubtitleCue cueOf(String startTime, String endTime, List<String> lines) {
        List<String> lineList = lines == null ? new ArrayList<>() : new ArrayList<>(lines);
        double endSec = parseTime(endTime);
        return new SubtitleCue(parseTime(startTime), endSec, lineList);
    }

    /** 更新「整份 JSON 最大结束秒」—— 磁盘时长补盖交叉校验用。 */
    public static double maxEndSec(double currentMax, double endSec) {
        return endSec > currentMax ? endSec : currentMax;
    }

    /**
     * 从 cues 建精确匹配集（v18）：每行 {@link #normalizeLine} 后非空才入集。
     */
    public static Set<String> exactLineSet(List<SubtitleCue> cues) {
        Set<String> out = new HashSet<>();
        if (cues == null) {
            return out;
        }
        for (SubtitleCue c : cues) {
            if (c == null || c.subtitles == null) {
                continue;
            }
            for (String line : c.subtitles) {
                String nl = normalizeLine(line);
                if (!nl.isEmpty()) {
                    out.add(nl);
                }
            }
        }
        return out;
    }

    /**
     * 抓屏文本是否还值得拿去对匹配集：非空、且长度 ≤ 字幕行上限
     * （超长 = 标题 / 简介 / 列表项，绝不是独立字幕 Text）。
     */
    public static boolean isPlausibleSubtitleProbe(String text, int maxLineLen) {
        if (text == null) {
            return false;
        }
        String t = normalizeLine(text);
        return !t.isEmpty() && t.length() <= maxLineLen;
    }
}
