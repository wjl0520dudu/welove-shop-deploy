#!/bin/bash
TOKEN=$(cat .admin_token.txt)
H="Authorization: Bearer $TOKEN"

pass=0
fail=0
fail_list=""

run() {
  local name="$1"; local url="$2"
  local body
  body=$(curl -s -H "$H" "$url")
  local code
  code=$(echo "$body" | node -e "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{try{console.log(JSON.parse(d).code)}catch{console.log('NO_JSON')}})")
  if [ "$code" = "0" ]; then
    pass=$((pass+1))
    echo "  OK  $name"
  else
    fail=$((fail+1))
    fail_list="$fail_list\n  FAIL $name  code=$code  body=${body:0:200}"
    echo "  FAIL $name  code=$code"
  fi
}

echo "=== Dashboard & User ==="
run "dashboard.stats"        "http://localhost:8080/api/admin/dashboard/stats"
run "users.list"             "http://localhost:8080/api/admin/users?page=1&size=3"

echo "=== Product ==="
run "product.list"           "http://localhost:8080/api/admin/product/list?page=1&size=3"
run "product.stats"          "http://localhost:8080/api/admin/product/stats"
run "product.brands"         "http://localhost:8080/api/admin/product/brands"

echo "=== Order ==="
run "order.list"             "http://localhost:8080/api/admin/order/list?page=1&size=3"
run "order.stats"            "http://localhost:8080/api/admin/order/stats"

echo "=== Conversation ==="
run "conversation.list"      "http://localhost:8080/api/admin/conversation/list?page=1&size=3"
run "conversation.stats"     "http://localhost:8080/api/admin/conversation/stats"

echo "=== Notice ==="
run "notice.list"            "http://localhost:8080/api/admin/notice/list?page=1&size=3"

echo "=== Agent ==="
run "agent.runs"             "http://localhost:8080/api/admin/agent/runs?page=1&size=3"
run "agent.toolCalls"        "http://localhost:8080/api/admin/agent/tool-calls?page=1&size=3"
run "agent.failedToolCalls"  "http://localhost:8080/api/admin/agent/tool-calls/failed?limit=3"

echo "=== QA ==="
run "qa.logs"                "http://localhost:8080/api/admin/qa/logs?page=1&size=3"
run "qa.unanswered"          "http://localhost:8080/api/admin/qa/unanswered/list"

echo "=== Knowledge ==="
run "knowledge.list"         "http://localhost:8080/api/admin/knowledge/list"

echo "=== Knowledge Inspection ==="
run "inspect.unanswered"     "http://localhost:8080/api/admin/knowledge-inspection/unanswered/analyze?minCount=1"
run "inspect.library"        "http://localhost:8080/api/admin/knowledge-inspection/library/analyze"

echo "=== Recommend ==="
run "recommend.stats"        "http://localhost:8080/api/admin/recommend/stats"
run "recommend.logs"         "http://localhost:8080/api/admin/recommend/logs?page=1&size=3"

echo
echo "=== SUMMARY: pass=$pass  fail=$fail ==="
if [ $fail -gt 0 ]; then
  echo -e "$fail_list"
fi
