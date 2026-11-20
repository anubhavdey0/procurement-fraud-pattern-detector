import { LayoutGroup, motion, useReducedMotion } from "motion/react";
import { useMemo, useRef, useState } from "react";
import type { KeyboardEvent, PointerEvent } from "react";
import { data } from "../lib/data";
import type { GroupPoint, Lead } from "../lib/data";
import { count, fixed, percent } from "../lib/format";
import { BipartiteGraph, GraphKey } from "./BipartiteGraph";
import { Label, Reveal, Section } from "./ui";

const { summary, groups, leads, price, config } = data;
const isLead = (group: GroupPoint) => group.screens.length >= config.min_screens;
const labelOf = Object.fromEntries(data.screens.map((screen) => [screen.key, screen.label]));

// ------------------------------------------------------------------ scatter

function Scatter({ selected, onSelect }: { selected: string; onSelect: (id: string) => void }) {
  const W = 760, H = 400, left = 54, right = 22, top = 26, bottom = 48;
  const plotW = W - left - right, plotH = H - top - bottom;
  const hi = Math.max(...groups.map((group) => group.joint)) * 1.25, lo = 2.4;
  const x = (value: number) => left + value * plotW;
  const y = (value: number) =>
    top + plotH - ((Math.log10(Math.max(value, 3)) - Math.log10(lo)) / (Math.log10(hi) - Math.log10(lo))) * plotH;
  const ticks = [3, 10, 30, 100, 300].filter((tick) => tick < hi);
  const frame = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<GroupPoint | null>(null);
  const ordered = useMemo(() => [...groups].sort((a, b) => Number(isLead(a)) - Number(isLead(b))), []);

  const onMove = (event: PointerEvent<SVGSVGElement>) => {
    const box = frame.current!.getBoundingClientRect();
    const px = ((event.clientX - box.left) / box.width) * W;
    const py = ((event.clientY - box.top) / box.height) * H;
    let best: GroupPoint | null = null;
    let nearest = 24 * 24;
    for (const group of groups) {
      const d = (x(group.exclusivity) - px) ** 2 + (y(group.joint) - py) ** 2;
      if (d < nearest) {
        nearest = d;
        best = group;
      }
    }
    setHover((current) => (current?.id === best?.id ? current : best));
  };
  const onKey = (event: KeyboardEvent, id: string) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect(id);
    }
  };

  return (
    <div className="relative">
      <svg ref={frame} viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" onPointerMove={onMove} onPointerLeave={() => setHover(null)}
        onClick={() => hover && isLead(hover) && onSelect(hover.id)} role="group"
        aria-label={`Scatter plot of ${summary.groups} co-bidding groups. Horizontal: exclusivity from 0 to 1. Vertical: tenders with two or more members bidding, on a log scale. ${summary.leads} leads are highlighted.`}>
        {ticks.map((tick) => (
          <g key={tick}>
            <line x1={left} x2={W - right} y1={y(tick)} y2={y(tick)} stroke="var(--line)" />
            <text x={left - 10} y={y(tick) + 4} textAnchor="end" fontSize={11} fill="var(--muted)" className="tabular font-mono">{tick}</text>
          </g>
        ))}
        {[0, 0.2, 0.4, 0.6, 0.8, 1].map((tick) => (
          <text key={tick} x={x(tick)} y={H - bottom + 18} textAnchor="middle" fontSize={11} fill="var(--muted)" className="tabular font-mono">{tick.toFixed(1)}</text>
        ))}
        <line x1={left} x2={W - right} y1={top + plotH} y2={top + plotH} stroke="var(--line-strong)" />
        <line x1={x(config.exclusivity_min)} x2={x(config.exclusivity_min)} y1={top} y2={top + plotH} stroke="var(--muted)" />
        <text x={x(config.exclusivity_min) + 7} y={top + 11} fontSize={11.5} fill="var(--ink-2)">closed-group threshold</text>
        <text x={left + plotW / 2} y={H - 8} textAnchor="middle" fontSize={12} fill="var(--ink-2)">Exclusivity: share of the group's co-bidding that is with each other</text>
        <text x={left - 42} y={12} fontSize={12} fill="var(--ink-2)">Joint tenders</text>
        {ordered.map((group) => {
          const lead = isLead(group);
          const cx = x(group.exclusivity), cy = y(group.joint);
          return lead ? (
            <g key={group.id}>
              {selected === group.id ? <circle cx={cx} cy={cy} r={10} fill="none" stroke="var(--ink)" strokeWidth={1.5} /> : null}
              <circle cx={cx} cy={cy} r={6} fill="var(--accent)" stroke="var(--surface)" strokeWidth={2} tabIndex={0} role="button"
                aria-label={`Lead ${group.id}: ${group.size} firms, exclusivity ${fixed(group.exclusivity)}, ${group.joint} joint tenders. Show it below.`}
                onFocus={() => setHover(group)} onBlur={() => setHover(null)} onKeyDown={(event) => onKey(event, group.id)} className="cursor-pointer" />
            </g>
          ) : (
            <circle key={group.id} cx={cx} cy={cy} r={hover?.id === group.id ? 5 : 3.6} fill="var(--context)" opacity={0.75} stroke="var(--surface)" strokeWidth={1} />
          );
        })}
      </svg>
      {hover ? (
        <div role="presentation" className="pointer-events-none absolute z-10 w-max max-w-[240px] -translate-x-1/2 -translate-y-[calc(100%+14px)] rounded-lg bg-ink px-3 py-2 text-[12.5px] leading-snug text-bg"
          style={{ left: `${(x(hover.exclusivity) / W) * 100}%`, top: `${(y(hover.joint) / H) * 100}%` }}>
          <strong className="block font-medium">
            <Label>{hover.id}</Label>: {hover.size} firms, {hover.joint} joint tenders
          </strong>
          <span className="opacity-80">
            exclusivity {fixed(hover.exclusivity)}
            {hover.screens.length ? `, fired: ${hover.screens.map((key) => labelOf[key].toLowerCase()).join(", ")}` : ", no screen fired"}
          </span>
        </div>
      ) : null}
      <ul className="mt-1 flex flex-wrap gap-x-6 gap-y-1 text-[13px] text-ink-2">
        <li className="flex items-center gap-2"><i aria-hidden="true" className="size-2.5 rounded-full bg-accent" />Lead for review: select one to open it below</li>
        <li className="flex items-center gap-2"><i aria-hidden="true" className="size-2.5 rounded-full bg-context" />Other group</li>
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------- histogram

function Histogram() {
  const W = 760, H = 290, left = 54, right = 18, top = 52, bottom = 44;
  const plotW = W - left - right, plotH = H - top - bottom;
  const peak = Math.max(...price.bins.map((bin) => bin.count));
  const step = peak > 1000 ? 500 : peak > 400 ? 200 : 100;
  const ceiling = Math.ceil(peak / step) * step;
  const slot = plotW / price.bins.length;
  const y = (value: number) => top + plotH - (value / ceiling) * plotH;
  const peaks = [...price.bins].sort((a, b) => b.count - a.count).slice(0, 2).filter((bin) => bin.count / price.n >= 0.05).sort((a, b) => a.at - b.at);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" role="img"
      aria-label={`Histogram of award value divided by the buyer's estimate for ${count(price.n)} awards. ${peaks.map((bin) => `${percent(bin.count / price.n)} at ${fixed(bin.at)}`).join(" and ")}.`}>
      {Array.from({ length: ceiling / step + 1 }, (_, i) => i * step).map((tick) => (
        <g key={tick}>
          <line x1={left} x2={W - right} y1={y(tick)} y2={y(tick)} stroke="var(--line)" />
          <text x={left - 10} y={y(tick) + 4} textAnchor="end" fontSize={11} fill="var(--muted)" className="tabular font-mono">{count(tick)}</text>
        </g>
      ))}
      {price.bins.map((bin, i) => {
        if (!bin.count) return null;
        const width = Math.max(slot - 2, 1), bx = left + i * slot + 1, by = y(bin.count), bh = y(0) - by;
        const r = Math.min(3, width / 2, bh);
        return (
          <path key={bin.at} fill="var(--accent)"
            d={`M${bx},${by + bh} L${bx},${by + r} Q${bx},${by} ${bx + r},${by} L${bx + width - r},${by} Q${bx + width},${by} ${bx + width},${by + r} L${bx + width},${by + bh} Z`}>
            <title>{`${count(bin.count)} awards at ${fixed(bin.at)} of the estimate`}</title>
          </path>
        );
      })}
      <line x1={left} x2={W - right} y1={y(0)} y2={y(0)} stroke="var(--line-strong)" />
      {[0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3].map((tick) => (
        <text key={tick} x={left + ((tick - 0.6) / 0.7) * (plotW - slot) + slot / 2} y={y(0) + 18} textAnchor="middle" fontSize={11} fill="var(--muted)" className="tabular font-mono">{tick.toFixed(2)}</text>
      ))}
      {peaks.map((bin, i) => {
        const cx = left + price.bins.findIndex((b) => b.at === bin.at) * slot + slot / 2;
        const anchor = i === 0 && peaks.length > 1 ? "end" : "start";
        return (
          <g key={bin.at}>
            <line x1={cx} x2={cx} y1={top - 26 + i * 16} y2={y(bin.count) - 4} stroke="var(--muted)" />
            <text x={cx + (anchor === "start" ? 7 : -7)} y={top - 30 + i * 16} textAnchor={anchor} fontSize={12} fill="var(--ink)">
              {percent(bin.count / price.n)} of awards at {fixed(bin.at)} of the estimate
            </text>
          </g>
        );
      })}
      <text x={left + plotW / 2} y={H - 6} textAnchor="middle" fontSize={12} fill="var(--ink-2)">Award value divided by the buyer's estimate</text>
    </svg>
  );
}

