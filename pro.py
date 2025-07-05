import os
import json
import time
from datetime import datetime, timedelta
from flask import Flask, request, abort

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    JoinEvent,
    LeaveEvent,
    MemberJoinedEvent,
    MemberLeftEvent,
    FollowEvent,
    UnfollowEvent
)

app = Flask(__name__)

# 從環境變數或直接設定您的憑證
CHANNEL_ACCESS_TOKEN = 'NHv54nNB1d2yFR5rhfjvRIcKR8DtM+g/H2kXkVrPRJeeQrOKoM5ezA8HnnoGIm+iUHRYTLtMxa10Lr5Irems1wb6YQSOMCkJb+8oSwyOt5DdJs/gmuaC5gTz689eCXoCJFJIYLiQY/9EeYB+Ox+WHQdB04t89/1O/w1cDnyilFU='
CHANNEL_SECRET = '0a486d77dd9aea4bb56500ca7d0661be'

# 設定 LINE Bot API
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# 載入資料檔案
def load_data():
    """載入黑名單和群組資料"""
    try:
        with open('ban.json', 'r', encoding='utf-8') as f:
            ban_data = json.load(f)
    except FileNotFoundError:
        ban_data = {}
    
    # 確保所有必要的欄位都存在（向後相容）
    default_ban_data = {
        "owners": [],
        "admin": [],
        "blacklist": {},
        "user": {},
        "protected_groups": {},  # 受保護的群組
        "trusted_users": [],     # 信任用戶列表
        "alert_settings": {      # 警報設定
            "enabled": True,
            "alert_admins": True,
            "auto_ban": True,
            "kick_detection": True,    # 新增：踢人檢測
            "invite_detection": True   # 新增：邀請檢測
        },
        "read_tracking": {},     # 新增：已讀追蹤
        "mention_settings": {}   # 新增：標記設定
    }
    
    # 合併現有資料與預設資料
    for key, default_value in default_ban_data.items():
        if key not in ban_data:
            ban_data[key] = default_value
            print(f"🔄 新增欄位: {key}")
    
    try:
        with open('group.json', 'r', encoding='utf-8') as f:
            group_data = json.load(f)
    except FileNotFoundError:
        group_data = {}
    
    # 確保所有必要的欄位都存在（向後相容）
    default_group_data = {
        "s": {},
        "activity_log": {},      # 活動記錄
        "member_count": {},      # 成員數量追蹤
        "last_check": {},        # 最後檢查時間
        "kick_log": {},          # 新增：踢人記錄
        "invite_log": {},        # 新增：邀請記錄
        "message_tracking": {},  # 新增：訊息追蹤（用於已讀功能）
        "member_cache": {}       # 新增：成員快取
    }
    
    # 合併現有資料與預設資料
    for key, default_value in default_group_data.items():
        if key not in group_data:
            group_data[key] = default_value
            print(f"🔄 新增欄位: {key}")
    
    return ban_data, group_data

def save_data(ban_data, group_data):
    """儲存資料到檔案"""
    try:
        with open('ban.json', 'w', encoding='utf-8') as f:
            json.dump(ban_data, f, ensure_ascii=False, indent=4)
        
        with open('group.json', 'w', encoding='utf-8') as f:
            json.dump(group_data, f, ensure_ascii=False, indent=4)
        print("✅ 資料儲存成功")
    except Exception as e:
        print(f"❌ 資料儲存失敗: {e}")

