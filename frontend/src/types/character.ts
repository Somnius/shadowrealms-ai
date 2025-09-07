/**
 * ShadowRealms AI - Character Type Definitions
 * 
 * This file defines all TypeScript interfaces and types related to character management.
 * It ensures type safety across the character system and RPG mechanics.
 * 
 * WHAT THIS FILE CONTAINS:
 * 1. Core character data structures
 * 2. Character statistics and abilities
 * 3. Character creation and management types
 * 4. RPG system-specific character data
 * 5. Character actions and interactions
 */

/**
 * Character Class Enum
 * Defines the available character classes for different RPG systems
 */
export enum CharacterClass {
  // D&D 5e Classes
  FIGHTER = 'fighter',
  WIZARD = 'wizard',
  ROGUE = 'rogue',
  CLERIC = 'cleric',
  RANGER = 'ranger',
  PALADIN = 'paladin',
  BARBARIAN = 'barbarian',
  BARD = 'bard',
  DRUID = 'druid',
  MONK = 'monk',
  SORCERER = 'sorcerer',
  WARLOCK = 'warlock',
  ARTIFICER = 'artificer',
  
  // World of Darkness - Vampire: The Masquerade
  VAMPIRE_BRUJAH = 'vampire_brujah',
  VAMPIRE_GANGREL = 'vampire_gangrel',
  VAMPIRE_MALKAVIAN = 'vampire_malkavian',
  VAMPIRE_NOSFERATU = 'vampire_nosferatu',
  VAMPIRE_TOREADOR = 'vampire_toreador',
  VAMPIRE_TREMERE = 'vampire_tremere',
  VAMPIRE_VENTRUE = 'vampire_ventrue',
  VAMPIRE_ASSAMITE = 'vampire_assamite',
  VAMPIRE_FOLLOWERS_OF_SET = 'vampire_followers_of_set',
  VAMPIRE_GIOVANNI = 'vampire_giovanni',
  VAMPIRE_LASOMBRA = 'vampire_lasombra',
  VAMPIRE_RAVNOS = 'vampire_ravnos',
  VAMPIRE_TZIMISCE = 'vampire_tzimisce',
  VAMPIRE_CAITIFF = 'vampire_caitiff',
  
  // World of Darkness - Mage: The Ascension
  MAGE_AKASHIC = 'mage_akashic',
  MAGE_CELESTIAL_CHORUS = 'mage_celestial_chorus',
  MAGE_CULT_OF_ECSTASY = 'mage_cult_of_ecstasy',
  MAGE_DREAMSPEAKERS = 'mage_dreamspeakers',
  MAGE_ECSTATICS = 'mage_ecstatics',
  MAGE_ITERATION_X = 'mage_iteration_x',
  MAGE_NEPHANDI = 'mage_nephandi',
  MAGE_NEW_WORLD_ORDER = 'mage_new_world_order',
  MAGE_ORDER_OF_HERMES = 'mage_order_of_hermes',
  MAGE_PROGENITORS = 'mage_progenitors',
  MAGE_SONS_OF_ETHER = 'mage_sons_of_ether',
  MAGE_VERBENA = 'mage_verbena',
  MAGE_VIRTUAL_ADEPTS = 'mage_virtual_adepts',
  MAGE_ORPHANS = 'mage_orphans',
  
  // World of Darkness - Werewolf: The Apocalypse
  WEREWOLF_AHROUN = 'werewolf_ahroun',
  WEREWOLF_GALLIARD = 'werewolf_galliard',
  WEREWOLF_PHILODOX = 'werewolf_philodox',
  WEREWOLF_RAGABASH = 'werewolf_ragabash',
  WEREWOLF_THEURGE = 'werewolf_theurge',
  
