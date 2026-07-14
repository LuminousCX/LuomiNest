#include "chat_ui.h"
#include "esp_log.h"
#include <string.h>

static const char *TAG = "chat_ui";

#define COLOR_BG_PANEL      lv_color_hex(0x0F0F1A)
#define COLOR_BUBBLE_USER   lv_color_hex(0x1A4A5A)
#define COLOR_BUBBLE_ASSIST lv_color_hex(0x1E1E32)
#define COLOR_TEXT_USER     lv_color_hex(0xD0F0F0)
#define COLOR_TEXT_ASSIST   lv_color_hex(0xC8C8E0)
#define COLOR_SCROLLBAR     lv_color_hex(0x3A3A5C)
#define COLOR_SCROLLBAR_ACT lv_color_hex(0x5A5A8C)

#define BUBBLE_RADIUS       12
#define BUBBLE_PAD_HOR      12
#define BUBBLE_PAD_VER      8
#define MSG_GAP             6
#define LIST_PAD            10

static lv_style_t style_sb;
static lv_style_t style_sb_scrolled;
static bool s_styles_initialized = false;
static int32_t s_panel_width = 0;

static void init_scrollbar_styles(void)
{
    if (s_styles_initialized) return;
    s_styles_initialized = true;

    static const lv_style_prop_t props[] = {LV_STYLE_BG_OPA, LV_STYLE_WIDTH, 0};
    static lv_style_transition_dsc_t trans;
    lv_style_transition_dsc_init(&trans, props, lv_anim_path_linear, 200, 0, NULL);

    lv_style_init(&style_sb);
    lv_style_set_width(&style_sb, 2);
    lv_style_set_pad_right(&style_sb, 3);
    lv_style_set_pad_ver(&style_sb, 4);
    lv_style_set_radius(&style_sb, 1);
    lv_style_set_bg_opa(&style_sb, LV_OPA_40);
    lv_style_set_bg_color(&style_sb, COLOR_SCROLLBAR);
    lv_style_set_transition(&style_sb, &trans);

    lv_style_init(&style_sb_scrolled);
    lv_style_set_width(&style_sb_scrolled, 3);
    lv_style_set_bg_opa(&style_sb_scrolled, LV_OPA_80);
    lv_style_set_bg_color(&style_sb_scrolled, COLOR_SCROLLBAR_ACT);
}

