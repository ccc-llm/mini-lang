# corpus/chinese

迷你語 mini-x 中文對話範例。每個檔案一類主題，對話者為 A / B。

字集規則（見 ../../spec.md）：
- 只用中文字集裡的字
- 數字用 0-9
- 小字集寫不出來的詞直接用 English

| 檔案 | 主題 |
| --- | --- |
| dialog.txt | 綜合日常（早晨、學業、買東西、錢、海邊、雨天） |
| family.txt | 家庭：家人、晚餐、爺爺奶奶、出遊、買衣服 |
| school.txt | 學校：上課、做題、圖書館、班級、做模型 |
| morning.txt | 早晨：起床、早餐、出門上學、回家 |
| outing.txt | 外出：散步、公園、吃飯、放風箏、回家 |
| transport.txt | 交通：公車、轉車、迷路、腳踏車 |
| airport.txt | 機場：報到、護照、登機、飛機上、抵達 |
| friends.txt | 交友：認識新朋友、聊天、朋友約、禮物 |
| market.txt | 市場購物：買菜買肉買水果、講價 |
| restaurant.txt | 餐廳：點餐、吃飯、買單、甜點 |
| hospital.txt | 醫院：看醫生、拿藥、探病、照護 |
| work.txt | 工作：上班、商店工作、學新東西 |
| phone.txt | 電話與訊息：打電話、傳訊息、約時間 |
| birthday.txt | 生日：慶生、送禮、蛋糕、拍照 |
| weather.txt | 天氣：冷熱、雨、雪、風、颱風 |

檢查字集（程式在 ../../code/charset_check.py）：

    python3 code/charset_check.py
