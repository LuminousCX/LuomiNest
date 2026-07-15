/**
 * LuomiNest P4 - BSP SPI Master 实现
 * 切片 5a: SPI2 @ 40 MHz, MODE 0, polling
 * 切片 12: 加 FreeRTOS recursive mutex 串行化 transfer
 *
 * 关键决策:
 *   - 用 spi_bus_initialize + spi_bus_add_device (不直接 spi_device_polling_transmit)
 *     因为这样 app 层可以自己拿 device handle 自由调度
 *   - CS 用硬件自动 (trans 前后自动拉低/拉高)
 *   - MISO 接 4 (C6 MOSI 接到 P4 这边), 留出 MISO 也读得到对方的字节
 *   - 切片 12: SPI 是单外设, recv task 和 status send task 同时调 transfer 会撞,
 *     内部加 recursive mutex 互斥, app 层不用管
 *
 * ⚠️ 当前切片 5 阶段, P4 端没有 C6 真实硬件可联调, 先用
 *    MOSI 短接到 MISO 做回环自测, 验证 transfer 路径工作.
 *    切片 5c 联调时再接 C6 板.
 */

#include "bsp_spi_p4.h"
#include "bsp_pins.h"
#include "esp_log.h"
#include "esp_check.h"
#include "driver/spi_master.h"
#include "driver/gpio.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

static const char *TAG = "bsp_spi";
static spi_device_handle_t s_dev = NULL;
static bool s_inited = false;
/* 切片 12: recursive mutex 让 recv/send task 不撞. 同一 task 内嵌套调也安全. */
static SemaphoreHandle_t s_spi_mutex = NULL;

esp_err_t bsp_spi_p4_init(void)
{
    if (s_inited) return ESP_OK;

    ESP_LOGI(TAG, "init: SPI%d CLK=%d MOSI=%d MISO=%d CS=%d @ %d Hz",
             BSP_SPI_P4_HOST, BSP_SPI_P4_CLK_PIN, BSP_SPI_P4_MOSI_PIN,
             BSP_SPI_P4_MISO_PIN, BSP_SPI_P4_CS_PIN, BSP_SPI_P4_FREQ_HZ);

    spi_bus_config_t bus_cfg = {
        .mosi_io_num     = BSP_SPI_P4_MOSI_PIN,
        .miso_io_num     = BSP_SPI_P4_MISO_PIN,
        .sclk_io_num     = BSP_SPI_P4_CLK_PIN,
        .quadwp_io_num   = -1,
        .quadhd_io_num   = -1,
        .max_transfer_sz = 64 * 1024,  /* 64 KB, 切片 8 流式解码时分块 */
    };
    ESP_RETURN_ON_ERROR(spi_bus_initialize(BSP_SPI_P4_HOST, &bus_cfg, SPI_DMA_CH_AUTO),
                        TAG, "spi_bus_initialize");

    spi_device_interface_config_t dev_cfg = {
        .clock_speed_hz = BSP_SPI_P4_FREQ_HZ,
        .mode           = 0,             /* MODE 0: CPOL=0, CPHA=0 */
        .spics_io_num   = BSP_SPI_P4_CS_PIN,
        .queue_size     = 4,
        .flags          = 0,             /* HALFDUPLEX 不开, 全双工 */
    };
    ESP_RETURN_ON_ERROR(spi_bus_add_device(BSP_SPI_P4_HOST, &dev_cfg, &s_dev),
                        TAG, "spi_bus_add_device");

    if (s_spi_mutex == NULL) {
        s_spi_mutex = xSemaphoreCreateRecursiveMutex();
        if (s_spi_mutex == NULL) return ESP_ERR_NO_MEM;
    }

    s_inited = true;
    ESP_LOGI(TAG, "init ok");
    return ESP_OK;
}

esp_err_t bsp_spi_p4_transfer(const uint8_t *tx, uint8_t *rx, size_t len)
{
    if (s_dev == NULL)      return ESP_ERR_INVALID_STATE;
    if (s_spi_mutex == NULL) return ESP_ERR_INVALID_STATE;   /* 必须先 init */
    if (len == 0)            return ESP_OK;
    if (tx == NULL && rx == NULL) return ESP_ERR_INVALID_ARG;

    /* 切片 12: recursive mutex 串行化, 防止 recv task + status send task 撞 SPI 外设 */
    if (xSemaphoreTakeRecursive(s_spi_mutex, portMAX_DELAY) != pdTRUE) {
        return ESP_FAIL;
    }

    spi_transaction_t t = {
        .length    = len * 8,
        .tx_buffer = tx,
        .rx_buffer = rx,
    };

    esp_err_t ret = spi_device_polling_transmit(s_dev, &t);
    xSemaphoreGiveRecursive(s_spi_mutex);
    return ret;
}

esp_err_t bsp_spi_p4_cs_low(void)
{
    if (s_dev == NULL) return ESP_ERR_INVALID_STATE;
    /* esp32 spi_master 提供 spi_device_acquire_bus + GPIO 手动控制,
     * 但简单做法: 用一个空的 transaction 也会自动拉 CS.
     * 这里返回 OK 占位, 后续切片要 debug CS 时序再用. */
    return ESP_OK;
}

esp_err_t bsp_spi_p4_cs_high(void)
{
    return ESP_OK;
}