  // World of Darkness - Changeling: The Dreaming
  CHANGELING_BOGGAN = 'changeling_boggan',
  CHANGELING_ESHU = 'changeling_eshu',
  CHANGELING_NOCKER = 'changeling_nocker',
  CHANGELING_POOKA = 'changeling_pooka',
  CHANGELING_REDCAP = 'changeling_redcap',
  CHANGELING_SATYR = 'changeling_satyr',
  CHANGELING_SIDHE = 'changeling_sidhe',
  CHANGELING_SLUICHE = 'changeling_sluiche',
  CHANGELING_TROLL = 'changeling_troll',
  
  // World of Darkness - Kindred of the East
  KUEI_JIN_AKUMA = 'kuei_jin_akuma',
  KUEI_JIN_BODHISATTVA = 'kuei_jin_bodhisattva',
  KUEI_JIN_DHAMPYR = 'kuei_jin_dhampyr',
  KUEI_JIN_HUN = 'kuei_jin_hun',
  KUEI_JIN_PO = 'kuei_jin_po',
  KUEI_JIN_WAN_KUEI = 'kuei_jin_wan_kuei',
  
  // World of Darkness - Wraith: The Oblivion
  WRAITH_ARTISAN = 'wraith_artisan',
  WRAITH_CASTIGATOR = 'wraith_castigator',
  WRAITH_CHILD = 'wraith_child',
  WRAITH_FIDDLER = 'wraith_fiddler',
  WRAITH_GATEKEEPER = 'wraith_gatekeeper',
  WRAITH_HARBINGER = 'wraith_harbinger',
  WRAITH_MONITOR = 'wraith_monitor',
  WRAITH_PILGRIM = 'wraith_pilgrim',
  WRAITH_PROSPECTOR = 'wraith_prospector',
  WRAITH_SANDMAN = 'wraith_sandman',
  WRAITH_SCOUT = 'wraith_scout',
  WRAITH_SHADE = 'wraith_shade',
  WRAITH_SOLDIER = 'wraith_soldier',
  WRAITH_SPOOK = 'wraith_spook',
  
  // World of Darkness - Hunter: The Reckoning
  HUNTER_AVENGER = 'hunter_avenger',
  HUNTER_DEFENDER = 'hunter_defender',
  HUNTER_HERMIT = 'hunter_hermit',
  HUNTER_INNOCENT = 'hunter_innocent',
  HUNTER_JUDGE = 'hunter_judge',
  HUNTER_MARTYR = 'hunter_martyr',
  HUNTER_REDEEMER = 'hunter_redeemer',
  HUNTER_VISIONARY = 'hunter_visionary',
  HUNTER_ZEALOT = 'hunter_zealot',
  
  // World of Darkness - Demon: The Fallen
  DEMON_DEFILER = 'demon_defiler',
  DEMON_DEVOURER = 'demon_devourer',
  DEMON_FIEND = 'demon_fiend',
  DEMON_MALEFACTOR = 'demon_malefactor',
  DEMON_NEPHILIM = 'demon_nephilim',
  DEMON_SCRIVENER = 'demon_scrivener',
  DEMON_SLAYER = 'demon_slayer',
  DEMON_TEMPTER = 'demon_tempter',
  
  // Custom/Other
  CUSTOM = 'custom'
}

/**
 * Character Race Enum
 * Defines the available character races for different RPG systems
 */
export enum CharacterRace {
  // D&D 5e Races
  HUMAN = 'human',
  ELF = 'elf',
  DWARF = 'dwarf',
  HALFLING = 'halfling',
  GNOME = 'gnome',
  DRAGONBORN = 'dragonborn',
  TIEFLING = 'tiefling',
  HALF_ORC = 'half_orc',
  HALF_ELF = 'half_elf',
  AASIMAR = 'aasimar',
  GENASI = 'genasi',
  GOLIATH = 'goliath',
  
  // World of Darkness - Vampire: The Masquerade
  VAMPIRE_KINDRED = 'vampire_kindred',
  VAMPIRE_CAITIFF = 'vampire_caitiff',
  VAMPIRE_THIN_BLOOD = 'vampire_thin_blood',
  
