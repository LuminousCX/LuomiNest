/**
 * LuomiNest P4 - APP CHAT (LVGL 9 气泡)
 * 从旧 esp32-p4/main/chat_ui.c 移植深色主题样式, 适配新分层架构:
 *   - 接受 parent panel (由 app_ui 传入左侧 560px 容器)
 *   - 深色气泡: 用户 #1A4A5A, AI #1E1E32
 *   - 自定义滚动条 (2px→3px, 200ms 过渡动画)
 *   - lvgl_port_lock 保护所有 LVGL API
 *   - mock 定时器 4s/条, 8 条英中混合消息循环
 *
 * 数据流:
 *   esp_timer (4s) → queue → chat_task → lvgl_port_lock → create_bubble → unlock
 */

#include "app_chat.h"
#include "app_status.h"

#include "esp_log.h"
#include "esp_check.h"
#include "esp_timer.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

#include "esp_lvgl_port.h"
#include "lvgl.h"

#include <string.h>
#include <stdlib.h>

static const char *TAG = "app_chat";

/* === 颜色 (旧工程暗色主题, 与 chat_ui.c 一致) === */
#define COLOR_BG_PANEL      lv_color_hex(0x0F0F1A)
#define COLOR_BUBBLE_USER   lv_color_hex(0x1A4A5A)
#define COLOR_BUBBLE_ASSIST lv_color_hex(0x1E1E32)
#define COLOR_TEXT_USER     lv_color_hex(0xD0F0F0)
#define COLOR_TEXT_ASSIST   lv_color_hex(0xC8C8E0)
#define COLOR_SCROLLBAR     lv_color_hex(0x3A3A5C)
#define COLOR_SCROLLBAR_ACT lv_color_hex(0x5A5A8C)

/* === 几何 === */
#define BUBBLE_RADIUS       0    /* 无圆角: 减少滑动时渲染开销 */
#define BUBBLE_PAD_HOR      12
#define BUBBLE_PAD_VER      8
#define MSG_GAP             6
#define LIST_PAD            10
#define CHAT_HISTORY_MAX    64
#define CHAT_MOCK_PERIOD_MS 4000
#define CHAT_QUEUE_DEPTH    8

/* === Mock 消息 === */
typedef struct {
    chat_role_t role;
    const char *text;
} mock_msg_t;

static const mock_msg_t MOCK_MSGS[] = {
    {CHAT_ROLE_AI,    "Hello! I'm LuomiNest, your smart assistant."},
    {CHAT_ROLE_USER,  "Hi, what can you do?"},
    {CHAT_ROLE_AI,    "I can help you with smart home control, information queries, and more."},
    {CHAT_ROLE_USER,  "That sounds great! Can you turn on the living room light?"},
    {CHAT_ROLE_AI,    "Sure! Living room light has been turned on."},
    {CHAT_ROLE_USER,  "Thanks! What's the weather like today?"},
    {CHAT_ROLE_AI,    "Today is sunny, 26 degrees, suitable for going out."},
    {CHAT_ROLE_USER,  "Perfect, you're so helpful!"},
};
#define MOCK_COUNT (sizeof(MOCK_MSGS) / sizeof(MOCK_MSGS[0]))

/* === 队列消息 === */
typedef struct {
    chat_role_t role;
    char       *text;   /* strdup, 消费方 free */
} queue_msg_t;

/* === 全局 === */
static int32_t          s_panel_width  = 0;
static lv_obj_t        *s_msg_list     = NULL;
static lv_style_t       s_style_sb;
static lv_style_t       s_style_sb_scrolled;
static QueueHandle_t    s_msg_queue    = NULL;
static TaskHandle_t     s_chat_task_h  = NULL;
static esp_timer_handle_t s_mock_timer = NULL;
static uint32_t         s_msg_count    = 0;
static int              s_mock_idx     = 0;
static bool             s_started      = false;

/* === CJK 检测 (只 warn 一次) === */
static bool s_cjk_warned = false;
static void maybe_warn_cjk(const char *text)
{
    if (s_cjk_warned) return;
    for (const uint8_t *p = (const uint8_t *)text; *p; p++) {
        if (*p >= 0xE0 && *p <= 0xEF) {
            ESP_LOGW(TAG, "CJK char detected, will render as □ (no CJK font)");
            s_cjk_warned = true;
            return;
        }
    }
}

/* === 滚动条样式 (旧工程 chat_ui.c 一致) === */
static void init_scrollbar_styles(void)
{
    static const lv_style_prop_t props[] = {LV_STYLE_BG_OPA, LV_STYLE_WIDTH, 0};
    static lv_style_transition_dsc_t trans;
    lv_style_transition_dsc_init(&trans, props, lv_anim_path_linear, 200, 0, NULL);

    lv_style_init(&s_style_sb);
    lv_style_set_width(&s_style_sb, 2);
    lv_style_set_pad_right(&s_style_sb, 3);
    lv_style_set_pad_ver(&s_style_sb, 4);
    lv_style_set_radius(&s_style_sb, 1);
    lv_style_set_bg_opa(&s_style_sb, LV_OPA_40);
    lv_style_set_bg_color(&s_style_sb, COLOR_SCROLLBAR);
    lv_style_set_transition(&s_style_sb, &trans);

    lv_style_init(&s_style_sb_scrolled);
    lv_style_set_width(&s_style_sb_scrolled, 3);
    lv_style_set_bg_opa(&s_style_sb_scrolled, LV_OPA_80);
    lv_style_set_bg_color(&s_style_sb_scrolled, COLOR_SCROLLBAR_ACT);
}

