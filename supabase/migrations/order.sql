create table tests.order (
  id uuid not null default gen_random_uuid (),
  created_at timestamp with time zone not null default now(),
  trade_num integer null,
  product_name text null,
  amount integer null,
  status text null default '处理中'::text,
  email text null,
  phone text null,
  constraint order_pkey primary key (id)
) TABLESPACE pg_default;

-- 订单查询测试函数
create or replace function fetch_user_orders(
  p_user_email text default null,
  p_phone text default null
)
returns table (
  product_name text,
  trade_num int4,
  amount int4,
  email text,
  phone text,
  created_at  timestamptz,
  status text
)
language plpgsql
stable
as $$
begin
  if p_user_email is not null and p_user_email <> '' then
    return query
    select sp.product_name, sp.trade_num::int4,sp.amount, sp.email, sp.phone,sp. created_at, sp.status
    from tests.order sp
    where sp.email = p_user_email;
    return;
  end if;

  if p_phone is not null and p_phone <> '' then
    return query
    select sp.product_name, sp.subscription_url::text, sp.email, sp.phone,sp.created_at, sp.end_time
    from tests.test_products sp
    where sp.phone = p_phone;
    return;
  end if;
  -- 两者都空则返回空集
  return;
end;
$$;

-- 插入订单函数（包含超时跟踪）
create or replace function insert_order(
  p_product_name text,
  p_trade_num int4,
  p_amount int4,
  p_email text,
  p_phone text
)
returns uuid
language plpgsql
as $$
declare
  new_id uuid;
  check_time timestamp with time zone;
begin
  -- 开始事务
  begin
    -- 插入订单
    insert into tests.order (product_name, trade_num, amount, email, phone)
    values (p_product_name, p_trade_num, p_amount, p_email, p_phone)
    returning id into new_id;
    
    -- 计算10分钟后的检查时间
    check_time := now() + interval '10 minutes';
    
    -- 插入超时跟踪记录
    insert into tests.order_timeout_tracker (order_id, check_at)
    values (new_id, check_time);
    
    return new_id;
  end;
end;
$$;

-- 更新订单状态函数
create or replace function update_order_status(
  p_id uuid,
  p_status text
)
returns boolean
language plpgsql
as $$
declare
  rows_affected int;
begin
  update tests.order 
  set status = p_status
  where id = p_id;
  
  get diagnostics rows_affected = row_count;
  
  return rows_affected > 0;
end;
$$;

-- 创建订单超时跟踪表
create table if not exists tests.order_timeout_tracker (
  id uuid not null default gen_random_uuid(),
  order_id uuid not null references tests.order(id) on delete cascade,
  created_at timestamp with time zone not null default now(),
  check_at timestamp with time zone not null,
  processed boolean not null default false,
  constraint order_timeout_tracker_pkey primary key (id),
  constraint order_timeout_tracker_order_id_unique unique (order_id)
);

-- 创建索引以提高查询性能
create index if not exists idx_order_timeout_check_at on tests.order_timeout_tracker (check_at, processed);
create index if not exists idx_order_timeout_order_id on tests.order_timeout_tracker (order_id);

-- 检查并处理超时订单的函数
create or replace function check_timeout_orders()
returns int
language plpgsql
as $$
declare
  timeout_count int := 0;
  timeout_record record;
begin
  -- 查找所有需要检查的超时订单
  for timeout_record in
    select 
      ott.id as tracker_id,
      ott.order_id,
      o.status
    from tests.order_timeout_tracker ott
    join tests.order o on ott.order_id = o.id
    where ott.check_at <= now()
      and ott.processed = false
  loop
    -- 如果订单状态仍然是"处理中"，则更新为"已超时"
    if timeout_record.status = '处理中' then
      update tests.order 
      set status = '已超时' 
      where id = timeout_record.order_id;
      
      timeout_count := timeout_count + 1;
    end if;
    
    -- 标记该跟踪记录为已处理
    update tests.order_timeout_tracker 
    set processed = true 
    where id = timeout_record.tracker_id;
  end loop;
  
  return timeout_count;
end;
$$;

-- 手动触发超时检查的便捷函数
create or replace function process_order_timeouts()
returns json
language plpgsql
as $$
declare
  processed_count int;
  result json;
begin
  processed_count := check_timeout_orders();
  
  result := json_build_object(
    'processed_count', processed_count,
    'timestamp', now(),
    'message', format('已处理 %s 个超时订单', processed_count)
  );
  
  return result;
end;
$$;

-- 清理已处理的跟踪记录（可选，用于维护）
create or replace function cleanup_processed_timeout_trackers(
  p_days_old int default 7
)
returns int
language plpgsql
as $$
declare
  deleted_count int;
