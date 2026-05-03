#include "avatar_engine.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "driver/jpeg_decode.h"
#include "esp_lvgl_port.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include <string.h>

static const char *TAG = "avatar";

static lv_obj_t *s_avatar_img = NULL;
static avatar_state_t s_current_state = AVATAR_STATE_IDLE;
static avatar_state_changed_cb_t s_state_cb = NULL;
static SemaphoreHandle_t s_engine_mux = NULL;
static lv_draw_buf_t *s_frame_buf = NULL;

static jpeg_decoder_handle_t s_jpeg_decoder = NULL;
static uint8_t *s_jpeg_out_buf = NULL;
static uint32_t s_jpeg_out_buf_size = 0;

#define HW_JPEG_ALIGN 16
#define AVATAR_HEIGHT_ALIGNED ((AVATAR_HEIGHT + HW_JPEG_ALIGN - 1) / HW_JPEG_ALIGN * HW_JPEG_ALIGN)
#define AVATAR_ROW_BYTES (AVATAR_WIDTH * 2)
#define AVATAR_ALIGNED_ROW_BYTES (AVATAR_WIDTH * 2)

#define AVATAR_POS_ALIGN   LV_ALIGN_BOTTOM_RIGHT
#define AVATAR_POS_X_OFF   -30
#define AVATAR_POS_Y_OFF   -20

#define STATS_LOG_INTERVAL 100

static avatar_stats_t s_stats = {0};

#if CONFIG_LN_FRAME_DEDUP
static uint32_t s_last_frame_hash = 0;
static uint32_t s_last_frame_len = 0;
#define DEDUP_SAMPLE_SIZE 128
#endif

static const char *state_names[AVATAR_STATE_MAX] = {
    "idle", "happy", "sad", "angry", "surprised",
    "think", "neutral", "talk", "custom", "streaming"
};

static uint32_t fnv1a_hash(const uint8_t *data, uint32_t len)
{
    uint32_t hash = 2166136261U;
    for (uint32_t i = 0; i < len; i++) {
        hash ^= data[i];
        hash *= 16777619U;
    }
    return hash;
}

esp_err_t avatar_engine_init(lv_obj_t *parent)
{
    s_engine_mux = xSemaphoreCreateMutex();
    if (!s_engine_mux) return ESP_ERR_NO_MEM;

    uint32_t expected_raw = AVATAR_WIDTH * AVATAR_HEIGHT * 2;
    uint32_t aligned_raw = AVATAR_WIDTH * AVATAR_HEIGHT_ALIGNED * 2;

    ESP_LOGI(TAG, "Init: %dx%d (raw=%u, aligned=%dx%d=%u), free PSRAM=%u",
             AVATAR_WIDTH, AVATAR_HEIGHT, (unsigned)expected_raw,
             AVATAR_WIDTH, AVATAR_HEIGHT_ALIGNED, (unsigned)aligned_raw,
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));

    s_frame_buf = lv_draw_buf_create(AVATAR_WIDTH, AVATAR_HEIGHT,
                                      LV_COLOR_FORMAT_RGB565, 0);
    if (!s_frame_buf) {
        ESP_LOGE(TAG, "Failed to create frame buffer (%dx%d)", AVATAR_WIDTH, AVATAR_HEIGHT);
        return ESP_ERR_NO_MEM;
    }

    memset(s_frame_buf->data, 0, expected_raw);

    s_avatar_img = lv_image_create(parent);
    if (!s_avatar_img) {
        ESP_LOGE(TAG, "Failed to create image widget");
        return ESP_FAIL;
    }
    lv_obj_set_size(s_avatar_img, AVATAR_WIDTH, AVATAR_HEIGHT);
    lv_obj_align(s_avatar_img, AVATAR_POS_ALIGN, AVATAR_POS_X_OFF, AVATAR_POS_Y_OFF);
    lv_image_set_src(s_avatar_img, s_frame_buf);

    memset(&s_stats, 0, sizeof(s_stats));

    jpeg_decode_engine_cfg_t dec_eng_cfg = {
        .intr_priority = 0,
        .timeout_ms = 500,
    };
    esp_err_t ret = jpeg_new_decoder_engine(&dec_eng_cfg, &s_jpeg_decoder);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to create HW JPEG decoder: %s", esp_err_to_name(ret));
        return ret;
    }

    s_jpeg_out_buf_size = aligned_raw;
    jpeg_decode_memory_alloc_cfg_t mem_cfg = {
        .buffer_direction = JPEG_DEC_ALLOC_OUTPUT_BUFFER,
    };
    size_t allocated = 0;
    s_jpeg_out_buf = jpeg_alloc_decoder_mem(s_jpeg_out_buf_size, &mem_cfg, &allocated);
    if (!s_jpeg_out_buf) {
        ESP_LOGE(TAG, "Failed to alloc JPEG output buffer (%u bytes)", (unsigned)s_jpeg_out_buf_size);
        return ESP_ERR_NO_MEM;
    }

    ESP_LOGI(TAG, "HW JPEG decoder ready: out_buf=%p (%u alloc), free PSRAM=%u",
             s_jpeg_out_buf, (unsigned)allocated,
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
    return ESP_OK;
}

