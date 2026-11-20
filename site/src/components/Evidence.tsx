import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useState } from "react";
import type { CSSProperties } from "react";
import { data } from "../lib/data";
import { count, fixed, percent } from "../lib/format";
import { EASE, Reveal, Section } from "./ui";

const { validation } = data;
const variance = validation.screens.find((screen) => screen.key === "cv")!;
// Columns run from the case where the variance screen works best to the worst.
const cases = [...validation.cases].sort(
  (a, b) => (variance.cells[b.key].auc ?? 0) - (variance.cells[a.key].auc ?? 0),
);
const [country, place] = [(title: string) => title.split(": ")[0], (title: string) => title.split(": ")[1]];

function tint(auc: number | null) {
  if (auc == null) return { side: "none", strength: "0%" };
  const strength = Math.min(Math.abs(auc - 0.5) / 0.4, 1) * 62;
  return { side: auc >= 0.5 ? "above" : "below", strength: `${strength.toFixed(1)}%` };
}

function Interval({ low, high, auc }: { low: number; high: number; auc: number }) {
  const x = (value: number) => ((Math.min(Math.max(value, 0.3), 1) - 0.3) / 0.7) * 100;
  return (
    <div className="mt-5">
      <div className="relative h-8">
        <div className="absolute inset-x-0 top-1/2 h-px bg-line-strong" />
        <div className="absolute top-1 bottom-1 w-px bg-muted" style={{ left: `${x(0.5)}%` }} />
        <div className="absolute top-1/2 h-[3px] -translate-y-1/2 rounded-full bg-context"
          style={{ left: `${x(low)}%`, width: `${x(high) - x(low)}%` }} />
        <div className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface bg-accent"
          style={{ left: `${x(auc)}%` }} />
      </div>
      <div className="tabular relative h-4 font-mono text-[11px] text-muted">
        <span className="absolute left-0">0.3</span>
        <span className="absolute -translate-x-1/2" style={{ left: `${x(0.5)}%` }}>0.5</span>
        <span className="absolute right-0">1.0</span>
      </div>
    </div>
  );
}