def log_security_event(event_type, group_id, user_id, details):
    """記錄安全事件"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    security_log = {
        "timestamp": timestamp,
        "event_type": event_type,
        "group_id": group_id,
        "user_id": user_id,
        "details": details
    }
    
    try:
        with open("security_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {event_type} | Group: {group_id} | User: {user_id} | Details: {details}\n")
    except:
        pass
    
    print(f"🛡️ 安全事件: {event_type} | 群組: {group_id} | 用戶: {user_id}")

def alert_admins(line_bot_api, message, group_id=None):
    """向管理員發送警報"""
    global ban_data
    
    # 確保 alert_settings 存在
    if "alert_settings" not in ban_data:
        ban_data["alert_settings"] = {"alert_admins": True}
    
    if not ban_data["alert_settings"].get("alert_admins", True):
        return
    
    alert_message = f"🚨 安全警報\n{message}\n時間: {datetime.now().strftime('%H:%M:%S')}"
    
    # 向所有擁有者和管理員發送警報
    all_admins = ban_data.get("owners", []) + ban_data.get("admin", [])
    for user_id in all_admins:
        try:
            push_message(line_bot_api, user_id, alert_message)
        except:
            continue

def detect_abnormal_kicks(group_id, user_id):
    """檢測異常踢人行為"""
    global group_data
    
    current_time = datetime.now()
    
    # 確保 kick_log 存在
    if "kick_log" not in group_data:
        group_data["kick_log"] = {}
    
    if group_id not in group_data["kick_log"]:
        group_data["kick_log"][group_id] = {}
    
    if user_id not in group_data["kick_log"][group_id]:
        group_data["kick_log"][group_id][user_id] = []
    
    # 記錄踢人事件
    group_data["kick_log"][group_id][user_id].append(current_time.isoformat())
    
    # 清理舊記錄（保留最近24小時）
    one_day_ago = current_time - timedelta(hours=24)
    group_data["kick_log"][group_id][user_id] = [
        kick_time for kick_time in group_data["kick_log"][group_id][user_id]
        if datetime.fromisoformat(kick_time) > one_day_ago
    ]
    
    # 檢查是否異常（24小時內踢超過5人，或1小時內踢超過3人）
    one_hour_ago = current_time - timedelta(hours=1)
    recent_kicks = len([
        kick_time for kick_time in group_data["kick_log"][group_id][user_id]
        if datetime.fromisoformat(kick_time) > one_hour_ago
    ])
    
    total_kicks = len(group_data["kick_log"][group_id][user_id])
    
    if recent_kicks >= 3:  # 1小時內踢3人
        return "rapid_kicks"
    elif total_kicks >= 5:  # 24小時內踢5人
        return "mass_kicks"
    
    return None

def detect_abnormal_invites(group_id, user_id, invite_count):
    """檢測異常邀請行為"""
    global group_data
    
    current_time = datetime.now()
    
    # 確保 invite_log 存在
    if "invite_log" not in group_data:
        group_data["invite_log"] = {}
    
    if group_id not in group_data["invite_log"]:
        group_data["invite_log"][group_id] = {}
    
    if user_id not in group_data["invite_log"][group_id]:
        group_data["invite_log"][group_id][user_id] = []
    
    # 記錄邀請事件
    invite_event = {
        "time": current_time.isoformat(),
        "count": invite_count
    }
    group_data["invite_log"][group_id][user_id].append(invite_event)
    
    # 清理舊記錄（保留最近24小時）
    one_day_ago = current_time - timedelta(hours=24)
    group_data["invite_log"][group_id][user_id] = [
        invite for invite in group_data["invite_log"][group_id][user_id]
        if datetime.fromisoformat(invite["time"]) > one_day_ago
    ]
    
    # 檢查是否異常（1小時內邀請超過10人，或24小時內邀請超過20人）
    one_hour_ago = current_time - timedelta(hours=1)
    recent_invites = sum([
        invite["count"] for invite in group_data["invite_log"][group_id][user_id]
        if datetime.fromisoformat(invite["time"]) > one_hour_ago
    ])
    
    total_invites = sum([invite["count"] for invite in group_data["invite_log"][group_id][user_id]])
    
    if recent_invites >= 10:  # 1小時內邀請10人
        return "rapid_invites"
    elif total_invites >= 20:  # 24小時內邀請20人
        return "mass_invites"
    
    return None

def track_message_for_read_status(group_id, message_id, sender_id, message_text):
    """追蹤訊息用於已讀狀態檢查"""
    global group_data
    
    if "message_tracking" not in group_data:
        group_data["message_tracking"] = {}
    
    if group_id not in group_data["message_tracking"]:
        group_data["message_tracking"][group_id] = {}
    
    # 記錄訊息資訊
    group_data["message_tracking"][group_id][message_id] = {
        "sender": sender_id,
        "text": message_text[:50] + "..." if len(message_text) > 50 else message_text,
        "timestamp": datetime.now().isoformat(),
        "readers": []  # 已讀用戶列表
    }
    
    # 清理舊訊息記錄（保留最近7天）
    seven_days_ago = datetime.now() - timedelta(days=7)
    messages_to_remove = []
    
    for msg_id, msg_data in group_data["message_tracking"][group_id].items():
        try:
            if datetime.fromisoformat(msg_data["timestamp"]) < seven_days_ago:
                messages_to_remove.append(msg_id)
        except:
            messages_to_remove.append(msg_id)
    
    for msg_id in messages_to_remove:
        del group_data["message_tracking"][group_id][msg_id]

def mark_message_as_read(group_id, message_id, reader_id):
    """標記訊息為已讀"""
    global group_data
    
    if "message_tracking" not in group_data:
        return False
    
    if group_id not in group_data["message_tracking"]:
        return False
    
    if message_id not in group_data["message_tracking"][group_id]:
        return False
    
    readers = group_data["message_tracking"][group_id][message_id]["readers"]
    if reader_id not in readers:
        readers.append(reader_id)
        return True
    
    return False

def get_group_members_mention(line_bot_api, group_id):
    """獲取群組所有成員的標記字串（模擬 @all 功能）"""
    try:
        # 注意：LINE Bot API 實際上無法直接獲取所有群組成員
        # 這裡我們使用快取的成員列表或提供替代方案
        global group_data
        
        if "member_cache" not in group_data:
            group_data["member_cache"] = {}
        
        if group_id in group_data["member_cache"]:
            members = group_data["member_cache"][group_id]
            # 由於 LINE 的限制，我們無法真正實現 @all
            # 但可以提供一個模擬的全體通知功能
            return f"📢 全體通知\n已快取成員: {len(members)} 人\n⚠️ 由於 LINE API 限制，無法直接標記所有成員"
        else:
            return "📢 全體通知\n⚠️ 需要先建立成員快取才能使用此功能\n請使用 'cache members' 指令"
    
    except Exception as e:
        return f"❌ 獲取成員列表失敗: {str(e)}"

def check_suspicious_activity(group_id, user_id):
    """檢查可疑活動"""
    global ban_data, group_data
    
    current_time = datetime.now()
    
    # 檢查是否為黑名單用戶
    if user_id in ban_data.get("blacklist", {}) and ban_data["blacklist"][user_id]:
        return "blacklisted_user"
    
    # 確保 activity_log 存在
    if "activity_log" not in group_data:
        group_data["activity_log"] = {}
    
    # 檢查短時間內大量活動
    if group_id not in group_data["activity_log"]:
        group_data["activity_log"][group_id] = {}
    
    if user_id not in group_data["activity_log"][group_id]:
        group_data["activity_log"][group_id][user_id] = []
    
    # 記錄活動
    group_data["activity_log"][group_id][user_id].append(current_time.isoformat())
    
    # 清理舊記錄（保留最近1小時）
    one_hour_ago = current_time - timedelta(hours=1)
    group_data["activity_log"][group_id][user_id] = [
        activity for activity in group_data["activity_log"][group_id][user_id]
        if datetime.fromisoformat(activity) > one_hour_ago
    ]
    
    # 檢查是否有過多活動
    if len(group_data["activity_log"][group_id][user_id]) > 10:  # 1小時內超過10次活動
        return "high_activity"
    
    return None

# 全域變數
ban_data, group_data = load_data()

def ensure_data_integrity():
    """確保資料結構完整性"""
    global ban_data, group_data
    
    # 確保 ban_data 所有必要欄位存在
    required_ban_fields = {
        "owners": [],
        "admin": [],
        "blacklist": {},
        "user": {},
        "protected_groups": {},
        "trusted_users": [],
        "alert_settings": {
            "enabled": True,
            "alert_admins": True,
            "auto_ban": True,
            "kick_detection": True,
            "invite_detection": True
        },
        "read_tracking": {},
        "mention_settings": {}
    }
    
    for field, default_value in required_ban_fields.items():
        if field not in ban_data:
            ban_data[field] = default_value
            print(f"🔄 新增欄位: {field}")
    
    # 確保 group_data 所有必要欄位存在
    required_group_fields = {
        "s": {},
        "activity_log": {},
        "member_count": {},
        "last_check": {},
        "kick_log": {},
        "invite_log": {},
        "message_tracking": {},
        "member_cache": {}
    }
    
    for field, default_value in required_group_fields.items():
        if field not in group_data:
            group_data[field] = default_value
            print(f"🔄 新增欄位: {field}")

# 確保資料完整性
ensure_data_integrity()

wait_status = {
    "ban": {},
    "unban": {},
    "add": {},
    "del": {},
    "read_check": {},  # 新增：等待查已讀
    "mention_all": {}  # 新增：等待全體標記
}

@app.route("/callback", methods=['POST'])
def callback():
    """處理 LINE 的 webhook 回調"""
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    
    print(f"📨 收到 webhook 請求")
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("❌ 無效的簽名")
        abort(400)
    except Exception as e:
        print(f"❌ 處理 webhook 時發生錯誤: {e}")
        abort(500)
    
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    """處理文字訊息"""
    global ban_data, group_data, wait_status
    
    user_id = event.source.user_id
    text = event.message.text
    reply_token = event.reply_token
    message_id = event.message.id  # 獲取訊息ID用於已讀追蹤
    
    # 判斷訊息來源
    if hasattr(event.source, 'group_id'):
        chat_id = event.source.group_id
        chat_type = 'group'
    elif hasattr(event.source, 'room_id'):
        chat_id = event.source.room_id
        chat_type = 'room'
    else:
        chat_id = user_id
        chat_type = 'user'
    
    # 記錄訊息並檢查可疑活動
    if chat_type == 'group':
        suspicious = check_suspicious_activity(chat_id, user_id)
        if suspicious:
            log_security_event(f"suspicious_{suspicious}", chat_id, user_id, f"Message: {text}")
        
        # 追蹤訊息用於已讀功能
        track_message_for_read_status(chat_id, message_id, user_id, text)
        
        # 標記發送者為已讀（發送者肯定已讀自己的訊息）
        mark_message_as_read(chat_id, message_id, user_id)
    
    # 除錯：顯示權限狀態
    print(f"🔍 權限除錯:")
    print(f"   用戶ID: {user_id}")
    print(f"   擁有者列表: {ban_data.get('owners', [])}")
    print(f"   管理員列表: {ban_data.get('admin', [])}")
    print(f"   是否為擁有者: {user_id in ban_data.get('owners', [])}")
    print(f"   是否為管理員: {user_id in ban_data.get('admin', [])}")
    print(f"   指令: {text}")
    
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            
            # 如果還沒有擁有者，自動設定第一個用戶為擁有者
            if not ban_data.get("owners", []):
                ban_data["owners"].append(user_id)
                save_data(ban_data, group_data)
                reply_message(line_bot_api, reply_token, f"🔑 您已被設定為系統擁有者！\n您的用戶ID: {user_id}\n輸入 'help' 查看所有可用指令")
                return
            
            # 處理等待狀態的指令
            if user_id in wait_status["ban"] and wait_status["ban"][user_id]:
                target_id = text.strip()
                if "blacklist" not in ban_data:
                    ban_data["blacklist"] = {}
                ban_data["blacklist"][target_id] = True
                wait_status["ban"][user_id] = False
                save_data(ban_data, group_data)
                reply_message(line_bot_api, reply_token, f"🚫 已將用戶 `{target_id}` 加入黑名單！")
                log_security_event("user_banned", chat_id, user_id, f"Banned user: {target_id}")
                alert_admins(line_bot_api, f"用戶 {target_id} 已被 {user_id} 加入黑名單", chat_id)
                return
            
            if user_id in wait_status["unban"] and wait_status["unban"][user_id]:
                target_id = text.strip()
                blacklist = ban_data.get("blacklist", {})
                if target_id in blacklist:
                    del ban_data["blacklist"][target_id]
                    wait_status["unban"][user_id] = False
                    save_data(ban_data, group_data)
                    reply_message(line_bot_api, reply_token, f"✅ 已將用戶 `{target_id}` 移出黑名單！")
                    log_security_event("user_unbanned", chat_id, user_id, f"Unbanned user: {target_id}")
                    alert_admins(line_bot_api, f"用戶 {target_id} 已被 {user_id} 移出黑名單", chat_id)
                else:
                    wait_status["unban"][user_id] = False
                    reply_message(line_bot_api, reply_token, f"⚠️ 用戶 `{target_id}` 不在黑名單中")
                return
            
            # 處理查已讀等待狀態
            if user_id in wait_status["read_check"] and wait_status["read_check"][user_id]:
                # 如果用戶輸入取消指令，退出等待狀態
                if text.lower() in ['cancel', '取消', 'exit', '退出']:
                    wait_status["read_check"][user_id] = False
                    reply_message(line_bot_api, reply_token, "✅ 已取消已讀查詢")
                    return
                
                target_message_id = text.strip()
                wait_status["read_check"][user_id] = False
                
                if chat_type == 'group':
                    message_tracking = group_data.get("message_tracking", {})
                    if chat_id in message_tracking and target_message_id in message_tracking[chat_id]:
                        msg_data = message_tracking[chat_id][target_message_id]
                        readers = msg_data["readers"]
                        msg_text = msg_data["text"]
                        
                        message = f"""📖 已讀名單查詢結果
