import { Location } from '@angular/common';
import { inject, Service } from '@angular/core';
import { NavigationEnd, NavigationStart, Router } from '@angular/router';

/**
 * Remembers the pages visited in this tab, so a Back button returns to the page the person came from (like the
 * browser's back) and, when the page was opened directly (a link, a bookmark, a refresh), to its parent page instead
 * of leaving the app.
 */
@Service()
export class NavigationHistory {
  private readonly router = inject(Router);
  private readonly location = inject(Location);
  private readonly visited: string[] = [];
  private poppedBack = false;

  constructor() {
    this.router.events.subscribe((event) => {
      if (event instanceof NavigationStart) {
        this.poppedBack = event.navigationTrigger === 'popstate';
      } else if (event instanceof NavigationEnd) {
        if (this.poppedBack && this.visited.length > 1) {
          this.visited.pop();
        } else if (this.visited.at(-1) !== event.urlAfterRedirects) {
          this.visited.push(event.urlAfterRedirects);
        }
      }
    });
  }

  /** True when there is an earlier page of this app to go back to. */
  canGoBack(): boolean {
    return this.visited.length > 1;
  }

  back(fallback: string): void {
    if (this.canGoBack()) {
      this.location.back();
    } else {
      void this.router.navigateByUrl(fallback);
    }
  }
}
