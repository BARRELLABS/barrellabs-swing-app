"""
Milestone 5: Drill recommendations.

Reads the player's biggest coachable gaps (from compare.py's analysis) and
prescribes specific drills to address them. Gap → category mapping is
rule-based; each category has a curated bank of drills with how-to
instructions.

Usage:
  This module is imported and called by compare.py. You can also run it
  standalone:
      python drills.py
  to see the full drill database.
"""

# ---- DRILL DATABASE ----
# Each category has: title, why_it_matters, and a list of drills.
# Each drill has: name, how (instructions), reps (suggested volume).

DRILL_DB = {
    "head_stability": {
        "title": "Quiet the Head",
        "why_it_matters": (
            "Excessive head movement disconnects your eyes from the ball, "
            "leaks power out of your rotation, and makes consistent contact "
            "much harder. Elite hitters keep the head almost still through "
            "contact."
        ),
        "drills": [
            {
                "name": "Wall Drill",
                "how": (
                    "Stand in your stance with the back of your head lightly "
                    "touching a wall. Take dry swings without your head leaving "
                    "the wall. Start at half speed, build to full."
                ),
                "reps": "3 sets of 10",
            },
            {
                "name": "Towel-on-Head Drill",
                "how": (
                    "Balance a small towel on top of your head and take swings "
                    "off a tee. The towel falling = your head moved too much. "
                    "Forces you to rotate around a stable axis."
                ),
                "reps": "3 sets of 8",
            },
            {
                "name": "Eye-on-the-Tee",
                "how": (
                    "Set a tee at your normal contact point, but keep your eyes "
                    "locked on the EXACT spot where the ball sits — even after "
                    "contact. Don't track the ball off the bat."
                ),
                "reps": "3 sets of 10",
            },
            {
                "name": "Mirror Feedback",
                "how": (
                    "Take swings in front of a full-length mirror. Watch your "
                    "head position from setup through follow-through. Goal: "
                    "head finishes within a baseball-width of where it started."
                ),
                "reps": "5 minutes daily",
            },
        ],
    },

    "hip_rotation": {
        "title": "Drive the Hips",
        "why_it_matters": (
            "Power in a swing comes from the ground up: legs → hips → torso → "
            "arms → bat. If your hips don't fully rotate through contact, "
            "you're hitting with arms only and leaving big-time bat speed "
            "(and exit velocity) on the table."
        ),
        "drills": [
            {
                "name": "Hip Turn Step-Throughs",
                "how": (
                    "Slow-motion reps without a bat. Get to your stance, then "
                    "deliberately rotate the back hip all the way through, "
                    "letting the back foot pivot and the belt buckle face the "
                    "pitcher. Feel the full rotation."
                ),
                "reps": "3 sets of 10",
            },
            {
                "name": "Belt-Tug Drill",
                "how": (
                    "Partner stands behind you and lightly tugs a belt loop "
                    "(or towel through a belt loop) on your back hip during "
                    "your swing. The tug exaggerates the feel of leading with "
                    "the hip."
                ),
                "reps": "3 sets of 8",
            },
            {
                "name": "Resistance Band Rotations",
                "how": (
                    "Loop a resistance band around your waist, anchored "
                    "behind you. Take swings (no bat, then with bat) against "
                    "the band's pull. Builds rotational strength and teaches "
                    "your hips to drive forward, not just turn."
                ),
                "reps": "3 sets of 12",
            },
            {
                "name": "Closed-Stance Tee Work",
                "how": (
                    "Close your stance more than usual. This makes you "
                    "physically have to rotate your hips harder to get the "
                    "barrel to the ball. Then return to your normal stance "
                    "and the regular hip turn feels easier."
                ),
                "reps": "3 sets of 10",
            },
        ],
    },

    "hip_shoulder_separation": {
        "title": "Build Hip-Shoulder Separation (X-Factor)",
        "why_it_matters": (
            "The gap between your hips firing forward and your shoulders "
            "still loaded is where your bat speed comes from. Big-league "
            "hitters create 40°+ of separation. Without it, you're 'spinning' "
            "with the whole upper body and losing the elastic snap."
        ),
        "drills": [
            {
                "name": "Connection Ball Drill",
                "how": (
                    "Squeeze a small ball (or rolled towel) between your "
                    "front upper-arm and chest. Take swings keeping the ball "
                    "trapped through contact. Forces the back side to stay "
                    "loaded while hips fire."
                ),
                "reps": "3 sets of 10",
            },
            {
                "name": "Hips First, Hands Last",
                "how": (
                    "Slow-motion swings: rotate hips fully toward the pitcher "
                    "BEFORE the hands move forward. Pause at full hip rotation "
                    "with hands still back, then fire. Feels weird, that's "
                    "the point."
                ),
                "reps": "3 sets of 8",
            },
            {
                "name": "Heavy Bat Swings",
                "how": (
                    "Take 5–8 swings with a weighted bat (or regular bat in a "
                    "donut). The extra weight forces correct sequencing — "
                    "hips have to lead or you can't get the barrel through."
                ),
                "reps": "3 sets of 5",
            },
            {
                "name": "Cross-Arm Rotation",
                "how": (
                    "Cross your arms over your chest. Take stride and rotate "
                    "your hips fully while keeping shoulders pointed at the "
                    "pitcher as long as possible. Trains the separation feel "
                    "without the bat getting in the way."
                ),
                "reps": "3 sets of 10",
            },
        ],
    },

    "knee_extension": {
        "title": "Firm Up the Front Side",
        "why_it_matters": (
            "Your front leg is the brake that stops your weight transfer and "
            "redirects it into rotational power. A soft front knee at contact "
            "leaks energy and pulls your head off the ball."
        ),
        "drills": [
            {
                "name": "Front Knee Block Drill",
                "how": (
                    "Take swings and hold your finish for 3 seconds, "
                    "checking that your front leg is firm and braced — knee "
                    "slightly bent but not collapsing forward."
                ),
                "reps": "3 sets of 8",
            },
            {
                "name": "Wall Sit Holds",
                "how": (
                    "Wall sit at 90° for 30–45 seconds. Builds the quad "
                    "strength your front leg needs to stay firm at contact."
                ),
                "reps": "3 sets of 30s",
            },
            {
                "name": "Step-Back Drill",
                "how": (
                    "Start with your weight on your back leg, take an "
                    "exaggerated stride into a firm front-leg block, then "
                    "swing. Trains the load → block → fire sequence."
                ),
                "reps": "3 sets of 8",
            },
        ],
    },

    "timing": {
        "title": "Sharpen Timing & Quickness",
        "why_it_matters": (
            "A long, slow swing arrives late and leaves you guessing. Quick "
            "hands and a compact path let you wait longer on the pitch and "
            "still get the barrel there on time."
        ),
        "drills": [
            {
                "name": "Short-Toss Quick Hands",
                "how": (
                    "Partner soft-tosses from 8–10 feet away. Focus on the "
                    "shortest, most direct path from load to contact. No "
                    "wasted motion."
                ),
                "reps": "3 sets of 10",
            },
            {
                "name": "Tennis Ball Reactions",
                "how": (
                    "Partner randomly tosses tennis balls (different speeds, "
                    "small intentional pauses). Forces you to read and react "
                    "rather than time a rhythm."
                ),
                "reps": "3 sets of 10",
            },
            {
                "name": "One-Hand Top-Hand Tee",
                "how": (
                    "Take swings off a tee using only your top (back) hand. "
                    "Forces a compact, quick path — no looping or dragging."
                ),
                "reps": "3 sets of 8",
            },
        ],
    },
}


