# LuomiNest Firmware

LuomiNest 桌面伴侣固件，基于 **ESP32-P4** 开发板。通过 MQTT 推流实现 PC 端 Live2D 渲染 → ESP32 端 JPEG 解码显示。

## 系统架构

```
┌──────────────────┐   MQTT publish    ┌──────────────┐   MQTT subscribe   ┌──────────────────┐
│   PC 渲染器      │ ────────────────→ │  Mosquitto   │ ─────────────────→ │  ESP32-P4 开发板  │
│  192.168.1.222   │  JPEG 帧          │  :1883       │  JPEG 帧           │  JPEG 解码显示    │
│  stream_server   │  10-15 FPS        │              │                    │  LVGL → MIPI LCD │
│  --device p4     │                   │              │                    │                  │
└──────────────────┘                   └──────────────┘                    └──────────────────┘
```

核心设计：ESP32 不关心帧是谁渲染的，只负责 JPEG 解码 + 显示。更换渲染器只需改 PC 端。

---

## 推流传输原理

### 方案选择

| 方案 | 原理 | 带宽需求 | 可行性 | 当前状态 |
|------|------|---------|--------|---------|
| **① 逐帧图片流** | PC 渲染 → JPEG 编码 → MQTT 传输 → ESP32 解码显示 | 中 (~225-450 KB/s) | ✅ 完全可行 | **已实现** |
| ② 小型视频流 | PC 渲染 → H.264/MJPEG 编码 → 传输 → ESP32 解码播放 | 低 (~10-30 KB/s) | ❌ ESP32-P4 无 H.264 硬解 | 未实现 |
| ③ ESP32 本地 Live2D | PC 发指令 → ESP32 运行 Live2D 渲染器 | 极低 (~100 B/s) | ❌ 无 GPU/OpenGL | 不可行 |
| ④ 预渲染帧集 | PC 预渲染 → 启动时一次性传输 → ESP32 本地播放 | 启动时高，运行时零 | 🟡 部分可行 | 未实现 |

**方案① 被选为当前方案**，原因：
- ESP32-P4 具备 JPEG 硬件解码能力（~2ms/帧）
- 每帧独立，丢帧不影响后续帧，容错性好
- 实现简单，延迟可控（50-100ms）
- 帧去重机制可大幅降低静态场景带宽

### 当前方案详解：逐帧 JPEG 图片流

#### 完整数据流路径

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          PC 端 (server)                                 │
│                                                                         │
│  Live2D 渲染器 (live2d_renderer.py)                                    │
│  ┌────────────────────────────────────────────┐                        │
│  │ PyQt5 + QOpenGLWidget                      │                        │
│  │ live2d-py 渲染模型                          │                        │
│  │ 眨眼/呼吸/眼球/身体晃动/头部倾斜             │                        │
│  └──────────┬─────────────────────────────────┘                        │
│             │ render()                                                  │
│             ▼                                                           │
│     PIL Image (512×1024)                                               │
│             │                                                           │
│             │ 裁剪 + 缩放                                               │
│             ▼                                                           │
│     PIL Image (400×540)                                                │
│             │                                                           │
│             │ ColorCorrector 色彩校正                                    │
│             │  ├─ Per-channel Gamma 校正 (LUT 查表)                     │
│             │  ├─ 对比度调整                                             │
│             │  └─ HSV 饱和度增强                                         │
│             ▼                                                           │
│     PIL Image (色彩校正后)                                               │
│             │                                                           │
│             ├─→ img_to_jpeg() ──→ JPEG bytes (~15-30 KB/帧)            │
│             └─→ rgb888_to_rgb565_le() ──→ RGB565 raw bytes (432 KB/帧)  │
│                         │                                                │
│     ┌───────────────────┘                                                │
│     ▼                                                                    │
│  MQTT publish (QoS=0, fire-and-forget)                                  │
│  Topic: luominest/p4/stream                                             │
│  帧去重: MD5 采样哈希比较，相同帧不重复发送                               │
└─────────────────────────────────────────────────────────────────────────┘
                            │
                            │ 局域网 MQTT (TCP 1883)
                            │ 纯内网通信，不经外网
                            ▼
                ┌───────────────────────┐
                │   MQTT Broker         │
                │   Mosquitto           │
                │   运行在局域网内       │
                │   (可以是 PC 本机)     │
                └───────────┬───────────┘
                            │
                            ▼
                ┌───────────────────────────┐
                │      ESP32-P4             │
                │                           │
                │  以太网(优先)/WiFi(热切换) │
                │       │                   │
                │  MQTT subscribe           │
                │  luominest/p4/stream      │
                │  luominest/p4/cmd         │
                │       │                   │
                │  ┌─────▼──────┐           │
                │  │ 帧缓冲拼接  │           │
                │  │ (MQTT 分片  │           │
                │  │  自动重组)   │           │
                │  └─────┬──────┘           │
                │        │                  │
                │  ┌─────▼──────────┐       │
                │  │ 硬件 JPEG 解码  │       │
                │  │ jpeg_decoder_   │       │
                │  │ process          │       │
                │  │ ~2-15ms/帧       │       │
                │  └─────┬──────────┘       │
                │        │                  │
                │  ┌─────▼──────────┐       │
                │  │ PPA 硬件裁剪    │       │
                │  │ 544→540行对齐   │       │
                │  │ 双帧缓冲交替    │       │
                │  └─────┬──────────┘       │
                │  ┌─────▼──────────┐       │
                │  │ MIPI DSI LCD   │       │
                │  │ 1024×600 IPS   │       │
                │  │ 双缓冲+VSync   │       │
                │  └────────────────┘       │
                │                           │
                │  free(frame_data) ←──────│
                │  帧数据立即释放            │
                └───────────────────────────┘
