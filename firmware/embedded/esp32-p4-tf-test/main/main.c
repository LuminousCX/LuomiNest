#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <dirent.h>
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "esp_vfs_fat.h"
#include "driver/sdmmc_host.h"
#include "driver/gpio.h"
#include "sdmmc_cmd.h"
#include "sd_pwr_ctrl_by_on_chip_ldo.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "tf_test";

#define SDMMC_CLK_PIN   GPIO_NUM_43
#define SDMMC_CMD_PIN   GPIO_NUM_44
#define SDMMC_D0_PIN    GPIO_NUM_39
#define SDMMC_D1_PIN    GPIO_NUM_40
#define SDMMC_D2_PIN    GPIO_NUM_41
#define SDMMC_D3_PIN    GPIO_NUM_42
#define SD_LDO_CHAN     4

static void list_dir(const char *path, int depth)
{
    DIR *dir = opendir(path);
    if (!dir) {
        ESP_LOGE(TAG, "Failed to open dir: %s", path);
        return;
    }

    struct dirent *ent;
    while ((ent = readdir(dir)) != NULL) {
        for (int i = 0; i < depth; i++) printf("  ");
        if (ent->d_type == DT_DIR) {
            printf("[%s]\n", ent->d_name);
            if (strcmp(ent->d_name, ".") != 0 && strcmp(ent->d_name, "..") != 0 && depth < 3) {
                char subpath[512];
                snprintf(subpath, sizeof(subpath), "%s/%s", path, ent->d_name);
                list_dir(subpath, depth + 1);
            }
        } else {
            char filepath[512];
            snprintf(filepath, sizeof(filepath), "%s/%s", path, ent->d_name);
            struct stat st;
            uint32_t size_kb = 0;
            if (stat(filepath, &st) == 0) {
                size_kb = (uint32_t)(st.st_size / 1024);
            }
            printf("%s (%lu KB)\n", ent->d_name, (unsigned long)size_kb);
        }
    }
    closedir(dir);
}

static esp_err_t test_sdmmc_no_ldo(void)
{
    ESP_LOGI(TAG, "");
    ESP_LOGI(TAG, "===== Test 1: SDMMC 4-bit, NO LDO power control =====");

    const esp_vfs_fat_sdmmc_mount_config_t mount_config = {
        .format_if_mount_failed = false,
        .max_files = 10,
        .allocation_unit_size = 16 * 1024,
    };

    sdmmc_host_t host = SDMMC_HOST_DEFAULT();
    host.slot = SDMMC_HOST_SLOT_0;
    host.pwr_ctrl_handle = NULL;

    const sdmmc_slot_config_t slot_config = {
        .clk = SDMMC_CLK_PIN,
        .cmd = SDMMC_CMD_PIN,
        .d0 = SDMMC_D0_PIN,
        .d1 = SDMMC_D1_PIN,
        .d2 = SDMMC_D2_PIN,
        .d3 = SDMMC_D3_PIN,
        .d4 = GPIO_NUM_NC,
        .d5 = GPIO_NUM_NC,
        .d6 = GPIO_NUM_NC,
        .d7 = GPIO_NUM_NC,
        .cd = SDMMC_SLOT_NO_CD,
        .wp = SDMMC_SLOT_NO_WP,
        .width = 4,
        .flags = SDMMC_SLOT_FLAG_INTERNAL_PULLUP,
    };

    sdmmc_card_t *card = NULL;
    esp_err_t ret = esp_vfs_fat_sdmmc_mount("/sdcard", &host, &slot_config, &mount_config, &card);
    if (ret == ESP_OK) {
        ESP_LOGI(TAG, "SUCCESS! SD card mounted (4-bit, no LDO)");
        sdmmc_card_print_info(stdout, card);
        return ESP_OK;
    }

    ESP_LOGW(TAG, "FAILED (0x%x: %s)", ret, esp_err_to_name(ret));
    esp_vfs_fat_sdcard_unmount("/sdcard", card);
    return ret;
}

