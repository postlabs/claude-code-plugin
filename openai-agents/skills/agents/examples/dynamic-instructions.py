"""
Dynamic Instructions Example - OpenAI Agents SDK

Demonstrates context-aware agent instructions using functions.
"""

from dataclasses import dataclass
from agents import Agent, Runner, RunContextWrapper


@dataclass
class UserContext:
    """Application context passed to agent."""
    user_id: str
    user_name: str
    subscription_tier: str
    preferred_language: str


def get_instructions(context: RunContextWrapper[UserContext], agent: Agent) -> str:
    """Generate personalized instructions based on context."""
    ctx = context.context

    base = f"You are helping {ctx.user_name}."

    if ctx.subscription_tier == "premium":
        base += " Provide detailed, comprehensive responses."
    else:
        base += " Be concise and helpful."

    if ctx.preferred_language != "en":
        base += f" Respond in {ctx.preferred_language} when appropriate."

    return base


# Agent with dynamic instructions
agent = Agent(
    name="PersonalAssistant",
    instructions=get_instructions,
)


def main():
    # Create context for premium user
    context = UserContext(
        user_id="user_123",
        user_name="Alice",
        subscription_tier="premium",
        preferred_language="en",
    )

    result = Runner.run_sync(
        agent,
        "Help me plan my day",
        context=context,
    )
    print(f"Response: {result.final_output}")


if __name__ == "__main__":
    main()