// ------------------------------------------------------------ lead explorer

function LeadPanel({ lead }: { lead: Lead }) {
  const plotHeight = Math.min(Math.max(lead.graph.tenders.length * 12, 200), 430);
  return (
    <div role="tabpanel" id={`panel-${lead.id}`} aria-labelledby={`tab-${lead.id}`} tabIndex={0} className="grid gap-x-10 gap-y-8 lg:grid-cols-12 grid-cols-1">
      <div className="lg:col-span-7">
        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
          <h4 className="text-xl font-semibold tracking-tight text-ink">
            <Label>{lead.id}</Label>: {lead.size} firms, {lead.joint} joint tenders
          </h4>
          <GraphKey />
        </div>
        <p className="mt-1.5 text-[14px] text-ink-2">
          {lead.period}. Members won {lead.wins} of {lead.decided} decided tenders. On {lead.closed} tenders nobody outside the group bid.
        </p>
        <div className="mt-4">
          <BipartiteGraph graph={lead.graph} step={0.035} runId={lead.id} plotHeight={plotHeight}
            description={`Bipartite graph for lead ${lead.id}: ${lead.size} member firms and the ${lead.graph.tenders.length} tenders they bid on together.`} />
        </div>
        {lead.graph.total > lead.graph.tenders.length ? (
          <p className="mt-2 text-[13px] text-muted">Showing the first {lead.graph.tenders.length} of {lead.graph.total} joint tenders.</p>
        ) : null}
      </div>
      <div className="lg:col-span-5">
        <ul>
          {lead.screens.map((screen) => (
            <li key={screen.key} className="border-t border-line py-4 first:border-t-0 first:pt-0">
              <p className="flex items-center gap-2.5 text-[15px]">
                <i aria-hidden="true" className={`size-2.5 rounded-full border ${screen.fired ? "border-accent bg-accent" : "border-context"}`} />
                <span className="font-medium text-ink">{screen.label}</span>
                <span className="text-[13px] text-muted">{screen.fired ? "fired" : "did not fire"}</span>
              </p>
              <p className="mt-1.5 text-[14px] leading-relaxed text-ink-2">{screen.text}</p>
            </li>
          ))}
        </ul>
        <h5 className="mt-6 text-[13px] font-medium text-muted">Rule these out first</h5>
        <ul className="mt-2 grid gap-1.5 text-[14px] leading-relaxed text-ink-2">
          {lead.rule_out.map((item) => (
            <li key={item} className="grid grid-cols-[14px_1fr]"><span aria-hidden="true" className="text-context">/</span>{item}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function LeadExplorer({ selected, onSelect }: { selected: string; onSelect: (id: string) => void }) {
  const reduce = useReducedMotion();
  const lead = leads.find((item) => item.id === selected) ?? leads[0];
  const onKey = (event: KeyboardEvent<HTMLDivElement>) => {
    const index = leads.findIndex((item) => item.id === lead.id);
    const move = event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : event.key === "ArrowLeft" || event.key === "ArrowUp" ? -1 : 0;
    if (!move) return;
    event.preventDefault();
    const next = leads[(index + move + leads.length) % leads.length];
    onSelect(next.id);
    document.getElementById(`tab-${next.id}`)?.focus();
  };

  return (
    <div>
      <LayoutGroup>
        <div role="tablist" aria-label="Leads" onKeyDown={onKey} className="-mx-1 flex gap-1 overflow-x-auto px-1 pb-2">
          {leads.map((item) => {
            const active = item.id === lead.id;
            return (
              <button key={item.id} type="button" role="tab" id={`tab-${item.id}`} aria-selected={active} aria-controls={`panel-${item.id}`}
                tabIndex={active ? 0 : -1} onClick={() => onSelect(item.id)}
                className={`relative shrink-0 rounded-full px-4 py-2 font-mono text-[13.5px] transition-colors ${active ? "text-accent-ink" : "text-ink-2 hover:text-ink"}`}>
                {active ? (
                  <motion.span layoutId="lead-tab" className="absolute inset-0 rounded-full bg-accent"
                    transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 380, damping: 32 }} />
                ) : null}
                <span className="relative" translate="no">{item.id}</span>
              </button>
            );
          })}
        </div>
      </LayoutGroup>
      <div className="mt-6">
        <LeadPanel lead={lead} />
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ section

const STATS: [string, number][] = [
  ["Tenders in the source", summary.tenders],
  ["Tenders that list who bid", summary.with_bidders],
  ["Distinct bidders, matched by name", summary.bidders],
  ["Pairs that ever bid together", summary.pairs],
  ["Pairs linked beyond chance", summary.links],
  ["Co-bidding groups", summary.groups],
  ["Leads: two or more screens", summary.leads],
];

export function Assam() {
  const [selected, setSelected] = useState(leads[0]?.id ?? "");
  const choose = (id: string) => {
    setSelected(id);
    document.getElementById("lead-explorer")?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  };
  const peaks = [...price.bins].sort((a, b) => b.count - a.count).slice(0, 2).sort((a, b) => a.at - b.at);

  return (
    <Section id="assam" title={`Run on ${count(summary.with_bidders)} tenders from Assam`} wide
      lead={`The state's open data lists who bid and who won, not what the losers bid. Of ${summary.groups} co-bidding groups, ${summary.leads} had two or more screens fire. None of this is a finding.`}>
      <div className="grid gap-5 lg:grid-cols-12 grid-cols-1">
        <Reveal className="rounded-2xl border border-line bg-surface p-5 sm:p-7 lg:col-span-8">
          <h3 className="text-lg font-semibold tracking-tight text-ink">Every co-bidding group</h3>
          <p className="mt-1.5 max-w-[60ch] text-[14.5px] leading-relaxed text-ink-2">Most groups are what a local market looks like. The further right, the more a group bids only with itself.</p>
          <div className="mt-5"><Scatter selected={selected} onSelect={choose} /></div>
        </Reveal>
        <Reveal delay={0.06} className="rounded-2xl border border-line bg-surface p-5 sm:p-7 lg:col-span-4">
          <h3 className="text-lg font-semibold tracking-tight text-ink">The funnel</h3>
          <dl className="mt-4">
            {STATS.map(([label, value], i) => (
              <div key={label} className="flex items-baseline justify-between gap-4 border-t border-line py-3 first:border-t-0">
                <dt className="text-[14px] text-ink-2">{label}</dt>
                <dd className={`tabular font-mono text-[15px] ${i === STATS.length - 1 ? "font-semibold text-accent" : "text-ink"}`}>{count(value)}</dd>
              </div>
            ))}
          </dl>
        </Reveal>
        <Reveal className="grid items-center gap-x-10 gap-y-6 rounded-2xl border border-line bg-surface p-5 sm:p-7 lg:col-span-12 lg:grid-cols-12 grid-cols-1">
          <div className="lg:col-span-4">
            <h3 className="text-lg font-semibold tracking-tight text-ink">Prices pile up at two values</h3>
            <p className="mt-3 text-[14.5px] leading-relaxed text-ink-2">
              {percent(peaks[0].count / price.n)} of awards sit at {fixed(peaks[0].at)} of the buyer's estimate and {percent(peaks[1].count / price.n)} at {fixed(peaks[1].at)}.
              Piles like these usually come from a rule, such as a floor below which a bid is treated as abnormally low.
            </p>
            <p className="mt-3 text-[14.5px] leading-relaxed text-ink-2">So the price screen compares a group only with other tenders from the same buyer and region.</p>
          </div>
          <div className="lg:col-span-8"><Histogram /></div>
        </Reveal>
        <Reveal className="rounded-2xl border border-line bg-surface p-5 sm:p-7 lg:col-span-12">
          <div id="lead-explorer" className="scroll-mt-24">
            <h3 className="text-lg font-semibold tracking-tight text-ink">The {summary.leads} leads</h3>
            <p className="mt-1.5 max-w-[64ch] text-[14.5px] leading-relaxed text-ink-2">Firms and tenders appear as labels, and dates to the month. Each lead lists the ordinary explanations to rule out before reading anything into it.</p>
            <div className="mt-6"><LeadExplorer selected={selected} onSelect={setSelected} /></div>
          </div>
        </Reveal>
      </div>
    </Section>
  );
}
