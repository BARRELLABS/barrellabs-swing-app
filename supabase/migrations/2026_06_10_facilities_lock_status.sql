-- Close the facility self-activation hole.
--
-- The `facilities_owner` RLS policy is FOR ALL with only an ownership check,
-- and `authenticated` holds a table UPDATE grant, so any owner could run
--   UPDATE facilities SET status='active' WHERE id=<their own facility>
-- via the data API and self-grant free Pro to themselves and everyone who
-- joins their code. create_facility() correctly forces status='pending', but
-- nothing stopped a subsequent owner UPDATE. This trigger makes the
-- entitlement-bearing columns immutable for the authenticated API role, while
-- still allowing service_role (Stripe webhook / admin) and direct SQL
-- (migrations, manual activation) to change them.
--
-- NOTE: uses auth.role() (the request JWT's role claim), NOT current_user --
-- a trigger's current_user would not reliably reflect the caller. service_role
-- and unauthenticated direct SQL both have auth.role() <> 'authenticated'.

CREATE OR REPLACE FUNCTION public.facilities_lock_privileged_cols()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  -- Only the authenticated data-API role is restricted. Everything else
  -- (service_role, migrations, manual SQL activation) may change anything.
  IF auth.role() IS DISTINCT FROM 'authenticated' THEN
    RETURN NEW;
  END IF;

  IF NEW.status         IS DISTINCT FROM OLD.status
     OR NEW.plan_tier      IS DISTINCT FROM OLD.plan_tier
     OR NEW.roster_ceiling IS DISTINCT FROM OLD.roster_ceiling
     OR NEW.billing_mode   IS DISTINCT FROM OLD.billing_mode
     OR NEW.owner_user_id  IS DISTINCT FROM OLD.owner_user_id
     OR NEW.join_code      IS DISTINCT FROM OLD.join_code THEN
    RAISE EXCEPTION
      'facilities: status/plan/roster/billing/owner/join_code are not user-editable';
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS facilities_lock_privileged_cols ON public.facilities;
CREATE TRIGGER facilities_lock_privileged_cols
  BEFORE UPDATE ON public.facilities
  FOR EACH ROW
  EXECUTE FUNCTION public.facilities_lock_privileged_cols();
