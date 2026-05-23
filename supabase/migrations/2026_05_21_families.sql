-- ============================================================
--  Family Pro household schema
--  Date: 2026-05-21
--  Spec: docs/superpowers/specs/2026-05-21-family-dashboard-design.md
-- ============================================================

-- Helper function for keeping updated_at fresh
CREATE OR REPLACE FUNCTION public._family_set_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- ============================================================
--  families
-- ============================================================
CREATE TABLE IF NOT EXISTS public.families (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_user_id   uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  subscription_id uuid REFERENCES public.subscriptions(id) ON DELETE SET NULL,
  display_name    text NOT NULL DEFAULT 'My Household',
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS families_owner_user_id_unique
  ON public.families(owner_user_id);

CREATE INDEX IF NOT EXISTS families_subscription_id_idx
  ON public.families(subscription_id);

DROP TRIGGER IF EXISTS families_set_updated_at ON public.families;
CREATE TRIGGER families_set_updated_at
  BEFORE UPDATE ON public.families
  FOR EACH ROW EXECUTE FUNCTION public._family_set_updated_at();


-- ============================================================
--  family_members
-- ============================================================
CREATE TABLE IF NOT EXISTS public.family_members (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  family_id         uuid NOT NULL REFERENCES public.families(id) ON DELETE CASCADE,
  player_user_id    uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  role              text NOT NULL CHECK (role IN ('owner','parent','child')),
  invite_email      text,
  invite_token_hash text,
  invite_status     text NOT NULL DEFAULT 'pending'
                    CHECK (invite_status IN ('pending','active','removed')),
  is_minor          boolean NOT NULL DEFAULT false,
  display_name      text,
  added_at          timestamptz NOT NULL DEFAULT now(),
  removed_at        timestamptz
);

-- One active membership per user across all families
CREATE UNIQUE INDEX IF NOT EXISTS family_members_active_user_unique
  ON public.family_members(player_user_id)
  WHERE invite_status = 'active' AND player_user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS family_members_family_id_idx
  ON public.family_members(family_id);

CREATE INDEX IF NOT EXISTS family_members_invite_token_hash_idx
  ON public.family_members(invite_token_hash)
  WHERE invite_token_hash IS NOT NULL;

CREATE INDEX IF NOT EXISTS family_members_pending_email_idx
  ON public.family_members(family_id, lower(invite_email))
  WHERE invite_status = 'pending';


-- ============================================================
--  Row Level Security
-- ============================================================
ALTER TABLE public.families ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.family_members ENABLE ROW LEVEL SECURITY;

-- families: SELECT for owner or active member of this family
DROP POLICY IF EXISTS families_select ON public.families;
CREATE POLICY families_select ON public.families FOR SELECT
  USING (
    owner_user_id = auth.uid()
    OR EXISTS (
      SELECT 1 FROM public.family_members fm
       WHERE fm.family_id = families.id
         AND fm.player_user_id = auth.uid()
         AND fm.invite_status = 'active'
    )
  );

-- families: UPDATE only by owner
DROP POLICY IF EXISTS families_update ON public.families;
CREATE POLICY families_update ON public.families FOR UPDATE
  USING (owner_user_id = auth.uid())
  WITH CHECK (owner_user_id = auth.uid());

-- families: INSERT only via service-role (webhook); no policy means denied
-- families: DELETE only by owner
DROP POLICY IF EXISTS families_delete ON public.families;
CREATE POLICY families_delete ON public.families FOR DELETE
  USING (owner_user_id = auth.uid());

-- family_members: SELECT for any member of the same family, plus a
-- user can always see their OWN row (incl. pending/removed) so the
-- claim path and "you were removed" UX work.
DROP POLICY IF EXISTS family_members_select ON public.family_members;
CREATE POLICY family_members_select ON public.family_members FOR SELECT
  USING (
    -- Owner sees all members of their family
    EXISTS (
      SELECT 1 FROM public.families f
       WHERE f.id = family_members.family_id
         AND f.owner_user_id = auth.uid()
    )
    -- Active members see their family
    OR EXISTS (
      SELECT 1 FROM public.family_members fm
       WHERE fm.family_id = family_members.family_id
         AND fm.player_user_id = auth.uid()
         AND fm.invite_status = 'active'
    )
    -- A user can always read their OWN row, any status
    OR family_members.player_user_id = auth.uid()
  );

-- family_members: INSERT is gated to owner + seat cap as defense in depth,
-- but the broad INSERT grant is REVOKED below — all inserts flow through
-- the add_family_member() SECURITY DEFINER RPC which does FOR UPDATE.
DROP POLICY IF EXISTS family_members_insert ON public.family_members;
CREATE POLICY family_members_insert ON public.family_members FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.families f
       WHERE f.id = family_members.family_id
         AND f.owner_user_id = auth.uid()
    )
    AND (
      SELECT count(*) FROM public.family_members fm
       WHERE fm.family_id = family_members.family_id
         AND fm.invite_status = 'active'
    ) < 4
  );

