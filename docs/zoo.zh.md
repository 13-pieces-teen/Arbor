# 基准动物园（Benchmark Zoo）

**基准动物园**是一组经过筛选、用同一套标准且可校验的格式打包的基准，让任何人都能用 Arbor 复跑并
核对数字。它放在
[`arbor-zoo/`](https://github.com/RUC-NLPIR/Arbor/tree/main/arbor-zoo) 里，每个基准一个文件夹。

zoo 是**质量封顶、不是数量驱动**。它的首要用途是 Arbor 自己的回归 harness——一小批人工核对、可复跑
的任务，用来检验 Coordinator/Executor 循环——其次才是对外展示。它**刻意不做**我们自己战绩的榜单。
未经校验的基准不进 zoo：eval 正确性是地基，一个你无法信任的基准比没有更糟。

格式是**文档优先 + 一个极小的机器契约**。一个基准就是一个文档齐全的 repo；那些体检工具和无人值守
harness 真正需要、又没法靠 prose 核对的几项事实，写在 README 顶部一小段 YAML **front-matter** 里
（**不是单独的清单文件**）。其余给人读的全部留在 prose 中。

## 一个基准文件夹包含什么

每个 `arbor-zoo/<name>/` 是一个自包含基准，装着四样东西——给 **user** 的 guide、给 **Arbor** 的
说明、一个可跑的 **baseline**、一个受保护的 **eval**：

| 文件 / 目录 | 作用 | 面向 |
| --- | --- | --- |
| `README.md` | 一段 YAML **front-matter** 契约（指标、splits、baseline、编辑面）+ 四个固定章节的 prose 正文。 | 机器 + user + Arbor |
| baseline 代码 | **baseline 实现**，也是 Arbor 的编辑面——`solution.py`，*或一整套文件 / 一个子目录*。 | Arbor 编辑 |
| `eval.sh` *或* `eval.py` | 受保护 eval 入口。`bash eval.sh dev\|test`（或 `python eval.py --split …`）打印一行 `score: <float>`。 | 受保护 |
| `task.py`（如用到） | 受保护 ground truth：问题生成器、参考解、独立校验器。 | 受保护 |
| `data/` | 随包数据；不可再分发时放 `download.sh`。 | — |
| `PROVENANCE.md` | 来源、环境与配置、license、baseline 实现、baseline 复现、污染评估、注意事项。七个固定章节。 | 人工审核 |

**baseline 可以不止一个文件**——front-matter 里的 `edit:` 列出编辑面；其余一切（eval harness、
ground-truth 文件、数据）是受保护的其余部分。

以 `_` 开头的文件夹（如
[`_template`](https://github.com/RUC-NLPIR/Arbor/tree/main/arbor-zoo/_template)）是脚手架，所有
工具都会跳过。

### `README.md` front-matter —— 机器契约

README 最顶部一段用 `---` 围起来的小 YAML 块。只放那些非 prose、且体检/无人值守跑需要的事实：

```yaml
---
name: algotune_knn
metric:
  direction: maximize          # maximize | minimize
eval:
  cmd: "bash eval.sh"          # 可选；省略则用 eval.sh/eval.py 约定。体检会追加 dev / test
splits:                        # dev/test 怎么分——让体检能证明二者不相交
  kind: seed_range             # seed_range | path
  dev:  { base: 1000, count: 3 }
  test: { base: 9000, count: 3 }
baseline:
  score: 1.0                   # eval dev 现在打印的分数（体检核对实测是否相符）
  tolerance: 0.30              # reproduce + determinism 的相对容差
  kind: timing                 # exact | timing（timing 用比值容差）
edit: [solution.py]            # 可编辑文件/glob（≥1）；其余一切受保护
---
```

基于路径的 split 写成 `splits: {kind: path, dev: ["data/dev/**"], test: ["data/test/**"]}`。
这些字段名复用[插件](plugins.md)词汇，所以一个通过校验的基准稍加改动即可变成 plugin。

### `README.md` 正文 —— 四个固定章节

按此顺序，让每个基准读起来都一样：

1. **Task & metric** —— 任务是什么、一个解长什么样、编辑面、什么不许碰。
2. **Run the baseline** —— eval 的确切命令及其输出（安装/硬件/key 指向 PROVENANCE → Setup & environment）。
3. **Optimize with Arbor** —— 怎么把 Arbor 对准这个基准，以及建议的研究契约。
4. **Provenance** —— 指向 `PROVENANCE.md`。

### `PROVENANCE.md` —— 七个固定章节

`PROVENANCE.md` 是可信基准与"看起来像样"的基准之间的分界。必含标题：**Source**、
**Setup & environment**、**Data source & license**、**Baseline implementation**、
**Baseline reproduction**、**Contamination assessment**、**Caveats**。体检工具检查标题在场；
*内容*由人来读、由人来接受——绝不自动接受。

## 用 Arbor 跑一个基准

Arbor 在仓库根的 git worktree 里跑实验，所以请在 Arbor 检出**之外**的副本里工作：

```bash
cp -r arbor-zoo/algotune_knn /tmp/algotune_knn
cd /tmp/algotune_knn
git init -q && git add -A && git commit -qm baseline
arbor   # 在接入对话里确认契约
```

## 校验一个基准

```bash
arbor benchmark verify arbor-zoo/<name>             # 任一项不过即非零退出
arbor benchmark verify arbor-zoo/<name> --no-eval   # 仅结构检查
arbor benchmark list arbor-zoo                       # 基准的朴素索引
```

检查项证明契约能证明的，把判断题留给人工审核：

| 检查 | 档位 | 证明什么 |
| --- | --- | --- |
| `contract` | strong | README front-matter 在场且必填字段有效。 |
| `readme-sections` | strong | README 正文含四个固定章节。 |
| `provenance` | strong | PROVENANCE 七个标题齐全（含 baseline 实现 + 污染评估）。 |
| `splits-disjoint` | strong | 按声明的 split 机制，dev/test 可证明不相交。 |
| `edit-surface` | strong | 声明的可编辑文件存在；harness/ground-truth/数据不可编辑。 |
| `eval-dev` / `eval-test` | strong | `eval dev` 与 `eval test` 各能跑出可解析分数。 |
| `baseline-reproduces` | strong | 随包 baseline 在 `tolerance` 内复现 `baseline.score`。 |
| `determinism` | strong | 两次 dev 跑一致（`kind: timing` 用比值容差，否则要求相等）。 |
| `contamination` | advisory | 污染评估在场；内容需人工接受。 |

**仍交给人工**（契约证明不了意图）的有：污染评估是否诚实，以及声明的 baseline/split 是否反映真实的
留出协议，而非方便编出来的说法。

## 新增一个基准

1. 复制脚手架：`cp -r arbor-zoo/_template arbor-zoo/<name>`。
2. 填好 front-matter 契约 + baseline（一个或多个代码文件）、受保护 eval（`eval.sh` / `eval.py`、
   `task.py`）、四章节 `README.md`，以及七章节 `PROVENANCE.md`。
3. 反复跑 `arbor benchmark verify arbor-zoo/<name>` 直到退出 0。
4. 维护者审阅 PROVENANCE 卡片并接受这个基准。**起草可自动，接受不可**——且实现 baseline 的 agent
   必须与之后优化它的 loop 分开，否则评测是自证的。

!!! note "下一步"
    `arbor benchmark add "<论文 / repo / 数据集>"` 流程将让 Arbor 搜索、下载并*起草*一个你点名的
    基准——再交给校验器和你来接受。本页的格式与校验器就是这个流程的落点。
