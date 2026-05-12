#include "avatar_engine.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "jpeg_decoder.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "pin_config.h"
#include "lvgl_port.h"
#include <string.h>

static const char *TAG = "avatar";

static lv_obj_t *s_avatar_img = NULL;
static avatar_state_t s_current_state = AVATAR_STATE_IDLE;
static avatar_state_changed_cb_t s_state_cb = NULL;
static SemaphoreHandle_t s_engine_mux = NULL;
static lv_draw_buf_t *s_frame_buf = NULL;
static st7735s_handle_t *s_lcd = NULL;
static avatar_stats_t s_stats = {0};

#define JPEG_BUF_COUNT 2
static uint8_t *s_jpeg_outbuf[JPEG_BUF_COUNT] = {NULL, NULL};
static uint8_t s_decode_idx = 0;

#if CONFIG_LN_FRAME_DEDUP
static uint32_t s_last_frame_hash = 0;
static uint32_t s_last_frame_len = 0;
#define DEDUP_HEAD_SIZE  64
#define DEDUP_TAIL_SIZE  64
#endif

static const char *state_names[AVATAR_STATE_MAX] = {
    "idle", "happy", "sad", "angry", "surprised",
    "wave", "nod", "think", "sleep", "talk", "custom", "streaming"
};

esp_err_t avatar_engine_init(lv_obj_t *parent, st7735s_handle_t *lcd)
{
    s_engine_mux = xSemaphoreCreateMutex();
    if (!s_engine_mux) return ESP_ERR_NO_MEM;

    s_lcd = lcd;

    uint32_t buf_size = ST7735S_WIDTH * ST7735S_HEIGHT * 2;

    s_frame_buf = lv_draw_buf_create(ST7735S_WIDTH, ST7735S_HEIGHT,
                                      LV_COLOR_FORMAT_RGB565, 0);
    if (!s_frame_buf) {
        ESP_LOGE(TAG, "Failed to create frame buffer");
        return ESP_ERR_NO_MEM;
    }
    memset(s_frame_buf->data, 0, buf_size);

    for (int i = 0; i < JPEG_BUF_COUNT; i++) {
        s_jpeg_outbuf[i] = heap_caps_malloc(buf_size, MALLOC_CAP_SPIRAM);
        if (!s_jpeg_outbuf[i]) {
            ESP_LOGE(TAG, "Failed to allocate JPEG output buffer %d", i);
            return ESP_ERR_NO_MEM;
        }
    }

    s_avatar_img = lv_image_create(parent);
    lv_obj_center(s_avatar_img);
    lv_image_set_src(s_avatar_img, s_frame_buf);

    memset(&s_stats, 0, sizeof(s_stats));

    ESP_LOGI(TAG, "Avatar engine initialized (direct-write, %d states, dedup=%s, double-buf)",
             AVATAR_STATE_MAX,
#if CONFIG_LN_FRAME_DEDUP
             "on"
#else
             "off"
#endif
             );
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

esp_err_t avatar_engine_show_frame(const uint8_t *frame_data, uint32_t frame_len)
{
    if (!frame_data || frame_len == 0) return ESP_ERR_INVALID_ARG;

    s_stats.frames_received++;

#if CONFIG_LN_FRAME_DEDUP
    if (frame_len == s_last_frame_len && s_last_frame_len > 0) {
        uint32_t hash = 2166136261U;
        uint32_t head_len = frame_len > DEDUP_HEAD_SIZE ? DEDUP_HEAD_SIZE : frame_len;
        for (uint32_t i = 0; i < head_len; i++) {
            hash ^= frame_data[i];
            hash *= 16777619U;
        }
        if (frame_len > DEDUP_HEAD_SIZE + DEDUP_TAIL_SIZE) {
            uint32_t tail_offset = frame_len - DEDUP_TAIL_SIZE;
            for (uint32_t i = tail_offset; i < frame_len; i++) {
                hash ^= frame_data[i];
                hash *= 16777619U;
            }
        }
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
    xSemaphoreGive(s_engine_mux);

    uint32_t expected = ST7735S_WIDTH * ST7735S_HEIGHT * 2;
    bool displayed = false;

    if (frame_len != expected) {
        uint8_t decode_idx = s_decode_idx;
        uint8_t *outbuf = s_jpeg_outbuf[decode_idx];

        esp_jpeg_image_cfg_t jpeg_cfg = {
            .indata = (uint8_t *)frame_data,
            .indata_size = frame_len,
            .outbuf = outbuf,
            .outbuf_size = expected,
            .out_format = JPEG_IMAGE_FORMAT_RGB565,
            .out_scale = JPEG_IMAGE_SCALE_0,
            .flags.swap_color_bytes = 1,
        };
        esp_jpeg_image_output_t jpeg_out = {0};

        int64_t t0 = esp_timer_get_time();
        esp_err_t ret = esp_jpeg_decode(&jpeg_cfg, &jpeg_out);
        int64_t t1 = esp_timer_get_time();

        if (ret == ESP_OK) {
            s_stats.last_decode_ms = (uint32_t)((t1 - t0) / 1000);

            st7735s_draw_bitmap(s_lcd, 0, 0, ST7735S_WIDTH, ST7735S_HEIGHT,
                                (uint16_t *)outbuf);

            s_decode_idx = (decode_idx + 1) % JPEG_BUF_COUNT;

            xSemaphoreTake(s_engine_mux, portMAX_DELAY);
            memcpy(s_frame_buf->data, outbuf, expected);
            xSemaphoreGive(s_engine_mux);

            displayed = true;
            s_stats.frames_displayed++;
        } else {
            s_stats.decode_errors++;
            s_stats.frames_skipped_error++;
            ESP_LOGW(TAG, "JPEG decode failed: %s (%u bytes input, errors=%u)",
                     esp_err_to_name(ret), frame_len, s_stats.decode_errors);
        }
    }

    if (!displayed && frame_len == expected) {
        st7735s_draw_bitmap(s_lcd, 0, 0, ST7735S_WIDTH, ST7735S_HEIGHT,
                            (const uint16_t *)frame_data);

        xSemaphoreTake(s_engine_mux, portMAX_DELAY);
        memcpy(s_frame_buf->data, frame_data, expected);
        xSemaphoreGive(s_engine_mux);

        displayed = true;
        s_stats.frames_displayed++;
    }

    if (!displayed) {
        ESP_LOGD(TAG, "Frame skipped (%u bytes)", frame_len);
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
