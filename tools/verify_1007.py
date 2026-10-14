#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_1007.py —— code 1007 的 **dex 字节码层**验证。

code 1007 是本项目的**新功能**：字幕离线缓存（详见 CHANGELOG）。用户口径六条：
  ① 飞行模式 / 不挂代理时宿主自己也没有字幕（它是**每次播放音轨时在线抓取**的）；
  ② 缓存范围默认「全部在线播过的轨」，自动 LRU；
  ③ 设置页「其它」加「字幕缓存功能」开关 + 「清除所有字幕缓存」按钮；
  ④ 播放页右上角加一枚「字幕缓存」胶囊，锚在**官方 CC 按钮的左边**（CC 缺席时占它的位），
     **会话级、默认关**；关着时照旧抓在线字幕；
  ⑤ 默认上限 **256MB**，超出后按最早缓存顺序淘汰；
  ⑥ 身份认 `(trackCount, durationMs, currentIndex)` 指纹，并投入 Phase 3 的
     标题 / 媒体源 URI 确认通道（作品键正向校验）使其更稳。

验六件事：
  A. **新增物**是否真编进包（正向锚：1007 有 / 1006 无）——
     新类 SubtitleCache（+ Entry 内部类）、11 个公开方法、6 个字段、
     仓库 9 个新成员、总线/设置页/两 hook 的新签名、模块初始化落点。
  B. **常量层**（`dexdump -d` 字段定义的 `value :`）—— 新增 256MB / 3min / 索引 schema /
     簇宽比 / 深度上限 / 密码位；且**既有** PlaylistKey 三个权重与仓库时限一个都不许被动过。
  C. **调用链**（方法体里的指令序列）—— 落盘真的走了原子写 + LRU 收口；补盖真的做时间轴校验；
     命中真的做作品键正向校验；仓库真的把读写接进**宿主进程**；总线真的「清完/查完都回一条」；
     设置页真的广播 + 二次确认；两 hook 真的走 `getTag()` 取 testID + `contains` 判定 + 三档锚点阶梯。
  D. **负向锚**：1006 包里这些新物**都不存在**（证明区分力），且旧横幅串在 1007 包里消失。
  E. **保持型**：1006 的机器（作品键通道 / 五参判定 / 四条认领路径 / 按实例记账）一件都不许丢。
  F. **【code 1012】删除类 + 自动来源策略**（删除类锚要用第三参 = 上一版包做反向对照）——
     ① 播放页「字幕缓存」胶囊整套（显隐门 / 建按钮 / 落位 / 隐藏 / 观察者 / 拖动跟随 / 静态字段 /
        门控快照 / 视图 id 常量）**在 1012 已删**，而 1011 **曾有**；
     ② 仓库「会话级手动开关」三件套（setLocalCacheMode / isLocalCacheMode /
        hasLocalCacheForCurrentTrack）+ 字段 localCacheMode + tryResumeFromDiskNow
        + 旧落盘 maybeCacheToDisk 同样删净；
     ③ 新增物：stageCacheToDisk / flushStagedCache / isOffline / stagedCache* 五字段 /
        CACHE_FLUSH_FALLBACK_MS=2500；INDEX_SCHEMA 1 → 2；常开横幅 → code 1012。

⚠️ 写本脚本时按**本项目已有铁律**规避的四类坑（都实测过，别再犯）：
   ① **编译期常量不进指令行** ⇒ `LIMIT_BYTES_DEF` / `WORK_KEY_FRESH_MS` /
      `IDENTITY_TC_SCALE` / `CACHE_FLUSH_FALLBACK_MS` / `RemoteConfig.SUBTITLE_CACHE*` 这些
      静态 final 常量会被 javac 内联成 `const*` 立即数，字段名**不会**出现在方法体里。
      ⇒ 要证「用了它」只能钉**内联后的立即数**（见下方注释里的 hex 注释形态），
        或钉字段定义本身的 `value :`（那属于 B 段常量层）。两者分工不同，别混。
   ② **lambda / 匿名类会搬家** ⇒ `flushStagedCache` 里的 `put` 调用实际落在
      `lambda$flushStagedCache$N` 合成方法里（且顺序不稳定 ⇒ 全取再 any）；
      `registerCacheStatsReceiver` 的 `onReceive`
      落在某个 `SettingsActivity$N` 匿名类里。**不要钉 `$N` 的数字**（会随编译漂移），
      要用正则匹配 `lambda$<名字>\$\\d+` 或「遍历该类的所有内部类找一个 onReceive」。
   ③ dex 字符串池与指令行里，字符串是**带引号**的（`"subtitle_cache"`）；而
      `all_dex_text`（原始池）里**不带**引号。两个 API 的判据形态不同，别搞反。
   ④ 寄存器号会随编译变化 ⇒ 判据只钉**助记符 + 字段/方法名/立即数**，不钉 `v3`/`v9`。
      也**不要**写「两符号之间 ≤N 字符」这类距离判据（dexdump 指令行长度不定）。

用法：
    python tools/verify_1007.py <apk_主验> <apk_对照> [<apk_上一版>]
