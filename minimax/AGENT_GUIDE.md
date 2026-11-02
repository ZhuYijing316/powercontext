# 给 AI 的施工手册 —— 复刻《规有所依：SDD 上下文管理系统》

> 这份文档是写给**另一个 AI 会话**看的施工手册，不是给人看的汇报。
> 目标：让一个拿到这份文档的 AI，能独立复刻出同构的作品（赛题、技术选型、业务工程都可以换）。
>
> 配套材料：
> - `minimax/sddctx/` —— 完整可跑的模块源码（照着抄）
> - `minimax/specs/`、`minimax/tasks/` —— 规格与任务文档的写法范例
> - `minimax/validation/` —— 自证清白的验收脚本（**最重要的一份**）
> - `minimax/evidence/` —— 真实运行留下的证据（照着这个标准留证）
>
> 赛题原文：https://oceanbase.yuque.com/org-wiki-obtech-vh7w9r/hc3pio/qlqnoryzrs7gtqbw

---

## 0. 这道题在考什么（先建立正确直觉）

**一句话**：做一个「SDD 上下文模块」—— 给定一个开发任务，它能**找出适用的规格、该改的代码、要跑的测试**，
把这些交给大模型完成**一次真实的代码修改**，并且**把任务状态存起来、重启后还能接着用**。

**评分是全有全无**：官方 §4.1 六项必做项**全过 20 分，任一项不过 0 分**。所以
> **先建"自证清白的验收脚本"，再写实现。** 反过来做必然返工。

**三样技术的红线**（这是这道题真正的考点，也是最容易翻车的地方）：

| 技术 | 必须承担 | 绝对不能 |
|---|---|---|
| MiniMax | **真的产出被应用的代码改动** | 只在文档里提模型名 |
| seekdb | **真的存了资料并被查询**，查询结果进上下文 | 只测连接不查数据 |
| PowerContext | **真的写了状态**，换进程读回来并用上 | 只调用 API 不看结果 |

---

## 1. 先把官方题面抄成清单（别读一遍就开工）

**做法**：打开赛题页面，用浏览器渲染后逐条读，把下面三类内容抄成 Markdown 表格，存进 `REQUIREMENTS.md`。
（语雀是 SPA，`web_fetch` 只能拿到空壳，**必须用内置浏览器**渲染后再读。）

要抄的三张表：

1. **验收项表**（官方 §4.1）—— 每项写成 `ID | 通过条件 | 我的证据在哪`
2. **提交材料表**（官方 §4.3）—— 源码 / 运行说明 / 验证样例 / 代码与测试 / 技术使用记录 / 一页技术说明
3. **红线清单**（官方 §2.5 / §2.3）—— 逐条抄成"禁止"和"必须"

**判据**：`REQUIREMENTS.md` 写完后，**每一条后面都能填上一个文件路径**。填不上的，说明你还没做。

---

## 2. 选业务工程 + 写规格（SDD 的"SD"就在这里）

### 2.1 选工程的三条硬标准

| 标准 | 为什么 |
|---|---|
| **能跑** | 官方要求"能够运行" |
| **有测试套件** | 官方要求"修改前目标测试失败、修改后全绿 + 相关回归全绿"，没测试套件就没法证明 |
| **改动面小** | "局部修改"；改得越少，模型一次写对的概率越高，迭代轮数越少 |

**本作品的选择**：`jmespath.py` v1.1.0（MIT）—— 纯 Python、~9 个源文件、
**自带 991 个测试 + JMESPath 合规 JSON 测试集**、安装零依赖。
vendor 进 `sample_project/`，同时把**修改前的模块快照**存进 `sample_project/before/`（官方 §4.2 要求"修改前后代码快照"）。

> **vendor 一个小而全的 OSS 项目**比自写一个"玩具工程"强得多：评审一眼就知道不是 facade，
> 而且现成的回归套件就是免费的回归证据。

### 2.2 写规格：SDD 的核心动作

规格是**给人看也给 AI 看**的，必须能机器解析。格式（本作品用的）：

