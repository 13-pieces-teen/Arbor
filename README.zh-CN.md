<p align="center">
  <img src="assets/hero.svg" alt="Arbor — Optimize anything" width="100%">
</p>


# 基于假设树的面向通用自主科研方法（Toward Generalist Autonomous Research via Hypothesis-Tree Refinement）


<p align="center">
  <a href="https://arxiv.org/pdf/2606.11926"><img src="https://img.shields.io/badge/Paper-arXiv-B31B1B?style=for-the-badge&logo=arxiv&logoColor=white" alt="Paper"></a>
  <a href="https://github.com/RUC-NLPIR/Arbor"><img src="https://img.shields.io/badge/Code-GitHub-181717?style=for-the-badge&logo=github&logoColor=white" alt="GitHub"></a>
  <a href="https://RUC-NLPIR.github.io/Arbor/"><img src="https://img.shields.io/badge/Project_Page-Live-0E9B9B?style=for-the-badge&logo=githubpages&logoColor=white" alt="Project Page"></a>
  <a href="https://RUC-NLPIR.github.io/Arbor/docs/"><img src="https://img.shields.io/badge/Docs-Material-526CFE?style=for-the-badge&logo=materialformkdocs&logoColor=white" alt="Docs"></a>
  <a href="https://github.com/RUC-NLPIR/Arbor/discussions"><img src="https://img.shields.io/badge/讨论区-加入-5865F2?style=for-the-badge&logo=github&logoColor=white" alt="Discussions"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-D22128?style=for-the-badge&logo=apache&logoColor=white" alt="License: Apache 2.0"></a>
</p>

<p align="center">
  <a href="README.md">English</a> | <b>简体中文</b>
</p>

**Arbor 是一个自主科研智能体，可以把长周期目标转化为持续累积的搜索过程。** 给它一个基准
（benchmark）和一个目标，它会提出假设、修改代码、运行真实实验、从结果中学习，并保留那些在
留出（held-out）数据上经得起验证的改进。不同于“一次性尝试、过后即弃”的做法，Arbor 会逐步生长出一棵
**假设树**：每个想法都是一根分支，失败则剪枝，成功则保留；洞见会沿树反向传播，让后续想法
从更可靠的起点出发。

