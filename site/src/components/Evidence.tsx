import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { data } from "../lib/data";
import type { HeldOut } from "../lib/data";
import { count, fixed, percent } from "../lib/format";
import { EASE, Figure, Reveal, Section } from "./ui";

const { validation } = data;
const variance = validation.screens.find((screen) => screen.key === "cv")!;
// Columns run from the case where the variance screen works best to the worst.
const cases = [...validation.cases].sort(
  (a, b) => (variance.cells[b.key].auc ?? 0) - (variance.cells[a.key].auc ?? 0),
);
const titleOf = (key: string) => cases.find((item) => item.key === key)?.title ?? key;
const country = (title: string) => title.split(": ")[0];
const place = (title: string) => title.split(": ")[1] ?? title;

// Held-out check: the same cases, each scored with everything learned elsewhere.
const heldOut = cases
  .map((item) => (validation.held_out ?? []).find((row) => row.case === item.key))
  .filter((row): row is HeldOut => row != null);
const choices = new Set(heldOut.map((row) => row.chosen));
const weightsBetter = heldOut.filter((row) => row.weights_auc > row.chosen_auc + 0.01).length;
const ruleWorks = heldOut.filter((row) => (row.fixed_lift ?? 0) >= 1.1);
const tunedWorse = ruleWorks.filter((row) => (row.tuned_lift ?? 0) < (row.fixed_lift ?? 0)).length;

function tint(auc: number | null) {
  if (auc == null) return { side: "none", strength: "0%" };
  const strength = Math.min(Math.abs(auc - 0.5) / 0.4, 1) * 64;
  return { side: auc >= 0.5 ? "above" : "below", strength: `${strength.toFixed(1)}%` };
}

/** Position on the AUC axis used by every strip in this section, in percent. */
const axis = (value: number) => ((Math.min(Math.max(value, 0.3), 1) - 0.3) / 0.7) * 100;

function Interval({ low, high, auc }: { low: number; high: number; auc: number }) {
  return (
    <div className="mt-6">
      <div className="relative h-8">
        <div className="absolute inset-x-0 top-1/2 h-px bg-line-strong" />
        <div className="absolute bottom-1 top-1 border-l border-dashed border-muted" style={{ left: `${axis(0.5)}%` }} />
        <div className="absolute top-1/2 h-[3px] -translate-y-1/2 bg-context"
          style={{ left: `${axis(low)}%`, width: `${axis(high) - axis(low)}%` }} />
        <div className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-bg bg-accent"
          style={{ left: `${axis(auc)}%` }} />
      </div>
      <div className="tabular relative h-4 font-mono text-[11px] text-muted">
        <span className="absolute left-0">0.3</span>
        <span className="absolute -translate-x-1/2" style={{ left: `${axis(0.5)}%` }}>0.5</span>
        <span className="absolute right-0">1.0</span>
      </div>
    </div>
  );
}

