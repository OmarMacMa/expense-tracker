import { useState } from 'react';
import { Link } from 'react-router';
import { ArrowLeft, Percent } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useSpace, useUpdateSpace } from '@/hooks/useSpace';

export default function SettingsTaxes() {
  const { data: space, isLoading } = useSpace();
  const updateSpace = useUpdateSpace();

  const initialTax =
    space?.default_tax_pct !== null && space?.default_tax_pct !== undefined
      ? String(space.default_tax_pct)
      : '';
  const [taxValue, setTaxValue] = useState(initialTax);
  const [saved, setSaved] = useState(false);
  const [initialized, setInitialized] = useState(!isLoading);

  // Reset local state when space data arrives for the first time
  if (space && !initialized) {
    const val =
      space.default_tax_pct !== null ? String(space.default_tax_pct) : '';
    setTaxValue(val);
    setInitialized(true);
  }

  const handleSave = () => {
    if (!space) return;
    const parsed = taxValue.trim() === '' ? null : parseFloat(taxValue);
    if (parsed !== null && (isNaN(parsed) || parsed < 0 || parsed > 100))
      return;

    updateSpace.mutate(
      {
        name: space.name,
        timezone: space.timezone,
        default_tax_pct: parsed,
      },
      {
        onSuccess: () => {
          setSaved(true);
          setTimeout(() => setSaved(false), 2000);
        },
      },
    );
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="size-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  const currentPct = space?.default_tax_pct;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon-sm" asChild>
          <Link to="/settings">
            <ArrowLeft className="size-5" />
          </Link>
        </Button>
        <h1 className="text-2xl font-bold">Taxes</h1>
      </div>

      <div className="rounded-xl border bg-card p-6 shadow-sm">
        <div className="space-y-4">
          <div className="flex items-start gap-3">
            <div className="flex size-10 items-center justify-center rounded-lg bg-secondary">
              <Percent className="size-5 text-primary" />
            </div>
            <div>
              <h2 className="font-semibold">Default Tax Rate</h2>
              <p className="text-sm text-muted-foreground">
                Current:{' '}
                {currentPct !== null && currentPct !== undefined
                  ? `${currentPct}%`
                  : 'Not set'}
              </p>
            </div>
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSave();
            }}
            className="flex items-center gap-2"
          >
            <div className="relative max-w-[160px]">
              <Input
                type="number"
                min="0"
                max="100"
                step="0.01"
                placeholder="0.00"
                value={taxValue}
                onChange={(e) => {
                  setTaxValue(e.target.value);
                  setSaved(false);
                }}
                className="pr-8"
              />
              <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">
                %
              </span>
            </div>
            <Button type="submit" size="sm" disabled={updateSpace.isPending}>
              {saved ? 'Saved!' : 'Save'}
            </Button>
          </form>

          <p className="text-xs text-muted-foreground">
            Leave empty to disable default tax. Value applies to new expenses
            only.
          </p>
        </div>
      </div>
    </div>
  );
}
