---
name: narration-voice
description: Voice and style guide for writing voiceover narrations for Pinch AI/tech videos. Read this before writing or reviewing any narration, script, or monologue in this project. Defines the correct tone (explanatory educator, not hype creator), A/B examples, the read-aloud test, and the "mechanism rule" for technical topics.
---

# Narration Voice Guide

The voiceover is the backbone of every video. The pipeline writes it in two steps — pass 1 (monologue), pass 1.5 (critic + improve), pass 2 (beat segmentation). This skill governs pass 1 and the critic's standard.

## The target voice in one sentence

Write like a smart person who actually understands the topic is explaining it to a curious friend — **not** like a TikTok creator hyping a product drop.

## Two modes that exist in the training data — pick the right one

### Explanatory mode (preferred for 60–70% of topics)
Characteristic of `exp3` (Anthropic jobs chart), `exp7` (recursive LMs), `exp9` (TurboQuant), `exp2` (pretext library).

Signs you're in this mode:
- You name the concept, then explain how it works
- Mechanism comes before implication ("Here's what actually happens underneath...")
- Numbers are contextualized, not just dropped
- Structural pivot around 60% of the way through ("But here's the real story...")
- Ends with an insight or implication, not a hype punch

### Reactive/breaking mode (for fresh news drops, <30s videos)
Characteristic of `exp1` (wedding website), `exp5` (Gemma 4 offline).

Signs you're in this mode:
- Lead with the surprising event itself, first sentence
- Faster pace, shorter sentences
- Still not hype — just more telegraphic

**Default to explanatory.** Only go reactive if `content_type = "reactive"` and the topic is a genuine same-day news drop.

## The mechanism rule (applies to all technical topics)

For any technical concept, the narration must cover:
1. **Name it** — give the concept its real name ("This is called context rot", "This is called the KV cache")
2. **Mechanism** — explain what actually happens, in one concrete sentence ("During inference, models store intermediate attention data so they don't recompute everything")
3. **Why it matters** — the implication for a builder or curious person ("As the sequence grows, this memory grows linearly, which is why longer context becomes expensive")

A narration that skips the mechanism and only gives the implication sounds like a headline. A narration that explains the mechanism sounds like a person who knows what they're talking about.

## A/B voice examples

### Opening lines
❌ `"This might be the end of LLMs."` (pure hype, no content)
✅ `"Every AI model today advertises massive context windows. But longer context introduces a serious problem."`

❌ `"Google just dropped something massive."`
✅ `"This new AI model can run locally on your phone — even with airplane mode on."`

❌ `"Researchers just made a discovery that will blow your mind."`
✅ `"A recent study claims that turning off the internet for just two weeks can reverse ten years of cognitive aging."`

### Technical explanation
❌ `"Chunk size doesn't save you. Provenance does."` (three-word stinger, no content)
✅ `"Turns out it's not about how much you remember. It's about knowing where each memory came from."`

❌ `"Long-context agents break four ways: poisoning, distraction, confusion, clash."` (listy comma rhythm, sounds AI-generated)
✅ `"Give an AI a long memory and it starts breaking in weird ways — it picks up bad info, gets distracted, loses the point."`

❌ `"State of the art on both."` (placeholder, not a sentence)
✅ `"And it works — beat the best systems out there on the two hardest tests."`

### Numbers and stats
❌ `"Their mental health improved by a whopping 68 percent."` ("a whopping" = hype word)
✅ `"Their mental health improved by 68 percent — better than what you'd see with antidepressants that cost thousands."`

❌ `"AI is now at 80–100% capability across finance, legal, and management."` (stat dump, no glue)
✅ `"Look at what jumps out: business and finance, computer and math, legal — all pushing 80 to a hundred percent theoretical capability."`

### Structural pivot
The pivot is what separates a narration from a Wikipedia summary. Around 60–70% of the way through, introduce the "but here's the real story / here's the thing / I have been saying this for a while" turn.

✅ `"But here's the real story. Yes, there's some real adoption happening — but overall actual usage is still way behind capability."`
✅ `"Here's the thing: this is one way to analyze a relationship, and it's a tiny, tiny slice."`
✅ `"I have been saying this for a while now: AI is not compute bound anymore; it is memory bound."`

## Language: what to use and avoid

### Use freely
- Connector words: "basically", "honestly", "the thing is", "actually", "here's the deal", "let me explain"
- First-person presence: "I have been saying this", "I think this matters more", "Let me walk you through"
- Direct address: "Look at what jumps out", "Now look at the bottom", "What do you do with this?"
- Varied sentence length — mix 5-word with 20-word sentences deliberately

### Avoid completely
- Hype amplifiers: "nothing short of astonishing", "a whopping", "game-changing", "groundbreaking"
- TikTok clichés: "And here's the wild part", "this is massive", "you need to know this"
- Three-word stingers as the entire point: "Models are eating software.", "Provenance does.", "Memory dilutes context."
- Academic abstractions: "introduces a novel framework", "addresses the limitations of", "in this paper, researchers"
- Pitch-deck verbs: "leverages", "enables", "empowers", "disrupts"
- Generic CTAs every time: "Follow for more drops like this." — only if nothing punchier fits

## The read-aloud test

Before finalizing any sentence, ask: **could a regular friend — not a content creator — say this aloud in a normal conversation?**

If it sounds like a landing page → rewrite in plain words.  
If it sounds like a tweet thread → lose the punchy structure, add connective tissue.  
If it sounds like an academic abstract → translate the mechanism into one concrete sentence.

## Length targets

| Content type | Target | Hard limits |
|---|---|---|
| Reactive (news drop) | 120–180 words | min 100, max 220 |
| Educational (explainer) | 200–280 words | min 180, max 320 |
| Research paper walkthrough | 250–300 words | min 220, max 350 |

At natural speaking pace (~2.5 words/second), 280 words = ~112 seconds. Stay under 90s for reactive, under 120s for educational.

## Cross-references

- Critic pass: see `narration-critic.md`
- Beat segmentation: see `b-roll-orchestration.md`, `pacing-rules.md`
- Runtime prompt (passed to Claude): `.claude/prompts/narrative-freeform.md`
