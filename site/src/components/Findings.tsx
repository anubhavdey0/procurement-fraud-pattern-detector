import type { ReactNode } from "react";
import { data } from "../lib/data";
import { fixed, percent } from "../lib/format";
import { Reveal, Section } from "./ui";

const variance = data.validation.screens.find((screen) => screen.key === "cv")!;
const aucs = data.validation.cases
  .map((item) => ({ title: item.title, auc: variance.cells[item.key].auc ?? 0.5 }))
  .sort((a, b) => b.auc - a.auc);
const works = aucs.filter((item) => item.auc >= 0.6).length;
const leadChecks = data.validation.leads;
const beatChance = leadChecks.filter(
  (row) => row.leads > 0 && row.precision != null && row.precision > row.base_rate,
).length;
const titleOf = (key: string) => data.validation.cases.find((item) => item.key === key)?.title ?? key;
const heldOut = data.validation.held_out ?? [];
const alwaysChosen = heldOut.length > 0 && heldOut.every((row) => row.chosen === variance.label);

/** Six cases on one axis: where the variance screen works and where it fails. */
function AucStrip() {
  const x = (auc: number) => 8 + ((auc - 0.3) / 0.7) * 264;
  return (
    <svg viewBox="0 0 280 70" className="block h-auto w-full max-w-[340px]" role="img"
      aria-label={`AUC of the variance screen in six cases, from ${fixed(aucs[aucs.length - 1].auc)} to ${fixed(aucs[0].auc)}. 0.5 is a coin toss.`}>
      <line x1="8" x2="272" y1="34" y2="34" stroke="var(--line-strong)" />
      {[0.3, 0.5, 0.7, 0.9].map((tick) => (
        <line key={tick} x1={x(tick)} x2={x(tick)} y1="30" y2="38" stroke="var(--line-strong)" />
      ))}
      <line x1={x(0.5)} x2={x(0.5)} y1="16" y2="50" stroke="var(--muted)" strokeDasharray="2 3" />
      <text x={x(0.5)} y="64" textAnchor="middle" fontSize="10.5" fill="var(--muted)" className="font-mono">coin toss</text>
      {aucs.map((item) => (
        <circle key={item.title} cx={x(item.auc)} cy="34" r="5.5"
          fill={item.auc >= 0.6 ? "var(--accent)" : "var(--bg)"} stroke={item.auc >= 0.6 ? "var(--bg)" : "var(--context)"} strokeWidth="1.6">
          <title>{`${item.title}: ${fixed(item.auc)}`}</title>
        </circle>
      ))}
      <text x={x(aucs[0].auc)} y="16" textAnchor="middle" fontSize="11" fill="var(--ink)" className="tabular font-mono">
        {fixed(aucs[0].auc)}
      </text>
    </svg>
  );
}

/** For each case: how often flagged tenders were cartel tenders, against a random pick. */
function LeadCheck() {
  const scale = (value: number) => 4 + (value / 0.6) * 150;
  return (
    <ul className="grid max-w-[340px] gap-2.5 text-[13px] text-ink-2">
      {leadChecks.map((row) => (
        <li key={row.case} className="grid grid-cols-[1fr_158px] items-center gap-3">
          <span className="truncate">{titleOf(row.case).split(": ")[1]}</span>
          <svg viewBox="0 0 158 14" className="block h-auto w-full" role="img"
            aria-label={`${titleOf(row.case)}: ${row.leads === 0 ? "no leads" : `${percent(row.precision)} of flagged tenders were cartel tenders`}, against ${percent(row.base_rate)} for a random pick.`}>
            <line x1="4" x2="154" y1="7" y2="7" stroke="var(--line-strong)" />
            <rect x={scale(row.base_rate) - 3.5} y="3.5" width="7" height="7" fill="var(--context)" />
            {row.leads > 0 && row.precision != null ? (
              <circle cx={scale(row.precision)} cy="7" r="4.5" fill="var(--accent)" stroke="var(--bg)" strokeWidth="1.5" />
            ) : null}
          </svg>
        </li>
      ))}
      <li className="mt-1 flex gap-5 font-mono text-[11px] text-muted">
        <span className="flex items-center gap-1.5"><i aria-hidden="true" className="size-2 rounded-full bg-accent" />flagged tenders</span>
        <span className="flex items-center gap-1.5"><i aria-hidden="true" className="size-2 bg-context" />random pick</span>
      </li>
    </ul>
  );
}

