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

## 推流传输原理

### 四种方案对比

在设计之初，我们考虑了四种将 Live2D 动画呈现到 ESP32 屏幕上的方案：

| 方案 | 原理 | 带宽需求 | 可行性 | 当前状态 |
|------|------|---------|--------|---------|
| **① 逐帧图片流** | PC 渲染 → JPEG 编码 → MQTT 传输 → ESP32 解码显示 | 中 (~75-337 KB/s) | ✅ 完全可行 | **已实现** |
| ② 小型视频流 | PC 渲染 → H.264/MJPEG 编码 → 传输 → ESP32 解码播放 | 低 (~10-30 KB/s) | ❌ ESP32 无 H.264 硬解 | 未实现 |
| ③ ESP32 本地 Live2D | PC 发指令 → ESP32 运行 Live2D 渲染器 | 极低 (~100 B/s) | ❌ 无 GPU/OpenGL | 不可行 |
| ④ 预渲染帧集 | PC 预渲染 → 启动时一次性传输 → ESP32 本地播放 | 启动时高，运行时零 | 🟡 部分可行 | 未实现 |

**方案① 被选为当前方案**，原因：
- ESP32-S3/P4 均有 JPEG 解码能力（S3 软解，P4 硬解）
- 每帧独立，丢帧不影响后续帧，容错性好
- 实现简单，延迟可控（50-100ms）
- 帧去重机制可大幅降低静态场景带宽

**方案② 不可行的原因**：
- ESP32-S3/P4 **没有 H.264 硬件解码器**，CPU 无法软解
- MJPEG 本质仍是逐帧 JPEG，无带宽优势
- 视频流有 I帧/P帧 依赖，丢帧会导致花屏
- 延迟更高（需等完整片段才能播放）

**方案③ 不可行的原因**：
- Live2D Cubism SDK 需要 **OpenGL ES 2.0+** 或 DirectX 11
- ESP32 **没有 GPU**，不支持任何 OpenGL 变体
- Live2D 运行时需要 50-200 MB 内存，ESP32 最多 32MB PSRAM
- Live2D 模型文件（.moc3 + 纹理）通常 5-25 MB

**方案④ 可探索的方向**：
- 启动时将所有表情的帧序列预渲染并传输到 PSRAM/SD 卡
- 运行时 PC 只发指令（如 `happy`），ESP32 从本地存储播放
- 优点：运行时零带宽；缺点：表情种类有限，无法动态变化

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
│     PIL Image (128×160 或 400×540)                                     │
│             │                                                           │
│             │ ColorCorrector 色彩校正                                    │
│             │  ├─ Per-channel Gamma 校正 (LUT 查表)                     │
│             │  ├─ 对比度调整                                             │
│             │  └─ HSV 饱和度增强                                         │
│             ▼                                                           │
│     PIL Image (色彩校正后)                                               │
│             │                                                           │
│             ├─→ img_to_jpeg() ──→ JPEG bytes                            │
│             │      S3: ~3-8 KB/帧   P4: ~15-30 KB/帧                   │
│             │                                                           │
│             ├─→ rgb888_to_rgb565_le() ──→ RGB565 raw bytes              │
│             │      S3: 40 KB/帧       P4: 432 KB/帧                     │
│             │                                                           │
│             └─→ rgb888_to_rgb565_dithered() ──→ RGB565 + Floyd-Steinberg│
│                    抖动，消除色带伪影                                     │
│                         │                                                │
│     ┌───────────────────┘                                                │
│     ▼                                                                    │
│  MQTT publish (QoS=0, fire-and-forget)                                  │
│  Topic: luominest/s3/stream 或 luominest/p4/stream                      │
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
              ┌─────────────┴─────────────┐
              ▼                           ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│      ESP32-S3             │   │      ESP32-P4             │
