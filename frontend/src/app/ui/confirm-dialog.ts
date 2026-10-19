import {
  afterNextRender,
  Component,
  effect,
  ElementRef,
  inject,
  Injector,
  Service,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Reveal } from './reveal';

/** A question to confirm before something happens, such as a download or logging out. */
export type ConfirmRequest = {
  title: string;
  message?: string;
  confirmLabel: string;
  cancelLabel?: string;
  /** "danger" for an action that cannot be undone: the dialog then starts on Cancel. */
  tone?: 'primary' | 'danger' | 'dark';
};

/** A question that also needs a short answer typed in: a reason, a date. */
export type PromptRequest = ConfirmRequest & {
  label: string;
  type?: 'text' | 'date' | 'textarea' | 'password';
  value?: string;
  min?: string;
  max?: string;
  /** Leave false to allow an empty answer. */
  required?: boolean;
  hint?: string;
};

type OpenQuestion = (ConfirmRequest & Partial<PromptRequest>) & {
  prompt: boolean;
  answer: (yes: boolean, value?: string) => void;
};

/** Asks the person to confirm, or for a short answer. One question at a time; the app root shows it. */
@Service()
export class ConfirmDialog {
  private readonly current = signal<OpenQuestion | null>(null);
  readonly open = this.current.asReadonly();

  /** Resolves true once confirmed; false on Cancel, Escape, a click outside, or a newer question. */
  ask(request: ConfirmRequest): Promise<boolean> {
    return this.show(request, false).then((answer) => answer !== null);
  }

  /** Resolves with the typed answer once confirmed, or null when cancelled. */
  prompt(request: PromptRequest): Promise<string | null> {
    return this.show(request, true);
  }

  /** Asks for a new first password for someone else's login; null when cancelled. */
  firstPassword(
    title: string,
    message = 'Their old password stops working. Hand the new one over in person; they must change it at the next sign-in.',
    confirmLabel = 'Set password',
  ): Promise<string | null> {
    return this.prompt({
      title,
      message,
      label: 'New first password',
      type: 'password',
      hint: 'At least 8 characters, not all numbers.',
      confirmLabel,
    });
  }

  private show(request: ConfirmRequest | PromptRequest, prompt: boolean): Promise<string | null> {
    this.current()?.answer(false);
    return new Promise((resolve) => {
      const question: OpenQuestion = {
        ...request,
        prompt,
        answer: (yes, value) => {
          if (this.current() === question) {
            this.current.set(null);
          }
          resolve(yes ? (value ?? '') : null);
        },
      };
      this.current.set(question);
    });
  }
}

/** Shows the open question of ConfirmDialog, centred over the page. Place once in the app root. */
@Component({
  selector: 'app-confirm-host',
  imports: [FormsModule, Reveal],
  template: `
    @if (dialog.open(); as question) {
      <div class="confirm-backdrop" (click)="question.answer(false)"></div>
      <form
        #box
        class="confirm"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        [attr.aria-describedby]="question.message ? 'confirm-message' : null"
        (keydown)="keydown($event, question)"
        (ngSubmit)="submit(question)"
      >
        <h2 id="confirm-title">{{ question.title }}</h2>
        @if (question.message) {
          <p id="confirm-message">{{ question.message }}</p>
        }
        @if (question.prompt) {
          <div class="field answer">
            <label for="confirm-answer">{{ question.label }}</label>
            @if (question.type === 'textarea') {
              <textarea
                #answerField
                id="confirm-answer"
                name="answer"
                rows="3"
                [(ngModel)]="value"
              ></textarea>
            } @else {
              <div [class.password-field]="question.type === 'password'">
                <input
                  #answerField
                  id="confirm-answer"
                  name="answer"
                  [type]="question.type ?? 'text'"
                  [attr.autocomplete]="question.type === 'password' ? 'new-password' : 'off'"
                  [attr.min]="question.min ?? null"
                  [attr.max]="question.max ?? null"
                  [(ngModel)]="value"
                />
                @if (question.type === 'password') {
                  <app-reveal [for]="answerField" />
                }
              </div>
            }
            @if (question.hint) {
              <span class="field-hint">{{ question.hint }}</span>
            }
            @if (missing()) {
              <span class="error small">Fill this in to continue.</span>
            }
          </div>
        }
        <div class="confirm-actions">
          <button
            #cancelButton
            type="button"
            class="btn btn-secondary"
            (click)="question.answer(false)"
          >
            {{ question.cancelLabel ?? 'Cancel' }}
          </button>
          <button #confirmButton type="submit" [class]="'btn btn-' + (question.tone ?? 'dark')">
            {{ question.confirmLabel }}
          </button>
        </div>
      </form>
    }
  `,
  styles: `
    .confirm-backdrop {
      position: fixed;
      inset: 0;
      z-index: 85;
      background: rgba(20, 20, 20, 0.45);
    }

    .confirm {
      position: fixed;
      top: 50%;
      left: 50%;
      z-index: 90;
      width: min(440px, calc(100% - 32px));
      padding: 26px;
      border-radius: var(--radius-lg);
      background: var(--surface);
      box-shadow: var(--shadow-float);
      transform: translate(-50%, -50%);

      h2 {
        margin: 0 0 8px;
        font-size: 20px;
      }

      p {
        margin: 0;
        color: var(--muted);
        overflow-wrap: anywhere;
      }
    }

    .answer {
      margin-top: 16px;
    }

    .confirm-actions {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 10px;
      margin-top: 22px;
    }
  `,
})
export class ConfirmHost {
  protected readonly dialog = inject(ConfirmDialog);
  private readonly injector = inject(Injector);
  private readonly box = viewChild<ElementRef<HTMLElement>>('box');
  private readonly cancelButton = viewChild<ElementRef<HTMLButtonElement>>('cancelButton');
  private readonly confirmButton = viewChild<ElementRef<HTMLButtonElement>>('confirmButton');
  private readonly answerField = viewChild<ElementRef<HTMLInputElement>>('answerField');
  protected value = '';
  protected readonly missing = signal(false);
  /** What had focus before the question, to give it back after. */
  private returnTo: HTMLElement | null = null;

  constructor() {
    effect(() => {
      const question = this.dialog.open();
      untracked(() => {
        if (question) {
          this.value = question.value ?? '';
          this.missing.set(false);
          this.returnTo ??= document.activeElement as HTMLElement | null;
          const start = question.prompt
            ? this.answerField
            : question.tone === 'danger'
              ? this.cancelButton
              : this.confirmButton;
          afterNextRender(() => start()?.nativeElement.focus(), { injector: this.injector });
        } else if (this.returnTo) {
          const target = this.returnTo;
          this.returnTo = null;
          afterNextRender(() => target.focus?.(), { injector: this.injector });
        }
      });
    });
  }

  protected submit(question: OpenQuestion): void {
    if (question.prompt && question.required !== false && !this.value.trim()) {
      this.missing.set(true);
      return;
    }
    question.answer(true, question.type === 'password' ? this.value : this.value.trim());
  }

  protected keydown(event: KeyboardEvent, question: OpenQuestion): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      question.answer(false);
    } else if (event.key === 'Tab') {
      // Focus stays inside the dialog.
      const focusable = Array.from(
        this.box()?.nativeElement.querySelectorAll<HTMLElement>('button, input, textarea') ?? [],
      );
      const at = focusable.indexOf(document.activeElement as HTMLElement);
      const next = (at + (event.shiftKey ? -1 : 1) + focusable.length) % focusable.length;
      event.preventDefault();
      focusable[next]?.focus();
    }
  }
}
