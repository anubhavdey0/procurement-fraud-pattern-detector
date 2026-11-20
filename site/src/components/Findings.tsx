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

/** Six cases on one axis: where the variance screen works and where it fails. */
function AucStrip() {
  const x = (auc: number) => 8 + ((auc - 0.3) / 0.7) * 224;
  return (
    <svg viewBox="0 0 240 64" className="block h-auto w-full max-w-[300px]" role="img"
      aria-label={`AUC of the variance screen in six cases, from ${fixed(aucs[aucs.length - 1].auc)} to ${fixed(aucs[0].auc)}. 0.5 is a coin toss.`}>
      <line x1="8" x2="232" y1="30" y2="30" stroke="var(--line-strong)" />
      <line x1={x(0.5)} x2={x(0.5)} y1="14" y2="46" stroke="var(--muted)" />
      <text x={x(0.5)} y="60" textAnchor="middle" fontSize="10" fill="var(--muted)">coin toss</text>
      {aucs.map((item) => (
        <circle key={item.title} cx={x(item.auc)} cy="30" r="5.5"
          fill={item.auc >= 0.6 ? "var(--accent)" : "var(--context)"} stroke="var(--surface)" strokeWidth="2">
          <title>{`${item.title}: ${fixed(item.auc)}`}</title>
        </circle>
      ))}
      <text x={x(aucs[0].auc)} y="14" textAnchor="middle" fontSize="10.5" fill="var(--ink)" className="tabular font-mono">
        {fixed(aucs[0].auc)}
      </text>
    </svg>
  );
}

/** For each case: how often flagged tenders were cartel tenders, against a random pick. */
function LeadCheck() {
  const scale = (value: number) => 4 + (value / 0.6) * 150;
  return (
    <ul className="grid max-w-[300px] gap-2 text-[12.5px] text-ink-2">
      {leadChecks.map((row) => (
        <li key={row.case} className="grid grid-cols-[1fr_158px] items-center gap-3">
          <span className="truncate">{titleOf(row.case).split(": ")[1]}</span>
          <svg viewBox="0 0 158 14" className="block h-auto w-full" role="img"
            aria-label={`${titleOf(row.case)}: ${row.leads === 0 ? "no leads" : `${percent(row.precision)} of flagged tenders were cartel tenders`}, against ${percent(row.base_rate)} for a random pick.`}>
            <line x1="4" x2="154" y1="7" y2="7" stroke="var(--line-strong)" />
            <circle cx={scale(row.base_rate)} cy="7" r="4" fill="var(--context)" />
            {row.leads > 0 && row.precision != null ? (
              <circle cx={scale(row.precision)} cy="7" r="4.5" fill="var(--accent)" stroke="var(--surface)" strokeWidth="1.5" />
            ) : null}
          </svg>
        </li>
      ))}
      <li className="mt-1 flex gap-4 text-[11.5px] text-muted">
        <span className="flex items-center gap-1.5"><i aria-hidden="true" className="size-2 rounded-full bg-accent" />flagged tenders</span>
        <span className="flex items-center gap-1.5"><i aria-hidden="true" className="size-2 rounded-full bg-context" />random pick</span>
      </li>
    </ul>
  );
}

/** Every co-bidding group as a dot; the leads are the few in colour. */
function GroupCloud() {
  const top = Math.max(...data.groups.map((group) => group.joint));
  const y = (joint: number) => 58 - (Math.log10(Math.max(joint, 2)) / Math.log10(top)) * 50;
  return (
    <svg viewBox="0 0 240 64" className="block h-auto w-full max-w-[300px]" role="img"
      aria-label={`${data.summary.groups} co-bidding groups plotted by how closed they are. ${data.summary.leads} are leads.`}>
      {data.groups.map((group) => {
        const lead = group.screens.length >= 2;
        return (
          <circle key={group.id} cx={6 + group.exclusivity * 228} cy={y(group.joint)} r={lead ? 3.6 : 1.7}
            fill={lead ? "var(--accent)" : "var(--context)"} opacity={lead ? 1 : 0.55} />
        );
      })}
    </svg>
  );
}

function Row({ figure, caption, title, children, visual }: {
  figure: string; caption: string; title: string; children: ReactNode; visual: ReactNode;
}) {
  return (
    <Reveal className="grid items-center gap-x-10 gap-y-6 border-t border-line py-10 first:border-t-0 first:pt-0 md:grid-cols-12 md:py-12 grid-cols-1">
      <div className="md:col-span-3">
        <p className="tabular font-mono text-5xl font-medium tracking-tight text-ink md:text-6xl">{figure}</p>
        <p className="mt-2 text-[13px] text-muted">{caption}</p>
      </div>
      <div className="md:col-span-5">
        <h3 className="text-xl font-semibold tracking-tight text-ink md:text-2xl">{title}</h3>
        <p className="mt-3 max-w-[46ch] leading-relaxed text-ink-2">{children}</p>
      </div>
      <div className="md:col-span-4 md:justify-self-end">{visual}</div>
    </Reveal>
  );
}

export function Findings() {
  return (
    <Section id="findings" title="Three results, by how much weight they bear"
      lead="The tool was built to be checked. These are what the checks returned, including the ones that went against it.">
      <Row figure={fixed(aucs[0].auc)} caption="best AUC of the variance screen" visual={<AucStrip />}
        title="Price screens work where every bid is published.">
        On six documented cartels the variance screen separates rigged tenders in {works} cases and
        fails in {aucs.length - works}. No screen works everywhere.
      </Row>
      <Row figure={`${beatChance} of ${leadChecks.length}`} caption="cases where leads beat a random pick" visual={<LeadCheck />}
        title="Who bids with whom does not find cartels.">
        Leads built only from participation and outcomes landed on none of the documented cartels.
        The graph shows where collusion would be easy, not where it happened.
      </Row>
      <Row figure={`${data.summary.leads} / ${data.summary.groups}`} caption="leads among co-bidding groups in Assam" visual={<GroupCloud />}
        title="Indian open data supports only the weaker screens.">
        Assam publishes who bid and who won, not what the losers bid. So its leads are a reading
        list and nothing more.
      </Row>
    </Section>
  );
}
