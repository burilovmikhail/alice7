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

## Architecture

    conversation: V2's turn
        + one more cheap call: how the exchange felt (affect), intentions with "later"
        + one background thought after the reply
    silence, stepped in simulated time:
        session closes at the 3-hour gap → pressure check (the moment it is most likely thought over)
        every stream tick (hourly while awake, every 3 hours at night):
            cheap model → one short thought, scored for novelty
            monitor (no model) → pressure vs threshold → maybe a wake (dialogue model)
        02:00, if anything new → sleep (dialogue model): merge, link, tidy lessons, portrait of the day

A wake may form an opinion, an intention or a question, change a lesson, resolve something,
or write to the user. Lived experience stays in V1's memory; the agent's own thoughts are
kept apart and shown under their own heading, so it can tell what it was told from what it
told itself. In experiments there are no threads: before each conversation and probe, the
agent lives through every tick, wake and sleep scheduled since its last event, each at its
own simulated time. A week of silence takes seconds.

## Experiments

V3 is compared with V2, the event-driven predecessor. Where a scenario is unchanged from §4
(E5, E6, the reminder scenario of E7), V2's runs from §4 are reused.

### E8 — Silence

A conversation ends with something open: a job offer to decide by next Monday, or a puzzle
(always tired on Sundays). Probes after 12 hours, one or two days and about a week ask,
without repeating the details, whether anything has come to mind.

### E9 — Delayed intention

The user asks to be reminded on Thursday to call the dentist, or to be checked on after an
interview on Thursday. No conversation until days later. **Initiative probes** ask nothing:
they score what the agent wrote first in the silence before them (whether, when, about what).
A probe at the user's return checks whether the matter comes up unprompted.

### E10 — Sleep consolidation

E6's contradictory-experience scenarios with nights between sessions (lesson hygiene), and a
memory scenario in which the same facts are mentioned again and again over five evenings
(duplicates and correctness).

### Regression

E5's prose and short-reply scenarios: V2's learned behavior must survive the stream, wakes
and sleep.

## Results (preliminary)

> **Status: one run per scenario × condition (N = 1).** 15 V3 runs and 5 new V2 runs, plus
> V2's runs from §4 for unchanged scenarios. Two pilot runs before the pass changed the
> design (below). After the pass, two rules were changed and three scenarios rerun; both
> versions are reported. Read the numbers as directions.

**Silence is not empty, and it is cheap.** Per simulated day, with conversations included:

| | short scenarios (E8–E10) | long scenarios (E5, E6) |
|---|---|---|
| background thoughts (cheap model) | about 16 | about 17 |
| wakes (dialogue model), whole scenario | 1–6 | 10–18 |
| wakes that changed persistent state | 75–100% | 50–80% |
| cost per simulated day | $0.04–0.08 | $0.03–0.07 |

Background thoughts cost under a cent a day; wakes and sleep account for most of the rest.

**The agent first had to be told it has time of its own.** In the first pilot run, asked to
remind the user on Thursday, the dialogue model answered that it can't write first and
would remind her *if she messaged on Thursday*, and stored the intention in those words.
On Thursday morning the due intention did wake it, and it decided to keep its word: "I told
Clara I can't reach out of the blue — that was the whole point of being honest with her."
Elsewhere it told a user: "I don't turn it over on my own like that." The base model assumes
it has no existence between conversations, and no mechanism changes that until the agent is
told. A section of the system prompt now says that between conversations it keeps thinking,
sleeps at night, and can write first when it has a reason; the persona prompt is unchanged.

