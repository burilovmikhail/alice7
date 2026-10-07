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
