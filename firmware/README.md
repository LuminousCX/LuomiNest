# LuomiNest Firmware

基于 ESP32-S3 N16R8 + ST7735S 的 Live2D 桌面伴侣，通过 MQTT 推流实现 PC 端 Live2D 渲染 → ESP32 端 JPEG 解码显示。

## 系统架构

```
┌──────────────────┐   MQTT publish    ┌──────────────┐   MQTT subscribe   ┌──────────────────┐
│   PC 渲染器      │ ────────────────→ │  Mosquitto   │ ─────────────────→ │  ESP32-S3        │
│  192.168.1.222   │  JPEG帧 ~2.4KB   │  :1883       │  JPEG帧            │  192.168.1.18    │
│  stream_server   │  15 FPS           │              │                    │  esp_jpeg 解码    │
│                  │                   │              │                    │  LVGL → ST7735S  │
└──────────────────┘                   └──────────────┘                    └──────────────────┘
```

核心设计：ESP32 不关心帧是谁渲染的，只负责 JPEG 解码 + 显示。更换渲染器只需改 PC 端。

---

## 硬件

### ESP32-S3 N16R8 主控板

| 参数 | 详情 |
|------|------|
| CPU | Xtensa 32 位 LX7 双核，最高 240MHz |
| Wi-Fi | IEEE 802.11 b/g/n (2.4GHz) |
| 蓝牙 | Bluetooth 5 (LE) |
| SRAM | 512 KB |
| ROM | 384 KB |
| Flash | 16 MB（N16 = 16MB Flash） |
| PSRAM | 8 MB（R8 = 8MB PSRAM） |
| 封装 | QFN56 (7×7mm) |
| 工作电压 | 3.0V ~ 3.6V（典型 3.3V） |
| USB | 全速 USB OTG + USB Serial/JTAG 控制器 |

开发板特性：USB Type-C 供电/下载、RST/BOOT 按键、板载 RGB LED (WS2812)、板载 PCB 天线。

#### GPIO 引脚排列

**上排（从右到左）**

| 丝印 | GPIO | 功能说明 |
|------|------|----------|
| 3V3 | - | 3.3V 电源输出 |
| RST | EN (GPIO0) | 复位/使能 |
| 4 | GPIO4 | 通用IO / ADC1_CH3 |
| 5 | GPIO5 | 通用IO / ADC1_CH4 |
| 6 | GPIO6 | 通用IO / ADC1_CH5 |
| 7 | GPIO7 | 通用IO / ADC1_CH6 |
| 15 | GPIO15 | 通用IO / ADC2_CH4 / U0RTS |
| 16 | GPIO16 | 通用IO / ADC2_CH5 / U0CTS |
| 17 | GPIO17 | 通用IO / ADC2_CH6 / U1TXD |
| 18 | GPIO18 | 通用IO / ADC2_CH7 / U1RXD |
| 8 | GPIO8 | 通用IO / ADC1_CH7 / SUBSPICS1 |
| 3 | GPIO3 | 通用IO / ADC1_CH2 / **Strapping** |
| 46 | GPIO46 | 通用IO / **Strapping** |
| 9 | GPIO9 | 通用IO / ADC1_CH8 / FSPIHD |
| 10 | GPIO10 | 通用IO / ADC1_CH9 / FSPICS0 |
| 11 | GPIO11 | 通用IO / ADC2_CH0 / FSPID |
| 12 | GPIO12 | 通用IO / ADC2_CH1 / FSPICLK |
| 13 | GPIO13 | 通用IO / ADC2_CH2 / FSPIQ |
| 14 | GPIO14 | 通用IO / ADC2_CH3 / FSPIWP |

**下排（从左到右）**

