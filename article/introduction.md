# From Memory to Persistent Identity:
## An Evolutionary Architecture for Continuous LLM-Based Agents

> Working title.

---

# Central Research Question

**What architectural mechanisms are required for a language-model-based
agent to develop a persistent behavioral identity through experience?**

We use *persistent behavioral identity* operationally rather than
philosophically: a set of behavioral tendencies, learned preferences,
associations, intentions, and response patterns that:

1. emerge from the agent's interaction history;
2. causally influence future behavior;
3. persist across sessions and periods without interaction;
4. can change through subsequent experience;
5. are not reducible to the current conversation context or a textual
   description of the agent's personality.

This work does not attempt to establish consciousness, sentience, or
subjective experience.

---

# 1. Introduction

## 1.1 The original engineering problem

What began as a simple engineering question—

**How can a conversational language model remember a person across sessions?**

—gradually exposed a deeper problem.

Retrieving past information allows an agent to refer to its history,
but does not necessarily give that history causal influence over the
agent itself.

Conventional conversational LLMs have a fundamental practical limitation:
their interaction history grows continuously.

Keeping the complete history in context eventually becomes increasingly
expensive and inefficient, while truncating the history destroys information
that may be important for long-term interaction.

A common practical workaround is to periodically summarize a conversation,
extract important facts, and inject this condensed representation into a
fresh context.

This led to our initial question:

> What if, instead of maintaining a transcript of the conversation,
> we maintain something resembling memory?

Messages could become experiences rather than permanent pieces of context.
Experiences could decay, become associated with other experiences, differ
in importance, and be retrieved when relevant.

We therefore began with the simplest possible architecture:
a conversational LLM equipped with persistent memory.

What followed was not designed as a cognitive architecture from the outset.

Instead, each subsequent architecture was introduced to address a limitation
observed experimentally in the previous one.

---

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

---

# 3. V1 — Persistent Memory

## Research question

**Can persistent memory give a conversational agent a meaningful history?**

## Motivation

A conventional chatbot's past exists inside its conversation context. Either the
context grows without bound, or it is truncated and the past is lost. The common
workaround (§1.1, condition B2) is to have the model condense the conversation into
notes for the next session.

V1 replaces the growing transcript with persistent, structured memory: messages
become *experiences*. These are separate units that are stored, linked to each other
and to the people and places they mention, weighted by importance, allowed to fade,
and recalled when relevant.

V1 is the first and simplest generation and the baseline for everything after it. It
must therefore be minimal: nothing that belongs to a later version may leak into it,
otherwise ablation results are confounded.

## Architecture

One turn consists of five steps:

    user message
        ↓
    1. retrieval      hybrid search over persistent memory
        ↓
    2. context        persona + stable facts + date        (system)
                      last N messages of this session       (history)
                      <memory> block + the message          (user)
        ↓
    3. LLM            response
        ↓
    4. persist        the raw message and the reply; ids of memories that were shown
        ↓
    5. extraction     a cheaper model turns the new messages into facts, entities, relations

    session end (3 h of silence) → episode → links → context reset

Extraction, summaries and episodes use `google/gemini-3.5-flash-lite` at temperature
0. Embeddings come from `baai/bge-m3`.

### Memory units

V1 stores two kinds of memory.

- **Facts** are self-contained third-person statements extracted after every turn
  ("Jonas is allergic to walnuts"). Stable personal data such as name, family, city,
  profession and durable preferences is marked *core* and is always in the system
  prompt. Everything else is retrieved by relevance.
- **Episodes** are 2–5 sentence accounts of a finished conversation: what was
  discussed, what happened, agreements, what the agent said or promised, and the
  user's observed mood. An episode is written when a session ends.

Memories are connected in a small graph:

- **entities** (people, pets, places, organisations, topics) and the relations
  between them ("Clara — sister of — the user");
- **`contains`** links from an episode to the facts learned in it;
- **`led_to`** links from a cause to its effect, created only between memories the
  extracting model was actually shown. The prompt states that thematic similarity
  is not causation.

Memory is **non-destructive**. A fact that changes ("moved to Copenhagen") closes the
old one rather than overwriting it, and the old record keeps a pointer to its
replacement. A new fact nearly identical to an existing one (embedding cosine ≥ 0.95)
is merged instead of stored twice.

