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
| V2 | Reflection, lessons, self-model, affect | Can history change the agent? |
| V3 | Autonomous tick, sleep, consolidation | Can change happen without interaction? |
| V3.5 | Cheap background model + threshold-triggered expensive model | Can continuous cognition be affordable? |
| V4 | Non-linguistic cognitive dynamics | Can identity exist apart from the model's story about itself? |

Metrics apply across all versions: memory, plasticity, persistence, autonomy,
identity robustness (context reset, self-model ablation, model swap, false
self-belief), narrative–behavior divergence, and computational efficiency.

## Status

| Version | Spec | Implementation |
|---|---|---|
| V1 | [specs/v1/llm-chat-with-better-memory.md](specs/v1/llm-chat-with-better-memory.md) | not started |
| V2–V4 | — | — |

## Repository

```
article/   paper draft and working notes
specs/     per-version specifications
```

Planned layout once code lands (see the V1 spec, §10): `alice/` (shared core,
versions, baselines, eval harness), `prompts/`, `experiments/scenarios/`, `tests/`,
`results/`.

## Setup (planned)

Models are accessed through [OpenRouter](https://openrouter.ai). The key lives in a
local `.env` file that is never committed:

```bash
cp .env.example .env        # then set OPENROUTER_API_KEY=sk-or-...
uv run alice-v1 chat        # interactive chat
uv run alice-v1 run experiments/scenarios/e1/*.yaml
uv run pytest               # offline tests
```

## License

- Code: [MIT](LICENSE)
- Article text (`article/`): [CC BY 4.0](article/LICENSE)
