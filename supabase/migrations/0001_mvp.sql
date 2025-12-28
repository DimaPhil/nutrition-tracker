create extension if not exists "pgcrypto";

create table if not exists users (
    id uuid primary key default gen_random_uuid(),
    telegram_user_id bigint unique not null,
    created_at timestamptz not null default now(),
    last_active_at timestamptz not null default now()
);

create table if not exists user_settings (
    user_id uuid primary key references users(id) on delete cascade,
    timezone text null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists photos (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references users(id) on delete cascade,
    telegram_chat_id bigint not null,
    telegram_message_id bigint not null,
    telegram_file_id text not null,
    telegram_file_unique_id text null,
    created_at timestamptz not null default now()
);

create table if not exists photo_sessions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references users(id) on delete cascade,
    photo_id uuid references photos(id) on delete set null,
    status text not null,
    context_json jsonb not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    expires_at timestamptz null
);

create table if not exists foods_user_library (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references users(id) on delete cascade,
    name text not null,
    brand text null,
    store text null,
    source_type text not null,
    source_ref text null,
    basis text not null,
    serving_size_g numeric null,
    calories numeric not null,
    protein_g numeric not null,
    fat_g numeric not null,
    carbs_g numeric not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    use_count int not null default 0,
    last_used_at timestamptz null
);

create table if not exists food_aliases (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references users(id) on delete cascade,
    food_id uuid references foods_user_library(id) on delete cascade,
    alias_text text not null
);

create table if not exists meal_logs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references users(id) on delete cascade,
    logged_at timestamptz not null,
    total_calories numeric not null,
    total_protein_g numeric not null,
    total_fat_g numeric not null,
    total_carbs_g numeric not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists meal_items (
    id uuid primary key default gen_random_uuid(),
    meal_log_id uuid references meal_logs(id) on delete cascade,
    food_id uuid null references foods_user_library(id) on delete set null,
    name_snapshot text not null,
    nutrition_snapshot jsonb not null,
    portion_grams numeric not null,
    item_calories numeric not null,
    item_protein_g numeric not null,
    item_fat_g numeric not null,
    item_carbs_g numeric not null,
    confidence_json jsonb null
);

create table if not exists audit_events (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references users(id) on delete cascade,
    entity_type text not null,
    entity_id uuid not null,
    event_type text not null,
    before_json jsonb null,
    after_json jsonb null,
    created_at timestamptz not null default now()
);

create table if not exists model_usage_daily (
    id uuid primary key default gen_random_uuid(),
    day date not null,
    user_id uuid references users(id) on delete cascade,
    model text not null,
    requests int not null,
    input_tokens int not null,
    output_tokens int not null,
    created_at timestamptz not null default now()
);

create index if not exists idx_photos_user_id on photos(user_id);
create index if not exists idx_photo_sessions_user_id on photo_sessions(user_id);
create index if not exists idx_foods_user_library_user_id on foods_user_library(user_id);
create index if not exists idx_food_aliases_food_id on food_aliases(food_id);
create index if not exists idx_meal_logs_user_id on meal_logs(user_id);
create index if not exists idx_meal_items_meal_log_id on meal_items(meal_log_id);
create index if not exists idx_audit_events_user_id on audit_events(user_id);
create index if not exists idx_model_usage_daily_user_id on model_usage_daily(user_id);