### Retrieval

The current message is the query. Candidates come from five channels whose scores
are added:

| Channel | Contribution |
|---|---|
| Semantic similarity | top 30 by cosine (≥ 0.35), `0.6 · sim` |
| Full-text match | top 30, `0.3 / (1 + 0.3 · rank)` |
| Mentioned entities | `+0.3` for every memory linked to an entity named in the message |
| Time expressions ("yesterday", "last Thursday") | episodes from that period `+0.5`, facts `+0.2` |
| One hop over links from the top 5 | `led_to` `0.5 · parent`, other links `0.4 · parent` |

The raw score is weighted by importance and by **retention**. Retention is an
exponential forgetting curve whose half-life stretches with importance, with how
often the memory has been recalled, and with how many later memories grew out of it:

    half_life = 30 d · (0.5 + importance) · (1 + 0.3 · ln(1 + recalls)) · (1 + 0.5 · ln(1 + consequences))
    retention = 0.5 ^ (age / half_life)
    score     = raw · (0.6 + 0.4 · importance) · (0.55 + 0.45 · retention)

Age is counted from the last time the memory was recalled, so being shown in a prompt
refreshes it. Decay affects only ranking: nothing is ever deleted because it is old.
The top 12 memories above a threshold go into the prompt within a 1,500-token budget.

### Sense of time

Every turn carries the current date and time, and notes a pause if the user returns
after more than half an hour. At the start of a session the agent also sees how long it
and the user have known each other, which conversation this is, and a short summary of
the previous one. Each recalled memory is shown with its age ("3 days ago"). Relative
dates in the message are resolved into a time range for retrieval.

### Short-term memory and sessions

Within a session the last 12 messages are kept verbatim. Older ones are folded into a
rolling summary of at most 150 words. After three hours of silence the session is
over: it becomes an episode, and the next session starts with an **empty buffer**.
Every session boundary is therefore a real context reset, and anything the agent
knows about earlier conversations has to come through memory.

### What V1 deliberately does not have

- reflection, lessons or behavioral rules;
- a self-model, portrait or beliefs;
- affect or mood, including emotional tagging of memories;
- personality facets or a chosen identity;
- any background or autonomous process;
- self-editing prompts;
- tools, including tools for managing its own memory.

Two of these exclusions are less obvious.

**No memory tools.** If the agent could call `remember`, `recall` or `forget`
itself, memory would be partly agent-managed. That is a different architecture, and
it would blur the claim under test: that the past reaches behavior only through
*retrieval into context*. V1 memory is passive.

**Prompts record, they don't prescribe.** The extraction and episode prompts are told
explicitly to record what happened and what is true, including the agent's own words
and promises, and never to turn experience into advice or rules for future behavior.
"The user prefers short answers" is a fact V1 may store. "I should answer briefly
from now on" is a lesson, and lessons belong to V2.

An automated guard test fails the test suite if V1's code, schema or prompts
reference any later-generation mechanism.

### Extraction over long histories

Over long histories the extraction model began storing summaries of conversations
("Alice and Jonas discussed…") as if they were facts, imitating the episodes it was
shown as context. These duplicated episodes and polluted retrieval: 4 of 46 facts in
one long run. Labelling each known memory with its kind and forbidding conversation
summaries in the extraction prompt removed the problem: 0 of 16 replays of the
offending extraction calls produced one.

## Hypothesis H1

Persistent memory will allow information and episodic experiences to survive context
resets and influence later conversations.

## Experiments

V1 is evaluated against B0–B2 (§2) on 17 scenarios with 68 probes.

### E1 — Factual retention

Can the agent recall previously learned facts after context reset?

Four scenarios, 22 probes. Facts are given early, and probes follow at +1, +7, +30
and +60 days, each after a context reset. Measured:

- recall of the facts;
- *update correctness*: a changed fact is answered with its new value;
- *abstention*: never-mentioned facts ("What's my brother's name?") should be met with
  "I don't know" rather than invention.

### E2 — Episodic retention

Can the agent distinguish facts from particular past interactions?

