/**
 * ShadowRealms design system (Part A of the v0.9 UI work). See ./README.md.
 * Importing this module loads the tokens (CSS custom properties on :root, element styles only
 * under .sr-app), so it is safe to import before the shell opts in.
 */
import './tokens.css';

export {
  DesignProvider,
  MotionToggle,
  useMotionPreference,
  useReducedMotionPref,
  useSystemReducedMotion,
  useDocumentVisible,
  useInView,
  useAmbient,
  useAtmosphere,
  ATMOSPHERE_LEVELS,
} from './motion';

/* glyphs */
export { default as Glyph, AnimatedCandle, BlinkingEye, AiSigil, DrippingBlood, SigilDraw } from './glyphs/Glyph';
export { default as DieFace } from './glyphs/DieFace';
export { GLYPHS, GLYPH_NAMES, GLYPH_GROUPS, sigilFor } from './glyphs/glyphData';

/* components */
export { default as Button, IconButton } from './components/Button';
export { default as Spinner } from './components/Spinner';
export { default as Tooltip } from './components/Tooltip';
export { default as Tabs } from './components/Tabs';
export { default as DotTrack } from './components/DotTrack';
export { Card, Panel, Badge, Avatar, Divider, EmptyState, Kbd } from './components/Surface';
export { Field, Input, Textarea, Select, Checkbox, Switch } from './components/Fields';
export { Modal, Drawer, ToastProvider, useToast, useOptionalToast } from './components/Overlay';
export { Portal } from './components/internal';

/* atmosphere */
export { FogLayer, CandleGlow, BloodDrip } from './atmosphere/Atmosphere';
export { default as SigilReveal, buildSigilPaths } from './atmosphere/SigilReveal';
export {
  Vignette,
  Grain,
  CandleHalo,
  CrackOverlay,
  RollFx,
  rollMood,
  FOUL_MOODS,
  GLORY_MOODS,
  ChronicleSigil,
  RouteTransition,
} from './atmosphere/Ambience';
export { default as DiceRollViz, describeRoll } from './atmosphere/DiceRollViz';
export { analyzeV5, analyzeClassic, OUTCOME_LABELS, outcomeLabels } from './atmosphere/diceAnalysis';