**V3 writes first; V2 can't (E9).** In both E9 scenarios V3 wrote to the user in the silence,
V2 never did. In the pass, though, the timing went wrong. Right after the dentist
conversation the agent sent an unprompted check-in ("how's the tooth feeling tonight? I've
got Thursday marked"), and the rule against a second unanswered message then blocked the
Thursday reminder. In the interview scenario it wrote the day before, about preparation, and
the same rule blocked the message after the interview. With a quiet period after a
conversation and due intentions exempt from the unanswered-message rule, the rerun sent
"today's the day to call Dr. Haas" at 08:00 on Thursday and "it's the day after… how did it
actually go?" on Friday (both judged 1.0, against 0 in the pass). One unprompted check-in on
the day before the reminder remained.

When the user returned, both versions asked about the dentist (1.0) and half-raised the
interview (0.5): what memory alone can do, V2 already did.

**The reminder V2 lost (E7).** In §4's reminder scenario V2 closed the intention in the
conversation that created it. V3 brought the email up in the following conversations,
asked three times, then decided on its own to stop ("continuing to press risks turning
gentle curiosity into pressure"). The probe, placed at the fourth conversation, scored 0 for
both: it was placed too late to see the difference.

**Thinking in silence did not change the answers (E8).** Both versions offered new angles on
the Lisbon decision and the Sunday tiredness when asked (1.0 and 0.75 for both): the
dialogue model produces new angles on the spot. The difference is in the logs and in what the
agent says about itself. V3 had woken right after the conversation, noted what it had not
asked (whether the lease can be broken, who else helps the mother), and on the deadline day
wrote first with exactly those questions. V2 said things it could not have done:
"I did keep turning it over a bit", "I've been curious about it since yesterday", "Thursday's
interview has been on my mind". The two versions' reports of an inner life are the same; only
V3's are backed by events.

**Sleep tidies lessons (E10).** After contradictory experience V3 ended with 2 and 5 active
lessons, 4 retired in each scenario; V2 had kept 9 and 5, retiring none. In the duplicates
scenario there was nothing to merge (0 groups in six nights): V1's extraction already avoids
storing the same fact twice. Both versions answered the factual probes (V3 0.83, V2 0.67 by
the judge).

**Sleep also entrenched a misreading (regression).** In the short-reply scenario, the first
reflection read the dry "ok." the opposite way from §4 ("a short, flat reply… is usually a
neutral acknowledgment, not fatigue — don't over-interpret it"). Sleep and wakes then
reinforced it eight times, "consistently confirmed… no contradicting evidence", up to a
confidence of 0.95, with no new reaction from the user. Replies on novel topics were about 250
words, against about 140 for V2. In the prose scenario V2's effect survived (about 2 list items
against 3). In the E6 scenarios, beliefs in the portrait grew in weight without new evidence
5 and 7 times, against none for V2. With sleep and wakes no longer allowed to change a
lesson's confidence, the rerun of the short-reply scenario reached 170–220 words: better, still
not V2's 105–150; sleep now retired a fresh hypothesis to answer concisely instead.

## Analysis (preliminary)

**H3 is supported for state, and only partly for behavior.** Without any input, V3 thought
over what had happened, formed and dropped intentions, tidied its lessons and wrote first
when something fell due, all traceable in the logs, at a few cents per simulated day. Where
the change had to show in a reply, it showed in the cases that memory cannot cover: writing
first, and bringing an intention back after the conversation that made it. Where the dialogue
model can produce the result on the spot (new angles on a decision), thinking in advance made
no visible difference.

**An agent that can act on its own must be told so.** The base model's assumption that it has
no existence between conversations is strong enough to override the mechanism: it
promised to wait, and waited. The fix is one paragraph of the prompt; the finding is that
the architecture and the model's picture of itself have to agree.

**What an agent says about its inner life is not evidence of one.** V2, which does nothing
between conversations, reported having thought about the user's problem in the same words V3
did. This is narrative–behavior divergence (§8) in its plainest form, and it argues for
judging V3 by its logs, not by its reports.

**Thinking without new evidence reinforces itself.** Sleep and wakes are meant to step back.
Given the freedom to strengthen what they reviewed, they strengthened it, including a
misreading, and the self-portrait grew more confident about the same things. Restricting them
to revising and retiring helped but did not undo the dependence on the first interpretation.
This is the loop §6 starts from, now observed rather than assumed.

**Open before final conclusions:** runs 2–5; E8 probes that need something only prior thought
could provide; a duplicates scenario that actually produces duplicates; the remaining false
start; and whether sleep should be allowed to retire a hypothesis without new evidence.

## Expected limitation

The agent now changes on its own, but every change it makes is still written by a
language model and stored as text it will read later. A thought becomes a memory, the
memory feeds the portrait, the portrait feeds the next thought.

**Is the agent changing, or is the language model writing an increasingly consistent story
about an agent that is changing?**

This motivates V4.
