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

static lv_obj_t *s_avatar_img = NULL;
static avatar_state_t s_current_state = AVATAR_STATE_IDLE;
static avatar_state_changed_cb_t s_state_cb = NULL;
static SemaphoreHandle_t s_engine_mux = NULL;
static lcd_parallel_handle_t *s_lcd = NULL;
static avatar_stats_t s_stats = {0};
static avatar_mode_t s_mode = AVATAR_MODE_HYBRID;
static bool s_mqtt_online = false;

static uint8_t *s_decode_buf = NULL;
static uint32_t s_decode_buf_size = 0;

#define STATS_LOG_INTERVAL 500

#if CONFIG_LN_FRAME_DEDUP
static uint32_t s_last_frame_hash = 0;
static uint32_t s_last_frame_len = 0;
#define DEDUP_SAMPLE_SIZE 128
#endif

static const char *state_names[AVATAR_STATE_MAX] = {
    "idle", "happy", "sad", "angry", "surprised",
    "wave", "nod", "think", "sleep", "talk", "custom", "streaming"
};

static const char *local_state_names[] = {
    "idle", "sleep", "neutral", NULL
};

bool avatar_engine_is_local_state(avatar_state_t state)
{
    const char *name = state_names[state];
    for (int i = 0; local_state_names[i] != NULL; i++) {
        if (strcmp(name, local_state_names[i]) == 0) {
            return true;
        }
    }
    return false;
}

const char *avatar_engine_state_name(avatar_state_t state)
{
    if (state >= AVATAR_STATE_MAX) return "unknown";
    return state_names[state];
}

static bool should_use_local(avatar_state_t state)
{
    if (s_mode == AVATAR_MODE_LOCAL) return true;
    if (s_mode == AVATAR_MODE_STREAM) return false;
    if (!s_mqtt_online) return true;
    if (avatar_engine_is_local_state(state)) return true;
    return false;
}

static void on_local_playback_done(const char *sequence_name)
{
    avatar_engine_play_state(AVATAR_STATE_IDLE);
}

static esp_err_t jpeg_decode_and_show(const uint8_t *frame_data, uint32_t frame_len)
{
    if (!s_decode_buf || !s_lcd) return ESP_FAIL;

    esp_jpeg_image_cfg_t jpeg_cfg = {
        .indata = frame_data,
        .indata_size = frame_len,
        .outbuf = s_decode_buf,
        .outbuf_size = s_decode_buf_size,
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

        lcd_parallel_draw_bitmap(s_lcd, 0, 0, ILI9486_WIDTH, ILI9486_HEIGHT,
                                 (uint16_t *)s_decode_buf);

        s_stats.frames_displayed++;
        return ESP_OK;
    } else {
        s_stats.decode_errors++;
        s_stats.frames_skipped_error++;
        return ESP_FAIL;
    }
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

    s_avatar_img = lv_image_create(parent);
    lv_obj_center(s_avatar_img);

    ESP_ERROR_CHECK(frame_player_init());
    frame_player_register_frame_cb(avatar_engine_on_local_frame);
    frame_player_register_done_cb(on_local_playback_done);

    memset(&s_stats, 0, sizeof(s_stats));

    ESP_LOGI(TAG, "Avatar engine initialized (direct LCD, decode_buf=%u, free PSRAM=%u)",
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

    if (should_use_local(state)) {
        frame_player_stop();
        const char *name = state_names[state];
        esp_err_t ret = frame_player_start(name, 15, true);
        if (ret == ESP_OK) return ESP_OK;
    } else {
        frame_player_stop();
    }

    return ESP_OK;
}

esp_err_t avatar_engine_play_action(const char *action_name, uint16_t frame_count,
                                     uint16_t fps, bool loop)
{
    if (!action_name) return ESP_ERR_INVALID_ARG;
    xSemaphoreTake(s_engine_mux, portMAX_DELAY);
    s_current_state = AVATAR_STATE_CUSTOM;
    xSemaphoreGive(s_engine_mux);
    return ESP_OK;
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

esp_err_t avatar_engine_show_frame(const uint8_t *frame_data, uint32_t frame_len)
{
    if (!frame_data || frame_len == 0) return ESP_ERR_INVALID_ARG;

    if (frame_player_is_playing()) return ESP_OK;

    s_stats.frames_received++;

#if CONFIG_LN_FRAME_DEDUP
    if (frame_len == s_last_frame_len && s_last_frame_len > 0) {
        uint32_t tail_offset = frame_len > DEDUP_SAMPLE_SIZE ? frame_len - DEDUP_SAMPLE_SIZE : 0;
        uint32_t hash = 2166136261U;
        for (uint32_t i = tail_offset; i < frame_len; i++) {
            hash ^= frame_data[i];
            hash *= 16777619U;
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

    esp_err_t result = jpeg_decode_and_show(frame_data, frame_len);

    if (s_stats.frames_displayed > 0 && s_stats.frames_displayed % STATS_LOG_INTERVAL == 0) {
        ESP_LOGI(TAG, "Stream[%u]: decode=%ums, rx=%u show=%u err=%u",
                 (unsigned)s_stats.frames_displayed,
                 (unsigned)s_stats.last_decode_ms,
                 (unsigned)s_stats.frames_received,
                 (unsigned)s_stats.frames_displayed,
                 (unsigned)s_stats.decode_errors);
    }

    return result;
}

void avatar_engine_on_local_frame(const uint8_t *jpeg_data, uint32_t jpeg_len)
{
    if (!jpeg_data || jpeg_len == 0) return;

    esp_err_t result = jpeg_decode_and_show(jpeg_data, jpeg_len);
    if (result == ESP_OK) {
        s_stats.local_frames_played++;
    }

    if (s_stats.local_frames_played > 0 && s_stats.local_frames_played % STATS_LOG_INTERVAL == 0) {
        ESP_LOGI(TAG, "Local[%u]: decode=%ums",
                 (unsigned)s_stats.local_frames_played,
                 (unsigned)s_stats.last_decode_ms);
    }
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

esp_err_t avatar_engine_set_mode(avatar_mode_t mode)
{
    xSemaphoreTake(s_engine_mux, portMAX_DELAY);
    s_mode = mode;
    xSemaphoreGive(s_engine_mux);

    ESP_LOGI(TAG, "Avatar mode set to: %s",
             mode == AVATAR_MODE_HYBRID ? "HYBRID" : (mode == AVATAR_MODE_LOCAL ? "LOCAL" : "STREAM"));
    return ESP_OK;
}

avatar_mode_t avatar_engine_get_mode(void)
{
    return s_mode;
}

esp_err_t avatar_engine_set_mqtt_online(bool online)
{
    bool was_online = s_mqtt_online;
    s_mqtt_online = online;

    if (was_online && !online) {
        avatar_engine_play_state(AVATAR_STATE_IDLE);
    } else if (!was_online && online) {
        if (s_mode == AVATAR_MODE_HYBRID && frame_player_is_playing()) {
            if (!avatar_engine_is_local_state(s_current_state)) {
                frame_player_stop();
            }
        }
    }

    return ESP_OK;
}
