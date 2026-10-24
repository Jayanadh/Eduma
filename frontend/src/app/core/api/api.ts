import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Service } from '@angular/core';
import { Observable } from 'rxjs';

/** Query values; empty ones are left out. */
export type Query = Record<string, string | number | boolean | null | undefined>;

export function params(query: Query = {}): HttpParams {
  let result = new HttpParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== null && value !== undefined && value !== '') {
      result = result.set(key, String(value));
    }
  }
  return result;
}

/** A thin, typed wrapper over HttpClient for the /api/v1/ endpoints. */
@Service()
export class Api {
  private readonly http = inject(HttpClient);

  get<T>(path: string, query?: Query): Observable<T> {
    return this.http.get<T>(`/api/v1/${path}`, { params: params(query) });
  }

  post<T>(path: string, body: unknown = {}): Observable<T> {
    return this.http.post<T>(`/api/v1/${path}`, body);
  }

  patch<T>(path: string, body: unknown): Observable<T> {
    return this.http.patch<T>(`/api/v1/${path}`, body);
  }

  put<T>(path: string, body: unknown): Observable<T> {
    return this.http.put<T>(`/api/v1/${path}`, body);
  }

  delete<T = void>(path: string): Observable<T> {
    return this.http.delete<T>(`/api/v1/${path}`);
  }

  /** A multipart upload of one file under `field`, with any other form fields alongside it. */
  upload<T>(path: string, field: string, file: File, extra: Record<string, string> = {}): Observable<T> {
    const form = new FormData();
    for (const [name, value] of Object.entries(extra)) {
      form.append(name, value);
    }
    form.append(field, file);
    return this.http.post<T>(`/api/v1/${path}`, form);
  }
}