# Average adult torso (shoulder-mid → hip-mid vertical) in inches.
# Used to translate "torso-lengths" into something a human can picture.
TYPICAL_TORSO_INCHES = 22


def _movement_phrase(t):
    """Plain-English distance for a head-movement value in torso-lengths."""
    inches = abs(t) * TYPICAL_TORSO_INCHES
    if inches < 0.75:
        return "barely moves at all"
    if inches < 1.5:
        return "about an inch"
    if inches < 11.5:
        return f"about {inches:.0f} inches"
    if inches < 14:
        return f"about a foot ({inches:.0f} inches)"
    if inches < 17:
        return f"over a foot ({inches:.0f} inches)"
    if inches < 21:
        return f"about a foot and a half ({inches:.0f} inches)"
    if inches < 26:
        return f"almost two feet ({inches:.0f} inches)"
    return f"over two feet ({inches:.0f} inches)"


def _wrap(text, indent="  ", width=70):
    """Word-wrap a paragraph and print with the given indent prefix."""
    words = text.split()
    line = indent
    for w in words:
        if len(line) + len(w) + 1 > width:
            print(line)
            line = indent + w
        else:
            line = line + (" " if line.strip() else "") + w
    if line.strip():
        print(line)


def _intensity(ratio):
    """Convert a 'how-many-times-the-reference' ratio into a word."""
    if ratio >= 5:
        return "dramatically"
    if ratio >= 2.5:
        return "significantly"
    if ratio >= 1.5:
        return "noticeably"
    return "somewhat"


