-- Upgrade an already-seeded deployment without touching existing rows.
-- NULL strata_bounds means the experiment predates pre-registered strata and
-- keeps recomputing with the original unstratified Welch/CUPED method.
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS strata_bounds JSON;