-- family_members: UPDATE split into two policies.
-- (a) Owner can update any row in their family, but cannot migrate a
--     row into a different family_id.
DROP POLICY IF EXISTS family_members_update ON public.family_members;
DROP POLICY IF EXISTS family_members_update_owner ON public.family_members;
CREATE POLICY family_members_update_owner ON public.family_members FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM public.families f
       WHERE f.id = family_members.family_id
         AND f.owner_user_id = auth.uid()
    )
  )
  WITH CHECK (
    family_id = (SELECT fm2.family_id FROM public.family_members fm2
                  WHERE fm2.id = family_members.id)
  );

-- (b) A member can update ONLY their own active row, and the WITH CHECK
--     pins every sensitive column to its OLD value — so a kid cannot
--     re-activate themselves after removal, elevate role, move family,
--     or rewrite their invite token. The column grant below further
--     restricts writable columns to (display_name, is_minor).
DROP POLICY IF EXISTS family_members_update_self ON public.family_members;
CREATE POLICY family_members_update_self ON public.family_members FOR UPDATE
  USING (
    player_user_id = auth.uid()
    AND invite_status = 'active'
  )
  WITH CHECK (
    player_user_id = auth.uid()
    AND invite_status = 'active'
    AND family_id = (SELECT fm2.family_id FROM public.family_members fm2
                      WHERE fm2.id = family_members.id)
    AND role = (SELECT fm2.role FROM public.family_members fm2
                 WHERE fm2.id = family_members.id)
    AND invite_email IS NOT DISTINCT FROM
        (SELECT fm2.invite_email FROM public.family_members fm2
          WHERE fm2.id = family_members.id)
    AND invite_token_hash IS NOT DISTINCT FROM
        (SELECT fm2.invite_token_hash FROM public.family_members fm2
          WHERE fm2.id = family_members.id)
  );

-- family_members: no DELETE policy means denied — soft-delete via UPDATE


-- ============================================================
--  v_my_effective_plan view (replaces v_my_plan for callers
--  that want family-aware plan resolution)
-- ============================================================
CREATE OR REPLACE VIEW public.v_my_effective_plan
WITH (security_invoker = true) AS
WITH direct AS (
  SELECT s.plan_id, s.status, 'direct'::text AS source
    FROM public.subscriptions s
   WHERE s.owner_user_id = auth.uid()
     AND s.status IN ('active','trialing','past_due')
   ORDER BY
     CASE s.status WHEN 'active' THEN 0 WHEN 'trialing' THEN 1 ELSE 2 END,
     s.created_at DESC
   LIMIT 1
),
via_family AS (
  SELECT s.plan_id, s.status, 'family'::text AS source
    FROM public.family_members fm
    JOIN public.families f ON f.id = fm.family_id
    JOIN public.subscriptions s ON s.id = f.subscription_id
   WHERE fm.player_user_id = auth.uid()
     AND fm.invite_status = 'active'
     AND s.status IN ('active','trialing','past_due')
   ORDER BY
     CASE s.status WHEN 'active' THEN 0 WHEN 'trialing' THEN 1 ELSE 2 END,
     s.created_at DESC
   LIMIT 1
)
SELECT auth.uid() AS user_id,
       COALESCE(d.plan_id, vf.plan_id) AS plan_id,
       COALESCE(d.status,  vf.status)  AS status,
       COALESCE(d.source,  vf.source)  AS source
  FROM (SELECT 1) base
  LEFT JOIN direct d ON true
  LEFT JOIN via_family vf ON true;


