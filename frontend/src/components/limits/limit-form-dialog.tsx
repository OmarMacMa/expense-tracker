import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useCategories } from '@/hooks/useCategories';
import type { LimitProgress } from '@/types/api';

interface LimitFormData {
  name: string;
  timeframe: string;
  threshold_amount: string;
  warning_pct: string;
  category_ids: string[];
}

function buildInitialForm(limit?: LimitProgress | null): LimitFormData {
  if (!limit) {
    return {
      name: '',
      timeframe: 'monthly',
      threshold_amount: '',
      warning_pct: '60',
      category_ids: [],
    };
  }
  return {
    name: limit.name,
    timeframe: limit.timeframe,
    threshold_amount: limit.threshold_amount,
    warning_pct: String(Math.round(parseFloat(limit.warning_pct) * 100)),
    category_ids: limit.filters
      .filter((f) => f.filter_type === 'category')
      .map((f) => f.id),
  };
}

interface LimitFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: Record<string, unknown>) => void;
  isSubmitting: boolean;
  editingLimit?: LimitProgress | null;
}

export function LimitFormDialog({
  open,
  onOpenChange,
  onSubmit,
  isSubmitting,
  editingLimit,
}: LimitFormDialogProps) {
  // Key forces inner form to remount (and re-initialize state) when dialog opens/closes or target changes
  const formKey = `${open}-${editingLimit?.id ?? 'new'}`;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <LimitFormInner
          key={formKey}
          editingLimit={editingLimit}
          onSubmit={onSubmit}
          onCancel={() => onOpenChange(false)}
          isSubmitting={isSubmitting}
        />
      </DialogContent>
    </Dialog>
  );
}

function LimitFormInner({
  editingLimit,
  onSubmit,
  onCancel,
  isSubmitting,
}: {
  editingLimit?: LimitProgress | null;
  onSubmit: (data: Record<string, unknown>) => void;
  onCancel: () => void;
  isSubmitting: boolean;
}) {
  const [form, setForm] = useState<LimitFormData>(() =>
    buildInitialForm(editingLimit),
  );
  const { data: categories } = useCategories();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const payload: Record<string, unknown> = {
      name: form.name.trim(),
      timeframe: form.timeframe,
      threshold_amount: parseFloat(form.threshold_amount),
      warning_pct: parseFloat(form.warning_pct) / 100,
    };
    if (form.category_ids.length > 0) {
      payload.category_ids = form.category_ids;
    }
    onSubmit(payload);
  }

  const isValid =
    form.name.trim() !== '' &&
    parseFloat(form.threshold_amount) > 0 &&
    parseFloat(form.warning_pct) >= 0 &&
    parseFloat(form.warning_pct) <= 100;

  function toggleCategory(categoryId: string) {
    setForm((prev) => ({
      ...prev,
      category_ids: prev.category_ids.includes(categoryId)
        ? prev.category_ids.filter((id) => id !== categoryId)
        : [...prev.category_ids, categoryId],
    }));
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>
          {editingLimit ? 'Edit Limit' : 'Create Limit'}
        </DialogTitle>
        <DialogDescription>
          {editingLimit
            ? 'Update the spending limit settings.'
            : 'Set a spending limit to stay on budget.'}
        </DialogDescription>
      </DialogHeader>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="limit-name">Name</Label>
          <Input
            id="limit-name"
            placeholder="e.g. Monthly Groceries"
            value={form.name}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, name: e.target.value }))
            }
            required
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <Label htmlFor="limit-timeframe">Timeframe</Label>
            <Select
              value={form.timeframe}
              onValueChange={(value) =>
                setForm((prev) => ({ ...prev, timeframe: value }))
              }
            >
              <SelectTrigger id="limit-timeframe">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="weekly">Weekly</SelectItem>
                <SelectItem value="monthly">Monthly</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="limit-threshold">Threshold ($)</Label>
            <Input
              id="limit-threshold"
              type="number"
              min="1"
              step="0.01"
              placeholder="400"
              value={form.threshold_amount}
              onChange={(e) =>
                setForm((prev) => ({
                  ...prev,
                  threshold_amount: e.target.value,
                }))
              }
              required
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="limit-warning">Warning at (%)</Label>
          <Input
            id="limit-warning"
            type="number"
            min="0"
            max="100"
            step="1"
            placeholder="60"
            value={form.warning_pct}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, warning_pct: e.target.value }))
            }
          />
          <p className="text-xs text-muted-foreground">
            You&apos;ll see a warning when spending reaches this percentage.
          </p>
        </div>

        {categories && categories.length > 0 && (
          <div className="space-y-2">
            <Label>Category filter (optional)</Label>
            <div className="flex flex-wrap gap-1.5">
              {categories.map((cat) => (
                <button
                  key={cat.id}
                  type="button"
                  onClick={() => toggleCategory(cat.id)}
                  className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                    form.category_ids.includes(cat.id)
                      ? 'border-primary bg-accent text-accent-foreground'
                      : 'border-border bg-card text-muted-foreground hover:bg-secondary'
                  }`}
                >
                  {cat.name}
                </button>
              ))}
            </div>
            {form.category_ids.length > 0 && (
              <p className="text-xs text-muted-foreground">
                {form.category_ids.length} categor
                {form.category_ids.length === 1 ? 'y' : 'ies'} selected
              </p>
            )}
          </div>
        )}

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={onCancel}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button type="submit" disabled={!isValid || isSubmitting}>
            {isSubmitting ? 'Saving…' : editingLimit ? 'Update' : 'Create'}
          </Button>
        </DialogFooter>
      </form>
    </>
  );
}
