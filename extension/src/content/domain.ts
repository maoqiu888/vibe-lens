import { DOMAIN_RULES } from "../shared/constants";
import type { Domain } from "../shared/types";

export function detectDomain(url: string): Domain | null {
  return DOMAIN_RULES.find((r) => r.test.test(url))?.domain ?? null;
}
