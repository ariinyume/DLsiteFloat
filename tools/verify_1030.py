import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from sdkpath import build_tools as _build_tools
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【code 1030 / v2.3.5】设置页第四轮九项的 **产物层**（APK）验证。

一律「主验 + 上一版对照」**单进程双表**（铁律 79）：
主验 = 本轮 code 1030 包，对照 = 上一轮 code 1029 包。
每条都报「有没有区分力」，验不到的**如实标注**（铁律 79）。

验什么
------
A1–A6   版本档位（code / versionName / 对照包 / 三档 sdk）
B1–B6   文案改名（「清除已缓存字幕」「清除预取字幕」三语，旧繁体名清除干净）
C1–C5   预取清理链路（clearAll / deleteRecursively / handlePrefetchClear /
        sendPrefetchClear 四个调用点 + ACTION 常量串）
D1–D2   关闭实验性开关不再清缓存（方法体级反证）
E1–E6   底栏容器换成普通 LinearLayout（标签名 + 四条被丢掉的属性 + 吸底仍成立）
F1–F3   页签组 40dp / 滚动区底部 12dp / 外观卡内上内边距 16dp
G1–G5   保持型（预览三层 / preview_mini 不复辟 / 溢出键圆底 / 常开横幅 / versionName）
H       如实标注：本轮哪几件在产物层**没有**区分力

⚠️ 判「节点自己有没有某个属性」必须**只取本节点那一层**（`node()` 按缩进切），
   不能用定长字符窗口 —— 窗口会把兄弟/子节点的属性一起卷进来，造出假阳性（铁律 60）。

用法
----
    python verify_1030.py [new.apk] [old.apk]
