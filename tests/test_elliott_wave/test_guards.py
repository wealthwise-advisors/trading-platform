"""TR-2 blocked-rule guards.

These are the tests that stop a future change from quietly filling a
documented gap with an invented number. Every assertion here corresponds to an
Open Question that is still OPEN; when one is resolved, the matching guard is
expected to be deleted deliberately, not to start failing by accident.
"""

import inspect
import pkgutil
import re
from pathlib import Path

import pytest

import src.analysis.elliott_wave as ew
from src.analysis.elliott_wave import measurements, validation
from src.analysis.elliott_wave.models import LifecycleState, StructureType, Wave

PKG_DIR = Path(ew.__path__[0])
MODULE_NAMES = sorted(m.name for m in pkgutil.iter_modules(ew.__path__))


def _code_only(path: Path) -> str:
    """Source with docstrings and comments stripped, so prose EXPLAINING a gap
    is never mistaken for an implementation of it."""
    src = path.read_text(encoding="utf-8")
    src = re.sub(r'"""7?.*?"""', "", src, flags=re.S)
    src = re.sub(r"'''.*?'''", "", src, flags=re.S)
    return "\n".join(line.split("#")[0] for line in src.splitlines())


ALL_CODE = {name: _code_only(PKG_DIR / f"{name}.py") for name in MODULE_NAMES}
ALL_CODE["__init__"] = _code_only(PKG_DIR / "__init__.py")

# validation.py IS the blocked-rule registry: its data literally names every
# deferred concept and quotes the reference's own wording. Scanning it for
# those words would flag the very mechanism that keeps the gaps honest, so the
# "is this concept mentioned" guards run against IMPL_CODE. Guards about
# BEHAVIOUR (scoring fields, purity) still cover every module via ALL_CODE.
IMPL_CODE = {k: v for k, v in ALL_CODE.items() if k != "validation"}


class TestOQ05NoFibonacciTolerance:
    """OQ-05 open: ratios may be COMPUTED, never MATCHED."""

    FIB = ["0.618", "1.618", "0.382", "0.236", "1.236", "2.618", "0.764",
           "0.854", "3.236", "61.8", "38.2", "23.6", "76.4", "85.4", "161.8",
           "123.6", "323.6", "14.6"]

    @pytest.mark.parametrize("module", sorted(IMPL_CODE))
    def test_no_fibonacci_constant_in_code(self, module):
        hits = [f for f in self.FIB if re.search(rf"(?<![\d.]){re.escape(f)}(?![\d])",
                                                 IMPL_CODE[module])]
        assert not hits, f"{module}.py contains Fibonacci constant(s) {hits}"

    @pytest.mark.parametrize("module", sorted(IMPL_CODE))
    def test_no_tolerance_identifier_in_code(self, module):
        hits = re.findall(r"\b(tolerance|epsilon|atol|rtol|EPS|isclose|approx)\b",
                          IMPL_CODE[module])
        assert not hits, f"{module}.py references {set(hits)}"

    def test_measurements_exposes_no_match_function(self):
        names = [n for n, _ in inspect.getmembers(measurements, inspect.isfunction)]
        banned = [n for n in names
                  if re.search(r"match|within|close_to|tolerance|score", n, re.I)]
        assert not banned, f"measurements.py exposes {banned}"

    def test_recorded_ratios_are_raw_numbers_not_verdicts(self):
        """A recorded measurement must never be a boolean 'matched' flag."""
        src = ALL_CODE["measurements"]
        assert "matched" not in src

    def test_ambiguous_base_ratios_are_not_computed(self):
        """OQ-06 / OQ-07 / OQ-11: where the reference leaves the ratio's BASE
        undefined, the ratio must be absent, not guessed."""
        src = ALL_CODE["measurements"]
        assert "IMP-F02" not in src, "wave3/wave1-2 base is undefined (OQ-06)"
        assert "wave_ab" not in src.lower(), "'wave AB' base is undefined (OQ-11)"
        assert "inverse" not in src.lower(), "'inverse retracement' undefined (OQ-07)"


