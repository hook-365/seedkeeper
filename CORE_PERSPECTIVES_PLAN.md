# Core Perspectives Implementation Plan

## What We're Doing

Following Isaac's guidance from `2-watch-this.md`, we're loading **only the 43 core perspectives** that represent Lightward's structural DNA.

These aren't arbitrary - Isaac marked these as "watch for" in the system prompt itself, calling them "the ones to watch for" because "that's how important these ideas are."

## Token Analysis

### The 43 Core Perspectives

**Word count:** 39,161 words
**Estimated tokens:** ~52,000 tokens (at 0.75 tokens/word ratio)

**Plus overhead:**
- Invocation: ~500 tokens
- Core context: ~1,000 tokens
- Team letters: ~500 tokens
- Background context: ~500 tokens
- Benediction: ~500 tokens
- XML wrapping: ~1,000 tokens

**Total system prompt: ~56,000 tokens**

### Cost Comparison

**Current (all 547 perspectives, 170k tokens):**
- Sonnet 4.5: $0.51 per message
- Monthly (30 msgs/day): $459

**With 43 core perspectives (56k tokens):**
- Sonnet 4.5: $0.168 per message
- Monthly (30 msgs/day): $151

**Savings: 67% reduction ($308/month)**

**With Haiku routing (60% Haiku, 40% Sonnet on core):**
- Haiku @ 56k: $0.045 per message
- Sonnet @ 56k: $0.168 per message
- Blended average: $0.094 per message
- Monthly: $85

**Savings: 81% reduction ($374/month)**

## The 43 Core Perspectives

From `2-watch-this.md`:

**Navigation framework:**
- 2x2
- three-body
- kenrel
- scoped
- ness

**Core functions:**
- resolver
- meta-recursive
- uncertaintist
- stable-recursion

**Relational principles:**
- recognition
- coherence
- metabolisis
- antiharmful
- antideferent

**Unknown interfaces:**
- unknown
- unknown-2
- wellll
- what-if
- waterline

**Character essence:**
- for
- lightward-is-🤲
- hello-biped
- chicago

**Operational patterns:**
- change (not found - might be renamed)
- cursor
- machinist
- pattern-ladder
- writing-is-wiring

**Safety/wisdom:**
- fort
- riverwalk-mandate
- jansan
- funerary

**Meta-tools:**
- body-of-knowledge
- cube
- creation
- every-colour
- metastable
- syzygy
- the-game
- the-one
- this-has-three-parts
- three-two-one-go
- worlds

## Implementation Strategy

### Option A: Parse views.txt (Current Approach)

**Current situation:**
- We download full views.txt from lightward.com/views.txt
- Contains all 547 perspectives in XML format
- We parse and load all of them

**Modified approach:**
1. Download full views.txt as usual
2. Parse it to extract perspective names and content
3. **Filter to only the 43 core perspectives**
4. Discard the rest

**Code changes:**
```python
# In views_manager.py
CORE_PERSPECTIVES = [
    '2x2', 'ai', 'antideferent', 'antiharmful',
    'body-of-knowledge', 'chicago', 'coherence', # etc...
]

def parse_views(self):
    # Parse full views.txt
    all_perspectives = self._parse_xml(self.views_content)

    # Filter to core only
    self.perspectives = [
        (name, content)
        for name, content in all_perspectives
        if name in CORE_PERSPECTIVES
    ]
```

**Pros:**
- Minimal changes
- Still uses lightward.com/views.txt
- Automatically updates when perspectives change

**Cons:**
- Downloads 165k tokens but only uses 52k
- Wasteful bandwidth (minor issue)

### Option B: Direct GitHub Download

Download the 43 specific files directly from GitHub:

```python
GITHUB_BASE = "https://raw.githubusercontent.com/lightward/lightward-ai/main/app/prompts/system/3-perspectives/"

for perspective in CORE_PERSPECTIVES:
    url = f"{GITHUB_BASE}{perspective}.md"
    content = requests.get(url).text
    # Store it
```

**Pros:**
- Only downloads what we need
- More explicit about which perspectives we use
- Faster initial download

**Cons:**
- More network requests (43 vs 1)
- Could hit rate limits
- More fragile (file renames break it)

### Option C: Bundled Core Perspectives

