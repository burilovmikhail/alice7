# Article

One file per top-level section; the numeric prefix is the order.

| File | Section |
|---|---|
| `01-introduction.md` | title, central research question, §1 Introduction |
| `02-method.md` | §2 Research Method (shared protocol for all versions) |
| `03-v1-persistent-memory.md` | §3 V1 — Persistent Memory |
| `04-v2-adaptive-identity.md` | §4 V2 — Adaptive Identity |
| `05-v3-continuous-cognition.md` | §5 V3 — Continuous Cognition (cheap background stream + expensive wakes) |
| `06-v4-continuous-cognitive-dynamics.md` | §6 V4 — Continuous Cognitive Dynamics |
| `07-critical-experiments.md` | §7 Critical Experiments (E11–E14) |
| `08-cross-version-metrics.md` | §8 Cross-Version Metrics |
| `09-experimental-matrix.md` | §9 Experimental Matrix |
| `10-discussion.md` | §10 Discussion |
| `11-limitations.md` | §11 Limitations |
| `12-conclusion.md` | §12 Conclusion |

Full text in one file:

```bash
for f in article/[0-9]*.md; do cat "$f"; printf '\n---\n\n'; done > article.md
```

Shorter versions for specific venues are cut from these files, not maintained separately.
