#idf_component_register(
#    SRCS "main.c"
#    INCLUDE_DIRS "."
#)
# The above lines are intentionally commented. This project uses the more common
# approach of using idf_component_register in the top-level CMakeLists.txt.

idf_component_register(
    SRCS "main.c"
    INCLUDE_DIRS "."
    REQUIRES
        driver
        esp_wifi
        esp_netif
        esp_event
        nvs_flash
        mqtt
        lwip
    PRIV_REQUIRES
        esp_timer
)
