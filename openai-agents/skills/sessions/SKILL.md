---
name: OpenAI Agents SDK - Sessions
description: This skill should be used when the user asks to "add session", "persist conversation", "save chat history", "configure memory", "use SQLite session", "use encrypted session", "manage conversation state", or needs guidance on session types, session operations, or conversation persistence in OpenAI Agents SDK.
version: 1.0.0
---

# OpenAI Agents SDK - Sessions

## Overview

Sessions persist conversation history across agent interactions. They enable multi-turn conversations, state management, and conversation branching.

> **Latest Documentation**: Query Context7 MCP with Library ID `/openai/openai-agents-python` for up-to-date API references.

## Session Types

| Type | Storage | Use Case |
|------|---------|----------|
| `SQLiteSession` | Local file/memory | Development, simple apps |
| `OpenAIConversationsSession` | OpenAI cloud | Production with OpenAI |
| `SQLAlchemySession` | Any SQL database | Production, scalable |
| `AdvancedSQLiteSession` | SQLite with branches | Branching conversations |
| `EncryptedSession` | Encrypted storage | Sensitive data |
| `CompactionSession` | Auto-compacting | Long conversations |

## SQLiteSession

```python
from agents import Agent, Runner
from agents.extensions.session import SQLiteSession

# In-memory (volatile)
session = SQLiteSession(session_id="user_123")

# File-based (persistent)
session = SQLiteSession(
    session_id="user_123",
    db_path="conversations.db",
)

# Use with agent
result = await Runner.run(agent, "Hello!", session=session)
result = await Runner.run(agent, "Remember what I said?", session=session)
```

## OpenAIConversationsSession

```python
from agents.extensions.session import OpenAIConversationsSession

# New conversation
session = OpenAIConversationsSession()

# Resume existing conversation
session = OpenAIConversationsSession(conversation_id="conv_abc123")
```

## SQLAlchemySession (Production)

```python
from agents.extensions.sqlalchemy_session import SQLAlchemySession

# From URL
session = await SQLAlchemySession.from_url(
    session_id="user_123",
    url="postgresql+asyncpg://user:pass@localhost/db",
    create_tables=True,
)

# From engine
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine("postgresql+asyncpg://...")
session = SQLAlchemySession(
    session_id="user_123",
    engine=engine,
    create_tables=True,
)
```

## AdvancedSQLiteSession (Branching)

```python
from agents.extensions.advanced_sqlite_session import AdvancedSQLiteSession

session = AdvancedSQLiteSession(
    session_id="user_123",
    db_path="conversations.db",
)

# Create branch from specific turn
branch_session = await session.create_branch_from_turn(turn_number=2)

# Track usage
await session.store_run_usage(result)
```

## EncryptedSession

```python
from agents.extensions.encrypted_session import EncryptedSession

base_session = SQLiteSession(session_id="user_123", db_path="conv.db")

encrypted_session = EncryptedSession(
    session_id="user_123",
    underlying_session=base_session,
    encryption_key="your-32-byte-key-here",
    ttl=3600,  # 1 hour expiration
)
```

## CompactionSession

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
# Get conversation history
items = await session.get_items()

# Add items
await session.add_items([new_item])

# Remove last item (undo)
last_item = await session.pop_item()

# Clear entire session
await session.clear_session()
```

## Best Practices

1. **Choose Appropriate Storage**: SQLite for dev, SQL database for production
2. **Session IDs**: Use unique, consistent identifiers per user/conversation
3. **Encryption**: Encrypt sensitive conversations
4. **Compaction**: Enable for long-running conversations
5. **Branching**: Use for "what if" scenarios and rollback

## Additional Resources

For the latest API references and detailed documentation, query Context7 MCP with Library ID `/openai/openai-agents-python`.
