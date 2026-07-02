"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import AboutTab from "../src/components/AboutTab";
import HowItWorksTab from "../src/components/HowItWorksTab";
import ExploreTab from "../src/components/ExploreTab";
import CustomReformTab from "../src/components/CustomReformTab";
import VariablesTab from "../src/components/VariablesTab";
import EquationsTab from "../src/components/EquationsTab";

const TAB_OPTIONS = [
  { id: "about", label: "About" },
  { id: "how", label: "How it works" },
  { id: "explore", label: "Explore scenarios" },
  { id: "reform", label: "Build a reform" },
  { id: "variables", label: "Variables" },
  { id: "equations", label: "Equations" },
];

function getInitialTab(tabParam) {
  if (TAB_OPTIONS.some((tab) => tab.id === tabParam)) {
    return tabParam;
  }
  return "about";
}

function Dashboard() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [activeTab, setActiveTab] = useState(() => getInitialTab(searchParams.get("tab")));
  const [model, setModel] = useState(null);
  const [explorer, setExplorer] = useState(null);
  const [grid, setGrid] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setActiveTab(getInitialTab(searchParams.get("tab")));
  }, [searchParams]);

  useEffect(() => {
    async function loadData() {
      try {
        const [mRes, eRes, gRes] = await Promise.all([
          fetch("/data/model_data.json"),
          fetch("/data/explorer_data.json"),
          fetch("/data/reform_grid.json"),
        ]);
        if (!mRes.ok) throw new Error("model_data.json not found");
        setModel(await mRes.json());
        setExplorer(eRes.ok ? await eRes.json() : null);
        setGrid(gRes.ok ? await gRes.json() : null);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  function handleTabChange(tab) {
    setActiveTab(tab);
    if (tab === "about") {
      router.replace("/", { scroll: false });
      return;
    }
    router.replace(`/?tab=${tab}`, { scroll: false });
  }

  return (
    <div className="app-shell min-h-screen">
      <header className="title-row">
        <div className="mx-auto flex max-w-[1400px] items-center justify-between px-6 py-4 md:px-8">
          <h1>The OBR Macroeconomic Model</h1>
        </div>
      </header>

      <main className="relative z-[1] mx-auto max-w-[1400px] px-6 py-10 md:px-8 md:py-12">
        <div className="animate-[fadeIn_0.4s_ease-out]">
          <p className="mb-3 max-w-[80ch] text-[1.05rem] leading-relaxed text-slate-600">
            An independent Python re-implementation of the{" "}
            <a
              href="https://obr.uk/forecasts-in-depth/obr-macroeconomic-model/"
              target="_blank"
              rel="noreferrer"
              className="underline"
            >
              OBR&apos;s published macroeconomic model
            </a>{" "}
            — the same set of equations the Budget Responsibility Committee uses to build the UK
            economy forecast. Explore policy scenarios, browse the 372 published equations, and search
            every model variable. Results use the user&apos;s own assumptions and are not OBR or
            Treasury forecasts.
          </p>
        </div>

        <div className="mb-8 mt-8 flex w-fit flex-wrap border-b-2 border-slate-200">
          {TAB_OPTIONS.map((tab) => (
            <button
              key={tab.id}
              className={`tab-button ${activeTab === tab.id ? "active" : ""}`}
              onClick={() => handleTabChange(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {error && (
          <p className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">
            Error: {error}
          </p>
        )}
        {loading && !error && (
          <p className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
            Loading data...
          </p>
        )}

        {!loading && !error && model && (
          <div className="animate-[fadeIn_0.4s_ease-out]">
            {activeTab === "about" && <AboutTab model={model} explorer={explorer} />}
            {activeTab === "how" && <HowItWorksTab model={model} explorer={explorer} />}
            {activeTab === "explore" && <ExploreTab explorer={explorer} />}
            {activeTab === "reform" && <CustomReformTab grid={grid} />}
            {activeTab === "variables" && <VariablesTab model={model} />}
            {activeTab === "equations" && <EquationsTab model={model} />}
          </div>
        )}

        <footer className="mt-12 border-t border-slate-200 pt-8 text-center text-sm text-slate-500">
          <p>
            Built from the OBR&apos;s published model code (15 October 2025). Replication code:{" "}
            <a
              href="https://github.com/PolicyEngine/obr-macroeconomic-model"
              target="_blank"
              rel="noreferrer"
            >
              PolicyEngine/obr-macroeconomic-model
            </a>
            . Independent project — results are not OBR or Treasury forecasts.
          </p>
        </footer>
      </main>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<p className="p-12 text-center text-slate-500">Loading...</p>}>
      <Dashboard />
    </Suspense>
  );
}
