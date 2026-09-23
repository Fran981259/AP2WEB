# AP2WEB Mobile

Expo Go SDK 57 client for the AP2WEB API. The server remains the source of truth for
authentication, matches, predictions, jobs and history.

## Local setup

```bash
cp .env.example .env
npm install
npx expo start
```

Set `EXPO_PUBLIC_API_BASE_URL` to the HTTPS Tailscale address reachable from
the phone. The phone must be connected to the same Tailnet. Never put a secret
in an `EXPO_PUBLIC_*` variable.

The first screen uses `/api/v1/mobile/auth/login`, stores bearer credentials in
Expo SecureStore, and rotates refresh tokens through `/api/v1/mobile/auth/refresh`.