class TestDeferredStructuresAbsent:
    """Structures blocked by an open question must not exist at all."""

    def test_no_deferred_structure_types(self):
        present = set(StructureType.__members__)
        banned = {"TRIANGLE", "DOUBLE_THREE", "TRIPLE_THREE", "MOTIVE_SEQUENCE",
                  "IMPULSE_WITH_EXTENSION", "FLAT_REGULAR", "FLAT_EXPANDED"}
        assert not (present & banned), f"deferred types present: {present & banned}"

    def test_no_deferred_modules(self):
        banned = {"motive_sequence", "advanced", "fibonacci", "targets",
                  "alternates", "scoring"}
        assert not (set(MODULE_NAMES) & banned)

    @pytest.mark.parametrize("term,oq", [
        ("triangle", "OQ-12/13"),
        ("motive_sequence", "OQ-14"),
        ("double_three", "OQ-18"),
        ("triple_three", "OQ-18"),
        ("wedge", "OQ-15"),
    ])
    def test_no_logic_for_deferred_concept(self, term, oq):
        for module, src in IMPL_CODE.items():
            assert term not in src.lower(), f"{module}.py implements {term} ({oq} open)"

    def test_no_regular_or_expanded_flat_distinction(self):
        """OQ-09/OQ-10 open: the two subtypes are indistinguishable, so no code
        may try to separate them."""
        for module, src in IMPL_CODE.items():
            low = src.lower()
            assert "flat_regular" not in low and "flat_expanded" not in low, module
            for word in ("substantially", "slightly", "near_start"):
                assert word not in low, f"{module}.py uses '{word}' (OQ-09/10 open)"

    def test_no_extension_detection(self):
        """OQ-24: 'extension' has no numeric definition."""
        for module, src in IMPL_CODE.items():
            assert not re.search(r"\bis_extended\b|\bextension\b", src.lower()), module

    def test_no_named_degree_assignment(self):
        """OQ-17: pivots carry a scale index, never one of the 9 degree names."""
        names = ["grand super cycle", "supercycle", "subminuette", "minuette",
                 "degree_name", "DEGREE_NAME_MAP"]
        for module, src in IMPL_CODE.items():
            for n in names:
                assert n.lower() not in src.lower(), f"{module}.py mentions {n}"


class TestNoScoring:
    """FR-7.4: the reference states no weighting function anywhere."""

    def test_wave_has_no_score_field(self):
        fields = set(Wave.__dataclass_fields__)
        assert not (fields & {"confidence", "score", "probability", "rank", "weight"})

    def test_wave_has_no_validity_field(self):
        """FR-5.4/DM-2.2: a failing candidate is never created, so there is
        nothing for such a field to describe."""
        fields = set(Wave.__dataclass_fields__)
        assert not (fields & {"valid", "violated_rules", "invalid", "rejected"})

    def test_no_rejected_lifecycle_state(self):
        assert not ({"INVALID", "REJECTED", "FAILED"} & set(LifecycleState.__members__))

    @pytest.mark.parametrize("module", sorted(IMPL_CODE))
    def test_no_scoring_identifiers(self, module):
        hits = re.findall(r"\b(confidence|probability)\b", IMPL_CODE[module])
        assert not hits, f"{module}.py references {set(hits)}"


