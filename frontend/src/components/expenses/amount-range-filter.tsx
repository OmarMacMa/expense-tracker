import { useId, useState } from 'react';
import { X } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { useCurrency } from '@/hooks/useCurrency';
import { parseAmountRange, type AmountRange } from '@/lib/amount-range';

interface AmountRangeFilterProps {
  range: AmountRange;
  onApply: (range: AmountRange) => void;
}

export function AmountRangeFilter({ range, onApply }: AmountRangeFilterProps) {
  const { currencyCode } = useCurrency();
  const id = useId();
  const separator =
    new Intl.NumberFormat()
      .formatToParts(1.1)
      .find((part) => part.type === 'decimal')?.value ?? '.';
  const localize = (value?: string) => (value ?? '').replace('.', separator);
  const [minimum, setMinimum] = useState(localize(range.min_amount));
  const [maximum, setMaximum] = useState(localize(range.max_amount));
  const [submitted, setSubmitted] = useState(false);
  const { range: draft, error } = parseAmountRange(minimum, maximum, separator);
  const applied =
    range.min_amount !== undefined || range.max_amount !== undefined;
  const description =
    range.min_amount !== undefined && range.max_amount !== undefined
      ? `${localize(range.min_amount)} to ${localize(range.max_amount)}`
      : range.min_amount !== undefined
        ? `at least ${localize(range.min_amount)}`
        : `up to ${localize(range.max_amount)}`;

  return (
    <div className="space-y-2 rounded-xl bg-secondary/50 p-3">
      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-[8rem] flex-1 text-xs font-medium text-muted-foreground">
          Minimum amount ({currencyCode})
          <Input
            aria-describedby={`${id}-help`}
            aria-invalid={!!error}
            inputMode="decimal"
            value={minimum}
            placeholder="No minimum"
            onChange={(event) => setMinimum(event.target.value)}
            className="mt-1 h-10 rounded-xl border-none bg-card"
          />
        </label>
        <label className="min-w-[8rem] flex-1 text-xs font-medium text-muted-foreground">
          Maximum amount ({currencyCode})
          <Input
            aria-describedby={`${id}-help`}
            aria-invalid={!!error}
            inputMode="decimal"
            value={maximum}
            placeholder="No maximum"
            onChange={(event) => setMaximum(event.target.value)}
            className="mt-1 h-10 rounded-xl border-none bg-card"
          />
        </label>
        <Button
          type="button"
          className="h-10 rounded-full"
          onClick={() => {
            setSubmitted(true);
            if (!error) onApply(draft);
          }}
        >
          Apply range
        </Button>
        {(applied || minimum || maximum) && (
          <button
            type="button"
            onClick={() => {
              setMinimum('');
              setMaximum('');
              setSubmitted(false);
              onApply({});
            }}
            className="text-sm font-medium text-primary hover:underline"
          >
            Clear amount range
          </button>
        )}
      </div>
      <p id={`${id}-help`} className="text-xs text-muted-foreground">
        Inclusive expense totals. Blank means unbounded. Apply when ready.
      </p>
      {error && (submitted || minimum || maximum) && (
        <p role="alert" className="text-xs text-destructive">
          {error}
        </p>
      )}
      {applied && (
        <button
          type="button"
          aria-label="Remove applied amount range"
          onClick={() => onApply({})}
          className="flex max-w-full items-center gap-2 rounded-full bg-accent px-3 py-1.5 text-left text-xs font-medium text-accent-foreground"
        >
          <span className="min-w-0 break-all">
            Amount: {currencyCode} {description}
          </span>
          <X className="h-3.5 w-3.5 shrink-0" />
        </button>
      )}
    </div>
  );
}