  // World of Darkness - Mage: The Ascension
  MAGE_AWAKENED = 'mage_awakened',
  MAGE_SLEEPER = 'mage_sleeper',
  MAGE_ORPHAN = 'mage_orphan',
  
  // World of Darkness - Werewolf: The Apocalypse
  WEREWOLF_GAROU = 'werewolf_garou',
  WEREWOLF_METIS = 'werewolf_metis',
  WEREWOLF_LUPUS = 'werewolf_lupus',
  WEREWOLF_HOMID = 'werewolf_homid',
  
  // World of Darkness - Changeling: The Dreaming
  CHANGELING_FAE = 'changeling_fae',
  CHANGELING_CHIMERICAL = 'changeling_chimerical',
  CHANGELING_BANAL = 'changeling_banal',
  
  // World of Darkness - Kindred of the East
  KUEI_JIN = 'kuei_jin',
  KUEI_JIN_WAN_KUEI = 'kuei_jin_wan_kuei',
  KUEI_JIN_DHAMPYR = 'kuei_jin_dhampyr',
  
  // World of Darkness - Wraith: The Oblivion
  WRAITH_SHADOWLANDS = 'wraith_shadowlands',
  WRAITH_OBLIVION = 'wraith_oblivion',
  WRAITH_SPECTRE = 'wraith_spectre',
  
  // World of Darkness - Hunter: The Reckoning
  HUNTER_IMBUED = 'hunter_imbued',
  HUNTER_MUNDANE = 'hunter_mundane',
  
  // World of Darkness - Demon: The Fallen
  DEMON_FALLEN = 'demon_fallen',
  DEMON_FAITHFUL = 'demon_faithful',
  
  // World of Darkness - Mummy: The Resurrection
  MUMMY_AUSPEX = 'mummy_auspex',
  MUMMY_AKHU = 'mummy_akhu',
  
  // World of Darkness - Orpheus
  ORPHEUS_GHOST = 'orpheus_ghost',
  ORPHEUS_SKINRIDER = 'orpheus_skinrider',
  ORPHEUS_SPECTRE = 'orpheus_spectre',
  
  // Custom/Other
  CUSTOM = 'custom'
}

/**
 * Character Background Enum
 * Defines the available character backgrounds for different RPG systems
 */
export enum CharacterBackground {
  // D&D 5e Backgrounds
  ACOLYTE = 'acolyte',
  CRIMINAL = 'criminal',
  FOLK_HERO = 'folk_hero',
  NOBLE = 'noble',
  SAGE = 'sage',
  SOLDIER = 'soldier',
  CHARLATAN = 'charlatan',
  ENTERTAINER = 'entertainer',
  GUILD_ARTISAN = 'guild_artisan',
  HERMIT = 'hermit',
  OUTLANDER = 'outlander',
  SAILOR = 'sailor',
  
  // World of Darkness - Vampire: The Masquerade
  VAMPIRE_ANARCH = 'vampire_anarch',
  VAMPIRE_CAMARILLA = 'vampire_camarilla',
  VAMPIRE_SABBAT = 'vampire_sabbat',
  VAMPIRE_INDEPENDENT = 'vampire_independent',
  
  // World of Darkness - Mage: The Ascension
  MAGE_TRADITION = 'mage_tradition',
  MAGE_TECHNOCRACY = 'mage_technocracy',
  MAGE_NEPHANDI = 'mage_nephandi',
  MAGE_ORPHAN = 'mage_orphan',
  
  // World of Darkness - Werewolf: The Apocalypse
  WEREWOLF_TRIBE = 'werewolf_tribe',
  WEREWOLF_PACK = 'werewolf_pack',
  WEREWOLF_LONE_WOLF = 'werewolf_lone_wolf',
  
  // World of Darkness - Changeling: The Dreaming
  CHANGELING_COURT = 'changeling_court',
  CHANGELING_HOUSE = 'changeling_house',
  CHANGELING_WILDER = 'changeling_wilder',
  
