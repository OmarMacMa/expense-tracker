import { useState } from 'react';
import { Plus, ShieldAlert, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { LimitCard } from '@/components/limits/limit-card';
import { LimitFormDialog } from '@/components/limits/limit-form-dialog';
import {
  useLimits,
  useCreateLimit,
  useUpdateLimit,
  useDeleteLimit,
} from '@/hooks/useLimits';
import type { LimitProgress } from '@/types/api';

export default function Limits() {
  const { data: limits, isLoading, isError } = useLimits();
  const createLimit = useCreateLimit();
  const updateLimit = useUpdateLimit();
  const deleteLimit = useDeleteLimit();

  const [formOpen, setFormOpen] = useState(false);
  const [editingLimit, setEditingLimit] = useState<LimitProgress | null>(null);
  const [deletingLimit, setDeletingLimit] = useState<LimitProgress | null>(
    null,
  );

  function handleCreate() {
    setEditingLimit(null);
    setFormOpen(true);
  }

  function handleEdit(limit: LimitProgress) {
    setEditingLimit(limit);
    setFormOpen(true);
  }

  function handleFormSubmit(data: Record<string, unknown>) {
    if (editingLimit) {
      updateLimit.mutate(
        { id: editingLimit.id, data },
        { onSuccess: () => setFormOpen(false) },
      );
    } else {
      createLimit.mutate(data, { onSuccess: () => setFormOpen(false) });
    }
  }

  function handleConfirmDelete() {
    if (!deletingLimit) return;
    deleteLimit.mutate(deletingLimit.id, {
      onSuccess: () => setDeletingLimit(null),
    });
  }

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-2 text-muted-foreground">
        <ShieldAlert className="size-8" />
        <p className="text-sm">Failed to load limits. Please try again.</p>
      </div>
    );
  }

  const hasLimits = limits && limits.length > 0;

  return (
    <>
      {/* Header */}
      <div className="mb-5 flex items-center justify-between">
        <h1 className="text-xl font-bold text-foreground sm:text-2xl">
          Spending Limits
        </h1>
        <Button size="sm" onClick={handleCreate}>
          <Plus className="size-4" />
          Add Limit
        </Button>
      </div>

      {/* Limit cards */}
      {hasLimits ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {limits.map((limit) => (
            <LimitCard
              key={limit.id}
              limit={limit}
              onEdit={handleEdit}
              onDelete={setDeletingLimit}
            />
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed bg-card py-16 text-center shadow-[var(--shadow-card)]">
          <ShieldAlert className="mb-3 size-10 text-muted-foreground/50" />
          <h2 className="text-base font-semibold text-foreground">
            No spending limits yet
          </h2>
          <p className="mt-1 max-w-xs text-sm text-muted-foreground">
            Create a limit to track spending against a weekly or monthly budget.
          </p>
          <Button size="sm" className="mt-4" onClick={handleCreate}>
            <Plus className="size-4" />
            Add your first limit
          </Button>
        </div>
      )}

      {/* Create / Edit dialog */}
      <LimitFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        onSubmit={handleFormSubmit}
        isSubmitting={createLimit.isPending || updateLimit.isPending}
        editingLimit={editingLimit}
      />

      {/* Delete confirmation dialog */}
      <Dialog
        open={!!deletingLimit}
        onOpenChange={(open) => {
          if (!open) setDeletingLimit(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete limit</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete &ldquo;{deletingLimit?.name}
              &rdquo;? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeletingLimit(null)}
              disabled={deleteLimit.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirmDelete}
              disabled={deleteLimit.isPending}
            >
              {deleteLimit.isPending ? 'Deleting…' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
