import { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router';
import {
  Tag,
  CreditCard,
  Hash,
  Users,
  Link as LinkIcon,
  Percent,
  ChevronRight,
  Pencil,
  Check,
  X,
  Globe,
  type LucideIcon,
} from 'lucide-react';
import { useSpace, useUpdateSpace } from '@/hooks/useSpace';

interface NavItem {
  label: string;
  icon: LucideIcon;
  to: string;
}

const navItems: NavItem[] = [
  { label: 'Categories', icon: Tag, to: '/settings/categories' },
  {
    label: 'Payment Methods',
    icon: CreditCard,
    to: '/settings/payment-methods',
  },
  { label: 'Tags', icon: Hash, to: '/settings/tags' },
  { label: 'Members', icon: Users, to: '/settings/members' },
  { label: 'Invite', icon: LinkIcon, to: '/settings/invite' },
  { label: 'Taxes', icon: Percent, to: '/settings/taxes' },
];

export default function Settings() {
  const { data: space, isLoading } = useSpace();
  const updateSpace = useUpdateSpace();

  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState('');
  const nameInputRef = useRef<HTMLInputElement>(null);

  const [editingTimezone, setEditingTimezone] = useState(false);
  const [timezoneValue, setTimezoneValue] = useState('');
  const timezoneInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingName && nameInputRef.current) {
      nameInputRef.current.focus();
      nameInputRef.current.select();
    }
  }, [editingName]);

  useEffect(() => {
    if (editingTimezone && timezoneInputRef.current) {
      timezoneInputRef.current.focus();
      timezoneInputRef.current.select();
    }
  }, [editingTimezone]);

  const saveName = () => {
    const trimmed = nameValue.trim();
    if (trimmed && space && trimmed !== space.name) {
      updateSpace.mutate({
        name: trimmed,
        timezone: space.timezone,
        default_tax_pct: space.default_tax_pct,
      });
    }
    setEditingName(false);
  };

  const saveTimezone = () => {
    const trimmed = timezoneValue.trim();
    if (trimmed && space && trimmed !== space.timezone) {
      updateSpace.mutate({
        name: space.name,
        timezone: trimmed,
        default_tax_pct: space.default_tax_pct,
      });
    }
    setEditingTimezone(false);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="size-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Settings</h1>

      {/* Space info card */}
      <div className="rounded-xl border bg-card py-6 text-card-foreground shadow-sm">
        <div className="space-y-4 px-6">
          {/* Space name */}
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-muted-foreground">
              Space Name
            </span>
            {!editingName && (
              <button
                onClick={() => {
                  setNameValue(space?.name ?? '');
                  setEditingName(true);
                }}
                className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                aria-label="Edit space name"
              >
                <Pencil className="size-4" />
              </button>
            )}
          </div>
          {editingName ? (
            <div className="flex items-center gap-2">
              <input
                ref={nameInputRef}
                type="text"
                value={nameValue}
                onChange={(e) => setNameValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') saveName();
                  if (e.key === 'Escape') setEditingName(false);
                }}
                className="flex-1 rounded-lg border bg-background px-3 py-2 text-lg font-semibold outline-none focus:ring-2 focus:ring-primary"
              />
              <button
                onClick={saveName}
                className="rounded-md p-1.5 text-primary transition-colors hover:bg-primary-container"
                aria-label="Save name"
              >
                <Check className="size-5" />
              </button>
              <button
                onClick={() => setEditingName(false)}
                className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-secondary"
                aria-label="Cancel editing name"
              >
                <X className="size-5" />
              </button>
            </div>
          ) : (
            <p className="text-lg font-semibold">{space?.name ?? '—'}</p>
          )}

          <div className="border-t" />

          {/* Currency */}
          <div>
            <span className="text-sm font-medium text-muted-foreground">
              Currency
            </span>
            <p className="mt-1">
              <span className="inline-block rounded-full bg-secondary px-3 py-1 text-sm font-medium">
                {space?.currency_code ?? '—'}
              </span>
            </p>
          </div>

          <div className="border-t" />

          {/* Timezone */}
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-muted-foreground">
              Timezone
            </span>
            {!editingTimezone && (
              <button
                onClick={() => {
                  setTimezoneValue(space?.timezone ?? '');
                  setEditingTimezone(true);
                }}
                className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                aria-label="Edit timezone"
              >
                <Pencil className="size-4" />
              </button>
            )}
          </div>
          {editingTimezone ? (
            <div className="flex items-center gap-2">
              <input
                ref={timezoneInputRef}
                type="text"
                value={timezoneValue}
                onChange={(e) => setTimezoneValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') saveTimezone();
                  if (e.key === 'Escape') setEditingTimezone(false);
                }}
                placeholder="e.g. America/New_York"
                className="flex-1 rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              />
              <button
                onClick={saveTimezone}
                className="rounded-md p-1.5 text-primary transition-colors hover:bg-primary-container"
                aria-label="Save timezone"
              >
                <Check className="size-5" />
              </button>
              <button
                onClick={() => setEditingTimezone(false)}
                className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-secondary"
                aria-label="Cancel editing timezone"
              >
                <X className="size-5" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Globe className="size-4 text-muted-foreground" />
              <p className="text-sm">{space?.timezone ?? '—'}</p>
            </div>
          )}
        </div>
      </div>

      {/* Navigation list */}
      <div className="rounded-xl border bg-card text-card-foreground shadow-sm">
        <nav>
          <ul className="divide-y">
            {navItems.map((item) => (
              <li key={item.to}>
                <Link
                  to={item.to}
                  className="flex items-center gap-4 px-6 py-4 transition-colors hover:bg-secondary/50"
                >
                  <div className="flex size-9 items-center justify-center rounded-lg bg-secondary">
                    <item.icon className="size-5 text-primary" />
                  </div>
                  <span className="flex-1 font-medium">{item.label}</span>
                  <ChevronRight className="size-5 text-muted-foreground" />
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </div>
  );
}
