/**
 * LuomiNest P4 - BSP LCD (JD9165 MIPI-DSI 1024x600)
 * 切片 9 重构后: bsp_lcd 只做 LDO + DSI bus + DBI IO + DPI panel + JD9165 init +
 *                背光 + 一次性蓝屏; DSI 写权限已交给 espressif/esp_lvgl_port
 *                (LVGL 单生产者, avoid_tearing=1, 整屏 1024x600 双缓冲 PSRAM).
 *
 * 历史:
 *   切片 2: 蓝屏 init 验证
 *   切片 4: 加 drv_jpeg → bsp_lcd_draw_jpeg 路径
 *   切片 8: 加 bsp_lcd_fill_blue 一次性 + 流式去重
 *   切片 9 (旧版): 双生产者 (avatar + LVGL chat) 写 DSI fb, 加 cur_fb_index hack
 *                  + s_flush_done_sem + 5s debug log, 全部失败
 *   切片 9 重构: 删全部 hack, 改 LVGL 单生产者, bsp_lcd 退化为 panel accessor
 */

#include "bsp_lcd.h"
#include "bsp_pins.h"
#include "esp_log.h"
#include "esp_check.h"
#include "esp_heap_caps.h"
#include "esp_lcd_mipi_dsi.h"
#include "esp_lcd_panel_ops.h"   /* esp_lcd_panel_reset / init / draw_bitmap */
#include "esp_lcd_jd9165.h"
#include "esp_ldo_regulator.h"
#include "driver/ledc.h"

static const char *TAG = "bsp_lcd";
static esp_lcd_panel_handle_t   s_panel = NULL;
static esp_lcd_panel_io_handle_t s_io    = NULL;   /* DBI IO, 切片 9 重构: 给 app 拿 */

/* JD9165 厂商初始化序列 (从旧 esp32-p4 工程验证, 1024x600) */
static const jd9165_lcd_init_cmd_t lcd_init_cmds[] = {
    {0x30, (uint8_t[]){0x00}, 1, 0},
    {0xF7, (uint8_t[]){0x49,0x61,0x02,0x00}, 4, 0},
    {0x30, (uint8_t[]){0x01}, 1, 0},
    {0x04, (uint8_t[]){0x0C}, 1, 0},
    {0x05, (uint8_t[]){0x00}, 1, 0},
    {0x06, (uint8_t[]){0x00}, 1, 0},
    {0x0B, (uint8_t[]){0x11}, 1, 0},
    {0x17, (uint8_t[]){0x00}, 1, 0},
    {0x20, (uint8_t[]){0x04}, 1, 0},
    {0x1F, (uint8_t[]){0x05}, 1, 0},
    {0x23, (uint8_t[]){0x00}, 1, 0},
    {0x25, (uint8_t[]){0x19}, 1, 0},
    {0x28, (uint8_t[]){0x18}, 1, 0},
    {0x29, (uint8_t[]){0x04}, 1, 0},
    {0x2A, (uint8_t[]){0x01}, 1, 0},
    {0x2B, (uint8_t[]){0x04}, 1, 0},
    {0x2C, (uint8_t[]){0x01}, 1, 0},
    {0x30, (uint8_t[]){0x02}, 1, 0},
    {0x01, (uint8_t[]){0x22}, 1, 0},
    {0x03, (uint8_t[]){0x12}, 1, 0},
    {0x04, (uint8_t[]){0x00}, 1, 0},
    {0x05, (uint8_t[]){0x64}, 1, 0},
    {0x0A, (uint8_t[]){0x08}, 1, 0},
    {0x0B, (uint8_t[]){0x0A,0x1A,0x0B,0x0D,0x0D,0x11,0x10,0x06,0x08,0x1F,0x1D}, 11, 0},
    {0x0C, (uint8_t[]){0x0D,0x0D,0x0D,0x0D,0x0D,0x0D,0x0D,0x0D,0x0D,0x0D,0x0D}, 11, 0},
    {0x0D, (uint8_t[]){0x16,0x1B,0x0B,0x0D,0x0D,0x11,0x10,0x07,0x09,0x1E,0x1C}, 11, 0},
    {0x0E, (uint8_t[]){0x0D,0x0D,0x0D,0x0D,0x0D,0x0D,0x0D,0x0D,0x0D,0x0D,0x0D}, 11, 0},
    {0x0F, (uint8_t[]){0x16,0x1B,0x0D,0x0B,0x0D,0x11,0x10,0x1C,0x1E,0x09,0x07}, 11, 0},
    {0x10, (uint8_t[]){0x0D,0x0D,0x0D,0x0D,0x0D,0x0D,0x0D,0x0D,0x0D,0x0D,0x0D}, 11, 0},
    {0x11, (uint8_t[]){0x0A,0x1A,0x0D,0x0B,0x0D,0x11,0x10,0x1D,0x1F,0x08,0x06}, 11, 0},
    {0x12, (uint8_t[]){0x0D,0x0D,0x0D,0x0D,0x0D,0x0D,0x0D,0x0D,0x0D,0x0D,0x0D}, 11, 0},
    {0x14, (uint8_t[]){0x00,0x00,0x11,0x11}, 4, 0},
    {0x18, (uint8_t[]){0x99}, 1, 0},
    {0x30, (uint8_t[]){0x06}, 1, 0},
    {0x12, (uint8_t[]){0x36,0x2C,0x2E,0x3C,0x38,0x35,0x35,0x32,0x2E,0x1D,0x2B,0x21,0x16,0x29}, 14, 0},
    {0x13, (uint8_t[]){0x36,0x2C,0x2E,0x3C,0x38,0x35,0x35,0x32,0x2E,0x1D,0x2B,0x21,0x16,0x29}, 14, 0},
    {0x30, (uint8_t[]){0x0A}, 1, 0},
    {0x02, (uint8_t[]){0x4F}, 1, 0},
    {0x0B, (uint8_t[]){0x40}, 1, 0},
    {0x12, (uint8_t[]){0x3E}, 1, 0},
    {0x13, (uint8_t[]){0x78}, 1, 0},
    {0x30, (uint8_t[]){0x0D}, 1, 0},
    {0x0D, (uint8_t[]){0x04}, 1, 0},
    {0x10, (uint8_t[]){0x0C}, 1, 0},
    {0x11, (uint8_t[]){0x0C}, 1, 0},
    {0x12, (uint8_t[]){0x0C}, 1, 0},
    {0x13, (uint8_t[]){0x0C}, 1, 0},
    {0x30, (uint8_t[]){0x00}, 1, 0},
    {0x3A, (uint8_t[]){0x55}, 1, 0},
    {0x11, (uint8_t[]){0x00}, 1, 120},
    {0x29, (uint8_t[]){0x00}, 1, 20},
};

