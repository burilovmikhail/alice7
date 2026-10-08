# Alice7: From Memory to Persistent Identity

Research code and article for **an evolutionary architecture for continuous
LLM-based agents**.

> **Central question:** what architectural mechanisms does a language-model-based
> agent need to develop a persistent behavioral identity through experience?

"Persistent behavioral identity" is meant operationally: behavioral tendencies,
preferences, associations and intentions that come from interaction history, causally
shape later behavior, persist across sessions and silence, can change with new
experience, and can't be reduced to the current context or a textual self-description.
No claims are made about consciousness or subjective experience.

## Method

Iterative architecture ablation. Each generation adds the smallest mechanism that
addresses a limitation observed in the previous one. The base model, persona,
scenarios, sampling and evaluation stay the same, so the main thing that varies is
the architecture around the LLM.

| Version | Adds | Question |
|---|---|---|
| **V1** | Persistent memory | Can an agent keep a history? |
| V2 | Reflection, lessons, self-model, intentions | Can history change the agent? |
| V3 | Autonomous tick, sleep, consolidation | Can change happen without interaction? |
| V3.5 | Cheap background model + threshold-triggered expensive model | Can continuous cognition be affordable? |
| V4 | Non-linguistic cognitive dynamics | Can identity exist apart from the model's story about itself? |

Metrics apply across all versions: memory, plasticity, persistence, autonomy,
identity robustness (context reset, self-model ablation, model swap, false
self-belief), narrative–behavior divergence, and computational efficiency.

## Status

| Version | Spec | Implementation |
|---|---|---|
| V1 | [specs/v1/llm-chat-with-better-memory.md](specs/v1/llm-chat-with-better-memory.md) | done, frozen; preliminary results (N = 1) |
| V2 | [specs/v2/adaptive-identity.md](specs/v2/adaptive-identity.md) | implemented; preliminary results (N = 1, E5–E7) |
| V3–V4 | — | — |

## Repository

```
alice/
  common/      config, OpenRouter client, clock, tracing (shared by every version)
  v1/          V1: persistent memory (frozen)
  v2/          V2: lessons, self-model, intentions on top of V1
  baselines/   B0 stateless, B1 full transcript, B2 summary notes, B3 reflective notes
  eval/        scenario runner, probes on forks, scoring, report (version-agnostic)
prompts/       persona.md, identical for every version and condition
experiments/   scenarios e1-e7 and the filler bank
tests/         offline tests (fake LLM and embedder)
article/       paper draft, one file per section
specs/         per-version specifications
results/raw/   run artifacts (gitignored)
```

## Setup

Models are accessed through [OpenRouter](https://openrouter.ai). The key lives in a
local `.env` file that is never committed:

```bash
cp .env.example .env        # then set OPENROUTER_API_KEY=sk-or-...
uv run pytest               # offline tests, no key needed
```

## V1: persistent memory

```bash
uv run alice-v1 chat                                    # interactive chat; /help for commands
uv run alice-v1 chat --agent B2                         # chat with a reference condition
uv run alice-v1 run experiments/scenarios/e1/*.yaml     # V1, B0, B1, B2 on scenarios
```

## V2: adaptive identity

```bash
uv run alice-v2 chat                     # data/v2/memory.db (ALICE_V2_DB); --sim 2026-01-05T10:00 for a sim clock
```

In the chat, `/lessons`, `/lesson <id>`, `/portrait [history]`, `/opinions`,
`/intentions`, `/why` (the chain behind the last reply), `/reflect` and
`/switch lessons|selfmodel|intentions on|off` show and change V2 state. They are
operator commands; the model never sees them.

```bash
# conditions V2, V1, B0, B1, B2, B3 by default
uv run alice-v2 run experiments/scenarios/e5/*.yaml --estimate          # cost first
uv run alice-v2 run experiments/scenarios/e5/*.yaml --jobs 4 --out results/raw/v2
uv run alice-v2 run experiments/scenarios/e5/*.yaml --jobs 4 --out results/raw/v2 --skip-existing  # resume
uv run alice-v2 report results/raw/v2
uv run alice-v2 chain results/raw/v2/<run> --probe <probe-id>          # why a probe reply looks as it does
```

Mechanisms can be switched off for a whole run with `ALICE_V2_SWITCHES`
(e.g. `lessons,intentions`), or on a single probe with `fork: {switches: ...}` in
the scenario.

## Common to every version

- `run -n 5 --start-index 2` adds runs 2..6 to an existing pass.
- `rescore <dir>` re-scores saved replies after a rubric or check changes, without
  re-running agents (`--no-judge` for deterministic checks only).
- `report <dir>` writes `report.md` / `report.json`: scores with 95% CI, behavior vs
  B0, learning curves, self-report vs behavior, V2 state, costs, and a human
  spot-check sample.

## License

- Code: [MIT](LICENSE)
- Article text (`article/`): [CC BY 4.0](article/LICENSE)
