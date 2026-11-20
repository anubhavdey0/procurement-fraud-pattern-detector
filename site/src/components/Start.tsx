import { ArrowUpRight, Check, Copy } from "@phosphor-icons/react";
import { useState } from "react";
import { data, REPO } from "../lib/data";
import { Reveal, Section } from "./ui";

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
      className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[13px] text-ink-2 transition-colors hover:bg-mid hover:text-ink active:scale-[0.97]"
    >
      {copied ? <Check size={15} aria-hidden="true" /> : <Copy size={15} aria-hidden="true" />}
      <span aria-live="polite">{copied ? "Copied" : "Copy commands"}</span>
    </button>
  );
}

export function Start() {
  return (
    <Section
      id="start"
      title="Run it yourself"
      lead="The demo needs no download. It runs every screen on a synthetic market with a planted cartel and writes a report."
    >
      <div className="grid gap-10 lg:grid-cols-12 grid-cols-1">
        <Reveal className="lg:col-span-7">
          <div className="overflow-hidden rounded-2xl border border-line bg-surface">
            <div className="flex items-center justify-between border-b border-line px-5 py-2.5">
              <p className="text-[13px] text-muted">Python 3.10 or later</p>
              <CopyButton />
            </div>
            <pre className="overflow-x-auto px-5 py-5 font-mono text-[14px] leading-7 text-ink" tabIndex={0}>
              <code>
                {COMMANDS.map((line) => (
                  <span key={line} className="block whitespace-pre">
                    <span aria-hidden="true" className="select-none text-context">
                      ${" "}
                    </span>
                    {line}
                  </span>
                ))}
              </code>
            </pre>
          </div>
          <p className="mt-4 max-w-[62ch] text-[14.5px] leading-relaxed text-ink-2">
            To reproduce the real results, run <code className="font-mono text-ink">bidscreen fetch</code>,{" "}
            <code className="font-mono text-ink">bidscreen validate</code> and{" "}
            <code className="font-mono text-ink">bidscreen screen assam</code>. Downloads are pinned to a
            commit and checked against a checksum.
          </p>
        </Reveal>
        <ul className="lg:col-span-5">
          {LINKS.map((link, i) => (
            <li key={link.href} className="border-t border-line first:border-t-0">
              <Reveal delay={i * 0.05}>
                <a href={link.href} className="group flex items-start justify-between gap-6 py-5">
                  <span>
                    <span className="block text-[17px] font-semibold tracking-tight text-ink decoration-line-strong underline-offset-4 group-hover:underline">
                      {link.title}
                    </span>
                    <span className="mt-1 block max-w-[40ch] text-[14.5px] leading-relaxed text-ink-2">{link.body}</span>
                  </span>
                  <ArrowUpRight
                    size={20}
                    aria-hidden="true"
                    className="mt-1 shrink-0 text-muted transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-ink"
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
    <footer className="border-t border-line">
      <div className="mx-auto grid max-w-[1240px] gap-8 px-5 py-12 text-[14px] leading-relaxed text-ink-2 md:grid-cols-12 md:px-8 grid-cols-1">
        <div className="md:col-span-5">
          <p className="font-mono text-[15px] font-medium text-ink" translate="no">
            bidscreen
          </p>
          <p className="mt-3 max-w-[44ch] font-medium text-ink">{data.meta.notice}</p>
        </div>
        <div className="md:col-span-7">
          <p className="max-w-[70ch]">
            This page contains information from the Assam Public Procurement Data, made available by
            CivicDataLab under the Open Database License. The figures shown here are available under the
            same licence. The six cartel case files come from Garcia Rodriguez et al. (2022) and are not
            redistributed.
          </p>
          <p className="mt-3">
            Code under the MIT licence.{" "}
            <a href={REPO} className="text-ink underline decoration-line-strong underline-offset-4 hover:decoration-ink">
              View on GitHub
            </a>
          </p>
        </div>
      </div>
    </footer>
  );
}
