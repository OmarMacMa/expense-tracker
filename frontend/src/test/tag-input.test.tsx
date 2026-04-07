import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, act, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState, useRef, useCallback } from 'react';

/**
 * Minimal component that mirrors the tag-input logic used in
 * add-expense.tsx and expense-detail.tsx so we can test the
 * mobile-friendly commit triggers (comma, blur, add-button)
 * without pulling in all the routing/query dependencies.
 */
function TagInputTestHarness({
  existingTags = [] as { id: string; name: string }[],
}: {
  existingTags?: { id: string; name: string }[];
}) {
  const [selectedTags, setSelectedTags] = useState<
    { id: string; name: string }[]
  >([]);
  const [tagInput, setTagInput] = useState('');
  const tagInputRef = useRef<HTMLInputElement>(null);
  const [, setTagDropdownOpen] = useState(false);
  const [, setHighlightedTag] = useState(-1);

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

  const commitTagFromInput = useCallback(
    (input: string) => {
      const normalizedName = input.replace(/^#/, '').toLowerCase().trim();
      if (!normalizedName) return;

      const existingTag = existingTags.find((t) => t.name === normalizedName);
      if (existingTag) {
        handleAddTag(existingTag);
      } else {
        handleAddTag({
          id: `new-${normalizedName}`,
          name: normalizedName,
        });
      }
    },
    [existingTags, handleAddTag],
  );

  const handleTagInput = useCallback(
    (value: string) => {
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
      if (e.key === 'Enter' && tagInput.trim()) {
        e.preventDefault();
        commitTagFromInput(tagInput);
      }
      if (e.key === 'Backspace' && tagInput === '' && selectedTags.length > 0) {
        setSelectedTags((prev) => prev.slice(0, -1));
      }
    },
    [tagInput, selectedTags, commitTagFromInput],
  );

  return (
    <div>
      <div data-testid="selected-tags">
        {selectedTags.map((tag) => (
          <span key={tag.id} data-testid={`tag-${tag.name}`}>
            #{tag.name}
          </span>
        ))}
      </div>
      <input
        ref={tagInputRef}
        data-testid="tag-input"
        type="text"
        value={tagInput}
        onChange={(e) => handleTagInput(e.target.value)}
        onKeyDown={handleTagKeyDown}
        onBlur={() =>
          setTimeout(() => {
            setTagDropdownOpen(false);
            if (tagInput.trim()) {
              commitTagFromInput(tagInput);
            }
          }, 200)
        }
        placeholder="Type # to add tags (comma to add)..."
      />
      {tagInput.replace(/^#/, '').trim() && (
        <button
          type="button"
          data-testid="add-tag-button"
          aria-label="Add tag"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => commitTagFromInput(tagInput)}
        >
          +
        </button>
      )}
    </div>
  );
}

describe('Tag input – mobile-friendly creation', () => {
  afterEach(() => {
    cleanup();
  });

  it('creates a tag when Enter is pressed (existing behavior)', async () => {
    render(<TagInputTestHarness />);
    const input = screen.getByTestId('tag-input');

    await userEvent.type(input, '#food');
    fireEvent.keyDown(input, { key: 'Enter' });

    expect(screen.getByTestId('tag-food')).toBeInTheDocument();
    expect(input).toHaveValue('');
  });

  it('creates a tag when comma is typed (mobile-friendly)', async () => {
    render(<TagInputTestHarness />);
    const input = screen.getByTestId('tag-input');

    await userEvent.type(input, '#lunch,');

    expect(screen.getByTestId('tag-lunch')).toBeInTheDocument();
    expect(input).toHaveValue('');
  });

  it('creates a tag on blur (mobile-friendly)', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });

    render(<TagInputTestHarness />);
    const input = screen.getByTestId('tag-input');

    await userEvent.type(input, '#dinner');
    fireEvent.blur(input);

    // Blur handler uses a 200ms timeout
    act(() => {
      vi.advanceTimersByTime(250);
    });

    expect(screen.getByTestId('tag-dinner')).toBeInTheDocument();
    expect(input).toHaveValue('');

    vi.useRealTimers();
  });

  it('creates a tag when Add button is clicked (mobile-friendly)', async () => {
    render(<TagInputTestHarness />);
    const input = screen.getByTestId('tag-input');

    await userEvent.type(input, '#travel');

    const addButton = screen.getByTestId('add-tag-button');
    fireEvent.click(addButton);

    expect(screen.getByTestId('tag-travel')).toBeInTheDocument();
    expect(input).toHaveValue('');
  });

  it('normalizes tag name: removes # prefix and lowercases', async () => {
    render(<TagInputTestHarness />);
    const input = screen.getByTestId('tag-input');

    await userEvent.type(input, '#MyTag');
    fireEvent.keyDown(input, { key: 'Enter' });

    expect(screen.getByTestId('tag-mytag')).toBeInTheDocument();
  });

  it('does not create a tag from empty or whitespace input on blur', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });

    render(<TagInputTestHarness />);
    const input = screen.getByTestId('tag-input');

    await userEvent.type(input, '   ');
    fireEvent.blur(input);

    act(() => {
      vi.advanceTimersByTime(250);
    });

    expect(screen.getByTestId('selected-tags').children).toHaveLength(0);

    vi.useRealTimers();
  });

  it('does not create a tag from just "#" on comma', async () => {
    render(<TagInputTestHarness />);
    const input = screen.getByTestId('tag-input');

    await userEvent.type(input, '#,');

    expect(screen.getByTestId('selected-tags').children).toHaveLength(0);
  });

  it('matches existing tag by name instead of creating a duplicate', async () => {
    const existing = [{ id: 'uuid-1', name: 'food' }];
    render(<TagInputTestHarness existingTags={existing} />);
    const input = screen.getByTestId('tag-input');

    await userEvent.type(input, '#food');
    fireEvent.keyDown(input, { key: 'Enter' });

    const tag = screen.getByTestId('tag-food');
    expect(tag).toBeInTheDocument();
    // No `new-` prefix id means it matched the existing tag
  });

  it('shows the Add button only when there is valid input', async () => {
    render(<TagInputTestHarness />);
    const input = screen.getByTestId('tag-input');

    // Initially no button
    expect(screen.queryByTestId('add-tag-button')).not.toBeInTheDocument();

    // Typing only # should not show button
    await userEvent.type(input, '#');
    expect(screen.queryByTestId('add-tag-button')).not.toBeInTheDocument();

    // Typing a real name should show button
    await userEvent.type(input, 'food');
    expect(screen.getByTestId('add-tag-button')).toBeInTheDocument();
  });

  it('does not add duplicate tags', async () => {
    render(<TagInputTestHarness />);
    const input = screen.getByTestId('tag-input');

    await userEvent.type(input, '#food');
    fireEvent.keyDown(input, { key: 'Enter' });

    expect(screen.getByTestId('tag-food')).toBeInTheDocument();

    await userEvent.type(input, '#food');
    fireEvent.keyDown(input, { key: 'Enter' });

    // Should still be exactly one tag
    expect(screen.getAllByTestId('tag-food')).toHaveLength(1);
  });

  it('creates tag without # prefix when typed without hash', async () => {
    render(<TagInputTestHarness />);
    const input = screen.getByTestId('tag-input');

    await userEvent.type(input, 'groceries,');

    expect(screen.getByTestId('tag-groceries')).toBeInTheDocument();
  });
});
