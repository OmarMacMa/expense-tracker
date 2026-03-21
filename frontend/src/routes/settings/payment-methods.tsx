import { useState, useMemo } from 'react';
import { Link } from 'react-router';
import { ArrowLeft, Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  usePaymentMethods,
  useCreatePaymentMethod,
  useDeletePaymentMethod,
} from '@/hooks/usePaymentMethods';
import { useMembers } from '@/hooks/useMembers';
import { useAuth } from '@/hooks/useAuth';

export default function SettingsPaymentMethods() {
  const { data: methods, isLoading } = usePaymentMethods();
  const { data: members } = useMembers();
  const { user } = useAuth();
  const createMethod = useCreatePaymentMethod();
  const deleteMethod = useDeletePaymentMethod();

  const [newLabel, setNewLabel] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<{
    id: string;
    label: string;
  } | null>(null);

  const memberMap = useMemo(() => {
    const map = new Map<string, string>();
    members?.forEach((m) => map.set(m.user_id, m.display_name));
    return map;
  }, [members]);

  // Group methods: system first, then by owner
  const grouped = useMemo(() => {
    if (!methods) return [];
    const system = methods.filter((m) => m.is_system);
    const personal = methods.filter((m) => !m.is_system);

    const byOwner = new Map<string, typeof personal>();
    personal.forEach((m) => {
      const key = m.owner_id ?? 'unknown';
      if (!byOwner.has(key)) byOwner.set(key, []);
      byOwner.get(key)!.push(m);
    });

    const groups: { title: string; items: typeof methods }[] = [];
    if (system.length > 0) groups.push({ title: 'System', items: system });
    byOwner.forEach((items, ownerId) => {
      groups.push({
        title: memberMap.get(ownerId) ?? 'Unknown',
        items,
      });
    });
    return groups;
  }, [methods, memberMap]);

  const handleCreate = () => {
    const trimmed = newLabel.trim();
    if (!trimmed) return;
    createMethod.mutate(
      { label: trimmed },
      { onSuccess: () => setNewLabel('') },
    );
  };

  const handleDelete = () => {
    if (!deleteTarget) return;
    deleteMethod.mutate(deleteTarget.id, {
      onSuccess: () => setDeleteTarget(null),
    });
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
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon-sm" asChild>
          <Link to="/settings">
            <ArrowLeft className="size-5" />
          </Link>
        </Button>
        <h1 className="text-2xl font-bold">Payment Methods</h1>
      </div>

      {/* Add payment method */}
      <div className="rounded-xl border bg-card p-4 shadow-sm">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleCreate();
          }}
          className="flex gap-2"
        >
          <Input
            placeholder="New payment method label"
            value={newLabel}
            onChange={(e) => setNewLabel(e.target.value)}
            className="flex-1"
          />
          <Button
            type="submit"
            size="sm"
            disabled={!newLabel.trim() || createMethod.isPending}
          >
            <Plus className="mr-1 size-4" />
            Add
          </Button>
        </form>
      </div>

      {/* Grouped list */}
      {grouped.map((group) => (
        <div key={group.title} className="space-y-2">
          <h2 className="px-1 text-sm font-medium text-muted-foreground">
            {group.title}
          </h2>
          <div className="rounded-xl border bg-card shadow-sm">
            <ul className="divide-y">
              {group.items.map((method) => {
                const isOwn = method.owner_id === user?.id;
                return (
                  <li
                    key={method.id}
                    className="flex items-center gap-3 px-4 py-3"
                  >
                    <span className="flex-1 font-medium">{method.label}</span>
                    {method.is_system ? (
                      <Badge variant="secondary">System</Badge>
                    ) : isOwn ? (
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() =>
                          setDeleteTarget({
                            id: method.id,
                            label: method.label,
                          })
                        }
                      >
                        <Trash2 className="size-4 text-destructive" />
                      </Button>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      ))}

      {methods?.length === 0 && (
        <div className="rounded-xl border bg-card px-4 py-8 text-center text-muted-foreground shadow-sm">
          No payment methods yet. Add one above.
        </div>
      )}

      {/* Delete confirmation */}
      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete "{deleteTarget?.label}"?</AlertDialogTitle>
            <AlertDialogDescription>
              Expenses using this method will show "Deleted method". This action
              cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteMethod.isPending}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
