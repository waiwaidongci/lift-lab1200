"""Guards for the stratified analysis contract.

Covers: whole-sample weights used identically for both arms, per-stratum CUPED
theta, retained stratum results, withheld conclusions on missing/short strata,
overall-vs-stratified disagreement samples, legacy (NULL bounds) recomputation,
and export traceability.

Run from backend/:  python3 -m scripts.check_strata
"""
import csv, io, math, random
import numpy as np
from src.services.statistics_service import analyze, welch
from src.services.run_service import export_run
from src.utils.strata import validate_bounds, labels, index_of, describe


class Row:
    def __init__(self, subject, arm, pre_value, value):
        self.subject, self.arm = subject, arm
        self.pre_value, self.value = pre_value, value


def dataset(seed=7, n=2400, effect=0., pre="normal"):
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        arm = "control" if i % 2 == 0 else "treatment"
        if pre == "bimodal":
            x = rng.gauss(12, 3) if i % 4 < 2 else rng.gauss(70, 6)
        else:
            x = rng.gauss(36, 12)
        x = max(.1, x)
        gain = effect
        if pre == "bimodal" and i % 4 < 2: gain = 0.
        y = max(0, 7 + .65 * x + rng.gauss(0, 7) + gain)
        rows.append(Row(f"U-{i:05}", arm, round(x, 4), round(y, 4)))
    return rows


def close(a, b, tolerance=1e-9):
    return math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance)


def test_weights_equal_whole_sample_share():
    rows = dataset(pre="bimodal", effect=2.8)
    result = analyze(rows, .05, True, [30, 60])
    stratified = result["stratified"]
    assert stratified["enabled"] and stratified["valid"]
    total = len(rows)
    counts = [sum(1 for r in rows if index_of(r.pre_value, [30, 60]) == i) for i in range(3)]
    assert [item["n"] for item in stratified["strata"]] == counts
    assert all(close(w, c / total) for w, c in zip(stratified["weights"], counts))
    assert close(sum(stratified["weights"]), 1.)
    for item, weight in zip(stratified["strata"], stratified["weights"]):
        assert close(weight, item["weight"])
    combined = stratified["combined"]["raw"]
    check = sum(weight * item["raw"]["difference"] for weight, item in zip(stratified["weights"], stratified["strata"]))
    assert close(combined["difference"], check)
    # Same weights for both arms: aggregated means use the same share weights.
    check_control = sum(weight * item["raw"]["control_mean"] for weight, item in zip(stratified["weights"], stratified["strata"]))
    check_treatment = sum(weight * item["raw"]["treatment_mean"] for weight, item in zip(stratified["weights"], stratified["strata"]))
    assert close(combined["control_mean"], check_control)
    assert close(combined["treatment_mean"], check_treatment)
    assert all(item["weight"] == stratified["weights"][i] for i, item in enumerate(stratified["strata"]))


def test_within_stratum_correction_and_retained_strata():
    rows = dataset(pre="bimodal", effect=2.8)
    pooled = analyze([r for r in rows], .05, True, None)
    result = analyze(rows, .05, True, [30, 60])
    stratified = result["stratified"]
    assert result["raw"] == pooled["raw"] and result["cuped"] == pooled["cuped"]
    assert stratified["theta_per_stratum"] != [result["theta"]] * len(stratified["strata"])
    for item in stratified["strata"]:
        sub = [r for r in rows if index_of(r.pre_value, [30, 60]) == item["index"]]
        expected_raw = welch(np.array([r.value for r in sub if r.arm == "control"]),
                             np.array([r.value for r in sub if r.arm == "treatment"]), .05)
        assert item["raw"]["difference"] == expected_raw["difference"]
        assert item["raw"]["p_value"] == expected_raw["p_value"]
        if item["cuped"] is not None:
            x = np.array([r.pre_value for r in sub]); y = np.array([r.value for r in sub])
            theta = float(np.cov(y, x, ddof=1)[0, 1] / np.var(x, ddof=1))
            assert close(item["theta"], theta)
    # Bounds recorded exactly as registered, labels are derived from them.
    assert stratified["bounds"] == [30.0, 60.0]
    assert labels([30, 60]) == ["< 30", "[30, 60)", "≥ 60"]


def test_missing_arm_withholds_conclusion():
    rows = [r for r in dataset(pre="bimodal", effect=2.8) if not (r.arm == "treatment" and r.pre_value < 30)]
    result = analyze(rows, .05, True, [30, 60])
    stratified = result["stratified"]
    assert stratified["valid"] is False and stratified["conclusion_withheld"] is True
    assert stratified["chosen_method"] is None and stratified["significant"] is None
    blocked = stratified["strata"][0]
    assert blocked["valid"] is False and "缺候选组" in blocked["reason"]
    assert any("缺候选组" in reason for reason in stratified["blocked_reasons"])
    assert "不给出放量结论" in result["interpretation"]
    assert result["interpretation_basis"] == "withheld"
    # The overall result is still retained for reference.
    assert result["raw"]["n_treatment"] > 0


def test_small_stratum_withholds_conclusion():
    rows = [r for r in dataset(pre="bimodal", effect=2.8) if not (r.arm == "control" and 30 <= r.pre_value < 60)]
    rows = [r for r in rows if index_of(r.pre_value, [30, 60]) != 1] + [
        Row("S-1", "control", 45., 30.), Row("S-2", "treatment", 46., 33.)]
    result = analyze(rows, .05, True, [30, 60])
    assert result["stratified"]["valid"] is False
    small = result["stratified"]["strata"][1]
    assert "样本不足" in small["reason"] and small["n_control"] == 1


