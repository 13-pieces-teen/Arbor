# 路线图

这是一份方向文档，不是发布排期。它列出我们想推进的几个方向，以及每个方向下的几个具体
思路。条目会随着认识的深入而移动、合并或删除。

## 定位

已经有一些自动研究系统和本计划的一部分重叠。最接近的是
[AutoSOTA](https://github.com/tsinghua-fib-lab/AutoSOTA)：一个闭环系统，会做文献调研、
改研究代码、跑实验，并维护一个按领域组织、覆盖 100+ 篇论文的 per-paper leaderboard，
带 baseline 复现和防篡改的 eval。

这种重叠是真实的，所以我们明确：Arbor **不打算**做第二个"自动优化已发表论文"的榜单。

- 我们要做的价值是一个**可复用、可校验、别人能复跑的基准格式**，而不是我们自己战绩的目录。
- 我们靠 **held-out 纪律**——只有在受保护的 test split 上超过一定 margin 才保留改动——
  而不是"刷出了更高的数字"。
- 我们首先把这套基准集合当成 **Arbor 自己的回归 harness**（用于检验 Coordinator/Executor），
  其次才是对外展示。

---

## 方向一 —— 基本功能

### 1.1 搜索与文献接地的 ideation ✅ *（已完成）* {#sec-1-1}

最初搜索被隔离在独立的 `SearchAgent` 里，idea 生成与 Coordinator 不能直接搜索开放网络。
这让基准运行保持公平——系统无法从网上抄一个成品 idea——但对真实研究太严：真实研究里，
人会先读相关工作再提方向。

已落地（默认关，基准运行保持公平），用法见
[检索与外部知识](search.zh.md)指南：

- **接地 ideation**（`search.grounded_ideation`，默认关）——ideation 阶段 Coordinator 获得
  `ResearchSearch` 工具（intent：related-work / survey / lookup / explore）。
- **分离而非禁止**——接地 lane 与新颖性审计 lane 不共享状态；塑造了某个 idea 的来源记录在该
  节点的 `grounding` 字段，与审计的 `related_work` 分开。
- **可插拔后端**，在 `search.backends` 后扇出合并：alphaXiv + Jina（免 key）、Serper + Exa REST
  （需 key）、**Exa via MCP**（免 key）、以及自托管 endpoint。读取页面经 Jina reader 免 key
  （raw-`requests` 兜底），无需 browse 端点。
- **全文与 PDF 摄取**——接地 lane 用更大的 token 预算（`research_visit_tokens`）读取并解析 PDF，
  让模型能读到论文的方法/结果章节，而不只是摘要。

尚未做：把每次检索的轮次/visit 上限做成硬性成本约束，以及给出按 run 的检索成本（归在
[1.3](#sec-1-3)）。

### 1.2 评测纪律 ✅ *（已完成）*

已完成：

- **Split 溯源**——每个分数在数据模型层就标注来自哪个 split（`dev`/`test`），并在
  REPORT.md、CLI dashboard 和 WebUI 中带标签渲染。验证过的 B_test 分数在 merge 时自动
  记录到节点与 trunk meta。
- **eval 防篡改**——受保护路径在运行中（而不仅 merge 时）做哈希校验。每个 executor 的
  worktree 会拿到其受保护文件的 SHA-256 清单，外加尽力而为的 OS 只读；运行中任何改动都会
  作废该节点的 dev 分数并阻止 merge（发出 `eval.protected_tamper`）。这堵上了 executor
  通过写 `data/`/`evaluation/` 抬高 B_dev 的口子。
- **污染自检**——声明式的 `eval_contract.contamination` 块（发布日期、`is_public`、
  canary）驱动一个非阻塞的 preflight 警告和一次 INIT 期探测（`eval.contamination_assessed`，
  记录在 tree meta）。声明式启发式 + canary 扫描现已随包；LLM 成员推断探测作为后续。

关于 `contamination` 块与运行时受保护路径强制，见 [Plugins](plugins.md) 指南。

### 1.3 成本与调度 {#sec-1-3}

- 预算分层（smoke → pilot → full），让较大的扫描可预估。
- 在运行开始前就给出按 backend / 按 run 的成本核算，而不是事后。

---

## 方向二 —— 外部资源

### 2.1 按 domain 划分的 benchmark zoo 🚧 *（格式与工具已完成；集合扩充中）*

一个经过筛选、统一格式的任务集合，按领域分组（如 CV、NLP、时序、优化），每个任务用一篇已
发表论文的结果作为要超越的 baseline。它以 `arbor-zoo/` 放在仓库里，每个基准一个文件夹，
首要用途是 Arbor 自己的回归 harness——而非我们战绩的榜单。

已完成——Task Pack 格式、校验器，以及第一个参考 pack。完整规格与校验器的检查清单见
[Benchmark Zoo](zoo.md) 指南：

- **Task Pack 格式**，每个基准一个文件夹，契约写在 **README front-matter** 里（metric、
  dev/test 切分、baseline、编辑面）——*没有单独的清单文件*。同目录还有：可运行的 baseline
  （如 `solution.py`）、一个受保护的 eval 入口（`eval.sh` / `eval.py`），对 `dev`|`test`
  各打印恰好一行 `score: <float>`、一个可选的受保护 `task.py`（确定性的 `generate_problem`
  + *独立的* `is_solution` 验证器，让“快但错”无法得分），以及一份 `PROVENANCE.md` 卡片
  （来源、license、setup/环境、baseline 复现、污染、注意事项）。
- **`arbor benchmark verify`** 为一个 pack 把关：front-matter + `PROVENANCE.md` 可解析
  且完整、eval 在 dev 与 test 上各产出一个可解析的分数、baseline 能复现声称的数字、
  dev/test held out、受保护路径不可写、eval 确定且离线。任何一项失败即非零退出——未经校验
  的 pack 不进 zoo。**`arbor benchmark list`** 索引一个 zoo 目录（只是索引，不是榜单）。
- **参考 pack + 脚手架**：
  [`algotune_knn`](https://github.com/RUC-NLPIR/Arbor/tree/main/arbor-zoo/algotune_knn)
  （已校验）和一个可复制的 `_template`。以 `_` 开头的文件夹被工具跳过。

尚未做：

- **扩充集合**到 3–5 个高质量、人工核对的 pack，覆盖不同任务形态，以 `algotune_knn` 为
  参考。质量封顶，不是数量封顶。
- **`arbor benchmark add`**——半自动转换:从一句话需求出发,agent 找到数据集,在交互终端里
  询问用户**用哪个数据集、baseline 从哪来**(收割现成的 / 按你描述的方法实现 / 上网找),并产出
  一个可运行草稿,再由校验器和人工接受这一步把关(起草自动、接受需校验——绝不自动接受)。*实现*
  baseline 的 agent 与之后优化它的 loop 分开,使评测不自证。*(已实现:discovery + 交互式
  bring-up;bring-up 的推理仍在打磨。)*
- **把一个 pack 降级成 [plugin](plugins.md)** 以实现一行改写重定向——front-matter 契约
  复用 `plugin` 词汇（`eval_contract` / `protected_paths`），应能几乎无返工地导出（与 2.2
  配套）。

### 2.2 插件库

在 `mle_kaggle` 之外提供更多范例领域插件，与上面的 Task Pack 配对，让把 Arbor 重定向到
一个领域只需改一行 `plugin:`。

### 2.3 搜索 backend ✅ *（已完成）*

方向一里的可插拔后端（alphaXiv、Jina、Serper、Exa REST、Exa via MCP、自托管 endpoint）同样是
外部资源——用户接入一次，便可跨 run 复用。见
[1.1](#sec-1-1)与[检索指南](search.zh.md)。

---

## 方向三 —— 用户展示

### 3.1 Zoo / leaderboard 视图

一个可浏览的 benchmark zoo 页面：按领域展示论文 baseline、Arbor 结果、提升，以及复现它的
确切命令。重点是可复现——每一行都是读者能复跑的东西——而不是一个计分牌。

### 3.2 运行对比

- 对同一基准的两次 run 做 diff。
- 在同一任务上跨 model/provider 比较 Idea Tree。

### 3.3 报告与导出

在今天的 `REPORT.md` 和 HTML 导出基础上，加入引用（每个 idea 背后的接地来源）和按 run
的成本明细。

---

有想法，或想认领其中一条线索？开一个
[discussion](https://github.com/RUC-NLPIR/Arbor/discussions)，或见 [贡献](contributing.md)。
