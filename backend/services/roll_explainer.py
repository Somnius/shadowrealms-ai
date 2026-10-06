"""
`/ai explain`: a step-by-step explanation of one dice roll, built only from the stored roll.

The facts (dice, which dice are Hunger dice, difficulty, specialty / Willpower, successes,
criticals, margin, outcome, room leniency, rerolls) come from the dice_rolls row and the chat
card (the dice_animation marker), and are re-counted with the app's own dice engines
(services.v5_dice.resolve_v5, services.wod_dice.resolve_classic, services.v5_dice.resolve_rouse).
When the re-count disagrees with what was stored, the explanation says so instead of picking one.
No LLM is involved here; routes/ai.py and services/ai_slash_commands.py may add a short
Storyteller line after it.

Three layers:
- build_*_record(): a dice_rolls row (+ marker) or a marker alone -> a plain record dict;
- explain(record, lang): the record -> {markdown, summary, facts, mismatches} in 'en' or 'el'
  (game terms stay English: Hunger, bestial failure, messy critical, botch, ...);
- find_roll(cursor, ...): which roll to explain (the replied-to dice card, else the newest roll
  in the room the requester can see; hidden rolls only for staff).

Page refs are the ones docs/rules/V5.md and docs/rules/CLASSIC_REVISED.md cite.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from services.message_actions import hidden_dice_sql_filter, is_hidden_kind

V5 = "v5"
CLASSIC = "classic"
ROUSE = "rouse"

# ---------------------------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------------------------


def _json(value: Any, default: Any) -> Any:
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _ints(values: Any) -> List[int]:
    out = []
    for v in values or []:
        if isinstance(v, bool):
            continue
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            continue
    return out


def _int_or(value: Any, default: Optional[int]) -> Optional[int]:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_record_from_row(row: Dict[str, Any], marker: Optional[Dict[str, Any]] = None,
                          game_system: str = "") -> Optional[Dict[str, Any]]:
    """A dice_rolls row (dict) and, optionally, the chat card's marker -> record. None if unusable."""
    if not row:
        return None
    mods = _json(row.get("modifiers"), {})
    if not isinstance(mods, dict):
        mods = {}
    results = _ints(_json(row.get("results"), []))
    roll_type = str(row.get("roll_type") or "")
    base = {
        "roll_id": row.get("id"),
        "source": "record",
        "roll_type": roll_type,
        "action": str(row.get("action_description") or ""),
        "character_name": row.get("character_name"),
        "username": row.get("username"),
        "difficulty": _int_or(row.get("difficulty"), None),
        "stored": {
            "successes": _int_or(row.get("successes"), None),
            "is_botch": bool(row.get("is_botch")),
            "is_critical": bool(row.get("is_critical")),
        },
        "marker": marker if isinstance(marker, dict) else None,
        "card_kind": (marker or {}).get("roll_kind") if isinstance(marker, dict) else None,
        "hidden": bool((mods.get("posted") or {}).get("hidden")) if isinstance(mods.get("posted"), dict) else False,
    }
    edition = str(mods.get("rules_edition") or "").lower()
    if roll_type == "rouse":
        return {
            **base,
            "edition": ROUSE,
            "die": results[0] if results else None,
            "hunger_before": _int_or(mods.get("hunger_before"), None),
            "stored_hunger_after": _int_or(mods.get("hunger_after"), None),
        }
    if edition == V5:
        normal = mods.get("normal_dice")
        hunger = mods.get("hunger_dice")
        if normal is None and hunger is None:
            # Older rows: results are normal dice then Hunger dice (services.v5_dice.resolve_v5).
            h = max(0, min(_int_or(mods.get("hunger"), 0) or 0, len(results)))
            normal, hunger = results[: len(results) - h], results[len(results) - h:]
        rerolled = bool(mods.get("rerolled"))
        return {
            **base,
            "edition": V5,
            "normal_dice": _ints(normal),
            "hunger_dice": _ints(hunger),
            "difficulty": base["difficulty"] if base["difficulty"] is not None else 1,
            "v5_leniency": mods.get("v5_leniency"),
            "rerolled": rerolled,
            "rerolled_indices": _ints(mods.get("rerolled_indices")) if rerolled else [],
            "original_normal_dice": _ints(mods.get("original_normal_dice")) if rerolled else [],
            "willpower_cost": mods.get("willpower_cost") if rerolled else None,
            "sheet_hunger": _int_or(mods.get("sheet_hunger"), None),
            "hunger_override": _int_or(mods.get("hunger_override"), None),
        }
    from services.rules_edition import reroll_ones_cancel

    roc = mods.get("reroll_ones_cancel")
    return {
        **base,
        "edition": CLASSIC,
        "dice": results,
        "difficulty": base["difficulty"] if base["difficulty"] is not None else 6,
        "specialty": bool(mods.get("specialty")),
        "specialty_rerolls": _ints(mods.get("specialty_rerolls")),
        "willpower": bool(mods.get("willpower")),
        "reroll_ones_cancel": bool(roc) if roc is not None else reroll_ones_cancel(game_system),
        "leniency_floor": _int_or(mods.get("leniency_floor"), None),
    }


def build_record_from_marker(marker: Dict[str, Any], game_system: str = "") -> Optional[Dict[str, Any]]:
    """
    A chat card without a stored roll (the admin `/ai roll` flow builds the marker in the
    browser) -> record from the dice on the card. None when the card doesn't show every die.
    """
    if not isinstance(marker, dict):
        return None
    preview = _ints(marker.get("dice_preview"))
    if not preview or _int_or(marker.get("extra_dice_count"), 0):
        return None
    stored = {
        "successes": _int_or(marker.get("successes"), None),
        "is_botch": bool(marker.get("is_botch")),
        "is_critical": bool(marker.get("is_critical")),
    }
    base = {"roll_id": None, "source": "card", "roll_type": "card", "action": "",
            "character_name": None, "username": None, "stored": stored, "marker": marker,
            "card_kind": marker.get("roll_kind")}
    if str(marker.get("rules_edition") or "").lower() == V5:
        flags = marker.get("hunger_flags") if isinstance(marker.get("hunger_flags"), list) else []
        normal = [d for i, d in enumerate(preview) if not (i < len(flags) and flags[i])]
        hunger = [d for i, d in enumerate(preview) if i < len(flags) and flags[i]]
        return {**base, "edition": V5, "normal_dice": normal, "hunger_dice": hunger,
                "difficulty": _int_or(marker.get("difficulty"), 1), "v5_leniency": None,
                "rerolled": False, "rerolled_indices": [], "original_normal_dice": [],
                "willpower_cost": None, "sheet_hunger": None, "hunger_override": None}
    from services.rules_edition import reroll_ones_cancel

    return {**base, "edition": CLASSIC, "dice": preview,
            "difficulty": _int_or(marker.get("difficulty"), 6),
            "specialty": bool(marker.get("specialty")),
            "specialty_rerolls": _ints(marker.get("specialty_rerolls")),
            "willpower": bool(marker.get("willpower")),
            "reroll_ones_cancel": reroll_ones_cancel(game_system), "leniency_floor": None}


