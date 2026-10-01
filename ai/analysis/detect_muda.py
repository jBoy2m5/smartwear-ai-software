"""Find camera-visible candidates for human review, not confirmed Muda."""

from difflib import SequenceMatcher

MIN_EXTRA_MS = 500
MIN_INSERTED_MS = 300
MIN_DURATION_RATIO = 1.5


def _comment_vi(candidate):
    """Describe only the visible evidence behind one review candidate."""
    hand = "tay trái" if candidate["hand"] == "left" else "tay phải"
    actions = {
        "OPEN": "mở", "GRAB": "nắm", "REACH": "đưa tới",
        "RELEASE": "thả", "ASSEMBLY": "ở trạng thái ASSEMBLY",
    }
    label = candidate["expert_label"] if candidate["reason"] == "missing_visible_action" else candidate["worker_label"]
    action = actions.get(label, f"ở trạng thái {label}")

    def seconds(ms):
        return f"{ms / 1000:.3f}".replace(".", ",")

    if candidate["reason"] == "missing_visible_action":
        return (f"Mẫu có đoạn {hand} {action}, nhưng camera không ghi nhận đoạn tương ứng "
                f"gần giây {seconds(candidate['worker_time_hint_ms'])} trong video của bạn. "
                "Hãy xem ảnh mẫu và video quanh mốc này.")

    start = seconds(candidate["start_ms"])
    end = seconds(candidate["end_ms"])
    if candidate["reason"] == "longer_visible_action":
        return (f"Camera ghi nhận {hand} {action} từ giây {start} đến {end}, "
                f"lâu hơn đoạn tương ứng trong mẫu {seconds(candidate['extra_ms'])} giây. "
                "Hãy xem lại video đoạn này.")
    if candidate["reason"] == "shorter_visible_action":
        return (f"Camera ghi nhận {hand} {action} từ giây {start} đến {end}, "
                f"ngắn hơn đoạn cùng hành động trong mẫu {seconds(-candidate['extra_ms'])} giây. "
                "Hãy xem lại video đoạn này; chưa kết luận thao tác sai.")
    if candidate["reason"] == "repeated_visible_action":
        return (f"Camera ghi nhận đoạn {hand} {action} trong một chuỗi động tác lặp "
                f"từ giây {start} đến {end}. Hãy xem lại video đoạn này.")
    if candidate["reason"] == "extra_visible_action":
        return (f"Camera ghi nhận thêm đoạn {hand} {action} từ giây {start} đến {end} "
                "so với chuỗi trong mẫu. Hãy xem lại video đoạn này.")
    if candidate["reason"] == "inserted_visible_action":
        return (f"Camera ghi nhận đoạn {hand} {action} từ giây {start} đến {end} "
                "chen giữa các đoạn khớp mẫu. Hãy xem lại video đoạn này.")
    raise ValueError(f"Unknown Muda review reason: {candidate['reason']}")


def _uncertain_between(uncertain, start_ms, end_ms):
    """An unobserved hand or camera gap cannot establish an omitted action."""
    if end_ms - start_ms > 500:
        return True
    return any(item["start_ms"] < end_ms and item["end_ms"] > start_ms
               for item in uncertain)