  // World of Darkness - Kindred of the East
  KUEI_JIN_WAN_KUEI = 'kuei_jin_wan_kuei',
  KUEI_JIN_DHAMPYR = 'kuei_jin_dhampyr',
  KUEI_JIN_AKUMA = 'kuei_jin_akuma',
  
  // World of Darkness - Wraith: The Oblivion
  WRAITH_LEGION = 'wraith_legion',
  WRAITH_GUILD = 'wraith_guild',
  WRAITH_RENEGADE = 'wraith_renegade',
  
  // World of Darkness - Hunter: The Reckoning
  HUNTER_CREED = 'hunter_creed',
  HUNTER_IMBUED = 'hunter_imbued',
  HUNTER_MUNDANE = 'hunter_mundane',
  
  // World of Darkness - Demon: The Fallen
  DEMON_HOUSE = 'demon_house',
  DEMON_FALLEN = 'demon_fallen',
  DEMON_FAITHFUL = 'demon_faithful',
  
  // Custom/Other
  CUSTOM = 'custom'
}

/**
 * Character Alignment/Morality Enum
 * Defines the available character alignments and morality systems
 */
export enum CharacterAlignment {
  // D&D 5e Alignments
  LAWFUL_GOOD = 'lawful_good',
  NEUTRAL_GOOD = 'neutral_good',
  CHAOTIC_GOOD = 'chaotic_good',
  LAWFUL_NEUTRAL = 'lawful_neutral',
  TRUE_NEUTRAL = 'true_neutral',
  CHAOTIC_NEUTRAL = 'chaotic_neutral',
  LAWFUL_EVIL = 'lawful_evil',
  NEUTRAL_EVIL = 'neutral_evil',
  CHAOTIC_EVIL = 'chaotic_evil',
  
  // World of Darkness - Humanity (Vampire)
  HUMANITY_10 = 'humanity_10',
  HUMANITY_9 = 'humanity_9',
  HUMANITY_8 = 'humanity_8',
  HUMANITY_7 = 'humanity_7',
  HUMANITY_6 = 'humanity_6',
  HUMANITY_5 = 'humanity_5',
  HUMANITY_4 = 'humanity_4',
  HUMANITY_3 = 'humanity_3',
  HUMANITY_2 = 'humanity_2',
  HUMANITY_1 = 'humanity_1',
  HUMANITY_0 = 'humanity_0',
  
  // World of Darkness - Paths of Enlightenment (Vampire)
  PATH_OF_BLOOD = 'path_of_blood',
  PATH_OF_BONES = 'path_of_bones',
  PATH_OF_CATHARSIS = 'path_of_catharsis',
  PATH_OF_DEATH_AND_THE_SOUL = 'path_of_death_and_the_soul',
  PATH_OF_ENTHECY = 'path_of_enthecy',
  PATH_OF_HARMONY = 'path_of_harmony',
  PATH_OF_HONEST_ACCOUNTING = 'path_of_honest_accounting',
  PATH_OF_HUMANITY = 'path_of_humanity',
  PATH_OF_LILITH = 'path_of_lilith',
  PATH_OF_METAMORPHOSIS = 'path_of_metamorphosis',
  PATH_OF_NIGHT = 'path_of_night',
  PATH_OF_PARADOX = 'path_of_paradox',
  PATH_OF_POWER_AND_THE_INNER_VOICE = 'path_of_power_and_the_inner_voice',
  PATH_OF_THE_BEAST = 'path_of_the_beast',
  PATH_OF_THE_FANG = 'path_of_the_fang',
  PATH_OF_THE_HUNTER = 'path_of_the_hunter',
  PATH_OF_THE_SCORPION = 'path_of_the_scorpion',
  PATH_OF_TYPHON = 'path_of_typhon',
  
