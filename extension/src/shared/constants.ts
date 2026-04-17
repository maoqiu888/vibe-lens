import type { Domain } from "./types";

export const DOMAIN_RULES: Array<{ test: RegExp; domain: Domain }> = [
  // Books
  { test: /book\.douban\.com/, domain: "book" },
  { test: /goodreads\.com/, domain: "book" },
  { test: /amazon\.\w+\/.*\/dp\//, domain: "book" },
  { test: /weread\.qq\.com/, domain: "book" },
  { test: /read\.douban\.com/, domain: "book" },
  { test: /dangdang\.com/, domain: "book" },
  { test: /jd\.com\/.*book/, domain: "book" },

  // Movies
  { test: /movie\.douban\.com/, domain: "movie" },
  { test: /imdb\.com/, domain: "movie" },
  { test: /rottentomatoes\.com/, domain: "movie" },
  { test: /maoyan\.com/, domain: "movie" },
  { test: /piaofang\.maoyan\.com/, domain: "movie" },
  { test: /taopiaopiao\.com/, domain: "movie" },
  { test: /bilibili\.com\/bangumi/, domain: "movie" },
  { test: /iqiyi\.com/, domain: "movie" },
  { test: /v\.qq\.com/, domain: "movie" },
  { test: /youku\.com/, domain: "movie" },
  { test: /netflix\.com/, domain: "movie" },
  { test: /disneyplus\.com/, domain: "movie" },

  // Games
  { test: /store\.steampowered\.com/, domain: "game" },
  { test: /store\.epicgames\.com/, domain: "game" },
  { test: /ign\.com/, domain: "game" },
  { test: /metacritic\.com\/game/, domain: "game" },
  { test: /taptap\.cn/, domain: "game" },
  { test: /taptap\.io/, domain: "game" },
  { test: /nintendo\.com/, domain: "game" },
  { test: /playstation\.com/, domain: "game" },
  { test: /xbox\.com/, domain: "game" },

  // Music
  { test: /music\.163\.com/, domain: "music" },
  { test: /y\.qq\.com/, domain: "music" },
  { test: /spotify\.com/, domain: "music" },
  { test: /music\.apple\.com/, domain: "music" },
  { test: /bandcamp\.com/, domain: "music" },
  { test: /soundcloud\.com/, domain: "music" },
  { test: /kugou\.com/, domain: "music" },
  { test: /kuwo\.cn/, domain: "music" },
];

export const MIN_TEXT_LEN = 2;
export const MAX_TEXT_LEN = 200;

/** Default domain when URL doesn't match any known site */
export const DEFAULT_DOMAIN: Domain = "movie";