# ---------------------------------------------------------------------------------------------
# Wording
# ---------------------------------------------------------------------------------------------

T = {
    "en": {
        "title": "**Roll explained**",
        "roll_no": "roll #{id}",
        "by": "Rolled by **{who}**.",
        "dice": "**Dice:** {dice}",
        "v5_pool": "- **Pool:** {pool} dice ({h} Hunger). **Difficulty:** {diff} (successes needed, core pp. 118–121).",
        "counting": "**Counting**",
        "v5_step1": "1. Each die showing 6 or more is one success (core pp. 118–121). Dice at 6+: {list} → **{n}**.",
        "v5_step2_none": "2. Each pair of 10s adds 2 more successes, so a pair counts 4 (pp. 120–121). 10s: none → no pair.",
        "v5_step2_one": "2. Each pair of 10s adds 2 more successes, so a pair counts 4 (pp. 120–121). 10s: one → no pair.",
        "v5_step2": "2. Each pair of 10s adds 2 more successes, so a pair counts 4 (pp. 120–121). 10s: {tens} → {pairs} pair(s) → **+{bonus}**.",
        "v5_step3": "3. **{s} successes** against difficulty **{diff}** → margin **{margin}** (margin = successes − difficulty, p. 121).",
        "none": "none",
        "result": "**Result: {label}**",
        "first_roll": "**First roll:** {dice} → {s} successes ({label}).",
        "wp_reroll": "**Willpower reroll** (p. 122): {changes}. Hunger dice are never rerolled; the counting below is for the dice after the reroll.",
        "wp_cost_sup": " It cost 1 Willpower (1 Superficial Willpower damage, p. 126).",
        "wp_cost_agg": " It cost 1 Willpower; the track was full, so a Superficial box turned Aggravated (p. 126).",
        "card_first": "_The card you replied to shows the first roll; this roll was later rerolled with Willpower._",
        "die_no": "die #{i}: {a} → {b}",
        "hunger_note": "_Hunger {used} was used for this roll; the character sheet said {sheet}._",
        "lenient_v5": "_Room leniency was on for this roll ({desc}). It shaped which faces the dice could show; the counting is the normal rule._",
        "lenient_v5_reroll": "_Room leniency was on for the first roll only ({desc}); the Willpower reroll used plain dice._",
        "mean_win": "- **Win:** {s} successes reach difficulty {diff}. The margin ({margin}) is what damage and many powers scale with (p. 121).",
        "mean_crit": "- **Critical win:** a winning roll with at least one pair of 10s (pp. 120–121): an especially good result.",
        "mean_messy": "- **Messy critical:** a critical win where a 10 is on a Hunger die (p. 207). It succeeds, but the Beast's way: Stains, a Masquerade breach or losing an Advantage dot are typical; if none fits, the mess turns it into a failure.",
        "mean_fail": "- **Failure:** {s} of {diff} successes needed. With some successes the Storyteller may offer a win at a cost (p. 121).",
        "mean_total": "- **Total failure:** zero successes (p. 122). What it costs is the Storyteller's call.",
        "mean_bestial": "- **Bestial failure:** the roll failed and a Hunger die shows **1** (p. 207). In play the Beast acts: typically a Compulsion (pp. 208–211); gentler options are losing an Advantage dot, Aggravated Health damage or +1 Hunger (above 5 that means a hunger frenzy test at difficulty 4).",
        "cl_dice": "**Dice:** {dice} at difficulty **{diff}**",
        "cl_step1": "1. Each die showing {diff} or more is a success; a 10 always is (core pp. 190–191): {list} → **{n}**.",
        "cl_step2_none": "2. Each 1 cancels one success (p. 192): no 1s.",
        "cl_step2": "2. Each 1 cancels one success (p. 192): {ones} × 1 → **−{ones}**.",
        "cl_spec": "{k}. Specialty (p. 117): each 10 counts and is rolled again, and a 10 on a reroll is rolled again too. Rerolls: {list} → **+{n}**.",
        "cl_spec_ones_cancel": " In this game line a rerolled 1 cancels one success (Mage Revised): **−{n}**.",
        "cl_spec_ones_keep": " A rerolled 1 cancels nothing here (rerolls only add).",
        "cl_wp": "{k}. Willpower (pp. 137, 193): **+1** automatic success that 1s can't cancel.",
        "cl_net": "→ **{n} net successes** (never below 0).",
        "cl_botch": "**Result: Botch** — no die succeeded and at least one 1 showed (p. 192). A botch is worse than a plain failure: something goes wrong, and the Storyteller decides what.",
        "cl_fail_cancelled": "**Result: Failure** — successes were rolled, but the 1s cancelled them. That is a plain failure, not a botch (p. 192).",
        "cl_fail": "**Result: Failure** — no successes.",
        "cl_success_one": "**Result: Success** — 1 net success (a marginal success).",
        "cl_success": "**Result: Success** — {n} net successes.",
        "cl_exceptional": "**Result: Exceptional success** — 4 net successes (Revised degrees of success: 1 marginal, 2 moderate, 3 complete, 4 exceptional, 5 or more phenomenal).",
        "cl_phenomenal": "**Result: Phenomenal success** — {n} net successes (Revised degrees of success: 5 or more is phenomenal).",
        "cl_wp_saved": "_Without Willpower this would have been a botch; the bought success stands (pp. 137, 193)._",
        "cl_lenient": "_Room leniency floor {f} was on for this roll: no 1s, and with 2 or more dice one die is at least {f}. It shaped the dice; the counting is the normal rule._",
        "rouse_title": "**Rouse check** (V5, pp. 123, 211)",
        "rouse_rule": "One die, no Hunger dice: 6 or more = Hunger stays the same; otherwise Hunger +1 (max 5). The effect that called for the check happens either way.",
        "rouse_ok": "Rolled **{die}** → success: Hunger stays **{h}**.",
        "rouse_fail": "Rolled **{die}** → failure: Hunger **{a} → {b}**.",
        "rouse_max": "Rolled **{die}** → failure at Hunger **5**: Hunger can't rise further, so the vampire makes a hunger frenzy test at difficulty 4 (p. 211).",
        "check_ok": "_Checked: re-counting the dice with the app's {rules} rules gives the same result as the stored roll._",
        "check_bad": "**Note:** re-counting the dice with the app's {rules} rules gives a different result from what was stored ({diffs}). The explanation above follows the dice; please tell the Storyteller or an admin.",
        "card_only": "_There is no stored roll record for this card (an `/ai roll` card); this is explained from the dice shown on the card._",
        "rules_v5": "V5",
        "rules_classic": "Classic (Revised)",
        "rules_rouse": "V5 Rouse",
        "note_latest": "_Explaining the latest roll in this room. Reply to a dice card with `/ai explain` to pick another one._",
        "note_reply_not_roll": "_The message you replied to isn't a dice roll, so this explains the latest roll in this room._",
        "nothing": "**`/ai explain`**\n\nThere is no roll to explain in this room yet. Roll dice, then reply to the dice card with `/ai explain`.",
        "no_record": "**`/ai explain`**\n\nThat dice card has no stored roll the app can read, so it can't be explained.",
        "storyteller": "**Storyteller:** {text}",
        "labels": {
            "win": "Win", "critical": "Critical win", "messy": "Messy critical",
            "fail": "Failure", "bestial": "Bestial failure", "total": "Total failure",
        },
        "field": {"successes": "successes", "is_critical": "critical", "is_botch": "botch",
                  "outcome": "outcome", "is_messy_critical": "messy critical",
                  "is_bestial_failure": "bestial failure", "is_total_failure": "total failure",
                  "margin": "margin", "hunger_after": "Hunger after"},
        "recount_says": "{field}: re-count {a}, stored {b}",
    },
    "el": {
        "title": "**Εξήγηση ρίψης**",
        "roll_no": "ρίψη #{id}",
        "by": "Έριξε: **{who}**.",
        "dice": "**Ζάρια:** {dice}",
        "v5_pool": "- **Pool:** {pool} ζάρια ({h} Hunger). **Δυσκολία:** {diff} (επιτυχίες που χρειάζονται, core σσ. 118–121).",
        "counting": "**Μέτρημα**",
        "v5_step1": "1. Κάθε ζάρι με 6 ή παραπάνω είναι μία επιτυχία (core σσ. 118–121). Ζάρια με 6+: {list} → **{n}**.",
        "v5_step2_none": "2. Κάθε ζευγάρι 10 δίνει 2 επιπλέον επιτυχίες, άρα ένα ζευγάρι μετράει για 4 (σσ. 120–121). 10: κανένα → κανένα ζευγάρι.",
        "v5_step2_one": "2. Κάθε ζευγάρι 10 δίνει 2 επιπλέον επιτυχίες, άρα ένα ζευγάρι μετράει για 4 (σσ. 120–121). 10: ένα → κανένα ζευγάρι.",
        "v5_step2": "2. Κάθε ζευγάρι 10 δίνει 2 επιπλέον επιτυχίες, άρα ένα ζευγάρι μετράει για 4 (σσ. 120–121). 10: {tens} → {pairs} ζευγάρι(α) → **+{bonus}**.",
        "v5_step3": "3. **{s} επιτυχίες** έναντι δυσκολίας **{diff}** → περιθώριο (margin) **{margin}** (περιθώριο = επιτυχίες − δυσκολία, σ. 121).",
        "none": "κανένα",
        "result": "**Αποτέλεσμα: {label}**",
        "first_roll": "**Πρώτη ρίψη:** {dice} → {s} επιτυχίες ({label}).",
        "wp_reroll": "**Ξαναρίξιμο με Willpower** (σ. 122): {changes}. Τα ζάρια Hunger δεν ξαναρίχνονται ποτέ· το μέτρημα παρακάτω είναι για τα ζάρια μετά το ξαναρίξιμο.",
        "wp_cost_sup": " Κόστισε 1 Willpower (1 Superficial ζημιά στο Willpower, σ. 126).",
        "wp_cost_agg": " Κόστισε 1 Willpower· η μπάρα ήταν γεμάτη, οπότε ένα Superficial κουτάκι έγινε Aggravated (σ. 126).",
        "card_first": "_Η κάρτα στην οποία απάντησες δείχνει την πρώτη ρίψη· η ρίψη αυτή ξαναρίχτηκε αργότερα με Willpower._",
        "die_no": "ζάρι #{i}: {a} → {b}",
        "hunger_note": "_Σε αυτή τη ρίψη χρησιμοποιήθηκε Hunger {used}· το φύλλο χαρακτήρα έγραφε {sheet}._",
        "lenient_v5": "_Σε αυτή τη ρίψη ίσχυε η επιείκεια του δωματίου ({desc}). Αυτή επηρέασε ποιες όψεις μπορούσαν να φέρουν τα ζάρια· το μέτρημα είναι ο κανονικός κανόνας._",
        "lenient_v5_reroll": "_Η επιείκεια του δωματίου ίσχυε μόνο στην πρώτη ρίψη ({desc})· το ξαναρίξιμο με Willpower έγινε με κανονικά ζάρια._",
        "mean_win": "- **Επιτυχία (win):** {s} επιτυχίες φτάνουν τη δυσκολία {diff}. Με το περιθώριο ({margin}) κλιμακώνονται η ζημιά και πολλές δυνάμεις (σ. 121).",
        "mean_crit": "- **Critical win:** επιτυχημένη ρίψη με τουλάχιστον ένα ζευγάρι 10 (σσ. 120–121): ιδιαίτερα καλό αποτέλεσμα.",
        "mean_messy": "- **Messy critical:** critical win όπου ένα 10 είναι σε ζάρι Hunger (σ. 207). Πετυχαίνει, αλλά με τον τρόπο του Θηρίου (the Beast): συνήθως Stains, παραβίαση της Masquerade ή απώλεια μιας τελείας Advantage· αν δεν ταιριάζει τίποτα, το χάος τη μετατρέπει σε αποτυχία.",
        "mean_fail": "- **Αποτυχία:** {s} από τις {diff} επιτυχίες που χρειάζονταν. Αν υπάρχουν κάποιες επιτυχίες, ο Storyteller μπορεί να προσφέρει επιτυχία με κόστος (σ. 121).",
        "mean_total": "- **Total failure:** καμία επιτυχία (σ. 122). Τι κοστίζει το αποφασίζει ο Storyteller.",
        "mean_bestial": "- **Bestial failure:** η ρίψη απέτυχε και ένα ζάρι Hunger δείχνει **1** (σ. 207). Στο παιχνίδι δρα το Θηρίο (the Beast): συνήθως ένα Compulsion (σσ. 208–211)· πιο ήπιες επιλογές είναι η απώλεια μιας τελείας Advantage, Aggravated ζημιά στο Health ή +1 Hunger (πάνω από 5 σημαίνει τεστ hunger frenzy με δυσκολία 4).",
        "cl_dice": "**Ζάρια:** {dice} με δυσκολία **{diff}**",
        "cl_step1": "1. Κάθε ζάρι με {diff} ή παραπάνω είναι επιτυχία· το 10 είναι πάντα (core σσ. 190–191): {list} → **{n}**.",
        "cl_step2_none": "2. Κάθε 1 ακυρώνει μία επιτυχία (σ. 192): κανένα 1.",
        "cl_step2": "2. Κάθε 1 ακυρώνει μία επιτυχία (σ. 192): {ones} × 1 → **−{ones}**.",
        "cl_spec": "{k}. Specialty (σ. 117): κάθε 10 μετράει και ξαναρίχνεται, και ένα 10 στο ξαναρίξιμο ξαναρίχνεται κι αυτό. Ξαναριξίματα: {list} → **+{n}**.",
        "cl_spec_ones_cancel": " Σε αυτή τη σειρά παιχνιδιών ένα 1 στο ξαναρίξιμο ακυρώνει μία επιτυχία (Mage Revised): **−{n}**.",
        "cl_spec_ones_keep": " Εδώ ένα 1 στο ξαναρίξιμο δεν ακυρώνει τίποτα (τα ξαναριξίματα μόνο προσθέτουν).",
        "cl_wp": "{k}. Willpower (σσ. 137, 193): **+1** αυτόματη επιτυχία που τα 1 δεν ακυρώνουν.",
        "cl_net": "→ **{n} καθαρές επιτυχίες** (ποτέ κάτω από 0).",
        "cl_botch": "**Αποτέλεσμα: Botch** — κανένα ζάρι δεν πέτυχε και φάνηκε τουλάχιστον ένα 1 (σ. 192). Το botch είναι χειρότερο από μια απλή αποτυχία: κάτι πάει στραβά και το τι αποφασίζει ο Storyteller.",
        "cl_fail_cancelled": "**Αποτέλεσμα: Αποτυχία** — υπήρξαν επιτυχίες, αλλά τα 1 τις ακύρωσαν. Αυτό είναι απλή αποτυχία, όχι botch (σ. 192).",
        "cl_fail": "**Αποτέλεσμα: Αποτυχία** — καμία επιτυχία.",
        "cl_success_one": "**Αποτέλεσμα: Επιτυχία** — 1 καθαρή επιτυχία (οριακή επιτυχία).",
        "cl_success": "**Αποτέλεσμα: Επιτυχία** — {n} καθαρές επιτυχίες.",
        "cl_exceptional": "**Αποτέλεσμα: Εξαιρετική επιτυχία** — 4 καθαρές επιτυχίες (βαθμοί επιτυχίας του Revised: 1 οριακή, 2 μέτρια, 3 πλήρης, 4 εξαιρετική, 5 ή περισσότερες εκπληκτική).",
        "cl_phenomenal": "**Αποτέλεσμα: Εκπληκτική επιτυχία** — {n} καθαρές επιτυχίες (βαθμοί επιτυχίας του Revised: 5 ή περισσότερες είναι εκπληκτική).",
        "cl_wp_saved": "_Χωρίς το Willpower αυτό θα ήταν botch· η επιτυχία που αγοράστηκε μένει (σσ. 137, 193)._",
        "cl_lenient": "_Σε αυτή τη ρίψη ίσχυε το κατώτατο όριο επιείκειας {f} του δωματίου: κανένα 1, και με 2 ή περισσότερα ζάρια ένα ζάρι είναι τουλάχιστον {f}. Αυτό επηρέασε τα ζάρια· το μέτρημα είναι ο κανονικός κανόνας._",
        "rouse_title": "**Rouse check** (V5, σσ. 123, 211)",
        "rouse_rule": "Ένα ζάρι, χωρίς ζάρια Hunger: με 6 ή παραπάνω το Hunger μένει ίδιο· αλλιώς Hunger +1 (έως 5). Η δύναμη που απαίτησε το check ενεργοποιείται έτσι κι αλλιώς.",
        "rouse_ok": "Έφερε **{die}** → επιτυχία: το Hunger μένει **{h}**.",
        "rouse_fail": "Έφερε **{die}** → αποτυχία: Hunger **{a} → {b}**.",
        "rouse_max": "Έφερε **{die}** → αποτυχία με Hunger **5**: το Hunger δεν ανεβαίνει άλλο, οπότε ο βρικόλακας κάνει τεστ hunger frenzy με δυσκολία 4 (σ. 211).",
        "check_ok": "_Έλεγχος: το ξαναμέτρημα των ζαριών με τους κανόνες {rules} της εφαρμογής δίνει το ίδιο αποτέλεσμα με την αποθηκευμένη ρίψη._",
        "check_bad": "**Σημείωση:** το ξαναμέτρημα των ζαριών με τους κανόνες {rules} της εφαρμογής δίνει άλλο αποτέλεσμα από αυτό που αποθηκεύτηκε ({diffs}). Η εξήγηση παραπάνω ακολουθεί τα ζάρια· ενημέρωσε τον Storyteller ή έναν διαχειριστή.",
        "card_only": "_Δεν υπάρχει αποθηκευμένη εγγραφή για αυτή την κάρτα (κάρτα `/ai roll`)· η εξήγηση βασίζεται στα ζάρια που δείχνει η κάρτα._",
        "rules_v5": "V5",
        "rules_classic": "Classic (Revised)",
        "rules_rouse": "V5 Rouse",
        "note_latest": "_Εξηγείται η πιο πρόσφατη ρίψη σε αυτό το δωμάτιο. Απάντησε σε μια κάρτα ζαριών με `/ai explain` για να διαλέξεις άλλη._",
        "note_reply_not_roll": "_Το μήνυμα στο οποίο απάντησες δεν είναι ρίψη ζαριών, οπότε εξηγείται η πιο πρόσφατη ρίψη σε αυτό το δωμάτιο._",
        "nothing": "**`/ai explain`**\n\nΔεν υπάρχει ακόμα ρίψη για εξήγηση σε αυτό το δωμάτιο. Ρίξε ζάρια και απάντησε στην κάρτα των ζαριών με `/ai explain`.",
        "no_record": "**`/ai explain`**\n\nΑυτή η κάρτα ζαριών δεν έχει αποθηκευμένη ρίψη που μπορεί να διαβάσει η εφαρμογή, οπότε δεν μπορεί να εξηγηθεί.",
        "storyteller": "**Storyteller:** {text}",
        "labels": {
            "win": "Επιτυχία", "critical": "Critical win", "messy": "Messy critical",
            "fail": "Αποτυχία", "bestial": "Bestial failure", "total": "Total failure",
        },
        "field": {"successes": "επιτυχίες", "is_critical": "critical", "is_botch": "botch",
                  "outcome": "αποτέλεσμα", "is_messy_critical": "messy critical",
                  "is_bestial_failure": "bestial failure", "is_total_failure": "total failure",
                  "margin": "περιθώριο", "hunger_after": "Hunger μετά"},
        "recount_says": "{field}: ξαναμέτρημα {a}, αποθηκευμένο {b}",
    },
}


