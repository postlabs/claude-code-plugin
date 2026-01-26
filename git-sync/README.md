# git-sync

Git commit protocol for multi-session collaboration with structured commit messages.

## Features

- Standardized commit message format with scope and AFFECTS tags
- Protocol for checking recent changes from other sessions
- Consistent workflow for staging, committing, and pushing

## Installation

Add to your project's `.claude/plugins.json`:

```json
{
  "plugins": ["path/to/git-sync"]
}
```

Or use as a global plugin.

## Commands

| Command | Description |
|---------|-------------|
| `/git-sync:sync` | Check recent changes from other sessions |
| `/git-sync:commit` | Create a structured commit following the protocol |

## Usage

The skill automatically activates when:
- Committing changes
- Starting a new session
- After pulling changes

### Commit Format

```
[scope] short summary

- specific change 1
- specific change 2

AFFECTS: frontend|backend|both|none
```

### Scopes

- `feat` - New feature
- `fix` - Bug fix
- `refactor` - Code refactoring
- `api` - API changes
- `schema` - Database/schema changes
- `config` - Configuration changes
