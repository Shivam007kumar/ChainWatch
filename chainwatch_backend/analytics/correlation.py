import math
from collections import defaultdict
from datetime import datetime
from config import settings

def _parse_ts(ts):
    if isinstance(ts, (int, float)):
        return float(ts)
    try:
        return datetime.fromisoformat(str(ts)).timestamp()
    except Exception:
        return 0.0

def correlate_captures(network_captures: list[dict]) -> list[dict]:
    """
    Input: list of {txid, src_ip, timestamp} from network_capture table.
    Output: list of {txid, src_ip, confidence, delta_seconds} — candidate IPs kept,
    scored by proximity to the earliest observed capture for that txid.
    confidence = exp(-delta / tau), delta = |t - earliest_t|
    Only captures within CORRELATION_WINDOW_SECONDS of the earliest are considered
    genuine candidates; anything beyond the window is dropped as noise (unrelated
    late relay / clock skew beyond plausibility), not scored near-zero.
    """
    by_txid = defaultdict(list)
    for c in network_captures:
        by_txid[c["txid"]].append({**c, "_ts": _parse_ts(c["timestamp"])})
        
    results = []
    for txid, captures in by_txid.items():
        if not captures:
            continue
        earliest_ts = min(c["_ts"] for c in captures)
        for c in captures:
            delta = abs(c["_ts"] - earliest_ts)
            if delta > settings.correlation_window_seconds:
                continue  # outside window, not a credible candidate broadcaster
            confidence = round(math.exp(-delta / settings.correlation_tau), 4)
            results.append({
                "txid": txid,
                "src_ip": c["src_ip"],
                "confidence": confidence,
                "delta_seconds": round(delta, 2),
            })
    return results