_MD_LINK_RE = re.compile(r"!?\[([^\]\n]*)\]\([^)\n]*\)")
_MD_CONTROL_RE = re.compile(r"[`*_~#>|\[\]()<>!\\]")
_URL_RE = re.compile(r"\b(?:https?|ftp|javascript|data):\S*", re.IGNORECASE)


def plain_text(value: Any, limit: int) -> str:
    """
    Player-written text (roll reason, character or user name) as plain words for the
    Storyteller-attributed explanation: links reduced to their label, URLs and markdown
    control characters (backticks, emphasis, headings, quotes, brackets) removed, one line.
    """
    t = _MD_LINK_RE.sub(r"\1", str(value or ""))
    t = _URL_RE.sub("", t)
    t = _MD_CONTROL_RE.sub("", t)
    t = " ".join(t.split())
    return t[:limit].rstrip()


def _t(lang: str) -> Dict[str, Any]:
    return T["el"] if lang == "el" else T["en"]


def _signed(n: int) -> str:
    return f"+{n}" if n > 0 else (f"−{-n}" if n < 0 else "0")


def _join(values: Sequence[Any]) -> str:
    return " · ".join(str(v) for v in values)


def _list_or_none(values: Sequence[Any], tr: Dict[str, Any]) -> str:
    return ", ".join(str(v) for v in values) if values else tr["none"]


