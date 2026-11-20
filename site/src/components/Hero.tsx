import { ArrowCounterClockwise, ArrowDown, GithubLogo } from "@phosphor-icons/react";
import { motion, useReducedMotion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { data, REPO } from "../lib/data";
import { BipartiteGraph, firmStats, GraphKey } from "./BipartiteGraph";
import { EASE, Label } from "./ui";

const STEP = 0.13;

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
    <p className="tabular font-mono text-[13px] text-ink-2" aria-live="off">
      Tender {String(shown).padStart(2, "0")} of {total}
      {winner ? (
        <>
          <span className="mx-2 text-line-strong" aria-hidden="true">
            /
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
    <div className="relative overflow-hidden rounded-2xl border border-line bg-surface">
      <div aria-hidden="true" className="stage-grid pointer-events-none absolute inset-0 opacity-60" />
      <div className="relative flex items-center justify-between gap-4 border-b border-line px-5 py-3.5">
        <p className="text-[13px] text-ink-2">Demo market with a planted cartel</p>
        <GraphKey />
      </div>
      <div className="relative px-3 pt-3 sm:px-5">
        <BipartiteGraph
          graph={graph}
          step={STEP}
          runId={runId}
          description={`Bipartite graph of a planted cartel in a synthetic market: ${graph.firms.length} firms on the left, ${graph.tenders.length} tenders on the right. A curve is a bid and a heavier curve is the winning bid.`}
        />
      </div>
      <div className="relative flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-line px-5 py-3.5">
        <Ticker runId={runId} />
        <button
          type="button"
          onClick={() => setRunId((id) => id + 1)}
          className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] text-ink-2 transition-colors hover:bg-mid hover:text-ink active:scale-[0.97]"
        >
          <ArrowCounterClockwise size={15} aria-hidden="true" />
          Replay
        </button>
      </div>
      {summary.loser ? (
        <motion.p
          key={runId}
          initial={reduce ? false : { opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: reduce ? 0 : done, duration: 0.7, ease: EASE }}
          className="relative border-t border-line px-5 py-3.5 text-[14px] leading-relaxed text-ink-2"
        >
          {summary.winners} firms share every win, in turn. <Label>{summary.loser.label}</Label> bid{" "}
          {summary.loser.bids} times and won none. That is what a lead looks like.
        </motion.p>
      ) : null}
    </div>
  );
}

export function Hero() {
  const reduce = useReducedMotion();
  const rise = (delay: number) => ({
    initial: reduce ? false : ({ opacity: 0, y: 22 } as const),
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.9, delay, ease: EASE },
  });

  return (
    <section id="top" aria-labelledby="hero-title" className="relative">
      <div className="mx-auto grid max-w-[1240px] items-center gap-12 px-5 pb-20 pt-10 md:px-8 md:pt-16 xl:grid-cols-12 xl:gap-10 xl:pb-28 grid-cols-1">
        <div className="xl:col-span-5">
          <motion.p {...rise(0)} className="text-[13px] font-medium uppercase tracking-[0.16em] text-muted">
            Collusion screens for public tender data
          </motion.p>
          <h1
            id="hero-title"
            className="mt-6 text-[2.6rem] font-semibold leading-[1.04] tracking-[-0.035em] sm:text-6xl xl:text-[3.2rem] [&>span]:whitespace-nowrap"
          >
            <motion.span {...rise(0.08)} className="block text-ink">
              Leads for review.
            </motion.span>
            <motion.span {...rise(0.16)} className="block text-muted">
              Never a verdict.
            </motion.span>
          </h1>
          <motion.p {...rise(0.26)} className="mt-7 max-w-[44ch] text-lg leading-relaxed text-ink-2">
            bidscreen reads public tender data for the patterns bid rigging leaves behind, and tests
            every screen against six documented cartels.
          </motion.p>
          <motion.div {...rise(0.36)} className="mt-9 flex flex-wrap items-center gap-x-6 gap-y-4">
            <a
              href={REPO}
              className="flex items-center gap-2.5 rounded-full bg-accent px-6 py-3 text-[15px] font-medium text-accent-ink transition-transform hover:-translate-y-px active:scale-[0.98]"
            >
              <GithubLogo size={18} weight="fill" aria-hidden="true" />
              View on GitHub
            </a>
            <a
              href="#evidence"
              className="group flex items-center gap-2 text-[15px] font-medium text-ink underline decoration-line-strong underline-offset-[6px] transition-colors hover:decoration-ink"
            >
              See the evidence
              <ArrowDown size={15} aria-hidden="true" className="transition-transform group-hover:translate-y-0.5" />
            </a>
          </motion.div>
        </div>
        <motion.div
          className="xl:col-span-7"
          initial={reduce ? false : { opacity: 0, y: 28 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, delay: 0.2, ease: EASE }}
        >
          <Stage />
        </motion.div>
      </div>
    </section>
  );
}