/* === 创建一条气泡 (旧工程 chat_ui.c create_bubble 一致) === */
static void create_bubble(chat_role_t role, const char *text)
{
    maybe_warn_cjk(text);

    /* wrapper: 撑满宽度, 子项靠左/靠右 */
    lv_obj_t *wrapper = lv_obj_create(s_msg_list);
    lv_obj_remove_style_all(wrapper);
    lv_obj_set_size(wrapper, lv_pct(100), LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(wrapper, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(wrapper, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_START);
    lv_obj_set_style_pad_hor(wrapper, LIST_PAD, 0);
    lv_obj_set_style_pad_ver(wrapper, MSG_GAP, 0);

    /* spacer: 用户消息靠右, AI 消息靠左 */
    lv_obj_t *spacer_left = lv_obj_create(wrapper);
    lv_obj_remove_style_all(spacer_left);
    lv_obj_set_flex_grow(spacer_left, role == CHAT_ROLE_USER ? 1 : 0);
    lv_obj_set_size(spacer_left, 0, 0);

    /* 计算气泡最大宽度 */
    int32_t avail_w = s_panel_width - LIST_PAD * 4;
    int32_t max_bubble_w = avail_w * 78 / 100;
    int32_t max_label_w = max_bubble_w - BUBBLE_PAD_HOR * 2;
    if (max_label_w < 60) max_label_w = 60;

    /* bubble */
    lv_obj_t *bubble = lv_obj_create(wrapper);
    lv_obj_remove_style_all(bubble);
    lv_obj_set_size(bubble, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_style_max_width(bubble, max_bubble_w, 0);
    lv_obj_set_style_bg_color(bubble,
        role == CHAT_ROLE_USER ? COLOR_BUBBLE_USER : COLOR_BUBBLE_ASSIST, 0);
    lv_obj_set_style_bg_opa(bubble, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(bubble, BUBBLE_RADIUS, 0);
    lv_obj_set_style_pad_hor(bubble, BUBBLE_PAD_HOR, 0);
    lv_obj_set_style_pad_ver(bubble, BUBBLE_PAD_VER, 0);
    lv_obj_set_style_border_width(bubble, 0, 0);

    /* label */
    lv_obj_t *label = lv_label_create(bubble);
    lv_label_set_text(label, text);
    lv_obj_set_style_text_color(label,
        role == CHAT_ROLE_USER ? COLOR_TEXT_USER : COLOR_TEXT_ASSIST, 0);
    lv_obj_set_style_text_font(label, &lv_font_montserrat_14, 0);
    lv_label_set_long_mode(label, LV_LABEL_LONG_WRAP);
    lv_obj_set_style_max_width(label, max_label_w, 0);

    /* 右侧 spacer */
    lv_obj_t *spacer_right = lv_obj_create(wrapper);
    lv_obj_remove_style_all(spacer_right);
    lv_obj_set_flex_grow(spacer_right, role == CHAT_ROLE_AI ? 1 : 0);
    lv_obj_set_size(spacer_right, 0, 0);

    /* 滚到底 */
    lv_obj_scroll_to_y(s_msg_list, LV_COORD_MAX, LV_ANIM_ON);
    s_msg_count++;
}

/* === FIFO: 超 64 删最旧 === */
static void trim_history(void)
{
    while (lv_obj_get_child_cnt(s_msg_list) > CHAT_HISTORY_MAX) {
        lv_obj_delete(lv_obj_get_child(s_msg_list, 0));
    }
}

/* === chat_task: 唯一 LVGL API 执行点 === */
static void chat_task(void *arg)
{
    (void)arg;
    queue_msg_t msg;
    while (1) {
        if (xQueueReceive(s_msg_queue, &msg, portMAX_DELAY) == pdTRUE) {
            if (lvgl_port_lock(5000)) {
                create_bubble(msg.role, msg.text);
                trim_history();
                lvgl_port_unlock();
            } else {
                ESP_LOGW(TAG, "lvgl_port_lock timeout, msg dropped");
            }
            free(msg.text);
        }
    }
}

/* === mock_push_cb: esp_timer 回调, 发 queue === */
static void mock_push_cb(void *arg)
{
    (void)arg;
    const mock_msg_t *m = &MOCK_MSGS[s_mock_idx];
    queue_msg_t q = { .role = m->role, .text = strdup(m->text) };
    if (q.text == NULL) { ESP_LOGW(TAG, "strdup failed"); return; }
    if (xQueueSend(s_msg_queue, &q, 0) != pdTRUE) {
        free(q.text);
        return;
    }
    s_mock_idx = (s_mock_idx + 1) % MOCK_COUNT;
}

/* === 公共 API === */

esp_err_t app_chat_push_message(chat_role_t role, const char *text)
{
    if (s_msg_queue == NULL || text == NULL) return ESP_ERR_INVALID_STATE;
    queue_msg_t q = { .role = role, .text = strdup(text) };
    if (q.text == NULL) return ESP_ERR_NO_MEM;
    if (xQueueSend(s_msg_queue, &q, 0) != pdTRUE) {
        free(q.text);
        return ESP_ERR_TIMEOUT;
    }
    return ESP_OK;
}

uint32_t app_chat_get_count(void) { return s_msg_count; }

void app_chat_deinit(void)
{
    if (s_mock_timer) {
        esp_timer_stop(s_mock_timer);
        esp_timer_delete(s_mock_timer);
        s_mock_timer = NULL;
    }
    if (s_chat_task_h) { vTaskDelete(s_chat_task_h); s_chat_task_h = NULL; }
    if (s_msg_queue) {
        /* 排空队列, 释放 strdup 分配的 text */
        queue_msg_t msg;
        while (xQueueReceive(s_msg_queue, &msg, 0) == pdTRUE) {
            free(msg.text);
        }
        vQueueDelete(s_msg_queue);
        s_msg_queue = NULL;
    }
    s_started = false;
}

esp_err_t app_chat_init(lv_obj_t *parent)
{
    if (s_started) return ESP_OK;
    if (parent == NULL) return ESP_ERR_INVALID_ARG;

    if (!lvgl_port_lock(5000)) {
        ESP_LOGE(TAG, "lvgl_port_lock failed");
        return ESP_ERR_INVALID_STATE;
    }

    /* 读取 parent 宽度 (lock 后 layout 已就绪) */
    s_panel_width = lv_obj_get_width(parent);
    if (s_panel_width <= 0) {
        s_panel_width = 1024;  /* fallback: layout 未就绪时用屏幕宽度 */
    }

    /* 滚动条样式 */
    init_scrollbar_styles();

    /* chat panel (撑满 parent) */
    lv_obj_t *panel = lv_obj_create(parent);
    lv_obj_remove_style_all(panel);
    lv_obj_set_size(panel, lv_pct(100), lv_pct(100));
    lv_obj_set_style_bg_color(panel, COLOR_BG_PANEL, LV_PART_MAIN);
    lv_obj_set_style_bg_opa(panel, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_scrollbar_mode(panel, LV_SCROLLBAR_MODE_OFF);
    lv_obj_clear_flag(panel, LV_OBJ_FLAG_SCROLLABLE);

    /* msg_list: flex column, 自定义滚动条 */
    s_msg_list = lv_obj_create(panel);
    lv_obj_remove_style_all(s_msg_list);
    lv_obj_set_size(s_msg_list, lv_pct(100), lv_pct(100));
    lv_obj_set_style_bg_color(s_msg_list, COLOR_BG_PANEL, LV_PART_MAIN);
    lv_obj_set_style_bg_opa(s_msg_list, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_pad_all(s_msg_list, LIST_PAD, 0);
    lv_obj_set_flex_flow(s_msg_list, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(s_msg_list, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_END, LV_FLEX_ALIGN_START);
    lv_obj_set_scrollbar_mode(s_msg_list, LV_SCROLLBAR_MODE_ACTIVE);
    lv_obj_set_scroll_dir(s_msg_list, LV_DIR_VER);

    /* 应用自定义滚动条样式 */
    lv_obj_remove_style(s_msg_list, NULL, LV_PART_SCROLLBAR | LV_STATE_ANY);
    lv_obj_add_style(s_msg_list, &s_style_sb, LV_PART_SCROLLBAR);
    lv_obj_add_style(s_msg_list, &s_style_sb_scrolled, LV_PART_SCROLLBAR | LV_STATE_SCROLLED);

    lvgl_port_unlock();

    /* 队列 + chat task */
    s_msg_queue = xQueueCreate(CHAT_QUEUE_DEPTH, sizeof(queue_msg_t));
    if (s_msg_queue == NULL) return ESP_ERR_NO_MEM;

    BaseType_t ok = xTaskCreate(chat_task, "chat", 6144, NULL, 3, &s_chat_task_h);
    if (ok != pdPASS) return ESP_ERR_NO_MEM;

    /* mock timer (4s 周期) */
    esp_timer_create_args_t tcfg = {
        .callback = mock_push_cb,
        .name     = "chat_mock",
    };
    ESP_ERROR_CHECK(esp_timer_create(&tcfg, &s_mock_timer));
    ESP_ERROR_CHECK(esp_timer_start_periodic(s_mock_timer,
                    (uint64_t)CHAT_MOCK_PERIOD_MS * 1000));

    s_started = true;
    ESP_LOGI(TAG, "chat ready, panel %ldpx, mock %d ms, %d msgs",
             (long)s_panel_width, CHAT_MOCK_PERIOD_MS, (int)MOCK_COUNT);
    return ESP_OK;
}
