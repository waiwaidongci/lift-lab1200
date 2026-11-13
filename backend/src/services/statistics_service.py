"""Welch comparison, pooled CUPED and pre-registered pre-revenue stratification.

Stratified mode follows the registration-time cut points: each stratum is
analyzed on its own (Welch, and CUPED with a within-stratum theta), then the
stratum differences are combined with weights equal to each stratum's share of
the *whole* sample (the same weights for both arms). Every stratum result is
kept. When a stratum is missing an arm or has too few samples, it is reported
with a reason and the stratified conclusion is withheld instead of dropping the
stratum or silently reweighting the rest.
"""
import numpy as np
from scipy.stats import t

from ..utils.strata import describe, index_of, labels, validate_bounds


def welch(a, b, alpha):
    if min(len(a), len(b)) < 3:
        raise ValueError("每组至少需要 3 个独立样本")
    va, vb = float(np.var(a, ddof=1)), float(np.var(b, ddof=1))
    se2 = va / len(a) + vb / len(b)
    if se2 <= 1e-14:
        raise ValueError("组内方差为零，不能执行 Welch 检验")
    se = se2 ** .5
    diff = float(np.mean(b) - np.mean(a))
    df = se2 ** 2 / ((va / len(a)) ** 2 / (len(a) - 1) + (vb / len(b)) ** 2 / (len(b) - 1))
    critical = float(t.ppf(1 - alpha / 2, df))
    return {"control_mean": float(np.mean(a)), "treatment_mean": float(np.mean(b)), "difference": diff,
            "standard_error": se, "degrees_of_freedom": df, "p_value": float(2 * t.sf(abs(diff / se), df)),
            "ci_low": diff - critical * se, "ci_high": diff + critical * se,
            "n_control": len(a), "n_treatment": len(b)}


def _stratum(x, y, arms, mask, alpha, use_cuped):
    """Raw and CUPED results inside one stratum, keeping the stratum's own theta."""
    a = mask & (arms == "control")
    b = mask & (arms == "treatment")
    n_control, n_treatment = int(a.sum()), int(b.sum())
    if n_control == 0 or n_treatment == 0:
        missing = "该层无样本" if n_control == n_treatment == 0 else ("缺对照组" if n_control == 0 else "缺候选组")
        return None, None, None, missing, ""
    if min(n_control, n_treatment) < 3:
        return None, None, None, (
            f"样本不足：对照组 {n_control} 人、候选组 {n_treatment} 人（每组至少 3 人）"), ""
    try:
        raw = welch(y[a], y[b], alpha)
    except ValueError as error:
        return None, None, None, str(error), ""
    if not use_cuped:
        return raw, None, None, "", ""
    vx = float(np.var(x[mask], ddof=1))
    if vx <= 1e-14:
        return raw, None, None, "", "层内前置收入为常量，CUPED 无法计算"
    theta = float(np.cov(y[mask], x[mask], ddof=1)[0, 1] / vx)
    transformed = y - theta * (x - np.mean(x[mask]))
    try:
        adjusted = welch(transformed[a], transformed[b], alpha)
    except ValueError as error:
        return raw, None, theta, "", f"层内 CUPED 无法计算：{error}"
    return raw, adjusted, theta, "", ""


def _combine(entries, weights, alpha):
    """Aggregate stratum results: same weights for both arms, variance w^2 * se^2."""
    total = 0.
    mean_control = 0.
    mean_treatment = 0.
    n_control = 0
    n_treatment = 0
    df_denominator = 0.
    for weight, result in zip(weights, entries):
        total += weight * result["difference"]
        mean_control += weight * result["control_mean"]
        mean_treatment += weight * result["treatment_mean"]
        n_control += result["n_control"]
        n_treatment += result["n_treatment"]
        df_denominator += (weight ** 2 * result["standard_error"] ** 2) ** 2 / result["degrees_of_freedom"]
    se2 = sum((weight ** 2 * result["standard_error"] ** 2) for weight, result in zip(weights, entries))
    if se2 <= 1e-14:
        raise ValueError("层内加权标准误为零，不能汇总分层结果")
    se = se2 ** .5
    df = se2 ** 2 / df_denominator
    critical = float(t.ppf(1 - alpha / 2, df))
    return {"control_mean": mean_control, "treatment_mean": mean_treatment, "difference": total,
            "standard_error": se, "degrees_of_freedom": df,
            "p_value": float(2 * t.sf(abs(total / se), df)),
            "ci_low": total - critical * se, "ci_high": total + critical * se,
            "n_control": n_control, "n_treatment": n_treatment}