更多详情，请访问我们的[项目主页](https://ruc-nlpir.github.io/Arbor/)并阅读[论文](https://arxiv.org/pdf/2606.11926)。如需详细的使用说明，请参阅[文档](https://ruc-nlpir.github.io/Arbor/docs/)。🧭 你也可以根据自己的环境和工作流选择使用 [CLI 版本或技能套件版本](https://claude.ai/chat/e7121091-ce2c-4970-a60f-16b54c453729#-cli-与技能套件版本)。

## 💡 为什么选择 Arbor

- **通用优化能力** — 无论是模型训练、评测工程，还是数据合成，只要有明确的优化目标和可量化的评估指标，Arbor 都能胜任。
- **真正落地可用的自主科研** — Arbor 不仅是一个研究原型，它同时提供原生 CLI 运行时和适用于 Codex 与 Claude Code 的智能体技能套件。你可以直接使用完整 CLI 以获得最佳效果，也可以在其他编程智能体中加载技能套件来使用。
- **长期结构化探索** — 假设树框架让 Arbor 能够持续运行，进行累积式搜索：实验结果、失败原因和提炼出的洞察都会保存在想法树中并向上传播，让后续想法越来越聪明，而不是淹没在无尽的上下文滚动里。
- **严格的实验纪律** — 执行器在开发集上迭代，在留出的测试集上验证，只有超过可配置阈值的改进才会被合并，有效避免对评估指标的过拟合。
- **隔离且可回滚的执行环境** — 每个实验都在独立的 git 工作树和专属分支上运行，在你主动合并之前，`main` 分支始终不受影响。
- **专为长时间实验设计** — 长时间训练是一等公民：宽裕的超时设置、超时时的部分指标恢复，以及从小规模烟雾测试到试点运行再到完整运行的可选分阶段预算管理。
- **灵活的模型与工作流支持** — Arbor 通过 LiteLLM 支持 Anthropic、OpenAI / Responses API 及 OpenAI 兼容后端，包括 DeepSeek、Gemini、Qwen、vLLM、Ollama 和本地网关。
- **高度可控与可扩展** — 实时终端仪表盘、只读 WebUI、可选的人工审核介入，以及一行配置即可切换的领域插件，让你无需修改 Arbor 核心代码就能灵活调整实验走向。

## 🧩 框架原理

<p align="center">   <img src="assets/framework.png" alt="Arbor 框架" width="100%"> </p>

Arbor 由**两个协同工作的智能体**组成：

- **协调器（Coordinator）** — 研究总监。负责维护想法树、驱动 Arbor 循环并下发实验任务。
- **执行器（Executor）** — 研究工程师。接收单个想法后，忠实地实现代码变更，在隔离的 git 工作树中运行实验，并汇报实验证据。

两者共同重复执行六步 **Arbor 循环**：

1. **观察（Observe）** — 协调器重新审视想法树，读取当前活跃前沿、约束条件、祖先节点的洞察、近期实验证据及当前最优产物。
2. **构思（Ideate）** — 选择一个父节点，提出子假设，对树中已有知识进行精化、修正或扩展。
3. **择优（Select）** — 在当前最优方向与未解决的备选方案之间取得平衡，选出最值得测试的待处理叶节点。
4. **派发（Dispatch）** — 将选中的假设分发给独立的执行器，执行器在全新工作树中实现并在开发信号上评估。
5. **反向传播（Backpropagate）** — 记录每个实验的结果、分数、洞察和分支，并将归纳出的经验向上传递给祖先节点和未来的想法。
6. **决策（Decide）** — 协调器决定是否合并、剪枝、继续探索、将节点置为待定，或终止研究，合并决策以留出集验证为依据。

## 🎬 演示

https://github.com/user-attachments/assets/49c1a306-d2e9-49d6-9c83-65e38a62df30

## 🚀 CLI 与技能套件版本

本仓库提供两种使用 Arbor 的方式：

| 版本            | 位置                                                 | 适用场景                                                     | 建议                                                        |
| --------------- | ---------------------------------------------------- | ------------------------------------------------------------ | ----------------------------------------------------------- |
| 原生 CLI 运行时 | Python 包及 `arbor` 命令                             | 真实的 Arbor 研究运行、长时间实验、仪表盘、检查点、执行器工具、合并/测试纪律、插件、报告 | **推荐使用**。功能更完整、更可靠，能发挥 Arbor 的最佳性能。 |
| 智能体技能套件  | [`skills/`](https://claude.ai/chat/skills/README.md) | 在 Codex 或 Claude Code 环境中获得 Arbor 风格的行为，无需运行原生 Arbor 运行时 | 实用的集成层和备用方案，但功能不如 CLI 运行时完整。         |

如果你能运行 CLI，就使用 CLI。原生 `arbor` 运行时包含完整实现：任务摄入、研究合同、实时仪表盘、事件总线、检查点与恢复、执行器派发、受保护的开发/测试评估纪律、搜索智能体、插件和最终报告生成。

仓库根目录下的 [`skills/`](https://claude.ai/chat/skills/README.md) 目录是一套 Codex/Claude Code 技能套件。安装完成后，在 Codex 中调用 `$arbor-research-agent`，或在 Claude Code 中调用 `/arbor-research-agent`，然后像描述 Arbor 任务一样描述你的研究目标即可。当目标、指标、数据、权限、预算或运行模式不明确时，技能套件会先进行 Arbor 风格的澄清确认，再加载协调器和各阶段技能。该目录与存放在 `src/skills/` 下的内部运行时技能是分开的。

------

## 📦 安装

**环境要求：** Python ≥ 3.10 及 Git。推荐使用虚拟环境。

```bash
pip install arbor-agent   # 或使用：uv pip install arbor-agent
arbor doctor              # 验证 PATH、git 及 API 密钥
```

> 想要全局命令？使用 `pipx install arbor-agent` 可将 `arbor` 命令安装至全局环境。

<details>
<summary>从源码安装（用于开发）</summary>

```bash
git clone https://github.com/RUC-NLPIR/Arbor.git
cd Arbor
python -m venv .venv && source .venv/bin/activate   # 推荐
pip install -e .                                    # 或使用：uv pip install -e .
arbor doctor
```

若需本地查看文档站点，运行 `pip install -e ".[docs]" && mkdocs serve`，或通过上方的 **Docs** 徽章在线阅读。

</details>

------

## ⚡ 快速开始

```bash
arbor setup       # 首次使用：配置模型提供商 / 模型 / base_url / API 密钥
arbor             # 在当前目录启动交互式会话
arbor doctor      # 诊断安装状态
```

`arbor setup` 会将配置写入 `~/.arbor/config.yaml`，此后日常使用直接运行 `arbor` 即可，无需额外参数。Arbor 启动后首先进行一次**任务摄入对话**，将你的目标、目标目录、评估指标、基线、预算、开发/测试纪律和产物路径整理成一份简洁的 **Arbor 研究合同**。确认后，实时仪表盘随即接管。

```bash
# 指定基准目录和配置文件
arbor --cwd ./benchmark --config research_config.yaml

# 预先提供初始目标，摄入对话会补全其余细节
arbor "提升验证集分数，不得修改测试集" --cwd ./benchmark

# 小规模试运行
arbor --cwd ./benchmark --config research_config.yaml --max-cycles 3
```

运行过程中，你可以随时输入 `/status`、`/tree`、`/evidence`、`/branches`、`/cost`、`/pause`、`/resume`、`/report` 或 `/abort` 来查看状态或控制流程。

### 准备基准

你的目标目录应包含：

- 一个可运行的评估脚本（例如 `run_eval.py`），
- 评估数据（最好区分**开发集**和留出的**测试集**），以及
- 一个干净的 git 仓库（无未提交的改动）。

一个最简的 `research_config.yaml` 示例：

```yaml
# LLM/API 配置由 `arbor setup` 管理；项目配置通常只需指定任务和预算。
task: >
  优化智能体在该基准上的准确率。
  不得修改评估框架或数据文件。

coordinator:
  max_cycles: 10          # Arbor 循环轮数
  max_depth: 2            # 想法树深度
  merge_threshold: 5.0    # 合并到主干所需的留出集最低提升百分比
  ui:
    interaction_mode: review   # auto | direction | review | collaborative

executor:
  max_turns: 100
```

包含所有选项的完整示例配置文件位于 [`examples/research_config.example.yaml`](https://claude.ai/chat/examples/research_config.example.yaml)。

------

## 🧠 工作原理

### Arbor 循环

每轮循环执行六个步骤：

```
① 观察（OBSERVE）    分析当前结果与失败模式
② 构思（IDEATE）     基于分析和树中洞察，提出 1–3 个新想法
③ 择优（SELECT）     选择优先级最高的想法进行测试
④ 派发（DISPATCH）   在隔离的 git 工作树中运行执行器
⑤ 反向传播（BACKPROP） 记录结果，将洞察向上抽象至祖先节点
⑥ 决策（DECIDE）     继续 / 合并到主干 / 剪枝 / 停止
```

### 想法树

```
ROOT（基线：20%）
├── 1：检索优化            [洞察："检索质量是瓶颈"]
│   ├── 1.1：约束分解 + 验证        [40%，已合并]
│   ├── 1.2：周期性重读注入          [40%，已剪枝 — 无净收益]
│   └── 1.3：答案抽取调优            [35%，已剪枝]
├── 2：多视角搜索          [洞察："搜索脚手架在此场景下有害"]
│   └── 2.1：广度优先搜索            [25%，已剪枝]
└── 3：代码层干预          [洞察："代码层 > 提示层"]
    ├── 3.1：续写注入                [70%，已合并]
    └── 3.2：ANSWER 标签抽取         [45%，已完成]
```

- **深度 0（根节点）：** 研究目标与全局洞察。
- **深度 1：** 研究方向（论文题目级别的想法）。
- **深度 2+：** 具体方法，由执行器实现并测试。

### Git 策略与评估

每个执行器在专属分支的独立工作树中工作。经过验证的改进会合并到本次运行专属的 `trunk` 分支；只有当你满意时，才将 `trunk` 推入 `main`（`git merge research/run_xxx/trunk`）。执行器在**开发集**上迭代，但一个改动只有在**留出测试集**上超过阈值才会被保留，以防止对评估指标的过拟合。

### 人工介入

通过 `ui.interaction_mode`（或 `--interaction-mode`）设置你的介入程度：

| 模式            | 行为                                   |
| --------------- | -------------------------------------- |
| `auto`          | 完全自主运行。                         |
| `direction`     | 在构思阶段询问你下一步的方向。         |
| `review`        | 在每个节点和执行器启动前暂停等待确认。 |
| `collaborative` | `direction` + `review` 的组合。        |

暂停时，你的输入会开启一个与只读伴侣智能体的独立讨论，不会污染协调器的上下文。完整说明请参阅 [`docs/`](https://claude.ai/chat/docs/index.md)。

------

## ⚙️ 配置

通过 `arbor setup` 一次性配置 LLM 访问（存储在 `~/.arbor/config.yaml`），只需填写一个 `provider` 字段：

| `provider` | 适用场景 |
| --- | --- |
| `auto`（默认） | 交给 Arbor 自动判断：探测端点的 OpenAI **Responses** API，支持就用（保留思维链），否则回退到 chat completions；Claude 模型走原生 Anthropic API。探测结果会被冻结写入配置。 |
| `openai-responses` | OpenAI / o 系列模型，走 Responses API（跨轮保留加密思维链）。 |
| `openai-chat` | 任何 OpenAI 兼容的 chat-completions 端点——DeepSeek / Qwen / GLM / vLLM / Ollama / 本地网关。 |
| `anthropic` | Claude，走原生 Anthropic Messages API（签名思维块 + 提示缓存）。 |

大多数用户只需运行 `arbor setup`、保持 `auto`、填好 `model` 与 `base_url` 即可。API 密钥从环境变量或配置文件中读取；针对具体项目的任务和预算配置则放在 `research_config.yaml` 中。详情请参阅[配置指南](https://ruc-nlpir.github.io/Arbor/docs/configuration/)和 [`examples/research_config.example.yaml`](examples/research_config.example.yaml)。

------

## 🧰 CLI 参考

日常使用只需记住 `arbor`：

| 命令                     | 功能                                                        |
| ------------------------ | ----------------------------------------------------------- |
| `arbor`                  | 启动交互式研究会话。                                        |
| `arbor setup`            | 配置模型提供商 / 模型 / API 密钥 → `~/.arbor/config.yaml`。 |
| `arbor report <session>` | 重新渲染某次历史会话的 `REPORT.md`。                        |
| `arbor export <session> [output]` | 将历史会话导出为自包含 HTML；当 `output` 以 `.jsonl` 结尾时导出 JSONL。 |
| `arbor doctor`           | 诊断安装状态、PATH、git 及 API 密钥。                       |
| `arbor version`          | 打印已安装的版本号。                                        |

底层入口点（`run-research`、`coordinator`、`executor`、`review-research`）保留供调试使用——详见 [CLI 参考文档](https://ruc-nlpir.github.io/Arbor/docs/cli/)。

------

## 🔌 插件与技能

一行配置即可将智能体切换到新领域——评估协议、受保护的数据目录、必要的输出内容和超时预设均由插件提供：

```yaml
plugin: mle_kaggle   # 切换到 Kaggle/MLE 模式
```

插件是一个 YAML 文件（包含提示注入点、配置覆盖、运行配置、生命周期钩子和评估合同）；技能则是智能体在运行时按需加载的 Markdown 手册。Kaggle 配置的开箱即用示例位于 [`examples/kaggle_config.example.yaml`](https://claude.ai/chat/examples/kaggle_config.example.yaml)。

------

## 💾 输出与恢复

每次运行会在 `.arbor/sessions/` 下创建一个会话目录，包含 `REPORT.md`、`events.jsonl`、`run_stats.json`、想法树以及各实验的产物文件。运行支持断点恢复——用 `Ctrl+C` 中断后，稍后使用 `--resume` 继续；Arbor 会重新加载想法树并从中断处继续。

```bash
arbor report .arbor/sessions/<run_name>   # 重新渲染历史报告
arbor export <run_name>                   # 写入 .arbor/sessions/<run_name>/arbor-session-<run_name>.html
arbor export <run_name> session.jsonl     # 导出 JSONL 产物包
arbor --resume --run-name <run_name>      # 继续中断的运行
```

------

## 📊 实验结果

Arbor 作为**单一控制器**，在模型训练、harness 工程和数据合成等场景中进行评测；实验中只改变材料、
目标、评测器和预算。在全部六项任务上，Arbor 都在留出 test 上超过了强大的单智能体基线。

| 任务               | 优化方向 | 初始值 | Codex | Claude Code | **Arbor**  | 提升   |
| ------------------ | -------- | ------ | ----- | ----------- | ---------- | ------ |
| 优化器设计         | 步数 ↓   | 3325   | 3325  | 3287.5      | **3237.5** | +2.63% |
| 架构设计           | 损失 ↓   | 1.098  | 1.083 | 1.033       | **1.028**  | +6.38% |
| Terminal-Bench 2.0 | 通过率 ↑ | 69.81  | 73.59 | 71.70       | **77.36**  | +7.55  |
| BrowseComp         | 准确率 ↑ | 45.33  | 50.00 | 53.33       | **67.67**  | +22.34 |
| 搜索智能体数据     | 差距 ↑   | 5.00   | 9.00  | 12.00       | **18.00**  | +13.0  |
| 数学推理数据       | 差距 ↑   | 1.04   | 6.25  | 8.33        | **20.83**  | +19.79 |

在使用 GPT-5.5 的 **MLE-Bench Lite** 上，Arbor 达到了 **86.36% 任意奖牌率**（100% 有效提交，95.45% 超过中位数，77.27% 获得金奖）。完整的实验协议和消融分析请参阅[论文](https://arxiv.org/pdf/2606.11926)。

------

## 🗂️ 项目结构

代码位于 `src/`，以 `arbor` 包的形式导入。

```
src/                 # `arbor` 包
├── core/            共享基础设施：ReAct 循环、工具、LLM 提供方、上下文管理
├── executor/        Executor agent 和 `executor` CLI
├── coordinator/     Coordinator agent、Idea Tree、orchestrator、coordinator 工具
├── cli/             `arbor` CLI：intake、实时仪表盘、setup、doctor、config
├── events/          类型化 event bus 和 payload
├── report/          报告生成
├── webui/           只读运行监控 Web 服务器
├── plugins/         领域插件（例如 mle_kaggle.yaml）
├── skills/          按需加载的 Markdown 手册
├── dashboard.py     HTML 仪表盘生成器
├── run.py           `run-research` CLI
└── review.py        `review-research` CLI
```

------

## 🙏 致谢

Arbor 构建在优秀的开源项目
[claw-code](https://github.com/ultraworkers/claw-code) 之上。

claw-code 是 Claude Code 的开源 Rust 复现，为 Arbor CLI 提供了 REPL 框架、
工具调用基础设施和跨平台编译能力。非常感谢 ultraworkers 团队的出色工作。

🔗 claw-code: https://github.com/ultraworkers/claw-code

------

## 📚 引用

```bibtex
@misc{jin2026arbor,
  title  = {Toward Generalist Autonomous Research via Hypothesis-Tree Refinement},
  author = {Jiajie Jin and Yuyang Hu and Kai Qiu and Qi Dai and Chong Luo and
            Guanting Dong and Xiaoxi Li and Tong Zhao and Xiaolong Ma and
            Gongrui Zhang and Zhirong Wu and Bei Liu and Zhengyuan Yang and
            Linjie Li and Lijuan Wang and Hongjin Qian and Yutao Zhu and Zhicheng Dou},
  year   = {2026},
  eprint = {2606.11926},
  archivePrefix = {arXiv},
  url    = {https://arxiv.org/abs/2606.11926}
}
```

------

## 📄 许可证

本项目基于 [Apache License 2.0](https://claude.ai/chat/LICENSE) 开源发布。

------

由中国人民大学高瓴人工智能学院与微软研究院联合研发。
