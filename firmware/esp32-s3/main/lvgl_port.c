#include "lvgl_port.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "esp_timer.h"
#include "pin_config.h"

static const char *TAG = "lvgl_port";

static st7735s_handle_t *s_lcd = NULL;
static SemaphoreHandle_t s_lvgl_mux = NULL;

static void lvgl_flush_cb(lv_display_t *disp, const lv_area_t *area, uint8_t *px_map)
{
    int w = lv_area_get_width(area);
    int h = lv_area_get_height(area);

    lv_draw_sw_rgb565_swap(px_map, w * h);

    st7735s_draw_bitmap(s_lcd, area->x1, area->y1, w, h, (uint16_t *)px_map);
    lv_display_flush_ready(disp);
}

static void lvgl_tick_cb(void *arg)
{
    (void)arg;
    lv_tick_inc(2);
}

void lvgl_port_lock(void)
{
    if (s_lvgl_mux) {
        xSemaphoreTake(s_lvgl_mux, portMAX_DELAY);
    }
}

void lvgl_port_unlock(void)
{
    if (s_lvgl_mux) {
        xSemaphoreGive(s_lvgl_mux);
    }
}

esp_err_t lvgl_port_init(st7735s_handle_t *lcd_handle, lvgl_port_t *port)
{
    s_lcd = lcd_handle;

    s_lvgl_mux = xSemaphoreCreateMutex();
    if (!s_lvgl_mux) return ESP_ERR_NO_MEM;

    lv_init();

    port->lcd_handle = lcd_handle;
    port->display = lv_display_create(ST7735S_WIDTH, ST7735S_HEIGHT);
    lv_display_set_flush_cb(port->display, lvgl_flush_cb);
    lv_display_set_color_format(port->display, LV_COLOR_FORMAT_RGB565);

    size_t buf_pixels = ST7735S_WIDTH * ST7735S_HEIGHT / 10;
    size_t buf_size = buf_pixels * 2;

    void *buf1 = heap_caps_malloc(buf_size, MALLOC_CAP_DMA | MALLOC_CAP_8BIT);
    void *buf2 = heap_caps_malloc(buf_size, MALLOC_CAP_DMA | MALLOC_CAP_8BIT);
    if (!buf1 || !buf2) {
        ESP_LOGE(TAG, "Failed to allocate LVGL buffers");
        return ESP_ERR_NO_MEM;
    }

    lv_display_set_buffers(port->display, buf1, buf2, buf_size,
                           LV_DISPLAY_RENDER_MODE_PARTIAL);

    port->screen = lv_screen_active();

    const esp_timer_create_args_t tick_args = {
        .callback = lvgl_tick_cb,
        .name = "lvgl_tick",
    };
    esp_timer_handle_t tick_timer;
    esp_timer_create(&tick_args, &tick_timer);
    esp_timer_start_periodic(tick_timer, 2000);

    ESP_LOGI(TAG, "LVGL port initialized (%dx%d, buf=%d bytes)", ST7735S_WIDTH, ST7735S_HEIGHT, buf_size);
    return ESP_OK;
}