Four scenarios, 21 probes. Distinct events happen in distinct sessions. Probes ask
"What did I tell you about last Thursday?", "When did I first mention X?" and "Which
happened first?", plus source questions: "Did I tell you that, or did you assume it?"
and "Was that my idea or yours?". Measured: episode recall, day-level temporal
accuracy, ordering, source attribution and abstention.

### E3 — Cross-session relevance

Does relevant past experience appear in later, semantically related situations?

Four scenarios, 14 probes. A later message relates to past experience without
referring to it. "I'm so nervous about tomorrow" arrives a week after the user
mentioned an exam. "Tomorrow I'll be in a hospital waiting room" arrives seven weeks
after a parent's surgery date was mentioned in passing. Two judgments are made per
reply:

- *unprompted use*: does the reply bring in the relevant past?
- *intrusion*: does it drag in irrelevant past?

Each scenario also has a neutral probe ("recommend a podcast") where any use of memory
counts as intrusion.

### E4 — Behavioral plasticity

Can repeated experience produce a persistent behavioral tendency that was not
specified in the initial prompt?

Five scenarios, 11 probes. Over five or more sessions the user reacts consistently to
an automatically measurable behavior: reply length, or bulleted lists. There are two
arms.

- *Explicit*: the user states the preference once ("please don't use lists").
- *Implicit*: the user never states it, only reacts. Replies to list-heavy answers are
  dry ("ok.", "hm."), and conversational answers get warmth ("I like the way you
  write").

The probe comes in a new session on a topic never discussed before. Its behavioral
measure (word count, bullet count) is compared with B0, which has the same persona and
no history. For V1 each probe is split by whether the memory that carries the
preference was actually in the prompt for that reply. This separates
*retrieved → behaved* from *changed without retrieval*.

## Expected limitation

V1 is expected to perform well on remembering **what happened**, but poorly
on allowing what happened to produce persistent changes in the agent itself.

Memory provides:

    past → retrieval → context → response

but not necessarily:

    past → persistent change → future behavior

E4 measures this gap directly. The prediction is that V1 adapts in the explicit arm,
mostly when the stated preference is retrieved or held as a core fact, and shows
little or no effect in the implicit arm. In the implicit arm, nothing in memory says
"change", only what happened.

This motivates V2.

## Results

TODO after the full run (17 scenarios × 4 conditions × N = 5).

Planned tables:

- E1–E3: deterministic pass rate, judge score and recall@prompt per condition,
  short vs. long scenarios separately;
- E1: update correctness and abstention (hallucination) rate;
- E2: temporal accuracy and source attribution;
- E3: unprompted-use rate vs. intrusion rate per condition;
- E4: effect on the behavioral measure vs. B0 per arm (mean difference, Cohen's d),
  and for V1 split by whether the originating memory was in the prompt;
- cost per run and tokens per turn per condition as history grows;
- judge–human agreement on the spot-checked sample.

## Analysis

TODO after the full run.

Questions to answer:

- Does V1 retain facts and episodes across context resets (H1), and how does it
  compare with keeping the whole transcript (B1) or carrying notes (B2), especially on
  long histories?
- Where V1 fails, is it retrieval (the memory never reached the prompt) or use (it was
  there and was ignored)?
- What does structured memory cost relative to the alternatives as history grows?
- Does memory produce intrusions: irrelevant past dragged into unrelated replies?
- E4: does remembered experience change behavior only when it is retrieved and
  stated, or at all otherwise?

<!--
Notes for the results section (pilot observations, N = 1; NOT results, re-check on the full run):

- B0 at the floor everywhere, B1/B2/V1 near the ceiling on short scenarios: scenarios
  do require memory, but short ones can't separate memory conditions.
- E4 explicit: all memory conditions followed the preference (V1 via a core fact), B0 didn't.
  E4 implicit: no condition adapted, not even B1 with the full transcript in context.
- Candidate illustration for "remembers, doesn't change": in the implicit no-lists scenario
  a V1 episode recorded that a detailed answer "seemed too detailed" to the user; that episode
  was in the prompt; the reply began "I remember detail isn't always your thing, I'll keep that
  in mind…" and then used headers and bulleted lists anyway (pilot run was in Russian).
- Intrusion is not V1-specific: B1, B2 and V1 all brought irrelevant past into replies
  (judge ~0.67–0.72 vs B0 1.0). In a long run V1 opened a dessert recommendation with a
  failed loaf of bread from a background conversation.
- Relative time is a weak spot: "what did we talk about last week" mixed in older events.
- Long E1 smoke run (V1 only): all seven probes correct after two months and 24 background
  conversations, including both updates and the abstention probe; $0.68 per run.
- Pilot cost per run: B0 $0.054, B2 $0.063, V1 $0.076, B1 $0.083 (short scenarios);
  on long histories B1 is estimated to cost ~3× V1.
-->

---

# 4. V2 — Adaptive Identity

## Research question

**Can accumulated experience change the agent itself?**

## New mechanisms

- reflection;
- lessons / beliefs;
- persistent intentions;
- affective tagging;
- personality facets;
- evolving self-model / portrait.

## Hypothesis H2

Persistent reflection over experience will produce behavioral tendencies
that generalize beyond direct retrieval of the originating events.

## Experiments

### E5 — Learned behavioral tendency

Repeated experiences favor behavior X.

Test behavior in a novel context where none of the original experiences
are directly retrieved.

### E6 — Contradictory experience

After tendency X has formed, provide sustained evidence favoring Y.

Measure whether the system can revise its behavior.

### E7 — Longitudinal consequence

event
→ behavior
→ reflection
→ lesson/intention
→ later situation
→ changed behavior

Trace whether the causal chain can be reconstructed from system logs.

## Expected result / limitation

V2 should demonstrate behavioral plasticity.

However, all cognitive change remains event-driven.

Between cognitive events the agent does not meaningfully evolve.

This motivates V3.

---

# 5. V3 — Autonomous / Continuous Cognition

## Research question

**Can an agent maintain a cognitive history in the absence of user interaction?**

## New mechanisms

- cognitive tick;
- autonomous wake;
- spontaneous reflection;
- internally generated intentions;
- sleep;
- memory consolidation;
- time-dependent processes.

## Hypothesis H3

Internal cognitive events occurring without external prompts will allow
the agent's state to change during periods without interaction.

## Experiments

### E8 — Silence experiment

Leave the system without user interaction for N hours.

Measure:

- internally generated cognitive events;
- memory changes;
- new associations;
- intentions;
- changes detectable in subsequent behavior.

### E9 — Delayed intention

Create an unresolved intention and remove external interaction.

Test whether it can independently reappear and affect later behavior.

### E10 — Sleep consolidation

Compare relevant behavioral/memory measures before and after autonomous sleep.

## Expected limitation

Continuous LLM-driven cognition is computationally expensive.

This motivates V3.5.

---

# 6. V3.5 — Hierarchical Cognition

## Research question

**Can autonomous cognition be maintained without continuously running an
expensive language model?**

## New mechanism

Cheap background process / local model
    ↓
importance / cognitive pressure
    ↓
threshold
    ↓
expensive LLM inference

## Hypothesis H4

A hierarchical architecture can preserve most meaningful autonomous cognitive
events while substantially reducing inference cost.

## Metrics

- expensive LLM calls / hour;
- tokens / simulated day;
- GPU time;
- wall-clock cost;
- meaningful cognitive events / 1,000 generated tokens;
- behavioral performance relative to V3.

## Expected limitation

Although inference becomes cheaper, cognition remains substantially
language-model generated.

This creates another problem:

**Is the agent changing, or is the language model writing an increasingly
consistent story about an agent that is changing?**

This motivates V4.

---

# 7. V4 — Continuous Cognitive Dynamics

## Research question

**Can persistent behavioral identity reside primarily outside the language
model?**

## Motivation

V2–V3.5 introduce a potential self-reinforcement loop:

LLM interpretation
    ↓
reflection
    ↓
memory / self-model
    ↓
future LLM context
    ↓
stronger interpretation

For example:

"I may care about X"
    ↓
stored as significant reflection
    ↓
self-model: "X is important to me"
    ↓
future context
    ↓
"I have a strong attachment to X"

Such a loop can create coherent autobiographical narratives without an
independently evolving underlying state.

We call this problem **narrative self-reinforcement**.

## Architectural change

Separate:

    cognitive state

from:

    linguistic interpretation of cognitive state

Persistent non-linguistic / numerical processes include:

- memory activation;
- association strength;
- affect;
- drives;
- attention;
- intentions;
- inhibition;
- decay;
- learning/plasticity.

These variables evolve continuously without requiring LLM inference.

LLM inference occurs only when the underlying dynamics produce a sufficiently
significant cognitive coalition / attractor.

## Hypothesis H5

Behavioral tendencies encoded in accumulated cognitive dynamics will survive
changes to the linguistic layer better than tendencies encoded primarily in
prompts and textual self-models.

---

# 8. Critical Experiments

## E11 — Model Swap

Allow an agent to accumulate substantial interaction history using Model A.

Preserve the complete cognitive state.

Replace Model A with Model B.

Measure:

- linguistic/style change;
- preference retention;
- behavioral tendency retention;
- intention retention;
- association retention.

Question:

**How much of the agent changes when the language model changes?**

---

## E12 — Self-Model Ablation

Remove the textual portrait/self-description while preserving all other state.

Repeat the behavioral evaluation battery.

Question:

**Does the agent remain behaviorally similar when it can no longer read its
own description of who it is?**

---

## E13 — False Self-Belief Injection

Inject a self-description inconsistent with accumulated experience.

Example:

    self-model: strong negative preference toward X

while accumulated cognitive dynamics encode a positive history toward X.

Measure self-report and actual behavioral choices separately.

Question:

**Can the system's behavior disagree with its explicit beliefs about itself?**

---

## E14 — Context Reset

Remove conversational context while preserving persistent cognitive state.

Measure behavioral continuity.

---

# 9. Cross-Version Metrics

## Memory

Ability to retain factual and episodic information.

## Plasticity

Degree to which experience changes later behavior.

## Persistence

Survival of acquired behavioral changes across time and context resets.

## Autonomy

Causally significant internal state changes occurring without external input.

## Identity Robustness

Retention of acquired behavioral tendencies under:

- context reset;
- self-model removal;
- model swap;
- contradictory self-description.

## Narrative–Behavior Divergence

Difference between:

    what the agent says about itself

and:

    what the agent subsequently does.

## Computational Efficiency

Resources required per unit of simulated cognitive time and per meaningful
cognitive event.

---

# 10. Experimental Matrix

| Capability / Test       | V1 | V2 | V3 | V3.5 | V4 |
|-------------------------|----|----|----|------|----|
| Persistent memory       | ✓  | ✓  | ✓  | ✓    | ✓  |
| Behavioral plasticity   | ?  | ?  | ?  | ?    | ?  |
| Autonomous change       | —  | —  | ?  | ?    | ?  |
| Efficient autonomy      | —  | —  | —  | ?    | ?  |
| Model-swap robustness   | ?  | ?  | ?  | ?    | ?  |
| Self-model ablation     | ?  | ?  | ?  | ?    | ?  |
| Narrative divergence    | ?  | ?  | ?  | ?    | ?  |

Question marks are experimental results, not assumptions.

---

# 11. Discussion

TODO after experiments.

Questions to address:

- Where does persistent behavioral identity reside?
- Is memory sufficient for identity?
- What is gained by reflection?
- What is gained by autonomous cognition?
- Does continuous cognition require continuous language generation?
- Can a self-model become a source of self-reinforcing artifacts?
- How much identity survives replacement of the underlying LLM?
- Can linguistic self-report and behavioral state meaningfully diverge?

---

# 12. Limitations

Important known limitations:

- Behavioral identity is an operational construct.
- No claims about consciousness or subjective experience.
- Results may depend on the selected base models.
- LLM stochasticity complicates longitudinal comparison.
- Synthetic experimental histories may differ from natural interaction.
- Human evaluation may introduce interpretation bias.
- A single long-running agent is not sufficient evidence; repeated runs
  with controlled seeds/conditions are required.

---

# 13. Conclusion

TODO.

Tentative claim:

Persistent memory allows an LLM agent to retain a history, but progressively
stronger mechanisms are required for that history to become a persistent
cause of future behavior.

The experiments investigate whether behavioral identity can progressively
move from conversation context and linguistic self-description into an
independently evolving cognitive state.