```

#### 帧数据生命周期：播放后即丢弃

每一帧数据在显示完成后**立即释放**，不缓存、不累积、不泄漏：

```
  MQTT 收到帧
       │
       ▼
  heap_caps_malloc(PSRAM)     ← 1. 在 PSRAM 中分配内存
       │
       ▼
  memcpy 到队列消息            ← 2. 拷贝数据（原始 MQTT 缓冲区可被覆盖）
       │
       ▼
  xQueueSend(frame_queue)     ← 3. 放入帧队列（队列满则丢弃最旧帧）
       │
       ▼
  xQueueReceive               ← 4. frame_decode_task 取出消息
       │
       ▼
  app_avatar_show_frame()     ← 5. JPEG 解码 → 写入 LVGL frame_buf
       │
       ▼
  free(msg.data)              ← 6. ★ 立即释放原始帧数据 ★
       │
       ▼
  LVGL frame_buf 中的像素     ← 7. 在下一帧到来时被覆盖（循环复用）
```

**唯一常驻内存**：LVGL 的 frame_buf（432KB），在每帧解码时被覆盖复用。

#### 帧去重机制

两端均实现帧去重，静态 idle 场景可节省 ~94% 带宽：

- **PC 端**（`stream_server.py`）：MD5 采样哈希，相同帧不发送
- **ESP32 端**（`components/app/app_avatar.c`）：FNV-1a 头部+尾部采样哈希，相同帧跳过解码

#### MQTT 分片重组

P4 的 JPEG 帧较大（15-30KB），可能超过单个 MQTT 数据事件的大小。`components/app/app_mqtt.c` 实现了自动分片重组：

```c
// MQTT 分片自动重组
if (event->current_data_offset == 0) {
    stream_buf_reset();                    // 新帧开始
}
stream_buf_ensure(event->total_data_len);  // 确保 PSRAM 缓冲够大
memcpy(s_stream_buf + s_stream_buf_len, event->data, event->data_len);
s_stream_buf_len += event->data_len;

if (s_stream_buf_len >= event->total_data_len) {
    s_stream_cb(s_stream_topic, s_stream_buf, s_stream_buf_len);  // 完整帧回调
}
```

### 网络流量分析

#### 纯局域网，零外网流量

所有通信都在局域网内完成：

```
PC (192.168.1.x) ←→ 路由器 (192.168.1.1) ←→ ESP32-P4 (192.168.1.y)
         │                                           │
         └──── MQTT Broker (192.168.1.222) ──────────┘
                    完全在局域网内
