-- Allow the verified render worker's service_role to register outputs and pending owner approvals.
-- The edge function verifies the GitHub OIDC workflow identity before calling the finalization RPC.
grant select, insert on public.video_outputs to service_role;
grant select, insert on public.approvals to service_role;