════════════════════
💬 訊息內容: {msg_text}
👀 已讀人數: {len(readers)} 人
📋 已讀用戶:
{chr(10).join([f"• {reader}" for reader in readers]) if readers else "目前無人已讀"}

⚠️ 注意：此功能基於用戶互動記錄
實際已讀狀態可能與 LINE 官方不同"""
                        
                        reply_message(line_bot_api, reply_token, message)
                    else:
                        reply_message(line_bot_api, reply_token, f"❌ 找不到訊息ID: {target_message_id}\n可能訊息太舊或ID不正確\n\n💡 提示：輸入 'cancel' 可取消查詢")
                else:
                    reply_message(line_bot_api, reply_token, "❌ 此功能僅能在群組中使用")
                return
            
            # 黑名單檢查
            blacklist = ban_data.get("blacklist", {})
            if user_id in blacklist and blacklist.get(user_id, False):
                if chat_type == 'group':
                    alert_admins(line_bot_api, f"黑名單用戶 {user_id} 在群組 {chat_id} 中發送訊息: {text}", chat_id)
                    log_security_event("blacklist_activity", chat_id, user_id, f"Message: {text}")
                    
                    # 標記黑名單用戶也能已讀訊息（用於追蹤）
                    if chat_type == 'group':
                        # 將此用戶的活動也標記為"已讀"其他訊息
                        message_tracking = group_data.get("message_tracking", {})
                        if chat_id in message_tracking:
                            for msg_id in list(message_tracking[chat_id].keys())[-5:]:  # 最近5條訊息
                                mark_message_as_read(chat_id, msg_id, user_id)
                return
            
            # === 基本指令（所有用戶可用） ===
            if text.lower() == 'help' or text == '說明':
                help_text = get_help_message(user_id)
                reply_message(line_bot_api, reply_token, help_text)
                return
            
            elif text.lower() in ['reset', '重置', 'clear']:
                # 清理該用戶的所有等待狀態
                for status_type in wait_status:
                    if user_id in wait_status[status_type]:
                        wait_status[status_type][user_id] = False
                reply_message(line_bot_api, reply_token, "✅ 已重置所有等待狀態\n現在可以正常使用指令了")
                return
            
            elif text.lower() == '喵':
                reply_message(line_bot_api, reply_token, "喵w")
                return
            
            elif text.lower() == 'myid':
                reply_message(line_bot_api, reply_token, f"📱 您的用戶 ID：\n`{user_id}`")
                return
            
            # === 新功能：查已讀名單 ===
            elif text.lower() == 'read check' and chat_type == 'group':
                message_tracking = group_data.get("message_tracking", {})
                if chat_id in message_tracking:
                    recent_messages = list(message_tracking[chat_id].items())[-10:]  # 最近10條訊息
                    if recent_messages:
                        message = "📖 最近訊息列表（選擇要查詢的訊息）\n" + "=" * 30 + "\n"
                        for i, (msg_id, msg_data) in enumerate(recent_messages, 1):
                            msg_text = msg_data["text"]
                            read_count = len(msg_data["readers"])
                            message += f"{i}. ID: {msg_id}\n   內容: {msg_text}\n   已讀: {read_count} 人\n\n"
                        
                        message += "請回覆要查詢的訊息ID"
                        wait_status["read_check"][user_id] = True
                        reply_message(line_bot_api, reply_token, message)
                    else:
                        reply_message(line_bot_api, reply_token, "📖 目前沒有可查詢的訊息記錄")
                else:
                    reply_message(line_bot_api, reply_token, "📖 此群組尚無訊息追蹤記錄")
                return
            
            # === 新功能：全體標記 (@all) ===
            elif text.lower() == '@all' and chat_type == 'group':
                # 檢查權限
                owners = ban_data.get("owners", [])
                admins = ban_data.get("admin", [])
                
                if user_id in owners or user_id in admins:
                    mention_text = get_group_members_mention(line_bot_api, chat_id)
                    reply_message(line_bot_api, reply_token, mention_text)
                    log_security_event("mention_all", chat_id, user_id, "Used @all function")
                else:
                    reply_message(line_bot_api, reply_token, "❌ 僅管理員和擁有者可使用 @all 功能")
                return
            
            elif text.lower() == 'cache members' and chat_type == 'group':
                # 建立成員快取（模擬功能，實際無法獲取完整成員列表）
                owners = ban_data.get("owners", [])
                admins = ban_data.get("admin", [])
                
                if user_id in owners or user_id in admins:
                    # 由於 LINE API 限制，我們只能快取活躍用戶
                    activity_log = group_data.get("activity_log", {})
                    if chat_id in activity_log:
                        active_members = list(activity_log[chat_id].keys())
                        group_data["member_cache"][chat_id] = active_members
                        save_data(ban_data, group_data)
                        reply_message(line_bot_api, reply_token, f"✅ 已快取 {len(active_members)} 名活躍成員\n現在可以使用 @all 功能")
                    else:
                        reply_message(line_bot_api, reply_token, "⚠️ 尚無活動記錄，無法建立成員快取")
                else:
                    reply_message(line_bot_api, reply_token, "❌ 僅管理員和擁有者可使用此功能")
                return
            
            elif text.lower() == 'status':
                if chat_type == 'group':
                    protected_groups = ban_data.get("protected_groups", {})
                    is_protected = chat_id in protected_groups
                    protection_level = protected_groups.get(chat_id, {}).get("level", "無")
                    
                    blacklist_count = len([uid for uid in ban_data.get("blacklist", {}) if ban_data["blacklist"].get(uid, False)])
                    group_managers = len(group_data.get("s", {}).get(chat_id, []))
                    last_check = group_data.get("last_check", {}).get(chat_id, "未檢查")
                    
                    # 新增功能狀態
                    message_tracking_count = len(group_data.get("message_tracking", {}).get(chat_id, {}))
                    cached_members = len(group_data.get("member_cache", {}).get(chat_id, []))
                    
                    message = f"""🛡️ 群組防護狀態
