# Jev 微信助手（Windows）

Windows 版在电脑版微信旁运行，不读取微信数据库、不注入微信进程，也不调用微信接口。它优先使用 Windows UI Automation 读取当前可见聊天文字；若微信未暴露控件文本，则截取用户明确框选的聊天区域并在本机 OCR。识别结果先发送给 TypeSafe Jev 做结构化判断；配置 DeepSeek API 后，再根据 Jev 判断生成三条建议回复。

建议回复只能点击“复制”，程序没有操作微信输入框、点击“发送”或模拟 Enter 的路径。检测到转账、红包、收款、支付等交易词时会拒绝分析。

## 环境

- Windows 10/11（x64）
- 电脑版微信进程名 `Weixin.exe` 或 `WeChat.exe`
- Python 3.11 或 3.12（仅源码运行/构建需要；依赖 rapidocr-onnxruntime 要求 Python <3.13，3.13/3.14 不可用）
- TypeSafe/Jev API Key
- DeepSeek API Key（可选；未配置时仍可只做 Jev 判断）

## 源码运行

在仓库根目录打开 PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\windows\install.ps1
powershell -ExecutionPolicy Bypass -File .\windows\start.ps1
```

首次启动：

1. 打开电脑版微信并进入一个普通文字聊天。
2. 在“设置”里保存 TypeSafe 控制台生成的 Jev API 密钥。
3. 如需建议回复，在同一设置窗口填写 DeepSeek API 密钥。默认模型是 `deepseek-flash`，也可改成 `deepseek-v4-pro`。
4. 点击“框选聊天区”，只框消息气泡区域，不要包含左侧会话列表和底部输入区。
5. 点击“分析当前微信对话”。

两枚密钥都写入 Windows 凭据管理器，`settings.json` 不保存密钥。DeepSeek 留空时，程序只显示 Jev 判断，不会报错。

分析开始时助手窗口会短暂隐藏，这是为了避免置顶窗口遮住微信后被 OCR 当成聊天内容。界面会依次显示“读取微信 → Jev 判断 → DeepSeek 建议”，不会再用一个状态覆盖整个过程。

框选坐标相对于微信客户区保存。微信窗口尺寸或缩放发生明显变化后，应重新校准。

## 打包 Windows 应用

```powershell
powershell -ExecutionPolicy Bypass -File .\windows\build.ps1
```

产物位于 `dist\Jev微信助手\Jev微信助手.exe`。PyInstaller 的文件夹模式包含 OCR 模型及运行库，可直接复制整个文件夹到同架构 Windows 机器。

## 隐私和边界

- 当前框选区域的可见文字会交给 TypeSafe Jev；配置 DeepSeek 后，对话和 Jev 判断也会交给 DeepSeek 用于生成建议。OCR 本身完全在本机执行。
- 不读本地聊天数据库，不绕过微信权限，不 hook、不注入。
- 配置文件位于 `%APPDATA%\JevChatAssistant\settings.json`，其中不含密钥。
- 可在设置中配置会话标题白名单。
- 目前只面向普通文字对话；图片、语音、引用卡片等不会被可靠还原。

## 常见问题

- **提示 Jev / TypeSafe 密钥无效（401）**：请填写 `console.typesafe.ai` 控制台生成的 API Key，不能填写 OpenRouter 密钥、模型名或账户 ID。
- **提示 DeepSeek 密钥无效或余额不足**：在设置中更新 DeepSeek API 密钥或充值；Jev 判断仍然会保留显示。
- **识别结果出现“候选回复”“Jev 判断”等助手界面文字**：这是旧版置顶窗口被截进聊天区的缺陷，新版会在截图期间自动隐藏。请确认运行的是最新构建，并重新分析。
- **“我/对方”仍有少量颠倒**：重新框选，只包含中间消息气泡区域，不要包含左侧会话列表、顶部标题和底部输入框。
