import { Component, computed, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { PublicSite, Section } from '../../core/api/types';
import { FaqSectionView } from './sections/faq';
import { FeatureSectionView } from './sections/feature';
import { GallerySectionView } from './sections/gallery';
import { HeroSectionView } from './sections/hero';
import { OfferingsSectionView } from './sections/offerings';
import { PeopleSectionView } from './sections/people';
import { StepsSectionView } from './sections/steps';
import { TestimonialsSectionView } from './sections/testimonials';

/** Menu words for each kind of section; a short eyebrow (the section's own label) is used instead when it fits. */
const NAV_LABELS: Readonly<Record<Section['type'], string>> = {
  hero: '',
  offerings: 'What we offer',
  steps: 'How it works',
  people: 'People',
  gallery: 'Gallery',
  testimonials: 'Stories',
  feature: 'More',
  faq: 'FAQ',
};

/**
 * A public page: header, the visible sections in their order, and the footer. Used for visitors (LandingPage) and, with
 * `preview`, inside the site editor, where links do not navigate and nothing leaves the editor.
 */
@Component({
  selector: 'app-site-view',
  imports: [
    FaqSectionView,
    FeatureSectionView,
    GallerySectionView,
    HeroSectionView,
    OfferingsSectionView,
    PeopleSectionView,
    RouterLink,
    StepsSectionView,
    TestimonialsSectionView,
  ],
  template: `
    <div class="site" [class.preview]="preview()" (click)="stayInPreview($event)">
      <header class="site-header">
        <div class="site-header-bar">
          <a class="site-brand" href="#top">
            @if (logoUrl(); as logo) {
              <img [src]="logo" alt="" width="40" height="40" />
            }
            <span>{{ name() }}</span>
          </a>
          @if (!titleOnly()) {
            <nav class="site-nav" aria-label="On this page">
              @for (item of nav(); track item.href) {
                <a [href]="item.href">{{ item.label }}</a>
              }
            </nav>
          }
          <div class="site-header-actions">
            @if (site().kind === 'institution' && !preview()) {
              <a class="cta cta-outline cta-small" routerLink="/apply">Apply</a>
              <a class="cta cta-outline cta-small" routerLink="/login">Sign in</a>
            }
            @if (hero(); as hero) {
              @if (!titleOnly()) {
                <a class="cta cta-primary cta-small header-cta" [href]="hero.primary_cta.href">{{
                  hero.primary_cta.label
                }}</a>
              }
            }
          </div>
        </div>
      </header>

      <main id="top">
        @for (section of sections(); track section.id) {
          <section [id]="'s-' + section.id" [class]="'block block-' + section.type">
            @switch (section.type) {
              @case ('hero') {
                <app-hero-section [section]="section" [titleOnly]="titleOnly()" />
                @if (titleOnly()) {
                  <p class="opening-soon"><span class="pill-eyebrow tone-2">Opening soon</span></p>
                }
              }
              @case ('offerings') {
                <app-offerings-section [section]="section" />
              }
              @case ('steps') {
                <app-steps-section [section]="section" />
              }
              @case ('people') {
                <app-people-section [section]="section" />
              }
              @case ('gallery') {
                <app-gallery-section [section]="section" />
              }
              @case ('testimonials') {
                <app-testimonials-section [section]="section" />
              }
              @case ('feature') {
                <app-feature-section [section]="section" />
              }
              @case ('faq') {
                <app-faq-section [section]="section" />
              }
            }
          </section>
        }
      </main>

      <footer class="site-footer">
        <div class="wrap site-footer-inner">
          <div>
            <p class="site-footer-name">{{ name() }}</p>
            @if (contact(); as info) {
              @if (info.address) {
                <p>{{ info.address }}</p>
              }
            }
          </div>
          <ul class="site-footer-links">
            @if (contact(); as info) {
              @if (info.contact_phone) {
                <li><a [href]="'tel:' + info.contact_phone">{{ info.contact_phone }}</a></li>
              }
              @if (info.contact_email) {
                <li><a [href]="'mailto:' + info.contact_email">{{ info.contact_email }}</a></li>
              }
              @if (!preview()) {
                <li><a routerLink="/login">Sign in</a></li>
              }
            }
          </ul>
          <p class="site-footer-credit">
            @if (site().kind === 'institution') {
              Powered by Eduma
            } @else {
              Eduma · for schools, colleges and universities
            }
          </p>
        </div>
      </footer>
    </div>
  `,
})
export class SiteView {
  readonly site = input.required<PublicSite>();
  readonly preview = input(false);

  protected readonly titleOnly = computed(() => {
    const site = this.site();
    return site.kind === 'institution' && site.mode === 'opening_soon';
  });
  protected readonly sections = computed(() => {
    const site = this.site();
    const visible = 'content' in site ? site.content.sections.filter((section) => section.visible) : [];
    return this.titleOnly() ? visible.slice(0, 1) : visible;
  });
  protected readonly hero = computed(() => {
    const first = this.sections()[0];
    return first?.type === 'hero' ? first : null;
  });
  protected readonly nav = computed(() =>
    this.sections()
      .filter((section) => section.type !== 'hero')
      .map((section) => ({
        href: `#s-${section.id}`,
        label: section.eyebrow && section.eyebrow.length <= 20 ? section.eyebrow : NAV_LABELS[section.type],
      })),
  );
  protected readonly name = computed(() => {
    const site = this.site();
    return site.kind === 'institution' ? site.institution.display_name : 'Eduma';
  });
  protected readonly logoUrl = computed(() => {
    const site = this.site();
    return 'logo_url' in site ? site.logo_url : null;
  });
  protected readonly contact = computed(() => {
    const site = this.site();
    return site.kind === 'institution' && 'contact_email' in site.institution ? site.institution : null;
  });

  /** In the editor's preview, links show where they go but do not follow it. */
  protected stayInPreview(event: MouseEvent): void {
    if (this.preview() && (event.target as HTMLElement).closest('a')) {
      event.preventDefault();
    }
  }
}
