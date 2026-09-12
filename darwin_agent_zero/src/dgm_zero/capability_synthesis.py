from __future__ import annotations

import itertools
import math
import re

from .capability_model import SkillCandidate, TrainingView, render_function


class TemplateSynthesizer:
    """Local starter synthesizer for small, pure, JSON-in/JSON-out functions.

    The synthesizer sees training examples only. Its grammar covers common string,
    sequence, scalar, small affine numeric transformations, and simple diagnostic
    classifiers inferred from discriminative training tokens. The acquisition loop
    accepts any generator implementing the same ``generate`` protocol, so stronger
    synthesis/model providers can be plugged in without weakening evaluation.
    """

    def generate(
        self,
        view: TrainingView,
        *,
        prior_source: str | None,
        max_candidates: int,
    ) -> list[SkillCandidate]:
        if max_candidates <= 0:
            raise ValueError("max_candidates must be positive")

        candidates: list[SkillCandidate] = []
        if prior_source:
            candidates.append(SkillCandidate(prior_source, "current-skill"))

        candidates.append(
            SkillCandidate(
                render_function(view.entrypoint, view.arity, "None"),
                "null",
            )
        )
        if view.arity == 1:
            candidates.extend(self._single_argument_candidates(view))
            candidates.extend(self._classification_candidates(view))
        candidates.extend(self._numeric_candidates(view))

        args = [f"x{i}" for i in range(view.arity)]
        if view.arity == 2:
            a, b = args
            for expression, label in (
                (f"{a} + {b}", "binary-add"),
                (f"{a} - {b}", "binary-subtract"),
                (f"{b} - {a}", "binary-reverse-subtract"),
                (f"{a} * {b}", "binary-multiply"),
                (f"min({a}, {b})", "binary-min"),
                (f"max({a}, {b})", "binary-max"),
                (f"str({a}) + str({b})", "binary-concatenate"),
            ):
                candidates.append(
                    SkillCandidate(
                        render_function(view.entrypoint, view.arity, expression),
                        label,
                    )
                )
        if view.arity == 3:
            x, low, high = args
            candidates.append(
                SkillCandidate(
                    render_function(
                        view.entrypoint,
                        view.arity,
                        f"min(max({x}, {low}), {high})",
                    ),
                    "clamp",
                )
            )

        unique: list[SkillCandidate] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate.digest in seen:
                continue
            seen.add(candidate.digest)
            unique.append(candidate)
            if len(unique) >= max_candidates:
                break
        return unique

    def _single_argument_candidates(
        self,
        view: TrainingView,
    ) -> list[SkillCandidate]:
        arg = "x0"
        expressions = (
            (arg, "identity"),
            (f"abs({arg})", "absolute"),
            (f"len({arg})", "length"),
            (f"str({arg})", "stringify"),
            (f"{arg}.strip()", "strip"),
            (f"{arg}.lower()", "lower"),
            (f"{arg}.upper()", "upper"),
            (f"{arg}.casefold()", "casefold"),
            (f"' '.join({arg}.split())", "collapse-whitespace"),
            (f"' '.join({arg}.strip().lower().split())", "normalize-text"),
            (f"' '.join({arg}.strip().casefold().split())", "normalize-text-casefold"),
            (f"sum({arg})", "sum-sequence"),
            (f"min({arg}) if {arg} else None", "minimum"),
            (f"max({arg}) if {arg} else None", "maximum"),
            (f"(max({arg}) - min({arg})) if {arg} else 0", "sequence-span"),
            (f"sorted({arg})", "sort"),
            (f"list(reversed({arg}))", "reverse-sequence"),
            (f"{arg}[0] if {arg} else None", "first"),
            (f"{arg}[-1] if {arg} else None", "last"),
            (f"{arg}[::-1]", "reverse-slice"),
        )
        return [
            SkillCandidate(
                render_function(view.entrypoint, view.arity, expression),
                label,
            )
            for expression, label in expressions
        ]

    def _classification_candidates(
        self,
        view: TrainingView,
    ) -> list[SkillCandidate]:
        rows: list[tuple[str, object]] = []
        for case in view.cases:
            if len(case.args) != 1 or not isinstance(case.args[0], str):
                return []
            if not isinstance(case.expected, (str, int, bool)):
                return []
            rows.append((case.args[0], case.expected))

        labels = list(dict.fromkeys(label for _, label in rows))
        if len(labels) < 2:
            return []

        token_sets = {
            label: [
                set(re.findall(r"[a-z0-9_]+", text.casefold()))
                for text, row_label in rows
                if row_label == label
            ]
            for label in labels
        }
        cues: dict[object, str] = {}
        for label in labels:
            own_sets = token_sets[label]
            if not own_sets:
                return []
            common = set.intersection(*own_sets)
            other = set().union(
                *(
                    token_set
                    for other_label in labels
                    if other_label != label
                    for token_set in token_sets[other_label]
                )
            )
            unique = [
                token
                for token in common - other
                if len(token) >= 3
            ]
            if not unique:
                return []
            cues[label] = sorted(
                unique,
                key=lambda token: (-len(token), token),
            )[0]

        lines = [
            f"def {view.entrypoint}(x0):",
            "    text = x0.casefold()",
        ]
        for label in labels:
            lines.append(f"    if {cues[label]!r} in text:")
            lines.append(f"        return {label!r}")
        lines.append("    return None")
        return [
            SkillCandidate(
                "\n".join(lines) + "\n",
                "keyword-classifier",
            )
        ]

    def _numeric_candidates(
        self,
        view: TrainingView,
    ) -> list[SkillCandidate]:
        rows: list[tuple[tuple[float, ...], float]] = []
        for case in view.cases:
            if (
                len(case.args) != view.arity
                or isinstance(case.expected, bool)
                or not isinstance(case.expected, (int, float))
                or any(
                    isinstance(value, bool) or not isinstance(value, (int, float))
                    for value in case.args
                )
            ):
                return []
            rows.append(
                (
                    tuple(float(value) for value in case.args),
                    float(case.expected),
                )
            )
        if not rows:
            return []

        candidates: list[SkillCandidate] = []
        matches = 0
        for coeffs in itertools.product(range(-4, 5), repeat=view.arity):
            for bias in range(-5, 6):
                if all(
                    math.isclose(
                        sum(
                            coefficient * value
                            for coefficient, value in zip(coeffs, values)
                        )
                        + bias,
                        expected,
                        rel_tol=1e-12,
                        abs_tol=1e-12,
                    )
                    for values, expected in rows
                ):
                    terms = [
                        f"({coefficient} * x{index})"
                        for index, coefficient in enumerate(coeffs)
                        if coefficient
                    ]
                    if bias or not terms:
                        terms.append(str(bias))
                    candidates.append(
                        SkillCandidate(
                            render_function(
                                view.entrypoint,
                                view.arity,
                                " + ".join(terms),
                            ),
                            "affine-fit",
                        )
                    )
                    matches += 1
                    if matches >= 8:
                        return candidates
        return candidates
