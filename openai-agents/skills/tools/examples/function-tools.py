"""
Function Tools Examples - OpenAI Agents SDK

Demonstrates various function tool patterns.
"""

from dataclasses import dataclass
from typing import Any
from agents import Agent, Runner, function_tool, RunContextWrapper


# Basic function tool
@function_tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression.

    Args:
        expression: A mathematical expression to evaluate (e.g., "2 + 2")

    Returns:
        The result of the calculation
    """
    try:
        result = eval(expression)  # In production, use a safe parser
        return f"Result: {result}"
    except Exception as e:
        return f"Error: {e}"


# Async function tool
@function_tool
async def fetch_data(url: str) -> str:
    """Fetch data from a URL.

    Args:
        url: The URL to fetch data from

    Returns:
        The fetched data or error message
    """
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()


# Context-aware function tool
@dataclass
class AppContext:
    user_id: str
    database: Any


@function_tool
async def get_user_orders(ctx: RunContextWrapper[AppContext]) -> str:
    """Get orders for the current user.

    Returns:
        List of user's recent orders
    """
    user_id = ctx.context.user_id
    db = ctx.context.database
    orders = await db.fetch_orders(user_id)
    return f"Found {len(orders)} orders: {orders}"


# Tool with custom name
@function_tool(name_override="search_products")
def find_products(query: str, category: str = "all") -> str:
    """Search for products in the catalog.

    Args:
        query: Search query
        category: Product category filter

    Returns:
        Matching products
    """
    return f"Found products matching '{query}' in {category}"


# Tool with multiple return types
from agents import ToolOutputText, ToolOutputImage


@function_tool
def generate_chart(data: str, chart_type: str = "bar") -> list:
    """Generate a chart from data.

    Args:
        data: JSON data for the chart
        chart_type: Type of chart (bar, line, pie)

    Returns:
        Description and chart image
    """
    # In reality, generate chart using matplotlib/plotly
    chart_image_base64 = "..."  # Base64 encoded image
    return [
        ToolOutputText(text=f"Generated {chart_type} chart from data"),
        ToolOutputImage(image_data=chart_image_base64, media_type="image/png"),
    ]


# Agent with multiple tools
agent = Agent(
    name="MultiToolAgent",
    instructions="Help users with calculations and data retrieval",
    tools=[calculate, find_products],
)


def main():
    result = Runner.run_sync(agent, "What is 25 * 4?")
    print(result.final_output)

    result = Runner.run_sync(agent, "Search for laptops in electronics")
    print(result.final_output)


if __name__ == "__main__":
    main()