| 丝印 | GPIO | 功能说明 |
|------|------|----------|
| GND | - | 接地 |
| TX | GPIO43 / U0TXD | UART0 发送 |
| RX | GPIO44 / U0RXD | UART0 接收 |
| 1 | GPIO1 | 通用IO / ADC1_CH0 |
| 2 | GPIO2 | 通用IO / ADC1_CH1 |
| 42 | GPIO42 | 通用IO / MTMS |
| 41 | GPIO41 | 通用IO / MTDI / CLK_OUT1 |
| 40 | GPIO40 | 通用IO / MTDO / CLK_OUT2 |
| 39 | GPIO39 | 通用IO / MTCK / CLK_OUT3 |
| 38 | GPIO38 | 通用IO / FSPIWP |
| 37 | GPIO37 | 通用IO / FSPIQ / **PSRAM用** |
| 36 | GPIO36 | 通用IO / FSPICLK / **PSRAM用** |
| 35 | GPIO35 | 通用IO / FSPID / **PSRAM用** |
| 0 | GPIO0 | 通用IO / RTC_GPIO0 / **Strapping** |
| 45 | GPIO45 | 通用IO / **Strapping** |
| 48 | GPIO48 | 通用IO / SPICLK_N_DIFF |
| 47 | GPIO47 | 通用IO / SPICLK_P_DIFF |
| 21 | GPIO21 | 通用IO / RTC_GPIO21 |
| 20 | GPIO20 | 通用IO / RTC_GPIO20 / USB_D+ |
| 19 | GPIO19 | 通用IO / RTC_GPIO19 / USB_D- |

**特殊功能引脚**

| 引脚 | 说明 |
|------|------|
| GPIO0, GPIO3, GPIO45, GPIO46 | Strapping 引脚，上电时决定启动模式，不可悬空 |
| GPIO19, GPIO20 | USB-JTAG 默认功能，用作 GPIO 时会禁用 USB-JTAG |
| GPIO26~GPIO37 | 通常连接 SPI Flash/PSRAM，不建议他用 |

### ST7735S 显示屏

| 参数 | 规格 |
|------|------|
| 制造商 | Sitronix（矽创电子） |
| 类型 | 单芯片 262K 色 TFT LCD 控制器/驱动器 |
| 分辨率 | 132(H) × 162(V) RGB（实际常用 128×160） |
| 色彩深度 | 18-bit (262,144 色)，可配置 16-bit (65,536 色) |
| 接口 | SPI 串行接口（3线/4线模式） |
| GRAM | 132×162×18-bit = 388,908 bits 内置显示内存 |
| 逻辑电压 | 1.65V ~ 3.3V（IOVCC） |
| 驱动电压 | 2.5V ~ 4.8V（VCI） |

#### 驱动板引脚定义（从右到左）

| 引脚 | 全称 | 类型 | 说明 |
|------|------|------|------|
| BLK | BackLight | 输入 | LED 背光控制（PWM 调光） |
| CS | Chip Select | 输入 | SPI 片选，低电平有效 |
| DC | Data/Command | 输入 | 数据/命令选择（高=数据，低=命令） |
| RST | Reset | 输入 | 硬件复位，低电平有效 |
| SDA | Serial Data | 输入 | SPI MOSI 数据线 |
| SCL | Serial Clock | 输入 | SPI 时钟线 |
| VDD | Power Supply | 电源 | 3.3V 逻辑电源 |
| GND | Ground | 电源 | 接地 |

#### 实际接线表（已验证）

| ST7735S | ESP32-S3 | 丝印 | 代码宏定义 | 说明 |
|---------|----------|------|-----------|------|
| SCL | GPIO12 | 12 | `ST7735S_CLK_PIN` | FSPI_CLK |
| SDA | GPIO11 | 11 | `ST7735S_MOSI_PIN` | FSPI_MOSI |
| CS | GPIO10 | 10 | `ST7735S_CS_PIN` | 软件CS（关键） |
| DC | GPIO5 | 5 | `ST7735S_DC_PIN` | 数据/命令 |
| RST | GPIO4 | 4 | `ST7735S_RST_PIN` | 复位 |
| BLK | GPIO6 | 6 | `ST7735S_BL_PIN` | PWM 背光 |
| VDD | 3V3 | - | - | 电源 |
| GND | GND | - | - | 接地 |

```
ESP32-S3 开发板          ST7735S 显示屏
    3V3  ────────────────►  VDD
    GND  ────────────────►  GND
    GPIO12 ──────────────►  SCL (SPI_CLK)
    GPIO11 ──────────────►  SDA (SPI_MOSI)
    GPIO5  ──────────────►  DC
    GPIO4  ──────────────►  RST
    GPIO10 ──────────────►  CS
    GPIO6  ──────────────►  BLK (PWM调光)
```

#### ST7735S 驱动参数（已验证）

