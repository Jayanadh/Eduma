import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { SEARCH_DELAY_MS, SearchBox } from './search-box';

const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

describe('SearchBox', () => {
  async function render() {
    TestBed.configureTestingModule({ imports: [SearchBox] });
    const fixture = TestBed.createComponent(SearchBox);
    const searched: string[] = [];
    fixture.componentInstance.search.subscribe((text) => searched.push(text));
    await fixture.whenStable();
    const input = fixture.nativeElement.querySelector('input') as HTMLInputElement;
    const type = (value: string) => {
      input.value = value;
      input.dispatchEvent(new Event('input'));
    };
    return { fixture, searched, type };
  }

  it('waits for three letters, then searches after a short pause', async () => {
    const { fixture, searched, type } = await render();
    type('ab');
    await pause(SEARCH_DELAY_MS + 50);
    await fixture.whenStable();
    expect(searched).toEqual([]);
    expect(fixture.nativeElement.textContent).toContain('Type 1 more to search');
    type('abc');
    expect(searched).toEqual([]); // not on the key itself
    await pause(SEARCH_DELAY_MS + 50);
    expect(searched).toEqual(['abc']);
  });

  it('searches once for quick typing, and again when emptied', async () => {
    const { searched, type } = await render();
    type('kav');
    type('kava');
    type('kaval');
    await pause(SEARCH_DELAY_MS + 50);
    expect(searched).toEqual(['kaval']);
    type('');
    await pause(SEARCH_DELAY_MS + 50);
    expect(searched).toEqual(['kaval', '']);
  });

  it('leaves the id to the input, so its label focuses it', async () => {
    @Component({ imports: [SearchBox], template: '<app-search-box id="people-search" label="Search people" />' })
    class Host {}
    const fixture = TestBed.createComponent(Host);
    await fixture.whenStable();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelectorAll('#people-search').length).toBe(1);
    expect(root.querySelector('#people-search')?.tagName).toBe('INPUT');
  });
});
