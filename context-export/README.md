# context-export

Export current coding context as a comprehensive prompt for web LLMs like Claude.ai, ChatGPT, or Gemini.

## Features

- Generates copy-paste-ready prompts for web LLMs
- Captures project context, problem description, and constraints
- Includes code snippets and attempted solutions
- Suggests web search topics for fresh perspectives

## Installation

Add to your project's `.claude/plugins.json`:

```json
{
  "plugins": ["path/to/context-export"]
}
```

Or use as a global plugin.

## Commands

| Command | Description |
|---------|-------------|
| `/context-export:export` | Generate a copy-paste-ready prompt for web LLMs |

## Usage

The skill automatically activates when:
- User is stuck and wants fresh ideas
- Phrases like "export context", "fresh perspective", "copy for ChatGPT"
- User expresses frustration with current solutions

### Trigger Phrases

- "describe situation"
- "export context"
- "fresh ideas"
- "get outside perspective"
- "prepare prompt for web LLM"
- "copy for ChatGPT/Claude/Gemini"
- "I'm stuck, need fresh eyes"

### Output Format

A structured markdown prompt containing:
- Project Overview
- Current Situation
- The Problem
- What We've Tried
- Relevant Code Context
- Constraints & Requirements
- What I Need