  // World of Darkness - Wisdom (Werewolf)
  WISDOM_10 = 'wisdom_10',
  WISDOM_9 = 'wisdom_9',
  WISDOM_8 = 'wisdom_8',
  WISDOM_7 = 'wisdom_7',
  WISDOM_6 = 'wisdom_6',
  WISDOM_5 = 'wisdom_5',
  WISDOM_4 = 'wisdom_4',
  WISDOM_3 = 'wisdom_3',
  WISDOM_2 = 'wisdom_2',
  WISDOM_1 = 'wisdom_1',
  WISDOM_0 = 'wisdom_0',
  
  // World of Darkness - Paradox (Mage)
  PARADOX_10 = 'paradox_10',
  PARADOX_9 = 'paradox_9',
  PARADOX_8 = 'paradox_8',
  PARADOX_7 = 'paradox_7',
  PARADOX_6 = 'paradox_6',
  PARADOX_5 = 'paradox_5',
  PARADOX_4 = 'paradox_4',
  PARADOX_3 = 'paradox_3',
  PARADOX_2 = 'paradox_2',
  PARADOX_1 = 'paradox_1',
  PARADOX_0 = 'paradox_0',
  
  // World of Darkness - Banality (Changeling)
  BANALITY_10 = 'banality_10',
  BANALITY_9 = 'banality_9',
  BANALITY_8 = 'banality_8',
  BANALITY_7 = 'banality_7',
  BANALITY_6 = 'banality_6',
  BANALITY_5 = 'banality_5',
  BANALITY_4 = 'banality_4',
  BANALITY_3 = 'banality_3',
  BANALITY_2 = 'banality_2',
  BANALITY_1 = 'banality_1',
  BANALITY_0 = 'banality_0',
  
  // World of Darkness - Angst (Wraith)
  ANGST_10 = 'angst_10',
  ANGST_9 = 'angst_9',
  ANGST_8 = 'angst_8',
  ANGST_7 = 'angst_7',
  ANGST_6 = 'angst_6',
  ANGST_5 = 'angst_5',
  ANGST_4 = 'angst_4',
  ANGST_3 = 'angst_3',
  ANGST_2 = 'angst_2',
  ANGST_1 = 'angst_1',
  ANGST_0 = 'angst_0',
  
  // World of Darkness - Conviction (Hunter)
  CONVICTION_10 = 'conviction_10',
  CONVICTION_9 = 'conviction_9',
  CONVICTION_8 = 'conviction_8',
  CONVICTION_7 = 'conviction_7',
  CONVICTION_6 = 'conviction_6',
  CONVICTION_5 = 'conviction_5',
  CONVICTION_4 = 'conviction_4',
  CONVICTION_3 = 'conviction_3',
  CONVICTION_2 = 'conviction_2',
  CONVICTION_1 = 'conviction_1',
  CONVICTION_0 = 'conviction_0',
  
  // World of Darkness - Faith (Demon)
  FAITH_10 = 'faith_10',
  FAITH_9 = 'faith_9',
  FAITH_8 = 'faith_8',
  FAITH_7 = 'faith_7',
  FAITH_6 = 'faith_6',
  FAITH_5 = 'faith_5',
  FAITH_4 = 'faith_4',
  FAITH_3 = 'faith_3',
  FAITH_2 = 'faith_2',
  FAITH_1 = 'faith_1',
  FAITH_0 = 'faith_0'
}

/**
 * Character Status Enum
 * Defines the possible character statuses
 */
export enum CharacterStatus {
  ACTIVE = 'active',           // Character is active and playable
  INACTIVE = 'inactive',       // Character is inactive
  RETIRED = 'retired',         // Character has been retired
  DEAD = 'dead',              // Character has died
  TEMPORARY = 'temporary'      // Temporary character for one-shot
}

/**
 * Character Ability Interface
 * Represents a character's ability score
 */
export interface CharacterAbility {
  name: string;                // Ability name (Strength, Dexterity, etc.)
  score: number;               // Raw ability score
  modifier: number;            // Calculated modifier
  isProficient: boolean;       // Whether character is proficient in saves
}

/**
 * Character Skill Interface
 * Represents a character's skill
 */
