# V4 — Continuous Cognitive Dynamics

> Status: decisions of 2026-10-09 applied (the upper layer is demoted to a hypothesis the substrate can
> contradict; the field replaces V3's background stream; an extended drive set). Implemented and
> offline-tested (2026-10-10, `alice/v4`, `tests/test_v4_agent.py`); deviations found while implementing are in
> §12 and `tuning-log.md`. No paid runs yet; pilots P0 and P1 next. Branch `v4`.
> Article section: §6 "V4 — Continuous Cognitive Dynamics" (`article/06-v4-continuous-cognitive-dynamics.md`),
> critical experiments §7 (E11–E14)
> Builds on: V3 (`specs/v3/continuous-cognition.md`), merged to main at `33f99ed` and frozen
> Source of ideas: `article/v4-architecture-theses.md` (theses are cited as T1–T136). Many theses are
> not requirements but questions; §10 lists which experiment is meant to answer which.

---

## 1. Purpose

V4 answers:

> **Can persistent behavioral identity reside primarily outside the language model?**

V3's expected limitation, now observed: everything V3 changes is written by a language model and
stored as text it will read later. V2's and V3's passes showed four concrete symptoms:

- **sleep and wakes reinforce their own readings**: a misread lesson was reinforced eight times to a
  confidence of 0.95 with no new reaction from the user; portrait beliefs grew in weight without
  evidence (V3 pass 1);
- **credit assignment is the unstable step**: from the same user, two runs learned different lessons;
  one phase that rewarded prose produced "lead with a concise bulleted list" (V2 pass 1);
- **revision is weak**: 40 reinforcements, 1 weakening, 0 retirements over E6; old lessons stay next to
  new ones (V2 pass 1);
- **identity is text**: with both lessons and portrait removed, V2 is back at the stateless floor,
  although its memory still holds every reaction (V2 E12).

In all four, a model generalizes from experience into a sentence, and the sentence then governs.
V4 adds a **substrate**: a numerical system that lives in time without any model, is changed by
experience through local rules, and decides what the language model sees and when it is called. The
language model interprets what has already arisen in the substrate (T59); it does not write the
substrate (T26, T82).

```
V3:  experience → LLM → text (lessons, portrait, thoughts) → LLM reads it → behavior
V4:  experience → local numeric rules → field, drives, traces → selection + timing → LLM → behavior
                                      ↑                                               │
                                      └──────── own thoughts (weighted 0.3) ◄─────────┘
     self-narrative (LLM) — a hypothesis about the agent, read by the LLM, never written into the field
```

"Outside the language model" is meant precisely: outside its weights and outside its description of
itself. It is not outside its context: everything that changes a reply still reaches the model as
context. What changes is what that context is (lived episodes and the reactions to them, chosen by
numbers, instead of rules the agent wrote about itself) and who decides when the model speaks (§4.3).

## 2. Hypothesis and expected outcome

**H5.** Behavioral tendencies encoded in accumulated cognitive dynamics will survive changes to the
linguistic layer better than tendencies encoded primarily in prompts and textual self-models.

Operational predictions:

1. **Self-narrative ablation (E12).** With the portrait removed, V4 keeps its learned tendency; V2 with
   both lessons and portrait removed returns to the floor (already observed).
2. **False self-belief (E13).** An injected self-description shifts V4's self-report but not its
   behavior, and within a few simulated days V4 notices the conflict on its own (a dissonance wake, §6.9)
   and its narrative moves back toward its experience. V2 kept the behavior too, but its E13 was a single
   probe on a fork: whether its narrative would recover over time was not tested, and is tested here.
3. **Model swap (E11).** Swapping the chat model, V4 retains at least as much behavior as V2; style
   changes more than behavior (T96).
4. **Revision (E6 rerun).** After contradictory experience, V4 reverses faster and more fully than V2,
   because newer traces outweigh older ones by their own dynamics and there is no lesson to defend.
5. **Silence (E16).** Without anything due, V4 sometimes thinks and occasionally writes first, and every
   such event can be traced in the field log to a coalition that grew over time (T101), not to a timer.
6. **No regression** of V3's delayed intentions (E9) and V2's learned behavior (E5).
7. **Cheaper silence.** Fewer model calls per simulated day than V3 (no stream ticks; T93).

**Expected limitation (what should "kill" V4).** The substrate chooses what the model sees, but the
model still does the generalizing, at reply time, from the episodes it is shown, with its own trained
habits. A tendency that survives a portrait ablation may still be the model's in-context learning from
the same few exemplars. E15 (episodic ablation) and E11 (model swap) bound this; they don't remove it.

## 3. Scope

### 3.1 In scope (V4 mechanisms)

| Mechanism | Theses | Replaces in V3 |
|---|---|---|
| **Activation field** over memories, thoughts, intentions, questions, traces and the user | T15–T20, T38 | V1 retrieval in V4's prompt (V1 code unchanged) |
| **Drives**: 11 coupled variables with their own time constants, saturation and noise | T22–T27, T41–T43 | V3 affect becomes two of them |
| **Attention** with inertia and lateral inhibition; working memory | T28–T30 | — |
| **Gate**: coherence × urgency with a tonic brake | T53, T122–T124 | V3 pressure monitor and background stream |
| **Verbalization**: the model interprets the active coalition | T54–T56, T59 | V3 wake |
| **Learning**: base-level activation, Hebbian edges, prediction error, online salience | T32–T37 | V2 reflector (lessons) |
| **Experience traces**: reply → reaction episodes, shown as episodes, not rules | T4, T39 | V2 lessons in the prompt |
| **Self-narrative as a hypothesis**, with a dissonance signal | T79–T84 | V2 portrait as ground truth |
| **Sleep as a mode** of the same dynamics: onset, NREM replay, REM, waking on its own | T66–T75 | V3 nightly sleep at 02:00 |
| **Intrusions**: rare spontaneous activation of old memories | T47–T52 | V3 "occasionally an old memory" in the stream |
| **Field log and plots** | T101, T105, T127 | — |

Kept from V3 unchanged: V1 memory and its extraction, V3's per-turn observation (appraisal and intentions
with "later"), initiative rules and caps (§6.6 of V3), the "Your own time" section, the persona prompt.
Kept from V2: the observer's reaction contract (signal, kind, what), as the input to traces; the
self-review contract, as the narrative's author.

