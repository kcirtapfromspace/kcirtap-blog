"""Owner-labeled, held-out validation. Never silently tune model weights/floors."""
from .store import digest, require, verify_owner
from .domain import STAGES, owner_action
from .jev import validate_response
import json


def validate(store, policy, envelope, signers):
    p = verify_owner(envelope, signers)
    require(p.get("kind") == "calibration" and p.get("task_id") == "POLICY", "Signed policy validation required")
    require(p.get("policy_hash") == digest(policy), "Calibration bound to another policy")
    examples = p.get("examples", [])
    require(len({e["request_hash"] for e in examples}) == len(examples), "Examples must be distinct")
    for stage in STAGES:
        selected = [e for e in examples if e.get("stage") == stage]
        require(len(selected) >= policy["minimum_validation_examples_per_stage"], f"Too few held-out owner labels for {stage}")
        accepted, correct = 0, 0
        for e in selected:
            require(e.get("split") == "held-out" and e.get("label_recorded_before_review") is True, "Use held-out labels recorded before model review")
            req = json.loads(store.get(e["request_hash"]))
            require(req["model"] == policy["model"], "Validation model differs")
            attempts = [a["payload"] for a in store.events(kind="jev-attempt") if a["payload"].get("request_hash") == e["request_hash"] and a["payload"].get("response_hash") == e["response_hash"] and a["payload"].get("status") == "complete"]
            require(bool(attempts), "Validation needs original completed Jev transport receipt")
            res = validate_response(store.get(e["response_hash"]), req)
            require(set(e["labels"]) == set(res["answers"]), "Label every validation question")
            for key, a in res["answers"].items():
                if a["confidence"] >= policy["thresholds"][stage]:
                    accepted += 1
                    correct += a["choice"] == e["labels"][key]
        require(accepted >= policy["minimum_validation_examples_per_stage"], "Too few decisions above the proposed floor")
        require(correct / accepted >= policy["minimum_validation_accuracy"], "Proposed thresholds failed held-out validation; do not relax to pass a candidate")
    return owner_action(store, envelope, signers)
