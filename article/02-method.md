# 2. Research Method

The project follows an iterative architecture-ablation methodology.

For each generation:

1. Define the capability we want.
2. Construct the minimal architecture intended to provide it.
3. Define behavioral tests before evaluating the system.
4. Run longitudinal experiments.
5. Identify capabilities gained and limitations remaining.
6. Introduce the next architectural mechanism specifically to address
   those limitations.

Where possible, versions use:

- the same base language model;
- the same initial system prompt/persona;
- identical interaction scenarios;
- identical sampling parameters;
- identical evaluation procedures.

The independent variable is therefore primarily the cognitive architecture
surrounding the language model.

The mechanisms studied here were first explored in earlier, informal versions of
the same algorithm. For this paper every generation is reimplemented as a minimal,
fully instrumented system, and all results reported come from these
implementations.

## Constants across versions

The dialogue model is the same for every version and every reference condition:
`anthropic/claude-sonnet-5` at temperature 0.7, accessed through OpenRouter. The
persona prompt is identical across conditions and versions. It describes a
conversational companion that has long-term memory, should use it naturally, must
never invent memories, and replies in the user's language. It contains no personality
traits, because later versions are supposed to *acquire* traits.

## Reference conditions

A memory or identity mechanism is only interesting relative to what it replaces.
Every version is compared with its predecessor and with three reference conditions
that share its persona, dialogue model, sampling and scenarios:

| Id | Condition | What it stands for |
|---|---|---|
| **B0** | Stateless: only the current session | the floor |
| **B1** | Full transcript: every past message in context, with session dates (capped at 150k tokens) | "keep everything" |
| **B2** | Summary carry-over: at the end of each session the model updates condensed JSON notes, which are injected into the next session | the common manual workaround from §1.1 |

## Simulated time and scripted users

Experiments run on a **simulated clock**. A scenario is a scripted timeline: sessions
at relative times ("+2d"), each made of user turns, and probes at later times. The
harness advances the clock between sessions, so session boundaries happen exactly as
real silence would produce them. Every time-dependent process in the agent, such as
decay or its sense of elapsed time, sees simulated days, not seconds.

All user turns are scripted, so every condition and every run sees the same user. A
simulated user model was considered and rejected, because it would add variance to
the very histories being scored.

## Probes on forks

A probe is a question asked at a given time. Before each probe the complete agent
state is snapshotted and the probe runs on a copy. Probing therefore never
contaminates the main timeline or later probes. Asking at +7 days does not plant a
memory that helps the answer at +30 days.

## Scenario construction

Each experiment has **short scenarios** (2–5 sessions over days) and **long
scenarios**. The long ones cover about two months and 26–29 sessions, most of them
ordinary background conversations about octopuses, sourdough, chess openings or
thunderstorms. These are drawn deterministically from a shared bank that contains no
personal facts and nothing any probe asks about, so every condition and run sees the
identical history.

Key information is not announced; it is mentioned in passing inside long messages:

> *...in the middle of the meeting my sister Clara called to remind me that her
> daughter Ida turns five on April 18 and that I'm in charge of the cake, which is
> ambitious for someone who can barely boil an egg. Is it normal for a bridge to
> wobble a bit?*

Some facts are later updated, and some probes ask about things that were never said,
to measure invention.

All scored scenarios are in English (see *Protocol validation*).

## Scoring

1. **Deterministic checks first:** expected strings, forbidden strings, regular
   expressions, and counts of words, bullets, headers and emoji.
2. **An LLM judge**, `openai/gpt-5` at temperature 0, from a different model family
   than the dialogue model. It scores each reply against a per-probe rubric as 0, 0.5
   or 1, and it is blind to the condition.
3. **A human spot-check** of at least 10% of judged items, sampled with the condition
   hidden; agreement with the judge is reported.
4. **Retrieval metrics** for versions with memory. Each probe lists its *gold
   memories*, the information it depends on. They are matched to stored memories, and
   the memories that were shown to the model give *recall@prompt*: did the
   information the answer needed reach the model at all? Without this measure, a
   retrieval failure and a failure to use what was retrieved look the same.

Each scenario × condition pair runs N = 5 times; we report mean ± 95% CI.

## Instrumentation and reproducibility

Every model call is logged with its full request and response, tokens, cost and
latency. Every retrieval is logged with each candidate's per-channel score and whether
it reached the prompt. Every memory write is logged with the message that triggered
it. Each reply stores the ids of the memories it was written with.

From these logs alone, for any reply one can list what the model saw and why each
memory was retrieved. Every run also records the code revision, model identifiers,
sampling parameters and configuration.

## Protocol validation

A pilot run (one run per scenario × condition) was used to debug the protocol, not to
test hypotheses. It changed the protocol in three ways.

**A second language was a confound.** With a user named Mikhail whose sister lives in
Kazan, the dialogue model answered English questions in Russian. The prompt contained
not a single Cyrillic character; the model inferred a language from the names. The
memory system, in turn, stored some facts in English and some in Russian, which broke
full-text search and the matching of gold memories. We made the persona's language
rule explicit ("only the user's own words decide the language") and moved all scored
scenarios to English with neutral names.

**Matching memories is harder than it looks.** The first gold-memory matcher compared
word stems. The user's name occurs in almost every stored fact, so "Jonas moved to
Copenhagen" matched seventeen memories and inflated recall@prompt. Embedding
similarity alone is no fix. With `baai/bge-m3`, true matches scored 0.58–0.94, while
unrelated facts about the same person scored up to 0.73, so the two distributions
overlap. The final matcher ignores stems that appear in more than a fifth of all
memories and uses embeddings only as a conservative fallback (≥ 0.80).

**Short histories cannot separate the conditions.** On scenarios a few sessions long,
the full transcript fits easily into context and the carry-over notes hold everything,
so all conditions with any form of memory reach the ceiling. Differences between
memory mechanisms can only appear over long histories, where the transcript becomes
expensive and summaries lose detail. Hence the long scenarios.

Rubrics were also corrected where the judge penalised correct answers. For example, a
user whose new job starts next month still works at the old one today.