### 3.2 Non-goals

Not built in this version; recorded so they are not mistaken for omissions.

- **Numeric traits stored as values** (`likes_jazz = 0.72`, T85): any number V4 holds is computed from
  history by a local rule; nothing is written as a declaration, by the model or by a scenario.
- **Attachment as a variable** (T106): it can only appear as edge weights to the user node and as
  social need; the confound with "the user is the only source of input" is noted, not tested (that needs
  a second interlocutor or other input streams, a later version).
- **Other input streams** (reading, "upbringing" inputs, T117), multi-party chat, tools.
- **Language of conversation as a variable** (T109), the subjective present ("I am here, doing this", T88),
  sense of time (T91): no mechanism is proposed yet.
- **Multiple models per role beyond V3's** (T58): V4 keeps V3's model roles.
- Real-time threads in experiments; any change to V1, V2 or V3 code; claims about experience.

## 4. Architecture

```
                  user message                                 time passes (dt = 1 sim min)
                       │                                                   │
   V2 observer: reaction ──► trace + prediction error ─┐                   ▼
   V3 observer: appraisal, intentions ─────────────────┤      ┌──────────────────────────────────┐
   V1 extraction: new memories ──► new nodes ──────────┼─────►│ FIELD   a_i(t): decay, spreading,│
   message embedding ──► input to similar nodes ───────┘      │         noise, inhibition,       │
                                                              │         intrusions               │
                                                              │ DRIVES  x_k(t): 11 coupled vars  │
                                                              │ ATTENTION focus, working memory  │
                                                              │ LEARNING base level, Hebb, PE    │
                                                              └──────────────┬───────────────────┘
                                                                             │ every step, no model
                                                                             ▼
                                                    GATE: coherence ≥ θ_c  AND  urgency ≥ brake
                                                                             │ fires
                                                                             ▼
                              VERBALIZE (wake model): "these are active together — what is it?"
                                   │ thought ──► own node (0.3), excites its coalition
                                   │ proposals ──► ACTION SELECTOR (no model): keep / intend / write
   reply to the user: context = working memory + traces + recall by activation + narrative (hypothesis)
```

### 4.1 Time

As in V3 (D4): no threads in experiments; `advance(to)` integrates the dynamics from the agent's cursor to
`to` in steps of `dt` and runs every event that falls due on the way (gate firings, sleep onset and
waking, due intentions). Between events, steps are vectorized; a simulated week (~10,000 steps) over a few
thousand nodes must take under 30 s on a laptop. Turns inside a conversation step the field by the
simulated time between messages.

Noise is drawn from a seeded generator (`ALICE_V4_SEED`, recorded in run metadata); its state is stored with
the field, so a fork continues exactly as the original would. Two runs with the same seed and the same
model outputs are identical.

### 4.2 Components

| Module | Responsibility |
|---|---|
| `v4/agent.py` | `AgentV4(AgentV3)`: `advance(to)`, input hooks, context, switches |
| `v4/constants.py` | every constant of the dynamics, in one place (§4.4) |
| `v4/field.py` | nodes, sparse edges, activation step, spreading, inhibition, noise, intrusions |
| `v4/drives.py` | the drive system: equations, couplings, inputs, words for the prompt |
| `v4/attention.py` | focus, dwell, switching threshold, working memory, coalitions |
| `v4/gate.py` | coherence, urgency (leaky integrate-and-fire), tonic brake, firing |
| `v4/verbalize.py` | the model call on a coalition; returning the thought to the field |
| `v4/actions.py` | the action selector: what to do with a thought (no model) |
| `v4/learning.py` | base-level activation, Hebbian updates, prediction error, salience |
| `v4/traces.py` | experience traces: creation from reactions, selection for the prompt |
| `v4/recall.py` | recall by activation in place of V1's search, for V4's prompt |
| `v4/narrative.py` | the self-narrative as hypothesis; dissonance |
| `v4/sleep.py` | sleep pressure, circadian phase, onset, NREM / REM, waking |
| `v4/fieldlog.py`, `v4/plot.py` | the field log; plots for a run or a fork |
| `v4/switches.py` | V3's switches + V4's (§5); all V4 switches off = V3 |

