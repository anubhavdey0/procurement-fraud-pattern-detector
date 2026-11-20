import raw from "../data/site-data.json";

// The shape of site-data.json, written by `bidscreen export-site`.

export type ScreenKey = "closed" | "rotation" | "cover" | "price";

export interface Graph {
  firms: { label: string; member: boolean }[];
  tenders: { label: string; month: string; bidders: number }[];
  /** [firm index, tender index, won] */
  edges: [number, number, boolean][];
  total: number;
}

export interface LeadScreen {
  key: ScreenKey;
  label: string;
  fired: boolean;
  text: string;
}

export interface Lead {
  id: string;
  members: string[];
  size: number;
  period: string;
  joint: number;
  closed: number;
  closed_share: number | null;
  wins: number;
  decided: number;
  segments: number;
  exclusivity: number;
  screens: LeadScreen[];
  rule_out: string[];
  graph: Graph;
}

export interface GroupPoint {
  id: string;
  size: number;
  exclusivity: number;
  joint: number;
  closed_share: number | null;
  screens: ScreenKey[];
}

export interface Cell {
  auc: number | null;
  low: number | null;
  high: number | null;
}

export interface ValidationCase {
  key: string;
  title: string;
  description: string;
  identifies_bidders: boolean;
  lowest_bid_wins: boolean;
  tenders: number;
  cartel_tenders: number;
}

export interface ValidationScreen {
  key: string;
  label: string;
  expected: "low" | "high" | null;
  why: string;
  cells: Record<string, Cell>;
}

export interface SiteData {
  meta: {
    generated: string;
    version: string;
    market: string;
    description: string;
    source: string;
    licence: string;
    notice: string;
  };
  summary: {
    tenders: number;
    with_bidders: number;
    with_winner: number;
    bidders: number;
    pairs: number;
    links: number;
    groups: number;
    leads: number;
    priced: number;
    screens_fired: Record<ScreenKey, number>;
  };
  config: Record<string, number>;
  screens: { key: ScreenKey; label: string; rule_out: string[] }[];
  groups: GroupPoint[];
  price: { n: number; median: number; bins: { at: number; count: number }[] };
  leads: Lead[];
  validation: {
    cases: ValidationCase[];
    screens: ValidationScreen[];
    rule: Record<string, number | string | null>[];
    cobid: { case: string; score: string; n_pairs: number; n_cartel_pairs: number; auc: number }[];
    leads: {
      case: string;
      leads: number;
      n_flagged: number;
      precision: number | null;
      base_rate: number;
      n_collusive: number;
      n_tenders: number;
    }[];
  };
  demo: { members: string[]; joint: number; screens: string[]; graph: Graph };
}

export const data = raw as unknown as SiteData;

export const REPO = "https://github.com/anubhavdey0/procurement-fraud-pattern-detector";