主验 = code 1012 包；对照 = code 1006 包（1007 新功能的唯一区分力基准）；
第三参（可选）= code 1011 包 —— 仅供「本轮删除类」锚（add_gone）做**反向对照**：
那些符号是 1007/1011 引进、1012 删掉的，1006 两版都没有（拿它当对照只会判「无区分力」）。
"""
import os
import re
import subprocess
import sys
import tempfile
import zipfile

DEXDUMP = os.environ.get(
    'DEXDUMP',
    r'F:\WorkBuddyCache\DLSiteSound_Plus\toolchain\android-sdk\build-tools\34.0.0\dexdump.exe'
)

C_CACHE = 'Lio/github/ariinyume/dlsitesoundfloat/data/SubtitleCache;'
C_ENTRY = 'Lio/github/ariinyume/dlsitesoundfloat/data/SubtitleCache$Entry;'
C_KEY = 'Lio/github/ariinyume/dlsitesoundfloat/data/PlaylistKey;'
C_REPO = 'Lio/github/ariinyume/dlsitesoundfloat/data/SubtitleRepository;'
C_BUS = 'Lio/github/ariinyume/dlsitesoundfloat/config/ConfigBus;'
C_PROTO = 'Lio/github/ariinyume/dlsitesoundfloat/config/Protocol;'
C_SCFG = 'Lio/github/ariinyume/dlsitesoundfloat/config/SubtitleConfig;'
C_RCFG = 'Lio/github/ariinyume/dlsitesoundfloat/config/RemoteConfig;'
C_I18N = 'Lio/github/ariinyume/dlsitesoundfloat/util/I18n;'
C_STR = 'Lio/github/ariinyume/dlsitesoundfloat/ui/Strings;'
C_SETT = 'Lio/github/ariinyume/dlsitesoundfloat/ui/SettingsActivity;'
C_SVH = 'Lio/github/ariinyume/dlsitesoundfloat/hook/SubtitleViewHook;'
C_SRES = 'Lio/github/ariinyume/dlsitesoundfloat/hook/SubtitleViewHook$ScanResult;'
C_ABH = 'Lio/github/ariinyume/dlsitesoundfloat/hook/ActivityButtonHook;'
C_MOD1 = 'Lio/github/ariinyume/dlsitesoundfloat/DlsiteSoundSubtitleModule$1;'
C_PSRC = 'Lio/github/ariinyume/dlsitesoundfloat/hook/PlayerSourceHook;'


def dex_blobs(apk):
    out = []
    with zipfile.ZipFile(apk) as z:
        for n in z.namelist():
            m = re.match(r'classes(\d*)\.dex$', n)
            if m:
                out.append((int(m.group(1) or 0), n, z.read(n)))
    out.sort(key=lambda x: x[0])
    return out


def all_dex_text(apk):
    return b'\n'.join(b for _, _, b in dex_blobs(apk))


def dump_all(apk, tmp):
    os.makedirs(tmp, exist_ok=True)
    tag = os.path.basename(apk)
    parts = []
    for _, name, blob in dex_blobs(apk):
        p = os.path.join(tmp, '%s.%s' % (tag, name))
        with open(p, 'wb') as f:
            f.write(blob)
        dp = p + '.dump'
        subprocess.run([DEXDUMP, '-d', p],
                       stdout=open(dp, 'w', encoding='utf-8', errors='replace'),
                       check=False)
        parts.append(open(dp, encoding='utf-8', errors='replace').read())
    return '\n'.join(parts)


def slice_class(dump, cls):
    for pat in ("Class descriptor  : '%s'" % cls, 'Class descriptor  : %s' % cls):
        if pat in dump:
            i = dump.index(pat)
            m = re.search(r'\n\s*Class #\d+\s', dump[i + len(pat):])
            j = i + len(pat) + (m.start() if m else len(dump))
            return dump[i:j]
    return None


def field_value(class_seg, fname):
    """从类的 field 段里取 `value :`（静态常量的**数值真源**）。

    ⚠️ 本函数的返回值只对**数值型**字段有意义（int/long/float/double）。
    String 常量在这里取不到（`value : "..."` 不是纯数字），要用 `all_dex_text` 查串。
    """
    if class_seg is None:
        return None
    m = re.search(r"name\s+:\s+'%s'\s*\n\s*type\s+:\s*'[^']*'\s*\n\s*access\s+:\s*[^\n]*\n"
                  r"\s*value\s+:\s*(-?\d+)" % re.escape(fname), class_seg)
    return int(m.group(1)) if m else None


def has_field(class_seg, name, typ=None):
    """判「类的**字段段**里有这个字段（可选钉类型）」。

    ⚠️ 铁律：dexdump 的**字段段**是 `name :` / `type :` **分行**写的 —— 没有
    `名字:类型` 连写（那**只在指令行**的 iget/iput/sget 操作数里出现）。
    ⇒ 判「字段存在」必须走本函数；判「字段被读写」才用 `.X:T` 连写形式。
    两者的区别正是「编译期常量字段」的陷阱：常量的字段名**永不进指令行**（被内联），
    所以 `.LIMIT_BYTES_DEF:J` 永远查不到，只能靠本函数看字段定义。
    """
    if class_seg is None:
        return False
    if typ is None:
        return re.search(r"name\s+:\s+'%s'\s*\n" % re.escape(name), class_seg) is not None
    return re.search(r"name\s+:\s+'%s'\s*\n\s*type\s+:\s*'%s'\s*\n"
                     % (re.escape(name), re.escape(typ)), class_seg) is not None


def method_body(class_seg, name):
    """按 dexdump 的方法头切出**单个方法**的完整代码块（切到下一个方法头/类尾）。"""
    if not class_seg:
        return None
    m = re.search(r"name\s+:\s+'%s'\s*\n" % re.escape(name), class_seg)
    if not m:
        return None
    nxt = re.search(r'\n\s+#\d+\s+: \(in ', class_seg[m.end():])
    return class_seg[m.start():m.end() + (nxt.start() if nxt else len(class_seg))]


def lambda_body(class_seg, name_prefix):
    """找一个合成 lambda 方法体（`lambda$<name_prefix>$N`）—— 不钉 N（会漂移）。"""
    if not class_seg:
        return ''
    m = re.search(r"name\s+:\s*'lambda\$%s\$\d+'\s*\n" % re.escape(name_prefix), class_seg)
    if not m:
        return ''
    nxt = re.search(r'\n\s+#\d+\s+: \(in ', class_seg[m.end():])
    return class_seg[m.start():m.end() + (nxt.start() if nxt else len(class_seg))]


def lambda_bodies(class_seg, name_prefix):
    """取**全部** `lambda$<name_prefix>$N` 合成方法体（列表）。

    ⚠️ 同一个宿主方法里可能有多条 lambda（如 flushStagedCache 既有落盘 lambda、
    又有 postDelayed 的刷新 lambda），而**合成方法的先后顺序不稳定** ⇒
    只取第一个会踩空，必须全取再 any()。
    """
    if not class_seg:
        return []
    out = []
    for m in re.finditer(r"name\s+:\s*'lambda\$%s\$\d+'\s*\n" % re.escape(name_prefix),
                         class_seg):
        nxt = re.search(r'\n\s+#\d+\s+: \(in ', class_seg[m.end():])
        out.append(class_seg[m.start():m.end() + (nxt.start() if nxt else len(class_seg))])
    return out


def method_body_typed(class_seg, name, typ):
    """按「名字 + **描述符**」切方法体 —— 重载方法必须用它。

    ⚠️ 铁律：`method_body(name)` 只按名字找，遇到**同名重载**（本项目
    SubtitleRepository 有 4 个 onTrackChanged）会切到**第一个**（往往是 1 参那个），
    判据静默假 FAIL。凡目标方法有重载，一律走本函数。
    """
    if not class_seg:
        return None
    m = re.search(r"name\s+:\s*'%s'\s*\n\s*type\s+:\s*'%s'\s*\n"
                  % (re.escape(name), re.escape(typ)), class_seg)
    if not m:
        return None
    nxt = re.search(r'\n\s+#\d+\s+: \(in ', class_seg[m.end():])
    return class_seg[m.start():m.end() + (nxt.start() if nxt else len(class_seg))]


def inner_on_receive(dump, outer_cls, needle):
    """在 `outer_cls` 的**所有内部类**里找一个 `onReceive` 且其体内含 needle。

    ⚠️ 匿名类编号（SettingsActivity$1 / $2 …）会随编译漂移 ⇒ 只能这样遍历找，别钉数字。
    """
    return inner_method_contains(dump, outer_cls, 'onReceive', needle)


def inner_method_contains(dump, outer_cls, method, needle):
    """在 `outer_cls` 的所有内部类里找一个 `method`，其体内含 needle（避开匿名类编号）。

    `outer_cls` 传完整描述符（如 `L…/SettingsActivity;`）；内部类描述符形如
    `L…/SettingsActivity$2;`。
    """
    pat = re.compile(r"Class descriptor  : '(%s\$[^']*)'" % re.escape(outer_cls[:-1]))
    for m in pat.finditer(dump):
        seg = slice_class(dump, m.group(1))
        body = method_body(seg, method)
        if body and needle in body:
            return True
    return False


class Checker:
    def __init__(self):
        self.rows = []
        self.fails = 0

    def add(self, label, hit_new, hit_old):
        v = 'OK 有区分力' if (hit_new and not hit_old) else (
            '!! 无区分力(两版都成立)' if hit_new else 'FAIL 未命中（新包没有）')
        if v != 'OK 有区分力':
            self.fails += 1
        self.rows.append((label, hit_new, hit_old, v))

    def add_keep(self, label, ok_new, ok_old=None):
        v = 'OK 保持' if ok_new else 'FAIL 功能丢失（新包没有）'
        if not ok_new:
            self.fails += 1
        self.rows.append((label, ok_new, ok_old, v))

    def add_diff(self, label, ok_new, ok_old):
        """方法体类断言专用：要求「新包成立 **且** 对照包不成立」才算有区分力。"""
        if ok_new and not ok_old:
            v = 'OK 有区分力'
        elif ok_new and ok_old:
            v = '!! 无区分力(两版都成立)'
        else:
            v = 'FAIL 未命中（新包没有）'
        if v != 'OK 有区分力':
            self.fails += 1
        self.rows.append((label, ok_new, ok_old, v))

    def add_gone(self, label, gone_new, present_prev):
        """**删除类**断言：要求「主验包**没有** **且** 上一版**有**」才算有区分力。

        ⚠️ 这类锚**不能**拿 1006 当对照 —— 这些符号本来就是 1007/1011 才引入的，
        1006 两版都没有，用 add() 会判成「无区分力」。反向对照必须是**上一版**包
        （3 号命令行参数），否则说明「压根没提供删除类锚需要的那一半证据」。
        """
        if gone_new and present_prev:
            v = 'OK 有区分力(已移除)'
        elif gone_new:
            v = '!! 无区分力(上一版也没有)'
            self.fails += 1
        else:
            v = 'FAIL 未移除（主验包还在）'
            self.fails += 1
        self.rows.append((label, gone_new, present_prev, v))

    def add_const(self, label, exp, new_v, old_v):
        ok = (new_v == exp)
        if not ok:
            v = 'FAIL 值不对（新包 %s，期望 %s）' % (new_v, exp)
            self.fails += 1
        elif old_v == exp:
            v = '!! 无区分力(旧包同值)'
            self.fails += 1
        elif old_v is None:
            v = 'OK 有区分力(旧包无此字段 → %s)' % new_v
        else:
            v = 'OK 有区分力(%s → %s)' % (old_v, new_v)
        self.rows.append((label, new_v, old_v, v))

    def add_const_keep(self, label, exp, new_v, old_v):
        ok = (new_v == exp)
        v = 'OK 保持(%s)' % new_v if ok else 'FAIL 值不对（新包 %s，期望 %s）' % (new_v, exp)
        if not ok:
            self.fails += 1
        self.rows.append((label, new_v, old_v, v))

    def add_manual(self, label, ok, detail=''):
        v = 'OK' if ok else 'FAIL ' + detail
        if not ok:
            self.fails += 1
        self.rows.append((label, None, None, v))

    def report(self):
        print()
        print('=' * 96)
        print('code 1007~1012 —— dex 验证'
              '（主验 1012 / 对照 1006 / 反向对照 1011）')
        print('=' * 96)
        for label, a, b, v in self.rows:
            fa = 'Y' if a is True else (a if isinstance(a, int) else '.' if a is False else '-')
            fb = 'Y' if b is True else (b if isinstance(b, int) else '.' if b is False else '-')
            print('%-7s %-7s %s' % (fa, fb, label))
        print()
        anchors = sum(1 for r in self.rows if '有区分力' in r[3])
        print('  断言 %d 项，其中有区分力锚 %d 个' % (len(self.rows), anchors))
        if self.fails:
            print('FAIL %d/%d' % (self.fails, len(self.rows)))
            for label, a, b, v in self.rows:
                if v.startswith('!!') or v.startswith('FAIL'):
                    print('   x %s  [%s]' % (label, v))
            return 1
        print('PASS %d/%d' % (len(self.rows), len(self.rows)))
        return 0


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    apk_new, apk_old = sys.argv[1], sys.argv[2]
    apk_prev = sys.argv[3] if len(sys.argv) > 3 else None
    tmp = os.environ.get('TMP', tempfile.gettempdir())
    print('主验 =', os.path.basename(apk_new))
    print('对照 =', os.path.basename(apk_old))
    print('上一版 =', os.path.basename(apk_prev) if apk_prev
          else '(未提供 → 所有 add_gone 删除类锚会判 FAIL，请补第三个参数)')

    tn, to = all_dex_text(apk_new), all_dex_text(apk_old)
    dn, do = dump_all(apk_new, tmp), dump_all(apk_old, tmp)
    tp = all_dex_text(apk_prev) if apk_prev else b''
    dp = dump_all(apk_prev, tmp) if apk_prev else ''

    def new(s):
        return s.encode() in tn

    def old(s):
        return s.encode() in to

    def cn(d, cls):
        return slice_class(d, cls)

    ca_n, ca_o = cn(dn, C_CACHE), cn(do, C_CACHE)
    en_n, en_o = cn(dn, C_ENTRY), cn(do, C_ENTRY)
    kn, ko = cn(dn, C_KEY), cn(do, C_KEY)
    rn, ro = cn(dn, C_REPO), cn(do, C_REPO)
    bn, bo = cn(dn, C_BUS), cn(do, C_BUS)
    pn, po = cn(dn, C_PROTO), cn(do, C_PROTO)
    scn, sco = cn(dn, C_SCFG), cn(do, C_SCFG)
    rcn, rco = cn(dn, C_RCFG), cn(do, C_RCFG)
    ien, ieo = cn(dn, C_I18N), cn(do, C_I18N)
    stn, sto = cn(dn, C_STR), cn(do, C_STR)
    sen, seo = cn(dn, C_SETT), cn(do, C_SETT)
    svn, svo = cn(dn, C_SVH), cn(do, C_SVH)
    sr_n, _ = cn(dn, C_SRES), None
    an, ao = cn(dn, C_ABH), cn(do, C_ABH)
    # 【code 1012】第三参（上一版）的类段 —— 仅供「删除类」锚 add_gone 做反向对照
    ap = cn(dp, C_ABH) if apk_prev else None
    rp = cn(dp, C_REPO) if apk_prev else None
    cp = cn(dp, C_CACHE) if apk_prev else None

    def prev_txt(s):
        return s.encode() in tp
    psn, pso = cn(dn, C_PSRC), cn(do, C_PSRC)
    m1n, m1o = cn(dn, C_MOD1), cn(do, C_MOD1)
    ck = Checker()

    # ══════════════ A. 新增物（正向锚：1007 有 / 1006 无）══════════════
    ck.add('1★ 新类 SubtitleCache（字幕磁盘缓存数据层）',
           ca_n is not None, ca_o is not None)
    ck.add('2★ 内部类 SubtitleCache$Entry（单条元数据；字段名即 index.json 的键名）',
           en_n is not None, en_o is not None)
    ck.add('3★ SubtitleCache.get:()L…/SubtitleCache;（单例）',
           'get:()Lio/github/ariinyume/dlsitesoundfloat/data/SubtitleCache;' in (ca_n or ''),
           'get:()Lio/github/ariinyume/dlsitesoundfloat/data/SubtitleCache;' in (ca_o or ''))
    ck.add('4★ SubtitleCache.init:(Landroid/content/Context;)V（幂等初始化，只在宿主进程）',
           'init:(Landroid/content/Context;)V' in (ca_n or ''),
           'init:(Landroid/content/Context;)V' in (ca_o or ''))
    ck.add('5★ SubtitleCache.put:(Ljava/lang/String;IIJLjava/lang/String;ID)V（落盘一条）',
           'put:(Ljava/lang/String;IIJLjava/lang/String;ID)V' in (ca_n or ''),
           'put:(Ljava/lang/String;IIJLjava/lang/String;ID)V' in (ca_o or ''))
    ck.add('6★ SubtitleCache.stampDuration:(JJ)V（时长补盖 + 时间轴交叉校验）',
           'stampDuration:(JJ)V' in (ca_n or ''),
           'stampDuration:(JJ)V' in (ca_o or ''))
    ck.add('7★ SubtitleCache.lookup:(JJLjava/lang/String;)Ljava/lang/String;（三参：身份 + 选择 + 当前作品键）',
           'lookup:(JJLjava/lang/String;)Ljava/lang/String;' in (ca_n or ''),
           'lookup:(JJLjava/lang/String;)Ljava/lang/String;' in (ca_o or ''))
    ck.add('8★ SubtitleCache.has:(JJ)Z（播放页按钮用：只查内存索引，不读盘）',
           'has:(JJ)Z' in (ca_n or ''),
           'has:(JJ)Z' in (ca_o or ''))
    ck.add('9★ SubtitleCache.clearAll:()V（设置页「清除所有字幕缓存」的落点）',
           'clearAll:()V' in (ca_n or ''),
           'clearAll:()V' in (ca_o or ''))
    ck.add('10★ SubtitleCache.count/bytes/limitBytes（设置页占用读数的三个 getter）',
           all(s in (ca_n or '') for s in ('count:()I', 'bytes:()J', 'limitBytes:()J')),
           all(s in (ca_o or '') for s in ('count:()I', 'bytes:()J', 'limitBytes:()J')))
    ck.add('11★ 字段 SubtitleCache.LIMIT_BYTES_DEF:J（容量上限真源；常量→只看字段段）',
           has_field(ca_n, 'LIMIT_BYTES_DEF', 'J'),
           has_field(ca_o, 'LIMIT_BYTES_DEF', 'J'))
    ck.add('12★ 字段 SubtitleCache.sInstance（volatile 单例）',
           ".sInstance:Lio/github/ariinyume/dlsitesoundfloat/data/SubtitleCache;" in (ca_n or ''),
           ".sInstance:Lio/github/ariinyume/dlsitesoundfloat/data/SubtitleCache;" in (ca_o or ''))
    ck.add('13★ PlaylistKey.makeIdentity:(IDI)J 升为 public（缓存的身份口径与换轨判据同源）',
           'makeIdentity:(IDI)J' in (kn or ''), 'makeIdentity:(IDI)J' in (ko or ''))
    ck.add('14★ PlaylistKey.identityDurationMs:(J)J（从身份键反解时长，补盖用）',
           'identityDurationMs:(J)J' in (kn or ''), 'identityDurationMs:(J)J' in (ko or ''))
    ck.add_gone('15★ 【code 1012】仓库 setLocalCacheMode:(Z)V 已删（会话级手动开关，上一版曾有）',
                'setLocalCacheMode:(Z)V' not in (rn or ''),
                'setLocalCacheMode:(Z)V' in (rp or ''))
    ck.add_gone('16★ 【code 1012】仓库 isLocalCacheMode:()Z 已删（按钮态回读）',
                'isLocalCacheMode:()Z' not in (rn or ''),
                'isLocalCacheMode:()Z' in (rp or ''))
    ck.add_gone('17★ 【code 1012】仓库 hasLocalCacheForCurrentTrack:()Z 已删（按钮显隐门）',
                'hasLocalCacheForCurrentTrack:()Z' not in (rn or ''),
                'hasLocalCacheForCurrentTrack:()Z' in (rp or ''))
    ck.add('18★ 仓库 cacheUsable:()Z（【code 1012】只看配置总闸）',
           'cacheUsable:()Z' in (rn or ''), 'cacheUsable:()Z' in (ro or ''))
    ck.add('19★ 仓库 freshWorkKey:()Ljava/lang/String;（作品键新鲜窗口，防误拒）',
           'freshWorkKey:()Ljava/lang/String;' in (rn or ''),
           'freshWorkKey:()Ljava/lang/String;' in (ro or ''))
    ck.add('20★ 仓库 tryResumeFromDisk:(Ljava/lang/String;JJ)Z（换轨时读盘）',
           'tryResumeFromDisk:(Ljava/lang/String;JJ)Z' in (rn or ''),
           'tryResumeFromDisk:(Ljava/lang/String;JJ)Z' in (ro or ''))
    ck.add_gone('21★ 【code 1012】仓库 tryResumeFromDiskNow:()V 已删'
                '（会话级开关的「立即读盘」入口）',
                'tryResumeFromDiskNow:()V' not in (rn or ''),
                'tryResumeFromDiskNow:()V' in (rp or ''))
    ck.add('22★ 仓库 refreshLocalCacheAvailability:(J)V（刷新「本轨有没有缓存」）',
           'refreshLocalCacheAvailability:(J)V' in (rn or ''),
           'refreshLocalCacheAvailability:(J)V' in (ro or ''))
    ck.add_gone('23★ 【code 1012】仓库 maybeCacheToDisk 已删（改为「先暂存 stageCacheToDisk」）',
                'maybeCacheToDisk:(Ljava/lang/String;IIID)V' not in (rn or ''),
                'maybeCacheToDisk:(Ljava/lang/String;IIID)V' in (rp or ''))
    ck.add_gone('24★ 【code 1012】字段 SubtitleRepository.localCacheMode:Z 已删（会话级手动开关）',
                '.localCacheMode:Z' not in (rn or ''), '.localCacheMode:Z' in (rp or ''))
    ck.add('24a★ 【code 1012】仓库 stageCacheToDisk:(Ljava/lang/String;ID)V'
           '（先暂存，等权威轨标签）',
           'stageCacheToDisk:(Ljava/lang/String;ID)V' in (rn or ''),
           'stageCacheToDisk:(Ljava/lang/String;ID)V' in (ro or ''))
    ck.add('24b★ 【code 1012】仓库 flushStagedCache:(J)V（拿到权威选择键后兑现落盘）',
           'flushStagedCache:(J)V' in (rn or ''),
           'flushStagedCache:(J)V' in (ro or ''))
    ck.add('24c★ 【code 1012】仓库 isOffline:()Z（无活动网络 ⇒ 直接读盘，不干等裁决窗）',
           'isOffline:()Z' in (rn or ''), 'isOffline:()Z' in (ro or ''))
    ck.add('24d★ 【code 1012】仓库暂存四件套字段 + 代数令牌'
           '（stagedCacheJson / WorkKey / Cues / MaxEnd / Token）',
           all(s in (rn or '') for s in (
               '.stagedCacheJson:Ljava/lang/String;', '.stagedCacheWorkKey:Ljava/lang/String;',
               '.stagedCacheCues:I', '.stagedCacheMaxEnd:D', '.stagedCacheToken:J')),
           False)
    ck.add('25★ 字段 SubtitleRepository.localCacheAvailable:Z（【code 1012】降为纯诊断读数）',
           '.localCacheAvailable:Z' in (rn or ''), '.localCacheAvailable:Z' in (ro or ''))
    ck.add('26★ 字段 SubtitleRepository.lastSeenWorkKeyAtMs:J（作品键新鲜度记账）',
           '.lastSeenWorkKeyAtMs:J' in (rn or ''), '.lastSeenWorkKeyAtMs:J' in (ro or ''))
    ck.add('27★ 字段 SubtitleRepository.lastCacheableJson:Ljava/lang/String;（要落盘的字幕原文）',
           '.lastCacheableJson:Ljava/lang/String;' in (rn or ''),
           '.lastCacheableJson:Ljava/lang/String;' in (ro or ''))
    ck.add('28★ 字段 SubtitleRepository.cacheIo:ExecutorService（盘 IO 不占主线程）',
           '.cacheIo:Ljava/util/concurrent/ExecutorService;' in (rn or ''),
           '.cacheIo:Ljava/util/concurrent/ExecutorService;' in (ro or ''))
    ck.add('29★ 配置键 K_SUBTITLE_CACHE_ENABLED（subtitle_cache_enabled）',
           'K_SUBTITLE_CACHE_ENABLED' in (scn or ''),
           'K_SUBTITLE_CACHE_ENABLED' in (sco or ''))
    ck.add('30★ 配置字段 SubtitleConfig.subtitleCacheEnabled:Z（默认开）',
           '.subtitleCacheEnabled:Z' in (scn or ''), '.subtitleCacheEnabled:Z' in (sco or ''))
    ck.add('31★ RemoteConfig.subtitleCacheEnabled:()Z（远方读配置总闸）',
           'subtitleCacheEnabled:()Z' in (rcn or ''),
           'subtitleCacheEnabled:()Z' in (rco or ''))
    ck.add('32★ 总线 ConfigBus.handleCacheClear:(Landroid/content/Context;Ljava/lang/String;)V',
           'handleCacheClear:(Landroid/content/Context;Ljava/lang/String;)V' in (bn or ''),
           'handleCacheClear:(Landroid/content/Context;Ljava/lang/String;)V' in (bo or ''))
    ck.add('33★ 总线 ConfigBus.answerCacheStats:(Landroid/content/Context;Ljava/lang/String;)V',
           'answerCacheStats:(Landroid/content/Context;Ljava/lang/String;)V' in (bn or ''),
           'answerCacheStats:(Landroid/content/Context;Ljava/lang/String;)V' in (bo or ''))
    ck.add('34★ 总线 ConfigBus.sendCacheStats:(Landroid/content/Context;IJ)V（宿主 → 设置页回执）',
           'sendCacheStats:(Landroid/content/Context;IJ)V' in (bn or ''),
           'sendCacheStats:(Landroid/content/Context;IJ)V' in (bo or ''))
    ck.add('35★ 总线 ConfigBus.sendCacheClear:(Landroid/content/Context;)V（设置页 → 宿主）',
           'sendCacheClear:(Landroid/content/Context;)V' in (bn or ''),
           'sendCacheClear:(Landroid/content/Context;)V' in (bo or ''))
    ck.add('36★ 总线 ConfigBus.sendCacheStatsRequest:(Landroid/content/Context;)V',
           'sendCacheStatsRequest:(Landroid/content/Context;)V' in (bn or ''),
           'sendCacheStatsRequest:(Landroid/content/Context;)V' in (bo or ''))
    ck.add('37★ I18n.cacheOn/cacheOff:()Ljava/lang/String;'
           '（【code 1012】胶囊已删，文案保留作量宽样本）',
           'cacheOn:()Ljava/lang/String;' in (ien or '')
           and 'cacheOff:()Ljava/lang/String;' in (ien or ''),
           'cacheOn:()Ljava/lang/String;' in (ieo or '')
           and 'cacheOff:()Ljava/lang/String;' in (ieo or ''))
    ck.add('38★ 设置页 SettingsActivity.buildSubtitleCacheRow:(Landroid/widget/LinearLayout;)V',
           'buildSubtitleCacheRow:(Landroid/widget/LinearLayout;)V' in (sen or ''),
           'buildSubtitleCacheRow:(Landroid/widget/LinearLayout;)V' in (seo or ''))
    ck.add('39★ 设置页 onClearCacheClicked/applyCacheStats/renderCacheUsage/fmtBytes',
           all(s in (sen or '') for s in (
               'onClearCacheClicked:()V', 'applyCacheStats:(IJ)V',
               'renderCacheUsage:()V', 'fmtBytes:(J)Ljava/lang/String;')),
           all(s in (seo or '') for s in (
               'onClearCacheClicked:()V', 'applyCacheStats:(IJ)V',
               'renderCacheUsage:()V', 'fmtBytes:(J)Ljava/lang/String;')))
    ck.add('40★ 设置页 onDestroy:()V（本轮新增：注销缓存统计接收器）',
           'onDestroy:()V' in (sen or ''), 'onDestroy:()V' in (seo or ''))
    ck.add('41★ 视图树 hook：probeOfficialToolbar:(Landroid/view/View;L…/ScanResult;)V',
           'probeOfficialToolbar:(Landroid/view/View;'
           'Lio/github/ariinyume/dlsitesoundfloat/hook/SubtitleViewHook$ScanResult;)V'
           in (svn or ''),
           'probeOfficialToolbar' in (svo or ''))
    ck.add('42★ 视图树 hook：trailingToolbarClusterRect:(Ljava/lang/ref/WeakReference;)[I（兜底锚点）',
           'trailingToolbarClusterRect:(Ljava/lang/ref/WeakReference;)[I' in (svn or ''),
           'trailingToolbarClusterRect' in (svo or ''))
    ck.add('43★ ScanResult 新增字段 ccFound/ccButtonRef/ccRect/closeFound/closeButtonRef/trailingClusterRect',
           all(has_field(sr_n, n, t) for n, t in (
               ('ccFound', 'Z'), ('ccButtonRef', 'Ljava/lang/ref/WeakReference;'),
               ('ccRect', '[I'), ('closeFound', 'Z'),
               ('closeButtonRef', 'Ljava/lang/ref/WeakReference;'),
               ('trailingClusterRect', '[I'))),
           False)
    _CAPSULE_SYMS = (
        '.sCacheButton:Landroid/widget/TextView;', '.sLastCcRect:[I',
        '.sHasLastCcRect:Z', '.sCachePlacedAt:[I', '.sCacheVisible:Z',
        '.sCacheAnchorSrc:Ljava/lang/String;')
    ck.add_gone('44★ 【code 1012】播放页 hook：cacheButtonWanted:(L…/SubtitleRepository;)Z 已删',
                'cacheButtonWanted' not in (an or ''), 'cacheButtonWanted' in (ap or ''))
    ck.add_gone('45★ 【code 1012】播放页 hook：ensureCacheButton:(Landroid/app/Activity;…)'
                'Landroid/widget/TextView; 已删',
                'ensureCacheButton' not in (an or ''), 'ensureCacheButton' in (ap or ''))
    ck.add_gone('46★ 【code 1012】播放页 hook：layoutCacheButton（三档锚点阶梯）已删',
                'layoutCacheButton' not in (an or ''), 'layoutCacheButton' in (ap or ''))
    ck.add_gone('47★ 【code 1012】播放页 hook：hideCacheButton / applyCacheButtonState 已删',
                'hideCacheButton' not in (an or '')
                and 'applyCacheButtonState' not in (an or ''),
                'hideCacheButton' in (ap or '') or 'applyCacheButtonState' in (ap or ''))
    ck.add_gone('48★ 【code 1012】播放页 hook：胶囊六个静态字段已删',
                not any(s in (an or '') for s in _CAPSULE_SYMS),
                any(s in (ap or '') for s in _CAPSULE_SYMS))
    # ⚠️ 1007~1010 的日志串仍在；[code 1011] 的串**只在胶囊代码里**，已随胶囊移除
    #   （1011 从未上真机 ⇒ 没有「必须保留的现场证据」；见 181★ 的负向锚）。
    _MILESTONES = (1007, 1008, 1009, 1010, 1012)
    ck.add('49★ 里程碑日志串 [code 1007] / 1008 / 1009 / 1010 / 1012 都在',
           all(new('[code %d]' % c) for c in _MILESTONES),
           any(old('[code %d]' % c) for c in _MILESTONES))
    ck.add('50★ 配置键字面量 subtitle_cache_enabled', new('subtitle_cache_enabled'),
           old('subtitle_cache_enabled'))
    ck.add('51★ 新 action 字面量 SUBTITLE_CACHE_CLEAR',
           new('io.github.ariinyume.dlsitesoundfloat.action.SUBTITLE_CACHE_CLEAR'),
           old('io.github.ariinyume.dlsitesoundfloat.action.SUBTITLE_CACHE_CLEAR'))
    ck.add('52★ 新 action 字面量 SUBTITLE_CACHE_STATS_REQ / SUBTITLE_CACHE_STATS',
           new('io.github.ariinyume.dlsitesoundfloat.action.SUBTITLE_CACHE_STATS_REQ'),
           old('io.github.ariinyume.dlsitesoundfloat.action.SUBTITLE_CACHE_STATS_REQ'))
    ck.add('53★ 缓存目录/索引文件名字面量（subtitle_cache / index.json）',
           new('subtitle_cache') and new('index.json'),
           old('subtitle_cache') or old('index.json'))
    # 【code 1015】改名后**必须用零终止匹配** —— 「字幕缓存」是「字幕缓存功能」的**子串**，
    #   裸串在两版都命中、判据会假装两版一样（dex 的 string_data_item 本身是零终止的）。
    ck.add('54★ 三语文案（简/繁/英各取一条，证 enum 三语齐全；【code 1015】已改名「字幕缓存」）',
           new('字幕缓存\x00') and new('字幕快取\x00') and new('Subtitle cache\x00'),
           old('字幕缓存功能\x00') or old('字幕快取功能\x00') or old('Subtitle cache\x00'))
    ck.add('55★ 占用读数格式串（含三语占位符）',
           new('已缓存 %1$d 轨 · 占用 %2$s / %3$s') and new('已快取 %1$d 軌 · 佔用 %2$s / %3$s'),
           old('已缓存 %1$d 轨 · 占用 %2$s / %3$s'))
    ck.add('56★ 胶囊文案三语仍在（Cache ON / 快取 開 / 缓存 开；'
           '【code 1012】胶囊已删、文案保留作量宽样本）',
           new('Cache ON') and new('快取 開') and new('缓存 开'),
           old('Cache ON') or old('快取 開') or old('缓存 开'))
    # ⚠️ 判「常开横幅行」必须用**零终止**形态：履历段（`… / code 1006 （【code 1006 —— …`）
    #   保留了同一前缀，只找前缀会两版都命中、失去区分力。dex 的 string_data_item 是
    #   零终止的 ⇒ 在原始池里搜 `… / code 1007\x00` 才是「这条串到此为止」。
    ck.add('57★ 常开横幅行 ==== BUILD 2.3.2 / code 1017（versionName 不动、只升 code）',
           new('[DLsiteSoundFloat] ==== BUILD 2.3.2 / code 1017\x00'),
           old('[DLsiteSoundFloat] ==== BUILD 2.3.2 / code 1017\x00'))
    ck.add('58★ 官方两枚 testID 后缀串（SUBTITLE_BUTTON / FULL_PLAYER_CLOSE_BUTTON）',
           new('SUBTITLE_BUTTON') and new('FULL_PLAYER_CLOSE_BUTTON'),
           old('SUBTITLE_BUTTON') or old('FULL_PLAYER_CLOSE_BUTTON'))

    # ══════════════ B. 常量层（dexdump 字段 value = 数值真源）══════════════
    ck.add_const('59★ SubtitleCache.LIMIT_BYTES_DEF = 268435456（= 256MiB，用户口径；文档旧稿的 128MB 已废）',
                 268435456, field_value(ca_n, 'LIMIT_BYTES_DEF'),
                 field_value(ca_o, 'LIMIT_BYTES_DEF'))
    ck.add_const('60★ 【code 1012】SubtitleCache.INDEX_SCHEMA = 2'
                 '（1 → 2：作废 1007 因「加载时刻选择键」而标错的旧条目）',
                 2, field_value(ca_n, 'INDEX_SCHEMA'), field_value(ca_o, 'INDEX_SCHEMA'))
    ck.add_const('61★ SubtitleCache.TIMELINE_TOLERANCE_SEC = 2（补盖容差秒；dexdump 把 double 2.0 印成 2）',
                 2, field_value(ca_n, 'TIMELINE_TOLERANCE_SEC'),
                 field_value(ca_o, 'TIMELINE_TOLERANCE_SEC'))
    ck.add_const('62★ SubtitleRepository.WORK_KEY_FRESH_MS = 180000（= 3min 作品键新鲜窗口）',
                 180000, field_value(rn, 'WORK_KEY_FRESH_MS'), field_value(ro, 'WORK_KEY_FRESH_MS'))
    ck.add_gone('63★ 【code 1012】ActivityButtonHook.CACHE_BUTTON_ID 字段已删（上一版曾有）',
                field_value(an, 'CACHE_BUTTON_ID') is None,
                field_value(ap, 'CACHE_BUTTON_ID') is not None)
    ck.add_gone('64★ 【code 1012】ActivityButtonHook.CACHE_PLACE_DEADZONE_PX 字段已删',
                field_value(an, 'CACHE_PLACE_DEADZONE_PX') is None,
                field_value(ap, 'CACHE_PLACE_DEADZONE_PX') is not None)
    ck.add_const('65★ SubtitleViewHook.CLUSTER_MAX_DEPTH = 8（兜底下潜层数上限）',
                 8, field_value(svn, 'CLUSTER_MAX_DEPTH'), field_value(svo, 'CLUSTER_MAX_DEPTH'))
    ck.add_const('66★ SubtitleViewHook.CLUSTER_W_RATIO = 3（簇宽 ≤ 收起键宽 × 3；float 3.0f 印成 3）',
                 3, field_value(svn, 'CLUSTER_W_RATIO'), field_value(svo, 'CLUSTER_W_RATIO'))
    ck.add_const('67★ Protocol.PROTOCOL_VERSION 1 → 2（本轮新增三条 cache action）',
                 2, field_value(pn, 'PROTOCOL_VERSION'), field_value(po, 'PROTOCOL_VERSION'))
    for lbl, owner, name, exp in (
        ('68★', 'kn', 'IDENTITY_TC_SCALE', 1000000000000),
        ('69★', 'kn', 'IDENTITY_IDX_SCALE', 1000),
        ('70★', 'kn', 'SELECTION_TC_SCALE', 100000),
        ('71★', 'rn', 'REBUILT_PLAYLIST_CLAIM_MS', 15000),
        ('72★', 'rn', 'NO_SUBTITLE_GRACE_MS', 3000),
        ('73★', 'rn', 'NO_SUBTITLE_GRACE_MS_CACHED', 15000),
    ):
        seg = {'kn': kn, 'rn': rn}[owner]
        seg_o = {'kn': ko, 'rn': ro}[owner]
        ck.add_const_keep('%s 既有常量 %s 一字未动' % (lbl, name), exp,
                          field_value(seg, name), field_value(seg_o, name))

    # ══════════════ C. 调用链（方法体内指令；每条都带对照包读数）══════════════
    def cache_mb(name, side):
        return method_body(ca_n if side == 0 else ca_o, name) or ''

    def repo_mb(name, side):
        return method_body(rn if side == 0 else ro, name) or ''

    def bus_mb(name, side):
        return method_body(bn if side == 0 else bo, name) or ''

    def sett_mb(name, side):
        return method_body(sen if side == 0 else seo, name) or ''

    def svh_mb(name, side):
        return method_body(svn if side == 0 else svo, name) or ''

    def abh_mb(name, side):
        return method_body(an if side == 0 else ao, name) or ''

    # ---- C1 数据层：落盘 / 补盖 / 命中 / 淘汰 ----
    ck.add_diff('74★ init 真的建目录（File.mkdirs）并装载索引（loadIndexLocked）',
                'Ljava/io/File;.mkdirs:()Z' in cache_mb('init', 0)
                and 'loadIndexLocked:()V' in cache_mb('init', 0),
                'loadIndexLocked:()V' in cache_mb('init', 1))
    ck.add_diff('75★ put 先算选择键（makeSelection）再落盘 —— 标签竞态下先挂副键',
                'PlaylistKey;.makeSelection:(II)J' in cache_mb('put', 0),
                'PlaylistKey;.makeSelection:(II)J' in cache_mb('put', 1))
    ck.add_diff('76★ put 落盘走**原子写**（writeFileAtomic：临时文件 + rename）',
                'SubtitleCache;.writeFileAtomic:(Ljava/lang/String;[B)Z' in cache_mb('put', 0),
                'writeFileAtomic' in cache_mb('put', 1))
    ck.add_diff('77★ put 末尾做 LRU 收口（enforceLimitLocked）',
                'enforceLimitLocked:()V' in cache_mb('put', 0),
                'enforceLimitLocked:()V' in cache_mb('put', 1))
    ck.add_diff('78★ put 末尾持久化索引（persistIndexLocked）',
                'persistIndexLocked:()V' in cache_mb('put', 0),
                'persistIndexLocked:()V' in cache_mb('put', 1))
    ck.add_diff('79★ 内容哈希去重：put 真的调 md5，md5 用 MessageDigest("MD5") 生成摘要',
                'SubtitleCache;.md5:(Ljava/lang/String;)Ljava/lang/String;' in cache_mb('put', 0)
                and '"MD5"' in cache_mb('md5', 0)
                and 'Ljava/security/MessageDigest;.getInstance:(Ljava/lang/String;)'
                'Ljava/security/MessageDigest;' in cache_mb('md5', 0),
                'SubtitleCache;.md5:' in cache_mb('put', 1))
    ck.add_diff('80★ 落盘时若时长已就绪即直接算身份键（makeIdentity）—— 否则留孤儿',
                'PlaylistKey;.makeIdentity:(IDI)J' in cache_mb('put', 0),
                'PlaylistKey;.makeIdentity:(IDI)J' in cache_mb('put', 1))
    ck.add_diff('81★ stampDuration 真的反解时长（identityDurationMs）做时间轴交叉校验',
                'PlaylistKey;.identityDurationMs:(J)J' in cache_mb('stampDuration', 0),
                'identityDurationMs:(J)J' in cache_mb('stampDuration', 1))
    ck.add_diff('82★ stampDuration 判完后写回身份并落索引（persistIndexLocked）',
                'persistIndexLocked:()V' in cache_mb('stampDuration', 0)
                and 'byIdentity' in cache_mb('stampDuration', 0),
                'persistIndexLocked:()V' in cache_mb('stampDuration', 1))
    ck.add_diff('83★ lookup 做作品键正向校验（String.equals）—— 跨作品冒充的唯一正证据',
                'Ljava/lang/String;.equals:(Ljava/lang/Object;)Z' in cache_mb('lookup', 0),
                'Ljava/lang/String;.equals:(Ljava/lang/Object;)Z' in cache_mb('lookup', 1))
    ck.add_diff('84★ lookup 命中后读文件（readFile）并刷新 lastUsed（LRU 依据）',
                'SubtitleCache;.readFile:(Ljava/lang/String;)Ljava/lang/String;'
                in cache_mb('lookup', 0)
                and 'persistIndexLocked:()V' in cache_mb('lookup', 0),
                'SubtitleCache;.readFile:(Ljava/lang/String;)Ljava/lang/String;'
                in cache_mb('lookup', 1))
    ck.add_diff('85★ clearAll 逐条删文件（deleteFile）后落索引',
                'SubtitleCache;.deleteFile:(Ljava/lang/String;)V' in cache_mb('clearAll', 0)
                and 'persistIndexLocked:()V' in cache_mb('clearAll', 0),
                'SubtitleCache;.deleteFile:(Ljava/lang/String;)V' in cache_mb('clearAll', 1))
    ck.add_diff('86★ LRU 淘汰真的把条目按序排（Collections.sort + removeEntryLocked 循环）',
                'Ljava/util/Collections;.sort:(Ljava/util/List;Ljava/util/Comparator;)V'
                in cache_mb('enforceLimitLocked', 0)
                and 'SubtitleCache;.removeEntryLocked:' in cache_mb('enforceLimitLocked', 0),
                'Ljava/util/Collections;.sort:(Ljava/util/List;Ljava/util/Comparator;)V'
                in cache_mb('enforceLimitLocked', 1))
    ck.add_diff('87★ 比较器按 used 升序（匿名 Comparator 读 Entry.used + Long.compare）',
                'SubtitleCache$Entry;.used:J'
                in (slice_class(dn, 'Lio/github/ariinyume/dlsitesoundfloat/data/SubtitleCache$1;')
                    or '')
                and inner_method_contains(
                    dn, C_CACHE, 'compare', 'Ljava/lang/Long;.compare:(JJ)I'),
                inner_method_contains(
                    do, C_CACHE, 'compare', 'Ljava/lang/Long;.compare:(JJ)I'))

    # ---- C2 仓库接线：读写都真的接到 SubtitleCache ----
    ck.add_gone('88★ 【code 1012】仓库 tryResumeFromDiskNow 已删'
                '（其 SubtitleCache.lookup 调用点一并消失）',
                'tryResumeFromDiskNow:()V' not in (rn or ''),
                'tryResumeFromDiskNow:()V' in (rp or ''))
    ck.add_manual('88a★ 【code 1012】stageCacheToDisk 只**暂存**不落盘'
                  '（体内没有 SubtitleCache.put / 没有线程池提交）',
                  'SubtitleCache;.put:' not in (method_body_typed(
                      rn, 'stageCacheToDisk', '(Ljava/lang/String;ID)V') or '')
                  and 'ExecutorService;.execute:' not in (method_body_typed(
                      rn, 'stageCacheToDisk', '(Ljava/lang/String;ID)V') or ''),
                  'stageCacheToDisk 里混进了落盘动作')
    ck.add_diff('89★ 仓库 tryResumeFromDisk 真的查缓存'
                '（【code 1012】保留：换轨离线直读 / 云端兜底）',
                'SubtitleCache;.lookup:(JJLjava/lang/String;)Ljava/lang/String;'
                in repo_mb('tryResumeFromDisk', 0),
                'SubtitleCache;.lookup:(JJLjava/lang/String;)Ljava/lang/String;'
                in repo_mb('tryResumeFromDisk', 1))
    ck.add_diff('90★ 【code 1012】仓库 cacheUsable 只看配置总闸（不再叠会话级开关）',
                'subtitleCacheEnabled:Z' in repo_mb('cacheUsable', 0)
                and 'localCacheMode' not in repo_mb('cacheUsable', 0),
                'subtitleCacheEnabled:Z' in repo_mb('cacheUsable', 1))
    ck.add_gone('91★ 【code 1012】仓库 setLocalCacheMode 与其「复位即读盘」接线一并消失',
                'setLocalCacheMode:(Z)V' not in (rn or ''),
                'setLocalCacheMode:(Z)V' in (rp or ''))
    ck.add_diff('92★ 【code 1012】仓库 flushStagedCache 把落盘丢进缓存线程池'
                '（ExecutorService.execute → 主线程不碰盘）',
                'Ljava/util/concurrent/ExecutorService;.execute:(Ljava/lang/Runnable;)V'
                in repo_mb('flushStagedCache', 0),
                'Ljava/util/concurrent/ExecutorService;.execute:(Ljava/lang/Runnable;)V'
                in repo_mb('flushStagedCache', 1))
    ck.add_manual('93★ 【code 1012】仓库落盘 lambda 真的调 SubtitleCache.put'
                  '（flushStagedCache 的合成 lambda；顺序不稳定 ⇒ 全取再 any）',
                  any('SubtitleCache;.put:(Ljava/lang/String;IIJLjava/lang/String;ID)V' in b
                      for b in lambda_bodies(rn, 'flushStagedCache')),
                  'flushStagedCache 的 lambda 里没有 put')
    ck.add_manual('94★ 仓库 freshWorkKey 用 3min 窗口判新鲜（内联 180000 = 0x2bf20）',
                  '#0002bf20' in repo_mb('freshWorkKey', 0), '未见 #0002bf20')

    # ---- C2b 【code 1012】云端优先 / 本地兜底 的落点（重载方法 ⇒ 必须按描述符切体）----
    _OTC4 = method_body_typed(rn, 'onTrackChanged', '(Ljava/lang/String;ZJJ)V') or ''
    ck.add_manual('94a★ 【需求】换轨入口先按权威选择键兑现暂存'
                  '（onTrackChanged 四参体内有 flushStagedCache）',
                  'flushStagedCache:(J)V' in _OTC4, '换轨入口未见 flushStagedCache')
    ck.add_manual('94b★ 【需求】换轨入口只有**已确认离线**才直接读盘'
                  '（isOffline 与 tryResumeFromDisk 同体）',
                  'isOffline:()Z' in _OTC4 and 'tryResumeFromDisk:' in _OTC4,
                  '换轨入口未见 isOffline 门控')
    ck.add_manual('94c★ 【需求】云端一直没给字幕 ⇒ 裁决超时回退本地'
                  '（resolvePendingTrack 体内有 tryResumeFromDisk）',
                  'tryResumeFromDisk:' in (
                      method_body_typed(rn, 'resolvePendingTrack', '(J)V') or ''),
                  '裁决超时未见本地兜底')
    ck.add_manual('94d★ 【根因】加载路径改为调 stageCacheToDisk'
                  '（不再用「加载时刻的选择键」落盘）',
                  'stageCacheToDisk:' in (method_body_typed(
                      rn, 'loadFromJsonArrayInternal',
                      '(Lorg/json/JSONArray;Ljava/lang/String;Z)V') or '')
                  and 'cacheTc' not in (method_body_typed(
                      rn, 'loadFromJsonArrayInternal',
                      '(Lorg/json/JSONArray;Ljava/lang/String;Z)V') or ''),
                  '加载路径未见 stageCacheToDisk / 仍有旧标签变量')
    ck.add_manual('94e★ 【code 1012】离线判定真的查网络'
                  '（ConnectivityManager.getActiveNetwork + NetworkCapabilities.hasCapability）',
                  'Landroid/net/ConnectivityManager;.getActiveNetwork:()Landroid/net/Network;'
                  in (method_body_typed(rn, 'isOffline', '()Z') or '')
                  and 'Landroid/net/NetworkCapabilities;.hasCapability:(I)Z'
                  in (method_body_typed(rn, 'isOffline', '()Z') or ''),
                  'isOffline 未见 ConnectivityManager 调用')

    # ---- C3 总线：设置页 ↔ 宿主 的三条 action 真的接上 ----
    ck.add_diff('95★ handleCacheClear 清完**回一条统计**（0 条也要回，设置页那行才能归零）',
                'SubtitleCache;.clearAll:()V' in bus_mb('handleCacheClear', 0)
                and 'sendCacheStats:' in bus_mb('handleCacheClear', 0),
                'SubtitleCache;.clearAll:()V' in bus_mb('handleCacheClear', 1))
    ck.add_diff('96★ answerCacheStats 查完**回一条统计**（宿主侧先 init 兜底）',
                'SubtitleCache;.count:()I' in bus_mb('answerCacheStats', 0)
                and 'sendCacheStats:' in bus_mb('answerCacheStats', 0),
                'SubtitleCache;.count:()I' in bus_mb('answerCacheStats', 1))
    ck.add_diff('97★ sendCacheStats 真的带两个 extra（cache_count / cache_bytes）并广播',
                '"cache_count"' in bus_mb('sendCacheStats', 0)
                and '"cache_bytes"' in bus_mb('sendCacheStats', 0),
                '"cache_count"' in bus_mb('sendCacheStats', 1))
    # ⚠️ `Intent.setPackage(String)` 在 compileSdk 34 上**返回 Intent**（不是 void）
    #   ⇒ 描述符是 `(Ljava/lang/String;)Landroid/content/Intent;`，不是 `…V`。
    ck.add_diff('98★ sendCacheClear 真的把 action 定向投给宿主（Intent.setPackage(HOST_PKG)）',
                '"io.github.ariinyume.dlsitesoundfloat.action.SUBTITLE_CACHE_CLEAR"'
                in bus_mb('sendCacheClear', 0)
                and 'Landroid/content/Intent;.setPackage:(Ljava/lang/String;)'
                'Landroid/content/Intent;' in bus_mb('sendCacheClear', 0),
                'Landroid/content/Intent;.setPackage:' in bus_mb('sendCacheClear', 1))
    ck.add_diff('99★ 宿主侧 responder 把两条新 action 都挂进 IntentFilter（addAction）',
                '"io.github.ariinyume.dlsitesoundfloat.action.SUBTITLE_CACHE_CLEAR"'
                in bus_mb('installResponder', 0)
                and '"io.github.ariinyume.dlsitesoundfloat.action.SUBTITLE_CACHE_STATS_REQ"'
                in bus_mb('installResponder', 0),
                '"io.github.ariinyume.dlsitesoundfloat.action.SUBTITLE_CACHE_CLEAR"'
                in bus_mb('installResponder', 1))

    # ---- C4 设置页：广播 + 二次确认 + 归零 ----
    ck.add_diff('100★ buildSubtitleCacheRow 真的摆出开关行 + 清除按钮 + 占用读数',
                all(s in sett_mb('buildSubtitleCacheRow', 0) for s in (
                    'SUBTITLE_CACHE:Lio/github/ariinyume/dlsitesoundfloat/ui/Strings;',
                    'CACHE_CLEAR:Lio/github/ariinyume/dlsitesoundfloat/ui/Strings;',
                    'renderCacheUsage:()V')),
                'SUBTITLE_CACHE:Lio/github/ariinyume/dlsitesoundfloat/ui/Strings;'
                in sett_mb('buildSubtitleCacheRow', 1))
    ck.add_diff('101★ renderCacheUsage 用「已缓存 N 轨 · 占用 a / b」格式并读 256MB 上限'
                '（内联 268435456 = 0x10000000）',
                'CACHE_USAGE:Lio/github/ariinyume/dlsitesoundfloat/ui/Strings;'
                in sett_mb('renderCacheUsage', 0)
                and 'fmtBytes:(J)Ljava/lang/String;' in sett_mb('renderCacheUsage', 0)
                and '// #10000000' in sett_mb('renderCacheUsage', 0),
                'CACHE_USAGE:Lio/github/ariinyume/dlsitesoundfloat/ui/Strings;'
                in sett_mb('renderCacheUsage', 1))
    # ⚠️ 真正发广播那一步在确认框的**回调 lambda** 里（`lambda$onClearCacheClicked$N`），
    #   不在方法本体 —— 只查本体必然漏（首次就这样假 FAIL）。
    ck.add_diff('102★ onClearCacheClicked 先弹二次确认（MaterialAlertDialogBuilder），确认后才发广播',
                'MaterialAlertDialog' in sett_mb('onClearCacheClicked', 0)
                and 'ConfigBus;.sendCacheClear:(Landroid/content/Context;)V'
                in (lambda_body(sen, 'onClearCacheClicked') or ''),
                'MaterialAlertDialog' in sett_mb('onClearCacheClicked', 1))
    ck.add_diff('103★ applyCacheStats 用**宿主回执**触发「已清除」提示（不是点下按钮就报成功）',
                'mPendingClearToast:Z' in sett_mb('applyCacheStats', 0)
                and 'CACHE_CLEAR_DONE:Lio/github/ariinyume/dlsitesoundfloat/ui/Strings;'
                in sett_mb('applyCacheStats', 0),
                'mPendingClearToast:Z' in sett_mb('applyCacheStats', 1))
    ck.add_manual('104★ 设置页的匿名接收器 onReceive 真的读 extra 并交给 applyCacheStats',
                  inner_on_receive(dn, C_SETT, 'applyCacheStats:') is True,
                  '未找到含 applyCacheStats 的 onReceive')
    ck.add_manual('105★ onDestroy 注销接收器（unregisterReceiver）—— 防泄漏',
                  'unregisterReceiver:(Landroid/content/BroadcastReceiver;)V'
                  in sett_mb('onDestroy', 0), '未注销')
    ck.add_diff('106★ onResume 主动问一次缓存占用（sendCacheStatsRequest）',
                'ConfigBus;.sendCacheStatsRequest:(Landroid/content/Context;)V'
                in sett_mb('onResume', 0),
                'ConfigBus;.sendCacheStatsRequest:(Landroid/content/Context;)V'
                in sett_mb('onResume', 1))

    # ---- C5 视图树：testID 判定 + 兜底锚点 ----
    ck.add_diff('107★ probeOfficialToolbar 用**普通 tag**（View.getTag）取 testID —— 不需知道宿主 R.id',
                'Landroid/view/View;.getTag:()Ljava/lang/Object;' in svh_mb('probeOfficialToolbar', 0),
                'Landroid/view/View;.getTag:()Ljava/lang/Object;'
                in svh_mb('probeOfficialToolbar', 1))
    ck.add_diff('108★ 判定用 String.endsWith 做后缀匹配'
                '（code 1007 起是 contains；code 1009 归一化后改后缀匹配）',
                'Ljava/lang/String;.endsWith:(Ljava/lang/String;)Z'
                in svh_mb('probeOfficialToolbar', 0),
                'Ljava/lang/String;.endsWith:(Ljava/lang/String;)Z'
                in svh_mb('probeOfficialToolbar', 1))
    ck.add_diff('109★ probeOfficialToolbar 认两个 testID 后缀串（内联立即数）',
                '"SUBTITLE_BUTTON"' in svh_mb('probeOfficialToolbar', 0)
                and '"FULL_PLAYER_CLOSE_BUTTON"' in svh_mb('probeOfficialToolbar', 0),
                '"SUBTITLE_BUTTON"' in svh_mb('probeOfficialToolbar', 1))
    # ⚠️ 调用点在**采集循环 collect** 里（每个可见节点问一次），不在 scan 本体；
    #   scan 尾部只负责「CC 缺席但收起键在场」时算兜底簇。
    ck.add_diff('110★ 采集点真的接上 testID 探测：collect 调 probeOfficialToolbar，scan 尾部算兜底锚',
                'probeOfficialToolbar:' in svh_mb('collect', 0)
                and 'trailingToolbarClusterRect:' in svh_mb('scan', 0),
                'probeOfficialToolbar:' in svh_mb('collect', 1))
    ck.add_diff('111★ 簇推断按「右侧可见子」收敛（code 1011 起用 hasVisibleChildRightOf / '
                'unionChildrenRightOf，不再取最后一个可见子 —— 那会被全屏手势层占住）',
                ('SubtitleViewHook;.hasVisibleChildRightOf:'
                 in svh_mb('trailingToolbarClusterRect', 0)
                 and 'SubtitleViewHook;.unionChildrenRightOf:'
                 in svh_mb('trailingToolbarClusterRect', 0)),
                'lastVisibleChild' in svh_mb('trailingToolbarClusterRect', 1))
    ck.add_diff('112★ 兜底下潜真的量屏幕矩形（rectOnScreen），不猜坐标',
                'SubtitleViewHook;.rectOnScreen:(Landroid/view/View;)[I'
                in svh_mb('trailingToolbarClusterRect', 0),
                'SubtitleViewHook;.rectOnScreen:' in svh_mb('trailingToolbarClusterRect', 1))

    # ---- C6 播放页胶囊：落位阶梯 / 跟随 / 显隐门 ----
    ck.add_gone('113★ 【code 1012】layoutCacheButton（读 CC 矩形 / 记 sLastCcRect / arraycopy）'
                '已随胶囊删除',
                'layoutCacheButton' not in (an or ''), 'layoutCacheButton' in (ap or ''))
    ck.add_gone('114★ 【code 1012】hideCacheButton（无锚点时收起胶囊）已随胶囊删除',
                'hideCacheButton' not in (an or ''), 'hideCacheButton' in (ap or ''))
    ck.add_gone('115★ 【code 1012】applyFollowOffset 不再对胶囊做 setTranslationY',
                'sCacheButton' not in (method_body(an, 'applyFollowOffset') or ''),
                'sCacheButton' in (method_body(ap, 'applyFollowOffset') or ''))
    ck.add_gone('116★ 【code 1012】仓库观察者不再刷新胶囊'
                '（主验包内 applyCacheButtonState 已不存在）',
                'applyCacheButtonState' not in (an or ''),
                'applyCacheButtonState' in (ap or ''))
    ck.add_gone('117★ 【code 1012】detach 时不再清理胶囊'
                '（removeButton 的 lambda 里无 findViewById / sCachePlacedAt）',
                'sCachePlacedAt' not in (lambda_body(an, 'removeButton') or ''),
                'sCachePlacedAt' in (lambda_body(ap, 'removeButton') or ''))
    ck.add_diff('118★ 胶囊复用量宽样本（capsuleTextPx 里仍含两枚缓存文案；'
                '【code 1012】胶囊已删、样本**故意保留**，免得改到另两枚胶囊的字号）',
                'I18n;.cacheOn:()Ljava/lang/String;' in abh_mb('capsuleTextPx', 0)
                and 'I18n;.cacheOff:()Ljava/lang/String;' in abh_mb('capsuleTextPx', 0),
                'I18n;.cacheOn:()Ljava/lang/String;' in abh_mb('capsuleTextPx', 1))

    # ---- C7 模块：只在宿主进程初始化 ----
    ck.add_diff('119★ 模块在宿主进程初始化缓存（DlsiteSoundSubtitleModule$1.afterVoid → get().init）',
                'SubtitleCache;.get:' in (m1n or '')
                and 'SubtitleCache;.init:(Landroid/content/Context;)V' in (m1n or ''),
                'SubtitleCache;.init:(Landroid/content/Context;)V' in (m1o or ''))
    ck.add_diff('120★ 数据层包名 io.github.ariinyume.dlsitesoundfloat（2.1.0 起的包名口径未回退）',
                'Lio/github/ariinyume/dlsitesoundfloat/data/SubtitleCache;' in (dn or ''),
                'Lio/github/ariinyume/dlsitesoundfloat/data/SubtitleCache;' in (do or ''))

    # ══════════════ D. 负向锚（旧世界必须彻底消失）══════════════
    ck.add_manual('121★ 负向：1006 包里 SubtitleCache 类**不存在**（新物确有区分力）',
                  ca_o is None, '旧包也有该类')
    ck.add_manual('122★ 负向：1006 包里 PlaylistKey.makeIdentity:(IDI)J **不存在**',
                  'makeIdentity:(IDI)J' not in (ko or ''), '旧包已有')
    ck.add_manual('123★ 负向：1006 包里没有 subtitle_cache_enabled 串',
                  not old('subtitle_cache_enabled'), '旧包已有')
    ck.add_manual('124★ 负向：1006 包里没有 [code 1007] 里程碑串',
                  not old('[code 1007]'), '旧包已有')
    ck.add_manual('125★ 负向：1006 包里没有 SUBTITLE_CACHE_CLEAR action 串',
                  not old('io.github.ariinyume.dlsitesoundfloat.action.SUBTITLE_CACHE_CLEAR'),
                  '旧包已有')
    ck.add_manual('126★ 负向：1006 的**常开横幅行**在本轮包里已消失（零终止精确匹配；'
                  '履历段保留不算，见 145★）',
                  not new('[DLsiteSoundFloat] ==== BUILD 2.3.1 / code 1006\x00'),
                  '本轮包里仍有 1006 常开横幅')

    # ══════════════ D2. 【code 1008】取证件（诊断 + testID 兜底通道）══════════════
    #    本轮只加日志与兜底，判据都是「新形态有 / 旧形态没有」的**变化类**锚。
    ck.add('148★ 里程碑串 [code 1008]（本轮取证）', new('[code 1008]'), old('[code 1008]'))
    ck.add_gone('149★ 【code 1012】门控读数日志串（[code 1008] cache gate …）已随按钮移除',
                not new('[code 1008] cache gate '),
                prev_txt('[code 1008] cache gate '))
    ck.add('150★ testID 普查日志串 + 非串 tag 计数',
           new('[code 1008] tag census #') and new('nonStringTag='),
           old('[code 1008] tag census #'))
    ck.add('151★ 两个控件认到的日志串（button FOUND tag=）+ 去重入口 logFoundOnce / 去重标志字段；'
           'code 1011 起由 logFoundOnce 统一拼接，不再写死两条字面量',
           new('button FOUND tag=') and 'logFoundOnce:' in (svn or '')
           and 'sCcFoundLogged' in (svn or ''),
           old('button FOUND tag='))
    ck.add('152★ 兜底通道：按名字查 react_test_id 资源 + 命中日志',
           new('react_test_id') and new('[code 1008] react_test_id res id = '),
           old('react_test_id'))
    ck.add('153★ 仓库层可用性翻转日志串（local cache availability ->）',
           new('[code 1008] local cache availability -> '),
           old('[code 1008] local cache availability -> '))
    ck.add_gone('154★ 【code 1012】播放页字段 sLastCacheGateDiag 已随胶囊移除',
                '.sLastCacheGateDiag:Ljava/lang/String;' not in (an or ''),
                '.sLastCacheGateDiag:Ljava/lang/String;' in (ap or ''))
    ck.add_diff('155★ 视图层字段 sTagSamples/sTagCensusDone/sReactTestIdRes（普查件）',
                all(sym in (svn or '') for sym in (
                    '.sTagSamples:Ljava/util/LinkedHashSet;', '.sTagCensusDone:Z',
                    '.sReactTestIdRes:I')),
                all(sym in (svo or '') for sym in (
                    '.sTagSamples:Ljava/util/LinkedHashSet;', '.sTagCensusDone:Z',
                    '.sReactTestIdRes:I')))
    ck.add_diff('156★ 视图层新增 censusTag/fmtRect/reactTestIdRes 三个方法',
                all(m in (svn or '') for m in (
                    'censusTag:', 'fmtRect:([I)Ljava/lang/String;', 'reactTestIdRes:')),
                'censusTag:' in (svo or ''))
    ck.add_manual('157★ 负向：1006 包里没有 [code 1008] 里程碑串',
                  not old('[code 1008]'), '旧包已有')
    ck.add_manual('158★ 负向：1007 的**常开横幅行**在本轮包里已消失（零终止精确匹配）',
                  not new('[DLsiteSoundFloat] ==== BUILD 2.3.1 / code 1007\x00'),
                  '本轮包里仍有 1007 常开横幅')

    # ══════════════ D3. 【code 1009】真机根因修复（testID 归一化）══════════════
    ck.add('159★ 里程碑串 [code 1009]（本轮修复）', new('[code 1009]'), old('[code 1009]'))
    ck.add('160★ SubtitleViewHook.normalizeTag 编进包（归一化助手）',
           'normalizeTag:' in (svn or ''), 'normalizeTag' in (svo or ''))
    ck.add('161★ 归一化真的用 Character.toUpperCase（大写折叠，不是原样返回）',
           'Ljava/lang/Character;.toUpperCase:(C)C' in (svn or ''),
           'Ljava/lang/Character;.toUpperCase:(C)C' in (svo or ''))
    ck.add_diff('162★ probeOfficialToolbar 用 String.endsWith 做后缀匹配（code 1009 起，不再 contains）',
                'Ljava/lang/String;.endsWith:(Ljava/lang/String;)Z'
                in svh_mb('probeOfficialToolbar', 0),
                'Ljava/lang/String;.endsWith:(Ljava/lang/String;)Z'
                in svh_mb('probeOfficialToolbar', 1))
    ck.add('163★ 顶栏专属小预算日志串 [code 1009] toolbar-ish tag #（普查停了也照抄）',
           new('[code 1009] toolbar-ish tag #'), old('[code 1009] toolbar-ish tag #'))
    ck.add_manual('164★ 负向：1006 包里没有 [code 1009] 里程碑串',
                  not old('[code 1009]'), '旧包已有')
    ck.add_manual('165★ 负向：1008 的**常开横幅行**在本轮包里已消失（零终止精确匹配）',
                  not new('[DLsiteSoundFloat] ==== BUILD 2.3.1 / code 1008\x00'),
                  '本轮包里仍有 1008 常开横幅')

    # ══════════════ D4. 【code 1010】普查早停修复（「胶囊仍不出现」的第二个根因）══════════════
    #    真机取证：census 在进播放页**之前**就停了（18:53:01 停 / 18:53:47 才进播放页）。
    ck.add('166★ 里程碑串 [code 1010]（本轮修复）', new('[code 1010]'), old('[code 1010]'))
    ck.add('167★ 现场取证串 [code 1010] tag dump (（锚点全丢那一刻全量倒样本）',
           new('[code 1010] tag dump ('), old('[code 1010] tag dump ('))
    ck.add_diff('168★ 视图层新增 dumpTagSamples 方法（按钮层可回调的取证入口）',
                'dumpTagSamples:(Ljava/lang/String;)V' in (svn or ''),
                'dumpTagSamples:(Ljava/lang/String;)V' in (svo or ''))
    ck.add_manual('169★ 负向：1006 包里没有 [code 1010] 里程碑串',
                  not old('[code 1010]'), '旧包已有')
    ck.add_manual('170★ 负向：1009 的**常开横幅行**在本轮包里已消失（零终止精确匹配）',
                  not new('[DLsiteSoundFloat] ==== BUILD 2.3.1 / code 1009\x00'),
                  '本轮包里仍有 1009 常开横幅')


    # ══════════════ D5. 【code 1011】簇推断根修 + 对称几何兜底 + 日志精简 ══════════════
    #    真机 20:03（首次跑上 1010）：close=true（81 次认到）但 cluster=false ⇒ 第三档恒空；
    #    追因是「最后一个可见子」被全屏手势层占住。另 FOUND 那条单次会话自重打 81 遍。
    ck.add('171★ 【根因】视图层新增 hasVisibleChildRightOf（「存在可见子在收起键右侧」）',
           'hasVisibleChildRightOf:' in (svn or ''),
           'hasVisibleChildRightOf:' in (svo or ''))
    ck.add('172★ 【根因】视图层新增 unionChildrenRightOf（右侧可见子外接矩形 = 按钮簇）',
           'unionChildrenRightOf:' in (svn or ''),
           'unionChildrenRightOf:' in (svo or ''))
    ck.add('173★ 视图层新增 leftmostChildRightOf（外接矩形过宽时下潜收敛）',
           'leftmostChildRightOf:' in (svn or ''),
           'leftmostChildRightOf:' in (svo or ''))
    ck.add('174★ 新增第四档「对称几何」兜底方法 symmetricCcRect',
           'symmetricCcRect:' in (svn or ''),
           'symmetricCcRect:' in (svo or ''))
    ck.add('175★ 视图层新增 FOUND 去重入口 logFoundOnce',
           'logFoundOnce:' in (svn or ''),
           'logFoundOnce:' in (svo or ''))
    ck.add('176★ 去重标志字段 sCcFoundLogged 编进包（sget/sput 会带字段名）',
           'sCcFoundLogged' in (svn or ''), 'sCcFoundLogged' in (svo or ''))
    ck.add_gone('177★ 【code 1012】按钮层第四档文案串（no cluster / no mirror）已随胶囊移除'
                '（视图层 symmetricCcRect 能力仍留，见 174★）',
                not new('no cluster / no mirror'), prev_txt('no cluster / no mirror'))
    ck.add_manual('178★ 负向：1006 包里没有 171★~177★ 的新符号（上面对照侧已各自为 False）',
                  not old('symmetricCcRect') and not old('no cluster / no mirror'),
                  '旧包已有')
    ck.add_manual('179★ 负向：1010 的**常开横幅行**在本轮包里已消失（零终止精确匹配）',
                  not new('[DLsiteSoundFloat] ==== BUILD 2.3.1 / code 1010\x00'),
                  '本轮包里仍有 1010 常开横幅')

    # ══════════════ E. 保持型（1006 机器一件都不许丢）══════════════
    for lbl, owner, sym in (
        ('127★', 'kn', 'workKeyOf:(Ljava/lang/String;)Ljava/lang/String;'),
        ('128★', 'kn', 'cuesBelongToChangedWork:(Ljava/lang/String;Ljava/lang/String;JJJ)Z'),
        ('129★', 'kn', 'makeSelection:(II)J'),
        ('130★', 'rn', 'ownsCuesForChangedWork:(J)Z'),
        ('131★', 'rn', 'notePlaylistLoaded:()V'),
        ('132★', 'rn', 'loadFromJson:(Ljava/lang/String;Ljava/lang/String;)V'),
        ('133★', 'rn', 'ownsCuesFor:(J)Z'),
        ('134★', 'rn', 'tryResumeFromCache:(Ljava/lang/String;JJ)Z'),
        ('135★', 'psn', 'settleChange'),
        ('136★', 'psn', 'onPlaylistStateFromStatusMap'),
    ):
        seg = {'kn': kn, 'rn': rn, 'psn': psn}[owner] or ''
        ck.add_keep('%s 保持型：%s 仍在' % (lbl, sym), sym in seg)
    for lbl, owner, name in (
        ('137★', 'rn', '.cuesWorkKey:Ljava/lang/String;'),
        ('138★', 'rn', '.lastSeenWorkKey:Ljava/lang/String;'),
        ('139★', 'rn', '.workChangeKey:Ljava/lang/String;'),
        ('140★', 'rn', '.workChangeAtMs:J'),
        ('141★', 'psn', '.sLastTcByListId:Ljava/util/LinkedHashMap;'),
    ):
        seg = {'rn': rn, 'psn': psn}[owner] or ''
        ck.add_keep('%s 保持型：字段 %s 仍在（1006 机器的基础件）' % (lbl, name), name in seg)
    ck.add_keep('142★ 保持型：1006 的里程碑日志 [code 1006] 仍在', new('[code 1006]'))
    ck.add_keep('143★ 保持型：1006 的认领日志串 came from a DIFFERENT work 仍在',
                new('came from a DIFFERENT work'))
    ck.add_keep('144★ 保持型：1005 的里程碑日志 [code 1005] 仍在', new('[code 1005]'))
    ck.add_keep('145★ 保持型：code 1006 的履历段仍在（追加式，不覆盖）',
                new('==== BUILD 2.3.1 / code 1006 （'))
    ck.add_keep('146★ 保持型：NetworkHook 仍在（本轮没改它，别弄丢）',
                cn(dn, 'Lio/github/ariinyume/dlsitesoundfloat/hook/NetworkHook;') is not None)
    ck.add_keep('147★ 保持型：悬浮窗 / 状态栏数据类仍在（本轮只加不改）',
                cn(dn, 'Lio/github/ariinyume/dlsitesoundfloat/data/SubtitleRepository;') is not None
                and cn(dn, 'Lio/github/ariinyume/dlsitesoundfloat/ui/Strings;') is not None)

    # ══════════════ F. 【code 1012】删胶囊 + 云端优先/本地兜底 ══════════════
    #    反向对照 = 第三个参数（上一版 code 1011）——
    #    这些符号是 1007/1011 引进、本轮删掉的，1006 两版都没有（拿它当对照必判「无区分力」）。
    ck.add('180★ 里程碑串 [code 1012]（本轮）', new('[code 1012]'), old('[code 1012]'))
    ck.add_manual('181★ 负向：1011 的**常开横幅行**已消失（零终止精确匹配）',
                  not new('[DLsiteSoundFloat] ==== BUILD 2.3.1 / code 1011\x00'),
                  '本轮包里仍有 1011 常开横幅')
    ck.add_keep('182★ 保持型：code 1012 的履历段已追加（不覆盖旧履历）',
                new('==== BUILD 2.3.1 / code 1012 （'))
    ck.add_gone('183★ 【code 1012】播放页胶囊整套符号在包内已全无'
                '（cacheButtonWanted / ensureCacheButton / layoutCacheButton / hideCacheButton / '
                'applyCacheButtonState / sCacheButton / sLastCcRect / sCachePlacedAt / '
                'sCacheAnchorSrc）',
                not any(s in (an or '') for s in (
                    'cacheButtonWanted', 'ensureCacheButton', 'layoutCacheButton',
                    'hideCacheButton', 'applyCacheButtonState', 'sCacheButton',
                    'sLastCcRect', 'sCachePlacedAt', 'sCacheAnchorSrc')),
                any(s in (ap or '') for s in (
                    'cacheButtonWanted', 'ensureCacheButton', 'layoutCacheButton',
                    'hideCacheButton', 'applyCacheButtonState', 'sCacheButton',
                    'sLastCcRect', 'sCachePlacedAt', 'sCacheAnchorSrc')))
    ck.add_gone('184★ 【code 1012】仓库「会话级手动开关」三件套 + 字段 + 即时读盘入口 + '
                '旧落盘方法全部消失（上一版曾有）',
                not any(s in (rn or '') for s in (
                    'setLocalCacheMode', 'isLocalCacheMode', 'hasLocalCacheForCurrentTrack',
                    'localCacheMode:Z', 'tryResumeFromDiskNow', 'maybeCacheToDisk')),
                any(s in (rp or '') for s in (
                    'setLocalCacheMode', 'isLocalCacheMode', 'hasLocalCacheForCurrentTrack',
                    'localCacheMode:Z', 'tryResumeFromDiskNow', 'maybeCacheToDisk')))
    ck.add_const('185★ 【code 1012】SubtitleRepository.CACHE_FLUSH_FALLBACK_MS = 2500'
                 '（等权威轨标签的兜底窗口；旧包无此字段）',
                 2500, field_value(rn, 'CACHE_FLUSH_FALLBACK_MS'),
                 field_value(ro, 'CACHE_FLUSH_FALLBACK_MS'))
    ck.add_manual('186★ 【code 1012】反向对照：上一版(1011) 的 INDEX_SCHEMA 仍是 1',
                  field_value(cp, 'INDEX_SCHEMA') == 1,
                  '上一版 INDEX_SCHEMA = %s' % field_value(cp, 'INDEX_SCHEMA'))
    ck.add('187★ 【code 1012】云端兜底日志串（resumed from LOCAL disk cache）',
           new('resumed from LOCAL disk cache'),
           old('resumed from LOCAL disk cache'))


    # ══════════════ G. 【code 1013】暂存落盘的轨标签改用「JSON 到达那刻的印章」══════════════
    #    真机（2026-10-14 挂代理场）暴露的时序缝隙：落盘是「先暂存、等权威轨标签」，
    #    而兑现时取的是**当时**的当前选择键；暂存后 2.5s 内又换到别的轨 ⇒ 兜底兑现
    #    会把一条音轨的字幕标到另一条音轨头上（离线读回错字幕）。
    #    判据：换轨入口的说明与真机实测一致 —— 切轨时序号**立刻**翻、新轨 JSON 约
    #    165ms 后才到 ⇒ JSON 到达那刻盖的选择键印章才是权威轨标签。
    #    ⚠️ 字段判据只搜裸名：dexdump 的**字段段**不写「名字:类型」连写（铁律 60），
    #       写连写会假 FAIL；裸名在字段段与指令行两处都能命中。
    ck.add_manual('188★ 【code 1013】新增字段 SubtitleRepository.stagedCacheSelection'
                  '（暂存那份 JSON 自己的轨标签）',
                  'stagedCacheSelection' in (rn or ''),
                  'stagedCacheSelection' in (ro or ''))
    ck.add_manual('189★ 【code 1013】负向：1012 的**常开横幅行**已消失（零终止精确匹配）',
                  not new('[DLsiteSoundFloat] ==== BUILD 2.3.1 / code 1012\x00'),
                  '本轮包里仍有 1012 常开横幅')
    ck.add_keep('190★ 保持型：code 1013 的履历段已追加（不覆盖旧履历）',
                new('==== BUILD 2.3.1 / code 1013 （'))

    # ══════════════ H. 【code 1014】云端优先的窗口分级 + 兜底钥匙 ══════════════
    #    真机 2026-10-14（关代理后重开宿主，RJ01609334 五音轨）：
    #      10:25:07 序号零→一（手上一片空白）走三秒窗 ⇒ 10:25:10 磁盘命中 ✅
    #      10:25:22 序号一→二、10:25:25 序号二→三（握着上一轨 148 条 cues）
    #        ⇒ 走十五秒长窗 ⇒ 盘上明明有本轨缓存却干等（日志 10:25:30 导出，
    #          裁决点 10:25:37 尚未到）。两个破口：
    #      ① 窗口分级漏了「盘上有无本轨缓存」这一档；
    #      ② 兜底读盘用的是全局观测键（列表重建/快切时会指到别的轨）。
    #    ⚠️ 字段名只搜裸名 —— dexdump 的**字段段**不写「名字:类型」连写（铁律 60），
    #       写连写会假 FAIL；裸名在字段段与指令行两处都能命中。
    ck.add('191★ 【code 1014】新增字段 SubtitleRepository.pendingTrackIdentity'
           '（本次换轨的目标身份；兜底读盘优先用它）',
           'pendingTrackIdentity' in (rn or ''),
           'pendingTrackIdentity' in (ro or ''))
    ck.add('192★ 【code 1014】新增字段 SubtitleRepository.pendingTrackSelection'
           '（本次换轨的目标选择键）',
           'pendingTrackSelection' in (rn or ''),
           'pendingTrackSelection' in (ro or ''))
    ck.add('193★ 【code 1014】新增方法 SubtitleRepository.hasDiskCacheFor'
           '（纯内存索引查询：盘上有无本轨缓存）',
           'hasDiskCacheFor' in (rn or ''),
           'hasDiskCacheFor' in (ro or ''))
    ck.add_manual('194★ 【code 1014】接线级证据：hasDiskCacheFor 真的走内存索引'
                  '（调 SubtitleCache.has，且**不**走 lookup/读盘）',
                  'SubtitleCache;.has:(JJ)Z' in method_body(rn or '', 'hasDiskCacheFor')
                  and 'lookup' not in method_body(rn or '', 'hasDiskCacheFor'),
                  'method_body(hasDiskCacheFor) 不含 SubtitleCache.has')
    ck.add_manual('195★ 【code 1014】负向：1013 的**常开横幅行**已消失（零终止精确匹配）',
                  not new('[DLsiteSoundFloat] ==== BUILD 2.3.1 / code 1013\x00'),
                  '本轮包里仍有 1013 常开横幅')
    ck.add_keep('196★ 保持型：code 1014 的履历段已追加（不覆盖旧履历）',
                new('==== BUILD 2.3.1 / code 1014 （'))

    # ══════════════ W. 【code 1015 / 2.3.2】「实验性功能」卡片 ══════════════
    #    Ari 五项需求：默认关 + 连点状态卡五次解锁 + 版本升级后保持 + 摆在液态玻璃
    #    与「其他」之间 + 字幕缓存搬入并改名 + 总开关关闭时下属全关/置灰/清缓存。
    ck.add('201★ 【code 1015】配置键串 experimental_enabled（新键，默认关）',
           new('experimental_enabled'),
           old('experimental_enabled'))
    ck.add('202★ 【code 1015】字段 SubtitleConfig.experimentalEnabled:Z（默认 false）',
           '.experimentalEnabled:Z' in (scn or ''),
           '.experimentalEnabled:Z' in (sco or ''))
    ck.add('203★ 【code 1015】方法 SettingsActivity.buildExperimentalGroup:(Landroid/widget/LinearLayout;)V',
           'buildExperimentalGroup:(Landroid/widget/LinearLayout;)V' in (sen or ''),
           'buildExperimentalGroup:(Landroid/widget/LinearLayout;)V' in (seo or ''))
    ck.add('204★ 【code 1015】方法 SettingsActivity.onStatusCardClicked:()V（状态卡连点解锁）',
           'onStatusCardClicked:()V' in (sen or ''),
           'onStatusCardClicked:()V' in (seo or ''))
    ck.add('205★ 【code 1015】方法 SettingsActivity.applyExperimentalVisibility:()V（卡片显隐）',
           'applyExperimentalVisibility:()V' in (sen or ''),
           'applyExperimentalVisibility:()V' in (seo or ''))
    ck.add('206★ 【code 1015】方法 SettingsActivity.applyExperimentalChildEnabled:(Z)V（子开关置灰）',
           'applyExperimentalChildEnabled:(Z)V' in (sen or ''),
           'applyExperimentalChildEnabled:(Z)V' in (seo or ''))
    ck.add_const('207★ 【code 1015】SettingsActivity.STATUS_TAP_REQUIRED = 5（连点几次解锁）',
                 5, field_value(sen, 'STATUS_TAP_REQUIRED'),
                 field_value(seo, 'STATUS_TAP_REQUIRED'))
    ck.add_const('208★ 【code 1015】SettingsActivity.STATUS_TAP_WINDOW_MS = 3000（连点时间窗）',
                 3000, field_value(sen, 'STATUS_TAP_WINDOW_MS'),
                 field_value(seo, 'STATUS_TAP_WINDOW_MS'))
    ck.add_manual('209★ 【code 1015】负向：1014 的**常开横幅行**已消失（零终止精确匹配）',
                  not new('[DLsiteSoundFloat] ==== BUILD 2.3.1 / code 1014\x00'),
                  '本轮包里仍有 1014 常开横幅')
    ck.add_keep('210★ 保持型：code 1015 的履历段已追加（不覆盖旧履历）',
                new('==== BUILD 2.3.2 / code 1015 （'))

    # ══════════════ X. 【code 1016】设置页五条 ══════════════
    #    ⚠️ 文案类判据一律**零终止**：「实验性功能」是「实验性功能尚未定型…」的前缀，
    #       裸串两版都命中（铁律 84）。
    ck.add('213★ 【code 1016】新提示文案（已打开实验性功能）三语齐全',
           new('你已经打开实验性功能，无需进行此操作\x00')
           and new('你已經開啟實驗性功能，無需進行此操作\x00')
           and new('Experimental features are already on — no need to do this\x00'),
           old('你已经打开实验性功能，无需进行此操作\x00')
           or old('你已經開啟實驗性功能，無需進行此操作\x00'))
    ck.add_manual('214★ 【code 1016 / 需求2 负向】旧的总开关说明小字已从包里消失',
                  not new('实验性功能尚未定型'),
                  '本轮包里仍有旧的总开关说明文案')
    ck.add('215★ 【code 1016 / 需求3】缓存说明改成新口径（新串在、旧前缀不在）',
           new('播放过的音轨字幕会自动缓存') and not new('播放过的音轨会自动缓存字幕'),
           old('播放过的音轨字幕会自动缓存') or old('播放过的音轨会自动缓存字幕'))
    ck.add_manual('216★ 【code 1016 / 需求3 负向】旧口径残句（断网 / 飞行模式下也能显示）已消失',
                  not new('断网 / 飞行模式下也能显示'),
                  '本轮包里仍有旧口径残句')
    ck.add_manual('217★ 【code 1016】负向：1015 的**常开横幅行**已消失（零终止精确匹配）',
                  not new('[DLsiteSoundFloat] ==== BUILD 2.3.2 / code 1015\x00'),
                  '本轮包里仍有 1015 常开横幅')
    ck.add_keep('218★ 保持型：code 1016 的履历段已追加（不覆盖旧履历）',
                new('==== BUILD 2.3.2 / code 1016 （'))

    # ══════════════ Y. 【code 1017】缓存孤儿清扫 ══════════════
    ck.add('219★ 【code 1017】新增私有方法 sweepOrphansLocked:()I（孤儿清扫，返回删除数）',
           'sweepOrphansLocked:()I' in (ca_n or ''),
           'sweepOrphansLocked:()I' in (ca_o or ''))
    ck.add('220★ 【code 1017】新增私有方法 discardIndexAndSweepLocked:()V（作废即清扫 + 重写空索引）',
           'discardIndexAndSweepLocked:()V' in (ca_n or ''),
           'discardIndexAndSweepLocked:()V' in (ca_o or ''))
    ck.add('221★ 【code 1017】schema 不匹配改用**新诊断串**（丢弃索引 + 清扫孤儿）',
           new('index schema mismatch (found ') and new(') -> discard index + sweep orphans'),
           old('index schema mismatch (found '))
    ck.add('222★ 【code 1017】清扫真的列目录并逐个删（listFiles + File.delete）',
           'Ljava/io/File;.listFiles' in cache_mb('sweepOrphansLocked', 0)
           and 'Ljava/io/File;.delete:()Z' in cache_mb('sweepOrphansLocked', 0),
           'sweepOrphansLocked' in cache_mb('sweepOrphansLocked', 1))
    ck.add_diff('223★ 【code 1017】init 末尾真的调用孤儿清扫（开机顺手回收）',
                'sweepOrphansLocked:()I' in cache_mb('init', 0),
                'sweepOrphansLocked:()I' in cache_mb('init', 1))
    ck.add_diff('224★ 【code 1017】schema 不匹配分支真的走 discardIndexAndSweepLocked（不再空手返回）',
                'discardIndexAndSweepLocked:()V' in cache_mb('loadIndexLocked', 0),
                'discardIndexAndSweepLocked:()V' in cache_mb('loadIndexLocked', 1))
    ck.add_keep('225★ 保持型：清扫白名单的保底串（索引文件名）仍在常量池',
                new('index.json'))
    ck.add_manual('226★ 【code 1017 负向】旧诊断串（索引失配即重建为空）已从包里消失',
                  not new('index schema mismatch -> rebuild as empty'),
                  '本轮包里仍有旧诊断串')
    ck.add_manual('227★ 【code 1017】负向：1016 的**常开横幅行**已消失（零终止精确匹配）',
                  not new('[DLsiteSoundFloat] ==== BUILD 2.3.2 / code 1016\x00'),
                  '本轮包里仍有 1016 常开横幅')
    ck.add_keep('228★ 保持型：code 1017 的履历段已追加（不覆盖旧履历）',
                new('==== BUILD 2.3.2 / code 1017 （'))
    # ⚠️ 裸搜 'Experimental' 会被 kotlinx 的 require-ExperimentalCoroutineDispatcher 污染
    #   （旧包里也是 True ⇒ 无区分力）；零终止才是「这是一个独立字符串」的正确判据。
    ck.add('211★ 【code 1015】实验性功能卡片三语文案（标题 简/繁/英，零终止精确匹配）',
           new('实验性功能\x00') and new('實驗性功能\x00') and new('Experimental\x00'),
           old('实验性功能\x00') or old('實驗性功能\x00') or old('Experimental\x00'))
    # ⚠️ 曾想加「旧文案『字幕缓存功能』已从包里消失」——**这条判据立不住**：
    #   履历段与 javadoc 必然会提到旧名（「把『字幕缓存功能』移入该卡片并改名」），
    #   字符串池里永远搜得到。改名这件事由 54★ 的零终止匹配负责（它才问得准）。

    return ck.report()


if __name__ == '__main__':
    sys.exit(main())