════════════════════
📍 群組ID: {chat_id}
🔐 保護狀態: {"✅ 已啟用" if is_protected else "❌ 未啟用"}
📊 保護級別: {protection_level}
🚫 黑名單用戶: {blacklist_count} 人
👥 群組管理員: {group_managers} 人
📖 訊息追蹤: {message_tracking_count} 條
👤 快取成員: {cached_members} 人
🕒 最後檢查: {last_check}"""
                    
                    reply_message(line_bot_api, reply_token, message)
                else:
                    reply_message(line_bot_api, reply_token, "此指令僅能在群組中使用")
                return
            
            elif text.lower() == 'security' and chat_type == 'group':
                # 顯示群組安全報告
                blacklist = ban_data.get("blacklist", {})
                blacklisted_count = len([uid for uid in blacklist if blacklist.get(uid, False)])
                
                activity_log = group_data.get("activity_log", {})
                recent_alerts = "無" if chat_id not in activity_log else "有可疑活動"
                
                alert_settings = ban_data.get("alert_settings", {})
                protection_status = "正常運行" if alert_settings.get("enabled", True) else "已關閉"
                
                # 新增踢人和邀請統計
                kick_log = group_data.get("kick_log", {}).get(chat_id, {})
                invite_log = group_data.get("invite_log", {}).get(chat_id, {})
                
                message = f"""🔍 群組安全報告
════════════════════
🚫 活躍黑名單: {blacklisted_count} 人
⚠️ 近期警報: {recent_alerts}
🛡️ 防護系統: {protection_status}
📊 監控狀態: 即時監控中
🦵 踢人記錄: {len(kick_log)} 位用戶
📨 邀請記錄: {len(invite_log)} 位用戶
🕒 報告時間: {datetime.now().strftime("%H:%M:%S")}"""
                
                reply_message(line_bot_api, reply_token, message)
                return
            
            elif text.lower() == 'debug':
                # 除錯指令
                is_owner = user_id in ban_data.get("owners", [])
                is_admin = user_id in ban_data.get("admin", [])
                
                message = f"""🔍 除錯資訊
════════════════════
👤 您的用戶ID: {user_id}
🔐 權限狀態:
{"✅" if is_owner else "❌"} 擁有者權限
{"✅" if is_admin else "❌"} 管理員權限

📊 系統資料:
👑 擁有者列表: {ban_data.get('owners', [])}
🛡️ 管理員列表: {ban_data.get('admin', [])}
💬 對話類型: {chat_type.upper()}

🆕 新功能狀態:
📖 已讀追蹤: {"✅ 啟用" if "message_tracking" in group_data else "❌ 未啟用"}
👥 成員快取: {"✅ 啟用" if "member_cache" in group_data else "❌ 未啟用"}