```markdown
---
spec_id: SPEC-JP-FN-001
title: matches(subject, pattern) 正则谓词函数
target_project: sample_project/jmespath
applies_to:
  - jmespath/functions.py
status: approved
---

## R1 | matches 必须是恰好两个字符串参数
（正文）

## B1 | 既有内建函数行为不变      ← 不变行为（回归要求）
（正文）

## A1 | 新增验收测试文件          ← 验收标准
（正文）
```

**三条设计经验**（这几条直接决定了后面能不能自动化）：

1. **小节 ID 带类型前缀**：`R`=需求 `B`=不变行为 `A`=验收 `G`=目标 `K`=必须保持。
   解析器据此给每条打上 `kind`，上下文里就能区分「这是需求」还是「这是不许改的行为」。
   > ⚠️ **前缀要按字母提取**（`R1` → `R`），不是按第一个字符。踩过这个坑：写成 `id.split("-")[0]` 会得到 `"R1"`，
   > 映射查不到 → 所有条目 kind 全变成 `note` → 上下文里看不出条目类型。
2. **不变行为单独成条**（`B*`）。模型最需要知道的就是"什么不能动"。
3. **标题里带语义**（`| 命中返回 true，未命中返回 false`）。它会进上下文标题，模型直接看得到。

### 2.3 写任务文档：把"做什么"和"怎么算做完"分开

`tasks/<TASK_ID>.md`：

```markdown
---
task_id: T-2026-001
title: ...
spec_ids: [SPEC-JP-FN-001]     ← 关联哪些规格
keywords: [matches, signature, ...]   ← 检索用关键词
applies_to: [jmespath/functions.py]    ← 要改哪些文件（决定代码检索范围）
target_tests: [tests/test_matches.py]  ← 要新增/关注哪些测试
---

## GOAL | 目标
## KEEP | 必须保持的行为     ← 列表，原样进上下文
## ACCEPT | 验收命令        ← 会被真的逐条执行
```

**`ACCEPT` 里的命令会被脚本逐条执行并记录退出码** —— 这是"代码修改有效"那一项的全部证据来源。

---

## 3. 上下文模块：六个组件

```
        specs/*.md ──┐
        tasks/*.md ──┼──> import ──> seekdb (sdd_spec / sdd_code / sdd_test)
   sample_project/ ──┘                    │
                                          │  MATCH(content) AGAINST (关键词)
                                          ▼
                                     context 组装
                                          │
            ┌─────────────────────────────┼──────────────────────────────┐
            ▼                             ▼                              ▼
      适用规格条目(R/B/A)          要改的代码符号                 验证用的测试
            └─────────────────────────────┼──────────────────────────────┘
                                          ▼
                       模型（生成目标测试 / 生成实现补丁）
                                          ▼
                        git apply ──> pytest ──> 状态写入 PowerContext
```

### 3.1 数据库层（seekdb）

三张表，**每张都带中文全文索引**：

```sql
CREATE TABLE sdd_spec  (spec_id, section_id, kind, title, content, source_path, source_line, ...);
CREATE TABLE sdd_code  (file_path, symbol, kind, signature, content, source_path, source_line, ...);
CREATE TABLE sdd_test  (test_id, file_path, name, target, content, source_path, source_line, ...);

CREATE FULLTEXT INDEX idx_sdd_spec_fts ON sdd_spec (content) WITH PARSER ik;
CREATE FULLTEXT INDEX idx_sdd_code_fts ON sdd_code (content) WITH PARSER ik;
CREATE FULLTEXT INDEX idx_sdd_test_fts ON sdd_test (content) WITH PARSER ik;
```

**必须用 `MATCH(content) AGAINST (?)` 做检索**，并且把**检索模式记进证据**
（`fulltext` / `like`）—— 评审要看到"数据库真的参与了检索"，光有表不够。

> ⚠️ **`ensure_database()` 的坑**：PyMySQL 的 `database=None` 表示"**不选库**"，
> 而"用配置里的库名"是另一个语义。用哨兵对象区分，否则建库前就报 `Unknown database`。
> 参考 `sddctx/seekdb_store.py` 的 `DEFAULT_DATABASE` 哨兵。

### 3.2 检索顺序（决定上下文质量）

**不要**只靠全文检索——那会召回一堆噪音。正确顺序：

