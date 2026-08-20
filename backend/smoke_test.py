"""smoke_test.py — end-to-end check of the ClauseGuard API against a live backend.

Exercises the full path: upload → list → detail → analyze → detail → delete,
asserting the response shape at every step. Requires a running backend and a
reachable database; the AI analysis step is skipped automatically when no
OPENAI_API_KEY is configured.

USAGE
-----
    # terminal 1
    docker compose up -d
    uvicorn main:app --port 8000

    # terminal 2
    python smoke_test.py
    python smoke_test.py --base-url http://127.0.0.1:8000
    python smoke_test.py --keep          # don't delete the contract at the end

Exits non-zero on the first failure.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

import fitz
import httpx

CLAUSES = [
    "FREELANCE SERVICE AGREEMENT",
    "1. SCOPE OF WORK. The Contractor shall provide web development services "
    "including design, implementation and deployment of the Client's marketing "
    "website. Deliverables are listed in Exhibit A.",
    "2. PAYMENT TERMS. The Client shall pay the Contractor a fixed fee of USD "
    "12,000, invoiced in three equal instalments, each payable net 60 days.",
    "3. INTELLECTUAL PROPERTY. The Contractor hereby irrevocably assigns to the "
    "Client all right, title and interest in all work product and inventions "
    "created during the engagement, whether or not related to the Deliverables.",
    "4. CONFIDENTIALITY. The Contractor shall hold all proprietary information "
    "of the Client in strict confidence in perpetuity.",
    "5. LIABILITY. The Contractor shall indemnify and hold harmless the Client "
    "from any and all claims and damages, without limitation as to amount.",
    "6. TERMINATION. The Client may terminate for convenience upon zero days "
    "notice with no obligation to pay for work in progress.",
    "7. GOVERNING LAW. This Agreement is governed by the laws of Delaware, with "
    "exclusive jurisdiction in Wilmington and a waiver of jury trial.",
]

_passed = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global _passed
    if condition:
        _passed += 1
        print(f"  PASS  {label}")
        return
    print(f"  FAIL  {label}")
    if detail:
        print(f"        {detail}")
    sys.exit(1)


def build_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(
        fitz.Rect(56, 56, 556, 780),
        "\n\n".join(CLAUSES),
        fontsize=9.5,
        fontname="helv",
        lineheight=1.35,
    )
    data: bytes = doc.tobytes()
    doc.close()
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="ClauseGuard API smoke test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--keep", action="store_true", help="Skip the delete step.")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    # Analysis is one LLM round-trip per clause and runs synchronously.
    client = httpx.Client(base_url=base, timeout=300.0)

    print(f"\nClauseGuard smoke test against {base}\n")

    # --- health -----------------------------------------------------------
    print("[1] GET /api/health")
    res = client.get("/api/health")
    check("responds 200", res.status_code == 200, res.text[:200])
    health: dict[str, Any] = res.json()
    check(
        "database reachable",
        health.get("database") == "ok",
        f"database={health.get('database')} — is Postgres running? docker compose up -d",
    )
    llm_ready = bool(health.get("llm_configured"))
    print(f"        llm_configured={llm_ready} ({health.get('provider')}/{health.get('model')})")

    # --- upload -----------------------------------------------------------
    print("\n[2] POST /api/contracts/upload")
    res = client.post(
        "/api/contracts/upload",
        files={"file": ("smoke_contract.pdf", build_pdf(), "application/pdf")},
    )
    check("responds 200", res.status_code == 200, res.text[:300])
    upload = res.json()
    check("status is success", upload.get("status") == "success", res.text[:300])
    check("contract_id present", bool(upload.get("contract_id")))

    clauses = upload.get("parsed_clauses") or []
    check("more than one clause extracted", len(clauses) > 1, f"got {len(clauses)}")
    required = {
        "parsed_clause_id", "contract_id", "clause_index",
        "raw_text", "clause_type", "clause_type_confidence",
    }
    check(
        "clause objects carry every contract field",
        required.issubset(clauses[0].keys()),
        f"missing {required - set(clauses[0].keys())}",
    )
    check(
        "clause_index is 1-based and monotonic",
        [c["clause_index"] for c in clauses] == list(range(1, len(clauses) + 1)),
    )
    contract_id = upload["contract_id"]
    print(f"        contract_id={contract_id}, {len(clauses)} clauses")
    for clause in clauses:
        print(f"          #{clause['clause_index']:<2} {clause['clause_type']}")

    # --- oversized upload is refused --------------------------------------
    print("\n[3] POST /api/contracts/upload (11 MB)")
    res = client.post(
        "/api/contracts/upload",
        files={"file": ("too_big.pdf", b"\0" * (11 * 1024 * 1024), "application/pdf")},
    )
    check("responds 413", res.status_code == 413, f"got {res.status_code}")
    check("error envelope preserved", res.json().get("parsed_clauses") == [])

    # --- list -------------------------------------------------------------
    print("\n[4] GET /api/contracts")
    res = client.get("/api/contracts")
    check("responds 200", res.status_code == 200, res.text[:200])
    listing = res.json()
    match = next((c for c in listing["contracts"] if c["id"] == contract_id), None)
    check("new contract appears in the list", match is not None)
    assert match is not None
    check("clause_count matches upload", match["clause_count"] == len(clauses))
    check("has_analysis is False before analysis", match["has_analysis"] is False)

    # --- detail before analysis -------------------------------------------
    print("\n[5] GET /api/contracts/{id} (before analysis)")
    res = client.get(f"/api/contracts/{contract_id}")
    check("responds 200", res.status_code == 200, res.text[:200])
    detail = res.json()
    check("all clauses returned", len(detail["clauses"]) == len(clauses))
    check(
        "risk fields are null before analysis",
        all(c["risk_level"] is None for c in detail["clauses"]),
    )
    check(
        "unanalyzed bucket holds every clause",
        detail["risk_distribution"]["unanalyzed"] == len(clauses),
    )

    # --- analyze ----------------------------------------------------------
    print("\n[6] POST /api/contracts/{id}/analyze (asynchronous run)")
    res = client.post(f"/api/contracts/{contract_id}/analyze")

    if not llm_ready:
        check(
            "responds 503 when no LLM is configured",
            res.status_code == 503,
            f"got {res.status_code}: {res.text[:200]}",
        )
        print("        Skipping analysis assertions — set a real OPENAI_API_KEY (or")
        print("        DSPY_PROVIDER=fake) to exercise the pipeline end to end.")
    else:
        check("responds 202", res.status_code == 202, res.text[:400])
        run = res.json()["run"]
        run_id = run["id"]
        check("run is scheduled", run["status"] in ("pending", "running"), run["status"])

        # A second analyze while one is active must be refused.
        res = client.post(f"/api/contracts/{contract_id}/analyze")
        check("concurrent analyze responds 409", res.status_code == 409, res.text[:200])

        # Poll the run to completion — this is exactly what the frontend does.
        deadline = time.time() + 180
        status = run["status"]
        while time.time() < deadline and status in ("pending", "running"):
            time.sleep(0.5)
            res = client.get(f"/api/analysis-runs/{run_id}")
            check("run poll responds 200", res.status_code == 200, res.text[:200])
            run = res.json()["run"]
            status = run["status"]
        check("run completed", status == "completed", f"status={status}, err={run.get('error_message')}")
        check(
            "progress reached every clause",
            run["completed_clauses"] == len(clauses),
            f"{run['completed_clauses']}/{len(clauses)}",
        )
        check("processing time recorded", isinstance(run["processing_time_ms"], int))
        print(
            f"        run completed in {run['processing_time_ms']}ms — "
            f"metadata={run.get('run_metadata')}"
        )

        print("\n[7] GET /api/contracts/{id} (after analysis)")
        res = client.get(f"/api/contracts/{contract_id}")
        check("responds 200", res.status_code == 200)
        detail = res.json()
        check("has_analysis is now True", detail["has_analysis"] is True)
        check(
            "every clause has a risk level",
            all(c["risk_level"] in ("high", "medium", "low") for c in detail["clauses"]),
        )
        check(
            "every clause has a plain-language summary",
            all(c["plain_language_summary"] for c in detail["clauses"]),
        )
        check(
            "risk_factors deserialize as lists",
            all(isinstance(c["risk_factors"], list) for c in detail["clauses"]),
        )
        check(
            "distribution buckets sum to the clause count",
            sum(detail["risk_distribution"].values()) == len(clauses),
        )
        check(
            "latest_run is reported on the detail view",
            detail.get("latest_run", {}).get("id") == run_id,
        )
        for clause in detail["clauses"]:
            print(
                f"          #{clause['clause_index']:<2} {clause['risk_level']:<7} "
                f"{clause['risk_score']:<5} {clause['plain_language_summary'][:52]}..."
            )

        print("\n[8] POST analyze again (content-hash cache, wait=true)")
        res = client.post(f"/api/contracts/{contract_id}/analyze?wait=true")
        check("responds 202", res.status_code == 202, res.text[:200])
        rerun = res.json()["run"]
        check("cached re-run completed synchronously", rerun["status"] == "completed", rerun["status"])
        meta = rerun.get("run_metadata") or {}
        check(
            "every clause served from cache",
            meta.get("cached_clauses") == len(clauses),
            f"metadata={meta}",
        )
        check(
            "no clause re-billed",
            meta.get("analyzed_clauses") == 0,
            f"metadata={meta}",
        )
        res = client.get(f"/api/contracts/{contract_id}")
        check(
            "re-running does not duplicate clauses",
            len(res.json()["clauses"]) == len(clauses),
        )

    # --- not found --------------------------------------------------------
    print("\n[9] GET /api/contracts/{unknown}")
    res = client.get("/api/contracts/00000000-0000-0000-0000-000000000000")
    check("responds 404", res.status_code == 404, f"got {res.status_code}")
    res = client.get("/api/contracts/not-a-uuid")
    check("malformed UUID responds 422", res.status_code == 422, f"got {res.status_code}")

    # --- delete -----------------------------------------------------------
    if args.keep:
        print(f"\n[10] Skipping delete (--keep). Contract {contract_id} retained.")
    else:
        print("\n[10] DELETE /api/contracts/{id}")
        res = client.delete(f"/api/contracts/{contract_id}")
        check("responds 200", res.status_code == 200, res.text[:200])
        res = client.get(f"/api/contracts/{contract_id}")
        check("contract is gone (cascade)", res.status_code == 404)
        res = client.delete(f"/api/contracts/{contract_id}")
        check("second delete responds 404", res.status_code == 404)

    client.close()
    print(f"\nAll {_passed} checks passed.\n")


if __name__ == "__main__":
    main()
