/**
 * Tag validation rules mirrored from backend/app/services/tag.py.
 * Keep these constants in sync with TAG_PATTERN and the schema length cap.
 */

export const TAG_PATTERN = /^[a-zA-Z0-9_-]+$/;
export const TAG_MAX_LENGTH = 50;

/**
 * Validate a normalized tag name (no `#` prefix, lowercase, trimmed).
 * Returns null if valid, or a human-readable error message.
 */
export function validateTagName(name: string): string | null {
  if (!name) return null;
  if (name.length > TAG_MAX_LENGTH) {
    return `Tags can be up to ${TAG_MAX_LENGTH} characters`;
  }
  if (!TAG_PATTERN.test(name)) {
    return 'Tags can only contain letters, numbers, hyphens, and underscores';
  }
  return null;
}