def _yes_no(v: Any, lang: str) -> str:
    if isinstance(v, bool):
        return ("ναι" if v else "όχι") if lang == "el" else ("yes" if v else "no")
    return str(v)


# ---------------------------------------------------------------------------------------------
# V5
# ---------------------------------------------------------------------------------------------


def v5_labels(res: Dict[str, Any]) -> List[str]:
    """Outcome label keys of a resolve_v5 result: e.g. ['bestial', 'total'] or ['messy']."""
    if res.get("outcome") == "win":
        if res.get("is_messy_critical"):
            return ["messy"]
        if res.get("is_critical"):
            return ["critical"]
        return ["win"]
    out = []
    if res.get("is_bestial_failure"):
        out.append("bestial")
    if res.get("is_total_failure"):
        out.append("total")
    return out or ["fail"]


def _v5_dice_text(normal: Sequence[int], hunger: Sequence[int]) -> str:
    """'4 · 1 · 1 · 4 | Hunger: 1' (Hunger dice set apart)."""
    text = _join(normal) if normal else "—"
    return text + (f" | Hunger: {_join(hunger)}" if hunger else "")


def _v5_compare(derived: Dict[str, Any], stored: Dict[str, Any], marker: Optional[Dict[str, Any]],
                marker_res: Optional[Dict[str, Any]]) -> List[Tuple[str, Any, Any]]:
    out = []
    if stored.get("successes") is not None and stored["successes"] != derived["successes"]:
        out.append(("successes", derived["successes"], stored["successes"]))
    if "is_critical" in stored and bool(stored["is_critical"]) != bool(derived["is_critical"]):
        out.append(("is_critical", derived["is_critical"], stored["is_critical"]))
    if marker and marker_res:
        for key in ("successes", "margin"):
            if key in marker and _int_or(marker[key], None) != marker_res[key]:
                out.append((key, marker_res[key], marker[key]))
        if "outcome" in marker and marker["outcome"] != marker_res["outcome"]:
            out.append(("outcome", marker_res["outcome"], marker["outcome"]))
        for key in ("is_critical", "is_messy_critical", "is_bestial_failure", "is_total_failure"):
            if key in marker and bool(marker[key]) != bool(marker_res[key]):
                out.append((key, marker_res[key], marker[key]))
    seen, uniq = set(), []
    for item in out:
        if item[0] not in seen:
            seen.add(item[0])
            uniq.append(item)
    return uniq


