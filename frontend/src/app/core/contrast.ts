import { StoredTheme, Theme } from './api/types';

/**
 * The server's colour rules (backend sites/theme.py), so the editor's preview shows the readable colours a theme will
 * get before it is saved. The server stays the authority: it derives them again on every save.
 */
export const INK = '#17132B';
export const WHITE = '#FFFFFF';

function rgb(color: string): [number, number, number] {
  const value = color.replace('#', '');
  return [0, 2, 4].map((i) => parseInt(value.slice(i, i + 2), 16) / 255) as [number, number, number];
}

function luminance(color: string): number {
  const [r, g, b] = rgb(color).map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrast(a: string, b: string): number {
  const [lighter, darker] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (lighter + 0.05) / (darker + 0.05);
}

export function readableOn(color: string): string {
  return contrast(WHITE, color) >= contrast(INK, color) ? WHITE : INK;
}

// Python's colorsys HLS conversions, which the server uses.
function rgbToHls(r: number, g: number, b: number): [number, number, number] {
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  if (max === min) {
    return [0, l, 0];
  }
  const range = max - min;
  const s = l <= 0.5 ? range / (max + min) : range / (2 - max - min);
  const [rc, gc, bc] = [(max - r) / range, (max - g) / range, (max - b) / range];
  const h = r === max ? bc - gc : g === max ? 2 + rc - bc : 4 + gc - rc;
  return [(((h / 6) % 1) + 1) % 1, l, s];
}

function hlsToRgb(h: number, l: number, s: number): [number, number, number] {
  if (s === 0) {
    return [l, l, l];
  }
  const m2 = l <= 0.5 ? l * (1 + s) : l + s - l * s;
  const m1 = 2 * l - m2;
  const v = (hue: number) => {
    hue = ((hue % 1) + 1) % 1;
    if (hue < 1 / 6) return m1 + (m2 - m1) * hue * 6;
    if (hue < 0.5) return m2;
    if (hue < 2 / 3) return m1 + (m2 - m1) * (2 / 3 - hue) * 6;
    return m1;
  };
  return [v(h + 1 / 3), v(h), v(h - 1 / 3)];
}

/** `color` if readable as text on `background`, otherwise the same hue darkened in 2% steps until it is. */
export function textSafe(color: string, background = WHITE, target = 4.5): string {
  let result = color.toUpperCase();
  const [h, initial, s] = rgbToHls(...rgb(result));
  let l = initial;
  while (contrast(result, background) < target && l > 0) {
    l = Math.max(0, l - 0.02);
    result =
      '#' +
      hlsToRgb(h, l, s)
        .map((c) => Math.round(c * 255).toString(16).padStart(2, '0'))
        .join('')
        .toUpperCase();
  }
  return result;
}

export function deriveTheme(theme: StoredTheme): Theme {
  return {
    ...theme,
    on_primary: readableOn(theme.primary_color),
    primary_text: textSafe(theme.primary_color),
    on_secondary: readableOn(theme.secondary_color),
    secondary_text: textSafe(theme.secondary_color),
  };
}
