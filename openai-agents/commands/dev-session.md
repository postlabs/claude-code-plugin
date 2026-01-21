---
description: Configure sessions for conversation persistence
argument-hint: [request]
allowed-tools: Read, Write, Edit, Grep, Glob
---

Configure sessions for agent memory: $ARGUMENTS

## Session Types

### SQLiteSession (Local/Development)

```python
from agents import Runner
from agents.extensions.session import SQLiteSession

# In-memory (volatile)
session = SQLiteSession(session_id="user_123")

# File-based (persistent)
session = SQLiteSession(
    session_id="user_123",
    db_path="conversations.db",
)

result = await Runner.run(agent, "Hello", session=session)
result = await Runner.run(agent, "What did I say?", session=session)
```

### OpenAIConversationsSession (Cloud)

```python
from agents.extensions.session import OpenAIConversationsSession

# New conversation
session = OpenAIConversationsSession()

# Resume existing
session = OpenAIConversationsSession(conversation_id="conv_123")
```

### SQLAlchemySession (Production)

```python
from agents.extensions.sqlalchemy_session import SQLAlchemySession

session = await SQLAlchemySession.from_url(
    session_id="user_123",
    url="postgresql+asyncpg://user:pass@host/db",
    create_tables=True,
)
```

### EncryptedSession (Secure)

```python
from agents.extensions.encrypted_session import EncryptedSession

base = SQLiteSession(session_id="user_123", db_path="conv.db")

session = EncryptedSession(
    session_id="user_123",
    underlying_session=base,
    encryption_key="32-byte-key-here",
    ttl=3600,  # 1 hour expiration
)
```

### CompactionSession (Long Conversations)

```python
from agents.extensions.session import OpenAIResponsesCompactionSession

session = OpenAIResponsesCompactionSession(
    underlying_session=SQLiteSession("user_123"),
    compaction_threshold=50,  # Compact after 50 messages
)

# Manual compaction
await session.run_compaction({"force": True})
```

## Session Operations

```python
# Get history
items = await session.get_items()

# Add items
await session.add_items([new_item])

# Undo last
await session.pop_item()

# Clear all
await session.clear_session()
```

## Session Type Comparison

| Type | Storage | Use Case |
|------|---------|----------|
| SQLiteSession | Local file | Development |
| OpenAIConversationsSession | OpenAI cloud | Production w/ OpenAI |
| SQLAlchemySession | Any SQL DB | Scalable production |
| EncryptedSession | Encrypted | Sensitive data |
| CompactionSession | Auto-compact | Long conversations |

## Best Practices

1. **Unique IDs**: Use consistent session_id per user
2. **Choose Right Type**: Match to deployment needs
3. **Encrypt Sensitive**: Use EncryptedSession for PII
4. **Compact Long Chats**: Enable compaction for long conversations
5. **Handle Cleanup**: Clear old sessions periodically

## Implementation

Configure the session as requested.
Choose appropriate session type for the use case.
