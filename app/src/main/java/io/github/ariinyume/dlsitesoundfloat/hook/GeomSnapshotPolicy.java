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
 * 【code 1050 / 架构优化 A1】几何快照的**采信与重落位闸** —— 零状态纯判定层。
 *
 * <p>从 {@code ActivityButtonHook.detectAndLayout} / {@code replaceCapsuleByGeometry}
 * 抽出：哪些扫描值可以写入 {@code sLast*}、窗口形态是否变了、已落位快照是否仍视为
 * 「没变」（含 settle 迟滞）。判据顺序与比较符逐条照搬原实现；本类不读静态字段、
 * 不写日志、不碰 View。
 *
 * <p>与 {@link CapsuleGeometry} / {@link DetectGatePolicy} 同构：算术进纯函数，
 * 副作用留 hook。
 */
final class GeomSnapshotPolicy {

    private GeomSnapshotPolicy() {
    }

    /**
     * 是否采信本趟扫到的滑条中心 / 高度（以及同源的时间行底边）。
     *
     * <p>铁律（code 925）：不稳定坐标 = RN settle 中间态 → <b>不采信</b>，沿用上次稳定值。
     * 这只影响「按钮摆在哪」，不影响「按钮出不出现」（出现由 verdict / hasMainSlider 决定）。
     */
    static boolean acceptSliderCenter(boolean hasMainSlider, int mainSliderY,
            boolean mainSliderStable) {
        return hasMainSlider && mainSliderY > 0 && mainSliderStable;
    }

    /**
     * 在 {@link #acceptSliderCenter} 已为真的前提下，是否采信时间行底边。
     *
     * <p>与滑条中心共用稳定门 —— 两个基准线必须同源，否则会出现「滑条上一帧、
     * 时间行这一帧」的混合态（code 1045）。
     */
    static boolean acceptTimeLabelBottom(boolean sliderCenterAccepted, int timeLabelBottom) {
        return sliderCenterAccepted && timeLabelBottom > 0;
    }

    /** 是否采信滑条右缘（= x + w）。不叠稳定门：右缘只服务水平对齐，抖动代价低。 */
    static boolean acceptSliderRight(boolean hasMainSlider, int mainSliderX, int mainSliderW) {
        return hasMainSlider && mainSliderW > 0 && mainSliderX >= 0;
    }

    /** 是否采信简介行底边。 */
    static boolean acceptDescBottom(int descLineBottom) {
        return descLineBottom > 0;
    }

    /**
     * 窗口形态是否变了（浮窗进出 / 分屏 / 转屏 / 被拖动）。
     *
     * <p>变了 ⇒ 调用方必须 <b>force</b> 重落位：只看滑条/时间行动没动看不出来
     * （浮窗里宿主可能一个控件都不挪，只是整个窗口换了位置，code 1048）。
     */
    static boolean windowMoved(int decorTop, int screenW, int screenH,
            int placedDecorTop, int lastScreenW, int lastScreenH) {
        return decorTop != placedDecorTop
                || screenW != lastScreenW
                || screenH != lastScreenH;
    }

    /**
     * 当前几何相对「已落位快照」是否仍视为未变（含 settle 迟滞）。
     *
     * <p>{@code true} ⇒ {@code replaceCapsuleByGeometry} 应直接 return，避免每帧
     * {@code setLayoutParams} 造成布局回环（code 927 / GEO_SNAPSHOT_DEADZONE）。
     *
     * @param deadzonePx 迟滞半径（调用方传入 {@code GEO_SNAPSHOT_DEADZONE_PX}）
     */
    static boolean geoUnchanged(int sliderCy, int descBottom, int sliderRight,
            int timeLabelBottom,
            int placedSliderCy, int placedDescBottom, int placedSliderRight,
            int placedTimeLabelBottom, int deadzonePx) {
        return Math.abs(sliderCy - placedSliderCy) <= deadzonePx
                && Math.abs(descBottom - placedDescBottom) <= deadzonePx
                && Math.abs(sliderRight - placedSliderRight) <= deadzonePx
                && Math.abs(timeLabelBottom - placedTimeLabelBottom) <= deadzonePx;
    }
}