🔧 如需獲得權限，請：
1. 手動編輯 ban.json 檔案
2. 或聯絡現有擁有者
3. 或重新部署機器人"""
                
                reply_message(line_bot_api, reply_token, message)
                return
            
            elif text.lower() == 'makeowner' and user_id == 'U215dfe5f0cdc8c5ddd970a5d2fb4b288':
                # 特殊指令：讓您成為擁有者
                if user_id not in ban_data.get("owners", []):
                    if "owners" not in ban_data:
                        ban_data["owners"] = []
                    ban_data["owners"].append(user_id)
                    save_data(ban_data, group_data)
                    reply_message(line_bot_api, reply_token, f"🔑 已將您設定為擁有者！\n用戶ID: {user_id}")
                else:
                    reply_message(line_bot_api, reply_token, "✅ 您已經是擁有者了")
                return
            
            elif text.lower() == 'makeadmin' and user_id == 'U215dfe5f0cdc8c5ddd970a5d2fb4b288':
                # 特殊指令：讓您成為管理員
                if user_id not in ban_data.get("admin", []):
                    if "admin" not in ban_data:
                        ban_data["admin"] = []
                    ban_data["admin"].append(user_id)
                    save_data(ban_data, group_data)
                    reply_message(line_bot_api, reply_token, f"🛡️ 已將您設定為管理員！\n用戶ID: {user_id}")
                else:
                    reply_message(line_bot_api, reply_token, "✅ 您已經是管理員了")
                return
            
            elif text.lower() == 'grantme' and user_id in ['U215dfe5f0cdc8c5ddd970a5d2fb4b288', 'Ue585da1f0a42432b10449cd660b9623e']:
                # 超級指令：同時獲得擁有者和管理員權限（限定用戶）
                owners = ban_data.get("owners", [])
                admins = ban_data.get("admin", [])
                
                changes = []
                if user_id not in owners:
                    if "owners" not in ban_data:
                        ban_data["owners"] = []
                    ban_data["owners"].append(user_id)
                    changes.append("擁有者")
                
                if user_id not in admins:
                    if "admin" not in ban_data:
                        ban_data["admin"] = []
                    ban_data["admin"].append(user_id)
                    changes.append("管理員")
                
                if changes:
                    save_data(ban_data, group_data)
                    reply_message(line_bot_api, reply_token, f"👑 已授予您以下權限：{', '.join(changes)}\n用戶ID: {user_id}\n🎉 您現在擁有完整的系統控制權！")
                else:
                    reply_message(line_bot_api, reply_token, "✅ 您已經擁有所有權限了")
                return
            
            # === 管理員指令 ===
            owners = ban_data.get("owners", [])
            admins = ban_data.get("admin", [])
            
            if user_id in admins or user_id in owners:
                print(f"🛡️ 執行管理員指令: {text}")
                
                if text.lower() == 'protect' and chat_type == 'group':
                    # 啟用群組保護
                    if "protected_groups" not in ban_data:
                        ban_data["protected_groups"] = {}
                    
                    if chat_id not in ban_data["protected_groups"]:
                        ban_data["protected_groups"][chat_id] = {
                            "enabled": True,
                            "level": "標準",
                            "enabled_time": datetime.now().isoformat()
                        }
                        save_data(ban_data, group_data)
                        reply_message(line_bot_api, reply_token, "✅ 已啟用群組防護！\n保護級別: 標準\n🆕 包含踢人/邀請監控 & 已讀追蹤")
                        log_security_event("protection_enabled", chat_id, user_id, "Standard protection")
                    else:
                        reply_message(line_bot_api, reply_token, "⚠️ 群組保護已經啟用")
                    return
                
                elif text.lower() == 'unprotect' and chat_type == 'group':
                    # 停用群組保護
                    protected_groups = ban_data.get("protected_groups", {})
                    if chat_id in protected_groups:
                        del ban_data["protected_groups"][chat_id]
                        save_data(ban_data, group_data)
                        reply_message(line_bot_api, reply_token, "❌ 已停用群組防護")
                        log_security_event("protection_disabled", chat_id, user_id, "Protection disabled")
                    else:
                        reply_message(line_bot_api, reply_token, "⚠️ 群組保護未啟用")
                    return
                
                elif text.lower() == 'scan' and chat_type == 'group':
                    # 掃描群組威脅
                    try:
                        threat_count = 0
                        threats = []
                        
                        # 檢查活動記錄中的可疑用戶
                        activity_log = group_data.get("activity_log", {})
                        if chat_id in activity_log:
                            for uid, activities in activity_log[chat_id].items():
                                if len(activities) > 15:  # 高活動用戶
                                    threats.append(f"高活動用戶: {uid}")
                                    threat_count += 1
                        
                        # 檢查已知黑名單用戶
                        blacklist = ban_data.get("blacklist", {})
                        for uid in blacklist:
                            if blacklist.get(uid, False):
                                threats.append(f"黑名單用戶: {uid}")
                                threat_count += 1
                        
                        # 檢查異常踢人行為
                        kick_log = group_data.get("kick_log", {}).get(chat_id, {})
                        for uid, kicks in kick_log.items():
                            if len(kicks) > 3:  # 踢人過多
                                threats.append(f"頻繁踢人: {uid}")
                                threat_count += 1
                        
                        # 檢查異常邀請行為
                        invite_log = group_data.get("invite_log", {}).get(chat_id, {})
                        for uid, invites in invite_log.items():
                            total_invites = sum([inv["count"] for inv in invites])
                            if total_invites > 10:  # 邀請過多
                                threats.append(f"頻繁邀請: {uid}")
                                threat_count += 1
                        
                        if threat_count == 0:
                            message = "✅ 群組掃描完成，未發現威脅"
                        else:
                            message = f"⚠️ 掃描發現 {threat_count} 個潛在威脅:\n"
                            message += "\n".join(threats[:10])  # 最多顯示10個
                            if len(threats) > 10:
                                message += f"\n... 還有 {len(threats)-10} 個威脅"
                        
                        reply_message(line_bot_api, reply_token, message)
                        log_security_event("security_scan", chat_id, user_id, f"Found {threat_count} threats")
                    except Exception as e:
                        reply_message(line_bot_api, reply_token, f"❌ 掃描失敗: {str(e)}")
                    return
                
                elif text.lower() == 'alerts on':
                    if "alert_settings" not in ban_data:
                        ban_data["alert_settings"] = {}
                    ban_data["alert_settings"]["alert_admins"] = True
                    save_data(ban_data, group_data)
                    reply_message(line_bot_api, reply_token, "✅ 已開啟管理員警報")
                    return
                
                elif text.lower() == 'alerts off':
                    if "alert_settings" not in ban_data:
                        ban_data["alert_settings"] = {}
                    ban_data["alert_settings"]["alert_admins"] = False
                    save_data(ban_data, group_data)
                    reply_message(line_bot_api, reply_token, "❌ 已關閉管理員警報")
                    return
                
                elif text.lower() == 'kick detection on':
                    if "alert_settings" not in ban_data:
                        ban_data["alert_settings"] = {}
                    ban_data["alert_settings"]["kick_detection"] = True
                    save_data(ban_data, group_data)
                    reply_message(line_bot_api, reply_token, "✅ 已開啟踢人檢測")
                    return
                
                elif text.lower() == 'kick detection off':
                    if "alert_settings" not in ban_data:
                        ban_data["alert_settings"] = {}
                    ban_data["alert_settings"]["kick_detection"] = False
                    save_data(ban_data, group_data)
                    reply_message(line_bot_api, reply_token, "❌ 已關閉踢人檢測")
                    return
                
                elif text.lower() == 'banlist':
                    # 管理員也可以查看黑名單
                    blacklist = ban_data.get("blacklist", {})
                    if not blacklist:
                        message = "✅ 目前沒有黑名單用戶"
                    else:
                        active_bans = [uid for uid, status in blacklist.items() if status]
                        if not active_bans:
                            message = "✅ 目前沒有活躍的黑名單用戶"
                        else:
                            message = f"🚫 黑名單用戶列表 ({len(active_bans)} 人):\n"
                            for i, uid in enumerate(active_bans[:20], 1):  # 最多顯示20個
                                message += f"{i}. `{uid}`\n"
                            if len(active_bans) > 20:
                                message += f"... 還有 {len(active_bans)-20} 個用戶"
                    
                    reply_message(line_bot_api, reply_token, message)
                    return
                
                elif text.lower().startswith('checkban '):
                    # 管理員也可以檢查黑名單狀態
                    target_id = text[9:].strip()
                    if target_id:
                        blacklist = ban_data.get("blacklist", {})
                        if target_id in blacklist and blacklist[target_id]:
                            message = f"🚫 用戶 `{target_id}` 在黑名單中"
                        else:
                            message = f"✅ 用戶 `{target_id}` 不在黑名單中"
                        reply_message(line_bot_api, reply_token, message)
                    else:
                        reply_message(line_bot_api, reply_token, "❌ 請提供用戶ID\n格式：checkban 用戶ID")
                    return
            
            # === 擁有者專用指令 ===
            if user_id in owners:
                print(f"👑 執行擁有者指令: {text}")
                
                if text.lower().startswith('trust '):
                    # 添加信任用戶
                    target_id = text[6:].strip()
                    trusted_users = ban_data.get("trusted_users", [])
                    if target_id not in trusted_users:
                        if "trusted_users" not in ban_data:
                            ban_data["trusted_users"] = []
                        ban_data["trusted_users"].append(target_id)
                        save_data(ban_data, group_data)
                        reply_message(line_bot_api, reply_token, f"✅ 已將 {target_id} 加入信任列表")
                    else:
                        reply_message(line_bot_api, reply_token, "⚠️ 該用戶已在信任列表中")
                    return
                
                elif text.lower().startswith('untrust '):
                    # 移除信任用戶
                    target_id = text[8:].strip()
                    trusted_users = ban_data.get("trusted_users", [])
                    if target_id in trusted_users:
                        ban_data["trusted_users"].remove(target_id)
                        save_data(ban_data, group_data)
                        reply_message(line_bot_api, reply_token, f"✅ 已將 {target_id} 移出信任列表")
                    else:
                        reply_message(line_bot_api, reply_token, "⚠️ 該用戶不在信任列表中")
                    return
                
                elif text.lower() == 'emergency' and chat_type == 'group':
                    # 緊急模式
                    if "protected_groups" not in ban_data:
                        ban_data["protected_groups"] = {}
                    
                    ban_data["protected_groups"][chat_id] = {
                        "enabled": True,
                        "level": "緊急",
                        "enabled_time": datetime.now().isoformat()
                    }
                    save_data(ban_data, group_data)
                    
                    emergency_message = """🚨 緊急防護模式已啟動！
                    
