---
name: context-export
description: This skill exports the current coding context as a comprehensive prompt for web LLMs. Use when user wants fresh perspectives from Claude.ai, ChatGPT, Gemini, or other web LLMs. Triggers on phrases like "describe situation", "export context", "fresh ideas", "get outside perspective", "prepare prompt for web LLM", "copy for ChatGPT/Claude/Gemini", "I'm stuck, need fresh eyes", or when user expresses frustration with current solutions.
---

# Context Export for Web LLMs

Generate a comprehensive, copy-paste-ready prompt that captures the current coding situation for web LLMs (Claude.ai, ChatGPT, Gemini) to provide fresh perspectives with web search capabilities.

## When to Use

- User is stuck and wants fresh ideas from another LLM
- Current solutions aren't satisfactory
- Need web-researched alternatives
- Want to validate approach with external perspective
- Complex architectural decisions need broader input

## Output Format

Generate a markdown code block containing a structured prompt. The user copies everything inside the code block.

```markdown
# Context Export - [Brief Title]

## Project Overview
[1-3 sentences: what the project is, tech stack, purpose]

## Current Situation
[What we're working on right now, what state the code is in]

## The Problem
[Clear statement of what we're trying to solve]

## What We've Tried / Considered
[List approaches attempted or discussed, with brief notes on why they didn't work or concerns]

## Relevant Code Context
[Key snippets, interfaces, or structures - keep minimal but sufficient]

## Constraints & Requirements
[Technical limitations, performance needs, compatibility requirements, preferences]

## What I Need
[Specific ask: alternative approaches? validation? specific technique research?]

---
*Please search the web for current best practices and provide fresh perspectives.*
```

## Extraction Process

1. **Scan project structure** - Identify tech stack, framework, key directories
2. **Review recent conversation** - Extract the problem being solved, options discussed
3. **Identify pain points** - What's not working? What's frustrating the user?
4. **Gather relevant code** - Only include code directly related to the problem (interfaces, error points, config)
5. **Infer constraints** - From discussion: performance, compatibility, style preferences
6. **Determine the ask** - What kind of help would be most valuable?

## Guidelines

### Be Concise But Complete
- Web LLMs have limited context. Aim for 500-1500 words total.
- Include enough context for an outsider to understand, but no more.
- Code snippets: 20-50 lines max, focused on the problem area.

### Highlight Uncertainty
- Clearly mark where the current approach is uncertain
- Note which "solutions" were rejected and why
- Express what tradeoffs are acceptable

### Make It Actionable
- End with a clear, specific request
- Suggest the web LLM search for specific topics if relevant
- Ask for alternatives, not just validation

### Preserve Key Details
- Error messages (exact text)
- Version numbers that matter
- Specific library/framework names

## Example Output

When user says "I'm stuck on this auth flow, can you prepare something I can ask ChatGPT?":

~~~markdown
```markdown
# Context Export - OAuth2 PKCE Implementation Issue

## Project Overview
Next.js 14 app with App Router, using NextAuth.js for authentication. Building a B2B SaaS dashboard that needs to integrate with customer Azure AD instances.

## Current Situation
Auth flow works for Google OAuth but failing silently for Azure AD with PKCE. No errors in console, just redirects back to login.

## The Problem
PKCE code_verifier validation failing on Azure AD token exchange. Suspect the verifier isn't being stored/retrieved correctly across the redirect, but NextAuth's session handling makes this opaque.

## What We've Tried
1. **Custom PKCE generation** - Implemented manual code_verifier/challenge, same result
2. **Session storage for verifier** - Stored in cookies, but unclear if NextAuth overwrites
3. **Azure AD specific config** - Added `allowDangerousEmailAccountLinking`, no change
4. **Debug logging** - Can't see the actual token exchange request NextAuth makes

## Relevant Code Context
```typescript
// Current provider config (next-auth)
AzureADProvider({
  clientId: process.env.AZURE_AD_CLIENT_ID!,
  clientSecret: process.env.AZURE_AD_CLIENT_SECRET!,
  tenantId: "common",
  authorization: { params: { scope: "openid profile email" } },
})
```

## Constraints
- Must use NextAuth.js (team decision, can't switch)
- Need to support multiple Azure AD tenants ("common" endpoint)
- Must work with PKCE (required by some enterprise clients)

## What I Need
Alternative approaches to debug or implement PKCE with NextAuth + Azure AD. Specifically:
- Is there a way to intercept/log the actual PKCE exchange?
- Are there known issues with NextAuth + Azure AD + PKCE?
- Should we consider a different authorization flow?

---
*Please search for recent NextAuth.js Azure AD PKCE issues and current best practices (2024).*
```
~~~

## Tone Calibration

Match the user's frustration level:
- **Mildly stuck**: Neutral, exploratory tone in the export
- **Very frustrated**: Emphasize what's been tried, make the "help needed" section more direct
- **Exploring options**: Frame as "seeking validation or alternatives"

## After Generating

1. Present the export in a code block for easy copying
2. Briefly note what was included and what was omitted
3. Suggest which web LLM might be best (Claude.ai for nuanced analysis, ChatGPT/Gemini for web search)
