# 5. V3 — Continuous Cognition

## Research question

**Can an agent maintain a cognitive history in the absence of user interaction, at a cost
that makes continuous existence practical?**

## Motivation

V2 changes only when something happens to it. Between conversations nothing happens:
the state twelve hours after a conversation is the state at its end, and what the agent
did not reflect on when the session closed, it never will. V2's first pass (§4) showed
three concrete consequences: an intention to remind the user "next time" was closed in
the conversation that created it; lessons accumulated instead of being revised; and the
interpretation of a reaction, made once at the end of a session, was never revisited.

The straightforward fix is to let the agent think on a schedule. Thinking with the
dialogue model on a clock is expensive, and most moments of silence contain nothing worth
thinking about. V3 therefore builds continuous cognition from two layers from the start:
a cheap background process that is always on, and expensive thought only when something
has accumulated. (In earlier plans these were two generations; they are one here, because
the expensive-only design is not a system anyone would run.)

## New mechanisms

- **background stream:** a cheap model produces short associative thoughts at a steady
  rhythm, faster in conversation and slower in silence; these are working thoughts, not
  memories;
- **pressure monitor:** a computation without any model that sums what has accumulated:
  fresh and important experience, unresolved intentions and questions, unsettled affect,
  and the novelty of the background thoughts;
- **wake:** when pressure crosses a threshold, the dialogue model thinks it through and
  may form an opinion, an intention or a question, revise a lesson, or decide to write to
  the user first;
- **initiative:** the agent can start a conversation, within strict limits;
- **sleep:** in long silence, offline consolidation: near-duplicate recent memories are
  merged, old and new memories are linked, contradictory lessons are resolved, and the
  self-portrait absorbs the day;
- **affect:** a fast reaction to each exchange and a slow mood that drifts back to a
  baseline over time; memories keep the emotional tone of their moment;
- **intentions with a notion of "later":** an intention cannot be fulfilled in the
  conversation that created it, and can fall due at a time when no one is talking.

Safeguards against self-excitation are part of the pressure formula, not patches: the
agent's own thoughts weigh less than external experience, a background thought adds
pressure only through its novelty, a wake consumes what triggered it, each wake raises the
threshold for a while (fatigue), and there are hourly and daily caps. None of these numbers
is shown to the model: a visible measure would become a target.

## Hypothesis H3

Internal cognitive events occurring without external prompts will allow the agent's state
to change during periods without interaction, and a cheap background process gated by
accumulated pressure is enough to produce them.

## Experiments

V3 is compared with V2, the event-driven predecessor. Time is simulated and stepped: before
each conversation and probe, the agent lives through every background tick, wake and sleep
scheduled since its last event.

### E8 — Silence

A conversation ends with something open. After 12 hours, two days and a week of silence
(separate probes), measure what changed during the silence (from the logs), whether it
traces back to background thoughts and wakes, and whether the next conversation shows it.

### E9 — Delayed intention

An intention falls due when no one is talking: a reminder the user asked for on a given
day, or a follow-up after an event. Measure whether the agent writes first, when, and about
what, and whether it raises the intention unprompted when the user returns. V2's reminder
scenario is included unchanged.

### E10 — Sleep consolidation

Contradictory experience (E6) with nights between sessions, and a memory scenario with
many near-duplicate mentions. Measure lesson hygiene and reversal speed against V2, and
duplicates and factual correctness before and after sleep.

### Efficiency

Cost per simulated day with and without conversation; background thoughts, wakes and
sleeps per day; and the share of wakes that changed any persistent state.

## Expected limitation

The agent now changes on its own, but every change it makes is still written by a
language model and stored as text it will read later. A thought becomes a memory, the
memory feeds the portrait, the portrait feeds the next thought.

**Is the agent changing, or is the language model writing an increasingly consistent story
about an agent that is changing?**

This motivates V4.