```

- MQTT Broker 默认地址 `192.168.1.222` 是**私有 IP**
- Broker 可以运行在 PC 本机（`localhost`）或局域网内任何设备
- 所有数据包不经过 WAN 口，**零外网流量，零流量费用**
- 即使断开外网，只要路由器通电，系统正常工作

#### 带宽估算

| 场景 | 编码 | 每帧大小 | 每秒流量 (15fps) | 每分钟 | 每小时 |
|------|------|---------|-----------------|--------|--------|
| P4 | JPEG Q=80 | ~15-30 KB | ~225-450 KB/s | ~13.5-27 MB | ~810 MB-1.6 GB |
| P4 | RGB565 | 432 KB | ~6.5 MB/s | ~390 MB | ~23 GB |

**推荐**：JPEG 模式（当前默认），约 337KB/s，普通家用路由器完全够用。

#### QoS 策略

| Topic | QoS | 原因 |
|-------|-----|------|
| `*/stream` | 0 | 丢帧可接受，下一帧马上到，低延迟优先 |
| `*/cmd` | 1 | 指令不能丢，必须送达 |
| `*/status` | 1 | 设备状态需可靠传输 |
| `*/mode` | 1 | 模式切换需可靠传输 |

### 端到端延迟分析

```
PC 渲染一帧 (~5ms)
    → 色彩校正 (~1ms)
    → JPEG 编码 (~2ms)
    → MQTT publish (QoS=0, <1ms)
    → 网络传输 (局域网 <1ms)
    → MQTT broker 转发 (<1ms)
    → ESP32 MQTT 接收 (<1ms)
    → 帧队列等待 (0-66ms, 取决于队列深度)
    → JPEG 解码 (~5ms)
    → LVGL 刷新 (下次 vsync)
    → LCD 显示