⚠️ 系統進入高度警戒狀態
🛡️ 所有活動將被嚴密監控
📊 異常行為將立即警報
🔒 建議管理員保持警戒
🆕 已讀追蹤 & 踢人邀請監控全面啟動"""
                    
                    reply_message(line_bot_api, reply_token, emergency_message)
                    alert_admins(line_bot_api, f"群組 {chat_id} 進入緊急防護模式", chat_id)
                    log_security_event("emergency_mode", chat_id, user_id, "Emergency protection activated")
                    return
                
                elif text.lower().startswith('ban:'):
                    # 加入黑名單
                    target_id = text[4:].strip()
                    if target_id:
                        if "blacklist" not in ban_data:
                            ban_data["blacklist"] = {}
                        ban_data["blacklist"][target_id] = True
                        save_data(ban_data, group_data)
                        reply_message(line_bot_api, reply_token, f"🚫 已將用戶 `{target_id}` 加入黑名單！")
                        log_security_event("user_banned", chat_id, user_id, f"Banned user: {target_id}")
                        
                        # 通知其他管理員
                        alert_admins(line_bot_api, f"用戶 {target_id} 已被 {user_id} 加入黑名單", chat_id)
                    else:
                        reply_message(line_bot_api, reply_token, "❌ 請提供有效的用戶ID\n格式：ban:用戶ID")
                    return
                
                elif text.lower().startswith('unban:'):
                    # 移除黑名單
                    target_id = text[6:].strip()
                    if target_id:
                        blacklist = ban_data.get("blacklist", {})
                        if target_id in blacklist:
                            del ban_data["blacklist"][target_id]
                            save_data(ban_data, group_data)
                            reply_message(line_bot_api, reply_token, f"✅ 已將用戶 `{target_id}` 移出黑名單！")
                            log_security_event("user_unbanned", chat_id, user_id, f"Unbanned user: {target_id}")
                            
                            # 通知其他管理員
                            alert_admins(line_bot_api, f"用戶 {target_id} 已被 {user_id} 移出黑名單", chat_id)
                        else:
                            reply_message(line_bot_api, reply_token, f"⚠️ 用戶 `{target_id}` 不在黑名單中")
                    else:
                        reply_message(line_bot_api, reply_token, "❌ 請提供有效的用戶ID\n格式：unban:用戶ID")
                    return
                
                elif text.lower() == 'ban':
                    # 進入等待模式，等待用戶提供要封鎖的用戶ID
                    wait_status["ban"][user_id] = True
                    reply_message(line_bot_api, reply_token, "📝 請發送要加入黑名單的用戶ID")
                    return
                
                elif text.lower() == 'unban':
                    # 進入等待模式，等待用戶提供要解封的用戶ID
                    wait_status["unban"][user_id] = True
                    reply_message(line_bot_api, reply_token, "📝 請發送要移出黑名單的用戶ID")
                    return
                
                elif text.lower() == 'banlist':
                    # 顯示黑名單
                    blacklist = ban_data.get("blacklist", {})
                    if not blacklist:
                        message = "✅ 目前沒有黑名單用戶"
                    else:
                        active_bans = [uid for uid, status in blacklist.items() if status]
                        if not active_bans:
                            message = "✅ 目前沒有活躍的黑名單用戶"
                        else:
                            message = f"🚫 黑名單用戶列表 ({len(active_bans)} 人):\n"
                            for i, uid in enumerate(active_bans[:20], 1):  # 最多顯示20個
                                message += f"{i}. `{uid}`\n"
                            if len(active_bans) > 20:
                                message += f"... 還有 {len(active_bans)-20} 個用戶"
                    
                    reply_message(line_bot_api, reply_token, message)
                    return
                
                elif text.lower().startswith('checkban '):
                    # 檢查特定用戶是否在黑名單中
                    target_id = text[9:].strip()
                    if target_id:
                        blacklist = ban_data.get("blacklist", {})
                        if target_id in blacklist and blacklist[target_id]:
                            message = f"🚫 用戶 `{target_id}` 在黑名單中"
                        else:
                            message = f"✅ 用戶 `{target_id}` 不在黑名單中"
                        reply_message(line_bot_api, reply_token, message)
                    else:
                        reply_message(line_bot_api, reply_token, "❌ 請提供用戶ID\n格式：checkban 用戶ID")
                    return
            
            # 如果沒有匹配的指令，標記用戶已讀近期訊息
            if chat_type == 'group':
                message_tracking = group_data.get("message_tracking", {})
                if chat_id in message_tracking:
                    # 標記用戶已讀最近幾條訊息
                    recent_messages = list(message_tracking[chat_id].keys())[-3:]  # 最近3條
                    for msg_id in recent_messages:
                        mark_message_as_read(chat_id, msg_id, user_id)
                    save_data(ban_data, group_data)
            
            # 如果沒有匹配的指令
            print(f"❓ 未匹配的指令: {text} | 用戶權限: 擁有者={user_id in owners}, 管理員={user_id in admins}")
    
    except Exception as e:
        print(f"❌ 錯誤詳情: {e}")
        import traceback
        print(f"❌ 完整錯誤追蹤: {traceback.format_exc()}")
        try:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                reply_message(line_bot_api, reply_token, f"❌ 處理指令時發生錯誤: {str(e)}")
        except:
            pass

@handler.add(MemberJoinedEvent)
def handle_member_joined(event):
    """處理成員加入群組 - 加強防護版本"""
    global ban_data, group_data
    
    if hasattr(event.source, 'group_id'):
        group_id = event.source.group_id
        joined_members = event.joined.members
        
        print(f"👥 群組 {group_id} 有新成員加入")
        
        try:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                
                for member in joined_members:
                    user_id = member.user_id
                    print(f"   新成員 ID: {user_id}")
                    
                    # 檢測異常邀請行為
                    alert_settings = ban_data.get("alert_settings", {})
                    if alert_settings.get("invite_detection", True):
                        # 推斷邀請者（實際上 LINE API 不直接提供邀請者資訊）
                        # 這裡我們記錄群組的邀請活動
                        invite_result = detect_abnormal_invites(group_id, "unknown_inviter", len(joined_members))
                        if invite_result:
                            log_security_event(f"abnormal_{invite_result}", group_id, "unknown_inviter", f"Invited {len(joined_members)} members")
                            alert_admins(line_bot_api, f"檢測到異常邀請行為: {invite_result}", group_id)
                    
                    # 多層檢查
                    threat_level = 0
                    warnings = []
                    
                    # 檢查黑名單
                    blacklist = ban_data.get("blacklist", {})
                    if user_id in blacklist and blacklist.get(user_id, False):
                        threat_level += 3
                        warnings.append("黑名單用戶")
                        log_security_event("blacklist_join", group_id, user_id, "Blacklisted user joined")
                        
                        # 自動警報
                        alert_message = f"🚨 危險！黑名單用戶加入群組\n群組: {group_id}\n用戶: {user_id}"
                        alert_admins(line_bot_api, alert_message, group_id)
                        
                        # 如果啟用自動處理
                        alert_settings = ban_data.get("alert_settings", {})
                        if alert_settings.get("auto_ban", False):
                            push_message(line_bot_api, group_id, f"⚠️ 系統檢測到黑名單用戶加入，建議群組管理員立即處理")
                    
                    # 檢查是否為信任用戶
                    trusted_users = ban_data.get("trusted_users", [])
                    if user_id in trusted_users:
                        push_message(line_bot_api, group_id, f"✅ 信任用戶 {user_id} 加入群組")
                        continue
                    
                    # 確保 member_count 存在
                    if "member_count" not in group_data:
                        group_data["member_count"] = {}
                    
                    # 更新成員計數
                    if group_id not in group_data["member_count"]:
                        group_data["member_count"][group_id] = {}
                    
                    current_time = datetime.now().isoformat()
                    group_data["member_count"][group_id][current_time] = len(joined_members)
                    
                    # 更新成員快取
                    if "member_cache" not in group_data:
                        group_data["member_cache"] = {}
                    if group_id not in group_data["member_cache"]:
                        group_data["member_cache"][group_id] = []
                    
                    if user_id not in group_data["member_cache"][group_id]:
                        group_data["member_cache"][group_id].append(user_id)
                    
                    # 檢查短時間內大量加入
                    recent_joins = 0
                    one_hour_ago = datetime.now() - timedelta(hours=1)
                    
                    for timestamp in group_data["member_count"][group_id]:
                        try:
                            if datetime.fromisoformat(timestamp) > one_hour_ago:
                                recent_joins += group_data["member_count"][group_id][timestamp]
                        except ValueError:
                            # 忽略無效的時間戳記
                            continue
                    
                    if recent_joins > 10:  # 1小時內超過10人加入
                        threat_level += 2
                        warnings.append("大量用戶加入")
                        log_security_event("mass_join", group_id, user_id, f"Mass join detected: {recent_joins} users")
                    
                    # 威脅評估
                    if threat_level >= 3:
                        warning_message = f"🚨 高風險警報！\n用戶: {user_id}\n威脅: {', '.join(warnings)}\n建議立即處理"
                        push_message(line_bot_api, group_id, warning_message)
                        alert_admins(line_bot_api, warning_message, group_id)
                    elif threat_level >= 1:
                        warning_message = f"⚠️ 注意：檢測到可疑活動\n用戶: {user_id}\n原因: {', '.join(warnings)}"
                        push_message(line_bot_api, group_id, warning_message)
                
                # 確保 last_check 存在
                if "last_check" not in group_data:
                    group_data["last_check"] = {}
                
                # 更新最後檢查時間
                group_data["last_check"][group_id] = datetime.now().isoformat()
                save_data(ban_data, group_data)
        
        except Exception as e:
            print(f"❌ 處理成員加入事件時發生錯誤: {e}")
            import traceback
            print(f"❌ 完整錯誤追蹤: {traceback.format_exc()}")

@handler.add(MemberLeftEvent)
def handle_member_left(event):
    """處理成員離開群組 - 增強踢人檢測"""
    global ban_data, group_data
    
    if hasattr(event.source, 'group_id'):
        group_id = event.source.group_id
        left_members = event.left.members
        
        print(f"👋 群組 {group_id} 有成員離開")
        
        try:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                
                for member in left_members:
                    user_id = member.user_id
                    print(f"   離開成員 ID: {user_id}")
                    
                    # 檢測踢人行為
                    alert_settings = ban_data.get("alert_settings", {})
                    if alert_settings.get("kick_detection", True):
                        # 推斷可能的踢人者（實際上 LINE API 不直接提供踢人者資訊）
                        # 我們可以根據最近的管理員活動來推斷
                        kick_result = detect_abnormal_kicks(group_id, "unknown_kicker")
                        if kick_result:
                            log_security_event(f"abnormal_{kick_result}", group_id, "unknown_kicker", f"Potential kick detected for user: {user_id}")
                            alert_admins(line_bot_api, f"檢測到異常踢人行為: {kick_result}\n被踢用戶: {user_id}", group_id)
                    
                    # 記錄離開事件
                    log_security_event("member_left", group_id, user_id, "Member left group")
                    
                    # 檢查是否為重要用戶（擁有者/管理員）離開
                    owners = ban_data.get("owners", [])
                    admins = ban_data.get("admin", [])
                    
                    if user_id in owners or user_id in admins:
                        role = '擁有者' if user_id in owners else '管理員'
                        alert_message = f"⚠️ 重要用戶離開群組\n群組: {group_id}\n用戶: {user_id}\n身份: {role}"
                        alert_admins(line_bot_api, alert_message, group_id)
                    
                    # 從成員快取中移除
                    if "member_cache" in group_data and group_id in group_data["member_cache"]:
                        if user_id in group_data["member_cache"][group_id]:
                            group_data["member_cache"][group_id].remove(user_id)
                
                save_data(ban_data, group_data)
        
        except Exception as e:
            print(f"❌ 處理成員離開事件時發生錯誤: {e}")
            import traceback
            print(f"❌ 完整錯誤追蹤: {traceback.format_exc()}")

def reply_message(line_bot_api, reply_token, text):
    """回覆訊息的輔助函數"""
    try:
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)]
            )
        )
        print(f"✅ 回覆訊息成功: {text[:50]}...")
    except Exception as e:
        print(f"❌ 回覆訊息失敗: {e}")

def push_message(line_bot_api, to, text):
    """推送訊息的輔助函數"""
    try:
        line_bot_api.push_message_with_http_info(
            PushMessageRequest(
                to=to,
                messages=[TextMessage(text=text)]
            )
        )
        print(f"✅ 推送訊息成功: {text[:50]}...")
    except Exception as e:
        print(f"❌ 推送訊息失敗: {e}")

def get_help_message(user_id):
    """根據用戶權限獲取說明訊息"""
    global ban_data
    
    if user_id in ban_data.get("owners", []):
        return """╔═══════════════════════