│                           │   │                           │
│  WiFi 连接路由器           │   │  以太网(优先)/WiFi(热切换) │
│       │                   │   │       │                   │
│  MQTT subscribe           │   │  MQTT subscribe / SPI帧  │
│  luominest/s3/stream      │   │  luominest/p4/stream     │
│  luominest/s3/cmd         │   │  luominest/p4/cmd         │
│       │                   │   │       │                   │
│  ┌─────▼──────┐           │   │  ┌─────▼──────┐           │
│  │ 帧队列      │           │   │  │ 帧缓冲拼接  │           │
│  │ (2 slots)  │           │   │  │ (MQTT 分片  │           │
│  └─────┬──────┘           │   │  │  自动重组)   │           │
│        │                  │   │  └─────┬──────┘           │
│  ┌─────▼──────────┐       │   │        │                  │
│  │ 软件 JPEG 解码  │       │   │  ┌─────▼──────────┐       │
│  │ esp_jpeg_decode │       │   │  │ 硬件 JPEG 解码  │       │
│  │ ~20-40ms/帧     │       │   │  │ jpeg_decoder_   │       │
│  └─────┬──────────┘       │   │  │ process          │       │
│        │                  │   │  │ ~2-15ms/帧       │       │
│  ┌─────▼──────────┐       │   │  └─────┬──────────┘       │
│  │ LVGL frame_buf │       │   │        │                  │
│  │ (RGB565, 40KB) │       │   │  ┌─────▼──────────┐       │
│  └─────┬──────────┘       │   │  │ PPA 硬件裁剪    │       │
│        │                  │   │  │ 544→540行对齐   │       │
│  ┌─────▼──────────┐       │   │  │ 双帧缓冲交替    │       │
│  │ ST7735S SPI LCD│       │   │  └─────┬──────────┘       │
│  │ 128×160        │       │   │  ┌─────▼──────────┐       │
│  │ 20MHz SPI      │       │   │  │ MIPI DSI LCD   │       │
│  └────────────────┘       │   │  │ 1024×600 IPS   │       │
│                           │   │  │ 双缓冲+VSync   │       │
│  free(frame_data) ←──────│   │  └────────────────┘       │
│  帧数据立即释放            │   │                           │
│                           │   │  free(frame_data) ←──────│
│                           │   │  帧数据立即释放            │
└───────────────────────────┘   └───────────────────────────┘
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
  avatar_engine_show_frame()  ← 5. JPEG 解码 → 写入 LVGL frame_buf
       │
       ▼
  free(msg.data)              ← 6. ★ 立即释放原始帧数据 ★
       │
       ▼
  LVGL frame_buf 中的像素     ← 7. 在下一帧到来时被覆盖（循环复用）
```

**关键代码**（ESP32-S3 [main.c](esp32-s3/main/main.c)，ESP32-P4 [main.c](esp32-p4/main/main.c)）：

```c
static void frame_decode_task(void *pvParameter) {
    frame_msg_t msg = {0};
    while (1) {
        if (xQueueReceive(s_frame_queue, &msg, pdMS_TO_TICKS(1000)) == pdTRUE) {
            avatar_engine_show_frame(msg.data, msg.len);  // 解码 + 显示
            free(msg.data);   // ← 立即释放！不缓存
            msg.data = NULL;
        }
    }
}
```

**唯一常驻内存**：LVGL 的 frame_buf（S3: 40KB，P4: 432KB），在每帧解码时被覆盖复用。

#### 帧去重机制

两端均实现帧去重，静态 idle 场景可节省 ~94% 带宽：

- **PC 端**（[stream_server.py](server/stream_server.py)）：MD5 采样哈希，相同帧不发送
- **ESP32 端**（[avatar_engine.c](esp32-s3/main/avatar_engine.c)）：FNV-1a 头部+尾部采样哈希，相同帧跳过解码

```
PC 端去重:
  渲染帧 → 采样 MD5 → 与上一帧比较 → 相同则跳过 publish

ESP32 端去重:
  收到帧 → FNV-1a 哈希头部64字节+尾部64字节 → 与上一帧比较 → 相同则跳过解码
```

#### MQTT 分片重组（P4 专属）

P4 的 JPEG 帧较大（15-30KB），可能超过单个 MQTT 数据事件的大小。P4 的 `app_mqtt.c` 实现了自动分片重组：

```c
// P4: MQTT 分片自动重组
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