/** Every co-bidding group as a dot; the leads are the few in colour. */
function GroupCloud() {
  const top = Math.max(...data.groups.map((group) => group.joint));
  const y = (joint: number) => 62 - (Math.log10(Math.max(joint, 2)) / Math.log10(top)) * 54;
  return (
    <svg viewBox="0 0 280 70" className="block h-auto w-full max-w-[340px]" role="img"
      aria-label={`${data.summary.groups} co-bidding groups plotted by how closed they are. ${data.summary.leads} are leads.`}>
      <line x1="4" x2="276" y1="66" y2="66" stroke="var(--line-strong)" />
      {data.groups.map((group) => {
        const lead = group.screens.length >= 2;
        return lead ? null : (
          <circle key={group.id} cx={6 + group.exclusivity * 268} cy={y(group.joint)} r={1.7}
            fill="var(--context)" opacity={0.6} />
        );
      })}
      {data.groups.filter((group) => group.screens.length >= 2).map((group) => (
        <circle key={group.id} cx={6 + group.exclusivity * 268} cy={y(group.joint)} r={4}
          fill="var(--accent)" stroke="var(--bg)" strokeWidth="1.5" />
      ))}
    </svg>
  );
}

function Row({ numeral, figure, caption, title, children, visual }: {
  numeral: string; figure: string; caption: string; title: string; children: ReactNode; visual: ReactNode;
}) {
  return (
    <Reveal className="grid grid-cols-1 items-start gap-x-10 gap-y-6 border-t border-line py-10 first:border-t-0 first:pt-0 md:grid-cols-12 md:py-14">
      <div className="md:col-span-3">
        <p className="display lining text-[4.2rem] leading-none text-ink md:text-[5rem]">{figure}</p>
        <p className="mt-3 max-w-[22ch] font-mono text-[12px] leading-relaxed text-muted">{caption}</p>
      </div>
      <div className="md:col-span-5">
        <h3 className="display text-[1.65rem] leading-[1.15] text-ink md:text-[1.95rem]">
          <span className="mr-3 font-mono text-[13px] tracking-normal text-accent">{numeral}</span>
          {title}
        </h3>
        <p className="mt-4 max-w-[48ch] text-[16px] leading-[1.7] text-ink-2">{children}</p>
      </div>
      <div className="md:col-span-4 md:justify-self-end md:pt-3">{visual}</div>
    </Reveal>
  );
}

export function Findings() {
  return (
    <Section id="findings" number="01" kicker="Findings" title="Three results, by how much weight they bear"
      lead="The tool was built to be checked. These are what the checks returned, including the ones that went against it.">
      <Row numeral="i." figure={fixed(aucs[0].auc)} caption="best AUC of the variance screen, on six cartels" visual={<AucStrip />}
        title="Price screens work where every bid is published.">
        On six documented cartels the variance screen separates rigged tenders in {works} cases and
        fails in {aucs.length - works}.{" "}
        {alwaysChosen
          ? "Set any one case aside and learn from the other five, and it is still the screen they pick. "
          : ""}
        No screen works everywhere.
      </Row>
      <Row numeral="ii." figure={`${beatChance}/${leadChecks.length}`} caption="cases where leads beat a random pick" visual={<LeadCheck />}
        title="Who bids with whom does not find cartels.">
        Leads built only from participation and outcomes landed on none of the documented cartels.
        The graph shows where collusion would be easy, not where it happened.
      </Row>
      <Row numeral="iii." figure={`${data.summary.leads}`} caption={`leads among ${data.summary.groups} co-bidding groups in Assam`} visual={<GroupCloud />}
        title="Indian open data supports only the weaker screens.">
        Assam publishes who bid and who won, not what the losers bid. So its leads are a reading
        list and nothing more.
      </Row>
    </Section>
  );
}
