import json
import logging
from pathlib import Path
from typing import Annotated, Any, Literal

import pandas as pd
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("car-dealer")

DATA_FILE = Path(__file__).parent / "data" / "Automobile.csv"

cars = pd.read_csv(DATA_FILE)  # loaded once at startup
# mpg is the American unit; Norwegian customers think in litres per 100 km.
cars["liters_per_100km"] = (235.215 / cars["mpg"]).round(1)

mcp = MCPServer(
    "car-dealer",
    instructions=(
        "Car data for a car dealership. Use the tools to find cars and their "
        "selling points; a higher mpg means the car uses less fuel."
    ),
)

Limit = Annotated[int, Field(ge=1, le=50, description="How many cars to return")]

# column -> (phrase, higher_is_better)
HIGHLIGHT_METRICS = {
    "mpg": ("Uses less fuel", True),
    "horsepower": ("Has more horsepower", True),
    "acceleration": ("Accelerates faster", False),
    "weight": ("Is lighter", False),
}


def to_records(df: pd.DataFrame) -> list[dict]:
    """Convert rows to dicts via JSON, so missing values become null instead of NaN (NaN is not valid JSON)."""
    return json.loads(df.to_json(orient="records"))


def find_car(name: str) -> pd.DataFrame:
    """Find one car by name: exact match first, then partial match, newest model year wins."""
    query = name.strip().lower()
    matches = cars[cars["name"] == query]
    if matches.empty:
        matches = cars[cars["name"].str.contains(query, regex=False)]
    if matches.empty:
        log.warning("find_car name=%r -> no match", name)
        raise ToolError(
            f"No car matching '{name}'. Use search_cars to find valid names."
        )
    return matches.loc[[matches["model_year"].idxmax()]]  # newest model year


@mcp.tool()
def most_fuel_efficient(limit: Limit = 5) -> list[dict]:
    """Return the cars that use the least fuel (highest miles per gallon). Use this when the customer wants an economical car."""
    result = cars.nlargest(limit, "mpg")
    log.info("most_fuel_efficient limit=%s -> %d rows", limit, len(result))
    return to_records(result)


@mcp.tool()
def most_horsepower(limit: Limit = 5) -> list[dict]:
    """Return the most powerful cars (highest horsepower). Use this when the customer wants a strong or sporty car."""
    result = cars.dropna(subset=["horsepower"]).nlargest(limit, "horsepower")
    log.info("most_horsepower limit=%s -> %d rows", limit, len(result))
    return to_records(result)


@mcp.tool()
def fastest_acceleration(limit: Limit = 5) -> list[dict]:
    """Return the quickest cars. Acceleration is seconds from 0 to 60 mph, so lower is faster. Use this when the customer wants a quick or sporty car."""
    result = cars.nsmallest(limit, "acceleration")
    log.info("fastest_acceleration limit=%s -> %d rows", limit, len(result))
    return to_records(result)


@mcp.tool()
def origin_statistics() -> list[dict]:
    """Return one summary row per origin (usa, japan, europe): number of cars, share of stock and average mpg, fuel use, horsepower and weight. Use this to compare regions."""
    stats = (
        cars.groupby("origin")
        .agg(
            cars=("name", "count"),
            avg_mpg=("mpg", "mean"),
            avg_liters_per_100km=("liters_per_100km", "mean"),
            avg_horsepower=("horsepower", "mean"),
            avg_weight=("weight", "mean"),
        )
        .reset_index()
    )
    stats.insert(2, "share_percent", stats["cars"] / len(cars) * 100)
    stats = stats.sort_values("cars", ascending=False).round(1)
    log.info("origin_statistics -> %d rows", len(stats))
    return to_records(stats)


@mcp.tool()
def search_cars(
    origin: Literal["usa", "japan", "europe"] | None = None,
    min_mpg: float | None = None,
    min_horsepower: float | None = None,
    limit: Limit = 10,
) -> list[dict]:
    """Search cars by origin, minimum mpg and minimum horsepower, sorted by mpg (most fuel efficient first). Use this to find cars that match the customer's needs or to look up valid car names."""
    result = cars
    if origin is not None:
        result = result[result["origin"] == origin]
    if min_mpg is not None:
        result = result[result["mpg"] >= min_mpg]
    if min_horsepower is not None:
        result = result[result["horsepower"] >= min_horsepower]
    result = result.sort_values("mpg", ascending=False).head(limit)
    log.info(
        "search_cars origin=%s min_mpg=%s min_horsepower=%s limit=%s -> %d rows",
        origin,
        min_mpg,
        min_horsepower,
        limit,
        len(result),
    )
    return to_records(result)


@mcp.tool()
def car_highlights(name: str) -> dict[str, Any]:
    """Return selling points for one car: how it compares to the other cars in stock on fuel use, horsepower, acceleration and weight. Use this when the customer asks why they should pick a specific car."""
    car = find_car(name)
    beats_percent = {}
    for column, (_, higher_is_better) in HIGHLIGHT_METRICS.items():
        value = car[column].iloc[0]
        if pd.isna(value):
            continue
        others = cars[column].dropna()
        beaten = others < value if higher_is_better else others > value
        beats_percent[column] = round(beaten.mean() * 100)

    highlights = [
        f"{HIGHLIGHT_METRICS[column][0]} than {p}% of the cars in stock"
        for column, p in beats_percent.items()
        if p >= 75
    ]
    if not highlights and beats_percent:
        best = max(beats_percent, key=beats_percent.get)
        highlights = [
            f"{HIGHLIGHT_METRICS[best][0]} than {beats_percent[best]}% of the cars in stock"
        ]

    log.info("car_highlights name=%r -> %d rows", name, len(car))
    return {
        "car": to_records(car)[0],
        "beats_percent": beats_percent,
        "highlights": highlights,
    }


@mcp.tool()
def compare_cars(name_a: str, name_b: str) -> dict[str, Any]:
    """Compare two cars head to head and list where each one is better. Use this when the customer is choosing between two cars."""
    car_a = find_car(name_a)
    car_b = find_car(name_b)
    if car_a.index[0] == car_b.index[0]:
        log.warning("compare_cars name_a=%r name_b=%r -> same car", name_a, name_b)
        raise ToolError("Both names match the same car. Pick two different cars.")

    record_a = to_records(car_a)[0]
    record_b = to_records(car_b)[0]
    advantages = {record_a["name"]: [], record_b["name"]: []}
    for column, (phrase, higher_is_better) in HIGHLIGHT_METRICS.items():
        value_a = car_a[column].iloc[0]
        value_b = car_b[column].iloc[0]
        if pd.isna(value_a) or pd.isna(value_b) or value_a == value_b:
            continue
        a_wins = value_a > value_b if higher_is_better else value_a < value_b
        winner = record_a if a_wins else record_b
        advantages[winner["name"]].append(phrase)

    log.info("compare_cars name_a=%r name_b=%r", name_a, name_b)
    return {"car_a": record_a, "car_b": record_b, "advantages": advantages}


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
