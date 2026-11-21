import { ArrowUpRight, CircleHalf, List, X } from "@phosphor-icons/react";
import { useMotionValueEvent, useScroll } from "motion/react";
import { useEffect, useState } from "react";
import { REPO } from "../lib/data";
import { CONTAINER } from "./ui";

const LINKS = [
  { id: "findings", label: "Findings" },
  { id: "evidence", label: "Evidence" },
  { id: "method", label: "Method" },
  { id: "assam", label: "Assam" },
  { id: "safeguards", label: "Safeguards" },
];

/** The id of the section that holds the middle of the viewport, if any. */
function useActiveSection(ids: string[]): string | null {
  const [active, setActive] = useState<string | null>(null);
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setActive(entry.target.id);
          else setActive((current) => (current === entry.target.id ? null : current));
        }
      },
      { rootMargin: "-50% 0px -50% 0px" },
    );
    ids.forEach((id) => {
      const node = document.getElementById(id);
      if (node) observer.observe(node);
    });
    return () => observer.disconnect();
  }, [ids]);
  return active;
}

function Wordmark() {
  return (
    <a href="#top" className="group flex items-center gap-2.5 text-ink" aria-label="bidscreen, back to top">
      <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
        <path d="M5 6 19 12M5 18 19 12" stroke="var(--context)" strokeWidth="1.3" strokeLinecap="round" />
        <path d="M5 6 19 19" stroke="var(--accent)" strokeWidth="1.8" strokeLinecap="round" />
        <rect x="2.6" y="3.6" width="4.8" height="4.8" fill="var(--ink)" />
        <rect x="2.6" y="15.6" width="4.8" height="4.8" fill="var(--ink)" />
        <circle cx="19" cy="12" r="2.2" fill="var(--context)" />
        <circle cx="19" cy="19" r="2.2" fill="var(--accent)" />
      </svg>
      <span className="font-mono text-[15px] font-medium tracking-tight" translate="no">
        bidscreen
      </span>
    </a>
  );
}

function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const stored = document.documentElement.dataset.theme;
    setDark(stored ? stored === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches);
  }, []);

  const toggle = () => {
    const next = dark ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("theme", next);
    } catch {
      // Private mode: the choice simply lasts for this visit.
    }
    setDark(!dark);
  };

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      className="flex h-9 items-center gap-2 rounded-[3px] px-2.5 text-[13px] text-ink-2 transition-colors duration-200 hover:bg-mid hover:text-ink active:translate-y-px"
    >
      <CircleHalf size={17} weight="regular" aria-hidden="true" className={dark ? "rotate-180" : ""} />
      <span className="hidden font-mono lg:inline">{dark ? "Light" : "Dark"}</span>
    </button>
  );
}

export function Nav() {
  const { scrollY } = useScroll();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const active = useActiveSection(LINKS.map((link) => link.id));

  useMotionValueEvent(scrollY, "change", (y) => {
    const next = y > 12;
    setScrolled((current) => (current === next ? current : next));
  });

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <header
      className={`sticky top-0 z-40 border-b transition-[background-color,border-color] duration-300 ${
        scrolled || open ? "border-line bg-bg/90 backdrop-blur-md" : "border-transparent bg-bg/0"
      }`}
    >
      <a
        href="#main"
        className="sr-only rounded-[3px] bg-ink text-sm text-bg focus-visible:not-sr-only focus-visible:absolute focus-visible:left-4 focus-visible:top-3 focus-visible:px-4 focus-visible:py-2"
      >
        Skip to content
      </a>
      <div className={`${CONTAINER} flex h-[60px] items-center justify-between gap-6`}>
        <Wordmark />
        <nav aria-label="Sections" className="hidden items-center gap-1 md:flex">
          {LINKS.map((link, i) => {
            const current = active === link.id;
            return (
              <a
                key={link.id}
                href={`#${link.id}`}
                aria-current={current ? "location" : undefined}
                className={`group relative flex items-baseline gap-1.5 rounded-[3px] px-2.5 py-2 text-[14px] transition-colors duration-200 ${
                  current ? "text-ink" : "text-ink-2 hover:text-ink"
                }`}
              >
                <span className={`tabular font-mono text-[10.5px] ${current ? "text-accent" : "text-muted"}`}>
                  0{i + 1}
                </span>
                {link.label}
                <span
                  aria-hidden="true"
                  className={`absolute inset-x-2.5 -bottom-px h-px origin-left bg-accent transition-transform duration-300 ${
                    current ? "scale-x-100" : "scale-x-0"
                  }`}
                />
              </a>
            );
          })}
        </nav>
        <div className="flex items-center gap-1">
          <ThemeToggle />
          <a
            href={REPO}
            className="hidden h-9 items-center gap-1.5 rounded-[3px] bg-ink px-3.5 text-[13.5px] font-medium text-bg transition-colors duration-200 hover:bg-accent hover:text-accent-ink active:translate-y-px sm:flex"
          >
            Source code
            <ArrowUpRight size={14} weight="bold" aria-hidden="true" />
          </a>
          <button
            type="button"
            onClick={() => setOpen(!open)}
            aria-expanded={open}
            aria-controls="mobile-menu"
            aria-label={open ? "Close menu" : "Open menu"}
            className="grid size-10 place-items-center rounded-[3px] text-ink md:hidden"
          >
            {open ? <X size={20} /> : <List size={20} />}
          </button>
        </div>
      </div>
      {open ? (
        <nav id="mobile-menu" aria-label="Sections" className="border-t border-line md:hidden">
          <ul className={`${CONTAINER} pb-4 pt-1`}>
            {LINKS.map((link, i) => (
              <li key={link.id} className="border-b border-line">
                <a
                  href={`#${link.id}`}
                  onClick={() => setOpen(false)}
                  className="flex items-baseline gap-3 py-3.5 text-[17px] text-ink"
                >
                  <span className="tabular font-mono text-[11px] text-accent">0{i + 1}</span>
                  {link.label}
                </a>
              </li>
            ))}
            <li>
              <a href={REPO} className="mt-1 flex items-center gap-2 py-3.5 text-[17px] font-medium text-ink">
                Source code on GitHub
                <ArrowUpRight size={15} weight="bold" aria-hidden="true" />
              </a>
            </li>
          </ul>
        </nav>
      ) : null}
    </header>
  );
}