def _interpret(result, alpha):
    if result["ci_low"] > 0:
        return "区间完全高于零，可供放量会议审议"
    if result["ci_high"] < 0:
        return "区间完全低于零，证据指向负向影响"
    return "证据不足或效果为负，建议保留观察"


def _stratified(observations, x, y, arms, bounds, alpha, use_cuped):
    indices = np.array([index_of(float(value), bounds) for value in x])
    stratum_labels = labels(bounds)
    n_total = len(observations)
    strata = []
    invalid_reasons = []
    cuped_reasons = []
    for index, label in enumerate(stratum_labels):
        mask = indices == index
        weight = float(mask.sum()) / n_total
        raw, adjusted, theta, reason, cuped_reason = _stratum(x, y, arms, mask, alpha, use_cuped)
        if reason:
            invalid_reasons.append(f"{label}：{reason}")
        if cuped_reason:
            cuped_reasons.append(f"{label}：{cuped_reason}")
        strata.append({
            "index": index, "label": label,
            "bound_low": bounds[index - 1] if index > 0 else None,
            "bound_high": bounds[index] if index < len(bounds) else None,
            "n": int(mask.sum()), "n_control": int((mask & (arms == "control")).sum()),
            "n_treatment": int((mask & (arms == "treatment")).sum()),
            "weight": weight, "raw": raw, "cuped": adjusted, "theta": theta,
            "valid": raw is not None and reason == "",
            "reason": reason, "cuped_reason": cuped_reason,
        })
    payload = {
        "enabled": True,
        "bounds": bounds, "labels": stratum_labels,
        "weight_basis": "全体样本各层占比；对照组与候选组使用相同权重",
        "aggregation_basis": "各层独立 Welch；CUPED 在层内估计 θ 与变换；层间按权重汇总，方差按 w²·SE² 合成",
        "n_total": n_total,
        "weights": [item["weight"] for item in strata],
        "strata": strata,
        "combined": None,
        "theta_per_stratum": [item["theta"] for item in strata],
        "variance_reduction": None,
        "valid": False,
        "conclusion_withheld": True,
        "blocked_reasons": invalid_reasons,
        "cuped_blocked_reasons": cuped_reasons,
        "chosen_method": None,
        "significant": None,
        "interpretation": "",
        "conclusion_comparison": None,
    }
    if invalid_reasons:
        payload["interpretation"] = (
            "前置收入分层不可汇总：" + "；".join(invalid_reasons) + "。本次不给出放量结论。")
        return payload
    weights = payload["weights"]
    try:
        combined_raw = _combine([item["raw"] for item in strata], weights, alpha)
    except ValueError as error:
        payload["blocked_reasons"] = [str(error)]
        payload["interpretation"] = f"前置收入分层不可汇总：{error}。本次不给出放量结论。"
        return payload
    combined_cuped = None
    if use_cuped and not cuped_reasons:
        try:
            combined_cuped = _combine([item["cuped"] for item in strata], weights, alpha)
        except ValueError as error:
            cuped_reasons.append(str(error))
    chosen = combined_cuped if combined_cuped is not None else combined_raw
    if use_cuped and combined_cuped is None:
        payload["cuped_blocked_reasons"] = cuped_reasons
    payload.update({
        "combined": {"raw": combined_raw, "cuped": combined_cuped},
        "variance_reduction": (1 - combined_cuped["standard_error"] ** 2 / combined_raw["standard_error"] ** 2)
        if combined_cuped else None,
        "valid": True,
        "chosen_method": "cuped" if use_cuped and combined_cuped is not None else "raw",
        "significant": bool(chosen["p_value"] < alpha),
        "interpretation": _interpret(chosen, alpha),
    })
    payload["conclusion_withheld"] = bool(use_cuped and combined_cuped is None)
    if payload["conclusion_withheld"]:
        # 原始汇总仍保留供追溯，但本次不以任何一种方法给出结论。
        payload["chosen_method"] = None
        payload["significant"] = None
        payload["interpretation"] = (
            "分层校正不可汇总：" + "；".join(cuped_reasons) + "。本次不给出放量结论。")
    return payload


