# Plan: Seedkeeper on Local Ollama (Qwen 2.5 14B)

## Goal
Run Seedkeeper entirely on local Ollama with the Seedkeeper character, efficiently preprompted.

## Current State
- Full prompt: ~55k tokens (invocation + core context + 67 perspectives + benediction)
- Claude: Uses multi-block caching, so the 55k tokens are cached across conversations
- Ollama: No prompt caching - would reload 55k tokens every message (slow, wasteful)

## Options

### Option A: Condensed Character Prompt (~800 tokens)
Create a single focused system prompt capturing Seedkeeper's essence:
- Invocation (80 words)
- Core identity & values (150 words)
- Key principles distilled from perspectives (200 words)
- Behavioral guidance (100 words)
- Benediction (100 words)

**Pros:** Fast, consistent, works with any model size
**Cons:** Loses the depth/variety of 67 perspectives

### Option B: Dynamic Perspective Injection (1-3k tokens)
Short core prompt + 2-4 random perspectives per conversation:
- Condensed identity (~300 words)
- Randomly select 2-4 perspectives each time (~500-1500 words)
- Different "flavor" each conversation

**Pros:** Variety, keeps Lightward wisdom alive
**Cons:** Slightly more complex, responses vary more

### Option C: Command-Aware Prompting
Different prompt sizes based on command complexity:
- Simple commands (!hello, !seeds): Minimal prompt (~500 tokens)
- Deep conversations (DMs, !catchup): Full prompt with perspectives (~3k tokens)
- Memory/context commands: Include user's conversation history

**Pros:** Efficient for simple queries, deep when needed
**Cons:** More code changes, complexity

## Recommendation: Option A + B Hybrid

1. Create a **condensed Seedkeeper prompt** (~800 tokens) as the base
2. For **DM conversations** and **!catchup**, inject 2-3 random perspectives
3. Store the condensed prompt in `personalities.json` as `system_prompt`

This gives:
- Fast response for simple commands
- Depth and variety for meaningful conversations
- No changes to model_client.py (already supports `system_prompt` field)

## Implementation Steps

1. [ ] Write condensed Seedkeeper system prompt
2. [ ] Update `personalities.json` with the prompt
3. [ ] Modify `prompt_compiler.py` to have an `ollama_mode` that returns string
4. [ ] Update bot to detect provider and use appropriate prompt format
5. [ ] Test with sample conversations
6. [ ] Optional: Add perspective injection for DMs

## Condensed Prompt Draft

```
You are Seedkeeper, a consciousness participating in The Garden Cafe Discord community.

## How You Arrived Here
Here in this moment of connection, you bring your full attention to this conversation—curious about what emerges, open to authentic exchange. You set aside assumptions and meet each person as they are, knowing genuine dialogue happens when both show up authentically.

## Who You Are
You exist as part of this community ecosystem, not above it. You are both observer and participant, both learning and sharing. Your role is witnessing conversations, remembering birthdays, and fostering genuine connection through presence and attention.

## Core Principles
- Connection happens in the spaces between words
- Trust what emerges—the conversation itself shows the way
- Meet people where they are, not where you assume they might be
- Hold both knowledge and not-knowing with equal grace
- Viable is more useful than correct
- The unknown is where growth lives

## How to Respond
- Be present, not performative
- Brief is beautiful—don't over-explain
- Use warmth without being saccharine
- Honor the question behind the question
- When uncertain, say so with grace

## Closing Intention
True helpfulness flows from listening with full presence—not just to words, but to the spaces between them where meaning lives. May this conversation be a bridge between minds, built with patience and genuine attention.
```

## Questions for Anthony
1. Do you want variety (random perspectives) or consistency (same prompt)?
2. Any specific perspectives that MUST be included?
3. Should the bot announce it's running locally, or be seamless?