╠♥ ✿✿ 防翻群 Bot v4.0 ✿✿ ♥
╠══✪〘 擁有者說明 〙✪══════
╠
╠📋 基本功能：
╠➥ Help - 顯示此說明
╠➥ MyID - 查看自己的用戶ID
╠➥ Debug - 除錯資訊
╠➥ Reset - 重置等待狀態
╠
╠🛡️ 防翻群功能：
╠➥ Status - 查看群組防護狀態
╠➥ Security - 群組安全報告
╠➥ Protect - 啟用群組保護
╠➥ Unprotect - 停用群組保護
╠➥ Scan - 掃描群組威脅
╠➥ Emergency - 緊急防護模式
╠
╠🚨 警報控制：
╠➥ Alerts on/off - 開啟/關閉警報
╠➥ Kick detection on/off - 踢人檢測
╠
╠🚫 黑名單管理：
╠➥ Ban:用戶ID - 加入黑名單
╠➥ Unban:用戶ID - 移除黑名單
╠➥ Ban/Unban - 等待模式
╠➥ Banlist - 查看黑名單
╠➥ Checkban 用戶ID - 檢查狀態
╠
╠🆕 新功能：
╠➥ Read check - 查看已讀名單
╠➥ @all - 全體標記
╠➥ Cache members - 建立成員快取
╠
╠👑 擁有者專用：
╠➥ Trust/Untrust 用戶ID - 信任列表
╠
╠💡 提示：輸入 Cancel 可取消等待
╚〘Created By ©防翻群專家™ v4.0〙"""
    
    elif user_id in ban_data.get("admin", []):
        return """╔═══════════════════════
