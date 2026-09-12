"""
backend/benchmarks/calibration.py

Confidence Calibration and Reliability Curve Analysis for HotChords.
Evaluates the relationship between model-reported confidence scores and empirical correctness:
- Standard confidence binning (0.0-0.49, 0.50-0.59, 0.60-0.69, 0.70-0.79, 0.80-0.89, 0.90-1.00)
- Expected Calibration Error (ECE)
- Maximum Calibration Error (MCE)
- Brier Score calculation
- Transparent calibration reporting
"""

from typing import List, Dict, Any, Tuple
import numpy as np


def compute_calibration_curve(
    confidences: List[float],
    accuracies: List[bool],
    bins: List[Tuple[float, float]] = None,
    min_samples_for_calibration: int = 1000
) -> Dict[str, Any]:
    """
    Computes empirical accuracy within confidence bins and calculates ECE / MCE / Brier Score.
    Strictly flags INSUFFICIENT_GROUND_TRUTH when sample size is insufficient to prevent
    misleading statistical claims.
    """
    if bins is None:
        bins = [
            (0.00, 0.49),
            (0.50, 0.59),
            (0.60, 0.69),
            (0.70, 0.79),
            (0.80, 0.89),
            (0.90, 1.00)
        ]

    if not confidences or not accuracies or len(confidences) != len(accuracies):
        return {
            "is_calibrated": False,
            "confidence_calibration_status": "INSUFFICIENT_GROUND_TRUTH",
            "total_samples": 0,
            "ece": 0.0,
            "mce": 0.0,
            "brier_score": 0.0,
            "bins": []
        }

    conf_arr = np.array(confidences, dtype=float)
    acc_arr = np.array(accuracies, dtype=bool)
    n_total = len(conf_arr)

    bin_results = []
    ece = 0.0
    mce = 0.0

    for (b_low, b_high) in bins:
        # Include upper boundary on the last bin
        if b_high >= 1.0:
            mask = (conf_arr >= b_low) & (conf_arr <= b_high)
        else:
            mask = (conf_arr >= b_low) & (conf_arr < b_high)

        count = int(np.sum(mask))
        if count > 0:
            bin_acc = float(np.mean(acc_arr[mask]))
            bin_conf = float(np.mean(conf_arr[mask]))
            calibration_gap = abs(bin_acc - bin_conf)
            ece += (count / n_total) * calibration_gap
            mce = max(mce, calibration_gap)
        else:
            bin_acc = 0.0
            bin_conf = (b_low + b_high) / 2.0
            calibration_gap = 0.0

        bin_results.append({
            "range": f"{b_low:.2f}-{b_high:.2f}",
            "count": count,
            "mean_confidence": round(bin_conf, 4),
            "empirical_accuracy": round(bin_acc, 4),
            "calibration_gap": round(calibration_gap, 4),
        })

    # Brier score: MSE between confidence probability and binary outcome
    brier_score = float(np.mean((conf_arr - acc_arr.astype(float)) ** 2))

    # Declare calibration status
    status = "CALIBRATED" if n_total >= min_samples_for_calibration else "INSUFFICIENT_GROUND_TRUTH"

    return {
        "is_calibrated": (status == "CALIBRATED"),
        "confidence_calibration_status": status,
        "total_samples": n_total,
        "ece": round(float(ece), 4),
        "mce": round(float(mce), 4),
        "brier_score": round(brier_score, 4),
        "bins": bin_results,
        "notes": (
            "Calibration represents heuristic reliability alignment. In the absence of massive "
            "independent multi-track ground truth, confidence scores must not be treated as true Bayesian posterior probabilities."
        )
    }
