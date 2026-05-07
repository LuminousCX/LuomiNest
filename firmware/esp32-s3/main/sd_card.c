#include "sd_card.h"
#include "esp_log.h"
#include "esp_vfs_fat.h"
#include "driver/sdspi_host.h"
#include "driver/spi_master.h"
#include "sdmmc_cmd.h"
#include "pin_config.h"
#include <string.h>

static const char *TAG = "sd_card";

static sdmmc_card_t *s_card = NULL;
static bool s_mounted = false;
static bool s_bus_initialized = false;

static esp_err_t try_mount(uint32_t freq_khz)
{
    esp_vfs_fat_sdmmc_mount_config_t mount_config = {
        .format_if_mount_failed = false,
        .max_files = 10,
        .allocation_unit_size = 32 * 1024,
    };

    sdmmc_host_t host = SDSPI_HOST_DEFAULT();
    host.slot = SD_SPI_HOST;
    host.max_freq_khz = freq_khz;

    sdspi_device_config_t slot_config = SDSPI_DEVICE_CONFIG_DEFAULT();
    slot_config.gpio_cs = SD_SS_PIN;
    slot_config.host_id = SD_SPI_HOST;

    return esp_vfs_fat_sdspi_mount(SD_MOUNT_POINT, &host, &slot_config, &mount_config, &s_card);
}

esp_err_t sd_card_init(void)
{
    if (s_mounted) {
        ESP_LOGW(TAG, "SD card already mounted");
        return ESP_OK;
    }

    if (!s_bus_initialized) {
        spi_bus_config_t bus_cfg = {
            .mosi_io_num = SD_MOSI_PIN,
            .miso_io_num = SD_MISO_PIN,
            .sclk_io_num = SD_SCK_PIN,
            .quadwp_io_num = -1,
            .quadhd_io_num = -1,
            .max_transfer_sz = 32768,
        };
        esp_err_t ret = spi_bus_initialize(SD_SPI_HOST, &bus_cfg, SDSPI_DEFAULT_DMA);
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "Failed to initialize SPI bus: %s", esp_err_to_name(ret));
            return ret;
        }
        s_bus_initialized = true;
        ESP_LOGI(TAG, "SPI bus initialized for SD card");
    }

    esp_err_t ret = try_mount(SDMMC_FREQ_DEFAULT);
    if (ret == ESP_OK) {
        s_mounted = true;
        sdmmc_card_print_info(stdout, s_card);
        ESP_LOGI(TAG, "SD card mounted at %s (20MHz)", SD_MOUNT_POINT);
        return ESP_OK;
    }

    ESP_LOGW(TAG, "Mount at 20MHz failed (%s), trying 10MHz...", esp_err_to_name(ret));
    esp_vfs_fat_sdcard_unmount(SD_MOUNT_POINT, s_card);

    ret = try_mount(10000);
    if (ret == ESP_OK) {
        s_mounted = true;
        sdmmc_card_print_info(stdout, s_card);
        ESP_LOGI(TAG, "SD card mounted at %s (10MHz)", SD_MOUNT_POINT);
        return ESP_OK;
    }

    ESP_LOGW(TAG, "Mount at 10MHz failed (%s), trying probing speed...", esp_err_to_name(ret));
    esp_vfs_fat_sdcard_unmount(SD_MOUNT_POINT, s_card);

    ret = try_mount(SDMMC_FREQ_PROBING);
    if (ret == ESP_OK) {
        s_mounted = true;
        sdmmc_card_print_info(stdout, s_card);
        ESP_LOGI(TAG, "SD card mounted at %s (400kHz)", SD_MOUNT_POINT);
        return ESP_OK;
    }

    ESP_LOGE(TAG, "SD card mount failed at all speeds: %s", esp_err_to_name(ret));
    return ret;
}

esp_err_t sd_card_deinit(void)
{
    if (!s_mounted) return ESP_OK;

    esp_err_t ret = esp_vfs_fat_sdcard_unmount(SD_MOUNT_POINT, s_card);
    if (ret == ESP_OK) {
        s_mounted = false;
        s_card = NULL;
        ESP_LOGI(TAG, "SD card unmounted");
    }
    return ret;
}

esp_err_t sd_card_info(sd_card_info_t *info)
{
    if (!info) return ESP_ERR_INVALID_ARG;
    if (!s_mounted || !s_card) return ESP_ERR_INVALID_STATE;

    info->mounted = s_mounted;
    info->total_bytes = (uint64_t)s_card->csd.capacity * s_card->csd.sector_size;
    info->free_bytes = 0;

    FATFS *fs = NULL;
    DWORD free_clusters = 0;
    if (f_getfree("0:", &free_clusters, &fs) == FR_OK) {
        uint32_t sector_size = 512;
        uint32_t sectors_per_cluster = fs->csize;
        info->free_bytes = (uint64_t)free_clusters * sectors_per_cluster * sector_size;
    }

    return ESP_OK;
}

bool sd_card_is_mounted(void)
{
    return s_mounted;
}