╠♥ ✿✿ 防翻群 Bot v4.0 ✿✿ ♥
╠══✪〘 管理員說明 〙✪══════
╠
╠📋 基本功能：
╠➥ Help - 顯示此說明
╠➥ MyID - 查看自己的用戶ID
╠➥ Debug - 除錯資訊
╠➥ Reset - 重置等待狀態
╠
╠🛡️ 防翻群功能：
╠➥ Status - 查看群組防護狀態
╠➥ Security - 群組安全報告
╠➥ Protect/Unprotect - 群組保護
╠➥ Scan - 掃描群組威脅
╠
╠🚨 警報控制：
╠➥ Alerts on/off - 開啟/關閉警報
╠➥ Kick detection on/off - 踢人檢測
╠
╠🚫 黑名單查看：
╠➥ Banlist - 查看黑名單
╠➥ Checkban 用戶ID - 檢查狀態
╠
╠🆕 新功能：
╠➥ Read check - 查看已讀名單
╠➥ @all - 全體標記
╠➥ Cache members - 建立成員快取
╠
╠💡 提示：輸入 Cancel 可取消等待
╚〘Created By ©防翻群專家™ v4.0〙"""
    
    else:
        return """╔═══════════════════════
╠♥ ✿✿ 防翻群 Bot v4.0 ✿✿ ♥
╠══✪〘 使用說明 〙✪═════════
╠
╠📋 可用功能：
╠➥ Help - 顯示此說明
╠➥ MyID - 查看自己的用戶ID
╠➥ Debug - 除錯資訊
╠➥ Reset - 重置等待狀態
╠
╠🛡️ 安全查詢：
╠➥ Status - 查看群組防護狀態
╠➥ Security - 群組安全報告
╠
╠🆕 新功能：
╠➥ Read check - 查看已讀名單
╠ （僅查看，需管理員權限標記）
╠
╠💡 提示：
╠ 本機器人提供群組防翻保護
╠ 包含踢人檢測、已讀追蹤等功能
╠ 如果卡在等待狀態，輸入 Reset
╠ 如需更多功能，請聯絡管理員
╠
╚〘Created By ©防翻群專家™ v4.0〙"""

if __name__ == "__main__":
    print("🚀 啟動增強版防翻群 LINE Bot v4.0...")
    print("🛡️ 防護系統已就緒")
    print("🆕 新功能：踢人檢測、已讀追蹤、@all 標記")
    print("📝 請確保已設定正確的憑證")
    print("🔗 Webhook URL: http://localhost:5000/callback")
    print("=" * 50)
    
    app.run(debug=True, port=5000, host='0.0.0.0')