import React from 'react';
import { classifyClassicDie } from '../../dice/classicDiceDisplay';
import { classifyV5Die } from '../../dice/v5DiceDisplay';

const CLASSIC_BG = { one: '#8b0000', ten: '#ffd700', success: '#2d7a3e', fail: '#374151' };
const V5_BG = {
  normal: { ten: '#ffd700', success: '#2d7a3e', fail: '#374151', bestial: '#374151' },
  hunger: { ten: '#ff6b6b', success: '#991b1b', fail: '#3f1d1d', bestial: '#450a0a' },
};

/**
 * One die face. V5 Hunger dice get a red body and border; a Hunger 1 shows a skull.
 * `reroll`: a classic specialty reroll die (dashed border + ↻ corner mark).
 */
export default function DiceFace({
  value,
  edition,
  difficulty,
  hunger = false,
  reroll = false,
  size = 54,
  selected = false,
  onClick,
  title,
}) {
  const v = parseInt(value, 10) || 1;
  let bg;
  let label = String(v);
  let border = '1px solid rgba(255,255,255,0.12)';
  if (edition === 'v5') {
    const c = classifyV5Die(v, hunger);
    bg = V5_BG[c.kind][c.state];
    if (hunger) border = '2px solid #dc2626';
    if (c.state === 'bestial') label = '☠';
  } else {
    bg = CLASSIC_BG[classifyClassicDie(v, difficulty)];
  }
  if (reroll) border = '2px dashed #fbbf24';
  if (selected) border = '3px solid #38bdf8';
  const dark = (edition === 'v5' && !hunger && v === 10) || (edition !== 'v5' && v === 10);
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag
      type={onClick ? 'button' : undefined}
      onClick={onClick}
      title={title || (hunger ? `Hunger die: ${v}` : reroll ? `Specialty reroll: ${v}` : `${v}`)}
      aria-pressed={onClick ? selected : undefined}
      style={{
        width: `${size}px`,
        height: `${size}px`,
        borderRadius: `${Math.round(size / 4.5)}px`,
        border,
        background: `linear-gradient(180deg, ${bg} 0%, rgba(15, 23, 41, 0.2) 100%)`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        boxShadow: hunger ? '0 0 14px rgba(220,38,38,0.45)' : '0 10px 35px rgba(0,0,0,0.45)',
        color: dark ? '#1b1b1b' : 'white',
        fontFamily: 'Cinzel, serif',
        fontSize: `${Math.round(size / 3)}px`,
        fontWeight: 900,
        userSelect: 'none',
        padding: 0,
        cursor: onClick ? 'pointer' : 'default',
        position: 'relative',
      }}
    >
      {label}
      {reroll ? (
        <span
          aria-hidden="true"
          style={{
            position: 'absolute',
            top: '-7px',
            right: '-7px',
            fontSize: `${Math.max(10, Math.round(size / 4.5))}px`,
            lineHeight: 1,
            padding: '2px 3px',
            borderRadius: '999px',
            background: '#fbbf24',
            color: '#1b1b1b',
          }}
        >
          ↻
        </span>
      ) : null}
    </Tag>
  );
}
