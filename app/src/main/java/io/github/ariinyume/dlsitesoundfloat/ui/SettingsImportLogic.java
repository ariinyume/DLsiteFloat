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
package io.github.ariinyume.dlsitesoundfloat.ui;

import java.util.Set;

import org.json.JSONObject;

import io.github.ariinyume.dlsitesoundfloat.config.SubtitleConfig;

/**
 * 【code 1060 / 架构优化 B1】设置页**导入预检 + 对齐枚举**的零状态逻辑。
 *
 * <p>从 {@link SettingsActivity#importConfigFrom} / 对齐分段控件抽出。Uri I/O、
 * Toast、{@code fromJson}、View 仍在 Activity。
 *
 * <p>口径：PRD §12（schema 过新拒绝）/ 空壳 JSON 拒收 / 导入保留本页
 * {@code uiLanguage} + {@link SettingsDraftPolicy#quantize}。
 */
public final class SettingsImportLogic {

    /** 粗判「像真配置」时认的键（与原 {@code looksLikeSubtitleConfig} 一致）。 */
    public static final String[] KNOWN_KEYS = {
            SubtitleConfig.K_SUBTITLE_COLOR,
            SubtitleConfig.K_SHADOW_COLOR,
            SubtitleConfig.K_TEXT_ALIGN,
            SubtitleConfig.K_LINE_SPACING_DP,
            SubtitleConfig.K_FLOAT_WINDOW_COLOR,
            SubtitleConfig.K_UI_LANGUAGE,
    };

    public enum Preflight {
        /** 可继续 fromJson。 */
        OK,
        /** schema 比本模块新（PRD §12 E-04）。 */
        TOO_NEW,
        /** schema 缺失且没有任何已知键 → 空壳。 */
        BROKEN_SHELL
    }

    private SettingsImportLogic() {
    }

    /** 键名集合版（单测用，不碰 {@link JSONObject}）。 */
    public static boolean looksLikeSubtitleConfig(Set<String> keyNames) {
        if (keyNames == null || keyNames.isEmpty()) {
            return false;
        }
        for (String k : KNOWN_KEYS) {
            if (keyNames.contains(k)) {
                return true;
            }
        }
        return false;
    }

    /** Activity 接线：读 JSONObject。 */
    public static boolean looksLikeSubtitleConfig(JSONObject o) {
        if (o == null) {
            return false;
        }
        for (String k : KNOWN_KEYS) {
            if (o.has(k)) {
                return true;
            }
        }
        return false;
    }

    /**
     * 导入预检。
     *
     * @param schema          文件里的 schema（缺省 0）
     * @param looksLike       {@link #looksLikeSubtitleConfig}
     * @param supportedSchema 本模块 {@link SubtitleConfig#SCHEMA_VERSION}
     */
    public static Preflight preflight(int schema, boolean looksLike, int supportedSchema) {
        if (schema > supportedSchema) {
            return Preflight.TOO_NEW;
        }
        if (schema <= 0 && !looksLike) {
            return Preflight.BROKEN_SHELL;
        }
        return Preflight.OK;
    }

    /**
     * 导入进草稿：保留本页语言并 quantize（原地改 {@code imported}）。
     */
    public static void prepareImportedDraft(SubtitleConfig imported, String keepUiLanguage) {
        if (imported == null) {
            return;
        }
        imported.uiLanguage = keepUiLanguage == null
                ? SubtitleConfig.LANG_SYSTEM : keepUiLanguage;
        SettingsDraftPolicy.quantize(imported);
    }

    /** 分段下标 → {@link SubtitleConfig} 对齐枚举。 */
    public static String alignValueOf(int index) {
        switch (index) {
            case 0:
                return SubtitleConfig.ALIGN_LEFT;
            case 2:
                return SubtitleConfig.ALIGN_RIGHT;
            case 1:
            default:
                return SubtitleConfig.ALIGN_CENTER;
        }
    }

    /** 对齐枚举 → 分段下标（未知回落居中 = 1）。 */
    public static int alignIndex(String v) {
        if (SubtitleConfig.ALIGN_LEFT.equals(v)) {
            return 0;
        }
        if (SubtitleConfig.ALIGN_RIGHT.equals(v)) {
            return 2;
        }
        return 1;
    }
}
