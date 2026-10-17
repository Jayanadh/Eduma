import { Component, computed, DestroyRef, effect, inject, input, output, signal, untracked } from '@angular/core';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors, problemOf } from '../../core/api-error';
import {
  ImageSlot,
  LifecycleStatus,
  PublicInstitution,
  PublicSite,
  Revision,
  RevisionListItem,
  Section,
  SiteContent,
  StoredTheme,
} from '../../core/api/types';
import { deriveTheme } from '../../core/contrast';
import { dateTime } from '../../core/format';
import { themeVariables } from '../../core/site-store';
import { UnsavedChanges } from '../../core/unsaved-changes';
import { SiteView } from '../public/site-view';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { Icon } from '../../ui/icon';
import { StatusBadge } from '../../ui/status-badge';
import { ToastService } from '../../ui/toast';
import { canAdd, SECTION_LABELS, withUrls } from './limits';
import { SectionForm } from './section-form';
import { ThemeForm } from './theme-form';

/** Whose page is edited: any institution's from the console, or one's own from its workspace. */
export type EditorScope = { kind: 'platform'; institutionId: string } | { kind: 'institution' };
export type EditorInstitution = PublicInstitution & { lifecycle_status: LifecycleStatus };

/** The site API's base under /api/v1/ for a scope. */
export function siteBase(scope: EditorScope): string {
  return scope.kind === 'platform' ? `platform/institutions/${scope.institutionId}/site` : 'institution/site';
}

/**
 * The page editor: look (logo, colours, fonts) and sections on one side, the real public page as a live preview on the
 * other. Edits are a draft until published; saving sends the version it started from, so two editors cannot silently
 * overwrite each other.
 */
@Component({
  selector: 'app-site-editor',
  imports: [Icon, SectionForm, SiteView, StatusBadge, ThemeForm],
  templateUrl: './site-editor.html',
  styleUrl: './site-editor.scss',
  host: { '(window:beforeunload)': 'warnBeforeUnload($event)' },
})
export class SiteEditor {
  readonly scope = input.required<EditorScope>();
  readonly institution = input.required<EditorInstitution>();
  /** After a publish, so the page around the editor can refresh its readiness checklist. */
  readonly published = output();
  private readonly api = inject(Api);
  private readonly confirm = inject(ConfirmDialog);
  private readonly toasts = inject(ToastService);
  private readonly unsaved = inject(UnsavedChanges);

  protected readonly base = computed(() => siteBase(this.scope()));
  protected readonly labels = SECTION_LABELS;
  protected readonly dateTime = dateTime;
  readonly canAdd = canAdd;

  protected readonly draft = signal<Revision | null>(null);
  /** The sections being edited: a copy the forms change in place; `edits` counts changes for the preview. */
  content: SiteContent = { sections: [] };
  private readonly edits = signal(0);
  protected readonly theme = signal<StoredTheme>({
    primary_color: '#4B5AE4',
    secondary_color: '#FFD43B',
    heading_font: 'bricolage',
    body_font: 'dm-sans',
  });
  protected readonly logo = signal<{ id: string; url: string } | null>(null);
  readonly dirty = signal(false);
  protected readonly saving = signal(false);
  readonly conflict = signal(false);
  /** The draft was published or replaced by someone else: only reloading makes sense. */
  protected readonly draftGone = signal(false);
  protected readonly problems = signal<string[]>([]);
  protected readonly loadError = signal('');
  protected readonly open = signal<string | null>('hero');
  protected readonly view = signal<'edit' | 'preview'>('edit');
  protected readonly width = signal<'wide' | 'phone'>('wide');
  protected readonly history = signal<RevisionListItem[] | null>(null);

  readonly previewStyle = computed(() => themeVariables(deriveTheme(this.theme())));
  protected readonly previewSite = computed<PublicSite>(() => {
    this.edits();
    return {
      kind: 'institution',
      mode: 'full',
      institution: this.institution(),
      theme: deriveTheme(this.theme()),
      content: withUrls(this.content),
      logo_url: this.logo()?.url ?? null,
    };
  });

  constructor() {
    effect(() => {
      this.base();
      untracked(() => this.load());
    });
    inject(DestroyRef).onDestroy(() => this.unsaved.dirty.set(false));
  }

  protected load(): void {
    this.loadError.set('');
    this.api.get<Revision>(`${this.base()}/draft`).subscribe({
      next: (draft) => this.accept(draft),
      error: (err) => this.loadError.set(apiErrorMessage(err)),
    });
  }

  private accept(draft: Revision): void {
    this.draft.set(draft);
    this.content = structuredClone(draft.content);
    const { primary_color, secondary_color, heading_font, body_font } = draft.theme;
    this.theme.set({ primary_color, secondary_color, heading_font, body_font });
    this.logo.set(draft.logo);
    this.conflict.set(false);
    this.draftGone.set(false);
    this.problems.set([]);
    this.setDirty(false);
    this.edits.update((n) => n + 1);
  }

  private setDirty(value: boolean): void {
    this.dirty.set(value);
    this.unsaved.dirty.set(value);
  }

  changed(): void {
    this.setDirty(true);
    this.edits.update((n) => n + 1);
  }

  setTheme(name: keyof StoredTheme, value: string): void {
    this.theme.update((theme) => ({ ...theme, [name]: value }));
    this.changed();
  }

