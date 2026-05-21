#include "frame_player.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "pin_config.h"
#include <string.h>
#include <sys/stat.h>

static const char *TAG = "frame_player";

#define NOTIFY_START_BIT  (1 << 0)
#define NOTIFY_STOP_BIT   (1 << 1)

#define FRAME_BUF_SIZE (400 * 1024)

typedef struct {
    char name[32];
    uint16_t frame_count;
    uint16_t fps;
    bool loop;
    frame_format_t format;
} sequence_info_t;

static TaskHandle_t s_task = NULL;
static volatile bool s_stop_requested = false;
static volatile bool s_is_playing = false;
static sequence_info_t s_current_seq = {0};
static frame_player_frame_cb_t s_frame_cb = NULL;
static frame_player_done_cb_t s_done_cb = NULL;
static SemaphoreHandle_t s_seq_mux = NULL;

static uint8_t *s_frame_buf_a = NULL;
static uint8_t *s_frame_buf_b = NULL;
static uint32_t s_prefetch_len = 0;
static uint16_t s_prefetch_idx = 0;
static bool s_prefetch_valid = false;
static uint8_t *s_display_buf = NULL;
static uint8_t *s_read_buf = NULL;

static bool file_exists(const char *path)
{
    struct stat st;
    return (stat(path, &st) == 0);
}

static frame_format_t detect_format(const char *dir_path)
{
    char test_path[192];
    snprintf(test_path, sizeof(test_path), "%s/0001.raw", dir_path);
    if (file_exists(test_path)) return FRAME_FORMAT_RGB565;

    snprintf(test_path, sizeof(test_path), "%s/0001.jpg", dir_path);
    if (file_exists(test_path)) return FRAME_FORMAT_JPEG;

    return FRAME_FORMAT_JPEG;
}

static uint16_t count_frames(const char *dir_path, frame_format_t format)
{
    uint16_t count = 0;
    char file_path[192];
    const char *ext = (format == FRAME_FORMAT_RGB565) ? "raw" : "jpg";
    while (true) {
        snprintf(file_path, sizeof(file_path), "%s/%04d.%s", dir_path, count + 1, ext);
        if (!file_exists(file_path)) break;
        count++;
    }
    return count;
}

static uint32_t read_frame_file(const char *path, uint8_t *buf, uint32_t buf_size)
{
    FILE *f = fopen(path, "rb");
    if (!f) return 0;

    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);

    if (size <= 0 || (uint32_t)size > buf_size) {
        fclose(f);
        return 0;
    }

    if (fread(buf, 1, size, f) != (size_t)size) {
        fclose(f);
        return 0;
    }

    fclose(f);
    return (uint32_t)size;
}

static void build_frame_path(char *out, size_t out_size,
                              const char *dir_path, uint16_t idx, frame_format_t fmt)
{
    const char *ext = (fmt == FRAME_FORMAT_RGB565) ? "raw" : "jpg";
    snprintf(out, out_size, "%s/%04d.%s", dir_path, idx, ext);
}

