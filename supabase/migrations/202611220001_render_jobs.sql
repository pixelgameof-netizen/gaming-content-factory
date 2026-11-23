-- Dynamic render queue, additive and owner-scoped.
-- This migration is staged in the hardening PR branch; it is NOT applied to Supabase.

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

-- Worker-only RPCs keep the render queue usable without exposing the new table
-- through the public Data API. All writes run as service_role (SECURITY INVOKER).
create or replace function public.gcf_get_render_job_for_worker(p_job_id uuid)
returns table (
  id uuid,
  owner_id uuid,
  package_id uuid,
  status text,
  output_type text,
  platform text,
  aspect_ratio text,
  manifest jsonb,
  expires_at timestamptz,
  output_id uuid
)
language sql
stable
security invoker
set search_path = ''
as $$
  select j.id, j.owner_id, j.package_id, j.status, j.output_type, j.platform,
         j.aspect_ratio, j.manifest, j.expires_at, j.output_id
  from public.render_jobs as j
  where j.id = p_job_id
$$;

create or replace function public.gcf_prepare_render_job_upload(p_job_id uuid)
returns table (
  id uuid,
  owner_id uuid,
  package_id uuid,
  status text,
  output_type text,
  platform text,
  aspect_ratio text,
  expires_at timestamptz
)
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_job public.render_jobs%rowtype;
begin
  update public.render_jobs as j
     set status = 'uploading',
         started_at = coalesce(j.started_at, now()),
         updated_at = now()
   where j.id = p_job_id
     and j.status in ('queued', 'preparing', 'uploading')
     and (j.expires_at is null or j.expires_at > now())
  returning j.* into v_job;

  if not found then
    raise exception 'render job is missing, expired, or not uploadable';
  end if;

  return query select v_job.id, v_job.owner_id, v_job.package_id, v_job.status,
                      v_job.output_type, v_job.platform, v_job.aspect_ratio, v_job.expires_at;
end;
$$;

create or replace function public.gcf_finalize_render_job_output(
  p_job_id uuid,
  p_owner_id uuid,
  p_storage_path text,
  p_sha256 text,
  p_duration_seconds numeric
)
returns table (
  job_id uuid,
  output_id uuid,
  approval_id uuid,
  version_no integer,
  output_sha256 text
)
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_job public.render_jobs%rowtype;
  v_output_id uuid;
  v_approval_id uuid;
  v_version integer;
  v_existing public.video_outputs%rowtype;
begin
  select j.* into v_job
    from public.render_jobs as j
   where j.id = p_job_id
   for update;

  if not found or v_job.owner_id <> p_owner_id then
    raise exception 'render job not found';
  end if;

  if v_job.status = 'awaiting_owner' and v_job.output_id is not null then
    select o.* into v_existing
      from public.video_outputs as o
     where o.id = v_job.output_id
       and o.owner_id = p_owner_id;
    if found and v_existing.storage_path = p_storage_path
       and v_existing.sha256 = lower(p_sha256) then
      select a.id into v_approval_id
        from public.approvals as a
       where a.video_output_id = v_existing.id
         and a.owner_id = p_owner_id
         and a.output_version = v_existing.version_no
         and a.output_sha256 = v_existing.sha256
       order by a.created_at desc
       limit 1;
      if v_approval_id is null then
        raise exception 'finalized output has no matching approval record';
      end if;
      return query select v_job.id, v_existing.id, v_approval_id,
                          v_existing.version_no, v_existing.sha256;
      return;
    end if;
    raise exception 'render job already finalized with a different output';
  end if;

  if v_job.status <> 'uploading' then
    raise exception 'render job is not in uploading state';
  end if;
  if p_storage_path is null
     or p_storage_path not like (v_job.owner_id::text || '/' || v_job.package_id::text ||
                                 '/render-jobs/' || v_job.id::text || '/%.mp4')
     or p_storage_path like '%..%'
     or p_sha256 is null
     or p_sha256 !~ '^[a-fA-F0-9]{64}$'
     or p_duration_seconds is null
     or p_duration_seconds <= 1
     or p_duration_seconds > 900 then
    raise exception 'invalid output metadata';
  end if;

  perform pg_advisory_xact_lock(hashtextextended(
    v_job.package_id::text || ':' || v_job.output_type || ':' || v_job.platform, 0
  ));

  select coalesce(max(o.version_no), 0) + 1 into v_version
    from public.video_outputs as o
   where o.package_id = v_job.package_id
     and o.output_type = v_job.output_type
     and o.platform = v_job.platform;

  insert into public.video_outputs (
    owner_id, package_id, output_type, platform, aspect_ratio, version_no,
    storage_provider, storage_bucket, storage_path, sha256, duration_seconds, quality_status
  ) values (
    v_job.owner_id, v_job.package_id, v_job.output_type, v_job.platform, v_job.aspect_ratio, v_version,
    'supabase', 'gcf-video-outputs', p_storage_path, lower(p_sha256),
    round(p_duration_seconds)::integer, 'passed'
  ) returning id into v_output_id;

  insert into public.approvals (
    owner_id, video_output_id, output_version, output_sha256, status
  ) values (
    v_job.owner_id, v_output_id, v_version, lower(p_sha256), 'pending'
  ) returning id into v_approval_id;

  update public.render_jobs
     set output_id = v_output_id,
         status = 'awaiting_owner',
         completed_at = now(),
         updated_at = now()
   where id = v_job.id;

  return query select v_job.id, v_output_id, v_approval_id, v_version, lower(p_sha256);
