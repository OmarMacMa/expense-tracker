import { useState, useRef, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router';
import {
  ArrowLeft,
  CalendarIcon,
  Clock,
  Pencil,
  Trash2,
  X,
  ChevronDown,
} from 'lucide-react';
import { format } from 'date-fns';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
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
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import { Calendar } from '@/components/ui/calendar';
import { cn } from '@/lib/utils';
import { getCategoryColor } from '@/lib/expense-utils';
import { useCurrency } from '@/hooks/useCurrency';
import {
  useExpense,
  useUpdateExpense,
  useDeleteExpense,
} from '@/hooks/useExpenses';
import { useMerchantSuggest } from '@/hooks/useMerchants';
import { useCategories } from '@/hooks/useCategories';
import { usePaymentMethods } from '@/hooks/usePaymentMethods';
import { useTags } from '@/hooks/useTags';
import { useMembers } from '@/hooks/useMembers';

function getInitials(name: string): string {
  return name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

function formatTimeValue(date: Date): string {
  const hours = date.getHours();
  const minutes = date.getMinutes();
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
}

function formatFullDatetime(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

function formatTimestamp(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

// ─── View Mode ────────────────────────────────────────────────────────────────

function ExpenseViewMode({
  expense,
  categories,
  paymentMethods,
  onEdit,
  onDelete,
  isDeleting,
}: {
  expense: NonNullable<ReturnType<typeof useExpense>['data']>;
  categories: ReturnType<typeof useCategories>['data'];
  paymentMethods: ReturnType<typeof usePaymentMethods>['data'];
  onEdit: () => void;
  onDelete: () => void;
  isDeleting: boolean;
}) {
  const line = expense.lines[0];
  const { format: formatAmount } = useCurrency();
  const category = categories?.find((c) => c.id === line?.category_id);
  const categoryColor = category ? getCategoryColor(category.name) : null;
  const paymentMethod = paymentMethods?.find(
    (pm) => pm.id === expense.payment_method_id,
  );

  return (
    <div className="rounded-2xl bg-card p-6 shadow-[var(--shadow-card)] md:p-9">
      {/* Hero: Merchant + Amount */}
      <div className="pb-6 pt-1 text-center">
        <h2 className="mb-1 text-xl font-semibold text-foreground md:text-2xl">
          {expense.merchant}
        </h2>
        <div className="text-[2.25rem] font-bold leading-tight text-foreground md:text-[2.5rem]">
          {formatAmount(expense.total_amount)}
        </div>
        <div className="mx-auto mt-2 h-1.5 w-10 rounded-full bg-accent" />
      </div>

      {/* Details section */}
      <div className="mb-4">
        <p className="mb-2 text-[0.72rem] font-medium uppercase tracking-wider text-muted-foreground">
          Details
        </p>
        <div className="h-0.5 w-full bg-secondary" />
      </div>

      <div className="space-y-4">
        {/* Category */}
        <div className="flex items-center justify-between">
          <span className="text-[0.82rem] text-muted-foreground">Category</span>
          {category && categoryColor ? (
            <Badge
              className={cn(
                'rounded-full px-3 py-1 text-[0.78rem] font-medium',
                categoryColor.bg,
                categoryColor.text,
              )}
            >
              {category.name}
            </Badge>
          ) : (
            <span className="text-[0.88rem] text-foreground">
              Uncategorized
            </span>
          )}
        </div>

        {/* Purchase date */}
        <div className="flex items-center justify-between">
          <span className="text-[0.82rem] text-muted-foreground">Date</span>
          <span className="text-[0.88rem] text-foreground">
            {formatFullDatetime(expense.purchase_datetime)}
          </span>
        </div>

        {/* Spender */}
        <div className="flex items-center justify-between">
          <span className="text-[0.82rem] text-muted-foreground">Paid By</span>
          <div className="flex items-center gap-2">
            <div className="flex size-6 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-accent to-primary text-[0.58rem] font-bold text-primary-foreground">
              {getInitials(expense.spender.display_name)}
            </div>
            <span className="text-[0.88rem] text-foreground">
              {expense.spender.display_name}
            </span>
          </div>
        </div>

        {/* Payment method */}
        <div className="flex items-center justify-between">
          <span className="text-[0.82rem] text-muted-foreground">
            Payment Method
          </span>
          <span className="text-[0.88rem] text-foreground">
            {paymentMethod?.label ?? '—'}
          </span>
        </div>

        {/* Status */}
        <div className="flex items-center justify-between">
          <span className="text-[0.82rem] text-muted-foreground">Status</span>
          <Badge
            className={cn(
              'rounded-full px-3 py-1 text-[0.78rem] font-medium capitalize',
              expense.status === 'confirmed'
                ? 'bg-[#D4E8DD] text-[#2E4A3D]'
                : 'bg-[var(--butter-container)] text-[#4A4220]',
            )}
          >
            {expense.status}
          </Badge>
        </div>
      </div>

      {/* Tags */}
      {line?.tags && line.tags.length > 0 && (
        <>
          <div className="mb-4 mt-6">
            <p className="mb-2 text-[0.72rem] font-medium uppercase tracking-wider text-muted-foreground">
              Tags
            </p>
            <div className="h-0.5 w-full bg-secondary" />
          </div>
          <div className="flex flex-wrap gap-2">
            {line.tags.map((tag, i) => (
              <Badge
                key={tag.id}
                className={cn(
                  'rounded-full px-3 py-1.5 text-[0.8rem] font-medium',
                  i % 2 === 0
                    ? 'bg-[#D4E8DD] text-[#2E4A3D]'
                    : 'bg-accent text-accent-foreground',
                )}
              >
                #{tag.name}
              </Badge>
            ))}
          </div>
        </>
      )}

      {/* Notes */}
      {expense.notes && (
        <>
          <div className="mb-4 mt-6">
            <p className="mb-2 text-[0.72rem] font-medium uppercase tracking-wider text-muted-foreground">
              Notes
            </p>
            <div className="h-0.5 w-full bg-secondary" />
          </div>
          <p className="whitespace-pre-wrap text-[0.88rem] leading-relaxed text-foreground">
            {expense.notes}
          </p>
        </>
      )}

      {/* Timestamps */}
      <div className="mt-6 border-t border-secondary pt-4">
        <div className="flex flex-col gap-1 text-[0.72rem] text-muted-foreground">
          <span>Created {formatTimestamp(expense.created_at)}</span>
          {expense.updated_at !== expense.created_at && (
            <span>Updated {formatTimestamp(expense.updated_at)}</span>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="mt-6 flex flex-col-reverse items-center gap-2 md:flex-row md:justify-end md:gap-3">
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button
              variant="outline"
              className="h-11 w-full rounded-[20px] border-destructive/30 text-[0.88rem] font-normal text-destructive hover:bg-destructive/10 hover:text-destructive md:w-auto md:px-6"
            >
              <Trash2 className="mr-2 size-4" />
              {isDeleting ? 'Deleting...' : 'Delete'}
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete Expense</AlertDialogTitle>
              <AlertDialogDescription>
                Are you sure you want to delete this expense? This cannot be
                undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={onDelete}
                className="bg-destructive text-white hover:bg-destructive/90"
              >
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        <Button
          onClick={onEdit}
          className="h-11 w-full rounded-[20px] bg-primary text-[0.9rem] font-medium tracking-wide text-primary-foreground shadow-[0_2px_8px_rgba(124,111,160,0.2)] hover:bg-primary/90 md:w-auto md:px-9"
        >
          <Pencil className="mr-2 size-4" />
          Edit
        </Button>
      </div>
    </div>
  );
}

// ─── Edit Mode ────────────────────────────────────────────────────────────────

function ExpenseEditMode({
  expense,
  onSave,
  onCancel,
  isSaving,
  saveError,
}: {
  expense: NonNullable<ReturnType<typeof useExpense>['data']>;
  onSave: (changes: Record<string, unknown>) => void;
  onCancel: () => void;
  isSaving: boolean;
  saveError: Error | null;
}) {
  const line = expense.lines[0];
  const { format: formatAmount } = useCurrency();

  // Form state initialized from expense
  const [amount, setAmount] = useState(expense.total_amount);
  const [merchant, setMerchant] = useState(expense.merchant);
  const [merchantQuery, setMerchantQuery] = useState(expense.merchant);
  const [categoryId, setCategoryId] = useState(line?.category_id ?? '');
  const [purchaseDate, setPurchaseDate] = useState<Date>(
    new Date(expense.purchase_datetime),
  );
  const [purchaseTime, setPurchaseTime] = useState(
    formatTimeValue(new Date(expense.purchase_datetime)),
  );
  const [spenderId, setSpenderId] = useState(expense.spender.id);
  const [paymentMethodId, setPaymentMethodId] = useState(
    expense.payment_method_id ?? '',
  );
  const [selectedTags, setSelectedTags] = useState<
    { id: string; name: string }[]
  >(line?.tags ?? []);
  const [tagInput, setTagInput] = useState('');
  const [notes, setNotes] = useState(expense.notes ?? '');

  // Dropdown open states
  const [merchantOpen, setMerchantOpen] = useState(false);
  const [categoryOpen, setCategoryOpen] = useState(false);
  const [dateOpen, setDateOpen] = useState(false);
  const [spenderOpen, setSpenderOpen] = useState(false);
  const [paymentMethodOpen, setPaymentMethodOpen] = useState(false);
  const [tagDropdownOpen, setTagDropdownOpen] = useState(false);

  const merchantInputRef = useRef<HTMLInputElement>(null);
  const tagInputRef = useRef<HTMLInputElement>(null);

  const [highlightedMerchant, setHighlightedMerchant] = useState(-1);
  const [highlightedTag, setHighlightedTag] = useState(-1);

  // Data hooks
  const { data: merchantSuggestions } = useMerchantSuggest(merchantQuery);
  const { data: categories } = useCategories();
  const { data: paymentMethods } = usePaymentMethods();
  const { data: tags } = useTags();
  const { data: members } = useMembers();

  const handleMerchantInput = useCallback((value: string) => {
    setMerchantQuery(value);
    setMerchant(value);
    setMerchantOpen(value.length >= 1);
    setHighlightedMerchant(-1);
  }, []);

  const handleMerchantSelect = useCallback((name: string) => {
    setMerchant(name);
    setMerchantQuery(name);
    setMerchantOpen(false);
    setHighlightedMerchant(-1);
  }, []);

  const handleMerchantKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (!merchantOpen || !merchantSuggestions?.length) return;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setHighlightedMerchant((prev) =>
          prev < merchantSuggestions.length - 1 ? prev + 1 : 0,
        );
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setHighlightedMerchant((prev) =>
          prev > 0 ? prev - 1 : merchantSuggestions.length - 1,
        );
      } else if (e.key === 'Enter' && highlightedMerchant >= 0) {
        e.preventDefault();
        handleMerchantSelect(merchantSuggestions[highlightedMerchant].name);
      } else if (e.key === 'Escape') {
        setMerchantOpen(false);
        setHighlightedMerchant(-1);
      }
    },
    [
      merchantOpen,
      merchantSuggestions,
      highlightedMerchant,
      handleMerchantSelect,
    ],
  );

  const handleAddTag = useCallback(
    (tag: { id: string; name: string }) => {
      if (!selectedTags.find((t) => t.id === tag.id)) {
        setSelectedTags((prev) => [...prev, tag]);
      }
      setTagInput('');
      setTagDropdownOpen(false);
      tagInputRef.current?.focus();
    },
    [selectedTags],
  );

  const handleRemoveTag = useCallback((tagId: string) => {
    setSelectedTags((prev) => prev.filter((t) => t.id !== tagId));
  }, []);

  const handleTagInput = useCallback((value: string) => {
    setTagInput(value);
    setHighlightedTag(-1);
    if (value.startsWith('#') && value.length > 1) {
      setTagDropdownOpen(true);
    } else if (value.length === 0) {
      setTagDropdownOpen(false);
    }
  }, []);

  const handleTagKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      const currentFilteredTags = tags?.filter((t) => {
        const q = tagInput.replace(/^#/, '').toLowerCase();
        return t.name.includes(q) && !selectedTags.find((st) => st.id === t.id);
      });

      if (tagDropdownOpen && currentFilteredTags?.length) {
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          setHighlightedTag((prev) =>
            prev < currentFilteredTags.length - 1 ? prev + 1 : 0,
          );
          return;
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          setHighlightedTag((prev) =>
            prev > 0 ? prev - 1 : currentFilteredTags.length - 1,
          );
          return;
        } else if (e.key === 'Enter' && highlightedTag >= 0) {
          e.preventDefault();
          handleAddTag(currentFilteredTags[highlightedTag]);
          setHighlightedTag(-1);
          return;
        } else if (e.key === 'Escape') {
          setTagDropdownOpen(false);
          setHighlightedTag(-1);
          return;
        }
      }

      if (e.key === 'Enter' && tagInput.trim()) {
        e.preventDefault();
        const normalizedName = tagInput.replace(/^#/, '').toLowerCase().trim();
        if (!normalizedName) return;

        const existingTag = tags?.find((t) => t.name === normalizedName);
        if (existingTag) {
          handleAddTag(existingTag);
        } else {
          handleAddTag({ id: `new-${normalizedName}`, name: normalizedName });
        }
      }
      if (e.key === 'Backspace' && tagInput === '' && selectedTags.length > 0) {
        setSelectedTags((prev) => prev.slice(0, -1));
      }
    },
    [
      tagInput,
      tags,
      selectedTags,
      handleAddTag,
      tagDropdownOpen,
      highlightedTag,
    ],
  );

  const buildPurchaseDatetime = useCallback((): string => {
    const [hours, minutes] = purchaseTime.split(':').map(Number);
    const dt = new Date(purchaseDate);
    dt.setHours(hours, minutes, 0, 0);
    return dt.toISOString();
  }, [purchaseDate, purchaseTime]);

  const handleSubmit = useCallback(() => {
    if (!amount || parseFloat(amount) <= 0) return;

    const payload: Record<string, unknown> = {
      merchant: merchant.trim(),
      amount: parseFloat(String(amount)),
      purchase_datetime: buildPurchaseDatetime(),
      spender_id: spenderId,
      notes: notes.trim() || null,
      payment_method_id: paymentMethodId || null,
      category_id: categoryId || null,
      tags: selectedTags.map((t) => t.name),
    };

    onSave(payload);
  }, [
    amount,
    merchant,
    buildPurchaseDatetime,
    spenderId,
    notes,
    paymentMethodId,
    categoryId,
    selectedTags,
    onSave,
  ]);

  const selectedCategory = categories?.find((c) => c.id === categoryId);
  const selectedMember = members?.find((m) => m.user_id === spenderId);
  const selectedPaymentMethod = paymentMethods?.find(
    (pm) => pm.id === paymentMethodId,
  );

  const filteredTags = tags?.filter((t) => {
    const query = tagInput.replace(/^#/, '').toLowerCase();
    return t.name.includes(query) && !selectedTags.find((st) => st.id === t.id);
  });

  const maxDate = new Date();

  return (
    <div className="rounded-2xl bg-card p-6 shadow-[var(--shadow-card)] md:p-9">
      {/* Hero amount */}
      <div className="pb-7 pt-1 text-center">
        <p className="mb-1.5 text-[0.72rem] font-medium uppercase tracking-wider text-muted-foreground">
          Amount
        </p>
        <div className="mb-3 text-[2.5rem] font-bold leading-tight text-foreground">
          {formatAmount(amount || '0')}
        </div>
        <div className="mx-auto h-2 w-12 rounded-full bg-accent" />
        <Input
          type="number"
          inputMode="decimal"
          step="0.01"
          min="0"
          placeholder="0.00"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className="mx-auto mt-4 h-12 max-w-[200px] rounded-xl border-none bg-secondary text-center text-lg font-medium focus:bg-[#EEEAF4]"
        />
      </div>

      {/* Section: Details */}
      <div className="mb-5">
        <p className="mb-2 text-[0.72rem] font-medium uppercase tracking-wider text-muted-foreground">
          Details
        </p>
        <div className="h-0.5 w-full bg-secondary" />
      </div>

      {/* Merchant */}
      <div className="relative mb-5">
        <Label className="mb-1.5 block text-[0.78rem] font-medium text-muted-foreground">
          Merchant
        </Label>
        <Input
          ref={merchantInputRef}
          placeholder="Enter merchant name..."
          value={merchantQuery}
          onChange={(e) => handleMerchantInput(e.target.value)}
          onFocus={() => {
            if (merchantQuery.length >= 1) setMerchantOpen(true);
          }}
          onBlur={() => setTimeout(() => setMerchantOpen(false), 200)}
          onKeyDown={handleMerchantKeyDown}
          className="h-12 rounded-xl border-none bg-secondary text-[0.88rem] focus:bg-[#EEEAF4]"
        />
        {merchantOpen &&
          merchantSuggestions &&
          merchantSuggestions.length > 0 && (
            <div className="absolute left-0 right-0 top-full z-50 mt-1 rounded-xl border bg-popover p-1 shadow-md">
              {merchantSuggestions.map((s, index) => (
                <button
                  key={s.name}
                  type="button"
                  className={cn(
                    'flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left text-sm hover:bg-accent',
                    index === highlightedMerchant && 'bg-accent',
                  )}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => handleMerchantSelect(s.name)}
                >
                  <span>{s.name}</span>
                  <span className="text-xs text-muted-foreground">
                    {s.use_count}×
                  </span>
                </button>
              ))}
            </div>
          )}
      </div>

      {/* Category + Payment Method row */}
      <div className="flex flex-col gap-0 md:flex-row md:gap-4">
        {/* Category */}
        <div className="mb-5 flex-1">
          <Label className="mb-1.5 block text-[0.78rem] font-medium text-muted-foreground">
            Category
          </Label>
          <Popover open={categoryOpen} onOpenChange={setCategoryOpen}>
            <PopoverTrigger asChild>
              <button
                type="button"
                className="flex h-12 w-full items-center justify-between rounded-xl bg-secondary px-4 text-[0.88rem]"
              >
                <span
                  className={
                    selectedCategory
                      ? 'text-foreground'
                      : 'text-muted-foreground/60'
                  }
                >
                  {selectedCategory?.name ?? 'Select category...'}
                </span>
                <ChevronDown className="size-4 text-muted-foreground" />
              </button>
            </PopoverTrigger>
            <PopoverContent
              className="w-[--radix-popover-trigger-width] p-0"
              align="start"
            >
              <Command>
                <CommandList>
                  <CommandEmpty>No categories found.</CommandEmpty>
                  <CommandGroup>
                    {categories?.map((cat) => (
                      <CommandItem
                        key={cat.id}
                        value={cat.name}
                        onSelect={() => {
                          setCategoryId(cat.id);
                          setCategoryOpen(false);
                        }}
                      >
                        {cat.name}
                      </CommandItem>
                    ))}
                  </CommandGroup>
                </CommandList>
              </Command>
            </PopoverContent>
          </Popover>
        </div>

        {/* Payment Method */}
        <div className="mb-5 flex-1">
          <Label className="mb-1.5 block text-[0.78rem] font-medium text-muted-foreground">
            Payment Method
          </Label>
          <Popover open={paymentMethodOpen} onOpenChange={setPaymentMethodOpen}>
            <PopoverTrigger asChild>
              <button
                type="button"
                className="flex h-12 w-full items-center justify-between rounded-xl bg-secondary px-4 text-[0.88rem]"
              >
                <span
                  className={
                    selectedPaymentMethod
                      ? 'text-foreground'
                      : 'text-muted-foreground/60'
                  }
                >
                  {selectedPaymentMethod?.label ?? 'Select method...'}
                </span>
                <ChevronDown className="size-4 text-muted-foreground" />
              </button>
            </PopoverTrigger>
            <PopoverContent
              className="w-[--radix-popover-trigger-width] p-0"
              align="start"
            >
              <Command>
                <CommandList>
                  <CommandEmpty>No payment methods.</CommandEmpty>
                  <CommandGroup>
                    {paymentMethods?.map((pm) => (
                      <CommandItem
                        key={pm.id}
                        value={pm.label}
                        onSelect={() => {
                          setPaymentMethodId(pm.id);
                          setPaymentMethodOpen(false);
                        }}
                      >
                        {pm.label}
                      </CommandItem>
                    ))}
                  </CommandGroup>
                </CommandList>
              </Command>
            </PopoverContent>
          </Popover>
        </div>
      </div>

      {/* Date / Time / Paid By row */}
      <div className="flex flex-col gap-0 md:flex-row md:gap-4">
        {/* Date */}
        <div className="mb-5 md:flex-[0_0_40%]">
          <Label className="mb-1.5 block text-[0.78rem] font-medium text-muted-foreground">
            Date
          </Label>
          <Popover open={dateOpen} onOpenChange={setDateOpen}>
            <PopoverTrigger asChild>
              <button
                type="button"
                className="flex h-12 w-full items-center gap-2.5 rounded-xl bg-secondary px-4 text-[0.88rem]"
              >
                <CalendarIcon className="size-4 shrink-0 text-muted-foreground" />
                <span className="text-foreground">
                  {format(purchaseDate, 'MMM d, yyyy')}
                </span>
              </button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0" align="start">
              <Calendar
                mode="single"
                selected={purchaseDate}
                onSelect={(date) => {
                  if (date) {
                    setPurchaseDate(date);
                    setDateOpen(false);
                  }
                }}
                disabled={(date) => date > maxDate}
                initialFocus
              />
            </PopoverContent>
          </Popover>
        </div>

        {/* Time */}
        <div className="mb-5 md:flex-[0_0_calc(25%_-_8px)]">
          <Label className="mb-1.5 block text-[0.78rem] font-medium text-muted-foreground">
            Time
          </Label>
          <div className="flex h-12 items-center gap-2.5 rounded-xl bg-secondary px-4">
            <Clock className="size-4 shrink-0 text-muted-foreground" />
            <input
              type="time"
              value={purchaseTime}
              onChange={(e) => setPurchaseTime(e.target.value)}
              className="w-full bg-transparent text-[0.88rem] text-foreground outline-none"
            />
          </div>
        </div>

        {/* Paid By */}
        <div className="mb-5 md:flex-1">
          <Label className="mb-1.5 block text-[0.78rem] font-medium text-muted-foreground">
            Paid By
          </Label>
          <Popover open={spenderOpen} onOpenChange={setSpenderOpen}>
            <PopoverTrigger asChild>
              <button
                type="button"
                className="flex h-12 w-full items-center justify-between rounded-xl bg-secondary px-4 text-[0.88rem]"
              >
                <div className="flex items-center gap-2.5">
                  <div className="flex size-6 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-accent to-primary text-[0.58rem] font-bold text-primary-foreground">
                    {selectedMember
                      ? getInitials(selectedMember.display_name)
                      : '??'}
                  </div>
                  <span className="text-foreground">
                    {selectedMember?.display_name ?? 'Select...'}
                  </span>
                </div>
                <ChevronDown className="size-4 text-muted-foreground" />
              </button>
            </PopoverTrigger>
            <PopoverContent
              className="w-[--radix-popover-trigger-width] p-0"
              align="start"
            >
              <Command>
                <CommandList>
                  <CommandEmpty>No members.</CommandEmpty>
                  <CommandGroup>
                    {members?.map((m) => (
                      <CommandItem
                        key={m.user_id}
                        value={m.display_name}
                        onSelect={() => {
                          setSpenderId(m.user_id);
                          setSpenderOpen(false);
                        }}
                      >
                        <div className="flex items-center gap-2">
                          <div className="flex size-6 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-accent to-primary text-[0.58rem] font-bold text-primary-foreground">
                            {getInitials(m.display_name)}
                          </div>
                          {m.display_name}
                        </div>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                </CommandList>
              </Command>
            </PopoverContent>
          </Popover>
        </div>
      </div>

      {/* Section: Extras */}
      <div className="mb-5">
        <p className="mb-2 text-[0.72rem] font-medium uppercase tracking-wider text-muted-foreground">
          Extras
        </p>
        <div className="h-0.5 w-full bg-secondary" />
      </div>

      {/* Tags */}
      <div className="relative mb-5">
        <Label className="mb-1.5 block text-[0.78rem] font-medium text-muted-foreground">
          Tags
        </Label>
        <div className="flex min-h-[48px] flex-wrap items-center gap-2 rounded-xl bg-secondary px-3 py-2.5">
          {selectedTags.map((tag, i) => (
            <Badge
              key={tag.id}
              className={cn(
                'gap-1.5 rounded-full px-3 py-1.5 text-[0.8rem] font-medium',
                i % 2 === 0
                  ? 'bg-[#D4E8DD] text-[#2E4A3D] hover:bg-[#D4E8DD]'
                  : 'bg-accent text-accent-foreground hover:bg-accent',
              )}
            >
              #{tag.name}
              <button
                type="button"
                onClick={() => handleRemoveTag(tag.id)}
                className="opacity-60 transition-opacity hover:opacity-100"
              >
                <X className="size-3" />
              </button>
            </Badge>
          ))}
          <input
            ref={tagInputRef}
            type="text"
            value={tagInput}
            onChange={(e) => handleTagInput(e.target.value)}
            onKeyDown={handleTagKeyDown}
            onFocus={() => {
              if (tagInput.startsWith('#') && tagInput.length > 1) {
                setTagDropdownOpen(true);
              }
            }}
            onBlur={() => setTimeout(() => setTagDropdownOpen(false), 200)}
            placeholder={
              selectedTags.length === 0 ? 'Type # to add tags...' : ''
            }
            className="min-w-[100px] flex-1 bg-transparent text-[0.82rem] text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
          />
        </div>
        {tagDropdownOpen && filteredTags && filteredTags.length > 0 && (
          <div className="absolute left-0 right-0 top-full z-50 mt-1 rounded-xl border bg-popover p-1 shadow-md">
            {filteredTags.map((tag, index) => (
              <button
                key={tag.id}
                type="button"
                className={cn(
                  'flex w-full items-center rounded-lg px-3 py-2.5 text-left text-sm hover:bg-accent',
                  index === highlightedTag && 'bg-accent',
                )}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => handleAddTag(tag)}
              >
                #{tag.name}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Notes */}
      <div className="mb-5">
        <Label className="mb-1.5 block text-[0.78rem] font-medium text-muted-foreground">
          Notes
        </Label>
        <Textarea
          placeholder="Add notes..."
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={3}
          className="min-h-[80px] resize-none rounded-xl border-none bg-secondary text-[0.88rem] focus:bg-[#EEEAF4]"
        />
      </div>

      {/* Actions */}
      <div className="mt-7 flex flex-col-reverse items-center gap-1 border-t-0 pt-5 md:flex-row md:justify-end md:gap-3">
        <Button
          type="button"
          variant="ghost"
          onClick={onCancel}
          className="h-11 w-full rounded-[20px] text-[0.88rem] font-normal text-muted-foreground md:w-auto md:px-6"
        >
          Cancel
        </Button>
        <Button
          type="button"
          onClick={handleSubmit}
          disabled={!amount || parseFloat(amount) <= 0 || isSaving}
          className="h-11 w-full rounded-[20px] bg-primary text-[0.9rem] font-medium tracking-wide text-primary-foreground shadow-[0_2px_8px_rgba(124,111,160,0.2)] hover:bg-primary/90 md:w-auto md:px-9"
        >
          {isSaving ? 'Saving...' : 'Save Changes'}
        </Button>
      </div>

      {/* Error display */}
      {saveError && (
        <p className="mt-3 text-center text-sm text-destructive">
          {saveError.message || 'Failed to save changes. Please try again.'}
        </p>
      )}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function ExpenseDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [mode, setMode] = useState<'view' | 'edit'>('view');

  const { data: expense, isLoading, error } = useExpense(id ?? '');
  const updateExpense = useUpdateExpense();
  const deleteExpense = useDeleteExpense();

  const { data: categories } = useCategories();
  const { data: paymentMethods } = usePaymentMethods();

  const handleSave = useCallback(
    (changes: Record<string, unknown>) => {
      if (!id) return;
      updateExpense.mutate(
        { id, data: changes },
        { onSuccess: () => setMode('view') },
      );
    },
    [id, updateExpense],
  );

  const handleDelete = useCallback(() => {
    if (!id) return;
    deleteExpense.mutate(id, {
      onSuccess: () => navigate('/transactions'),
    });
  }, [id, deleteExpense, navigate]);

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <div className="size-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  if (error || !expense) {
    return (
      <div className="flex min-h-[40vh] flex-col items-center justify-center gap-3">
        <p className="text-muted-foreground">Expense not found.</p>
        <Button variant="ghost" onClick={() => navigate('/transactions')}>
          <ArrowLeft className="mr-2 size-4" />
          Back to Transactions
        </Button>
      </div>
    );
  }

  return (
    <div className="flex min-h-full justify-center px-4 py-6 md:px-10 md:py-8">
      <div className="w-full max-w-[720px]">
        {/* Top bar */}
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-lg font-medium md:hidden">
            {mode === 'view' ? 'Expense Detail' : 'Edit Expense'}
          </h1>
          <button
            onClick={() => navigate('/transactions')}
            className="hidden items-center gap-1 text-sm text-primary hover:underline md:inline-flex"
          >
            <ArrowLeft className="size-4" />
            Back to Transactions
          </button>
          <button
            onClick={() => navigate('/transactions')}
            className="flex size-10 items-center justify-center rounded-full text-foreground transition-colors hover:bg-secondary md:hidden"
            aria-label="Go back"
          >
            <ArrowLeft className="size-5" />
          </button>
        </div>

        {mode === 'view' ? (
          <ExpenseViewMode
            expense={expense}
            categories={categories}
            paymentMethods={paymentMethods}
            onEdit={() => setMode('edit')}
            onDelete={handleDelete}
            isDeleting={deleteExpense.isPending}
          />
        ) : (
          <ExpenseEditMode
            key={expense.updated_at}
            expense={expense}
            onSave={handleSave}
            onCancel={() => setMode('view')}
            isSaving={updateExpense.isPending}
            saveError={
              updateExpense.isError ? (updateExpense.error as Error) : null
            }
          />
        )}
      </div>
    </div>
  );
}
