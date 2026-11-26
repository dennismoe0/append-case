# Car Dealer MCP Server

An [MCP](https://modelcontextprotocol.io) server that gives a car dealer's AI assistant access to the stock list (398 cars from the [Automobile dataset](https://www.kaggle.com/datasets/tawfikelmetwally/automobile-dataset)). The assistant looks facts up through tools instead of guessing, and can pull out the selling points of a specific car.

Built with Python, the official MCP SDK and pandas.

## Tools

| Tool | Arguments | Returns |
|---|---|---|
| `most_fuel_efficient` | `limit` (1-50, default 5) | The cars that use the least fuel |
| `most_horsepower` | `limit` (1-50, default 5) | The most powerful cars |
| `fastest_acceleration` | `limit` (1-50, default 5) | The quickest cars from 0 to 60 mph |
| `origin_statistics` | none | Count, share and averages per origin (usa, japan, europe) |
| `search_cars` | `origin`, `min_mpg`, `min_horsepower`, `limit` (all optional) | Cars matching the filters, most fuel efficient first |
| `car_highlights` | `name` | Where one car beats the rest of the stock, as ready-made selling points |
| `compare_cars` | `name_a`, `name_b` | Two cars side by side, and where each one is better |

Every car also gets `liters_per_100km`, since `mpg` is the American unit.

## Run

```bash
docker compose up
```

The server listens on `http://localhost:8000/mcp`.

## Use it

### Demo client

`client.py` is a small MCP client without an AI. It lists the tools, calls each one once and prints every call with its result. Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python client.py
```

```
Connecting to http://localhost:8000/mcp

tools/list
  most_fuel_efficient: Return the cars that use the least fuel (highest miles per gallon).
  most_horsepower: Return the most powerful cars (highest horsepower).
  ...

tools/call most_fuel_efficient {"limit": 3}
{
  "result": [
    {
      "name": "mazda glc",
      "mpg": 46.6,
      ...
```

### Claude Code

`.mcp.json` registers the server, so Claude Code picks it up when you open this folder and approve `car-dealer`. Ask in plain language, for example "Which three cars use the least fuel?", and the model chooses the tool itself.

### By hand with curl

The full loop an MCP client runs, without an SDK. Replies are piped through [jq](https://jqlang.org) for readability.

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

**2. Add two helpers.** `call` sends one JSON-RPC message and prints the reply. `tool` wraps a tool name and its arguments in a `tools/call` message.

```bash
call() { curl -s -X POST $URL "${H[@]}" -H "Mcp-Session-Id: $SID" -d "$1" | sed -n 's/^data: //p'; }
tool() { call "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{\"name\":\"$1\",\"arguments\":$2}}"; }
```

**3. Ask which tools exist.**

```bash
call '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | jq -r '.result.tools[].name'
```

```
most_fuel_efficient
most_horsepower
fastest_acceleration
origin_statistics
search_cars
car_highlights
compare_cars
```

**4. Call the tools.** The examples below pick a few fields with jq to keep the output short. Drop the filter to see the whole reply.

## Tool examples

### `most_fuel_efficient`

```bash
tool most_fuel_efficient '{"limit":3}' | jq -c '.result.structuredContent.result[] | {name, mpg, liters_per_100km, origin}'
```

```json
{"name":"mazda glc","mpg":46.6,"liters_per_100km":5.0,"origin":"japan"}
{"name":"honda civic 1500 gl","mpg":44.6,"liters_per_100km":5.3,"origin":"japan"}
{"name":"vw rabbit c (diesel)","mpg":44.3,"liters_per_100km":5.3,"origin":"europe"}
```

### `most_horsepower`

```bash
tool most_horsepower '{"limit":3}' | jq -c '.result.structuredContent.result[] | {name, horsepower, model_year, origin}'
```

```json
{"name":"pontiac grand prix","horsepower":230.0,"model_year":73,"origin":"usa"}
{"name":"pontiac catalina","horsepower":225.0,"model_year":70,"origin":"usa"}
{"name":"buick estate wagon (sw)","horsepower":225.0,"model_year":70,"origin":"usa"}
```

### `fastest_acceleration`

```bash
tool fastest_acceleration '{"limit":3}' | jq -c '.result.structuredContent.result[] | {name, acceleration, horsepower, origin}'
```

```json
{"name":"plymouth 'cuda 340","acceleration":8.0,"horsepower":160.0,"origin":"usa"}
{"name":"plymouth fury iii","acceleration":8.5,"horsepower":215.0,"origin":"usa"}
{"name":"amc ambassador dpl","acceleration":8.5,"horsepower":190.0,"origin":"usa"}
```

### `origin_statistics`

```bash
tool origin_statistics '{}' | jq -c '.result.structuredContent.result[]'
```

```json
{"origin":"usa","cars":249,"share_percent":62.6,"avg_mpg":20.1,"avg_liters_per_100km":12.9,"avg_horsepower":119.0,"avg_weight":3361.9}
{"origin":"japan","cars":79,"share_percent":19.8,"avg_mpg":30.5,"avg_liters_per_100km":8.1,"avg_horsepower":79.8,"avg_weight":2221.2}
{"origin":"europe","cars":70,"share_percent":17.6,"avg_mpg":27.9,"avg_liters_per_100km":8.9,"avg_horsepower":80.6,"avg_weight":2423.3}
```

### `search_cars`

```bash
tool search_cars '{"origin":"europe","min_horsepower":100,"limit":3}' | jq -c '.result.structuredContent.result[] | {name, mpg, horsepower, model_year}'
```

```json
{"name":"bmw 2002","mpg":26.0,"horsepower":113.0,"model_year":70}
{"name":"saab 99le","mpg":25.0,"horsepower":115.0,"model_year":75}
{"name":"saab 99le","mpg":24.0,"horsepower":110.0,"model_year":73}
```

### `car_highlights`

```bash
tool car_highlights '{"name":"mazda glc"}' | jq -c '.result.structuredContent | {beats_percent, highlights}'
```

```json
{"beats_percent":{"mpg":100,"horsepower":7,"acceleration":19,"weight":84},"highlights":["Uses less fuel than 100% of the cars in stock","Is lighter than 84% of the cars in stock"]}
```

### `compare_cars`

```bash
tool compare_cars '{"name_a":"mazda glc","name_b":"pontiac grand prix"}' | jq -c '.result.structuredContent.advantages'
```

```json
{"mazda glc":["Uses less fuel","Is lighter"],"pontiac grand prix":["Has more horsepower","Accelerates faster"]}
```

### Errors

Errors come back as a normal result with `isError: true` and a message the model can act on.

```bash
tool car_highlights '{"name":"tesla"}' | jq -r '.result.content[0].text'
```

```
Error executing tool car_highlights: No car matching 'tesla'. Use search_cars to find valid names.
```

The limit is part of the tool's schema, so an invalid value is rejected before any of our code runs:

```bash
tool most_fuel_efficient '{"limit":0}' | jq '.result.isError'
```

```
true
```

## How it works

- The CSV is loaded into a pandas DataFrame once, at startup.
- Each tool is a plain Python function with `@mcp.tool()` on top.
- Type hints become the tool's input schema, and the docstring is the description the model reads when it picks a tool.
- Missing values (6 cars have no horsepower) are returned as `null`.
- Every tool call writes one log line (`docker compose logs`).

## Development

Open the folder in VS Code and choose **Reopen in Container**. The [dev container](.devcontainer/devcontainer.json) installs Python, uv and the dependencies, and forwards port 8000.

```bash
uv run python server.py   # run the server without Docker
uv run pytest             # known-answer tests for every tool
uv run ruff check .       # lint
```

## Structure

```
server.py              the MCP server and its tools
client.py              demo client: lists the tools and calls each one
data/Automobile.csv    the dataset
tests/test_server.py   tests
Dockerfile             image for the server
compose.yaml           docker compose up
.mcp.json              registers the server in Claude Code
.devcontainer/         development container
pyproject.toml         dependencies (locked in uv.lock)
```