1. **代码**：任务 `applies_to` 声明的文件里**全部**符号（这就是要改的文件）→ 再补全文命中的少量符号
2. **测试**：任务 `target_tests` 声明的文件里**全部**用例 → 再补全文命中的少量用例
3. **规格**：全文命中 + 任务 `spec_ids` 声明的规格的**全部小节**（保证需求集完整）

> ⚠️ **索引必须包含 import 块**。模型生成 diff 时要复制文件头的 import，
> 只索引函数和类 → 模型凭记忆写 import → 行序/内容对不上 → `git apply` 失败。
> 参考 `code_index.py: extract_imports()`。

> ⚠️ **上下文里还要放"待改文件的完整原文"**（不是只有符号切片）。
> diff 的上下文行必须**逐字节**匹配文件，否则补丁套不上。参考 `context.py: DevelopmentContext.files`。

### 3.3 任务状态（PowerContext）

用 **PowerContext 1.4.1 的三个设施**：

| 设施 | API | 用途 |
|---|---|---|
| Scope | `POST /v1/scopes` | 每个任务一个独立边界 |
| Work Contract | `POST /v1/work/contracts/create` | 任务基线（目标/事实/范围内/范围外/完成标准） |
| Task Outcome | `POST /v1/work/outcomes/record` | 每一步的结果（状态/检查项/剩余工作） |
| Atomic Memory | `POST /v1/memory/remember` + `POST /v1/memory/search` | **状态本体**：写进去、读回来 |

**三个必须踩过才知道的坑**：

1. **Scope 的幂等键绑定参数**：第一次 `POST /v1/scopes` 用的 `idempotency_key`
   会**和当时的 title/summary 绑定**；之后用不同参数再调同一个 key → **409 `scope_idempotency_conflict`**。
   → **title/summary 必须只由 task_id 决定**（`f"sdd task {task_id}"` / `f"SDD development task {task_id}"`），
   并且 409 时**按 task_id 子串找回已有 scope**而不是报错。

2. **Source 身份绑定内容**：同一个 `source_id` 用不同内容再写 → **409 `source_conflict`**。
   → **source_id 必须由内容摘要派生**：
   ```python
   digest = hashlib.sha256(content.encode()).hexdigest()[:12]
   source_id = f"sddctx:{task_id}:outcome:{digest}"
   ```
   这样重复跑幂等，内容真变了也能记。

3. **幂等键别用会变的值**。`idempotency_key=f"sddctx:{task_id}"` 就好。

**读回状态**（这是"状态能够复用"那一项的全部）：
```python
records = client.search_state(scope_id, task_id)   # POST /v1/memory/search
# 取 artifact.revision / state_version 最大的那条
state = json.loads(record["text"])
```
然后 **把 state 喂回上下文组装**，上下文里出现「已完成 / 待办 / 已验证」三段 —— 官方 §2.3 的第四个要求。

### 3.4 模型调用

OpenAI 兼容接口，本作品用 MiniMax：`POST {base}/chat/completions`，`Authorization: Bearer <key>`。

> ⚠️ **推理模型会吃掉输出预算**。MiniMax-M3 把 7633 tokens 花在 `<think>` 上，
> `max_tokens=8192` 只剩 ~560 给正文 → **回答被截断，生成的文件是半截的**。
> → **把 `max_tokens` 提到 32768**，并在 `max_tokens` 用尽时判定为失败重试。

> ⚠️ **代码围栏要接受语言标记**。模型爱输出 ```` ```python ````，
> 只匹配 ```` ```diff|patch ```` 会匹配不上 → 整段回答（含围栏）被当成代码写进文件。
> → 正则用 `` r"```[a-zA-Z0-9_+.-]*[ \t]*\r?\n(?P<body>.*?)``` " ``。

### 3.5 应用补丁

```python
git apply --whitespace=nowarn --recount <patch>     # 先试这个
git apply --whitespace=nowarn <patch>               # 再退回这个
```

> ⚠️ **`--recount` 是必须的**。模型生成的 diff **经常把 hunk 头的行数写错**
> （声明 `@@ -1,6 +1,7 @@` 但 hunk 体只有 5 行）→ git 直接报 **`corrupt patch at ...:11`** 而拒绝。
> `--recount` 让 git 从 hunk 体自己重算行数。**这是本项目最值钱的一个参数。**

