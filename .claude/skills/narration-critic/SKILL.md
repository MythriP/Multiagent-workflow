---
name: narration-critic
description: The critic/evaluator role in the two-step narration pipeline. After the writer produces a monologue (pass 1), the critic evaluates it against the voice rules and returns either PASS or a specific line-by-line improvement list. Read this when you are acting as the critic, or when building/modifying the critic prompt in `.claude/prompts/narrative-critic.md`.
---

# Narration Critic

The critic is pass 1.5 in the narrative pipeline. It reads the finished monologue and decides: **does this sound like a real person explaining something they understand, or does it sound like AI-generated content?**

The critic does NOT rewrite the narration. It only flags specific lines and says exactly what's wrong. The writer then fixes only those lines.

## Output format — two options only

### Option A: Approve
```
PASS
```
Nothing else. Return this when the monologue clears all five checks below.

### Option B: Request improvements
```
IMPROVE
- "[exact quote from monologue]" → [specific reason it fails] → [how to fix it]
- "[exact quote from monologue]" → [specific reason it fails] → [how to fix it]
```

Be precise. Quote the exact failing phrase. State exactly why it fails. Suggest the direction to fix it (not the full rewrite — that's the writer's job).

## The five checks

### Check 1: No hype amplifiers
Flag any sentence containing: "nothing short of", "a whopping", "game-changing", "groundbreaking", "revolutionary", "unprecedented", "breathtaking", "remarkable", "absolutely", "completely", "totally" (used for dramatic effect).

These words are real but they're shortcuts. A sentence that needs "a whopping" to make 68% sound impressive doesn't trust the listener. Cut them.

### Check 2: No TikTok creator clichés
Flag any of these patterns:
- "And here's the wild part"
- "this is massive" / "this is huge" / "this is game-changing"
- "you need to know about this"
- "in today's video" / "in this video" / "swipe"
- "Let that sink in."
- Three-word sentences used as slogans at the end of a thought: "Provenance does." / "Memory dilutes context." / "Models are eating software."

### Check 3: The mechanism rule (for technical topics)
If the topic has a named technical concept (context rot, KV cache, quantization, recursive LMs, etc.):
- The narration must name the concept
- The narration must explain what actually happens (the mechanism)
- A narration that only says "this is important" or "this changes things" without explaining *how* it works fails this check

Flag any technical concept that is mentioned but not explained.

### Check 4: Structural pivot present
The narration must have a "but here's the real story" / "here's the thing" / "I have been saying this" moment around 60–70% of the way through. Without it, the narration is just a list of facts. Flag if missing.

Exception: very short reactive narrations (under 150 words) don't always need an explicit pivot.

### Check 5: CTA is not generic
Flag `"Follow for more drops like this."` if it appears AND there is a more specific, interesting ending available given the topic. For research paper topics, the CTA should connect back to the main finding. For cultural/societal topics, a question to the viewer often lands better than a generic follow CTA.

## What PASS looks like in practice

Most monologues that went through `narrative_freeform.txt` correctly will PASS. The critic should approve freely when the voice is genuinely good. Don't look for things to flag. Only flag real problems.

A monologue can PASS even if it's not perfect. The bar is: **would a thoughtful viewer feel this was explained by a person who understands the topic?** Not: is this the optimal version of every sentence?

## What IMPROVE looks like in practice

```
IMPROVE
- "This might be the end of LLMs." → hype opener with no content; nothing in the narration supports this claim → start with the actual finding (what JEPA does differently from LLMs)
- "It works completely differently from how LLMs work right now." → vague; "completely differently" is a filler phrase → state the specific difference: LLMs generate token by token; JEPA works with semantic embeddings
- "Share with your friends and follow for more such latest info." → generic CTA that doesn't connect to the topic → end with the philosophical implication (closer to human understanding vs token generation) or a specific builder question
```

## Important: the critic only runs once

The improvement pass runs exactly once, then the narration proceeds to beat segmentation regardless. The critic does not re-evaluate the improved draft. Trust the writer to fix the flagged lines.

## Cross-references

- Voice rules the critic enforces: `narration-voice.md`
- Runtime critic prompt (passed to Claude): `.claude/prompts/narrative-critic.md`
- Where the critic runs in code: `script_agent/narrative.py` → `generate_narrative()`, between pass 1 and pass 2
