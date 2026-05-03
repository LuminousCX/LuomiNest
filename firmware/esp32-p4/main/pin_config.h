#ifndef PIN_CONFIG_H
#define PIN_CONFIG_H

#include "driver/gpio.h"

#define LCD_RST_PIN         GPIO_NUM_0
#define LCD_BL_PIN          GPIO_NUM_23

#define SDMMC_CLK_PIN       GPIO_NUM_43
#define SDMMC_CMD_PIN       GPIO_NUM_44
#define SDMMC_D0_PIN        GPIO_NUM_39
#define SDMMC_D1_PIN        GPIO_NUM_40
#define SDMMC_D2_PIN        GPIO_NUM_41
#define SDMMC_D3_PIN        GPIO_NUM_42

#define SD_LDO_CHAN         4

#define HOSTED_SDIO_CLK     GPIO_NUM_12
#define HOSTED_SDIO_CMD     GPIO_NUM_13
#define HOSTED_SDIO_D0      GPIO_NUM_11
#define HOSTED_SDIO_D1      GPIO_NUM_10
#define HOSTED_SDIO_D2      GPIO_NUM_9
#define HOSTED_SDIO_D3      GPIO_NUM_8
#define HOSTED_RESET_SLAVE  GPIO_NUM_54

#define ETH_MDC_PIN         GPIO_NUM_31
#define ETH_MDIO_PIN        GPIO_NUM_52
#define ETH_PHY_RST_PIN     GPIO_NUM_51

#endif
