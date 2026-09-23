import { clearSession, readSession, saveSession } from './storage';

type Envelope<T> = { data: T; message: string; statusCode: number };
type User = { username: string; role: string };
type AuthPayload = {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  expires_in: number;
  user: User;
};

const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/$/, '');

function requireBaseUrl() {
  if (!API_BASE_URL) throw new Error('EXPO_PUBLIC_API_BASE_URL não configurada');
  return API_BASE_URL;
}

async function request<T>(path: string, init: RequestInit = {}) {
  const session = await readSession();
  const headers = new Headers(init.headers);
  headers.set('Content-Type', 'application/json');
  if (session) headers.set('Authorization', `Bearer ${session.accessToken}`);
  const response = await fetch(`${requireBaseUrl()}${path}`, { ...init, headers });
  const body = (await response.json()) as Envelope<T> | { detail?: string };
  if (!response.ok) throw new Error('detail' in body ? body.detail : 'Erro na API');
  return (body as Envelope<T>).data;
}

export async function login(username: string, password: string) {
  const payload = await request<AuthPayload>('/api/v1/mobile/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  await saveSession(payload.access_token, payload.refresh_token);
  return payload.user;
}

export async function refresh() {
  const session = await readSession();
  if (!session) return false;
  try {
    const payload = await request<AuthPayload>('/api/v1/mobile/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: session.refreshToken }),
    });
    await saveSession(payload.access_token, payload.refresh_token);
    return true;
  } catch {
    await clearSession();
    return false;
  }
}

export async function logout() {
  try {
    await request('/api/v1/mobile/auth/logout', { method: 'POST' });
  } finally {
    await clearSession();
  }
}
