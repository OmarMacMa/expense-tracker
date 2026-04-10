export interface User {
  id: string;
  email: string;
  display_name: string;
  avatar_url: string | null;
}

export interface Space {
  id: string;
  name: string;
  currency_code: string;
  timezone: string;
  default_tax_pct: number | null;
  created_at: string;
}

export interface AuthMeResponse {
  id: string;
  email: string;
  display_name: string;
  avatar_url: string | null;
  spaces: { id: string; name: string }[];
}

export interface SpaceMember {
  id: string;
  user_id: string;
  display_name: string;
  email: string;
  avatar_url: string | null;
  joined_at: string;
}

export interface Category {
  id: string;
  name: string;
  normalized_name: string;
  is_system: boolean;
  created_at: string;
}

export interface PaymentMethod {
  id: string;
  label: string;
  is_system: boolean;
  owner_id: string | null;
  created_at: string;
}

export interface Tag {
  id: string;
  name: string;
  created_at: string;
}

export interface ExpenseLine {
  id: string;
  amount: string;
  category_id: string;
  category_name: string | null;
  line_order: number;
  tags: { id: string; name: string }[];
}

export interface Expense {
  id: string;
  space_id: string;
  merchant: string;
  purchase_datetime: string;
  total_amount: string;
  spender: { id: string; display_name: string; email: string };
  payment_method_id: string | null;
  notes: string | null;
  status: string;
  lines: ExpenseLine[];
  created_at: string;
  updated_at: string;
}

export interface ExpenseListResponse {
  data: Expense[];
  next_cursor: string | null;
}

export interface LimitProgress {
  id: string;
  name: string;
  timeframe: string;
  threshold_amount: string;
  warning_pct: string;
  filters: {
    id: string;
    filter_type: string;
    filter_value: string;
    filter_display_name: string;
  }[];
  created_at: string;
  spent: string;
  progress: string;
  days_remaining: number;
  status: 'ok' | 'warning' | 'critical' | 'exceeded';
}

export interface InsightsSummary {
  total_spent: string;
  delta_pct: number | null;
  period_label: string;
  window_start: string;
  window_end: string;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}
