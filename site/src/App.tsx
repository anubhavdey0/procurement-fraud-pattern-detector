import { MotionConfig } from "motion/react";
import { Assam } from "./components/Assam";
import { Evidence } from "./components/Evidence";
import { Findings } from "./components/Findings";
import { Hero } from "./components/Hero";
import { Method } from "./components/Method";
import { Nav } from "./components/Nav";
import { Safeguards } from "./components/Safeguards";
import { Footer, Start } from "./components/Start";

export function App() {
  return (
    // "user" makes every animation honour the visitor's reduced-motion setting.
    <MotionConfig reducedMotion="user">
      <Nav />
      <main id="main">
        <Hero />
        <Findings />
        <Evidence />
        <Method />
        <Assam />
        <Safeguards />
        <Start />
      </main>
      <Footer />
    </MotionConfig>
  );
}
