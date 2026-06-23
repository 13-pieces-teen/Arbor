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

### 1.2 评测纪律

- 更强的 held-out 保证，并更清楚地标明一个数字来自哪个 split。
- **污染自检**——当一个基准的 test set 很可能已在预训练数据里时给出标记，因为那会让数字
  失去意义。
- eval 防篡改——确认受保护路径在运行中确实不可写（AutoSOTA 有 anti-tampering，我们要同样
  的保证）。

### 1.3 成本与调度 {#sec-1-3}

- 预算分层（smoke → pilot → full），让较大的扫描可预估。
- 在运行开始前就给出按 backend / 按 run 的成本核算，而不是事后。

---

## 方向二 —— 外部资源

### 2.1 按 domain 划分的 benchmark zoo

一个经过筛选、已做成 Arbor 可评分 repo 形式的任务集合，按领域分组（如 CV、NLP、时序、
优化），每个任务用一篇已发表论文的结果作为要超越的 baseline。它以 `arbor-zoo/` 放在仓库
里，每个基准一个文件夹，首要用途是 Arbor 自己的回归 harness——而非我们战绩的榜单。下面是
我们打算标准化的格式，目前都还没实现。

**仓库布局。** `arbor-zoo/<benchmark-name>/`，每个基准一个文件夹；以 `_` 开头的（如
`_template`）是脚手架，工具会跳过。

**每个基准文件夹包含**——已有的可评分 repo 契约，再加两个元数据文件和一份给人读的 README：

| 文件 | 作用 |
| --- | --- |
| `solution.py` | Arbor 优化的可编辑 artifact（唯一编辑面）。 |
| `eval.sh` / `eval.py` | 受保护 eval；`bash eval.sh dev\|test` 打印一行 `score: <float>`。 |
| `data/` | 随包数据；不可再分发时放下载脚本。 |
| `pack.yaml` | 机器可读清单（metric、splits、baseline、setup、license）。 |
| `PROVENANCE.md` | 来源、license、baseline 复现、污染评估。 |
| `README.md` | 给人读的介绍，含六个固定章节（见下）。 |

**Task Pack 格式。** 把今天隐式的可评分 repo 契约提升为一个有版本的标准：一个可编辑
artifact、一个以 `bash eval.sh dev|test` 调用、只打印一行 `score: <float>` 的受保护
eval、不相交且 test 真正 held out 的 dev/test 切分，外加 `pack.yaml` 清单和
`PROVENANCE.md` 卡片。清单字段名复用 `plugin` 词汇（`eval_contract` / `protected_paths`
/ `profiles`），所以一个 pack 无需返工即可降级成 [plugin](plugins.md)。

**把 setup 要求写明。** 因为有些基准需要额外的 API key、服务或 GPU 才能跑，`pack.yaml`
带一个机器可读的 `setup:` 块（`hardware`、`python`、`install`、`env`、`services`），让
工具在运行前就能警告，并在 README 的"Setup & requirements"章节里用人读语言镜像一遍。

**来源卡片。** `PROVENANCE.md` 是可信 pack 与"看起来像样"的 pack 之间的分界：来源、数据
来源与 license、如何收集、baseline 复现（已发表数字 vs 随包 baseline 实际打印的数字，及
差距）、一项必填的污染评估，以及已知注意事项。

**两个 README。** 一个顶层 `arbor-zoo/README.md`（索引、格式、怎么用一个基准跑 Arbor、
怎么新增一个），以及每个基准一个 `README.md`，六个固定章节顺序：Task & metric →
Setup & requirements → Run the baseline → Optimize with Arbor → Provenance。

**`arbor benchmark verify`。** 一个校验器——也是校验器的规格——确认：`pack.yaml` /
`PROVENANCE.md` 可解析且完整、eval 在 dev 与 test 上各产出一个可解析的分数、baseline 能
复现声称的数字、dev/test 不相交且 held out、受保护路径不可写、eval 确定且离线、license
允许随包用途。任何一项不通过的 pack 都不进 zoo——eval 正确性是地基，未经校验的 pack 比
没有更糟。

**半自动转换。** 用 intake agent 从原始基准*起草*一个 Task Pack，再由校验器和人工接受
这一步把关。自动指的是起草自动、接受需校验——绝不自动接受。*实现* baseline 的 agent 必须
与之后优化它的 loop 分开，否则评测是自证的。

**License。** 允许再分发时附带数据；否则附下载脚本加来源卡片。

从小处起步：先做 3–5 个高质量、人工核对的 pack，覆盖不同任务形态，以
[`examples/algotune_knn`](https://github.com/RUC-NLPIR/Arbor/tree/main/examples/algotune_knn)
作为参考，再扩展。质量封顶，不是数量封顶。

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