def _explain_v5(rec: Dict[str, Any], lang: str, replied: bool = False) -> Dict[str, Any]:
    from services.v5_dice import describe_v5_leniency, resolve_v5

    tr = _t(lang)
    normal, hunger, diff = rec["normal_dice"], rec["hunger_dice"], int(rec["difficulty"])
    res = resolve_v5(normal, hunger, diff)
    first = None
    if rec.get("rerolled") and len(rec.get("original_normal_dice") or []) == len(normal):
        first = resolve_v5(rec["original_normal_dice"], hunger, diff)
    marker = rec.get("marker")
    # The card shows the first roll (roll_kind manual) or the reroll (roll_kind reroll).
    marker_res = first if (first is not None and rec.get("card_kind") != "reroll") else res

    def label_of(r: Dict[str, Any]) -> str:
        return " · ".join(tr["labels"][k] for k in v5_labels(r))

    lines = []
    if first is not None:
        lines.append(tr["first_roll"].format(
            dice=_v5_dice_text(rec["original_normal_dice"], hunger), s=first["successes"], label=label_of(first),
        ))
        changes = ", ".join(
            tr["die_no"].format(i=i + 1, a=rec["original_normal_dice"][i], b=normal[i])
            for i in rec.get("rerolled_indices") or [] if 0 <= i < len(normal)
        )
        wp = tr["wp_reroll"].format(changes=changes or "—")
        if rec.get("willpower_cost") == "superficial":
            wp += tr["wp_cost_sup"]
        elif rec.get("willpower_cost") == "aggravated":
            wp += tr["wp_cost_agg"]
        lines.append(wp)
        if replied and rec.get("card_kind") == "manual":  # only when the user picked that card
            lines.append(tr["card_first"])
        lines.append("")
    lines.append(tr["dice"].format(dice=_v5_dice_text(normal, hunger)))
    lines.append(tr["v5_pool"].format(pool=len(normal) + len(hunger), h=len(hunger), diff=diff))
    if rec.get("hunger_override") is not None and rec.get("sheet_hunger") is not None:
        lines.append(tr["hunger_note"].format(used=rec["hunger_override"], sheet=rec["sheet_hunger"]))
    lines.append("")
    lines.append(tr["counting"])
    succ_list = [str(d) for d in normal if d >= 6] + [f"{d} (Hunger)" for d in hunger if d >= 6]
    lines.append(tr["v5_step1"].format(list=_list_or_none(succ_list, tr), n=len(succ_list)))
    tens = sum(1 for d in normal + hunger if d == 10)
    if tens == 0:
        lines.append(tr["v5_step2_none"])
    elif tens == 1:
        lines.append(tr["v5_step2_one"])
    else:
        lines.append(tr["v5_step2"].format(tens=tens, pairs=res["critical_pairs"], bonus=2 * res["critical_pairs"]))
    fmt = {"s": res["successes"], "diff": diff, "margin": _signed(res["margin"])}
    lines.append(tr["v5_step3"].format(**fmt))
    lines.append("")

    labels = v5_labels(res)
    lines.append(tr["result"].format(label=label_of(res)))
    if res["outcome"] == "win":
        lines.append(tr["mean_win"].format(**fmt))
        if res["is_messy_critical"]:
            lines.append(tr["mean_messy"])
        elif res["is_critical"]:
            lines.append(tr["mean_crit"])
    else:
        lines.append(tr["mean_total"] if res["is_total_failure"] else tr["mean_fail"].format(**fmt))
        if res["is_bestial_failure"]:
            lines.append(tr["mean_bestial"])

    lenient = describe_v5_leniency(rec.get("v5_leniency"))
    if lenient:
        lines.append("")
        lines.append(tr["lenient_v5_reroll" if first is not None else "lenient_v5"].format(desc=lenient))

    mismatches = _v5_compare(res, rec.get("stored") or {}, marker, marker_res)
    facts = {
        "rules_edition": V5,
        "normal_dice": list(normal),
        "hunger_dice": list(hunger),
        "difficulty": diff,
        "successes": res["successes"],
        "critical_pairs": res["critical_pairs"],
        "margin": res["margin"],
        "outcome": res["outcome"],
        "is_critical": res["is_critical"],
        "is_messy_critical": res["is_messy_critical"],
        "is_bestial_failure": res["is_bestial_failure"],
        "is_total_failure": res["is_total_failure"],
        "labels": labels,
        "rerolled": first is not None,
        "first_roll_normal_dice": list(rec.get("original_normal_dice") or []) if first is not None else None,
        "v5_leniency": rec.get("v5_leniency") or None,
    }
    en = T["en"]["labels"]
    summary = (
        f"V5 roll: normal dice [{', '.join(map(str, normal))}], Hunger dice [{', '.join(map(str, hunger))}], "
        f"difficulty {diff}; {res['successes']} success{'' if res['successes'] == 1 else 'es'}, "
        f"margin {res['margin']:+d}"
        + f"; result: {', '.join(en[k] for k in labels)}"
        + (f" (after a Willpower reroll; first roll: {first['successes']} successes)" if first is not None else "")
        + "."
    )
    return {"lines": lines, "facts": facts, "mismatches": mismatches, "summary": summary,
            "rules": tr["rules_v5"]}


