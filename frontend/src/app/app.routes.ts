import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    loadComponent: () => import('./features/public/landing-page').then((m) => m.LandingPage),
  },
  {
    path: '**',
    title: 'Not found',
    data: { kind: 'not-found' },
    loadComponent: () => import('./features/public/notice-page').then((m) => m.NoticePage),
  },
];
