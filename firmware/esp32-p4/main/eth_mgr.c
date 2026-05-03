#include "eth_mgr.h"
#include "pin_config.h"
#include "esp_log.h"
#include "esp_eth.h"
#include "esp_eth_mac_esp.h"
#include "esp_eth_phy.h"
#include "esp_eth_netif_glue.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "nvs_flash.h"

static const char *TAG = "eth_mgr";

static esp_eth_handle_t s_eth_handle = NULL;
static esp_eth_netif_glue_handle_t s_eth_glue = NULL;
static esp_netif_t *s_eth_netif = NULL;
static eth_connected_cb_t s_connected_cb = NULL;
static eth_disconnected_cb_t s_disconnected_cb = NULL;
static bool s_connected = false;
static bool s_initialized = false;
static char s_ip_str[16] = {0};

static void eth_event_handler(void *arg, esp_event_base_t event_base,
                               int32_t event_id, void *event_data)
{
    if (event_base == ETH_EVENT) {
        if (event_id == ETHERNET_EVENT_CONNECTED) {
            ESP_LOGI(TAG, "Ethernet Link Up");
        } else if (event_id == ETHERNET_EVENT_DISCONNECTED) {
            ESP_LOGW(TAG, "Ethernet Link Down");
            s_connected = false;
            s_ip_str[0] = '\0';
            if (s_disconnected_cb) s_disconnected_cb();
        } else if (event_id == ETHERNET_EVENT_START) {
            ESP_LOGI(TAG, "Ethernet Started");
        } else if (event_id == ETHERNET_EVENT_STOP) {
            ESP_LOGI(TAG, "Ethernet Stopped");
        }
    }
}

static void got_ip_event_handler(void *arg, esp_event_base_t event_base,
                                  int32_t event_id, void *event_data)
{
    if (event_base == IP_EVENT && event_id == IP_EVENT_ETH_GOT_IP) {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *)event_data;
        snprintf(s_ip_str, sizeof(s_ip_str), IPSTR, IP2STR(&event->ip_info.ip));
        ESP_LOGI(TAG, "Ethernet Got IP:%s", s_ip_str);
        s_connected = true;
        if (s_connected_cb) s_connected_cb();
    }
}

esp_err_t eth_mgr_init(void)
{
    if (s_initialized) return ESP_OK;

    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "NVS init failed: 0x%x", ret);
        return ret;
    }

    ret = esp_netif_init();
    if (ret != ESP_OK && ret != ESP_ERR_INVALID_STATE) {
        ESP_LOGE(TAG, "Netif init failed: 0x%x", ret);
        return ret;
    }

    ret = esp_event_loop_create_default();
    if (ret != ESP_OK && ret != ESP_ERR_INVALID_STATE) {
        ESP_LOGE(TAG, "Event loop create failed: 0x%x", ret);
        return ret;
    }

    ESP_ERROR_CHECK(esp_event_handler_register(ETH_EVENT, ESP_EVENT_ANY_ID, &eth_event_handler, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_ETH_GOT_IP, &got_ip_event_handler, NULL));

    esp_netif_config_t cfg = ESP_NETIF_DEFAULT_ETH();
    s_eth_netif = esp_netif_new(&cfg);

    eth_mac_config_t mac_config = ETH_MAC_DEFAULT_CONFIG();
    eth_esp32_emac_config_t esp32_emac_config = ETH_ESP32_EMAC_DEFAULT_CONFIG();
    esp32_emac_config.smi_gpio.mdc_num = ETH_MDC_PIN;
    esp32_emac_config.smi_gpio.mdio_num = ETH_MDIO_PIN;

    esp_eth_mac_t *mac = esp_eth_mac_new_esp32(&esp32_emac_config, &mac_config);
    if (!mac) {
        ESP_LOGE(TAG, "Failed to create EMAC");
        return ESP_FAIL;
    }

    eth_phy_config_t phy_config = ETH_PHY_DEFAULT_CONFIG();
    phy_config.phy_addr = CONFIG_LN_ETH_PHY_ADDR;
    phy_config.reset_gpio_num = ETH_PHY_RST_PIN;

    esp_eth_phy_t *phy = NULL;
#if CONFIG_LN_ETH_PHY_IP101
    phy = esp_eth_phy_new_ip101(&phy_config);
#elif CONFIG_LN_ETH_PHY_LAN8720
    phy = esp_eth_phy_new_lan87xx(&phy_config);
#elif CONFIG_LN_ETH_PHY_RTL8201
    phy = esp_eth_phy_new_rtl8201(&phy_config);
#elif CONFIG_LN_ETH_PHY_DP83848
    phy = esp_eth_phy_new_dp83848(&phy_config);
#elif CONFIG_LN_ETH_PHY_KSZ80XX
    phy = esp_eth_phy_new_ksz80xx(&phy_config);
#else
    phy = esp_eth_phy_new_generic(&phy_config);
#endif

    if (!phy) {
        ESP_LOGE(TAG, "Failed to create PHY");
        return ESP_FAIL;
    }

    esp_eth_config_t eth_config = ETH_DEFAULT_CONFIG(mac, phy);
    ESP_ERROR_CHECK(esp_eth_driver_install(&eth_config, &s_eth_handle));

    s_eth_glue = esp_eth_new_netif_glue(s_eth_handle);
    ESP_ERROR_CHECK(esp_netif_attach(s_eth_netif, s_eth_glue));

    s_initialized = true;
    ESP_LOGI(TAG, "Ethernet manager initialized (EMAC + RMII, PHY addr=%d)", CONFIG_LN_ETH_PHY_ADDR);
    return ESP_OK;
}

esp_err_t eth_mgr_start(void)
{
    if (!s_initialized || !s_eth_handle) return ESP_ERR_INVALID_STATE;
    ESP_LOGI(TAG, "Starting Ethernet...");
    return esp_eth_start(s_eth_handle);
}

esp_err_t eth_mgr_stop(void)
{
    if (!s_initialized || !s_eth_handle) return ESP_ERR_INVALID_STATE;
    return esp_eth_stop(s_eth_handle);
}

bool eth_mgr_is_connected(void)
{
    return s_connected;
}

esp_err_t eth_mgr_register_connected_cb(eth_connected_cb_t cb)
{
    s_connected_cb = cb;
    return ESP_OK;
}

esp_err_t eth_mgr_register_disconnected_cb(eth_disconnected_cb_t cb)
{
    s_disconnected_cb = cb;
    return ESP_OK;
}

void eth_mgr_get_ip_str(char *buf, size_t buf_len)
{
    if (!buf || buf_len == 0) return;
    snprintf(buf, buf_len, "%s", s_ip_str);
}