static esp_err_t test_sdmmc_1bit_no_ldo(void)
{
    ESP_LOGI(TAG, "");
    ESP_LOGI(TAG, "===== Test 2: SDMMC 1-bit, NO LDO power control =====");

    const esp_vfs_fat_sdmmc_mount_config_t mount_config = {
        .format_if_mount_failed = false,
        .max_files = 10,
        .allocation_unit_size = 16 * 1024,
    };

    sdmmc_host_t host = SDMMC_HOST_DEFAULT();
    host.slot = SDMMC_HOST_SLOT_0;
    host.max_freq_khz = SDMMC_FREQ_PROBING;
    host.pwr_ctrl_handle = NULL;

    const sdmmc_slot_config_t slot_config = {
        .clk = SDMMC_CLK_PIN,
        .cmd = SDMMC_CMD_PIN,
        .d0 = SDMMC_D0_PIN,
        .d1 = GPIO_NUM_NC,
        .d2 = GPIO_NUM_NC,
        .d3 = GPIO_NUM_NC,
        .d4 = GPIO_NUM_NC,
        .d5 = GPIO_NUM_NC,
        .d6 = GPIO_NUM_NC,
        .d7 = GPIO_NUM_NC,
        .cd = SDMMC_SLOT_NO_CD,
        .wp = SDMMC_SLOT_NO_WP,
        .width = 1,
        .flags = SDMMC_SLOT_FLAG_INTERNAL_PULLUP,
    };

    sdmmc_card_t *card = NULL;
    esp_err_t ret = esp_vfs_fat_sdmmc_mount("/sdcard", &host, &slot_config, &mount_config, &card);
    if (ret == ESP_OK) {
        ESP_LOGI(TAG, "SUCCESS! SD card mounted (1-bit, 400kHz, no LDO)");
        sdmmc_card_print_info(stdout, card);
        return ESP_OK;
    }

    ESP_LOGW(TAG, "FAILED (0x%x: %s)", ret, esp_err_to_name(ret));
    esp_vfs_fat_sdcard_unmount("/sdcard", card);
    return ret;
}

static esp_err_t test_sdmmc_with_ldo_0v(void)
{
    ESP_LOGI(TAG, "");
    ESP_LOGI(TAG, "===== Test 3: SDMMC 4-bit, LDO CH4 created but NOT set (stays 0V) =====");

    const esp_vfs_fat_sdmmc_mount_config_t mount_config = {
        .format_if_mount_failed = false,
        .max_files = 10,
        .allocation_unit_size = 16 * 1024,
    };

    sdmmc_host_t host = SDMMC_HOST_DEFAULT();
    host.slot = SDMMC_HOST_SLOT_0;

    sd_pwr_ctrl_ldo_config_t ldo_config = {
        .ldo_chan_id = SD_LDO_CHAN,
    };
    sd_pwr_ctrl_handle_t pwr_ctrl_handle = NULL;
    esp_err_t ret = sd_pwr_ctrl_new_on_chip_ldo(&ldo_config, &pwr_ctrl_handle);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "LDO create failed (0x%x)", ret);
        return ret;
    }
    host.pwr_ctrl_handle = pwr_ctrl_handle;
    ESP_LOGI(TAG, "LDO CH4 created (voltage NOT set, should be 0V)");

    vTaskDelay(pdMS_TO_TICKS(500));

    const sdmmc_slot_config_t slot_config = {
        .clk = SDMMC_CLK_PIN,
        .cmd = SDMMC_CMD_PIN,
        .d0 = SDMMC_D0_PIN,
        .d1 = SDMMC_D1_PIN,
        .d2 = SDMMC_D2_PIN,
        .d3 = SDMMC_D3_PIN,
        .d4 = GPIO_NUM_NC,
        .d5 = GPIO_NUM_NC,
        .d6 = GPIO_NUM_NC,
        .d7 = GPIO_NUM_NC,
        .cd = SDMMC_SLOT_NO_CD,
        .wp = SDMMC_SLOT_NO_WP,
        .width = 4,
        .flags = SDMMC_SLOT_FLAG_INTERNAL_PULLUP,
    };

    sdmmc_card_t *card = NULL;
    ret = esp_vfs_fat_sdmmc_mount("/sdcard", &host, &slot_config, &mount_config, &card);
    if (ret == ESP_OK) {
        ESP_LOGI(TAG, "SUCCESS! SD card mounted (4-bit, LDO at 0V)");
        sdmmc_card_print_info(stdout, card);
        return ESP_OK;
    }

    ESP_LOGW(TAG, "FAILED (0x%x: %s)", ret, esp_err_to_name(ret));
    esp_vfs_fat_sdcard_unmount("/sdcard", card);
    return ret;
}

