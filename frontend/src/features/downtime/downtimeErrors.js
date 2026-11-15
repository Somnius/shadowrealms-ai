import { errorText } from '../../app/http';
import { t } from '../../i18n';

/** Every refusal code of backend/routes/downtime.py → translated text. */
const CODES = {
  invalid_input: () => t('downtime:err.invalid_input', 'Something in the form is not valid.'),
  roll_refused: () => t('downtime:err.roll_refused', 'The roll was refused.'),
  conflict: () => t('downtime:err.conflict', 'That was changed at the same time; reload and try again.'),
  server_error: () => t('downtime:err.server_error', 'Downtime request failed. Try again.'),
  campaign_not_found: () => t('downtime:err.campaign_not_found', 'Chronicle not found.'),
  storyteller_only: () => t('downtime:err.storyteller_only', 'Only the Storyteller can do this.'),
  not_a_member: () => t('downtime:err.not_a_member', 'You are not a player in this chronicle.'),
  no_playing_character: () => t('downtime:err.no_playing_character', 'Pick your playing character in this chronicle first.'),
  character_suspended: () => t('downtime:err.character_suspended', "Your character's play is suspended."),
  character_fallen: () => t('downtime:err.character_fallen', 'Your character has fallen.'),
  round_not_found: () => t('downtime:err.round_not_found', 'Downtime round not found.'),
  round_already_live: () => t('downtime:err.round_already_live', 'Release the current round before opening a new one.'),
  round_wrong_status: () => t('downtime:err.round_wrong_status', 'The round has moved on since you loaded it; reloaded.'),
  invalid_parent: () => t('downtime:err.invalid_parent', 'The parent goal must be one of your own projects.'),
  too_many_projects: () => t('downtime:err.too_many_projects', 'You have too many active projects.'),
  project_not_found: () => t('downtime:err.project_not_found', 'Project not found.'),
  no_open_round: () => t('downtime:err.no_open_round', 'There is no open downtime round.'),
  round_locked: () => t('downtime:err.round_locked', 'The Storyteller is resolving this round.'),
  project_closed: () => t('downtime:err.project_closed', 'This project is closed.'),
  phase_exists: () => t('downtime:err.phase_exists', 'This project already has a phase in this round.'),
  pool_required: () => t('downtime:err.pool_required', 'Enter a dice pool of at least 1.'),
  pool_too_big: () => t('downtime:err.pool_too_big', 'The dice pool can be at most 50.'),
  phase_not_found: () => t('downtime:err.phase_not_found', 'Phase not found.'),
  already_rolled: () => t('downtime:err.already_rolled', 'This phase has already been rolled.'),
  phase_resolved: () => t('downtime:err.phase_resolved', 'The Storyteller has already resolved this phase.'),
  difficulty_not_set: () => t('downtime:err.difficulty_not_set', 'Wait for the Storyteller to set the difficulty.'),
  version_required: () => t('downtime:err.version_required', 'Reload and try again.'),
  version_conflict: () => t('downtime:err.version_conflict', 'Someone changed this while you were editing. It has been reloaded; check it and try again.'),
  invalid_difficulty: () => t('downtime:err.invalid_difficulty', 'That difficulty is out of range for this chronicle.'),
  difficulty_required: () => t('downtime:err.difficulty_required', 'Set a difficulty to hide it.'),
  round_released: () => t('downtime:err.round_released', 'This round has been released; its results are final.'),
  invalid_deltas: () => t('downtime:err.invalid_deltas', 'Each change needs a target and a number between -1000 and 1000.'),
  too_many_deltas: () => t('downtime:err.too_many_deltas', 'Too many changes for one phase.'),
  value_out_of_range: () => t('downtime:err.value_out_of_range', 'That value is out of range.'),
  round_not_resolving: () => t('downtime:err.round_not_resolving', 'Close the round to players first.'),
  invalid_result_kind: () => t('downtime:err.invalid_result_kind', 'Pick what kind of result this is.'),
  invalid_location: () => t('downtime:err.invalid_location', 'That room is not in this chronicle.'),
  invalid_target: () => t('downtime:err.invalid_target', "A change points at an indicator or variable that isn't part of this project or chronicle."),
  unresolved_phases: () => t('downtime:err.unresolved_phases', 'Some phases have no result yet.'),
  invalid_status: () => t('downtime:err.invalid_status', 'That project status is not valid.'),
  name_taken: () => t('downtime:err.name_taken', 'That name is already used.'),
  indicator_not_found: () => t('downtime:err.indicator_not_found', 'Indicator not found.'),
  variable_not_found: () => t('downtime:err.variable_not_found', 'Variable not found.'),
};

export const DOWNTIME_ERROR_CODES = Object.keys(CODES);

export function downtimeErrorText(data, fallback) {
  const code = data && data.code;
  if (code && CODES[code]) return CODES[code]();
  return errorText(data, fallback || t('downtime:err.generic', 'Something went wrong.'));
}

export function isVersionConflict(r) {
  return Boolean(r && !r.ok && r.data && (r.data.code === 'version_conflict' || r.data.code === 'conflict'));
}
