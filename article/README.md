# Article

One file per top-level section; the numeric prefix is the order.

| File | Section |
|---|---|
| `01-introduction.md` | title, central research question, §1 Introduction |
| `02-method.md` | §2 Research Method (shared protocol for all versions) |
| `03-v1-persistent-memory.md` | §3 V1 — Persistent Memory |
| `04-v2-adaptive-identity.md` | §4 V2 — Adaptive Identity |
| `05-v3-continuous-cognition.md` | §5 V3 — Autonomous / Continuous Cognition |
| `06-v3.5-hierarchical-cognition.md` | §6 V3.5 — Hierarchical Cognition |
| `07-v4-continuous-cognitive-dynamics.md` | §7 V4 — Continuous Cognitive Dynamics |
| `08-critical-experiments.md` | §8 Critical Experiments (E11–E14) |
| `09-cross-version-metrics.md` | §9 Cross-Version Metrics |
| `10-experimental-matrix.md` | §10 Experimental Matrix |
| `11-discussion.md` | §11 Discussion |
| `12-limitations.md` | §12 Limitations |
| `13-conclusion.md` | §13 Conclusion |

Full text in one file:

```bash
for f in article/[0-9]*.md; do cat "$f"; printf '\n---\n\n'; done > article.md
```

Shorter versions for specific venues are cut from these files, not maintained separately.
