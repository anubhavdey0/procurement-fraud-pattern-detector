import { motion, useReducedMotion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import type { Graph } from "../lib/data";
import { EASE } from "./ui";

/** True while the viewport matches a media query. */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window === "undefined" ? false : window.matchMedia(query).matches,
  );
  useEffect(() => {
    const media = window.matchMedia(query);
    const update = () => setMatches(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [query]);
  return matches;
}

interface FirmStat {
  label: string;
  member: boolean;
  bids: number;
  wins: number;
}

export function firmStats(graph: Graph): FirmStat[] {
  return graph.firms.map((firm, index) => {
    const mine = graph.edges.filter(([f]) => f === index);
    return {
      label: firm.label,
      member: firm.member,
      bids: mine.length,
      wins: mine.filter(([, , won]) => won).length,
    };
  });
}

interface Props {
  graph: Graph;
  /** Seconds between one tender's bids and the next. */
  step?: number;
  /** Change this to draw the graph again from the start. */
  runId?: number | string;
  /** Height of the plot area in drawing units. */
  plotHeight?: number;
  /** A sentence describing the picture for screen readers. */
  description: string;
}

/**
 * Firms on the left, tenders on the right, one curve per bid. Bids are drawn
 * tender by tender in time order, so the reader watches the pattern form:
 * who keeps turning up, and who wins.
 */
export function BipartiteGraph({ graph, step = 0.12, runId = 0, plotHeight = 330, description }: Props) {
  const reduce = useReducedMotion();
  const narrow = useMediaQuery("(max-width: 640px)");

  const layout = useMemo(() => {
    const width = narrow ? 372 : 640;
    const firmX = narrow ? 104 : 168;
    const tenderX = narrow ? width - 22 : width - 104;
    const top = 30;
    const spread = (countOf: number, index: number, inset = 0) =>
      countOf <= 1
        ? top + plotHeight / 2
        : top + inset + ((plotHeight - 2 * inset) * index) / (countOf - 1);
    const firmY = graph.firms.map((_, i) => spread(graph.firms.length, i, 26));
    const tenderY = graph.tenders.map((_, i) => spread(graph.tenders.length, i));
    return { width, height: top + plotHeight + 24, firmX, tenderX, firmY, tenderY };
  }, [graph, narrow, plotHeight]);

  const stats = useMemo(() => firmStats(graph), [graph]);
  const { width, height, firmX, tenderX, firmY, tenderY } = layout;
  const done = graph.tenders.length * step + 0.35;
  const mid = (firmX + tenderX) / 2;

  const curve = (firm: number, tender: number) =>
    `M ${firmX + 8} ${firmY[firm]} C ${mid} ${firmY[firm]}, ${mid} ${tenderY[tender]}, ${tenderX - 6} ${tenderY[tender]}`;

  // Losing bids first, winning bids on top.
  const ordered = [...graph.edges].sort((a, b) => Number(a[2]) - Number(b[2]));
  let lastMonth = "";
  let lastLabelY = -Infinity;

  return (
    <figure className="m-0">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={description}
        className="block h-auto w-full"
      >
        <g key={`${runId}-${narrow}`}>
          {ordered.map(([firm, tender, won]) => (
            <motion.path
              key={`${firm}-${tender}`}
              d={curve(firm, tender)}
              fill="none"
              stroke={won ? "var(--accent)" : "var(--context)"}
              strokeWidth={won ? 1.9 : 1}
              strokeLinecap="round"
              initial={reduce ? false : { pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: won ? 0.95 : 0.5 }}
              transition={{
                pathLength: { delay: tender * step, duration: 0.55, ease: EASE },
                opacity: { delay: tender * step, duration: 0.2 },
              }}
            />
          ))}

          {graph.tenders.map((tender, i) => {
            const showMonth =
              !narrow && tender.month !== lastMonth && tenderY[i] - lastLabelY >= 14;
            lastMonth = tender.month;
            if (showMonth) lastLabelY = tenderY[i];
            return (
              <motion.g
                key={tender.label}
                initial={reduce ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * step, duration: 0.25 }}
              >
                <circle cx={tenderX} cy={tenderY[i]} r={3.6} fill="var(--context)" stroke="var(--surface)" strokeWidth={1.5}>
                  <title>{`${tender.label}, ${tender.month}, ${tender.bidders} bidders`}</title>
                </circle>
                {showMonth ? (
                  <text x={tenderX + 12} y={tenderY[i] + 3.5} fontSize={10.5} fill="var(--muted)" className="tabular font-mono">
                    {tender.month}
                  </text>
                ) : null}
              </motion.g>
            );
          })}

          {stats.map((firm, i) => (
            <g key={firm.label}>
              <circle
                cx={firmX}
                cy={firmY[i]}
                r={7}
                fill={firm.member ? "var(--accent)" : "var(--context)"}
                stroke="var(--surface)"
                strokeWidth={2}
              />
              <text
                x={firmX - 16}
                y={firmY[i] - 1}
                textAnchor="end"
                fontSize={narrow ? 10.5 : 12}
                fill="var(--ink)"
                className="font-mono"
              >
                {firm.label}
              </text>
              <motion.text
                x={firmX - 16}
                y={firmY[i] + 13}
                textAnchor="end"
                fontSize={narrow ? 9.5 : 10.5}
                fill="var(--muted)"
                className="tabular font-mono"
                initial={reduce ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: done, duration: 0.6 }}
              >
                {`${firm.bids} bids, ${firm.wins} won`}
              </motion.text>
            </g>
          ))}
        </g>
      </svg>
      <figcaption className="sr-only">
        {stats.map((firm) => `${firm.label}: ${firm.bids} bids, ${firm.wins} won.`).join(" ")}
      </figcaption>
    </figure>
  );
}

/** A two-item key for the graph: what a heavy line and a light line mean. */
export function GraphKey() {
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1 text-[13px] text-ink-2">
      <li className="flex items-center gap-2">
        <span aria-hidden="true" className="h-[2px] w-5 rounded-full bg-accent" />
        Winning bid
      </li>
      <li className="flex items-center gap-2">
        <span aria-hidden="true" className="h-px w-5 bg-context" />
        Losing bid
      </li>
    </ul>
  );
}
