import { Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { NavigationHistory } from './core/navigation-history';
import { ConfirmHost } from './ui/confirm-dialog';
import { ToastHost } from './ui/toast';

@Component({
  imports: [ConfirmHost, RouterOutlet, ToastHost],
  selector: 'app-root',
  template: `<router-outlet /><app-confirm-host /><app-toast-host />`,
})
export class App {
  // Started with the app, so Back buttons know every page visited in this tab.
  private readonly history = inject(NavigationHistory);
}