static void create_bubble(lv_obj_t *parent, chat_msg_role_t role, const char *text)
{
    lv_obj_t *wrapper = lv_obj_create(parent);
    lv_obj_remove_style_all(wrapper);
    lv_obj_set_size(wrapper, lv_pct(100), LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(wrapper, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(wrapper, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_START);
    lv_obj_set_style_pad_hor(wrapper, LIST_PAD, 0);
    lv_obj_set_style_pad_ver(wrapper, MSG_GAP, 0);

    lv_obj_t *spacer_left = lv_obj_create(wrapper);
    lv_obj_remove_style_all(spacer_left);
    lv_obj_set_flex_grow(spacer_left, role == CHAT_MSG_USER ? 1 : 0);
    lv_obj_set_size(spacer_left, 0, 0);

    int32_t avail_w = s_panel_width - LIST_PAD * 4;
    int32_t max_bubble_w = avail_w * 78 / 100;
    int32_t max_label_w = max_bubble_w - BUBBLE_PAD_HOR * 2;
    if (max_label_w < 60) max_label_w = 60;

    lv_obj_t *bubble = lv_obj_create(wrapper);
    lv_obj_remove_style_all(bubble);
    lv_obj_set_size(bubble, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_set_style_max_width(bubble, max_bubble_w, 0);
    lv_obj_set_style_bg_color(bubble,
        role == CHAT_MSG_USER ? COLOR_BUBBLE_USER : COLOR_BUBBLE_ASSIST, 0);
    lv_obj_set_style_bg_opa(bubble, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(bubble, BUBBLE_RADIUS, 0);
    lv_obj_set_style_pad_hor(bubble, BUBBLE_PAD_HOR, 0);
    lv_obj_set_style_pad_ver(bubble, BUBBLE_PAD_VER, 0);
    lv_obj_set_style_border_width(bubble, 0, 0);

    lv_obj_t *label = lv_label_create(bubble);
    lv_label_set_text(label, text);
    lv_obj_set_style_text_color(label,
        role == CHAT_MSG_USER ? COLOR_TEXT_USER : COLOR_TEXT_ASSIST, 0);
    lv_obj_set_style_text_font(label, &lv_font_montserrat_14, 0);
    lv_label_set_long_mode(label, LV_LABEL_LONG_WRAP);
    lv_obj_set_style_max_width(label, max_label_w, 0);

    lv_obj_t *spacer_right = lv_obj_create(wrapper);
    lv_obj_remove_style_all(spacer_right);
    lv_obj_set_flex_grow(spacer_right, role == CHAT_MSG_ASSISTANT ? 1 : 0);
    lv_obj_set_size(spacer_right, 0, 0);
}

esp_err_t chat_ui_init(chat_ui_t *chat, lv_obj_t *parent, int32_t width, int32_t height)
{
    if (!chat || !parent) return ESP_ERR_INVALID_ARG;

    memset(chat, 0, sizeof(chat_ui_t));

    s_panel_width = width;

    chat->panel = lv_obj_create(parent);
    lv_obj_remove_style_all(chat->panel);
    lv_obj_set_size(chat->panel, width, height);
    lv_obj_set_style_bg_color(chat->panel, COLOR_BG_PANEL, LV_PART_MAIN);
    lv_obj_set_style_bg_opa(chat->panel, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_pos(chat->panel, 0, 0);
    lv_obj_set_scrollbar_mode(chat->panel, LV_SCROLLBAR_MODE_OFF);
    lv_obj_clear_flag(chat->panel, LV_OBJ_FLAG_SCROLLABLE);

    chat->msg_list = lv_obj_create(chat->panel);
    lv_obj_remove_style_all(chat->msg_list);
    lv_obj_set_size(chat->msg_list, lv_pct(100), lv_pct(100));
    lv_obj_set_style_bg_color(chat->msg_list, COLOR_BG_PANEL, LV_PART_MAIN);
    lv_obj_set_style_bg_opa(chat->msg_list, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_pad_all(chat->msg_list, LIST_PAD, 0);
    lv_obj_set_flex_flow(chat->msg_list, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(chat->msg_list, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_END, LV_FLEX_ALIGN_START);
    lv_obj_set_scrollbar_mode(chat->msg_list, LV_SCROLLBAR_MODE_ACTIVE);
    lv_obj_set_scroll_dir(chat->msg_list, LV_DIR_VER);

    init_scrollbar_styles();
    lv_obj_remove_style(chat->msg_list, NULL, LV_PART_SCROLLBAR | LV_STATE_ANY);
    lv_obj_add_style(chat->msg_list, &style_sb, LV_PART_SCROLLBAR);
    lv_obj_add_style(chat->msg_list, &style_sb_scrolled, LV_PART_SCROLLBAR | LV_STATE_SCROLLED);

    chat->cont = chat->panel;
    chat->count = 0;

    ESP_LOGI(TAG, "Chat UI initialized (%dx%d)", (int)width, (int)height);
    return ESP_OK;
}

esp_err_t chat_ui_add_message(chat_ui_t *chat, chat_msg_role_t role, const char *text)
{
    if (!chat || !text) return ESP_ERR_INVALID_ARG;

    if (chat->count >= CHAT_MAX_MESSAGES) {
        chat_ui_clear(chat);
    }

    uint16_t idx = chat->count;
    chat->messages[idx].role = role;
    strncpy(chat->messages[idx].text, text, CHAT_MSG_MAX_LEN - 1);
    chat->messages[idx].text[CHAT_MSG_MAX_LEN - 1] = '\0';
    chat->count++;

    create_bubble(chat->msg_list, role, chat->messages[idx].text);

    chat_ui_scroll_to_bottom(chat);

    return ESP_OK;
}

void chat_ui_scroll_to_bottom(chat_ui_t *chat)
{
    if (!chat || !chat->msg_list) return;
    lv_obj_scroll_to_y(chat->msg_list, LV_COORD_MAX, LV_ANIM_ON);
}

void chat_ui_clear(chat_ui_t *chat)
{
    if (!chat || !chat->msg_list) return;

    lv_obj_clean(chat->msg_list);
    chat->count = 0;
}

void chat_ui_add_demo_messages(chat_ui_t *chat)
{
    if (!chat) return;

    static const struct { chat_msg_role_t role; const char *text; } demos[] = {
        { CHAT_MSG_ASSISTANT, "Hello! I'm LuomiNest, your smart assistant." },
        { CHAT_MSG_USER,     "Hi, what can you do?" },
        { CHAT_MSG_ASSISTANT, "I can help you with smart home control, information queries, schedule management, and more." },
        { CHAT_MSG_USER,     "That sounds great! Can you turn on the living room light?" },
        { CHAT_MSG_ASSISTANT, "Sure! Living room light has been turned on." },
        { CHAT_MSG_USER,     "Thanks! What's the weather like today?" },
        { CHAT_MSG_ASSISTANT, "Today is sunny, 26 degrees, humidity 45%, suitable for going out." },
        { CHAT_MSG_USER,     "Any suggestions for dinner?" },
        { CHAT_MSG_ASSISTANT, "How about trying Italian pasta? There's a great restaurant 500m away." },
        { CHAT_MSG_USER,     "Good idea! Set a reminder for 6pm." },
        { CHAT_MSG_ASSISTANT, "Done! I'll remind you at 6pm for dinner." },
        { CHAT_MSG_USER,     "Can you play some light music?" },
        { CHAT_MSG_ASSISTANT, "Playing 'Peaceful Piano' playlist for you now." },
        { CHAT_MSG_USER,     "Perfect, you're so helpful!" },
        { CHAT_MSG_ASSISTANT, "Thank you! I'm always here whenever you need me." },
    };

    for (int i = 0; i < sizeof(demos) / sizeof(demos[0]); i++) {
        chat_ui_add_message(chat, demos[i].role, demos[i].text);
    }
}
