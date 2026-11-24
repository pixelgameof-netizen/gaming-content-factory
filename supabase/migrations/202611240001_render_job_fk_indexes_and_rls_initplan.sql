-- Add covering indexes for render_jobs foreign keys and avoid per-row auth.uid() evaluation.
create index if not exists render_jobs_package_owner_idx
  on public.render_jobs(package_id, owner_id);

create index if not exists render_jobs_output_owner_idx
  on public.render_jobs(output_id, owner_id)
  where output_id is not null;

drop policy if exists "Owners can read their render jobs" on public.render_jobs;
create policy "Owners can read their render jobs"
  on public.render_jobs
  for select
  to authenticated
  using (owner_id = (select auth.uid()));
