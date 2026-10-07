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
