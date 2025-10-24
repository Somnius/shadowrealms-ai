import React, { useEffect, useState } from 'react';

// Gothic Border with decorations
// theme: 'vampire' (blood), 'mage' (sparkles), 'werewolf' (bites), 'none' (clean)
export const GothicBox = ({ children, style, className = '', theme = 'none' }) => {
  const [bloodDrops, setBloodDrops] = useState([]);
  const [sparkles, setSparkles] = useState([]);
  const [biteMarks, setBiteMarks] = useState([]);

  useEffect(() => {
    // Generate blood drops for vampire theme
    if (theme === 'vampire') {
      const drops = Array.from({ length: 3 }, (_, i) => ({
        id: i,
        left: `${Math.random() * 90 + 5}%`,
        delay: `${Math.random() * 3}s`
      }));
      setBloodDrops(drops);
    }

    // Generate sparkles for mage theme
    if (theme === 'mage') {
      const sparks = Array.from({ length: 4 }, (_, i) => ({
        id: i,
        top: `${Math.random() * 80 + 10}%`,
        left: `${Math.random() * 80 + 10}%`,
        delay: `${Math.random() * 2}s`
      }));
      setSparkles(sparks);
    }

    // Generate bite marks for werewolf theme
    if (theme === 'werewolf') {
      const bites = Array.from({ length: 3 }, (_, i) => ({
        id: i,
        top: `${Math.random() * 70 + 10}%`,
        left: `${Math.random() * 80 + 10}%`,
        delay: `${Math.random() * 4}s`,
        rotation: Math.random() * 360
      }));
      setBiteMarks(bites);
    }
  }, [theme]);

  return (
    <div className={`gothic-border gothic-card ${className}`} style={{ position: 'relative', ...style }}>
      {/* Skeleton Hand Corners */}
      <div className="gothic-corner top-left">
        <i className="fas fa-hand-paper"></i>
      </div>
      <div className="gothic-corner top-right">
        <i className="fas fa-hand-paper"></i>
      </div>
      <div className="gothic-corner bottom-left">
        <i className="fas fa-hand-paper"></i>
      </div>
      <div className="gothic-corner bottom-right">
        <i className="fas fa-hand-paper"></i>
      </div>

      {/* Candles */}
      <div className="candle-decoration left">
        <i className="fas fa-candle-holder candle"></i>
      </div>
      <div className="candle-decoration right">
        <i className="fas fa-candle-holder candle"></i>
      </div>

      {/* Blood Drops - Vampire Theme */}
      {theme === 'vampire' && bloodDrops.map(drop => (
        <div
          key={drop.id}
          className="blood-drop"
          style={{
            left: drop.left,
            top: '0',
            animationDelay: drop.delay
          }}
        />
      ))}

      {/* Magic Sparkles - Mage Theme */}
      {theme === 'mage' && sparkles.map(spark => (
        <div
          key={spark.id}
          className="magic-sparkle"
          style={{
            top: spark.top,
            left: spark.left,
            animationDelay: spark.delay
          }}
        >
          ✦
        </div>
      ))}

      {/* Bite Marks - Werewolf Theme */}
      {theme === 'werewolf' && biteMarks.map(bite => (
        <div
          key={bite.id}
          className="bite-mark"
          style={{
            top: bite.top,
            left: bite.left,
            animationDelay: bite.delay,
            transform: `rotate(${bite.rotation}deg)`
          }}
        />
      ))}

      {/* Content */}
      {children}
    </div>
  );
};

// Skull Divider
export const SkullDivider = () => (
  <div className="skull-divider">
    <i className="fas fa-skull"></i> ⚔ <i className="fas fa-skull"></i>
  </div>
);

// Ornate Divider with Gothic Icons
export const OrnateDivider = ({ icon = 'skull' }) => (
  <div className="ornate-divider">
    <i className={`fas fa-${icon}`} style={{ color: '#e94560', margin: '0 10px' }}></i>
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
    icon: ['✦', '✧', '★', '☆', '•'][Math.floor(Math.random() * 5)]
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
          {p.icon}
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

export default {
  GothicBox,
  SkullDivider,
  OrnateDivider,
  GothicButton,
  FloatingParticles,
  MagicCircle,
  BloodSplatter
};

