const API_BASE = '/api/v1';

export interface ApiError extends Error {
  status?: number;
  data?: { error?: { code?: string; message?: string } };
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: Record<string, unknown> | unknown[];
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }

  async get<T>(path: string, params?: Record<string, string>): Promise<T> {
    const url = new URL(`${this.baseUrl}${path}`, window.location.origin);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          url.searchParams.set(key, value);
        }
      });
    }
    return this.request<T>(url.toString(), { method: 'GET' });
  }

  async post<T>(path: string, body?: Record<string, unknown>): Promise<T> {
    return this.request<T>(`${this.baseUrl}${path}`, {
      method: 'POST',
      body,
    });
  }

  async patch<T>(path: string, body?: Record<string, unknown>): Promise<T> {
    return this.request<T>(`${this.baseUrl}${path}`, {
      method: 'PATCH',
      body,
    });
  }

  async put<T>(path: string, body?: Record<string, unknown>): Promise<T> {
    return this.request<T>(`${this.baseUrl}${path}`, {
      method: 'PUT',
      body,
    });
  }

  async delete(path: string): Promise<void> {
    await this.request<void>(`${this.baseUrl}${path}`, {
      method: 'DELETE',
    });
  }

  private async request<T>(url: string, options: RequestOptions): Promise<T> {
    const { body, ...rest } = options;
    const response = await fetch(url, {
      ...rest,
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...rest.headers,
      },
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      const error: ApiError = new Error(
        errorData?.error?.message || `HTTP ${response.status}`,
      );
      error.status = response.status;
      error.data = errorData;

      if (response.status === 401) {
        window.location.href = '/';
        throw error;
      }

      throw error;
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }
}

export const api = new ApiClient();
