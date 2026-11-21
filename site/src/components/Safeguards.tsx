import { useInView } from "motion/react";
import { useEffect, useId, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { Reveal, Section } from "./ui";

const PROMISES = [
  {
    title: "Publish a name",
    body: "Firms, tenders and buyers appear as labels. The key that maps them back stays on the analyst’s machine.",
  },
  {
    title: "Save a report with a real name in it",
    body: "The finished page is searched for every real identifier. One match, and nothing is written.",
  },
  {
    title: "Call a pattern a finding",
    body: "Every lead lists the ordinary explanations to rule out first: a small local market, a stale estimate, a rule that piles bids at a floor.",
  },
  {
    title: "Redistribute the data",
    body: "Raw files hold the names of firms and of individual contractors. They are downloaded by the user and checked against a checksum.",
  },
];

/** One refusal: the thing it will not do, struck through once it is read. */
function Refusal({ index, title, body }: { index: number; title: string; body: string }) {
  const ref = useRef<HTMLLIElement>(null);
  const seen = useInView(ref, { once: true, amount: 0.8 });
  return (
    <li ref={ref} className="grid grid-cols-[36px_1fr] border-t border-line py-6 first:border-t-0 first:pt-0 md:grid-cols-[48px_1fr]">
      <span className="tabular pt-2 font-mono text-[12px] text-accent">0{index + 1}</span>
      <div>
        <h3 className="display text-[1.55rem] leading-[1.2] text-ink md:text-[1.75rem]">
          <span className="strike" style={{ "--strike": seen ? "100%" : "0%", transitionDelay: `${index * 0.12}s` } as CSSProperties}>
            {title}
          </span>
        </h3>
        <p className="mt-2.5 max-w-[52ch] text-[15.5px] leading-[1.7] text-ink-2">{body}</p>
      </div>
    </li>
  );
}

/** The same folding the tool applies before matching: case, punctuation, "M/s". */
function normalise(name: string): string {
  return name
    .replace(/^\s*m\s*\/\s*s\b\.?/i, " ")
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\bprivate\b/g, "pvt")
    .replace(/\blimited\b/g, "ltd")
    .trim();
}

/**
 * A working miniature of the labelling step. A key is generated in the
 * browser for this visit only, so the label shown here means nothing
 * outside this page, which is the point.
 */
function LabelDemo() {
  const inputId = useId();
  const helpId = useId();
  const key = useRef<CryptoKey | null>(null);
  const [name, setName] = useState("M/s. Northwind Example Traders");
  const [label, setLabel] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const supported = typeof crypto !== "undefined" && !!crypto.subtle;

  useEffect(() => {
    if (!supported) return;
    crypto.subtle.generateKey({ name: "HMAC", hash: "SHA-256" }, false, ["sign"]).then((made) => {
      key.current = made;
      setReady(true);
    });
  }, [supported]);

  useEffect(() => {
    const folded = normalise(name);
    if (!ready || !key.current || !folded) {
      setLabel(null);
      return;
    }
    let current = true;
    crypto.subtle.sign("HMAC", key.current, new TextEncoder().encode(folded)).then((digest) => {
      if (!current) return;
      const number = new DataView(digest).getUint32(0) % 100000;
      setLabel(`FIRM-${String(number).padStart(5, "0")}`);
    });
    return () => {
      current = false;
    };
  }, [name, ready]);

  return (
    <div className="bg-sunk p-6 sm:p-8">
      <p className="tabular font-mono text-[12px] text-muted">
        <span className="mr-2.5 text-accent">Fig. 7</span>Try it
      </p>
      <h3 className="display mt-2 text-[1.75rem] leading-tight text-ink">How a name becomes a label</h3>
      <div className="mt-7 grid gap-2">
        <label htmlFor={inputId} className="font-mono text-[12px] text-ink-2">
          Type any name
        </label>
        <input
          id={inputId}
          name="example-name"
          type="text"
          value={name}
          onChange={(event) => setName(event.target.value)}
          aria-describedby={helpId}
          autoComplete="off"
          spellCheck={false}
          className="w-full border-0 border-b border-ink bg-transparent px-0 py-2.5 text-[18px] text-ink outline-none transition-colors duration-200 placeholder:text-muted focus-visible:border-accent focus-visible:outline-none focus-visible:shadow-[0_1px_0_0_var(--accent)]"
        />
        <p id={helpId} className="text-[13.5px] leading-relaxed text-ink-2">
          Nothing you type leaves this page. Try the same name in capitals, or without the “M/s”.
        </p>
      </div>
      <div className="mt-8" aria-live="polite">
        <p className="font-mono text-[12px] text-muted">Appears in every report as</p>
        <p className="mt-3">
          <span
            translate="no"
            className="tabular inline-block border-2 border-accent px-3.5 py-1.5 font-mono text-[1.9rem] font-medium leading-none tracking-tight text-accent outline outline-1 outline-offset-[3px] outline-accent/50"
          >
            {supported ? (label ?? "FIRM-.....") : "unavailable"}
          </span>
        </p>
        <p className="mt-5 text-[13.5px] leading-relaxed text-ink-2">
          {supported
            ? "Spelling variants of one name get one label. The key was made for this visit and will be thrown away, so the same name gets a different label next time and the label cannot be reversed."
            : "This browser does not expose the cryptography needed for the demo. The tool itself uses the same keyed hash."}
        </p>
      </div>
    </div>
  );
}

export function Safeguards() {
  return (
    <Section id="safeguards" number="05" kicker="Safeguards" title="What it will not do"
      lead="A screen that attached company names to the word fraud would be reckless, and wrong most of the time. These limits are built into the code, and tested.">
      <div className="grid grid-cols-1 gap-x-12 gap-y-12 lg:grid-cols-12">
        <ol className="lg:col-span-7">
          {PROMISES.map((promise, i) => (
            <Refusal key={promise.title} index={i} {...promise} />
          ))}
        </ol>
        <Reveal delay={0.1} className="lg:col-span-5">
          <LabelDemo />
        </Reveal>
      </div>
    </Section>
  );
}
