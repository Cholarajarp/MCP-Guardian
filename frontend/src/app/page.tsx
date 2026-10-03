import { CtaBand } from "@/components/landing/CtaBand";
import { Features } from "@/components/landing/Features";
import { Hero } from "@/components/landing/Hero";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { WhyStrip } from "@/components/landing/WhyStrip";

export default function LandingPage() {
  return (
    <>
      <Hero />
      <HowItWorks />
      <Features />
      <WhyStrip />
      <CtaBand />
    </>
  );
}
