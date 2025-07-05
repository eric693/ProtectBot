## 📖 專案簡介

防翻群 LINE Bot 是一個專為 LINE 群組設計的安全防護機器人，提供全方位的群組管理和安全監控功能。透過智能檢測系統，有效防止惡意用戶破壞群組環境，確保社群健康發展。

### 🎯 解決的問題

- ✅ **惡意翻群攻擊** - 自動識別並警報可疑行為
- ✅ **黑名單管理** - 持久化封鎖問題用戶
- ✅ **群組管理效率** - 自動化監控減少人工負擔
- ✅ **成員活動追蹤** - 已讀狀態與互動記錄
- ✅ **異常行為檢測** - 踢人/邀請行為監控

---

## 🚀 功能特色

### 🛡️ 核心防護功能

| 功能 | 描述 | 狀態 |
|------|------|------|
| **黑名單系統** | 永久封鎖惡意用戶，阻止其使用 Bot 功能 | ✅ |
| **實時監控** | 24/7 監控群組活動與成員變化 | ✅ |
| **威脅檢測** | 多層次安全檢查，智能評估風險等級 | ✅ |
| **自動警報** | 即時通知管理員可疑活動 | ✅ |

### 🆕 進階功能

#### 📖 已讀追蹤系統
- **訊息追蹤** - 記錄群組訊息的互動狀況
- **已讀名單** - 查看特定訊息的已讀用戶列表
- **互動分析** - 基於用戶活動的已讀狀態推斷

#### 📢 全體標記功能
- **@all 模擬** - 提供類似全體標記的通知效果
- **成員快取** - 智能記錄活躍成員列表
- **權限控制** - 僅限管理員使用，防止濫用

#### 🔍 異常行為檢測
- **踢人監控** - 檢測頻繁踢人行為 (1小時3人/24小時5人)
- **邀請監控** - 識別大量邀請活動 (1小時10人/24小時20人)
- **活動分析** - 追蹤用戶行為模式，識別異常

### 👑 權限管理系統

#### 🏆 三級權限架構
1. **擁有者 (Owner)** - 最高權限，可管理所有功能
2. **管理員 (Admin)** - 群組管理權限，可使用大部分功能
3. **一般用戶 (User)** - 基本查詢權限

#### 🔐 安全機制
- **多重驗證** - 特殊指令需要特定用戶 ID 驗證
- **操作記錄** - 所有安全相關操作都會被記錄
- **權限隔離** - 不同權限級別的功能嚴格分離

---

## ⚙️ 配置說明

### 🔑 LINE Bot 設定

