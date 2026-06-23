# Provenance — TODO_pack_name

All seven headings below are required. The verifier checks they are present; a maintainer
reads and accepts the content before the benchmark ships. The README front-matter holds
the machine facts (metric, splits, baseline, edit surface); this card holds the human
trust + setup story.

## Source

Where the benchmark comes from — the paper, repo, or competition, with a link, and how
the data was collected or generated.

## Setup & environment

Hardware (CPU / GPU), Python version, install command, env vars the eval expects, and any
API keys, downloads, or services the user must provision. State whether it is offline.

## Data source & license

Where the data comes from, its license, and whether it may be redistributed. If it may not
be bundled, ship `data/download.sh` instead of the data.

## Baseline implementation

**How the shipped baseline works** — the algorithm/approach, why it scores what it does,
and what headroom it deliberately leaves for Arbor.

## Baseline reproduction

The number `eval dev` prints today (this must match `baseline.score` in the front-matter)
and any gap from the published number.

## Contamination assessment

**Mandatory.** Could the test split already be in a model's pre-training data? Is the
held-out split truly disjoint from dev? Explain why a high score reflects real capability
and not memorisation.

## Caveats

Known limitations — hardware sensitivity, metric noise, scope, anything a user should know
before trusting the number.
