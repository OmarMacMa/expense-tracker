export function getRelativeDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const expenseDay = new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
  );
  const diffDays = Math.floor(
    (today.getTime() - expenseDay.getTime()) / (1000 * 60 * 60 * 24),
  );

  if (diffDays === 0) return formatTime(dateStr);
  return formatShortDate(dateStr);
}

export function getDateGroup(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const expenseDay = new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
  );
  const diffDays = Math.floor(
    (today.getTime() - expenseDay.getTime()) / (1000 * 60 * 60 * 24),
  );

  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays <= 7) return 'This Week';
  return 'Earlier';
}

export function formatCurrency(
  amount: string | number,
  currency: string = 'USD',
): string {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
  }).format(num);
}

export function getCurrencySymbol(currency: string = 'USD'): string {
  return (
    new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    })
      .formatToParts(0)
      .find((part) => part.type === 'currency')?.value ?? '$'
  );
}

function formatTime(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

function formatShortDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

const CATEGORY_COLORS = [
  {
    bg: 'bg-[var(--sage-container)]',
    text: 'text-[#2E4A3D]',
    circleBg: 'bg-[var(--sage-container)]',
    circleText: 'text-[#2E4A3D]',
  },
  {
    bg: 'bg-[var(--dusty-rose-container)]',
    text: 'text-[#4A3346]',
    circleBg: 'bg-[var(--dusty-rose-container)]',
    circleText: 'text-[#4A3346]',
  },
  {
    bg: 'bg-[var(--lavender-container)]',
    text: 'text-[#32264E]',
    circleBg: 'bg-[var(--lavender-container)]',
    circleText: 'text-[#32264E]',
  },
  {
    bg: 'bg-[var(--butter-container)]',
    text: 'text-[#4A4220]',
    circleBg: 'bg-[var(--butter-container)]',
    circleText: 'text-[#4A4220]',
  },
];

export function getCategoryColor(categoryName: string) {
  let hash = 0;
  for (let i = 0; i < categoryName.length; i++) {
    hash = categoryName.charCodeAt(i) + ((hash << 5) - hash);
  }
  return CATEGORY_COLORS[Math.abs(hash) % CATEGORY_COLORS.length];
}