def _sequence_candidates(side, expert, worker, expert_images, worker_images,
                         uncertain, existing_ids):
    """Find visible insertions/deletions bounded by matching action labels."""
    # One-frame label flicker is not a reliable factory step.
    expert = [item for item in expert if item["duration_ms"] >= MIN_INSERTED_MS]
    worker = [item for item in worker if item["duration_ms"] >= MIN_INSERTED_MS]
    if not expert or not worker:
        return []
    labels_e = [item["label"] for item in expert]
    labels_w = [item["label"] for item in worker]
    opcodes = SequenceMatcher(None, labels_e, labels_w, autojunk=False).get_opcodes()
    found = []
    for index, (operation, e0, e1, w0, w1) in enumerate(opcodes):
        if operation not in ("insert", "delete"):
            # A replacement alone cannot tell which action was omitted or added.
            continue
        before = opcodes[index - 1] if index else None
        after = opcodes[index + 1] if index + 1 < len(opcodes) else None
        bounded = (before is not None and after is not None
                   and before[0] == after[0] == "equal")
        repeated_tail = (operation == "insert" and after is None and before is not None
                         and before[0] == "equal" and w1 - w0 >= 2
                         and w0 >= w1 - w0
                         and labels_w[w0:w1] == labels_w[w0 - (w1 - w0):w0])
        repeated_head = (operation == "insert" and before is None and after is not None
                         and after[0] == "equal" and w1 - w0 >= 2
                         and w1 + (w1 - w0) <= len(worker)
                         and labels_w[w0:w1] == labels_w[w1:w1 + (w1 - w0)])
        complete_reference_at_edge = (
            operation == "insert" and len(opcodes) == 2
            and ((before is None and after is not None and after[0] == "equal"
                  and after[2] - after[1] == len(expert))
                 or (after is None and before is not None and before[0] == "equal"
                     and before[2] - before[1] == len(expert))))
        if not bounded and not repeated_tail and not repeated_head and not complete_reference_at_edge:
            continue
        if operation == "insert":
            left_time = worker[w0 - 1]["end_ms"] if w0 else worker[w0]["start_ms"]
            right_time = worker[w1]["start_ms"] if w1 < len(worker) else worker[w1 - 1]["end_ms"]
            if _uncertain_between(uncertain, left_time, worker[w0]["start_ms"]) or \
                    _uncertain_between(uncertain, worker[w1 - 1]["end_ms"], right_time):
                continue
            inserted_labels = labels_w[w0:w1]
            previous_labels = labels_w[max(0, w0 - len(inserted_labels)):w0]
            following_labels = labels_w[w1:w1 + len(inserted_labels)]
            repeated = (len(inserted_labels) >= 2 and
                        (inserted_labels == previous_labels
                         or inserted_labels == following_labels))
            for segment in worker[w0:w1]:
                if segment["duration_ms"] < MIN_INSERTED_MS or segment["segment_id"] in existing_ids:
                    continue
                found.append({
                    "hand": side,
                    "reason": "repeated_visible_action" if repeated else "extra_visible_action",
                    "worker_segment_id": segment["segment_id"],
                    "expert_segment_id": None,
                    "worker_label": segment["label"], "expert_label": None,
                    "start_ms": segment["start_ms"], "end_ms": segment["end_ms"],
                    "duration_ms": segment["duration_ms"], "extra_ms": None,
                    "worker_image_path": worker_images.get(segment["segment_id"]),
                })
                existing_ids.add(segment["segment_id"])
        elif bounded and w0 > 0 and w0 < len(worker):
            left_time, right_time = worker[w0 - 1]["end_ms"], worker[w0]["start_ms"]
            if _uncertain_between(uncertain, left_time, right_time):
                continue
            for segment in expert[e0:e1]:
                if segment["duration_ms"] < MIN_INSERTED_MS:
                    continue
                found.append({
                    "hand": side, "reason": "missing_visible_action",
                    "worker_segment_id": None,
                    "expert_segment_id": segment["segment_id"],
                    "worker_label": None, "expert_label": segment["label"],
                    "start_ms": None, "end_ms": None,
                    "duration_ms": None, "extra_ms": None,
                    "worker_time_hint_ms": right_time,
                    "expert_start_ms": segment["start_ms"],
                    "expert_end_ms": segment["end_ms"],
                    "expert_image_path": expert_images.get(segment["segment_id"]),
                    "worker_image_path": worker_images.get(worker[w0]["segment_id"]),
                })
    return found


