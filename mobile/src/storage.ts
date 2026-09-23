import * as SecureStore from 'expo-secure-store';

const ACCESS_KEY = 'ap2web.access_token';
const REFRESH_KEY = 'ap2web.refresh_token';

export async function saveSession(accessToken: string, refreshToken: string) {
  await SecureStore.setItemAsync(ACCESS_KEY, accessToken);
  await SecureStore.setItemAsync(REFRESH_KEY, refreshToken);
}

export async function readSession() {
  const [accessToken, refreshToken] = await Promise.all([
    SecureStore.getItemAsync(ACCESS_KEY),
    SecureStore.getItemAsync(REFRESH_KEY),
  ]);
  return accessToken && refreshToken ? { accessToken, refreshToken } : null;
}

export async function clearSession() {
  await Promise.all([
    SecureStore.deleteItemAsync(ACCESS_KEY),
    SecureStore.deleteItemAsync(REFRESH_KEY),
  ]);
}