static esp_err_t test_gpio45_high(void)
{
    ESP_LOGI(TAG, "");
    ESP_LOGI(TAG, "===== Test 4: SDMMC 4-bit, GPIO45=HIGH (force Q1 gate high) =====");

    gpio_config_t gpio45_cfg = {
        .pin_bit_mask = BIT64(GPIO_NUM_45),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&gpio45_cfg);
    gpio_set_level(GPIO_NUM_45, 1);
    ESP_LOGI(TAG, "GPIO45 = HIGH (Q1 gate driven HIGH, MOSFET should be OFF)");
    vTaskDelay(pdMS_TO_TICKS(500));

    const esp_vfs_fat_sdmmc_mount_config_t mount_config = {
        .format_if_mount_failed = false,
        .max_files = 10,
        .allocation_unit_size = 16 * 1024,
    };

    sdmmc_host_t host = SDMMC_HOST_DEFAULT();
    host.slot = SDMMC_HOST_SLOT_0;
    host.pwr_ctrl_handle = NULL;

    const sdmmc_slot_config_t slot_config = {
        .clk = SDMMC_CLK_PIN,
        .cmd = SDMMC_CMD_PIN,
        .d0 = SDMMC_D0_PIN,
        .d1 = SDMMC_D1_PIN,
        .d2 = SDMMC_D2_PIN,
        .d3 = SDMMC_D3_PIN,
        .d4 = GPIO_NUM_NC,
        .d5 = GPIO_NUM_NC,
        .d6 = GPIO_NUM_NC,
        .d7 = GPIO_NUM_NC,
        .cd = SDMMC_SLOT_NO_CD,
        .wp = SDMMC_SLOT_NO_WP,
        .width = 4,
        .flags = SDMMC_SLOT_FLAG_INTERNAL_PULLUP,
    };

    sdmmc_card_t *card = NULL;
    esp_err_t ret = esp_vfs_fat_sdmmc_mount("/sdcard", &host, &slot_config, &mount_config, &card);
    if (ret == ESP_OK) {
        ESP_LOGI(TAG, "SUCCESS! SD card mounted (GPIO45=HIGH)");
        sdmmc_card_print_info(stdout, card);
        return ESP_OK;
    }

    ESP_LOGW(TAG, "FAILED (0x%x: %s)", ret, esp_err_to_name(ret));
    esp_vfs_fat_sdcard_unmount("/sdcard", card);

    gpio_set_level(GPIO_NUM_45, 0);
    ESP_LOGI(TAG, "GPIO45 = LOW (Q1 gate released, R13 should pull down)");
    return ret;
}

static esp_err_t test_gpio45_low(void)
{
    ESP_LOGI(TAG, "");
    ESP_LOGI(TAG, "===== Test 5: SDMMC 4-bit, GPIO45=LOW (R13 pulls Q1 gate LOW) =====");

    gpio_set_level(GPIO_NUM_45, 0);
    ESP_LOGI(TAG, "GPIO45 = LOW (Q1 gate should be LOW via R13, MOSFET should be ON)");
    vTaskDelay(pdMS_TO_TICKS(500));

    const esp_vfs_fat_sdmmc_mount_config_t mount_config = {
        .format_if_mount_failed = false,
        .max_files = 10,
        .allocation_unit_size = 16 * 1024,
    };

    sdmmc_host_t host = SDMMC_HOST_DEFAULT();
    host.slot = SDMMC_HOST_SLOT_0;
    host.pwr_ctrl_handle = NULL;

    const sdmmc_slot_config_t slot_config = {
        .clk = SDMMC_CLK_PIN,
        .cmd = SDMMC_CMD_PIN,
        .d0 = SDMMC_D0_PIN,
        .d1 = SDMMC_D1_PIN,
        .d2 = SDMMC_D2_PIN,
        .d3 = SDMMC_D3_PIN,
        .d4 = GPIO_NUM_NC,
        .d5 = GPIO_NUM_NC,
        .d6 = GPIO_NUM_NC,
        .d7 = GPIO_NUM_NC,
        .cd = SDMMC_SLOT_NO_CD,
        .wp = SDMMC_SLOT_NO_WP,
        .width = 4,
        .flags = SDMMC_SLOT_FLAG_INTERNAL_PULLUP,
    };

    sdmmc_card_t *card = NULL;
    esp_err_t ret = esp_vfs_fat_sdmmc_mount("/sdcard", &host, &slot_config, &mount_config, &card);
    if (ret == ESP_OK) {
        ESP_LOGI(TAG, "SUCCESS! SD card mounted (GPIO45=LOW)");
        sdmmc_card_print_info(stdout, card);
        return ESP_OK;
    }

    ESP_LOGW(TAG, "FAILED (0x%x: %s)", ret, esp_err_to_name(ret));
    esp_vfs_fat_sdcard_unmount("/sdcard", card);
    return ret;
}

