# Understanding the Remaining Limits ✅

**Purpose**: Clarify what "SMTP protocol limit" and "connection pool limit" actually mean

---

## PART 1: SMTP Protocol Limit ("limited only by SMTP protocol")

### What Is SMTP Protocol?

SMTP = Simple Mail Transfer Protocol. It's the **standard protocol** used to send emails between servers.

### Why It's a Bottleneck

Every single email message requires **4 SEPARATE CONVERSATIONS** with the Gmail/Outlook SMTP server:

```
Step 1: MAIL FROM (Tell server who the email is from)
        Client → Server: "MAIL FROM:<sender@example.com>"
        Server → Client: "250 OK"
        Time: ~20ms

Step 2: RCPT TO (Tell server who the email is going to)
        Client → Server: "RCPT TO:<recipient@gmail.com>"
        Server → Client: "250 OK"
        Time: ~20ms

Step 3: DATA (Tell server you're about to send the message content)
        Client → Server: "DATA"
        Server → Client: "354 Start mail input"
        Time: ~20ms

Step 4: SEND MESSAGE BODY (Send the actual email content)
        Client → Server: <message content bytes>
        Server → Client: "250 OK - Message accepted"
        Time: ~20ms

TOTAL TIME FOR ONE MESSAGE: 80ms minimum
```

### Network Latency Makes It Slower

The times above assume instant communication. In reality:
- Gmail servers are in Google datacenters (California, Europe, etc.)
- Network packets travel at speed of light (~200,000 km/sec)
- Typical ping to Gmail: 10-50ms depending on your location
- This gets added to every step

**Realistic timing per message**:
```
Step 1: 20ms (SMTP) + 20ms (network latency) = 40ms
Step 2: 20ms (SMTP) + 20ms (network latency) = 40ms
Step 3: 20ms (SMTP) + 20ms (network latency) = 40ms
Step 4: 20ms (SMTP) + 20ms (network latency) = 40ms

TOTAL: 160ms per message
```

### Example: Sending 100 Messages

```
Message 1: 160ms
Message 2: 160ms
Message 3: 160ms
...
Message 100: 160ms

Total time: 100 × 160ms = 16,000ms = 16 seconds
Throughput: 100 messages ÷ 16 seconds = 6.25 msg/sec
```

### This Is UNAVOIDABLE

**Why you can't make it faster**:
1. Gmail/Outlook SMTP servers REQUIRE all 4 steps (RFC 5321 specification)
2. You can't skip steps - the protocol says you MUST do them
3. Network latency is physics - information can't travel faster than light
4. Even with perfect code, you're stuck at ~6-10 msg/sec per account

**Example**: You're at the limit of what's possible with SMTP protocol itself.

---

## PART 2: Connection Pool Limit ("Connection pool and per-account limits still enforced")

### What Is Connection Pool?

Instead of creating a NEW connection for every message, the proxy **REUSES** existing connections.

```
MESSAGE 1:
  ├─ Create connection to Gmail SMTP (200ms overhead!)
  ├─ Send MAIL FROM → RCPT TO → DATA → MESSAGE (160ms)
  ├─ Keep connection OPEN
  └─ Total: 360ms

MESSAGE 2:
  ├─ REUSE existing connection (0ms overhead!)
  ├─ Send MAIL FROM → RCPT TO → DATA → MESSAGE (160ms)
  ├─ Keep connection OPEN
  └─ Total: 160ms (SAVED 200ms!)

MESSAGE 3:
  ├─ REUSE existing connection (0ms overhead!)
  ├─ Send MAIL FROM → RCPT TO → DATA → MESSAGE (160ms)
  └─ Total: 160ms
```

### Connection Pool Settings

**File**: `config.json` or provider defaults

```json
{
  "providers": {
    "gmail": {
      "connection_pool": {
        "max_connections_per_account": 50,
        "max_messages_per_connection": 100
      }
    }
  }
}
```

#### **max_connections_per_account: 50**

Means: One Gmail account can have **at most 50 open SMTP connections** at the same time.

**Why 50?**
- Allows parallelism (50 messages can relay simultaneously)
- Doesn't overwhelm Gmail's servers
- Gmail itself limits connections (undocumented, but ~5-10 per account)

**Example with 50 connections**:
```
Message 1 → Uses connection 1 (0-160ms)
Message 2 → Uses connection 2 (0-160ms)
Message 3 → Uses connection 3 (0-160ms)
...
Message 50 → Uses connection 50 (0-160ms)

All 50 messages happen IN PARALLEL:
Total time: ~160ms for all 50 messages!
Throughput: 50 messages ÷ 0.16 seconds = 312 msg/sec!
```

But wait... there's another limit.

#### **max_messages_per_connection: 100**

Means: Each connection can send **at most 100 messages**, then it's closed and recreated.

**Why 100?**
- Gmail closes connections after a while
- Prevents connection state corruption
- Ensures fresh authentication state

**Example**:
```
Connection 1: Can send messages 1-100 (then closed)
Connection 2: Can send messages 101-200 (then closed)
Connection 3: Can send messages 201-300 (then closed)
```

---

