import { ArrowUpRight, Check, Copy } from "@phosphor-icons/react";
import { useState } from "react";
import { data, REPO } from "../lib/data";
import { CONTAINER, Reveal, Section } from "./ui";

const COMMANDS = [
  `git clone ${REPO}.git`,
  "cd procurement-fraud-pattern-detector",
  "pip install -e .",
  "bidscreen demo",
];

const LINKS = [
  {
    href: "./report/assam.html",
    title: "Open the sample report",
    body: "The full Assam report as the tool writes it: one self-contained page.",
  },
  {
    href: `${REPO}/blob/main/docs/methodology.md`,
    title: "Read the method",
    body: "Every formula, null model and threshold, and where they differ from the papers.",
  },
  {
    href: `${REPO}/blob/main/docs/responsible-use.md`,
    title: "Read the rules of use",
    body: "What a lead is, how often leads are wrong, and what not to do with one.",
  },
];

function CopyButton() {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(COMMANDS.join("\n"));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  };
  return (
    <button
      type="button"
      onClick={copy}
      className="-mr-2 flex items-center gap-1.5 rounded-[3px] px-2 py-1.5 text-[13px] text-ink-2 transition-colors duration-200 hover:bg-mid hover:text-ink active:translate-y-px"
    >
      {copied ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
      <span aria-live="polite">{copied ? "Copied" : "Copy"}</span>
    </button>
  );
}

export function Start() {
  return (
    <Section
      id="start"
      number="06"
      kicker="Run it"
      title="Run it yourself"
      lead="The demo needs no download. It runs every screen on a synthetic market with a planted cartel and writes a report."
    >
      <div className="grid grid-cols-1 gap-x-12 gap-y-12 lg:grid-cols-12">
        <Reveal className="lg:col-span-7">
          <div className="bg-sunk">
            <div className="flex items-center justify-between border-b border-line-strong px-5 py-2">
              <p className="font-mono text-[12px] text-muted">Python 3.10 or later</p>
              <CopyButton />
            </div>
            <pre className="overflow-x-auto px-5 py-5 font-mono text-[14px] leading-7 text-ink" tabIndex={0}>
              <code>
                {COMMANDS.map((line) => (
                  <span key={line} className="block whitespace-pre">
                    <span aria-hidden="true" className="select-none text-accent">
                      ${" "}
                    </span>
                    {line}
                  </span>
                ))}
              </code>
            </pre>
          </div>
          <p className="mt-5 max-w-[62ch] text-[15px] leading-[1.7] text-ink-2">
            To reproduce the real results, run <code className="font-mono text-[0.92em] text-ink">bidscreen fetch</code>,{" "}
            <code className="font-mono text-[0.92em] text-ink">bidscreen validate</code> and{" "}
            <code className="font-mono text-[0.92em] text-ink">bidscreen screen assam</code>. Downloads are pinned to a
            commit and checked against a checksum.
          </p>
        </Reveal>
        <ul className="border-t border-line-strong lg:col-span-5">
          {LINKS.map((link, i) => (
            <li key={link.href} className="border-b border-line">
              <Reveal delay={i * 0.05}>
                <a href={link.href} className="group flex items-start justify-between gap-6 py-5">
                  <span>
                    <span className="display block text-[1.45rem] leading-tight text-ink decoration-accent decoration-1 underline-offset-[5px] group-hover:underline">
                      {link.title}
                    </span>
                    <span className="mt-1.5 block max-w-[40ch] text-[14.5px] leading-relaxed text-ink-2">{link.body}</span>
                  </span>
                  <ArrowUpRight
                    size={18}
                    aria-hidden="true"
                    className="mt-1.5 shrink-0 text-muted transition-[transform,color] duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-accent"
                  />
                </a>
              </Reveal>
            </li>
          ))}
        </ul>
      </div>
    </Section>
  );
}

export function Footer() {
  return (
    <footer className="mt-24 md:mt-32">
      <div className={CONTAINER}>
        <div className="grid grid-cols-1 gap-x-10 gap-y-8 border-t border-ink py-10 text-[13.5px] leading-relaxed text-ink-2 md:grid-cols-12 md:pb-14">
          <div className="md:col-span-3">
            <p className="font-mono text-[15px] font-medium text-ink" translate="no">
              bidscreen
            </p>
            <p className="tabular mt-1 font-mono text-[12px] text-muted">version {data.meta.version}</p>
          </div>
          <div className="md:col-span-4">
            <p className="display text-[1.3rem] leading-snug text-ink">{data.meta.notice}</p>
          </div>
          <div className="md:col-span-5">
            <p className="max-w-[64ch]">
              This page contains information from the Assam Public Procurement Data, made available by
              CivicDataLab under the Open Database License. The figures shown here are available under the
              same licence. The six cartel case files come from Garcia Rodriguez et al. (2022) and are not
              redistributed.
            </p>
            <p className="mt-3">
              Code under the MIT licence.{" "}
              <a href={REPO} className="text-ink underline decoration-line-strong underline-offset-4 transition-colors duration-200 hover:decoration-accent">
                Source on GitHub
              </a>
            </p>
            <p className="mt-3 text-muted">Set in Newsreader, IBM Plex Sans and IBM Plex Mono.</p>
          </div>
        </div>
      </div>
    </footer>
  );
}
