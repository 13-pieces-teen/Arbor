<p align="center">
  <img src="assets/hero.svg" alt="Arbor — Optimize anything" width="100%">
</p>

<p align="center">
  <em>面向通用自主科研的假设树精炼方法（Toward Generalist Autonomous Research via Hypothesis-Tree Refinement）</em>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+"></a>
  <a href="assets/arbor_paper.pdf"><img src="https://img.shields.io/badge/Paper-PDF-B31B1B?style=for-the-badge" alt="Paper"></a>
  <a href="https://github.com/RUC-NLPIR/Arbor"><img src="https://img.shields.io/badge/Code-GitHub-181717?style=for-the-badge&logo=github&logoColor=white" alt="GitHub"></a>
  <a href="https://RUC-NLPIR.github.io/Arbor/"><img src="https://img.shields.io/badge/Project_Page-Live-0E9B9B?style=for-the-badge&logo=githubpages&logoColor=white" alt="Project Page"></a>
  <a href="https://RUC-NLPIR.github.io/Arbor/docs/"><img src="https://img.shields.io/badge/Docs-Material-526CFE?style=for-the-badge&logo=materialformkdocs&logoColor=white" alt="Docs"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-D22128?style=for-the-badge&logo=apache&logoColor=white" alt="License: Apache 2.0"></a>
</p>

<p align="center">
  <a href="README.md">English</a> | <b>简体中文</b>
</p>

**Arbor 是一个自主科研智能体，它把一个长周期目标转化为持续累积的搜索过程。** 给它一个基准
（benchmark）和一个目标；它会提出假设、修改代码、运行真实实验、从结果中学习，并保留那些在
留出（held-out）数据上确实站得住脚的改进。不同于"一次性尝试、转头就忘"的做法，Arbor 会生长出
一棵**假设树**：每个想法都是一根分支——失败就剪枝，成功就收获——而洞见会反向传播，让后来的想法
从更聪明的起点出发。

Arbor 由**两个协作的智能体**组成：

- **Coordinator（协调者）** —— 科研总监。它维护想法树（Idea Tree），通过 *arbor cycle*（Arbor 循环）
  驱动搜索，并派发实验。
- **Executor（执行者）** —— 科研工程师。给定一个想法，它忠实地实现代码改动，在隔离的 git worktree 中
  运行实验，并汇报证据。

<table>
<tr><td><b>会累积的假设树</b></td><td>结果、失败模式与提炼出的洞见保存在想法树中并向上反向传播——让后来的想法从更聪明的起点出发，而不是淹没在滚动缓冲区里。</td></tr>
<tr><td><b>默认的留出纪律</b></td><td>Executor 在 dev 划分上迭代；只有在留出 test 划分上跨过可配置阈值的改进才会被合并。绝不对你优化的指标过拟合。</td></tr>
<tr><td><b>隔离、可回退的实验</b></td><td>每个实验都在自己的 git worktree、独立分支上运行。在你主动合并之前，<code>main</code> 绝不会被触碰。</td></tr>
<tr><td><b>为真实实验而生</b></td><td>长时间训练是一等公民：宽裕的超时、超时后的部分指标恢复，以及可选的分阶段预算（smoke → pilot → full）。</td></tr>
<tr><td><b>任意模型</b></td><td>Anthropic、OpenAI / Responses API，或任何通过 LiteLLM 接入的 OpenAI 兼容后端（DeepSeek、Gemini、Qwen、vLLM、Ollama、本地网关）。</td></tr>
<tr><td><b>引导与适配</b></td><td>实时终端仪表盘 + 只读 WebUI、在构思/审阅处可选的人在回路，以及一行即切的领域插件——无需改代码。</td></tr>
</table>

## CLI 版与 Skill 版

本仓库同时包含两种 Arbor 使用方式：

