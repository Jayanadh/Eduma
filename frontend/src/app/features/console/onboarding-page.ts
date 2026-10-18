import { HttpClient } from '@angular/common/http';
import { afterNextRender, Component, computed, ElementRef, inject, Injector, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { catchError, debounceTime, distinctUntilChanged, map, of, switchMap } from 'rxjs';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
import { Category, CATEGORY_LABELS, InstitutionDetail, ModuleInfo } from '../../core/api/types';
import { COUNTRIES, CURRENCIES, TIME_ZONES } from '../../core/locales';
import { defaultsFor } from '../../core/modules';
import { slugify } from '../../core/slug';
import { Icon } from '../../ui/icon';
import { ModulePicker } from './module-picker';
import { PageHeader } from '../../ui/page-header';
import { Reveal } from '../../ui/reveal';

const STEPS = ['Identity and type', 'Contacts', 'Web address', 'Modules', 'Institution Admin', 'Review and create'];
/** Which step holds each field, so a server error can send the admin back to it. */
const GROUP_STEP: Readonly<Record<string, number>> = { identity: 0, contacts: 1, address: 2, modules: 3, admin: 4 };
const FIELD_GROUP: Readonly<Record<string, string>> = {
  legal_name: 'identity',
  display_name: 'identity',
  category: 'identity',
  board_affiliation_code: 'identity',
  udise_code: 'identity',
  aishe_code: 'identity',
  contact_email: 'contacts',
  contact_phone: 'contacts',
  address: 'contacts',
  country_code: 'contacts',
  timezone: 'contacts',
  base_currency: 'contacts',
  slug: 'address',
  modules: 'modules',
};
type SlugCheck = { available: boolean; reason: string };

/**
 * Onboarding: the platform admin enters an institution, chooses its web address and gives its Institution Admin a
 * first password. One request creates it all; a retry (the same Idempotency-Key) never makes a second institution.
 */
@Component({
  selector: 'app-onboarding-page',
  imports: [Icon, ModulePicker, PageHeader, ReactiveFormsModule, Reveal],
  templateUrl: './onboarding-page.html',
  styleUrl: './onboarding-page.scss',
})
export class OnboardingPage {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly injector = inject(Injector);
  private readonly heading = viewChild<ElementRef<HTMLElement>>('stepHeading');
  /** One key for this wizard, so retrying the same request after a timeout cannot create a duplicate. */
  private readonly key = crypto.randomUUID();
  private readonly fb = inject(NonNullableFormBuilder);

  protected readonly steps = STEPS;
  protected readonly categories = Object.entries(CATEGORY_LABELS);
  protected readonly countries = COUNTRIES;
  protected readonly timeZones = TIME_ZONES;
  protected readonly currencies = CURRENCIES;
  /** What follows the typed name: this site's own host, e.g. localhost:4201. */
  protected readonly baseHost = window.location.host;
  readonly form = this.fb.group({
    identity: this.fb.group({
      legal_name: ['', Validators.required],
      display_name: ['', Validators.required],
      category: ['school', Validators.required],
      board_affiliation_code: [''],
      udise_code: [''],
      aishe_code: [''],
    }),
    contacts: this.fb.group({
      contact_email: ['', [Validators.required, Validators.email]],
      contact_phone: ['', Validators.required],
      address: [''],
      country_code: ['IN', Validators.required],
      timezone: ['Asia/Kolkata', Validators.required],
      base_currency: ['INR', Validators.required],
    }),
    address: this.fb.group({ slug: ['', Validators.required] }),
    admin: this.fb.group({
      full_name: ['', Validators.required],
      username: ['', Validators.required],
      email: ['', Validators.email],
      mobile: [''],
      password: ['', [Validators.required, Validators.minLength(8)]],
    }),
  });

  readonly step = signal(0);
  /** Every module a plan can include, and the ones chosen: the category's defaults until the admin changes them. */
  protected readonly catalogue = signal<ModuleInfo[]>([]);
  /** The list could not be loaded: the server then gives the category's usual modules. */
  protected readonly catalogueFailed = signal(false);
  readonly modules = signal<string[]>([]);
  private modulesTouched = false;
  protected readonly busy = signal(false);
  protected readonly error = signal('');
  protected readonly serverErrors = signal<Record<string, string>>({});
  protected readonly category = toSignal(this.form.controls.identity.controls.category.valueChanges, {
    initialValue: 'school',
  });
  protected readonly isSchool = computed(() => this.category() === 'school');
  protected readonly slug = toSignal(this.form.controls.address.controls.slug.valueChanges, { initialValue: '' });
  /** The full address the slug gives, e.g. http://aster.localhost:4201, for the review step. */
  protected readonly previewUrl = computed(
    () => `${window.location.protocol}//${this.slug() || 'your-address'}.${this.baseHost}`,
  );
  protected readonly slugCheck = toSignal(
    this.form.controls.address.controls.slug.valueChanges.pipe(
      debounceTime(300),
      map((value) => value.trim().toLowerCase()),
      distinctUntilChanged(),
      switchMap((value) =>
        value
          ? this.http
              .get<SlugCheck>('/api/v1/platform/institutions/slug-check', { params: { slug: value } })
              .pipe(catchError(() => of(null)))
          : of(null),
      ),
    ),
    { initialValue: null as SlugCheck | null },
  );

  constructor() {
    const { identity, address, admin } = this.form.controls;
    this.http.get<ModuleInfo[]>('/api/v1/platform/modules').subscribe({
      next: (catalogue) => {
        this.catalogue.set(catalogue);
        this.resetModules();
      },
      error: () => this.catalogueFailed.set(true),
    });
    identity.controls.category.valueChanges.pipe(takeUntilDestroyed()).subscribe(() => this.resetModules());
    // Suggestions follow the name until the admin types their own.
    identity.controls.display_name.valueChanges.pipe(takeUntilDestroyed()).subscribe((name) => {
      if (!address.controls.slug.dirty) {
        address.controls.slug.setValue(slugify(name));
      }
    });
    address.controls.slug.valueChanges.pipe(takeUntilDestroyed()).subscribe((slug) => {
      if (!admin.controls.username.dirty && slug) {
        // Login IDs are at most 40 characters: room for ".admin" after the address.
        admin.controls.username.setValue(`${slug.slice(0, 34).replace(/-+$/, '')}.admin`);
      }
    });
  }

  chooseModules(keys: string[]): void {
    this.modulesTouched = true;
    this.modules.set(keys);
  }

  private resetModules(): void {
    if (!this.modulesTouched) {
      const category = this.form.controls.identity.controls.category.value as Category;
      this.modules.set(defaultsFor(category, this.catalogue()));
    }
  }

  protected moduleLabels(): string {
    const chosen = this.catalogue().filter((module) => this.modules().includes(module.key));
    return chosen.map((module) => module.label).join(', ') || '—';
  }

  /** The first problem with a field: the server's answer, else the form's own check once touched. */
  protected problem(group: keyof typeof this.form.controls, field: string): string {
    const path = group === 'admin' ? `admin.${field}` : field;
    const server = this.serverErrors()[path];
    if (server) {
      return server;
    }
    const control = this.form.get([group, field]);
    if (!control?.touched || !control.errors) {
      return '';
    }
    if (control.errors['required']) {
      return 'Fill this in.';
    }
    if (control.errors['email']) {
      return 'Enter an email address like office@school.example.';
    }
    if (control.errors['minlength']) {
      return 'Use at least 8 characters.';
    }
    return 'Check this.';
  }

  protected next(): void {
    const group = Object.keys(GROUP_STEP).find((name) => GROUP_STEP[name] === this.step());
    if (group) {
      const controls = this.form.get(group);
      controls?.markAllAsTouched();
      if (controls?.invalid) {
        return;
      }
      if (group === 'address' && this.slugCheck()?.available === false) {
        return;
      }
    }
    this.go(this.step() + 1);
  }

  protected back(): void {
    this.go(this.step() - 1);
  }

  protected go(step: number): void {
    this.step.set(Math.max(0, Math.min(STEPS.length - 1, step)));
    afterNextRender(() => this.heading()?.nativeElement.focus(), { injector: this.injector });
  }

  create(): void {
    if (this.busy()) {
      return;
    }
    const { identity, contacts, address, admin } = this.form.getRawValue();
    const slug = address.slug.trim().toLowerCase();
    const modules = this.catalogue().length ? { modules: this.modules() } : {};
    const body = { ...identity, ...contacts, slug, ...modules, admin };
    this.busy.set(true);
    this.error.set('');
    this.serverErrors.set({});
    this.http
      .post<InstitutionDetail>('/api/v1/platform/institutions', body, { headers: { 'Idempotency-Key': this.key } })
      .subscribe({
        next: (created) => void this.router.navigateByUrl(`/console/institutions/${created.id}`),
        error: (err) => {
          this.busy.set(false);
          const errors = fieldErrors(err);
          const fields = Object.keys(errors);
          if (fields.length) {
            this.serverErrors.set(errors);
            const group = fields[0].startsWith('admin.') ? 'admin' : FIELD_GROUP[fields[0]];
            this.go(group ? GROUP_STEP[group] : this.step());
          }
          this.error.set(apiErrorMessage(err));
        },
      });
  }

  protected value(group: keyof typeof this.form.controls, field: string): string {
    return String(this.form.get([group, field])?.value ?? '') || '—';
  }

  protected categoryLabel(): string {
    return CATEGORY_LABELS[this.category() as keyof typeof CATEGORY_LABELS];
  }
}
