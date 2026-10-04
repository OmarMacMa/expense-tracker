import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { api, errorMessage } from '@/lib/api-client';
import {
  clearPendingInvite,
  hasPendingInviteIntent,
  readPendingInvite,
} from '@/lib/pendingInvite';
import { refreshMembership } from '@/lib/membershipCache';
import type {
  InvitePreview,
  LeavePreview,
  MembershipOutcome,
} from '@/types/api';

export function LeaveSpaceDialog({ spaceId }: { spaceId: string }) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [intent, setIntent] = useState(false);
  const [name, setName] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [completed, setCompleted] = useState<MembershipOutcome | null>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const preview = useQuery({
    queryKey: ['leave-preview', spaceId],
    queryFn: ({ signal }) =>
      api.get<LeavePreview>(
        `/spaces/${spaceId}/leave-preview`,
        undefined,
        signal,
      ),
    enabled: open && !completed,
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: 0,
  });
  const destination = useQuery({
    queryKey: ['invite-preview', token],
    queryFn: ({ signal }) =>
      api.get<InvitePreview>(
        `/spaces/invites/${encodeURIComponent(token ?? '')}/preview`,
        undefined,
        signal,
      ),
    enabled: open && !!token && !completed,
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: 0,
  });

  useEffect(() => {
    setName('');
  }, [preview.dataUpdatedAt, destination.dataUpdatedAt]);

  useEffect(() => {
    if (!open || completed) return;
    const check = () => {
      const current = readPendingInvite();
      if (current !== token || (intent && !current)) {
        setName('');
        setError(
          'The invitation changed or expired. Cancel and review the intended invitation again. Nothing has been changed.',
        );
      }
    };
    const timer = window.setInterval(check, 1000);
    return () => window.clearInterval(timer);
  }, [open, completed, token, intent]);

  const show = () => {
    setToken(readPendingInvite());
    setIntent(hasPendingInviteIntent());
    setName('');
    setError(null);
    setOpen(true);
  };

  const finish = async (outcome: MembershipOutcome) => {
    setPending(true);
    try {
      await refreshMembership(client, outcome.destination_space_id, navigate);
    } catch (err: unknown) {
      setError(
        `Membership change completed, but your session could not refresh. ${errorMessage(err)}`,
      );
    } finally {
      setPending(false);
    }
  };

  const submit = async () => {
    if (!preview.data || pending || completed) return;
    if (readPendingInvite() !== token || (intent && !token)) {
      setName('');
      setError(
        'The invitation changed or expired. Cancel and review again. Nothing has been changed.',
      );
      return;
    }
    setPending(true);
    setError(null);
    let outcome: MembershipOutcome;
    try {
      const data = { source_name: name, preview: preview.data };
      outcome = token
        ? await api.post<MembershipOutcome>(
            `/spaces/${spaceId}/membership-transfers`,
            { ...data, invite_token: token },
          )
        : await api.delete<MembershipOutcome>(
            `/spaces/${spaceId}/members/me`,
            data,
          );
      setCompleted(outcome);
      clearPendingInvite();
      toast.success(
        outcome.source_deleted
          ? 'The space was deleted'
          : "You've left the space",
      );
    } catch (err: unknown) {
      setError(errorMessage(err));
      setName('');
      await preview.refetch();
      if (token) await destination.refetch();
      setPending(false);
      return;
    }
    await finish(outcome);
  };

  const target = destination.data;
  const ready =
    preview.data &&
    !preview.isFetching &&
    !preview.isError &&
    (!intent ||
      (token &&
        target &&
        !destination.isFetching &&
        !destination.isError &&
        !target.already_member &&
        target.member_count < target.max_members));
  return (
    <section
      id="danger-zone"
      className="scroll-mt-8 space-y-3 rounded-2xl bg-card p-6 shadow-[var(--shadow-card)]"
    >
      <h2 className="text-lg font-semibold text-destructive">Danger Zone</h2>
      <p className="text-sm text-muted-foreground">
        Leave this space. If you're its last member, the space and all its data
        are permanently deleted. Your account is kept.
      </p>
      <Button variant="destructive" onClick={show}>
        Review leaving space
      </Button>
      <Dialog
        open={open}
        onOpenChange={(value) => {
          if (!pending && !completed) setOpen(value);
        }}
      >
        <DialogContent
          className="max-h-[85dvh] overflow-y-auto"
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            cancelRef.current?.focus();
          }}
        >
          <DialogHeader>
            <DialogTitle>
              {completed
                ? 'Membership change completed'
                : token
                  ? `Leave and join "${target?.space_name ?? 'invited space'}"`
                  : 'Leave space'}
            </DialogTitle>
            <DialogDescription>
              {completed
                ? 'Do not submit the membership change again. Refresh your session to continue.'
                : 'Only your membership changes. No data is transferred, and your account is not deleted.'}
            </DialogDescription>
          </DialogHeader>
          {completed ? (
            <>
              {error && (
                <p role="alert" className="text-sm text-destructive">
                  {error}
                </p>
              )}
              <Button disabled={pending} onClick={() => finish(completed)}>
                Refresh session
              </Button>
              <Button
                variant="outline"
                onClick={() => window.location.reload()}
              >
                Reload page
              </Button>
            </>
          ) : (
            <>
              {intent && !token && (
                <p role="alert" className="text-destructive">
                  Your pending invitation expired. Cancel and open it again, or
                  explicitly abandon it before a standalone leave.
                </p>
              )}
              {preview.isFetching && (
                <p role="status">Loading current consequences...</p>
              )}
              {(preview.isError || destination.isError || error) && (
                <p role="alert" className="text-sm text-destructive">
                  {error ?? errorMessage(preview.error ?? destination.error)}
                </p>
              )}
              {target && (
                <p className="text-sm">
                  Destination: <strong>{target.space_name}</strong> (
                  {target.member_count} / {target.max_members} members).{' '}
                  {target.already_member
                    ? 'You already belong to this space. Do not leave it to join itself.'
                    : 'If joining fails, your current membership and all data remain unchanged.'}
                </p>
              )}
              {preview.data && (
                <>
                  <p className="text-sm">
                    <strong>{preview.data.space_name}</strong> has{' '}
                    {preview.data.member_count} member(s).{' '}
                    {preview.data.source_deleted
                      ? 'You are the last member. Successful confirmation permanently deletes this space and ALL its data. This cannot be undone.'
                      : 'Shared history, original expense attribution and payment methods remain available to the other members.'}
                  </p>
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-1 rounded-xl bg-secondary p-3 text-sm">
                    {Object.entries(preview.data.counts).map(
                      ([label, count]) => (
                        <div key={label} className="contents">
                          <dt>{label.replaceAll('_', ' ')}</dt>
                          <dd className="text-right tabular-nums">{count}</dd>
                        </div>
                      ),
                    )}
                  </dl>
                  <Label htmlFor="confirm-source">
                    Type "{preview.data.space_name}" exactly to confirm
                  </Label>
                  <Input
                    id="confirm-source"
                    value={name}
                    autoComplete="off"
                    disabled={pending}
                    onChange={(event) => setName(event.target.value)}
                  />
                </>
              )}
              <DialogFooter>
                <Button
                  ref={cancelRef}
                  variant="outline"
                  disabled={pending}
                  onClick={() => setOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  variant="outline"
                  disabled={pending}
                  onClick={() => {
                    setName('');
                    setError(null);
                    preview.refetch();
                    if (token) destination.refetch();
                  }}
                >
                  Refresh preview
                </Button>
                <Button
                  variant="destructive"
                  disabled={
                    !ready ||
                    !!error ||
                    pending ||
                    name !== preview.data?.space_name
                  }
                  onClick={submit}
                >
                  {pending
                    ? 'Working...'
                    : token
                      ? `Leave and join ${target?.space_name ?? 'invited space'}`
                      : 'Leave space'}
                </Button>
              </DialogFooter>
              {intent && (
                <Button
                  variant="ghost"
                  disabled={pending}
                  onClick={() => {
                    clearPendingInvite();
                    setOpen(false);
                  }}
                >
                  Abandon invitation (no membership change)
                </Button>
              )}
              {(preview.isError || destination.isError || error) && (
                <Button
                  variant="outline"
                  disabled={pending}
                  onClick={() => {
                    window.location.href = '/api/v1/auth/google';
                  }}
                >
                  Sign in again
                </Button>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>
    </section>
  );
}