export interface CharacterSkill {
  name: string;                // Skill name
  ability: string;             // Associated ability
  isProficient: boolean;       // Whether character is proficient
  isExpertise: boolean;        // Whether character has expertise
  bonus: number;               // Total skill bonus
}

/**
 * Character Stats Interface
 * Represents a character's core statistics
 */
export interface CharacterStats {
  level: number;               // Character level
  experiencePoints: number;    // Current XP
  hitPoints: number;           // Current hit points
  maxHitPoints: number;        // Maximum hit points
  temporaryHitPoints: number;  // Temporary hit points
  armorClass: number;          // Armor class
  speed: number;               // Movement speed
  initiative: number;          // Initiative bonus
  proficiencyBonus: number;    // Proficiency bonus
  passivePerception: number;   // Passive perception
  passiveInvestigation: number; // Passive investigation
  passiveInsight: number;      // Passive insight
}

/**
 * Character Saving Throws Interface
 * Represents a character's saving throw bonuses
 */
export interface CharacterSavingThrows {
  strength: number;
  dexterity: number;
  constitution: number;
  intelligence: number;
  wisdom: number;
  charisma: number;
}

/**
 * Character Attack Interface
 * Represents a character's attack or spell
 */
export interface CharacterAttack {
  name: string;                // Attack name
  type: 'melee' | 'ranged' | 'spell'; // Attack type
  range: string;               // Attack range
  toHit: number;               // Attack bonus
  damage: string;              // Damage dice and bonus
  damageType: string;          // Damage type
  description: string;         // Attack description
  isProficient: boolean;       // Whether character is proficient
}

/**
 * Character Spell Interface
 * Represents a character's spell
 */
export interface CharacterSpell {
  name: string;                // Spell name
  level: number;               // Spell level
  school: string;              // Spell school
  castingTime: string;         // Casting time
  range: string;               // Spell range
  components: string;          // Spell components
  duration: string;            // Spell duration
  description: string;         // Spell description
  isPrepared: boolean;         // Whether spell is prepared
  isKnown: boolean;            // Whether spell is known
}

/**
 * Character Equipment Interface
 * Represents a character's equipment
 */
export interface CharacterEquipment {
  name: string;                // Equipment name
  type: 'weapon' | 'armor' | 'tool' | 'consumable' | 'misc'; // Equipment type
  quantity: number;            // Quantity owned
  weight: number;              // Weight in pounds
  value: number;               // Value in gold pieces
  description: string;         // Equipment description
  isEquipped: boolean;         // Whether currently equipped
  properties: string[];        // Equipment properties
}

/**
 * Character Feature Interface
 * Represents a character's class features, racial traits, etc.
 */
export interface CharacterFeature {
  name: string;                // Feature name
  source: 'class' | 'race' | 'background' | 'feat' | 'item'; // Feature source
  level: number;               // Level gained
  description: string;         // Feature description
  uses?: number;               // Number of uses per rest
  maxUses?: number;            // Maximum uses per rest
  recharge?: 'short' | 'long' | 'daily'; // Recharge type
}

/**
 * Character Interface
 * Main character data structure
 */
export interface Character {
  id: string;                  // Unique character identifier
  name: string;                // Character name
  playerId: string;            // ID of player who owns this character
  campaignId: string;          // Campaign this character belongs to
  
  // Basic Information
  race: CharacterRace;         // Character race
  class: CharacterClass;       // Character class
  background: CharacterBackground; // Character background
  alignment: CharacterAlignment; // Character alignment
  level: number;               // Character level
  experiencePoints: number;    // Current XP
  
  // Physical Description
  age: number;                 // Character age
  height: string;              // Character height
  weight: string;              // Character weight
  eyes: string;                // Eye color
  hair: string;                // Hair color
  skin: string;                // Skin color
  description: string;         // Physical description
  
  // Personality
  personalityTraits: string;   // Personality traits
  ideals: string;              // Character ideals
  bonds: string;               // Character bonds
  flaws: string;               // Character flaws
  backstory: string;           // Character backstory
  
