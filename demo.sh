#!/bin/bash

BASE_URL="http://localhost:8080"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo ""
    echo "=============================================="
    echo -e "${BLUE}$1${NC}"
    echo "=============================================="
}

print_step() {
    echo ""
    echo -e "${YELLOW}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

wait_for_service() {
    echo "等待服务启动..."
    for i in {1..30}; do
        if curl -s "$BASE_URL/status" > /dev/null 2>&1; then
            print_success "服务已启动!"
            return 0
        fi
        sleep 1
    done
    echo -e "${RED}服务启动超时${NC}"
    return 1
}

print_header "拣货波次编排服务 - 完整演示路径"

wait_for_service

echo ""
echo -e "${BLUE}演示路径：${NC}"
echo "  1. 查看初始状态（门店、库存、需求）"
echo "  2. 首次生成波次（按优先级编排，整单原则）"
echo "  3. 查看波次详情和库存占用"
echo "  4. 提交波次待确认（锁定库存）"
echo "  5. 新增一家高优先级门店需求（验证库存锁定不被抢走）"
echo "  6. 修改待确认波次中的门店需求数量（触发重排）"
echo "  7. 查看重排前后对比（哪些门店被挪动、为什么）"
echo "  8. 确认波次（库存从锁定转为已分配）"
echo "  9. 模拟超时释放（验证超时后库存重新分配）"
echo "  10. 查看完整重排历史记录"

read -p $'\n按回车键开始演示...' -n1 -s

print_header "第1步：查看初始状态"

print_step "查看所有门店（按优先级）"
curl -s "$BASE_URL/stores" | python3 -m json.tool

print_step "查看当前库存"
curl -s "$BASE_URL/inventory" | python3 -m json.tool

print_step "查看待处理的补货需求"
curl -s "$BASE_URL/requests?status=pending" | python3 -m json.tool

read -p $'\n按回车键继续...' -n1 -s

print_header "第2步：首次生成波次"

print_step "触发生成波次（按门店优先级，整单进入）"
RESULT=$(curl -s -X POST "$BASE_URL/waves/generate" -H "Content-Type: application/json" -d '{"trigger": "demo_initial"}')
echo "$RESULT" | python3 -m json.tool

REARRANGE_ID=$(echo "$RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin)['rearrangement_id'])")
print_success "重排记录ID: $REARRANGE_ID"

read -p $'\n按回车键继续...' -n1 -s

print_header "第3步：查看波次详情和库存占用"

print_step "查看所有波次"
curl -s "$BASE_URL/waves" | python3 -m json.tool

print_step "查看第一个波次详情"
FIRST_WAVE=$(curl -s "$BASE_URL/waves" | python3 -c "import sys, json; waves=json.load(sys.stdin); print(waves[0]['wave_id'] if waves else '')")
if [ -n "$FIRST_WAVE" ]; then
    curl -s "$BASE_URL/waves/$FIRST_WAVE" | python3 -m json.tool
fi

print_step "查看当前库存状态（注意locked_quantity已被锁定）"
curl -s "$BASE_URL/inventory" | python3 -m json.tool

read -p $'\n按回车键继续...' -n1 -s

print_header "第4步：提交波次待确认（锁定库存）"

if [ -n "$FIRST_WAVE" ]; then
    print_step "将波次 $FIRST_WAVE 提交待确认（超时时间2分钟，演示用）"
    curl -s -X POST "$BASE_URL/waves/$FIRST_WAVE/submit-confirm" \
         -H "Content-Type: application/json" \
         -d '{"timeout_minutes": 2}' | python3 -m json.tool
    print_success "波次已进入待确认状态，库存已锁定"
fi

print_step "再次查看库存状态"
curl -s "$BASE_URL/inventory" | python3 -m json.tool

read -p $'\n按回车键继续...' -n1 -s

print_header "第5步：新增高优先级门店需求（验证锁定不被抢走）"

print_step "新增一家优先级为1的高优先级门店需求"
NEW_REQ=$(curl -s -X POST "$BASE_URL/requests" \
     -H "Content-Type: application/json" \
     -d '{
       "store_id": "STORE-001",
       "items": {
         "PROD-001": 20,
         "PROD-002": 30,
         "PROD-003": 15
       }
     }')
echo "$NEW_REQ" | python3 -m json.tool
NEW_REQ_ID=$(echo "$NEW_REQ" | python3 -c "import sys, json; print(json.load(sys.stdin)['request_id'])")

print_step "重新生成波次 - 验证已锁定的货不会被抢走"
RESULT2=$(curl -s -X POST "$BASE_URL/waves/generate" -H "Content-Type: application/json" -d '{"trigger": "demo_new_high_priority"}')
echo "$RESULT2" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print('重排记录ID:', data['rearrangement_id'])
print('变动原因:', data['reason_summary'])
print('门店变动数:', len(data['store_changes']))
for sc in data['store_changes']:
    print(f'  - {sc[\"store_id\"]}: {sc[\"change_type\"]} ({sc[\"reason\"]})')
"

print_step "查看波次状态 - 已确认/待确认的波次应该保持不变"
curl -s "$BASE_URL/waves" | python3 -c "
import sys, json
waves = json.load(sys.stdin)
for w in waves:
    print(f'波次 {w[\"wave_id\"]}: 状态={w[\"status\"]}, 门店数={len(w[\"stores\"])}')
"

print_success "验证：已锁定（待确认）的波次中的库存不会被新的高优先级需求抢走"

read -p $'\n按回车键继续...' -n1 -s

print_header "第6步：修改待确认波次中门店的需求数量（触发重排）"

print_step "先找到仍在待处理状态的需求"
PENDING_REQS=$(curl -s "$BASE_URL/requests?status=pending")
echo "$PENDING_REQS" | python3 -c "
import sys, json
reqs = json.load(sys.stdin)
for r in reqs:
    print(f'{r[\"request_id\"]} - {r[\"store_name\"]} - {r[\"status\"]}')
"

print_step "找一个在波次中但尚未确认的需求来修改"
IN_WAVE_REQ=$(curl -s "$BASE_URL/requests?status=in_wave" | python3 -c "
import sys, json
reqs = json.load(sys.stdin)
if reqs:
    print(reqs[0]['request_id'])
else:
    print('')
")

if [ -n "$IN_WAVE_REQ" ]; then
    print_step "修改需求 $IN_WAVE_REQ 的数量（增加数量，可能导致重排）"
    MODIFY_RESULT=$(curl -s -X PUT "$BASE_URL/requests/$IN_WAVE_REQ/quantity" \
         -H "Content-Type: application/json" \
         -d '{
           "items": {
             "PROD-001": 30,
             "PROD-002": 40,
             "PROD-003": 20,
             "PROD-004": 15
           }
         }')
    echo "$MODIFY_RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print('重排记录ID:', data['rearrangement_id'])
print('触发原因:', data['trigger'])
print('变动总结:', data['reason_summary'])
print('门店变动:')
for sc in data['store_changes']:
    print(f'  {sc[\"store_id\"]}: {sc[\"change_type\"]} - {sc[\"reason\"]}')
"
    MODIFY_REARRANGE_ID=$(echo "$MODIFY_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin)['rearrangement_id'])")
    print_success "修改需求后自动触发重排"
else
    print_step "没有在波次中的需求，新增一个需求来演示"
    curl -s -X POST "$BASE_URL/requests" \
         -H "Content-Type: application/json" \
         -d '{"store_id": "STORE-004", "items": {"PROD-001": 5, "PROD-002": 8}}' > /dev/null
    curl -s -X POST "$BASE_URL/waves/generate" -H "Content-Type: application/json" -d '{"trigger": "demo_prepare"}' > /dev/null

    IN_WAVE_REQ=$(curl -s "$BASE_URL/requests?status=in_wave" | python3 -c "
import sys, json
reqs = json.load(sys.stdin)
if reqs:
    print(reqs[-1]['request_id'])
else:
    print('')
")

    if [ -n "$IN_WAVE_REQ" ]; then
        print_step "修改需求 $IN_WAVE_REQ 的数量"
        MODIFY_RESULT=$(curl -s -X PUT "$BASE_URL/requests/$IN_WAVE_REQ/quantity" \
             -H "Content-Type: application/json" \
             -d '{"items": {"PROD-001": 100, "PROD-002": 200}}')
        echo "$MODIFY_RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print('重排记录ID:', data['rearrangement_id'])
print('触发原因:', data['trigger'])
print('变动总结:', data['reason_summary'])
print('门店变动:')
for sc in data['store_changes']:
    print(f'  {sc[\"store_id\"]}: {sc[\"change_type\"]} - {sc[\"reason\"]}')
"
        MODIFY_REARRANGE_ID=$(echo "$MODIFY_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin)['rearrangement_id'])")
    fi
fi

read -p $'\n按回车键继续...' -n1 -s

print_header "第7步：查看重排前后对比"

if [ -n "$MODIFY_REARRANGE_ID" ]; then
    print_step "查看重排前后详细对比"
    curl -s "$BASE_URL/rearrangements/compare/$MODIFY_REARRANGE_ID" | python3 -m json.tool
fi

print_step "查看所有重排历史"
curl -s "$BASE_URL/rearrangements" | python3 -c "
import sys, json
records = json.load(sys.stdin)
for r in records:
    print(f'{r[\"rearrangement_id\"]} - {r[\"trigger\"]} - {r[\"reason_summary\"]}')
    for sc in r['store_changes']:
        print(f'    {sc[\"store_id\"]}: {sc[\"change_type\"]}')
"

read -p $'\n按回车键继续...' -n1 -s

print_header "第8步：确认波次（库存从锁定转为已分配）"

print_step "查看所有待确认状态的波次"
PENDING_WAVES=$(curl -s "$BASE_URL/waves?status=pending_confirm")
echo "$PENDING_WAVES" | python3 -c "
import sys, json
waves = json.load(sys.stdin)
for w in waves:
    print(f'{w[\"wave_id\"]} - 状态: {w[\"status\"]} - 门店数: {len(w[\"stores\"])}')
"

PENDING_WAVE_ID=$(echo "$PENDING_WAVES" | python3 -c "
import sys, json
waves = json.load(sys.stdin)
print(waves[0]['wave_id'] if waves else '')
")

if [ -n "$PENDING_WAVE_ID" ]; then
    print_step "确认波次 $PENDING_WAVE_ID"
    curl -s -X POST "$BASE_URL/waves/$PENDING_WAVE_ID/confirm" | python3 -c "
import sys, json
w = json.load(sys.stdin)
print(f'波次 {w[\"wave_id\"]} 已确认')
print(f'确认时间: {w[\"confirmed_at\"]}')
"
    print_success "波次已确认，库存从锁定转为已分配"

    print_step "查看确认后的库存状态（allocated_quantity增加）"
    curl -s "$BASE_URL/inventory" | python3 -m json.tool
fi

read -p $'\n按回车键继续...' -n1 -s

print_header "第9步：模拟超时释放"

print_step "先创建一个新波次并提交待确认"
RESULT3=$(curl -s -X POST "$BASE_URL/waves/generate" -H "Content-Type: application/json" -d '{"trigger": "demo_expire_prep"}')
NEW_WAVE_FOR_EXPIRE=$(curl -s "$BASE_URL/waves?status=draft" | python3 -c "
import sys, json
waves = json.load(sys.stdin)
print(waves[0]['wave_id'] if waves else '')
")

if [ -n "$NEW_WAVE_FOR_EXPIRE" ]; then
    print_step "将波次 $NEW_WAVE_FOR_EXPIRE 提交待确认（超时时间设为0.1分钟=6秒，快速演示）"
    curl -s -X POST "$BASE_URL/waves/$NEW_WAVE_FOR_EXPIRE/submit-confirm" \
         -H "Content-Type: application/json" \
         -d '{"timeout_minutes": 0.1}' | python3 -c "
import sys, json
w = json.load(sys.stdin)
print(f'波次 {w[\"wave_id\"]} 已提交待确认')
print(f'过期时间: {w[\"expires_at\"]}')
"

    print_step "等待7秒让波次超时..."
    sleep 7

    print_step "触发超时检查"
    EXPIRE_RESULT=$(curl -s -X POST "$BASE_URL/waves/check-expired")
    echo "$EXPIRE_RESULT" | python3 -m json.tool

    print_step "查看波次状态 - 超时的波次已过期，库存已释放"
    curl -s "$BASE_URL/waves" | python3 -c "
import sys, json
waves = json.load(sys.stdin)
for w in waves:
    print(f'波次 {w[\"wave_id\"]}: 状态={w[\"status\"]}')
"

    print_success "超时波次的库存已释放，可以重新分配给其他门店"
fi

read -p $'\n按回车键继续...' -n1 -s

print_header "第10步：查看完整重排历史"

print_step "所有重排记录"
curl -s "$BASE_URL/rearrangements" | python3 -c "
import sys, json
records = json.load(sys.stdin)
print(f'共 {len(records)} 次重排记录:')
print()
for i, r in enumerate(records, 1):
    print(f'{i}. [{r[\"timestamp\"]}] {r[\"trigger\"]}')
    print(f'   总结: {r[\"reason_summary\"]}')
    if r['store_changes']:
        print(f'   门店变动:')
        for sc in r['store_changes']:
            print(f'     - {sc[\"store_id\"]}: {sc[\"change_type\"]}')
            print(f'       原因: {sc[\"reason\"]}')
    print()
"

print_header "演示完成！"

echo ""
echo -e "${GREEN}演示已完成，您可以通过以下方式继续探索：${NC}"
echo ""
echo "  API文档:  http://localhost:8000/docs"
echo "  系统状态:  http://localhost:8000/status"
echo "  演示概览:  http://localhost:8000/demo"
echo ""
echo "  核心API:"
echo "    GET  /stores             - 门店列表"
echo "    GET  /products           - 商品列表"
echo "    GET  /inventory          - 库存状态"
echo "    GET  /requests           - 需求列表"
echo "    POST /requests           - 提交新需求"
echo "    GET  /waves              - 波次列表"
echo "    POST /waves/generate     - 生成波次"
echo "    POST /waves/{id}/submit-confirm  - 提交待确认"
echo "    POST /waves/{id}/confirm - 确认波次"
echo "    PUT  /requests/{id}/quantity - 修改需求数量"
echo "    GET  /rearrangements     - 重排历史"
echo "    GET  /rearrangements/compare/{id} - 重排前后对比"
echo ""
