import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useAuth } from '@/hooks/useAuth';
import { useCreateSpace, useGenerateInvite } from '@/hooks/useSpaces';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Sparkles,
  Copy,
  Check,
  ArrowRight,
  Users,
  Loader2,
} from 'lucide-react';
import type { Space } from '@/types/api';

const CURRENCIES = [
  { code: 'USD', label: 'USD — US Dollar' },
  { code: 'EUR', label: 'EUR — Euro' },
  { code: 'MXN', label: 'MXN — Mexican Peso' },
  { code: 'GBP', label: 'GBP — British Pound' },
  { code: 'CAD', label: 'CAD — Canadian Dollar' },
  { code: 'AUD', label: 'AUD — Australian Dollar' },
  { code: 'JPY', label: 'JPY — Japanese Yen' },
] as const;

const TIMEZONE_GROUPS: { region: string; zones: string[] }[] = [
  {
    region: 'America',
    zones: [
      'America/New_York',
      'America/Chicago',
      'America/Denver',
      'America/Los_Angeles',
      'America/Anchorage',
      'America/Phoenix',
      'America/Toronto',
      'America/Vancouver',
      'America/Mexico_City',
      'America/Bogota',
      'America/Lima',
      'America/Santiago',
      'America/Sao_Paulo',
      'America/Argentina/Buenos_Aires',
    ],
  },
  {
    region: 'Europe',
    zones: [
      'Europe/London',
      'Europe/Paris',
      'Europe/Berlin',
      'Europe/Madrid',
      'Europe/Rome',
      'Europe/Amsterdam',
      'Europe/Zurich',
      'Europe/Stockholm',
      'Europe/Warsaw',
      'Europe/Moscow',
      'Europe/Istanbul',
    ],
  },
  {
    region: 'Asia',
    zones: [
      'Asia/Dubai',
      'Asia/Kolkata',
      'Asia/Bangkok',
      'Asia/Singapore',
      'Asia/Hong_Kong',
      'Asia/Shanghai',
      'Asia/Seoul',
      'Asia/Tokyo',
    ],
  },
  {
    region: 'Pacific',
    zones: [
      'Pacific/Auckland',
      'Pacific/Fiji',
      'Pacific/Honolulu',
      'Australia/Sydney',
      'Australia/Melbourne',
      'Australia/Perth',
    ],
  },
  {
    region: 'Africa',
    zones: [
      'Africa/Cairo',
      'Africa/Lagos',
      'Africa/Johannesburg',
      'Africa/Nairobi',
    ],
  },
];

function formatTimezoneLabel(tz: string): string {
  const city = tz.split('/').pop()!.replace(/_/g, ' ');
  try {
    const now = new Date();
    const offset = new Intl.DateTimeFormat('en-US', {
      timeZone: tz,
      timeZoneName: 'shortOffset',
    })
      .formatToParts(now)
      .find((p) => p.type === 'timeZoneName')?.value;
    return `${city} (${offset ?? tz})`;
  } catch {
    return city;
  }
}

function getDetectedTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    return 'America/New_York';
  }
}

