import { contrast, deriveTheme, readableOn, textSafe } from './contrast';

// The same rules and expected values as the server's sites/theme.py tests.
describe('contrast', () => {
  it('matches WCAG for known pairs', () => {
    expect(contrast('#FFFFFF', '#000000')).toBeCloseTo(21, 5);
    expect(contrast('#767676', '#FFFFFF')).toBeCloseTo(4.54, 2);
    expect(contrast('#4B5AE4', '#FFFFFF')).toBeCloseTo(5.41, 1);
  });

  it('picks the readable text colour', () => {
    expect(readableOn('#4B5AE4')).toBe('#FFFFFF');
    expect(readableOn('#FFD43B')).toBe('#17132B');
  });

  it('darkens a colour for text only when needed', () => {
    expect(textSafe('#4B5AE4')).toBe('#4B5AE4');
    const darker = textSafe('#FFD43B');
    expect(contrast(darker, '#FFFFFF')).toBeGreaterThanOrEqual(4.5);
    expect(darker).toMatch(/^#[0-9A-F]{6}$/);
  });

  it('gives exactly what the server gives', () => {
    // Values printed by sites.theme.text_safe on the server.
    expect(textSafe('#FFD43B')).toBe('#8D6E00');
    expect(textSafe('#FCD34D')).toBe('#8F6E02');
    expect(textSafe('#F9A8D4')).toBe('#DA0F7D');
  });

  it('puts text on a darker fill for mid-tones where neither white nor ink reaches 4.5:1', () => {
    for (const color of ['#E0393E', '#D9480F', '#1C7ED6', '#CF2AD5']) {
      const theme = deriveTheme({ primary_color: color, secondary_color: color, heading_font: 'bricolage', body_font: 'dm-sans' });
      expect(theme.primary_fill).not.toBe(color);
      expect(contrast(theme.on_primary, theme.primary_fill)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it('derives the theme the server would', () => {
    expect(deriveTheme({ primary_color: '#4B5AE4', secondary_color: '#FFD43B', heading_font: 'bricolage', body_font: 'dm-sans' })).toMatchObject({
      on_primary: '#FFFFFF',
      primary_text: '#4B5AE4',
      on_secondary: '#17132B',
    });
  });
});
