"""Tests for shared.parsers — unified yen/age/size parsing."""

import datetime

from shared.parsers import (
    parse_yen, parse_building_age, parse_size_sqm,
    parse_year_to_age, parse_digits_as_yen,
)


# --- parse_yen ---

class TestParseYen:
    def test_man_yen_format(self):
        assert parse_yen("8.2万円") == 82000

    def test_man_yen_two_decimals(self):
        assert parse_yen("8.29万円") == 82900

    def test_man_yen_integer(self):
        assert parse_yen("10万円") == 100000

    def test_plain_yen_with_comma(self):
        assert parse_yen("101,800円") == 101800

    def test_yen_symbol(self):
        assert parse_yen("¥115,000") == 115000

    def test_plain_digits_yen(self):
        assert parse_yen("5000円") == 5000

    def test_dash_returns_zero(self):
        assert parse_yen("-") == 0

    def test_empty_string_returns_zero(self):
        assert parse_yen("") == 0

    def test_none_returns_zero(self):
        assert parse_yen(None) == 0

    def test_whitespace_dash(self):
        assert parse_yen(" - ") == 0

    def test_yen_no_comma(self):
        assert parse_yen("¥80000") == 80000


# --- parse_building_age ---

class TestParseBuildingAge:
    def test_standard_age(self):
        assert parse_building_age("築20年") == 20

    def test_new_build(self):
        assert parse_building_age("新築") == 0

    def test_empty_returns_negative(self):
        assert parse_building_age("") == -1

    def test_none_returns_negative(self):
        assert parse_building_age(None) == -1

    def test_single_year(self):
        assert parse_building_age("築1年") == 1


# --- parse_size_sqm ---

class TestParseSizeSqm:
    def test_standard_sqm(self):
        assert parse_size_sqm("50.28m²") == 50.28

    def test_m2_format(self):
        assert parse_size_sqm("65.5m2") == 65.5

    def test_empty_returns_zero(self):
        assert parse_size_sqm("") == 0.0

    def test_none_returns_zero(self):
        assert parse_size_sqm(None) == 0.0

    def test_integer_size(self):
        assert parse_size_sqm("70m²") == 70.0


# --- parse_year_to_age ---

class TestParseYearToAge:
    def test_japanese_year_format(self):
        expected = datetime.datetime.now().year - 2010
        assert parse_year_to_age("2010年 9月") == expected

    def test_plain_year(self):
        expected = datetime.datetime.now().year - 2015
        assert parse_year_to_age("2015") == expected

    def test_english_format(self):
        expected = datetime.datetime.now().year - 2010
        assert parse_year_to_age("Built in 2010") == expected

    def test_none_returns_negative(self):
        assert parse_year_to_age(None) == -1

    def test_empty_returns_negative(self):
        assert parse_year_to_age("") == -1

    def test_no_year_returns_negative(self):
        assert parse_year_to_age("no year here") == -1

    def test_future_year_clamps_to_zero(self):
        assert parse_year_to_age("2099") == 0


# --- parse_digits_as_yen ---

class TestParseDigitsAsYen:
    def test_yen_with_fullwidth_symbol(self):
        assert parse_digits_as_yen("￥50,000") == 50000

    def test_yen_with_halfwidth_symbol(self):
        assert parse_digits_as_yen("¥80,000") == 80000

    def test_monthly_costs_prefix(self):
        assert parse_digits_as_yen("Monthly Costs ¥150,490") == 150490

    def test_plain_digits(self):
        assert parse_digits_as_yen("50000") == 50000

    def test_none_returns_zero(self):
        assert parse_digits_as_yen(None) == 0

    def test_empty_returns_zero(self):
        assert parse_digits_as_yen("") == 0

    def test_dash_returns_zero(self):
        assert parse_digits_as_yen("-") == 0

    def test_none_string_returns_zero(self):
        assert parse_digits_as_yen("None") == 0

    def test_na_returns_zero(self):
        assert parse_digits_as_yen("N/A") == 0

    def test_free_returns_zero(self):
        assert parse_digits_as_yen("free") == 0

    def test_zero_string(self):
        assert parse_digits_as_yen("0") == 0

    def test_yen_zero(self):
        assert parse_digits_as_yen("¥0") == 0