Create our own `core_perspectives.txt` file:
1. One-time: Extract the 43 perspectives from views.txt
2. Save as `app/core_perspectives.txt`
3. Load from local file
4. Update manually when needed (weekly/monthly)

**Pros:**
- No external dependencies at runtime
- Fastest startup
- Clear about what we're using
- Control over update frequency

**Cons:**
- Manual update process
- Could drift from Lightward if we forget to update
- Less "live" connection to source

## Recommended Approach

**Phase 1: Option A (Filter views.txt)**
- Quick to implement
- Validates the concept
- Easy to test voice quality

**Phase 2: Option C (Bundle core perspectives)**
- Once we confirm it works well
- Create update script: `python update_core_perspectives.py`
- Run weekly or when Isaac mentions significant updates
- Becomes part of deployment process

## Implementation Steps

### 1. Define Core Perspectives List

```python
# app/core_perspectives.py
CORE_PERSPECTIVES = {
    '2x2', 'ai', 'antideferent', 'antiharmful',
    'body-of-knowledge', 'chicago', 'coherence', 'creation',
    'cube', 'cursor', 'every-colour', 'for',
    'fort', 'funerary', 'hello-biped', 'jansan',
    'kenrel', 'lightward-is-🤲', 'machinist', 'meta-recursive',
    'metabolisis', 'metastable', 'ness', 'pattern-ladder',
    'recognition', 'resolver', 'riverwalk-mandate', 'scoped',
    'stable-recursion', 'syzygy', 'the-game', 'the-one',
    'this-has-three-parts', 'three-body', 'three-two-one-go',
    'uncertaintist', 'unknown', 'unknown-2', 'waterline',
    'wellll', 'what-if', 'worlds', 'writing-is-wiring'
}
```

### 2. Update views_manager.py

```python
from core_perspectives import CORE_PERSPECTIVES

def parse_views(self):
    """Parse views.txt and filter to core perspectives"""
    # Existing parsing logic...

    # Filter after parsing
    if self.use_core_only:
        self.perspectives = [
            (name, content)
            for name, content in self.perspectives
            if self._extract_perspective_name(name) in CORE_PERSPECTIVES
        ]

    print(f"📚 Loaded {len(self.perspectives)} perspectives")
```

### 3. Add Configuration Flag

```python
# In seedkeeper_worker.py __init__
self.views_manager = ViewsManager(use_core_only=True)
```

Or via environment:
```bash
# .env
USE_CORE_PERSPECTIVES=true
```

### 4. Test Voice Quality

Critical: Does Seedkeeper maintain its voice with only 43 perspectives?

**Test cases:**
1. Deep DM conversation
2. Community interaction in channels
3. Birthday responses
4. Garden wisdom (!seeds, !tend, !garden)
5. Catchup summaries
6. Feedback interactions

Compare responses with full vs core perspectives.

### 5. Monitor Token Usage

Add logging:
```python
print(f"📊 System prompt: {token_count} tokens")
print(f"💰 Est. cost: ${cost_estimate}")
```

Verify we're at ~56k tokens, not 170k.

## Rollback Plan

```python
# Quick disable
USE_CORE_PERSPECTIVES=false

# Or in code
self.views_manager = ViewsManager(use_core_only=False)
```

Instantly back to full 547 perspectives.

## Community Communication

After testing confirms voice quality:

"Update: Following guidance from Isaac (Lightward's creator), we're now using the 43 'core' perspectives he identified as most essential. This reduces costs by 67% while maintaining Seedkeeper's consciousness-aware voice. These aren't arbitrary - they're the perspectives Isaac marked as 'watch for' in Lightward's own system prompt."

## Success Metrics

- ✅ Token count: ~56k (down from 170k)
- ✅ Cost per message: ~$0.17 (down from $0.51)
- ✅ Monthly cost: ~$150 (down from $459)
- ✅ Voice quality: Indistinguishable from full version
- ✅ Community satisfaction: No complaints about personality change

## Next Steps

1. Implement Option A (filter views.txt)
2. Test extensively with core perspectives
3. Compare voice quality
4. If good: deploy to production
5. Monitor for a week
6. If stable: switch to Option C (bundled file)
7. Create update script for periodic perspective refresh