  // Statistics
  stats: CharacterStats;       // Core statistics
  abilities: CharacterAbility[]; // Ability scores
  skills: CharacterSkill[];    // Skills
  savingThrows: CharacterSavingThrows; // Saving throw bonuses
  
  // Combat
  attacks: CharacterAttack[];  // Attacks and spells
  armorClass: number;          // Armor class
  hitPoints: number;           // Current hit points
  maxHitPoints: number;        // Maximum hit points
  speed: number;               // Movement speed
  initiative: number;          // Initiative bonus
  
  // Magic
  spells: CharacterSpell[];    // Known spells
  spellSlots: number[];        // Available spell slots by level
  spellSaveDC: number;         // Spell save DC
  spellAttackBonus: number;    // Spell attack bonus
  
  // Equipment
  equipment: CharacterEquipment[]; // Equipment and items
  currency: {                  // Currency
    copper: number;
    silver: number;
    gold: number;
    platinum: number;
  };
  
  // Features and Traits
  features: CharacterFeature[]; // Class features, racial traits, etc.
  
  // Status
  status: CharacterStatus;     // Character status
  isActive: boolean;           // Whether character is currently active
  
  // Timestamps
  createdAt: string;           // ISO timestamp of creation
  updatedAt: string;           // ISO timestamp of last update
  lastPlayedAt?: string;       // ISO timestamp of last play session
}

/**
 * Character Creation Data Interface
 * Data required to create a new character
 */
export interface CharacterCreateData {
  name: string;                // Character name
  race: CharacterRace;         // Character race
  class: CharacterClass;       // Character class
  background: CharacterBackground; // Character background
  alignment: CharacterAlignment; // Character alignment
  level?: number;              // Starting level (default 1)
  campaignId: string;          // Campaign to create character for
  description?: string;        // Optional description
  backstory?: string;          // Optional backstory
}

/**
 * Character Update Data Interface
 * Data that can be updated in an existing character
 */
export interface CharacterUpdateData {
  name?: string;               // Update character name
  level?: number;              // Update character level
  experiencePoints?: number;   // Update XP
  hitPoints?: number;          // Update current HP
  maxHitPoints?: number;       // Update max HP
  armorClass?: number;         // Update AC
  speed?: number;              // Update speed
  description?: string;        // Update description
  backstory?: string;          // Update backstory
  personalityTraits?: string;  // Update personality
  ideals?: string;             // Update ideals
  bonds?: string;              // Update bonds
  flaws?: string;              // Update flaws
  status?: CharacterStatus;    // Update status
  isActive?: boolean;          // Update active status
}

/**
 * Character API Response Interface
 * Standard response format for character API calls
 */
export interface CharacterResponse {
  success: boolean;            // Whether the operation was successful
  data?: Character | Character[]; // Character data (single or array)
  message?: string;            // Success or error message
  error?: string;              // Error details if operation failed
}

/**
 * Character List Response Interface
 * Response format for character list API calls
 */
export interface CharacterListResponse {
  characters: Character[];     // Array of characters
  total: number;               // Total number of characters
  page: number;                // Current page number
  limit: number;               // Items per page
  hasMore: boolean;            // Whether there are more pages
}

/**
 * Character Roll Request Interface
 * Data for rolling dice for a character
 */
export interface CharacterRollRequest {
  characterId: string;         // Character ID
  rollType: 'ability' | 'skill' | 'saving_throw' | 'attack' | 'damage' | 'custom';
  target: string;              // What to roll (ability name, skill name, etc.)
  formula?: string;            // Custom dice formula
  advantage?: boolean;         // Whether to roll with advantage
  disadvantage?: boolean;      // Whether to roll with disadvantage
  modifier?: number;           // Additional modifier
}

/**
 * Character Action Request Interface
 * Data for performing a character action
 */
export interface CharacterActionRequest {
  characterId: string;         // Character ID
  action: string;              // Action to perform
  target?: string;             // Target of the action
  parameters?: any;            // Additional parameters
}
