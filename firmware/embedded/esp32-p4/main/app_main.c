/**
 * LuomiNest P4 嵌入式端 - 启动入口
 * 切片 9 重构: LVGL 单生产者模式 (espressif/esp_lvgl_port + avoid_tearing=1)
 * 切片 12 调整: bsp_spi_p4_init 提前到 app_status_init 之前
 * 迁移整合: NVS/SD/ETH/MQTT/TimeMgr/FramePlayer/SettingsUI
 *
 * 启动顺序 (严格):
 *   0. nvs_flash_init    (NVS 存储, web_config/app_mqtt 都依赖)
 *   1. bsp_spi_p4_init   (Mutex 提前就绪, status_task 推送不会撞)
 *   2. app_status_init   (状态机, 后面所有 init 进度都被记)
 *   3. bsp_lcd_init      (LDO + DSI bus + DBI IO + DPI panel + JD9165)
 *      bsp_lcd_set_brightness(80)
 *      bsp_lcd_fill_blue  (一次性蓝屏, LVGL 接管前的视觉锚点)
 *   4. bsp_sd_mount      (SDMMC, 非致命: 失败只 log 警告)
 *   5. lvgl_port_init    (创建 lvgl_mux 递归 mutex + LVGL 内部 task)
 *   6. lvgl_port_add_disp_dsi (avoid_tearing=1, 整屏 1024x600 RGB565 双缓冲 PSRAM)
 *   7. bsp_eth_init + start (以太网, 非致命: 未插网线也能 boot)
 *   8. app_mqtt_init     (MQTT 客户端, 默认 broker, 非致命)
 *   9. time_mgr_init     (SNTP, 需要网络, 非致命)
 *  10. CRC 自测 + loopback (回归切片 5/11)
 *  11. app_ui_init       (全屏布局: 状态栏 + 滑动页面 + chat + avatar + 设置页)
 *  12. frame_player_init + task (SD 卡帧序列播放, 非致命: 无 SD 则跳过)
 *  13. app_spi_recv_init (SPI 接收 task, mock 模式内部 no-op)
 *  14. lvgl_port_add_touch (LVGL 触摸 indev, 手势走 LVGL 事件回调)
 *
 * 详细分层约定见 D:\luominest\firmware\CLAUDE.md §7
 */

#include <stdio.h>
#include <string.h>
#include "esp_log.h"
#include "esp_system.h"
#include "esp_heap_caps.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

/* BSP */
#include "bsp_lcd.h"
#include "bsp_touch.h"
#include "bsp_sd.h"
#include "bsp_eth.h"
#include "bsp_spi_p4.h"

/* Drivers */
#include "drv_spi_master.h"

/* App */
#include "esp_lvgl_port.h"
#include "app_status.h"
#include "app_ui.h"
#include "app_avatar.h"
#include "app_spi_recv.h"
#include "app_mqtt.h"
#include "time_mgr.h"
#include "frame_player.h"
#include "web_config.h"

static const char *TAG = "boot";

#define MQTT_DEFAULT_BROKER  "mqtt://192.168.1.222:1883"
#define MQTT_DEFAULT_CLIENT  "luominest_p4_01"

/* 后台延迟初始化: ETH + MQTT + SNTP + SD + frame_player, 不阻塞 UI 显示 */
static void deferred_init_task(void *arg)
{
    /* SD 卡挂载 */
    esp_err_t sd_ret = bsp_sd_mount();
    if (sd_ret != ESP_OK) ESP_LOGW("init", "SD mount failed");

    /* 以太网 */
    esp_err_t eth_ret = bsp_eth_init();
    if (eth_ret == ESP_OK) bsp_eth_start();

    /* MQTT */
    ln_config_t cfg = {0};
    web_config_load(&cfg);
    const char *broker = cfg.mqtt_broker[0] ? cfg.mqtt_broker : MQTT_DEFAULT_BROKER;
    const char *client = cfg.mqtt_client[0] ? cfg.mqtt_client : MQTT_DEFAULT_CLIENT;
    app_mqtt_init(broker, client);

    /* SNTP */
    time_mgr_init();

    /* avatar 初始化 (需要 LVGL 锁保护) */
    lv_obj_t *rp = app_ui_get_right_panel();
    bool avatar_ok = false;
    if (rp) {
        if (lvgl_port_lock(5000)) {
            avatar_ok = (app_avatar_init(rp) == ESP_OK);
            lvgl_port_unlock();
        }
    }

    /* frame_player (需要 avatar 已初始化) */
    if (avatar_ok && frame_player_init() == ESP_OK && frame_player_is_sd_available()) {
        xTaskCreate(frame_player_task, "frame_play", 4096, NULL, 3, NULL);
        vTaskDelay(pdMS_TO_TICKS(50));
        if (frame_player_has_state(AVATAR_STATE_IDLE)) {
            frame_player_start(AVATAR_STATE_IDLE);
            ESP_LOGI("init", "auto-playing idle animation");
        }
    }

    /* 应用亮度配置 */
    if (cfg.brightness > 0) bsp_lcd_set_brightness(cfg.brightness);

    ESP_LOGI("init", "deferred init done");
    vTaskDelete(NULL);
}



