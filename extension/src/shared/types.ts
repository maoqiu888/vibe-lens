export type Domain = "book" | "game" | "movie" | "music";

export interface MatchedTag {
  tag_id: number;
  name: string;
  weight: number;
}

export interface AnalyzeResult {
  match_score: number;
  summary: string;
  matched_tags: MatchedTag[];
  text_hash: string;
  cache_hit: boolean;
}

export interface CardOption {
  tag_id: number;
  name: string;
  tier: number;
  tagline: string;
  examples: string[];
}

export interface CategoryCard {
  category: string;
  category_label: string;
  options: CardOption[];
}

export interface ColdStartCardsResult {
  cards: CategoryCard[];
}

export interface ColdStartSubmitResult {
  status: string;
  profile_initialized: boolean;
  already_initialized?: boolean;
}

export interface RadarDimension {
  category: string;
  category_label: string;
  score: number;
  dominant_tag: { tag_id: number; name: string };
}

export interface RadarResult {
  user_id: number;
  dimensions: RadarDimension[];
  total_analyze_count: number;
  total_action_count: number;
}

export type Msg =
  | { type: "ANALYZE"; payload: { text: string; domain: Domain; pageTitle: string; pageUrl: string } }
  | { type: "ACTION"; payload: { action: "star" | "bomb"; matchedTagIds: number[]; textHash?: string } }
  | { type: "COLD_START_GET_CARDS" }
  | { type: "COLD_START_SUBMIT"; payload: { selectedTagIds: number[] } }
  | { type: "GET_RADAR" };

export type MsgResponse<T> =
  | { ok: true; data: T }
  | { ok: false; error: { code: string; message: string } };
