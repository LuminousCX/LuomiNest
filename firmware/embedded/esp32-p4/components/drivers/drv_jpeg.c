/**
 * LuomiNest P4 - DRV JPEG 硬解
 * 切片 9 重构: 解 1 张 JPEG → 调用方提供的 RGB565 缓冲 (不画到 LCD)
 *                app 层拿到 buf 后, 走 lv_image_set_src 让 LVGL 接管 DSI.
 *
 * 协议解耦点: drivers 层不 include bsp_lcd.h / esp_lcd_panel_ops.h
 */

#include "drv_jpeg.h"
#include "esp_log.h"
#include "esp_check.h"
#include "jpeg_decoder.h"

static const char *TAG = "drv_jpeg";

esp_err_t drv_jpeg_decode_to_buf(const uint8_t *jpg, uint32_t jpg_len,
                                 uint16_t *out_buf, uint32_t out_buf_sz,
                                 uint16_t *out_w, uint16_t *out_h)
{
    if (jpg == NULL || jpg_len == 0)  return ESP_ERR_INVALID_ARG;
    if (out_buf == NULL)              return ESP_ERR_INVALID_ARG;
    if (out_buf_sz < 1024)            return ESP_ERR_INVALID_ARG;  /* 至少 1 KB */

    /* esp_jpeg 硬解: RGB565, RGB 顺序 (不是 BGR).
     * 旧工程用 BGR 是 bug, 红蓝颠倒. */
    esp_jpeg_image_cfg_t cfg = {
        .indata      = (uint8_t *)jpg,
        .indata_size = jpg_len,
        .outbuf      = (uint8_t *)out_buf,
        .outbuf_size = out_buf_sz,
        .out_format  = JPEG_IMAGE_FORMAT_RGB565,
        .out_scale   = JPEG_IMAGE_SCALE_0,
        .flags = {
            .swap_color_bytes = 0,   /* RGB 输出, 1 会变 BGR */
        },
    };

    esp_jpeg_image_output_t outimg = {0};
    esp_err_t ret = esp_jpeg_decode(&cfg, &outimg);
    ESP_RETURN_ON_ERROR(ret, TAG, "esp_jpeg_decode");

    if (out_w) *out_w = outimg.width;
    if (out_h) *out_h = outimg.height;

    ESP_LOGD(TAG, "decoded %ux%u", outimg.width, outimg.height);
    return ESP_OK;
}