S3 的帧较小（3-8KB），通常在单个 MQTT 事件中完整到达，无需重组。

### 网络流量分析

#### 纯局域网，零外网流量

所有通信都在局域网内完成：

```
PC (192.168.1.x) ←→ 路由器 (192.168.1.1) ←→ ESP32 (192.168.1.y)
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
| S3 | JPEG Q=70 | ~3-8 KB | ~45-120 KB/s | ~2.7-7.2 MB | ~162-432 MB |
| S3 | RGB565 | 40 KB | ~600 KB/s | ~36 MB | ~2.1 GB |
| P4 | JPEG Q=80 | ~15-30 KB | ~225-450 KB/s | ~13.5-27 MB | ~810 MB-1.6 GB |
| P4 | RGB565 | 432 KB | ~6.5 MB/s | ~390 MB | ~23 GB |

**推荐**：JPEG 模式（当前默认）。S3 约 75KB/s，P4 约 337KB/s，普通家用路由器完全够用。

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
    → JPEG 解码 (S3: ~40ms / P4: ~5ms)
    → LVGL 刷新 (下次 vsync)
    → LCD 显示
```

**总延迟**：S3 约 30-80ms，P4 约 10-80ms（主要取决于帧队列等待和 vsync 时机）

---

## 色彩校正系统

PC 端渲染的图像与 ESP32 屏幕显示之间存在色差，原因有多层叠加。统一服务端内置了 `ColorCorrector` 色彩校正类，按设备配置自动校正。

### 色差根因分析

| # | 根因 | 影响设备 | 严重度 |
|---|------|---------|--------|
| 1 | **P4 硬件 JPEG 解码器 BGR 顺序错误** — 红蓝通道互换 | ESP32-P4 | 🔴 极严重（已修复） |
| 2 | **JPEG 4:2:0 色度子采样** — 色度分辨率仅为亮度 1/4 | 两者 | 🟡 中等 |
| 3 | **RGB888→RGB565 量化损失** — R/B 只保留 5 位（32 级），渐变出现色带 | 两者 | 🟡 中等 |
| 4 | **ST7735S Gamma 偏淡** — TN 面板色域仅 ~45% NTSC | ESP32-S3 | 🟠 较明显 |
| 5 | **两屏色域差异** — ST7735S (TN, 45% NTSC) vs JD9165 (IPS, 60-70% NTSC) | 两者 | 🟠 较明显 |

### 已实施的修复

#### 1. P4 硬件 JPEG BGR 顺序修复

[avatar_engine.c](esp32-p4/main/avatar_engine.c) 中 `JPEG_DEC_RGB_ELEMENT_ORDER_BGR` → `JPEG_DEC_RGB_ELEMENT_ORDER_RGB`。这是 P4 色差最严重的原因，红蓝通道完全互换。

#### 2. Per-device 色彩校正管线

`ColorCorrector` 类在渲染管线中执行三步校正：

```
原始渲染帧 → 对比度调整 → Per-channel Gamma 校正 (LUT) → HSV 饱和度增强 → 输出
```

每个设备有独立的校正参数：

| 参数 | S3 (ST7735S) | P4 (JD9165) | 说明 |
|------|-------------|-------------|------|
| `saturation_boost` | 1.70 | 1.20 | ST7735S TN 面板偏淡，需要更强补偿 |
| `gamma_r/g/b` | 1.0/1.0/1.0 | 1.0/1.0/1.0 | Per-channel Gamma，可微调偏色 |
| `contrast` | 1.10 | 1.05 | 对比度补偿 |

#### 3. Floyd-Steinberg 抖动模式

新增 `rgb565_dither` 传输模式，使用误差扩散算法将 RGB888 转为 RGB565，有效消除色带（banding）伪影：

```powershell
# 切换到抖动模式（消除色带，但带宽需求大于 JPEG）
mosquitto_pub -h 192.168.1.222 -t "luominest/s3/mode" -m "rgb565_dither"
```

### 色彩微调指南

如果仍有色差，可编辑 [live2d_renderer.py](server/live2d_renderer.py) 中的 `DEVICE_PROFILES`：

