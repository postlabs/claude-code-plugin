# /openai-agent:dev-session

Configure sessions and memory persistence.

## Usage

```
/openai-agent:dev-session [request]
```

## Session Types

### SQLiteSession (Local)
```python
from agents.extensions.session import SQLiteSession
session = SQLiteSession(db_path="conversations.db")
```

### OpenAIConversationsSession (Cloud)
```python
from agents.extensions.session import OpenAIConversationsSession
session = OpenAIConversationsSession()
```

### SQLAlchemySession (Production)
```python
from agents.extensions.session import SQLAlchemySession
session = SQLAlchemySession(connection_string="postgresql://...")
```

### EncryptedSession
```python
from agents.extensions.session import EncryptedSession
session = EncryptedSession(base_session=..., encryption_key=...)
```

## Operations

- get_items(): Get history
- add_items(): Store messages
- pop_item(): Undo last exchange
- clear_session(): Wipe data

## Examples

```
/openai-agent:dev-session add SQLite session
/openai-agent:dev-session configure encrypted cloud session
```
