/**
 * Checks if a URL is safe for redirection (internal only).
 * Prevents Open Redirect vulnerabilities.
 *
 * @param url The URL to check
 * @returns true if the URL starts with '/' and does NOT start with '//'
 */
export function isSafeRedirectUrl(url: string | null | undefined): boolean {
  if (!url) return false;
  return url.startsWith('/') && !url.startsWith('//');
}
