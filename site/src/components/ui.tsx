import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

/** Easing shared by every entrance on the page. */
export const EASE = [0.16, 1, 0.3, 1] as const;

/** The page's measure: one container width for every section. */
export const CONTAINER = "mx-auto w-full max-w-[1280px] px-5 md:px-10";

/**
 * Content rises into place the first time it enters the viewport. It marks
 * where a new block starts as the reader scrolls; with reduced motion it is
 * simply there.
 */
export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? false : { opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }}
      transition={{ duration: 0.8, delay, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}

/**
 * A numbered section, set like a chapter of a report: a heavy rule, the
 * number and name in the margin, the title and standfirst beside them.
 */
export function Section({
  id,
  number,
  kicker,
  title,
  lead,
  children,
}: {
  id: string;
  number: string;
  kicker: string;
  title: ReactNode;
  lead?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="pt-20 md:pt-28">
      <div className={CONTAINER}>
        <Reveal className="grid grid-cols-1 gap-y-5 border-t border-ink pt-5 md:grid-cols-12 md:gap-x-10 md:pt-7">
          <p className="tabular font-mono text-[12.5px] text-muted md:col-span-3 md:pt-3">
            <span className="text-accent">{number}</span>
            <span aria-hidden="true" className="mx-2.5 inline-block h-px w-5 translate-y-[-0.3em] bg-line-strong" />
            {kicker}
          </p>
          <div className="md:col-span-9">
            <h2
              id={`${id}-title`}
              className="display max-w-[20ch] text-[2.35rem] leading-[1.02] text-ink sm:text-5xl md:text-[3.6rem]"
            >
              {title}
            </h2>
            {lead ? (
              <p className="mt-5 max-w-[62ch] text-[17px] leading-[1.65] text-ink-2 md:mt-6 md:text-lg">{lead}</p>
            ) : null}
          </div>
        </Reveal>
        <div className="pt-12 md:pt-16">{children}</div>
      </div>
    </section>
  );
}

/**
 * A numbered figure: the number in the pencil colour, a plain-language title,
 * the graphic, and an optional note under it.
 */
export function Figure({
  n,
  title,
  aside,
  note,
  children,
  className = "",
}: {
  n: number;
  title: ReactNode;
  aside?: ReactNode;
  note?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <figure className={`m-0 border-t border-line-strong pt-3.5 ${className}`}>
      <figcaption className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
        <span className="text-[14px] leading-snug text-ink">
          <span className="tabular mr-2.5 font-mono text-[12px] text-accent">Fig. {n}</span>
          {title}
        </span>
        {aside}
      </figcaption>
      <div className="mt-5">{children}</div>
      {note ? <p className="mt-4 max-w-[70ch] text-[13px] leading-relaxed text-muted">{note}</p> : null}
    </figure>
  );
}

/** A label such as FIRM-00042: monospaced, and never machine-translated. */
export function Label({ children }: { children: ReactNode }) {
  return (
    <span translate="no" className="font-mono text-[0.9em]">
      {children}
    </span>
  );
}