end;
$$;

revoke all on function public.gcf_get_render_job_for_worker(uuid) from public, anon, authenticated;
revoke all on function public.gcf_prepare_render_job_upload(uuid) from public, anon, authenticated;
revoke all on function public.gcf_finalize_render_job_output(uuid, uuid, text, text, numeric) from public, anon, authenticated;
grant execute on function public.gcf_get_render_job_for_worker(uuid) to service_role;
grant execute on function public.gcf_prepare_render_job_upload(uuid) to service_role;
grant execute on function public.gcf_finalize_render_job_output(uuid, uuid, text, text, numeric) to service_role;


-- Authenticated app RPCs: clients never write directly to render_jobs.
create or replace function public.gcf_create_render_job(
  p_package_id uuid,
  p_output_type text,
  p_platform text,
  p_aspect_ratio text,
  p_manifest jsonb
)
returns table (
  id uuid,
  status text,
  output_type text,
  platform text,
  aspect_ratio text,
  created_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_owner uuid := auth.uid();
  v_item jsonb;
  v_asset public.media_assets%rowtype;
  v_review public.rights_reviews%rowtype;
  v_job_id uuid;
  v_scene_count integer := 0;
  v_voice_count integer := 0;
  v_asset_count integer;
  v_unique_ids integer;
  v_unique_names integer;
  v_file_name text;
  v_role text;
begin
  if v_owner is null then
    raise exception 'authentication required';
  end if;
  if p_manifest is null or jsonb_typeof(p_manifest) <> 'object'
     or jsonb_typeof(p_manifest->'assets') <> 'array' then
    raise exception 'manifest must contain an assets array';
  end if;
  select count(*), count(distinct value->>'asset_id'), count(distinct value->>'file_name')
    into v_asset_count, v_unique_ids, v_unique_names
    from jsonb_array_elements(p_manifest->'assets') as entries(value);
  if v_asset_count < 2 or v_asset_count > 20
     or v_asset_count <> v_unique_ids or v_asset_count <> v_unique_names then
    raise exception 'manifest must contain 2 to 20 unique assets and filenames';
  end if;

  if not exists (
    select 1 from public.content_packages as p
     where p.id = p_package_id and p.owner_id = v_owner
  ) then
    raise exception 'content package not found';
  end if;

  for v_item in select value from jsonb_array_elements(p_manifest->'assets') as entries(value)
  loop
    if coalesce(v_item->>'asset_id','') !~* '^[0-9a-f-]{36}$' then
      raise exception 'manifest contains an invalid asset id';
    end if;
    v_file_name := v_item->>'file_name';
    if v_file_name is null or v_file_name !~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$'
       or v_file_name like '%..%' then
      raise exception 'manifest contains an unsafe filename';
    end if;

    select a.* into v_asset
      from public.media_assets as a
     where a.id = (v_item->>'asset_id')::uuid
       and a.owner_id = v_owner
       and a.package_id = p_package_id
       and a.rights_status = 'approved';
    if not found then
      raise exception 'asset is missing, unapproved, or outside this package';
    end if;
    if v_asset.storage_bucket <> 'gcf-source-media'
       or v_asset.storage_path is null
       or v_asset.storage_path not like (v_owner::text || '/%')
       or v_asset.storage_path like '%..%'
       or v_asset.sha256 !~* '^[a-f0-9]{64}$' then
      raise exception 'asset storage path or SHA-256 is invalid';
    end if;

    v_role := v_asset.asset_role;
    if v_role in ('gameplay','trailer') then
      if v_file_name !~ '^scene-[0-9]{2,3}\.mp4$' or v_asset.mime_type <> 'video/mp4' then
        raise exception 'gameplay/trailer must be MP4 scene files';
      end if;
      v_scene_count := v_scene_count + 1;
    elsif v_role = 'voiceover' then
      if v_file_name <> 'voiceover.wav' or v_asset.mime_type not in ('audio/wav','audio/x-wav') then
        raise exception 'voiceover must be voiceover.wav';
      end if;
      v_voice_count := v_voice_count + 1;
    elsif v_role = 'music' then
      if v_file_name <> 'music.wav' or v_asset.mime_type not in ('audio/wav','audio/x-wav') then
        raise exception 'music must be music.wav';
      end if;
    else
      raise exception 'unsupported render asset role';
    end if;

    if v_role in ('gameplay','trailer','music') and v_asset.source_id is null then
      raise exception 'source-backed gameplay, trailer, and music require rights review';
    end if;
    if v_asset.source_id is not null then
      select r.* into v_review
        from public.rights_reviews as r
       where r.owner_id = v_owner and r.source_id = v_asset.source_id
       order by r.created_at desc
       limit 1;
      if not found or v_review.status <> 'approved_by_owner'
         or v_review.commercial_use is not true
         or v_review.derivatives_allowed is not true
         or v_review.redistribution_allowed is not true
         or v_review.game_policy_verified is not true
         or v_review.third_party_assets_verified is not true
         or v_review.license_url is null
         or v_review.reviewed_by <> v_owner
         or v_review.reviewed_at is null
         or (v_review.expires_at is not null and v_review.expires_at <= now()) then
        raise exception 'latest rights review is not owner-approved for this asset';
      end if;
      if v_role in ('gameplay','trailer','music') and v_review.music_rights_verified is not true then
        raise exception 'music rights or absence of music have not been verified';
      end if;
    end if;
  end loop;

  if v_scene_count < 1 or v_voice_count <> 1 then
    raise exception 'render requires at least one scene and exactly one voiceover';
  end if;

  insert into public.render_jobs (
    owner_id, package_id, output_type, platform, aspect_ratio, manifest, status, expires_at
  ) values (
    v_owner, p_package_id, p_output_type, p_platform, p_aspect_ratio, p_manifest, 'queued', now() + interval '1 day'
  ) returning render_jobs.id into v_job_id;

  return query
    select j.id, j.status, j.output_type, j.platform, j.aspect_ratio, j.created_at
      from public.render_jobs as j
     where j.id = v_job_id;
end;
$$;

create or replace function public.gcf_list_render_jobs(p_package_id uuid)
returns table (
  id uuid,
  package_id uuid,
  status text,
  output_type text,
  platform text,
  aspect_ratio text,
  output_id uuid,
  created_at timestamptz,
  updated_at timestamptz,
  completed_at timestamptz
)
language sql
stable
security definer
set search_path = ''
as $$
  select j.id, j.package_id, j.status, j.output_type, j.platform, j.aspect_ratio,
         j.output_id, j.created_at, j.updated_at, j.completed_at
    from public.render_jobs as j
   where j.owner_id = auth.uid()
     and j.package_id = p_package_id
   order by j.created_at desc
   limit 50
$$;

revoke all on function public.gcf_create_render_job(uuid, text, text, text, jsonb) from public, anon, service_role;
revoke all on function public.gcf_list_render_jobs(uuid) from public, anon, service_role;
grant execute on function public.gcf_create_render_job(uuid, text, text, text, jsonb) to authenticated;
grant execute on function public.gcf_list_render_jobs(uuid) to authenticated;
