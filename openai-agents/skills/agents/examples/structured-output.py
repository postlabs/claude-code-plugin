"""
Structured Output Example - OpenAI Agents SDK

Demonstrates typed agent responses using Pydantic models.
"""

from pydantic import BaseModel, Field
from agents import Agent, Runner


class TaskExtraction(BaseModel):
    """Extracted task information from user input."""
    title: str = Field(description="Brief task title")
    priority: str = Field(description="Priority: high, medium, or low")
    due_date: str | None = Field(description="Due date if mentioned")
    tags: list[str] = Field(description="Relevant tags for categorization")


class SentimentAnalysis(BaseModel):
    """Sentiment analysis result."""
    sentiment: str = Field(description="positive, negative, or neutral")
    confidence: float = Field(description="Confidence score 0-1")
    key_phrases: list[str] = Field(description="Key phrases affecting sentiment")


# Task extraction agent
task_agent = Agent(
    name="TaskExtractor",
    instructions="Extract task information from user input. Be precise with priorities and dates.",
    output_type=TaskExtraction,
)

# Sentiment analysis agent
sentiment_agent = Agent(
    name="SentimentAnalyzer",
    instructions="Analyze the sentiment of the given text.",
    output_type=SentimentAnalysis,
)


def main():
    # Extract task
    result = Runner.run_sync(
        task_agent,
        "I need to finish the quarterly report by Friday, it's really urgent!"
    )
    task: TaskExtraction = result.final_output
    print(f"Task: {task.title}")
    print(f"Priority: {task.priority}")
    print(f"Due: {task.due_date}")
    print(f"Tags: {task.tags}")

    print("\n---\n")

    # Analyze sentiment
    result = Runner.run_sync(
        sentiment_agent,
        "The new product launch was amazing! Customer feedback has been overwhelmingly positive."
    )
    sentiment: SentimentAnalysis = result.final_output
    print(f"Sentiment: {sentiment.sentiment}")
    print(f"Confidence: {sentiment.confidence:.2%}")
    print(f"Key phrases: {sentiment.key_phrases}")


if __name__ == "__main__":
    main()