esp_err_t bsp_lcd_init(void)
{
    ESP_LOGI(TAG, "=== LCD init start ===");

    /* 1. 启 LDO 3 给 MIPI PHY 供电 (2.5V) */
    esp_ldo_channel_handle_t phy_pwr = NULL;
    esp_ldo_channel_config_t ldo_cfg = {
        .chan_id    = BSP_MIPI_PHY_LDO_CHAN,
        .voltage_mv = BSP_MIPI_PHY_LDO_VOLTAGE_MV,
    };
    ESP_RETURN_ON_ERROR(esp_ldo_acquire_channel(&ldo_cfg, &phy_pwr), TAG, "LDO");
    ESP_LOGI(TAG, "MIPI PHY LDO%d = %dmV", BSP_MIPI_PHY_LDO_CHAN, BSP_MIPI_PHY_LDO_VOLTAGE_MV);

    /* 2. 创建 DSI bus */
    esp_lcd_dsi_bus_handle_t dsi_bus = NULL;
    esp_lcd_dsi_bus_config_t bus_config = {
        .bus_id              = 0,
        .num_data_lanes      = BSP_LCD_DSI_LANES,
        .phy_clk_src         = MIPI_DSI_PHY_CLK_SRC_DEFAULT,
        .lane_bit_rate_mbps  = BSP_LCD_LANE_MBPS,
    };
    ESP_RETURN_ON_ERROR(esp_lcd_new_dsi_bus(&bus_config, &dsi_bus), TAG, "DSI bus");
    ESP_LOGI(TAG, "DSI bus: %d-lane @ %dMbps", BSP_LCD_DSI_LANES, BSP_LCD_LANE_MBPS);

    /* 3. 创建 DBI IO (DSI 转 DBI, 给 JD9165 发 init 序列) */
    esp_lcd_dbi_io_config_t dbi_config = {
        .virtual_channel = 0,
        .lcd_cmd_bits    = 8,
        .lcd_param_bits  = 8,
    };
    ESP_RETURN_ON_ERROR(esp_lcd_new_panel_io_dbi(dsi_bus, &dbi_config, &s_io), TAG, "DBI IO");

    /* 4. DPI panel 配置 (1024x600 RGB565, 双 framebuffer, PSRAM, 留给 esp_lvgl_port 接管) */
    esp_lcd_dpi_panel_config_t dpi_config = {
        .dpi_clk_src        = MIPI_DSI_DPI_CLK_SRC_DEFAULT,
        .dpi_clock_freq_mhz = BSP_LCD_DPI_CLK_MHZ,
        .virtual_channel    = 0,
        .pixel_format       = LCD_COLOR_PIXEL_FORMAT_RGB565,
        .num_fbs            = 2,                       /* avoid_tearing=1 需要 ≥2 */
        .video_timing = {
            .h_size            = BSP_LCD_H_RES,
            .v_size            = BSP_LCD_V_RES,
            .hsync_back_porch  = 160,
            .hsync_pulse_width = 24,
            .hsync_front_porch = 160,
            .vsync_back_porch  = 21,
            .vsync_pulse_width = 2,
            .vsync_front_porch = 12,
        },
        .flags = {
            .use_dma2d = true,    /* P4 内部硬件 2D DMA, P4 v1.x CPU 路径会 Guru */
            /* ESP-IDF 5.5.3 无 fb_in_psram flag, DSI 默认就放 PSRAM (heap_caps SPIRAM) */
        },
    };

    /* 5. JD9165 厂商配置 */
    jd9165_vendor_config_t vendor_config = {
        .init_cmds      = lcd_init_cmds,
        .init_cmds_size = sizeof(lcd_init_cmds) / sizeof(jd9165_lcd_init_cmd_t),
        .mipi_config = {
            .dsi_bus    = dsi_bus,
            .dpi_config = &dpi_config,
        },
    };
    esp_lcd_panel_dev_config_t lcd_dev_config = {
        .reset_gpio_num = BSP_LCD_RST_PIN,
        .rgb_ele_order  = LCD_RGB_ELEMENT_ORDER_RGB,
        .bits_per_pixel = 16,
        .vendor_config  = &vendor_config,
    };
    ESP_RETURN_ON_ERROR(esp_lcd_new_panel_jd9165(s_io, &lcd_dev_config, &s_panel), TAG, "JD9165 panel");

    /* 6. reset + init (启用 DSI 输出) */
    ESP_RETURN_ON_ERROR(esp_lcd_panel_reset(s_panel), TAG, "panel reset");
    ESP_RETURN_ON_ERROR(esp_lcd_panel_init(s_panel), TAG, "panel init");

    /* 切片 9 重构: 此处**不**再注册 DSI on_refresh_done 回调,
     * esp_lvgl_port(avoid_tearing=1) 内部会注册自己的 vsync 回调 + trans_sem.
     * 也**不**创建 s_lcd_mutex / s_flush_done_sem / 任何 hack —
     * LVGL 是 DSI 唯一生产者, 撕裂根因已消除. */

    ESP_LOGI(TAG, "=== LCD init ok (%dx%d), num_fbs=%d, fb_in_psram=1, panel_ready_for_lvgl ===",
             BSP_LCD_H_RES, BSP_LCD_V_RES, dpi_config.num_fbs);
    return ESP_OK;
}