| 参数 | 值 | 说明 |
|------|-----|------|
| SPI 频率 | 15 MHz | 从 10MHz 提升，可达 ~35FPS |
| CS 管理 | 软件手动 (`spics_io_num = -1`) | 硬件CS会导致花屏 |
| MADCTL | `0x00` | RGB 顺序 |
| 颜色反转 | `INVOFF` (0x20) | 关闭反转 |
| 字节交换 | `__builtin_bswap16` | SPI 大端序 |
| 颜色格式 | RGB565 (16bit) | |
| X/Y 偏移 | 0, 0 | 128x160 黑 Tab |

**已解决的关键问题**

| 问题 | 原因 | 修复 |
|------|------|------|
| 花屏 | 硬件CS在SPI传输间隙自动拉高 | 改用软件CS，整个帧数据一次发送 |
| 颜色错乱 | MADCTL=0x08(BGR) + INVON | 改为 MADCTL=0x00(RGB) + INVOFF |

---

## Mosquitto MQTT Broker 配置

### 安装与基础配置

以管理员权限打开 PowerShell，追加监听配置到 `mosquitto.conf`：

```powershell
Add-Content -Path "C:\Program Files\mosquitto\mosquitto.conf" -Value "`nlistener 1883 0.0.0.0`nallow_anonymous true`nmax_message_size 0"
```

重启 Mosquitto 服务：

```powershell
net stop mosquitto
net start mosquitto
```

验证监听状态：

```powershell
netstat -an | findstr 1883
```

应看到 `TCP 0.0.0.0:1883 0.0.0.0:0 LISTENING`。

### 高频优化配置

追加高频消息优化参数：

```powershell
$config = @"
max_inflight_messages 200
max_queued_messages 1000
max_keepalive 3600
"@
Add-Content -Path "C:\Program Files\mosquitto\mosquitto.conf" -Value $config
```

重启服务使配置生效：

```powershell
net stop mosquitto
net start mosquitto
```

> 如果服务未运行，`net stop` 会报错 3521，直接 `net start` 即可。

### 配置文件说明

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `listener` | `1883 0.0.0.0` | 监听所有网卡的 1883 端口 |
| `allow_anonymous` | `true` | 允许匿名连接（局域网环境） |
| `max_message_size` | `0` | 不限制消息大小（JPEG 帧可能较大） |
| `max_inflight_messages` | `200` | 同时在途消息数，提升吞吐 |
| `max_queued_messages` | `1000` | 排队消息上限 |
| `max_keepalive` | `3600` | 最大 keepalive 时间（秒） |

项目内保留了配置副本：[config/mosquitto.conf](config/mosquitto.conf)

---

## MQTT Topic

| Topic | 方向 | 格式 | 说明 |
|-------|------|------|------|
| `luominest/s3/cmd` | PC → ESP32+PC | UTF-8 | 表情命令 (happy/sad/angry/...) |
| `luominest/s3/mode` | PC → PC | UTF-8 | 传输模式 (jpeg/rgb565) |
| `luominest/s3/stream` | PC → ESP32 | JPEG/RGB565 二进制 | 视频帧 |
| `luominest/s3/status` | ESP32 → PC | JSON | 设备状态 |

### 表情控制命令

```powershell
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h 192.168.1.222 -t "luominest/s3/cmd" -m "happy"
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h 192.168.1.222 -t "luominest/s3/cmd" -m "sad"
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h 192.168.1.222 -t "luominest/s3/cmd" -m "angry"
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h 192.168.1.222 -t "luominest/s3/cmd" -m "surprised"
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h 192.168.1.222 -t "luominest/s3/cmd" -m "wave"
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h 192.168.1.222 -t "luominest/s3/cmd" -m "think"
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h 192.168.1.222 -t "luominest/s3/cmd" -m "sleep"
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h 192.168.1.222 -t "luominest/s3/cmd" -m "talk"
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h 192.168.1.222 -t "luominest/s3/cmd" -m "idle"

# 切换传输模式
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h 192.168.1.222 -t "luominest/s3/mode" -m "jpeg"
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h 192.168.1.222 -t "luominest/s3/mode" -m "rgb565"
```

---

## 性能

| 模式 | 帧大小 | 带宽 | 帧率 | 延迟 |
|------|--------|------|------|------|
| JPEG (quality=60) | ~2.4KB | ~36KB/s | 15 FPS | ~50ms |
| RGB565 (raw) | 40KB | ~400KB/s | 10 FPS | ~30ms |

---

## ESP-IDF 项目配置

| 配置项 | 值 |
|--------|-----|
| IDF 版本 | v5.5.3 |
| 目标芯片 | esp32s3 |
| Flash | QIO, 16MB |
| PSRAM | OCT 模式, 80MHz |
| LVGL | RGB565, FreeRTOS |
| MQTT | 3.1.1 |
| esp_jpeg | v1.3.1 (TJpgDec ROM 解码) |

---

## 构建与烧录

```powershell
# 加载 ESP-IDF 环境
. "C:\Espressif\tools\Microsoft.v5.5.3.PowerShell_profile.ps1"

