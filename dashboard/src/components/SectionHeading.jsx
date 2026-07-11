// Single source of section typography: every titled block in every tab uses
// this. `size="lg"` is for the group intros that sit between section cards.
export default function SectionHeading({ title, description, size = "base" }) {
  return (
    <div className={size === "lg" ? "mb-2" : "mb-5"}>
      <h2
        className={`${size === "lg" ? "text-2xl" : "text-xl"} font-semibold tracking-tight text-slate-900`}
      >
        {title}
      </h2>
      {description ? (
        <div className="mt-2 text-sm leading-6 text-slate-600">{description}</div>
      ) : null}
    </div>
  );
}