- **偏红**：增大 `gamma_r`（如 1.1），减少红色输出
- **偏绿**：增大 `gamma_g`（如 1.1），减少绿色输出
- **偏蓝**：增大 `gamma_b`（如 1.1），减少蓝色输出
- **偏灰/对比度不足**：增大 `contrast`（如 1.15）
- **颜色不够鲜艳**：增大 `saturation_boost`
- **JPEG 色差明显**：提高 `jpeg_quality`（P4 可从 80 提到 85-90）

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
| **帧缓冲** | 单缓冲, PARTIAL | **双帧缓冲交替 + PPA 硬件裁剪** |
| **LVGL 模式** | 单缓冲, PARTIAL | **双缓冲 + 防撕裂, FULL** |
| **网络优先级** | WiFi only | **以太网优先 → WiFi 热切换** |
| **时钟同步** | 无 | **SNTP (CST-8) + 状态栏时钟** |
| **C6 协调器** | 无 | **SPI 帧转发 (可选)** |
| **JPEG 质量** | 70 (~3-8KB/帧) | 80 (~15-30KB/帧) |
| **色彩校正** | 饱和度 1.70 + 对比度 1.10 | 饱和度 1.20 + 对比度 1.05 |
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
- SPI 驱动 LCD，20MHz SPI + 直接写屏 + 双帧缓冲
- 软件 JPEG 解码，每帧 ~20-40ms（240MHz CPU）
- 双核并行：Core 0 LVGL 渲染，Core 1 JPEG 解码
- AP 配置门户：WiFi 扫描 + MQTT 设置 + Captive Portal

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
      main.c                       # 主入口（网络优先级、UI 状态指示、SNTP、SPI）
      app_mqtt.c/h                 # MQTT 客户端
      wifi_mgr.c/h                 # WiFi 管理（ESP-Hosted, 热切换, 异步连接）
      eth_mgr.c/h                  # 以太网管理（EMAC + RMII）
      avatar_engine.c/h            # Avatar 引擎（硬件 JPEG 解码 + PPA 裁剪 + 双帧缓冲）
      mipi_lcd.c/h                 # MIPI DSI LCD 驱动 (JD9165, 双帧缓冲)
      web_config.c/h               # AP 配置 Web 服务器（cJSON 安全解析）
      touch_driver.c/h             # 触摸驱动 (GT911)
      chat_ui.c/h                  # 聊天 UI
      settings_ui.c/h              # 设置 UI
      time_mgr.c/h                 # SNTP 时间同步 (CST-8)
      spi_frame_rx.c/h             # C6 协调器 SPI 帧接收
      pin_config.h                 # GPIO 引脚定义（含以太网 + SPI）
      Kconfig.projbuild            # 项目配置菜单（含 PHY 选择）
      CMakeLists.txt
      idf_component.yml
    CMakeLists.txt
    sdkconfig.defaults
    partitions.csv

  esp32-c6-coordinator/            # C6 协调器固件（可选）
    main/
      main.c                       # MQTT 订阅 + SPI Slave 帧转发
      Kconfig.projbuild
      CMakeLists.txt
    CMakeLists.txt
    sdkconfig.defaults
    partitions.csv

  server/                          # PC 端渲染服务（统一版本）
    live2d_renderer.py             # Live2D 渲染器 + 色彩校正系统
    stream_server.py               # MQTT 推流服务（支持 --device s3/p4）
    exp_map.json                   # 表情映射配置
    requirements.txt               # Python 依赖
    models/                        # Live2D 模型文件
      llny/                        # llny 角色
        mianfeimox/                # 模型数据（.model3.json + .moc3 + 纹理 + 表情）
      cat/                         # cat 角色
        whitecatfree_vts/          # 模型数据

  config/
    mosquitto.conf                 # Mosquitto MQTT Broker 配置

  Docs/                            # 项目文档
    esp32-s3-n16r8.md              # S3 硬件详细文档 + 踩坑记录
    esp32-p4-jc1060p470c.md        # P4 硬件详细文档 + 踩坑记录
    esp32p4单片机调查.md            # P4 迁移与 Live2D 可行性调查报告
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

