"""Recompute every answer-key figure from the mock data and parameters (W-006).

These are reference implementations of the deterministic tools (merge rule, SLA clock,
rank_causes, derive_requirements, exclusions, parts, options and scores, auto-book check,
verification conditions). The real tools must give the same answers.

Usage (from the repo root): python data/mock-data/validate.py
Exit code 0 when every figure matches answer_key.csv, 1 otherwise.
"""
import csv
import sys
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import yaml

TWO = Decimal("0.01")


def q(x) -> Decimal:
    return Decimal(x).quantize(TWO, rounding=ROUND_HALF_UP)


def read(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def dt(s):
    return datetime.fromisoformat(s)


def iso(d):
    return d.isoformat()


class Data:
    def __init__(self, root: Path):
        s = root / "03_structured"
        k = root / "05_answer_key"
        self.p = yaml.safe_load((root / "04_config" / "parameters.yaml").read_text())
        for name in [
            "install_base", "alarm_map", "fault_causes", "skill_matrix", "parts", "technicians",
            "certificates", "bookings", "travel_matrix", "van_stock", "depot_stock",
            "service_history", "maintenance_intervals", "bulletins", "agreement_register",
            "telemetry_series", "telemetry_readings_pre", "telemetry_readings_post",
        ]:
            setattr(self, name, read(s / f"{name}.csv"))
        self.facts = read(k / "agreement_facts.csv")
        self.extractions = read(k / "expected_extractions.csv")
        self.evidence = read(k / "expected_evidence.csv")
        self.answers = read(k / "answer_key.csv")
        self.travel = {(r["from_loc"], r["to_loc"]): int(r["minutes"]) for r in self.travel_matrix}


def merge(d: Data):
    """BR-002: same asset + fault family within MERGE_WINDOW (inclusive)."""
    window = timedelta(minutes=d.p["merge_window_min"])
    reports = sorted(d.extractions, key=lambda r: dt(r["received_at"]))
    tickets = []
    for r in reports:
        for t in tickets:
            first = t[0]
            if (r["asset_id"] == first["asset_id"] and r["fault_family"] == first["fault_family"]
                    and dt(r["received_at"]) - dt(first["received_at"]) <= window):
                t.append(r)
                break
        else:
            tickets.append([r])
    return tickets


def entitlement(d: Data, asset_id, report_time):
    """BR-003: the latest document in effect at the report date that mentions the asset."""
    report_day = report_time.date()
    reg = {r["doc_id"]: r for r in d.agreement_register}
    candidates = [
        f for f in d.facts
        if f["asset_id"] == asset_id
        and date.fromisoformat(reg[f["doc_id"]]["effective_from"]) <= report_day
    ]
    gov = max(candidates, key=lambda f: reg[f["doc_id"]]["effective_from"])
    return gov["doc_id"], gov["schedule"], int(gov["response_hours"])


def breaches(rows, series, low, high):
    """Count contiguous runs of readings outside [low, high]."""
    count, inside = 0, False
    for r in rows:
        if r["series_id"] != series:
            continue
        out = not (low <= float(r["value"]) <= high)
        if out and not inside:
            count += 1
        inside = out
    return count


def band(d: Data, series):
    s = next(x for x in d.telemetry_series if x["series_id"] == series)
    return float(s["band_low"]), float(s["band_high"])


def months_between(a: date, b: date):
    m = (b.year - a.year) * 12 + (b.month - a.month)
    return m - (1 if b.day < a.day - 1 else 0)


def rank_causes(d: Data, model, family):
    weights = {k: Decimal(v) for k, v in d.p["likelihood"]["evidence_weights"].items()}
    raw = {}
    for c in d.fault_causes:
        if c["model"] == model and c["fault_family"] == family:
            raw[c["cause_id"]] = Decimal(c["prior"])
    for e in d.evidence:
        if e["status"] == d.p["likelihood"]["counted_status"]:
            raw[e["cause_id"]] += weights[e["evidence_type"]]
    total = sum(raw.values())
    lik = {k: q(v / total) for k, v in raw.items()}
    ordered = sorted(lik, key=lambda k: lik[k], reverse=True)
    margin = Decimal(d.p["cause_margin"])
    top = lik[ordered[0]]
    separable = (top - lik[ordered[1]]) >= margin
    contention = [c for c in ordered if top - lik[c] < margin]
    return lik, separable, contention


def requirements(d: Data, family, contention):
    rows = [r for r in d.skill_matrix if r["fault_family"] == family and r["cause_id"] in contention]
    level = max(int(r["min_level"]) for r in rows)
    certs = sorted({r["certificate"] for r in rows})
    parts = set()
    for c in d.fault_causes:
        if c["cause_id"] in contention and c["likely_parts"]:
            parts.update(c["likely_parts"].split(";"))
    return level, certs, sorted(parts)


def stock(rows, key, holder):
    return {r["part_no"] for r in rows if r[key] == holder and int(r["qty"]) > 0}


def options(d: Data, site, deadline, run_at, level, certs, parts):
    visit_day = run_at.date()
    consumables = {p["part_no"] for p in d.parts if p["consumable"] == "Y"}
    needed = set(parts) - consumables
    excluded, opts = {}, []
    sc = d.p["scoring"]
    scale = Decimal(sc["scale_min"])
    w = {k: Decimal(v) for k, v in sc["weights"].items()}

    def score(drive, slack, fit, tech_level):
        travel = q(max(Decimal(0), 1 - Decimal(drive) / scale))
        sl = q(0) if slack < 0 else q(min(Decimal(1), Decimal(slack) / scale))
        pf = q(sc["parts_fit"][fit])
        sk = q(sc["skill_margin"]["one_or_more_above" if tech_level > level else "at_required"])
        total = q(travel * w["travel"] + sl * w["slack"] + pf * w["parts"] + sk * w["skill"])
        return {"c_travel": travel, "c_slack": sl, "c_parts": pf, "c_skill": sk, "total": total}

    for t in d.technicians:
        tid, tl = t["tech_id"], int(t["refrigeration_level"])
        held = {c["certificate"]: date.fromisoformat(c["expires_on"]) for c in d.certificates if c["tech_id"] == tid}
        if any(c not in held or held[c] < visit_day for c in certs):
            excluded[tid] = "CERT_EXPIRED"
            continue
        if tl < level:
            excluded[tid] = "SKILL_BELOW_REQUIRED"
            continue
        locked = [b for b in d.bookings if b["tech_id"] == tid and b["locked"] == "true"
                  and dt(b["start"]) <= run_at + timedelta(hours=8) and dt(b["end"]) > run_at]
        if locked:
            b = locked[0]
            start_loc, start_at, kind = b["site_id"], dt(b["end"]), "after"
        else:
            start_loc, start_at, kind = t["home_base"], run_at, "direct"
        van = stock(d.van_stock, "van_id", t["van_id"])
        drive = d.travel[(start_loc, site)]
        arrival = start_at + timedelta(minutes=drive)
        fit = "full" if needed <= van else ("partial" if needed & van or consumables & set(parts) else "none")
        slack = int((deadline - arrival).total_seconds() // 60)
        opts.append({"id": f"{tid}_{kind}", "arrival": arrival, "fit": fit, "slack": slack,
                     "drive": drive, **score(drive, slack, fit, tl)})
        if fit != "full":
            for dep in sorted({r["depot_id"] for r in d.depot_stock}):
                if not (needed - van) <= stock(d.depot_stock, "depot_id", dep):
                    continue
                via = d.travel[(start_loc, dep)] + d.travel[(dep, site)]
                detour = via - drive
                if detour > d.p["depot_detour_max_min"]:
                    continue
                arr = start_at + timedelta(minutes=via + d.p["depot_handling_min"])
                sl = int((deadline - arr).total_seconds() // 60)
                opts.append({"id": f"{tid}_{dep}", "arrival": arr, "fit": "full", "slack": sl,
                             "drive": via, "detour": detour, **score(via, sl, "full", tl)})
    opts.sort(key=lambda o: o["total"], reverse=True)
    return excluded, opts


def autobook(d: Data, separable, opts, safety=False):
    codes = []
    if not separable:
        codes.append("CAUSES_NOT_SEPARABLE")
    qualifying = [o for o in opts if o["fit"] == "full" and o["slack"] >= d.p["slack_min"]]
    if not qualifying:
        codes.append("NO_FULL_FIT_WITH_MIN_SLACK")
    elif qualifying[0]["total"] < Decimal(d.p["auto_book_score"]):
        codes.append("SCORE_BELOW_THRESHOLD")
    if safety:
        codes.append("SAFETY_CRITICAL")
    return not codes, codes


def max_gap(rows, series):
    times = [dt(r["ts"]) for r in rows if r["series_id"] == series]
    return int(max((b - a).total_seconds() for a, b in zip(times, times[1:])) // 60)


def compute(d: Data):
    tz_run = dt(f'{d.p["demo"]["date"]}T{d.p["demo"]["run_time"]}:00{d.p["demo"]["utc_offset"]}')
    out = {}
    tickets = merge(d)
    t = tickets[0]
    out["tickets_after_merge"] = len(tickets)
    out["merged_reports"] = ";".join(r["report_id"] for r in t)
    clock = min(dt(r["received_at"]) for r in t)
    out["clock_start"] = iso(clock)
    asset = t[0]["asset_id"]
    gov, sched, hours = entitlement(d, asset, clock)
    out["governing_document"], out["schedule"], out["sla_hours"] = gov, sched, hours
    deadline = clock + timedelta(hours=hours)
    out["deadline"] = iso(deadline)

    lo, hi = band(d, "CU2-FC")
    out["fan_current_breaches_pre"] = breaches(d.telemetry_readings_pre, "CU2-FC", lo, hi)
    last_clean = max(dt(h["closed_at"]).date() for h in d.service_history
                     if h["asset_id"] == asset and "COIL-CLN" in h["parts_used"])
    months = months_between(last_clean, tz_run.date())
    interval = next(int(m["interval_months"]) for m in d.maintenance_intervals if m["task"] == "Condenser coil clean")
    out["coil_clean_months_since"] = months
    out["coil_clean_overdue"] = str(months > interval).lower()

    model = next(a["model"] for a in d.install_base if a["asset_id"] == asset)
    family = t[0]["fault_family"]
    lik, separable, contention = rank_causes(d, model, family)
    for c, v in lik.items():
        out[f"likelihood_{c}"] = str(v)
    out["separable"] = str(separable).lower()
    out["causes_in_contention"] = ";".join(contention)
    level, certs, parts = requirements(d, family, contention)
    out["required_level"] = level
    out["required_certificate"] = ";".join(certs)
    out["likely_parts"] = ";".join(parts)

    site = next(a["site_id"] for a in d.install_base if a["asset_id"] == asset)
    excluded, opts = options(d, site, deadline, tz_run, level, certs, parts)
    out["excluded"] = ";".join(f"{k}:{v}" for k, v in sorted(excluded.items()))
    out["option_count"] = len(opts)
    names = {"T1_direct": "T1_direct", "T1_D2": "T1_D2", "T4_after": "T4_after"}
    for o in opts:
        key = names.get(o["id"], o["id"])
        out[f"opt_{key}_arrival"] = iso(o["arrival"])
        out[f"opt_{key}_parts_fit"] = o["fit"]
        out[f"opt_{key}_slack"] = o["slack"]
        out[f"opt_{key}_score"] = str(o["total"])
        if "detour" in o:
            out[f"opt_{key}_detour"] = o["detour"]
    out["option_order"] = ";".join(o["id"] for o in opts)
    booked, codes = autobook(d, separable, opts)
    out["auto_book"] = str(booked).lower()
    out["reason_codes"] = ";".join(codes)

    v_start = datetime(2026, 12, 1, 14, 5).replace(tzinfo=clock.tzinfo)
    v_end = v_start + timedelta(minutes=d.p["verify_window_min"])
    out["verify_window"] = f"{iso(v_start)}/{iso(v_end)}"
    plo, phi = band(d, "CU2-DP")
    post = d.telemetry_readings_post
    p_ok = breaches(post, "CU2-DP", plo, phi) == 0
    f_breaches = breaches(post, "CU2-FC", lo, hi)
    gap = max(max_gap(post, "CU2-DP"), max_gap(post, "CU2-FC"))
    out["pressure_in_band_post"] = str(p_ok).lower()
    out["fan_current_breaches_post"] = f_breaches
    out["max_gap_post_min"] = gap
    if gap > d.p["telemetry_gap_max_min"]:
        verdict = "insufficient_evidence"
    elif p_ok and f_breaches == 0:
        verdict = "verified"
    else:
        verdict = "not_verified"
    out["verdict"] = verdict
    return out, opts


def main(root: Path):
    d = Data(root)
    got, opts = compute(d)
    fails = 0
    print(f"{'id':6} {'figure':28} {'expected':45} {'computed':45} ok")
    for a in d.answers:
        c = str(got.get(a["figure"], "<missing>"))
        ok = c == a["expected"]
        fails += not ok
        print(f"{a['id']:6} {a['figure']:28} {a['expected'][:45]:45} {c[:45]:45} {'OK' if ok else 'FAIL'}")
    print("\nOption table:")
    for o in opts:
        print(f"  {o['id']:10} arrival {o['arrival'].strftime('%H:%M')}  fit {o['fit']:7}  slack {o['slack']:4} min  "
              f"| travel {o['c_travel']}  slack {o['c_slack']}  parts {o['c_parts']}  skill {o['c_skill']}  "
              f"= {o['total']}")
    print(f"\n{len(d.answers) - fails}/{len(d.answers)} figures match")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parent))