def _narrate_gap(gap, ref_name):
    """Return a list of paragraph strings (issue / why / fix) for one gap."""
    label = gap["label"].lower()
    group = gap["group"]
    p, r = gap["p"], gap["r"]

    # ---- HEAD ----
    if group == "Head" and "total" in label:
        ratio = abs(p) / max(abs(r), 0.01)
        return [
            f"Your head moves {abs(p):.2f} torso-lengths total during the swing — "
            f"{_intensity(ratio)} more than {ref_name}'s {abs(r):.2f}T.",

            "Why it costs you: every fraction of a torso-length your head moves is "
            "ball-tracking error. Your eyes are reading the pitch from a moving "
            "platform, which shows up as inconsistent contact, mis-hits on the same "
            "pitch you crushed yesterday, and getting fooled on offspeed.",

            "What the fix feels like: the swing should rotate AROUND your head, "
            "not drag it forward. Chin stays anchored at setup; the body spins "
            "underneath. If you can see the contact zone the entire swing, "
            "you're doing it right.",
        ]

    if group == "Head" and "Δx" in gap["label"]:
        direction = "toward the pitcher" if p > 0 else "away from the pitcher"
        return [
            f"Your head drifts {abs(p):.2f} torso-lengths {direction} during the "
            f"swing while {ref_name} stays at {abs(r):.2f}T.",

            "Why it costs you: that forward lurch tells your brain the ball is "
            "arriving faster than it really is, which is why you'll feel late on "
            "fastballs and out in front on changeups. It also kills your back-side "
            "leverage — you can't drive a ball when your weight has already "
            "gone past it.",

            "What the fix feels like: stay 'tall' through contact. The hips can "
            "move forward, but the head should stay stacked over the back hip "
            "until well after the bat passes the zone.",
        ]

    if group == "Head" and "Δy" in gap["label"]:
        direction = "downward" if p > 0 else "upward"
        return [
            f"Your head moves {abs(p):.2f} torso-lengths {direction} through the "
            f"swing — {ref_name} stays nearly level ({abs(r):.2f}T).",

            "Why it costs you: vertical head movement is the #1 reason hitters "
            "mis-time pitch HEIGHT. When your eyes drop, high pitches look like "
            "strikes; when they lift, low pitches look hittable. It's also a "
            "sign the spine angle is collapsing — leaking power.",

            "What the fix feels like: the spine angle you set at foot plant "
            "should not change until your follow-through is complete. Imagine "
            "a string from the top of your head holding you upright through "
            "the entire rotation.",
        ]

    # ---- ROTATION ----
    if group == "Rotation" and "separation" in label and "peak" in label:
        return [
            f"Your peak hip-shoulder separation tops out at {p:+.0f}° while "
            f"{ref_name} reaches {r:+.0f}°.",

            "Why it costs you: the gap between hips firing forward and shoulders "
            "staying loaded is where bat speed actually comes from — it's the "
            "elastic stretch that snaps the barrel through. With less separation "
            "you're 'spinning' the whole upper body, which feels strong but "
            "produces weak contact.",

            "What the fix feels like: hips fire while the back shoulder feels "
            "'stuck' for an extra beat. If it feels like your hands are late, "
            "you're probably doing it right.",
        ]

    if group == "Rotation" and "contact" in label:
        return [
            f"At contact your hips have rotated only {p:+.0f}° vs "
            f"{ref_name}'s {r:+.0f}°.",

            "Why it costs you: incomplete hip rotation means you're hitting with "
            "mostly arms. The kinetic chain (legs → hips → torso → arms) stops "
            "short, and you lose the biggest source of free bat speed.",

            "What the fix feels like: belly button finishes pointing at the "
            "pitcher. The back foot pivots clean off the ground at finish — if "
            "it doesn't, the hips didn't fire through.",
        ]

    if group == "Rotation":
        return [
            f"{gap['label']}: {p:+.1f}° vs {ref_name}'s {r:+.1f}° "
            f"(gap of {abs(p - r):.1f}°).",

            "Why it costs you: rotational mechanics are how the legs deliver "
            "power to the bat. Anything off here gets multiplied by the time "
            "the bat reaches the ball.",

            "What the fix feels like: lead with the lower body, let the upper "
            "body follow. Hips first, hands last.",
        ]

    # ---- KNEE ----
    if group == "Front Knee":
        return [
            f"Your front knee {gap['label'].lower()}: {p:+.1f}° vs "
            f"{ref_name}'s {r:+.1f}°.",

            "Why it costs you: the front leg is your brake. If it's soft or "
            "re-extending, energy that should rebound up into the swing leaks "
            "out the bottom — like jumping on a soft mattress.",

            "What the fix feels like: at contact, the front leg should feel "
            "'posted' — firm but not locked. The chest stacks over a stable "
            "base.",
        ]

    # ---- TIMING (rare — usually filtered) ----
    if group == "Timing":
        return [
            f"{gap['label']} timing differs: {p:.0f}{gap['units']} vs "
            f"{ref_name}'s {r:.0f}{gap['units']}.",

            "Why it costs you: a slow swing arrives late and leaves you guessing; "
            "a rushed swing gets fooled. Tempo is everything.",

            "What the fix feels like: short, direct path from load to contact. "
            "No wasted motion.",
        ]

    # ---- FALLBACK ----
    return [
        f"{gap['label']}: player {p:.2f}{gap['units']} vs "
        f"{ref_name} {r:.2f}{gap['units']}.",
    ]


