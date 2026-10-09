export interface AmountRange {
  min_amount?: string;
  max_amount?: string;
}

function canonicalDecimal(value: string): string {
  const [whole, fraction = ''] = value.split('.');
  return `${whole.replace(/^0+(?=\d)/, '') || '0'}.${fraction}`;
}

function compareDecimals(left: string, right: string): number {
  const [a, af] = canonicalDecimal(left).split('.');
  const [b, bf] = canonicalDecimal(right).split('.');
  if (a.length !== b.length) return a.length < b.length ? -1 : 1;
  if (a !== b) return a < b ? -1 : 1;
  const width = Math.max(af.length, bf.length);
  const ap = af.padEnd(width, '0');
  const bp = bf.padEnd(width, '0');
  return ap === bp ? 0 : ap < bp ? -1 : 1;
}

export function parseAmountRange(
  minimum: string,
  maximum: string,
  decimalSeparator = '.',
): { range: AmountRange; error?: string } {
  const values = [minimum, maximum].map((value) =>
    value.trim().replace(decimalSeparator, '.'),
  );
  if (
    values.some(
      (value) => value !== '' && !/^(?:\d+(?:\.\d+)?|\.\d+)$/.test(value),
    )
  ) {
    return {
      range: {},
      error: 'Enter finite, nonnegative amounts, or leave a bound blank.',
    };
  }
  const [min, max] = values;
  if (min && max && compareDecimals(min, max) > 0) {
    return { range: {}, error: 'Minimum must not exceed maximum.' };
  }
  return {
    range: {
      min_amount: min || undefined,
      max_amount: max || undefined,
    },
  };
}
