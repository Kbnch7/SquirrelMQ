-- phantom read
-- это когда второй такой же запрос видит новые строки
-- запускать в двух окнах psql

-- session a
begin transaction isolation level read committed;
select count(*) as new_orders_count from orders where status = 'new';
-- должно быть 2

-- session b
begin transaction isolation level read committed;
insert into orders (customer_name, amount, status)
values ('oleg', 400, 'new');
commit;

-- session a
select count(*) as new_orders_count from orders where status = 'new';
-- теперь будет 3 потому что добавился новый заказ
commit;

-- удаляем добавленную строку чтобы можно было повторить
delete from orders where customer_name = 'oleg' and amount = 400 and status = 'new';