# ---- CATEGORY-AWARE NARRATORS -----------------------------------------
# These take ALL the player's gaps in a single coaching category and produce
# one consolidated 3-paragraph diagnosis, so we never repeat the same advice
# three times just because head-Δx, head-Δy, and head-total all happen to
# fail. They also speak in inches instead of torso-lengths.

def _narrate_head_stability(head_gaps, ref_name):
    """One combined narrative covering all head-drift metrics."""
    # Pull the three head metrics if present.
    by_axis = {}
    for g in head_gaps:
        lbl = g["label"]
        if "Δx" in lbl:
            by_axis["dx"] = g
        elif "Δy" in lbl:
            by_axis["dy"] = g
        elif "total" in lbl.lower():
            by_axis["total"] = g

    # Prefer "total" as the headline number; otherwise use the worst-ranked.
    primary = by_axis.get("total") or head_gaps[0]
    p_total = primary["p"]
    r_total = primary["r"]
    player_dist = _movement_phrase(p_total)
    ref_dist = _movement_phrase(r_total)

    # Direction-of-drift detail from dx and dy (only mention if meaningful).
    drift_parts = []
    if "dx" in by_axis:
        dx_val = by_axis["dx"]["p"]
        # 0.05 torso-lengths ≈ 1 inch — anything smaller isn't worth calling out.
        if abs(dx_val) > 0.05:
            dir_word = "forward, toward the pitcher" if dx_val > 0 else "back, away from the pitcher"
            drift_parts.append(f"{_movement_phrase(dx_val)} {dir_word}")
    if "dy" in by_axis:
        dy_val = by_axis["dy"]["p"]
        if abs(dy_val) > 0.05:
            dir_word = "downward" if dy_val > 0 else "upward"
            drift_parts.append(f"{_movement_phrase(dy_val)} {dir_word}")

    first = (
        f"From foot plant to contact your head moves {player_dist} total, "
        f"while {ref_name}'s head {ref_dist}."
    )
    if drift_parts:
        first += " Specifically, your head goes " + " and ".join(drift_parts) + " during the swing."

    why = (
        "Why it costs you: every inch of head movement is ball-tracking "
        "error. Your eyes are reading the pitch from a moving platform, "
        "which shows up as inconsistent contact, mis-hits on pitches you "
        "should crush, and getting fooled on offspeed. Vertical movement "
        "is especially brutal on pitch HEIGHT — when your eyes drop, high "
        "pitches look like strikes; when they lift, low pitches look "
        "hittable."
    )

    fix = (
        "What the fix feels like: the swing should rotate AROUND your "
        "head, not drag it forward or up. Chin stays anchored where it "
        "started; the body spins underneath it. If you can keep your eyes "
        "locked on the contact point through the entire swing, you're "
        "doing it right."
    )

    return [first, why, fix]


