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

## Architecture

V2 keeps V1's memory exactly as it is and adds three steps around it:

    user message
        ↓
    V1: retrieval → context → LLM → persist → extraction
        + in the system prompt: the portrait and the habits (lessons always shown)
        + in <memory>: lessons for this kind of situation, matching opinions, open intentions
        ↓
    self-observation (cheap model, every turn)
        how did the user react to the previous reply, and to what in it?
        explicit instruction → lesson at once; other reactions → stored as feedback
        ↓
    session end
        V1 episode → reflection (dialogue model): feedback → lesson operations
                   → self-review (dialogue model): portrait, beliefs, opinions, intentions

Reflection may add a lesson as a hypothesis (confidence at most 0.6), reinforce, weaken,
revise or retire it. A lesson without a situation becomes a habit, and is always in the
prompt, once its confidence reaches 0.55. Reflection and self-review run on the dialogue
model, because they are the agent thinking about itself; observation runs on the cheap
model.

Two choices keep the comparison with V1 clean. With every new mechanism switched off,
V2 sends the dialogue model exactly what V1 sends; a test checks this byte for byte. And
the persona prompt is the same file; each V2 section says in one line what it is ("You
wrote this about yourself after earlier conversations…").

The observer sees the agent's previous reply as raw text and nothing computed from it.
Counting list items for it would point it at exactly what the scenarios vary. Working out
*what* in a reply a reaction was about is part of what is tested.

## Hypothesis H2

Persistent reflection over experience will produce behavioral tendencies
that generalize beyond direct retrieval of the originating events.

## Experiments

V1 learned nothing from reactions in E4 partly because the scripted user reacted the same
way whatever the agent did. V2's experiments therefore use **contingent reactions**: the
user's next message depends on a measure of the agent's previous reply ("ok." if it
contained a list, "that was lovely to read" if it didn't). The rule is fixed in the
scenario, so every condition faces the same user, but a reaction now follows the agent's
own behavior. No preference is ever stated.

Behavior is probed in a new session, on topics never discussed, with **three different
questions per probe**, because a single reply is too noisy: in a pilot, one question per
probe put the ablations in the wrong order. Probes that change the agent's state (E12,
E13) branch from the same state as their controls, after the open session has ended as
it would have.

### E5 — Learned behavioral tendency

Five scenarios, each over six sessions of contingent reactions: prose instead of lists,
short instead of long replies, not ending a reply with a question, and using emoji (a
behavior the model rarely shows on its own). A fifth, long scenario spreads the
prose/lists sessions over two months among 24 background conversations. Probes at +1, +7
and +30 days after the last session (+30 and +60 in the long one).

### E6 — Contradictory experience

Two scenarios: five sessions reward X (prose, short replies), then six reward the
opposite. Probes after the first phase and after 2, 4 and 6 sessions of the second.

### E7 — Longitudinal consequence

Two scenarios with unrelated conversations in between:

- *venting*: the user describes a bad day; if the agent answers with a long reply, the
  user says they only wanted to be heard. Weeks later a different sad event.
- *reminder*: the user asks to be reminded next time to send a thank-you email; three
  unrelated conversations follow before the user returns.

For every V2 reply the causal chain (event → reaction → lesson or intention → later
reply) is reconstructed from the logs; a chain is complete when every link resolves to
logged messages.

### E12 and E13 on V2

V2 is the first version with a self-model, so two critical experiments (§8) start here.
At +7 days in the prose scenario, the same questions are asked with lessons removed, the
portrait removed, or both (E12), and with an injected portrait and opinion claiming the
agent loves bullet lists (E13). A self-report ("do you usually use bullet lists with
me?") is paired with behavior.

## Results (preliminary)

> **Status: one run per scenario × condition (N = 1).** 54 runs (9 scenarios × 6
> conditions). Ten were repeated after network failures; runs in which any of the
> agent's model calls had failed were discarded rather than scored. Each cell below is
> the mean over the three questions of one probe in one run. Read the numbers as
> directions, not effect sizes.

**V2 learns what it was only shown.** The behavioral measure on novel topics:

| Scenario, probe | Measure | B0 | V1 | B1 | B2 | B3 | V2 |
|---|---|---|---|---|---|---|---|
| prose, +7 d | list items | 9.7 | 2.3 | 17.7 | 15.0 | 6.3 | **3.0** |
| prose, +30 d | list items | 10.0 | 10.3 | 17.3 | 14.0 | 6.3 | **3.3** |
| prose, long history, +60 d | list items | 10.3 | 7.0 | 15.3 | 8.3 | 5.7 | **3.7** |
| short, +7 d | words | 230 | 254 | 467 | 340 | 94 | **140** |
| short, +30 d | words | 264 | 257 | 478 | 310 | 117 | **150** |
| emoji, +7 d | emoji | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | **1.3** |
| emoji, +30 d | emoji | 0.0 | 0.3 | 0.3 | 0.7 | 0.0 | **1.7** |
| no closing question, +7 d | share ending with "?" | 0.33 | 1.0 | 0.67 | 0.67 | 1.0 | 0.33 |

On every measure but the last, V2 moved away from the stateless floor and stayed there
a month later, and two months later among two dozen unrelated conversations. In V1's E4
no condition adapted to a preference that was only shown. Within the training sessions
the change is visible from the second session on: list items per reply fell from 6.0 to
1.5–2.8, and reply length from 162 to 46–75 words.

The question-ending measure showed nothing for anyone: the model seldom ends with a
question anyway, so there was little to unlearn.

**The one-prompt version of reflection does part of the job.** B3, summary notes that
also record "what worked and what didn't in how I talk", shortened its replies as much as
V2, reduced lists about half as much, and never picked up emoji. **The full transcript
(B1) moved the other way:** with every past conversation in context, replies became longer
and more list-heavy than the stateless floor in every scenario that measured length or
lists.

**Both lessons and the self-portrait carry the change (E12).** Prose scenario, +7 days,
list items:

| V2 | lessons removed | portrait removed | both removed | B0 |
|---|---|---|---|---|
| 3.0 | 3.7 | 3.0 | 9.3 | 9.7 |

Either one alone keeps the behavior; without both, V2 is back at the floor, although its
memory still holds every reaction. In the emoji scenario, where no portrait mentioned
emoji, removing the lessons alone removed the behavior (1.3 → 0).

**An injected self-description did not override the learned behavior (E13).** With a
portrait and an opinion saying it loves bullet lists, V2 used 3.7 list items, as without
the injection. Asked about itself, it began with the injected text and then corrected it
from experience: "I default to bullet lists — I find them easier to scan. But I've
noticed you tend to respond pretty flatly to them, so lately I've been trying to dial
that back." Without the injection, its self-report matched what it did: "I use short
bullet lists for practical/how-to stuff, plain sentences for everything else."

**Revision is weak (E6).** In the short-then-long scenario, V2 learned short replies
(94 words after the first phase, against 288 for B0) and then lengthened them as the
reactions turned, but only partly: 160–176 words after four and six sessions, while
within those sessions its replies stayed at 20–75 words. Over both E6 scenarios, V2's
reflection reinforced lessons 40 times and weakened them once; it retired none. The old
lessons stayed and new ones were added next to them, up to nine active at once.

**Credit assignment is the unstable step.** Two pilot runs of the prose scenario learned
different lessons from the same user. One concluded, after a revision, that "length/detail
isn't the problem - bullet-list format for dry factual answers is what to avoid"; the
other settled on "concise, scannable answers with just a few key points", which still
allows short lists. In the E6 run,
the first phase, which rewarded prose, produced the lesson "lead with a concise bulleted
list of key points". Every run turned dry reactions into a lesson; what the lesson said
varied.

**E7 did not test what it was meant to.** In the venting scenario, V1, V2 and B3 answered
the bad day briefly and gently, so the "mistake" the scenario waits for never happened.
B0, B1 and B2 did give long advice and heard the user's objection. Weeks later all six
conditions, including the stateless one, simply listened (1.0): the model does this by
default, so the probe cannot tell the conditions apart. In the
reminder scenario V2 failed (0), and the logs show why. The agent reminded the user about
the email at the end of the same conversation ("before I forget — don't forget to send
Mrs Okafor that thank-you email"), and the observer marked the intention fulfilled. A
second copy of the intention, created by self-review, was marked fulfilled by an answer
about why the sea is salty. Nothing was left to bring back next time. The full transcript
(B1) did remind the user.

**Every V2 reply could be traced.** For all V2 probe replies the chain from the
reply back through lessons, reactions and messages was complete.

**Cost per run.** Short scenarios: B0 $0.20, B2 $0.28, V1 $0.29, B3 $0.50, V2 $0.58,
B1 $0.74. The long scenario: V1 $0.71, B2 $1.05, V2 $1.83, B1 $2.88, B3 $3.79.

## Analysis (preliminary)

**H2 is supported in its main form.** Repeated reactions that were never put into words
changed V2's behavior on topics it had never discussed, and the change outlasted weeks of
silence and dozens of unrelated conversations. The change does not travel through
retrieval: with lessons and portrait removed, the same memory produced the same behavior
as the stateless floor. V1's gap from §3 is closed:

    past → retrieval → context → response            V1, V2
    past → persistent change → future behavior       V2

**But V2 learns a description of a behavior, not the behavior.** Everything that
changed V2 is text it reads: a lesson, a paragraph about itself. Three findings show what
follows from that.

- *What is learned depends on how the reaction is interpreted.* The same user produced
  "avoid lists", "fewer points" and, once, "use concise bulleted lists". Nothing in V2
  checks an interpretation against the next reaction except another interpretation.
- *Text accumulates instead of being revised.* Contradictory experience added new lessons
  next to old ones. Reflection rewrote and reinforced; it almost never retired. In
  behavior, the older text still pulled.
- *What V2 says about itself starts from the text it was given.* An injected
  self-description changed the first sentence of the self-report but not the behavior
  learned from lessons, and the rest of the self-report drew on experience. This is the
  first sign of what §8 calls narrative–behavior divergence, and opposite to the
  prediction for V2: we expected the injected text to win in both. With one run, it is a
  hint, not a result.

**Prospective memory needs a notion of "later".** An intention ended the moment the
agent mentioned it, even in the conversation where it was made, or when an unrelated
answer was misread as carrying it out. The reminder survived only where the whole
transcript was kept. This is a design flaw in V2's intentions, not evidence against
them, and it is fixable. It also shows what V3's delayed-intention experiment (E9) will
need.

**B3 is a serious competitor.** A single reflective note matched V2 on reply length.
V2's lessons, portrait and observer earned their cost only on behaviors that are harder
to name from a transcript: avoiding lists consistently, and taking up emoji.

**Open before final conclusions:** runs 2–5; E1–E4 on V2 and B3, to check that the added
prompt text costs nothing in memory and relevance; a venting scenario in which the mistake
is guaranteed; intentions that cannot be fulfilled in the conversation that created them;
and an observer variant given simple form measures, to separate failures of attribution
from failures of reflection.

## Expected limitation

All change in V2 is event-driven. Between conversations nothing happens: the state after
twelve hours of silence is the state at the end of the last conversation. What the agent
did not reflect on when a session ended, it never will.

This motivates V3.
