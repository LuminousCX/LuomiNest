# LuomiNest Firmware

Live2D 桌面伴侣固件，支持 **ESP32-S3** 和 **ESP32-P4** 两款开发板。通过 MQTT 推流实现 PC 端 Live2D 渲染 → ESP32 端 JPEG 解码显示。

## 系统架构

```
┌──────────────────┐   MQTT publish    ┌──────────────┐   MQTT subscribe   ┌──────────────────┐
│   PC 渲染器      │ ────────────────→ │  Mosquitto   │ ─────────────────→ │  ESP32 开发板     │
│  192.168.1.222   │  JPEG 帧          │  :1883       │  JPEG 帧           │  JPEG 解码显示    │
│  stream_server   │  10-15 FPS        │              │                    │  LVGL → LCD      │
│  --device p4/s3  │                   │              │                    │                  │
└──────────────────┘                   └──────────────┘                    └──────────────────┘
```

核心设计：ESP32 不关心帧是谁渲染的，只负责 JPEG 解码 + 显示。更换渲染器只需改 PC 端。

---

## 两个开发板对比

| 特性 | ESP32-S3 N16R8 | ESP32-P4 |
|------|----------------|----------|
| **CPU** | Xtensa LX7 双核 240MHz | RISC-V 双核 400MHz |
| **SRAM** | 512 KB | 768 KB |
| **PSRAM** | 8 MB (Octal, 80MHz) | 32 MB (Octal, 200MHz) |
| **Flash** | 16 MB | 16 MB |
| **WiFi** | 内置 WiFi4 + BT5.0 | 无（需 ESP-Hosted + ESP32-C6） |
| **以太网** | 无 | **内置 EMAC (RMII, 10/100M)** |
| **显示接口** | SPI（软件驱动） | **MIPI DSI**（硬件 DPI） |
| **显示屏** | 1.8" ST7735S (128×160) | 10.1" JC1060P470C (1024×600) |
| **JPEG 解码** | 软件 ~60ms/帧 | **硬件 ~2ms/帧** |
| **2D 加速** | 无 | **PPA 像素加速器** |
| **LVGL 模式** | 单缓冲, PARTIAL | **双缓冲 + 防撕裂, FULL** |
| **网络优先级** | WiFi only | **以太网优先 → WiFi 备用** |
| **JPEG 质量** | 60 (~2.4KB/帧) | 80 (~30KB/帧) |
| **饱和度补偿** | 1.70 (ST7735S 偏淡) | 1.20 (IPS 屏色彩好) |
| **目标应用** | 小屏 IoT 终端 | 中控屏、桌面伴侣 |
| **MQTT Topic** | `luominest/s3/*` | `luominest/p4/*` |

### ESP32-S3 — 轻量小屏版

```
┌─────────────────────┐
│  ESP32-S3 N16R8     │
│  + ST7735S 128×160  │
│                     │
│  WiFi 内置          │
│  SPI 显示           │
│  软件 JPEG 解码     │
│  单缓冲渲染         │
└─────────────────────┘
```

**特点**：
- 体积小、成本低、WiFi 内置即插即用
- 1.8 英寸小屏，适合桌面小摆件
- SPI 驱动 LCD，带宽有限（15MHz）
- 软件 JPEG 解码，每帧 ~60ms
- 单缓冲 PARTIAL 渲染，简单可靠

### ESP32-P4 — 高性能大屏版

```
┌─────────────────────────────────┐
│  ESP32-P4                       │
│  + JC1060P470C 1024×600 IPS     │
│                                 │
│  EMAC 以太网 (优先)             │
│  WiFi via ESP-Hosted + C6       │
│  MIPI DSI 显示                  │
│  硬件 JPEG 解码 (~2ms)          │
│  双缓冲 + VSync 防撕裂          │
│  PPA 2D 加速器                  │
│  32MB PSRAM                     │
└─────────────────────────────────┘
```

**特点**：
- 10.1 英寸 IPS 大屏，1024×600 分辨率，色彩鲜艳
- MIPI DSI 高带宽显示接口（1.5Gbps）
- 硬件 JPEG 解码，每帧仅 ~2ms
- 双帧缓冲 + VSync 防撕裂，画面无撕裂
- 以太网优先（延迟更低、带宽更稳定），WiFi 备用
- 32MB PSRAM，可承载更复杂的 UI 和缓冲
- 右上角实时显示网络状态（连接类型、IP 地址、信号强度）

---

## 项目结构

