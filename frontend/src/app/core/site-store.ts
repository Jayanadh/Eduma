import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { computed, inject, Service, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { PublicSite, SiteKind, Theme } from './api/types';

/** Font codes the server accepts (sites.theme) → the CSS family each one loads (see styles/_fonts.scss). */
export const FONT_FAMILIES: Readonly<Record<string, string>> = {
  bricolage: "'Bricolage Grotesque Variable', system-ui, sans-serif",
  fredoka: "'Fredoka Variable', system-ui, sans-serif",
  jakarta: "'Plus Jakarta Sans Variable', system-ui, sans-serif",
  'space-grotesk': "'Space Grotesk Variable', system-ui, sans-serif",
  fraunces: "'Fraunces Variable', Georgia, serif",
  playfair: "'Playfair Display Variable', Georgia, serif",
  'dm-sans': "'DM Sans Variable', system-ui, -apple-system, 'Segoe UI', sans-serif",
  inter: "'Inter Variable', system-ui, -apple-system, 'Segoe UI', sans-serif",
  nunito: "'Nunito Variable', system-ui, sans-serif",
  'source-sans': "'Source Sans 3 Variable', system-ui, sans-serif",
  lora: "'Lora Variable', Georgia, serif",
};

/** The CSS variables a theme sets (see styles/_tokens.scss); the soft tints follow from these. */
export function themeVariables(theme: Theme): Record<string, string> {
  return {
    '--brand-primary': theme.primary_color,
    '--brand-on-primary': theme.on_primary,
    '--brand-primary-text': theme.primary_text,
    '--brand-secondary': theme.secondary_color,
    '--brand-on-secondary': theme.on_secondary,
    '--brand-secondary-text': theme.secondary_text,
    '--font-heading': FONT_FAMILIES[theme.heading_font] ?? FONT_FAMILIES['bricolage'],
    '--font-body': FONT_FAMILIES[theme.body_font] ?? FONT_FAMILIES['dm-sans'],
  };
}

const EDUMA_LOGO = '/eduma-logo.png';

/**
 * What this address serves: the Eduma main site, an institution's site, or nothing (an unknown address). Asked once at
 * start-up; the answer themes the whole app with the site's colours, fonts and logo.
 */
@Service()
export class SiteStore {
  private readonly http = inject(HttpClient);
  private readonly current = signal<PublicSite | null>(null);
  readonly failed = signal(false);

  readonly site = this.current.asReadonly();
  readonly kind = computed<SiteKind>(() => this.current()?.kind ?? 'unknown');
  readonly institutionName = computed(() => {
    const site = this.current();
    return site?.kind === 'institution' ? site.institution.display_name : 'Eduma';
  });
  /** The logo shown in headers: the site's own, Eduma's on the platform, or none (show the name instead). */
  readonly logoUrl = computed(() => {
    const site = this.current();
    if (!site || site.kind === 'platform') {
      return EDUMA_LOGO;
    }
    return 'logo_url' in site ? site.logo_url : null;
  });

  async load(): Promise<void> {
    try {
      this.current.set(await firstValueFrom(this.http.get<PublicSite>('/api/v1/public/site')));
      this.failed.set(false);
    } catch (err) {
      this.current.set(null);
      // A 404 is an address with no Eduma site; anything else is a failure worth retrying.
      this.failed.set(!(err instanceof HttpErrorResponse && err.status === 404));
    }
    const site = this.current();
    if (site && 'theme' in site) {
      this.apply(site.theme, this.logoUrl(), this.institutionName());
    } else {
      document.title = this.institutionName();
    }
  }

  apply(theme: Theme, logoUrl: string | null, title: string): void {
    const root = document.documentElement;
    for (const [name, value] of Object.entries(themeVariables(theme))) {
      root.style.setProperty(name, value);
    }
    let icon = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
    if (!icon) {
      icon = document.createElement('link');
      icon.rel = 'icon';
      document.head.appendChild(icon);
    }
    icon.href = logoUrl ?? EDUMA_LOGO;
    document.title = title;
  }
}
