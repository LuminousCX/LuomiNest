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

#define FRAME_BUF_SIZE (200 * 1024)

typedef struct {
    char name[32];
    uint16_t frame_count;
    uint16_t fps;
    bool loop;
} sequence_info_t;

static TaskHandle_t s_task = NULL;
static volatile bool s_stop_requested = false;
static volatile bool s_is_playing = false;
static sequence_info_t s_current_seq = {0};
static frame_player_frame_cb_t s_frame_cb = NULL;
static frame_player_done_cb_t s_done_cb = NULL;
static SemaphoreHandle_t s_seq_mux = NULL;
static uint8_t *s_frame_buf = NULL;

static bool file_exists(const char *path)
{
    struct stat st;
    return (stat(path, &st) == 0);
}

static uint16_t count_frames(const char *dir_path)
{
    uint16_t count = 0;
    char file_path[192];
    while (true) {
        snprintf(file_path, sizeof(file_path), "%s/%04d.jpg", dir_path, count + 1);
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

        uint16_t frame_count = count_frames(dir_path);
        if (frame_count == 0) {
            ESP_LOGW(TAG, "No frames for: %s", s_current_seq.name);
            s_is_playing = false;
            continue;
        }

        s_current_seq.frame_count = frame_count;
        TickType_t frame_ticks = pdMS_TO_TICKS(1000 / s_current_seq.fps);
        if (frame_ticks == 0) frame_ticks = 1;

        s_is_playing = true;
        uint16_t frame_idx = 0;

        while (!s_stop_requested) {
            TickType_t tick_start = xTaskGetTickCount();

            char file_path[192];
            snprintf(file_path, sizeof(file_path), "%s/%04d.jpg", dir_path, frame_idx + 1);

            uint32_t frame_len = read_frame_file(file_path, s_frame_buf, FRAME_BUF_SIZE);

            if (frame_len == 0) {
                if (frame_idx == 0) {
                    ESP_LOGW(TAG, "Cannot read frame 1 for: %s", s_current_seq.name);
                    break;
                }
                if (s_current_seq.loop) {
                    frame_idx = 0;
                    continue;
                } else {
                    break;
                }
            }

            if (s_frame_cb) {
                s_frame_cb(s_frame_buf, frame_len);
            }

            frame_idx++;
            if (frame_idx >= frame_count) {
                if (s_current_seq.loop) {
                    frame_idx = 0;
                } else {
                    break;
                }
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

    s_frame_buf = heap_caps_malloc(FRAME_BUF_SIZE, MALLOC_CAP_SPIRAM);
    if (!s_frame_buf) {
        ESP_LOGE(TAG, "Failed to alloc frame buffer (%d bytes)", FRAME_BUF_SIZE);
        return ESP_ERR_NO_MEM;
    }

    BaseType_t ret = xTaskCreatePinnedToCore(player_task, "frame_player",
                                               6144, NULL, 5, &s_task, 1);
    if (ret != pdPASS) {
        ESP_LOGE(TAG, "Failed to create player task");
        return ESP_ERR_NO_MEM;
    }

    ESP_LOGI(TAG, "Frame player initialized (buf=%d bytes)", FRAME_BUF_SIZE);
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
