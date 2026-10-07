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