def test_legacy_recomputes_with_original_method():
    rows = dataset(effect=2.8)
    legacy = analyze(rows, .05, True, None)
    assert legacy["stratified"]["enabled"] is False
    assert legacy["stratified"]["bounds"] is None
    assert legacy["interpretation_basis"] == "overall"
    assert legacy["interpretation"] == legacy["overall_interpretation"]
    assert legacy["conclusion_comparison"] is None
    assert legacy["theta"] != 0 and legacy["cuped"] is not None


def test_overall_and_stratified_disagree():
    """Simpson-style sample: the whole-sample difference is positive because the
    candidate arm is concentrated in the high pre-revenue stratum, while every
    stratum shows the same small negative effect."""
    rows = []
    rng = random.Random(11)

    def add(prefix, arm, pre, value, count):
        for i in range(count):
            rows.append(Row(f"{prefix}-{i:05}", arm, pre + rng.gauss(0, 1), value + rng.gauss(0, 1.5)))

    add("CL", "control", 12., 20., 1000)
    add("TL", "treatment", 12., 17., 300)
    add("CM", "control", 38., 35., 300)
    add("TM", "treatment", 38., 32., 300)
    add("CH", "control", 70., 50., 300)
    add("TH", "treatment", 70., 47., 1000)
    # Registered without CUPED so the comparison is pooled raw vs stratum-weighted raw.
    result = analyze(rows, .05, False, [25, 55])
    overall = result["raw"]
    assert overall["ci_low"] > 0, "fixture must show a whole-sample positive effect"
    stratified = result["stratified"]
    assert stratified["valid"]
    assert result["conclusion_comparison"] == "相反", result["conclusion_comparison"]
    for item in stratified["strata"]:
        assert item["raw"]["difference"] < 0
    assert stratified["combined"]["raw"]["difference"] < 0
    assert stratified["combined"]["raw"]["ci_high"] < 0
    assert stratified["significant"] is True
    assert result["interpretation_basis"] == "stratified"
    assert result["interpretation"] == "区间完全低于零，证据指向负向影响"


def test_stratum_cuped_stays_inside_stratum():
    """A stratum's CUPED result (explicitly closing the correction) keeps the
    stratum's original Welch values, and the export states both."""
    rows = dataset(pre="bimodal", effect=2.8)
    off = analyze(rows, .05, False, [30, 60])
    on = analyze(rows, .05, True, [30, 60])
    for off_item, on_item in zip(off["stratified"]["strata"], on["stratified"]["strata"]):
        assert off_item["raw"] == on_item["raw"]
        assert on_item["theta"] is not None
    assert off["cuped"] is None and off["stratified"]["combined"]["cuped"] is None
    assert off["variance_reduction"] == 0.
    assert off["stratified"]["chosen_method"] == "raw"


def test_layer_cuped_failure_withholds_conclusion():
    rows = []
    rng = random.Random(2)
    for i in range(100):
        arm = "control" if i % 4 < 2 else "treatment"
        rows.append(Row(f"L-{i}", arm, 10., 20. + rng.gauss(0, 3)))
    for i in range(200):
        arm = "control" if i % 2 == 0 else "treatment"
        rows.append(Row(f"H-{i}", arm, 50. + rng.gauss(0, 3), 30. + rng.gauss(0, 5)))
    result = analyze(rows, .05, True, [30])
    stratified = result["stratified"]
    assert stratified["valid"] is True
    assert stratified["strata"][0]["cuped"] is None
    assert "常量" in stratified["strata"][0]["cuped_reason"]
    assert stratified["conclusion_withheld"] is True and stratified["chosen_method"] is None
    assert stratified["combined"]["raw"] is not None and stratified["combined"]["cuped"] is None
    assert result["significant"] is None and result["interpretation_basis"] == "withheld"
    assert "不给出放量结论" in result["interpretation"]


def test_bounds_validation():
    for bad in ([30, 30], [40, 30], [30, True], [float("nan")], [30, float("inf")], []):
        try:
            validate_bounds(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted invalid bounds {bad}")
    assert validate_bounds(None) is None
    assert describe([30, 60]) == "< 30 / [30, 60) / ≥ 60 元"


def test_export_traceability():
    rows = dataset(pre="bimodal", effect=2.8)
    result = analyze(rows, .05, True, [30, 60])
    class Run:
        id = 1; status = "completed"; experiment_id = 1
        error = ""; created_at = "2026-11-13T00:00:00+00:00"
    Run.result = result
    class Db:
        def get(self, model, rid): return Run()
    text = export_run(Db(), 1)
    table = list(csv.reader(io.StringIO(text)))
    flat = [row for row in table if row]
    assert any(row[0] == "strata_bounds" and row[1] == "30/60" for row in flat)
    assert any(row[0] == "strata_weight_basis" for row in flat)
    assert any(row[0] == "strata_aggregation_basis" for row in flat)
    assert any(row[0] == "conclusion_comparison" for row in flat)
    assert any(row[0] == "stratum" and "weight" in row for row in flat)
    labels_seen = {row[0] for row in flat if row[0] in labels([30, 60])}
    assert set(labels([30, 60])).issubset(labels_seen)
    # Invalid stratum reasons surface in the export.
    bad_rows = [r for r in rows if not (r.arm == "treatment" and r.pre_value < 30)]
    bad = analyze(bad_rows, .05, True, [30, 60])
    Run.result = bad
    text = export_run(Db(), 1)
    assert "缺候选组" in text and "strata_conclusion_withheld" in text


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} checks passed")


if __name__ == "__main__":
    main()