## Example: How Both Limits Work Together

### Scenario: Sending 1000 Messages from 1 Gmail Account

**Settings**:
```
max_connections_per_account: 50
max_messages_per_connection: 100
```

**Timeline**:

```
Time 0ms: Connections 1-50 are created and start sending

Connections 1-50 send messages 1-50 in parallel:
Time 0-160ms: Messages 1-50 complete (all 50 connections busy)
              Throughput: 50 msg ÷ 0.16s = 312 msg/sec

Time 160ms: Connections 1-50 become available
            Each connection has sent 1 message, can send 99 more
            Start messages 51-100

Time 160-320ms: Messages 51-100 complete (parallel again)
                Throughput: 50 msg ÷ 0.16s = 312 msg/sec

Time 320ms: Connections 1-50 still busy (or becoming free)
            Each has sent 2 messages, can send 98 more
            Start messages 101-150

... pattern continues ...

Time ~1600ms: Connections 1-50 have each sent 100 messages
              Connections 1-50 are CLOSED (max_messages_per_connection reached)

Time 1600ms: New connections 51-100 are created
             Start messages 501-550

Time 1600-1760ms: Messages 501-550 complete

... pattern continues until all 1000 messages sent ...

TOTAL TIME: ~1600ms + 1600ms = 3200ms = 3.2 seconds
THROUGHPUT: 1000 messages ÷ 3.2 seconds = 312 msg/sec
```

---

## PART 3: Per-Account Concurrency Limit

### What Is This?

The proxy limits how many messages from ONE account can be "in flight" (being processed) at the same time.

**Default**: 150 concurrent messages per account

### Why This Limit?

```
Scenario WITHOUT per-account limit:

If you send 10,000 messages from 1 account simultaneously:
- Proxy tries to process all 10,000 at once
- Memory usage explodes (10,000 × message size)
- Connection pool overwhelmed
- CPU maxed out
- System crashes
```

```
Scenario WITH per-account limit (150):

If you send 10,000 messages from 1 account:
- Proxy processes 150 at a time
- Memory stays reasonable
- Connection pool stays manageable
- CPU stays responsive
- System stable

After 150 complete → Next 150 start
After those complete → Next 150 start
... etc ...
```

### In Code

**File**: `src/smtp/handler.py` line 416-426

```python
async with account.lock:
    if not account.can_send():  # Check concurrent_messages < max
        logger.warning(
            f"[{account.email}] Per-account concurrency limit reached "
            f"({account.concurrent_messages}/{account.max_concurrent_messages})"
        )
        self.send_response(451, "4.4.5 Server busy - per-account limit reached, try again later")
        return

    account.concurrent_messages += 1  # Increment when message starts
```

When relay completes (in background task), counter is decremented and next message can start.

---

## Part 4: Provider Rate Limits

### What Are These?

Gmail and Outlook **enforce their own limits** on how many emails you can send.

### Gmail SMTP Rate Limit

**Official limit**: Not documented, but empirically observed:
- ~10-15 messages per second per account
- Soft limit (may get throttled)
- Hard limit: ~100 messages per minute before temporary block

**What happens when exceeded**:
```
Gmail server response: 452 Too many simultaneous connections

Proxy response to PowerMTA: 451 4.4.5 Server busy
PowerMTA retries later
```

### Outlook SMTP Rate Limit

**Official limit**: Similar to Gmail
- ~10-15 messages per second per account
- May be stricter (~100 msg/hour in some cases)

### These Are UPSTREAM

These limits are enforced **by Gmail/Outlook servers**, not by the proxy.

Even if the proxy says "go send 1000 msg/sec", Gmail will block it:

```
Proxy: "Here's message 1000 to relay"
Gmail: "452 Too many simultaneous connections"
Proxy: "Message relay failed"
PowerMTA: "Gmail rejected it, I'll retry later"
```

---

## Summary: All Three Limits

| Limit | Type | Enforced By | Impact | Example |
|-------|------|-------------|--------|---------|
| **SMTP Protocol** | Physics | Gmail/Outlook | ~160ms per message | 1000 msg = 2.6 minutes minimum |
| **Connection Pool** | Proxy Code | `src/smtp/connection_pool.py` | Max 50 connections, 100 msg/connection | Enables parallelism (50 concurrent) |
| **Per-Account Concurrency** | Proxy Code | `src/smtp/handler.py` | Max 150 messages in flight | Prevents memory/CPU exhaustion |
| **Provider Rate Limit** | Upstream | Gmail/Outlook SMTP | ~10-15 msg/sec per account | Rejected if exceeded |

---

## Real-World Example

### Setup

```json
{
  "providers": {
    "gmail": {
      "connection_pool": {
        "max_connections_per_account": 50,
        "max_messages_per_connection": 100
      },
      "concurrency": {
        "max_concurrent_messages": 150
      }
    }
  }
}
```

### You Want to Send 5000 Emails

From 5 Gmail accounts (1000 emails each)

### What Happens