```
firmware/
  esp32-s3/                        # S3 固件
    main/
      main.c                       # 主入口
      app_mqtt.c/h                 # MQTT 客户端
      wifi_mgr.c/h                 # WiFi 管理（内置 WiFi）
      avatar_engine.c/h            # Avatar 引擎（软件 JPEG 解码）
      st7735s.c/h                  # ST7735S SPI LCD 驱动
      lvgl_port.c/h                # LVGL 移植层
      web_config.c/h               # AP 配置 Web 服务器
      pin_config.h                 # GPIO 引脚定义
      Kconfig.projbuild            # 项目配置菜单
      CMakeLists.txt
      idf_component.yml
    CMakeLists.txt
    sdkconfig.defaults
    partitions.csv

  esp32-p4/                        # P4 固件
    main/
      main.c                       # 主入口（网络优先级、UI 状态指示）
      app_mqtt.c/h                 # MQTT 客户端
      wifi_mgr.c/h                 # WiFi 管理（ESP-Hosted）
      eth_mgr.c/h                  # 以太网管理（EMAC + RMII）
      avatar_engine.c/h            # Avatar 引擎（硬件 JPEG 解码 + 16字节对齐）
      mipi_lcd.c/h                 # MIPI DSI LCD 驱动 (JD9165, 双帧缓冲)
      web_config.c/h               # AP 配置 Web 服务器
      pin_config.h                 # GPIO 引脚定义（含以太网）
      Kconfig.projbuild            # 项目配置菜单（含 PHY 选择）
      CMakeLists.txt
      idf_component.yml
    CMakeLists.txt
    sdkconfig.defaults
    partitions.csv

  server/                          # PC 端渲染服务
    live2d/                        # Live2D 渲染器（当前版本）
      live2d_renderer.py
      stream_server.py
      exp_map.json
      requirements.txt
    pillow/                        # Pillow 渲染器（旧版）
      avatar_renderer.py
      stream_server.py
      requirements.txt
    legacy/                        # 旧版服务端
      luominest_server.py
      requirements.txt

  config/
    mosquitto.conf                 # Mosquitto MQTT Broker 配置

  Docs/                            # 项目文档
    esp32-p4-jc1060p470c.md        # P4 硬件详细文档 + 踩坑记录
```

---

## 构建与烧录

### 环境准备（通用）

```powershell
# 加载 ESP-IDF 环境（必须！）
. "C:\Espressif\tools\Microsoft.v5.5.3.PowerShell_profile.ps1"
```

### ESP32-S3

```powershell
cd C:\Users\lumin\Projects\Project\LuomiNest\firmware\esp32-s3
idf.py set-target esp32s3   # 首次
idf.py build
idf.py -p COM3 flash monitor
```

### ESP32-P4

```powershell
cd C:\Users\lumin\Projects\Project\LuomiNest\firmware\esp32-p4
idf.py set-target esp32p4   # 首次
idf.py build
idf.py -p COM4 flash monitor
```

### 首次构建（完全清理）

```powershell
rm -Recurse -Force .\build, .\sdkconfig
idf.py set-target esp32p4    # 或 esp32s3
idf.py build
```

---

## PC 端渲染器

### Live2D 渲染器

```powershell
cd C:\Users\lumin\Projects\Project\LuomiNest\firmware\server\live2d

# 首次设置
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# P4 模式（1024×600, JPEG quality=80）
python stream_server.py --broker 192.168.1.222 --fps 10 --device p4

# S3 模式（128×160, JPEG quality=60）
python stream_server.py --broker 192.168.1.222 --fps 15 --device s3
```

### 表情控制命令

```powershell
# P4
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h 192.168.1.222 -t "luominest/p4/cmd" -m "happy"

# S3
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h 192.168.1.222 -t "luominest/s3/cmd" -m "happy"
```

可用命令：`happy` `sad` `angry` `surprised` `wave` `think` `sleep` `talk` `idle`

---

## MQTT Topic

| Topic | 方向 | 格式 | 说明 |
|-------|------|------|------|
| `luominest/{s3\|p4}/cmd` | PC → ESP32+PC | UTF-8 | 表情命令 |
| `luominest/{s3\|p4}/mode` | PC → PC | UTF-8 | 传输模式 (jpeg/rgb565) |
| `luominest/{s3\|p4}/stream` | PC → ESP32 | JPEG/RGB565 二进制 | 视频帧 |
| `luominest/{s3\|p4}/status` | ESP32 → PC | JSON | 设备状态 |
| `luominest/p4/audio/rx` | PC → ESP32 | PCM 二进制 | TTS 音频播放（P4 专属） |
| `luominest/p4/audio/tx` | ESP32 → PC | PCM 二进制 | 麦克风录音（P4 专属） |