| 版本 | 位置 | 适合场景 | 推荐程度 |
| --- | --- | --- | --- |
| 原生 CLI runtime | Python package 和 `arbor` 命令 | 真实 Arbor 科研运行、长实验、dashboard、checkpoint、executor tools、merge/test discipline、plugins、reports | 推荐。这个路径功能更完整、更可靠，Arbor 效果最好。 |
| Agent Skill Suite | [`skills/`](skills/README.md) | 在 Codex 或 Claude Code 中复刻 Arbor-style 行为，尤其是不运行原生 Arbor runtime 的环境 | 有用的集成层和 fallback，但不如 CLI runtime 完整。 |

如果能运行 CLI，优先使用 CLI。原生 `arbor` runtime 包含完整实现：intake、Research
Contract、live dashboard、EventBus、checkpoint/resume、executor dispatch、
受保护的 dev/test 评测纪律、SearchAgent、plugins 和最终报告。

仓库根目录下的 [`skills/`](skills/README.md) 是给 Codex / Claude Code 使用的
skill suite。安装后，在 Codex 中调用 `$arbor-research-agent`，或在 Claude Code 中调用
`/arbor-research-agent`，然后像使用 Arbor 一样描述你的研究目标。若目标、指标、数据、
权限、预算或运行模式不清楚，skill suite 会先做 Arbor-style clarification，再加载
orchestrator 和各阶段 skill。它与 `src/skills/` 中原生 runtime 内部加载的技能不是同一层东西。

---

## 安装

**环境要求：** Python ≥ 3.10 与 Git。建议使用虚拟环境。

```bash
git clone https://github.com/RUC-NLPIR/Arbor.git
cd Arbor
python -m venv .venv && source .venv/bin/activate   # 推荐
pip install -e .                                    # 或：uv pip install -e .
arbor doctor                                        # 检查 PATH、git 与 API key
```

> 想要全局命令？`pipx install -e .` 可让 `arbor` 在任意目录可用。
> 文档站用 `pip install -e ".[docs]" && mkdocs serve` 构建，或点上方 **Docs** 徽章在线阅读。

---

## 快速上手

```bash
arbor setup       # 一次性：配置 provider / model / base_url / API key
arbor             # 在当前目录启动一次交互式会话
arbor doctor      # 诊断安装
```

`arbor setup` 会写入 `~/.arbor/config.yaml`，于是日常你只需直接运行 `arbor`、无需任何参数。
Arbor 启动后做的第一件事是一次**接入对话（intake）**：把你的目标、目标目录、指标、基线、预算、
dev/test 纪律以及产物路径，整理成一屏的 **Arbor 研究契约（Research Contract）**。一经你确认，
实时仪表盘便接管全程。

```bash
# 指向一个基准目录与一份配置
arbor --cwd ./benchmark --config research_config.yaml

# 一开始就给出目标；intake 会把其余部分补全
arbor "improve validation score without touching the test split" --cwd ./benchmark

# 小规模试跑
arbor --cwd ./benchmark --config research_config.yaml --max-cycles 3
```

运行过程中你可以输入 `/status`、`/tree`、`/evidence`、`/branches`、`/cost`、
`/pause`、`/resume`、`/report` 或 `/abort`。

### 准备一个基准

你的目标目录应当包含：

- 一个可运行的评测脚本（如 `run_eval.py`），
- 评测数据（最好有 **dev** 划分与留出的 **test** 划分），以及
- 一个干净的 git 仓库（没有未提交改动）。

一份最小的 `research_config.yaml`：

```yaml
# LLM/API 在 `arbor setup` 里配置；项目配置通常只放任务与预算。
task: >
  Optimize the agent's accuracy on the benchmark.
  Do NOT modify the evaluation harness or data files.

coordinator:
  max_cycles: 10          # 探索的 arbor 循环数
  max_depth: 2            # 想法树深度
  merge_threshold: 5.0    # 合并入主干所需的最小留出提升（%）
  ui:
    interaction_mode: review   # auto | direction | review | collaborative

executor:
  max_turns: 100
```

一份包含全部选项、可直接复制的示例见
[`examples/research_config.example.yaml`](examples/research_config.example.yaml)。

---

