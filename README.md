# Boss直聘自动打招呼助手

基于浏览器自动化的 Boss 直聘职位批量沟通工具，支持薪资筛选、经验过滤、公司黑名单等功能。

## 功能特性

- 🎯 **智能职位筛选**：按薪资下限、工作经验、公司关键词多维度过滤
- 🤖 **自动化沟通**：批量点击"立即沟通"，自动处理弹窗和对话框
- 🛡️ **反风控策略**：随机延迟、模拟滚动、人类行为模拟
- 🔧 **灵活配置**：支持自定义岗位关键词、工作地点、沟通数量
- 🖥️ **图形界面**：基于 CustomTkinter 的现代化暗色主题 UI
- 📦 **一键打包**：支持 PyInstaller 编译为独立可执行文件

## 环境要求

- **操作系统**：Windows 10/11
- **浏览器**：Microsoft Edge（已安装）
- **Python**：3.9 或以上版本（仅源码运行需要）

## 快速开始

### 方式一：使用可执行文件（推荐）

1. **启动 Edge 调试模式**
   ```bash
   # 双击运行或在命令行执行
   start_edge_debug.bat
   ```
   此脚本会自动：
   - 启动 Edge 浏览器并开启 9222 调试端口
   - 使用独立用户数据目录（不影响日常浏览）
   - 自动打开 Boss 直聘首页

2. **登录 Boss 直聘**
   - 在启动的 Edge 浏览器中访问 https://www.zhipin.com/
   - 完成账号登录（如需）

3. **运行程序**
   ```bash
   # 双击运行
   BossAutoGreeter.exe
   ```

4. **测试连接**
   - 点击"测试浏览器连接"按钮
   - 确认日志显示连接成功

5. **配置参数并开始**
   - 设置目标岗位、工作地点、薪资下限等参数
   - 点击"开始运行应用"

### 方式二：从源码运行

1. **克隆仓库**
   ```bash
   git clone https://github.com/FreemanLi25/JobHelper.git
   cd JobHelper
   ```

2. **安装依赖**
   ```bash
   # 创建虚拟环境
   python -m venv .venv
   
   # 激活虚拟环境
   .venv\Scripts\activate  # Windows PowerShell
   # 或
   .venv\Scripts\activate.bat  # CMD
   
   # 安装依赖包
   pip install -r requirements.txt
   ```

3. **启动 Edge 调试模式**
   ```bash
   start_edge_debug.bat
   ```

4. **运行程序**
   ```bash
   python main.py
   ```

## 使用说明

### 参数配置

| 参数 | 说明 | 示例 |
|------|------|------|
| 目标岗位关键词 | 搜索的职位名称 | `后端开发`、`Python工程师` |
| 工作地点 | 目标城市 | `杭州`、`北京`、`上海` |
| 工作经验限制 | 筛选经验要求 | `不限`、`1-3年`、`应届生` |
| 期望薪资下限（K） | 最低月薪（千元） | `15` 表示 15K |
| 最大沟通数量 | 本轮最大打招呼数 | `50`、`100` |
| 公司限制 | 排除的公司关键词（用；分割） | `外包；培训；保险` |

### 工作流程

1. 程序会接管已启动的 Edge 浏览器（端口 9222）
2. 自动导航至 Boss 直聘并搜索目标职位
3. 遍历职位卡片，按以下条件筛选：
   - 薪资是否达到设定下限
   - 工作经验是否符合要求
   - 公司名是否命中黑名单
4. 对符合条件的职位点击"立即沟通"
5. 自动处理弹窗，保持返回列表页继续处理
6. 滚动加载更多职位，直到达到目标数量或无新职位

### 日志说明

程序右侧显示实时运行日志，包含：
- `[符合]`：职位符合筛选条件，准备沟通
- `[成功]`：已成功发送打招呼消息
- `[跳过]`：职位不符合条件（标注具体原因）
- `[失败]`：点击沟通按钮失败

## 编译可执行文件

如需自行打包为 exe：

```bash
# 运行打包脚本
build_exe.bat
```

编译完成后，可执行文件位于：`dist\BossAutoGreeter.exe`

## 常见问题

### 1. 浏览器连接失败

**错误信息**：`未检测到 127.0.0.1:9222 调试端口`

**解决方案**：
- 确认已运行 `start_edge_debug.bat`
- 关闭 Edge 后台加速：Edge 设置 → 系统和性能 → 启动增强 → 关闭
- 重启后再次运行脚本

### 2. 端口 9222 未暴露

**错误信息**：`Edge did not expose port 9222`

**解决方案**：
- 脚本会提示是否强制关闭所有 Edge 进程，选择 `Y`
- 或手动关闭所有 Edge 窗口后重新运行

### 3. 职位识别失败

**可能原因**：
- Boss 直聘页面结构调整
- 未登录或登录状态过期
- 触发验证码或安全验证

**解决方案**：
- 在接管的 Edge 中手动完成登录/验证
- 程序会等待人工处理后再继续

### 4. 网络连接问题（拉取代码时）

如果在国内网络环境下 clone 失败：

```bash
# 配置代理（假设代理端口为 7890）
git config --global http.proxy http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890

# 拉取代码
git clone https://github.com/FreemanLi25/JobHelper.git

# 完成后取消代理
git config --global --unset http.proxy
git config --global --unset https.proxy
```

## 注意事项

- ⚠️ 本工具仅供学习交流使用，请遵守平台使用规范
- ⚠️ 自动化操作可能触发平台风控，建议控制使用频率
- ⚠️ 程序使用的 Edge 配置目录为 `C:\tmp\BossAutoGreeterProfile`，与日常浏览数据隔离
- ⚠️ 运行期间请勿手动关闭 Edge 调试窗口

## 技术栈

- **浏览器自动化**：[DrissionPage](https://github.com/g1879/DrissionPage) - 基于 Chromium 协议的自动化工具
- **GUI 框架**：[CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) - 现代化 Tkinter UI
- **打包工具**：PyInstaller
- **目标平台**：Boss 直聘 Web 版

## 项目结构

```
JobHelper/
├── main.py                 # 主程序（GUI + 自动化逻辑）
├── requirements.txt        # Python 依赖
├── start_edge_debug.bat    # Edge 调试模式启动脚本
├── build_exe.bat          # PyInstaller 打包脚本
├── .gitignore             # Git 忽略配置
└── README.md              # 项目说明文档
```

## License

本项目仅供学习交流使用，请勿用于商业或违规用途。
