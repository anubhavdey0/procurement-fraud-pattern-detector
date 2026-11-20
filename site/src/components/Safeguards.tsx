import { EyeSlash, FileX, ListChecks, LockKey } from "@phosphor-icons/react";
import { useEffect, useId, useRef, useState } from "react";
import { Reveal, Section } from "./ui";

const PROMISES = [
  {
    icon: EyeSlash,
    title: "Publish a name",
    body: "Firms, tenders and buyers appear as labels. The key that maps them back stays on the analyst's machine.",
  },
  {
    icon: FileX,
    title: "Save a report with a real name in it",
    body: "The finished page is searched for every real identifier. One match, and nothing is written.",
  },
  {
    icon: ListChecks,
    title: "Call a pattern a finding",
    body: "Every lead lists the ordinary explanations to rule out first: a small local market, a stale estimate, a rule that piles bids at a floor.",
  },
  {
    icon: LockKey,
    title: "Redistribute the data",
    body: "Raw files hold the names of firms and of individual contractors. They are downloaded by the user and checked against a checksum.",
  },
];

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
    <div className="rounded-2xl border border-line bg-surface p-6 sm:p-8">
      <h3 className="text-lg font-semibold tracking-tight text-ink">How a name becomes a label</h3>
      <div className="mt-6 grid gap-2">
        <label htmlFor={inputId} className="text-[14px] font-medium text-ink">
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
          className="w-full rounded-[10px] border border-line-strong bg-bg px-4 py-3 text-[16px] text-ink placeholder:text-muted focus-visible:border-accent"
        />
        <p id={helpId} className="text-[13.5px] leading-relaxed text-ink-2">
          Nothing you type leaves this page. Try the same name in capitals, or without the “M/s”.
        </p>
      </div>
      <div className="mt-6 border-t border-line pt-6" aria-live="polite">
        <p className="text-[13px] text-muted">Appears in every report as</p>
        <p className="tabular mt-1 min-h-[2.75rem] font-mono text-4xl font-medium tracking-tight text-ink" translate="no">
          {supported ? (label ?? "FIRM-.....") : "unavailable"}
        </p>
        <p className="mt-3 text-[13.5px] leading-relaxed text-ink-2">
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
    <Section id="safeguards" title="What it will not do"
      lead="A screen that attached company names to the word fraud would be reckless, and wrong most of the time. These limits are built into the code, and tested.">
      <div className="grid gap-10 lg:grid-cols-12 grid-cols-1">
        <ul className="grid content-start gap-x-10 gap-y-9 sm:grid-cols-2 lg:col-span-7 grid-cols-1">
          {PROMISES.map(({ icon: Icon, title, body }, i) => (
            <li key={title}>
              <Reveal delay={i * 0.05}>
                <Icon size={26} weight="light" aria-hidden="true" className="text-accent" />
                <h3 className="mt-4 text-[17px] font-semibold tracking-tight text-ink">{title}</h3>
                <p className="mt-2 max-w-[38ch] text-[15px] leading-relaxed text-ink-2">{body}</p>
              </Reveal>
            </li>
          ))}
        </ul>
        <Reveal delay={0.1} className="lg:col-span-5">
          <LabelDemo />
        </Reveal>
      </div>
    </Section>
  );
}
