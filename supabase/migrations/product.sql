create or replace function fetch_user_products(
  p_user_email text default null,
  p_phone text default null
)
returns table (
  product_name text,
  subscription_url text,
  email text,
  phone text,
  buy_time  timestamptz,
  end_time timestamptz
)
language plpgsql
stable
as $$
begin
  if p_user_email is not null and p_user_email <> '' then
    return query
    select sp.product_name, sp.subscription_url::text, sp.email, sp.phone,sp.buy_time, sp.end_time
    from tests.test_products sp
    where sp.email = p_user_email;
    return;
  end if;

  if p_phone is not null and p_phone <> '' then
    return query
    select sp.product_name, sp.subscription_url::text, sp.email, sp.phone,sp.buy_time, sp.end_time
    from tests.test_products sp
    where sp.phone = p_phone;
    return;
  end if;
  -- 两者都空则返回空集
  return;
end;
$$;

-- 插入产品函数
create or replace function insert_product(
  p_product_name text,
  p_subscription_url text,
  p_email text,
  p_phone text,
  p_time_plan interval
)
returns uuid
language plpgsql
as $$
declare
  new_id uuid;
  calculated_end_time timestamptz;
begin
  -- 计算结束时间：当前时间 + 时间计划
  calculated_end_time := now() + p_time_plan;
  
  insert into tests.test_products (product_name, subscription_url, email, phone, buy_time, end_time)
  values (p_product_name, p_subscription_url, p_email, p_phone, now(), calculated_end_time)
  returning id into new_id;
  
  return new_id;
end;
$$;

GRANT USAGE ON SCHEMA tests TO service_role;
GRANT SELECT ON tests.test_products TO service_role;
GRANT INSERT ON tests.test_products TO service_role;
GRANT EXECUTE ON FUNCTION fetch_user_products_test(text, text) TO service_role;
GRANT EXECUTE ON FUNCTION insert_product(text, text, text, text, interval) TO service_role;