esp_err_t avatar_engine_fill_test(uint16_t color565)
{
    if (!s_frame_buf || !s_avatar_img) return ESP_ERR_INVALID_STATE;

    xSemaphoreTake(s_engine_mux, portMAX_DELAY);

    uint32_t pixel_count = AVATAR_WIDTH * AVATAR_HEIGHT;
    uint16_t *pixels = (uint16_t *)s_frame_buf->data;
    for (uint32_t i = 0; i < pixel_count; i++) {
        pixels[i] = color565;
    }

    lvgl_port_lock(5000);
    lv_image_set_src(s_avatar_img, s_frame_buf);
    lv_obj_invalidate(s_avatar_img);
    lvgl_port_unlock();

    xSemaphoreGive(s_engine_mux);
    return ESP_OK;
}

esp_err_t avatar_engine_play_state(avatar_state_t state)
{
    if (state >= AVATAR_STATE_MAX) return ESP_ERR_INVALID_ARG;

    xSemaphoreTake(s_engine_mux, portMAX_DELAY);
    s_current_state = state;
    xSemaphoreGive(s_engine_mux);

    if (s_state_cb) s_state_cb(state);

    ESP_LOGI(TAG, "State: %s", state_names[state]);
    return ESP_OK;
}

esp_err_t avatar_engine_play_action(const char *action_name, uint16_t frame_count,
                                     uint16_t fps, bool loop)
{
    if (!action_name) return ESP_ERR_INVALID_ARG;

    xSemaphoreTake(s_engine_mux, portMAX_DELAY);
    s_current_state = AVATAR_STATE_CUSTOM;
    xSemaphoreGive(s_engine_mux);

    ESP_LOGI(TAG, "Action: %s", action_name);
    return ESP_OK;
}

esp_err_t avatar_engine_stop(void)
{
    xSemaphoreTake(s_engine_mux, portMAX_DELAY);
    s_current_state = AVATAR_STATE_IDLE;
    xSemaphoreGive(s_engine_mux);
    return ESP_OK;
}

avatar_state_t avatar_engine_get_state(void)
{
    return s_current_state;
}

esp_err_t avatar_engine_register_state_cb(avatar_state_changed_cb_t cb)
{
    s_state_cb = cb;
    return ESP_OK;
}

static void copy_aligned_to_framebuf(const uint8_t *src, uint8_t *dst,
                                      uint32_t src_stride, uint32_t dst_stride,
                                      uint32_t row_bytes, int rows)
{
    for (int y = 0; y < rows; y++) {
        memcpy(dst, src, row_bytes);
        src += src_stride;
        dst += dst_stride;
    }
}