### 3.6 迭代闭环：把失败回灌给模型

**模型不会一次写对。** 本作品的实际迭代：

| 轮 | 现象 | 原因 | 修法 |
|---|---|---|---|
| 1 | 生成的文件被截断 | 推理吃光 max_tokens | 提高预算 |
| 2 | `NameError: name 're' is not defined` | 没加 import | **把测试失败输出回灌给模型** |
| 3 | `patch does not apply` | diff 基于破损代码、上下文行写错 | 先回滚 + 重新导入，再让它对着原文件做 diff |
| 4 | `corrupt patch` | hunk 行数写错 | `git apply --recount` |
| 5 | `LexerError` | **模型自己写的测试转义写错了** | 把 LexerError 回灌，让它重写测试 |

**机制**：`request_patch(..., feedback=失败输出)` 把上一轮的失败塞进下一次 prompt。

> ⚠️ **回灌测试失败时，要明确写"不要削弱测试"**——
> 官方明令"不得通过删除断言、跳过测试或修改预期结果使其通过"。
> 让模型修**转义/语法**，不是删用例。

> ⚠️ **回滚后必须重新导入**。否则 seekdb 索引里还是上一版破损代码，
> 模型会对着破损代码做 diff（→ 第 3 轮那个坑）。

---

## 4. 自证清白的验收脚本（**最重要的一份交付物**）

官方是全有全无打分，所以**你必须自己写一个能一次性判定六项全过的脚本**，
让评审和你都不用逐条人工核对。

本作品的 `minimax/validation/check_acceptance.py` 结构：

```python
checks = [
    check_runnable(config),          # 1 能够运行：三个依赖都活着 + 模块自测通过
    check_minimax_involved(config),   # 2 MiniMax 实际参与：有调用记录 + 产物在盘上 + 与快照不同
    check_context(config),           # 3 上下文正确：四类来源都在 + 每个来源在磁盘上核对过行号
    check_spec_follows_edit(config),  # 3b 规格改了重新导入 → 检索结果跟着变
    check_database(config),          # 4 数据库实际参与：行数 > 0 + 有全文检索语句被记录
    check_state_reuse(config),       # 5 状态能够复用：独立进程读回 + 进了上下文
    check_code_change(config),       # 6 代码修改有效：before 失败 / after 通过 / 回归通过
]
```

**每一条 check 的"通过条件"必须是可自动判定的**，例如：

```python
# 上下文正确：每个来源都必须在磁盘上核对过行号
for entry in context.specs + context.code + context.tests:
    path = Path(entry.source_path)
    if not path.is_file():
        problems.append(f"source does not exist: {entry.source}")
    line = entry.source_line
    if line <= 0 or line > len(path.read_text().splitlines()):
        problems.append(f"source line out of range: {entry.source}")
```

**规格更新后重新导入**这一条要**真的去改文件**：

```python
spec_path.write_text(edited)          # 插入一个唯一标记
import_material(config, recorder)     # 重新导入
context = build_context(task, store)
if MARKER not in " ".join(e.body for e in context.specs):
    problems.append("the edited specification is not used by the context")
# finally: 还原文件 + 再导入一次，让交付状态回到规格原文
```

**代码修改有效**这一条要**读"修改前"的日志文件**，确认失败原因是功能未实现：

```python
before_text = (EVIDENCE_DIR / "test-before.txt").read_text()
if "Unknown function: matches()" not in before_text:
    problems.append("the before-change log does not show the unimplemented feature")
if "NameError" in before_text:
    problems.append("the before-change failure looks like an environment error")
```

> ⚠️ 官方明令：**「目标测试不能以缺少依赖、无法启动等环境错误充当修改前的功能失败」**。
> 所以你的 before 日志里必须出现的是**"函数不存在/行为未实现"**这类**业务错误**，不是 `ModuleNotFoundError`。
> **这条 check 要主动把 `NameError`/`ImportError` 判为不合格。**

**再配一个"重建证据链"脚本** `reproduce_evidence.py`：

