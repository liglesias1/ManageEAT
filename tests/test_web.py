"""The shared euro filter used by every page."""
from web import eur


def test_euros_have_thousands_separator_and_two_decimals():
    assert eur(1234.5) == "€1,234.50"


def test_negative_amounts_put_the_sign_before_the_euro_symbol():
    assert eur(-3200) == "-€3,200.00"