export function Evidence() {
  const reduce = useReducedMotion();
  const [selected, setSelected] = useState({ screen: "cv", item: cases[0].key });
  const screen = validation.screens.find((row) => row.key === selected.screen)!;
  const item = cases.find((row) => row.key === selected.item)!;
  const cell = screen.cells[item.key];
  const verdict =
    cell.auc == null ? "not scored" : cell.auc >= 0.7 ? "separates cartel tenders" : cell.auc >= 0.55 ? "weak signal" : cell.auc >= 0.45 ? "no better than a coin toss" : "points the wrong way";
  const excess = validation.cobid.filter((row) => row.score === "excess co-bidding");

  return (
    <Section id="evidence" title="Checked against six documented cartels" wide
      lead="Each number is an AUC: the chance that a cartel tender ranks above a competitive one. 0.5 is a coin toss, and below it the screen points the wrong way. Pick a cell to see what is behind it.">
      <div className="grid gap-8 lg:grid-cols-12 grid-cols-1">
        <Reveal className="lg:col-span-8">
          <div className="overflow-x-auto rounded-2xl border border-line bg-surface" tabIndex={0} role="region" aria-label="AUC by screen and case">
            <table className="w-full min-w-[680px] table-fixed border-collapse text-[14px]">
              <colgroup>
                <col className="w-[30%]" />
                {cases.map((column) => (
                  <col key={column.key} />
                ))}
              </colgroup>
              <thead>
                <tr>
                  <th scope="col" className="sticky left-0 z-10 bg-surface px-5 py-4 text-left text-[13px] font-medium text-muted">Screen</th>
                  {cases.map((column) => (
                    <th key={column.key} scope="col" className="px-1.5 py-4 text-center align-bottom font-medium">
                      <span className="block text-[11.5px] text-muted">{country(column.title)}</span>
                      <span className="block text-[13px] text-ink">{place(column.title).replace("Graubunden and See-Gaster", "Graubunden")}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {validation.screens.map((row) => (
                  <tr key={row.key} className={row.key === "composite" ? "border-t border-line-strong" : "border-t border-line"}>
                    <th scope="row" className="sticky left-0 z-10 bg-surface px-5 py-2 text-left font-medium text-ink">{row.label}</th>
                    {cases.map((column) => {
                      const value = row.cells[column.key];
                      const { side, strength } = tint(value.auc);
                      const active = selected.screen === row.key && selected.item === column.key;
                      const choose = () => setSelected({ screen: row.key, item: column.key });
                      return (
                        <td key={column.key} className="p-1">
                          <button type="button" onClick={choose} onFocus={choose} aria-pressed={active}
                            aria-label={`${row.label}, ${column.title}: ${fixed(value.auc)}`}
                            data-side={side} style={{ "--strength": strength } as CSSProperties}
                            className={`heat tabular block w-full rounded-lg py-2.5 font-mono text-[13.5px] text-ink transition-shadow hover:shadow-[inset_0_0_0_1.5px_var(--ink)] ${active ? "shadow-[inset_0_0_0_2px_var(--ink)]" : ""}`}>
                            {fixed(value.auc)}
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-[13px] text-ink-2">
            <li className="flex items-center gap-2"><i aria-hidden="true" className="size-3 rounded-[4px] bg-accent" />Above 0.5: ranks cartel tenders higher</li>
            <li className="flex items-center gap-2"><i aria-hidden="true" className="size-3 rounded-[4px] bg-mid" />0.5: no signal</li>
            <li className="flex items-center gap-2"><i aria-hidden="true" className="size-3 rounded-[4px] bg-warm" />Below 0.5: points the wrong way</li>
          </ul>
        </Reveal>

        <Reveal delay={0.08} className="lg:col-span-4">
          <div className="rounded-2xl border border-line bg-surface p-6 lg:sticky lg:top-24" aria-live="polite">
            <AnimatePresence mode="wait" initial={false}>
              <motion.div key={`${selected.screen}-${selected.item}`}
                initial={reduce ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                exit={reduce ? undefined : { opacity: 0, y: -6 }} transition={{ duration: 0.28, ease: EASE }}>
                <p className="text-[13px] text-muted">{item.title}</p>
                <h3 className="mt-1 text-xl font-semibold tracking-tight text-ink">{screen.label}</h3>
                <p className="tabular mt-5 font-mono text-5xl font-medium tracking-tight text-ink">{fixed(cell.auc)}</p>
                <p className="mt-1.5 text-[14px] text-ink-2">
                  {verdict}
                  {cell.low != null && cell.high != null ? `, 95% interval ${fixed(cell.low)} to ${fixed(cell.high)}` : ""}
                </p>
                {cell.auc != null && cell.low != null && cell.high != null ? (
                  <Interval low={cell.low} high={cell.high} auc={cell.auc} />
                ) : null}
                <dl className="mt-6 grid gap-4 border-t border-line pt-5 text-[14px] leading-relaxed">
                  <div>
                    <dt className="text-muted">Why it should work</dt>
                    <dd className="text-ink-2">
                      {screen.expected ? `Expected to be ${screen.expected} under collusion: ${screen.why}.` : `Averages ${screen.why}.`}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted">The case</dt>
                    <dd className="text-ink-2">
                      {item.description} {count(item.cartel_tenders)} of {count(item.tenders)} scored tenders were cartel tenders.
                    </dd>
                  </div>
                </dl>
              </motion.div>
            </AnimatePresence>
          </div>
        </Reveal>
      </div>

      <div className="mt-14 grid gap-10 md:grid-cols-2 grid-cols-1">
        <Reveal>
          <h3 className="text-lg font-semibold tracking-tight text-ink">Does bidding together single out cartel pairs?</h3>
          <p className="mt-2 max-w-[48ch] text-[15px] leading-relaxed text-ink-2">In one case of four. In the other three, closeness on the graph was no better than a coin toss.</p>
          <table className="mt-5 w-full text-[14px]">
            <thead>
              <tr className="border-b border-line-strong text-left text-[13px] text-muted">
                <th scope="col" className="py-2 font-medium">Case</th>
                <th scope="col" className="py-2 text-right font-medium">Cartel pairs</th>
                <th scope="col" className="py-2 text-right font-medium">AUC</th>
              </tr>
            </thead>
            <tbody>
              {[...excess].sort((a, b) => b.auc - a.auc).map((row) => (
                <tr key={row.case} className="border-b border-line last:border-b-0">
                  <th scope="row" className="py-2.5 text-left font-normal text-ink">{cases.find((c) => c.key === row.case)?.title}</th>
                  <td className="tabular py-2.5 text-right font-mono text-ink-2">{count(row.n_cartel_pairs)}</td>
                  <td className="tabular py-2.5 text-right font-mono text-ink">{fixed(row.auc)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Reveal>
        <Reveal delay={0.06}>
          <h3 className="text-lg font-semibold tracking-tight text-ink">Do the leads land on cartel tenders?</h3>
          <p className="mt-2 max-w-[48ch] text-[15px] leading-relaxed text-ink-2">No. This is why the Assam output is called a reading list.</p>
          <table className="mt-5 w-full text-[14px]">
            <thead>
              <tr className="border-b border-line-strong text-left text-[13px] text-muted">
                <th scope="col" className="py-2 font-medium">Case</th>
                <th scope="col" className="py-2 text-right font-medium">Leads</th>
                <th scope="col" className="py-2 text-right font-medium">Cartel share of flagged</th>
                <th scope="col" className="py-2 text-right font-medium">Random pick</th>
              </tr>
            </thead>
            <tbody>
              {validation.leads.map((row) => (
                <tr key={row.case} className="border-b border-line last:border-b-0">
                  <th scope="row" className="py-2.5 text-left font-normal text-ink">{cases.find((c) => c.key === row.case)?.title}</th>
                  <td className="tabular py-2.5 text-right font-mono text-ink-2">{row.leads}</td>
                  <td className="tabular py-2.5 text-right font-mono text-ink">{row.leads > 0 ? percent(row.precision) : <span className="font-sans text-muted">none flagged</span>}</td>
                  <td className="tabular py-2.5 text-right font-mono text-ink-2">{percent(row.base_rate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Reveal>
      </div>
    </Section>
  );
}