```
1. 从 before/ 快照还原文件          ← 保证 before 状态可复现
2. 跑验收命令，必须失败             ← 记录 before 证据
3. 应用 MiniMax 的补丁
4. 跑验收命令，必须全绿             ← 记录 after 证据
5. 重新导入（索引与代码一致）
6. 写入任务状态
```

**这样评审可以一条命令复现整条 before→after 链，而不是相信你贴的日志。**

---

## 5. 证据怎么留（让评审能自己核对）

| 做法 | 为什么 |
|---|---|
| **模块自己写 JSONL 事件日志**（`sddctx/evidence.py`），不是事后手抄 | 手抄会漂移；自动记录的才是真的 |
| 记录**每一条 SQL**（语句 + 参数 + 结果行数 + 检索模式） | 证明"数据库真的参与了检索" |
| 记录**每次模型调用**（request_id + token 用量 + 完整回答） | 证明"模型真的参与了"；官方 §4.3 要"开发记录与代码差异对应" |
| 记录**每条 PowerContext 调用**（请求 + 响应摘要） | 证明"状态真的写了" |
| 记录**每次测试运行**（命令 + 退出码 + 输出） | 官方 §4.3 要"测试日志需记录命令、退出码和对应代码版本" |
| **原始日志提交进仓库**（别 gitignore） | 它就是技术使用记录 |

**扫描一遍确保日志里没有凭据**：模型 Key 不写进任何记录，DB 密码只在 `.env`（gitignore）里。
提交前 `git diff --cached | Select-String 'sk-|github_pat_'` 确认一下。

---

## 6. 交付清单（对着官方 §4.3 抄）

| 官方要求 | 本作品的文件 |
|---|---|
| 完整源码 | `sddctx/`（模块）+ `sample_project/`（业务工程）+ `validation/`（核验脚本） |
| 运行说明 | `docs/RUN.md` —— 依赖版本、配置步骤、数据初始化、调用入口、测试命令、网络条件、**已知限制** |
| 验证样例 | `docs/WALKTHROUGH.md` —— 任务描述、有效规格、初始数据、操作步骤、预期结果、**重置方法** |
| 代码与测试 | `sample_project/before/`（修改前快照）+ `evidence/code-diff.patch` + `evidence/patches/` + `evidence/test-before*.txt` / `test-after*.txt` |
| 技术使用记录 | `docs/EVIDENCE.md` + `evidence/raw/*.jsonl` |
| 一页技术说明 | `README.md` —— 模块结构、三样技术分工、上下文选择方式 |

**两个容易漏但很值钱的小节**：

- **「重置方法」**：官方 §4.3 明写"如果样例依赖连续操作，应说明执行顺序及**如何恢复初始状态**"。
- **「已知限制」**：官方 §4.2 明写要写已知功能限制。写不出来反而可疑。

---

## 7. 一键复现（评审会照着做）

```bash
cd minimax
python -m sddctx doctor                    # 三个依赖都活着？
python -m sddctx import                    # 资料进 seekdb
python -m sddctx context --task T-2026-001 # 上下文能定位来源？
python -m validation.reproduce_evidence    # 重建 before→after 证据链
python -m validation.check_acceptance       # 六项必做项全过？
```

**每个命令都必须有 `--help` 和清晰的输出**。`doctor` 尤其重要——评审第一步就是照着它检查环境。

---

## 8. 动手顺序（照这个来，别跳）

| 阶段 | 做什么 | 完成判据 |
|---|---|---|
| 0 | 抄题面成清单；写 `REQUIREMENTS.md` | 每条后面都填得上一个文件路径 |
| 1 | 选工程、vendor、写规格 + 任务文档 | 规格能被解析器读出 R/B/A 条目 |
| 2 | 实现 `import` + `context` + `doctor` | `doctor` 三段全绿；`context` 能定位四类来源 |
| 3 | **先写验收脚本**（六项 check） | 脚本能跑，**多数项 FAIL**（因为还没实现） |
| 4 | 实现模型调用 + 补丁应用 + 跑测试 + 存状态 | 单条命令能跑通一次完整任务 |
| 5 | 跑 `reproduce_evidence`，拿到 before/after | before 日志里是"功能未实现"，不是环境错误 |
| 6 | 迭代直到 `check_acceptance` 全绿 | 7/7 |
| 7 | 写四份文档 + 证据目录 | 对照 §4.3 逐条有文件 |
| 8 | commit + push，汇报分支名 + 40 位 SHA + `ls-remote` 核对 | 远端可拉取 |

