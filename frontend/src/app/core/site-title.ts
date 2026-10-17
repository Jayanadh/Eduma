import { inject, Injectable } from '@angular/core';
import { Title } from '@angular/platform-browser';
import { RouterStateSnapshot, TitleStrategy } from '@angular/router';
import { SiteStore } from './site-store';

export function siteTitle(page: string | undefined, site: string): string {
  return page ? `${page} · ${site}` : site;
}

/** Browser tab titles name the page and the site it belongs to: "Sign in · Aster School". */
@Injectable()
export class SiteTitleStrategy extends TitleStrategy {
  private readonly title = inject(Title);
  private readonly site = inject(SiteStore);

  override updateTitle(snapshot: RouterStateSnapshot): void {
    this.title.setTitle(siteTitle(this.buildTitle(snapshot), this.site.institutionName()));
  }
}