# 进入项目
cd C:\Users\lumin\Projects\Project\LuomiNest\firmware\esp32-s3

# 清理（可选）
rm -Recurse -Force .\build, .\sdkconfig

# 构建
idf.py build

# 烧录并监控（替换 COM3 为实际端口）
idf.py -p COM3 flash monitor
```

---

## PC 端渲染器

### Pillow 渲染器（旧版）

```powershell
cd C:\Users\lumin\Projects\Project\LuomiNest\firmware\server\pillow

# 首次设置
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 启动
python stream_server.py --broker 192.168.1.222 --fps 15 --mode jpeg
```

### Live2D 渲染器（当前版本）

使用 `live2d-py` + PyQt5 QOpenGLWidget 渲染 Live2D 模型，通过 MQTT 推流到 ESP32。

```powershell
cd C:\Users\lumin\Projects\Project\LuomiNest\firmware\server\live2d

# 首次设置
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 启动（默认使用 llny 模型）
python stream_server.py --broker 192.168.1.222 --fps 15 --mode jpeg --character llny

# 使用猫娘模型
python stream_server.py --broker 192.168.1.222 --fps 15 --mode jpeg --character cat

# 指定自定义模型路径
python stream_server.py --broker 192.168.1.222 --model "path/to/model.model3.json"
```

#### 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--broker` | `192.168.1.222` | MQTT Broker 地址 |
| `--port` | `1883` | MQTT Broker 端口 |
| `--fps` | `15` | 目标帧率 |
| `--mode` | `jpeg` | 推流模式 (jpeg/rgb565) |
| `--quality` | `60` | JPEG 压缩质量 |
| `--model` | llny 模型路径 | Live2D model3.json 路径 |
| `--exp-map` | `exp_map.json` | 表情映射配置文件路径 |
| `--character` | `llny` | 角色名 (llny/cat) |

#### 表情映射

| 命令 | llny 表情 | cat 表情 |
|------|-----------|----------|
| `idle` | 默认 | 默认 |
| `happy` | 比心 + 笑眼 | cat.exp3.json |
| `sad` | 哭 + 八字眉 | 3.exp3.json |
| `angry` | 生气 + 怒眉 | 2.exp3.json |
| `surprised` | 星星 + 大眼 | 4.exp3.json |
| `wave` | 比心 + 笑眼 | cat.exp3.json |
| `nod` | 默认 | 默认 |
| `think` | - - + 眼球偏移 | 默认 + 眼球偏移 |
| `sleep` | 闭眼 | 闭眼 |
| `talk` | 嘴巴张合动画 | sing + 嘴巴张合 |

#### Live2D 渲染器架构

```
┌─────────────────────────────────────────────────────┐
│  PC 端 (server/live2d)                              │
│                                                     │
│  ┌──────────────┐   ┌──────────┐   ┌────────────┐  │
│  │ Live2D Model │ → │ QOpenGL  │ → │ JPEG/RGB565│  │
│  │ (live2d-py)  │   │ 截帧     │   │ 编码       │  │
│  └──────────────┘   └──────────┘   └────────────┘  │
│         ↑                                ↓          │
│  表情/动画控制                    MQTT publish       │
│  (cmd topic)                     (stream topic)     │
└─────────────────────────────────────────────────────┘
```

#### 依赖清单

| 依赖 | 版本 | 用途 |
|------|------|------|
| `paho-mqtt` | >=2.0.0 | MQTT 客户端通信 |
| `Pillow` | >=10.0.0 | 图像裁剪/缩放/JPEG 编码 |
| `numpy` | >=1.24.0 | 帧缓冲区转 PIL Image / RGB565 转换 |
| `PyQt5` | >=5.15.0 | QOpenGLWidget 渲染容器 |
| `PyOpenGL` | >=3.1.6 | glClearColor 设置背景色 |
| `live2d-py` | >=0.5.3.5 | Live2D Cubism SDK Python 绑定 |

---

## Live2D 迁移说明