# ---------------------------------------------------------------------------------------------
# Classic
# ---------------------------------------------------------------------------------------------


def _explain_classic(rec: Dict[str, Any], lang: str) -> Dict[str, Any]:
    from services.wod_dice import classic_outcome_label, resolve_classic

    tr = _t(lang)
    dice, diff = rec["dice"], int(rec["difficulty"])
    rerolls = rec.get("specialty_rerolls") or []
    roc = bool(rec.get("reroll_ones_cancel"))
    r = resolve_classic(dice, diff, specialty_rerolls=rerolls, willpower=bool(rec.get("willpower")),
                        leniency_floor=rec.get("leniency_floor"), specialty=rec.get("specialty"),
                        reroll_ones_cancel=roc)
    lines = [tr["cl_dice"].format(dice=_join(dice) if dice else "—", diff=diff), "", tr["counting"]]
    lines.append(tr["cl_step1"].format(diff=diff, list=_list_or_none([d for d in dice if d >= diff], tr),
                                       n=r.raw_successes))
    lines.append(tr["cl_step2"].format(ones=r.ones) if r.ones else tr["cl_step2_none"])
    k = 3
    if rec.get("specialty") or rerolls:
        spec = tr["cl_spec"].format(k=k, list=_list_or_none(rerolls, tr), n=r.reroll_successes)
        if r.reroll_ones:
            spec += (tr["cl_spec_ones_cancel"].format(n=r.reroll_ones) if roc else tr["cl_spec_ones_keep"])
        lines.append(spec)
        k += 1
    if r.willpower:
        lines.append(tr["cl_wp"].format(k=k))
    lines.append(tr["cl_net"].format(n=r.net_successes))
    lines.append("")
    if r.botch:
        lines.append(tr["cl_botch"])
    elif r.net_successes == 0 and r.raw_successes + r.reroll_successes > 0:
        lines.append(tr["cl_fail_cancelled"])
    elif r.net_successes == 0:
        lines.append(tr["cl_fail"])
    elif r.phenomenal:
        lines.append(tr["cl_phenomenal"].format(n=r.net_successes))
    elif r.exceptional:
        lines.append(tr["cl_exceptional"])
    elif r.net_successes == 1:
        lines.append(tr["cl_success_one"])
    else:
        lines.append(tr["cl_success"].format(n=r.net_successes))
    if r.willpower and r.raw_successes == 0 and r.ones > 0:
        lines.append(tr["cl_wp_saved"])
    if r.leniency_floor is not None:
        lines.append("")
        lines.append(tr["cl_lenient"].format(f=r.leniency_floor))

    stored = rec.get("stored") or {}
    mismatches = []
    if stored.get("successes") is not None and stored["successes"] != r.net_successes:
        mismatches.append(("successes", r.net_successes, stored["successes"]))
    if "is_botch" in stored and bool(stored["is_botch"]) != r.botch:
        mismatches.append(("is_botch", r.botch, stored["is_botch"]))
    label = classic_outcome_label(r)
    facts = {
        "rules_edition": CLASSIC,
        "dice": list(dice),
        "difficulty": diff,
        "raw_successes": r.raw_successes,
        "ones": r.ones,
        "specialty": bool(rec.get("specialty")),
        "specialty_rerolls": list(rerolls),
        "reroll_successes": r.reroll_successes,
        "reroll_ones": r.reroll_ones,
        "reroll_ones_cancel": roc,
        "willpower": r.willpower,
        "net_successes": r.net_successes,
        "is_botch": r.botch,
        "is_exceptional": r.exceptional,
        "is_phenomenal": r.phenomenal,
        "label": label,
        "leniency_floor": r.leniency_floor,
    }
    summary = (
        f"Classic (Revised) roll: dice [{', '.join(map(str, dice))}] at difficulty {diff}"
        + (f", specialty rerolls [{', '.join(map(str, rerolls))}]" if rerolls else "")
        + (", Willpower +1" if r.willpower else "")
        + f"; {r.raw_successes} raw successes, {r.ones} ones; {r.net_successes} net successes; result: {label}."
    )
    return {"lines": lines, "facts": facts, "mismatches": mismatches, "summary": summary,
            "rules": tr["rules_classic"]}


