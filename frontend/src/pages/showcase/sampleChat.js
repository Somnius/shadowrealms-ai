/**
 * A scripted scene for the chat preview: plain message rows shaped like the API's
 * (GET /campaigns/<c>/locations/<l>), rendered by the real chat components. No network.
 */
import { buildDiceMarker } from '../../dice/diceMarker';
import { t } from '../../i18n';
import { rollV5, seededRandom } from './diceDemo';

const MIN = 60 * 1000;

const PEOPLE = {
  mara: { user_id: 11, username: 'lef', character_id: 101, character_name: 'Mara Voss', speaker_mode: 'character' },
  jonah: { user_id: 12, username: 'dimitra', character_id: 102, character_name: 'Jonah Crane', speaker_mode: 'character' },
  lefOoc: { user_id: 11, username: 'lef', speaker_mode: 'player' },
  nyx: { user_id: 13, username: 'Nyx', speaker_mode: 'staff', staff_kind: 'storyteller' },
};

const iso = (ms) => new Date(ms).toISOString();

function row(id, ms, who, content, extra = {}) {
  return { id, created_at: iso(ms), role: 'user', message_type: 'chat', content, ...(who ? PEOPLE[who] : {}), ...extra };
}

const ai = (id, ms, content) => ({ id, created_at: iso(ms), role: 'assistant', message_type: 'chat', content });
const system = (id, ms, content) => ({ id, created_at: iso(ms), role: 'user', message_type: 'system', username: 'system', content });

/**
 * A V5 roll as the two rows the server posts: the animation marker and the final line. The line is
 * the server's English text ("… rolls (V5) for **reason**"); the card itself is built from the marker.
 */
function diceRows(id, ms, who, outcome, seed, reason) {
  const roll = rollV5({ pool: 6, hunger: 2, difficulty: 3, outcome }, seededRandom(seed));
  const animationId = `showcase${id}`;
  const marker = buildDiceMarker(roll.result, { animationId, startedAtMs: ms, durationMs: 1 });
  return [
    {
      id: id - 0.5,
      created_at: iso(ms),
      role: 'user',
      message_type: 'action',
      ai_message_kind: `dice_animation:${animationId}`,
      content: JSON.stringify(marker),
      ...PEOPLE[who],
    },
    row(id, ms, who, `**${PEOPLE[who].character_name}** rolls (V5) for **${reason}**`, {
      message_type: 'action',
      ai_message_kind: `dice_roll:${animationId}`,
    }),
  ];
}

/** The opening of the scene (already in the room when the preview loads). */
export function openingScene(now = Date.now()) {
  const at = (minAgo) => now - minAgo * MIN;
  return [
    system(1, at(42), t('showcase:chat.sys.enter', '**Mara Voss** entered Elysium.')),
    row(2, at(40), 'mara', t('showcase:chat.mara1', "The Prince's herald is watching the door. I keep my smile thin and my hands where he can see them.")),
    row(3, at(39), 'mara', t('showcase:chat.mara2', '“Good evening. I was told the gallery stays open late for friends of the Court.”')),
    row(4, at(37), 'lefOoc', t('showcase:chat.ooc', 'can I roll Insight to read him? he seems nervous')),
    row(5, at(36), 'nyx', t('showcase:chat.st1', 'Sure. **Wits + Insight**, Difficulty 3.')),
    ...diceRows(6, at(35), 'mara', 'messy', 7, 'Wits + Insight'),
    ai(
      7,
      at(34),
      t(
        'showcase:chat.ai1',
        "You read him at once: the herald is afraid, and not of you. His eyes keep drifting to the east stair, where the candles have burned down to stubs and no one has come to replace them. But the Beast reads him too. It smells the sweat under his collar, hears the quick bird-heartbeat in his throat, and for one long moment you are not sure which of you is smiling. He takes a step back. Somewhere above, a door closes very softly."
      )
    ),
    row(8, at(33), 'mara', t('showcase:chat.action1', '*steps back into the shadow of the colonnade and lets the herald breathe*'), { message_type: 'action' }),
  ];
}

/** "Continue the scene": one step per click. */
export function sceneScript() {
  return [
    (now) => [row(20, now, 'jonah', t('showcase:chat.jonah1', 'While he’s rattled, I slip past him toward the east stair.'))],
    (now) => diceRows(21, now, 'jonah', 'bestial', 3, 'Dexterity + Stealth'),
    (now) => [
      ai(
        22,
        now,
        t(
          'showcase:chat.ai2',
          'Your foot finds the one step that creaks. The herald turns, and the Hunger answers before you can think: your lips pull back from your teeth. Two Kindred in the gallery have seen it.'
        )
      ),
    ],
    (now) => [system(23, now, t('showcase:chat.sys.end', 'The Storyteller ended the scene.'))],
  ];
}