def detect_muda_candidates(tracks, worker_tracks, expert_tracks=None,
                           expert_images=None, worker_images=None,
                           worker_uncertain=None):
    """Report conservative, per-hand timing and inserted-action candidates.

    DTW can map one segment several times. Timing comparisons need an unambiguous
    same-label pair; a very short mismatched tail does not mask a shortened step.
    An inserted action needs matching worker actions on both sides.
    """
    expert_images = expert_images or {}
    worker_images = worker_images or {}
    worker_uncertain = worker_uncertain or {"left": [], "right": []}
    hands = {}
    for side in ("left", "right"):
        track = tracks[side]
        worker_by_id = {segment["segment_id"]: segment
                        for segment in worker_tracks[side]}
        pairs = track["alignment"]
        candidates = []
        expert_counts = {}
        worker_counts = {}
        expert_pairs = {}
        for pair in pairs:
            expert_counts[pair["expert_segment_id"]] = (
                expert_counts.get(pair["expert_segment_id"], 0) + 1)
            worker_counts[pair["worker_segment_id"]] = (
                worker_counts.get(pair["worker_segment_id"], 0) + 1)
            expert_pairs.setdefault(pair["expert_segment_id"], []).append(pair)

        for index, pair in enumerate(pairs):
            segment_id = pair["worker_segment_id"]
            worker = worker_by_id.get(segment_id)
            if worker is None:
                continue
            extra = pair["worker_extra_ms"]
            reason = None
            if (pair["same_label"] and extra >= MIN_EXTRA_MS
                    and pair["worker_duration_ms"] >= MIN_DURATION_RATIO *
                    max(1, pair["expert_duration_ms"])
                    and expert_counts[pair["expert_segment_id"]] == 1
                    and worker_counts[segment_id] == 1):
                reason = "longer_visible_action"
            elif (pair["same_label"] and -extra >= MIN_EXTRA_MS
                  and pair["expert_duration_ms"] >= MIN_DURATION_RATIO *
                  max(1, pair["worker_duration_ms"])
                  and pair["worker_duration_ms"] >= MIN_INSERTED_MS
                  and worker_counts[segment_id] == 1
                  and all(other is pair or
                          (not other["same_label"] and
                           other["worker_duration_ms"] < MIN_INSERTED_MS)
                          for other in expert_pairs[pair["expert_segment_id"]])):
                # A very short mismatched tail can reuse the expert segment in DTW;
                # it is not evidence that the matching worker action lasted longer.
                reason = "shorter_visible_action"
            elif (not pair["same_label"] and worker["duration_ms"] >= MIN_INSERTED_MS
                  and worker_counts[segment_id] == 1 and 0 < index < len(pairs) - 1):
                before, after = pairs[index - 1], pairs[index + 1]
                if (before["expert_segment_id"] == pair["expert_segment_id"]
                        == after["expert_segment_id"]
                        and before["same_label"] and after["same_label"]
                        and before["worker_segment_id"] != segment_id
                        and after["worker_segment_id"] != segment_id):
                    reason = "inserted_visible_action"
            if reason:
                candidates.append({
                    "hand": side, "reason": reason,
                    "worker_segment_id": segment_id,
                    "expert_segment_id": pair["expert_segment_id"],
                    "worker_label": pair["worker_label"],
                    "expert_label": pair["expert_label"],
                    "start_ms": worker["start_ms"], "end_ms": worker["end_ms"],
                    "duration_ms": worker["duration_ms"],
                    "extra_ms": extra if reason in (
                        "longer_visible_action", "shorter_visible_action") else None,
                    "worker_image_path": pair.get("worker_image_path"),
                })
        if expert_tracks is not None and track["status"] == "compared":
            candidates.extend(_sequence_candidates(
                side, expert_tracks[side], worker_tracks[side], expert_images,
                worker_images, worker_uncertain[side],
                {item["worker_segment_id"] for item in candidates}))
        candidates.sort(key=lambda item: (
            item["start_ms"] if item["start_ms"] is not None
            else item["worker_time_hint_ms"], item["reason"]))
        for candidate in candidates:
            candidate["comment_vi"] = _comment_vi(candidate)
        hands[side] = {"status": track["status"], "candidates": candidates,
                       "candidate_count": len(candidates)}

    return {
        "status": "review_candidates_only",
        "method": "camera_visible_action_timing_and_sequence_v2",
        "note": "Candidates are not confirmed Muda. Review the video; demo references are not certified work standards.",
        "uses_sensor_values": False,
        "hands": hands,
    }
