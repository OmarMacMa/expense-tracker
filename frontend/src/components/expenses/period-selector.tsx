import { useId, useState } from 'react';
import { CalendarRange, ChevronDown } from 'lucide-react';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  PERIOD_OPTIONS,
  periodLabel,
  readPeriodSelection,
  type PeriodSelection,
} from '@/lib/periodSelection';

interface PeriodSelectorProps {
  selection: PeriodSelection;
  onChange: (selection: PeriodSelection) => void;
  mode: 'home' | 'analysis';
}

export function PeriodSelector({
  selection,
  onChange,
  mode,
}: PeriodSelectorProps) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [choosingMonth, setChoosingMonth] = useState(false);
  const [monthDraft, setMonthDraft] = useState('');
  const extended = mode !== 'home';
  const label = periodLabel(selection);

  return (
    <Popover
      open={open}
      onOpenChange={(value) => {
        setOpen(value);
        setChoosingMonth(false);
        setMonthDraft(selection.month ?? '');
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          data-testid="period-control"
          aria-label={`Period: ${label}`}
          className="flex h-8 w-fit max-w-full shrink-0 items-center gap-1.5 rounded-full bg-secondary px-3 text-[13px] hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
          <CalendarRange
            className="size-4 shrink-0 text-primary"
            aria-hidden="true"
          />
          <span className="min-w-0 truncate font-semibold text-foreground">
            {label}
          </span>
          <ChevronDown
            className="size-3.5 shrink-0 text-primary"
            aria-hidden="true"
          />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        aria-label="Period settings"
        className="w-[212px] max-w-[calc(100vw-2rem)] rounded-xl border-none bg-card p-2 shadow-[var(--shadow-card)]"
      >
        <fieldset>
          <legend className="sr-only">Period</legend>
          {PERIOD_OPTIONS.filter(
            (option) =>
              extended ||
              option.value === 'this_week' ||
              option.value === 'this_month',
          ).map((option) => (
            <label
              key={option.value}
              className="flex min-h-11 cursor-pointer items-center gap-3 rounded-xl px-2 text-sm hover:bg-secondary focus-within:bg-secondary"
            >
              <input
                type="radio"
                name={`${id}-period`}
                value={option.value}
                checked={!selection.month && selection.period === option.value}
                onChange={() => {
                  onChange({ period: option.value });
                  setOpen(false);
                }}
                onClick={() => {
                  if (!selection.month && selection.period === option.value) {
                    onChange({ period: option.value });
                    setOpen(false);
                  }
                }}
                className="size-4 shrink-0 accent-primary"
              />
              {option.label}
            </label>
          ))}
        </fieldset>
        {extended && (
          <button
            type="button"
            onClick={() => setChoosingMonth(true)}
            className="flex min-h-11 w-full items-center rounded-xl px-2 text-sm font-medium text-primary hover:bg-secondary focus-visible:outline-2 focus-visible:outline-primary"
          >
            Choose a month…
          </button>
        )}
        {extended && choosingMonth && (
          <div className="mt-2 space-y-2 rounded-xl bg-secondary/50 p-3">
            <label className="block space-y-1 text-xs text-muted-foreground">
              <span>Choose a month to apply</span>
              <Input
                type="month"
                aria-label="Month picker"
                min="0001-01"
                max="9999-12"
                value={monthDraft}
                onChange={(event) => setMonthDraft(event.target.value)}
                className="h-11 w-full rounded-xl border-none bg-card text-sm"
              />
            </label>
            <Button
              type="button"
              disabled={!readPeriodSelection({ month: monthDraft })}
              className="h-11 w-full rounded-full"
              onClick={() => {
                const next = readPeriodSelection({ month: monthDraft });
                if (next) {
                  onChange(next);
                  setOpen(false);
                  setChoosingMonth(false);
                }
              }}
            >
              Apply month
            </Button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