# ---------------------------------------------------------------------------------------------
# Rouse
# ---------------------------------------------------------------------------------------------


def _explain_rouse(rec: Dict[str, Any], lang: str) -> Dict[str, Any]:
    from services.v5_dice import resolve_rouse

    tr = _t(lang)
    die = rec.get("die")
    before = rec.get("hunger_before") if rec.get("hunger_before") is not None else 0
    res = resolve_rouse(int(die or 0), before)
    lines = [tr["rouse_title"], tr["rouse_rule"], ""]
    if res["success"]:
        lines.append(tr["rouse_ok"].format(die=die, h=res["hunger_after"]))
    elif res["at_max_hunger"]:
        lines.append(tr["rouse_max"].format(die=die))
    else:
        lines.append(tr["rouse_fail"].format(die=die, a=res["hunger_before"], b=res["hunger_after"]))
    stored = rec.get("stored") or {}
    mismatches = []
    if stored.get("successes") is not None and stored["successes"] != (1 if res["success"] else 0):
        mismatches.append(("successes", 1 if res["success"] else 0, stored["successes"]))
    if rec.get("stored_hunger_after") is not None and rec["stored_hunger_after"] != res["hunger_after"]:
        mismatches.append(("hunger_after", res["hunger_after"], rec["stored_hunger_after"]))
    facts = {"rules_edition": V5, "rouse": True, **res}
    summary = (
        f"V5 Rouse check: rolled {die}; {'success, Hunger stays' if res['success'] else 'failure'}; "
        f"Hunger {res['hunger_before']} -> {res['hunger_after']}."
    )
    return {"lines": lines, "facts": facts, "mismatches": mismatches, "summary": summary,
            "rules": tr["rules_rouse"]}


# ---------------------------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------------------------


# "1 successes" / "1 επιτυχίες": the templates use the plural, so fix the singular after a lone 1.
_ONE = r"(?<![\d.,−-])1(\*\*)? "
_SINGULAR = {
    "en": [
        (_ONE + r"net successes", r"1\1 net success"),
        (_ONE + r"successes reach", r"1\1 success reaches"),
        (_ONE + r"successes", r"1\1 success"),
        (_ONE + r"dice\b", r"1\1 die"),
    ],
    "el": [
        (_ONE + r"καθαρές επιτυχίες", r"1\1 καθαρή επιτυχία"),
        (_ONE + r"επιτυχίες φτάνουν", r"1\1 επιτυχία φτάνει"),
        (_ONE + r"επιτυχίες", r"1\1 επιτυχία"),
        (_ONE + r"ζάρια", r"1\1 ζάρι"),
    ],
}


def singular_after_one(text: str, lang: str) -> str:
    """Grammatical singular after the number 1 in an explanation (EN and EL)."""
    for pattern, repl in _SINGULAR.get(lang if lang in _SINGULAR else "en", []):
        text = re.sub(pattern, repl, text)
    return text


def explain(rec: Dict[str, Any], lang: str = "en", note: Optional[str] = None) -> Dict[str, Any]:
    """
    record -> {markdown, summary (English one-liner for prompts), facts, mismatches, lang}.
    note: 'latest' | 'reply_not_roll' | None (how the roll was picked).
    """
    lang = "el" if lang == "el" else "en"
    tr = _t(lang)
    edition = rec.get("edition")
    if edition == ROUSE:
        part = _explain_rouse(rec, lang)
    elif edition == V5:
        part = _explain_v5(rec, lang, replied=note is None)
    else:
        part = _explain_classic(rec, lang)

    head = [part["rules"]]
    if rec.get("roll_id") is not None:
        head.append(tr["roll_no"].format(id=rec["roll_id"]))
    action = plain_text(rec.get("action"), 80)
    if action and action.lower() not in ("dice roll", "rouse check"):
        head.append(action)
    lines = [f"{tr['title']} — {' · '.join(head)}"]
    who = plain_text(rec.get("character_name") or rec.get("username"), 60)
    if who:
        lines.append(tr["by"].format(who=who))
    if note == "latest":
        lines.append(tr["note_latest"])
    elif note == "reply_not_roll":
        lines.append(tr["note_reply_not_roll"])
    lines.append("")
    lines.extend(part["lines"])
    lines.append("")
    if rec.get("source") == "card":
        lines.append(tr["card_only"])
    if part["mismatches"]:
        diffs = "; ".join(
            tr["recount_says"].format(field=tr["field"].get(f, f), a=_yes_no(a, lang), b=_yes_no(b, lang))
            for f, a, b in part["mismatches"]
        )
        lines.append(tr["check_bad"].format(rules=part["rules"], diffs=diffs))
    elif rec.get("source") != "card":
        lines.append(tr["check_ok"].format(rules=part["rules"]))
    markdown = singular_after_one("\n".join(lines).strip(), lang)
    while "\n\n\n" in markdown:
        markdown = markdown.replace("\n\n\n", "\n\n")
    return {
        "markdown": markdown,
        "summary": part["summary"],
        "facts": {**part["facts"], "roll_id": rec.get("roll_id"), "source": rec.get("source")},
        "mismatches": [{"field": f, "recount": a, "stored": b} for f, a, b in part["mismatches"]],
        "lang": lang,
    }


