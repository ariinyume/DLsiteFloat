# `tools/` 索引

> 全部脚本只读，不改任何文件（`release.py` 例外：它执行发版，需显式传参）。
> 汇总入口：`python tools/run_all_verify.py`（任一 FAIL ⇒ 退出码非 0）
> 🔴 **脚本清单与项数的单点真源 = `python tools/run_all_verify.py --list`**；
>   本文是人类可读的补充说明、可能滞后于最新几轮，**不要当清单副本引用**。

---

## 目录政策（2026-11-03 起）

顶层**只放当前活跃的通用工具**；按轮次编号的判据脚本一律归档到 `archive/`。

```
tools/
├── run_all_verify.py        ← 唯一汇总入口（自动配包 + 在册调度归档脚本）
├── verify_layer.py          ← 原语层 + 清单 runner（新轮次的标准姿势）
├── manifests/round_*.json   ← 新轮次的判据清单
├── audit_criteria.py        ← 判据画像（四口径分档，发版前自查）
├── audit_arch.py            ← 架构体检
├── verify_pathdata.py       ← 矢量图 pathData 语法校验（与轮次无关）
├── verify_protocol_src.py   ← Protocol 单点真源（与轮次无关）
├── sdkpath.py               ← SDK / build-tools 定位（归档脚本仍 import 它）
├── release.py               ← 双仓发版
└── archive/                 ← 历史轮次，**仍在册调度**；明细见 archive/README.md
    ├── verify_994 … verify_1044（61 个判据脚本）
    ├── geom/                ← 几何黄金向量（code 993/994）
    └── patches/             ← 64 个一次性补丁脚本（未入库，纯本机现场记录）
```

🔴 **归档 ≠ 退役**。`run_all_verify.py` 的 `SCRIPTS` 清单仍登记那 61 个脚本，
`locate()` 先找顶层、再找 `archive/` ⇒ **62 席回归链一条没少**（实测 61 PASS + 1 DEGRADED）。

归档脚本文件头都带一段「`__file__` 回拨」块（见任意 `archive/verify_*.py` 前 15 行）：
归档后文件深了一层，所有基于 `__file__` 的相对定位都会错一层；回拨把它指回
`tools/` 下的虚拟原位置，**正文一行不用改**，同时把 `tools/` 塞进 `sys.path`
让 `from sdkpath import …` 照常可用。

---

## 一键跑全部

```bash
python tools/run_all_verify.py               # 全部（含 archive/ 里在册的 61 个）
python tools/run_all_verify.py 995 protocol  # 只跑名字含这些关键字的
python tools/run_all_verify.py --list        # 只列清单不执行
```

脚本会**自动找出 APK 并按每个 dex 脚本期望的 code 精确配包**，
不需要手动传路径（漏配对照包会在输出里显式提示，且**不算失败**）。

---

## 验证链与脚本对照

| 层 | 验什么 | 脚本 | 位置 |
| --- | --- | --- | --- |
| **① 单元测试** | 纯函数内核的黄金向量（纯 JVM，不碰 Android） | `app/src/test/` · `GoldenVectorTest` | 89 条 |
| **② 源码层** | 单点真源、字面量归零、转发壳完好 | `verify_protocol_src.py` | 顶层 |
| **③ dex 字节码层** | 改动**确实编进了 APK** | `verify_994.py` · `verify_995.py` … | `archive/` |
| **④ 资源层** | aapt2 读编译后资源（float 有精度损失 ⇒ 必须容差） | `verify_pathdata.py` | 顶层 |
| **⑤ 真机日志** | 真实行为是否与判据一致 | `verify_994_log_window.py` | `archive/` |
| **⑥ 清单层** | 新轮次判据（恒成立口径，不随轮次假红） | `manifests/round_*.json` → `verify_layer.py` | 顶层 |

---

## ⚠️ 判据纪律（三条，别绕过）

1. **有区分力才算判据**。真锚 = 主验命中**且**对照未命中。
   「两版都成立」= 没测到东西。`run_all_verify.py` 会把锚数打在汇总表里。
2. **优先读脚本自报值**。日志自带 `OK` / `OFF=n` / `PASS n/n` 时，别自己拿原始字段重算 ——
   字段名与语义没有对应关系时，算出来的数可能是假绿。
3. **判 FAIL 前先确认不是脚本判据错**。995 的 dex 层首版报了 3 个 FAIL，
   取证后确认**全是脚本判据错、零真回归**。这个方向要敢怀疑。

---

### ⚠️ `ENVBLOCK`：环境拦截 ≠ 判据失败

`run_all_verify.py` 有个 `ENVBLOCK` 状态。触发条件：
脚本输出里带 `SAFE_DELETE_BULK_CONFIRM_REQUIRED` **且** 没有自己的 `FAIL n/m` 汇总行。

**背景**：本环境有「**单轮**删除 ≥ 50 个文件需确认」的保护。
`verify_994.py` / `verify_995.py` 跑完会清临时 dump ⇒ **同一轮里把一键验证连跑两次**，
第二次的清理就会被拦，命令被**从外部中断**（Python `try/except` 捕不到）
⇒ 脚本在自己的判据汇总行**之前**就被掐断 ⇒ 看起来像 FAIL，其实什么都没验出来。

⇒ **规矩**：同一轮里一键验证最多跑**两次**；真要连跑，先等下一轮。
（两个脚本的清理也改成了**非致命**：`_rm()` 吞异常，且首块用 `'w'` 覆盖写 ——
避免"删不掉时把上一轮的 dump 追加进来"这种更隐蔽的错。）
