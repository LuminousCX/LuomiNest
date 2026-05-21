#include "avatar_engine.h"
#include "frame_player.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "jpeg_decoder.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "pin_config.h"
#include <string.h>

static const char *TAG = "avatar";

static avatar_state_t s_current_state = AVATAR_STATE_IDLE;
static avatar_state_changed_cb_t s_state_cb = NULL;
static SemaphoreHandle_t s_engine_mux = NULL;
static lcd_parallel_handle_t *s_lcd = NULL;
static avatar_stats_t s_stats = {0};

static uint8_t *s_decode_buf = NULL;
static uint32_t s_decode_buf_size = 0;

#define STATS_LOG_INTERVAL 200

static const char *state_names[AVATAR_STATE_MAX] = {
    "idle", "happy", "sad", "angry", "surprised",
    "wave", "nod", "think", "sleep", "talk", "custom"
};

const char *avatar_engine_state_name(avatar_state_t state)
{
    if (state >= AVATAR_STATE_MAX) return "unknown";
    return state_names[state];
}

static void on_playback_done(const char *sequence_name)
{
    avatar_engine_play_state(AVATAR_STATE_IDLE);
}

static void show_jpeg_frame(const uint8_t *jpeg_data, uint32_t jpeg_len)
{
    if (!s_decode_buf || !s_lcd) return;

    int64_t t0 = esp_timer_get_time();

    esp_jpeg_image_cfg_t jpeg_cfg = {
        .indata = jpeg_data,
        .indata_size = jpeg_len,
        .outbuf = s_decode_buf,
        .outbuf_size = s_decode_buf_size,
        .out_format = JPEG_IMAGE_FORMAT_RGB565,
        .out_scale = JPEG_IMAGE_SCALE_0,
        .flags.swap_color_bytes = 1,
    };
    esp_jpeg_image_output_t jpeg_out = {0};

    esp_err_t ret = esp_jpeg_decode(&jpeg_cfg, &jpeg_out);
    if (ret == ESP_OK) {
        lcd_parallel_draw_bitmap(s_lcd, 0, 0, ILI9486_WIDTH, ILI9486_HEIGHT,
                                 (uint16_t *)s_decode_buf);
        int64_t t1 = esp_timer_get_time();
        s_stats.last_frame_ms = (uint32_t)((t1 - t0) / 1000);
        s_stats.frames_displayed++;
    } else {
        s_stats.decode_errors++;
    }
}

static void show_raw_frame(const uint8_t *raw_data, uint32_t raw_len)
{
    if (!s_lcd) return;

    int64_t t0 = esp_timer_get_time();

    lcd_parallel_draw_bitmap(s_lcd, 0, 0, ILI9486_WIDTH, ILI9486_HEIGHT,
                             (const uint16_t *)raw_data);

    int64_t t1 = esp_timer_get_time();
    s_stats.last_frame_ms = (uint32_t)((t1 - t0) / 1000);
    s_stats.frames_displayed++;
}

esp_err_t avatar_engine_init(lv_obj_t *parent, lcd_parallel_handle_t *lcd)
{
    s_engine_mux = xSemaphoreCreateMutex();
    if (!s_engine_mux) return ESP_ERR_NO_MEM;

    s_lcd = lcd;

    uint32_t rgb_size = ILI9486_WIDTH * ILI9486_HEIGHT * 2;
    s_decode_buf_size = rgb_size + (ILI9486_WIDTH * ILI9486_HEIGHT);
    s_decode_buf = heap_caps_malloc(s_decode_buf_size, MALLOC_CAP_SPIRAM);
    if (!s_decode_buf) {
        ESP_LOGE(TAG, "Failed to alloc decode buffer (%u bytes)", (unsigned)s_decode_buf_size);
        return ESP_ERR_NO_MEM;
    }

    ESP_ERROR_CHECK(frame_player_init());
    frame_player_register_frame_cb(avatar_engine_on_frame);
    frame_player_register_done_cb(on_playback_done);

    memset(&s_stats, 0, sizeof(s_stats));

    ESP_LOGI(TAG, "Avatar engine initialized (decode_buf=%u, free PSRAM=%u)",
             (unsigned)s_decode_buf_size,
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
    return ESP_OK;
}

esp_err_t avatar_engine_play_state(avatar_state_t state)
{
    if (state >= AVATAR_STATE_MAX) return ESP_ERR_INVALID_ARG;

    xSemaphoreTake(s_engine_mux, portMAX_DELAY);
    s_current_state = state;
    xSemaphoreGive(s_engine_mux);

    if (s_state_cb) s_state_cb(state);

    frame_player_stop();
    const char *name = state_names[state];
    esp_err_t ret = frame_player_start(name, 15, true);

    return ret;
}

esp_err_t avatar_engine_stop(void)
{
    frame_player_stop();
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

void avatar_engine_on_frame(const uint8_t *data, uint32_t len, frame_format_t format)
{
    if (!data || len == 0) return;

    if (format == FRAME_FORMAT_RGB565) {
        show_raw_frame(data, len);
    } else {
        show_jpeg_frame(data, len);
    }

    s_stats.local_frames_played++;

    if (s_stats.local_frames_played > 0 && s_stats.local_frames_played % STATS_LOG_INTERVAL == 0) {
        ESP_LOGI(TAG, "[%u] %s %ums/frame",
                 (unsigned)s_stats.local_frames_played,
                 format == FRAME_FORMAT_RGB565 ? "RAW" : "JPEG",
                 (unsigned)s_stats.last_frame_ms);
    }
}

const avatar_stats_t *avatar_engine_get_stats(void)
{
    return &s_stats;
}

void avatar_engine_reset_stats(void)
{
    memset(&s_stats, 0, sizeof(s_stats));
}
