"""A simple MCP client without an LLM: lists the server's tools and calls each one once."""

import asyncio
import json
import sys

import httpx2  # the HTTP library the MCP SDK uses
from mcp import Client

DEFAULT_URL = "http://localhost:8000/mcp"

EXAMPLE_CALLS = [
    ("most_fuel_efficient", {"limit": 3}),
    ("most_horsepower", {"limit": 3}),
    ("fastest_acceleration", {"limit": 3}),
    ("origin_statistics", {}),
    ("search_cars", {"origin": "europe", "min_horsepower": 100, "limit": 3}),
    ("car_highlights", {"name": "mazda glc"}),
    ("compare_cars", {"name_a": "mazda glc", "name_b": "pontiac grand prix"}),
    ("most_fuel_efficient", {"limit": 0}),  # invalid on purpose: limit must be >= 1
]


async def main(url: str) -> None:
    print(f"Connecting to {url}")
    async with Client(url) as client:
        print("\ntools/list")
        for tool in (await client.list_tools()).tools:
            first_sentence = (tool.description or "").split(". ")[0].rstrip(".")
            print(f"  {tool.name}: {first_sentence}.")

        for name, arguments in EXAMPLE_CALLS:
            print(f"\ntools/call {name} {json.dumps(arguments)}")
            result = await client.call_tool(name, arguments)
            if result.is_error:
                print(f"ERROR: {result.content[0].text}")
            else:
                print(json.dumps(result.structured_content, indent=2))


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    try:
        asyncio.run(main(url))
    except* httpx2.ConnectError:
        print(
            f"The MCP server is not reachable at {url}. "
            "Start it with: docker compose up",
            file=sys.stderr,
        )
        sys.exit(1)
