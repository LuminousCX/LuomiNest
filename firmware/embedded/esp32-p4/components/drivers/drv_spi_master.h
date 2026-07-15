/**
 * LuomiNest P4 - DRV SPI Master 帧协议 (P4 <-> C6)
 * 切片 5b: 9 字节头 + payload + payload CRC16
 *
 * 帧格式 (大端, 见 CLAUDE.md §6):
 *   偏移  长度  字段         说明
 *   0x00  2     magic        固定 0xAA55
 *   0x02  1     type         0x01=JPEG, 0x02=chat, 0x03=cmd, 0x10=status
 *   0x03  2     len          payload 长度 (大端)
 *   0x05  2     seq          帧序号 (大端)
 *   0x07  2     hdr_crc16    CRC16-CCITT (poly 0x1021) 仅覆盖前 7 字节
 *   ----  ---   payload
 *   +     2     pld_crc16    CRC16-CCITT 仅覆盖 payload
 *
 * type 方向 (CLAUDE.md §5):
 *   0x01 / 0x02 / 0x03  : C6 -> P4 (接收)
 *   0x10                : P4 -> C6 (发送, status 上报)
 */

#ifndef DRV_SPI_MASTER_H
#define DRV_SPI_MASTER_H

#include "esp_err.h"
#include <stdint.h>
#include <stddef.h>

#define DRV_SPI_MAGIC            0xAA55
#define DRV_SPI_HDR_SIZE         9
#define DRV_SPI_CRC16_SIZE       2
#define DRV_SPI_TYPE_JPEG        0x01
#define DRV_SPI_TYPE_CHAT        0x02
#define DRV_SPI_TYPE_CMD         0x03
#define DRV_SPI_TYPE_STATUS      0x10

/** 9 字节头解出来的视图. */
typedef struct __attribute__((packed)) {
    uint16_t magic;          /* DRV_SPI_MAGIC */
    uint8_t  type;           /* DRV_SPI_TYPE_* */
    uint16_t len;            /* payload length, 大端 */
    uint16_t seq;            /* frame sequence, 大端 */
    /* 后 2 字节是 hdr_crc16, 不存到 struct 里 */
} drv_spi_hdr_t;

_Static_assert(sizeof(drv_spi_hdr_t) == 7, "hdr struct must be 7 bytes");

/** CRC16-CCITT (poly 0x1021, init 0xFFFF, no reflect, xorout 0x0000).
 *  用软件查表, 切片 8 再换成 256 字节 LUT 加速. */
uint16_t drv_spi_crc16(const uint8_t *data, size_t len);

/** 编码 9 字节头到 out_buf (out_buf 至少 9 字节). */
void drv_spi_encode_hdr(uint8_t *out_buf, uint8_t type, uint16_t len, uint16_t seq);

/** 解码 9 字节头 + 校验 hdr_crc16.
 *  成功返回 ESP_OK, CRC 错返回 ESP_ERR_INVALID_CRC, 格式错 ESP_ERR_INVALID_RESPONSE. */
esp_err_t drv_spi_decode_hdr(const uint8_t *in_buf, drv_spi_hdr_t *out_hdr);

/** 高层: 发送一帧 (hdr + payload + pld_crc16). */
esp_err_t drv_spi_send_frame(uint8_t type, const uint8_t *payload, uint16_t len, uint16_t seq);

/** 高层: 阻塞接收一帧, 写到 out_payload (上限 max_len). 实际 payload 长度写到 *out_len. */
esp_err_t drv_spi_recv_frame(uint8_t *out_type, uint8_t *out_payload, size_t max_len,
                             uint16_t *out_len, uint32_t timeout_ms);

#endif /* DRV_SPI_MASTER_H */
