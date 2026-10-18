import { Routes } from '@angular/router';
import { guestOnly, memberOnly, platformOnly, requires, signedIn } from './core/guards';
import { leaveGuard } from './core/unsaved-changes';

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    loadComponent: () => import('./features/public/landing-page').then((m) => m.LandingPage),
  },
  {
    path: 'login',
    title: 'Sign in',
    canActivate: [guestOnly],
    loadComponent: () => import('./features/auth/login-page').then((m) => m.LoginPage),
  },
  {
    path: 'change-password',
    title: 'Change password',
    canActivate: [signedIn],
    loadComponent: () =>
      import('./features/auth/change-password-page').then((m) => m.ChangePasswordPage),
  },
  {
    path: 'console',
    loadComponent: () => import('./layout/shell').then((m) => m.Shell),
    // canActivateChild, not canActivate: it must run on every navigation inside the shell.
    canActivateChild: [signedIn, platformOnly],
    children: [
      {
        path: '',
        title: 'Overview',
        loadComponent: () => import('./features/console/overview-page').then((m) => m.OverviewPage),
      },
      {
        path: 'institutions',
        title: 'Institutions',
        loadComponent: () =>
          import('./features/console/institutions-page').then((m) => m.InstitutionsPage),
      },
      {
        path: 'institutions/new',
        title: 'Add institution',
        loadComponent: () =>
          import('./features/console/onboarding-page').then((m) => m.OnboardingPage),
      },
      {
        path: 'institutions/:id',
        title: 'Institution',
        canDeactivate: [leaveGuard],
        loadComponent: () =>
          import('./features/console/institution-page').then((m) => m.InstitutionPage),
      },
      {
        path: 'audit',
        title: 'Audit log',
        loadComponent: () => import('./features/console/audit-page').then((m) => m.AuditPage),
      },
    ],
  },
  {
    path: 'app',
    loadComponent: () => import('./layout/shell').then((m) => m.Shell),
    canActivateChild: [signedIn, memberOnly],
    children: [
      {
        path: '',
        title: 'Home',
        loadComponent: () => import('./features/app/home-page').then((m) => m.HomePage),
      },
      {
        path: 'site',
        title: 'Public site',
        canDeactivate: [leaveGuard],
        loadComponent: () => import('./features/app/site-page').then((m) => m.SitePage),
      },
      {
        path: 'organization',
        title: 'Organization',
        canActivate: [requires('organization.manage')],
        loadComponent: () => import('./features/org/organization-page').then((m) => m.OrganizationPage),
      },
      {
        path: 'profile',
        title: 'Profile',
        loadComponent: () => import('./features/app/profile-page').then((m) => m.ProfilePage),
      },
    ],
  },
  {
    path: '**',
    title: 'Not found',
    data: { kind: 'not-found' },
    loadComponent: () => import('./features/public/notice-page').then((m) => m.NoticePage),
  },
];
