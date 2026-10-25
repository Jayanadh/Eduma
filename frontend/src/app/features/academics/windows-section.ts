import { Component, computed, inject, signal } from '@angular/core';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
import { AcademicYear, RegistrationWindow } from '../../core/api/types';
import { date } from '../../core/format';
import { load } from '../../core/load';
import { ToastService } from '../../ui/toast';

/** Each term's registration window (S5C-01): when students register, the drop deadline and the credit limit. */
@Component({
  selector: 'app-windows-section',
  template: `
    <section class="card stack section">
      <h2 class="card-title">Registration windows</h2>
      <ul class="rows">
        @for (w of windows.value() ?? []; track w.id) {
          <li>
            <span><strong>{{ w.year }} {{ w.term }}</strong> <span class="muted small meta">{{ date(w.opens_on) }} to {{ date(w.closes_on) }} · drop until {{ date(w.drop_until) }} · {{ w.max_credits }} credits{{ w.needs_approval ? ' · adviser approval' : '' }}</span></span>
            <span class="badge" [class.badge-success]="w.open">{{ w.open ? 'Open' : 'Closed' }}</span>
          </li>
        } @empty {
          <li class="muted small">No term has a registration window yet.</li>
        }
      </ul>
      @if (free().length) {
        <form id="add-window" class="add" (submit)="$event.preventDefault(); add($any($event.target))">
          <div class="field">
            <label for="window-term">Term</label>
            <select id="window-term">
              @for (t of free(); track t.id) { <option [value]="t.id">{{ t.label }}</option> }
            </select>
          </div>
          <div class="field"><label for="window-opens">Opens</label><input id="window-opens" type="date" /></div>
          <div class="field">
            <label for="window-closes">Closes</label><input id="window-closes" type="date" />
            @if (errors()['closes_on']; as m) { <span class="field-error">{{ m }}</span> }
          </div>
          <div class="field">
            <label for="window-drop">Drop until</label><input id="window-drop" type="date" />
            @if (errors()['drop_until']; as m) { <span class="field-error">{{ m }}</span> }
          </div>
          <div class="field"><label for="window-credits">Credit limit</label><input id="window-credits" type="number" min="0" step="0.5" value="24" /></div>
          <label class="small"><input id="window-approval" type="checkbox" /> Adviser approves</label>
          <button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Open window</button>
        </form>
      }
    </section>
  `,
  styles: `
    .add {
      display: grid;
      gap: 12px;
      align-items: end;

      @media (min-width: 900px) {
        grid-template-columns: repeat(6, minmax(0, 1fr)) auto;
      }
    }
  `,
})
export class WindowsSection {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly date = date;
  protected readonly windows = load(() => this.api.get<RegistrationWindow[]>('institution/academics/windows'));
  protected readonly years = load(() => this.api.get<AcademicYear[]>('institution/academics/years'));
  /** Terms of open years that have no window yet. */
  protected readonly free = computed(() => {
    const taken = new Set((this.windows.value() ?? []).map((w) => w.term_id));
    return (this.years.value() ?? [])
      .filter((y) => y.status !== 'closed')
      .flatMap((y) => y.terms.map((t) => ({ id: t.id, label: `${y.code} ${t.name}` })))
      .filter((t) => !taken.has(t.id));
  });
  protected readonly busy = signal(false);
  protected readonly errors = signal<Record<string, string>>({});

  protected add(form: HTMLFormElement): void {
    const field = (id: string) => form.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)!.value;
    const body = {
      term: field('window-term'),
      opens_on: field('window-opens'),
      closes_on: field('window-closes'),
      drop_until: field('window-drop'),
      max_credits: field('window-credits'),
      needs_approval: form.querySelector<HTMLInputElement>('#window-approval')!.checked,
    };
    this.busy.set(true);
    this.errors.set({});
    this.api.post<RegistrationWindow>('institution/academics/windows', body).subscribe({
      next: (made) => {
        this.busy.set(false);
        this.toasts.show(`Registration for ${made.term} set up.`);
        this.windows.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.errors.set(fieldErrors(err));
        if (!Object.keys(fieldErrors(err)).length) {
          this.toasts.show(apiErrorMessage(err), 'danger');
        }
      },
    });
  }
}
