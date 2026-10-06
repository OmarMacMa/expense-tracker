import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import ts from 'typescript';

async function loadTypeScriptModule(path) {
  const source = await readFile(new URL(path, import.meta.url), 'utf8');
  const { outputText, diagnostics } = ts.transpileModule(source, {
    fileName: path,
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
    },
    reportDiagnostics: true,
  });
  const errors = diagnostics.filter(
    (diagnostic) => diagnostic.category === ts.DiagnosticCategory.Error,
  );
  assert.equal(
    errors.length,
    0,
    errors
      .map((error) => ts.flattenDiagnosticMessageText(error.messageText, '\n'))
      .join('\n'),
  );
  return import(
    `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`
  );
}

const { canonicalFilters, filtersFromParams, filtersToParams } =
  await loadTypeScriptModule('../src/lib/expenseFilters.ts');
const { api } = await loadTypeScriptModule('../src/lib/api-client.ts');

test('repeated keys round trip without comma-splitting merchant names', () => {
  const filters = {
    period: 'this_month',
    category: ['third', 'first', 'second'],
    spender: ['user-id'],
    merchant: ['Cafe, North', 'Shop %'],
    tag: ['#Red', ' blue ', 'red'],
    payment_method: ['visa', 'debit'],
    status: 'confirmed',
  };
  const params = filtersToParams(filters);
  assert.deepEqual(params.getAll('category'), ['first', 'second', 'third']);
  assert.deepEqual(params.getAll('merchant'), ['Cafe, North', 'Shop %']);
  assert.deepEqual(params.getAll('tag'), ['blue', 'red']);
  assert.deepEqual(filtersFromParams(params), canonicalFilters(filters));
});

test('single values remain compatible; empty dimensions omitted; scalar month/status retained', () => {
  assert.deepEqual(
    filtersFromParams(
      new URLSearchParams(
        'category=one&merchant=Cafe%2C+North&month=2026-01&status=confirmed',
      ),
    ),
    {
      month: '2026-01',
      status: 'confirmed',
      category: ['one'],
      merchant: ['Cafe, North'],
    },
  );
  assert.equal(
    filtersToParams({ category: [], tag: [], search: '' }).toString(),
    '',
  );
});

test('query cache identities are order-independent, duplicate-free, and dimension-sensitive', () => {
  const key = (filters) =>
    JSON.stringify(['expenses', 'space', canonicalFilters(filters)]);
  assert.equal(
    key({ category: ['b', 'a', 'a'], tag: ['red'], spender: ['user'] }),
    key({ spender: ['user'], tag: ['#RED'], category: ['a', 'b'] }),
  );
  assert.notEqual(
    key({ category: ['a'] }),
    key({ category: ['a'], spender: ['user'] }),
  );
  assert.notEqual(
    key({ category: ['a'] }),
    key({ category: ['a'], status: 'confirmed' }),
  );
  assert.equal(key({ category: [] }), key({}));
});

test('Insights omits unsupported search from parsed, cached and outgoing context', () => {
  const params = new URLSearchParams(
    'period=this_month&category=one&category=two&search=hidden',
  );
  const insights = filtersFromParams(params, 'insights');
  assert.deepEqual(insights, {
    period: 'this_month',
    category: ['one', 'two'],
  });
  assert.equal(filtersToParams(insights).has('search'), false);
  assert.deepEqual(
    canonicalFilters({ ...insights, search: 'hidden' }, 'insights'),
    insights,
  );
  assert.equal(filtersFromParams(params).search, 'hidden');
});

test('API client appends repeated keys and keeps pagination/scalar callers intact', async () => {
  globalThis.window = {
    location: { origin: 'http://localhost:5181', pathname: '/insights' },
  };
  const previousFetch = globalThis.fetch;
  const requests = [];
  globalThis.fetch = async (url) => {
    requests.push(new URL(url));
    return new Response(JSON.stringify({ data: [] }), { status: 200 });
  };
  try {
    const params = filtersToParams({
      category: ['a', 'b'],
      merchant: ['Cafe, North'],
    });
    params.set('cursor', 'cursor-value');
    await api.get('/spaces/space/expenses', params);
    assert.deepEqual(requests[0].searchParams.getAll('category'), ['a', 'b']);
    assert.deepEqual(requests[0].searchParams.getAll('merchant'), [
      'Cafe, North',
    ]);
    assert.equal(requests[0].searchParams.get('cursor'), 'cursor-value');
    await api.get('/spaces/space/expenses', { category: 'a' });
    assert.deepEqual(requests[1].searchParams.getAll('category'), ['a']);
  } finally {
    globalThis.fetch = previousFetch;
    delete globalThis.window;
  }
});
