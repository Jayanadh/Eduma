import { Route } from '@angular/router';
import { leaveGuard } from './core/unsaved-changes';
import { routes } from './app.routes';

function child(path: string): Route {
  const app = routes.find((route) => route.path === 'app')!;
  return app.children!.find((route) => route.path === path)!;
}

describe('workspace routes', () => {
  it('checks the permission on every page the menu hides', () => {
    for (const path of ['site', 'staff', 'staff/new', 'staff/:id', 'roles', 'roles/new', 'roles/:id', 'organization']) {
      expect(child(path).canActivate?.length, path).toBe(1);
    }
  });

  it('asks before leaving forms that can hold unsaved typing', () => {
    for (const path of ['site', 'staff/new']) {
      expect(child(path).canDeactivate, path).toContain(leaveGuard);
    }
  });
});
