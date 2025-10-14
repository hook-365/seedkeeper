# Actual Cost Analysis with 5-Minute Caching

## What's Actually Implemented

### ✅ Currently Active:
1. **Prompt caching enabled** (from earlier today)
   - All 6 API calls in `seedkeeper_worker.py` use caching
   - All 6 API calls in `garden_wisdom.py` use caching
   - Single-message caching (entire system prompt cached as one block)

2. **Core perspectives loaded** (just now)
   - 44 perspectives from Isaac's "watch for" list
   - ~56k tokens in system prompt (down from ~170k)
   - Automatically used when bot starts

### ❌ NOT Implemented Yet:
- Multi-message layered caching (we designed it but didn't implement)
- Haiku routing for simple commands (designed but not implemented)

## Real Cost Predictions with 5-Minute Cache

### Your Traffic Pattern
- **12-50 messages/day**
- **Average: ~30 messages/day**
- **Bursty:** Most messages arrive in clusters, then quiet periods

### Key Insight: Cache Expires Every 5 Minutes

**The 5-minute window is CRITICAL.** Let's model realistic scenarios:

### Scenario 1: Evenly Distributed Messages (Worst Case)

Messages arrive every 15+ minutes (cache always expired):

| Component | Tokens | Cost/Message |
|-----------|--------|--------------|
| System prompt (write) | 56,000 | $0.168 |
| Response (1000 tokens avg) | 1,000 | $0.015 |
| **Total per message** | | **$0.183** |

**Monthly cost:**
- 30 msgs/day × 30 days = 900 messages
- 900 × $0.183 = **$165/month**

### Scenario 2: Realistic Bursty Pattern (Best Case)

5 bursts per day, 6 messages per burst, 5+ min between bursts:

**Per burst:**
- Message 1: Cache write ($0.168) + response ($0.015) = $0.183
- Messages 2-6: Cache read ($0.017) + response ($0.015) = $0.032 each

**Per day:**
- 5 bursts × [1 write ($0.183) + 5 reads ($0.032×5)] = 5 × $0.343 = **$1.72/day**

**Monthly:**
- $1.72 × 30 = **$52/month** 🎉

### Scenario 3: Mixed Pattern (Most Realistic)

- 60% of messages catch cache hits (arrive within 5 min of previous)
- 40% of messages miss cache (cold start)

**Daily breakdown:**
- 30 messages/day
- 12 cache writes @ $0.183 = $2.20
- 18 cache reads @ $0.032 = $0.58
- **Total: $2.78/day**

**Monthly:**
- $2.78 × 30 = **$83/month**

## Cache Hit Rate is EVERYTHING

| Cache Hit Rate | Cost/Day | Cost/Month | Savings vs No Cache |
|----------------|----------|------------|---------------------|
| 0% (no bursts) | $5.49 | $165 | vs $459 (64% off) |
| 30% (some bursts) | $4.20 | $126 | vs $459 (73% off) |
| 60% (realistic) | $2.78 | $83 | vs $459 (82% off) |
| 80% (very bursty) | $1.86 | $56 | vs $459 (88% off) |

## What Affects Cache Hit Rate?

**Increases cache hits:**
- ✅ Active conversation hours (people chatting back and forth)
- ✅ Commands clustered together (!hello, !seeds, !garden in quick succession)
- ✅ Multi-user simultaneous activity
- ✅ DM conversations (natural back-and-forth)

**Decreases cache hits:**
- ❌ Quiet periods between messages
- ❌ Single user, long pauses between thoughts
- ❌ Night/day boundary (nobody active for hours)
- ❌ Infrequent channel activity

## Your Actual Costs: Prediction

Based on "12-50 messages/day, can get bursty":

**Conservative estimate (30% cache hit rate):**
- **$126/month**

**Realistic estimate (60% cache hit rate):**
- **$83/month**

**Optimistic estimate (80% cache hit rate during active periods):**
- **$56/month**

**My best guess for Garden Cafe: $70-90/month**

## Additional Optimizations Available

### Option A: Haiku Routing (Not Implemented Yet)

Use Haiku for simple commands, Sonnet for deep conversations.

**Haiku costs @ 56k tokens:**
- Cache write: $0.045
- Cache read: $0.0045
- Response (1k tokens): $0.004

**If 60% of messages use Haiku:**
- 18 Haiku msgs/day: Mix of $0.045 and $0.0045 ≈ $0.30/day
- 12 Sonnet msgs/day: Mix of $0.183 and $0.032 ≈ $1.50/day
- **Total: $1.80/day = $54/month**

**Additional savings: ~$30/month**

### Option B: Multi-Layer Caching (Not Implemented Yet)

Split system prompt into layers that cache separately:
- Layer 1: Invocation + context (5k tokens - rarely changes)
- Layer 2: Perspectives (52k tokens - changes with updates)
- Layer 3: Closing (1k tokens - rarely changes)

**Benefit during active conversations:**
When multiple channels active simultaneously, Layer 1 & 3 stay cached across ALL conversations, only Layer 2 varies.

**Realistic impact:** 10-20% additional savings during bursts
**Monthly savings:** ~$8-15

**Complexity:** High (more failure modes, harder to debug)

### Option C: Longer Context Reuse

Currently each message rebuilds conversation context. Could maintain conversation state:

**Not recommended** - adds complexity, marginal savings

## What We Built Today vs What We Designed

### Built & Active:
✅ Core 44 perspectives (56k tokens)
✅ Prompt caching on all API calls
✅ Update script for perspectives

### Designed But NOT Implemented:
❌ Multi-layer caching
❌ Haiku routing
❌ Dynamic context layers

## Recommendations

### Deploy Now (What's Built):
Current implementation gets you:
- **67% reduction in base cost** (170k → 56k tokens)
- **60-80% cache hit rate likely** for your traffic
- **Estimated $70-90/month** (down from $459)
- **Simple, maintainable, working**

### Consider Later (If You Want More Savings):
1. **Haiku routing** (~$54/month total)
   - Moderate complexity
   - Good voice quality for simple commands
   - Additional $20-35/month savings

2. **Multi-layer caching** (~$60/month total)
   - High complexity
   - Marginal benefit for your traffic
   - Additional $10-20/month savings

3. **Both** (~$40/month total)
   - Maximum optimization
   - Maximum complexity
   - Diminishing returns on effort

## Bottom Line

**What you have RIGHT NOW:**
- System prompt: 56k tokens (was 170k)
- Caching: Enabled (5-min TTL)
- Expected cost: **$70-90/month** (was $459)
- **Savings: ~80% without additional optimization**

**Is it worth implementing more optimizations?**

To save another $20-30/month:
- Haiku routing: 1-2 days work, moderate complexity
- Multi-layer: 2-3 days work, high complexity

**For a community Discord bot?** The 80% savings you have now is probably enough. Spend your time using the bot, not optimizing it.

## Actual Next Step

**Deploy what's built, monitor for 1 week, measure actual cache hit rate:**

```bash
# Add logging to track cache behavior
# In API responses, Anthropic returns usage stats:
{
  "usage": {
    "input_tokens": 56000,
    "cache_creation_input_tokens": 56000,  # First request
    "cache_read_input_tokens": 0,
    "output_tokens": 800
  }
}
```

After a week, you'll know:
- Actual cache hit rate
- Actual costs
- Whether further optimization is worth it

## Summary Table

| Scenario | Monthly Cost | Savings vs Original | Effort |
|----------|--------------|---------------------|--------|
| Original (no caching, 170k) | $459 | 0% | - |
| **Current (caching, 56k)** | **$70-90** | **~80%** | **Done!** |
| + Haiku routing | $54 | 88% | 1-2 days |
| + Multi-layer caching | $60 | 87% | 2-3 days |
| + Both optimizations | $40 | 91% | 3-4 days |

The diminishing returns are clear: You've captured 80% of savings with what's built. The last 11% would take as much work as the first 80%.
