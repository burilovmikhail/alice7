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

---

# 3. V1 — Persistent Memory

## Research question

**Can persistent memory give a conversational agent a meaningful history?**

## Motivation

A conventional chatbot's past primarily exists inside its conversation
context.

V1 replaces indefinitely growing conversational history with persistent
structured memory.

## Architecture

TODO

Minimal intended architecture:

User input
    ↓
Memory retrieval
    ↓
LLM
    ↓
Response
    ↓
Memory extraction/storage

No:

- reflection;
- learned personality;
- self-model;
- affect;
- autonomous cognition;
- continuous internal state.

## Hypothesis H1

Persistent memory will allow information and episodic experiences to survive
context resets and influence later conversations.

## Experiments

### E1 — Factual retention
Can the agent recall previously learned facts after context reset?

### E2 — Episodic retention
Can the agent distinguish facts from particular past interactions?

### E3 — Cross-session relevance
Does relevant past experience appear in later, semantically related situations?

### E4 — Behavioral plasticity
Can repeated experience produce a persistent behavioral tendency that was
not specified in the initial prompt?

## Expected limitation

V1 is expected to perform well on remembering **what happened**, but poorly
on allowing what happened to produce persistent changes in the agent itself.

Memory provides:

    past → retrieval → context → response

but not necessarily:

    past → persistent change → future behavior

This motivates V2.

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