function HeatTable({ selected, onSelect }: {
  selected: { screen: string; item: string };
  onSelect: (value: { screen: string; item: string }) => void;
}) {
  return (
    <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="AUC by screen and case">
      <table className="w-full min-w-[680px] table-fixed border-collapse text-[14px]">
        <colgroup>
          <col className="w-[29%]" />
          {cases.map((column) => (
            <col key={column.key} />
          ))}
        </colgroup>
        <thead>
          <tr className="border-b border-line-strong">
            <th scope="col" className="paper sticky left-0 z-10 py-3 pr-4 text-left align-bottom font-mono text-[11.5px] font-normal text-muted">Screen</th>
            {cases.map((column) => (
              <th key={column.key} scope="col" className="px-1 pb-3 pt-2 text-center align-bottom font-normal">
                <span className="block font-mono text-[11px] text-muted">{country(column.title)}</span>
                <span className="mt-0.5 block text-[13px] leading-tight text-ink">{place(column.title).replace("Graubunden and See-Gaster", "Graubunden")}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {validation.screens.map((row) => (
            <tr key={row.key} className={row.key === "composite" ? "border-t border-line-strong" : ""}>
              <th scope="row" className={`paper sticky left-0 z-10 py-1 pr-4 text-left font-normal ${row.key === "composite" ? "pt-2.5 italic text-ink-2" : "text-ink"}`}>
                {row.label}
              </th>
              {cases.map((column) => {
                const value = row.cells[column.key];
                const { side, strength } = tint(value.auc);
                const active = selected.screen === row.key && selected.item === column.key;
                const choose = () => onSelect({ screen: row.key, item: column.key });
                return (
                  <td key={column.key} className={`px-[3px] py-[3px] ${row.key === "composite" ? "pt-2.5" : ""}`}>
                    <button type="button" onClick={choose} onFocus={choose} aria-pressed={active}
                      aria-label={`${row.label}, ${column.title}: ${fixed(value.auc)}`}
                      data-side={side} style={{ "--strength": strength } as CSSProperties}
                      className={`heat tabular block w-full rounded-[3px] py-2.5 font-mono text-[13px] text-ink transition-shadow duration-200 hover:shadow-[inset_0_0_0_1px_var(--ink)] ${active ? "shadow-[inset_0_0_0_2px_var(--ink)]" : ""}`}>
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
  );
}

function Detail({ selected }: { selected: { screen: string; item: string } }) {
  const reduce = useReducedMotion();
  const screen = validation.screens.find((row) => row.key === selected.screen)!;
  const item = cases.find((row) => row.key === selected.item)!;
  const cell = screen.cells[item.key];
  const verdict =
    cell.auc == null ? "not scored" : cell.auc >= 0.7 ? "separates cartel tenders" : cell.auc >= 0.55 ? "weak signal" : cell.auc >= 0.45 ? "no better than a coin toss" : "points the wrong way";

  return (
    <div className="border-l border-line-strong pl-6 lg:sticky lg:top-24" aria-live="polite">
      <AnimatePresence mode="wait" initial={false}>
        <motion.div key={`${selected.screen}-${selected.item}`}
          initial={reduce ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
          exit={reduce ? undefined : { opacity: 0, y: -6 }} transition={{ duration: 0.28, ease: EASE }}>
          <p className="font-mono text-[12px] text-muted">{item.title}</p>
          <h3 className="display mt-1.5 text-[1.6rem] leading-tight text-ink">{screen.label}</h3>
          <p className="display lining mt-5 text-[3.6rem] leading-none text-ink">{fixed(cell.auc)}</p>
          <p className="mt-2 text-[14px] text-ink-2">
            {verdict}
            {cell.low != null && cell.high != null ? `, 95% interval ${fixed(cell.low)} to ${fixed(cell.high)}` : ""}
          </p>
          {cell.auc != null && cell.low != null && cell.high != null ? (
            <Interval low={cell.low} high={cell.high} auc={cell.auc} />
          ) : null}
          <dl className="mt-7 grid gap-4 border-t border-line pt-5 text-[14px] leading-relaxed">
            <div>
              <dt className="font-mono text-[11.5px] text-muted">Why it should work</dt>
              <dd className="mt-1 text-ink-2">
                {screen.expected ? `Expected to be ${screen.expected} under collusion: ${screen.why}.` : `Averages ${screen.why}.`}
              </dd>
            </div>
            <div>
              <dt className="font-mono text-[11.5px] text-muted">The case</dt>
              <dd className="mt-1 text-ink-2">
                {item.description} {count(item.cartel_tenders)} of {count(item.tenders)} scored tenders were cartel tenders.
              </dd>
            </div>
          </dl>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

/** For each case set aside: three ways of scoring it, all learned on the other five. */
function HeldOutPlot() {
  const ticks = [0.3, 0.5, 0.7, 0.9];
  return (
    <div role="table" aria-label="Each case scored with everything learned from the other five" className="text-[14px]">
      <div role="row" className="hidden grid-cols-[minmax(0,1.1fr)_minmax(0,2fr)_88px_88px] gap-x-6 border-b border-line-strong pb-2.5 font-mono text-[11.5px] text-muted md:grid">
        <span role="columnheader">Case set aside</span>
        <span role="columnheader">AUC on that case</span>
        <span role="columnheader" className="text-right">Rule, tuned</span>
        <span role="columnheader" className="text-right">Published</span>
      </div>
      {heldOut.map((row) => (
        <div role="row" key={row.case}
          className="grid grid-cols-2 items-center gap-x-4 gap-y-2 border-b border-line py-3.5 md:grid-cols-[minmax(0,1.1fr)_minmax(0,2fr)_88px_88px] md:gap-x-6">
          <span role="rowheader" className="col-span-2 text-ink md:col-span-1">{titleOf(row.case)}</span>
          <span role="cell" className="relative col-span-2 h-6 md:col-span-1"
            aria-label={`${row.chosen}, chosen on the other five: ${fixed(row.chosen_auc)}. Fitted weights: ${fixed(row.weights_auc)}. All seven averaged: ${fixed(row.composite_auc)}.`}>
            <span aria-hidden="true" className="absolute inset-x-0 top-1/2 h-px bg-line" />
            <span aria-hidden="true" className="absolute bottom-0 top-0 border-l border-dashed border-muted" style={{ left: `${axis(0.5)}%` }} />
            <span aria-hidden="true" title={`All seven averaged: ${fixed(row.composite_auc)}`}
              className="absolute top-1/2 size-[9px] -translate-x-1/2 -translate-y-1/2 bg-context" style={{ left: `${axis(row.composite_auc)}%` }} />
            <span aria-hidden="true" title={`Fitted weights: ${fixed(row.weights_auc)}`}
              className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-[1.5px] border-ink bg-bg" style={{ left: `${axis(row.weights_auc)}%` }} />
            <span aria-hidden="true" title={`${row.chosen}: ${fixed(row.chosen_auc)}`}
              className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-bg bg-accent" style={{ left: `${axis(row.chosen_auc)}%` }} />
          </span>
          <span role="cell" className="tabular font-mono text-[12.5px] text-ink-2 md:text-right md:text-[13px]">
            <span className="text-muted md:hidden">lift, tuned </span>{fixed(row.tuned_lift)}
          </span>
          <span role="cell" className="tabular text-right font-mono text-[12.5px] text-ink md:text-[13px]">
            <span className="text-muted md:hidden">published </span>{fixed(row.fixed_lift)}
          </span>
        </div>
      ))}
      <div aria-hidden="true" className="hidden grid-cols-[minmax(0,1.1fr)_minmax(0,2fr)_88px_88px] gap-x-6 pt-2 md:grid">
        <span />
        <span className="tabular relative h-4 font-mono text-[11px] text-muted">
          {ticks.map((tick) => (
            <span key={tick} className="absolute -translate-x-1/2" style={{ left: `${axis(tick)}%` }}>{tick.toFixed(1)}</span>
          ))}
        </span>
      </div>
    </div>
  );
}

function SmallTable({ caption, head, children }: { caption: string; head: string[]; children: ReactNode }) {
  return (
    <table className="mt-5 w-full text-[14px]">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr className="border-b border-line-strong text-left font-mono text-[11.5px] text-muted">
          {head.map((cell, i) => (
            <th key={cell} scope="col" className={`py-2 font-normal ${i ? "text-right" : ""}`}>{cell}</th>
          ))}
        </tr>
      </thead>
      <tbody>{children}</tbody>
    </table>
  );
}

export function Evidence() {
  const [selected, setSelected] = useState({ screen: "cv", item: cases[0].key });
  const excess = validation.cobid.filter((row) => row.score === "excess co-bidding");
  const chosen = choices.size === 1 ? [...choices][0] : null;

  return (
    <Section id="evidence" number="02" kicker="Evidence" title="Checked against six documented cartels"
      lead="Each number is an AUC: the chance that a cartel tender ranks above a competitive one. 0.5 is a coin toss, and below it the screen points the wrong way. Pick a cell to see what is behind it.">
      <div className="grid grid-cols-1 gap-x-12 gap-y-10 lg:grid-cols-12">
        <Reveal className="lg:col-span-8">
          <Figure n={2} title="Seven price screens on six cases"
            note={<>Tenders need three or more bids to be scored. Cases run from where the variance screen works best to where it works worst.</>}>
            <HeatTable selected={selected} onSelect={setSelected} />
            <ul className="mt-4 flex flex-wrap gap-x-6 gap-y-1.5 text-[13px] text-ink-2">
              <li className="flex items-center gap-2"><i aria-hidden="true" className="size-3 rounded-[2px] bg-accent" />Above 0.5: ranks cartel tenders higher</li>
              <li className="flex items-center gap-2"><i aria-hidden="true" className="size-3 rounded-[2px] bg-mid" />0.5: no signal</li>
              <li className="flex items-center gap-2"><i aria-hidden="true" className="size-3 rounded-[2px] bg-cool" />Below 0.5: points the wrong way</li>
            </ul>
          </Figure>
        </Reveal>
        <Reveal delay={0.08} className="lg:col-span-4 lg:pt-12">
          <Detail selected={selected} />
        </Reveal>
      </div>

      {heldOut.length ? (
        <Reveal className="mt-20 grid grid-cols-1 gap-x-12 gap-y-8 md:mt-24 lg:grid-cols-12">
          <div className="lg:col-span-4">
            <h3 className="display text-[1.85rem] leading-[1.12] text-ink md:text-[2.1rem]">Learned on five cases, tested on the sixth</h3>
            <p className="mt-4 max-w-[46ch] text-[15.5px] leading-[1.7] text-ink-2">
              The table above was read with every case in view. Here each case was set aside in turn, and
              everything was learned from the other five: which screen to trust, weights for all seven,
              and thresholds for the rule “variance below c, relative distance above r”.
            </p>
            <ul className="mt-6 grid gap-3 text-[14.5px] leading-relaxed text-ink-2">
              {chosen ? (
                <li className="grid grid-cols-[18px_1fr]"><span aria-hidden="true" className="text-accent">—</span>
                  <span>Whichever case is set aside, the other five pick the {chosen.toLowerCase()}. Its record is not the product of hindsight.</span></li>
              ) : null}
              <li className="grid grid-cols-[18px_1fr]"><span aria-hidden="true" className="text-accent">—</span>
                <span>
                  Weights fitted on all seven screens beat the chosen screen by more than 0.01 in {weightsBetter === 0 ? "no case" : `${weightsBetter} of ${heldOut.length}`}.
                  What they learn beyond it changes from one set of five to the next.
                </span></li>
              {ruleWorks.length ? (
                <li className="grid grid-cols-[18px_1fr]"><span aria-hidden="true" className="text-accent">—</span>
                  <span>
                    Tuned thresholds did worse than the published ones in {tunedWorse} of the {ruleWorks.length} cases where the rule works at all.
                    Lift is the cartel share among flagged tenders over the share among all.
                  </span></li>
              ) : null}
            </ul>
          </div>
          <div className="lg:col-span-8">
            <Figure n={3} title="Each case scored with what the other five taught"
              aside={
                <ul className="flex flex-wrap gap-x-5 gap-y-1 text-[12.5px] text-ink-2">
                  <li className="flex items-center gap-2"><i aria-hidden="true" className="size-3 rounded-full bg-accent" />{chosen ?? "Best screen elsewhere"}</li>
                  <li className="flex items-center gap-2"><i aria-hidden="true" className="size-3 rounded-full border-[1.5px] border-ink" />Fitted weights</li>
                  <li className="flex items-center gap-2"><i aria-hidden="true" className="size-[9px] bg-context" />Seven averaged</li>
                </ul>
              }>
              <HeldOutPlot />
            </Figure>
          </div>
        </Reveal>
      ) : null}

      <div className="mt-20 grid grid-cols-1 gap-x-12 gap-y-14 md:mt-24 md:grid-cols-2">
        <Reveal>
          <h3 className="display text-[1.6rem] leading-tight text-ink">Does bidding together single out cartel pairs?</h3>
          <p className="mt-3 max-w-[48ch] text-[15.5px] leading-[1.7] text-ink-2">In one case of four. In the other three, closeness on the graph was no better than a coin toss.</p>
          <SmallTable caption="Co-bidding check by case" head={["Case", "Cartel pairs", "AUC"]}>
            {[...excess].sort((a, b) => b.auc - a.auc).map((row) => (
              <tr key={row.case} className="border-b border-line">
                <th scope="row" className="py-3 text-left font-normal text-ink">{titleOf(row.case)}</th>
                <td className="tabular py-3 text-right font-mono text-ink-2">{count(row.n_cartel_pairs)}</td>
                <td className="tabular py-3 text-right font-mono text-ink">{fixed(row.auc)}</td>
              </tr>
            ))}
          </SmallTable>
        </Reveal>
        <Reveal delay={0.06}>
          <h3 className="display text-[1.6rem] leading-tight text-ink">Do the leads land on cartel tenders?</h3>
          <p className="mt-3 max-w-[48ch] text-[15.5px] leading-[1.7] text-ink-2">No. This is why the Assam output is called a reading list.</p>
          <SmallTable caption="Lead check by case" head={["Case", "Leads", "Cartel share flagged", "Random pick"]}>
            {validation.leads.map((row) => (
              <tr key={row.case} className="border-b border-line">
                <th scope="row" className="py-3 text-left font-normal text-ink">{titleOf(row.case)}</th>
                <td className="tabular py-3 text-right font-mono text-ink-2">{row.leads}</td>
                <td className="tabular py-3 text-right font-mono text-ink">{row.leads > 0 ? percent(row.precision) : <span className="font-sans text-muted">none</span>}</td>
                <td className="tabular py-3 text-right font-mono text-ink-2">{percent(row.base_rate)}</td>
              </tr>
            ))}
          </SmallTable>
        </Reveal>
      </div>
    </Section>
  );
}