ESP32 端只负责 `JPEG 解码 → 显示`，完全不关心帧是谁渲染的。迁移到 Live2D 只需替换 PC 端渲染器，ESP32 固件零修改。

```
旧版：  Pillow 渲染 → JPEG → MQTT → ESP32 解码显示
当前：  Live2D 渲染 → JPEG → MQTT → ESP32 解码显示
                         ↑
                    ESP32 代码完全不变
```

渲染器接口保持一致：

```python
renderer.render() -> PIL.Image  # 返回 128x160 RGB 图像
```

### Live2D 模型资源

| 来源 | 说明 |
|------|------|
| 项目内置 | `Demo/Demo_Live2D/Live2D-Virtual-Girlfriend/Character/` 下有 llny 和 cat 两个模型 |
| Live2D 官方示例 | https://www.live2d.com/download/sample-data/ |
| nizima | https://nizima.com/ (免费/付费模型) |
| BOOTH | https://booth.pm/ (搜索 "Live2D moc3") |

---

## 踩坑记录与关键技术细节

### QOpenGLWidget 隐藏后不渲染（黑屏）

**现象**：MQTT 推流正常（15FPS），ESP32 端收到数据但显示黑屏，JPEG 帧仅 0.9KB（正常应 2-4KB）。

**根因**：`QOpenGLWidget.hide()` 后，Qt 不会为不可见 widget 调用 `paintGL()`，OpenGL 帧缓冲区始终为空。

**修复**：

```python
# 错误写法
self._canvas = _Live2DCanvas(...)
self._canvas.hide()  # paintGL 永远不会被调用

# 正确写法：show() + 移到屏幕外
self._canvas = _Live2DCanvas(...)
self._canvas.move(-10000, -10000)  # 移到屏幕外，用户看不到
self._canvas.show()                 # Qt 认为可见，会正常调用 paintGL

# 每帧渲染时强制重绘
self._canvas.repaint()              # 立即重绘（不是 update() 的延迟调度）
self._app.processEvents()           # 确保重绘完成后再截图
```

**诊断方法**：观察 JPEG 帧大小。0.9KB ≈ 纯黑图像，2-4KB ≈ 正常 Live2D 渲染。

### Live2D 模型在低分辨率画布上不可见

**现象**：在 128×160 的 QOpenGLWidget 上直接渲染 Live2D 模型，模型极小甚至不可见。

**根因**：Live2D 模型设计分辨率通常为 800×1600 左右，缩到 128×160 后模型只占画面极小区域。

**修复**：采用「大画布渲染 → 裁剪上半身 → 缩放输出」策略：

```
512×1024 画布渲染 → 裁剪顶部 38% → 居中裁切适配比例 → 缩放到 128×160
```

| `CROP_BOTTOM_RATIO` | 裁剪范围 | 效果 |
|---------------------|----------|------|
| `0.35` | 顶部 35% | 肩膀及以上（紧凑） |
| `0.38` | 顶部 38% | 前胸及以上（当前默认） |
| `0.42` | 顶部 42% | 腰部及以上（宽松） |
| `0.55` | 顶部 55% | 半身像（画面太小） |

### 颜色暗淡发灰

**现象**：Live2D 模型显示出来但颜色偏暗，细节不鲜明。

**根因**：`live2d.clearBuffer()` 默认清除为透明黑色 `(0, 0, 0, 0)`，模型边缘抗锯齿像素与黑色背景混合后变暗。

**修复**：在 `initializeGL()` 中设置 OpenGL 清除色为浅色暖白：

```python
from OpenGL import GL

def initializeGL(self):
    r, g, b = [c / 255.0 for c in (240, 235, 230)]
    GL.glClearColor(r, g, b, 1.0)

    live2d.glInit()
    self.model = live2d.LAppModel()
```

| 背景色 | RGB | 效果 |
|--------|-----|------|
| `(30, 30, 50)` | 深蓝黑 | 暗淡，模型边缘发黑 |
| `(240, 235, 230)` | 暖白 | 鲜艳自然，当前默认 |
| `(200, 220, 255)` | 浅蓝 | 清新风格 |
| `(0, 0, 0)` | 纯黑 | 模型边缘最暗 |

### 待机动画系统

6 个独立动画控制器：