esp_err_t bsp_lcd_set_brightness(int percent)
{
    if (percent < 0)   percent = 0;
    if (percent > 100) percent = 100;

    static bool inited = false;
    if (!inited) {
        const ledc_timer_config_t timer = {
            .speed_mode      = LEDC_LOW_SPEED_MODE,
            .duty_resolution = LEDC_TIMER_10_BIT,
            .timer_num       = LEDC_TIMER_1,
            .freq_hz         = 20000,
            .clk_cfg         = LEDC_AUTO_CLK,
        };
        const ledc_channel_config_t ch = {
            .gpio_num   = BSP_LCD_BL_PIN,
            .speed_mode = LEDC_LOW_SPEED_MODE,
            .channel    = LEDC_CHANNEL_1,
            .intr_type  = LEDC_INTR_DISABLE,
            .timer_sel  = LEDC_TIMER_1,
            .duty       = 0,
            .hpoint     = 0,
        };
        ESP_RETURN_ON_ERROR(ledc_timer_config(&timer), TAG, "ledc timer");
        ESP_RETURN_ON_ERROR(ledc_channel_config(&ch), TAG, "ledc ch");
        inited = true;
    }
    uint32_t duty = (1023 * percent) / 100;
    ESP_RETURN_ON_ERROR(ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_1, duty), TAG, "set duty");
    ESP_RETURN_ON_ERROR(ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_1), TAG, "update duty");
    return ESP_OK;
}

esp_err_t bsp_lcd_fill_blue(void)
{
    if (s_panel == NULL) return ESP_ERR_INVALID_STATE;

    /* 切片 9 重构: 一次性蓝屏 (启动到 LVGL init 完成之间的视觉锚点).
     * 不再需要 lock/sem/hack — LVGL 还没接管, DSI 直接写一次即可. */
    const size_t px = (size_t)BSP_LCD_H_RES * BSP_LCD_V_RES;
    uint16_t *buf = heap_caps_malloc(px * 2, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (buf == NULL) return ESP_ERR_NO_MEM;
    for (size_t i = 0; i < px; i++) buf[i] = 0x001F;  /* RGB565 蓝 */

    esp_err_t ret = esp_lcd_panel_draw_bitmap(s_panel, 0, 0,
                                              BSP_LCD_H_RES, BSP_LCD_V_RES, buf);
    free(buf);
    ESP_RETURN_ON_ERROR(ret, TAG, "draw bitmap");
    ESP_LOGI(TAG, "fill blue ok (one-shot before LVGL takes over)");
    return ESP_OK;
}

esp_lcd_panel_handle_t bsp_lcd_get_panel_handle(void)
{
    return s_panel;
}

esp_lcd_panel_io_handle_t bsp_lcd_get_io_handle(void)
{
    return s_io;
}