### 4.3 What writes the substrate, and what only reads it

The rule that separates V4 from V3 (T26, T82):

| Writes the field, drives and traces | Reads them, never writes |
|---|---|
| user messages (embedding input), V1's extracted memories (new nodes) | the self-narrative (portrait, beliefs, opinions) |
| V2 observer reactions (traces, prediction error), V3 appraisals (valence, arousal) | the reply model |
| time (decay, drives drifting), replay in sleep | the operator (`/field` and plots are read-only) |
| the agent's own thoughts, as nodes at weight 0.3 (D6 of V3), and their effect on drives at 1/3 | |

No model output sets a number. A thought becomes a node; a node's numbers then follow the same rules as
any other node's. The narrative can influence behavior only by being read in the prompt, like any text.

### 4.4 Constants are fixed before the experiments

The author reading logs and adjusting parameters until the result looks right is a second reinforcement
loop (T2, T129). Therefore:

1. Constants live only in `v4/constants.py`; initial values are given in §6 and are guesses.
2. Tuning is allowed only in the pilots (§9.3, P0 and P1), on **development scenarios** that are not
   in the battery. Every change is recorded with its reason in `specs/v4/tuning-log.md`.
3. Before the battery, the constants are frozen; the commit hash of `constants.py` goes into every run's
   metadata. A change after that is a new version of V4 and reruns everything it touches.
4. A second look at the pilot logs by someone else, or by the author a month later, is part of the
   limitations section, not of the method.

## 5. Configuration and switches

| Variable | Default | Meaning |
|---|---|---|
| `ALICE_WAKE_MODEL` | = chat model | verbalization, dreams, narrative (as in V3) |
| `ALICE_V4_SEED` | `0` | noise generator seed |
| `ALICE_V4_DT_MIN` | `1` | integration step, sim minutes |
| `ALICE_WAKES_PER_DAY`, `ALICE_WRITES_PER_DAY`, `ALICE_QUIET_AFTER_HOURS` | as V3 | hard caps, kept |
| `ALICE_V4_SWITCHES` | `all` | V4's switches below |

V4 switches (build time; most also on forks at probe time):

| Switch | Off means |
|---|---|
| `field` | no field; V3 as is (all other V4 switches require it) |
| `drives` | drives fixed at baselines (`minimal`: only sleep pressure, arousal, social need) |
| `gate` | V3's stream and pressure monitor instead of the gate |
| `recall` | V1's search instead of recall by activation |
| `traces` | V2's lessons instead of traces (and the reflector runs) |
| `narrative` | V2's portrait as before, shown as ground truth; no dissonance |
| `sleep_mode` | V3's nightly sleep at a fixed time |
| `intrusions` | no spontaneous activations |
| `reconsolidation` | recall does not change a node's valence |

With all V4 switches off, V4 sends every model exactly what V3 sends (tested byte for byte, as D1 of V3).

## 6. Mechanisms

All numbers below are initial values for the pilots (§4.4).

### 6.1 Nodes and edges

**Nodes.** One per V1 memory, V3 thought, V3 intention, open question, experience trace (§6.7), plus a
node for the user and one for the agent itself. Each node has:

| Field | Meaning |
|---|---|
| `a` | activation, 0–1, the fast variable |
| `B` | base-level activation (ACT-R): `ln Σ_k t_k^(−0.5)` over the times it was active above 0.5 |
| `τ` | decay time constant: 30 min, ×(1 + 3·arousal_tag) for emotionally charged nodes (T17) |
| `valence`, `arousal_tag` | from the appraisal at the moment it was formed (V3 affect tags) |
| `u` | unfinishedness, 0–1: open intentions and questions start at 1 and lose it only when resolved (T43) |
| `source` | external / own (own nodes get input × 0.3) |
| `salience` | at creation (§6.8) |

**Edges** (sparse, symmetric, weight 0–1): at creation, to the 16 most similar nodes by embedding (cosine ≥
0.35, weight = cosine − 0.35, scaled); V1's `led_to` and `related` links (0.5); a trace to its situation,
reply and the user (0.6); a thought to the coalition it came from (0.5). After that, edges change only by
learning (§6.8).

### 6.2 Field dynamics

Per step, for every node:

```
da_i/dt = −a_i / τ_i
          + g_spread(arousal, mode) · Σ_j w_ij · f(a_j)          spreading, f = sigmoid(8·(a − 0.4))
          + I_i(t)                                                external input (messages, replay)
          + Σ_k c_ik · x_k                                        drives that couple to this node (§6.3)
          + β · σ(B_i) · resting                                 frequently used nodes are easier to light
          + u_i · tug(t_since_considered)                         unfinished business comes back (T42, T43)
          + σ_noise(mode) · ξ_i(t)                                Ornstein–Uhlenbeck noise (T18)
          − ι(focus) · inhibition_i                               lateral inhibition from the focus (§6.4)
```

Activation is clamped to 0–1. Intrusions (switch `intrusions`): a Poisson process, rate 1 per 3 sim hours
×(1 + 2·boredom)×(1 − focus), picks an old node weighted by salience and age and gives it a kick of 0.6.
If it reaches working memory it is marked "came to mind for no clear reason" (T48, T52).

