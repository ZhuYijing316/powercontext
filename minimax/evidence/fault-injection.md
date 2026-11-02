# 故障注入验证 —— 证明验收脚本不是橡皮章

生成时间：2026-11-02T15:58:41

一个永远输出 PASS 的验收脚本没有任何价值。这份记录逐个**故意弄坏**交付物，
断言对应的验收项必须变红（FAIL），再还原并断言它恢复绿色（PASS）。
每一次破坏都在 `finally` 里还原，所以脚本中途失败也不会留下坏状态。

## 结果总览

| # | 注入的故障 | 期望变红的验收项 | 实际变红 | 还原后 | 判定 |
| --- | --- | --- | --- | --- | --- |
| 1 | seekdb 里的规格行被删掉 | `database-involved`、`context-correct` | database-involved、context-correct | database-involved=PASS、context-correct=PASS | **PASS** |
| 2 | 实现被撤回到修改前快照 | `code-change-effective` | code-change-effective | code-change-effective=PASS | **PASS** |
| 3 | 规格文件被改了但没有重新导入 | `context-correct` | context-correct | context-correct=PASS | **PASS** |
| 4 | 目标测试文件被移走 | `code-change-effective`、`context-correct` | code-change-effective、context-correct | code-change-effective=PASS、context-correct=PASS | **PASS** |
| 5 | PowerContext 不可达，任务状态读不到 | `state-reuse` | state-reuse | state-reuse=PASS | **PASS** |
| 6 | MiniMax 的原始调用记录被移走 | `minimax-involved` | minimax-involved | minimax-involved=PASS | **PASS** |

## 每条故障的细节

### 1. seekdb 里的规格行被删掉

- **怎么弄坏的**：规格条目不在数据库里了，但文件还在 —— 数据库没有真正承担存储职责。
- **期望变红的验收项**：`database-involved`、`context-correct`
- **实际变红的**：`database-involved`、`context-correct`
- **还原后**：database-involved=PASS、context-correct=PASS
- **判定**：**PASS**
- 备注：删除前 sdd_spec 有 12 行

### 2. 实现被撤回到修改前快照

- **怎么弄坏的**：matches() 没有实现，目标测试因此失败 —— 证明『修改后全绿』不是白送。
- **期望变红的验收项**：`code-change-effective`
- **实际变红的**：`code-change-effective`
- **还原后**：code-change-effective=PASS
- **判定**：**PASS**

### 3. 规格文件被改了但没有重新导入

- **怎么弄坏的**：文件与索引里的内容对不上 —— 检索结果指向的已经不是磁盘上的真实内容。
- **期望变红的验收项**：`context-correct`
- **实际变红的**：`context-correct`
- **还原后**：context-correct=PASS
- **判定**：**PASS**

### 4. 目标测试文件被移走

- **怎么弄坏的**：测试文件不在了 —— 『修改前失败 / 修改后通过』这条链就没有证据了。
- **期望变红的验收项**：`code-change-effective`、`context-correct`
- **实际变红的**：`code-change-effective`、`context-correct`
- **还原后**：code-change-effective=PASS、context-correct=PASS
- **判定**：**PASS**

### 5. PowerContext 不可达，任务状态读不到

- **怎么弄坏的**：状态存不进去也读不回来 —— 『状态能够复用』这条就不成立。
- **期望变红的验收项**：`state-reuse`
- **实际变红的**：`state-reuse`
- **还原后**：state-reuse=PASS
- **判定**：**PASS**

### 6. MiniMax 的原始调用记录被移走

- **怎么弄坏的**：拿不出模型的开发记录 —— 『MiniMax 实际参与』无法被核对。
- **期望变红的验收项**：`minimax-involved`
- **实际变红的**：`minimax-involved`
- **还原后**：minimax-involved=PASS
- **判定**：**PASS**

## 全部还原后的最终验收

六次破坏全部还原后，交付物回到未受损状态，
`python -m validation.check_acceptance` 的退出码是 **0**（0 表示七项全过）。

> 这份记录和 `acceptance.md` 一起构成「验收结论可信」的证据：
> 一方面证明交付物满足要求，另一方面证明得出这个结论的脚本在交付物不满足要求时会报警。