"""The two questions ShadowRealms asks Laya, and the state it gives.

Kept in one place so training (prep_items.py), evaluation and the app
(infer.py) ask exactly the same thing. The state is plain text.
"""

# (a) Is the message written in character? Asked of messages posted in an
# Out-Of-Character room: P(true) high = an OOC-rule violation.
OOC_QUESTION = {
    "t": "noul",
    "ins": "This message was posted in the chat of a World of Darkness tabletop RPG "
           "(e.g. Vampire: The Masquerade). Is it written in character: the player "
           "speaking or acting as their character inside the story?",
    "crit": {
        "false": "out of character: the player talking as themselves about rules, dice, "
                 "combat mechanics, scheduling, plans for their character, jokes or real life",
        "true": "in character: the character's own speech, actions or narration inside the fiction",
    },
}

# (b) What is the message about? Used to route it to the right handler/model.
INTENTS = ["dice", "combat", "rules_question", "roleplay", "general"]
INTENT_QUESTION = {
    "t": "choice",
    "ins": "What is this message in a tabletop RPG chat about?",
    "crit": {
        "dice": "a dice roll or check: asks to roll, gives a dice pool or difficulty, reports a roll result",
        "combat": "fighting: attacks, initiative, damage, soak, health levels, fleeing a fight",
        "rules_question": "a question about the game's rules, mechanics, powers, lore or character stats",
        "roleplay": "the story: a character speaks or acts in a scene, or the player asks for or plans a scene",
        "general": "anything else: greetings, banter, scheduling, out-of-game talk",
    },
}
assert list(INTENT_QUESTION["crit"]) == INTENTS


def state_of(text: str) -> str:
    """The state Laya reads: the message alone (no room name, so the model
    can't shortcut on it)."""
    return "Chat message: " + text.strip()