void app_main(void)
{
    ESP_LOGI(TAG, "========================================");
    ESP_LOGI(TAG, "  ESP32-P4 TF Card Diagnostic Tool");
    ESP_LOGI(TAG, "========================================");
    ESP_LOGI(TAG, "Pins: CLK=43 CMD=44 D0=39 D1=40 D2=41 D3=42");
    ESP_LOGI(TAG, "LDO: CH4 (via R4->Q1 gate, R13 pulldown)");
    ESP_LOGI(TAG, "Free heap: %u, PSRAM: %u",
             (unsigned)esp_get_free_heap_size(),
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
    ESP_LOGI(TAG, "");

    esp_err_t ret;

    ret = test_sdmmc_no_ldo();
    if (ret == ESP_OK) goto success;

    ret = test_sdmmc_1bit_no_ldo();
    if (ret == ESP_OK) goto success;

    ret = test_sdmmc_with_ldo_0v();
    if (ret == ESP_OK) goto success;

    ret = test_gpio45_high();
    if (ret == ESP_OK) goto success;

    ret = test_gpio45_low();
    if (ret == ESP_OK) goto success;

    ESP_LOGE(TAG, "");
    ESP_LOGE(TAG, "========================================");
    ESP_LOGE(TAG, "  ALL TESTS FAILED!");
    ESP_LOGE(TAG, "========================================");
    ESP_LOGE(TAG, "");
    ESP_LOGE(TAG, "Hardware checks needed:");
    ESP_LOGE(TAG, "  1. Measure SD slot Pin4(VDD) to GND - expect ~3.3V");
    ESP_LOGE(TAG, "  2. Measure Q1 gate voltage - should be ~0V for MOSFET ON");
    ESP_LOGE(TAG, "  3. Check if SD card works on S3 board (SPI mode)");
    ESP_LOGE(TAG, "  4. Try FAT32 formatted card instead of exFAT");
    ESP_LOGE(TAG, "  5. Check R2(8Ohm) voltage drop under load");
    return;

success:
    ESP_LOGI(TAG, "");
    ESP_LOGI(TAG, "=== SD Card Contents ===");
    list_dir("/sdcard", 0);

    ESP_LOGI(TAG, "");
    ESP_LOGI(TAG, "=== Testing file read ===");
    FILE *f = fopen("/sdcard/frames/manifest.json", "r");
    if (f) {
        char buf[512];
        size_t n = fread(buf, 1, sizeof(buf) - 1, f);
        buf[n] = '\0';
        fclose(f);
        ESP_LOGI(TAG, "manifest.json (%d bytes): %s", (int)n, buf);
    } else {
        ESP_LOGI(TAG, "No manifest.json found (this is OK if not yet generated)");
    }

    DIR *dir = opendir("/sdcard/frames");
    if (dir) {
        ESP_LOGI(TAG, "/sdcard/frames/ directory exists!");
        closedir(dir);
    } else {
        ESP_LOGI(TAG, "/sdcard/frames/ directory not found");
    }

    ESP_LOGI(TAG, "");
    ESP_LOGI(TAG, "=== Test complete! ===");
}