void app_main(void)
{
    /* 静默大部分日志 */
    esp_log_level_set("*", ESP_LOG_WARN);
    esp_log_level_set("boot", ESP_LOG_INFO);
    esp_log_level_set("frame_player", ESP_LOG_INFO);
    esp_log_level_set("avatar", ESP_LOG_INFO);
    esp_log_level_set("init", ESP_LOG_INFO);
    esp_log_level_set("mqtt", ESP_LOG_ERROR);
    esp_log_level_set("esp-tls", ESP_LOG_NONE);
    esp_log_level_set("transport_base", ESP_LOG_NONE);
    esp_log_level_set("mqtt_client", ESP_LOG_NONE);

    ESP_LOGI(TAG, "=== LuomiNest P4 boot v0.1 ===");
    ESP_LOGI(TAG, "Free heap: %u bytes", (unsigned)esp_get_free_heap_size());

    /* 0. NVS flash init (web_config / app_mqtt 都依赖) */
    esp_err_t nvs_ret = nvs_flash_init();
    if (nvs_ret == ESP_ERR_NVS_NO_FREE_PAGES || nvs_ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGW(TAG, "NVS: erasing and re-init");
        nvs_flash_erase();
        nvs_ret = nvs_flash_init();
    }
    if (nvs_ret != ESP_OK) {
        ESP_LOGE(TAG, "NVS init failed: %s", esp_err_to_name(nvs_ret));
    }

    /* 1. SPI Master init 提前, 让 status_task 1s 后的 SPI 推送不会撞 INVALID_STATE */
    ESP_ERROR_CHECK(bsp_spi_p4_init());

    /* 2. status task 先启, 后面所有 init 进度都会被它记到 log */
    ESP_ERROR_CHECK(app_status_init());

    /* 3. LCD panel init (无 hack, 给 lvgl_port 接管) */
    ESP_ERROR_CHECK(bsp_lcd_init());
    ESP_ERROR_CHECK(bsp_lcd_fill_blue());
    ESP_ERROR_CHECK(bsp_lcd_set_brightness(80));

    /* 3b. Touch init (GT911 I2C, 必须在 LCD 之后) */
    esp_err_t touch_ret = bsp_touch_init();
    if (touch_ret != ESP_OK) {
        ESP_LOGW(TAG, "Touch init failed: %s (touch will not work)", esp_err_to_name(touch_ret));
    }

    /* 4. LVGL init (SD/ETH/MQTT 移到后台延迟初始化) */
    lvgl_port_cfg_t lvgl_cfg = ESP_LVGL_PORT_INIT_CONFIG();
    lvgl_cfg.task_stack    = 12288;   /* 默认 7168 不够渲染复杂 UI */
    lvgl_cfg.task_priority = 5;       /* 默认 4, 提高到 5 避免被 MQTT/SPI 抢占 */
    ESP_ERROR_CHECK(lvgl_port_init(&lvgl_cfg));

    /* 6. 注册 DSI 显示 (direct_mode: 只渲染+sync 脏区域, 配合 PERF_MONITOR 制造脏区域) */
    const lvgl_port_display_cfg_t disp_cfg = {
        .io_handle      = bsp_lcd_get_io_handle(),
        .panel_handle   = bsp_lcd_get_panel_handle(),
        .control_handle = NULL,
        .buffer_size    = BSP_LCD_H_RES * BSP_LCD_V_RES,  /* direct_mode 要求整屏 buffer */
        .double_buffer  = 1,
        .hres           = BSP_LCD_H_RES,
        .vres           = BSP_LCD_V_RES,
        .monochrome     = false,
        .rotation       = { .swap_xy = false, .mirror_x = false, .mirror_y = false },
        .color_format   = LV_COLOR_FORMAT_RGB565,
        .flags = {
            .buff_dma     = false,
            .buff_spiram  = true,
            .sw_rotate    = false,
            .full_refresh = false,
            .direct_mode  = true,    /* 只渲染脏区域: cache sync 只刷变化像素, 不是整屏 1.2MB */
        },
    };
    const lvgl_port_display_dsi_cfg_t dpi_cfg = {
        .flags = { .avoid_tearing = true },
    };
    lv_display_t *disp = lvgl_port_add_disp_dsi(&disp_cfg, &dpi_cfg);
    if (disp == NULL) {
        ESP_LOGE(TAG, "lvgl_port_add_disp_dsi failed");
        return;
    }
    ESP_LOGI(TAG, "lvgl display added: %dx%d RGB565, avoid_tearing=1", BSP_LCD_H_RES, BSP_LCD_V_RES);

    /* 立即设深色背景, 消除 LVGL 初始化时的白屏 */
    if (lvgl_port_lock(1000)) {
        lv_obj_set_style_bg_color(lv_screen_active(), lv_color_hex(0x0F0F1A), 0);
        lvgl_port_unlock();
    }

    /* 6b. 注册 LVGL 触摸输入设备 (GT911 via esp_lvgl_port) */
    const lvgl_port_touch_cfg_t touch_cfg = {
        .disp   = disp,
        .handle = bsp_touch_get_handle(),
        .scale  = { .x = 1.0f, .y = 1.0f },
    };
    lv_indev_t *indev = lvgl_port_add_touch(&touch_cfg);
    if (indev == NULL) {
        ESP_LOGW(TAG, "lvgl_port_add_touch failed (swipe/gesture will not work)");
    } else {
        ESP_LOGI(TAG, "LVGL touch indev registered");
    }

    app_status_set_state(APP_STATE_STREAM);

    /* 11. 全屏 UI 布局 (状态栏 + 滑动页面 + chat + avatar + 设置页) */
    ESP_ERROR_CHECK(app_ui_init());

    /* 12. SPI recv task */
    ESP_ERROR_CHECK(app_spi_recv_init());

    /* 13. 后台延迟初始化: SD/ETH/MQTT/SNTP/frame_player */
    xTaskCreatePinnedToCore(deferred_init_task, "deferred", 8192, NULL, 2, NULL, 1);

    ESP_LOGI(TAG, "boot done");

    while (1) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
