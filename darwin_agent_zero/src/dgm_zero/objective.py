from __future__ import annotations

from dataclasses import dataclass

from .capability_model import CapabilityCase, CapabilitySpec


@dataclass(frozen=True)
class CapabilityObjective:
    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("objective text must be non-empty")


class ObjectiveCompiler:
    """Compile supported natural-language objectives into sealed benchmark specs.

    Unsupported objectives fail rather than receiving invented tests. New benchmark
    families can be added independently of search, sandboxing, validation, holdout,
    and promotion.
    """

    def compile(
        self,
        objective: CapabilityObjective | str,
    ) -> CapabilitySpec:
        text = (
            objective.text
            if isinstance(objective, CapabilityObjective)
            else objective
        )
        if not isinstance(text, str) or not text.strip():
            raise ValueError("objective text must be non-empty")
        normalized = " ".join(text.casefold().split())

        if "python" in normalized and any(
            word in normalized
            for word in ("debug", "diagnos", "error")
        ):
            return self._python_error_diagnosis()
        if "normal" in normalized and "text" in normalized:
            return self._normalize_text()
        if any(
            term in normalized
            for term in (
                "sequence span",
                "numeric range",
                "max minus min",
            )
        ):
            return self._sequence_span()
        if "clamp" in normalized:
            return self._clamp()

        raise ValueError(
            "unsupported objective family; provide an explicit capability JSON "
            "specification or add a benchmark factory for this objective"
        )

    @staticmethod
    def _normalize_text() -> CapabilitySpec:
        return CapabilitySpec(
            "normalize_text",
            (
                "Normalize text by lowercasing and collapsing "
                "surrounding/internal whitespace."
            ),
            "solve",
            (
                CapabilityCase(
                    "train_spaces",
                    "train",
                    ("  Hello   WORLD  ",),
                    "hello world",
                ),
                CapabilityCase(
                    "train_case",
                    "train",
                    ("A  B",),
                    "a b",
                ),
                CapabilityCase(
                    "validation_mixed",
                    "validation",
                    ("  Mixed CASE",),
                    "mixed case",
                ),
                CapabilityCase(
                    "validation_newlines",
                    "validation",
                    ("ONE\n\nTwo",),
                    "one two",
                ),
                CapabilityCase(
                    "validation_tabs",
                    "validation",
                    ("A\t B\tC",),
                    "a b c",
                ),
                CapabilityCase(
                    "holdout_tabs",
                    "holdout",
                    ("\tNEW   Value\n",),
                    "new value",
                ),
                CapabilityCase(
                    "holdout_unicode_case",
                    "holdout",
                    ("  CAFÉ   TEST  ",),
                    "café test",
                ),
                CapabilityCase(
                    "holdout_mixed_whitespace",
                    "holdout",
                    ("Alpha\r\n  BETA\tGamma",),
                    "alpha beta gamma",
                ),
            ),
        )

    @staticmethod
    def _sequence_span() -> CapabilitySpec:
        return CapabilitySpec(
            "sequence_span",
            "Return the numeric span of a sequence: maximum minus minimum.",
            "solve",
            (
                CapabilityCase(
                    "train_positive",
                    "train",
                    ([1, 5, 3],),
                    4,
                ),
                CapabilityCase(
                    "train_mixed",
                    "train",
                    ([-2, 4],),
                    6,
                ),
                CapabilityCase(
                    "validation_flat",
                    "validation",
                    ([10, 10],),
                    0,
                ),
                CapabilityCase(
                    "validation_negative",
                    "validation",
                    ([-8, -3, -11],),
                    8,
                ),
                CapabilityCase(
                    "validation_fractional",
                    "validation",
                    ([1.5, -2.5, 4.0],),
                    6.5,
                ),
                CapabilityCase(
                    "holdout_wide",
                    "holdout",
                    ([-5, 0, 7],),
                    12,
                ),
                CapabilityCase(
                    "holdout_two_values",
                    "holdout",
                    ([100, -25],),
                    125,
                ),
                CapabilityCase(
                    "holdout_fractional",
                    "holdout",
                    ([-0.25, 0.5, 2.75],),
                    3.0,
                ),
            ),
        )

    @staticmethod
    def _clamp() -> CapabilitySpec:
        return CapabilitySpec(
            "clamp_value",
            "Clamp a scalar value to inclusive lower and upper bounds.",
            "solve",
            (
                CapabilityCase(
                    "train_low",
                    "train",
                    (-5, 0, 10),
                    0,
                ),
                CapabilityCase(
                    "train_mid",
                    "train",
                    (5, 0, 10),
                    5,
                ),
                CapabilityCase(
                    "train_high",
                    "train",
                    (15, 0, 10),
                    10,
                ),
                CapabilityCase(
                    "validation_negative",
                    "validation",
                    (-2, -1, 1),
                    -1,
                ),
                CapabilityCase(
                    "validation_inside_negative_bounds",
                    "validation",
                    (-5, -10, -2),
                    -5,
                ),
                CapabilityCase(
                    "validation_upper_boundary",
                    "validation",
                    (4, -3, 4),
                    4,
                ),
                CapabilityCase(
                    "holdout_shifted",
                    "holdout",
                    (9, 2, 7),
                    7,
                ),
                CapabilityCase(
                    "holdout_lower_boundary",
                    "holdout",
                    (2, 2, 7),
                    2,
                ),
                CapabilityCase(
                    "holdout_fractional",
                    "holdout",
                    (1.25, -0.5, 1.0),
                    1.0,
                ),
            ),
        )

    @staticmethod
    def _python_error_diagnosis() -> CapabilitySpec:
        return CapabilitySpec(
            "python_error_diagnosis",
            (
                "Classify common Python runtime failures into stable "
                "diagnostic categories from error messages."
            ),
            "solve",
            (
                CapabilityCase(
                    "train_name_1",
                    "train",
                    ("NameError: name 'total' is not defined",),
                    "undefined_name",
                ),
                CapabilityCase(
                    "train_name_2",
                    "train",
                    ("NameError: name 'counter' is not defined",),
                    "undefined_name",
                ),
                CapabilityCase(
                    "train_type_1",
                    "train",
                    (
                        "TypeError: unsupported operand type(s) for +: "
                        "'int' and 'str'",
                    ),
                    "type_mismatch",
                ),
                CapabilityCase(
                    "train_type_2",
                    "train",
                    (
                        "TypeError: can only concatenate str "
                        "(not 'int') to str",
                    ),
                    "type_mismatch",
                ),
                CapabilityCase(
                    "train_index_1",
                    "train",
                    ("IndexError: list index out of range",),
                    "bad_index",
                ),
                CapabilityCase(
                    "train_index_2",
                    "train",
                    ("IndexError: tuple index out of range",),
                    "bad_index",
                ),
                CapabilityCase(
                    "validation_name",
                    "validation",
                    ("NameError: name 'result' is not defined",),
                    "undefined_name",
                ),
                CapabilityCase(
                    "validation_type",
                    "validation",
                    ("TypeError: object of type 'int' has no len()",),
                    "type_mismatch",
                ),
                CapabilityCase(
                    "validation_index",
                    "validation",
                    ("IndexError: string index out of range",),
                    "bad_index",
                ),
                CapabilityCase(
                    "holdout_name",
                    "holdout",
                    ("NameError: name 'items' is not defined",),
                    "undefined_name",
                ),
                CapabilityCase(
                    "holdout_type",
                    "holdout",
                    ("TypeError: 'NoneType' object is not subscriptable",),
                    "type_mismatch",
                ),
                CapabilityCase(
                    "holdout_index",
                    "holdout",
                    ("IndexError: list assignment index out of range",),
                    "bad_index",
                ),
            ),
        )
