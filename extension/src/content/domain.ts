import { DEFAULT_DOMAIN, DOMAIN_RULES } from "../shared/constants";
import type { Domain } from "../shared/types";

/**
 * Detect content domain from URL. Returns a known domain if URL matches
 * any rule, otherwise returns the default domain.
 */
export function detectDomain(url: string): Domain {
  return DOMAIN_RULES.find((r) => r.test.test(url))?.domain ?? DEFAULT_DOMAIN;
}

/**
 * Check if the URL matches a known content site.
 * When false, UI may show a domain selector to let the user override.
 */
export function isKnownSite(url: string): boolean {
  return DOMAIN_RULES.some((r) => r.test.test(url));
}