---

## Mosquitto 配置

```powershell
# 配置文件
C:\Program Files\mosquitto\mosquitto.conf

# 关键配置
listener 1883 0.0.0.0
allow_anonymous true
message_size_limit 0
max_inflight_messages 200
max_queued_messages 1000

# 重启
net stop mosquitto
net start mosquitto
```

项目内保留了配置副本：[config/mosquitto.conf](config/mosquitto.conf)

---

## 性能对比

| 指标 | ESP32-S3 (128×160) | ESP32-P4 (1024×600) |
|------|--------------------|--------------------|
| JPEG 解码 | 软件 ~60ms | 硬件 ~2ms |
| JPEG 质量 | 60 (~2.4KB/帧) | 80 (~30KB/帧) |
| 显示带宽 | SPI 15MHz | MIPI DSI 1.5Gbps |
| 帧率 | 15 FPS | 10-15 FPS（受 MQTT 带宽限制） |
| 饱和度补偿 | 1.70 (ST7735S 偏淡) | 1.20 (IPS 屏色彩好) |
| RGB565 帧大小 | 40 KB | 1.2 MB |
| 网络连接 | WiFi only | 以太网优先 + WiFi 备用 |
| LVGL 渲染 | 单缓冲 PARTIAL | 双缓冲 FULL + 防撕裂 |
| 屏幕撕裂 | 有（无同步机制） | 无（VSync 页面翻转） |

---

## 关键技术细节

### P4 硬件 JPEG 解码 16 字节对齐

ESP32-P4 硬件 JPEG 解码器输出按 16 字节边界对齐。当图像高度不是 16 的倍数时，输出缓冲区需按对齐高度分配，解码后逐行拷贝有效数据到帧缓冲。

### P4 LVGL 防撕裂

DPI 面板分配双帧缓冲（`num_fbs=2`），LVGL 渲染到一个缓冲时 DPI 面板从另一个读取，VSync 信号到来时交换缓冲。需要 `avoid_tearing=true` + `full_refresh=true` + `sw_rotate=false`。

### P4 网络优先级

1. 先初始化以太网（EMAC + RMII），等待连接（8 秒超时）
2. 以太网连接成功 → 使用以太网启动 MQTT
3. 以太网超时 → 回退到 WiFi（ESP-Hosted via C6）
4. WiFi 也失败 → 启动 AP 配置模式

### S3 SPI 显示驱动

ST7735S 使用 SPI 接口，关键点：必须使用软件 CS（硬件 CS 在传输间隙自动拉高会导致花屏），SPI 频率 15MHz。

### 帧去重

服务端和嵌入式端均实现帧去重（MD5/FNV-1a 哈希比较），静态 idle 场景可节省 ~94% 带宽。

### 指数退避重连

WiFi 和 MQTT 均实现指数退避重连（初始 500ms/1000ms，最大 30s/60s），连接成功后自动重置。

---

## 详细文档

| 文档 | 说明 |
|------|------|
| [Docs/esp32-p4-jc1060p470c.md](Docs/esp32-p4-jc1060p470c.md) | P4 硬件详细文档：引脚定义、EMAC 以太网、MIPI DSI、JPEG 对齐、防撕裂配置、踩坑记录 |

---

## 官方文档参考

### ESP32-S3

| 文档 | 链接 |
|------|------|
| 技术规格书 | https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf |
| 技术参考手册 | https://www.espressif.com/sites/default/files/documentation/esp32-s3_technical_reference_manual_en.pdf |

### ESP32-P4

| 文档 | 链接 |
|------|------|
| 技术规格书 | https://www.espressif.com/sites/default/files/documentation/esp32-p4_datasheet_en.pdf |
| 技术参考手册 | https://www.espressif.com/sites/default/files/documentation/esp32-p4_technical_reference_manual_en.pdf |
| MIPI DSI API | https://docs.espressif.com/projects/esp-idf/en/latest/esp32p4/api-reference/peripherals/lcd/dsi.html |
| 以太网 EMAC | https://docs.espressif.com/projects/esp-idf/en/latest/esp32p4/api-reference/network/esp_eth.html |
| JPEG 硬件解码 | https://docs.espressif.com/projects/esp-idf/en/latest/esp32p4/api-reference/peripherals/jpeg.html |
| ESP-Hosted | https://docs.espressif.com/projects/esp-idf/en/latest/esp32p4/api-guides/esp-hosted.html |
