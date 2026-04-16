export type Domain = "book" | "game" | "movie" | "music";

export interface MatchedTag {
  tag_id: number;
  name: string;
  weight: number;
}

export type Verdict = "追" | "看心情" | "跳过";

export interface AnalyzeResult {
  match_score: number;
  summary: string;
  roast: string;
  verdict: Verdict;
  reasons: string[];
  matched_tags: MatchedTag[];
  text_hash: string;
  cache_hit: boolean;
  interaction_count: number;
  level: number;
  level_title: string;
  level_emoji: string;
  next_level_at: number;
  level_up: boolean;
  ui_stage: "welcome" | "learning" | "early" | "stable";
}

export interface ActionResult {
  status: string;
  updated_tags: number;
  interaction_count: number;
  level: number;
  level_title: string;
  level_emoji: string;
  next_level_at: number;
  level_up: boolean;
}

export interface RadarDimension {
  category: string;
  category_label: string;
  score: number;
  dominant_tag: { tag_id: number; name: string };
}

export interface RadarResult {
  user_id: number;
  interaction_count: number;
  level: number;
  level_title: string;
  level_emoji: string;
  next_level_at: number;
  ui_stage: "welcome" | "learning" | "early" | "stable";
  has_personality: boolean;
  dimensions: RadarDimension[];
  total_analyze_count: number;
  total_action_count: number;
}

export interface PersonalityResult {
  status: "ok" | "skipped";
  seeded_tag_count: number;
  summary: string;
}

export interface RecommendItem {
  domain: Domain;
  name: string;
  reason: string;
}

export interface RecommendResult {
  items: RecommendItem[];
}

export type Msg =
  | { type: "ANALYZE"; payload: { text: string; domain: Domain; pageTitle: string; pageUrl: string; hesitationMs: number | null } }
  | { type: "ACTION"; payload: { action: "star" | "bomb"; matchedTagIds: number[]; textHash?: string; readMs: number | null } }
  | { type: "GET_RADAR" }
  | { type: "RECOMMEND"; payload: { text: string; sourceDomain: Domain; matchedTagIds: number[] } }
  | { type: "PERSONALITY_SUBMIT"; payload: { mbti: string | null; constellation: string | null } };

export type MsgResponse<T> =
  | { ok: true; data: T }
  | { ok: false; error: { code: string; message: string } };
