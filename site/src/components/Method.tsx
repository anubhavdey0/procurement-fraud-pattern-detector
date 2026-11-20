import { motion, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { data } from "../lib/data";
import { Section } from "./ui";

const STEPS = [
  {
    title: "A bid is a link.",
    body: "Firms on one side, tenders on the other. Every bid joins one firm to one tender. That is the whole dataset, drawn as a graph.",
  },
  {
    title: "Fold the graph onto firms.",
    body: `Two firms are tied when they bid on at least ${data.config.min_joint} tenders together, and that is more than chance allows. Occasional encounters drop away.`,
  },
  {
    title: "Grow the closed groups.",
    body: "A group whose bidding is mostly with itself is where collusion would be easiest to sustain. Its exclusivity is tested against reshuffled copies of the market.",
  },
  {
    title: "Ask four questions of each group.",
    body: `Is it closed? Do winners rotate? Does one member always lose? Do awards sit near the estimate? ${["No", "One", "Two", "Three", "Four"][data.config.min_screens] ?? data.config.min_screens} yeses make a lead, and a lead is only a reason to open the files.`,
  },
];

// A small invented market: firms 0 to 2 keep meeting, firms 3 to 5 do not.
const BIDS: [number, number][] = [
  [0, 0], [1, 0], [2, 0], [0, 1], [1, 1], [1, 2], [2, 2], [0, 3], [2, 3], [3, 3],
  [3, 4], [4, 4], [4, 5], [5, 5], [3, 6], [5, 6],
];
const LINKS: [number, number, number][] = [
  [0, 1, 2], [0, 2, 2], [1, 2, 2], [0, 3, 1], [2, 3, 1], [3, 4, 1], [4, 5, 1], [3, 5, 1],
];
const COLUMN = [0, 1, 2, 3, 4, 5].map((i) => ({ x: 118, y: 62 + i * 55 }));
const NETWORK = [
  { x: 128, y: 112 }, { x: 236, y: 128 }, { x: 170, y: 222 },
  { x: 352, y: 168 }, { x: 306, y: 300 }, { x: 424, y: 286 },
];
const TENDERS = [0, 1, 2, 3, 4, 5, 6].map((j) => ({ x: 402, y: 50 + j * 50 }));
const SCREENS = data.screens.map((screen, i) => ({ label: screen.label, fired: i === 0 || i === 3 }));

function Graphic({ step }: { step: number }) {
  const reduce = useReducedMotion();
  const spring = reduce ? { duration: 0 } : { type: "spring" as const, stiffness: 110, damping: 20 };
  const fade = reduce ? { duration: 0 } : { duration: 0.45 };
  const position = step === 0 ? COLUMN : NETWORK;
  const inGroup = (i: number) => i <= 2;

  return (
    <svg viewBox="0 0 520 400" role="img" className="block h-auto w-full"
      aria-label={`Diagram, step ${step + 1} of ${STEPS.length}: ${STEPS[step].title}`}>
      <motion.circle cx={178} cy={154} r={104} fill="color-mix(in oklab, var(--accent) 9%, transparent)"
        stroke="var(--accent)" strokeWidth={1.4} style={{ transformOrigin: "178px 154px" }}
        initial={false} animate={{ opacity: step >= 2 ? 1 : 0, scale: step >= 2 ? 1 : 0.86 }} transition={spring} />

      {BIDS.map(([firm, tender]) => (
        <motion.line key={`b${firm}-${tender}`} x1={COLUMN[firm].x} y1={COLUMN[firm].y} x2={TENDERS[tender].x} y2={TENDERS[tender].y}
          stroke="var(--context)" strokeWidth={1.1} initial={false} animate={{ opacity: step === 0 ? 0.75 : 0 }} transition={fade} />
      ))}
      {TENDERS.map((tender, j) => (
        <motion.circle key={`t${j}`} cx={tender.x} cy={tender.y} r={5} fill="var(--context)" initial={false}
          animate={{ opacity: step === 0 ? 1 : 0 }} transition={fade} />
      ))}

      {LINKS.map(([a, b, weight]) => {
        const inside = inGroup(a) && inGroup(b);
        const opacity = step === 0 ? 0 : step === 1 ? 0.85 : inside ? 1 : step === 3 ? 0 : 0.22;
        return (
          <motion.line key={`l${a}-${b}`} stroke={inside && step >= 2 ? "var(--accent)" : "var(--ink-2)"} strokeLinecap="round"
            strokeWidth={weight === 2 ? 3 : 1.2} initial={false}
            animate={{ x1: NETWORK[a].x, y1: NETWORK[a].y, x2: NETWORK[b].x, y2: NETWORK[b].y, opacity }} transition={fade} />
        );
      })}

      {position.map((point, i) => {
        const dim = step >= 2 && !inGroup(i);
        return (
          <motion.circle key={`f${i}`} r={9} stroke="var(--surface)" strokeWidth={2.5} initial={false}
            fill={step >= 2 && inGroup(i) ? "var(--accent)" : "var(--ink)"}
            animate={{ cx: point.x, cy: point.y, opacity: dim ? (step === 3 ? 0 : 0.28) : 1 }} transition={spring} />
        );
      })}

      <motion.g initial={false} animate={{ opacity: step === 0 ? 1 : 0 }} transition={fade}>
        <text x={118} y={30} textAnchor="middle" fontSize={12} fill="var(--muted)">Firms</text>
        <text x={402} y={30} textAnchor="middle" fontSize={12} fill="var(--muted)">Tenders</text>
      </motion.g>
      <motion.g initial={false} animate={{ opacity: step === 2 ? 1 : 0 }} transition={fade}>
        <text x={178} y={292} textAnchor="middle" fontSize={12.5} fill="var(--ink)" className="tabular font-mono">exclusivity 0.74</text>
        <text x={178} y={310} textAnchor="middle" fontSize={11.5} fill="var(--muted)">share of bidding kept inside the group</text>
      </motion.g>

      {SCREENS.map((screen, i) => (
        <motion.g key={screen.label} initial={false}
          animate={{ opacity: step === 3 ? 1 : 0, x: step === 3 ? 0 : 14 }}
          transition={reduce ? { duration: 0 } : { duration: 0.45, delay: step === 3 ? 0.12 + i * 0.09 : 0 }}>
          <rect x={300} y={78 + i * 62} width={204} height={46} rx={10} fill="var(--surface)"
            stroke={screen.fired ? "var(--accent)" : "var(--line-strong)"} strokeWidth={screen.fired ? 1.6 : 1} />
          <circle cx={320} cy={101 + i * 62} r={5} fill={screen.fired ? "var(--accent)" : "none"}
            stroke={screen.fired ? "var(--accent)" : "var(--context)"} strokeWidth={1.5} />
          <text x={336} y={97 + i * 62} fontSize={12.5} fill="var(--ink)">{screen.label}</text>
          <text x={336} y={113 + i * 62} fontSize={11} fill="var(--muted)">{screen.fired ? "fired" : "did not fire"}</text>
        </motion.g>
      ))}
      <motion.text x={402} y={346} textAnchor="middle" fontSize={12.5} fill="var(--ink)" initial={false}
        animate={{ opacity: step === 3 ? 1 : 0 }} transition={fade}>
        2 screens fired: a lead for review
      </motion.text>
    </svg>
  );
}

export function Method() {
  const [active, setActive] = useState(0);
  const refs = useRef<(HTMLElement | null)[]>([]);

  useEffect(() => {
    // The step crossing the middle of the viewport is the active one.
    // On small screens the diagram is pinned at the top, so the step that
    // counts is the one in the lower part of the viewport.
    const small = window.matchMedia("(max-width: 1023px)").matches;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setActive(Number((entry.target as HTMLElement).dataset.step));
        }
      },
      { rootMargin: small ? "-62% 0px -30% 0px" : "-45% 0px -45% 0px" },
    );
    refs.current.forEach((node) => node && observer.observe(node));
    return () => observer.disconnect();
  }, []);

  return (
    <Section id="method" title="From a table of bids to a short reading list"
      lead="Every step is a published method with a stated null model. Scroll to follow one small market through all four.">
      <div className="grid gap-x-10 lg:grid-cols-12 grid-cols-1">
        <div className="sticky top-16 z-10 -mx-5 border-b border-line bg-bg px-5 pb-3 pt-2 lg:top-24 lg:col-span-7 lg:mx-0 lg:self-start lg:border-0 lg:bg-transparent lg:p-0">
          <div className="rounded-2xl border border-line bg-surface p-3 sm:p-6">
            <div className="mx-auto max-w-[280px] sm:max-w-[360px] lg:max-w-none">
              <Graphic step={active} />
            </div>
            <ol className="mt-2 flex justify-center gap-2" aria-label="Progress">
              {STEPS.map((step, i) => (
                <li key={step.title} aria-current={i === active ? "step" : undefined}
                  className={`h-1 rounded-full transition-[width,background-color] duration-300 ${i === active ? "w-8 bg-accent" : "w-3 bg-line-strong"}`}>
                  <span className="sr-only">{step.title}</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
        <div className="lg:col-span-4 lg:col-start-9">
          {STEPS.map((step, i) => (
            <article key={step.title} data-step={i} ref={(node) => { refs.current[i] = node; }}
              className="flex min-h-[60vh] flex-col justify-end pb-[14vh] pt-10 lg:min-h-[68vh] lg:justify-center lg:py-10">
              <h3 className={`text-2xl font-semibold tracking-tight transition-colors duration-300 ${i === active ? "text-ink" : "text-muted"}`}>
                {step.title}
              </h3>
              <p className="mt-4 max-w-[40ch] leading-relaxed text-ink-2">{step.body}</p>
            </article>
          ))}
        </div>
      </div>
    </Section>
  );
}
