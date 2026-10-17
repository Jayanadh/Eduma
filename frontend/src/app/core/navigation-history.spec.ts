import { Location } from '@angular/common';
import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { NavigationHistory } from './navigation-history';

@Component({ template: '' })
class Blank {}

describe('NavigationHistory', () => {
  let router: Router;
  let history: NavigationHistory;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideRouter([{ path: '**', component: Blank }])],
    });
    history = TestBed.inject(NavigationHistory);
    router = TestBed.inject(Router);
  });

  it('goes to the parent page when the page was opened directly', async () => {
    await router.navigateByUrl('/dsp/reports/5');
    const navigate = vi.spyOn(router, 'navigateByUrl');
    history.back('/dsp/reports');
    expect(navigate).toHaveBeenCalledWith('/dsp/reports');
  });

  it('goes back to the page the person came from', async () => {
    await router.navigateByUrl('/dsp');
    await router.navigateByUrl('/dsp/reports/5');
    const back = vi.spyOn(TestBed.inject(Location), 'back');
    const navigate = vi.spyOn(router, 'navigateByUrl');
    expect(history.canGoBack()).toBe(true);
    history.back('/dsp/reports');
    expect(back).toHaveBeenCalled();
    expect(navigate).not.toHaveBeenCalled();
  });
});
