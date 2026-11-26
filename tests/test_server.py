import pytest
from mcp.server.mcpserver.exceptions import ToolError

from server import (
    car_highlights,
    compare_cars,
    fastest_acceleration,
    most_fuel_efficient,
    most_horsepower,
    origin_statistics,
    search_cars,
)


def test_most_fuel_efficient():
    [car] = most_fuel_efficient(1)
    assert car["name"] == "mazda glc"
    assert car["mpg"] == 46.6
    assert car["liters_per_100km"] == 5.0


def test_most_horsepower():
    [car] = most_horsepower(1)
    assert car["name"] == "pontiac grand prix"
    assert car["horsepower"] == 230


def test_fastest_acceleration():
    [car] = fastest_acceleration(1)
    assert car["name"] == "plymouth 'cuda 340"
    assert car["acceleration"] == 8.0


def test_origin_statistics_counts():
    counts = {row["origin"]: row["cars"] for row in origin_statistics()}
    assert counts == {"usa": 249, "japan": 79, "europe": 70}


def test_missing_values_become_none():
    result = most_fuel_efficient(50)
    assert all(v == v for car in result for v in car.values())  # noqa: PLR0124 (NaN != NaN)
    assert any(car["horsepower"] is None for car in result)


def test_search_cars_filters():
    result = search_cars(origin="japan", min_mpg=40)
    assert result
    assert all(car["origin"] == "japan" and car["mpg"] >= 40 for car in result)


def test_car_highlights():
    result = car_highlights("mazda glc")
    assert result["beats_percent"]["mpg"] >= 99
    assert result["highlights"]


def test_car_highlights_unknown_car():
    with pytest.raises(ToolError):
        car_highlights("no such car xyz")


def test_compare_cars():
    result = compare_cars("mazda glc", "pontiac grand prix")
    assert "Uses less fuel" in result["advantages"]["mazda glc"]
    assert "Has more horsepower" in result["advantages"]["pontiac grand prix"]


def test_compare_cars_unknown_car():
    with pytest.raises(ToolError):
        compare_cars("mazda glc", "no such car xyz")


def test_compare_cars_same_car():
    with pytest.raises(ToolError):
        compare_cars("mazda glc", "mazda glc")