esp_err_t avatar_engine_show_frame(const uint8_t *frame_data, uint32_t frame_len)
{
    if (!frame_data || frame_len == 0) return ESP_ERR_INVALID_ARG;

    s_stats.frames_received++;

#if CONFIG_LN_FRAME_DEDUP
    if (frame_len == s_last_frame_len && s_last_frame_len > 0) {
        uint32_t tail_offset = frame_len > DEDUP_SAMPLE_SIZE ? frame_len - DEDUP_SAMPLE_SIZE : 0;
        uint32_t hash = fnv1a_hash(frame_data + tail_offset, frame_len - tail_offset);
        if (hash == s_last_frame_hash) {
            s_stats.frames_skipped_dedup++;
            return ESP_OK;
        }
        s_last_frame_hash = hash;
    }
    s_last_frame_len = frame_len;
#endif

    xSemaphoreTake(s_engine_mux, portMAX_DELAY);

    s_current_state = AVATAR_STATE_STREAMING;

    uint32_t expected_raw = AVATAR_WIDTH * AVATAR_HEIGHT * 2;
    bool displayed = false;

    if (frame_len != expected_raw) {
        if (!s_jpeg_decoder || !s_jpeg_out_buf) {
            s_stats.frames_skipped_error++;
            xSemaphoreGive(s_engine_mux);
            return ESP_FAIL;
        }

        jpeg_decode_cfg_t decode_cfg = {
            .output_format = JPEG_DECODE_OUT_FORMAT_RGB565,
            .rgb_order = JPEG_DEC_RGB_ELEMENT_ORDER_BGR,
            .conv_std = JPEG_YUV_RGB_CONV_STD_BT601,
        };

        uint32_t out_size = 0;
        int64_t t0 = esp_timer_get_time();
        esp_err_t ret = jpeg_decoder_process(s_jpeg_decoder, &decode_cfg,
                                              frame_data, frame_len,
                                              s_jpeg_out_buf, s_jpeg_out_buf_size,
                                              &out_size);
        int64_t t1 = esp_timer_get_time();
        uint32_t decode_ms = (uint32_t)((t1 - t0) / 1000);

        if (ret == ESP_OK && out_size > 0) {
            s_stats.last_decode_ms = decode_ms;

            uint32_t src_stride = AVATAR_ALIGNED_ROW_BYTES;
            uint32_t dst_stride = s_frame_buf->header.stride;

            copy_aligned_to_framebuf(s_jpeg_out_buf, s_frame_buf->data,
                                      src_stride, dst_stride,
                                      AVATAR_ROW_BYTES, AVATAR_HEIGHT);

            lvgl_port_lock(5000);
            lv_image_set_src(s_avatar_img, s_frame_buf);
            lv_obj_invalidate(s_avatar_img);
            lvgl_port_unlock();
            displayed = true;
            s_stats.frames_displayed++;
        } else {
            s_stats.decode_errors++;
            s_stats.frames_skipped_error++;
            ESP_LOGE(TAG, "HW JPEG err: %s, out=%u", esp_err_to_name(ret), (unsigned)out_size);
        }
    }

    if (!displayed && frame_len == expected_raw) {
        uint32_t stride = s_frame_buf->header.stride;
        if (stride == AVATAR_ROW_BYTES) {
            memcpy(s_frame_buf->data, frame_data, expected_raw);
        } else {
            copy_aligned_to_framebuf(frame_data, s_frame_buf->data,
                                      AVATAR_ROW_BYTES, stride,
                                      AVATAR_ROW_BYTES, AVATAR_HEIGHT);
        }
        lvgl_port_lock(5000);
        lv_image_set_src(s_avatar_img, s_frame_buf);
        lv_obj_invalidate(s_avatar_img);
        lvgl_port_unlock();
        displayed = true;
        s_stats.frames_displayed++;
    }

    if (!displayed) {
        ESP_LOGW(TAG, "Frame NOT displayed (%u bytes)", (unsigned)frame_len);
    }

    xSemaphoreGive(s_engine_mux);

    if (s_stats.frames_displayed % STATS_LOG_INTERVAL == 0 && s_stats.frames_displayed > 0) {
        ESP_LOGI(TAG, "Stats[%u]: decode=%ums, rx=%u show=%u err=%u",
                 (unsigned)s_stats.frames_displayed,
                 (unsigned)s_stats.last_decode_ms,
                 (unsigned)s_stats.frames_received,
                 (unsigned)s_stats.frames_displayed,
                 (unsigned)s_stats.decode_errors);
    }

    return displayed ? ESP_OK : ESP_FAIL;
}

esp_err_t avatar_engine_set_mouth_openness(uint8_t percent)
{
    (void)percent;
    return ESP_OK;
}

const avatar_stats_t *avatar_engine_get_stats(void)
{
    return &s_stats;
}

void avatar_engine_reset_stats(void)
{
    memset(&s_stats, 0, sizeof(s_stats));
}