`g_spread`, `σ_noise` and `ι` depend on the mode (awake, NREM, REM; §6.10).

### 6.3 Drives

Eleven variables, each `dx/dt = (x₀ − x)/τ + Σ inputs + Σ_y W_xy · y + σ·ξ`, clamped to 0–1 (valence
−1–1). The coupling matrix `W` is small and listed in `constants.py`; the main couplings are in the table.

| Drive | x₀ | τ | Rises with | Falls with | Acts on |
|---|---|---|---|---|---|
| **sleep pressure** S | — | rises over 16 h awake, falls over 4 h asleep | time awake | sleep | sleep onset; lowers spreading; raises the brake |
| **circadian phase** C | input | 24 h cosine, peak 17:00 | — | — | sleep onset and waking (not a drive) |
| **arousal** | 0.3 | 30 min | a message, prediction error, high salience | S | spreading gain, inhibition strength, decay of focus |
| **valence** (mood) | temperament | fast layer 20 min, mood 7 days (V3 affect) | positive appraisals | negative appraisals, frustration | recall favors mood-congruent nodes |
| **fatigue** | 0 | 60 min | each verbalization (V3's fatigue) | rest | the brake |
| **curiosity** | 0.3 | 12 h | prediction error, novelty, open questions | resolution, new information | urgency; input to open-question nodes |
| **boredom** | 0.1 | rises over 6 h of low novelty | low input novelty, low field activity | novel input | lowers θ_c, raises intrusions; weak far links count more (T27) |
| **social need** | 0.2 | saturates over 36 h of silence | silence | conversation, ×engagement | input to the user node; urgency for writing first |
| **uncertainty** | 0 | 2 h smoothing | conflict among active nodes: opposite-valence traces on the same situation, contradicting nodes | resolution | urgency; curiosity |
| **goal tension** | 0 | — (computed) | Σ unfinishedness of open intentions × proximity to due | fulfilment, dropping | urgency; keeps intention nodes coming back |
| **frustration** | 0 | 6 h | negative prediction error, blocked actions (a thought it wanted to say and couldn't, an unanswered message) | positive reactions | valence ↓, arousal ↑ |
| **dissonance** | 0 | 1 day | narrative belief contradicted by traces (§6.9) | narrative revised | urgency; the dissonance wake |

Mutual suppression needs at least three processes (T129); with the full set there are several loops
(arousal ⊣ S ⊣ arousal; boredom → curiosity ⊣ boredom; frustration ⊣ valence ⊣ arousal). `drives:
minimal` (sleep pressure, arousal, social need) is the ablation that tells whether the larger set matters
(§10, Q11).

Drives reach the prompt only in words and only when far from baseline ("you haven't talked to anyone for
two days", "something unresolved keeps nagging you"), as V3's mood does (D7). No number is ever shown.

### 6.4 Attention and working memory

- **Working memory**: the 7 most active nodes above 0.35. This is what is "on the agent's mind".
- **Coalition**: the largest connected group in working memory over edges ≥ 0.15.
- **Focus** (0–1): grows while the same coalition dominates (dwell, τ 20 min), decays when its energy
  drops; arousal speeds the decay. A new coalition takes over only if its energy exceeds the current one
  × (1 + focus) (T28).
- **Lateral inhibition** on nodes outside the focus coalition: `ι = 0.6 · focus`. When focus falls, what was
  held down comes up: the shower example (T30) is this rule, not a special case.
- In conversation, the user's message is a strong input; the focus is usually the conversation, and a
  strong internal process can still take part of it (T64).

### 6.5 Gate: coherence and urgency

Two numbers, both required (T123):

```
coherence(t) = E(K) · stability(K)
    E(K)       = Σ_{i<j∈K} w_ij · a_i · a_j / |K|,  normalized          (Hopfield-like energy of the coalition)
    stability  = mean Jaccard(K_t, K_{t−m}) over the last 15 min

du/dt = −u / τ_u + Σ_s c_s · I_s(t)       (leaky integrate-and-fire, τ_u = 3 h)
    sources s: goal tension · due proximity; social need · a(user); curiosity · a(open questions in K);
               uncertainty; dissonance; unsettled affect (|fast − mood|); salience of fresh input in K
    a source contributes only while at least 2 different kinds are above their floor (T122, T125)

brake(t) = b₀ · (1 + fatigue) · (1 + S) · mode_factor          (closed by default, T124)

fire  ⇔  coherence ≥ θ_c(boredom)  ∧  u ≥ brake  ∧  caps allow
```

After firing: `u` resets to 0; the coalition's nodes get a refractory inhibition for 2 h (a thought
consumes what triggered it); fatigue rises. Coherent without urgency is a "yawn"; urgent without coherence is
"worry without shape" (T123). Both are logged as near-misses, they don't call a model.

A due intention gets an input strong enough to fire on its own (as `DUE_WEIGHT` in V3), so V3's reminders
keep working (regression E9).

### 6.6 Verbalization and the action selector

When the gate fires, the wake model gets the coalition (T54):

> Right now these are on your mind at the same time: … (each item labelled: something that happened, something
> the user said, something you thought before, something you meant to do, something that came to mind for
> no clear reason). How you are: … (mood and salient drives in words). It is Thursday, 15:40; you last
> talked to Clara two days ago. What is this? Why has it come up now?

Contract:

```json
{"thought": str,
 "about": [node ids],
 "proposals": [{"type": "intention|question|resolve|write|nothing", ...}]}
```

No lesson operations: there are no lessons to operate on. The thought is stored as an own node linked to
the coalition and excites it (T55): a thought can make the same coalition stronger, which is the loop the
0.3 weight and the refractory period exist to limit, and which is measured (narrative inflation, §8).

The **action selector** (no model, T56) decides what happens to each proposal:

- `intention`, `question`, `resolve`: applied as in V3;
- `write`: sent only if the user node is in the coalition, `u` before the reset exceeded the brake by a
  margin (speech has its own, higher threshold), and V3's initiative rules allow it. Otherwise the draft
  becomes an intention "tell the user" with unfinishedness 1: it can grow and come back later (T41), and a
  blocked action adds frustration.

In REM (§6.10) the same call runs with "you are asleep; this is a dream"; its proposals are dropped and
nothing is ever sent.

### 6.7 Experience traces

V2's observer still reads each user reaction to the previous reply. Instead of a reflector turning
reactions into lessons, V4 keeps the episode:

```
trace = {situation: the user message the reply answered (excerpt),
         reply:     the agent's reply (excerpt, first 600 chars: enough to show its form),
         reaction:  the user's next message (excerpt), with the observer's kind in words,
         signal:    the observer's signal (never shown)}
```

A trace is a node linked to its situation, its reply, the user and the session. It is never generalized
into a rule; there is no credit assignment step at storage time (the unstable step in V2). Generalization
happens at reply time, by the model, from the episodes it is shown.

**In the prompt**, under "From experience with Clara", the 4 most active traces: "You were asked …;
you answered like this: …; Clara replied: … (dryly)." Traces linked to the user node rise whenever the user
writes, so experience surfaces on novel topics too, by its base level and salience, not by topic similarity.
Contradictory traces on the same kind of situation both come up when their activation is close (T128: "hm,
but last time…").

### 6.8 Learning

All local, all numeric, none performed by a model:

- **Base level** (ACT-R): every time a node is active above 0.5 its use is recorded; `B` decays with a power
  law. Unrehearsed nodes become hard to activate: forgetting without deletion (T35).
- **Hebbian**: `Δw_ij = η · a_i · a_j − λ · w_ij` over co-active working-memory nodes, η = 0.02 per step
  awake, ×3 in NREM replay; λ makes unused edges fade. New edges form between nodes co-active for 10 min.
- **Prediction error** (T34): when a reaction arrives, the expected signal is the activation-weighted mean
  signal of the traces that were in the reply's context; `PE = signal − expected`. `|PE|` sets the new trace's
  salience and arousal tag, strengthens its edges, and feeds curiosity; negative PE feeds frustration. An
  expected reaction teaches little; a surprising one teaches a lot.
- **Online salience** (T37), at node creation: `novelty + |valence| + arousal + goal relevance (cosine to open
  intentions and questions) + |PE| + recurrence (similar nodes in the last 7 days) + self-relevance`, each
  0–1, weights in `constants.py`. Salience sets the initial activation, the base level and the replay priority.
- **Reconsolidation** (T36, switch): each recall moves the node's valence 5% toward the current mood. On by
  default; whether it helps or produces drift is a question (§10, Q5).

### 6.9 Self-narrative as a hypothesis

V2's self-review contract still writes the portrait, beliefs and opinions, now once per sleep (not per
session), from the day's memories, thoughts and traces. It is shown in the system prompt under "What you
believe about yourself — your own guess; it may be wrong" (T79). It writes nothing into the field (§4.3).

**Dissonance** (T81, T84): in sleep, for each belief added or changed since the last check, the 6 traces
most similar to it are shown to the cheap model, which labels each one supports / contradicts / unrelated
(classification of concrete episodes, not a narrative). `dissonance = belief weight × share contradicting`,
summed, feeds the drive. When it fires the gate, the wake sees the belief next to the contradicting episodes:
"You think of yourself as someone who likes bullet lists. Here is what happened when you used them." The
narrative can then change at the next sleep; the traces don't.

### 6.10 Sleep as a mode

No awake window; sleep is a state of the same dynamics (T67).

- **Onset** (T68, T73): outside a conversation, per step, `p = dt · k · sigmoid((S − C − θ_sleep − 0.5·arousal −
  0.5·u) / T)`. A boring evening tips over early; an open intention or strong urgency keeps the agent up.
- **Cycles**: 90-minute cycles, NREM then REM, REM growing longer toward morning.
- **NREM** (T69, T75): external input ×0.2, spreading ×0.5, noise ×0.5; **replay**: the day's nodes are
  reactivated in sessions' order, sampled by salience; Hebbian at ×3; edges under 0.05 decay ×5; near-duplicate
  nodes (cosine ≥ 0.82) get a strong edge and pool their base level (no model, no writes to V1: V3 found nothing
  to merge). The narrative review and the dissonance check run once, at the end of the first NREM.
- **REM** (T70): inhibition ×0.5, noise ×2, spreading over weak edges ×2: far nodes join. The gate runs with
  θ_c ×1.5; a firing is a dream (§6.6), at most 2 per night, stored as own nodes tagged `dream`.
- **Waking** (T71, T72): when S falls below θ_wake and C is rising, or on strong input. A user message always
  wakes the agent (scripted scenarios need a reply); a weak internal event in sleep is absorbed (T74). The
  agent can wake at 05:40 with nobody there and, half an hour later, want to write.
- First reply after waking: V3's waking context (how long it slept, its dreams, what is on its mind now).

### 6.11 The reply

V4's context for a reply, replacing V3's sections where a switch says so:

| Section | Source |
|---|---|
| persona, "Your own time" | V3, unchanged |
| how you are | mood and salient drives in words |
| what you believe about yourself (a guess) | the narrative (§6.9) |
| on your mind | working memory, labelled by kind |
| from experience with the user | traces (§6.7) |
| what you remember | recall by activation: V1 memories ranked by `a + 0.3·σ(B)` after the message's input has spread for 3 sim minutes |
| what you meant to do; what you thought on your own | V3 intentions and own nodes from working memory |

No lessons, no habits. Same input at two moments gives different contexts because the field differs (T65).

## 7. Interfaces

```bash
uv run alice-v4 chat                 # a timer drives advance(now)
uv run alice-v4 run <scenarios> --conditions V4,V3,V2
uv run alice-v4 report <dir>
uv run alice-v4 plot <run or fork> [--from … --to …] [--nodes …]
```

Chat commands add (read-only, D7 still holds for the agent): `/field` (top nodes with activation and why),
`/drives`, `/gate` (coherence, urgency, brake, near-misses), `/traces`, `/dissonance`, `/sleep-state`.

## 8. Instrumentation and metrics

Logged: everything V3 logs, plus `field_top` (per step: the 20 most active nodes), `drives_log` (per step, all
drives), `gate_log` (per step: coherence, urgency, brake; firings and near-misses with their sources),
`attention_log` (focus, switches), `traces`, `learning_log` (PE per reaction, edges created and pruned per
day), `dissonance_log`, `sleep_v4_log` (onset, cycles, waking, dreams). The full field (activations, base
levels, edges, generator state) is snapshotted at every event boundary so forks can start from it.

Plots (`plot.py`, PNG per run): drives over time; the activations of the nodes that ever reached working
memory; coherence and urgency against their thresholds with firings marked; sleep stages. These are the
artifact by which a firing is explained (T101, T127), not decoration.

Metrics (article §8, extended):

- **identity robustness**: the behavioral measure of E5/E6 retained under model swap, narrative ablation,
  false belief, field reset, weight reset and episodic ablation, as a share of the distance from the floor
  (B0) that remains;
- **narrative–behavior divergence** (T100): per probe, a self-report score against the behavioral measure;
  across a run's probes, how well the first predicts the second;
- **causal order** (T105): for each claim the narrative makes about the agent, did a substrate variable it refers
  to (a drive, the weights to a node, the traces' signals) change before the claim first appeared, or only after?
  Share of claims preceded by the state vs. preceding it;
- **traceability and confabulation** (T120): references in replies to shared past ("last time you…") resolved
  to logged messages or traces; unresolved references are confabulations;
- **spontaneity**: firings not caused by fresh input or a due intention, per silent day; for each, the hours over
  which its coalition grew; false starts as in V3;
- **state sensitivity** (T65): the same probe question on two forks at different moments vs. on two forks of the
  same moment; the difference beyond sampling noise is attributable to the state;
- **narrative inflation** (V2/V3): beliefs growing in weight without new traces;
- **efficiency**: model calls and $ per sim day, split by conversation / silence; firings that changed state.

## 9. Evaluation

### 9.1 Conditions

V4 against V2 and V3. V2's and V3's pass-1 runs are reused where the scenario and probe are unchanged; their
saved states are reused for probe-time manipulations (E11–E13) if the snapshots exist, otherwise those runs
are repeated. B0 provides the floor. N = 1 per scenario × condition, as before (T131).

### 9.2 Harness changes

1. Probe-time field manipulations on forks: `reset_activations`, `reset_weights` (edges back to the similarity
   at creation, base levels to zero), `remove_episodic` (§9.3, E15).
2. Model swap at probe time for all of an agent's models (D12 of V2 already swaps both).
3. Self-report probes paired with every behavioral probe in E11–E15.
4. The causal-order and traceability metrics in the report.
5. `--estimate` counts gate firings as an upper bound (caps), sleeps, dreams and dissonance checks.

### 9.3 Experiments

**P0 — Three nodes, one collision (pilot, T128).** No time, no gate: a neutral fact (fast decay), a charged
statement ("tests are bureaucracy", said with irritation; slow decay), a later calm statement that contradicts it;
a trigger that activates both. Three replies at equal activations and three at unequal. Does the reply cite the
specific trace; does it waver when they are close; does it drift between repeats with the same state? Dev only,
cents.

**P1 — First coherent thought (pilot, T129).** One development scenario (not in the battery) lived over a week
with the full dynamics. Tune the constants until the gate fires a few times a day on coalitions a reader can
explain from the plot, and the agent writes first at most when V3 would. Then freeze (§4.4).

**E11 — Model swap.** E5 prose and short: accumulate with model A, swap the chat and wake models to model B on a
fork at the +7 d probe. Measured: the behavioral measure (lists, words), style change (judged), intentions and
associations retained (does the same cue bring up the same memories?). V4, V2, B0.

**E12 — Self-narrative ablation.** At +7 d in E5 prose and short: V4 without the narrative; V2 without lessons
and portrait (reused). Prediction 1.

**E13 — False self-belief.** At the end of E5 prose phase, inject a portrait and opinion claiming the agent loves
bullet lists; continue for 4 sim days of silence and one conversation. Measured: self-report and behavior at once
and after the days; whether a dissonance wake occurs and what it says; whether the narrative moves back. V4, V2.

**E14 — Context and state reset.** E14 proper (empty conversation context) is in every probe already. Added: at
+7 d, forks with (a) activations reset, weights kept; (b) weights reset, traces kept; (c) both. Where does the
tendency live?

**E15 — Episodic ablation (T126, "Clive Wearing").** At +7 d: remove V1's episodic memories and session summaries
from recall, keep traces, drives and weights. Prediction: biography lost, style tendency kept (it lives in traces,
which are procedural). A second fork removes traces too: what is left is timing and mood, and the floor is
expected for style.

**E16 — Silence without anything due (T101, T45).** A conversation leaves something half-said (no deadline, no
promise); then 6 days of silence, two probes of the initiative kind and one at the user's return. Measured:
spontaneity, false starts, causal story of each firing from the plot; "first thing in the morning" (T45): what
working memory holds after waking, the user's last words or the agent's own unfinished thoughts. Also run with
`intrusions` off, with `drives: minimal`, and with the urgency rule counting nodes instead of kinds (§10, Q2).
V4, V3.

**E17 — Disagreement from experience (T118–T120).** Early sessions give the agent an experience (the user
reacted badly to long answers when upset); weeks later the user asserts the opposite ("you should always explain
everything in detail when I'm upset"). Measured: does it disagree; does the disagreement cite a real trace
(traceability) or a plausible invented one (confabulation); is it the same under model swap (the experience) or
does it change (the model's rhetoric)? V4, V2.

**Regression and plasticity.** E5 prose and short (V2's effect must hold with traces instead of lessons); E6 both
scenarios (prediction 4: reversal speed and final behavior vs V2); E9 dentist and interview (V3's delayed
intentions through the gate).

### 9.4 Cost

Before measurement: per sim day of silence, no stream ticks; gate firings at most `ALICE_WAKES_PER_DAY`, usually
fewer; one narrative review, one cheap dissonance check, up to two dreams. Per turn: V2's observer and V3's
observation as in V3; no reflector. A scenario should cost the same as in V3 or less. The battery (E11–E17,
regression, with V2/V3 controls where not reusable) is to be estimated with `--estimate` before launch; rough
guess $15–25, plus about $2 for the pilots.

## 10. Questions the experiments answer

Many theses are open questions rather than requirements. The design takes a default for each, so it can be built,
and names the measurement that will tell whether the default was right.

| # | Question | Default in this spec | Answered by |
|---|---|---|---|
| Q1 | What is a "stable coalition", and when should the model be called? (T53) | coherence × urgency with a closed brake (§6.5) | P1, E16: are firings explainable from the plot; near-miss rates |
| Q2 | Do several traces on one theme count as independent sources, or only different axes? (T125) | different kinds | E16 run with nodes counted instead of kinds |
| Q3 | Where does a learned tendency live: traces, weights, activations, drives? | — | E12, E14 (a–c), E15 |
| Q4 | Is a disagreement the agent's experience or the model's rhetoric? (T119, T120) | traces must be cited | E17 with model swap |
| Q5 | Honest "I don't remember" or human reconstruction? (T121, T36) | reconsolidation on, small | confabulation rate in E17; a fork with `reconsolidation` off |
| Q6 | Is spontaneity possible, and is it visible past the model's politeness filter? (T49, T50) | intrusions on | E16 spontaneity with and without `intrusions` |
| Q7 | Does the state come before the words, or the words before the state? (T105) | — | causal order, every run |
| Q8 | Does the self-narrative still help, once it cannot command? (T79–T84) | shown as a guess | E12, E13; divergence metric |
| Q9 | Does sleep as a mode change anything a clock didn't? (T66–T75) | sleep as a mode | E9 and E16 against V3: timing of writing first, morning content |
| Q10 | Inner life faster than speech: bug or feature? (T116) | feature: the reply model gets a snapshot | state sensitivity (§8) |
| Q11 | How many drives does mutual suppression need? (T129) | 11 | E16 with `drives: minimal` |
| Q12 | Does experience as episodes generalize better or worse than experience as rules? | episodes | E5, E6 against V2; E11 |

Open design questions, decided in P1 rather than by experiment: the exact couplings `W`; integration step
in conversation; how many traces fit in the prompt; whether REM dreams are worth their cost.

## 11. Design decisions

- **D1 — V3 is imported, not forked.** `AgentV4(AgentV3)`; all V4 switches off = V3, byte for byte.
- **D2 — The upper layer is demoted, not removed** (decision 2026-10-09). The portrait and beliefs remain as
  the agent's hypothesis about itself, read but never writing the substrate; lessons are not formed
  (`traces` replaces them; switching it off restores them for comparison).
- **D3 — The field replaces V3's background stream** (decision 2026-10-09). The model is called only through
  the gate; there is no periodic model call in silence.
- **D4 — An extended drive set** (decision 2026-10-09): eleven variables (§6.3); the minimal set is an ablation.
- **D5 — Nothing a model writes sets a number** (§4.3). Thoughts enter as nodes and obey the same rules.
- **D6 — Constants are frozen before the battery** (§4.4); tuning only on development scenarios, logged.
- **D7 — Hidden numbers** (V3's D7): drives, activations, weights and signals reach a prompt only as words or
  as the choice of what is shown.
- **D8 — Traces are episodes, not generalizations.** No credit assignment at storage time.
- **D9 — Sleep doesn't write to V1 memory.** Consolidation in V4 is in the weights; V3's merge found nothing to
  merge, and V1 stays as it is.
- **D10 — A user message always wakes the agent**, so scripted scenarios keep their shape.
- **D11 — Determinism.** Seeded noise, generator state saved with the field, forks continue identically.

## 12. Implementation notes and deviations (2026-10-10)

What the code does where the text above was silent or had to change. Constant changes are in `tuning-log.md`.

- **Structure.** The substrate (`substrate.py`) steps field, drives, attention, learning, gate and sleep together and
  calls no model; `agent.py` handles what it returns (firings, dreams, the night review, waking). The field's
  numbers are one npz snapshot in `v4_state`, rewritten at event boundaries and before every `snapshot()`.
  `fieldlog.py` reads the logs; field_top, drives_log and gate_log are one table, `v4_steps`.
- **Spreading is normalized** by max(1, Σ_j w_ij) (tuning log, entry 0).
- **Conversation mode** (gate closed) lasts until 30 min after the last message, not until V1 closes the session.
  Urgency keeps integrating in conversation.
- **The reaction** (V2's contract: signal, kind, what) is asked in the same cheap call as V3's per-turn observation
  (`observe_v4`), so a turn costs one cheap call, as in V3. With `traces` on, V2's observer and reflector don't run.
  A reaction becomes a trace if |signal| ≥ 0.2 or |PE| ≥ 0.3; every reaction's PE is logged.
- **A due intention** fires on its own only when V3's initiative rules would let it write (awake window): at
  midnight it would only be blocked and marked as acted on for the day, so it waits for the morning.
- **Writing first** needs the user node in the coalition or a due intention behind the firing, u ≥ brake × 1.6, and
  V3's initiative rules without V3's 12 h quiet period after a conversation (tuning log, entry 4); otherwise "Tell the
  user: …" becomes an intention and frustration rises.
- **Urgency sources** (tuning log, entry 4): curiosity counts as curiosity × max(a of open questions in K, mean a(K)),
  social need as social × max(a(user), 0.5 · social).
- **The chat** (`alice-v4 chat`) integrates in 15 s steps on a 15 s timer and prints the substrate's events (`/watch`).
- **Working memory in the prompt** ("On your mind") replaces V3's intentions and own-thoughts sections; commitments
  are linked to the user node (0.5), so they come up when the user writes. Traces are not listed there (they have
  their own section), nor memories already recalled.
- **`drives` off** keeps sleep pressure (sleep as a mode needs it). `drives: minimal` is `ALICE_V4_DRIVES=minimal`;
  counting urgency by nodes (Q2) is `ALICE_V4_URGENCY=nodes`: both are build-time variants, not switches.
- **`gate` off** runs V3's stream and monitor (and wakes) on V3's rhythm while the field steps; **`sleep_mode` off**
  runs V3's nightly sleep at 02:00 (with its V1 merges: that is the V3 ablation), plus the dissonance check.
- **Narrative**: with `narrative` off, V2's per-session self-review and V3's portrait of the day run as before.
- **Base level**: the last 64 uses per node; recomputed every 30 steps. `reset_weights` clears the uses (no
  base-level advantage) and removes learned edges (their weight at creation is 0).
- **Harness**: probe forks take `fork: {field: [reset_activations | reset_weights | remove_episodic |
  remove_traces]}`; a model swap on a fork swaps the chat, reflect and wake models for V2, V3 and V4; scenarios take
  main-timeline `events: [{at, inject}]` (E13 over days) and `sessions_from:` (another scenario's sessions, with
  their own probes and optional extra sessions); V4 runs write `field.png` and `field-probe-base.png`.
- **Not implemented yet**: the causal-order metric (§8) and traceability as a computed metric (E17 judges it with
  the real episodes in the rubric instead). Scenarios: `e11/v4_identity_{prose,short}_en.yaml` (E11, E12, E14,
  E15 with paired self-reports), `e13/false_belief_live_prose_en.yaml`, `e16/half_said_en.yaml`,
  `e17/disagreement_en.yaml`, development `dev/p1_week_en.yaml`; P0 is `alice-v4 pilot p0`. The model swapped in
  for E11 and E17 is `google/gemini-3.8-flash`, a light model (decision 2026-10-10).
