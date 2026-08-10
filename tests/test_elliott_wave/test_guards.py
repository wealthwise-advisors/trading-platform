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
    src = re.sub(r'""".*?"""', "", src, flags=re.S)
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

    # The ONE scoped exception, approved 2026-08-10. DT-05/TT-05 state an
    # absolute prohibition -- "Wave Y can not pass 161.8% of wave W" -- which
    # is a one-sided INEQUALITY, not a ratio match. An inequality needs no
    # tolerance, so unlike every OQ-05 ratio it is implementable exactly as
    # written. Permitted in combination.py only; still banned everywhere else,
    # which test_fibonacci_exception_is_scoped_to_one_module enforces.
    ALLOWED = {"combination": {"1.618", "161.8"}}

    @pytest.mark.parametrize("module", sorted(IMPL_CODE))
    def test_no_fibonacci_constant_in_code(self, module):
        allowed = self.ALLOWED.get(module, set())
        hits = [f for f in self.FIB
                if f not in allowed
                and re.search(rf"(?<![\d.]){re.escape(f)}(?![\d])", IMPL_CODE[module])]
        assert not hits, f"{module}.py contains Fibonacci constant(s) {hits}"

    def test_fibonacci_exception_is_scoped_to_one_module(self):
        """The 161.8 allowance must not spread. Any other module using it is a
        regression, whatever the justification in its own comments."""
        offenders = [m for m, src in IMPL_CODE.items()
                     if m != "combination"
                     and re.search(r"(?<![\d.])1?61\.8(?![\d])", src)]
        assert not offenders, f"161.8 leaked into {offenders}"

    def test_the_exception_is_an_inequality_not_a_match(self):
        """The permitted constant must be used as a ceiling. If it ever becomes
        an equality/closeness test, that is OQ-05 matching by the back door."""
        src = IMPL_CODE["combination"]
        assert re.search(r"<=\s*WAVE_Y_CEILING_OF_W|WAVE_Y_CEILING_OF_W\s*\*", src)
        assert "==" not in src.split("WAVE_Y_CEILING_OF_W")[0].splitlines()[-1]

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
        # DOUBLE_THREE / TRIPLE_THREE were removed from this list when OQ-18
        # was resolved (depth cap, 2026-08-10) -- deliberately, not by accident.
        banned = {"TRIANGLE", "MOTIVE_SEQUENCE",
                  "IMPULSE_WITH_EXTENSION", "FLAT_REGULAR", "FLAT_EXPANDED"}
        assert not (present & banned), f"deferred types present: {present & banned}"

    def test_no_deferred_modules(self):
        banned = {"motive_sequence", "advanced", "fibonacci", "targets",
                  "alternates", "scoring"}
        assert not (set(MODULE_NAMES) & banned)

    @pytest.mark.parametrize("term,oq", [
        ("motive_sequence", "OQ-14"),
        ("wedge", "OQ-15"),
        # double_three / triple_three dropped here when OQ-18 was resolved.
        # "triangle" dropped 2026-08-10: candidates are now MEASURED. The ban
        # is replaced by the three scoped guards below, which forbid the
        # verdict rather than the word.
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

    def test_no_triangle_verdict(self):
        """OQ-12/OQ-13 open: triangle candidates may be MEASURED, never named.

        Narrowed 2026-08-10 (was: the word "triangle" banned outright). What
        must not exist is anything that renders a verdict -- a variant name, a
        sideways decision, or an RSI "supports" decision.
        """
        verdicts = (r"\bis_triangle\b|\bis_sideways\b|\brsi_supports\b|"
                    r"\bascending\b|\bdescending\b|\bcontracting\b|"
                    r"\bexpanding\b|triangle_variant|sideways_threshold")
        for module, src in IMPL_CODE.items():
            assert not re.search(verdicts, src.lower()), module

    def test_triangle_logic_is_scoped_to_two_modules(self):
        """triangle.py measures it; pipeline.py calls it. If "triangle"
        appears in impulse.py, diagonal.py or correction.py, it is gating."""
        allowed = {"triangle", "pipeline", "models"}
        for module, src in IMPL_CODE.items():
            if module in allowed:
                continue
            assert "triangle" not in src.lower(), (
                f"{module}.py references triangle; only {allowed} may (OQ-12)")

    def test_no_threshold_constant_in_the_triangle_code(self):
        """The load-bearing OQ-12 guard: no number stands in for "sideways".

        A sidewaysness cutoff would appear as a float literal, and the ratio
        must never be compared against anything. TRI-01's leg count (5) and
        the subdivision floor (2) are integers stated by the reference and by
        LD-03/ED-03's existing reading, not thresholds.
        """
        from src.analysis.elliott_wave import triangle
        src = inspect.getsource(triangle)
        src = re.sub(r'""".*?"""', "", src, flags=re.S)
        src = "\n".join(line.split("#")[0] for line in src.splitlines())

        floats = [f for f in re.findall(r"\b\d+\.\d+\b", src) if f != "0.0"]
        assert not floats, f"float literal in triangle code -- a threshold? {floats}"

        for line in src.splitlines():
            if "net_over_path" not in line and "_sidewaysness(" not in line:
                continue
            bare = line.replace("->", "")     # a return annotation is not a test
            assert not re.search(r"[<>]=?", bare), (
                f"the sidewaysness ratio is being thresholded: {line.strip()}")

    def test_no_threshold_constant_in_the_flat_subtype_code(self):
        """OQ-09/OQ-10 open: 'near', 'slightly beyond' and 'substantially
        beyond' were investigated on 356 real flats and have no natural width,
        so no number may stand in for them.

        FLE-01 is measured, and needs no constant to be: "beyond the starting
        level of wave A" is a sign test, not a magnitude test. So the same
        no-float-literal rule that guards the extension code applies here.
        """
        src = inspect.getsource(measurements.record_flat_subtype)
        src = re.sub(r'""".*?"""', "", src, flags=re.S)
        src = "\n".join(line.split("#")[0] for line in src.splitlines())

        floats = [f for f in re.findall(r"\b\d+\.\d+\b", src) if f != "1.0"]
        assert not floats, f"float literal in flat-subtype code: {floats}"

        for line in src.splitlines():
            if "retracement_of_waveA" in line or "waveC_beyond" in line:
                assert not re.search(r"[<>]=?", line), (
                    f"a flat ratio is being thresholded: {line.strip()}")

    def test_flat_subtype_measurement_does_not_gate(self):
        """It may not skip, reject or retype a structure."""
        src = inspect.getsource(measurements.record_flat_subtype)
        assert "structure_type =" not in src, "the measurement retypes a flat"
        assert "LifecycleState" not in src, "the measurement touches lifecycle"

    def test_no_extension_verdict(self):
        """OQ-24 open: extension may be MEASURED, never DECIDED.

        Narrowed 2026-08-10 (was: the word 'extension' banned outright). OQ-24
        was investigated on real data and stayed open -- no cliff in any of
        five candidate measures -- so the quantities are now recorded while the
        judgement is withheld. What must not exist is anything that renders a
        verdict.
        """
        verdicts = (r"\bis_extended\b|\bhas_extension\b|\bis_extension\b|"
                    r"extension_threshold|ext_threshold|min_extension|"
                    r"extended_wave\b|impulse_with_extension")
        for module, src in IMPL_CODE.items():
            assert not re.search(verdicts, src.lower()), module

    def test_extension_measurement_is_scoped_to_two_modules(self):
        """The exception must not spread into anything that gates.

        measurements.py computes it; pipeline.py calls it. If 'extension'
        appears in impulse.py or diagonal.py, something is gating on it.
        """
        allowed = {"measurements", "pipeline"}
        for module, src in IMPL_CODE.items():
            if module in allowed:
                continue
            assert "extension" not in src.lower(), (
                f"{module}.py references extension; only {allowed} may (OQ-24)")

    def test_no_threshold_constant_in_the_extension_code(self):
        """The load-bearing OQ-24 guard: there is no number to be extended BY.

        Any cutoff -- 1.618, 2.0, 1.5 -- would appear as a float literal in
        this code. There is none, and the measured ratio is never compared
        against anything.
        """
        funcs = [measurements.record_extension,
                 measurements._sole_max,
                 measurements._subdivision_measurements]
        src = "\n".join(inspect.getsource(f) for f in funcs)
        src = re.sub(r'""".*?"""', "", src, flags=re.S)
        src = "\n".join(line.split("#")[0] for line in src.splitlines())

        floats = re.findall(r"\b\d+\.\d+\b", src)
        assert not floats, f"float literal in extension code -- a threshold? {floats}"

        for line in src.splitlines():
            if "over_second" in line:
                assert not re.search(r"[<>]=?|==", line), (
                    f"the extension ratio is being compared: {line.strip()}")

    def test_no_named_degree_assignment(self):
        """OQ-17: pivots carry a scale index, never one of the 9 degree names."""
        names = ["grand super cycle", "supercycle", "subminuette", "minuette",
                 "degree_name", "DEGREE_NAME_MAP"]
        # note "of smaller degree" is reference wording quoted in
        # combination.py's docstring; docstrings are stripped by _code_only
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
                                    "OQ-14", "OQ-24", "OQ-25", "OQ-26"])
    def test_open_question_is_declared_blocked(self, oq):
        assert any(e["oq"] == oq for e in validation.BLOCKED_RULES), \
            f"{oq} is open but not declared in the registry"

    def test_oq05_does_not_claim_the_range_stated_rules(self):
        """Corrected 2026-08-10. FLE-F02 ("123.6% - 161.8% of wave AB") and
        FLU-F02 ("61.8% - 100% of wave AB") are stated as RANGES. A range is
        directly evaluable, so no tolerance is needed and OQ-05 does not apply.
        They remain blocked -- by OQ-11's undefined "wave AB" base."""
        oq05 = [e for e in validation.BLOCKED_RULES if e["oq"] == "OQ-05"][0]
        assert "FLE-F02" not in oq05["rules"]
        assert "FLU-F02" not in oq05["rules"]
        assert len(oq05["rules"]) == 14, "OQ-05 blocks 14 rules, not 16"

        oq11 = [e for e in validation.BLOCKED_RULES if e["oq"] == "OQ-11"][0]
        assert {"FLE-F02", "FLU-F02"} <= set(oq11["rules"])

    def test_imp_f04_is_blocked_by_both_oq05_and_oq07(self):
        """It has three bases: one undefined ("inverse retracement", OQ-07)
        and two discrete ("equal to wave 1", "61.8% of wave 1-3", OQ-05)."""
        for oq in ("OQ-05", "OQ-07"):
            entry = [e for e in validation.BLOCKED_RULES if e["oq"] == oq][0]
            assert "IMP-F04" in entry["rules"], f"IMP-F04 missing from {oq}"

    def test_oq14_is_declared_not_implementable_not_merely_blocked(self):
        """Closed 2026-08-10. OQ-14 is a terminal gap, not a pending decision:
        Motive Sequence is defined by "the numbers in the motive sequence" and
        the reference never states them, so there is nothing to decide. The id
        stays "OQ-14" -- consumers group by it -- and the disposition lives in
        the reason."""
        entry = [e for e in validation.BLOCKED_RULES if e["oq"] == "OQ-14"][0]
        assert set(entry["rules"]) == {"MS-01", "MS-02", "MS-03"}
        assert "not implementable" in entry["reason"].lower()

    def test_no_motive_sequence_numbers_were_invented(self):
        """MS-03's "much LIKE the Fibonacci number sequence" is a simile, not
        an identity. No Fibonacci integer set may appear as a swing-count
        target anywhere in the package."""
        for module, src in IMPL_CODE.items():
            low = src.lower()
            assert "motive_sequence" not in low, module
            for seq in ("[3, 5, 8", "[5, 9, 13", "(3, 5, 8", "(5, 9, 13"):
                assert seq not in low, f"{module}.py invents a sequence (OQ-14)"

    def test_oq18_no_longer_declared_blocked(self):
        """OQ-18 is resolved; leaving it in the registry would misreport."""
        assert not any(e["oq"] == "OQ-18" for e in validation.BLOCKED_RULES)

    def test_v1_limitations_are_declared(self):
        assert validation.V1_LIMITATIONS
        joined = " ".join(validation.V1_LIMITATIONS).lower()
        assert "depth 1" in joined            # the OQ-18 cap is disclosed
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