退出码 0 = 全部通过
"""

import os
import re
import subprocess
import sys
import zipfile

BT = _build_tools('36.0.0')
AAPT2 = os.path.join(BT, 'aapt2.exe')
DEXDUMP = os.path.join(BT, 'dexdump.exe')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UP = os.path.dirname(ROOT)                    # 仓库的上一级（本机工作区）
APK_NEW = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    ROOT, 'app', 'build', 'outputs', 'apk', 'debug', 'DLsiteFloat-2.3.5-code1030-debug.apk')
APK_OLD = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    UP, 'DLsiteFloat-2.3.5-code1029-debug.apk')

LAYOUT = 'res/layout/activity_settings.xml'

fails = []
total = 0
disc = 0
nodisc = []


def check(name, ok, detail=''):
    global total
    total += 1
    if ok:
        print('  PASS  %s' % name)
    else:
        print('  FAIL  %s   %s' % (name, detail))
        fails.append(name)


def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout.decode('utf-8', 'replace')


def badging(apk):
    return run([AAPT2, 'dump', 'badging', apk])[1]


def resources(apk):
    return run([AAPT2, 'dump', 'resources', apk])[1]


def xmltree(apk):
    return run([AAPT2, 'dump', 'xmltree', '--file', LAYOUT, apk])[1]


def res_id(apk, kind_slash_name):
    """从资源表里取 <type>/<name> 的 0x 数值（取不到返回 None）。"""
    m = re.search(r'resource (0x[0-9a-f]{8}) %s\b' % re.escape(kind_slash_name), resources(apk))
    return m.group(1) if m else None


def _ind(s):
    return len(s) - len(s.lstrip(' '))


def _tag(s):
    """'            E: LinearLayout (line=606)' -> 'LinearLayout'

    ⚠️ 必须先 strip()：node() 传进来的是**带缩进的原行**，
       直接 s[3:] 只砍掉三个空格，标签名前面还挂着一串空格（踩过）。
    """
    return s.strip()[3:].split(' (line=')[0].strip()


def node(apk, resid):
    """按 android:id 的数值定位节点，返回 (tag, 本节点属性, [(子tag, 子属性), ...])。

    属性按**缩进层级**归属：本节点的属性恰好比 E: 行深 2 格，子节点深 4 格、
    子节点属性深 6 格。定长字符窗口会把子节点属性算进来，故不用窗口（铁律 60）。
    """
    if resid is None:
        return None, [], []
    lines = xmltree(apk).splitlines()
    needle = 'android:id(0x010100d0)=@%s' % resid
    for i, ln in enumerate(lines):
        if needle not in ln:
            continue
        j = i
        while j >= 0 and not lines[j].strip().startswith('E: '):
            j -= 1
        if j < 0:
            return None, [], []
        e = _ind(lines[j])
        attrs, kids, cur = [], [], None
        k = j + 1
        while k < len(lines):
            s = lines[k].strip()
            d = _ind(lines[k])
            if not s:
                k += 1
                continue
            if s.startswith('E: ') and d <= e:
                break
            if s.startswith('E: ') and d == e + 4:
                cur = [_tag(s), []]
                kids.append(cur)
            elif not s.startswith('E: ') and d == e + 2:
                attrs.append(s)
            elif not s.startswith('E: ') and d == e + 6 and cur is not None:
                cur[1].append(s)
            k += 1
        return _tag(lines[j]), attrs, kids
    return None, [], []


def has(attrs, token):
    """本节点属性里有没有这个 token（子串匹配，属性和值都算）。"""
    return any(token in a for a in attrs)


def dex_blob(apk):
    z = zipfile.ZipFile(apk)
    names = [n for n in z.namelist() if re.match(r'classes\d*\.dex$', n)]
    return b''.join(z.read(n) for n in names)


def count(blob, token):
    return blob.count(token.encode('utf-8'))


_dump_cache = {}


def dex_dump(apk):
    """整个 APK 所有 dex 的 dexdump -d 文本（含指令层，用来判调用点）。"""
    if apk in _dump_cache:
        return _dump_cache[apk]
    z = zipfile.ZipFile(apk)
    out = []
    for nm in [n for n in z.namelist() if re.match(r'classes\d*\.dex$', n)]:
        # code 1037：临时 dex 落 app/build/_dextmp/ 覆盖写、**不删除**
        # （删 9 次/脚本会撞环境批量删除保护 ⇒ 进程被掐断 ⇒ 误报 ENVBLOCK）。
        scratch = os.path.join(ROOT, 'app', 'build', '_dextmp')
        os.makedirs(scratch, exist_ok=True)
        tmp = os.path.join(scratch, '_v1030_%s' % nm)
        with open(tmp, 'wb') as f:
            f.write(z.read(nm))
        out.append(run([DEXDUMP, '-d', tmp])[1])
    _dump_cache[apk] = ''.join(out)
    return _dump_cache[apk]


def method_body(d, name):
    """截某个方法的 dump 段：从 name 行到**下一个** name 行（不是定长窗口）。"""
    m = re.search(r"name\s+: '%s'" % re.escape(name), d)
    if not m:
        return ''
    n = re.compile(r"name\s+: '").search(d, m.end())
    return d[m.start():n.start() if n else m.start() + 20000]


def main():
    global disc
    for p in (APK_NEW, APK_OLD):
        if not os.path.isfile(p):
            print('找不到 APK：%s' % p)
            return 2

    print('主验：%s' % os.path.basename(APK_NEW))
    print('对照：%s\n' % os.path.basename(APK_OLD))

    bn = badging(APK_NEW)
    bo = badging(APK_OLD)

    print('── A 版本档位 ──────────────────────────────────────────────')
    check('A1 versionCode = 1030', "versionCode='1030'" in bn)
    check('A2 versionName = 2.3.5（本轮不升名）', "versionName='2.3.5'" in bn)
    check('A3 对照包仍是 1029（证明这是相邻两版）', "versionCode='1029'" in bo)
    check('A4 minSdk = 24（未动）', "minSdkVersion:'24'" in bn)
    check('A5 targetSdk = 36（未动）', "targetSdkVersion:'36'" in bn)
    check('A6 compileSdk = 36（未动）', "compileSdkVersion='36'" in bn)

    dn = dex_blob(APK_NEW)
    do = dex_blob(APK_OLD)

    print('\n── B 文案改名（新包有 / 旧包无）───────────────────────────')

    def added(name, token):
        global disc
        n = count(dn, token)
        o = count(do, token)
        ok = n > 0 and o == 0
        if ok:
            disc += 1
        check('%s  (new=%d / old=%d)' % (name, n, o), ok)
        return ok

    added('B1 「清除已缓存字幕」（原「清除所有字幕缓存」）', '清除已缓存字幕')
    added('B2 「清除已快取字幕」（繁体同步改）', '清除已快取字幕')
    added('B3 「清除预取字幕」（新增按钮）', '清除预取字幕')
    added('B4 「清除預取字幕」（繁体）', '清除預取字幕')
    added('B5 「Clear prefetched subtitles」（英文）', 'Clear prefetched subtitles')

    o_old_name = count(do, '清除所有字幕快取')
    n_old_name = count(dn, '清除所有字幕快取')
    ok = n_old_name == 0 and o_old_name > 0
    if ok:
        disc += 1
    check('B6 繁体旧名「清除所有字幕快取」已清干净  (new=%d / old=%d)'
          % (n_old_name, o_old_name), ok)
    print('  ── 注：简体旧名「清除所有字幕缓存」新包仍有 %d 处，那是常开横幅履历段'
          % count(dn, '清除所有字幕缓存'))
    print('     在讲「原名 XX 改成 YY」，**不能拿来判改名失效**（如实标注）。')

    print('\n── C 预取清理链路（dex 指令层调用点）───────────────────────')
    ddn = dex_dump(APK_NEW)
    ddo = dex_dump(APK_OLD)

    def invoke(name, sig):
        global disc
        n = ddn.count(sig)
        o = ddo.count(sig)
        ok = n > 0 and o == 0
        if ok:
            disc += 1
        check('%s  (new=%d / old=%d)' % (name, n, o), ok)

    invoke('C1 ZiptreePrefetch.clearAll() 调用点存在',
           'ZiptreePrefetch;.clearAll:()V')
    invoke('C2 ZiptreePrefetch.deleteRecursively(File) 调用点存在',
           'ZiptreePrefetch;.deleteRecursively:(Ljava/io/File;)V')
    invoke('C3 ConfigBus.handlePrefetchClear(Context, String) 调用点存在',
           'ConfigBus;.handlePrefetchClear:(Landroid/content/Context;Ljava/lang/String;)V')
    invoke('C4 ConfigBus.sendPrefetchClear(Context) 调用点存在（按钮侧发广播）',
           'ConfigBus;.sendPrefetchClear:(Landroid/content/Context;)V')
    added('C5 ACTION 常量串 SUBTITLE_PREFETCH_CLEAR', 'SUBTITLE_PREFETCH_CLEAR')

    print('\n── D 关闭开关不再清缓存（方法体级）────────────────────────')
    body_n = method_body(ddn, 'onExperimentalToggled')
    body_o = method_body(ddo, 'onExperimentalToggled')
    check('D1 onExperimentalToggled 里量到了方法体（判据有效性前提）',
          len(body_n) > 200 and len(body_o) > 200,
          'new=%d / old=%d' % (len(body_n), len(body_o)))
    check('D2 总开关关闭时体内已无 sendCacheClear  (new=%d / old=%d)'
          % (body_n.count('ConfigBus;.sendCacheClear'),
             body_o.count('ConfigBus;.sendCacheClear')),
          body_n.count('ConfigBus;.sendCacheClear') == 0
          and body_o.count('ConfigBus;.sendCacheClear') > 0)
    if body_n.count('ConfigBus;.sendCacheClear') == 0 and \
            body_o.count('ConfigBus;.sendCacheClear') > 0:
        disc += 1
    sc = ddn.count('ConfigBus;.sendCacheClear')
    check('D3 全包仍有 sendCacheClear 调用点（按钮那条链没被顺手删）  n=%d' % sc, sc > 0)

    print('\n── E 底栏容器：FloatingToolbarLayout → 普通 LinearLayout ────')
    tags_new = [_tag(l) for l in xmltree(APK_NEW).splitlines() if l.strip().startswith('E: ')]
    tags_old = [_tag(l) for l in xmltree(APK_OLD).splitlines() if l.strip().startswith('E: ')]
    n_ft = [t for t in tags_new if t.endswith('FloatingToolbarLayout')]
    o_ft = [t for t in tags_old if t.endswith('FloatingToolbarLayout')]
    check('E1 布局树里已无 FloatingToolbarLayout  (new=%d / old=%d)'
          % (len(n_ft), len(o_ft)), not n_ft and bool(o_ft))
    if not n_ft and o_ft:
        disc += 1

    tag_bn, attrs_bn, kids_bn = node(APK_NEW, res_id(APK_NEW, 'id/bottom_bar'))
    tag_bo, attrs_bo, _ = node(APK_OLD, res_id(APK_OLD, 'id/bottom_bar'))
    check('E2 bottom_bar 标签 = LinearLayout  (new=%s / old=%s)' % (tag_bn, tag_bo),
          tag_bn == 'LinearLayout' and (tag_bo or '').endswith('FloatingToolbarLayout'))

    def attr_gone(name, token):
        global disc
        ok = not has(attrs_bn, token) and has(attrs_bo, token)
        if ok:
            disc += 1
        check('%s  (new=%s / old=%s)' % (name, '无' if not has(attrs_bn, token) else '有',
                                         '无' if not has(attrs_bo, token) else '有'), ok)

    attr_gone('E3 本节点已无 backgroundTint（自带色调会重新上色）',
              'backgroundTint(0x7f030051)=')
    attr_gone('E4 本节点已无 elevation（没有背景就没有阴影）',
              'elevation(0x7f0301c2)=')
    attr_gone('E5 本节点已无 style=（不再挂官方 FloatingToolbar 样式）', 'style=@')
    attr_gone('E6 本节点已无 marginBottomSystemWindowInsets（不再二次让位）',
              'marginBottomSystemWindowInsets')

    ok = has(attrs_bn, 'layout_gravity(0x010100b3)=0x00800055') and \
        has(attrs_bn, 'layout_marginBottom(0x010100fa)=12.000000dp')
    check('E7 吸底定位不变（bottom|end + marginBottom 12dp）', ok,
          str(attrs_bn))
    check('E8 底栏仍有直接子容器（按钮组没丢）  kids=%d' % len(kids_bn),
          len(kids_bn) >= 1)

    print('\n── F 页签高度 / 底部留白 ───────────────────────────────────')
    tag_t, attrs_t, _ = node(APK_NEW, res_id(APK_NEW, 'id/appearance_tabs'))
    _, attrs_to, _ = node(APK_OLD, res_id(APK_OLD, 'id/appearance_tabs'))
    check('F1 页签组高 = 40dp（= 「对齐」那排）  (new=%s / old=%s)'
          % ('40dp' if has(attrs_t, 'layout_height(0x010100f5)=40.000000dp') else '非40dp',
             '48dp' if has(attrs_to, 'layout_height(0x010100f5)=48.000000dp') else '非48dp'),
          has(attrs_t, 'layout_height(0x010100f5)=40.000000dp')
          and has(attrs_to, 'layout_height(0x010100f5)=48.000000dp'))
    if has(attrs_t, 'layout_height(0x010100f5)=40.000000dp') and \
            has(attrs_to, 'layout_height(0x010100f5)=48.000000dp'):
        disc += 1

    _, attrs_s, _ = node(APK_NEW, res_id(APK_NEW, 'id/settings_scroll'))
    _, attrs_so, _ = node(APK_OLD, res_id(APK_OLD, 'id/settings_scroll'))
    check('F2 滚动区底部让位 = 12dp（原 96dp）  (new=%s / old=%s)'
          % ('12dp' if has(attrs_s, 'paddingBottom(0x010100d9)=12.000000dp') else '非12dp',
             '96dp' if has(attrs_so, 'paddingBottom(0x010100d9)=96.000000dp') else '非96dp'),
          has(attrs_s, 'paddingBottom(0x010100d9)=12.000000dp')
          and has(attrs_so, 'paddingBottom(0x010100d9)=96.000000dp'))
    if has(attrs_s, 'paddingBottom(0x010100d9)=12.000000dp') and \
            has(attrs_so, 'paddingBottom(0x010100d9)=96.000000dp'):
        disc += 1

    _, _, kids_cn = node(APK_NEW, res_id(APK_NEW, 'id/card_main'))
    _, _, kids_co = node(APK_OLD, res_id(APK_OLD, 'id/card_main'))
    top_n = has(kids_cn[0][1], 'paddingTop(0x010100d7)=16.000000dp') if kids_cn else False
    top_o = has(kids_co[0][1], 'paddingTop(0x010100d7)=10.000000dp') if kids_co else False
    check('F3 外观卡内上内边距 = 16dp（原 10dp，按钮不再贴卡片上沿）  (new=%s / old=%s)'
          % ('16dp' if top_n else '非16dp', '10dp' if top_o else '非10dp'),
          top_n and top_o)
    if top_n and top_o:
        disc += 1

    print('\n── G 保持型（本轮不该被顺手改坏）──────────────────────────')
    check('G1 完整预览三层 id 仍在',
          all(res_id(APK_NEW, 'id/preview_%s' % k) is not None
              for k in ('backdrop', 'panel', 'lines')))
    check('G2 折叠用的 preview_mini 四个 id 仍未复辟（1029 已删）',
          all(res_id(APK_NEW, 'id/preview_mini%s' % s) is None
              for s in ('', '_lines', '_backdrop', '_panel')))
    bg = res_id(APK_NEW, 'drawable/bg_toolbar_icon')
    _, ov_attrs, _ = node(APK_NEW, res_id(APK_NEW, 'id/overflow_button'))
    check('G3 溢出键仍自带圆底（去掉容器后靠它自己站住）  bg=%s' % (bg or '无'),
          bg is not None and has(ov_attrs, 'background(0x010100d4)=@%s' % bg))
    check('G4 常开横幅自报 1030',
          count(dn, '==== BUILD 2.3.5 / code 1030') > 0)
    check('G5 两包 versionName 一致（只升 code）',
          "versionName='2.3.5'" in bn and "versionName='2.3.5'" in bo)

    print('\n── H 如实标注（本轮这几件在产物层**没有**区分力）─────────────')
    for s in ('预览窗「上下各藏一行」+ 上沿按内容坐标裁：纯运行时几何，产物层无资源可判'
              '（源码层 verify_1030_src A1–A7）',
              '页签选中/未选着色（colorPrimary / colorSecondaryContainer）：'
              '运行时构造 ColorStateList，无对应资源',
              '「对齐」行搬到「悬浮窗颜色」之前：纯代码顺序，产物层不可见',
              '删「液态玻璃默认设置」下方小字：HINT_LIQUID_GLASS 字符串两包都在'
              '（枚举常量仍定义、未被 R8 裁），不能拿它的存在与否下结论',
              '「清除预取字幕」按钮并排连通组：运行时 ShapeAppearanceModel 逐角构造，'
              '无对应资源（源码层 E3）'):
        nodisc.append(s)
        print('  N/A   ' + s)

    print('\n' + '=' * 60)
    print('有区分力的锚：%d 条' % disc)
    if fails:
        print('FAIL %d/%d' % (len(fails), total))
        for f in fails:
            print('  - ' + f)
        return 1
    print('PASS %d/%d' % (total, total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
