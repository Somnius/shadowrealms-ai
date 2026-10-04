import React from 'react';
import { render, screen } from '@testing-library/react';
import Glyph, { AnimatedCandle } from '../glyphs/Glyph';
import DieFace from '../glyphs/DieFace';
import { GLYPHS, GLYPH_NAMES, GLYPH_GROUPS, sigilFor } from '../glyphs/glyphData';

describe('glyph set', () => {
  test('has the full set: 28+ identity glyphs plus UI, clan and discipline sigils', () => {
    expect(GLYPH_NAMES.length).toBeGreaterThanOrEqual(60);
    expect(GLYPH_GROUPS.clan.length).toBeGreaterThanOrEqual(16);
    expect(GLYPH_GROUPS.discipline.length).toBeGreaterThanOrEqual(12);
    ['menu', 'close', 'send', 'settings', 'user', 'logout', 'globe', 'bell', 'search', 'chevron-down'].forEach((n) =>
      expect(GLYPHS[n]).toBeDefined()
    );
  });

  test('every glyph renders an svg with drawable shapes and no NaN coordinates', () => {
    GLYPH_NAMES.forEach((name) => {
      const { container, unmount } = render(<Glyph name={name} />);
      const svg = container.querySelector('svg');
      expect(svg).not.toBeNull();
      expect(svg.getAttribute('viewBox')).toBe('0 0 24 24');
      expect(svg.querySelectorAll('path, circle, ellipse, rect').length).toBeGreaterThan(0);
      expect(svg.innerHTML).not.toMatch(/NaN|undefined/);
      unmount();
    });
  });

  test('with a title it is an image with that accessible name', () => {
    render(<Glyph name="candle" title="Storyteller is weaving" />);
    const img = screen.getByRole('img', { name: 'Storyteller is weaving' });
    expect(img.querySelector('title')).toHaveTextContent('Storyteller is weaving');
  });

  test('without a title it is hidden from assistive tech', () => {
    const { container } = render(<Glyph name="skull" />);
    expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
    expect(screen.queryByRole('img')).toBeNull();
  });

  test('unknown glyph renders nothing', () => {
    const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
    const { container } = render(<Glyph name="nope" />);
    expect(container.firstChild).toBeNull();
    warn.mockRestore();
  });

  test('animated and draw-on variants carry their classes', () => {
    const { container } = render(
      <>
        <AnimatedCandle />
        <Glyph name="clan-brujah" draw />
      </>
    );
    expect(container.querySelector('.sr-glyph--animate .sr-glyph-flame')).not.toBeNull();
    const drawn = container.querySelector('.sr-glyph--draw .sr-glyph-stroke');
    expect(drawn).toHaveAttribute('pathLength', '1');
  });

  test('sigilFor maps ids to glyph names', () => {
    expect(sigilFor('clan', 'Banu Haqim')).toBe('clan-banu-haqim');
    expect(sigilFor('discipline', 'blood_sorcery')).toBe('disc-blood-sorcery');
    expect(sigilFor('clan', 'Unknown Bloodline')).toBeNull();
  });

  test('DieFace names the die for screen readers', () => {
    render(<DieFace value={10} hunger />);
    expect(screen.getByRole('img', { name: 'Hunger die: 10, critical' })).toBeInTheDocument();
  });
});