-- ============================================================
--  Stored procedure: add_family_member
--  (server-side seat check + atomic insert; callers go through this
--  instead of raw INSERT so the seat cap is enforced even by
--  service-role keys)
-- ============================================================
CREATE OR REPLACE FUNCTION public.add_family_member(
  p_family_id   uuid,
  p_email       text,
  p_role        text DEFAULT 'child',
  p_is_minor    boolean DEFAULT false,
  p_display_name text DEFAULT NULL,
  p_token_hash  text DEFAULT NULL
) RETURNS public.family_members AS $$
DECLARE
  active_count integer;
  result public.family_members%ROWTYPE;
  v_family_id uuid;
BEGIN
  -- Lock the families row to serialize concurrent seat-cap checks
  -- (closes the TOCTOU where two concurrent invites both pass the count).
  SELECT id INTO v_family_id
    FROM public.families
   WHERE id = p_family_id AND owner_user_id = auth.uid()
   FOR UPDATE;

  IF v_family_id IS NULL THEN
    RAISE EXCEPTION 'add_family_member: caller is not family owner';
  END IF;

  -- Validate role against the CHECK constraint values
  IF p_role NOT IN ('owner','parent','child') THEN
    RAISE EXCEPTION 'add_family_member: invalid role %', p_role;
  END IF;

  -- Seat cap (now under the row lock above)
  SELECT count(*) INTO active_count
    FROM public.family_members
   WHERE family_id = p_family_id
     AND invite_status = 'active';
  IF active_count >= 4 THEN
    RAISE EXCEPTION 'add_family_member: household is full (4-seat cap)';
  END IF;

  INSERT INTO public.family_members
    (family_id, role, invite_email, invite_token_hash,
     invite_status, is_minor, display_name)
  VALUES
    (p_family_id, p_role, lower(p_email), p_token_hash,
     'pending', p_is_minor, LEFT(trim(coalesce(p_display_name, '')), 60))
  RETURNING * INTO result;

  RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;


-- ============================================================
--  Stored procedure: claim_family_invite
--  Atomic + SQL-side expiry. Invitee calls this with the sha256 of
--  the token they received. Runs as SECURITY DEFINER so it can read
--  + flip the pending row without a token-based SELECT policy.
-- ============================================================
CREATE OR REPLACE FUNCTION public.claim_family_invite(
  p_token_hash text
) RETURNS uuid AS $$
DECLARE
  v_row public.family_members%ROWTYPE;
BEGIN
  IF auth.uid() IS NULL THEN
    RAISE EXCEPTION 'claim_family_invite: not authenticated';
  END IF;

  -- Lock the matching pending, non-expired row
  SELECT * INTO v_row
    FROM public.family_members
   WHERE invite_token_hash = p_token_hash
     AND invite_status = 'pending'
     AND added_at > now() - interval '30 days'
   FOR UPDATE;

  IF v_row.id IS NULL THEN
    RAISE EXCEPTION 'claim_family_invite: invalid or expired';
  END IF;

  -- Enforce the 4-seat cap at claim time too (an invite could have been
  -- sent before another seat filled up).
  IF (SELECT count(*) FROM public.family_members
        WHERE family_id = v_row.family_id
          AND invite_status = 'active') >= 4 THEN
    RAISE EXCEPTION 'claim_family_invite: household is full';
  END IF;

  UPDATE public.family_members
     SET invite_status     = 'active',
         player_user_id    = auth.uid(),
         invite_token_hash = NULL
   WHERE id = v_row.id;

  RETURN v_row.family_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;


-- ============================================================
--  Grants — service role bypasses RLS. Authenticated users get:
--   - SELECT on families + members (RLS-scoped)
--   - UPDATE only on safe columns (display_name; member self-edit
--     of display_name/is_minor)
--   - NO direct INSERT/UPDATE-everything — those flow through the
--     SECURITY DEFINER RPCs which enforce ownership + seat caps.
-- ============================================================
GRANT SELECT ON public.families TO authenticated;
GRANT UPDATE (display_name) ON public.families TO authenticated;
GRANT SELECT ON public.family_members TO authenticated;
-- Column-scoped UPDATE: members may only ever write these two columns.
GRANT UPDATE (display_name, is_minor) ON public.family_members TO authenticated;
-- Direct INSERT is denied; add_family_member RPC is the only path.
REVOKE INSERT ON public.family_members FROM authenticated;
GRANT SELECT ON public.v_my_effective_plan TO authenticated;
GRANT EXECUTE ON FUNCTION public.add_family_member TO authenticated;
GRANT EXECUTE ON FUNCTION public.claim_family_invite TO authenticated;