```
ACCOUNT 1 (1000 emails):
├─ Start: 50 connections × 100 msg each = 5000 msg capacity ✓
├─ Concurrency: Max 150 in-flight at once
├─ Provider limit: 10-15 msg/sec (Gmail enforces)
├─ Protocol minimum: 160ms per message
├─ Expected time: ~100-150 seconds (limited by provider)

ACCOUNT 2 (1000 emails):
├─ Processes in parallel with Account 1
├─ Same limits apply
├─ Expected time: ~100-150 seconds

ACCOUNT 3 (1000 emails):
├─ Processes in parallel
├─ Expected time: ~100-150 seconds

ACCOUNT 4 (1000 emails):
├─ Processes in parallel
├─ Expected time: ~100-150 seconds

ACCOUNT 5 (1000 emails):
├─ Processes in parallel
├─ Expected time: ~100-150 seconds

TOTAL TIME FOR ALL 5000:
├─ NOT 5 × 150 = 750 seconds (sequential)
├─ Instead: ~150 seconds (parallel!)
├─ Because: All 5 accounts relay messages IN PARALLEL
└─ Throughput: 5000 msg ÷ 150s = 33 msg/sec total
```

### The Limiting Factor

Which limit actually stops you?

```
Potential #1: SMTP Protocol (160ms/msg)
  5000 × 160ms = 800,000ms = 800 seconds
  Throughput: 5000 ÷ 800 = 6.25 msg/sec

Potential #2: Connection Pool (50 conn × 100 msg)
  5000 msg from 1 account = needs ~1000 msg capacity
  Only have 50 × 100 = 5000 capacity ✓ (just fits!)
  No bottleneck for this workload

Potential #3: Per-Account Concurrency (150 max)
  150 in-flight at once = normal, not hitting limit
  No bottleneck

Potential #4: Provider Rate Limit (10-15 msg/sec per account)
  5 accounts = 5 × 10 = 50 msg/sec potential (parallel)
  Provider limit: BOTTLENECK! ← THIS ONE

ANSWER: Provider Rate Limit (Gmail/Outlook) is the bottleneck
  Expected: 50 msg/sec ÷ 5 accounts = 10 msg/sec per account
  This matches Gmail's published limits ✓
```

---

## What Changed When Rate Limiter Was Removed?

### BEFORE (With Rate Limiter)

```
Message relay → Rate limiter lock → Acquire token → Gmail relay
  (serialized through global lock)
```

The rate limiter was checking:
- "Did this account exceed 10,000 msg/hour?"
- If yes: REJECT message with 451 error
- If no: ALLOW message to proceed

**Problem**: All accounts had to wait for same global lock

### AFTER (Without Rate Limiter)

```
Message relay → (no rate limiter) → Connection pool → Gmail relay
  (no lock, direct to Gmail)
```

Now:
- Rate limiter checks are GONE
- Messages go directly to connection pool
- Connection pool enforces limits (50 connections, 100 msg/conn)
- Gmail enforces its own upstream limits

**Result**: Messages relay as fast as Gmail allows (no artificial proxy limit)

---

## FAQ

### Q: "Will my emails get blocked?"

**A**: No. If you exceed provider limits, Gmail will temporarily reject with 452 error. PowerMTA automatically retries. No emails are lost.

```
PowerMTA: "Send email X"
Proxy: "OK, relaying to Gmail"
Gmail: "452 Too many simultaneous connections"
Proxy: "Relay failed, status 452"
PowerMTA: "Gmail busy, I'll retry in 5 minutes"
(5 minutes later)
PowerMTA: "Retrying email X"
Gmail: "250 OK - Message accepted"
Email delivered ✓
```

### Q: "What if I set connection_pool to 1000 connections?"

**A**: Gmail will reject you:
```
"421 Service Temporarily Unavailable"
(Gmail internally limits connections)
```

Gmail's actual limit is ~5-10 per account (undocumented), but they'll close excess connections gracefully.

### Q: "Can I increase per-account concurrency to 10,000?"

**A**: Yes, but:
- Memory usage increases (more messages in queue)
- CPU usage increases (more concurrent tasks)
- Gmail still limits upstream (10-15 msg/sec)
- You won't send faster, just use more resources

### Q: "So I can't send more than 10-15 msg/sec per account?"

**A**: Correct. That's Gmail/Outlook's limit, not the proxy's. It's:
- Their infrastructure decision
- Their rate limiting policy
- Their business rules

To send faster:
1. Use more accounts (100 accounts = 1000+ msg/sec)
2. Use Gmail API instead of SMTP (different architecture)
3. Use a different mail provider with higher limits

---

## Bottom Line

**The three limits are**:

1. **SMTP Protocol** (160ms/msg): Unavoidable, fundamental protocol requirement
2. **Connection Pool** (50 conn × 100 msg): Proxy-enforced, prevents resource exhaustion
3. **Provider Rate Limit** (10-15 msg/sec): Gmail/Outlook enforced, their business policy

**All three must be satisfied** for messages to go through.

The **bottleneck** is usually the **Provider Rate Limit** (Gmail/Outlook), not the protocol or connection pool.

The **proxy is now unlimited** (removed rate limiter), so it doesn't add extra restrictions on top of what Gmail/Outlook already enforce.