def _narrate_hip_rotation(rotation_gaps, ref_name):
    """Combined narrative for hip-rotation gaps."""
    primary = rotation_gaps[0]  # worst-ranked
    p, r = primary["p"], primary["r"]
    label = primary["label"].lower()

    if "contact" in label:
        first = (
            f"At contact your hips have only rotated to {p:+.0f}° while "
            f"{ref_name}'s are at {r:+.0f}° — a {abs(p - r):.0f}° gap right "
            f"at the moment of impact."
        )
    elif "foot plant" in label:
        first = (
            f"At foot plant your hips are at {p:+.0f}° vs {ref_name}'s "
            f"{r:+.0f}°. You're starting your rotation late, which means "
            f"there's less runway to build bat speed before contact."
        )
    else:
        first = (
            f"{primary['label']}: yours is {p:+.0f}° vs {ref_name}'s "
            f"{r:+.0f}° — a {abs(p - r):.0f}° gap."
        )

    why = (
        "Why it costs you: power in a swing comes from the ground up — "
        "legs to hips to torso to arms to the bat. If the hips don't fully "
        "rotate through contact, you're swinging with mostly arms and "
        "leaving big-time bat speed on the table. That shows up as soft "
        "contact even on balls you square up."
    )

    fix = (
        "What the fix feels like: belly button finishes pointing at the "
        "pitcher. The back foot pivots clean off the ground at finish — "
        "if it doesn't, the hips never fully fired."
    )

    return [first, why, fix]


def _narrate_separation(sep_gaps, ref_name):
    """Combined narrative for hip-shoulder-separation (X-factor) gaps."""
    # Prefer the "peak" metric if present.
    primary = next((g for g in sep_gaps if "peak" in g["label"].lower()), sep_gaps[0])
    p, r = primary["p"], primary["r"]

    if "peak" in primary["label"].lower():
        first = (
            f"Your peak hip-shoulder separation tops out at {p:+.0f}° while "
            f"{ref_name} reaches {r:+.0f}°. That {abs(p - r):.0f}° gap is "
            f"where most of your missing bat speed lives."
        )
    else:
        first = (
            f"{primary['label']}: yours is {p:+.0f}° vs {ref_name}'s "
            f"{r:+.0f}° — separation of {abs(p - r):.0f}° less than the reference."
        )

    why = (
        "Why it costs you: the gap between your hips firing forward and "
        "your shoulders staying loaded is the elastic stretch that snaps "
        "the barrel through the zone. With less separation you're "
        "'spinning' the whole upper body at once — feels strong, produces "
        "weak contact."
    )

    fix = (
        "What the fix feels like: hips fire while the back shoulder feels "
        "stuck for an extra beat. If it feels like your hands are late, "
        "you're probably doing it right."
    )

    return [first, why, fix]


def _narrate_knee(knee_gaps, ref_name):
    """Combined narrative for front-knee gaps."""
    primary = knee_gaps[0]
    p, r = primary["p"], primary["r"]
    label = primary["label"].lower()

    if "re-extension" in label or "re_extension" in label:
        first = (
            f"Your front knee re-extends {p:+.0f}° between load and contact "
            f"vs {ref_name}'s {r:+.0f}°."
        )
    else:
        first = (
            f"Your front-knee bend ({primary['label'].lower()}) is "
            f"{p:+.0f}° vs {ref_name}'s {r:+.0f}°."
        )

    why = (
        "Why it costs you: the front leg is your brake. If it's soft or "
        "collapsing at contact, energy that should rebound up into the "
        "swing leaks out the bottom — like jumping on a soft mattress. "
        "That softness also pulls your head off the ball."
    )

    fix = (
        "What the fix feels like: at contact the front leg should feel "
        "'posted' — firm, slightly bent, but not collapsing forward. "
        "Your chest stacks over a stable base."
    )

    return [first, why, fix]


