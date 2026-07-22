const MASTER_CANONICAL_RE = /^\d{10}$/;
const SUBORDER_UI_RE = /^(\d{5})-(\d{5})-([1-9]\d*)$/;
const MASTER_UI_RE = /^(\d{4})-(\d{5})$/;

type CanonicalMasterOrderNumber = string & { readonly __brand: 'CanonicalMasterOrderNumber' };
type CanonicalSubOrderNumber = string & { readonly __brand: 'CanonicalSubOrderNumber' };

export function isCanonicalMasterOrderNumber(value: unknown): value is CanonicalMasterOrderNumber {
  if (typeof value !== 'string' || !MASTER_CANONICAL_RE.test(value)) {
    return false;
  }
  const sequence = Number.parseInt(value.slice(-3), 10);
  return sequence >= 1 && sequence <= 999;
}

export function isCanonicalSubOrderNumber(value: unknown): value is CanonicalSubOrderNumber {
  if (typeof value !== 'string' || !/^\d+$/.test(value) || value.length <= 10) {
    return false;
  }
  return (
    isCanonicalMasterOrderNumber(value.slice(0, 10)) && Number.parseInt(value.slice(10), 10) >= 1
  );
}

export function formatOrderNumber(
  value: string | null | undefined,
  options?: { kind?: 'auto' | 'master' | 'suborder' }
): string {
  if (!value) {
    return '';
  }

  const kind = options?.kind ?? 'auto';

  if ((kind === 'auto' || kind === 'suborder') && isCanonicalSubOrderNumber(value)) {
    return `${value.slice(0, 5)}-${value.slice(5, 10)}-${value.slice(10)}`;
  }

  if ((kind === 'auto' || kind === 'master') && isCanonicalMasterOrderNumber(value)) {
    return `${value.slice(1, 5)}-${value.slice(5, 10)}`;
  }

  return value;
}

export function normalizeOrderNumberInput(value: string): string | null {
  const compact = value.trim().replace(/\s+/g, '');

  if (!compact || /[^\d-]/.test(compact)) {
    return null;
  }

  if (isCanonicalMasterOrderNumber(compact) || isCanonicalSubOrderNumber(compact)) {
    return compact;
  }

  const masterMatch = compact.match(MASTER_UI_RE);
  if (masterMatch) {
    const body = masterMatch[2];
    const sequence = Number.parseInt(body.slice(-3), 10);
    if (sequence < 1 || sequence > 999) {
      return null;
    }
    return `${masterMatch[1]}${body}`;
  }

  const suborderMatch = compact.match(SUBORDER_UI_RE);
  if (suborderMatch) {
    const body = suborderMatch[2];
    const sequence = Number.parseInt(body.slice(-3), 10);
    if (sequence < 1 || sequence > 999) {
      return null;
    }
    return `${suborderMatch[1]}${body}${suborderMatch[3]}`;
  }

  return null;
}
