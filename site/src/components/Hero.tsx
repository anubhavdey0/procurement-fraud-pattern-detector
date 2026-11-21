import { ArrowCounterClockwise, ArrowDown, ArrowUpRight } from "@phosphor-icons/react";
import { motion, useReducedMotion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { data, REPO } from "../lib/data";
import { BipartiteGraph, firmStats, GraphKey } from "./BipartiteGraph";
import { CONTAINER, EASE, Label } from "./ui";

// Forty tenders at this pace finish drawing in under five seconds, so the
// motion ends before it needs a pause control.
const STEP = 0.11;
const generated = new Date(`${data.meta.generated}T00:00:00`).toLocaleDateString("en-GB", {
  month: "long",
  year: "numeric",
});

/**
 * The line under the graph: which tender is being drawn and who won it. It
 * holds its own state so the forty updates never re-render the graph.
 */
function Ticker({ runId }: { runId: number }) {
  const reduce = useReducedMotion();
  const { graph } = data.demo;
  const total = graph.tenders.length;
  const [shown, setShown] = useState(reduce ? total : 0);

  useEffect(() => {
    if (reduce) {
      setShown(total);
      return;
    }
    setShown(0);
    const timer = window.setInterval(() => {
      setShown((current) => {
        if (current >= total) {
          window.clearInterval(timer);
          return current;
        }
        return current + 1;
      });
    }, STEP * 1000);
    return () => window.clearInterval(timer);
  }, [runId, reduce, total]);

  const winner = useMemo(() => {
    if (shown === 0) return null;
    const edge = graph.edges.find(([, tender, won]) => tender === shown - 1 && won);
    return edge ? graph.firms[edge[0]].label : null;
  }, [graph, shown]);

  return (
    <p className="tabular font-mono text-[12.5px] text-ink-2" aria-live="off">
      Tender {String(shown).padStart(2, "0")} of {total}
      {winner ? (
        <>
          <span className="mx-2 text-line-strong" aria-hidden="true">
            ·
          </span>
          won by <span className="text-ink">{winner}</span>
        </>
      ) : null}
    </p>
  );
}

function Stage() {
  const reduce = useReducedMotion();
  const [runId, setRunId] = useState(0);
  const { graph } = data.demo;

  const summary = useMemo(() => {
    const members = firmStats(graph).filter((firm) => firm.member);
    const winners = members.filter((firm) => firm.wins > 0);
    const loser = members.filter((firm) => firm.wins === 0).sort((a, b) => b.bids - a.bids)[0];
    return { winners: winners.length, loser };
  }, [graph]);

  const done = graph.tenders.length * STEP + 0.5;

  return (
    <figure className="m-0 border-t border-ink">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 pt-3.5">
        <span className="text-[14px] text-ink">
          <span className="tabular mr-2.5 font-mono text-[12px] text-accent">Fig. 1</span>A planted
          cartel, drawn one tender at a time
        </span>
        <GraphKey />
      </figcaption>
      <div className="relative mt-3">
        <div aria-hidden="true" className="stage-grid pointer-events-none absolute inset-0 opacity-70" />
        <div className="relative">
          <BipartiteGraph
            graph={graph}
            step={STEP}
            runId={runId}
            description={`Bipartite graph of a planted cartel in a synthetic market: ${graph.firms.length} firms on the left, ${graph.tenders.length} tenders on the right. A curve is a bid and a heavier curve is the winning bid.`}
          />
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-line py-2.5">
        <Ticker runId={runId} />
        <button
          type="button"
          onClick={() => setRunId((id) => id + 1)}
          className="-mr-2 flex items-center gap-1.5 rounded-[3px] px-2 py-1.5 text-[13px] text-ink-2 transition-colors duration-200 hover:bg-mid hover:text-ink active:translate-y-px"
        >
          <ArrowCounterClockwise size={14} aria-hidden="true" />
          Draw again
        </button>
      </div>
      {summary.loser ? (
        <motion.p
          key={runId}
          initial={reduce ? false : { opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: reduce ? 0 : done, duration: 0.7, ease: EASE }}
          className="border-t border-line pt-3 text-[14px] leading-relaxed text-ink-2"
        >
          {summary.winners} firms share every win, in turn. <Label>{summary.loser.label}</Label> bid{" "}
          {summary.loser.bids} times and won none. That is what a lead looks like.
        </motion.p>
      ) : null}
    </figure>
  );
}

export function Hero() {
  const reduce = useReducedMotion();
  const [marked, setMarked] = useState(Boolean(reduce));
  const rise = (delay: number) => ({
    initial: reduce ? false : ({ opacity: 0, y: 20 } as const),
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.95, delay, ease: EASE },
  });

  useEffect(() => {
    if (reduce) {
      setMarked(true);
      return;
    }
    const timer = window.setTimeout(() => setMarked(true), 750);
    return () => window.clearTimeout(timer);
  }, [reduce]);

  return (
    <section id="top" aria-labelledby="hero-title">
      <div className={`${CONTAINER} pt-8 md:pt-12`}>
        <motion.div
          {...rise(0)}
          className="tabular flex items-baseline justify-between gap-6 border-b border-line pb-3 font-mono text-[12px] text-muted"
        >
          <span>Working paper, version {data.meta.version}</span>
          <span className="hidden md:inline">Collusion screens for public tender data</span>
          <span>{generated}</span>
        </motion.div>

        <div className="grid grid-cols-1 gap-x-12 gap-y-14 pb-6 pt-12 md:pt-16 xl:grid-cols-12 xl:pt-20">
          <div className="xl:col-span-6 xl:pt-2">
            <h1 id="hero-title" className="display text-[3.1rem] leading-[0.98] text-ink sm:text-[4.4rem] xl:text-[5.1rem]">
              <motion.span {...rise(0.08)} className="block">
                Leads for{" "}
                <span className="mark" style={{ "--mark": marked ? 1 : 0 } as CSSProperties}>
                  review.
                </span>
              </motion.span>
              <motion.span {...rise(0.18)} className="block italic text-muted">
                Never a verdict.
              </motion.span>
            </h1>
            <motion.p {...rise(0.3)} className="mt-8 max-w-[46ch] text-[17px] leading-[1.65] text-ink-2 md:text-lg">
              bidscreen reads public tender data for the patterns bid rigging leaves behind: firms
              that only meet each other, winners that take turns, a bidder who always loses. Every
              screen is tested against six cartels that courts and competition authorities
              documented.
            </motion.p>
            <motion.div {...rise(0.4)} className="mt-10 flex flex-wrap items-center gap-x-7 gap-y-4">
              <a
                href="#evidence"
                className="group flex items-center gap-2 rounded-[3px] bg-ink px-5 py-3 text-[15px] font-medium text-bg transition-colors duration-200 hover:bg-accent hover:text-accent-ink active:translate-y-px"
              >
                See the evidence
                <ArrowDown size={15} aria-hidden="true" className="transition-transform duration-200 group-hover:translate-y-0.5" />
              </a>
              <a
                href={REPO}
                className="group flex items-center gap-1.5 text-[15px] font-medium text-ink underline decoration-line-strong decoration-1 underline-offset-[6px] transition-colors duration-200 hover:decoration-accent"
              >
                Read the code
                <ArrowUpRight size={14} aria-hidden="true" className="transition-transform duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
              </a>
            </motion.div>
          </div>
          <motion.div
            className="xl:col-span-6"
            initial={reduce ? false : { opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 1, delay: 0.25, ease: EASE }}
          >
            <Stage />
          </motion.div>
        </div>
      </div>
    </section>
  );
}