## 工作原理

### Arbor 循环（the arbor cycle）

每个循环执行六个步骤：

```
① OBSERVE   分析当前结果与失败模式
② IDEATE    基于分析与树中洞见，提出 1–3 个新想法
③ SELECT    选出优先级最高的想法去验证
④ DISPATCH  在隔离的 git worktree 中派一个 Executor 去做
⑤ BACKPROP  记录结果；把洞见抽象上推到祖先节点
⑥ DECIDE    继续 / 合并入主干 / 剪枝 / 停止
```

### 想法树（the Idea Tree）

```
ROOT (baseline: 20%)
├── 1: Retrieval optimization        [insight: "retrieval quality is the bottleneck"]
│   ├── 1.1: Constraint decomposition + verification   [40%, merged]
│   ├── 1.2: Periodic re-read injection                [40%, pruned — no net gain]
│   └── 1.3: Answer-extraction tuning                  [35%, pruned]
├── 2: Multi-perspective search      [insight: "search scaffolding hurts here"]
│   └── 2.1: Breadth-first search                      [25%, pruned]
└── 3: Code-level intervention       [insight: "code-level > prompt-level"]
    ├── 3.1: Continuation injection                    [70%, merged]
    └── 3.2: ANSWER-tag extraction                     [45%, done]
```

- **深度 0（根）：** 研究目标与全局洞见。
- **深度 1：** 研究方向（论文标题级别的想法）。
- **深度 2+：** 具体方法，由 Executor 实现并测试。

### Git 策略与评测

每个 Executor 都在自己的 worktree、独立分支上工作。已验证的改进合并进每次运行的 `trunk`；当你
满意时，再把 `trunk` 提升进 `main`（`git merge research/run_xxx/trunk`）。Executor 在 **dev**
划分上迭代，但一个改动只有在 **留出 test** 划分上跨过阈值时才会被保留——以防止过拟合。

### 人在回路（Human-in-the-loop）

用 `ui.interaction_mode`（或 `--interaction-mode`）选择你对运行的引导程度：

| 模式 | 行为 |
| --- | --- |
| `auto` | 完全自主。 |
| `direction` | 在构思阶段问你下一步往哪走。 |
| `review` | 在每个节点与 Executor 之前暂停。 |
| `collaborative` | `direction` + `review`。 |

当暂停时，你的输入会开启一段与只读伴随智能体的隔离讨论——绝不会污染 Coordinator 的上下文。
完整方法见 [`docs/`](docs/index.md)。

---

## 配置