def _comparison(overall, stratified):
    if not stratified.get("valid") or stratified.get("conclusion_withheld"):
        return "分层结论已扣留"
    overall_significant, stratified_significant = overall["significant"], stratified["significant"]
    if not overall_significant and not stratified_significant:
        return "一致"
    if not overall_significant or not stratified_significant:
        return "不一致"
    overall_positive = overall["difference"] > 0
    stratified_positive = stratified["combined"][stratified["chosen_method"]]["difference"] > 0
    return "一致" if overall_positive == stratified_positive else "相反"


def analyze(observations, alpha=.05, use_cuped=True, strata_bounds=None):
    if not 0 < alpha < .5:
        raise ValueError("alpha 必须位于 (0,0.5)")
    if not observations:
        raise ValueError("数据集为空")
    try:
        bounds = validate_bounds(strata_bounds)
    except ValueError as error:
        raise ValueError(f"登记的分层区间无效：{error}")
    x = np.array([o.pre_value for o in observations], dtype=float)
    y = np.array([o.value for o in observations], dtype=float)
    arms = np.array([o.arm for o in observations])
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise ValueError("观测含非有限值")
    if not set(arms).issubset({"control", "treatment"}):
        raise ValueError("存在未知实验分组")
    a = arms == "control"
    b = arms == "treatment"
    raw = welch(y[a], y[b], alpha)
    theta = 0.
    adjusted = None
    reduction = 0.
    if use_cuped:
        vx = float(np.var(x, ddof=1))
        if vx <= 1e-14:
            raise ValueError("前置指标为常量，CUPED 无法计算")
        theta = float(np.cov(y, x, ddof=1)[0, 1] / vx)
        transformed = y - theta * (x - np.mean(x))
        adjusted = welch(transformed[a], transformed[b], alpha)
        reduction = 1 - adjusted["standard_error"] ** 2 / raw["standard_error"] ** 2
    chosen = adjusted or raw
    overall_significant = chosen["p_value"] < alpha
    result = {"raw": raw, "cuped": adjusted, "theta": theta, "variance_reduction": reduction,
              "alpha": alpha, "significant": overall_significant,
              "method": "Welch + pooled CUPED" if use_cuped else "Welch",
              "overall_interpretation": _interpret(chosen, alpha),
              "interpretation_basis": "overall"}
    if bounds is None:
        result["interpretation"] = result["overall_interpretation"]
        result["stratified"] = {
            "enabled": False,
            "bounds": None,
            "reason": "登记时未设置前置收入区间，按原方法复算",
        }
        result["conclusion_comparison"] = None
        result["assumptions"] = ("用户级独立随机分桶；前置变量须在分桶前取得；"
                                 "单一预注册指标，未做多重比较校正")
        return result
    stratified = _stratified(observations, x, y, arms, bounds, alpha, use_cuped)
    result["stratified"] = stratified
    result["conclusion_comparison"] = _comparison(
        {"significant": overall_significant, "difference": chosen["difference"]}, stratified)
    if not stratified["valid"] or stratified["conclusion_withheld"]:
        result["interpretation"] = (
            "整体结果仅供参考；" + stratified["interpretation"])
        result["interpretation_basis"] = "withheld"
        result["significant"] = None
    else:
        result["interpretation"] = stratified["interpretation"]
        result["interpretation_basis"] = "stratified"
        result["significant"] = stratified["significant"]
    result["assumptions"] = (
        f"用户级独立随机分桶；前置变量须在分桶前取得；单一预注册指标，未做多重比较校正。"
        f"前置收入分层区间（登记时固定）：{describe(bounds)}；"
        "层权重取自全体样本各层占比，两组采用相同权重；CUPED 在层内估计 θ；"
        "某层缺组或样本不足时说明原因，且不给出放量结论。")
    return result
