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
 * 【code 1056 / 架构优化 B2】状态栏 OEM **资源名目录 + 锚点裁决纯层**。
 *
 * <p>从 {@link StatusBarSubtitleHook} 抽出：各 ROM 候选 id 数组、锚点命中标签、
 * describe 文案、compat 缺项 CSV。树遍历仍走 {@link ViewProbe}；广播 / 滚动 /
 * 压制留在 Hook。
 *
 * <p>锚点数组顺序是契约：ColorOS 优先，再回退 AOSP —— 单测钉死「先命中者胜」。
 */
final class StatusBarOemHunt {

    /** 注入锚点：ColorOS fake 容器优先，再 AOSP start_side。 */
    static final String[] ANCHOR_IDS = {
            "status_bar_start_side_content_for_fake",
            "status_bar_start_side_container",
            "status_bar_start_side_content"
    };

    /** 时钟：字体/颜色同步源 + 遮挡目标。 */
    static final String[] CLOCK_IDS = {
            "clock", "status_bar_clock", "oplus_clock", "status_bar_clock_view"
    };

    /** 左侧通知图标区。 */
    static final String[] NOTIF_AREA_IDS = {
            "notification_icon_area",
            "notification_icons",
            "status_bar_notification_icons",
            "status_bar_notification_icon_area",
            "notification_icon_area_inner"
    };

    /** ColorOS 流体云 / 实时活动胶囊容器。 */
    static final String[] SEEDING_IDS = {
            "seeding_card_container",
            "ongoing_activity_chip_primary",
            "ongoing_activity_chip_secondary"
    };

    /** 起始区容器右界上限。 */
    static final String[] SIDE_CONTAINER_IDS = {
            "status_bar_start_side_container"
    };

    /** 挖孔占位。 */
    static final String[] CUTOUT_IDS = {
            "cutout_space_view"
    };

    /** 非 ColorOS 流体云资源名兜底。 */
    static final String[] FLUID_IDS = {
            "status_bar_fluid_cloud",
            "fluid_cloud",
            "fluid_cloud_view",
            "oplus_fluid_cloud",
            "status_bar_center_side_content",
            "status_bar_center_side_content_for_fake",
            "status_bar_center_side",
            "status_bar_center_content",
            "status_bar_middle_content",
            "status_bar_middle_content_for_fake",
            "status_bar_live_notification",
            "live_notification_view",
            "status_bar_capsule",
            "capsule_view",
            "status_bar_ongoing_activity"
    };

    /** 流体云类名特征兜底。 */
    static final String[] FLUID_HINTS = {
            "CapsulePluginContainer", "FluidCloud", "Capsule", "OngoingActivity",
            "LiveNotification", "LiveText", "PromptContainer", "CenterSide", "Fluid"
    };

    enum AnchorKind {
        ID,
        FALLBACK_CLOCK_PARENT,
        MISSING
    }

    static final class AnchorDecision {
        final AnchorKind kind;
        final String hitLabel;
        final String matchedName;

        AnchorDecision(AnchorKind kind, String hitLabel, String matchedName) {
            this.kind = kind;
            this.hitLabel = hitLabel;
            this.matchedName = matchedName;
        }
    }

    private StatusBarOemHunt() {
    }

    /** {@code id:name} */
    static String formatIdHit(String name) {
        return "id:" + name;
    }

    /** {@code fallback:parentOf(clockDescribe)} */
    static String formatClockParentFallback(String clockDescribe) {
        return "fallback:parentOf(" + clockDescribe + ")";
    }

    /**
     * 在候选名里找第一个「已解析且存在」的锚点名；没有则 null。
     *
     * @param present {@code name -> 该 id 在树上找得到}
     */
    static String firstHitAnchorName(String[] names, java.util.function.Predicate<String> present) {
        if (names == null || present == null) {
            return null;
        }
        for (String name : names) {
            if (name != null && present.test(name)) {
                return name;
            }
        }
        return null;
    }

    /**
     * 锚点三岔口：id 命中 / 时钟父容器兜底 / MISSING。
     *
     * @param firstHitAnchorName {@link #firstHitAnchorName} 结果；非空 ⇒ ID
     * @param clockDescribeOrNull 时钟 describe 文案；非空且无 id 命中 ⇒ FALLBACK
     */
    static AnchorDecision decideAnchor(String firstHitAnchorName, String clockDescribeOrNull) {
        if (firstHitAnchorName != null && !firstHitAnchorName.isEmpty()) {
            return new AnchorDecision(AnchorKind.ID, formatIdHit(firstHitAnchorName),
                    firstHitAnchorName);
        }
        if (clockDescribeOrNull != null && !clockDescribeOrNull.isEmpty()) {
            return new AnchorDecision(AnchorKind.FALLBACK_CLOCK_PARENT,
                    formatClockParentFallback(clockDescribeOrNull), null);
        }
        return new AnchorDecision(AnchorKind.MISSING, "MISSING", null);
    }

    /**
     * View-free describe：viewId 命中候选名 ⇒ 返回名；否则 {@code class#0xhex}。
     */
    static String describeLabel(int viewId, String[] candidateNames,
            java.util.function.ToIntFunction<String> nameToResId, String classSimpleName) {
        if (candidateNames != null && nameToResId != null && viewId != 0) {
            for (String n : candidateNames) {
                if (n == null) {
                    continue;
                }
                int rid = nameToResId.applyAsInt(n);
                if (rid != 0 && rid == viewId) {
                    return n;
                }
            }
        }
        String cls = classSimpleName == null ? "?" : classSimpleName;
        return cls + "#0x" + Integer.toHexString(viewId);
    }

    /**
     * compat 缺项 CSV（无 I/O）：如 {@code anchor,clock,seeding,}；全命中 ⇒ 空串。
     */
    static String missingCompatCsv(String anchorHit, boolean clockFound, boolean notifFound,
            boolean seedingFound) {
        StringBuilder miss = new StringBuilder();
        if (anchorHit == null || "MISSING".equals(anchorHit)) {
            miss.append("anchor,");
        } else if (anchorHit.startsWith("fallback")) {
            miss.append("anchor(兜底),");
        }
        if (!clockFound) {
            miss.append("clock,");
        }
        if (!notifFound) {
            miss.append("notif,");
        }
        if (!seedingFound) {
            miss.append("seeding,");
        }
        return miss.toString();
    }
}