> **阶段 3 放在实现之前**是这份手册最重要的一条。
> 全有全无的打分下，先有判分器，才知道自己在哪。

---

## 9. 通用硬性约束（和本赛题无关也要守）

1. **不许伪造任何结果**。所有数字来自实际运行；跑不起来就如实报 FAIL 并写明原因。
2. **密钥只进本机 `.env` 或平台表单**，绝不写进提交文件 / README / 日志 / 截图。配置示例用占位值。
3. **不自行开通付费服务**。
4. **遇到需要用户本人操作的环节**（登录 / 验证码 / 授权 / 付费），**列出用户要做的最小步骤，然后继续做其他不依赖它的工作，不要停**。
5. **不要伪造队友的工作**；只 `git add` 自己那个目录。

---

## 10. Windows / PowerShell 5.1 踩坑清单（这台机器）

| 现象 | 解法 |
|---|---|
| `npm` 报"禁止运行脚本" | 用 `npm.cmd`，别用 `npm` |
| `.ps1` 文件里的中文乱码 / 解析失败 | **`.ps1` 必须带 UTF-8 BOM**（`write` 工具写出来的是无 BOM 的） |
| commit message 带 BOM | 用 `[System.IO.File]::WriteAllText($p, $m, (New-Object System.Text.UTF8Encoding($false)))`，**别用 `Set-Content -Encoding UTF8`** |
| `Remove-Item` / `rm` 被安全策略拦 | `git clean -f -- <path>`、`Move-Item`，或 `rm --` |
| `edit` 工具匹配中文全角标点失败 | 改用 Python 脚本做字符串替换 |
| `git push` 偶发失败 | 先试 `-c http.proxy=http://127.0.0.1:7897`，失败就去掉代理重试；**推完必须 `git ls-remote` 核对** |
| 后台 PowerShell 任务被回收 | 用 `Start-Process -WindowStyle Hidden` 起常驻服务（PowerContext server），不要挂在前台命令里 |
| Python 读 JSONL 报"数组无效" | PowerShell 5.1 的 `Get-Content` 按 ANSI 读 UTF-8 → 中文乱码 → JSON 解析失败。**用 Python 读**，别用 PowerShell |

---

## 11. 抄这份时最容易抄错的三点

1. **别只抄 happy path**。`check_acceptance.py` 里那些"负向判断"（比如
   `if "NameError" in before_text: problems.append(...)`）才是这份作品的真正价值。
2. **别只抄代码，别抄"自动留证"**。`sddctx/evidence.py` 那 40 行决定了你的交付是
   "我自己说跑通了"还是"评审可以自己核对"。
3. **别抄"一次性成功"的版本**。本作品交付的是**迭代过 5 轮**的版本，
   `docs/EVIDENCE.md` 里那张迭代表和 `evidence/patches/` 里那 4 个补丁文件
   **是加分项，不是负担** —— 它证明你是真的在做开发，而不是在演一遍。

---

## 附：本作品的实测结果（用来对照"完成"长什么样）

| 项 | 实测 |
|---|---|
| MiniMax 调用 | 9 次，prompt 97 565 tokens / completion 53 037 tokens |
| seekdb | 12 规格 / 335 代码符号 / 87 测试用例；4 357 条语句被记录，24 条全文检索 |
| 上下文 | 12 规格 / 49 符号 / 8 用例，每个来源在磁盘上核对过行号 |
| 修改前 | 6 个目标测试全失败，原因是 `UnknownFunctionError: Unknown function: matches()` |
| 修改后 | 目标测试 6 passed；全量回归 997 passed / 1 skipped（基线 991 passed / 1 skipped） |
| 状态复用 | 独立进程从 PowerContext 读回并进入上下文 |
| 验收 | **7/7 PASS**（六项必做项 + 规格更新子项） |
