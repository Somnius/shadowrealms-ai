import React from 'react';
import { Card, Glyph } from '../design';
import './sheet.css';

const LINE = { vampire: 'vampire', werewolf: 'werewolf', mage: 'mage' };

/**
 * Themed panel used by the legacy sheet / creation screens. Now a design-system ornate Card
 * (original corner filigree, tokens) with the game line's accent. theme: 'vampire' | 'mage' |
 * 'werewolf' | 'none'. No icon font, no random particles.
 */
export const GothicBox = ({ children, style, className = '', theme = 'none' }) => (
  <Card
    ornate
    className={`sr-gbox sr-gbox--${theme} ${className}`.trim()}
    data-line={LINE[theme]}
    style={{ position: 'relative', ...style }}
  >
    {children}
  </Card>
);

// Skull Divider
export const SkullDivider = () => (
  <div className="skull-divider" aria-hidden="true">
    <Glyph name="skull" size={18} /> <Glyph name="dagger" size={18} /> <Glyph name="skull" size={18} />
  </div>
);

// Ornate Divider with Gothic Icons
export const OrnateDivider = ({ icon = 'skull' }) => (
  <div className="ornate-divider" aria-hidden="true">
    <Glyph name={icon} size={18} style={{ color: 'var(--sr-blood-500)', margin: '0 10px' }} />
  </div>
);

// Gothic Button with hover effect
export const GothicButton = ({ children, onClick, style, disabled, type = 'button' }) => (
  <button
    type={type}
    onClick={onClick}
    disabled={disabled}
    className="gothic-button"
    style={style}
  >
    {children}
  </button>
);

// Add random floating particles to a container
export const FloatingParticles = ({ count = 10 }) => {
  const particles = Array.from({ length: count }, (_, i) => ({
    id: i,
    top: `${Math.random() * 100}%`,
    left: `${Math.random() * 100}%`,
    delay: `${Math.random() * 4}s`,
    duration: `${3 + Math.random() * 3}s`,
  }));

  return (
    <>
      {particles.map(p => (
        <div
          key={p.id}
          className="particle"
          style={{
            top: p.top,
            left: p.left,
            animationDelay: p.delay,
            animationDuration: p.duration
          }}
        >
          <Glyph name="ornament" size={10} />
        </div>
      ))}
    </>
  );
};

// Magic Circle Decoration
export const MagicCircle = ({ style }) => (
  <div className="magic-circle" style={style}></div>
);

// Blood Splatter Decoration
export const BloodSplatter = ({ style }) => (
  <div className="blood-splatter" style={style}></div>
);

const GothicDecorations = {
  GothicBox,
  SkullDivider,
  OrnateDivider,
  GothicButton,
  FloatingParticles,
  MagicCircle,
  BloodSplatter
};

export default GothicDecorations;