static void player_task(void *arg)
{
    while (true) {
        xTaskNotifyWait(NOTIFY_START_BIT | NOTIFY_STOP_BIT, 0, NULL, portMAX_DELAY);

        if (s_stop_requested) {
            s_is_playing = false;
            continue;
        }

        char dir_path[128];
        snprintf(dir_path, sizeof(dir_path), "/sdcard/frames/%s", s_current_seq.name);

        s_current_seq.format = detect_format(dir_path);
        uint16_t frame_count = count_frames(dir_path, s_current_seq.format);
        if (frame_count == 0) {
            ESP_LOGW(TAG, "No frames for: %s", s_current_seq.name);
            s_is_playing = false;
            continue;
        }

        s_current_seq.frame_count = frame_count;
        TickType_t frame_ticks = pdMS_TO_TICKS(1000 / s_current_seq.fps);
        if (frame_ticks == 0) frame_ticks = 1;

        s_is_playing = true;
        s_display_buf = s_frame_buf_a;
        s_read_buf = s_frame_buf_b;
        s_prefetch_valid = false;

        ESP_LOGI(TAG, "Playing: %s (%d frames, %s, %d fps)",
                 s_current_seq.name, frame_count,
                 s_current_seq.format == FRAME_FORMAT_RGB565 ? "RAW" : "JPEG",
                 s_current_seq.fps);

        char file_path[192];
        uint32_t frame_len = 0;

        build_frame_path(file_path, sizeof(file_path), dir_path, 1, s_current_seq.format);
        frame_len = read_frame_file(file_path, s_display_buf, FRAME_BUF_SIZE);
        if (frame_len == 0) {
            ESP_LOGW(TAG, "Cannot read first frame for: %s", s_current_seq.name);
            s_is_playing = false;
            continue;
        }

        uint16_t frame_idx = 0;

        while (!s_stop_requested) {
            TickType_t tick_start = xTaskGetTickCount();

            uint16_t next_idx = frame_idx + 1;
            if (next_idx >= frame_count) {
                next_idx = s_current_seq.loop ? 0 : 0xFFFF;
            }

            if (next_idx != 0xFFFF && !s_prefetch_valid) {
                build_frame_path(file_path, sizeof(file_path), dir_path, next_idx + 1, s_current_seq.format);
                s_prefetch_len = read_frame_file(file_path, s_read_buf, FRAME_BUF_SIZE);
                s_prefetch_idx = next_idx;
                s_prefetch_valid = (s_prefetch_len > 0);
            }

            if (s_frame_cb) {
                s_frame_cb(s_display_buf, frame_len, s_current_seq.format);
            }

            frame_idx++;
            if (frame_idx >= frame_count) {
                if (s_current_seq.loop) {
                    frame_idx = 0;
                } else {
                    break;
                }
            }

            if (s_prefetch_valid && s_prefetch_idx == frame_idx) {
                uint8_t *tmp = s_display_buf;
                s_display_buf = s_read_buf;
                s_read_buf = tmp;
                frame_len = s_prefetch_len;
                s_prefetch_valid = false;
            } else {
                build_frame_path(file_path, sizeof(file_path), dir_path, frame_idx + 1, s_current_seq.format);
                frame_len = read_frame_file(file_path, s_display_buf, FRAME_BUF_SIZE);
                if (frame_len == 0) {
                    if (s_current_seq.loop) {
                        frame_idx = 0;
                        continue;
                    } else {
                        break;
                    }
                }
            }

            uint16_t next_prefetch = frame_idx + 1;
            if (next_prefetch >= frame_count) {
                next_prefetch = s_current_seq.loop ? 0 : 0xFFFF;
            }
            if (next_prefetch != 0xFFFF && !s_prefetch_valid) {
                build_frame_path(file_path, sizeof(file_path), dir_path, next_prefetch + 1, s_current_seq.format);
                s_prefetch_len = read_frame_file(file_path, s_read_buf, FRAME_BUF_SIZE);
                s_prefetch_idx = next_prefetch;
                s_prefetch_valid = (s_prefetch_len > 0);
            }

            TickType_t elapsed = xTaskGetTickCount() - tick_start;
            if (elapsed < frame_ticks) {
                vTaskDelay(frame_ticks - elapsed);
            }
        }

        s_is_playing = false;

        if (!s_stop_requested && s_done_cb) {
            s_done_cb(s_current_seq.name);
        }
    }
}

esp_err_t frame_player_init(void)
{
    s_seq_mux = xSemaphoreCreateMutex();
    if (!s_seq_mux) return ESP_ERR_NO_MEM;

    s_frame_buf_a = heap_caps_malloc(FRAME_BUF_SIZE, MALLOC_CAP_SPIRAM);
    s_frame_buf_b = heap_caps_malloc(FRAME_BUF_SIZE, MALLOC_CAP_SPIRAM);
    if (!s_frame_buf_a || !s_frame_buf_b) {
        ESP_LOGE(TAG, "Failed to alloc double frame buffers (%d bytes each)", FRAME_BUF_SIZE);
        return ESP_ERR_NO_MEM;
    }

    BaseType_t ret = xTaskCreatePinnedToCore(player_task, "frame_player",
                                               8192, NULL, 5, &s_task, 1);
    if (ret != pdPASS) {
        ESP_LOGE(TAG, "Failed to create player task");
        return ESP_ERR_NO_MEM;
    }

    ESP_LOGI(TAG, "Frame player initialized (double-buf, %d bytes each)", FRAME_BUF_SIZE);
    return ESP_OK;
}

esp_err_t frame_player_start(const char *sequence_name, uint16_t fps, bool loop)
{
    if (!sequence_name) return ESP_ERR_INVALID_ARG;

    xSemaphoreTake(s_seq_mux, portMAX_DELAY);

    s_stop_requested = true;
    xTaskNotify(s_task, NOTIFY_STOP_BIT, eSetBits);

    vTaskDelay(pdMS_TO_TICKS(5));

    strncpy(s_current_seq.name, sequence_name, sizeof(s_current_seq.name) - 1);
    s_current_seq.name[sizeof(s_current_seq.name) - 1] = '\0';
    s_current_seq.fps = fps > 0 ? fps : 15;
    s_current_seq.loop = loop;
    s_current_seq.frame_count = 0;

    s_stop_requested = false;

    xTaskNotify(s_task, NOTIFY_START_BIT, eSetBits);

    xSemaphoreGive(s_seq_mux);
    return ESP_OK;
}

esp_err_t frame_player_stop(void)
{
    s_stop_requested = true;
    s_is_playing = false;

    if (s_task) {
        xTaskNotify(s_task, NOTIFY_STOP_BIT, eSetBits);
    }

    return ESP_OK;
}

bool frame_player_is_playing(void)
{
    return s_is_playing;
}

void frame_player_register_frame_cb(frame_player_frame_cb_t cb)
{
    s_frame_cb = cb;
}

void frame_player_register_done_cb(frame_player_done_cb_t cb)
{
    s_done_cb = cb;
}
