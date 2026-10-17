import { afterNextRender, Component, computed, ElementRef, inject, Injector, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { AuthStore } from '../core/auth-store';
import { SiteStore } from '../core/site-store';
import { ConfirmDialog } from '../ui/confirm-dialog';
import { Icon } from '../ui/icon';
import { navFor } from './nav';

/**
 * The signed-in frame for the console (Eduma's address) and an institution's workspace (its own address): a left
 * sidebar with the site's logo and pages; below 900 px a top bar whose menu button opens the sidebar as a drawer.
 */
@Component({
  selector: 'app-shell',
  imports: [Icon, RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './shell.html',
  styleUrl: './shell.scss',
  host: {
    '(document:keydown.escape)': 'closeDrawer(true)',
    '(window:focus)': 'recheckSession()',
    '(document:visibilitychange)': 'recheckSession()',
  },
})
export class Shell {
  private readonly auth = inject(AuthStore);
  private readonly confirm = inject(ConfirmDialog);
  private readonly injector = inject(Injector);
  private readonly drawer = viewChild<ElementRef<HTMLElement>>('drawer');
  private readonly menuButton = viewChild<ElementRef<HTMLButtonElement>>('menuButton');
  protected readonly site = inject(SiteStore);

  protected readonly user = this.auth.user;
  protected readonly home = this.auth.home;
  protected readonly isInstitution = computed(() => this.site.kind() === 'institution');
  /** No menu until a first password has been replaced: nothing else can open before then. */
  protected readonly items = computed(() =>
    this.user()?.must_change_password ? [] : navFor(this.isInstitution() ? 'institution' : 'platform'),
  );
  protected readonly roleLabel = computed(() => (this.auth.isPlatformAdmin() ? 'Eduma platform admin' : 'Institution Admin'));
  protected readonly initials = computed(() =>
    (this.user()?.full_name ?? '')
      .split(' ')
      .filter((part) => part.length > 1)
      .slice(0, 2)
      .map((part) => part[0].toUpperCase())
      .join(''),
  );
  protected readonly drawerOpen = signal(false);

  constructor() {
    inject(Router)
      .events.pipe(
        filter((event) => event instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe(() => this.drawerOpen.set(false));
  }

  protected openDrawer(): void {
    this.drawerOpen.set(true);
    afterNextRender(() => this.drawer()?.nativeElement.focus(), { injector: this.injector });
  }

  protected closeDrawer(restoreFocus = false): void {
    if (!this.drawerOpen()) {
      return;
    }
    this.drawerOpen.set(false);
    if (restoreFocus) {
      afterNextRender(() => this.menuButton()?.nativeElement.focus(), { injector: this.injector });
    }
  }

  protected recheckSession(): void {
    if (document.visibilityState !== 'hidden') {
      void this.auth.recheckSession();
    }
  }

  protected async signOut(): Promise<void> {
    const yes = await this.confirm.ask({
      title: 'Sign out?',
      message: 'You will need your login ID and password to come back in.',
      confirmLabel: 'Sign out',
    });
    if (yes) {
      this.auth.signOut();
    }
  }
}
