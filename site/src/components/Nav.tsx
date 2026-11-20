import { GithubLogo, List, Moon, Sun, X } from "@phosphor-icons/react";
import { useMotionValueEvent, useScroll } from "motion/react";
import { useEffect, useState } from "react";
import { REPO } from "../lib/data";

const LINKS = [
  { href: "#findings", label: "Findings" },
  { href: "#evidence", label: "Evidence" },
  { href: "#method", label: "Method" },
  { href: "#assam", label: "Assam" },
  { href: "#safeguards", label: "Safeguards" },
];

function Wordmark() {
  return (
    <a href="#top" className="flex items-center gap-2.5 text-ink" aria-label="bidscreen, back to top">
      <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
        <path d="M6 6 18 12M6 18 18 12" stroke="var(--context)" strokeWidth="1.4" strokeLinecap="round" />
        <path d="M6 6 18 19" stroke="var(--accent)" strokeWidth="1.8" strokeLinecap="round" />
        <circle cx="6" cy="6" r="2.6" fill="var(--ink)" />
        <circle cx="6" cy="18" r="2.6" fill="var(--ink)" />
        <circle cx="18" cy="12" r="2.2" fill="var(--context)" />
        <circle cx="18" cy="19" r="2.2" fill="var(--accent)" />
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
      className="grid size-9 place-items-center rounded-full text-ink-2 transition-colors hover:bg-mid hover:text-ink active:scale-[0.96]"
    >
      {dark ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  );
}

export function Nav() {
  const { scrollY } = useScroll();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

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
      className={`sticky top-0 z-40 border-b backdrop-blur-md transition-colors duration-300 ${
        scrolled || open ? "border-line bg-bg/85" : "border-transparent bg-bg/0"
      }`}
    >
      <a
        href="#main"
        className="absolute left-4 top-[-60px] rounded-full bg-ink px-4 py-2 text-sm text-bg focus-visible:top-3"
      >
        Skip to content
      </a>
      <div className="mx-auto flex h-16 max-w-[1240px] items-center justify-between gap-6 px-5 md:px-8">
        <Wordmark />
        <nav aria-label="Sections" className="hidden items-center gap-7 md:flex">
          {LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-[14px] text-ink-2 transition-colors hover:text-ink"
            >
              {link.label}
            </a>
          ))}
        </nav>
        <div className="flex items-center gap-1.5">
          <ThemeToggle />
          <a
            href={REPO}
            className="hidden items-center gap-2 rounded-full border border-line-strong px-4 py-2 text-[14px] font-medium text-ink transition-colors hover:border-ink sm:flex active:scale-[0.98]"
          >
            <GithubLogo size={17} weight="fill" aria-hidden="true" />
            View on GitHub
          </a>
          <button
            type="button"
            onClick={() => setOpen(!open)}
            aria-expanded={open}
            aria-controls="mobile-menu"
            aria-label={open ? "Close menu" : "Open menu"}
            className="grid size-9 place-items-center rounded-full text-ink md:hidden"
          >
            {open ? <X size={20} /> : <List size={20} />}
          </button>
        </div>
      </div>
      {open ? (
        <nav id="mobile-menu" aria-label="Sections" className="border-t border-line px-5 pb-5 pt-2 md:hidden">
          <ul>
            {LINKS.map((link) => (
              <li key={link.href}>
                <a
                  href={link.href}
                  onClick={() => setOpen(false)}
                  className="block py-3 text-[17px] text-ink"
                >
                  {link.label}
                </a>
              </li>
            ))}
            <li>
              <a href={REPO} className="mt-2 flex items-center gap-2 py-3 text-[17px] font-medium text-ink">
                <GithubLogo size={19} weight="fill" aria-hidden="true" />
                View on GitHub
              </a>
            </li>
          </ul>
        </nav>
      ) : null}
    </header>
  );
}