# ---------------------------------------------------------------------------------------------
# Which roll (DB)
# ---------------------------------------------------------------------------------------------

ROLL_LINE_PREFIXES = ("dice_roll:", "dice_roll_hidden:")
MARKER_PREFIXES = ("dice_animation:", "dice_animation_hidden:")
ROUSE_PREFIX = "dice_rouse:"


def is_roll_message_kind(kind: Any) -> bool:
    k = str(kind or "").strip().lower()
    return k.startswith(ROLL_LINE_PREFIXES + MARKER_PREFIXES + (ROUSE_PREFIX,))


def can_see_hidden(site_role: Any, user_id: Any, campaign_created_by: Any) -> bool:
    """Hidden rolls: site admin / helper, or the chronicle's owner (as routes/messages.py)."""
    if str(site_role or "").strip().lower() in ("admin", "helper"):
        return True
    return campaign_created_by is not None and str(campaign_created_by) == str(user_id)


def _fetch_roll_row(cursor, roll_id: Any, campaign_id: int) -> Optional[Dict[str, Any]]:
    rid = _int_or(roll_id, None)
    if rid is None:
        return None
    cursor.execute(
        """
        SELECT dr.*, u.username, c.name AS character_name
        FROM dice_rolls dr
        LEFT JOIN users u ON u.id = dr.user_id
        LEFT JOIN characters c ON c.id = dr.character_id
        WHERE dr.id = %s AND dr.campaign_id = %s
        """,
        (rid, campaign_id),
    )
    return cursor.fetchone()


def record_for_message(cursor, msg: Dict[str, Any], campaign_id: int, location_id: int,
                       game_system: str = "") -> Optional[Dict[str, Any]]:
    """A dice chat row (result line, marker or Rouse line) -> record, or None."""
    kind = str(msg.get("ai_message_kind") or "").strip().lower()
    if kind.startswith(ROUSE_PREFIX):
        row = _fetch_roll_row(cursor, kind.split(":", 1)[1], campaign_id)
        return build_record_from_row(row, None, game_system) if row else None
    prefix, _, anim = kind.partition(":")
    if not anim:
        return None
    marker = None
    if kind.startswith(MARKER_PREFIXES):
        marker = _json(msg.get("content"), None)
    else:
        marker_kind = ("dice_animation_hidden:" if prefix == "dice_roll_hidden" else "dice_animation:") + anim
        cursor.execute(
            """
            SELECT content FROM messages
            WHERE campaign_id = %s AND location_id = %s AND LOWER(ai_message_kind) = %s
            ORDER BY id ASC LIMIT 1
            """,
            (campaign_id, location_id, marker_kind),
        )
        mrow = cursor.fetchone()
        marker = _json((mrow or {}).get("content"), None)
    if not isinstance(marker, dict):
        return None
    row = _fetch_roll_row(cursor, marker.get("roll_id"), campaign_id) if marker.get("roll_id") is not None else None
    if row:
        rec = build_record_from_row(row, marker, game_system)
        if rec is not None:
            rec["hidden"] = bool(rec.get("hidden")) or is_hidden_kind(kind)
        return rec
    rec = build_record_from_marker(marker, game_system)
    if rec is not None:
        rec["hidden"] = is_hidden_kind(kind)
    return rec


def find_roll(cursor, campaign_id: int, location_id: int, reply_to_id: Optional[int],
              sees_hidden: bool, game_system: str = "") -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    (record, note) of the roll to explain:
    - the replied-to message when it is a dice row in this room the requester can see (note None);
    - else the newest roll line in this room the requester can see
      (note 'reply_not_roll' when a reply was given, 'latest' otherwise);
    - (None, 'nothing') when the room has no roll, (None, 'no_record') when the dice row
      can't be read back.
    A hidden roll the requester can't see is treated like any non-roll message: never named.
    The newest-roll fallback prefers visible rolls even for staff. record['hidden'] is True for
    a hidden roll: its explanation must never be posted to the room (ai_slash_commands).
    """
    note = "latest"
    if reply_to_id is not None:
        cursor.execute(
            """
            SELECT id, campaign_id, location_id, ai_message_kind, content FROM messages
            WHERE id = %s
            """,
            (int(reply_to_id),),
        )
        msg = cursor.fetchone()
        ok = (
            msg is not None
            and str(msg.get("campaign_id")) == str(campaign_id)
            and str(msg.get("location_id")) == str(location_id)
            and is_roll_message_kind(msg.get("ai_message_kind"))
            and (sees_hidden or not is_hidden_kind(msg.get("ai_message_kind")))
        )
        if ok:
            rec = record_for_message(cursor, msg, campaign_id, location_id, game_system)
            return (rec, None) if rec is not None else (None, "no_record")
        note = "reply_not_roll"
    sql = """
        SELECT id, campaign_id, location_id, ai_message_kind, content FROM messages m
        WHERE m.campaign_id = %s AND m.location_id = %s
          AND (LOWER(COALESCE(m.ai_message_kind, '')) LIKE 'dice_roll%%'
               OR LOWER(COALESCE(m.ai_message_kind, '')) LIKE 'dice_rouse:%%')
    """
    # Visible rolls first, for staff too: a hidden roll is only picked by replying to its card,
    # or (staff) when the room has no visible roll at all.
    cursor.execute(sql + hidden_dice_sql_filter("m.ai_message_kind") + " ORDER BY m.id DESC LIMIT 1",
                   (campaign_id, location_id))
    msg = cursor.fetchone()
    if not msg and sees_hidden:
        cursor.execute(sql + " ORDER BY m.id DESC LIMIT 1", (campaign_id, location_id))
        msg = cursor.fetchone()
    if not msg:
        return None, "nothing"
    rec = record_for_message(cursor, msg, campaign_id, location_id, game_system)
    return (rec, note) if rec is not None else (None, "no_record")


def message_text(key: str, lang: str) -> str:
    """'nothing' / 'no_record' notices."""
    return _t(lang)[key]


def storyteller_line_markdown(text: str, lang: str) -> str:
    return _t(lang)["storyteller"].format(text=text.strip())
