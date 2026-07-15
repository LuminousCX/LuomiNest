/**
 * LuomiNest P4 - DRV JPEG 硬解 (P4 硬件 JPEG 解码器)
 * 切片 4: 解 1 张 JPEG → RGB565 → 画到 LCD (旧 API: drv_jpeg_decode_to_lcd)
 * 切片 9 重构: 改成 drv_jpeg_decode_to_buf, 输出到调用方提供的 RGB565 缓冲
 *                (一般是 lv_draw_buf_t->data), 不再调 bsp_lcd 直接画.
 *
 * 关键修正: flags.swap_color_bytes = 0 (RGB, 旧工程 BGR 是 bug, 红蓝颠倒)
 *           out_format = JPEG_IMAGE_FORMAT_RGB565
 */

#ifndef DRV_JPEG_H
#define DRV_JPEG_H

#include "esp_err.h"
#include <stdint.h>

/**
 * 解 1 张 JPEG → 调用方提供的 RGB565 缓冲.
 * 调用方负责分配 / 释放 (一般是 lv_draw_buf_t->data, size >= width*height*2).
 * esp_jpeg 硬解, RGB565 颜色顺序 RGB.
 *
 * @param jpg        JPEG 字节流 (baseline, 4:4:4 subsampling=0)
 * @param jpg_len    字节数
 * @param out_buf    调用方提供的 RGB565 输出缓冲
 * @param out_buf_sz out_buf 字节数 (>= width*height*2, 16 字节对齐更好)
 * @param out_w      实际解码宽度
 * @param out_h      实际解码高度
 */
esp_err_t drv_jpeg_decode_to_buf(const uint8_t *jpg, uint32_t jpg_len,
                                 uint16_t *out_buf, uint32_t out_buf_sz,
                                 uint16_t *out_w, uint16_t *out_h);

#endif /* DRV_JPEG_H */
