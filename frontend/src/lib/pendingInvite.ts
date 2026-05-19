/**
 * Shared helper for the pending invite token used by the join-then-OAuth flow.
 *
 * The token is set on /join/:token before redirecting to Google OAuth, read on
 * /auth/callback to resume the join, kept across the "you already have a
 * space → leave first → rejoin" flow, and cleared on successful join or on
 * landing-page mount (defensively).
 *
 * sessionStorage is tab-local and clears on tab close. A 10-minute TTL prevents
 * a stale token from a previous abandoned OAuth from silently hijacking a
 * later sign-in attempt within the same tab.
 */

const KEY = 'pending_invite_token';
const TTL_MS = 10 * 60 * 1000;

interface StoredInvite {
  token: string;
  ts: number;
}

export function setPendingInvite(token: string): void {
  sessionStorage.setItem(KEY, JSON.stringify({ token, ts: Date.now() }));
}

export function readPendingInvite(): string | null {
  const raw = sessionStorage.getItem(KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<StoredInvite>;
    if (typeof parsed.token !== 'string' || typeof parsed.ts !== 'number') {
      sessionStorage.removeItem(KEY);
      return null;
    }
    if (Date.now() - parsed.ts > TTL_MS) {
      sessionStorage.removeItem(KEY);
      return null;
    }
    return parsed.token;
  } catch {
    sessionStorage.removeItem(KEY);
    return null;
  }
}

export function clearPendingInvite(): void {
  sessionStorage.removeItem(KEY);
}