### 统一渲染服务

服务端已合并为统一版本，通过 `--device` 参数选择目标设备：

```powershell
cd C:\Users\lumin\Projects\Project\LuomiNest\firmware\server

# 首次设置
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# P4 模式（400×540, JPEG quality=80）
python stream_server.py --broker 192.168.1.222 --fps 10 --device p4

# S3 模式（128×160, JPEG quality=70）
python stream_server.py --broker 192.168.1.222 --fps 15 --device s3

# 使用 Floyd-Steinberg 抖动模式（消除色带伪影）
python stream_server.py --broker 192.168.1.222 --fps 15 --device s3 --mode rgb565_dither

# 禁用帧去重
python stream_server.py --broker 192.168.1.222 --fps 15 --device s3 --no-dedup
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
| `--character` | `llny` | 角色名 (llny/cat) |
| `--device` | `s3` | 目标设备：`s3` (128×160) 或 `p4` (400×540) |
| `--no-dedup` | 关 | 禁用帧去重 |

### 设备配置对比

| 参数 | `--device s3` | `--device p4` |
|------|---------------|---------------|
| 输出分辨率 | 128×160 | 400×540 |
| 渲染分辨率 | 512×1024 | 512×1024 |
| 裁剪底部 | 0.38 (前胸) | 0.55 (半身) |
| JPEG 质量 | 70 | 80 |
| 饱和度增强 | 1.70 | 1.20 |
| 对比度 | 1.10 | 1.05 |
| MQTT Topic | `luominest/s3/*` | `luominest/p4/*` |

### 传输模式对比

| 模式 | 说明 | 优点 | 缺点 |
|------|------|------|------|
| `jpeg` | JPEG 压缩传输 | 带宽低，S3~3-8KB/帧，P4~15-30KB/帧 | YCbCr 色度子采样，有轻微色差 |
| `rgb565` | RGB565 原始传输 | 无 JPEG 色差 | 带宽高，S3~40KB/帧，P4~432KB/帧 |
| `rgb565_dither` | RGB565 + Floyd-Steinberg 抖动 | 无 JPEG 色差 + 无色带伪影 | 带宽同 rgb565，计算量略大 |

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
| `luominest/{s3\|p4}/mode` | PC → PC | UTF-8 | 传输模式 (jpeg/rgb565/rgb565_dither) |
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
| JPEG 解码 | 软件 ~20-40ms | 硬件 ~2ms |
| 帧拷贝 | CPU memcpy ~1ms | PPA 硬件裁剪 ~0.1ms |
| 帧缓冲 | 单缓冲 | 双帧缓冲交替 |
| JPEG 质量 | 70 (~3-8KB/帧) | 80 (~15-30KB/帧) |
| 显示带宽 | SPI 20MHz | MIPI DSI 1.5Gbps |
| 帧率 | 20-30 FPS | 10-15 FPS（受 MQTT 带宽限制） |
| 色彩校正 | 饱和度 1.70 + 对比度 1.10 | 饱和度 1.20 + 对比度 1.05 |
| RGB565 帧大小 | 40 KB | 432 KB |
| 网络连接 | WiFi only | 以太网优先 + WiFi 备用 |
| LVGL 渲染 | 直接写屏 + 双帧缓冲 | 双缓冲 FULL + 防撕裂 |
| 屏幕撕裂 | 有（无同步机制） | 无（VSync 页面翻转） |
| CPU 频率 | 240 MHz (双核并行) | 400 MHz |
| 核心分配 | Core0:LVGL / Core1:JPEG | Core0:主+触控 / Core1:解码 |

---

## 关键技术细节

### P4 硬件 JPEG 解码 16 字节对齐

ESP32-P4 硬件 JPEG 解码器输出按 16 字节边界对齐。当图像高度不是 16 的倍数时，输出缓冲区需按对齐高度分配，解码后逐行拷贝有效数据到帧缓冲。

### P4 硬件 JPEG 解码 RGB 顺序

P4 硬件 JPEG 解码器的 `rgb_order` 必须设为 `JPEG_DEC_RGB_ELEMENT_ORDER_RGB`（而非 BGR），否则红蓝通道互换。MIPI LCD 的 DPI 配置使用 `ESP_LCD_COLOR_SPACE_RGB`，两者必须一致。

### P4 LVGL 防撕裂

DPI 面板分配双帧缓冲（`num_fbs=2`），LVGL 渲染到一个缓冲时 DPI 面板从另一个读取，VSync 信号到来时交换缓冲。需要 `avoid_tearing=true` + `full_refresh=true` + `sw_rotate=false`。

### P4 网络优先级与热切换

1. 先初始化以太网（EMAC + RMII），等待连接（8 秒超时）
2. 以太网连接成功 → 使用以太网启动 MQTT + SNTP，WiFi 预初始化备用
3. 以太网超时 → 回退到 WiFi（ESP-Hosted via C6）
4. WiFi 也失败 → 启动 AP 配置模式
5. **运行时热切换**：ETH 断开 → 自动 WiFi 连接；ETH 恢复 → 断开 WiFi 回到 ETH
6. WiFi 断开时若 ETH 在线则忽略，避免误切换

### P4 PPA 硬件加速帧拷贝

ESP32-P4 内置 PPA（Pixel Processing Accelerator），支持 2D blit/rotate/scale/色彩转换。当前用于替代 CPU `memcpy` 裁剪 JPEG 解码后的对齐填充行（544→540），速度提升 5-10 倍，且不占 CPU。

### P4 双帧缓冲策略

Avatar 引擎使用两个 `lv_draw_buf_t` 交替写入：解码写入 `write_buf`，LVGL 显示 `display_buf`，解码完成后交换索引。这样 JPEG 解码/PPA 裁剪与 LVGL DMA 传输完全并行，帧率提升 20-30%。

### P4 SNTP 时钟同步

网络连接成功后自动启动 SNTP 客户端（ntp.aliyun.com + pool.ntp.org），同步 UTC+8 时间。状态栏每秒刷新时钟显示，未同步时显示 `--:--`。

### P4 C6 协调器 SPI 帧转发（可选）

```
PC → MQTT Broker → ESP32-C6 (接收 JPEG 帧) → SPI 40MHz → ESP32-P4 (解码+显示)
```

C6 专司网络接收，P4 专注于 JPEG 解码和显示渲染。帧协议：`[0xAA][0x55][len:4bytes][JPEG data][CRC16:2bytes]`。P4 通过 GPIO6 握手信号检测 C6 是否有帧待发送。

### S3 SPI 显示驱动

ST7735S 使用 SPI 接口，关键点：必须使用软件 CS（硬件 CS 在传输间隙自动拉高会导致花屏），SPI 频率 20MHz。流模式下绕过 LVGL 直接写屏，JPEG 解码输出大端序 RGB565 直接通过 SPI 发送，消除字节交换和多次 memcpy 开销。双帧缓冲交替使用，减少 PSRAM 碎片。

### 帧去重

服务端和嵌入式端均实现帧去重（MD5/FNV-1a 哈希比较），静态 idle 场景可节省 ~94% 带宽。ESP32 端采样头部 64 字节 + 尾部 64 字节，兼顾表情变化（头部）和背景变化（尾部）。

### 指数退避重连

WiFi 和 MQTT 均实现指数退避重连（初始 500ms/1000ms，最大 30s/60s），连接成功后自动重置。

---

## 详细文档

| 文档 | 说明 |
|------|------|
| [Docs/esp32-s3-n16r8.md](Docs/esp32-s3-n16r8.md) | S3 硬件详细文档：引脚定义、SPI 驱动、JPEG 解码、性能优化、踩坑记录 |
| [Docs/esp32-p4-jc1060p470c.md](Docs/esp32-p4-jc1060p470c.md) | P4 硬件详细文档：引脚定义、EMAC 以太网、MIPI DSI、JPEG 对齐、防撕裂配置、踩坑记录 |
| [Docs/esp32p4单片机调查.md](Docs/esp32p4单片机调查.md) | P4 迁移与 Live2D 可行性调查报告 |

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