| 控制器 | 驱动参数 | 动画效果 |
|--------|----------|----------|
| `BlinkController` | `ParamEyeLOpen/ROpen` | 自然眨眼，支持双眨（60%概率），sine 缓动 |
| `BreathController` | `ParamBreath` | 呼吸起伏，正弦波驱动 |
| `MouthController` | `ParamMouthOpenY` | TALK 状态嘴巴张合 |
| `EyeBallController` | `ParamEyeBallX/Y` | 眼球自然漂移 + 微颤（30Hz/25Hz 高频抖动） |
| `BodySwayController` | `ParamBodyAngleX/Y/Z` + `ParamAngleX/Y/Z` | 身体 X/Y/Z 轴轻微晃动 |
| `HeadTiltController` | `ParamAngleZ` | 头部歪斜，3 段缓动（偏→回→归位） |

关键设计决策：所有动画使用 `time.time()` 而非帧计数，保证不同帧率下动画速度一致；使用 sine/cubic 缓动避免机械感；间隔、幅度、方向均随机化。

### 渲染管线完整流程

```
每帧执行流程：
1. _update_animation()
   ├── BlinkController.update(model)      — 眨眼
   ├── BreathController.update(model)     — 呼吸
   ├── MouthController.update(model)      — 嘴巴
   ├── EyeBallController.update(model)    — 眼球
   ├── BodySwayController.update(model)   — 身体晃动
   ├── HeadTiltController.update(model)   — 头部倾斜
   └── _apply_state_params(model)         — 表情参数
2. _canvas.repaint()                      — 强制 Qt 重绘
3. _app.processEvents()                   — 等待重绘完成
4. _canvas.grab_frame()                   — grabFramebuffer 截帧
5. _crop_and_resize(img)                  — 裁剪上半身 + 缩放到 128×160
6. img_to_jpeg() / rgb888_to_rgb565_le()  — 编码
7. mqtt.publish()                         — 推流
```

---

## 纠错与性能优化

### MQTT 遗嘱消息（LWT）

设备异常断线时，MQTT Broker 自动发布 `{"state":"offline"}` 到 `luominest/s3/status`。

```c
esp_mqtt_client_config_t cfg = {
    .session.last_will = {
        .topic = "luominest/s3/status",
        .msg = "{\"state\":\"offline\"}",
        .qos = 1,
        .retain = true,
    },
    .session.keepalive = 30,
};
```

### 指数退避重连

| 模块 | 初始退避 | 最大退避 | 策略 |
|------|----------|----------|------|
| WiFi | 500 ms | 30 s | 2^n 递增 |
| MQTT | 1000 ms | 60 s | 2^n 递增 |

退避在连接成功后自动重置。WiFi 首次连接失败 10 次后进入后台自动重连模式。

### 帧去重（节约带宽）

- **服务端**：`FrameDedup` 类对编码后的帧数据做 MD5 采样比较（首尾各 512 字节），相同帧不发送。表情切换时自动重置去重状态。
- **嵌入式端**：`avatar_engine` 使用 FNV-1a 哈希对 JPEG 帧前 128 字节做快速比较，相同帧跳过解码。可通过 `CONFIG_LN_FRAME_DEDUP` 开关控制。

| 场景 | 原始带宽 | 去重后带宽 | 节省 |
|------|----------|-----------|------|
| 静态 idle | ~36 KB/s | ~2 KB/s | ~94% |
| 呼吸动画 | ~36 KB/s | ~30 KB/s | ~17% |
| 表情切换 | ~36 KB/s | ~36 KB/s | ~0% |

### 自适应 JPEG 质量

Live2D 渲染器在检测到连续 3 帧无变化时，自动降低 JPEG 质量（base_quality - 20，最低 30），表情切换时恢复原始质量。

### 看门狗定时器

通过 `CONFIG_LN_ENABLE_WATCHDOG` 启用，默认超时 30 秒。`lvgl_task` 和 `frame_decode_task` 均注册看门狗，每秒喂狗。任务卡死超过阈值后触发 panic 重启。

### 设备状态遥测

`status_task` 每 10 秒上报一次设备状态：

```json
{
  "state": "online",
  "rssi": -45,
  "heap": 234567,
  "psram": 6123456,
  "frames": {
    "rx": 1500,
    "show": 1480,
    "dedup": 15,
    "err": 2
  },
  "decode_ms": 35
}
```

### Kconfig 菜单配置

