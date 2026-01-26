---
name: export
description: Generate a copy-paste-ready prompt for web LLMs (Claude.ai, ChatGPT, Gemini)
allowed-tools:
  - Read
  - Glob
  - Grep
argument-hint: "[optional: specific problem or focus area]"
---

# Context Export - Generate Web LLM Prompt

Generate a comprehensive, copy-paste-ready prompt that captures the current coding situation.

## Steps

1. **Scan project structure** - Identify tech stack, framework, key directories
2. **Review conversation context** - Extract the problem, options discussed, pain points
3. **Gather relevant code** - Only include code directly related to the problem (20-50 lines max)
4. **Infer constraints** - Performance, compatibility, style preferences from discussion

## Output Format

Generate a markdown code block with this structure:

```markdown
# Context Export - [Brief Title]

## Project Overview
[1-3 sentences: tech stack, purpose]

## Current Situation
[What we're working on, code state]

## The Problem
[Clear problem statement]

## What We've Tried / Considered
[Approaches attempted with results]

## Relevant Code Context
[Key snippets - minimal but sufficient]

## Constraints & Requirements
[Technical limitations, preferences]

## What I Need
[Specific ask]

---
*Please search the web for current best practices and provide fresh perspectives.*
```

## Guidelines

- Keep total output 500-1500 words
- Code snippets: 20-50 lines max
- End with clear, specific request
- Match user's frustration level in tone

## After Generating

1. Present in code block for easy copying
2. Note what was included/omitted
3. Suggest best web LLM (Claude.ai for analysis, ChatGPT/Gemini for web search)
