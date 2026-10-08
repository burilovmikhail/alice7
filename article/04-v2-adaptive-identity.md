# 4. V2 — Adaptive Identity

## Research question

**Can accumulated experience change the agent itself?**

## From declarative to non-declarative memory

Human memory is not one system. A common division separates *declarative* memory, which
can be recalled and stated, from *non-declarative* memory, which shows up in what a person
does rather than in what they can report. Sensory memory (visual, auditory) has no
counterpart in a text-only agent and is left out.

| Human memory system | What it holds | In the agent |
|---|---|---|
| Working | what is held right now | V1: last messages of the session and a rolling summary |
| Semantic (declarative) | facts | V1: facts, core facts |
| Episodic (declarative) | events | V1: episodes |
| Procedural (non-declarative) | skills and habits: how to act, without recalling where it was learned | **V2: lessons and habits** |
| Prospective | what one intends to do | **V2: intentions** |
| Autobiographical self-knowledge | who I am | **V2: self-model (portrait, beliefs, opinions)** |
| Emotional | how events felt | V3: affect, emotional tagging |
| Implicit associative | associations that shape behavior but can't be stated | V4: non-linguistic dynamics |

V1 has only declarative memory, and its E4 result is what that predicts: the agent
remembered the user's reactions as events but did not acquire a habit from them. V2 adds
the procedural, prospective and self-related systems on top of V1's memory, which stays
unchanged.

One caveat shapes the critical experiments. In V2 every new "memory system" is still
text that the language model reads. V2's procedural memory is therefore declarative
underneath: a stated rule, not a learned disposition. Removing that text (E12) or
contradicting it (E13) tests how much of the acquired behavior depends on it. Memory that
works without being stated is the subject of V4.

## New mechanisms

- **self-observation:** after every turn, a cheap model judges how the user reacted to the
  agent's previous reply and what in it the reaction was about;
- **reflection:** at the end of a session, accumulated reactions become lessons;
- **lessons** with a confidence that grows with confirmation and falls with
  contradiction; a single case stays a hypothesis, a repeated one becomes a habit that is
  always in the prompt;
- **self-model:** a short first-person portrait with weighted beliefs and opinions,
  rewritten gradually after each session, with every version kept;
- **persistent intentions:** what the agent promised or decided to do, raised at the start
  of later conversations until done.

Affect moves to V3, together with other processes that run over time. Personality facets
(per-relationship identity choices in the informal predecessor) are not part of the
series: with a single user they collapse into the self-model.

V2 is compared with V1, B0–B2, and one more reference condition, **B3**: B2's summary
notes extended with "what worked and what didn't in how I talk with this user". B3 is
the simplest form of reflection, a single prompt. If V2 does not beat it, its additional
machinery is not justified.

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