1. **建立 LINE Bot**
   - 前往 [LINE Developers Console](https://developers.line.biz/)
   - 建立新的 Provider 和 Channel
   - 選擇 "Messaging API"

2. **取得憑證**
   ```python
   CHANNEL_ACCESS_TOKEN = 'your_channel_access_token'
   CHANNEL_SECRET = 'your_channel_secret'
   ```

3. **設定 Webhook**
   - Webhook URL: `https://your-domain.com/callback`
   - 啟用 "Use webhook"

### 🗄️ 資料結構

#### ban.json
```json
{
  "owners": ["擁有者用戶ID列表"],
  "admin": ["管理員用戶ID列表"],
  "blacklist": {"用戶ID": true/false},
  "trusted_users": ["信任用戶ID列表"],
  "protected_groups": {
    "群組ID": {
      "enabled": true,
      "level": "標準/緊急",
      "enabled_time": "啟用時間"
    }
  },
  "alert_settings": {
    "enabled": true,
    "alert_admins": true,
    "auto_ban": false,
    "kick_detection": true,
    "invite_detection": true
  }
}
```

---

## 📚 使用指南

### 🎮 基本指令

#### 🌟 所有用戶可用
```
help          # 顯示幫助訊息
myid          # 查看自己的用戶ID
status        # 查看群組防護狀態
security      # 查看群組安全報告
debug         # 顯示除錯資訊
reset         # 重置等待狀態
read check    # 查看已讀名單 (群組功能)
```

### 🛡️ 管理員指令

#### 🔧 群組防護
```
protect       # 啟用群組保護
unprotect     # 停用群組保護
scan          # 掃描群組威脅
emergency     # 啟用緊急防護模式
```

#### 🚨 警報控制
```
alerts on/off           # 開啟/關閉管理員警報
kick detection on/off   # 開啟/關閉踢人檢測
```

#### 🚫 黑名單查看
```
banlist                 # 查看黑名單
checkban [用戶ID]       # 檢查用戶黑名單狀態
```

#### 🆕 新功能
```
@all                    # 全體標記 (需先建立成員快取)
cache members           # 建立成員快取
```

### 👑 擁有者專用指令

#### 🚫 黑名單管理
```
ban:[用戶ID]            # 直接加入黑名單
unban:[用戶ID]          # 直接移除黑名單
ban                     # 進入等待模式加入黑名單
unban                   # 進入等待模式移除黑名單
```

#### 👥 信任管理
```
trust [用戶ID]          # 加入信任列表
untrust [用戶ID]        # 移出信任列表
```

#### 🔑 特殊指令
```
grantme                 # 授予完整權限 (限定用戶)
makeowner               # 設為擁有者 (限定用戶)
makeadmin               # 設為管理員 (限定用戶)
```

---

## 🎯 使用範例

### 🔍 場景一：查看已讀名單

1. **用戶輸入**：`read check`
2. **Bot 回應**：顯示最近10條訊息列表
3. **用戶選擇**：輸入要查詢的訊息ID
4. **Bot 顯示**：該訊息的已讀用戶列表

```
📖 已讀名單查詢結果
════════════════════
💬 訊息內容: Hello everyone!
👀 已讀人數: 3 人
📋 已讀用戶:
• U12345...
• U67890...
• U13579...
```

### 🚨 場景二：黑名單管理

1. **管理員發現惡意用戶**
2. **輸入指令**：`ban:U惡意用戶ID`
3. **系統執行**：
   - 加入黑名單
   - 記錄安全事件
   - 通知其他管理員
   - 阻止該用戶使用 Bot 功能

### 📢 場景三：全體通知

1. **建立成員快取**：`cache members`
2. **發送全體通知**：`@all`
3. **Bot 回應**：模擬全體標記效果

---

#### 自訂監控閾值

修改 `pro.py` 中的監控參數：

```python
# 活動監控閾值
HIGH_ACTIVITY_THRESHOLD = 10  # 1小時內訊息數

# 踢人檢測閾值
RAPID_KICKS_THRESHOLD = 3     # 1小時內踢人數
MASS_KICKS_THRESHOLD = 5      # 24小時內踢人數

# 邀請檢測閾值
RAPID_INVITES_THRESHOLD = 10  # 1小時內邀請數
MASS_INVITES_THRESHOLD = 20   # 24小時內邀請數
```

### 🔄 資料備份

建議定期備份重要資料檔案：

```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p backups
cp ban.json backups/ban_${DATE}.json
cp group.json backups/group_${DATE}.json
cp security_log.txt backups/security_log_${DATE}.txt
```

---

## ❓ 常見問題

### 🤔 Q: Bot 無法回應訊息？

**A: 檢查以下項目：**
1. Webhook URL 是否正確設定
2. HTTPS 證書是否有效
3. 服務是否正常運行
4. 防火牆是否阻擋連接

### 🤔 Q: 已讀追蹤不準確？

**A: 已讀功能說明：**
- 基於用戶互動記錄，非官方 API
- 需要用戶在群組中有活動才會被記錄
- 準確度受限於 LINE Bot API 限制

### 🤔 Q: @all 功能無法使用？

**A: 使用步驟：**
1. 先執行 `cache members` 建立成員快取
2. 需要管理員或擁有者權限
3. 由於 LINE API 限制，僅提供模擬效果

### 🤔 Q: 黑名單用戶仍可在群組發言？

**A: 這是正常現象：**
- Bot 只能監控和警報，無法直接踢人
- 黑名單用戶無法使用 Bot 指令
- 需要群組管理員手動處理

### 🤔 Q: 如何重置所有資料？

**A: 清理步驟：**
```bash
# 停止 Bot
# 刪除資料檔案
rm ban.json group.json security_log.txt
# 重新啟動 Bot
python pro.py
```

---

## 🔒 安全考量

### 🛡️ 安全最佳實踐

1. **憑證保護**
   - 不要將 Access Token 提交到版本控制
   - 使用環境變數或安全的配置管理

2. **訪問控制**
   - 定期檢查擁有者和管理員列表
   - 移除不需要的權限用戶

3. **監控日誌**
   - 定期查看 `security_log.txt`
   - 注意異常活動模式

4. **資料備份**
   - 定期備份 `ban.json` 和 `group.json`
   - 測試恢復程序

### ⚠️ 已知限制

- **LINE API 限制**：無法直接踢人或禁言
- **已讀追蹤**：基於互動記錄，非真實已讀狀態
- **成員列表**：無法獲取完整群組成員列表
- **邀請者識別**：無法直接識別邀請者身份
