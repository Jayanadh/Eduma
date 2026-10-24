import { Component, inject, signal } from '@angular/core';
import { Api } from '../../core/api/api';
import { apiErrorMessage, fieldErrors } from '../../core/api-error';
import { Band, SchemeT } from '../../core/api/types';
import { load } from '../../core/load';
import { LoadError } from '../../ui/load-error';
import { PageHeader } from '../../ui/page-header';
import { ToastService } from '../../ui/toast';

type Row = { name: string; max_marks: string; weight: string; min_percent: string };

/** Assessment schemes (S7-01): components with maximum and weight, pass rules and grade bands; published ones never change. */
@Component({
  selector: 'app-schemes-page',
  imports: [LoadError, PageHeader],
  template: `
    <div class="page">
      <app-page-header eyebrow="Results" title="Assessment schemes" subtitle="How marks become a total, a pass and a grade. A published scheme never changes; revise it instead." />
      <app-load-error [message]="data.error()" (retry)="data.reload()" />
      @for (s of data.value() ?? []; track s.id) {
        <section class="card stack section">
          <h2 class="card-title">{{ s.name }} <span class="muted small">rev {{ s.revision }} · {{ s.status }}</span></h2>
          <p class="small">
            @for (c of s.components; track c.id) { <span class="part">{{ c.name }} {{ c.max_marks }} marks → {{ c.weight }}%{{ c.min_percent ? ' (min ' + c.min_percent + '%)' : '' }}</span> }
          </p>
          <p class="muted small">Pass {{ s.pass_percent }}% · grades @for (b of s.bands; track $index) { {{ b.grade }}≥{{ b.min }} ({{ b.point }}) }</p>
          <div class="actions">
            @if (s.status === 'draft') { <button type="button" class="btn btn-primary btn-sm" [disabled]="busy()" (click)="publish(s)">Publish</button> }
            @if (s.status === 'published') { <button type="button" class="btn btn-secondary btn-sm" [disabled]="busy()" (click)="revise(s)">New revision</button> }
          </div>
        </section>
      }
      <form id="add-scheme" class="card stack section" (submit)="$event.preventDefault(); add($any($event.target))">
        <h2 class="card-title">New scheme</h2>
        <div class="row">
          <div class="field grow"><label for="scheme-name">Name</label><input id="scheme-name" placeholder="Theory 40/60" /></div>
          <div class="field"><label for="scheme-pass">Pass %</label><input id="scheme-pass" type="number" value="40" /></div>
        </div>
        <h3 class="small">Components</h3>
        @for (r of rows(); track $index; let i = $index) {
          <div class="row">
            <div class="field grow"><label [for]="'comp-name-' + i">Name</label><input [id]="'comp-name-' + i" [value]="r.name" (input)="setRow(i, 'name', $any($event.target).value)" /></div>
            <div class="field"><label [for]="'comp-max-' + i">Maximum</label><input [id]="'comp-max-' + i" type="number" [value]="r.max_marks" (input)="setRow(i, 'max_marks', $any($event.target).value)" /></div>
            <div class="field"><label [for]="'comp-weight-' + i">Weight %</label><input [id]="'comp-weight-' + i" type="number" [value]="r.weight" (input)="setRow(i, 'weight', $any($event.target).value)" /></div>
            <div class="field"><label [for]="'comp-min-' + i">Minimum %</label><input [id]="'comp-min-' + i" type="number" [value]="r.min_percent" (input)="setRow(i, 'min_percent', $any($event.target).value)" /></div>
          </div>
        }
        <div><button type="button" class="btn btn-secondary btn-sm" (click)="rows.update((all) => [...all, { name: '', max_marks: '', weight: '', min_percent: '' }])">Add a component</button></div>
        @if (errors()['components']; as m) { <span class="field-error">{{ m }}</span> }
        <p class="muted small">Grade bands: O ≥90 (10), A ≥75 (8), B ≥60 (7), C ≥40 (5), F below (0) — change them by revising later.</p>
        <div><button type="submit" class="btn btn-primary btn-sm" [disabled]="busy()">Save draft</button></div>
      </form>
    </div>
  `,
  styles: `
    .row,
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: end;
    }

    .grow {
      flex: 1 1 160px;
    }

    .part + .part::before {
      content: ' · ';
    }
  `,
})
export class SchemesPage {
  private readonly api = inject(Api);
  private readonly toasts = inject(ToastService);
  protected readonly data = load(() => this.api.get<SchemeT[]>('institution/results/schemes'));
  protected readonly rows = signal<Row[]>([
    { name: 'Internal', max_marks: '40', weight: '40', min_percent: '' },
    { name: 'Final', max_marks: '60', weight: '60', min_percent: '40' },
  ]);
  protected readonly busy = signal(false);
  protected readonly errors = signal<Record<string, string>>({});
  private readonly bands: Band[] = [
    { min: '90', grade: 'O', point: '10' },
    { min: '75', grade: 'A', point: '8' },
    { min: '60', grade: 'B', point: '7' },
    { min: '40', grade: 'C', point: '5' },
    { min: '0', grade: 'F', point: '0' },
  ];

  protected setRow(i: number, key: keyof Row, value: string): void {
    this.rows.update((all) => all.map((r, j) => (j === i ? { ...r, [key]: value } : r)));
  }

  private run(request: ReturnType<Api['post']>, message: string): void {
    this.busy.set(true);
    this.errors.set({});
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.toasts.show(message);
        this.data.reload();
      },
      error: (err) => {
        this.busy.set(false);
        this.errors.set(fieldErrors(err));
        this.toasts.show(apiErrorMessage(err), 'danger');
      },
    });
  }

  protected add(form: HTMLFormElement): void {
    const body = {
      name: form.querySelector<HTMLInputElement>('#scheme-name')!.value.trim(),
      pass_percent: form.querySelector<HTMLInputElement>('#scheme-pass')!.value,
      bands: this.bands,
      components: this.rows()
        .filter((r) => r.name.trim())
        .map((r) => ({ name: r.name.trim(), max_marks: r.max_marks, weight: r.weight, min_percent: r.min_percent || null })),
    };
    this.run(this.api.post('institution/results/schemes', body), 'Scheme saved as a draft.');
  }

  protected publish(s: SchemeT): void {
    this.run(this.api.post(`institution/results/schemes/${s.id}/publish`, { version: s.version }), `${s.name} published.`);
  }

  protected revise(s: SchemeT): void {
    this.run(this.api.post(`institution/results/schemes/${s.id}/revise`, {}), `Revision drafted.`);
  }
}