def _narrate_timing_cat(timing_gaps, ref_name):
    """Combined narrative for timing/tempo gaps (rare — usually filtered)."""
    primary = timing_gaps[0]
    p, r = primary["p"], primary["r"]
    units = primary["units"]

    first = (
        f"{primary['label']}: yours is {p:.0f}{units} vs {ref_name}'s "
        f"{r:.0f}{units}."
    )

    why = (
        "Why it costs you: a slow swing arrives late and leaves you "
        "guessing on velocity; a rushed swing gets fooled on offspeed. "
        "Tempo is everything."
    )

    fix = (
        "What the fix feels like: short, direct path from load to contact. "
        "No wasted motion, no looping the bat."
    )

    return [first, why, fix]


_CATEGORY_NARRATORS = {
    "head_stability": _narrate_head_stability,
    "hip_rotation": _narrate_hip_rotation,
    "hip_shoulder_separation": _narrate_separation,
    "knee_extension": _narrate_knee,
    "timing": _narrate_timing_cat,
}

_CATEGORY_TITLES = {
    "head_stability": "HEAD STABILITY",
    "hip_rotation": "HIP ROTATION",
    "hip_shoulder_separation": "HIP-SHOULDER SEPARATION",
    "knee_extension": "FRONT-SIDE FIRMNESS",
    "timing": "TIMING & TEMPO",
}


def narrate_top_gaps(gaps_ranked, ref_name, top_n=2):
    """Coach-style diagnosis, deduped by coaching category.

    Multiple metrics from the same category (e.g. head Δx, Δy, and total
    drift) get combined into ONE narrative — so the player never reads the
    same fix three times in a row.
    """
    print("=" * 70)
    print("WHAT TO FIX")
    print("=" * 70)

    if not gaps_ranked:
        print()
        print("  No comparable gaps to diagnose — re-record both videos from")
        print("  similar angles and re-run.")
        print()
        return

    # Group gaps by category, preserving rank order (worst gap first).
    by_category = {}
    category_order = []  # categories in order of their worst-ranked appearance
    for gap in gaps_ranked:
        cat = classify_gap(gap)
        if cat is None:
            continue
        if cat not in by_category:
            by_category[cat] = []
            category_order.append(cat)
        by_category[cat].append(gap)

    if not category_order:
        print()
        print("  No diagnoseable gaps found.")
        print()
        return

    # Take top N unique categories.
    top_cats = category_order[:top_n]

    for rank, cat in enumerate(top_cats, 1):
        gaps_in_cat = by_category[cat]
        print()
        print(f"#{rank} — {_CATEGORY_TITLES.get(cat, cat.upper())}")
        print()
        narrator = _CATEGORY_NARRATORS.get(cat)
        if narrator:
            paragraphs = narrator(gaps_in_cat, ref_name)
        else:
            # Defensive fallback to the per-metric narrator.
            paragraphs = _narrate_gap(gaps_in_cat[0], ref_name)
        for paragraph in paragraphs:
            _wrap(paragraph)
            print()


def build_narratives(gaps_ranked, ref_name, top_n=2):
    """Return structured 'what to fix' narrative data WITHOUT printing.

    Used by the Streamlit UI to render each top-priority fix as its own card
    (issue paragraph, why-it-costs paragraph, what-the-fix-feels-like paragraph)
    instead of dumping all of it as a wall of monospace text.

    Returns a list of dicts:
        [{"rank": 1, "category": "head_stability", "title": "HEAD STABILITY",
          "paragraphs": [issue_str, why_str, fix_str]}, ...]
    """
    if not gaps_ranked:
        return []

    by_category = {}
    category_order = []
    for gap in gaps_ranked:
        cat = classify_gap(gap)
        if cat is None:
            continue
        if cat not in by_category:
            by_category[cat] = []
            category_order.append(cat)
        by_category[cat].append(gap)

    if not category_order:
        return []

    top_cats = category_order[:top_n]
    out = []
    for rank, cat in enumerate(top_cats, 1):
        gaps_in_cat = by_category[cat]
        narrator = _CATEGORY_NARRATORS.get(cat)
        if narrator:
            paragraphs = narrator(gaps_in_cat, ref_name)
        else:
            paragraphs = _narrate_gap(gaps_in_cat[0], ref_name)
        out.append({
            "rank": rank,
            "category": cat,
            "title": _CATEGORY_TITLES.get(cat, cat.upper()),
            "paragraphs": list(paragraphs),
        })
    return out


