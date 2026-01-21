"""
Basic Agent Example - OpenAI Agents SDK

Demonstrates simple agent creation and execution.
"""

from agents import Agent, Runner


# Basic agent with static instructions
agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant. Be concise and friendly.",
    model="gpt-4.1",
)


def main():
    # Synchronous execution
    result = Runner.run_sync(agent, "What is the capital of France?")
    print(f"Response: {result.final_output}")


async def main_async():
    # Asynchronous execution
    result = await Runner.run(agent, "What is the capital of France?")
    print(f"Response: {result.final_output}")


if __name__ == "__main__":
    main()
