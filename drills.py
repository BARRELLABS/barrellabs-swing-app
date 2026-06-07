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

# Training-aid taxonomy for the Drill Library equipment filter.
# key -> human label. Each drill lists the aids it needs in `equipment`.
EQUIPMENT = {
    'none': 'Just a bat',
    'tee': 'Tee',
    'net': 'Net / cage',
    'soft_toss': 'Soft / front toss (needs a helper)',
    'wall': 'Wall',
    'towel': 'Towel',
    'band': 'Resistance band',
    'weighted_bat': 'Weighted / light bat',
    'pvc': 'PVC / broomstick',
    'med_ball': 'Medicine ball',
    'mirror': 'Mirror',
}

DRILL_DB = {
    'head_stability': {
        "title": 'Quiet the Head',
        "why_it_matters": 'Excessive head movement disconnects your eyes from the ball, leaks power out of your rotation, and makes consistent contact much harder. Elite hitters keep the head almost still through contact so the eyes have a steady platform to track the pitch all the way in.',
        "drills": [
            {"name": 'Wall Drill', "reps": '3 x 10', "equipment": ['wall'],
             "how": 'Stand in your stance with the back of your head lightly touching a wall. Take dry swings without the head leaving the wall. Half speed, build to full.'},
            {"name": 'Towel-on-Head', "reps": '3 x 8', "equipment": ['towel', 'tee'],
             "how": 'Balance a small towel on your head and swing off a tee. Towel falls = head moved. Forces rotation around a stable axis.'},
            {"name": 'Eye-on-the-Tee', "reps": '3 x 10', "equipment": ['tee'],
             "how": "Hit off a tee but keep your eyes locked on the exact spot the ball sat, even after contact. Don't track the ball off the bat."},
            {"name": 'Mirror Feedback', "reps": '5 min', "equipment": ['mirror'],
             "how": 'Swing in front of a full-length mirror, watching head position from setup through finish. Goal: head finishes within a baseball-width of where it started.'},
            {"name": 'Hold-the-Finish', "reps": '3 x 8', "equipment": ['none'],
             "how": 'Take a full dry swing and freeze the finish for 3 seconds, eyes on the contact point. Builds an aware, balanced, quiet head.'},
            {"name": 'Chin-to-Chin', "reps": '3 x 10', "equipment": ['none'],
             "how": 'Start with chin on front shoulder, finish with chin on back shoulder, head staying centered between. Dry swings, slow then full.'},
            {"name": 'Two-Tee Tracking', "reps": '3 x 8', "equipment": ['tee'],
             "how": 'Set a second tee a few inches in front; keep eyes on the back tee through the swing without drifting to the front one.'},
            {"name": 'Still-Head Soft Toss', "reps": '3 x 10', "equipment": ['soft_toss'],
             "how": "Partner soft-tosses; you call out the ball's color/seams as you hit. Forces eyes (not head) to do the tracking."},
        ],
    },
    'hip_rotation': {
        "title": 'Drive the Hips',
        "why_it_matters": "Power comes from the ground up: legs, hips, torso, arms, then the bat. If the hips don't fully rotate through contact you're swinging with arms only and leaving real bat speed and exit velocity on the table.",
        "drills": [
            {"name": 'Hip Turn Step-Throughs', "reps": '3 x 10', "equipment": ['none'],
             "how": 'Slow-motion, no bat: get to your stance and deliberately rotate the back hip all the way through until the belt buckle faces the pitcher.'},
            {"name": 'Back-Foot Squish', "reps": '3 x 12', "equipment": ['none'],
             "how": "Dry swings focusing on 'squishing the bug' — pivot the back foot so the heel turns up and the hip clears fully."},
            {"name": 'Band-Resisted Rotation', "reps": '3 x 12', "equipment": ['band'],
             "how": 'Loop a band at waist height anchored behind you; swing against the pull. Builds rotational strength and teaches the hips to drive, not just turn.'},
            {"name": 'Med-Ball Rotational Throw', "reps": '3 x 8 each side', "equipment": ['med_ball', 'wall'],
             "how": 'Side-on to a wall, explosively throw a medicine ball using hip rotation. Mimics the lower-half fire of a swing.'},
            {"name": 'Walking Hip-Leads', "reps": '3 x 10', "equipment": ['none'],
             "how": 'Walk slowly toward the pitcher, leading each step by firing the hip before the hands. Grooves hip-before-hands sequence.'},
            {"name": 'Tee Pull-Side', "reps": '3 x 10', "equipment": ['tee'],
             "how": 'Set the tee inside and slightly forward; drive a hard pull-side line drive, which only happens with full hip rotation.'},
            {"name": 'PVC Hip Snap', "reps": '3 x 12', "equipment": ['pvc'],
             "how": 'Hold a PVC across the hips; rotate to snap it toward the pitcher fast, hands quiet. Isolates the hip turn.'},
            {"name": 'Front-Toss Hip Focus', "reps": '3 x 10', "equipment": ['soft_toss'],
             "how": 'Partner front-tosses; you exaggerate clearing the back hip on every swing. Add game speed to the feel.'},
        ],
    },
    'hip_shoulder_separation': {
        "title": 'Stretch the X',
        "why_it_matters": "The stretch between the hips and shoulders (the 'X-factor') is the rubber band of the swing. The hips start to open while the shoulders stay closed, loading torque that whips the barrel. No stretch, no whip.",
        "drills": [
            {"name": 'PVC Coil', "reps": '3 x 10', "equipment": ['pvc'],
             "how": 'Hold a PVC across the shoulders; load by turning the shoulders back as the hips begin forward. Feel the stretch, then fire.'},
            {"name": 'Band Separation Hold', "reps": '3 x 8', "equipment": ['band'],
             "how": 'Band anchored in front at chest height; coil away holding tension 2 seconds to feel the stretch, then swing through.'},
            {"name": 'Step-Back Load', "reps": '3 x 10', "equipment": ['none'],
             "how": 'As you stride, consciously keep the shoulders closed an extra beat while the hips go. Dry swings, then on a tee.'},
            {"name": 'Hands-Back Tee', "reps": '3 x 10', "equipment": ['tee'],
             "how": 'On the tee, feel the hands/shoulders stay back as the lower half starts. Hit firm line drives from that stretched position.'},
            {"name": 'Med-Ball Side Toss', "reps": '3 x 8', "equipment": ['med_ball', 'wall'],
             "how": 'Side-on to a wall, toss a med ball into it with a big coil-then-fire, exaggerating the separation, and catch the rebound.'},
            {"name": 'Mirror Coil Check', "reps": '5 min', "equipment": ['mirror'],
             "how": 'In the mirror, freeze at launch: front hip open, shoulders still closed. Train the look of the stretched position.'},
            {"name": 'Slow-Mo Separation', "reps": '3 x 8', "equipment": ['none'],
             "how": 'Full swings at 25% speed, feeling hips lead and shoulders lag. Speed up only once the sequence is clean.'},
            {"name": 'Towel Whip', "reps": '3 x 12', "equipment": ['towel'],
             "how": "Hold a towel like a bat; the loud 'whip' crack only happens with good separation and lag. Chase the sound."},
        ],
    },
    'knee_extension': {
        "title": 'Brace the Front Leg',
        "why_it_matters": 'A firm, extending front leg at contact is the wall the swing rotates against — it converts forward momentum into rotational speed. A soft, bending front leg bleeds power and drops the barrel.',
        "drills": [
            {"name": 'Front-Leg Brace', "reps": '3 x 10', "equipment": ['none'],
             "how": 'Dry swings feeling the front knee straighten and firm up at contact, like bracing into a wall. No drift past the front foot.'},
            {"name": 'Step-Down Brace', "reps": '3 x 8', "equipment": ['none'],
             "how": 'Front foot on a low step/plate; swing feeling the front leg post and stiffen as you rotate over it.'},
            {"name": 'Band-Resisted Stride', "reps": '3 x 10', "equipment": ['band'],
             "how": 'Band around the front thigh pulling back; stride and brace against it so the leg learns to firm up, not collapse.'},
            {"name": 'Firm-Front Tee', "reps": '3 x 10', "equipment": ['tee'],
             "how": 'Hit off a tee with one cue: drive the front knee from soft to locked at contact. Watch for a straight front leg in the finish.'},
            {"name": 'Wall Front-Knee', "reps": '3 x 10', "equipment": ['wall'],
             "how": 'Front foot a few inches from a wall; swing without the front knee drifting forward into it. Stops lunging.'},
            {"name": 'Single-Leg Balance Swing', "reps": '3 x 8', "equipment": ['none'],
             "how": 'Take dry swings balanced mostly on the front leg. Builds the strength and stability to post up at contact.'},
            {"name": 'Soft-Toss Brace', "reps": '3 x 10', "equipment": ['soft_toss'],
             "how": 'Partner soft-tosses; you punctuate each swing by bracing the front leg hard at contact, game speed.'},
            {"name": 'Slow-Mo Post-Up', "reps": '3 x 8', "equipment": ['none'],
             "how": 'Quarter-speed swings holding the braced front-leg position at contact for a 2-count before finishing.'},
        ],
    },
    'sequencing': {
        "title": 'Connect the Chain',
        "why_it_matters": 'A great swing fires in order — hips, then torso, then hands, then barrel. When the chain fires out of order (hands too early) you lose the whip and the barrel drags. Sequencing is timing the links.',
        "drills": [
            {"name": 'Pause-and-Go', "reps": '3 x 8', "equipment": ['none'],
             "how": 'Load, pause fully at the top for 1 second, then fire the lower half first. Removes rushing the hands.'},
            {"name": 'Step-Behind', "reps": '3 x 10', "equipment": ['none'],
             "how": 'Drop the back foot behind, then swing — the momentum forces the lower half to lead the hands.'},
            {"name": 'PVC Bottom-Up', "reps": '3 x 10', "equipment": ['pvc'],
             "how": 'With a PVC, deliberately start every rep from the ground: foot, hip, torso, then arms. Slow then build.'},
            {"name": 'Med-Ball Scoop Toss', "reps": '3 x 8', "equipment": ['med_ball'],
             "how": 'Scoop-toss a med ball forward using legs-then-core-then-arms in order. Grooves bottom-up sequence.'},
            {"name": 'Towel-Under-Arm', "reps": '3 x 10', "equipment": ['towel'],
             "how": "Tuck a towel under the lead arm; keep it pinned until rotation pulls it free. Trains connection so hands don't fly early."},
            {"name": 'Tee Bottom-Up', "reps": '3 x 10', "equipment": ['tee'],
             "how": 'On a tee, exaggerate firing the hips a beat before the hands. Hit line drives only when the order is right.'},
            {"name": 'Band Lag', "reps": '3 x 10', "equipment": ['band'],
             "how": 'Light band on the hands; the resistance makes the hands naturally lag behind the turning body.'},
            {"name": 'Front-Toss Rhythm', "reps": '3 x 10', "equipment": ['soft_toss'],
             "how": 'Partner front-tosses on a steady count; you sync load-and-fire so the swing flows in order at game speed.'},
        ],
    },
    'rotational_speed': {
        "title": 'Add Bat Speed',
        "why_it_matters": 'Bat speed is the single biggest driver of exit velocity and distance. Trained with intent and overload/underload work, the body learns to rotate and whip the barrel faster.',
        "drills": [
            {"name": 'Overload / Underload', "reps": '3 x 8 each', "equipment": ['weighted_bat'],
             "how": 'Alternate sets: a heavier bat (overload) then a lighter one (underload), swinging the light bat as fast as possible. Classic speed builder.'},
            {"name": 'Max-Intent Dry Swings', "reps": '3 x 6', "equipment": ['none'],
             "how": "Full-effort dry swings chasing the loudest 'whoosh.' Pure speed, no ball to distract."},
            {"name": 'Band-Resisted Speed', "reps": '3 x 8', "equipment": ['band'],
             "how": 'Light band pulling the bat back; swing through fast against it, then a set with no band to feel the release.'},
            {"name": 'Med-Ball Slam Rotation', "reps": '3 x 6 each side', "equipment": ['med_ball', 'wall'],
             "how": 'Explosive rotational med-ball throws into a wall, full effort. Trains the body to fire fast.'},
            {"name": 'Tee Max-Effort', "reps": '3 x 6', "equipment": ['tee'],
             "how": 'On the tee, swing at 100% intent for hard line drives. Intent on every rep is what builds speed.'},
            {"name": 'Short-Bat Quick Hands', "reps": '3 x 10', "equipment": ['none'],
             "how": 'Choke way up (or use a short bat) and take fast, compact swings to train quick hands and barrel turn.'},
            {"name": 'Game-Speed Net', "reps": '3 x 8', "equipment": ['net'],
             "how": 'Hit into a net at full game intent, no holding back, focusing on barrel speed through the zone.'},
            {"name": 'Underload Finish', "reps": '3 x 8', "equipment": ['weighted_bat'],
             "how": 'Swing a light bat focusing on a fast, full finish wrapped around the body — train end-of-swing speed.'},
        ],
    },
    'front_side_stability': {
        "title": 'Lock the Front Side',
        "why_it_matters": 'The lead arm and glove side form the brace the barrel rotates around. A firm front side keeps the swing on plane and the barrel in the zone longer; a flying-open front side pulls you off the ball.',
        "drills": [
            {"name": 'Front-Arm Bar', "reps": '3 x 10', "equipment": ['none'],
             "how": 'Dry swings feeling the lead arm stay extended and firm through contact, not collapsing into the body early.'},
            {"name": 'Lead-Arm-Only Tee', "reps": '3 x 8', "equipment": ['tee'],
             "how": 'One-handed tee swings with just the lead arm. Builds the strength and feel of a stable front side.'},
            {"name": 'Wall Front-Side', "reps": '3 x 10', "equipment": ['wall'],
             "how": 'Front shoulder a few inches from a wall; swing without the shoulder flying open into it. Stops pulling off.'},
            {"name": 'Band Pull-Apart', "reps": '3 x 12', "equipment": ['band'],
             "how": 'Band in both hands at chest; rotate into the swing keeping tension so the front side stays firm, not soft.'},
            {"name": 'Glove-Side Brace', "reps": '3 x 10', "equipment": ['none'],
             "how": "Cue: 'pull the front elbow into a firm wall.' Dry swings, then a tee, keeping the glove side stable."},
            {"name": 'One-Hand Lead Toss', "reps": '3 x 8', "equipment": ['soft_toss'],
             "how": 'Partner soft-tosses; hit lead-arm-only to force a strong, stable front side at contact.'},
            {"name": 'Mirror Front-Side Check', "reps": '5 min', "equipment": ['mirror'],
             "how": 'In the mirror, freeze at contact: front side firm, shoulder closed, not pulled out. Train the look.'},
            {"name": 'Stride-and-Stick', "reps": '3 x 8', "equipment": ['none'],
             "how": "Stride and 'stick' the landing with the front side quiet for a beat before swinging. Kills early flying open."},
        ],
    },
    'timing': {
        "title": 'Sharpen the Timing',
        "why_it_matters": "The best mechanics are useless if they fire at the wrong time. Timing is starting the load early enough and letting the barrel arrive on the ball — it's trained by varying speeds and forcing recognition.",
        "drills": [
            {"name": 'Metronome Load', "reps": '5 min', "equipment": ['none'],
             "how": 'Set a steady beat (phone metronome); load on one beat, fire on the next. Grooves an on-time, repeatable rhythm.'},
            {"name": 'Vary-the-Toss', "reps": '3 x 10', "equipment": ['soft_toss'],
             "how": 'Partner mixes soft-toss speeds and timing unpredictably; you adjust your load to stay on time.'},
            {"name": 'Front-Toss Recognition', "reps": '3 x 10', "equipment": ['soft_toss'],
             "how": 'Partner front-tosses from behind a screen at game-like speed; focus only on starting your load early.'},
            {"name": 'High-Tee / Low-Tee', "reps": '3 x 10', "equipment": ['tee'],
             "how": "Alternate a high and low tee each rep so you adjust the swing's timing and plane to the pitch location."},
            {"name": 'Pause Recognition', "reps": '3 x 8', "equipment": ['soft_toss'],
             "how": "Partner holds the ball a random beat before tossing; you hold your load and only fire when it's released."},
            {"name": 'Load-on-Time Dry', "reps": '5 min', "equipment": ['none'],
             "how": 'Watch a pitcher (live or video) and load in rhythm with their delivery, no swing — just train the trigger timing.'},
            {"name": 'Net Pitch-Count', "reps": '3 x 10', "equipment": ['net'],
             "how": 'Hit into a net working counts: shorten up with 2 strikes, look to drive early. Trains situational timing.'},
            {"name": 'Tee Rhythm Reset', "reps": '3 x 10', "equipment": ['tee'],
             "how": 'Between tee swings, reset feet and re-load with the same tempo every time. Builds a repeatable internal clock.'},
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
            f"Your head moves {abs(p):.2f} body-lengths total during the swing — "
            f"{_intensity(ratio)} more than {ref_name}'s {abs(r):.2f}.",

            "Why it costs you: every inch of head movement is ball-tracking "
            "error. Your eyes are reading the pitch from a moving "
            "platform, which shows up as inconsistent contact, mis-hits on the same "
            "pitch you crushed yesterday, and getting fooled on offspeed.",

            "What the fix feels like: keep your eyes glued to the contact spot "
            "so you can read the ball the whole way. The body spins "
            "underneath the eyes — the head stays steady.",
        ]

    if group == "Head" and "Δx" in gap["label"]:
        direction = "toward the pitcher" if p > 0 else "away from the pitcher"
        return [
            f"Your head drifts {abs(p):.2f} body-lengths {direction} during the "
            f"swing while {ref_name} stays at {abs(r):.2f}.",

            "Why it costs you: that forward lurch tells your brain the ball is "
            "arriving faster than it really is, which is why you'll feel late on "
            "fastballs and out in front on changeups. It also kills your back-side "
            "leverage — you can't drive a ball when your weight has already "
            "gone past it.",

            "What the fix feels like: keep your eyes glued to the contact spot "
            "so you can read the ball the whole way. The hips can "
            "move forward, but the head stays stacked.",
        ]

    if group == "Head" and "Δy" in gap["label"]:
        direction = "downward" if p > 0 else "upward"
        return [
            f"Your head moves {abs(p):.2f} body-lengths {direction} through the "
            f"swing — {ref_name} stays nearly level ({abs(r):.2f}).",

            "Why it costs you: vertical head movement is the #1 reason hitters "
            "mis-time pitch HEIGHT. When your eyes drop, high pitches look like "
            "strikes; when they lift, low pitches look hittable. It's also a "
            "sign the spine angle is collapsing — leaking power.",

            "What the fix feels like: keep your eyes glued to the contact spot "
            "so you can read the ball the whole way. The spine angle you set "
            "at foot plant stays steady all the way through contact.",
        ]

    # ---- ROTATION ----
    if group == "Rotation" and "separation" in label and "peak" in label:
        return [
            f"Your peak stretch between hips and shoulders tops out at {p:+.0f}° while "
            f"{ref_name} reaches {r:+.0f}°.",

            "Why it costs you: the stretch between hips firing forward and shoulders "
            "staying loaded is where bat speed actually comes from — it's the "
            "elastic snap that whips the barrel through. With less of that stretch "
            "you're 'spinning' the whole upper body, which feels strong but "
            "produces weak contact.",

            "What the fix feels like: make the bat stay back until the last "
            "second, then whip the barrel straight at the ball. The hips go "
            "first; the hands react.",
        ]

    if group == "Rotation" and "contact" in label:
        return [
            f"At contact your hips have rotated only {p:+.0f}° vs "
            f"{ref_name}'s {r:+.0f}°.",

            "Why it costs you: incomplete hip rotation means you're hitting with "
            "mostly arms. The order your body fires — hips, then torso, then arms "
            "— stops short, and you lose the biggest source of free bat speed.",

            "What the fix feels like: land soft, then push the ground away "
            "so the bat launches up and out. Belly button finishes pointing at the "
            "pitcher — the back foot pivots clean off the ground at the finish.",
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
            "not bracing into contact, energy that should rebound up into the "
            "swing leaks out the bottom — like jumping on a soft mattress.",

            "What the fix feels like: land soft, then push the ground away "
            "so the bat launches up and out. At contact the front leg should "
            "feel 'posted' — firm, braced, not collapsing forward.",
        ]

    # ---- TIMING (rare — usually filtered) ----
    if group == "Timing":
        return [
            f"{gap['label']} timing differs: {p:.0f}{gap['units']} vs "
            f"{ref_name}'s {r:.0f}{gap['units']}.",

            "Why it costs you: a slow swing arrives late and leaves you guessing; "
            "a rushed swing gets fooled. Tempo is everything.",

            "What the fix feels like: keep your front shoulder pointed at "
            "the pitcher until the ball's almost there, then fire the barrel "
            "through the line — short, direct, no wasted motion.",
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
        "What the fix feels like: keep your eyes glued to the contact spot "
        "so you can read the ball the whole way. The body spins underneath "
        "the eyes — the head doesn't go along for the ride."
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
        "legs, hips, torso, arms, then the bat. If the hips don't fully "
        "rotate through contact, you're swinging with mostly arms and "
        "leaving big-time bat speed on the table. That shows up as soft "
        "contact even on balls you square up."
    )

    fix = (
        "What the fix feels like: land soft, then push the ground away "
        "so the bat launches up and out through the zone. Belly button "
        "finishes pointing at the pitcher — the back foot pivots clean "
        "off the ground at the finish."
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
        "Why it costs you: the stretch between your hips firing forward and "
        "your shoulders staying loaded is what snaps the barrel through "
        "the zone. With less of that stretch you're 'spinning' the whole "
        "upper body at once — feels strong, produces weak contact."
    )

    fix = (
        "What the fix feels like: make the bat stay back until the last "
        "second, then whip the barrel straight at the ball. The hips go "
        "first; the hands react to what the hips did."
    )

    return [first, why, fix]


def _narrate_knee(knee_gaps, ref_name):
    """Combined narrative for front-knee gaps."""
    primary = knee_gaps[0]
    p, r = primary["p"], primary["r"]
    label = primary["label"].lower()

    if "re-extension" in label or "re_extension" in label:
        first = (
            f"Your front leg straightens back up {p:+.0f}° between load and contact "
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
        "What the fix feels like: land soft, then push the ground away "
        "so the bat launches up and out. At contact the front leg should "
        "feel 'posted' — firm, braced, not collapsing forward."
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
        "What the fix feels like: keep your front shoulder pointed at "
        "the pitcher until the ball's almost there, then fire the barrel "
        "through the line — short, direct, no wasted motion."
    )

    return [first, why, fix]


def _narrate_sequencing(gaps_in_cat, ref_name):
    """Power Sequence M1 narrative — hip → shoulder lag."""
    first = (
        f"The order your body fires — hips, then chest, then hands — "
        f"isn't happening on a delay. The upper body and the hips need to "
        f"fire separately to transfer full power into the bat."
    )
    why = (
        f"When the shoulders fire at the same time as the hips (or before "
        f"them), the upper body never gets to amplify what the lower body "
        f"started. {ref_name} fires in the right order — hips snap, then "
        f"the shoulders ride the snap. That's where the bat speed comes from."
    )
    fix = (
        "What the fix feels like: make the bat stay back until the last "
        "second, then whip the barrel straight at the ball. The hips go "
        "first; the hands react to what the hips did — they don't initiate."
    )
    return [first, why, fix]


def _narrate_rotational_speed(gaps_in_cat, ref_name):
    """Power Sequence M2 narrative — hip angular velocity."""
    first = (
        f"You're getting through the swing but not at top speed. The "
        f"hips are rotating, just not fast enough to drive elite "
        f"bat speed."
    )
    why = (
        f"How fast your hips snap is like how hard you can throw a ball — "
        f"it's a physical quality you can train. {ref_name} pulls the "
        f"trigger faster, which is why the barrel arrives with the kind "
        f"of speed defenses can't catch up to."
    )
    fix = (
        "What the fix feels like: short and violent, not long and smooth. "
        "Med-ball rotational throws teach the body to recruit power into "
        "the rotation rather than glide through it."
    )
    return [first, why, fix]


def _narrate_front_side_stability(gaps_in_cat, ref_name):
    """Power Sequence M3 narrative — early shoulder fly-out."""
    first = (
        f"Your front shoulder is opening up too early — before the front "
        f"foot has finished planting. That kills the stored power "
        f"between hips and shoulders."
    )
    why = (
        f"When the shoulders fly open early, the entire slingshot "
        f"effect is gone — the hips and shoulders end up firing together "
        f"and the bat has to catch up to a swing that already happened. "
        f"{ref_name} keeps the front shoulder pointed at the pitcher "
        f"until AFTER the front foot is down."
    )
    fix = (
        "What the fix feels like: keep your front shoulder pointed at "
        "the pitcher until the ball's almost there, then fire the barrel "
        "through the line. The front side stays closed while the lower "
        "body loads up — then everything fires."
    )
    return [first, why, fix]


_CATEGORY_NARRATORS = {
    "head_stability":           _narrate_head_stability,
    "hip_rotation":             _narrate_hip_rotation,
    "hip_shoulder_separation":  _narrate_separation,
    "knee_extension":           _narrate_knee,
    "timing":                   _narrate_timing_cat,
    # Power Sequence (new):
    "sequencing":               _narrate_sequencing,
    "rotational_speed":         _narrate_rotational_speed,
    "front_side_stability":     _narrate_front_side_stability,
}

_CATEGORY_TITLES = {
    "head_stability":           "HEAD QUIET",
    "hip_rotation":             "HIP TURN COMPLETION",
    "hip_shoulder_separation":  "TORQUE STORAGE",
    "knee_extension":           "LOWER-BODY DRIVE",
    "timing":                   "TIMING & TEMPO",
    # Power Sequence (new):
    "sequencing":               "POWER SEQUENCE",
    "rotational_speed":         "ROTATIONAL SPEED",
    "front_side_stability":     "STAY CLOSED",
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
    "More power": {
        "rotational_speed":          4,   # NEW — primary mapping
        "sequencing":                3,   # NEW — secondary
        "hip_rotation":              2,
        "hip_shoulder_separation":   2,
        "knee_extension":            1,
    },
    "Better contact": {
        "front_side_stability":      3,   # NEW — primary mapping
        "head_stability":            3,
        "sequencing":                2,   # NEW — secondary
        "timing":                    2,
    },
    "Better timing": {
        "sequencing":                4,   # NEW — exact match for "timing"
        "timing":                    3,
        "head_stability":            1,
    },
    "Fix timing": {                       # legacy label, alias the above
        "sequencing":                4,
        "timing":                    3,
        "head_stability":            1,
    },
    "Better consistency": {
        "front_side_stability":      2,   # NEW
        "head_stability":            2,
        "timing":                    2,
        "hip_rotation":              1,
    },
    "Improve bat path": {
        "front_side_stability":      3,   # NEW — bat path is tied to front side
        "hip_shoulder_separation":   3,
        "knee_extension":            2,
    },
    "Reduce strikeouts": {
        "timing":                    3,
        "head_stability":            2,
        "sequencing":                2,   # NEW
    },
    "Improve mechanics":     {},
    "Improve overall swing": {},
    "Find MLB comparison":   {},
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
        "Swing Score climbing over time."
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
    """Map a single gap result dict to a drill category key.

    Three new Power Sequence categories (Phase Power Sequence redesign):
      - sequencing            (kinematic chain — pelvis → torso lag)
      - rotational_speed      (peak hip angular velocity)
      - front_side_stability  (early shoulder fly-out)

    The new gaps are synthesized in analyzer.py from the `sequence`
    block's rating fields — see _synthesize_sequence_gaps() there.
    """
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
    if group == "Power Sequence":
        if "sequencing" in label or "lag" in label:
            return "sequencing"
        if "hip speed" in label or "omega" in label or "rotational speed" in label:
            return "rotational_speed"
        if "stay closed" in label or "fly-out" in label or "front-side" in label:
            return "front_side_stability"
    return None


# ---- PILLAR → CATEGORY MAPPING ----
# Maps the four swing-score pillars to drill categories per the spec.
# (sequence → sequencing, stability → head_stability, timing → timing,
#  stride → knee_extension).

_PILLAR_TO_CATEGORY = {
    "sequence":  "sequencing",
    "stability": "head_stability",
    "timing":    "timing",
    "stride":    "knee_extension",
}

# Verbs per pillar for the pro-relative motivation line.
_PILLAR_VERBS = {
    "sequence":  "sequences",
    "stability": "stays quiet on the ball",
    "timing":    "stays on time",
    "stride":    "lands and braces",
}


def gaps_from_pillars(pillars: dict) -> list:
    """Convert the Score pillars dict into a gap list that classify_gap /
    build_drill_plan already understand.

    Parameters
    ----------
    pillars
        The ``result["pillars"]`` dict from analyzer.analyze():
        {sequence|stability|timing|stride: {compliance, confidence, label}}.

    Returns
    -------
    list of gap dicts sorted by weakest CONFIDENT pillar first (lowest
    compliance among pillars with confidence > 0). Pillars with
    confidence == 0 or compliance is None are skipped entirely.

    Each gap entry has the minimal shape classify_gap requires:
      {"group": str, "label": str, "p": float, "r": float, "units": str,
       "similarity": float, "pillar": str}
    """
    # Collect confident pillars.
    entries = []
    for pillar_name, pillar in pillars.items():
        compliance = pillar.get("compliance")
        confidence = pillar.get("confidence", 0.0)
        if confidence <= 0 or compliance is None:
            continue
        category = _PILLAR_TO_CATEGORY.get(pillar_name)
        if category is None:
            continue
        entries.append({
            "pillar":     pillar_name,
            "compliance": compliance,
            "confidence": confidence,
            "category":   category,
        })

    # Sort by weakest compliance first (ascending).
    entries.sort(key=lambda e: e["compliance"])

    # Convert to the gap dict shape classify_gap / build_drill_plan expect.
    # We set similarity = compliance * 100 (so lowest compliance → lowest
    # similarity → ranks first in the drill plan). group + label must route
    # correctly through classify_gap.
    gaps = []
    for entry in entries:
        cat = entry["category"]
        # Build a group/label pair that routes through classify_gap correctly.
        if cat == "sequencing":
            group, label = "Power Sequence", "Sequencing lag"
        elif cat == "head_stability":
            group, label = "Head", "Total head drift (torso-rel)"
        elif cat == "timing":
            group, label = "Timing", "Foot plant → launch"
        elif cat == "knee_extension":
            group, label = "Front Knee", "Re-extension"
        else:
            group, label = "Power Sequence", cat

        gaps.append({
            "group":     group,
            "label":     label,
            "p":         entry["compliance"],
            "r":         1.0,        # "ideal" reference compliance
            "units":     "",
            "similarity": entry["compliance"] * 100,
            "pillar":    entry["pillar"],
            "synthetic": True,
        })

    return gaps


def pro_relative_line(pillar: str, pro_name: str) -> str:
    """Return the one short pro-relative motivation line for a fix card.

    Template (from spec):
        "This one tightens the move that gets you closer to how {pro} {verb}."

    Verbs per pillar:
        sequence  → "sequences"
        stability → "stays quiet on the ball"
        timing    → "stays on time"
        stride    → "lands and braces"

    The line is NEVER phrased as a fault.
    """
    verb = _PILLAR_VERBS.get(pillar, "plays")
    return f"This one tightens the move that gets you closer to how {pro_name} {verb}."


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
    print(f"    progress. The goal is your Swing Score climbing over time.")
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