export default function Onboarding() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const createSpace = useCreateSpace();

  const [name, setName] = useState('');
  const [currencyCode, setCurrencyCode] = useState('USD');
  const [timezone, setTimezone] = useState(getDetectedTimezone);
  const [defaultTaxPct, setDefaultTaxPct] = useState('');
  const [seedCategories, setSeedCategories] = useState(true);

  const [createdSpace, setCreatedSpace] = useState<Space | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const taxValue = defaultTaxPct.trim();
    createSpace.mutate(
      {
        name: name.trim(),
        currency_code: currencyCode,
        timezone,
        default_tax_pct: taxValue ? parseFloat(taxValue) : null,
        seed_default_categories: seedCategories,
      },
      {
        onSuccess: (space) => setCreatedSpace(space),
      },
    );
  };

  if (createdSpace) {
    return <SuccessView space={createdSpace} navigate={navigate} />;
  }

  return (
    <div className="flex min-h-screen items-start justify-center bg-[#FAFAFE] px-4 pt-12 pb-24 md:pt-20">
      <div className="w-full max-w-lg">
        {/* Header */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-[#E9DDFF]">
            <Sparkles className="h-7 w-7 text-[#7C6FA0]" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-[#1D1B20]">
            Create your space
          </h1>
          <p className="mt-2 text-[#615D69]">
            {user?.display_name
              ? `Welcome, ${user.display_name}! `
              : 'Welcome! '}
            Set up a shared space to start tracking expenses together.
          </p>
        </div>

        {/* Form Card */}
        <Card
          className="border-none bg-white"
          style={{
            boxShadow:
              '0 2px 12px rgba(29,27,32,0.04), 0 6px 24px rgba(29,27,32,0.03)',
          }}
        >
          <CardContent className="pt-6">
            <form onSubmit={handleSubmit} className="space-y-5">
              {/* Space name */}
              <div className="space-y-2">
                <Label htmlFor="space-name" className="text-[#1D1B20]">
                  Space name
                </Label>
                <Input
                  id="space-name"
                  placeholder="e.g. Our Household"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  maxLength={100}
                  className="border-[rgba(124,120,133,0.15)] bg-white focus-visible:ring-[#7C6FA0]"
                />
              </div>

              {/* Currency */}
              <div className="space-y-2">
                <Label htmlFor="currency" className="text-[#1D1B20]">
                  Currency
                </Label>
                <Select value={currencyCode} onValueChange={setCurrencyCode}>
                  <SelectTrigger
                    id="currency"
                    className="border-[rgba(124,120,133,0.15)] bg-white focus:ring-[#7C6FA0]"
                  >
                    <SelectValue placeholder="Select currency" />
                  </SelectTrigger>
                  <SelectContent>
                    {CURRENCIES.map((c) => (
                      <SelectItem key={c.code} value={c.code}>
                        {c.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-[#615D69]">
                  Currency cannot be changed after creation.
                </p>
              </div>

              {/* Timezone */}
              <div className="space-y-2">
                <Label htmlFor="timezone" className="text-[#1D1B20]">
                  Timezone
                </Label>
                <Select value={timezone} onValueChange={setTimezone}>
                  <SelectTrigger
                    id="timezone"
                    className="border-[rgba(124,120,133,0.15)] bg-white focus:ring-[#7C6FA0]"
                  >
                    <SelectValue placeholder="Select timezone" />
                  </SelectTrigger>
                  <SelectContent>
                    {TIMEZONE_GROUPS.map((group) => (
                      <SelectGroup key={group.region}>
                        <SelectLabel>{group.region}</SelectLabel>
                        {group.zones.map((tz) => (
                          <SelectItem key={tz} value={tz}>
                            {formatTimezoneLabel(tz)}
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Default tax */}
              <div className="space-y-2">
                <Label htmlFor="tax" className="text-[#1D1B20]">
                  Default tax %{' '}
                  <span className="font-normal text-[#615D69]">(optional)</span>
                </Label>
                <Input
                  id="tax"
                  type="number"
                  placeholder="e.g. 8.25"
                  value={defaultTaxPct}
                  onChange={(e) => setDefaultTaxPct(e.target.value)}
                  min={0}
                  max={100}
                  step="0.01"
                  className="border-[rgba(124,120,133,0.15)] bg-white focus-visible:ring-[#7C6FA0]"
                />
              </div>

              {/* Seed categories */}
              <div className="flex items-start gap-3 rounded-lg bg-[#F3F1F8] p-4">
                <Checkbox
                  id="seed-categories"
                  checked={seedCategories}
                  onCheckedChange={(checked) =>
                    setSeedCategories(checked === true)
                  }
                  className="mt-0.5 border-[#7C6FA0] data-[state=checked]:bg-[#7C6FA0] data-[state=checked]:text-white"
                />
                <div className="space-y-1">
                  <Label
                    htmlFor="seed-categories"
                    className="cursor-pointer text-[#1D1B20]"
                  >
                    Start with default categories
                  </Label>
                  <p className="text-xs text-[#615D69]">
                    Includes Groceries, Dining, Transport, Entertainment, and
                    more. You can customize them later.
                  </p>
                </div>
              </div>

              {/* Error message */}
              {createSpace.isError && (
                <p className="text-sm text-red-600">
                  {(createSpace.error as Error).message ||
                    'Something went wrong. Please try again.'}
                </p>
              )}

              {/* Submit */}
              <Button
                type="submit"
                disabled={!name.trim() || createSpace.isPending}
                className="h-11 w-full rounded-xl bg-[#7C6FA0] text-base font-medium text-white hover:bg-[#6B5F8A]"
              >
                {createSpace.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Creating…
                  </>
                ) : (
                  'Create Space'
                )}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

/* ---------- Success / Invite section ---------- */

function SuccessView({
  space,
  navigate,
}: {
  space: Space;
  navigate: ReturnType<typeof useNavigate>;
}) {
  const generateInvite = useGenerateInvite(space.id);
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleGenerateInvite = () => {
    generateInvite.mutate(undefined, {
      onSuccess: (data) => {
        const link = `${window.location.origin}/join/${data.token}`;
        setInviteLink(link);
      },
    });
  };

  const handleCopy = async () => {
    if (!inviteLink) return;
    try {
      await navigator.clipboard.writeText(inviteLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: select text in the input
    }
  };

  return (
    <div className="flex min-h-screen items-start justify-center bg-[#FAFAFE] px-4 pt-12 pb-24 md:pt-20">
      <div className="w-full max-w-lg">
        {/* Success header */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-[#D4E8DD]">
            <Check className="h-7 w-7 text-[#2E4A3D]" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-[#1D1B20]">
            You&apos;re all set!
          </h1>
          <p className="mt-2 text-[#615D69]">
            <span className="font-medium text-[#1D1B20]">{space.name}</span> has
            been created. Invite your partner to start tracking together.
          </p>
        </div>

        {/* Invite card */}
        <Card
          className="mb-4 border-none bg-white"
          style={{
            boxShadow:
              '0 2px 12px rgba(29,27,32,0.04), 0 6px 24px rgba(29,27,32,0.03)',
          }}
        >
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg text-[#1D1B20]">
              <Users className="h-5 w-5 text-[#7C6FA0]" />
              Invite your partner
            </CardTitle>
            <CardDescription className="text-[#615D69]">
              Generate a one-time invite link to share with your partner or
              family member.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {!inviteLink ? (
              <Button
                onClick={handleGenerateInvite}
                disabled={generateInvite.isPending}
                variant="outline"
                className="h-10 w-full rounded-xl border-[rgba(124,120,133,0.15)] text-[#7C6FA0] hover:bg-[#F3F1F8] hover:text-[#6B5F8A]"
              >
                {generateInvite.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Generating…
                  </>
                ) : (
                  'Generate Invite Link'
                )}
              </Button>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <Input
                    readOnly
                    value={inviteLink}
                    className="flex-1 border-[rgba(124,120,133,0.15)] bg-[#F3F1F8] text-sm text-[#1D1B20]"
                    onClick={(e) => (e.target as HTMLInputElement).select()}
                  />
                  <Button
                    onClick={handleCopy}
                    variant="outline"
                    size="icon"
                    className="shrink-0 border-[rgba(124,120,133,0.15)] text-[#7C6FA0] hover:bg-[#F3F1F8]"
                  >
                    {copied ? (
                      <Check className="h-4 w-4" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                </div>
                {copied && (
                  <p className="text-sm text-[#8BA89A]">
                    Link copied to clipboard!
                  </p>
                )}
              </div>
            )}
            {generateInvite.isError && (
              <p className="text-sm text-red-600">
                {(generateInvite.error as Error).message ||
                  'Failed to generate invite link.'}
              </p>
            )}
          </CardContent>
        </Card>

        {/* Go to Dashboard */}
        <Button
          onClick={() => navigate('/home')}
          className="h-11 w-full rounded-xl bg-[#7C6FA0] text-base font-medium text-white hover:bg-[#6B5F8A]"
        >
          Go to Dashboard
          <ArrowRight className="ml-1 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
