"use client";
import { useState, useMemo } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";
import SectionHeading from "./SectionHeading";

// Map an item's `type` to a short label + Tailwind pill classes (PE tokens).
function typeBadge(type) {
  const t = type || "";
  if (/^ident/i.test(t)) {
    return { label: "Identity", className: "bg-primary-50 text-primary-700" };
  }
  if (/^econom/i.test(t)) {
    return { label: "Econometric", className: "bg-red-50 text-red-700" };
  }
  if (/^calib/i.test(t)) {
    return { label: "Calibrated", className: "bg-amber-50 text-amber-700" };
  }
  if (/^exog/i.test(t)) {
    return { label: "Exogenous", className: "bg-slate-100 text-slate-600" };
  }
  return { label: t || "—", className: "bg-slate-100 text-slate-600" };
}

// Convert a published EViews equation string into a LaTeX string. This is a
// pragmatic token-level transform (not a full parser) that covers the forms the
// OBR file actually uses: dlog/d/log/exp, lags VAR(-n), @-functions, powers and
// products. It aims for readable maths, not a perfect AST.
function eviewsToLatex(src) {
  if (!src) return "";
  let s = String(src).trim();

  // Quoted date/string literals -> \text{...} so ':' and quotes don't render as
  // maths relations.
  s = s.replace(/"([^"]*)"/g, "\\text{$1}");
  // Escape literal underscores in identifiers (rare in the published codes) so
  // KaTeX doesn't treat them as subscripts.
  s = s.replace(/_/g, "\\_");

  // Difference / log operators (applied before lag conversion so inner lags are
  // converted afterwards inside the parentheses).
  s = s.replace(/\bdlog\s*\(/g, "\\Delta\\ln\\left(");
  s = s.replace(/\bd\s*\(/g, "\\Delta\\left(");
  s = s.replace(/\blog\s*\(/g, "\\ln\\left(");
  s = s.replace(/\bexp\s*\(/g, "\\exp\\left(");

  // @functions (@recode, @elem, @trend, @date, @dateval, @movav, ...) -> roman.
  s = s.replace(/@([A-Za-z]+)/g, "\\operatorname{$1}");

  // Lags and leads: VAR(-n) -> VAR_{t-n}, VAR(+n) -> VAR_{t+n}. Tolerates the
  // stray whitespace the OBR file sometimes has, e.g. BLIC(- 1).
  s = s.replace(/([A-Za-z][A-Za-z0-9]*)\s*\(\s*-\s*(\d+)\s*\)/g, "$1_{t-$2}");
  s = s.replace(/([A-Za-z][A-Za-z0-9]*)\s*\(\s*\+\s*(\d+)\s*\)/g, "$1_{t+$2}");

  // Powers: A^B -> A^{B}.
  s = s.replace(/\^\s*([A-Za-z0-9.]+)/g, "^{$1}");
  // Products: * -> \cdot.
  s = s.replace(/\*/g, "\\cdot ");
  // Balance the \left( we introduced with \right) by neutralising bare ')' — we
  // used \left(, so pair every ')' with \right). Simplest robust approach:
  // render all parens as \left(/\right) so counts always match.
  s = s.replace(/(?<!\\left)\(/g, "\\left(");
  s = s.replace(/(?<!\\right)\)/g, "\\right)");

  return s;
}

function MathEq({ src }) {
  const html = useMemo(() => {
    try {
      return katex.renderToString(eviewsToLatex(src), {
        throwOnError: false,
        displayMode: true,
        strict: false,
      });
    } catch {
      return null;
    }
  }, [src]);

  if (!html) {
    // Fallback: show the raw equation if KaTeX can't parse it.
    return (
      <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-xl bg-slate-50 p-3 font-mono text-xs text-slate-700">
        {src}
      </pre>
    );
  }
  return (
    <div
      className="overflow-x-auto py-1 text-slate-900"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

export default function EquationsTab({ model }) {
  const [search, setSearch] = useState("");
  const [group, setGroup] = useState("");
  const [showPy, setShowPy] = useState(false);

  const items = (model && model.items) || [];
  const groups = ((model && model.groups) || []).filter(Boolean);

  // Only items with a real equation (defensive: older data files carried
  // placeholder cells like "No Equation"; a real equation always contains "=").
  const withEq = useMemo(
    () => items.filter((it) => it.eq && it.eq.includes("=")),
    [items]
  );

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    return withEq.filter(
      (it) =>
        (!group || it.group === group) &&
        (!q ||
          (it.code || "").toLowerCase().indexOf(q) >= 0 ||
          (it.desc || "").toLowerCase().indexOf(q) >= 0)
    );
  }, [withEq, search, group]);

  return (
    <div className="space-y-6">
      <section className="section-card">
        <SectionHeading
          title="Model equations"
          description="Every behavioural and identity equation in the model, rendered as mathematics from the OBR's published EViews code. Toggle the transpiled Python the dashboard actually runs."
        />

        <div className="mb-4 flex flex-wrap items-center gap-3">
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search code or description…"
            aria-label="Search equations"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
          />
          <select
            value={group}
            onChange={(e) => setGroup(e.target.value)}
            aria-label="Filter by group"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
          >
            <option value="">All groups</option>
            {groups.map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={showPy}
              onChange={(e) => setShowPy(e.target.checked)}
            />
            show transpiled Python
          </label>
          <span className="text-sm text-slate-500">
            {filtered.length === withEq.length
              ? `${withEq.length} equations`
              : `${filtered.length} of ${withEq.length} equations`}
          </span>
        </div>

        {filtered.length ? (
          <div className="flex flex-col gap-3">
            {filtered.map((it) => {
              const badge = typeBadge(it.type);
              return (
                <div
                  key={it.code}
                  className="rounded-2xl border border-slate-200 bg-white p-4"
                >
                  <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span className="font-mono font-semibold text-primary-700">
                      {it.code}
                    </span>
                    {it.desc ? (
                      <span className="text-sm text-slate-700">{it.desc}</span>
                    ) : null}
                    <span
                      className={`rounded-md px-2 py-1 text-xs font-semibold ${badge.className}`}
                    >
                      {badge.label}
                    </span>
                    <span className="text-xs text-slate-400">{it.group}</span>
                  </div>

                  <div className="rounded-xl bg-slate-50 px-3 py-2">
                    <MathEq src={it.eq} />
                  </div>

                  {showPy && it.py ? (
                    <>
                      <div className="mb-1 mt-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Transpiled Python
                      </div>
                      <pre
                        className="overflow-x-auto whitespace-pre-wrap break-words rounded-xl p-3 font-mono text-xs leading-relaxed text-slate-100"
                        style={{ backgroundColor: "#0a2a27" }}
                      >
                        {it.py}
                      </pre>
                    </>
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-slate-500">
            No equations match your search.
          </p>
        )}
      </section>
    </div>
  );
}
