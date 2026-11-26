import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "./api";
import type { Meta, Plan, PlanRequest, PlanSummary, Rating } from "./types";
import PlanForm from "./components/PlanForm";
import PlanView from "./components/PlanView";

type View = "home" | "form" | "plan" | "saved";

export default function App() {
  const [view, setView] = useState<View>("home");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [saved, setSaved] = useState<PlanSummary[] | null>(null);
  const [ratings, setRatings] = useState<Record<string, Rating>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    api.meta().then(setMeta).catch((e: ApiError) => setMetaError(e.message));
    api.myFeedback().then(setRatings).catch(() => undefined);
  }, []);

  const generate = useCallback(async (req: PlanRequest) => {
    setBusy(true);
    setError(null);
    try {
      const p = await api.generate(req);
      setPlan(p);
      setView("plan");
      window.scrollTo({ top: 0 });
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError("Something went wrong. Please try again."));
    } finally {
      setBusy(false);
    }
  }, []);

  const openSaved = async () => {
    setView("saved");
    setSaved(null);
    try {
      setSaved(await api.plans());
    } catch {
      setSaved([]);
    }
  };

  const loadPlan = async (id: string) => {
    try {
      setPlan(await api.plan(id));
      setView("plan");
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError("Could not open that plan."));
    }
  };

  const rate = async (planId: string, recipeId: string, rating: Rating) => {
    setRatings((r) => ({ ...r, [recipeId]: rating }));
    try {
      await api.feedback(planId, recipeId, rating);
    } catch {
      setRatings((r) => {
        const { [recipeId]: _drop, ...rest } = r;
        return rest;
      });
    }
  };

  return (
    <>
      <header className="topbar">
        <button className="brand" onClick={() => setView("home")} aria-label="DietWise home">
          <span className="brand-mark" aria-hidden="true" />
          DietWise
        </button>
        <nav aria-label="Main">
          <button className={view === "form" ? "active" : ""} onClick={() => setView("form")}>New plan</button>
          <button className={view === "plan" ? "active" : ""} disabled={!plan} onClick={() => setView("plan")}>Current plan</button>
          <button className={view === "saved" ? "active" : ""} onClick={openSaved}>Saved plans</button>
        </nav>
      </header>

      <main>
        {metaError && <div className="banner error" role="alert">{metaError}</div>}

        {view === "home" && (
          <section className="hero">
            <h1>Plan the week around what you can spend.</h1>
            <p className="lead">
              Enter your budget, how many days and how many people. DietWise picks different meals for every day,
              lists the ingredients for each dish, and gives you one shopping list that stays within your budget.
            </p>
            <div className="hero-actions">
              <button className="btn primary" onClick={() => setView("form")}>Build my plan</button>
              <button className="btn" onClick={openSaved}>Open a saved plan</button>
            </div>
            <ul className="facts">
              <li><strong>Works in your currency.</strong> {meta ? `${meta.currencies.length} currencies and ${meta.cuisines.length} cuisines.` : "Many currencies and cuisines."}</li>
              <li><strong>Safe by default.</strong> Allergies and diet rules remove dishes before anything is ranked.</li>
              <li><strong>Honest about money.</strong> If your budget is too low, it says so and shows the cheapest option.</li>
            </ul>
          </section>
        )}

        {view === "form" && (
          meta ? <PlanForm meta={meta} busy={busy} error={error} onSubmit={generate} /> : !metaError && <p className="muted">Loading options…</p>
        )}

        {view === "plan" && plan && <PlanView plan={plan} ratings={ratings} onRate={rate} onNew={() => setView("form")} />}

        {view === "saved" && (
          <section className="narrow">
            <h2>Saved plans</h2>
            {saved === null && <p className="muted">Loading…</p>}
            {saved?.length === 0 && (
              <div className="empty">
                <p>No saved plans yet. Every plan you build is saved on this device's profile automatically.</p>
                <button className="btn primary" onClick={() => setView("form")}>Build a plan</button>
              </div>
            )}
            <ul className="saved-list">
              {saved?.map((s) => (
                <li key={s.id}>
                  <button onClick={() => loadPlan(s.id)}>
                    <span className="saved-title">{s.days} days for {s.people} {s.people === 1 ? "person" : "people"}</span>
                    <span className="muted">
                      {s.food_preference.replace("_", "-")}, {s.nutrition_goal.replace("_", " ")} · bill {s.currency.symbol}{s.grocery_total.toFixed(2)} of {s.currency.symbol}{s.budget}
                      {s.status === "over_budget" ? " · over budget" : ""} · {new Date(s.created_at).toLocaleDateString()}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>
      <footer className="foot">Prices and nutrition are estimates from a starter dataset, not live market data or medical advice.</footer>
    </>
  );
}
