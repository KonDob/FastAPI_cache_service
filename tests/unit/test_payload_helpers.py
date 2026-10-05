"""Pure helpers behind payload generation: no database, no HTTP."""

import pytest

from app.services.payload import _hash_input, interleave


def test_interleave_alternates_items_from_both_lists() -> None:
    assert interleave(["a1", "a2", "a3"], ["b1", "b2", "b3"]) == [
        "a1",
        "b1",
        "a2",
        "b2",
        "a3",
        "b3",
    ]


def test_interleave_rejects_lists_of_different_length() -> None:
    # The API validates lengths up front; this guards the invariant if the helper is reused.
    with pytest.raises(ValueError):
        interleave(["a1", "a2"], ["b1"])


def test_hash_input_is_stable_for_identical_input() -> None:
    assert _hash_input(["a", "b"], ["c", "d"]) == _hash_input(["a", "b"], ["c", "d"])


@pytest.mark.parametrize(
    ("first", "second"),
    [
        pytest.param((["a", "b"], ["c", "d"]), (["b", "a"], ["c", "d"]), id="order-within-list"),
        pytest.param((["a"], ["b"]), (["b"], ["a"]), id="lists-swapped"),
        pytest.param((["a,b"], ["c"]), (["a", "b"], ["c"]), id="comma-inside-string"),
        pytest.param((["a"], ["b", "c"]), (["a", "b"], ["c"]), id="list-boundary"),
    ],
)
def test_hash_input_distinguishes_inputs_that_must_get_their_own_id(
    first: tuple[list[str], list[str]], second: tuple[list[str], list[str]]
) -> None:
    assert _hash_input(*first) != _hash_input(*second)
