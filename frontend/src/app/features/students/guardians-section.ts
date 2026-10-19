import { Component, inject, input, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
import { GuardianLink, StudentRecord } from '../../core/api/types';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { ConfirmDialog } from '../../ui/confirm-dialog';
import { LoadError } from '../../ui/load-error';
import { Reveal } from '../../ui/reveal';
import { ToastService } from '../../ui/toast';

const BASES: [string, string][] = [
  ['parent', 'Parent'],
  ['legal_guardian', 'Legal guardian'],
  ['court_order', 'Court order'],
  ['student_consent', "The student's own consent"],
  ['other', 'Other'],
];
const METHODS: [string, string][] = [
  ['documents_in_person', 'Documents seen in person'],
  ['documents_on_file', 'Documents on file'],
  ['court_order', 'Court order'],
  ['other', 'Other'],
];

/**
 * Which adults may see this student, decided on the record (slice 4b). A link proposed at enrollment or here grants
 * nothing until someone with guardian_link.manage checks the adult's authority and verifies it.
 */
@Component({
  selector: 'app-guardians-section',
  imports: [LoadError, ReactiveFormsModule, Reveal],
  templateUrl: './guardians-section.html',
  styleUrl: './guardians-section.scss',
})
export class GuardiansSection {
  readonly student = input.required<StudentRecord>();
  private readonly api = inject(Api);
  private readonly confirm = inject(ConfirmDialog);
  private readonly toasts = inject(ToastService);
  private readonly fb = inject(NonNullableFormBuilder);
  protected readonly bases = BASES;
  protected readonly methods = METHODS;
  protected readonly date = date;

  protected readonly links = load(
    () => this.api.get<GuardianLink[]>(`${this.base()}`),
    () => this.student().id,
  );
  protected readonly verifying = signal<string | null>(null);
  protected readonly adding = signal(false);
  protected readonly busy = signal(false);
  protected readonly errors = signal<Record<string, string>>({});

  protected readonly addForm = this.fb.group({
    full_name: ['', Validators.required],
    relationship: ['', Validators.required],
    phone: [''],
    email: [''],
  });
  protected readonly verifyForm = this.fb.group({
    authority_basis: ['parent'],
    verification_method: ['documents_in_person'],
    verification_reference: [''],
    starts_on: [''],
    ends_on: [''],
    record: [true],
    fees: [false],
    messages: [false],
    restrictions: [''],
    login: [false],
    username: [''],
    password: [''],
  });

  private base(): string {
    return `institution/students/${this.student().id}/guardians`;
  }

  protected access(link: GuardianLink): string {
    const shared = [link.access.record && 'record', link.access.fees && 'fees', link.access.messages && 'messages'];
    const list = shared.filter(Boolean).join(', ');
    return list ? `Sees: ${list}` : 'Nothing shared';
  }

  protected openVerify(link: GuardianLink): void {
    this.verifyForm.reset();
    this.errors.set({});
    this.verifying.set(link.id);
  }

  private done(message: string): void {
    this.busy.set(false);
    this.verifying.set(null);
    this.adding.set(false);
    this.links.reload();
    this.toasts.show(message);
  }

  private failed(err: unknown): void {
    this.busy.set(false);
    const fields = fieldErrors(err);
    this.errors.set(fields);
    if (!Object.keys(fields).length) {
      this.toasts.show(apiErrorMessage(err), 'danger');
      this.links.reload();
    }
  }

  protected add(): void {
    const value = this.addForm.getRawValue();
    this.busy.set(true);
    this.errors.set({});
    const adult = { full_name: value.full_name, phone: value.phone, email: value.email };
    this.api.post<GuardianLink>(this.base(), { adult, relationship: value.relationship }).subscribe({
      next: () => {
        this.addForm.reset();
        this.done('Guardian added. Verify them once you have checked who they are.');
      },
      error: (err) => this.failed(err),
    });
  }

  protected verify(link: GuardianLink): void {
    const v = this.verifyForm.getRawValue();
    this.busy.set(true);
    this.errors.set({});
    const body = {
      version: link.version,
      authority_basis: v.authority_basis,
      verification_method: v.verification_method,
      verification_reference: v.verification_reference,
      starts_on: v.starts_on || null,
      ends_on: v.ends_on || null,
      access: { record: v.record, fees: v.fees, messages: v.messages },
      restrictions: v.restrictions,
      login: v.login && !link.has_login ? { username: v.username, password: v.password } : null,
    };
    this.api.post<GuardianLink>(`${this.base()}/${link.id}/verify`, body).subscribe({
      next: () => this.done(`${link.adult.full_name} verified.`),
      error: (err) => this.failed(err),
    });
  }

  protected async revoke(link: GuardianLink): Promise<void> {
    const reason = await this.confirm.prompt({
      title: `Revoke ${link.adult.full_name}'s link?`,
      message: 'They stop seeing this student straight away. To restore it later, add and verify them again.',
      label: 'Why?',
      type: 'textarea',
      required: true,
      confirmLabel: 'Revoke',
    });
    if (reason === null) {
      return;
    }
    this.busy.set(true);
    this.api.post<GuardianLink>(`${this.base()}/${link.id}/revoke`, { version: link.version, reason }).subscribe({
      next: () => this.done('Link revoked.'),
      error: (err) => this.failed(err),
    });
  }
}