# Maps the player's `primary_goal` (set on Player Settings page) to drill
# categories that move the needle on that goal. The value is a "boost"
# integer added to the gap-derived weight for that category — small enough
# that a glaring biomech gap still wins, large enough that, given two
# roughly-equal candidate categories, the player's stated goal breaks the
# tie. Tuned on the assumption that gap weights are in the 1-5 range
# (see build_drill_plan).
GOAL_CATEGORY_BOOSTS: dict[str, dict[str, int]] = {
    "More power":            {"hip_rotation": 3, "hip_shoulder_separation": 3,
                              "knee_extension": 2},
    "Better contact":        {"head_stability": 3, "timing": 2},
    "Better timing":         {"timing": 4, "head_stability": 1},
    "Fix timing":            {"timing": 4, "head_stability": 1},  # legacy label
    "Better consistency":    {"head_stability": 2, "timing": 2,
                              "hip_rotation": 1},
    "Improve bat path":      {"hip_shoulder_separation": 3, "knee_extension": 2},
    "Reduce strikeouts":     {"timing": 3, "head_stability": 2},
    "Improve mechanics":     {},          # balanced — no boost
    "Improve overall swing": {},          # balanced — no boost
    "Find MLB comparison":   {},          # not a training goal
}


def build_drill_plan(gaps_ranked, top_n_categories=2, *, preferred_goal=None):
    """Return structured drill-plan data WITHOUT printing.

    Mirrors the prioritization logic of recommend_drills() — top categories
    weighted by rank, top N taken — but returns data instead of printing.

    Parameters
    ----------
    gaps_ranked
        list of result dicts (sorted by similarity ascending) from compare.py
    top_n_categories
        how many drill categories to include in the plan (default 2)
    preferred_goal
        OPTIONAL — the player's `primary_goal` from the Player Settings
        page. When set, drill categories aligned with that goal get a
        small boost so the plan reflects the player's stated focus. A
        large gap still beats a small boost, so the analyzer's findings
        stay authoritative — the goal just breaks ties and re-ranks
        near-tied categories.

    Returns:
        {
          "categories": [
              {"priority": 1, "category": "head_stability",
               "title": "Quiet the Head", "why_it_matters": "...",
               "drills": [{"name": "Wall Drill", "reps": "3 sets of 10",
                           "how": "..."}, ...]},
              ...
          ],
          "weekly_guide": [bullet_str, bullet_str, ...],
          "goal_applied": "<the goal string, or None if no boost ran>"
        }
    """
    empty = {"categories": [], "weekly_guide": [], "goal_applied": None}
    if not gaps_ranked:
        return empty

    category_weights: dict[str, int] = {}
    for rank, gap in enumerate(gaps_ranked[:5]):
        cat = classify_gap(gap)
        if cat is None:
            continue
        weight = 5 - rank
        category_weights[cat] = category_weights.get(cat, 0) + weight

    if not category_weights:
        return empty

    # Apply the player's training-goal boost. We only boost categories
    # that ALREADY appeared in the gap-derived weights — we never invent
    # a category out of nothing, because the player's biomech needs to
    # actually need it for that drill to make sense.
    goal_applied = None
    if preferred_goal:
        boosts = GOAL_CATEGORY_BOOSTS.get(preferred_goal.strip(), {})
        if boosts:
            for cat, bonus in boosts.items():
                if cat in category_weights:
                    category_weights[cat] += bonus
            goal_applied = preferred_goal.strip()

    ordered_cats = sorted(category_weights.items(), key=lambda kv: -kv[1])
    top_cats = [cat for cat, _ in ordered_cats[:top_n_categories]]

    categories = []
    for i, cat in enumerate(top_cats, 1):
        info = DRILL_DB[cat]
        categories.append({
            "priority": i,
            "category": cat,
            "title": info["title"],
            "why_it_matters": info["why_it_matters"],
            "drills": [
                {"name": d["name"], "reps": d["reps"], "how": d["how"]}
                for d in info["drills"]
            ],
        })

    weekly = ["Pick 2 drills from PRIORITY 1 — do them every practice session."]
    if len(top_cats) > 1:
        weekly.append("Pick 1 drill from PRIORITY 2 — do it 3× per week.")
    weekly.append(
        "Re-film and re-run the comparison every 2–3 weeks. The goal is your "
        "similarity score climbing over time."
    )
    if goal_applied:
        weekly.insert(0,
            f"Tuned for your goal: {goal_applied}. Drills picked here weight "
            "the categories that move that goal most."
        )

    return {
        "categories": categories,
        "weekly_guide": weekly,
        "goal_applied": goal_applied,
    }


