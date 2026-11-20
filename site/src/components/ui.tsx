import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

/** Easing shared by every entrance on the page. */
export const EASE = [0.16, 1, 0.3, 1] as const;

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
      initial={reduce ? false : { opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.7, delay, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}

export function Section({
  id,
  title,
  lead,
  children,
  wide = false,
}: {
  id: string;
  title: string;
  lead?: ReactNode;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="border-t border-line">
      <div className="mx-auto max-w-[1240px] px-5 py-20 md:px-8 md:py-28">
        <Reveal>
          <h2
            id={`${id}-title`}
            className="max-w-[18ch] text-3xl font-semibold tracking-tight text-ink md:text-[2.75rem] md:leading-[1.05]"
          >
            {title}
          </h2>
          {lead ? (
            <p className={`mt-5 text-lg leading-relaxed text-ink-2 ${wide ? "max-w-[70ch]" : "max-w-[58ch]"}`}>
              {lead}
            </p>
          ) : null}
        </Reveal>
        <div className="mt-12 md:mt-16">{children}</div>
      </div>
    </section>
  );
}

/** A label such as FIRM-00042: monospaced, and never machine-translated. */
export function Label({ children }: { children: ReactNode }) {
  return (
    <span translate="no" className="font-mono text-[0.92em] tracking-tight">
      {children}
    </span>
  );
}