begin
  delete from tests.order_timeout_tracker 
  where processed = true 
    and created_at < now() - interval '1 day' * p_days_old;
  
  get diagnostics deleted_count = row_count;
  
  return deleted_count;
end;
$$;

-- 启用 pg_cron 扩展（需要超级用户权限）
-- CREATE EXTENSION IF NOT EXISTS pg_cron;

-- 设置自动执行超时检查的函数
-- 该函数存在bug，无法正常创建任务，故注释掉
-- create or replace function setup_automatic_timeout_check()
-- returns text
-- language plpgsql
-- as $$
-- declare
--   job_id int;
--   result_text text;
-- begin
--   -- 尝试创建 pg_cron 定时任务（每分钟执行一次）
--   begin
--     -- 删除可能已存在的任务
--     perform cron.unschedule('order-timeout-check');
    
--     -- 创建新的定时任务：每5分钟检查一次超时订单
--     select cron.schedule(
--       'order-timeout-check',           -- 任务名称
--       '*/5 * * * *',                   -- cron 表达式：每分钟执行
--       'SELECT tests.check_timeout_orders();'  -- 要执行的SQL
--     ) into job_id;
    
--     result_text := format('已成功创建自动超时检查任务，任务ID: %s', job_id);
    
--   exception when others then
--     result_text := format('创建自动任务失败: %s. 请确保已启用 pg_cron 扩展', SQLERRM);
--   end;
  
--   return result_text;
-- end;
-- $$;

-- 停止自动执行超时检查的函数
create or replace function stop_automatic_timeout_check()
returns text
language plpgsql
as $$
declare
  result_text text;
begin
  begin
    -- 取消定时任务
    perform cron.unschedule('order-timeout-check');
    result_text := '已成功停止自动超时检查任务';
    
  exception when others then
    result_text := format('停止自动任务失败: %s', SQLERRM);
  end;
  
  return result_text;
end;
$$;

-- 通过 SQL 设置定时任务
SELECT cron.schedule(
    'order-timeout-check',                    -- 任务名称
    '*/5 * * * *',                           -- cron 表达式：每5分钟执行一次
    'SELECT public.check_timeout_orders()'   -- 要执行的SQL命令
);
SELECT cron.schedule(
    'order-timeout-clear',                    -- 任务名称
    '30 4 * * 0',                           -- cron 表达式：每周日凌晨4:30执行一次
    'SELECT public.cleanup_processed_timeout_trackers()'   -- 要执行的SQL命令
);

-- 检查定时任务状态的函数
create or replace function check_cron_job_status()
returns table (
  jobid bigint,
  schedule text,
  command text,
  nodename text,
  nodeport int,
  database text,
  username text,
  active boolean
)
language plpgsql
as $$
begin
  -- 查询 cron 任务状态
  return query
  select 
    cj.jobid,
    cj.schedule,
    cj.command,
    cj.nodename,
    cj.nodeport,
    cj.database,
    cj.username,
    cj.active
  from cron.job cj
  where cj.jobname = 'order-timeout-check';
  
exception when others then
  -- 如果 pg_cron 不可用，返回空结果
  return;
end;
$$;

GRANT USAGE ON SCHEMA tests TO service_role;

-- 授予 orders 表权限
GRANT SELECT ON tests.order TO service_role;
GRANT INSERT ON tests.order TO service_role;
GRANT UPDATE ON tests.order TO service_role;

-- 授予 order_timeout_tracker 表权限
GRANT SELECT ON tests.order_timeout_tracker TO service_role;
GRANT INSERT ON tests.order_timeout_tracker TO service_role;
GRANT UPDATE ON tests.order_timeout_tracker TO service_role;
GRANT DELETE ON tests.order_timeout_tracker TO service_role;

-- 授予函数执行权限
GRANT EXECUTE ON FUNCTION insert_order(text, int4, int4, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION update_order_status(uuid, text) TO service_role;
GRANT EXECUTE ON FUNCTION check_timeout_orders() TO service_role;
GRANT EXECUTE ON FUNCTION process_order_timeouts() TO service_role;
GRANT EXECUTE ON FUNCTION cleanup_processed_timeout_trackers(int) TO service_role;
GRANT EXECUTE ON FUNCTION fetch_user_orders(text, text) TO service_role;
-- GRANT EXECUTE ON FUNCTION setup_automatic_timeout_check() TO service_role;
GRANT EXECUTE ON FUNCTION stop_automatic_timeout_check() TO service_role;
GRANT EXECUTE ON FUNCTION check_cron_job_status() TO service_role;

-- 授予cron的权限
GRANT SELECT ON cron.job TO service_role;
GRANT SELECT ON cron.job_run_details TO service_role;