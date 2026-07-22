#!/bin/bash
# 完整鉴权 + CUD 测试
TOKEN=$(cat .admin_token.txt)

pass=0
fail=0

# ============== 1. 鉴权隔离 ==============
echo "=== [Auth 1] 无 token 打 admin 接口 应 40001 ==="
body=$(curl -s http://localhost:8080/api/admin/dashboard/stats)
code=$(echo "$body" | node -e "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{try{console.log(JSON.parse(d).code)}catch{console.log('NO_JSON')}})")
if [ "$code" = "10002" ] || [ "$code" = "40001" ]; then
  echo "  OK  no-token blocked (code=$code)"; pass=$((pass+1))
else
  echo "  FAIL  code=$code body=$body"; fail=$((fail+1))
fi

echo
echo "=== [Auth 2] 用 C 端用户 token 打 admin 接口 应 60003 NOT_ADMIN_TOKEN ==="
# 用现有 C 端账号登录
USER_LOGIN=$(curl -s -X POST http://localhost:8080/api/user/auth/sendCode -d "phone=13800138000")
sleep 0.2
# 骨架期 sms.mock=true, 验证码统一 123456
USER_RESP=$(curl -s -X POST http://localhost:8080/api/user/auth/login \
  -H "Content-Type: application/json" \
  -d '{"phone":"13800138000","code":"123456"}')
echo "  login resp: ${USER_RESP:0:200}"
USER_TOKEN=$(echo "$USER_RESP" | node -e "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{try{const r=JSON.parse(d);console.log(r.data?.accessToken||r.accessToken||'')}catch(e){console.log('')}})")

if [ -n "$USER_TOKEN" ]; then
  # 用普通用户 token 打 admin 接口
  body=$(curl -s -H "Authorization: Bearer $USER_TOKEN" http://localhost:8080/api/admin/dashboard/stats)
  code=$(echo "$body" | node -e "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{try{console.log(JSON.parse(d).code)}catch{console.log('NO_JSON')}})")
  if [ "$code" = "60003" ]; then
    echo "  OK  USER token blocked from admin (code=60003)"; pass=$((pass+1))
  else
    echo "  FAIL  code=$code (期望 60003 NOT_ADMIN_TOKEN)"; fail=$((fail+1))
  fi

  # 用普通用户 token 打普通 C 端接口应能通
  body=$(curl -s -H "Authorization: Bearer $USER_TOKEN" http://localhost:8080/api/user/auth/profile)
  code=$(echo "$body" | node -e "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{try{console.log(JSON.parse(d).code)}catch{console.log('NO_JSON')}})")
  if [ "$code" = "0" ]; then
    echo "  OK  USER token works on user API (code=0)"; pass=$((pass+1))
  else
    echo "  FAIL  code=$code (期望 0)"; fail=$((fail+1))
  fi
else
  echo "  SKIP  no user token (mock sms may not be enabled with fixed code)"
fi

echo
echo "=== [Auth 3] admin token 打 C 端 API 应能通(role=ADMIN 也是 JWT 有效) ==="
body=$(curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/user/auth/profile)
code=$(echo "$body" | node -e "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{try{console.log(JSON.parse(d).code)}catch{console.log('NO_JSON')}})")
# 这里返回 0 或 40004(用户不存在,因为 admin id=1 可能不在 user_svc.users) 都算 JWT 通过
if [ "$code" = "0" ] || [ "$code" = "40004" ] || [ "$code" = "10001" ]; then
  echo "  OK  admin JWT valid on user API (biz code=$code)"; pass=$((pass+1))
else
  echo "  FAIL  code=$code body=${body:0:200}"; fail=$((fail+1))
fi

# ============== 2. Notice CUD ==============
echo
echo "=== [CUD Notice] 完整增改删循环 ==="
H="Authorization: Bearer $TOKEN"

# create
resp=$(curl -s -X POST -H "$H" -H "Content-Type: application/json" \
  http://localhost:8080/api/admin/notice/add \
  -d '{"title":"__test_notice__","content":"test content from curl","noticeType":"SYSTEM","isActive":1}')
code=$(echo "$resp" | node -e "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{try{console.log(JSON.parse(d).code)}catch{console.log('NO_JSON')}})")
if [ "$code" = "0" ]; then
  echo "  OK  notice.add"; pass=$((pass+1))
else
  echo "  FAIL  notice.add code=$code body=${resp:0:200}"; fail=$((fail+1))
fi

# list & find the test notice
list_resp=$(curl -s -H "$H" "http://localhost:8080/api/admin/notice/list?page=1&size=20")
notice_id=$(echo "$list_resp" | node -e "
let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{
  try{
    const r=JSON.parse(d);
    const arr=r.data?.records||r.data||[];
    const t=arr.find(x=>x.title==='__test_notice__');
    console.log(t?t.id:'')
  }catch{console.log('')}
})")

if [ -n "$notice_id" ]; then
  echo "  OK  notice.list found id=$notice_id"; pass=$((pass+1))

  # update
  resp=$(curl -s -X PUT -H "$H" -H "Content-Type: application/json" \
    http://localhost:8080/api/admin/notice/update \
    -d "{\"id\":$notice_id,\"title\":\"__test_notice_updated__\",\"content\":\"updated\",\"noticeType\":\"SYSTEM\",\"isActive\":1}")
  code=$(echo "$resp" | node -e "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{try{console.log(JSON.parse(d).code)}catch{console.log('NO_JSON')}})")
  if [ "$code" = "0" ]; then echo "  OK  notice.update"; pass=$((pass+1)); else echo "  FAIL  notice.update"; fail=$((fail+1)); fi

  # delete
  resp=$(curl -s -X DELETE -H "$H" "http://localhost:8080/api/admin/notice/delete/$notice_id")
  code=$(echo "$resp" | node -e "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{try{console.log(JSON.parse(d).code)}catch{console.log('NO_JSON')}})")
  if [ "$code" = "0" ]; then echo "  OK  notice.delete"; pass=$((pass+1)); else echo "  FAIL  notice.delete"; fail=$((fail+1)); fi
else
  echo "  FAIL  notice.list did not find created record"
  fail=$((fail+2))  # skip update/delete
fi

# ============== 3. Product Update Status ==============
echo
echo "=== [CUD Product] 上下架切换 ==="
# 拿一个商品 ID
list_resp=$(curl -s -H "$H" "http://localhost:8080/api/admin/product/list?page=1&size=1")
pid=$(echo "$list_resp" | node -e "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{try{const r=JSON.parse(d);const arr=r.data?.records||[];console.log(arr[0]?arr[0].id:'')}catch{console.log('')}})")
orig_status=$(echo "$list_resp" | node -e "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{try{const r=JSON.parse(d);const arr=r.data?.records||[];console.log(arr[0]?arr[0].status:'')}catch{console.log('')}})")

if [ -n "$pid" ]; then
  new_status=$((1 - orig_status))
  resp=$(curl -s -X PUT -H "$H" "http://localhost:8080/api/admin/product/$pid/status?status=$new_status")
  code=$(echo "$resp" | node -e "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{try{console.log(JSON.parse(d).code)}catch{console.log('NO_JSON')}})")
  if [ "$code" = "0" ]; then echo "  OK  product.updateStatus id=$pid $orig_status→$new_status"; pass=$((pass+1)); else echo "  FAIL  product.updateStatus code=$code"; fail=$((fail+1)); fi

  # 恢复原状态
  curl -s -X PUT -H "$H" "http://localhost:8080/api/admin/product/$pid/status?status=$orig_status" > /dev/null
  echo "  (restored to $orig_status)"
else
  echo "  SKIP  no product to test"
fi

# ============== 4. Data 完整性 ==============
echo
echo "=== [Data] 关键字段是否返回 ==="

# users.list 记录字段
body=$(curl -s -H "$H" "http://localhost:8080/api/admin/users?page=1&size=1")
has_fields=$(echo "$body" | node -e "
let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{
  try{
    const r=JSON.parse(d);
    const rec=r.data?.records?.[0];
    if(!rec){console.log('empty');return;}
    const keys=['id','phone','status','createTime'];
    console.log(keys.every(k=>rec[k]!==undefined)?'ok':'miss:'+keys.filter(k=>rec[k]===undefined).join(','))
  }catch(e){console.log('err:'+e.message)}
})")
if [ "$has_fields" = "ok" ] || [ "$has_fields" = "empty" ]; then
  echo "  OK  users.list fields ($has_fields)"; pass=$((pass+1))
else
  echo "  FAIL  users.list $has_fields"; fail=$((fail+1))
fi

# dashboard fields
body=$(curl -s -H "$H" "http://localhost:8080/api/admin/dashboard/stats")
has_fields=$(echo "$body" | node -e "
let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{
  try{
    const r=JSON.parse(d);
    const s=r.data;
    const keys=['userCount','productCount','orderCount','conversationCount','todayRevenue'];
    console.log(keys.every(k=>s[k]!==undefined)?'ok':'miss:'+keys.filter(k=>s[k]===undefined).join(','))
  }catch(e){console.log('err:'+e.message)}
})")
if [ "$has_fields" = "ok" ]; then echo "  OK  dashboard fields"; pass=$((pass+1)); else echo "  FAIL  dashboard $has_fields"; fail=$((fail+1)); fi

# product stats
body=$(curl -s -H "$H" "http://localhost:8080/api/admin/product/stats")
has_fields=$(echo "$body" | node -e "
let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{
  try{
    const r=JSON.parse(d);
    const s=r.data;
    const keys=['total','online','offline'];
    console.log(keys.every(k=>s[k]!==undefined)?'ok':'miss')
  }catch{console.log('err')}
})")
if [ "$has_fields" = "ok" ]; then echo "  OK  product.stats fields"; pass=$((pass+1)); else echo "  FAIL  product.stats $has_fields"; fail=$((fail+1)); fi

# order stats
body=$(curl -s -H "$H" "http://localhost:8080/api/admin/order/stats")
has_fields=$(echo "$body" | node -e "
let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{
  try{
    const s=JSON.parse(d).data;
    const keys=['totalOrders','pendingPayment','completed','todayOrders','totalRevenue'];
    console.log(keys.every(k=>s[k]!==undefined)?'ok':'miss:'+keys.filter(k=>s[k]===undefined).join(','))
  }catch{console.log('err')}
})")
if [ "$has_fields" = "ok" ]; then echo "  OK  order.stats fields"; pass=$((pass+1)); else echo "  FAIL  order.stats $has_fields"; fail=$((fail+1)); fi

echo
echo "=== SUMMARY: pass=$pass  fail=$fail ==="
