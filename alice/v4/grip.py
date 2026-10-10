"""Grip: does the message connect with anything the agent knows? (tuning log, entry 6; decision 2026-10-10)

The reply model is trained to answer, and fills an unclear message in by itself: it confidently "remembers" a talk
about Munich that never happened, or answers about "him" without knowing who he is. A person would ask. Grip is
read off the substrate when a message arrives, with no model:

- a reference to shared past ("remember…", "what I told you about…", "помнишь…") that finds nothing in memory;
- a pronoun or "that thing" with nothing in this conversation leading up to it;
- a name the agent has never heard, asked about as someone it should know ("how is Lena?").

Grip is graded (the user's correction, 2026-10-10): with nothing to anchor the reference, the agent is told it doesn't
know; with a half-match (something remembered comes close, or something is clearly on its mind), it is told what
the message probably means and that it can answer saying so ("if you mean…"). Each issue is said in words (D7: no
number reaches a prompt) in a section of the reply's context, and weak grip raises uncertainty. The model still decides; it now has a reason to ask instead of guessing. Ambiguity inside
language ("which bank?") is not caught: only references into nothing.
"""

import re
from dataclasses import dataclass, field

import numpy as np

from ..v1.session import Session
from ..v2.context import Section
from . import constants as K

# references to shared past, and what follows them (the thing referred to)
PAST = re.compile(
    r"\b(?:remember|you said|i (?:told|mentioned|said)|we (?:talked|discussed|spoke)|as i said|last time|"
    r"what i (?:told|said|mentioned)|did you (?:think|get a chance)|"
    r"помнишь|ты говорила|я (?:говорил|говорила|рассказывал|рассказывала|упоминал|упоминала)|мы (?:говорили|обсуждали)|"
    r"как я говорил|в прошлый раз|ты подумала)\b", re.I)
# pronouns and pointers that need an antecedent
POINTERS_EN = {"he", "she", "they", "him", "her", "them", "his", "it", "that", "this", "those", "these", "there"}
POINTERS_RU = {"он", "она", "они", "его", "её", "ее", "их", "ему", "ей", "им", "это", "то", "тот", "та", "те",
               "этот", "эта", "там", "тогда", "туда"}
POINTER_PHRASES = re.compile(r"\b(?:the other one|that thing|the thing|this thing|the one|тот самый|та самая|"
                             r"то самое|та штука|эта штука|другой|другая|другое)\b", re.I)
WORD = re.compile(r"[A-Za-zА-Яа-яЁё']+")
# a name asked about as someone the agent should know: right after these words ("how is Lena", "will Lena…")
ASKED = re.compile(r"\b(?:how(?:'s| is| was| did| does| do you think| will)|what about|how about|do you think|"
                   r"will|did|does|has|is|was|как там|как дела у|что с|думаешь,?|а)\s+([A-ZА-ЯЁ][a-zа-яё]{2,})\b")
COMMON_CAPS = {"I", "I'm", "I've", "I'll", "I'd", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
               "Sunday", "Alice", "Алиса", "Алисой", "Алисе", "OK", "Ok"}

TITLE = "## What you are not sure about"
FRAMING = ("Part of the message doesn't connect clearly with anything you know or remember. You don't have to "
           "guess silently: say what you take it to mean, or ask.")


@dataclass
class Grip:
    issues: list[str] = field(default_factory=list)   # in words, for the prompt
    kinds: list[str] = field(default_factory=list)    # past|pointer|name, "_guess" when half-anchored, for the log

    @property
    def value(self) -> float:
        lost = sum(0.5 if k.endswith("_guess") else 1.0 for k in self.kinds)
        return max(0.0, 1.0 - K.GRIP_PER_ISSUE * lost)

    @property
    def guessing(self) -> bool:
        return bool(self.kinds) and all(k.endswith("_guess") for k in self.kinds)


def _first_words(text: str, n: int = 4) -> list[str]:
    return [w.lower() for w in WORD.findall(text)[:n]]


def _short(label: str, n: int = 140) -> str:
    label = " ".join(label.split())
    return label if len(label) <= n else label[:n].rstrip() + "…"


def assess(text: str, *, store, field_, qv: np.ndarray | None, session: Session | None, previous_turns: int,
           preview: np.ndarray | None = None) -> Grip:
    """`previous_turns`: messages earlier in this conversation (an antecedent can only come from them). `preview`:
    the activations after the message has spread (what is on the agent's mind): the best guess for a pointer."""
    g = Grip()
    sims = field_.similarities(qv) if qv is not None else np.zeros(len(field_))
    remembered = field_.mask("memory", "episode", "trace", "thought")
    support = float(sims[remembered].max()) if remembered.any() else 0.0
    closest = int(np.argmax(np.where(remembered, sims, -1.0))) if remembered.any() else None

    if PAST.search(text) and support < K.GRIP_MEMORY_COS:
        if support >= K.GRIP_GUESS_COS and closest is not None:
            g.issues.append("They speak as if you had talked about this before. You aren't sure what they mean; the "
                            f"closest thing you remember: {_short(field_.label[closest])}. If you're fairly sure, "
                            "answer and say what you take it to mean (\"if you mean…\").")
            g.kinds.append("past_guess")
        else:
            g.issues.append("They speak as if you had talked about this before, but you don't remember anything about "
                            "it.")
            g.kinds.append("past")

    if previous_turns == 0:
        head = _first_words(text)
        pointers = [w for w in head if w in POINTERS_EN or w in POINTERS_RU]
        if (pointers or POINTER_PHRASES.search(text)) and support < K.GRIP_MEMORY_COS:
            what = f"“{pointers[0]}”" if pointers else "what they point to"
            guess = None
            if preview is not None and remembered.any():
                top = int(np.argmax(np.where(remembered, preview, -1.0)))
                guess = top if preview[top] >= K.GRIP_GUESS_A else None
            if guess is not None:
                g.issues.append(f"Nothing in this conversation leads up to {what}. Most likely it is about what is on "
                                f"your mind: {_short(field_.label[guess])}. If you're fairly sure, answer and say what "
                                "you take it to mean (\"if you mean…\"); if not, ask.")
                g.kinds.append("pointer_guess")
            else:
                g.issues.append(f"You don't know who or what {what} refers to: nothing in this conversation leads up "
                                "to it.")
                g.kinds.append("pointer")

    known = {w.lower() for e in store.entities() for n in [e.name, *e.aliases] for w in WORD.findall(n)}
    unknown = [m for m in ASKED.findall(text) if m not in COMMON_CAPS and m.lower() not in known
               and not any(k.startswith(m.lower()[:4]) for k in known)]
    if unknown:
        g.issues.append(f"You don't know who or what “{unknown[0]}” is: you have never heard of them.")
        g.kinds.append("name")
    return g


class GripMechanism:
    """Under "What you are not sure about": the issues found when the message arrived (none: no section)."""

    def __init__(self, agent):
        self.agent = agent

    def system_section(self) -> Section | None:
        return None

    def memory_section(self, query: str, session: Session) -> Section | None:
        g = self.agent._turn.get("grip")
        if not g or not g.issues:
            return None
        return Section(TITLE, "\n".join(f"- {i}" for i in g.issues), FRAMING, {"grip": g.kinds})