所有运行时配置已从硬编码迁移到 `Kconfig.projbuild`，通过 `idf.py menuconfig → LuomiNest Configuration` 修改：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `CONFIG_LN_WIFI_SSID` | `Xiaomi_65DF` | WiFi 名称 |
| `CONFIG_LN_WIFI_PASSWORD` | (空) | WiFi 密码 |
| `CONFIG_LN_MQTT_BROKER` | `mqtt://192.168.1.222:1883` | MQTT Broker |
| `CONFIG_LN_MQTT_CLIENT_ID` | `luominest_s3_01` | MQTT 客户端 ID |
| `CONFIG_LN_FRAME_QUEUE_SIZE` | `2` | 帧缓冲队列大小 |
| `CONFIG_LN_STATUS_INTERVAL_SEC` | `10` | 状态上报间隔（秒） |
| `CONFIG_LN_ENABLE_WATCHDOG` | `y` | 启用看门狗 |
| `CONFIG_LN_WATCHDOG_TIMEOUT_SEC` | `30` | 看门狗超时（秒） |
| `CONFIG_LN_MQTT_RECONNECT_MAX_MS` | `60000` | MQTT 最大重连退避（ms） |
| `CONFIG_LN_WIFI_RECONNECT_MAX_MS` | `30000` | WiFi 最大重连退避（ms） |
| `CONFIG_LN_FRAME_DEDUP` | `y` | 启用帧去重 |

---

## 项目目录结构

```
firmware/
  .gitignore                   # Git 忽略规则
  esp32-s3/                    # ESP32-S3 嵌入式固件 (ESP-IDF)
    main/
      main.c                   # 主入口（Kconfig 配置、看门狗、健康监控）
      app_mqtt.c/h             # MQTT 客户端（LWT、指数退避、状态机）
      wifi_mgr.c/h             # WiFi 管理器（指数退避、自动重连、RSSI）
      avatar_engine.c/h        # Avatar 引擎（JPEG 解码、帧去重、统计）
      st7735s.c/h              # ST7735S LCD 驱动
      lvgl_port.c/h            # LVGL 移植层
      pin_config.h             # GPIO 引脚定义
      Kconfig.projbuild        # 项目菜单配置
      CMakeLists.txt
      idf_component.yml
    CMakeLists.txt
    sdkconfig.defaults
    partitions.csv
  esp32-p4/                    # ESP32-P4 嵌入式固件 (ESP-IDF)
    components/
      audio/                   # 音频录制与播放
      display/                 # MIPI LCD 显示 + LVGL + UI 管理
      network/                 # MQTT 客户端 + WiFi 管理
      renderer/                # Avatar 引擎
      sensor/                  # 电池监测
    main/
      main.c                   # 主入口
      pin_config.h             # GPIO 引脚定义
      luominest_app.h
    configs/
      menuconfig.h
    CMakeLists.txt
    sdkconfig.defaults
    partitions.csv
  server/                      # PC 端渲染服务
    live2d/                    # Live2D 渲染器（当前版本）
      live2d_renderer.py       # Live2D 渲染 + 动画控制器
      stream_server.py         # MQTT 推流（帧去重、自适应质量）
      exp_map.json             # 表情映射配置
      requirements.txt
    pillow/                    # Pillow 渲染器（旧版）
      avatar_renderer.py
      stream_server.py         # MQTT 推流（帧去重）
      requirements.txt
    legacy/                    # 旧版服务端
      luominest_server.py
      requirements.txt
  config/                      # 配置文件
    mosquitto.conf             # Mosquitto MQTT Broker 配置
  Docs/                        # 项目文档
    esp32-s3-n16r8.md          # ESP32-S3 + ST7735S 硬件详细文档
```

---

## 官方文档参考

### ESP32-S3

| 文档 | 链接 |
|------|------|
| 技术规格书 (Datasheet) | https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf |
| 技术参考手册 (TRM) | https://www.espressif.com/sites/default/files/documentation/esp32-s3_technical_reference_manual_en.pdf |
| GPIO 参考 | https://docs.espressif.com/projects/esp-idf/zh_CN/v5.2.6/esp32s3/api-reference/peripherals/gpio.html |
| 开发板指南 | https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/hw-reference/esp32s3/user-guide-devkitc-1.html |

### ST7735S

| 文档 | 链接 |
|------|------|
| ST7735S 数据手册 | https://www.displayfuture.com/Display/datasheet/controller/ST7735.pdf |
| Sitronix 官网 | https://www.sitronix.com.tw/ |
