import { useState } from 'react';
import { Link } from 'react-router';
import { ArrowLeft, Link as LinkIcon, Copy, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/hooks/useAuth';
import { useGenerateInvite } from '@/hooks/useSpaces';

function formatExpiry(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function SettingsInvite() {
  const { currentSpace } = useAuth();
  const generateInvite = useGenerateInvite(currentSpace?.id ?? '');
  const [copied, setCopied] = useState(false);

  const inviteData = generateInvite.data;
  const inviteUrl = inviteData
    ? `${window.location.origin}/join/${inviteData.token}`
    : null;

  const handleGenerate = () => {
    generateInvite.mutate();
    setCopied(false);
  };

  const handleCopy = async () => {
    if (!inviteUrl) return;
    await navigator.clipboard.writeText(inviteUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon-sm" asChild>
          <Link to="/settings">
            <ArrowLeft className="size-5" />
          </Link>
        </Button>
        <h1 className="text-2xl font-bold">Invite</h1>
      </div>

      {/* Generate section */}
      <div className="rounded-xl border bg-card p-6 shadow-sm">
        <div className="space-y-4">
          <div className="flex items-start gap-3">
            <div className="flex size-10 items-center justify-center rounded-lg bg-secondary">
              <LinkIcon className="size-5 text-primary" />
            </div>
            <div>
              <h2 className="font-semibold">Invite Link</h2>
              <p className="text-sm text-muted-foreground">
                Generate a single-use invite link valid for 7 days.
              </p>
            </div>
          </div>

          {!inviteData && (
            <Button
              onClick={handleGenerate}
              disabled={generateInvite.isPending}
            >
              {generateInvite.isPending
                ? 'Generating…'
                : 'Generate Invite Link'}
            </Button>
          )}

          {inviteData && inviteUrl && (
            <div className="space-y-3">
              <div className="flex gap-2">
                <Input value={inviteUrl} readOnly className="flex-1" />
                <Button variant="outline" size="sm" onClick={handleCopy}>
                  {copied ? (
                    <>
                      <Check className="mr-1 size-4" />
                      Copied
                    </>
                  ) : (
                    <>
                      <Copy className="mr-1 size-4" />
                      Copy
                    </>
                  )}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Expires {formatExpiry(inviteData.expires_at)}
              </p>
              <Button variant="outline" size="sm" onClick={handleGenerate}>
                Generate New Link
              </Button>
            </div>
          )}

          {generateInvite.isError && (
            <p className="text-sm text-destructive">
              Failed to generate invite link. Please try again.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
