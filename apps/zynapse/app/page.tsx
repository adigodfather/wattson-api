import Nav from "@/components/Nav";
import Hero from "@/components/Hero";
import HowItWorks from "@/components/HowItWorks";
import Features from "@/components/Features";
import WorkflowDiagram from "@/components/WorkflowDiagram";
import Pricing from "@/components/Pricing";
import Footer from "@/components/Footer";

export default function Home() {
  return (
    <main>
      <Nav />
      <Hero />
      <HowItWorks />
      <Features />
      <WorkflowDiagram />
      <Pricing />
      <Footer />
    </main>
  );
}
