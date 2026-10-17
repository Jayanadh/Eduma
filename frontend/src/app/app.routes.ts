import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '**',
    title: 'Not found',
    data: { kind: 'not-found' },
    loadComponent: () => import('./features/public/notice-page').then((m) => m.NoticePage),
  },
];
