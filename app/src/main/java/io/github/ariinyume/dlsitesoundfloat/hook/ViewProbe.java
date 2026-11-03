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

import android.content.Context;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewParent;

import java.util.ArrayDeque;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 状态栏视图树的**探测原语**：按资源名 / 类名特征找视图、量屏幕坐标、判「此刻真的画得出来吗」。
 *
 * <p>从 {@link StatusBarSubtitleHook} 抽出来的第一块零状态内核。抽取原则沿用
 * ActivityButtonHook 那一轮（code 1047 后）：<b>行数不是边界，共享可变字段才是</b> ——
 * 这里搬走的全部是「只吃 View、只返回数字/布尔/引用」的纯查询，
 * 一个业务字段都不带走，因此调用方怎么改状态都与本类无关。
 *
 * <p>唯一保留的可变状态是 {@link #ID_CACHE}：它是 {@code getIdentifier} 的<b>记忆化缓存</b>
 * （纯函数缓存，不含业务语义），语义等价于原类的 {@code sResIdCache}。
 *
 * <p>为什么这些探测值得单独成类：它们全是 BFS/递归，写错就是「静默返回 null」或
 * 「把字幕右界压到屏左」这类难查的问题（见 {@link #leftmostVisibleChildLeft} 的注释），
 * 单独成文件后可以脱离状态机直接读、直接推理。
 */
final class ViewProbe {

    private ViewProbe() {
    }

    /** 资源名 -> id 的记忆化缓存。同一 SystemUI 会话内资源表不变，而 getIdentifier 很贵。 */
    private static final Map<String, Integer> ID_CACHE = new HashMap<>();

    /** 预热/刷新缓存（{@code refreshResIds} 在 attach 早期按已知名字批量填）。 */
    static void cacheResId(String name, int id) {
        ID_CACHE.put(name, id);
    }

    /**
     * 资源名 -> id。找不到返回 0。
     *
     * <p>⚠️ <b>0 也进缓存</b> —— 这是原实现的行为，必须原样保留：{@code ctx} 为 null
     * （attach 早期 {@code sRoot} 还没落）时那次查询同样会写入 0；若改成「只在拿到 ctx 时缓存」，
     * 后续调用会多出一次真实查询，与原实现的时序不再逐拍一致。
     */
    static int resId(Context ctx, String pkg, String name) {
        Integer cached = ID_CACHE.get(name);
        if (cached != null) {
            return cached;
        }
        int id = 0;
        try {
            if (ctx != null) {
                id = ctx.getResources().getIdentifier(name, "id", pkg);
            }
        } catch (Throwable ignored) {
        }
        ID_CACHE.put(name, id);
        return id;
    }

    /** 找出 root 下**所有** id 命中的视图（findViewById 只给第一个，重建后可能同时存在新旧实例）。 */
    static void collectByIds(View root, String pkg, String[] names, List<View> out) {
        if (root == null) {
            return;
        }
        int[] ids = new int[names.length];
        int n = 0;
        for (String name : names) {
            int id = resId(root.getContext(), pkg, name);
            if (id != 0) {
                ids[n++] = id;
            }
        }
        if (n == 0) {
            return;
        }
        try {
            ArrayDeque<View> queue = new ArrayDeque<>();
            queue.add(root);
            int guard = 0;
            while (!queue.isEmpty() && guard++ < 3000) {
                View v = queue.poll();
                int vid = v.getId();
                for (int i = 0; i < n; i++) {
                    if (vid == ids[i]) {
                        out.add(v);
                        break;
                    }
                }
                if (v instanceof ViewGroup) {
                    ViewGroup g = (ViewGroup) v;
                    for (int i = 0; i < g.getChildCount(); i++) {
                        View c = g.getChildAt(i);
                        if (c != null) {
                            queue.add(c);
                        }
                    }
                }
            }
        } catch (Throwable ignored) {
        }
    }

    /** 按资源名找状态栏内部视图（带缓存 id，找不到返回 null）。 */
    static View findById(View root, String pkg, String[] names) {
        if (root == null) {
            return null;
        }
        for (String n : names) {
            try {
                int rid = resId(root.getContext(), pkg, n);
                if (rid != 0) {
                    View v = root.findViewById(rid);
                    if (v != null) {
                        return v;
                    }
                }
            } catch (Throwable ignored) {
            }
        }
        return null;
    }

    /** 先按资源名，再按类名特征兜底。 */
    static View findSystemView(View root, String pkg, String[] ids, String classHint) {
        for (String id : ids) {
            try {
                int rid = resId(root.getContext(), pkg, id);
                if (rid != 0) {
                    View v = root.findViewById(rid);
                    if (v != null) {
                        return v;
                    }
                }
            } catch (Throwable ignored) {
            }
        }
        return findByClassHint(root, classHint);
    }

    /** 广度优先按类名特征找视图（ROM 改资源名时的兜底）。 */
    static View findByClassHint(View root, String hint) {
        if (root == null) {
            return null;
        }
        try {
            ArrayDeque<View> queue = new ArrayDeque<>();
            queue.add(root);
            int guard = 0;
            while (!queue.isEmpty() && guard++ < 4000) {
                View v = queue.poll();
                if (v.getClass().getName().contains(hint)) {
                    return v;
                }
                if (v instanceof ViewGroup) {
                    ViewGroup g = (ViewGroup) v;
                    for (int i = 0; i < g.getChildCount(); i++) {
                        View c = g.getChildAt(i);
                        if (c != null) {
                            queue.add(c);
                        }
                    }
                }
            }
        } catch (Throwable ignored) {
        }
        return null;
    }

    /** 视图的屏幕 x。宽度计算里所有横向量都换算到这个坐标系再比较。 */
    static int screenX(View v) {
        if (v == null) {
            return 0;
        }
        try {
            int[] p = new int[2];
            v.getLocationOnScreen(p);
            return p[0];
        } catch (Throwable t) {
            return 0;
        }
    }

    static boolean isAncestorOf(View ancestor, View target) {
        View p = target;
        int guard = 0;
        while (p != null && guard++ < 60) {
            if (p == ancestor) {
                return true;
            }
            ViewParent pv = p.getParent();
            p = pv instanceof View ? (View) pv : null;
        }
        return false;
    }

    static boolean isDescendantOf(View v, View ancestor) {
        return ancestor != null && isAncestorOf(ancestor, v);
    }

    /**
     * 「这个视图现在真的会被画出来吗」—— 比 getVisibility() 严格得多。
     *
     * <p>旧口径的两个漏判（都真机踩到）：
     * <ol>
     *   <li>祖先 GONE：子视图自身标志位还是 VISIBLE —— 由 {@code isShown()} 兜住；</li>
     *   <li>祖先 alpha=0（淡出动画期间）：alpha 是**沿祖先链相乘**生效的，但
     *       {@code getAlpha()} 只返回自身那一个值 —— 子视图自己是 1.0、实际全透明。</li>
     * </ol>
     * 这里把自身到 {@code stopAt}（含）的整条链都过一遍。
     *
     * @param stopAt 判定上界（流体云容器自身）；为 null 则一路走到根
     */
    static boolean isEffectivelyVisible(View v, View stopAt) {
        if (v == null || !v.isShown()) {
            return false;
        }
        try {
            View cur = v;
            int guard = 0;
            while (cur != null && guard++ < 12) {
                if (cur.getAlpha() <= 0.01f) {
                    return false;
                }
                if (cur == stopAt) {
                    break;
                }
                ViewParent p = cur.getParent();
                cur = (p instanceof View) ? (View) p : null;
            }
            return true;
        } catch (Throwable t) {
            return false;
        }
    }

    /** 递归找 group 内**最左的可见子视图**（base 坐标系），判定上界 = group 自身。 */
    static int leftmostVisibleChildLeft(View group, int base, int minValid) {
        return leftmostVisibleChildLeft(group, group, base, minValid);
    }

    /**
     * 递归找 group 内**最左的可见子视图**（base 坐标系）—— 对应 base.apk 的
     * {@code findLeftmostVisibleChildLeft}：只认 VISIBLE、宽&gt;0、alpha&gt;0.01、且
     * 左界 ∈ (minValid, best)。
     *
     * <p>alpha 那一项是精髓：胶囊收起/切换时子视图还留在树里、只是 alpha=0，
     * 不排除掉就会把字幕右界一路压到屏左（宽度算法：{@code avail = right - left}）。
     *
     * <p>【code 937 问题1 根修】旧口径 getVisibility() 只反映**自身标志位**：
     * 容器被 GONE / 从树上摘掉、或祖先正在 alpha 淡出时，子视图自己的 getVisibility()
     * 仍是 VISIBLE、getAlpha() 仍是 1.0、width 仍 &gt; 0 ⇒ 一个「已经画不出来」的容器照样
     * 通过判定并返回 left=448/454（真机实证：让位已从 42px 退回 3px 的那一拍，
     * 宽度仍是 "by seeding_card_container left=454"）。
     *
     * @param stopAt 有效可见性判定的上界（流体云容器自身）
     */
    static int leftmostVisibleChildLeft(View group, View stopAt, int base, int minValid) {
        if (!(group instanceof ViewGroup)) {
            return Integer.MAX_VALUE;
        }
        ViewGroup vg = (ViewGroup) group;
        int best = Integer.MAX_VALUE;
        for (int i = 0; i < vg.getChildCount(); i++) {
            View child = vg.getChildAt(i);
            if (child == null || !isEffectivelyVisible(child, stopAt)) {
                continue;
            }
            try {
                if (child.getAlpha() <= 0.01f) {
                    continue;
                }
                int l = screenX(child) - base;
                if (child.getWidth() > 0 && l > minValid && l < best) {
                    best = l;
                }
            } catch (Throwable ignored) {
            }
            int deeper = leftmostVisibleChildLeft(child, stopAt, base, minValid);
            if (deeper < best) {
                best = deeper;
            }
        }
        return best;
    }
}
