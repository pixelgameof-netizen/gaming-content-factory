-- Dynamic render queue, additive and owner-scoped.
-- This migration is staged in the hardening PR branch; it is NOT applied to Supabase yet.

create table if not exists public.render_jobs (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  package_id uuid not null,
  output_type text not null default 'short'
    check (output_type in ('long_video','short')),
  platform text not null default 'youtube_shorts'
    check (platform in ('youtube','youtube_shorts','tiktok','instagram_reels','facebook_reels')),
  status text not null default 'queued'
    check (status in ('queued','preparing','rendering','uploading','quality_check','awaiting_owner','failed','cancelled')),
  aspect_ratio text not null check (aspect_ratio in ('9:16','16:9')),
  manifest jsonb not null check (jsonb_typeof(manifest) = 'object'),
  output_id uuid,
  error_code text,
  error_detail text,
  attempt_count integer not null default 0 check (attempt_count >= 0 and attempt_count <= 3),
  expires_at timestamptz,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint render_jobs_package_owner_fkey
    foreign key (package_id, owner_id)
    references public.content_packages(id, owner_id) on delete cascade,
  constraint render_jobs_output_owner_fkey
    foreign key (output_id, owner_id)
    references public.video_outputs(id, owner_id) on delete restrict
);

create index if not exists render_jobs_owner_created_idx
  on public.render_jobs(owner_id, created_at desc);
create index if not exists render_jobs_status_created_idx
  on public.render_jobs(status, created_at)
  where status in ('queued','preparing','rendering','uploading','quality_check');

alter table public.render_jobs enable row level security;

drop policy if exists "Owners can read their render jobs" on public.render_jobs;
create policy "Owners can read their render jobs"
  on public.render_jobs
  for select
  to authenticated
  using (owner_id = auth.uid());

revoke all on public.render_jobs from anon, authenticated;
grant select on public.render_jobs to authenticated;
grant all on public.render_jobs to service_role;
