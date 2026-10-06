/**
 * Shared helper for the pending invite token used by the join-then-OAuth flow.
 *
 * The token is set on /join/:token before redirecting to Google OAuth, read on
 * /auth/callback to resume the join, kept across the "you already have a
 * space → leave first → rejoin" flow, and cleared on successful join or on
 * explicit abandonment.
 *
 * sessionStorage is tab-local and clears on tab close. A 10-minute TTL prevents
 * a stale token from a previous abandoned OAuth from silently hijacking a
 * later sign-in attempt within the same tab.
 */

const KEY = 'pending_invite_token';
const TTL_MS = 10 * 60 * 1000;

export function setPendingInvite(token: string): void {
  sessionStorage.setItem(KEY, JSON.stringify({ token, ts: Date.now() }));
}

export function readPendingInvite(): string | null {
  const raw = sessionStorage.getItem(KEY);
  if (!raw) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed !== 'object' ||
      parsed === null ||
      !('token' in parsed) ||
      !('ts' in parsed) ||
      typeof parsed.token !== 'string' ||
      !parsed.token ||
      typeof parsed.ts !== 'number' ||
      !Number.isFinite(parsed.ts)
    ) {
      return null;
    }
    if (Date.now() - parsed.ts > TTL_MS || parsed.ts > Date.now()) {
      return null;
    }

    return parsed.token;
  } catch {
    return null;
  }
}

export function hasPendingInviteIntent(): boolean {
  return sessionStorage.getItem(KEY) !== null;
}

export function clearPendingInvite(): void {
  sessionStorage.removeItem(KEY);
}
