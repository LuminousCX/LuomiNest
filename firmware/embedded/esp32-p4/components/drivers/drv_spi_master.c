/**
 * LuomiNest P4 - DRV SPI Master 帧协议实现
 * 切片 5b: CRC16-CCITT + 9 字节头 + 收发
 *
 * 这一层不直接调 ESP-IDF SPI HAL, 而是调 bsp_spi_p4_transfer.
 * 这样 drv_spi_master 不知道引脚和 freq, 只知道"有 9 字节头+payload".
 */

#include "drv_spi_master.h"
#include "bsp_spi_p4.h"
#include "esp_log.h"
#include "esp_check.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "drv_spi_master";

/* === CRC16-CCITT (poly 0x1021, init 0xFFFF) === */
uint16_t drv_spi_crc16(const uint8_t *data, size_t len)
{
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (int b = 0; b < 8; b++) {
            if (crc & 0x8000) crc = (crc << 1) ^ 0x1021;
            else              crc = (crc << 1);
        }
    }
    return crc;
}

void drv_spi_encode_hdr(uint8_t *out_buf, uint8_t type, uint16_t len, uint16_t seq)
{
    out_buf[0] = (DRV_SPI_MAGIC >> 8) & 0xFF;   /* 0xAA */
    out_buf[1] = DRV_SPI_MAGIC & 0xFF;          /* 0x55 */
    out_buf[2] = type;
    out_buf[3] = (len >> 8) & 0xFF;
    out_buf[4] = len & 0xFF;
    out_buf[5] = (seq >> 8) & 0xFF;
    out_buf[6] = seq & 0xFF;
    uint16_t crc = drv_spi_crc16(out_buf, 7);
    out_buf[7] = (crc >> 8) & 0xFF;
    out_buf[8] = crc & 0xFF;
}

esp_err_t drv_spi_decode_hdr(const uint8_t *in_buf, drv_spi_hdr_t *out_hdr)
{
    uint16_t magic = ((uint16_t)in_buf[0] << 8) | in_buf[1];
    if (magic != DRV_SPI_MAGIC) {
        ESP_LOGW(TAG, "decode_hdr: bad magic 0x%04X", magic);
        return ESP_ERR_INVALID_RESPONSE;
    }

    uint16_t got_crc = ((uint16_t)in_buf[7] << 8) | in_buf[8];
    uint16_t exp_crc = drv_spi_crc16(in_buf, 7);
    if (got_crc != exp_crc) {
        ESP_LOGW(TAG, "hdr_crc mismatch got=0x%04X exp=0x%04X", got_crc, exp_crc);
        return ESP_ERR_INVALID_CRC;
    }

    out_hdr->magic = magic;
    out_hdr->type  = in_buf[2];
    out_hdr->len   = ((uint16_t)in_buf[3] << 8) | in_buf[4];
    out_hdr->seq   = ((uint16_t)in_buf[5] << 8) | in_buf[6];
    return ESP_OK;
}

esp_err_t drv_spi_send_frame(uint8_t type, const uint8_t *payload, uint16_t len, uint16_t seq)
{
    if (len > 0 && payload == NULL) return ESP_ERR_INVALID_ARG;

    /* 拼成一块大 buffer: hdr(9) + payload + crc16(2) */
    const size_t total = DRV_SPI_HDR_SIZE + len + DRV_SPI_CRC16_SIZE;
    uint8_t *buf = malloc(total);
    if (buf == NULL) return ESP_ERR_NO_MEM;

    drv_spi_encode_hdr(buf, type, len, seq);
    if (len > 0) memcpy(buf + DRV_SPI_HDR_SIZE, payload, len);
    uint16_t pld_crc = drv_spi_crc16(payload, len);
    buf[DRV_SPI_HDR_SIZE + len    ] = (pld_crc >> 8) & 0xFF;
    buf[DRV_SPI_HDR_SIZE + len + 1] = pld_crc & 0xFF;

    esp_err_t ret = bsp_spi_p4_transfer(buf, NULL, total);
    free(buf);
    return ret;
}

esp_err_t drv_spi_recv_frame(uint8_t *out_type, uint8_t *out_payload, size_t max_len,
                             uint16_t *out_len, uint32_t timeout_ms)
{
    if (out_payload == NULL || out_len == NULL) return ESP_ERR_INVALID_ARG;

    /* 1. 收 9 字节头 */
    uint8_t hdr[DRV_SPI_HDR_SIZE] = {0};
    int64_t t0 = esp_timer_get_time();
    while (1) {
        esp_err_t ret = bsp_spi_p4_transfer(NULL, hdr, DRV_SPI_HDR_SIZE);
        if (ret == ESP_OK) break;
        if ((esp_timer_get_time() - t0) / 1000 > timeout_ms) {
            return ESP_ERR_TIMEOUT;
        }
        vTaskDelay(pdMS_TO_TICKS(1));
    }

    drv_spi_hdr_t h = {0};
    ESP_RETURN_ON_ERROR(drv_spi_decode_hdr(hdr, &h), TAG, "decode_hdr");

    if (h.len > max_len) {
        ESP_LOGE(TAG, "payload %u > max %u", h.len, (unsigned)max_len);
        return ESP_ERR_NO_MEM;
    }

    /* 2. 收 payload */
    if (h.len > 0) {
        ESP_RETURN_ON_ERROR(bsp_spi_p4_transfer(NULL, out_payload, h.len), TAG, "rx payload");
    }

    /* 3. 收 payload CRC16 */
    uint8_t crc_bytes[2] = {0};
    ESP_RETURN_ON_ERROR(bsp_spi_p4_transfer(NULL, crc_bytes, 2), TAG, "rx pld_crc");
    uint16_t got_crc = ((uint16_t)crc_bytes[0] << 8) | crc_bytes[1];
    uint16_t exp_crc = drv_spi_crc16(out_payload, h.len);
    if (got_crc != exp_crc) {
        ESP_LOGW(TAG, "pld_crc mismatch got=0x%04X exp=0x%04X", got_crc, exp_crc);
        return ESP_ERR_INVALID_CRC;
    }

    *out_type = h.type;
    *out_len  = h.len;
    ESP_LOGI(TAG, "recv type=0x%02X len=%u seq=%u", h.type, h.len, h.seq);
    return ESP_OK;
}
