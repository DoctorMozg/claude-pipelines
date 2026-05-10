from calculator import add, subtract


def test_add_returns_sum():
    assert add(2, 3) == 5


def test_subtract_returns_difference():
    assert subtract(5, 2) == 3