def classify_gap(result):
    """Map a single gap result dict to a drill category key."""
    group = result.get("group", "")
    label = result.get("label", "").lower()

    if group == "Head":
        return "head_stability"
    if group == "Rotation":
        if "separation" in label:
            return "hip_shoulder_separation"
        return "hip_rotation"
    if group == "Front Knee":
        return "knee_extension"
    if group == "Timing":
        return "timing"
    return None


def recommend_drills(gaps_ranked, top_n_categories=2):
    """Print a personalized drill plan based on the player's biggest gaps.

    gaps_ranked: list of result dicts (sorted by similarity ascending) from
                 compare.py — already excludes slow-mo and camera-angle-flagged
                 metrics.
    top_n_categories: how many drill categories to include (default 2).
    """
    print()
    print("=" * 70)
    print("PERSONALIZED DRILL PLAN")
    print("=" * 70)

    if not gaps_ranked:
        print()
        print("  No comparable gaps were found (all metrics flagged as unreliable).")
        print("  Re-record both videos from a similar angle and at the same fps")
        print("  to get drill recommendations.")
        print()
        return

    # Tally how often each category shows up in the top 5 gaps, weighted by rank.
    category_weights = {}
    for rank, gap in enumerate(gaps_ranked[:5]):
        cat = classify_gap(gap)
        if cat is None:
            continue
        # Earlier-ranked gaps weigh more heavily.
        weight = 5 - rank
        category_weights[cat] = category_weights.get(cat, 0) + weight

    if not category_weights:
        print()
        print("  Couldn't map gaps to drill categories. Skipping recommendations.")
        print()
        return

    # Sort categories by total weight, take top N.
    ordered_cats = sorted(category_weights.items(), key=lambda kv: -kv[1])
    top_cats = [cat for cat, _ in ordered_cats[:top_n_categories]]

    print()
    print(f"  Based on the {len(gaps_ranked)} comparable gap(s), focus on:")
    for i, cat in enumerate(top_cats, 1):
        print(f"    {i}. {DRILL_DB[cat]['title']}")
    print()

    for i, cat in enumerate(top_cats, 1):
        info = DRILL_DB[cat]
        print("-" * 70)
        print(f"PRIORITY {i}: {info['title'].upper()}")
        print("-" * 70)
        # Word-wrap the "why it matters" paragraph manually at ~68 chars.
        why = info["why_it_matters"]
        words = why.split()
        line = "  "
        for w in words:
            if len(line) + len(w) + 1 > 70:
                print(line)
                line = "  " + w
            else:
                line = line + (" " if line.strip() else "") + w
        if line.strip():
            print(line)
        print()
        print("  DRILLS:")
        for j, drill in enumerate(info["drills"], 1):
            print(f"    {j}. {drill['name']}  —  {drill['reps']}")
            # Indent the how-to text and word-wrap.
            words = drill["how"].split()
            line = "       "
            for w in words:
                if len(line) + len(w) + 1 > 70:
                    print(line)
                    line = "       " + w
                else:
                    line = line + (" " if line.strip() else "") + w
            if line.strip():
                print(line)
            print()

    # Quick weekly plan suggestion.
    print("=" * 70)
    print("WEEKLY PRACTICE GUIDE")
    print("=" * 70)
    print(f"  • Pick 2 drills from PRIORITY 1 — do them every practice session.")
    if len(top_cats) > 1:
        print(f"  • Pick 1 drill from PRIORITY 2 — do it 3x per week.")
    print(f"  • Re-film and re-run the comparison every 2–3 weeks to track")
    print(f"    progress. The goal is your similarity score climbing over time.")
    print()


# ---- Standalone mode: print the full drill database ----
if __name__ == "__main__":
    print()
    print("=" * 70)
    print("FULL DRILL DATABASE")
    print("=" * 70)
    for cat, info in DRILL_DB.items():
        print()
        print(f"## {info['title']} ({cat})")
        print(f"   {info['why_it_matters']}")
        print()
        for drill in info["drills"]:
            print(f"   • {drill['name']} — {drill['reps']}")
            print(f"     {drill['how']}")
        print()
