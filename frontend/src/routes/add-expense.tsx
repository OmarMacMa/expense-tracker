import { useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router';
import {
  ArrowLeft,
  CalendarIcon,
  Clock,
  X,
  ChevronDown,
  Plus,
} from 'lucide-react';
import { format } from 'date-fns';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
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
import { useAuth } from '@/hooks/useAuth';
import { useCurrency } from '@/hooks/useCurrency';
import { useCreateExpense } from '@/hooks/useExpenses';
import { useMerchantSuggest, useMerchantCategory } from '@/hooks/useMerchants';
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

export default function AddExpense() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { format: formatAmount } = useCurrency();
  const createExpense = useCreateExpense();

  // Form state
  const [amount, setAmount] = useState('');
  const [merchant, setMerchant] = useState('');
  const [merchantQuery, setMerchantQuery] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [categorySuggested, setCategorySuggested] = useState(false);
  const [suggestedFromMerchant, setSuggestedFromMerchant] = useState('');
  const [purchaseDate, setPurchaseDate] = useState<Date>(new Date());
  const [purchaseTime, setPurchaseTime] = useState(formatTimeValue(new Date()));
  const [spenderId, setSpenderId] = useState(() => user?.id ?? '');
  const [paymentMethodId, setPaymentMethodId] = useState('');
  const [selectedTags, setSelectedTags] = useState<
    { id: string; name: string }[]
  >([]);
  const [tagInput, setTagInput] = useState('');
  const [notes, setNotes] = useState('');
  // Tracks which merchant's category suggestion was already applied
  const [lastSuggestedMerchant, setLastSuggestedMerchant] = useState('');

  // Dropdown open states
  const [merchantOpen, setMerchantOpen] = useState(false);
  const [categoryOpen, setCategoryOpen] = useState(false);
  const [dateOpen, setDateOpen] = useState(false);
  const [spenderOpen, setSpenderOpen] = useState(false);
  const [paymentMethodOpen, setPaymentMethodOpen] = useState(false);
  const [tagDropdownOpen, setTagDropdownOpen] = useState(false);

  // Arrow-key highlight indices for custom dropdowns
  const [highlightedMerchant, setHighlightedMerchant] = useState(-1);
  const [highlightedTag, setHighlightedTag] = useState(-1);

  // Refs
  const merchantInputRef = useRef<HTMLInputElement>(null);
  const tagInputRef = useRef<HTMLInputElement>(null);

  // Data hooks
  const { data: merchantSuggestions } = useMerchantSuggest(merchantQuery);
  const { data: merchantCategory } = useMerchantCategory(merchant);
  const { data: categories } = useCategories();
  const { data: paymentMethods } = usePaymentMethods();
  const { data: tags } = useTags();
  const { data: members } = useMembers();

  // Derive spenderId from user if not yet set (handles async user load)
  const effectiveSpenderId = spenderId || user?.id || '';

  // Apply merchant category suggestion when data arrives for a new merchant
  if (
    merchantCategory?.last_category_id &&
    merchant &&
    merchant !== lastSuggestedMerchant &&
    !categoryId
  ) {
    setCategoryId(merchantCategory.last_category_id);
    setCategorySuggested(true);
    setSuggestedFromMerchant(merchant);
    setLastSuggestedMerchant(merchant);
  }

  const handleMerchantInput = useCallback((value: string) => {
    setMerchantQuery(value);
    setMerchantOpen(value.length >= 1);
    setHighlightedMerchant(-1);
  }, []);

  const handleMerchantSelect = useCallback((name: string) => {
    setMerchant(name);
    setMerchantQuery(name);
    setMerchantOpen(false);
    setHighlightedMerchant(-1);
    // Always reset category suggestion for proper re-triggering
    setCategoryId('');
    setCategorySuggested(false);
    setSuggestedFromMerchant('');
    setLastSuggestedMerchant('');
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

  const handleCategorySelect = useCallback((id: string) => {
    setCategoryId(id);
    setCategorySuggested(false);
    setSuggestedFromMerchant('');
    setCategoryOpen(false);
  }, []);

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

  const commitTagFromInput = useCallback(
    (input: string) => {
      const normalizedName = input.replace(/^#/, '').toLowerCase().trim();
      if (!normalizedName) return;

      const existingTag = tags?.find((t) => t.name === normalizedName);
      if (existingTag) {
        handleAddTag(existingTag);
      } else {
        handleAddTag({
          id: `new-${normalizedName}`,
          name: normalizedName,
        });
      }
    },
    [tags, handleAddTag],
  );

  const handleTagInput = useCallback(
    (value: string) => {
      // Treat comma as a tag separator (mobile-friendly)
      if (value.endsWith(',')) {
        const stripped = value.slice(0, -1);
        if (stripped.trim()) {
          commitTagFromInput(stripped);
        }
        return;
      }

      setTagInput(value);
      setHighlightedTag(-1);
      if (value.startsWith('#') && value.length > 1) {
        setTagDropdownOpen(true);
      } else if (value.length === 0) {
        setTagDropdownOpen(false);
      }
    },
    [commitTagFromInput],
  );

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
        commitTagFromInput(tagInput);
      }
      if (e.key === 'Backspace' && tagInput === '' && selectedTags.length > 0) {
        setSelectedTags((prev) => prev.slice(0, -1));
      }
    },
    [
      tagInput,
      tags,
      selectedTags,
      commitTagFromInput,
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

  const handleSubmit = useCallback(async () => {
    if (!amount || parseFloat(amount) <= 0) return;

    const payload: Record<string, unknown> = {
      merchant: merchant.trim(),
      amount: parseFloat(amount),
      purchase_datetime: buildPurchaseDatetime(),
      spender_id: effectiveSpenderId,
      category_id: categoryId || null,
      payment_method_id: paymentMethodId || null,
      notes: notes.trim() || null,
      tags: selectedTags.map((t) => t.name),
    };

    try {
      await createExpense.mutateAsync(payload);
      navigate('/transactions');
    } catch {
      // Error handled by mutation state
    }
  }, [
    amount,
    merchant,
    buildPurchaseDatetime,
    effectiveSpenderId,
    notes,
    categoryId,
    paymentMethodId,
    selectedTags,
    createExpense,
    navigate,
  ]);

  const selectedCategory = categories?.find((c) => c.id === categoryId);
  const selectedMember = members?.find((m) => m.user_id === effectiveSpenderId);
  const selectedPaymentMethod = paymentMethods?.find(
    (pm) => pm.id === paymentMethodId,
  );

  const filteredTags = tags?.filter((t) => {
    const query = tagInput.replace(/^#/, '').toLowerCase();
    return t.name.includes(query) && !selectedTags.find((st) => st.id === t.id);
  });

  // No future dates
  const maxDate = new Date();

  return (
    <div className="flex min-h-full justify-center px-4 py-6 md:px-10 md:py-8">
      <div className="w-full max-w-[720px]">
        {/* Top bar */}
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-lg font-medium md:hidden">New Expense</h1>
          <button
            onClick={() => navigate(-1)}
            className="hidden items-center gap-1 text-sm text-primary hover:underline md:inline-flex"
          >
            <ArrowLeft className="size-4" />
            Back to Home
          </button>
          <button
            onClick={() => navigate(-1)}
            className="flex size-10 items-center justify-center rounded-full text-foreground transition-colors hover:bg-secondary md:hidden"
            aria-label="Go back"
          >
            <ArrowLeft className="size-5" />
          </button>
        </div>

        {/* Form card */}
        <div className="rounded-2xl bg-card p-6 shadow-[var(--shadow-card)] md:p-9">
          {/* Hero amount */}
          <div className="pb-7 pt-1 text-center">
            <p className="mb-1.5 text-[0.72rem] font-medium uppercase tracking-wider text-muted-foreground">
              Amount <span className="text-red-500">*</span>
            </p>
            <div className="mb-3 text-[2.5rem] font-bold leading-tight text-foreground md:text-[2.5rem]">
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
              Merchant <span className="text-red-500">*</span>
            </Label>
            <Input
              ref={merchantInputRef}
              placeholder="Enter merchant name..."
              value={merchantQuery}
              onChange={(e) => handleMerchantInput(e.target.value)}
              onFocus={() => {
                if (merchantQuery.length >= 1) setMerchantOpen(true);
              }}
              onBlur={() => {
                setTimeout(() => setMerchantOpen(false), 200);
                setMerchant(merchantQuery);
              }}
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
            <p className="mt-1.5 text-[0.72rem] text-muted-foreground">
              Suggestions appear from history
            </p>
          </div>

          {/* Category + Payment Method row (side by side on desktop) */}
          <div className="flex flex-col gap-0 md:flex-row md:gap-4">
            {/* Category */}
            <div className="mb-5 flex-1">
              <Label className="mb-1.5 block text-[0.78rem] font-medium text-muted-foreground">
                Category <span className="text-red-500">*</span>
              </Label>
              <Popover open={categoryOpen} onOpenChange={setCategoryOpen}>
                <PopoverTrigger asChild>
                  <button
                    type="button"
                    className={cn(
                      'flex h-12 w-full items-center justify-between rounded-xl px-4 text-[0.88rem]',
                      categorySuggested ? 'bg-[#D4E8DD]' : 'bg-secondary',
                    )}
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
                            onSelect={() => handleCategorySelect(cat.id)}
                          >
                            {cat.name}
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
              {categorySuggested && suggestedFromMerchant && (
                <p className="mt-1.5 text-[0.72rem] text-primary">
                  Suggested from {suggestedFromMerchant}
                </p>
              )}
            </div>

            {/* Payment Method */}
            <div className="mb-5 flex-1">
              <Label className="mb-1.5 block text-[0.78rem] font-medium text-muted-foreground">
                Payment Method
              </Label>
              <Popover
                open={paymentMethodOpen}
                onOpenChange={setPaymentMethodOpen}
              >
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
                Date <span className="text-red-500">*</span>
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
                Paid By <span className="text-red-500">*</span>
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
                onBlur={() =>
                  setTimeout(() => {
                    setTagDropdownOpen(false);
                    if (tagInput.trim()) {
                      commitTagFromInput(tagInput);
                    }
                  }, 200)
                }
                placeholder={
                  selectedTags.length === 0
                    ? 'Type # to add tags (comma to add)...'
                    : ''
                }
                className="min-w-[100px] flex-1 bg-transparent text-[0.82rem] text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
              />
              {tagInput.replace(/^#/, '').trim() && (
                <button
                  type="button"
                  aria-label="Add tag"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => commitTagFromInput(tagInput)}
                  className="ml-1 flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition-colors hover:bg-primary/90"
                >
                  <Plus className="size-3.5" />
                </button>
              )}
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
              onClick={() => navigate(-1)}
              className="h-11 w-full rounded-[20px] text-[0.88rem] font-normal text-muted-foreground md:w-auto md:px-6"
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={handleSubmit}
              disabled={
                !amount || parseFloat(amount) <= 0 || createExpense.isPending
              }
              className="h-11 w-full rounded-[20px] bg-primary text-[0.9rem] font-medium tracking-wide text-primary-foreground shadow-[0_2px_8px_rgba(124,111,160,0.2)] hover:bg-primary/90 md:w-auto md:px-9"
            >
              {createExpense.isPending ? 'Saving...' : 'Save Expense'}
            </Button>
          </div>

          {/* Error display */}
          {createExpense.isError && (
            <p className="mt-3 text-center text-sm text-destructive">
              {(createExpense.error as Error)?.message ||
                'Failed to save expense. Please try again.'}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