  protected setLogo(slot: ImageSlot | null): void {
    this.logo.set(slot?.asset ? { id: slot.asset, url: `/api/v1/public/assets/${slot.asset}` } : null);
    this.changed();
  }

  /** Moves a section up or down; the hero stays first. */
  moveSection(index: number, delta: -1 | 1): void {
    const target = index + delta;
    const sections = this.content.sections;
    if (index === 0 || target <= 0 || target >= sections.length) {
      return;
    }
    [sections[index], sections[target]] = [sections[target], sections[index]];
    this.changed();
  }

  /** Shows or hides a section; the hero is always shown. */
  toggleSection(index: number): void {
    if (index === 0) {
      return;
    }
    this.content.sections[index].visible = !this.content.sections[index].visible;
    this.changed();
  }

  protected toggleOpen(section: Section): void {
    this.open.update((current) => (current === section.id ? null : section.id));
  }

  save(after?: () => void, version?: number): void {
    const draft = this.draft();
    if (!draft || this.saving()) {
      return;
    }
    this.saving.set(true);
    this.problems.set([]);
    this.api
      .put<Revision>(`${this.base()}/draft`, {
        version: version ?? draft.version,
        ...this.theme(),
        logo: this.logo()?.id ?? null,
        content: this.content,
      })
      .subscribe({
        next: (saved) => {
          this.saving.set(false);
          this.draft.set(saved);
          this.setDirty(false);
          this.conflict.set(false);
          if (after) {
            after();
          } else {
            this.toasts.show(`Draft saved (version ${saved.number}).`);
          }
        },
        error: (err) => {
          this.saving.set(false);
          const problem = problemOf(err);
          if (problem?.code === 'version_conflict') {
            this.conflict.set(true);
            this.draftGone.set(problem.current_version == null);
          } else if (problem?.code === 'validation_failed') {
            this.problems.set(Object.entries(fieldErrors(err)).map(([field, message]) => this.describe(field, message)));
          } else {
            this.toasts.show(apiErrorMessage(err), 'danger');
          }
        },
      });
  }

  /** "content.sections.2.items.0.cta.href" → "Steps, item 1: cta href: …", so the admin can find the field. */
  private describe(field: string, message: string): string {
    const match = field.match(/^content\.sections\.(\d+)\.?(.*)$/);
    if (!match) {
      return `${field.replace(/_/g, ' ') || 'Page'}: ${message}`;
    }
    const section = this.content.sections[Number(match[1])];
    const where = match[2].replace(/(items|images)\.(\d+)/, (_, kind, n) => `${kind === 'items' ? 'item' : 'picture'} ${Number(n) + 1}`);
    return `${section ? this.labels[section.type] : 'A section'}${where ? ', ' + where.replace(/[._]/g, ' ') : ''}: ${message}`;
  }

  /** After a conflict: keep these edits, saving them over the newer draft. */
  protected keepMine(): void {
    this.api.get<Revision>(`${this.base()}/draft`).subscribe({
      next: (latest) => this.save(undefined, latest.version),
      error: (err) => this.toasts.show(apiErrorMessage(err), 'danger'),
    });
  }

  publish(): void {
    if (this.dirty()) {
      this.save(() => this.publishSaved());
    } else {
      this.publishSaved();
    }
  }

  private publishSaved(): void {
    const draft = this.draft();
    if (!draft) {
      return;
    }
    this.saving.set(true);
    this.api.post<Revision>(`${this.base()}/draft/publish`, { version: draft.version }).subscribe({
      next: () => {
        this.saving.set(false);
        const live = this.institution().lifecycle_status === 'active';
        this.toasts.show(
          live ? 'Published. The public page is live.' : 'Published. It will go live when the institution is activated.',
        );
        this.history.set(null);
        this.published.emit();
        this.load();
      },
      error: (err) => {
        this.saving.set(false);
        if (problemOf(err)?.code === 'version_conflict') {
          this.conflict.set(true);
        } else {
          this.toasts.show(apiErrorMessage(err), 'danger');
        }
      },
    });
  }

  protected toggleHistory(): void {
    if (this.history()) {
      this.history.set(null);
      return;
    }
    this.api.get<RevisionListItem[]>(`${this.base()}/revisions`).subscribe({
      next: (revisions) => this.history.set(revisions),
      error: (err) => this.toasts.show(apiErrorMessage(err), 'danger'),
    });
  }

  protected async restore(revision: RevisionListItem): Promise<void> {
    const yes = await this.confirm.ask({
      title: `Restore version ${revision.number}?`,
      message: 'Its look and sections replace the current draft. Nothing goes live until you publish.',
      confirmLabel: 'Restore into the draft',
    });
    if (!yes) {
      return;
    }
    this.api.post<Revision>(`${this.base()}/revisions/${revision.id}/restore`).subscribe({
      next: (draft) => {
        this.accept(draft);
        this.history.set(null);
        this.toasts.show(`Version ${revision.number} is back in the draft.`);
      },
      error: (err) => this.toasts.show(apiErrorMessage(err), 'danger'),
    });
  }

  protected warnBeforeUnload(event: BeforeUnloadEvent): void {
    if (this.dirty()) {
      event.preventDefault();
    }
  }
}
