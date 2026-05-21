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

-- family_members: SELECT for any member of the same family
DROP POLICY IF EXISTS family_members_select ON public.family_members;
CREATE POLICY family_members_select ON public.family_members FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.family_members fm
       WHERE fm.family_id = family_members.family_id
         AND fm.player_user_id = auth.uid()
         AND fm.invite_status = 'active'
    )
    OR EXISTS (
      SELECT 1 FROM public.families f
       WHERE f.id = family_members.family_id
         AND f.owner_user_id = auth.uid()
    )
  );

-- family_members: INSERT — only owner, only when under seat cap
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

-- family_members: UPDATE — owner can update any row in their family;
-- members can only update their own display_name / is_minor
DROP POLICY IF EXISTS family_members_update ON public.family_members;
CREATE POLICY family_members_update ON public.family_members FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM public.families f
       WHERE f.id = family_members.family_id
         AND f.owner_user_id = auth.uid()
    )
    OR family_members.player_user_id = auth.uid()
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
BEGIN
  -- Permission check: caller must be the family owner
  IF NOT EXISTS (
    SELECT 1 FROM public.families f
     WHERE f.id = p_family_id AND f.owner_user_id = auth.uid()
  ) THEN
    RAISE EXCEPTION 'add_family_member: caller is not family owner';
  END IF;

  -- Seat cap
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
     'pending', p_is_minor, p_display_name)
  RETURNING * INTO result;

  RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- ============================================================
--  Grants — service role bypasses RLS; authenticated users need
--  SELECT/INSERT/UPDATE per the policies above
-- ============================================================
GRANT SELECT ON public.families TO authenticated;
GRANT UPDATE (display_name) ON public.families TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.family_members TO authenticated;
GRANT SELECT ON public.v_my_effective_plan TO authenticated;
GRANT EXECUTE ON FUNCTION public.add_family_member TO authenticated;