```

**总延迟**：约 10-80ms（主要取决于帧队列等待和 vsync 时机）

---

## 色彩校正系统

PC 端渲染的图像与 ESP32 屏幕显示之间存在色差，原因有多层叠加。统一服务端内置了 `ColorCorrector` 色彩校正类，按设备配置自动校正。

### 色差根因分析

| # | 根因 | 严重度 |
|---|------|--------|
| 1 | **P4 硬件 JPEG 解码器 BGR 顺序错误** — 红蓝通道互换 | 🔴 极严重（已修复） |
| 2 | **JPEG 4:2:0 色度子采样** — 色度分辨率仅为亮度 1/4 | 🟡 中等 |
| 3 | **RGB888→RGB565 量化损失** — R/B 只保留 5 位（32 级），渐变出现色带 | 🟡 中等 |
| 4 | **LCD 色域差异** — JD9165 (IPS, 60-70% NTSC) | 🟠 较明显 |

### 已实施的修复

#### 1. 硬件 JPEG BGR 顺序修复

`components/app/app_avatar.c` 中 `JPEG_DEC_RGB_ELEMENT_ORDER_BGR` → `JPEG_DEC_RGB_ELEMENT_ORDER_RGB`。这是色差最严重的原因，红蓝通道完全互换。

#### 2. Per-device 色彩校正管线

`ColorCorrector` 类在渲染管线中执行三步校正：

```
原始渲染帧 → 对比度调整 → Per-channel Gamma 校正 (LUT) → HSV 饱和度增强 → 输出
```

当前设备（JD9165）参数：

| 参数 | 值 | 说明 |
|------|-----|------|
| `saturation_boost` | 1.20 | IPS 面板饱和度补偿 |
| `gamma_r/g/b` | 1.0/1.0/1.0 | Per-channel Gamma，可微调偏色 |
| `contrast` | 1.05 | 对比度补偿 |

#### 3. Floyd-Steinberg 抖动模式

新增 `rgb565_dither` 传输模式，使用误差扩散算法将 RGB888 转为 RGB565，有效消除色带（banding）伪影：

```powershell
# 切换到抖动模式（消除色带，但带宽需求大于 JPEG）
mosquitto_pub -h 192.168.1.222 -t "luominest/p4/mode" -m "rgb565_dither"
```

### 色彩微调指南

如果仍有色差，可编辑 `server/live2d_renderer.py` 中的 `DEVICE_PROFILES`：

- **偏红**：增大 `gamma_r`（如 1.1），减少红色输出
- **偏绿**：增大 `gamma_g`（如 1.1），减少绿色输出
- **偏蓝**：增大 `gamma_b`（如 1.1），减少蓝色输出
- **偏灰/对比度不足**：增大 `contrast`（如 1.15）
- **颜色不够鲜艳**：增大 `saturation_boost`
- **JPEG 色差明显**：提高 `jpeg_quality`（可从 80 提到 85-90）

---

## 开发板规格

| 特性 | ESP32-P4 |
|------|----------|
| **CPU** | RISC-V 双核 400MHz |
| **SRAM** | 768 KB |
| **PSRAM** | 32 MB (Octal, 200MHz) |
| **Flash** | 16 MB |
| **WiFi** | 无（需 ESP-Hosted + ESP32-C6） |
| **以太网** | **内置 EMAC (RMII, 10/100M)** |
| **显示接口** | **MIPI DSI**（硬件 DPI） |
| **显示屏** | 10.1" JC1060P470C (1024×600) |
| **JPEG 解码** | **硬件 ~2ms/帧** |
| **2D 加速** | **PPA 像素加速器** |
| **帧缓冲** | **双帧缓冲交替 + PPA 硬件裁剪** |
| **LVGL 模式** | **双缓冲 + 防撕裂, FULL** |
| **网络优先级** | **以太网优先 → WiFi 热切换** |
| **时钟同步** | **SNTP (CST-8) + 状态栏时钟** |
| **JPEG 质量** | 80 (~15-30KB/帧) |
| **色彩校正** | 饱和度 1.20 + 对比度 1.05 |
| **目标应用** | 中控屏、桌面伴侣 |
| **MQTT Topic** | `luominest/p4/*` |

**特点**：
- 10.1 英寸 IPS 大屏，1024×600 分辨率，色彩鲜艳
- MIPI DSI 高带宽显示接口（1.5Gbps）
- 硬件 JPEG 解码，每帧仅 ~2ms
- 双帧缓冲交替 + PPA 硬件裁剪，解码与显示完全并行
- 双缓冲 + VSync 防撕裂，画面无撕裂
- 以太网优先（延迟更低、带宽更稳定），WiFi 热切换备用
- SNTP 时钟同步（CST-8），状态栏实时显示时间
- 可选 C6 协调器 SPI 帧转发，降低 MQTT 中转延迟
- 32MB PSRAM，可承载更复杂的 UI 和缓冲
- 右上角实时显示网络状态（连接类型、IP 地址、信号强度、时钟）

---

## 项目结构

```
firmware/
  embedded/
    esp32-p4/                      # P4 固件主工程
      components/                  # 组件化架构
        app/                       # 应用层组件
          app_main.c               # 主入口（网络优先级、UI 状态指示、SNTP、SPI）
          app_mqtt.c/h             # MQTT 客户端（分片重组）
          app_avatar.c/h           # Avatar 引擎（硬件 JPEG 解码 + PPA 裁剪 + 双帧缓冲）
          app_ui.c/h               # UI 主框架
          app_status.c/h           # 状态指示
          app_chat.c/h             # 聊天应用
          app_spi_recv.c/h         # SPI 帧接收
          frame_player.c/h         # 帧播放器
          settings_ui.c/h          # 设置 UI
          web_config.c/h           # AP 配置 Web 服务器
          time_mgr.c/h             # SNTP 时间同步 (CST-8)
        bsp/                       # 板级支持包
          bsp_eth.c/h              # 以太网管理（EMAC + RMII）
          bsp_lcd.c/h              # MIPI DSI LCD 驱动 (JD9165, 双帧缓冲)
          bsp_sd.c/h               # SD 卡驱动
          bsp_spi_p4.c/h           # SPI 外设驱动
          bsp_touch.c/h            # 触摸驱动 (GT911)
          bsp_pins.h               # GPIO 引脚定义（含以太网 + SPI）
        drivers/                   # 底层驱动
          drv_jpeg.c/h             # JPEG 硬件解码驱动
          drv_spi_master.c/h       # SPI Master 驱动
      main/
        app_main.c                 # 主函数入口
        test_400x540.jpg           # 测试图片
        CMakeLists.txt
        idf_component.yml
      .clangd                      # clangd 配置
      CMakeLists.txt
      idf_component.yml            # 顶层组件依赖
      partitions.csv
      sdkconfig.defaults
  .gitignore
  README.md
```

---

## 构建与烧录

### 环境准备

```powershell
# 加载 ESP-IDF 环境（必须！）
. "C:\Espressif\tools\Microsoft.v5.5.3.PowerShell_profile.ps1"
```

### ESP32-P4

```powershell
# 1. 加载 ESP-IDF 环境
. "C:\Espressif\tools\Microsoft.v5.5.3.PowerShell_profile.ps1"

# 2. 进入项目目录
cd C:\Users\lumin\Projects\Project\LuomiNest\firmware\embedded\esp32-p4

# 3. 清理编译文件（快速清理）
rm -Recurse -Force .\build, .\sdkconfig

# 4. 完全深度清理
idf.py fullclean
Remove-Item -Path build, sdkconfig, sdkconfig.old -Recurse -Force
Remove-Item -Path "managed_components" -Recurse -Force

# 5. 设置目标芯片
idf.py set-target esp32p4

# 6. 打开配置界面
idf.py menuconfig

# 7. 编译构建
idf.py build

# 8. 查看电脑可用串口
mode

# 9. 烧录并串口监控（根据实际端口修改 COM 号）
idf.py -p COM4 flash monitor

# 10. 仅烧录（不打开监控）
idf.py -p COM4 flash
```

### 首次构建（完全清理）

```powershell
rm -Recurse -Force .\build, .\sdkconfig
idf.py set-target esp32p4
idf.py build
```

---

## PC 端渲染器

### 统一渲染服务

服务端通过 `--device p4` 参数选择目标设备：

```powershell
cd C:\Users\lumin\Projects\Project\LuomiNest\firmware\server

# 首次设置
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# P4 模式（400×540, JPEG quality=80）
python stream_server.py --broker 192.168.1.222 --fps 10 --device p4

# 使用 Floyd-Steinberg 抖动模式（消除色带伪影）
python stream_server.py --broker 192.168.1.222 --fps 15 --device p4 --mode rgb565_dither

# 禁用帧去重
python stream_server.py --broker 192.168.1.222 --fps 15 --device p4 --no-dedup
```

### 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--broker` | `192.168.1.222` | MQTT Broker 地址 |
| `--port` | `1883` | MQTT Broker 端口 |
| `--fps` | `15` | 目标帧率 |
| `--mode` | `jpeg` | 推流模式：`jpeg` / `rgb565` / `rgb565_dither` |
| `--quality` | 设备配置 | JPEG 压缩质量 (1-100) |
| `--model` | llny 模型路径 | Live2D model3.json 路径 |
| `--exp-map` | `exp_map.json` | 表情映射配置文件路径 |
| `--character` | `llny` | 角色名 |
| `--device` | `p4` | 目标设备：`p4` (400×540) |
| `--no-dedup` | 关 | 禁用帧去重 |

### 设备配置

| 参数 | `--device p4` |
|------|---------------|
| 输出分辨率 | 400×540 |
| 渲染分辨率 | 512×1024 |
| 裁剪底部 | 0.55 (半身) |
| JPEG 质量 | 80 |
| 饱和度增强 | 1.20 |
| 对比度 | 1.05 |
| MQTT Topic | `luominest/p4/*` |

### 传输模式对比

| 模式 | 说明 | 优点 | 缺点 |
|------|------|------|------|
| `jpeg` | JPEG 压缩传输 | 带宽低，~15-30KB/帧 | YCbCr 色度子采样，有轻微色差 |
| `rgb565` | RGB565 原始传输 | 无 JPEG 色差 | 带宽高，~432KB/帧 |
| `rgb565_dither` | RGB565 + Floyd-Steinberg 抖动 | 无 JPEG 色差 + 无色带伪影 | 带宽同 rgb565，计算量略大 |

### 表情控制命令

```powershell
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h 192.168.1.222 -t "luominest/p4/cmd" -m "happy"
```

可用命令：`happy` `sad` `angry` `surprised` `wave` `think` `sleep` `talk` `idle`

---

## MQTT Topic

| Topic | 方向 | 格式 | 说明 |
|-------|------|------|------|
| `luominest/p4/cmd` | PC → ESP32+PC | UTF-8 | 表情命令 |
| `luominest/p4/mode` | PC → PC | UTF-8 | 传输模式 (jpeg/rgb565/rgb565_dither) |
| `luominest/p4/stream` | PC → ESP32 | JPEG/RGB565 二进制 | 视频帧 |
| `luominest/p4/status` | ESP32 → PC | JSON | 设备状态 |
| `luominest/p4/audio/rx` | PC → ESP32 | PCM 二进制 | TTS 音频播放 |
| `luominest/p4/audio/tx` | ESP32 → PC | PCM 二进制 | 麦克风录音 |

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

---

## 性能指标

| 指标 | ESP32-P4 (1024×600) |
|------|--------------------|
| JPEG 解码 | 硬件 ~2ms |
| 帧拷贝 | PPA 硬件裁剪 ~0.1ms |
| 帧缓冲 | 双帧缓冲交替 |
| JPEG 质量 | 80 (~15-30KB/帧) |
| 显示带宽 | MIPI DSI 1.5Gbps |
| 帧率 | 10-15 FPS（受 MQTT 带宽限制） |
| 色彩校正 | 饱和度 1.20 + 对比度 1.05 |
| RGB565 帧大小 | 432 KB |
| 网络连接 | 以太网优先 + WiFi 备用 |
| LVGL 渲染 | 双缓冲 FULL + 防撕裂 |
| 屏幕撕裂 | 无（VSync 页面翻转） |
| CPU 频率 | 400 MHz |
| 核心分配 | Core0:主+触控 / Core1:解码 |

---

## 关键技术细节

### 硬件 JPEG 解码 16 字节对齐

ESP32-P4 硬件 JPEG 解码器输出按 16 字节边界对齐。当图像高度不是 16 的倍数时，输出缓冲区需按对齐高度分配，解码后逐行拷贝有效数据到帧缓冲。

### 硬件 JPEG 解码 RGB 顺序

P4 硬件 JPEG 解码器的 `rgb_order` 必须设为 `JPEG_DEC_RGB_ELEMENT_ORDER_RGB`（而非 BGR），否则红蓝通道互换。MIPI LCD 的 DPI 配置使用 `ESP_LCD_COLOR_SPACE_RGB`，两者必须一致。

### LVGL 防撕裂

DPI 面板分配双帧缓冲（`num_fbs=2`），LVGL 渲染到一个缓冲时 DPI 面板从另一个读取，VSync 信号到来时交换缓冲。需要 `avoid_tearing=true` + `full_refresh=true` + `sw_rotate=false`。

### 网络优先级与热切换

1. 先初始化以太网（EMAC + RMII），等待连接（8 秒超时）
2. 以太网连接成功 → 使用以太网启动 MQTT + SNTP，WiFi 预初始化备用
3. 以太网超时 → 回退到 WiFi（ESP-Hosted via C6）
4. WiFi 也失败 → 启动 AP 配置模式
5. **运行时热切换**：ETH 断开 → 自动 WiFi 连接；ETH 恢复 → 断开 WiFi 回到 ETH
6. WiFi 断开时若 ETH 在线则忽略，避免误切换

### PPA 硬件加速帧拷贝

ESP32-P4 内置 PPA（Pixel Processing Accelerator），支持 2D blit/rotate/scale/色彩转换。当前用于替代 CPU `memcpy` 裁剪 JPEG 解码后的对齐填充行（544→540），速度提升 5-10 倍，且不占 CPU。

### 双帧缓冲策略

Avatar 引擎使用两个 `lv_draw_buf_t` 交替写入：解码写入 `write_buf`，LVGL 显示 `display_buf`，解码完成后交换索引。这样 JPEG 解码/PPA 裁剪与 LVGL DMA 传输完全并行，帧率提升 20-30%。

### SNTP 时钟同步

网络连接成功后自动启动 SNTP 客户端（ntp.aliyun.com + pool.ntp.org），同步 UTC+8 时间。状态栏每秒刷新时钟显示，未同步时显示 `--:--`。

### C6 协调器 SPI 帧转发（可选）

```
PC → MQTT Broker → ESP32-C6 (接收 JPEG 帧) → SPI 40MHz → ESP32-P4 (解码+显示)
```

C6 专司网络接收，P4 专注于 JPEG 解码和显示渲染。帧协议：`[0xAA][0x55][len:4bytes][JPEG data][CRC16:2bytes]`。P4 通过 GPIO6 握手信号检测 C6 是否有帧待发送。

### 帧去重

服务端和嵌入式端均实现帧去重（MD5/FNV-1a 哈希比较），静态 idle 场景可节省 ~94% 带宽。ESP32 端采样头部 64 字节 + 尾部 64 字节，兼顾表情变化（头部）和背景变化（尾部）。

### 指数退避重连

WiFi 和 MQTT 均实现指数退避重连（初始 500ms/1000ms，最大 30s/60s），连接成功后自动重置。

---

## 官方文档参考

### ESP32-P4

| 文档 | 链接 |
|------|------|
| 技术规格书 | https://www.espressif.com/sites/default/files/documentation/esp32-p4_datasheet_en.pdf |
| 技术参考手册 | https://www.espressif.com/sites/default/files/documentation/esp32-p4_technical_reference_manual_en.pdf |
| MIPI DSI API | https://docs.espressif.com/projects/esp-idf/en/latest/esp32p4/api-reference/peripherals/lcd/dsi.html |
| 以太网 EMAC | https://docs.espressif.com/projects/esp-idf/en/latest/esp32p4/api-reference/network/esp_eth.html |
| JPEG 硬件解码 | https://docs.espressif.com/projects/esp-idf/en/latest/esp32p4/api-reference/peripherals/jpeg.html |
| ESP-Hosted | https://docs.espressif.com/projects/esp-idf/en/latest/esp32p4/api-guides/esp-hosted.html |