class TestGuidelineNeverGates:
    """A guideline-tier rule must never cause a rejection; only mandatory-tier
    rules can. Fibonacci relationships are all guideline-tier."""

    def test_recorded_ratios_do_not_affect_acceptance(self, diverging_rsi):
        from src.analysis.elliott_wave import hierarchy, impulse
        from .conftest import up_impulse

        # Wave 2 retraces ~5% of wave 1 -- nowhere near any stated Fibonacci
        # value (50/61.8/76.4/85.4%). It must still be accepted.
        w = up_impulse(p0=100, p1=200, p2=195, p3=400, p4=300, p5=560)
        ratio = abs(w[2].price - w[1].price) / abs(w[1].price - w[0].price)
        assert ratio == pytest.approx(0.05)
        spans = hierarchy.SpanIndex()
        spans.freeze()
        waves = impulse.classify_impulses({1: w}, diverging_rsi(200), spans)
        structs = [x for x in waves if x.structure_type is StructureType.IMPULSE]
        assert structs, "a guideline ratio must never gate"

        # Measurements are attached by a separate pass (the pipeline calls it
        # after classification), which is itself the point: recording happens
        # downstream of acceptance and can never influence it.
        measurements.record(structs, {x.id: x for x in waves})
        assert structs[0].measurements["IMP-F01_wave2_over_wave1"] == pytest.approx(0.05)

    def test_diagonal_overlap_guideline_does_not_gate(self):
        """LD-02/ED-02 is the one place the reference explicitly says a
        condition does NOT apply."""
        src = ALL_CODE["diagonal"]
        # overlap is computed, but never used in a branch that skips a candidate
        assert "waves_1_and_4_overlap" in src
        assert not re.search(r"if\s+.*waves_1_and_4_overlap.*:\s*\n\s*continue", src)


class TestBlockedRuleRegistry:
    def test_registry_is_populated(self):
        assert len(validation.BLOCKED_RULES) >= 15
        assert len(validation.blocked_rule_ids()) >= 50

    def test_every_entry_names_an_oq_and_a_reason(self):
        for entry in validation.BLOCKED_RULES:
            assert entry["rules"] and entry["oq"] and len(entry["reason"]) > 20

    @pytest.mark.parametrize("oq", ["OQ-05", "OQ-09/OQ-10", "OQ-12/OQ-13",
                                    "OQ-14", "OQ-18", "OQ-24", "OQ-25"])
    def test_open_question_is_declared_blocked(self, oq):
        assert any(e["oq"] == oq for e in validation.BLOCKED_RULES), \
            f"{oq} is open but not declared in the registry"

    def test_v1_limitations_are_declared(self):
        assert validation.V1_LIMITATIONS
        joined = " ".join(validation.V1_LIMITATIONS).lower()
        assert "zigzag wave a/c" in joined      # diagonal host limitation
        assert "scale 1" in joined              # D-14 recursion floor


class TestIndependence:
    """FR-1f.2: the package must neither modify nor CONSUME the existing
    swing/zigzag modules. Checked against resolved bindings, not source text --
    a rename or aliased import would defeat a grep."""

    FORBIDDEN = ("swing_identification", "zigzag")

    def test_no_bound_name_resolves_to_a_forbidden_module(self):
        import importlib
        bad = []
        for name in MODULE_NAMES + ["__init__"]:
            mod = ew if name == "__init__" else importlib.import_module(
                f"src.analysis.elliott_wave.{name}")
            for attr, val in vars(mod).items():
                origin = getattr(val, "__module__", None) or getattr(val, "__name__", None)
                if origin and any(f in str(origin) for f in self.FORBIDDEN):
                    bad.append(f"{name}.{attr} -> {origin}")
        assert not bad, bad

    def test_only_permitted_shared_dependency_is_indicators(self):
        external = set()
        for name in MODULE_NAMES:
            src = _code_only(PKG_DIR / f"{name}.py")
            for m in re.finditer(r"from\s+(src\.[\w.]+)\s+import", src):
                external.add(m.group(1))
        assert external <= {"src.analysis.indicators"}, external


class TestPurity:
    """FR-6.1/6.2: deterministic, no clock, no randomness, no IO."""

    @pytest.mark.parametrize("module", sorted(ALL_CODE))
    def test_no_impure_calls(self, module):
        src = ALL_CODE[module]
        for banned in ("random.", "datetime.now", "time.time", "uuid", "open("):
            assert banned not in src, f"{module}.py uses {banned}"
