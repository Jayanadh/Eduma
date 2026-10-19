import { Routes } from '@angular/router';
import { applicantOnly, guestOnly, memberOnly, platformOnly, requires, signedIn, studentOnly } from './core/guards';
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
    path: 'apply',
    title: 'Admissions',
    loadComponent: () => import('./features/apply/apply-page').then((m) => m.ApplyPage),
  },
  {
    path: 'apply/signup',
    title: 'Create an account',
    canActivate: [guestOnly],
    loadComponent: () => import('./features/apply/signup-page').then((m) => m.SignupPage),
  },
  {
    path: 'apply/applications',
    title: 'Your applications',
    canActivate: [signedIn, applicantOnly],
    loadComponent: () => import('./features/apply/applications-page').then((m) => m.ApplicationsPage),
  },
  {
    path: 'apply/applications/:id',
    title: 'Application',
    canActivate: [signedIn, applicantOnly],
    canDeactivate: [leaveGuard],
    loadComponent: () => import('./features/apply/application-form-page').then((m) => m.ApplicationFormPage),
  },
  {
    path: 'student',
    title: 'Your record',
    canActivate: [signedIn, studentOnly],
    loadComponent: () => import('./features/student/student-home').then((m) => m.StudentHome),
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
        canActivate: [requires('institution_brand.update')],
        canDeactivate: [leaveGuard],
        loadComponent: () => import('./features/app/site-page').then((m) => m.SitePage),
      },
      {
        path: 'staff',
        title: 'Staff',
        canActivate: [requires('membership.read')],
        loadComponent: () => import('./features/staff/staff-page').then((m) => m.StaffPage),
      },
      {
        path: 'staff/new',
        title: 'Add staff',
        canActivate: [requires('membership.assign')],
        canDeactivate: [leaveGuard],
        loadComponent: () => import('./features/staff/add-staff-page').then((m) => m.AddStaffPage),
      },
      {
        path: 'staff/:id',
        title: 'Staff',
        canActivate: [requires('membership.read')],
        loadComponent: () => import('./features/staff/staff-detail-page').then((m) => m.StaffDetailPage),
      },
      {
        path: 'students',
        title: 'Students',
        canActivate: [requires('student.read')],
        loadComponent: () => import('./features/students/students-page').then((m) => m.StudentsPage),
      },
      {
        path: 'students/:id',
        title: 'Student',
        canActivate: [requires('student.read')],
        canDeactivate: [leaveGuard],
        loadComponent: () => import('./features/students/student-page').then((m) => m.StudentPage),
      },
      {
        path: 'roles',
        title: 'Roles',
        canActivate: [requires('role.manage')],
        loadComponent: () => import('./features/roles/roles-page').then((m) => m.RolesPage),
      },
      {
        path: 'roles/new',
        title: 'New role',
        canActivate: [requires('role.manage')],
        loadComponent: () => import('./features/roles/role-editor-page').then((m) => m.RoleEditorPage),
      },
      {
        path: 'roles/:id',
        title: 'Change role',
        canActivate: [requires('role.manage')],
        loadComponent: () => import('./features/roles/role-editor-page').then((m) => m.RoleEditorPage),
      },
      {
        path: 'settings',
        title: 'Settings',
        canActivate: [requires(['configuration.edit', 'configuration.publish'])],
        loadComponent: () => import('./features/settings/settings-page').then((m) => m.SettingsPage),
      },
      {
        path: 'settings/:key',
        title: 'Settings',
        canActivate: [requires(['configuration.edit', 'configuration.publish'])],
        canDeactivate: [leaveGuard],
        loadComponent: () => import('./features/settings/setting-editor-page').then((m) => m.SettingEditorPage),
      },
      {
        path: 'admissions/cycles',
        title: 'Admission cycles',
        canActivate: [requires(['admission_cycle.manage', 'application.review', 'admission.approve'])],
        loadComponent: () => import('./features/admissions/cycles-page').then((m) => m.CyclesPage),
      },
      {
        path: 'admissions/cycles/new',
        title: 'New cycle',
        canActivate: [requires('admission_cycle.manage')],
        canDeactivate: [leaveGuard],
        loadComponent: () => import('./features/admissions/cycle-editor-page').then((m) => m.CycleEditorPage),
      },
      {
        path: 'admissions/cycles/:id',
        title: 'Admission cycle',
        canActivate: [requires(['admission_cycle.manage', 'application.review', 'admission.approve'])],
        canDeactivate: [leaveGuard],
        loadComponent: () => import('./features/admissions/cycle-editor-page').then((m) => m.CycleEditorPage),
      },
      {
        path: 'admissions/applications',
        title: 'Applications',
        canActivate: [requires(['application.review', 'admission.approve'])],
        loadComponent: () => import('./features/admissions/applications-page').then((m) => m.StaffApplicationsPage),
      },
      {
        path: 'admissions/applications/:id',
        title: 'Application',
        canActivate: [requires(['application.review', 'admission.approve'])],
        loadComponent: () => import('./features/admissions/application-review-page').then((m) => m.ApplicationReviewPage),
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
