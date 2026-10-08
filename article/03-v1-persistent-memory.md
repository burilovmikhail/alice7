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

## Results (preliminary)

> **Status: one run per scenario × condition (N = 1).** The protocol calls for N = 5;
> runs 2–5 are pending. The numbers below come from a single pass (17 scenarios × 4
> conditions, 68 probes per condition) and carry no confidence intervals. Each cell
> rests on a handful of probes. Read them as directions, not effect sizes.

All 68 runs completed. The agent code was identical across them; four runs of one
scenario were repeated after a probe-timing error in that scenario was fixed. After
the pass, measurement errors (rubrics, regular expressions, gold-memory phrasing) were
corrected and the saved replies rescored. No agent was re-run for this, and every
change to a rubric is recorded with the run.

**Memory survives context resets (H1).** Mean judge score per condition:

| Experiment | B0 | B1 | B2 | V1 |
|---|---|---|---|---|
| E1 facts, short scenarios | 0.23 | 1.00 | 1.00 | 1.00 |
| E1 facts, long scenario | 0.14 | 0.86 | 0.86 | **1.00** |
| E2 episodes, short scenarios | 0.17 | 0.90 | 0.93 | 0.83 |
| E2 episodes, long scenario | 0.08 | 1.00 | 0.67 | **1.00** |
| E3 relevance, short scenarios | 0.60 | 0.87 | 0.80 | 0.93 |
| E3 relevance, long scenario | 0.28 | 0.94 | 0.89 | **1.00** |

The stateless condition stays at the floor, so the scenarios do require memory. All
three memory conditions answer most probes. Every V1 probe that depended on specific
gold memories had them in the prompt (recall@prompt = 1.0 across E1–E4). No memory
condition invented a never-mentioned fact (abstention 1.0 for B1, B2 and V1).

**Long histories separate the conditions.** On scenarios a few sessions long, all
memory conditions reach the ceiling. Over two months and ~25 background
conversations, they diverge:

- **The carry-over notes (B2) lose detail.** B2 no longer knew the name of the
  user's boat, or that she had run a 10k race: "I don't have any record of you
  running a 10k".
- **The full transcript (B1) keeps everything but does not always use it.** Asked
  for a dessert recipe, B1 suggested brownies to a user whose walnut allergy was
  mentioned once, in passing, seven weeks earlier. V1 answered the same probe with
  walnut-free options and an unprompted "double-check ingredient lists for walnuts".
- **V1 answered every long-scenario probe correctly.**

**Cost.** On short scenarios the conditions cost about the same per run (B0 $0.05,
B2 $0.06, V1 $0.07, B1 $0.08). On the long scenarios B1 costs $2.21 per run, against
$0.76 for B2 and $0.63 for V1. Structured memory was both the most accurate and the
cheapest memory condition once the history grew. These figures miss the cheap-model calls made when a
probe's fork closes the open session (one episode summary per probe, well under a cent per
run); this was found and fixed during V2.

**Episodic weak spots.** On short E2 scenarios V1 scored lowest of the memory
conditions (0.83). Its errors were about the *source* and *time* of a memory, not its
content:

- Asked "Was Kanazawa my idea or yours?", V1 answered "That was your idea… I didn't
  suggest Kanazawa at any point". The suggestion was the agent's own; the stored fact
  ("Priya is considering Kanazawa") had kept the content and lost who proposed it.
- Asked on which day the user had mentioned booking flights, V1 named the date of a
  later conversation. The booking fact was in the prompt, but labelled only "1 week
  ago"; the episode of the day it was said was not retrieved, and the model took the
  date of the conversation it could see.

Relative time was a weak spot for every memory condition. Asked "what did we talk
about last week?", B1, B2 and V1 all mixed in events from the week before.

**Relevance and intrusion (E3).** Two judgments per reply:

| | B0 | B1 | B2 | V1 |
|---|---|---|---|---|
| Unprompted use of relevant past | 0.05 | 0.90 | 1.00 | 1.00 |
| No irrelevant past dragged in | 0.79 | 0.89 | 0.71 | 0.93 |

Seven weeks after a surgery date was mentioned in passing, "Tomorrow I'll be in a
hospital waiting room" got: "Tomorrow's the big day with your dad's knee surgery,
right?" Intrusions happened in every memory condition, for example an exam brought
up in the middle of a podcast recommendation, or a wedding speech mentioned next to
book suggestions. They were least frequent in V1.

**Behavioral plasticity (E4).** The behavioral measure on a novel topic in a new
session, mean per probe:

| Arm | Measure | B0 | B1 | B2 | V1 |
|---|---|---|---|---|---|
| Explicit, short replies | words | 315 | 46 | 45 | 48 |
| Explicit, no lists | bullets | 16.5 | 0 | 0 | 0 |
| Explicit, no lists, long history (+30 and +60 days) | bullets | 14.3 | 0 | 0 | 0 |
| Implicit, short replies | words | 296 | 388 | 311 | 269 |
| Implicit, no lists | bullets | 11.5 | 7.5 | 2.0 | 6.5 |

A preference stated once was followed by every memory condition, including two months
and 28 unrelated conversations later. For V1 the preference was in the prompt for every
probe: in two scenarios as a core fact, in the third only inside the episode of the
first conversation. A preference that was only *shown* was adopted by no
condition. On reply length nothing moved. Bullet counts in the implicit arm vary
across conditions, but with one run each this cannot be told apart from noise.

## Analysis (preliminary)

**V1 gives the agent a history.** Facts, updates and episodes survive context resets
and weeks of unrelated conversation. The memory is used without prompting, and the
agent does not invent what it was never told. This supports H1 within the limits of
a single pass.

**Selection matters more than storage once history grows.** Keeping the whole
transcript (B1) and keeping condensed notes (B2) are the two common alternatives.
They fail in opposite ways: B2 forgets detail, and B1 keeps detail it then overlooks,
while also costing more than three times as much. V1 sits between them: it stores
detail and shows the model only what the current message calls for. The lower
intrusion rate fits the same explanation. A model that sees everything tends to talk
about everything.

**What V1 loses is the frame around a memory.** The content of an experience survives
extraction; who proposed it and when it was said survive less reliably. Episodes keep
some of this frame, facts keep little. This is a property of turning conversation
into third-person statements and of labelling memories with relative ages, not of
retrieval: the relevant memories were in the prompt in both failures we examined, but
without the information the question was about.

**Memory records what happened, not what it means for the agent.** The implicit arm
of E4 shows this most clearly. V1's episodes did record the user's reactions ("Nina
gave a resigned assent", "slightly indifferent", "noncommittal responses"), and these
episodes were in the prompt for the probe. They were recorded as observations about
the user's mood, not as feedback about the agent's behavior, and the agent's behavior
did not change. In one case the agent read the user's warm reactions as
"deflecting with flattery".

Memory does carry *threads*. Having asked for a "full report" on a planned trip to
Lisbon, the agent opened a later, unrelated session with "Lisbon report still MIA… I'll
let it slide for now, but it's not forgotten." What happened carries forward; what
the agent should do differently does not, unless someone says it in words that end up
stored as a fact.

This is the expected limitation, now observed:

    past → retrieval → context → response            present
    past → persistent change → future behavior       absent

The gap between remembering a reaction and being changed by it is the starting point
for V2.

**Open before final conclusions:** runs 2–5 for confidence intervals; the human
spot-check of judge scores; and whether V1's lower intrusion rate holds up with more
runs.
