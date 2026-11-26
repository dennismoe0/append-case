# Car Dealer MCP Server

An [MCP](https://modelcontextprotocol.io) server that gives a car dealer's AI assistant access to the stock list (398 cars from the [Automobile dataset](https://www.kaggle.com/datasets/tawfikelmetwally/automobile-dataset)). The assistant looks facts up through tools instead of guessing, and can pull out the selling points of a specific car.

Built with Python, the official MCP SDK and pandas.

## Tools

| Tool | Arguments | Returns |
|---|---|---|
| `most_fuel_efficient` | `limit` (1-50, default 5) | The cars that use the least fuel |
| `most_horsepower` | `limit` (1-50, default 5) | The most powerful cars |
| `origin_statistics` | none | Count, share and averages per origin (usa, japan, europe) |
| `search_cars` | `origin`, `min_mpg`, `min_horsepower`, `limit` (all optional) | Cars matching the filters, most fuel efficient first |
| `car_highlights` | `name` | Where one car beats the rest of the stock, as ready-made selling points |

Every car also gets `liters_per_100km`, since `mpg` is the American unit.

## Run

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python server.py
```

The server listens on `http://localhost:8000/mcp`.

## Call it by hand

No AI involved: this is the full loop an MCP client runs, done with `curl`. Responses are piped through [jq](https://jqlang.org) for readability.

**1. Connect.** The handshake returns a session id that every later request must carry.

```bash
URL=http://localhost:8000/mcp
H=(-H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream')

SID=$(curl -s -D - -o /dev/null -X POST $URL "${H[@]}" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"1.0"}}}' \
  | grep -i '^mcp-session-id' | cut -d' ' -f2 | tr -d '\r')

curl -s -X POST $URL "${H[@]}" -H "Mcp-Session-Id: $SID" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'
```

**2. Add a helper** so the remaining calls stay short. It sends one JSON-RPC message and prints the JSON reply.

```bash
call() { curl -s -X POST $URL "${H[@]}" -H "Mcp-Session-Id: $SID" -d "$1" | sed -n 's/^data: //p'; }
```

**3. Ask which tools exist.**

```bash
call '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | jq -r '.result.tools[].name'
```

```
most_fuel_efficient
most_horsepower
origin_statistics
search_cars
car_highlights
```

**4. Call a tool.**

```bash
call '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"most_fuel_efficient","arguments":{"limit":3}}}' \
  | jq -c '.result.structuredContent.result[] | {name, mpg, liters_per_100km, origin}'
```

```json
{"name":"mazda glc","mpg":46.6,"liters_per_100km":5.0,"origin":"japan"}
{"name":"honda civic 1500 gl","mpg":44.6,"liters_per_100km":5.3,"origin":"japan"}
{"name":"vw rabbit c (diesel)","mpg":44.3,"liters_per_100km":5.3,"origin":"europe"}
```

**5. Get the selling points for one car.**

```bash
call '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"car_highlights","arguments":{"name":"mazda glc"}}}' \
  | jq '.result.structuredContent | {beats_percent, highlights}'
```

```json
{
  "beats_percent": {
    "mpg": 100,
    "horsepower": 7,
    "acceleration": 19,
    "weight": 84
  },
  "highlights": [
    "Uses less fuel than 100% of the cars in stock",
    "Is lighter than 84% of the cars in stock"
  ]
}
```

**6. Send invalid input.** The limit is part of the tool's schema, so the server rejects it before any of our code runs.

```bash
call '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"most_fuel_efficient","arguments":{"limit":0}}}' \
  | jq '.result.isError'
```

```
true
```

## How it works

- The CSV is loaded into a pandas DataFrame once, at startup.
- Each tool is a plain Python function with `@mcp.tool()` on top.
- Type hints become the tool's input schema, and the docstring is the description the model reads when it picks a tool.
- Missing values (6 cars have no horsepower) are returned as `null`.

## Tests

```bash
uv run pytest
```

## Structure

```
server.py              the MCP server and its tools
data/Automobile.csv    the dataset
tests/test_server.py   known-answer tests for each tool
pyproject.toml         dependencies (locked in uv.lock)
```
