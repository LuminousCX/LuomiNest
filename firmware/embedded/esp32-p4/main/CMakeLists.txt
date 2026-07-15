idf_component_register(
    SRCS "app_main.c"
    INCLUDE_DIRS "."
    REQUIRES bsp drivers app esp_lvgl_port
    PRIV_REQUIRES nvs_flash
)
