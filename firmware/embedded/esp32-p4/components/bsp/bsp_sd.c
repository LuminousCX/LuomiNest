/**
 * LuomiNest P4 - BSP SD 卡 (SDMMC 4-bit)
 * 从旧 esp32-p4/main/main.c init_sdcard() 移植, 改为独立 BSP 组件
 *
 * 关键修复 (vs 旧工程):
 *   - 不用 LDO power control (P-MOSFET Q1 由 R13 下拉常开)
 *   - 4-bit 优先, fallback 1-bit
 *   - 频率从高到低尝试: 40→20→10→0.4 MHz
 */

#include "bsp_sd.h"
#include "bsp_pins.h"
#include "esp_log.h"
#include "esp_vfs_fat.h"
#include "driver/sdmmc_host.h"
#include "sdmmc_cmd.h"
#include "esp_ldo_regulator.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "bsp_sd";

static sdmmc_card_t *s_card = NULL;
static bool s_mounted = false;

static esp_err_t try_mount(sdmmc_host_t *host, const sdmmc_slot_config_t *slot,
                           const esp_vfs_fat_sdmmc_mount_config_t *mc,
                           uint32_t freq_khz)
{
    host->max_freq_khz = freq_khz;
    esp_err_t ret = esp_vfs_fat_sdmmc_mount("/sdcard", host, slot, mc, &s_card);
    if (ret == ESP_OK) {
        ESP_LOGI(TAG, "SD mounted @ %lu kHz", (unsigned long)freq_khz);
        sdmmc_card_print_info(stdout, s_card);
        s_mounted = true;
    }
    return ret;
}

esp_err_t bsp_sd_mount(void)
{
    if (s_mounted) return ESP_OK;

    const esp_vfs_fat_sdmmc_mount_config_t mount_config = {
        .format_if_mount_failed = false,
        .max_files = 12,
        .allocation_unit_size = 16 * 1024,
    };

    sdmmc_host_t host = SDMMC_HOST_DEFAULT();
    host.slot = SDMMC_HOST_SLOT_0;
    host.pwr_ctrl_handle = NULL;

    ESP_LOGI(TAG, "=== SD Card Init ===");
    ESP_LOGI(TAG, "SD pins: CLK=%d CMD=%d D0=%d D1=%d D2=%d D3=%d",
             BSP_SDMMC_CLK_PIN, BSP_SDMMC_CMD_PIN,
             BSP_SDMMC_D0_PIN, BSP_SDMMC_D1_PIN,
             BSP_SDMMC_D2_PIN, BSP_SDMMC_D3_PIN);

    /* 启用 LDO4 为 SD 卡供电 (3.3V) */
    esp_ldo_channel_handle_t sd_pwr = NULL;
    esp_ldo_channel_config_t ldo_cfg = {
        .chan_id = 4,
        .voltage_mv = 3300,
    };
    esp_err_t ldo_ret = esp_ldo_acquire_channel(&ldo_cfg, &sd_pwr);
    if (ldo_ret == ESP_OK) {
        ESP_LOGI(TAG, "LDO4 enabled at 3300mV for SD card");
    } else {
        ESP_LOGW(TAG, "LDO4 init failed: 0x%x (SD card may not have power)", ldo_ret);
    }

    vTaskDelay(pdMS_TO_TICKS(50));

    /* 4-bit slot */
    const sdmmc_slot_config_t slot_4bit = {
        .clk = BSP_SDMMC_CLK_PIN,
        .cmd = BSP_SDMMC_CMD_PIN,
        .d0 = BSP_SDMMC_D0_PIN,
        .d1 = BSP_SDMMC_D1_PIN,
        .d2 = BSP_SDMMC_D2_PIN,
        .d3 = BSP_SDMMC_D3_PIN,
        .d4 = GPIO_NUM_NC, .d5 = GPIO_NUM_NC,
        .d6 = GPIO_NUM_NC, .d7 = GPIO_NUM_NC,
        .cd = SDMMC_SLOT_NO_CD,
        .wp = SDMMC_SLOT_NO_WP,
        .width = 4,
        .flags = SDMMC_SLOT_FLAG_INTERNAL_PULLUP,
    };

    /* 1-bit slot */
    const sdmmc_slot_config_t slot_1bit = {
        .clk = BSP_SDMMC_CLK_PIN,
        .cmd = BSP_SDMMC_CMD_PIN,
        .d0 = BSP_SDMMC_D0_PIN,
        .d1 = GPIO_NUM_NC, .d2 = GPIO_NUM_NC, .d3 = GPIO_NUM_NC,
        .d4 = GPIO_NUM_NC, .d5 = GPIO_NUM_NC,
        .d6 = GPIO_NUM_NC, .d7 = GPIO_NUM_NC,
        .cd = SDMMC_SLOT_NO_CD,
        .wp = SDMMC_SLOT_NO_WP,
        .width = 1,
        .flags = SDMMC_SLOT_FLAG_INTERNAL_PULLUP,
    };

    /* 快速尝试: 4-bit 高频 → 4-bit 低频 → 1-bit 低频 */
    if (try_mount(&host, &slot_4bit, &mount_config, 40000) == ESP_OK) return ESP_OK;
    esp_vfs_fat_sdcard_unmount("/sdcard", s_card);
    vTaskDelay(pdMS_TO_TICKS(20));
    if (try_mount(&host, &slot_4bit, &mount_config, 400) == ESP_OK) return ESP_OK;
    esp_vfs_fat_sdcard_unmount("/sdcard", s_card);
    vTaskDelay(pdMS_TO_TICKS(20));
    if (try_mount(&host, &slot_1bit, &mount_config, 400) == ESP_OK) return ESP_OK;
    esp_vfs_fat_sdcard_unmount("/sdcard", s_card);

    ESP_LOGW(TAG, "SD card mount failed at all frequencies/modes");
    return ESP_FAIL;
}

esp_err_t bsp_sd_unmount(void)
{
    if (!s_mounted || !s_card) return ESP_OK;
    esp_err_t ret = esp_vfs_fat_sdcard_unmount("/sdcard", s_card);
    s_card = NULL;
    s_mounted = false;
    ESP_LOGI(TAG, "SD card unmounted");
    return ret;
}

bool bsp_sd_is_mounted(void)
{
    return s_mounted;
}
