import type { Domain } from "./types";

export const DOMAIN_RULES: Array<{ test: RegExp; domain: Domain }> = [
  { test: /^https?:\/\/book\.douban\.com\//, domain: "book" },
  { test: /^https?:\/\/movie\.douban\.com\//, domain: "movie" },
  { test: /^https?:\/\/store\.steampowered\.com\//, domain: "game" },
  { test: /^https?:\/\/music\.163\.com\//, domain: "music" },
];

export const MIN_TEXT_LEN = 2;
export const MAX_TEXT_LEN = 200;