LLM 访问只需用 `arbor setup` 配置一次（存放在 `~/.arbor/config.yaml`），只有一个 `provider`
字段——`anthropic`、`openai`（含任何 OpenAI 兼容的 Responses 端点），或 `litellm`（用于
DeepSeek / Gemini / Qwen / vLLM / Ollama / 本地网关）。key 来自环境变量或配置；项目级的任务与
预算设置放在 `research_config.yaml`。完整选项见
[配置指南](https://RUC-NLPIR.github.io/Arbor/docs/configuration/) 与
[`examples/research_config.example.yaml`](examples/research_config.example.yaml)。

---

## CLI 参考

日常你只需 `arbor`：

| 命令 | 作用 |
| --- | --- |
| `arbor` | 启动交互式科研会话。 |
| `arbor setup` | 配置 provider / model / key → `~/.arbor/config.yaml`。 |
| `arbor report <session>` | 为过往会话重新渲染 `REPORT.md`。 |
| `arbor doctor` | 诊断安装、PATH、git 与 API key。 |
| `arbor version` | 打印已安装版本。 |

更底层的入口（`run-research`、`coordinator`、`executor`、`review-research`）保留用于调试——
见 [CLI 参考](https://RUC-NLPIR.github.io/Arbor/docs/cli/)。

---

## 插件与技能（Plugins & Skills）

一行即可把智能体切换到新领域——评测协议、受保护的数据目录、必需产物以及超时预设，全部来自
该插件：

```yaml
plugin: mle_kaggle   # 切换到 Kaggle/MLE 模式
```

插件是**一个 YAML 文件**（prompt 注入点 + 配置覆盖 + profiles + 生命周期钩子 + 一份评测契约）；
技能（Skill）是智能体在运行时按需加载的 **markdown 操作手册**。一份可直接复制的 Kaggle 配置见
[`examples/kaggle_config.example.yaml`](examples/kaggle_config.example.yaml)。

---

## 输出与续跑（Output & Resume）

每次运行会在 `.arbor/sessions/` 下写出一个会话目录，包含 `REPORT.md`、`events.jsonl`、
`run_stats.json`、想法树以及每个实验的产物。运行可续跑——随时用 `Ctrl+C` 中断，之后用
`--resume` 继续；Arbor 会重新加载想法树并从中断处接续。

```bash
arbor report .arbor/sessions/<run_name>   # 重新渲染过往报告
arbor --resume --run-name <run_name>      # 继续一次被中断的运行
```

---

## 实验结果

Arbor 被作为**单一控制器**，跨模型训练、harness 工程与数据合成进行评测——仅改变材料、目标、
评测器与预算。在全部六项任务上，它都在留出 test 上胜过强单智能体基线。

| 任务 | 方向 | 初始 | Codex | Claude Code | **Arbor** | 增益 |
| --- | --- | --- | --- | --- | --- | --- |
| Optimizer Design | steps ↓ | 3325 | 3325 | 3287.5 | **3237.5** | +2.63% |
| Architecture Design | loss ↓ | 1.098 | 1.083 | 1.033 | **1.028** | +6.38% |
| Terminal-Bench 2.0 | pass ↑ | 69.81 | 73.59 | 71.70 | **77.36** | +7.55 |
| BrowseComp | acc ↑ | 45.33 | 50.00 | 53.33 | **67.67** | +22.34 |
| Search-Agent Data | gap ↑ | 5.00 | 9.00 | 12.00 | **18.00** | +13.0 |
| Math-Reasoning Data | gap ↑ | 1.04 | 6.25 | 8.33 | **20.83** | +19.79 |

在 **MLE-Bench Lite**（GPT-5.5）上，Arbor 达到 **86.36% Any-Medal**（100% 有效提交、95.45%
高于中位、77.27% 金牌）。完整协议与消融见[论文](assets/arbor_paper.pdf)。

---

## 项目结构

代码位于 `src/`，以 `research_agent` 包的形式导入。

```
src/                 # the `research_agent` package
├── core/            Shared infrastructure: ReAct loop, tools, LLM providers, context mgmt
├── executor/        Executor agent + `executor` CLI
├── coordinator/     Coordinator agent, Idea Tree, orchestrator, coordinator tools
├── cli/             `arbor` CLI: intake, live dashboard, setup, doctor, config
├── events/          Typed event bus and payloads
├── report/          Report generation
├── webui/           Read-only run-monitoring web server
├── plugins/         Domain plugins (e.g. mle_kaggle.yaml)
├── skills/          On-demand markdown playbooks
├── dashboard.py     HTML dashboard generator
├── run.py           `run-research` CLI
└── review.py        `review-research` CLI
```

---

## 引用

```bibtex
@misc{jin2026arbor,
  title  = {Toward Generalist Autonomous Research via Hypothesis-Tree Refinement},
  author = {Jiajie Jin and Yuyang Hu and Kai Qiu and Qi Dai and Chong Luo and
            Guanting Dong and Xiaoxi Li and Tong Zhao and Xiaolong Ma and
            Gongrui Zhang and Zhirong Wu and Bei Liu and Zhengyuan Yang and
            Linjie Li and Lijuan Wang and Hongjin Qian and Yutao Zhu and Zhicheng Dou},
  year   = {2026},
  note   = {Living technical report}
}
```

---

## 许可证

本项目以 [Apache License 2.0](LICENSE) 协议发布。

---

由中国人民大学高瓴人工智能学院与微软研究院共同打造。
